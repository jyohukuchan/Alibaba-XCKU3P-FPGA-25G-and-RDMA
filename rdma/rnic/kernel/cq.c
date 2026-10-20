/* SPDX-License-Identifier: GPL-2.0 OR BSD-2-Clause-Views */
#include <linux/errno.h>
#include <linux/module.h>
#include <linux/slab.h>
#include "cq.h"

static void notify(struct irq_work *work)
{
    struct as02_cq *c=container_of(work,struct as02_cq,notify);
    if(!READ_ONCE(c->closing) && !READ_ONCE(c->user_closed) &&
       READ_ONCE(c->initialized) && c->ibcq.comp_handler)
        c->ibcq.comp_handler(&c->ibcq,c->ibcq.cq_context);
}
int as02_cq_create(struct ib_cq *cq,const struct ib_cq_init_attr *attr,struct ib_udata *udata)
{
    struct as02_cq *c;
    if(!cq || !attr || attr->cqe<1 || attr->cqe>AS02_CQ_MAX_ENTRIES || attr->comp_vector || attr->flags)
        return -EINVAL;
    /* Generic legacy CQ commands need no private payload; unsupported
     * provider-specific extensions are refused rather than silently ignored.
     */
    if(udata && (udata->inlen || udata->outlen))return -EOPNOTSUPP;
    c=container_of(cq,struct as02_cq,ibcq);
    if(c->initialized || c->entries)return -EBUSY;
    c->entries=kcalloc(attr->cqe,sizeof(*c->entries),GFP_KERNEL);
    if(!c->entries)return -ENOMEM;
    spin_lock_init(&c->lock);init_irq_work(&c->notify,notify);
    c->capacity=attr->cqe;c->producer=0;c->consumer=0;c->pending=0;c->queue_refs=0;
    c->closing=false;c->armed=false;c->user_closed=false;c->hardware=NULL;cq->cqe=attr->cqe;
    WRITE_ONCE(c->initialized,true);return 0;
}
int as02_cq_attach_hardware(struct as02_cq *c,struct as02_cq_hw *h)
{
    unsigned long flags;
    int ret;
    if(!c || !h || !c->initialized || !h->pool || h->pool->mrs->ibdev!=c->ibcq.device)
        return -EINVAL;
    ret=as02_cq_hw_get_client(h);if(ret)return ret;
    spin_lock_irqsave(&c->lock,flags);
    if(c->closing || c->hardware || c->queue_refs || c->pending)ret=-EBUSY;
    else c->hardware=h;
    spin_unlock_irqrestore(&c->lock,flags);
    if(ret)as02_cq_hw_put_client(h);
    return ret;
}
int as02_cq_router_init(struct as02_cq_router *r)
{
    if(!r || r->initialized)return -EINVAL;
    memset(r,0,sizeof(*r));spin_lock_init(&r->lock);r->initialized=true;return 0;
}
int as02_cq_router_bind(struct as02_cq_router *r,struct as02_cq *c,struct ib_qp *qp)
{
    struct as02_cq *rc;
    unsigned long flags,cflags,rcflags=0;
    int ret=0;
    if(!r || !r->initialized || !c || !c->initialized || !qp || qp->qp_num>=AS02_SQ_QPS ||
        qp->device!=c->ibcq.device || qp->send_cq!=&c->ibcq || !qp->recv_cq ||
        qp->recv_cq->device!=qp->device)return -EINVAL;
    rc=container_of(qp->recv_cq,struct as02_cq,ibcq);
    if(!rc->initialized)return -EINVAL;
    spin_lock_irqsave(&r->lock,flags);
    spin_lock_irqsave(&c->lock,cflags);
    /* The router serializes every two-CQ acquisition; other paths lock just
     * one CQ, so opposite send/receive assignments cannot invert locks. */
    if(rc!=c)spin_lock_irqsave(&rc->lock,rcflags);
    if(r->qp[qp->qp_num] || c->closing || rc->closing || !c->hardware ||
       rc->hardware!=c->hardware)ret=-EBUSY;
    else{
        r->qp[qp->qp_num]=qp;r->cq[qp->qp_num]=c;r->recv_cq[qp->qp_num]=rc;
        r->abandoning[qp->qp_num]=false;
        c->queue_refs++;if(rc!=c)rc->queue_refs++;
    }
    if(rc!=c)spin_unlock_irqrestore(&rc->lock,rcflags);
    spin_unlock_irqrestore(&c->lock,cflags);
    spin_unlock_irqrestore(&r->lock,flags);
    return ret;
}
int as02_cq_router_unbind(struct as02_cq_router *r,struct ib_qp *qp)
{
    struct as02_cq *c,*rc;
    unsigned long flags,cflags,rcflags=0;
    int ret=0;
    if(!r || !r->initialized || !qp || qp->qp_num>=AS02_SQ_QPS)return -EINVAL;
    spin_lock_irqsave(&r->lock,flags);
    c=r->cq[qp->qp_num];rc=r->recv_cq[qp->qp_num];
    if(r->qp[qp->qp_num]!=qp || !c || !rc){ret=-ESTALE;goto out;}
    spin_lock_irqsave(&c->lock,cflags);
    if(rc!=c)spin_lock_irqsave(&rc->lock,rcflags);
    if(c->pending || rc->pending)ret=-EBUSY;
    else{
        r->qp[qp->qp_num]=NULL;r->cq[qp->qp_num]=NULL;r->recv_cq[qp->qp_num]=NULL;
        r->abandoning[qp->qp_num]=false;
        c->queue_refs--;if(rc!=c)rc->queue_refs--;
    }
    if(rc!=c)spin_unlock_irqrestore(&rc->lock,rcflags);
    spin_unlock_irqrestore(&c->lock,cflags);
out:
    spin_unlock_irqrestore(&r->lock,flags);return ret;
}
static void discard_qp_entries(struct as02_cq *c,struct ib_qp *qp)
{
    u32 read=c->consumer,write=c->consumer,old=c->pending,kept=0,i;
    /* Compact in logical ring order, including wrap. Other QPs' entries
     * retain order and contents; no user WR id is interpreted as a pointer.
     */
    for(i=0;i<old;i++){
        struct ib_wc wc=c->entries[read];
        read=(read+1)%c->capacity;
        if(wc.qp!=qp){c->entries[write]=wc;write=(write+1)%c->capacity;kept++;}
    }
    c->producer=write;c->pending=kept;
    for(i=kept;i<old;i++){
        memset(&c->entries[write],0,sizeof(*c->entries));write=(write+1)%c->capacity;
    }
}
static void stop_user_notifications(struct as02_cq *c)
{
    WRITE_ONCE(c->user_closed,true);
    if(c->armed){c->armed=false;as02_cq_hw_disarm(c->hardware);}
}
int as02_cq_router_abandon(struct as02_cq_router *r,struct ib_qp *qp)
{
    struct as02_cq *c,*rc;
    unsigned long flags,cflags,rcflags=0;
    int ret=0;
    if(!r || !r->initialized || !qp || qp->qp_num>=AS02_SQ_QPS)return -EINVAL;
    spin_lock_irqsave(&r->lock,flags);
    c=r->cq[qp->qp_num];rc=r->recv_cq[qp->qp_num];
    if(r->qp[qp->qp_num]!=qp || !c || !rc){ret=-ESTALE;goto out;}
    spin_lock_irqsave(&c->lock,cflags);
    if(rc!=c)spin_lock_irqsave(&rc->lock,rcflags);
    if(!c->initialized || !rc->initialized || c->closing || rc->closing)ret=-ESHUTDOWN;
    else{
        r->abandoning[qp->qp_num]=true;
        discard_qp_entries(c,qp);if(rc!=c)discard_qp_entries(rc,qp);
        stop_user_notifications(c);if(rc!=c)stop_user_notifications(rc);
    }
    if(rc!=c)spin_unlock_irqrestore(&rc->lock,rcflags);
    spin_unlock_irqrestore(&c->lock,cflags);
out:
    spin_unlock_irqrestore(&r->lock,flags);return ret;
}
int as02_cq_publish(void *context,const struct as02_sq_completion *event)
{
    struct as02_cq_router *r=context;
    struct as02_cq *c;
    struct ib_qp *qp;
    struct ib_wc wc={};
    unsigned long flags,cflags;
    bool signal=false;
    int ret=0;
    if(!r || !r->initialized || !event || event->qpn>=AS02_SQ_QPS ||
       event->status>IB_WC_GENERAL_ERR ||
       (event->opcode!=AS02_WQE_READ && event->opcode!=AS02_WQE_WRITE &&
        event->opcode!=AS02_WQE_SEND && event->opcode!=AS02_WQE_RECV &&
        event->opcode!=AS02_WQE_SEND_IMMEDIATE && event->opcode!=AS02_WQE_WRITE_IMMEDIATE))return -EINVAL;
    if((event->notification_flags!=0 && event->notification_flags!=1 && event->notification_flags!=3) ||
       (event->notification_flags && (event->opcode!=AS02_WQE_RECV || event->status!=IB_WC_SUCCESS)) ||
       (!event->notification_flags && event->notification))return -EINVAL;
    spin_lock_irqsave(&r->lock,flags);
    c=event->opcode==AS02_WQE_RECV ? r->recv_cq[event->qpn] : r->cq[event->qpn];
    qp=r->qp[event->qpn];
    if(!c || !qp){ret=-ESTALE;goto out;}
    spin_lock_irqsave(&c->lock,cflags);
    if(!c->initialized || c->closing){ret=-ESHUTDOWN;goto cq_out;}
    /* The actual native CQ decoder and SAME-WQE/MR/proof checks have already
     * succeeded. A closed user file no longer needs WC metadata, but this
     * success alone is NOT a native event or queue-retirement certificate.
     */
    if(r->abandoning[event->qpn])goto cq_out;
    if(c->pending==c->capacity){ret=-ENOSPC;goto cq_out;}
    wc.wr_id=event->wr_id;wc.qp=qp;wc.status=event->status;
    wc.opcode=event->opcode==AS02_WQE_READ ? IB_WC_RDMA_READ :
        (event->opcode==AS02_WQE_SEND || event->opcode==AS02_WQE_SEND_IMMEDIATE) ? IB_WC_SEND :
        event->opcode==AS02_WQE_RECV ? (event->notification_flags==3 ? IB_WC_RECV_RDMA_WITH_IMM:IB_WC_RECV) : IB_WC_RDMA_WRITE;
    wc.byte_len=(event->opcode==AS02_WQE_READ || event->opcode==AS02_WQE_RECV) ? event->length : 0;
    if(event->notification_flags){wc.wc_flags=IB_WC_WITH_IMM;wc.ex.imm_data=cpu_to_be32(event->notification);}
    c->entries[c->producer]=wc;c->producer=(c->producer+1)%c->capacity;c->pending++;
    if(c->armed){c->armed=false;as02_cq_hw_disarm(c->hardware);signal=true;}
cq_out:
    spin_unlock_irqrestore(&c->lock,cflags);
    if(signal)irq_work_queue(&c->notify);
out:
    spin_unlock_irqrestore(&r->lock,flags);return ret;
}
int as02_cq_poll(struct ib_cq *cq,int count,struct ib_wc *wc)
{
    struct as02_cq *c;
    unsigned long flags;
    int n=0,progress=0;
    if(!cq || count<0 || (count && !wc))return -EINVAL;
    if(!count)return 0;
    c=container_of(cq,struct as02_cq,ibcq);
    if(!READ_ONCE(c->initialized) || READ_ONCE(c->closing))return -ESHUTDOWN;
    /* Never hold CQ lock while entering CQ-MMIO -> SQ -> publish_cqe. */
    if(c->hardware)progress=as02_cq_hw_poll(c->hardware);
    spin_lock_irqsave(&c->lock,flags);
    while(n<count && c->pending){
        wc[n++]=c->entries[c->consumer];memset(&c->entries[c->consumer],0,sizeof(*wc));
        c->consumer=(c->consumer+1)%c->capacity;c->pending--;
    }
    spin_unlock_irqrestore(&c->lock,flags);
    if(n)return n;
    return progress<0 && progress!=-EAGAIN && progress!=-ENOSPC ? progress : 0;
}
int as02_cq_req_notify(struct ib_cq *cq,enum ib_cq_notify_flags flags)
{
    struct as02_cq *c;
    unsigned long irqflags;
    int missed;
    if(!cq || (flags&~(IB_CQ_NEXT_COMP|IB_CQ_REPORT_MISSED_EVENTS)) || !(flags&IB_CQ_NEXT_COMP))
        return -EOPNOTSUPP;
    c=container_of(cq,struct as02_cq,ibcq);
    if(!c->initialized)return -EINVAL;
    spin_lock_irqsave(&c->lock,irqflags);
    if(c->closing || c->user_closed){spin_unlock_irqrestore(&c->lock,irqflags);return -ESHUTDOWN;}
    if(!c->hardware){spin_unlock_irqrestore(&c->lock,irqflags);return -ENODEV;}
    if(!c->armed){c->armed=true;as02_cq_hw_arm(c->hardware);}
    missed=!!(flags&IB_CQ_REPORT_MISSED_EVENTS) && !!c->pending;
    spin_unlock_irqrestore(&c->lock,irqflags);return missed;
}
int as02_cq_destroy(struct ib_cq *cq,struct ib_udata *udata)
{
    struct as02_cq *c;
    struct as02_cq_hw *h;
    unsigned long flags;
    (void)udata;
    if(!cq)return -EINVAL;
    c=container_of(cq,struct as02_cq,ibcq);
    if(!c->initialized)return -EINVAL;
    spin_lock_irqsave(&c->lock,flags);
    if(c->queue_refs || c->pending){spin_unlock_irqrestore(&c->lock,flags);return -EBUSY;}
    c->closing=true;h=c->hardware;
    if(c->armed){c->armed=false;as02_cq_hw_disarm(h);}
    c->hardware=NULL;
    spin_unlock_irqrestore(&c->lock,flags);
    irq_work_sync(&c->notify);
    kfree(c->entries);c->entries=NULL;WRITE_ONCE(c->initialized,false);
    return h ? as02_cq_hw_put_client(h) : 0;
}
EXPORT_SYMBOL_GPL(as02_cq_create);
EXPORT_SYMBOL_GPL(as02_cq_destroy);
EXPORT_SYMBOL_GPL(as02_cq_poll);
EXPORT_SYMBOL_GPL(as02_cq_req_notify);
EXPORT_SYMBOL_GPL(as02_cq_attach_hardware);
EXPORT_SYMBOL_GPL(as02_cq_router_init);
EXPORT_SYMBOL_GPL(as02_cq_router_bind);
EXPORT_SYMBOL_GPL(as02_cq_router_unbind);
EXPORT_SYMBOL_GPL(as02_cq_router_abandon);
EXPORT_SYMBOL_GPL(as02_cq_publish);
