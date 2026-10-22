/* SPDX-License-Identifier: GPL-2.0 OR BSD-2-Clause-Views */
#include <linux/errno.h>
#include <linux/io.h>
#include <linux/jiffies.h>
#include <linux/module.h>
#include "verbs.h"
#include "atomic_profile.h"
#include "rnic_regs.h"

static int fatal_read(void *context,as02_u32 off,as02_u32 *value)
{
    struct as02_fatal_verbs *h=context;
    if(!h->registers || h->detached)return -ENODEV;
    if((off&3) || off>=AS02_FEC_BYTES)return -EINVAL;
    *value=readl(h->registers+off);return 0;
}
static int fatal_write(void *context,as02_u32 off,as02_u32 value)
{
    struct as02_fatal_verbs *h=context;
    if(!h->registers || h->detached)return -ENODEV;
    if(off!=AS02_FEC_ACK)return -EINVAL;
    writel(value,h->registers+off);return 0;
}
static const struct as02_fatal_transport fatal_transport={fatal_read,fatal_write};

int as02_fatal_verbs_bind(struct as02_fatal_verbs *h,struct as02_verbs_device *d,
                         void __iomem *registers,size_t bytes)
{
    int ret;
    if(!h || !d || !registers || bytes<AS02_FEC_BYTES || !d->initialized)return -EINVAL;
    if(h->initialized || h->reader.initialized || h->detached)return -EBUSY;
    mutex_init(&h->lock);mutex_lock(&h->lock);mutex_lock(&d->lock);
    if(!d->initialized || d->stopping || d->fatal || d->qp || !d->sq || !d->qp_hw ||
       !d->sq->profile_bound || d->sq->wqe_profile!=AS02_WQE_PROFILE_SEGMENTED_WRITE128 ||
       !d->qp_hw->initialized || !d->qp_hw->control ||
       d->qp_hw->control->control.features!=AS02_CTL_SEGMENTED_WRITE_NATIVE_FEATURES){ret=-EBUSY;goto out;}
    h->device=d;h->registers=registers;
    ret=as02_fatal_io_init(&h->reader,&fatal_transport,h);
    if(ret){h->device=NULL;h->registers=NULL;goto out;}
    h->initialized=true;d->fatal=h;
out:
    mutex_unlock(&d->lock);mutex_unlock(&h->lock);return ret;
}

/* Called by the real reader with attachment lock held. Device control lock
 * protects the registry and derived destroy path; QP-fast protects posting.
 * Never borrow only QPN or a different RNC command/packet-message cookie.
 */
static int fatal_record(void *context,const struct as02_fatal_decoded *event)
{
    struct as02_fatal_verbs *h=context;
    struct as02_verbs_device *d=h->device;
    struct as02_verbs_qp *q;
    struct as02_fatal_identity owner;
    unsigned long flags;int ret=-ESTALE;
    mutex_lock(&d->lock);q=d->qp;
    if(d->fatal!=h || !d->initialized || !q || !q->initialized || !q->pd ||
       !q->pd->live || !q->routed || !q->hw_owned || q->sq_closed || h->notification_qp)goto out;
    owner=(struct as02_fatal_identity){.cookie=q->owner.cookie,.epoch=q->owner.epoch,
        .qpn=q->owner.qpn,.pd=q->owner.pd};
    if(q->ibqp.qp_num!=owner.qpn || q->pd->number!=owner.pd ||
       !as02_fatal_identity_matches(event,&owner))goto out;
    spin_lock_irqsave(&q->lock,flags);
    if(q->fatal_event_recorded || (q->closing && !q->error_requested))goto unlock;
    if(q->attributes.qp_state!=IB_QPS_RTR && q->attributes.qp_state!=IB_QPS_RTS &&
       !(q->attributes.qp_state==IB_QPS_ERR && q->error_requested))goto unlock;
    q->fatal_event=*event;q->fatal_event_recorded=true;
    q->fatal_event_callback_pending=true;q->fatal_event_callback_active=false;
    q->closing=true;q->error_requested=true;q->error_pending=true;
    q->error_progress_status=-EAGAIN;q->attributes.qp_state=IB_QPS_ERR;
    /* These actual per-QP flags prevent destroy AND error/flush progress
     * until the external notification handler returns. No reference is put.
     */
    h->notification_qp=q;ret=0;
unlock:
    spin_unlock_irqrestore(&q->lock,flags);
out:
    mutex_unlock(&d->lock);return ret;
}

int as02_fatal_verbs_poll(struct as02_fatal_verbs *h)
{
    struct as02_verbs_device *d;
    struct as02_verbs_qp *q;
    struct ib_event event={};
    void (*handler)(struct ib_event *,void *)=NULL;void *context=NULL;
    unsigned long flags;int ret;
    if(!h || !h->initialized)return -EINVAL;
    mutex_lock(&h->lock);
    if(h->detached){ret=-ENODEV;goto out;}
    if(h->polling){ret=-EBUSY;goto out;}
    h->polling=true;d=h->device;
    ret=as02_fatal_io_poll(&h->reader,fatal_record,h);
    mutex_lock(&d->lock);
    if(h->reader.uncertain)WRITE_ONCE(d->stopping,true);
    q=h->notification_qp;
    if(q){
        /* The derived destroy guard must still own this actual allocation.
         * A violated registry freezes the attachment without dereferencing a
         * stale pointer or pretending a drain/ACK completed.
         */
        if(d->qp!=q || !q->initialized || !q->fatal_event_callback_pending){
            h->reader.uncertain=1;WRITE_ONCE(d->stopping,true);ret=-ESTALE;
            mutex_unlock(&d->lock);h->polling=false;goto out;
        }
        spin_lock_irqsave(&q->lock,flags);q->fatal_event_callback_active=true;
        event.device=&d->ibdev;event.element.qp=&q->ibqp;
        event.event=q->fatal_event.syndrome==0x61 ? IB_EVENT_QP_REQ_ERR:
            q->fatal_event.syndrome==0x62 ? IB_EVENT_QP_ACCESS_ERR:IB_EVENT_QP_FATAL;
        handler=q->ibqp.event_handler;context=q->ibqp.qp_context;
        spin_unlock_irqrestore(&q->lock,flags);
    }
    mutex_unlock(&d->lock);mutex_unlock(&h->lock);
    if(q && handler)handler(&event,context);
    /* No driver lock is held across the QP-specific handler. Reentrant poll
     * or detach is rejected by polling, and genuine destroy sees QP guards.
     */
    mutex_lock(&h->lock);mutex_lock(&d->lock);
    if(q){
        if(d->qp!=q || !q->initialized){
            h->reader.uncertain=1;WRITE_ONCE(d->stopping,true);ret=-ESTALE;
        }else{
            spin_lock_irqsave(&q->lock,flags);
            q->fatal_event_callback_active=false;q->fatal_event_callback_pending=false;
            q->fatal_event_notified=true;
            spin_unlock_irqrestore(&q->lock,flags);
            h->notification_qp=NULL;
            if(q->error_pending)schedule_delayed_work(&q->error_work,msecs_to_jiffies(1));
        }
    }
    mutex_unlock(&d->lock);h->polling=false;
out:
    mutex_unlock(&h->lock);return ret;
}

int as02_fatal_verbs_detach(struct as02_fatal_verbs *h)
{
    int ret;
    if(!h || !h->initialized)return -EINVAL;
    mutex_lock(&h->lock);
    if(h->polling){ret=-EBUSY;goto out;}
    if(h->detached){ret=-ENODEV;goto out;}
    mutex_lock(&h->device->lock);
    ret=as02_fatal_io_detach(&h->reader);
    if(!ret){h->detached=true;WRITE_ONCE(h->device->stopping,true);}
    /* d->fatal and all real parent/device/QP/MR/queue/BAR ownership remain. */
    mutex_unlock(&h->device->lock);
out:
    mutex_unlock(&h->lock);return ret;
}
EXPORT_SYMBOL_GPL(as02_fatal_verbs_bind);
EXPORT_SYMBOL_GPL(as02_fatal_verbs_poll);
EXPORT_SYMBOL_GPL(as02_fatal_verbs_detach);
