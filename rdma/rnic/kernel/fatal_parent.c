/* SPDX-License-Identifier: GPL-2.0 OR BSD-2-Clause-Views */
#include <linux/errno.h>
#include <linux/io.h>
#include <linux/jiffies.h>
#include <linux/module.h>
#include "verbs.h"
#include "fatal_parent.h"

int as02_fatal_parent_check(void __iomem *base,size_t bytes)
{
    u32 status,seq,ack;
    if(!base || bytes<AS02_FEC_BYTES)return -EINVAL;
    if(readl(base+AS02_FEC_ID)!=AS02_FEC_ID_VALUE ||
       readl(base+AS02_FEC_ABI)!=AS02_FEC_ABI_VALUE ||
       readl(base+AS02_FEC_FEATURES)!=AS02_FEC_FEATURE_VALUE)return -ENODEV;
    status=readl(base+AS02_FEC_STATUS);seq=readl(base+AS02_FEC_SEQUENCE);ack=readl(base+AS02_FEC_LAST_ACK);
    if(status || seq || ack || readl(base+AS02_FEC_SEQUENCE)!=seq || readl(base+AS02_FEC_STATUS)!=status)return -EBUSY;
    return 0;
}
static void poll_fatal(struct work_struct *work)
{
    struct as02_fatal_parent *h=container_of(to_delayed_work(work),struct as02_fatal_parent,poll_work);
    int ret;
    mutex_lock(&h->lock);
    if(!h->started || h->stop_requested || h->terminal){mutex_unlock(&h->lock);return;}
    mutex_unlock(&h->lock);
    /* No graph/lease/parent mutex is held across a QP-specific event handler. */
    ret=as02_fatal_verbs_poll(&h->verbs);
    mutex_lock(&h->lock);h->last_error=ret<0 ? ret:0;
    if(ret<0 && ret!=-EAGAIN && ret!=-EBUSY){
        h->terminal=true;h->started=false;
        mutex_lock(&h->verbs.device->lock);WRITE_ONCE(h->verbs.device->stopping,true);mutex_unlock(&h->verbs.device->lock);
    }
    if(h->started && !h->stop_requested && !h->terminal)
        schedule_delayed_work(&h->poll_work,msecs_to_jiffies(1));
    mutex_unlock(&h->lock);
}
int as02_fatal_parent_bind(struct as02_fatal_parent *h,struct as02_verbs_device *d,
                          void __iomem *base,size_t bytes)
{
    int ret;
    if(!h || h->initialized || h->verbs.initialized)return -EINVAL;
    mutex_init(&h->lock);INIT_DELAYED_WORK(&h->poll_work,poll_fatal);
    ret=as02_fatal_verbs_bind(&h->verbs,d,base,bytes);
    if(!ret)h->initialized=true;
    return ret;
}
int as02_fatal_parent_start(struct as02_fatal_parent *h)
{
    struct as02_verbs_device *d;int ret=0;
    if(!h || !h->initialized)return -EINVAL;
    mutex_lock(&h->lock);d=h->verbs.device;
    mutex_lock(&d->lock);
    if(h->started || h->stop_requested || h->stopped || h->terminal ||
       h->verbs.detached || !d->initialized || !d->published || !d->metadata_ready || d->stopping || d->fatal!=&h->verbs)ret=-EBUSY;
    else{h->started=true;schedule_delayed_work(&h->poll_work,0);}
    mutex_unlock(&d->lock);mutex_unlock(&h->lock);return ret;
}
int as02_fatal_parent_stop(struct as02_fatal_parent *h)
{
    int ret;
    if(!h || !h->initialized)return -EINVAL;
    if(current_work()==&h->poll_work.work)return -EDEADLK;
    mutex_lock(&h->lock);
    if(h->stopped){mutex_unlock(&h->lock);return 0;}
    h->stop_requested=true;mutex_unlock(&h->lock);
    /* Stop flag excludes every new enqueue; join without any parent/device/
     * graph/lease lock so a running handler can query/refuse destruction. */
    cancel_delayed_work_sync(&h->poll_work);
    ret=as02_fatal_verbs_detach(&h->verbs);
    mutex_lock(&h->lock);h->started=false;if(!ret)h->stopped=true;mutex_unlock(&h->lock);
    return ret;
}
EXPORT_SYMBOL_GPL(as02_fatal_parent_check);
EXPORT_SYMBOL_GPL(as02_fatal_parent_bind);
EXPORT_SYMBOL_GPL(as02_fatal_parent_start);
EXPORT_SYMBOL_GPL(as02_fatal_parent_stop);
