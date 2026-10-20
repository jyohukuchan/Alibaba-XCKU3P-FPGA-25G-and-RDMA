/* SPDX-License-Identifier: GPL-2.0 OR BSD-2-Clause-Views */
/* Complete normal native initialization: real control/MMIO/MR/queue adapters
 * -> standard device publication. Source/build/model stage, NEVER loaded.
 */
#include <linux/module.h>
#include <linux/netdevice.h>
#include <linux/slab.h>
#include "native_graph.h"

int as02_native_lease_init(struct as02_native_lease *e, u32 floor, const u64 epochs[AS02_SQ_QPS])
{
    if (!e || !epochs || floor >= AS02_MR_MAX_GENERATION) return -EINVAL;
    if (e->initialized) return -EBUSY;
    mutex_init(&e->lock);e->mr_floor=floor;
    memcpy(e->qp_epochs,epochs,sizeof(e->qp_epochs));
    e->sequence=0;e->owner=NULL;e->initialized=true;
    return 0;
}
static bool uncertain(struct as02_native_graph *g)
{
    return g->control.control.pending || g->control.control.uncertain ||
        g->sq_hw.control.pending || g->sq_hw.control.uncertain ||
        g->rq_hw.control.pending || g->rq_hw.control.uncertain ||
        g->completions.control.pending_ack || g->completions.control.uncertain ||
        g->qp.owned || g->qp.uncertain || g->qp.retry.pending || g->qp.retry.uncertain;
}
int as02_native_graph_open(const struct as02_native_binding *b, struct as02_native_lease *e,
                           struct as02_native_graph **out)
{
    struct as02_native_graph *g;
    void __iomem *bar;
    int ret;
    if(!out || *out || !b || !e || !e->initialized || !b->parent || !b->data_netdev ||
       !b->application_bar || b->application_bytes!=AS02_NATIVE_BAR_BYTES ||
       b->identity.bar_bytes!=b->application_bytes || b->data_netdev->dev.parent!=b->parent ||
       b->data_netdev->reg_state!=NETREG_REGISTERED)return -EINVAL;
    ret=as02_native_parent_validate(&b->identity);if(ret)return ret;
    g=kzalloc(sizeof(*g),GFP_KERNEL);if(!g)return -ENOMEM;
    mutex_init(&g->lock);
    mutex_lock(&e->lock);
    if(e->owner || e->sequence==U64_MAX || e->mr_floor>=AS02_MR_MAX_GENERATION ||
       e->qp_epochs[AS02_VERBS_QPN]==U64_MAX){
        ret=e->owner ? -EBUSY:-ENOSPC;mutex_unlock(&e->lock);kfree(g);return ret;
    }
    g->lease=e;g->lease_sequence=++e->sequence;e->owner=g;
    g->initial_mr_floor=e->mr_floor;
    memcpy(g->initial_qp_epochs,e->qp_epochs,sizeof(g->initial_qp_epochs));
    g->parent=get_device(b->parent);g->netdev=b->data_netdev;dev_hold(g->netdev);
    *out=g;mutex_unlock(&e->lock);
    bar=b->application_bar;
    /* Validate fresh real controllers before the epoch command. The CQ
     * read-only profile is checked here and again by its real adapter after
     * the MR epoch is established and the queue pool owns it.
     */
    ret=as02_rnic_hw_init(&g->control,bar+AS02_NATIVE_CONTROL_BASE,AS02_NATIVE_CONTROL_BYTES,1000);
    if(ret)goto failed;
    if(g->control.control.features!=AS02_CTL_FULL_NATIVE_FEATURES &&
       g->control.control.features!=AS02_CTL_IMMEDIATE_NATIVE_FEATURES){ret=-EOPNOTSUPP;goto failed;}
    if(readl(bar+AS02_NATIVE_CQ_BASE+AS02_CQC_ID)!=AS02_CQC_ID_VALUE ||
       readl(bar+AS02_NATIVE_CQ_BASE+AS02_CQC_ABI)!=AS02_CQC_ABI_VALUE ||
       readl(bar+AS02_NATIVE_CQ_BASE+AS02_CQC_FEATURES)!=
        ((g->control.control.features&AS02_CTL_FEATURE_IMMEDIATE) ?
         AS02_CQC_IMMEDIATE_FEATURE_VALUE:AS02_CQC_MESSAGE_FEATURE_VALUE)){ret=-ENODEV;goto failed;}
    g->device=as02_device_alloc();if(!g->device){ret=-ENOMEM;goto failed;}
    ret=as02_cq_router_init(&g->router);if(ret)goto failed;
    ret=as02_sq_hw_init(&g->sq_hw,bar+AS02_NATIVE_SQ_BASE,AS02_NATIVE_SQ_BYTES,30,as02_cq_publish,&g->router);
    if(ret)goto failed;
    ret=as02_sq_hw_init_receive(&g->rq_hw,&g->sq_hw,bar+AS02_NATIVE_RQ_BASE,AS02_NATIVE_RQ_BYTES,30);
    if(ret)goto failed;
    ret=as02_qp_hw_init(&g->qp,&g->control);if(ret)goto failed;
    ret=as02_qp_hw_enable_retry(&g->qp,bar+AS02_NATIVE_RETRY_BASE,AS02_RRP_BYTES,30);if(ret)goto failed;
    ret=as02_mr_pool_init(&g->mrs,&g->device->ibdev,&as02_rnic_mr_hw_ops,&g->control,g->initial_mr_floor);
    if(ret)goto failed;
    g->had_mr_pool=true;
    ret=as02_mr_pool_start_epoch(&g->mrs,g->initial_mr_floor);if(ret)goto failed;
    ret=as02_sq_pool_init(&g->queues,&g->mrs,g->parent,&as02_sqc_sq_hw_ops,&g->sq_hw,g->initial_qp_epochs);
    if(ret)goto failed;
    g->had_sq_pool=true;
    ret=as02_cq_hw_init(&g->completions,&g->queues,bar+AS02_NATIVE_CQ_BASE,AS02_CQC_BYTES);if(ret)goto failed;
    ret=as02_verbs_bind(g->device,&g->mrs,&g->queues,&g->completions,&g->qp,&g->router,
                       bar+AS02_NATIVE_ETH_BASE,AS02_NATIVE_ETH_BYTES);
    if(ret)goto failed;
    ret=as02_device_publish(g->device,g->parent,g->netdev,bar+AS02_NATIVE_ETH_BASE,AS02_NATIVE_ETH_BYTES);
    if(ret)goto failed;
    return 0;
failed:
    /* Every initialized object and ambiguous command remains visible to
     * the bus owner. No error path unmaps/frees an exposed graph behind it.
     */
    g->open_error=ret;return ret;
}
int as02_native_graph_reconcile_control(struct as02_native_graph *g, struct as02_ctl_reply *reply)
{
    int ret;
    if(!g || !reply)return -EINVAL;
    mutex_lock(&g->lock);ret=as02_rnic_hw_reconcile(&g->control,reply);mutex_unlock(&g->lock);
    return ret;
}
int as02_native_graph_close(struct as02_native_graph **handle)
{
    struct as02_native_graph *g;
    struct as02_native_lease *e;
    unsigned int i;
    int ret=0;
    if(!handle || !*handle)return -EINVAL;
    g=*handle;e=g->lease;mutex_lock(&g->lock);mutex_lock(&e->lock);
    if(e->owner!=g || e->sequence!=g->lease_sequence){ret=-ESTALE;goto out;}
    if(uncertain(g) || g->queues.queue_count || g->mrs.mapping_count){ret=-EBUSY;goto out;}
    if(g->device && g->device->initialized){
        ret=as02_device_unpublish(g->device);if(ret)goto out;
        ret=as02_verbs_unbind(g->device);if(ret)goto out;
    }
    if(g->completions.control.initialized && !g->completions.control.detached){
        ret=as02_cq_hw_detach(&g->completions);if(ret)goto out;
    }
    if(g->queues.initialized){ret=as02_sq_pool_destroy(&g->queues);if(ret)goto out;}
    if(g->mrs.initialized){ret=as02_mr_pool_destroy(&g->mrs);if(ret)goto out;}
    if(g->rq_hw.control.initialized && !g->rq_hw.control.detached){ret=as02_sq_hw_detach(&g->rq_hw);if(ret)goto out;}
    if(g->sq_hw.control.initialized && !g->sq_hw.control.detached){ret=as02_sq_hw_detach(&g->sq_hw);if(ret)goto out;}
    if(g->control.control.initialized && !g->control.control.detached){ret=as02_rnic_hw_detach(&g->control);if(ret)goto out;}
    if(g->device){ret=as02_device_free(g->device);if(ret)goto out;g->device=NULL;}
    /* Only after successful normal closure, never from a count/quiet-time
     * heuristic. These memory watermarks still require caller persistence
     * across driver/process/OS lifetimes before another attachment.
     */
    if(g->had_mr_pool && g->mrs.epoch.highest>e->mr_floor)e->mr_floor=g->mrs.epoch.highest;
    if(g->had_sq_pool)for(i=0;i<AS02_SQ_QPS;i++)
        if(g->queues.epoch_watermark[i]>e->qp_epochs[i])e->qp_epochs[i]=g->queues.epoch_watermark[i];
    e->owner=NULL;*handle=NULL;
out:
    mutex_unlock(&e->lock);mutex_unlock(&g->lock);
    if(!ret){dev_put(g->netdev);put_device(g->parent);kfree(g);}
    return ret;
}
EXPORT_SYMBOL_GPL(as02_native_lease_init);
EXPORT_SYMBOL_GPL(as02_native_graph_open);
EXPORT_SYMBOL_GPL(as02_native_graph_reconcile_control);
EXPORT_SYMBOL_GPL(as02_native_graph_close);
