/* SPDX-License-Identifier: GPL-2.0 OR BSD-2-Clause-Views */
#include <linux/errno.h>
#include <linux/err.h>
#include <linux/module.h>
#include <linux/slab.h>
#include <rdma/uverbs_ioctl.h>
#include "native_regs.h"
#include "sq_hw.h"
#include "verbs.h"

static struct as02_verbs_device *device(struct ib_device *ibdev)
{ return container_of(ibdev, struct as02_verbs_device, ibdev); }
static bool private_data(const struct ib_udata *u)
{ return u && (u->inlen || u->outlen); }
static bool ready(struct as02_verbs_device *d)
{ return READ_ONCE(d->initialized) && !READ_ONCE(d->stopping); }
static void error_worker(struct work_struct *work);

int as02_verbs_bind(struct as02_verbs_device *d, struct as02_mr_pool *mr,
                    struct as02_sq_pool *sq, struct as02_cq_hw *cq,
                    struct as02_qp_hw *qp, struct as02_cq_router *router,
                    void __iomem *eth, size_t bytes)
{
    struct as02_sq_hw *sq_hw;
    u32 status, mac_lo, mac_hi, epoch;
    unsigned int i;
    int ret;
    if (!d || d->initialized || !mr || !sq || !cq || !qp || !router ||
        !eth || bytes < AS02_NATIVE_ETH_BYTES || !mr->initialized ||
        mr->ibdev != &d->ibdev || !sq->initialized || sq->mrs != mr ||
        sq->hw != &as02_sqc_sq_hw_ops || !sq->hw_context ||
        !cq->control.initialized || cq->control.detached || cq->pool != sq || !qp->initialized ||
        qp->owned || qp->uncertain || !router->initialized)
        return -EINVAL;
    sq_hw = sq->hw_context;
    if (sq_hw->commit_cqe != as02_cq_publish || sq_hw->cq_context != router)
        return -EINVAL;
    if (readl(eth + AS02_ETH_ID) != AS02_ETH_ID_VALUE ||
        readl(eth + AS02_ETH_ABI) != AS02_ETH_ABI_VALUE)
        return -ENODEV;
    epoch = readl(eth + AS02_ETH_EPOCH);
    status = readl(eth + AS02_ETH_STATUS);
    if ((status & (AS02_ETH_ST_ENABLED | AS02_ETH_ST_COMMITTED)) !=
        (AS02_ETH_ST_ENABLED | AS02_ETH_ST_COMMITTED) ||
        (status & (AS02_ETH_ST_ERROR | AS02_ETH_ST_EXHAUSTED)) || (status & ~31U) || !epoch)
        return -EBUSY;
    mac_lo = readl(eth + AS02_ETH_ACTIVE + 8);
    mac_hi = readl(eth + AS02_ETH_ACTIVE + 12);
    d->local_ip = readl(eth + AS02_ETH_ACTIVE + 16);
    if (mac_hi > 65535 || !d->local_ip || readl(eth + AS02_ETH_ACTIVE + 20) != 1 ||
        readl(eth + AS02_ETH_EPOCH) != epoch || readl(eth + AS02_ETH_STATUS) != status)
        return -EIO;
    for (i = 0; i < 4; i++) d->peer_mac[5-i] = mac_lo >> (i*8);
    d->peer_mac[1] = mac_hi; d->peer_mac[0] = mac_hi >> 8;
    /* Control initialization is exclusive, before publishing this object to
     * any caller. Reserve PD0 in the shared pool, not just in the wrapper.
     */
    ret = as02_mr_pool_get_client(mr);
    if (ret) return ret;
    ret = as02_sq_pool_get_completion_client(sq);
    if (ret) { as02_mr_pool_put_client(mr); return ret; }
    mutex_lock(&sq->lock);
    mutex_lock(&mr->lock);
    if (!mr->ready || mr->mapping_count || mr->pd_zero_reserved || sq->queue_count || cq->cq_clients)
        ret = -EBUSY;
    else WRITE_ONCE(mr->pd_zero_reserved, true);
    mutex_unlock(&mr->lock);
    mutex_unlock(&sq->lock);
    if (ret) {
        as02_sq_pool_put_completion_client(sq); as02_mr_pool_put_client(mr);
        return ret;
    }
    ret=as02_sq_bind_transport_profile(sq,qp->control,cq);
    if(ret){
        mutex_lock(&mr->lock);WRITE_ONCE(mr->pd_zero_reserved,false);mutex_unlock(&mr->lock);
        as02_sq_pool_put_completion_client(sq);as02_mr_pool_put_client(mr);
        return ret;
    }
    mutex_init(&d->lock);
    d->mrs = mr; d->sq = sq; d->cq_hw = cq; d->qp_hw = qp; d->router = router;
    d->stopping = false;
    ib_set_device_ops(&d->ibdev, &as02_verbs_ops);
    WRITE_ONCE(d->initialized, true);
    return 0;
}
int as02_sq_bind_transport_profile(struct as02_sq_pool *p,struct as02_rnic_hw *c,struct as02_cq_hw *cq)
{
    struct as02_sq_hw *h,*rq;
    u32 transport,sq_features,rq_features=0,cq_features,profile=0;
    unsigned long flags;
    int ret;
    if(!p || !p->initialized || p->hw!=&as02_sqc_sq_hw_ops || !p->hw_context ||
       !c || !c->control.initialized || c->control.detached || !c->registers ||
       !cq || cq->pool!=p || !cq->control.initialized || cq->control.detached || !cq->registers)
        return -EINVAL;
    h=p->hw_context;rq=h->receive;
    mutex_lock(&p->lock);
    if(p->stopping || p->queue_count || !h->control.initialized || h->control.detached ||
       !h->registers || h->send_parent || (rq && !as02_sq_independent_receive_supported(p))){ret=-EBUSY;goto out;}
    /* RNC transport permits a sleeping read, whereas SQ/RQ/CQ MMIO is atomic.
     * No queue or posting exists under p->lock; do not nest IRQ locks across
     * the RNC mutex or infer support from a callback supplied by userspace. */
    mutex_lock(&c->lock);
    ret=c->control.io->read32(c->control.context,AS02_CTL_FEATURES,&transport);
    mutex_unlock(&c->lock);
    if(ret)goto out;
    spin_lock_irqsave(&h->lock,flags);
    ret=h->control.io->read32(h->control.context,AS02_SQC_FEATURES,&sq_features);
    spin_unlock_irqrestore(&h->lock,flags);
    if(ret)goto out;
    if(rq){
        spin_lock_irqsave(&rq->lock,flags);
        ret=rq->control.io->read32(rq->control.context,AS02_SQC_FEATURES,&rq_features);
        spin_unlock_irqrestore(&rq->lock,flags);
        if(ret)goto out;
    }
    spin_lock_irqsave(&cq->lock,flags);
    ret=cq->control.io->read32(cq->control.context,AS02_CQC_FEATURES,&cq_features);
    spin_unlock_irqrestore(&cq->lock,flags);
    if(ret)goto out;
    if(transport!=c->control.features || sq_features!=h->control.features ||
       (rq && rq_features!=rq->control.features) || cq_features!=cq->control.features){ret=-ESTALE;goto out;}
    if(transport&AS02_CTL_FEATURE_IMMEDIATE){
        if(transport!=AS02_CTL_IMMEDIATE_NATIVE_FEATURES || !rq ||
           sq_features!=AS02_SQC_IMMEDIATE_FEATURE_VALUE || rq_features!=AS02_RQC_IMMEDIATE_FEATURE_VALUE ||
           cq_features!=AS02_CQC_IMMEDIATE_FEATURE_VALUE){ret=-EOPNOTSUPP;goto out;}
        profile=AS02_WQE_PROFILE_IMMEDIATE;
    }else if(sq_features!=1 || (rq && rq_features!=1 && rq_features!=3) ||
        (cq_features!=AS02_CQC_FEATURE_VALUE && cq_features!=AS02_CQC_MESSAGE_FEATURE_VALUE)){
        ret=-EOPNOTSUPP;goto out;
    }
    spin_lock_irqsave(&p->fast_lock,flags);
    if(p->profile_bound && p->wqe_profile!=profile)ret=-ESTALE;
    else{p->wqe_profile=profile;p->profile_bound=true;ret=0;}
    spin_unlock_irqrestore(&p->fast_lock,flags);
out:
    mutex_unlock(&p->lock);return ret;
}
EXPORT_SYMBOL_GPL(as02_sq_bind_transport_profile);
static int alloc_pd(struct ib_pd *ibpd, struct ib_udata *u)
{
    struct as02_verbs_device *d = device(ibpd->device);
    struct as02_pd *p = container_of(ibpd, struct as02_pd, ibpd);
    int ret = 0;
    if (private_data(u)) return -EOPNOTSUPP;
    mutex_lock(&d->lock);
    if (!ready(d) || p->live) ret = -ESHUTDOWN;
    else if (d->next_pd == 65535) ret = -ENOSPC;
    else { p->number = ++d->next_pd; p->owners = 0; p->live = true; d->pd_count++; }
    mutex_unlock(&d->lock); return ret;
}
static int dealloc_pd(struct ib_pd *ibpd, struct ib_udata *u)
{
    struct as02_verbs_device *d = device(ibpd->device);
    struct as02_pd *p = container_of(ibpd, struct as02_pd, ibpd);
    int ret = 0;
    (void)u;
    mutex_lock(&d->lock);
    if (!p->live) ret = -EINVAL;
    else if (p->owners) ret = -EBUSY;
    else { p->live = false; d->pd_count--; }
    mutex_unlock(&d->lock); return ret;
}
static struct ib_mr *reg_user_mr(struct ib_pd *ibpd, u64 start, u64 length,
                                u64 iova, int access, struct ib_dmah *dmah,
                                struct ib_udata *u)
{
    struct as02_verbs_device *d = device(ibpd->device);
    struct as02_pd *p = container_of(ibpd, struct as02_pd, ibpd);
    struct as02_verbs_mr *m;
    int ret;
    if (private_data(u) || dmah || (access & ~(IB_ACCESS_LOCAL_WRITE |
        IB_ACCESS_REMOTE_WRITE | IB_ACCESS_REMOTE_READ))) return ERR_PTR(-EOPNOTSUPP);
    m = kzalloc(sizeof(*m), GFP_KERNEL);
    if (!m) return ERR_PTR(-ENOMEM);
    mutex_lock(&d->lock);
    if (!ready(d) || !p->live) { ret = -ESHUTDOWN; goto free; }
    m->pd = p; p->owners++;
    m->mapping = as02_user_mr_prepare(d->mrs, start, iova, length, p->number, access, 7);
    if (IS_ERR(m->mapping)) { ret = PTR_ERR(m->mapping); p->owners--; goto free; }
    ret = as02_user_mr_publish(m->mapping);
    if (ret) {
        /* The RDMA core never saw this MR, but the FPGA may have. Keep the
         * wrapper + PD owner until explicit real invalidation/drain cleanup.
         */
        d->orphan_mrs[m->mapping->layout.slot] = m;
        mutex_unlock(&d->lock); return ERR_PTR(ret);
    }
    m->ibmr.device = ibpd->device; m->ibmr.pd = ibpd;
    m->ibmr.iova = iova; m->ibmr.length = length;
    m->ibmr.lkey = m->mapping->layout.key; m->ibmr.rkey = m->mapping->layout.key;
    d->mr_count++;
    mutex_unlock(&d->lock); return &m->ibmr;
free:
    mutex_unlock(&d->lock); kfree(m); return ERR_PTR(ret);
}
static int dereg_mr(struct ib_mr *ibmr, struct ib_udata *u)
{
    struct as02_verbs_mr *m = container_of(ibmr, struct as02_verbs_mr, ibmr);
    struct as02_verbs_device *d = device(ibmr->device);
    int ret;
    (void)u;
    mutex_lock(&d->lock);
    ret = as02_user_mr_close(m->mapping);
    if (!ret) { m->pd->owners--; d->mr_count--; }
    mutex_unlock(&d->lock);
    if (!ret) kfree(m);
    return ret;
}
static int create_cq(struct ib_cq *ibcq, const struct ib_cq_init_attr *attr,
                     struct uverbs_attr_bundle *attrs)
{
    struct as02_verbs_device *d = device(ibcq->device);
    struct as02_cq *cq = container_of(ibcq, struct as02_cq, ibcq);
    int ret;
    mutex_lock(&d->lock);
    if (!ready(d)) { ret = -ESHUTDOWN; goto out; }
    if (d->cq_count == AS02_VERBS_MAX_CQS) { ret = -ENOSPC; goto out; }
    ret = as02_cq_create(ibcq, attr, attrs ? &attrs->driver_udata : NULL);
    if (ret) goto out;
    cq->ucontext=attrs ? attrs->context : NULL;
    ret = as02_cq_attach_hardware(cq, d->cq_hw);
    if (ret) as02_cq_destroy(ibcq, NULL);
    else d->cq_count++;
out:
    mutex_unlock(&d->lock); return ret;
}
static int destroy_cq(struct ib_cq *ibcq, struct ib_udata *u)
{
    struct as02_verbs_device *d = device(ibcq->device);
    int ret;
    mutex_lock(&d->lock);
    ret = as02_cq_destroy(ibcq, u);
    if (!ret) d->cq_count--;
    mutex_unlock(&d->lock); return ret;
}
static int create_qp(struct ib_qp *ibqp, struct ib_qp_init_attr *attr, struct ib_udata *u)
{
    struct as02_verbs_device *d = device(ibqp->device);
    struct as02_verbs_qp *q = container_of(ibqp, struct as02_verbs_qp, ibqp);
    struct as02_pd *p;
    struct as02_cq *cq,*recv_cq;
    u32 depth = 2, log = 1;
    u32 receive_depth=2, receive_log=1;
    bool independent=!!(d->qp_hw->control->control.features&AS02_CTL_FEATURE_SEPARATE_RQ);
    int ret;
    if (private_data(u) || !attr || !ibqp->pd || attr->qp_type != IB_QPT_RC ||
        attr->srq || attr->xrcd || attr->rwq_ind_tbl || attr->source_qpn ||
        (attr->port_num && attr->port_num != 1) || attr->create_flags ||
        (attr->cap.max_recv_wr && (!(d->qp_hw->control->control.features&AS02_CTL_FEATURE_RECV) ||
          attr->cap.max_recv_wr>8 || attr->cap.max_recv_sge!=1)) ||
        (!attr->cap.max_recv_wr && attr->cap.max_recv_sge) ||
        attr->cap.max_inline_data || !attr->cap.max_send_wr || attr->cap.max_send_wr > 256 ||
        attr->cap.max_send_sge != 1 || !attr->send_cq || !attr->recv_cq ||
        attr->send_cq->device != ibqp->device || attr->recv_cq->device != ibqp->device ||
        (attr->sq_sig_type != IB_SIGNAL_ALL_WR && attr->sq_sig_type != IB_SIGNAL_REQ_WR))
        return -EOPNOTSUPP;
    p = container_of(ibqp->pd, struct as02_pd, ibpd);
    cq = container_of(attr->send_cq, struct as02_cq, ibcq);
    recv_cq = container_of(attr->recv_cq, struct as02_cq, ibcq);
    if(!independent && attr->cap.max_recv_wr>256-attr->cap.max_send_wr)return -EOPNOTSUPP;
    while (depth < attr->cap.max_send_wr+(independent ? 0:attr->cap.max_recv_wr)) { depth <<= 1; log++; }
    while(receive_depth<attr->cap.max_recv_wr){receive_depth<<=1;receive_log++;}
    mutex_lock(&d->lock);
    if (!ready(d) || !p->live || d->qp || d->orphan_sq.cookie) { ret = -EBUSY; goto out; }
    if(u && (!rdma_udata_to_uverbs_attr_bundle(u)->context ||
       rdma_udata_to_uverbs_attr_bundle(u)->context->device!=ibqp->device ||
       cq->ucontext!=rdma_udata_to_uverbs_attr_bundle(u)->context ||
       recv_cq->ucontext!=rdma_udata_to_uverbs_attr_bundle(u)->context)){
        ret=-EINVAL;goto out;
    }
    if (!cq->initialized || cq->hardware != d->cq_hw ||
        !recv_cq->initialized || recv_cq->hardware != d->cq_hw ||
        d->sq->epoch_watermark[AS02_VERBS_QPN] == U64_MAX || ibqp->pd->device != ibqp->device) {
        ret = -EINVAL; goto out;
    }
    p->owners++;
    /* One real protected connection context. Preserve reserved QPN0/1. */
    ret = as02_sq_create(d->sq, AS02_VERBS_QPN, p->number,
                         d->sq->epoch_watermark[AS02_VERBS_QPN]+1, log, &q->owner);
    if (ret) goto failed;
    if(attr->cap.max_recv_wr) {
        ret=independent ? as02_sq_create_receive(d->sq,&q->owner,receive_log,attr->cap.max_recv_wr) :
            as02_sq_set_receive_limits(d->sq,&q->owner,depth-attr->cap.max_recv_wr,attr->cap.max_recv_wr);
        if(ret) {
            if(!as02_sq_close(d->sq,&q->owner))memset(&q->owner,0,sizeof(q->owner));
            goto failed;
        }
    }
    ibqp->qp_num = AS02_VERBS_QPN; ibqp->send_cq = attr->send_cq; ibqp->recv_cq = attr->recv_cq;
    ret = as02_cq_router_bind(d->router, cq, ibqp);
    if (ret) {
        if (!as02_sq_close(d->sq, &q->owner)) memset(&q->owner, 0, sizeof(q->owner));
        goto failed;
    }
    spin_lock_init(&q->lock);INIT_DELAYED_WORK(&q->error_work,error_worker);
    q->pd = p; q->cap = attr->cap;
    q->ucontext=u ? rdma_udata_to_uverbs_attr_bundle(u)->context : NULL;
    q->cap.max_send_wr = independent ? depth:depth-attr->cap.max_recv_wr;
    q->attributes.qp_state = IB_QPS_RESET; q->attributes.cap = q->cap;
    q->initialized = true; q->routed = true; q->signal_all = attr->sq_sig_type == IB_SIGNAL_ALL_WR;
    attr->cap = q->cap; q->initial = *attr; d->qp = q;
    goto out;
failed:
    if (q->owner.cookie) { d->orphan_sq = q->owner; d->orphan_sq_pd = p; }
    else p->owners--;
out:
    mutex_unlock(&d->lock); return ret;
}
static int query_qp(struct ib_qp *ibqp, struct ib_qp_attr *attr, int mask,
                    struct ib_qp_init_attr *initial)
{
    struct as02_verbs_qp *q = container_of(ibqp, struct as02_verbs_qp, ibqp);
    struct as02_verbs_device *d = device(ibqp->device);
    int supported = IB_QP_STATE | IB_QP_CUR_STATE | IB_QP_ACCESS_FLAGS |
        IB_QP_PKEY_INDEX | IB_QP_PORT | IB_QP_AV | IB_QP_PATH_MTU | IB_QP_DEST_QPN |
        IB_QP_RQ_PSN | IB_QP_SQ_PSN | IB_QP_MAX_DEST_RD_ATOMIC | IB_QP_MIN_RNR_TIMER |
        IB_QP_MAX_QP_RD_ATOMIC | IB_QP_CAP;
    int ret = 0;
    if (d->qp_hw->retry.initialized)
        supported |= IB_QP_TIMEOUT | IB_QP_RETRY_CNT | IB_QP_RNR_RETRY;
    if (!attr || !initial || (mask & ~supported)) return -EOPNOTSUPP;
    /* Query and modify both use the sleepable device control mutex. Do not
     * take QP-fast across copying attributes or calling any consumer.
     */
    mutex_lock(&d->lock);
    if (!q->initialized || d->qp != q) ret = -ESTALE;
    else {
        *attr = q->attributes; attr->cur_qp_state = attr->qp_state;
        *initial = q->initial;
    }
    mutex_unlock(&d->lock); return ret;
}
static int ipv4(const union ib_gid *gid, u32 *value)
{
    static const u8 prefix[12] = {0,0,0,0,0,0,0,0,0,0,255,255};
    if (memcmp(gid->raw, prefix, 12)) return -EOPNOTSUPP;
    *value = (u32)gid->raw[12]<<24 | (u32)gid->raw[13]<<16 |
             (u32)gid->raw[14]<<8 | gid->raw[15];
    return *value ? 0 : -EINVAL;
}
static bool error_retry(int ret)
{return ret==-EAGAIN || ret==-EBUSY || ret==-ENOSPC || ret==-ETIMEDOUT;}
/* Sleepable process/work context with device lock held. No fake requester
 * abort is supplied: outstanding SEND/READ/WRITE must still retire through
 * their real native proofs. Only genuinely cancelled receives get flush WCs.
 */
static int progress_error(struct as02_verbs_device *d,struct as02_verbs_qp *q)
{
    unsigned int i;int ret;
    if(q->sq_closed && !q->hw_owned){q->error_pending=false;return 0;}
    for(i=0;i<265;i++){ret=as02_cq_hw_poll(d->cq_hw);if(ret<=0)break;}
    if(ret<0)return ret;
    if(ret>0)return -EAGAIN;
    ret=as02_sq_prepare_receive_cancel(d->sq,&q->owner);
    if(ret && ret!=-EOPNOTSUPP)return ret;
    if(q->hw_owned){
        ret=as02_qp_hw_close(d->qp_hw,q->ibqp.qp_num,q->pd->number);if(ret)return ret;
        q->hw_owned=false;
    }
    ret=as02_sq_flush_receive(d->sq,&q->owner);
    if(ret && ret!=-EOPNOTSUPP)return ret;
    if(!q->sq_closed){ret=as02_sq_close(d->sq,&q->owner);if(ret)return ret;q->sq_closed=true;}
    q->error_pending=false;return 0;
}
static void error_worker(struct work_struct *work)
{
    struct as02_verbs_qp *q=container_of(to_delayed_work(work),struct as02_verbs_qp,error_work);
    struct as02_verbs_device *d=device(q->ibqp.device);int ret;
    mutex_lock(&d->lock);
    if(q->initialized && d->qp==q && q->error_pending){
        ret=progress_error(d,q);q->error_progress_status=ret;
        if(q->error_pending && error_retry(ret))schedule_delayed_work(&q->error_work,msecs_to_jiffies(1));
    }
    mutex_unlock(&d->lock);
}
static int modify_qp(struct ib_qp *ibqp, struct ib_qp_attr *attr, int mask, struct ib_udata *u)
{
    struct as02_verbs_qp *q = container_of(ibqp, struct as02_verbs_qp, ibqp);
    struct as02_verbs_device *d = device(ibqp->device);
    struct as02_qp_route route = {};
    const struct ib_global_route *grh;
    unsigned long flags;
    enum ib_qp_state old;
    u32 local_ip;
    int ret = 0, required;
    if (!attr || private_data(u) || !(mask & IB_QP_STATE)) return -EOPNOTSUPP;
    mutex_lock(&d->lock);
    spin_lock_irqsave(&q->lock, flags);
    old = q->attributes.qp_state;
    if (!ready(d) || !q->initialized || (q->closing &&
        !(attr->qp_state==IB_QPS_ERR && q->error_requested))) ret = -ESHUTDOWN;
    spin_unlock_irqrestore(&q->lock, flags);
    if (ret) goto out;
    if(attr->qp_state==IB_QPS_ERR){
        if(mask!=IB_QP_STATE){ret=-EOPNOTSUPP;goto out;}
        spin_lock_irqsave(&q->lock,flags);
        q->closing=true;q->error_requested=true;q->error_pending=true;q->attributes.qp_state=IB_QPS_ERR;
        spin_unlock_irqrestore(&q->lock,flags);
        q->error_progress_status=progress_error(d,q);
        if(q->error_pending && error_retry(q->error_progress_status))
            schedule_delayed_work(&q->error_work,msecs_to_jiffies(1));
        /* State change is accepted, not a claim that DMA has drained. CQ
         * backpressure/late hardware replies progress in process context. */
        ret=0;goto out;
    }
    if (old == IB_QPS_RESET && attr->qp_state == IB_QPS_INIT) {
        required = IB_QP_STATE | IB_QP_PORT | IB_QP_PKEY_INDEX | IB_QP_ACCESS_FLAGS;
        if (mask != required || attr->port_num != 1 || attr->pkey_index ||
            attr->qp_access_flags != (IB_ACCESS_REMOTE_READ | IB_ACCESS_REMOTE_WRITE)) {
            ret = -EOPNOTSUPP; goto out;
        }
        q->attributes.port_num = 1; q->attributes.pkey_index = 0;
        q->attributes.qp_access_flags = attr->qp_access_flags;
    } else if (old == IB_QPS_INIT && attr->qp_state == IB_QPS_RTR) {
        required = IB_QP_STATE | IB_QP_AV | IB_QP_PATH_MTU | IB_QP_DEST_QPN |
            IB_QP_RQ_PSN | IB_QP_MAX_DEST_RD_ATOMIC | IB_QP_MIN_RNR_TIMER;
        if (mask != required || attr->path_mtu != IB_MTU_4096 || attr->rq_psn > 0xffffff ||
            attr->dest_qp_num > 0xffffff || attr->max_dest_rd_atomic != 1 || attr->min_rnr_timer ||
            attr->ah_attr.type != RDMA_AH_ATTR_TYPE_ROCE ||
            rdma_ah_get_port_num(&attr->ah_attr) != 1 ||
            rdma_ah_get_sl(&attr->ah_attr) || rdma_ah_get_static_rate(&attr->ah_attr) ||
            rdma_ah_get_ah_flags(&attr->ah_attr) != IB_AH_GRH ||
            memcmp(rdma_ah_retrieve_dmac(&attr->ah_attr), d->peer_mac, 6)) {
            ret = -EOPNOTSUPP; goto out;
        }
        grh = rdma_ah_read_grh(&attr->ah_attr);
        if (!grh->sgid_attr || grh->sgid_attr->device != ibqp->device ||
            grh->sgid_attr->port_num != 1 || grh->sgid_attr->gid_type != IB_GID_TYPE_ROCE_UDP_ENCAP ||
            grh->traffic_class || grh->flow_label || grh->hop_limit != 100) {
            ret = -EOPNOTSUPP; goto out;
        }
        ret = ipv4(&grh->sgid_attr->gid, &local_ip);
        if (ret || local_ip != d->local_ip) { ret = -EADDRNOTAVAIL; goto out; }
        ret = ipv4(&grh->dgid, &route.peer_ip); if (ret) goto out;
        route.qpn = ibqp->qp_num; route.pd = q->pd->number;
        route.local_ip = local_ip; route.peer_qpn = attr->dest_qp_num; route.rx_psn = attr->rq_psn;
        /* Open real RTR receive authority with TX PSN0. A matched new core
         * applies TX-only PSN later without resetting the live RX context.
         */
        q->hw_owned = true;
        ret = as02_qp_hw_open(d->qp_hw, &route);
        if (ret) goto failed;
        q->attributes.ah_attr = attr->ah_attr;
        /* No borrowed sgid_attr pointer retained after this callback. */
        q->attributes.ah_attr.grh.sgid_attr = NULL;
        q->attributes.path_mtu = attr->path_mtu; q->attributes.dest_qp_num = attr->dest_qp_num;
        q->attributes.rq_psn = attr->rq_psn; q->attributes.max_dest_rd_atomic = 1;
    } else if (old == IB_QPS_RTR && attr->qp_state == IB_QPS_RTS) {
        /* Mandatory standard RC knobs are accepted ONLY with the actual
         * matched RRP1 owner. Readback includes SAME-SQ cookie/epoch/PD.
         * Error CQ/recovery/core drain/user provider are still incomplete:
         * this does NOT make registration or full standard RC safe yet.
         */
        required = IB_QP_STATE | IB_QP_SQ_PSN | IB_QP_MAX_QP_RD_ATOMIC;
        if (d->qp_hw->retry.initialized)
            required |= IB_QP_TIMEOUT | IB_QP_RETRY_CNT | IB_QP_RNR_RETRY;
        if (mask != required || attr->sq_psn > 0xffffff || attr->max_rd_atomic != 1 ||
            (d->qp_hw->retry.initialized &&
             (attr->timeout > 31 || attr->retry_cnt > 7 || attr->rnr_retry > 7))) {
            ret = -EOPNOTSUPP; goto out;
        }
        if (d->qp_hw->control->control.features & AS02_CTL_FEATURE_QP_TX) {
            ret = as02_qp_hw_set_tx(d->qp_hw, ibqp->qp_num, q->pd->number, attr->sq_psn);
            if (ret) goto failed;
        } else if (attr->sq_psn) { ret = -EOPNOTSUPP; goto out; }
        if (d->qp_hw->retry.initialized) {
            ret = as02_qp_hw_set_retry(d->qp_hw, &q->owner,
                                      attr->timeout, attr->retry_cnt, attr->rnr_retry);
            if (ret) goto failed;
            q->attributes.timeout = attr->timeout;
            q->attributes.retry_cnt = attr->retry_cnt;
            q->attributes.rnr_retry = attr->rnr_retry;
        }
        q->attributes.sq_psn = attr->sq_psn; q->attributes.max_rd_atomic = 1;
    } else { ret = -EOPNOTSUPP; goto out; }
    spin_lock_irqsave(&q->lock, flags);
    q->attributes.qp_state = attr->qp_state;
    spin_unlock_irqrestore(&q->lock, flags);
    goto out;
failed:
    spin_lock_irqsave(&q->lock, flags); q->closing = true;
    q->attributes.qp_state = IB_QPS_ERR; spin_unlock_irqrestore(&q->lock, flags);
out:
    mutex_unlock(&d->lock); return ret;
}
static int post_recv(struct ib_qp *ibqp, const struct ib_recv_wr *wr,
                      const struct ib_recv_wr **bad)
{
    struct as02_verbs_qp *q=container_of(ibqp,struct as02_verbs_qp,ibqp);
    struct as02_verbs_device *d=device(ibqp->device);
    const struct ib_recv_wr *r;
    unsigned long flags;
    int ret=0;
    if(!bad)return -EINVAL;
    *bad=NULL;spin_lock_irqsave(&q->lock,flags);
    if(!ready(d) || !q->initialized || q->closing ||
        (q->attributes.qp_state!=IB_QPS_RTR && q->attributes.qp_state!=IB_QPS_RTS)) {
        ret=-ESHUTDOWN;*bad=wr;goto out;
    }
    if(!q->cap.max_recv_wr || !(d->qp_hw->control->control.features&AS02_CTL_FEATURE_RECV)) {
        ret=-EOPNOTSUPP;*bad=wr;goto out;
    }
    for(r=wr;r;r=r->next) {
        ret=as02_sq_post_recv(d->sq,&q->owner,r);
        if(ret){*bad=r;break;}
    }
out:
    spin_unlock_irqrestore(&q->lock,flags);return ret;
}
static int post_send(struct ib_qp *ibqp, const struct ib_send_wr *wr,
                      const struct ib_send_wr **bad)
{
    struct as02_verbs_qp *q = container_of(ibqp, struct as02_verbs_qp, ibqp);
    struct as02_verbs_device *d = device(ibqp->device);
    const struct ib_send_wr *w;
    unsigned long flags;
    int ret = 0;
    if (!bad) return -EINVAL;
    *bad = NULL;
    spin_lock_irqsave(&q->lock, flags);
    if (!ready(d) || !q->initialized || q->closing || q->attributes.qp_state != IB_QPS_RTS) {
        ret = -ESHUTDOWN; *bad = wr; goto out;
    }
    for (w = wr; w; w = w->next) {
        bool send=w->opcode==IB_WR_SEND || w->opcode==IB_WR_SEND_WITH_IMM;
        bool immediate=w->opcode==IB_WR_SEND_WITH_IMM || w->opcode==IB_WR_RDMA_WRITE_WITH_IMM;
        if ((immediate && (!(d->qp_hw->control->control.features&AS02_CTL_FEATURE_IMMEDIATE) ||
                !d->sq->profile_bound || d->sq->wqe_profile!=AS02_WQE_PROFILE_IMMEDIATE)) ||
            (send && !(d->qp_hw->control->control.features&AS02_CTL_FEATURE_SEND)) ||
            (!send && w->opcode!=IB_WR_RDMA_READ && w->opcode!=IB_WR_RDMA_WRITE && w->opcode!=IB_WR_RDMA_WRITE_WITH_IMM))
            ret = -EOPNOTSUPP;
        else if (q->signal_all && send) {
            struct ib_send_wr copy = *w;
            copy.send_flags |= IB_SEND_SIGNALED;
            ret = as02_sq_post(d->sq, &q->owner, &copy);
        }
        else if (q->signal_all) {
            struct ib_rdma_wr copy = *rdma_wr(w);
            copy.wr.send_flags |= IB_SEND_SIGNALED;
            ret = as02_sq_post(d->sq, &q->owner, &copy.wr);
        } else ret = as02_sq_post(d->sq, &q->owner, w);
        if (ret) { *bad = w; break; }
    }
out:
    spin_unlock_irqrestore(&q->lock, flags); return ret;
}
static int destroy_qp(struct ib_qp *ibqp, struct ib_udata *u)
{
    struct as02_verbs_qp *q = container_of(ibqp, struct as02_verbs_qp, ibqp);
    struct as02_verbs_device *d = device(ibqp->device);
    unsigned long flags;
    int ret = 0;
    (void)u;
    if(q->initialized){
        spin_lock_irqsave(&q->lock,flags);q->closing=true;spin_unlock_irqrestore(&q->lock,flags);
        cancel_delayed_work_sync(&q->error_work);
    }
    mutex_lock(&d->lock);
    spin_lock_irqsave(&q->lock, flags); q->closing = true;
    spin_unlock_irqrestore(&q->lock, flags);
    if (!q->initialized || d->qp != q) { ret = -ESTALE; goto out; }
    if (q->hw_owned) {
        ret = as02_qp_hw_close(d->qp_hw, ibqp->qp_num, q->pd->number);
        if (ret) goto out;
        q->hw_owned = false;
    }
    if (!q->sq_closed) {
        ret = as02_sq_close(d->sq, &q->owner); if (ret) goto out;
        q->sq_closed = true;
    }
    if (q->routed) {
        ret = as02_cq_router_unbind(d->router, ibqp); if (ret) goto out;
        q->routed = false;
    }
    q->pd->owners--; d->qp = NULL; q->initialized = false;q->ucontext=NULL;q->error_pending=false;
out:
    if(ret && q->initialized && q->error_pending && error_retry(q->error_progress_status))
        schedule_delayed_work(&q->error_work,msecs_to_jiffies(1));
    mutex_unlock(&d->lock); return ret;
}
int as02_verbs_reap(struct as02_verbs_device *d)
{
    unsigned int i;
    int ret = 0;
    if (!d || !d->initialized) return -EINVAL;
    mutex_lock(&d->lock);
    if (d->orphan_sq.cookie) {
        ret = as02_sq_close(d->sq, &d->orphan_sq);
        if (ret) goto out;
        d->orphan_sq_pd->owners--; d->orphan_sq_pd = NULL;
        memset(&d->orphan_sq, 0, sizeof(d->orphan_sq));
    }
    for (i = 0; i < AS02_MR_SLOTS; i++) if (d->orphan_mrs[i]) {
        struct as02_verbs_mr *m = d->orphan_mrs[i];
        ret = as02_user_mr_close(m->mapping);
        if (ret) goto out;
        m->pd->owners--; d->orphan_mrs[i] = NULL; kfree(m);
    }
out:
    mutex_unlock(&d->lock); return ret;
}
int as02_verbs_unbind(struct as02_verbs_device *d)
{
    unsigned int i;
    int ret = 0;
    if (!d || !d->initialized) return -EINVAL;
    mutex_lock(&d->lock);
    if (d->published || d->publishing || d->context_count ||
        d->pd_count || d->mr_count || d->cq_count || d->qp || d->orphan_sq.cookie) ret = -EBUSY;
    for (i = 0; i < AS02_MR_SLOTS; i++) if (d->orphan_mrs[i]) ret = -EBUSY;
    if (ret) goto out;
    WRITE_ONCE(d->stopping, true);
    ret = as02_sq_pool_put_completion_client(d->sq);
    if (!ret) ret = as02_mr_pool_put_client(d->mrs);
    if (!ret) WRITE_ONCE(d->initialized, false);
out:
    mutex_unlock(&d->lock); return ret;
}
const struct ib_device_ops as02_verbs_ops = {
    .owner = THIS_MODULE,
    .alloc_pd = alloc_pd, .dealloc_pd = dealloc_pd,
    .reg_user_mr = reg_user_mr, .dereg_mr = dereg_mr,
    .create_cq = create_cq, .destroy_cq = destroy_cq,
    .poll_cq = as02_cq_poll, .req_notify_cq = as02_cq_req_notify,
    .create_qp = create_qp, .modify_qp = modify_qp, .query_qp = query_qp, .destroy_qp = destroy_qp,
    .post_recv = post_recv,
    .post_send = post_send,
    INIT_RDMA_OBJ_SIZE(ib_pd, as02_pd, ibpd),
    INIT_RDMA_OBJ_SIZE(ib_qp, as02_verbs_qp, ibqp),
    INIT_RDMA_OBJ_SIZE(ib_cq, as02_cq, ibcq),
};
EXPORT_SYMBOL_GPL(as02_verbs_ops);
EXPORT_SYMBOL_GPL(as02_verbs_bind);
EXPORT_SYMBOL_GPL(as02_verbs_unbind);
EXPORT_SYMBOL_GPL(as02_verbs_reap);
