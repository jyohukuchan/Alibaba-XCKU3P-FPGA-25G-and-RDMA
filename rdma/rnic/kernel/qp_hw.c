/* SPDX-License-Identifier: GPL-2.0 OR BSD-2-Clause-Views */
#include <linux/errno.h>
#include <linux/module.h>
#include <linux/string.h>
#include <linux/io.h>
#include <linux/ktime.h>
#include <linux/lockdep.h>
#include <asm/processor.h>
#include "qp_hw.h"

static int retry_read(void *context, as02_u32 offset, as02_u32 *value)
{
    struct as02_qp_hw *q=context;
    lockdep_assert_held(&q->control->lock);
    if(!q->retry_registers || q->control->control.detached)return -ENODEV;
    if(offset&3 || offset>=AS02_RRP_BYTES)return -EINVAL;
    *value=readl(q->retry_registers+offset);return 0;
}
static int retry_write(void *context, as02_u32 offset, as02_u32 value)
{
    struct as02_qp_hw *q=context;
    lockdep_assert_held(&q->control->lock);
    if(!q->retry_registers || q->control->control.detached)return -ENODEV;
    if(offset!=0x10 && offset!=0x14 && (offset<0x40 || offset>0x5c || offset&3))return -EINVAL;
    writel(value,q->retry_registers+offset);return 0;
}
static as02_u64 retry_time(void *context) {(void)context;return ktime_to_us(ktime_get());}
static void retry_relax(void *context) {(void)context;cpu_relax();}
static const struct as02_sqc_transport retry_mmio={
    .read32=retry_read,.write32=retry_write,.time_us=retry_time,.relax=retry_relax};
int as02_qp_hw_enable_retry(struct as02_qp_hw *q, void __iomem *base, size_t bytes, u32 timeout_us)
{
    int ret;
    if(!q || !q->initialized || !base || bytes<AS02_RRP_BYTES)return -EINVAL;
    mutex_lock(&q->control->lock);
    if(q->owned || q->uncertain || q->retry.initialized) {ret=-EBUSY;goto out;}
    if(!(q->control->control.features&AS02_CTL_FEATURE_QP_TX)) {ret=-EOPNOTSUPP;goto out;}
    q->retry_registers=base;
    ret=as02_retry_io_init(&q->retry,&retry_mmio,q,timeout_us);
    if(ret)q->retry_registers=NULL;
out:
    mutex_unlock(&q->control->lock);return ret;
}
int as02_qp_hw_set_retry(struct as02_qp_hw *q, const struct as02_sq_handle *owner,
                        u8 timeout, u8 retry, u8 rnr_retry)
{
    struct as02_retry_policy policy;
    int ret;
    if(!q || !q->initialized || !owner || timeout>31 || retry>7 || rnr_retry>7)return -EINVAL;
    mutex_lock(&q->control->lock);
    if(!q->retry.initialized) {ret=-EOPNOTSUPP;goto out;}
    if(!q->owned || q->uncertain || q->owner.qpn!=owner->qpn || q->owner.pd!=owner->pd) {
        ret=-ESTALE;goto out;
    }
    policy=(struct as02_retry_policy){.cookie=owner->cookie,.epoch=owner->epoch,
        .qpn=owner->qpn,.pd=owner->pd,.timeout=timeout,.retry=retry,.rnr_retry=rnr_retry};
    ret=as02_retry_io_configure(&q->retry,&policy);
    if(q->retry.uncertain)q->uncertain=true;
out:
    mutex_unlock(&q->control->lock);return ret;
}

static int command(struct as02_qp_hw *q, u32 op,
                   const struct as02_qp_route *route)
{
    struct as02_ctl_reply reply = {};
    u32 w[AS02_CTL_STAGE_WORDS] = {};
    int ret;
    if (q->next_cookie == U64_MAX)
        return -ENOSPC;
    ++q->next_cookie;
    w[AS02_W_OP] = op;
    w[AS02_W_COOKIE_LO] = q->next_cookie;
    w[AS02_W_COOKIE_HI] = q->next_cookie >> 32;
    if (route) {
        w[AS02_W_QP] = route->qpn; w[AS02_W_PD] = route->pd;
        w[AS02_W_PEER_QP] = route->peer_qpn;
        w[AS02_W_LOCAL_IP] = route->local_ip; w[AS02_W_PEER_IP] = route->peer_ip;
        w[AS02_W_RX_PSN] = route->rx_psn; w[AS02_W_TX_PSN] = route->tx_psn;
        if (op == AS02_CMD_QP_TX) {
            w[AS02_W_PEER_QP] = 0; w[AS02_W_LOCAL_IP] = 0;
            w[AS02_W_PEER_IP] = 0; w[AS02_W_RX_PSN] = 0;
        }
    }
    ret = as02_ctl_execute(&q->control->control, w, &reply);
    return ret ? ret : (reply.error ? -EIO : 0);
}
int as02_qp_hw_init(struct as02_qp_hw *q, struct as02_rnic_hw *h)
{
    if (!q || q->initialized || !h || !h->registers ||
        !h->control.initialized || h->control.detached ||
        h->control.pending || h->control.uncertain)
        return -EINVAL;
    q->control = h; q->next_cookie = 0;
    q->owned = false; q->uncertain = false; q->initialized = true;
    return 0;
}
int as02_qp_hw_open(struct as02_qp_hw *q, const struct as02_qp_route *route)
{
    int ret;
    if (!q || !q->initialized || !route || route->qpn >= AS02_SQ_QPS ||
        !route->pd || route->pd > 65535 || route->peer_qpn > 0xffffff ||
        !route->local_ip || !route->peer_ip ||
        route->rx_psn > 0xffffff || route->tx_psn > 0xffffff)
        return -EINVAL;
    mutex_lock(&q->control->lock);
    if (q->owned || q->uncertain) { ret = -EBUSY; goto out; }
    /* Publish authority ownership before the first potentially posted bell. */
    q->owner = *route; q->owned = true;
    ret = command(q, AS02_CMD_STOP, NULL);
    if (!ret) ret = command(q, AS02_CMD_QP, route);
    if (!ret) ret = command(q, AS02_CMD_RUN, NULL);
    if (ret) q->uncertain = true;
out:
    mutex_unlock(&q->control->lock);
    return ret;
}
int as02_qp_hw_set_tx(struct as02_qp_hw *q, u32 qpn, u16 pd, u32 tx_psn)
{
    struct as02_qp_route route = {};
    int ret;
    if (!q || !q->initialized || !pd || qpn >= AS02_SQ_QPS || tx_psn > 0xffffff)
        return -EINVAL;
    mutex_lock(&q->control->lock);
    if (!(q->control->control.features & AS02_CTL_FEATURE_QP_TX)) { ret = -EOPNOTSUPP; goto out; }
    if (!q->owned || q->uncertain || q->owner.qpn != qpn || q->owner.pd != pd) {
        ret = -ESTALE; goto out;
    }
    route.qpn = qpn; route.pd = pd; route.tx_psn = tx_psn;
    ret = command(q, AS02_CMD_QP_TX, &route);
    if (!ret) q->owner.tx_psn = tx_psn;
    else q->uncertain = true;
out:
    mutex_unlock(&q->control->lock); return ret;
}
int as02_qp_hw_close(struct as02_qp_hw *q, u32 qpn, u16 pd)
{
    struct as02_qp_route tombstone = {};
    int ret;
    if (!q || !q->initialized || !pd) return -EINVAL;
    mutex_lock(&q->control->lock);
    if (!q->owned || q->owner.qpn != qpn || q->owner.pd != pd) {
        ret = -ESTALE; goto out;
    }
    if (q->retry.pending || q->retry.uncertain) {
        /* An unacknowledged policy still owns the SAME SQC1 context.
         * Missing transport certainty never authorizes a QP/SQ teardown. */
        ret = -EBUSY; goto out;
    }
    /* Actual matched STOP reply requires endpoint + parent drain. Then
     * replace SAME protected/HLS connection authority with inaccessible PD0.
     * This is not a claim that HLS's context-valid bit has been cleared.
     * It stays paused; no live MR/SQ is ever authorized in the tombstone PD.
     */
    ret = command(q, AS02_CMD_STOP, NULL);
    tombstone.qpn = qpn;
    if (!ret) ret = command(q, AS02_CMD_QP, &tombstone);
    if (!ret) {
        memset(&q->owner, 0, sizeof(q->owner));
        q->owned = false; q->uncertain = false;
    } else q->uncertain = true;
out:
    mutex_unlock(&q->control->lock);
    return ret;
}
EXPORT_SYMBOL_GPL(as02_qp_hw_init);
EXPORT_SYMBOL_GPL(as02_qp_hw_open);
EXPORT_SYMBOL_GPL(as02_qp_hw_set_tx);
EXPORT_SYMBOL_GPL(as02_qp_hw_enable_retry);
EXPORT_SYMBOL_GPL(as02_qp_hw_set_retry);
EXPORT_SYMBOL_GPL(as02_qp_hw_close);
