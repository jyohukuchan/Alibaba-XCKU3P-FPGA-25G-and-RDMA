/* SPDX-License-Identifier: GPL-2.0 OR BSD-2-Clause-Views */
/* Standard RDMA publication of the actual bound graph. Never loaded here.
 * Kernel registration/netdev/pin/DMA/hot-unplug runtime still needs physical
 * qualification. No fake get_dma_mr, CM, MAD, Atomic or direct user BAR mmap.
 */
#include <linux/etherdevice.h>
#include <linux/module.h>
#include <linux/netdevice.h>
#include <rdma/ib_user_verbs.h>
#include "device.h"
#include "native_regs.h"
#include "sq_hw.h"

static struct as02_verbs_device *dev(struct ib_device *ibdev)
{ return container_of(ibdev, struct as02_verbs_device, ibdev); }
static bool ready(struct as02_verbs_device *d)
{ return d->initialized && !d->stopping && d->metadata_ready; }

/* RNE1 is an already committed fixed IPv4/MAC route. GID callbacks validate
 * that exact hardware route; they do not pretend to program a missing table.
 */
static int route(struct as02_verbs_device *d)
{
    u32 epoch, status, lo, hi, i;
    u8 mac[6];
    if (!d->ethernet_registers || !d->netdev) return -ENODEV;
    epoch = readl(d->ethernet_registers + AS02_ETH_EPOCH);
    status = readl(d->ethernet_registers + AS02_ETH_STATUS);
    if (!epoch || epoch != d->route_epoch ||
        (status & (AS02_ETH_ST_ENABLED | AS02_ETH_ST_COMMITTED)) !=
        (AS02_ETH_ST_ENABLED | AS02_ETH_ST_COMMITTED) ||
        (status & ~(AS02_ETH_ST_ENABLED | AS02_ETH_ST_SAFE | AS02_ETH_ST_COMMITTED)))
        return -ESTALE;
    lo = readl(d->ethernet_registers + AS02_ETH_ACTIVE);
    hi = readl(d->ethernet_registers + AS02_ETH_ACTIVE + 4);
    if (hi > 65535) return -EPROTO;
    for (i = 0; i < 4; i++) mac[5-i] = lo >> (i*8);
    mac[1] = hi; mac[0] = hi >> 8;
    if (!ether_addr_equal(mac, d->local_mac) ||
        !ether_addr_equal(mac, d->netdev->dev_addr) ||
        readl(d->ethernet_registers + AS02_ETH_ACTIVE + 16) != d->local_ip ||
        readl(d->ethernet_registers + AS02_ETH_ACTIVE + 20) != 1 ||
        readl(d->ethernet_registers + AS02_ETH_EPOCH) != epoch)
        return -ESTALE;
    return 0;
}
static int query_device(struct ib_device *ibdev, struct ib_device_attr *a,
                         struct ib_udata *u)
{
    struct as02_verbs_device *d = dev(ibdev);
    if (!a || (u && (u->inlen || u->outlen))) return -EOPNOTSUPP;
    if (!ready(d)) return -ESHUTDOWN;
    memset(a, 0, sizeof(*a));
    a->fw_ver = ((u64)AS02_CTL_ABI_VALUE << 32) | d->qp_hw->control->control.features;
    a->sys_image_guid = ibdev->node_guid;
    a->max_mr_size = AS02_MR_MAX_PAGES * 4096ULL;
    a->page_size_cap = 4096; a->vendor_id = 0x1234; a->vendor_part_id = 0x1001;
    a->hw_ver = AS02_CTL_ABI_VALUE;
    a->max_qp = 1; a->max_qp_wr = 256;
    a->max_send_sge = 1; a->max_recv_sge = 1; a->max_sge_rd = 1;
    /* Software CQs share one native completion publisher; allocation can
     * still fail for memory pressure, as with the existing real CQ API.
     */
    a->max_cq = AS02_VERBS_MAX_CQS; a->max_cqe = AS02_CQ_MAX_ENTRIES;
    a->max_mr = AS02_MR_SLOTS; a->max_pd = 65535;
    a->max_qp_rd_atom = 1; a->max_res_rd_atom = 1; a->max_qp_init_rd_atom = 1;
    a->atomic_cap = IB_ATOMIC_NONE; a->max_pkeys = 1;
    return 0;
}
static int query_port(struct ib_device *ibdev, u32 port, struct ib_port_attr *a)
{
    struct as02_verbs_device *d = dev(ibdev);
    bool up;
    int ret;
    if (port != 1 || !a) return -EINVAL;
    if (!ready(d)) return -ESHUTDOWN;
    ret = route(d); if (ret) return ret;
    memset(a, 0, sizeof(*a));
    /* Current actual QP implementation accepts PMTU4096 only. Worst-case
     * single-packet WRITE has60bytes of IP/UDP/BTH/RETH/ICRC overhead.
     */
    up = netif_running(d->netdev) && netif_carrier_ok(d->netdev) &&
         READ_ONCE(d->netdev->mtu) >= 4096+60;
    a->state = up ? IB_PORT_ACTIVE : IB_PORT_DOWN;
    a->phys_state = up ? IB_PORT_PHYS_STATE_LINK_UP : IB_PORT_PHYS_STATE_DISABLED;
    a->max_mtu = IB_MTU_4096; a->active_mtu = up ? IB_MTU_4096 : IB_MTU_256;
    a->phys_mtu = READ_ONCE(d->netdev->mtu);
    a->gid_tbl_len = AS02_GID_ENTRIES; a->pkey_tbl_len = 1; a->max_msg_sz = 4096;
    return ib_get_eth_speed(ibdev, port, &a->active_speed, &a->active_width);
}
static int immutable(struct ib_device *ibdev, u32 port, struct ib_port_immutable *a)
{
    if (port != 1 || !a || !ready(dev(ibdev))) return -EINVAL;
    memset(a, 0, sizeof(*a));
    a->gid_tbl_len = AS02_GID_ENTRIES; a->pkey_tbl_len = 1;
    /* RoCEv2/ETH AH only, not nonexistent MAD/CM/InfiniBand facilities. */
    a->core_cap_flags = RDMA_CORE_CAP_PROT_ROCE_UDP_ENCAP | RDMA_CORE_CAP_ETH_AH;
    return 0;
}
static enum rdma_link_layer link_layer(struct ib_device *ibdev, u32 port)
{ (void)ibdev; return port == 1 ? IB_LINK_LAYER_ETHERNET : IB_LINK_LAYER_UNSPECIFIED; }
static int pkey(struct ib_device *ibdev, u32 port, u16 index, u16 *value)
{
    if (port != 1 || index || !value) return -EINVAL;
    if (!ready(dev(ibdev))) return -ESHUTDOWN;
    *value = 0xffff; return 0;
}
static bool local_gid(struct as02_verbs_device *d, const struct ib_gid_attr *a)
{
    static const u8 prefix[12] = {0,0,0,0,0,0,0,0,0,0,255,255};
    u32 ip;
    if (!a || a->port_num != 1 || a->index >= AS02_GID_ENTRIES ||
        a->gid_type != IB_GID_TYPE_ROCE_UDP_ENCAP || a->ndev != d->netdev ||
        memcmp(a->gid.raw, prefix, sizeof(prefix))) return false;
    ip = ((u32)a->gid.raw[12]<<24) | ((u32)a->gid.raw[13]<<16) |
         ((u32)a->gid.raw[14]<<8) | a->gid.raw[15];
    return ip == d->local_ip;
}
static int add_gid(const struct ib_gid_attr *a, void **context)
{
    struct as02_verbs_device *d;
    int ret;
    if (!a || !a->device || !context) return -EINVAL;
    d = dev(a->device);
    if (!ready(d) || !local_gid(d,a)) return -EOPNOTSUPP;
    ret = route(d); if (ret) return ret;
    *context = d; return 0;
}
static int del_gid(const struct ib_gid_attr *a, void **context)
{
    /* Core owns GID cache entries. The immutable route is owned by the bus
     * parent, not individually by those entries; no HW mapping was allocated.
     */
    if (!a || !a->device || !context || *context != dev(a->device) ||
        !local_gid(dev(a->device),a)) return -EINVAL;
    return 0;
}
static int alloc_context(struct ib_ucontext *ibctx, struct ib_udata *u)
{
    struct as02_verbs_device *d = dev(ibctx->device);
    struct as02_ucontext *c = container_of(ibctx, struct as02_ucontext, ibucontext);
    int ret = 0;
    if (u && (u->inlen || u->outlen)) return -EOPNOTSUPP;
    mutex_lock(&d->lock);
    if (!ready(d) || !d->accepting_contexts || c->live) ret = -ESHUTDOWN;
    else if (d->context_count == U32_MAX) ret = -ENOSPC;
    else { d->context_count++; c->live = true;c->closing=false;c->cleanup_error=0; }
    mutex_unlock(&d->lock); return ret;
}
static void dealloc_context(struct ib_ucontext *ibctx)
{
    struct as02_verbs_device *d = dev(ibctx->device);
    struct as02_ucontext *c = container_of(ibctx, struct as02_ucontext, ibucontext);
    mutex_lock(&d->lock);
    /* Failed hardware cleanup can leave driver-owned QP/pins quarantined
     * after the core frees this ucontext. Never retain a pointer to it.
     */
    if(d->qp && d->qp->ucontext==ibctx)d->qp->ucontext=NULL;
    if (c->live) { c->live = false; d->context_count--; }
    mutex_unlock(&d->lock);
}
static void file_cleanup(struct ib_uverbs_file *file)
{
    struct ib_ucontext *ibctx=ib_uverbs_get_ucontext_file(file);
    struct as02_verbs_device *d;
    struct as02_ucontext *c;
    struct as02_verbs_qp *q;
    struct as02_cq *tx=NULL,*rx=NULL;
    unsigned long flags;
    unsigned int i;
    int ret=0;
    if(IS_ERR(ibctx) || !ibctx)return;
    d=dev(ibctx->device);c=container_of(ibctx,struct as02_ucontext,ibucontext);
    /* Core holds this file's hw_destroy_rwsem against concurrent commands.
     * Other files remain live; only its associated QP is stopped/abandoned.
     * Do not call core destructors or free core-owned objects here.
     */
    mutex_lock(&d->lock);c->closing=true;q=d->qp;
    if(!c->live || !q || !q->initialized || q->ucontext!=ibctx)goto out;
    spin_lock_irqsave(&q->lock,flags);q->closing=true;spin_unlock_irqrestore(&q->lock,flags);
    ret=as02_cq_router_abandon(d->router,&q->ibqp);
    if(ret)goto out;
    tx=container_of(q->ibqp.send_cq,struct as02_cq,ibcq);
    rx=container_of(q->ibqp.recv_cq,struct as02_cq,ibcq);
    /* One hardware connection, <=256 SEND plus <=8 RECV entries. Pump only
     * currently visible genuine events, never a wall-clock wait or invented
     * flush completion. Missing/invalid events retain work and DMA memory.
     * The core subsequently calls ordinary destroy_qp/dereg_mr/etc, which
     * still require the actual STOP and both native retirement replies.
     */
    for(i=0;i<265;i++){
        ret=as02_cq_hw_poll(d->cq_hw);
        if(ret<=0)break;
    }
    if(ret>0)ret=-EAGAIN;
    if(!ret){
        ret=as02_sq_cancel_receive(d->sq,&q->owner);
        if(ret==-EOPNOTSUPP)ret=0; /* Old profile keeps original drain-only behavior. */
    }
out:
    c->cleanup_error=ret;mutex_unlock(&d->lock);
    /* The core still owns these same-file CQs until this callback returns.
     * Suppression above prevents a new event handler; synchronize an already
     * running IRQ notification WITHOUT holding the verbs/CQ/router locks.
     */
    if(tx)irq_work_sync(&tx->notify);
    if(rx && rx!=tx)irq_work_sync(&rx->notify);
}
static int enable_driver(struct ib_device *ibdev)
{
    struct as02_verbs_device *d = dev(ibdev);
    if (!ready(d) || !d->publishing) return -EINVAL;
    mutex_lock(&d->lock); d->accepting_contexts = true; mutex_unlock(&d->lock);
    return 0;
}
const struct ib_device_ops as02_device_ops = {
    .owner = THIS_MODULE, .driver_id = RDMA_DRIVER_UNKNOWN,
    .uverbs_abi_ver = AS02_UVERBS_ABI,
    /* A new upstream driver ID is not allocated. Do not impersonate RXE or
     * mlx5. A private provider must match this experimental device identity.
     */
    .uverbs_no_driver_id_binding = 1,
    .query_device = query_device, .query_port = query_port,
    .get_port_immutable = immutable, .get_link_layer = link_layer,
    .query_pkey = pkey, .add_gid = add_gid, .del_gid = del_gid,
    .alloc_ucontext = alloc_context, .dealloc_ucontext = dealloc_context,
    .ufile_hw_cleanup = file_cleanup,
    .enable_driver = enable_driver,
    INIT_RDMA_OBJ_SIZE(ib_ucontext, as02_ucontext, ibucontext),
};
struct as02_verbs_device *as02_device_alloc(void)
{
    struct as02_verbs_device *d = ib_alloc_device(as02_verbs_device, ibdev);
    if (!d) return NULL;
    mutex_init(&d->device_lock); d->core_allocated = true;
    return d;
}
static bool empty(struct as02_verbs_device *d)
{
    unsigned int i;
    if (d->context_count || d->pd_count || d->mr_count || d->cq_count || d->qp || d->orphan_sq.cookie)
        return false;
    for (i=0;i<AS02_MR_SLOTS;i++) if (d->orphan_mrs[i]) return false;
    return true;
}
int as02_device_publish(struct as02_verbs_device *d, struct device *parent,
                        struct net_device *ndev, void __iomem *eth, size_t bytes)
{
    struct as02_sq_hw *sqhw;
    u32 lo,hi,i;
    u64 guid = 0;
    int ret;
    if (!d || !d->core_allocated || !parent || !ndev || !eth || bytes < AS02_NATIVE_ETH_BYTES)
        return -EINVAL;
    mutex_lock(&d->device_lock);
    if (!d->initialized || d->stopping || d->registration_attempted ||
        !d->mrs || !d->sq || !d->cq_hw || !d->qp_hw || !d->router) { ret=-EINVAL; goto out; }
    mutex_lock(&d->lock);
    sqhw=d->sq->hw_context;
    if (!empty(d) || !d->mrs->initialized || !d->mrs->ready || d->mrs->stopping ||
        d->mrs->mapping_count || d->sq->queue_count || d->sq->stopping ||
        !d->sq->initialized || !d->sq->dma_device || !d->router->initialized ||
        !d->cq_hw->control.initialized || d->cq_hw->control.detached ||
        d->cq_hw->control.uncertain || d->cq_hw->control.pending_ack ||
        d->cq_hw->pool != d->sq || !d->qp_hw->initialized || !d->qp_hw->retry.initialized ||
        d->qp_hw->retry.pending || d->qp_hw->retry.uncertain || d->qp_hw->owned ||
        d->qp_hw->uncertain ||
        (d->qp_hw->control->control.features!=AS02_CTL_FULL_NATIVE_FEATURES &&
         d->qp_hw->control->control.features!=AS02_CTL_IMMEDIATE_NATIVE_FEATURES) ||
        !d->sq->profile_bound || d->sq->wqe_profile!=
            ((d->qp_hw->control->control.features&AS02_CTL_FEATURE_IMMEDIATE) ? AS02_WQE_PROFILE_IMMEDIATE:0) ||
        d->cq_hw->control.features!=
            ((d->qp_hw->control->control.features&AS02_CTL_FEATURE_IMMEDIATE) ?
             AS02_CQC_IMMEDIATE_FEATURE_VALUE:AS02_CQC_MESSAGE_FEATURE_VALUE) ||
        !d->qp_hw->control->control.initialized || d->qp_hw->control->control.detached ||
        d->qp_hw->control->control.pending || d->qp_hw->control->control.uncertain ||
        d->sq->hw != &as02_sqc_sq_hw_ops || !sqhw || !sqhw->receive ||
        !sqhw->control.initialized || sqhw->control.detached || sqhw->control.pending || sqhw->control.uncertain ||
        !sqhw->receive->control.initialized || sqhw->receive->control.detached ||
        sqhw->receive->control.pending || sqhw->receive->control.uncertain ||
        !as02_sq_independent_receive_supported(d->sq) ||
        ndev->reg_state != NETREG_REGISTERED || ndev->dev.parent != parent ||
        d->sq->dma_device != parent || !is_valid_ether_addr(ndev->dev_addr)) {
        ret=-EBUSY; goto unlock;
    }
    if (readl(eth+AS02_ETH_ID)!=AS02_ETH_ID_VALUE || readl(eth+AS02_ETH_ABI)!=AS02_ETH_ABI_VALUE) {
        ret=-ENODEV; goto unlock;
    }
    d->ethernet_registers=eth; d->netdev=ndev;
    d->route_epoch=readl(eth+AS02_ETH_EPOCH);
    lo=readl(eth+AS02_ETH_ACTIVE);hi=readl(eth+AS02_ETH_ACTIVE+4);
    for(i=0;i<4;i++)d->local_mac[5-i]=lo>>(i*8);
    d->local_mac[1]=hi;d->local_mac[0]=hi>>8;
    ret=route(d); if(ret) {d->ethernet_registers=NULL;d->netdev=NULL;goto unlock;}
    dev_hold(ndev);d->device_parent=get_device(parent);
    d->ibdev.dev.parent=parent;
    for(i=0;i<6;i++)guid=(guid<<8)|d->local_mac[i];
    guid=((guid&0xffffff000000ULL)<<16)|0xfffe000000ULL|(guid&0xffffffULL);
    d->ibdev.node_guid=cpu_to_be64(guid);
    d->ibdev.node_type=RDMA_NODE_IB_CA; d->ibdev.phys_port_cnt=1;
    d->ibdev.num_comp_vectors=1;d->ibdev.local_dma_lkey=0;
    strscpy(d->ibdev.node_desc,"Alibaba XCKU3P native RoCEv2",sizeof(d->ibdev.node_desc));
    d->ibdev.uverbs_cmd_mask |= BIT_ULL(IB_USER_VERBS_CMD_POST_SEND) |
        BIT_ULL(IB_USER_VERBS_CMD_POST_RECV) | BIT_ULL(IB_USER_VERBS_CMD_POLL_CQ) |
        BIT_ULL(IB_USER_VERBS_CMD_REQ_NOTIFY_CQ);
    d->metadata_ready=true;d->publishing=true;d->registration_attempted=true;
    mutex_unlock(&d->lock);
    ib_set_device_ops(&d->ibdev,&as02_device_ops);
    ret=ib_device_set_netdev(&d->ibdev,ndev,1);
    if(!ret)ret=ib_register_device(&d->ibdev,"as02_%d",parent);
    mutex_lock(&d->lock);
    d->publishing=false;d->published=!ret;
    if(ret){d->accepting_contexts=false;d->stopping=true;}
unlock:
    mutex_unlock(&d->lock);
out:
    mutex_unlock(&d->device_lock);return ret;
}
int as02_device_unpublish(struct as02_verbs_device *d)
{
    bool registered;
    int ret=0;
    if(!d || !d->core_allocated || !d->initialized)return -EINVAL;
    mutex_lock(&d->device_lock);mutex_lock(&d->lock);
    if(!empty(d)){ret=-EBUSY;goto unlock;}
    registered=d->published;d->accepting_contexts=false;d->stopping=true;
    mutex_unlock(&d->lock);
    if(registered)ib_unregister_device(&d->ibdev);
    mutex_lock(&d->lock);d->published=false;d->metadata_ready=false;
unlock:
    mutex_unlock(&d->lock);mutex_unlock(&d->device_lock);return ret;
}
int as02_device_free(struct as02_verbs_device *d)
{
    struct device *parent;
    struct net_device *ndev;
    if(!d || !d->core_allocated)return -EINVAL;
    mutex_lock(&d->device_lock);
    if(d->initialized || d->published || d->publishing || d->context_count ||
       (d->mrs && d->mrs->initialized) || (d->sq && d->sq->initialized) ||
       (d->cq_hw && d->cq_hw->control.initialized && !d->cq_hw->control.detached)) {
        mutex_unlock(&d->device_lock);return -EBUSY;
    }
    parent=d->device_parent;ndev=parent ? d->netdev:NULL;
    mutex_unlock(&d->device_lock);
    ib_dealloc_device(&d->ibdev);
    if(ndev)dev_put(ndev);
    if(parent)put_device(parent);
    return 0;
}
EXPORT_SYMBOL_GPL(as02_device_alloc);
EXPORT_SYMBOL_GPL(as02_device_publish);
EXPORT_SYMBOL_GPL(as02_device_unpublish);
EXPORT_SYMBOL_GPL(as02_device_free);
EXPORT_SYMBOL_GPL(as02_device_ops);
