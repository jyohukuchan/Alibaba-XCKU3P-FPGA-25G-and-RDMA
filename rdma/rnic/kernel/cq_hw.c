/* SPDX-License-Identifier: GPL-2.0 OR BSD-2-Clause-Views */
#include <linux/errno.h>
#include <linux/lockdep.h>
#include <linux/module.h>
#include <linux/jiffies.h>
#include "cq_hw.h"

static int reg_read(void *context,as02_u32 offset,as02_u32 *value)
{
    struct as02_cq_hw *h=context;
    lockdep_assert_held(&h->lock);
    if(!h->registers || h->control.detached)return -ENODEV;
    if(offset&3 || offset>=AS02_CQC_BYTES)return -EINVAL;
    *value=readl(h->registers+offset);return 0;
}
static int reg_write(void *context,as02_u32 offset,as02_u32 value)
{
    struct as02_cq_hw *h=context;
    lockdep_assert_held(&h->lock);
    if(!h->registers || h->control.detached)return -ENODEV;
    if(offset!=AS02_CQC_ACK)return -EINVAL;
    writel(value,h->registers+offset);return 0;
}
static const struct as02_cq_transport actual_mmio={.read32=reg_read,.write32=reg_write};
static int deliver(void *context,const struct as02_cq_decoded *event)
{
    return as02_sq_complete_event(context,event);
}
static void poll_notifications(struct work_struct *work)
{
    struct as02_cq_hw *h=container_of(to_delayed_work(work),struct as02_cq_hw,poll_work);
    int ret=as02_cq_hw_poll(h);
    if(ret<0 && ret!=-EAGAIN && ret!=-ENOSPC)return;
    if(atomic_read(&h->notify_users) || READ_ONCE(h->control.pending_ack))
        schedule_delayed_work(&h->poll_work,msecs_to_jiffies(1));
}
int as02_cq_hw_init(struct as02_cq_hw *h,struct as02_sq_pool *p,void __iomem *base,size_t bytes)
{
    unsigned long flags;
    int ret;
    if(!h || !p || !base || bytes<AS02_CQC_BYTES)return -EINVAL;
    if(h->control.initialized || h->control.detached)return -EBUSY;
    ret=as02_sq_pool_get_completion_client(p);
    if(ret)return ret;
    spin_lock_init(&h->lock);h->pool=p;h->registers=base;
    atomic_set(&h->notify_users,0);INIT_DELAYED_WORK(&h->poll_work,poll_notifications);
    spin_lock_irqsave(&h->lock,flags);
    ret=as02_cq_io_init(&h->control,&actual_mmio,h);
    spin_unlock_irqrestore(&h->lock,flags);
    if(ret){h->pool=NULL;h->registers=NULL;as02_sq_pool_put_completion_client(p);}
    return ret;
}
int as02_cq_hw_poll(void *context)
{
    struct as02_cq_hw *h=context;
    unsigned long flags;
    int ret;
    if(!h || !h->control.initialized)return -EINVAL;
    spin_lock_irqsave(&h->lock,flags);
    ret=as02_cq_io_poll(&h->control,deliver,h->pool);
    spin_unlock_irqrestore(&h->lock,flags);
    return ret;
}
int as02_cq_hw_detach(struct as02_cq_hw *h)
{
    struct as02_sq_pool *p;
    unsigned long flags;
    int ret;
    if(!h || !h->control.initialized || h->control.detached)return -EINVAL;
    p=h->pool;
    mutex_lock(&p->lock);
    spin_lock_irqsave(&p->fast_lock,flags);
    ret=p->queue_count ? -EBUSY : 0;
    spin_unlock_irqrestore(&p->fast_lock,flags);
    if(ret)goto out;
    spin_lock_irqsave(&h->lock,flags);
    ret=h->cq_clients ? -EBUSY : as02_cq_io_detach(&h->control);
    if(!ret){h->registers=NULL;h->pool=NULL;}
    spin_unlock_irqrestore(&h->lock,flags);
out:
    mutex_unlock(&p->lock);
    if(!ret){cancel_delayed_work_sync(&h->poll_work);ret=as02_sq_pool_put_completion_client(p);}
    return ret;
}
int as02_cq_hw_get_client(struct as02_cq_hw *h)
{
    unsigned long flags;
    int ret=0;
    if(!h || !h->control.initialized)return -EINVAL;
    spin_lock_irqsave(&h->lock,flags);
    if(h->control.detached || h->control.uncertain || h->cq_clients==(unsigned int)-1)ret=-ESHUTDOWN;
    else h->cq_clients++;
    spin_unlock_irqrestore(&h->lock,flags);
    return ret;
}
int as02_cq_hw_put_client(struct as02_cq_hw *h)
{
    unsigned long flags;
    int ret=0;
    if(!h || !h->control.initialized)return -EINVAL;
    spin_lock_irqsave(&h->lock,flags);
    if(!h->cq_clients)ret=-EINVAL;
    else h->cq_clients--;
    spin_unlock_irqrestore(&h->lock,flags);
    return ret;
}
void as02_cq_hw_arm(struct as02_cq_hw *h)
{
    atomic_inc(&h->notify_users);
    schedule_delayed_work(&h->poll_work,0);
}
void as02_cq_hw_disarm(struct as02_cq_hw *h)
{
    atomic_dec(&h->notify_users);
}
EXPORT_SYMBOL_GPL(as02_cq_hw_init);
EXPORT_SYMBOL_GPL(as02_cq_hw_poll);
EXPORT_SYMBOL_GPL(as02_cq_hw_detach);
EXPORT_SYMBOL_GPL(as02_cq_hw_get_client);
EXPORT_SYMBOL_GPL(as02_cq_hw_put_client);
EXPORT_SYMBOL_GPL(as02_cq_hw_arm);
EXPORT_SYMBOL_GPL(as02_cq_hw_disarm);
