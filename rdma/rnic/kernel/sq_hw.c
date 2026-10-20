/* SPDX-License-Identifier: GPL-2.0 OR BSD-2-Clause-Views */
#include <linux/errno.h>
#include <linux/ktime.h>
#include <linux/lockdep.h>
#include <linux/module.h>
#include <linux/string.h>
#include <asm/processor.h>
#include "sq_hw.h"

static int reg_read(void *context, as02_u32 offset, as02_u32 *value)
{
    struct as02_sq_hw *h = context;
    lockdep_assert_held(&h->lock);
    if (!h->registers || h->control.detached)
        return -ENODEV;
    if ((offset & 3) || offset >= AS02_SQC_BYTES)
        return -EINVAL;
    *value = readl(h->registers+offset);
    return 0;
}
static int reg_write(void *context, as02_u32 offset, as02_u32 value)
{
    struct as02_sq_hw *h = context;
    lockdep_assert_held(&h->lock);
    if (!h->registers || h->control.detached)
        return -ENODEV;
    if ((offset & 3) || offset >= AS02_SQC_BYTES)
        return -EINVAL;
    writel(value, h->registers+offset);
    return 0;
}
static as02_u64 time_us(void *context)
{
    (void)context;
    return ktime_to_us(ktime_get());
}
static void relax_cpu(void *context)
{
    (void)context;
    cpu_relax();
}
static const struct as02_sqc_transport real_register_io = {
    .read32=reg_read, .write32=reg_write, .time_us=time_us, .relax=relax_cpu
};
static int initialize(struct as02_sq_hw *h, void __iomem *base, size_t bytes, u32 timeout_us,
                    int (*commit_cqe)(void *, const struct as02_sq_completion *), void *cq_context, u32 id)
{
    unsigned long flags;
    int ret;
    if (!h || !base || bytes < AS02_SQC_BYTES || !commit_cqe ||
        !timeout_us || timeout_us > AS02_SQC_MAX_TIMEOUT_US)
        return -EINVAL;
    if (h->control.initialized || h->control.detached)
        return h->control.detached ? -ENODEV : -EBUSY;
    spin_lock_init(&h->lock);
    h->registers = base;h->commit_cqe = commit_cqe;h->cq_context = cq_context;
    spin_lock_irqsave(&h->lock, flags);
    ret = as02_sqc_io_init_id(&h->control, &real_register_io, h, timeout_us, id);
    spin_unlock_irqrestore(&h->lock, flags);
    if (ret) {
        h->registers = NULL;h->commit_cqe = NULL;h->cq_context = NULL;
    }
    return ret;
}
int as02_sq_hw_init(struct as02_sq_hw *h, void __iomem *base, size_t bytes, u32 timeout_us,
                    int (*commit_cqe)(void *, const struct as02_sq_completion *), void *context)
{ return initialize(h,base,bytes,timeout_us,commit_cqe,context,AS02_SQC_ID_VALUE); }

int as02_sq_hw_init_receive(struct as02_sq_hw *h, struct as02_sq_hw *send,
                            void __iomem *base, size_t bytes, u32 timeout_us)
{
    int ret;
    if(!h || !send || h==send || !send->control.initialized || send->control.detached ||
       !send->registers || send->receive || send->send_parent)return -EINVAL;
    ret=initialize(h,base,bytes,timeout_us,send->commit_cqe,send->cq_context,AS02_RQC_ID_VALUE);
    if(!ret){h->send_parent=send;send->receive=h;}
    return ret;
}
int as02_sq_hw_detach(struct as02_sq_hw *h)
{
    unsigned long flags;
    int ret;
    if (!h || !h->control.initialized)
        return -EINVAL;
    if(h->receive)return -EBUSY;
    spin_lock_irqsave(&h->lock, flags);
    ret = as02_sqc_io_detach(&h->control);
    if (!ret) {
        h->registers = NULL;
        if(h->send_parent){h->send_parent->receive=NULL;h->send_parent=NULL;}
    }
    spin_unlock_irqrestore(&h->lock, flags);
    return ret;
}
int as02_sq_hw_reconcile(struct as02_sq_hw *h, struct as02_sqc_reply *out)
{
    unsigned long flags;
    int ret;
    if (!h || !h->control.initialized || !out)
        return -EINVAL;
    spin_lock_irqsave(&h->lock, flags);
    ret = as02_sqc_io_reconcile(&h->control, out);
    spin_unlock_irqrestore(&h->lock, flags);
    return ret;
}
static int layout_words(as02_u32 *w, const struct as02_sq_layout *l, u32 command,
                        u64 producer, u64 nonce)
{
    if (!l || !l->owner.cookie || !l->owner.epoch || l->owner.qpn >= AS02_SQ_QPS ||
        l->owner.pd > 65535 || l->log_depth < 1 || l->log_depth > 8 ||
        l->depth != (1U << l->log_depth))
        return -EINVAL;
    memset(w, 0, AS02_SQC_WORDS*sizeof(*w));
    w[1]=command;w[2]=l->owner.qpn;w[3]=l->owner.pd;
    w[4]=l->owner.epoch;w[5]=l->owner.epoch>>32;
    w[6]=l->owner.cookie;w[7]=l->owner.cookie>>32;
    w[8]=l->dma_base;w[9]=l->dma_base>>32;w[10]=l->log_depth;
    w[11]=producer;w[12]=producer>>32;w[13]=nonce;w[14]=nonce>>32;
    return 0;
}
static void reply_layout(const struct as02_sqc_reply *r, struct as02_sq_layout *l)
{
    l->owner.qpn=r->words[2];l->owner.pd=r->words[3];
    l->owner.epoch=r->words[4] | ((u64)r->words[5]<<32);
    l->owner.cookie=r->words[6] | ((u64)r->words[7]<<32);
    l->dma_base=r->words[8] | ((u64)r->words[9]<<32);
    l->log_depth=r->words[10];l->depth=1U<<l->log_depth;
}
static int execute(struct as02_sq_hw *h, const as02_u32 *w, struct as02_sqc_reply *r)
{
    unsigned long flags;
    int ret;
    if (!h || !h->control.initialized)
        return -EINVAL;
    spin_lock_irqsave(&h->lock, flags);
    ret = as02_sqc_io_execute(&h->control, w, r);
    spin_unlock_irqrestore(&h->lock, flags);
    return ret ? ret : (r->error ? -EIO : 0);
}
static int allocate(void *context, const struct as02_sq_layout *l, struct as02_sq_alloc_proof *proof)
{
    struct as02_sqc_reply r = {};
    as02_u32 w[AS02_SQC_WORDS];
    int ret;
    if (!proof)
        return -EINVAL;
    memset(proof, 0, sizeof(*proof));
    ret = layout_words(w, l, 1, 0, 0);
    if (!ret)
        ret = execute(context, w, &r);
    if (!ret) {
        reply_layout(&r, &proof->layout);
        proof->flags = r.flags;
    }
    return ret;
}
static int publish(void *context, const struct as02_sq_layout *l, u64 producer)
{
    struct as02_sqc_reply r = {};
    as02_u32 w[AS02_SQC_WORDS];
    int ret = layout_words(w, l, 2, producer, 0);
    /* as02_sq_post already performed dma_wmb after writing the coherent
     * descriptor and owning its MR ref; do not copy user payload here.
     */
    return ret ? ret : execute(context, w, &r);
}
static int retire(void *context, const struct as02_sq_layout *l, u64 producer,
                   u64 nonce, struct as02_sq_retire_proof *proof)
{
    struct as02_sqc_reply r = {};
    struct as02_sq_layout actual;
    as02_u32 w[AS02_SQC_WORDS];
    int ret;
    if (!proof)
        return -EINVAL;
    memset(proof, 0, sizeof(*proof));
    ret = layout_words(w, l, 3, producer, nonce);
    if (!ret)
        ret = execute(context, w, &r);
    if (!ret) {
        reply_layout(&r, &actual);proof->owner=actual.owner;
        proof->last_producer=r.words[11] | ((u64)r.words[12]<<32);
        proof->request_cookie=r.words[13] | ((u64)r.words[14]<<32);
        proof->flags=r.flags;
    }
    return ret;
}
static int commit_cqe(void *context, const struct as02_sq_completion *cqe)
{
    struct as02_sq_hw *h = context;
    unsigned long flags;
    int ret;
    if (!h || !cqe || !h->control.initialized)
        return -EINVAL;
    spin_lock_irqsave(&h->lock, flags);
    ret = h->control.detached || !h->registers ? -ENODEV :
          h->commit_cqe(h->cq_context, cqe);
    spin_unlock_irqrestore(&h->lock, flags);
    return ret;
}
static bool receive_supported(void *context)
{
    struct as02_sq_hw *h=context;
    return h && h->control.initialized && !h->control.detached && h->registers &&
        h->receive && h->receive->send_parent==h && h->receive->control.initialized &&
        !h->receive->control.detached && h->receive->registers;
}
static int allocate_receive(void *context,const struct as02_sq_layout *l,struct as02_sq_alloc_proof *p)
{
    struct as02_sq_hw *h=context;
    return receive_supported(h) ? allocate(h->receive,l,p):-EOPNOTSUPP;
}
static int publish_receive(void *context,const struct as02_sq_layout *l,u64 producer)
{
    struct as02_sq_hw *h=context;
    return receive_supported(h) ? publish(h->receive,l,producer):-ENODEV;
}
static int retire_receive(void *context,const struct as02_sq_layout *l,u64 producer,u64 nonce,
                           struct as02_sq_retire_proof *p)
{
    struct as02_sq_hw *h=context;
    return receive_supported(h) ? retire(h->receive,l,producer,nonce,p):-ENODEV;
}
static bool receive_cancel_supported(void *context)
{
    struct as02_sq_hw *h=context;
    return receive_supported(h) && (h->receive->control.features&AS02_RQC_CANCEL_FEATURE);
}
static int cancel_receive(void *context,const struct as02_sq_layout *l,u64 producer,u64 nonce,
                           struct as02_sq_retire_proof *proof)
{
    struct as02_sq_hw *h=context,*r;
    struct as02_sqc_reply reply={};struct as02_sq_layout actual;
    as02_u32 words[AS02_SQC_WORDS],i;unsigned long flags;int ret;
    if(!proof || !receive_cancel_supported(h))return -EOPNOTSUPP;
    memset(proof,0,sizeof(*proof));r=h->receive;
    ret=layout_words(words,l,4,producer,nonce);if(ret)return ret;
    spin_lock_irqsave(&r->lock,flags);
    if(r->control.pending || r->control.uncertain){
        /* Retry only the exact owned batch, never adopt someone else's late
         * reply or infer cancellation from transport resynchronization.
         */
        ret=0;for(i=1;i<AS02_SQC_WORDS;i++)if(words[i]!=r->control.expected[i])ret=-ESTALE;
        if(!ret)ret=as02_sqc_io_reconcile(&r->control,&reply);
    }else ret=as02_sqc_io_execute(&r->control,words,&reply);
    if(!ret && reply.error)ret=-EIO;
    if(!ret){
        reply_layout(&reply,&actual);proof->owner=actual.owner;
        proof->last_producer=reply.words[11]|((u64)reply.words[12]<<32);
        proof->request_cookie=reply.words[13]|((u64)reply.words[14]<<32);proof->flags=reply.flags;
    }
    spin_unlock_irqrestore(&r->lock,flags);return ret;
}
const struct as02_sq_hw_ops as02_sqc_sq_hw_ops = {
    .allocate=allocate, .retire_and_drain=retire,
    .publish_producer=publish, .publish_cqe=commit_cqe,
    .receive_supported=receive_supported,.allocate_receive=allocate_receive,
    .publish_receive=publish_receive,.retire_receive=retire_receive,
    .receive_cancel_supported=receive_cancel_supported,.cancel_receive=cancel_receive
};
EXPORT_SYMBOL_GPL(as02_sq_hw_init);
EXPORT_SYMBOL_GPL(as02_sq_hw_init_receive);
EXPORT_SYMBOL_GPL(as02_sq_hw_detach);
EXPORT_SYMBOL_GPL(as02_sq_hw_reconcile);
EXPORT_SYMBOL_GPL(as02_sqc_sq_hw_ops);
