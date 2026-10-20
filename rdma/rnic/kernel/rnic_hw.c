/* SPDX-License-Identifier: GPL-2.0 OR BSD-2-Clause-Views */
#include <linux/delay.h>
#include <linux/errno.h>
#include <linux/ktime.h>
#include <linux/lockdep.h>
#include <linux/string.h>
#include "rnic_hw.h"

static int as02_hw_read(void *context, u32 offset, u32 *value)
{
    struct as02_rnic_hw *h = context;
    lockdep_assert_held(&h->lock);
    if (!h->registers || h->control.detached)
        return -ENODEV;
    *value = readl(h->registers+offset);
    return 0;
}
static int as02_hw_write(void *context, u32 offset, u32 value)
{
    struct as02_rnic_hw *h = context;
    lockdep_assert_held(&h->lock);
    if (!h->registers || h->control.detached)
        return -ENODEV;
    writel(value, h->registers+offset);
    return 0;
}
static u64 as02_hw_now(void *context)
{
    (void)context;
    return ktime_to_us(ktime_get());
}
static void as02_hw_wait(void *context)
{
    (void)context;
    usleep_range(20, 40);
}
static const struct as02_ctl_transport transport = {
    .read32 = as02_hw_read, .write32 = as02_hw_write,
    .time_us = as02_hw_now, .wait = as02_hw_wait,
};
int as02_rnic_hw_init(struct as02_rnic_hw *h, void __iomem *base, size_t size, u32 timeout)
{
    int ret;
    if (!h || !base || size < AS02_CTL_FATAL_CODE+4)
        return -EINVAL;
    if (h->control.initialized)
        return -EBUSY;
    h->registers = base;
    mutex_init(&h->lock);
    mutex_lock(&h->lock);
    ret = as02_ctl_init(&h->control, &transport, h, timeout);
    mutex_unlock(&h->lock);
    return ret;
}
int as02_rnic_hw_detach(struct as02_rnic_hw *h)
{
    int ret;
    if (!h || !h->control.initialized)
        return -EINVAL;
    mutex_lock(&h->lock);
    ret = as02_ctl_detach(&h->control);
    if (!ret)
        h->registers = NULL;
    mutex_unlock(&h->lock);
    return ret;
}
int as02_rnic_hw_reconcile(struct as02_rnic_hw *h, struct as02_ctl_reply *reply)
{
    int ret;
    if (!h || !h->control.initialized)
        return -EINVAL;
    mutex_lock(&h->lock);
    ret = as02_ctl_reconcile(&h->control, reply);
    mutex_unlock(&h->lock);
    return ret;
}
static void owner_words(u32 *w, u64 cookie, u32 slot)
{
    memset(w, 0, AS02_CTL_STAGE_WORDS*sizeof(*w));
    w[AS02_W_COOKIE_LO] = (u32)cookie;w[AS02_W_COOKIE_HI] = cookie>>32;w[AS02_W_SLOT] = slot;
}
static int execute(struct as02_rnic_hw *h, u32 *w, struct as02_ctl_reply *r)
{
    int ret = as02_ctl_execute(&h->control, w, r);
    return ret ? ret : (r->error ? -EIO : 0);
}
static int seed_epoch(void *context, u64 cookie, u32 floor, struct as02_mr_epoch_proof *proof)
{
    struct as02_rnic_hw *h = context;
    struct as02_ctl_reply r = {};
    u32 w[AS02_CTL_STAGE_WORDS];
    int ret;
    if (!h || !h->control.initialized || !proof)
        return -EINVAL;
    memset(proof, 0, sizeof(*proof));
    owner_words(w, cookie, 0);w[AS02_W_OP] = AS02_CMD_EPOCH;w[AS02_W_KEY] = floor;
    mutex_lock(&h->lock);
    ret = execute(h, w, &r);
    if (!ret) {
        proof->cookie = r.cookie;proof->floor = r.key;
        proof->qps_closed = !!(r.flags & AS02_PROOF_QPS_CLOSED);
        proof->mr_table_invalid = !!(r.flags & AS02_PROOF_TABLE_INVALID);
        proof->dma_drained = !!(r.flags & AS02_PROOF_DMA_DRAINED);
    }
    mutex_unlock(&h->lock);
    return ret;
}
static int publish(void *context, const struct as02_mr_layout *m, struct as02_mr_publish_proof *proof)
{
    struct as02_rnic_hw *h = context;
    struct as02_ctl_reply r = {};
    u32 w[AS02_CTL_STAGE_WORDS], key, i;
    int ret;
    if (!h || !h->control.initialized || !proof || !m)
        return -EINVAL;
    memset(proof, 0, sizeof(*proof));
    if (m->state != AS02_MR_PUBLISHING || !m->cookie || m->slot >= AS02_MR_SLOTS ||
        !m->page_count || m->page_count > AS02_MR_MAX_PAGES || m->pages_written != m->page_count ||
        !m->length || m->length > 1048576 || m->pd > 65535 || m->access > AS02_MR_ACCESS_MASK)
        return -EINVAL;
    for (i = 0; i < m->page_count; i++)
        if (!(m->present[i/64] & (1ULL << (i%64))) || (m->pages[i] & 4095))
            return -EINVAL;
    owner_words(w, m->cookie, m->slot);w[AS02_W_OP] = AS02_CMD_BEGIN;
    w[AS02_W_PD] = m->pd;w[AS02_W_ACCESS] = m->access;w[AS02_W_VA_LO] = (u32)m->iova;
    w[AS02_W_VA_HI] = m->iova>>32;w[AS02_W_LENGTH] = m->length;w[AS02_W_FIRST] = m->first_offset;
    mutex_lock(&h->lock);
    ret = execute(h, w, &r);
    if (ret)
        goto out;
    key = r.key;
    if ((key & 7) != m->slot || (key>>3) <= m->required_generation) {
        ret = -EPROTO;
        goto out;
    }
    w[AS02_W_KEY] = key;
    for (i = 0; i < m->page_count; i++) {
        w[AS02_W_OP] = AS02_CMD_PAGE;w[AS02_W_PAGE_INDEX] = i;
        w[AS02_W_DMA_LO] = (u32)m->pages[i];w[AS02_W_DMA_HI] = m->pages[i]>>32;
        ret = execute(h, w, &r);
        if (ret)
            goto out;
    }
    w[AS02_W_OP] = AS02_CMD_SEAL;
    ret = execute(h, w, &r);
    if (!ret) {
        proof->cookie = r.cookie;proof->slot = r.slot;proof->key = r.key;
    }
out:
    /* NO error/timeout path frees pages or resets the device. The pool keeps
     * its PUBLISHING object, even if the actual SEAL reply was lost. */
    mutex_unlock(&h->lock);
    return ret;
}
static int invalidate_and_drain(void *context, const struct as02_mr_layout *m, struct as02_mr_revoke_proof *proof)
{
    struct as02_rnic_hw *h = context;
    struct as02_ctl_reply r = {};
    u32 w[AS02_CTL_STAGE_WORDS];
    int ret;
    if (!h || !h->control.initialized || !proof || !m ||
        (m->state != AS02_MR_REVOKING && m->state != AS02_MR_PUBLISHING && m->state != AS02_MR_LIVE))
        return -EINVAL;
    memset(proof, 0, sizeof(*proof));
    owner_words(w, m->cookie, m->slot);w[AS02_W_OP] = AS02_CMD_INVALIDATE;w[AS02_W_KEY] = m->key;
    mutex_lock(&h->lock);
    ret = execute(h, w, &r);
    if (!ret) {
        proof->cookie = r.cookie;proof->slot = r.slot;proof->generation = r.key>>3;
        proof->invalidated = !!(r.flags & AS02_PROOF_INVALIDATED);
        proof->dma_drained = !!(r.flags & AS02_PROOF_DMA_DRAINED);
    }
    mutex_unlock(&h->lock);
    return ret;
}
const struct as02_mr_hw_ops as02_rnic_mr_hw_ops = {
    .reset_epoch = seed_epoch, .publish = publish, .invalidate_and_drain = invalidate_and_drain,
};
