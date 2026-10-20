/* SPDX-License-Identifier: GPL-2.0 OR BSD-2-Clause-Views */
/* Copyright (c) 2026 jyohukuchan */
#include <linux/err.h>
#include <linux/module.h>
#include <linux/overflow.h>
#include <linux/slab.h>
#include "sq.h"
#include "sq_regs.h"
#include "cq_io.h"

struct as02_sq_slot {
    struct as02_user_mr *mr;
    struct as02_wqe work;
    bool used;
};
struct as02_sq {
    struct as02_sq_layout layout;
    void *ring;
    dma_addr_t dma;
    size_t bytes;
    struct as02_sq_slot *shadow;
    u64 producer, completed;
    u64 cancel_nonce;
    u32 pending, receive_pending, send_limit, receive_limit;
    struct as02_sq *receive;
    bool live, stopping, retiring, uncertain, retired, cancelling, cancel_proved;
};

static bool same_owner(const struct as02_sq_handle *a, const struct as02_sq_handle *b)
{
    return a->cookie == b->cookie && a->epoch == b->epoch && a->qpn == b->qpn && a->pd == b->pd;
}

static struct as02_sq *find_queue(struct as02_sq_pool *p, const struct as02_sq_handle *h)
{
    struct as02_sq *q;
    if (!h || h->qpn >= AS02_SQ_QPS)
        return NULL;
    q = p->slots[h->qpn];
    return q && same_owner(&q->layout.owner, h) ? q : NULL;
}

int as02_sq_pool_init(struct as02_sq_pool *p, struct as02_mr_pool *mrs, struct device *dev,
                      const struct as02_sq_hw_ops *hw, void *ctx, const u64 epochs[AS02_SQ_QPS])
{
    int ret;
    if (!p || p->initialized || !mrs || !dev || !hw || !epochs ||
        !hw->allocate || !hw->retire_and_drain || !hw->publish_producer || !hw->publish_cqe)
        return -EINVAL;
    ret = as02_mr_pool_get_client(mrs);
    if (ret)
        return ret;
    if (!try_module_get(THIS_MODULE)) {
        as02_mr_pool_put_client(mrs);
        return -ENODEV;
    }
    memset(p, 0, sizeof(*p));
    mutex_init(&p->lock);
    spin_lock_init(&p->fast_lock);
    p->mrs = mrs;
    p->dma_device = get_device(dev);
    p->hw = hw;
    p->hw_context = ctx;
    memcpy(p->epoch_watermark, epochs, sizeof(p->epoch_watermark));
    WRITE_ONCE(p->initialized, true);
    return 0;
}

int as02_sq_create(struct as02_sq_pool *p, u32 qpn, u16 pd, u64 epoch,
                   u32 log_depth, struct as02_sq_handle *out)
{
    struct as02_sq_alloc_proof proof = {};
    struct as02_sq *q;
    unsigned long flags;
    u64 last;
    int ret;
    if (out)
        memset(out, 0, sizeof(*out));
    if (!p || !READ_ONCE(p->initialized) || !out || qpn >= AS02_SQ_QPS || log_depth < 1 || log_depth > 8)
        return -EINVAL;
    mutex_lock(&p->lock);
    if (p->stopping || p->slots[qpn] || (!pd && READ_ONCE(p->mrs->pd_zero_reserved))) {
        ret = -EBUSY;
        goto unlock;
    }
    if (!epoch || epoch <= p->epoch_watermark[qpn] || p->next_cookie == U64_MAX) {
        ret = -ESTALE;
        goto unlock;
    }
    q = kzalloc(sizeof(*q), GFP_KERNEL);
    if (!q) {
        ret = -ENOMEM;
        goto unlock;
    }
    q->layout.owner = (struct as02_sq_handle){ .cookie=++p->next_cookie, .epoch=epoch, .qpn=qpn, .pd=pd };
    q->layout.depth = 1U << log_depth;
    q->send_limit = q->layout.depth;
    q->layout.log_depth = log_depth;
    q->bytes = q->layout.depth * AS02_WQE_BYTES;
    q->shadow = kcalloc(q->layout.depth, sizeof(*q->shadow), GFP_KERNEL);
    if (!q->shadow) {
        ret = -ENOMEM;
        goto free_queue;
    }
    q->ring = dma_alloc_coherent(p->dma_device, q->bytes, &q->dma, GFP_KERNEL);
    if (!q->ring) {
        ret = -ENOMEM;
        goto free_shadow;
    }
    if (((u64)q->dma & 63) || check_add_overflow((u64)q->dma, (u64)q->bytes-1, &last)) {
        ret = -ERANGE;
        goto free_dma;
    }
    q->layout.dma_base = (u64)q->dma;
    memset(q->ring, 0, q->bytes);
    dma_wmb();
    /* Publish the owner BEFORE calling hardware: ambiguous failure remains
     * pool-owned/mapped and never loses its only cleanup handle/reference.
     */
    spin_lock_irqsave(&p->fast_lock, flags);
    p->slots[qpn] = q;
    p->queue_count++;
    p->epoch_watermark[qpn] = epoch;
    *out = q->layout.owner;
    spin_unlock_irqrestore(&p->fast_lock, flags);
    ret = p->hw->allocate(p->hw_context, &q->layout, &proof);
    if (!ret && (!same_owner(&proof.layout.owner, &q->layout.owner) ||
        proof.layout.dma_base != q->layout.dma_base || proof.layout.depth != q->layout.depth ||
        proof.layout.log_depth != q->layout.log_depth ||
        proof.flags != (AS02_SQ_ALLOC_ACTIVE|AS02_SQ_ALLOC_EMPTY|AS02_SQ_ALLOC_PARENT_DRAINED)))
        ret = -EIO;
    spin_lock_irqsave(&p->fast_lock, flags);
    q->live = !ret;
    q->uncertain = !!ret;
    spin_unlock_irqrestore(&p->fast_lock, flags);
    goto unlock;
free_dma:
    dma_free_coherent(p->dma_device, q->bytes, q->ring, q->dma);
free_shadow:
    kfree(q->shadow);
free_queue:
    kfree(q);
unlock:
    mutex_unlock(&p->lock);
    return ret;
}


bool as02_sq_independent_receive_supported(struct as02_sq_pool *p)
{
    return p && READ_ONCE(p->initialized) && p->hw->receive_supported &&
        p->hw->allocate_receive && p->hw->publish_receive && p->hw->retire_receive &&
        p->hw->receive_supported(p->hw_context);
}
int as02_sq_create_receive(struct as02_sq_pool *p, const struct as02_sq_handle *owner,
                            u32 log_depth, u32 receive_limit)
{
    struct as02_sq_alloc_proof proof={};
    struct as02_sq *q,*receive=NULL;
    unsigned long flags;
    u64 last;
    int ret;
    if(!as02_sq_independent_receive_supported(p))return -EOPNOTSUPP;
    if(log_depth<1 || log_depth>8 || !receive_limit || receive_limit>8 ||
       receive_limit>(1U<<log_depth))return -EINVAL;
    mutex_lock(&p->lock);
    spin_lock_irqsave(&p->fast_lock,flags);
    q=find_queue(p,owner);
    if(!q || p->stopping || !q->live || q->stopping || q->uncertain ||
       q->receive || q->producer || q->pending || q->receive_limit || p->next_cookie==U64_MAX){
        ret=-EBUSY;goto fast_out_receive;
    }
    /* Prevent a concurrent first post while the second mapping is created. */
    q->stopping=true;spin_unlock_irqrestore(&p->fast_lock,flags);
    receive=kzalloc(sizeof(*receive),GFP_KERNEL);
    if(!receive){ret=-ENOMEM;goto restore_send;}
    receive->layout.owner=*owner;receive->layout.owner.cookie=++p->next_cookie;
    receive->layout.log_depth=log_depth;
    receive->layout.depth=1U<<log_depth;receive->receive_limit=receive_limit;
    receive->bytes=receive->layout.depth*AS02_WQE_BYTES;
    receive->shadow=kcalloc(receive->layout.depth,sizeof(*receive->shadow),GFP_KERNEL);
    if(!receive->shadow){ret=-ENOMEM;goto free_receive;}
    receive->ring=dma_alloc_coherent(p->dma_device,receive->bytes,&receive->dma,GFP_KERNEL);
    if(!receive->ring){ret=-ENOMEM;goto free_receive;}
    if(((u64)receive->dma&63) || check_add_overflow((u64)receive->dma,(u64)receive->bytes-1,&last)){
        ret=-ERANGE;goto free_receive;
    }
    receive->layout.dma_base=(u64)receive->dma;
    memset(receive->ring,0,receive->bytes);dma_wmb();
    /* Attach BEFORE potentially posted hardware access. Same QP identity,
     * separate physical ring, producer, completion order and MR references. */
    spin_lock_irqsave(&p->fast_lock,flags);q->receive=receive;
    spin_unlock_irqrestore(&p->fast_lock,flags);
    ret=p->hw->allocate_receive(p->hw_context,&receive->layout,&proof);
    if(!ret && (!same_owner(&proof.layout.owner,&receive->layout.owner) ||
       proof.layout.dma_base!=receive->layout.dma_base || proof.layout.depth!=receive->layout.depth ||
       proof.layout.log_depth!=receive->layout.log_depth ||
       proof.flags!=(AS02_SQ_ALLOC_ACTIVE|AS02_SQ_ALLOC_EMPTY|AS02_SQ_ALLOC_PARENT_DRAINED)))ret=-EIO;
    spin_lock_irqsave(&p->fast_lock,flags);
    receive->live=!ret;receive->uncertain=!!ret;receive->stopping=!!ret;
    q->uncertain=!!ret;q->stopping=!!ret;
fast_out_receive:
    spin_unlock_irqrestore(&p->fast_lock,flags);mutex_unlock(&p->lock);return ret;
free_receive:
    if(receive->ring)dma_free_coherent(p->dma_device,receive->bytes,receive->ring,receive->dma);
    kfree(receive->shadow);kfree(receive);
restore_send:
    spin_lock_irqsave(&p->fast_lock,flags);q->stopping=false;
    goto fast_out_receive;
}

int as02_sq_set_receive_limits(struct as02_sq_pool *p, const struct as02_sq_handle *owner,
                               u32 send_limit, u32 receive_limit)
{
    struct as02_sq *q;
    unsigned long flags;
    int ret=0;
    if(!p || !p->initialized || !send_limit || !receive_limit || receive_limit>8)return -EINVAL;
    spin_lock_irqsave(&p->fast_lock,flags);
    q=find_queue(p,owner);
    if(!q || q->receive || q->producer || q->pending || q->receive_limit || send_limit>q->layout.depth ||
        receive_limit>q->layout.depth-send_limit)ret=-EBUSY;
    else {q->send_limit=send_limit;q->receive_limit=receive_limit;}
    spin_unlock_irqrestore(&p->fast_lock,flags);return ret;
}
static int post_work(struct as02_sq_pool *p, const struct as02_sq_handle *owner,
                     const struct ib_send_wr *wr, const struct ib_recv_wr *receive)
{
    struct as02_sq_slot *slot;
    struct as02_user_mr *mr;
    struct as02_wqe work;
    struct as02_sq *q,*root;
    u8 encoded[AS02_WQE_BYTES];
    unsigned long flags;
    unsigned int index;
    int ret;
    if (!p || !READ_ONCE(p->initialized) || (!wr && !receive))
        return -EINVAL;
    spin_lock_irqsave(&p->fast_lock, flags);
    root=find_queue(p,owner);q=root;
    if(receive && root && root->receive)q=root->receive;
    if (!root || !root->live || root->stopping || root->uncertain ||
        p->stopping || !q->live || q->stopping || q->uncertain) {
        ret = -ESHUTDOWN;
        goto out;
    }
    if (q->pending == q->layout.depth || q->producer == U64_MAX ||
        (receive ? q->receive_pending>=q->receive_limit : q->pending-q->receive_pending>=q->send_limit)) {
        ret = -ENOSPC;
        goto out;
    }
    ret = receive ? as02_wqe_from_ib_recv_wr(encoded, receive, q->producer+1, owner->epoch) :
                    as02_wqe_from_ib_send_wr_profile(encoded, wr, q->producer+1, owner->epoch,p->wqe_profile);
    if (ret)
        goto out;
    ret = as02_wqe_decode_profile(&work, encoded,p->wqe_profile);
    if (ret)
        goto out;
    mr = as02_user_mr_get_work(p->mrs, owner->pd, work.local_key, work.local_address,
                              work.length, (work.opcode == AS02_WQE_READ || work.opcode == AS02_WQE_RECV) ? 1 : 0);
    if (IS_ERR(mr)) {
        ret = PTR_ERR(mr);
        goto out;
    }
    index = q->producer & (q->layout.depth-1);
    slot = &q->shadow[index];
    if (slot->used) {
        as02_user_mr_put_work(mr);
        q->uncertain = true;root->uncertain=true;
        ret = -EIO;
        goto out;
    }
    slot->mr = mr;
    slot->work = work;
    slot->used = true;
    memcpy((u8 *)q->ring + index*AS02_WQE_BYTES, encoded, AS02_WQE_BYTES);
    q->producer++;
    q->pending++;
    if(receive)q->receive_pending++;
    dma_wmb();
    ret = receive && root->receive ? p->hw->publish_receive(p->hw_context,&q->layout,q->producer) :
        p->hw->publish_producer(p->hw_context,&q->layout,q->producer);
    if (ret) {
        /* MMIO may already have reached the FPGA. Do not erase/rewind the
         * ring, drop MR refs, or pretend the work was never exposed.
         */
        q->uncertain = true;root->uncertain=true;
        q->stopping = true;
    }
out:
    spin_unlock_irqrestore(&p->fast_lock, flags);
    return ret;
}

int as02_sq_post(struct as02_sq_pool *p, const struct as02_sq_handle *owner, const struct ib_send_wr *wr)
{ return post_work(p,owner,wr,NULL); }
int as02_sq_post_recv(struct as02_sq_pool *p, const struct as02_sq_handle *owner, const struct ib_recv_wr *wr)
{ return post_work(p,owner,NULL,wr); }

static int complete_owned_work(struct as02_sq_pool *p, const struct as02_sq_completion_proof *proof,
                    const struct as02_cq_decoded *event)
{
    struct as02_sq_completion completion;
    struct as02_sq_slot *slot;
    struct as02_sq *q,*root;
    unsigned long flags;
    unsigned int index;
    int ret = 0;
    if (!p || !READ_ONCE(p->initialized) || !proof)
        return -EINVAL;
    spin_lock_irqsave(&p->fast_lock, flags);
    root=proof->owner.qpn<AS02_SQ_QPS ? p->slots[proof->owner.qpn] : NULL;q=root;
    if(root && root->receive && !event){ret=-EOPNOTSUPP;goto out;}
    if(root && root->receive && event && event->work.opcode==AS02_WQE_RECV)q=root->receive;
    if (!root || !same_owner(&q->layout.owner,&proof->owner) || !root->live || root->retiring || root->uncertain ||
        !q->live || q->retiring || q->uncertain) {
        ret = -ESTALE;
        goto out;
    }
    if (!q->pending || !proof->sequence || proof->sequence != q->completed+1 ||
        proof->flags != (AS02_SQ_CQE_MEMORY_DONE|AS02_SQ_CQE_TRANSPORT_DONE) ||
        proof->status > IB_WC_GENERAL_ERR) {
        q->uncertain = true;root->uncertain=true;
        ret = -EIO;
        goto out;
    }
    index = (proof->sequence-1) & (q->layout.depth-1);
    slot = &q->shadow[index];
    if (!slot->used || slot->work.sequence != proof->sequence || slot->work.epoch != proof->owner.epoch) {
        q->uncertain = true;root->uncertain=true;
        ret = -EIO;
        goto out;
    }
    /* A proof-only legacy completion cannot distinguish received bytes from
     * posted capacity. RECV needs the actual full-owner CQC1 event. */
    if ((slot->work.opcode == AS02_WQE_RECV || slot->work.opcode == AS02_WQE_SEND_IMMEDIATE ||
         slot->work.opcode == AS02_WQE_WRITE_IMMEDIATE) && !event) {
        ret = -EOPNOTSUPP;
        goto out;
    }
    if (event) {
        as02_byte expected[AS02_WQE_BYTES], observed[AS02_WQE_BYTES];
        if (event->proofs != AS02_CQC_COMPLETE_PROOFS || !event->event_sequence ||
            ((slot->work.opcode == AS02_WQE_SEND_IMMEDIATE || slot->work.opcode == AS02_WQE_WRITE_IMMEDIATE) &&
             (!p->profile_bound || p->wqe_profile!=AS02_WQE_PROFILE_IMMEDIATE || event->profile!=p->wqe_profile)) ||
            !event->tag || event->status != proof->status ||
            event->local_offset != slot->work.local_address-slot->mr->layout.iova ||
            !as02_cq_notification_valid(event) ||
            as02_wqe_encode_profile(expected, &slot->work,event->profile) ||
            as02_wqe_encode_profile(observed, &event->work,event->profile) ||
            memcmp(expected, observed, sizeof(expected))) {
            q->uncertain = true;root->uncertain=true;
            ret = -EIO;
            goto out;
        }
    }
    completion = (struct as02_sq_completion){
        .wr_id=slot->work.wr_id, .sequence=proof->sequence, .epoch=proof->owner.epoch,
        .qpn=proof->owner.qpn, .opcode=slot->work.opcode, .status=proof->status,
        .length=slot->work.opcode == AS02_WQE_RECV ? event->received_bytes : slot->work.length,
        .notification=event ? event->notification:0,.notification_flags=event ? event->notification_flags:0
    };
    if ((slot->work.flags & AS02_WQE_SIGNALED) || proof->status != IB_WC_SUCCESS) {
        ret = p->hw->publish_cqe(p->hw_context, &completion);
        if (ret)
            goto out;
    }
    ret = as02_user_mr_put_work(slot->mr);
    if (ret) {
        q->uncertain = true;root->uncertain=true;
        goto out;
    }
    if(slot->work.opcode==AS02_WQE_RECV)q->receive_pending--;
    memset(slot, 0, sizeof(*slot));
    q->completed = proof->sequence;
    q->pending--;
out:
    spin_unlock_irqrestore(&p->fast_lock, flags);
    return ret;
}

int as02_sq_complete(struct as02_sq_pool *p, const struct as02_sq_completion_proof *proof)
{
    return complete_owned_work(p, proof, NULL);
}

int as02_sq_complete_event(struct as02_sq_pool *p, const struct as02_cq_decoded *e)
{
    struct as02_sq_completion_proof proof;
    if (!e || e->qpn >= AS02_SQ_QPS || e->pd > 65535 || !e->cookie)
        return -EINVAL;
    proof = (struct as02_sq_completion_proof){
        .owner={.cookie=e->cookie,.epoch=e->work.epoch,.qpn=e->qpn,.pd=e->pd},
        .sequence=e->work.sequence,.flags=AS02_SQ_CQE_MEMORY_DONE|AS02_SQ_CQE_TRANSPORT_DONE,
        .status=e->status
    };
    return complete_owned_work(p, &proof, e);
}

int as02_sq_pool_get_completion_client(struct as02_sq_pool *p)
{
    unsigned long flags;
    int ret=0;
    if (!p || !READ_ONCE(p->initialized))return -EINVAL;
    mutex_lock(&p->lock);
    spin_lock_irqsave(&p->fast_lock, flags);
    if (!p->initialized || p->stopping || p->completion_clients == (unsigned int)-1)
        ret=-ESHUTDOWN;
    else p->completion_clients++;
    spin_unlock_irqrestore(&p->fast_lock, flags);
    mutex_unlock(&p->lock);
    return ret;
}

int as02_sq_pool_put_completion_client(struct as02_sq_pool *p)
{
    unsigned long flags;
    int ret=0;
    if (!p || !READ_ONCE(p->initialized))return -EINVAL;
    mutex_lock(&p->lock);
    spin_lock_irqsave(&p->fast_lock, flags);
    if (!p->completion_clients)ret=-EINVAL;
    else p->completion_clients--;
    spin_unlock_irqrestore(&p->fast_lock, flags);
    mutex_unlock(&p->lock);
    return ret;
}


static int cancel_receive(struct as02_sq_pool *p,const struct as02_sq_handle *owner,int mode)
{
    struct as02_sq *root,*q;struct as02_sq_retire_proof proof={};
    unsigned long flags;unsigned int i,used=0;int ret;
    if(!p || !p->initialized)return -EINVAL;
    if(!p->hw->receive_cancel_supported || !p->hw->cancel_receive ||
       !p->hw->receive_cancel_supported(p->hw_context))return -EOPNOTSUPP;
    mutex_lock(&p->lock);spin_lock_irqsave(&p->fast_lock,flags);
    root=find_queue(p,owner);q=root ? root->receive:NULL;
    if(!q || root->uncertain || q->uncertain){ret=-EBUSY;goto out;}
    root->stopping=true;q->stopping=true;
    if(q->retired){ret=0;goto out;}
    if(!q->cancelling){
        if(p->next_cookie==U64_MAX){ret=-ENOSPC;goto out;}
        q->cancel_nonce=++p->next_cookie;q->cancelling=true;
    }
    if(!q->cancel_proved){
        spin_unlock_irqrestore(&p->fast_lock,flags);
        ret=p->hw->cancel_receive(p->hw_context,&q->layout,q->producer,q->cancel_nonce,&proof);
        spin_lock_irqsave(&p->fast_lock,flags);
        if(ret)goto out; /* Keep refs AND permit genuine in-flight CQ progress. */
        if(!same_owner(&proof.owner,&q->layout.owner) || proof.last_producer!=q->producer ||
           proof.request_cookie!=q->cancel_nonce || proof.flags!=AS02_RQC_CANCEL_FLAGS){ret=-EIO;goto out;}
        q->cancel_proved=true;q->live=false;
    }
    for(i=0;i<q->layout.depth;i++)if(q->shadow[i].used){
        struct as02_wqe *w=&q->shadow[i].work;
        if(w->opcode!=AS02_WQE_RECV || w->epoch!=owner->epoch ||
           w->sequence<=q->completed || w->sequence>q->producer){ret=-EIO;goto out;}
        used++;
    }
    if(used!=q->pending || q->receive_pending!=q->pending){ret=-EIO;goto out;}
    if(mode==2){ret=0;goto out;} /* Retain ALL refs until real QP STOP, then flush. */
    /* The exact real cancellation certificate is now retained independently
     * of CQ delivery. Full software CQ must NOT reissue a retired HW command
     * or release an unreported work ref. Deliver in WQE order across wrap.
     * These are standard error WCs, never fabricated native/success events.
     */
    while(q->pending){
        struct as02_sq_slot *slot=&q->shadow[q->completed&(q->layout.depth-1)];
        struct as02_sq_completion completion;
        if(!slot->used || slot->work.sequence!=q->completed+1){ret=-EIO;goto out;}
        if(mode==1){
            completion=(struct as02_sq_completion){.wr_id=slot->work.wr_id,
                .sequence=slot->work.sequence,.epoch=slot->work.epoch,.qpn=owner->qpn,
                .opcode=AS02_WQE_RECV,.status=IB_WC_WR_FLUSH_ERR,.length=0};
            ret=p->hw->publish_cqe(p->hw_context,&completion);if(ret)goto out;
        }
        ret=as02_user_mr_put_work(slot->mr);
        if(ret){q->uncertain=true;root->uncertain=true;goto out;}
        memset(slot,0,sizeof(*slot));q->completed++;q->pending--;q->receive_pending--;
    }
    q->completed=q->producer;q->pending=0;q->receive_pending=0;
    q->retired=true;q->live=false;q->cancelling=false;ret=0;
out:
    spin_unlock_irqrestore(&p->fast_lock,flags);mutex_unlock(&p->lock);return ret;
}
int as02_sq_cancel_receive(struct as02_sq_pool *p,const struct as02_sq_handle *owner)
{return cancel_receive(p,owner,0);}
int as02_sq_flush_receive(struct as02_sq_pool *p,const struct as02_sq_handle *owner)
{return cancel_receive(p,owner,1);}
int as02_sq_prepare_receive_cancel(struct as02_sq_pool *p,const struct as02_sq_handle *owner)
{return cancel_receive(p,owner,2);}
int as02_sq_close(struct as02_sq_pool *p, const struct as02_sq_handle *owner)
{
    struct as02_sq_retire_proof proof;
    struct as02_sq *q,*rings[2],*closing_queue;
    unsigned long flags;
    u64 request_cookie;
    unsigned int n;
    int ret;
    if(!p || !READ_ONCE(p->initialized))return -EINVAL;
    mutex_lock(&p->lock);spin_lock_irqsave(&p->fast_lock,flags);
    q=find_queue(p,owner);
    if(!q){ret=-ESTALE;goto fast_out;}
    q->stopping=true;if(q->receive)q->receive->stopping=true;
    if(q->pending || (q->receive && (q->receive->pending || q->receive->cancelling))){ret=-EBUSY;goto fast_out;}
    q->retiring=true;q->live=false;
    rings[0]=q->receive;rings[1]=q;
    for(n=0;n<2;n++){
        closing_queue=rings[n];if(!closing_queue || closing_queue->retired)continue;
        closing_queue->retiring=true;closing_queue->live=false;
        if(p->next_cookie==U64_MAX){ret=-ENOSPC;goto fast_out;}
        request_cookie=++p->next_cookie;memset(&proof,0,sizeof(proof));
        spin_unlock_irqrestore(&p->fast_lock,flags);
        ret=n==0 ? p->hw->retire_receive(p->hw_context,&closing_queue->layout,closing_queue->producer,request_cookie,&proof) :
            p->hw->retire_and_drain(p->hw_context,&closing_queue->layout,closing_queue->producer,request_cookie,&proof);
        if(!ret && (!same_owner(&proof.owner,&closing_queue->layout.owner) || proof.request_cookie!=request_cookie ||
           proof.last_producer!=closing_queue->producer ||
           proof.flags!=(AS02_SQ_RETIRED|AS02_SQ_FETCH_DRAINED|AS02_SQ_WORK_DRAINED|
                          AS02_SQ_WIRE_DRAINED|AS02_SQ_COMPLETION_DRAINED)))ret=-EIO;
        spin_lock_irqsave(&p->fast_lock,flags);
        if(ret){closing_queue->uncertain=true;q->uncertain=true;goto fast_out;}
        /* A later failure must not re-retire this successfully closed ring.
         * Neither allocation is freed until BOTH genuine proofs exist. */
        closing_queue->retired=true;
    }
    p->slots[owner->qpn]=NULL;p->queue_count--;
    spin_unlock_irqrestore(&p->fast_lock,flags);
    for(n=0;n<2;n++)if(rings[n]){
        closing_queue=rings[n];dma_free_coherent(p->dma_device,closing_queue->bytes,closing_queue->ring,closing_queue->dma);
        kfree(closing_queue->shadow);kfree(closing_queue);
    }
    mutex_unlock(&p->lock);return 0;
fast_out:
    spin_unlock_irqrestore(&p->fast_lock,flags);mutex_unlock(&p->lock);return ret;
}

int as02_sq_pool_destroy(struct as02_sq_pool *p)
{
    unsigned long flags;
    int ret;
    if (!p || !READ_ONCE(p->initialized))
        return -EINVAL;
    mutex_lock(&p->lock);
    spin_lock_irqsave(&p->fast_lock, flags);
    p->stopping = true;
    if (p->queue_count || p->completion_clients) {
        spin_unlock_irqrestore(&p->fast_lock, flags);
        mutex_unlock(&p->lock);
        return -EBUSY;
    }
    WRITE_ONCE(p->initialized, false);
    spin_unlock_irqrestore(&p->fast_lock, flags);
    ret = as02_mr_pool_put_client(p->mrs);
    if (ret) {
        /* Internal lifetime inconsistency is NOT permission to free refs. */
        WRITE_ONCE(p->initialized, true);
        mutex_unlock(&p->lock);
        return ret;
    }
    put_device(p->dma_device);
    mutex_unlock(&p->lock);
    module_put(THIS_MODULE);
    return 0;
}

EXPORT_SYMBOL_GPL(as02_sq_pool_init);
EXPORT_SYMBOL_GPL(as02_sq_pool_destroy);
EXPORT_SYMBOL_GPL(as02_sq_create);
EXPORT_SYMBOL_GPL(as02_sq_close);
EXPORT_SYMBOL_GPL(as02_sq_cancel_receive);
EXPORT_SYMBOL_GPL(as02_sq_flush_receive);
EXPORT_SYMBOL_GPL(as02_sq_prepare_receive_cancel);
EXPORT_SYMBOL_GPL(as02_sq_create_receive);
EXPORT_SYMBOL_GPL(as02_sq_independent_receive_supported);
EXPORT_SYMBOL_GPL(as02_sq_post);
EXPORT_SYMBOL_GPL(as02_sq_set_receive_limits);
EXPORT_SYMBOL_GPL(as02_sq_post_recv);
EXPORT_SYMBOL_GPL(as02_sq_complete);
EXPORT_SYMBOL_GPL(as02_sq_complete_event);
EXPORT_SYMBOL_GPL(as02_sq_pool_get_completion_client);
EXPORT_SYMBOL_GPL(as02_sq_pool_put_completion_client);
