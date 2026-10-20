/* SPDX-License-Identifier: GPL-2.0 OR BSD-2-Clause-Views */
/* Copyright (c) 2026 jyohukuchan */
#include <linux/err.h>
#include <linux/mm.h>
#include <linux/limits.h>
#include <linux/module.h>
#include <linux/overflow.h>
#include <linux/sched/mm.h>
#include <linux/slab.h>
#include "mr.h"

/* Caller holds control mutex; the separately protected fast view is published
 * only after actual hardware publication/epoch confirmation. Never hold the
 * spinlock over hardware callbacks or pin/map/unpin/allocation operations.
 */
static void set_ready(struct as02_mr_pool *p, bool ready)
{
    unsigned long flags;
    spin_lock_irqsave(&p->fast_lock, flags);
    p->ready = ready;
    p->fast_ready = ready;
    spin_unlock_irqrestore(&p->fast_lock, flags);
}

static int next_cookie(struct as02_mr_pool *p, u64 *cookie)
{
    if (p->next_cookie == U64_MAX)
        return -ENOSPC;
    *cookie = ++p->next_cookie;
    return 0;
}

int as02_mr_pool_init(struct as02_mr_pool *p, struct ib_device *ibdev,
                     const struct as02_mr_hw_ops *hw, void *ctx, u32 floor)
{
    int ret;
    /* Caller supplies a zero-initialized, never-before-initialized pool. */
    if (p && p->initialized)
        return -EBUSY;
    if (!p || !ibdev || !hw || !hw->reset_epoch || !hw->publish || !hw->invalidate_and_drain)
        return -EINVAL;
    memset(p, 0, sizeof(*p));
    ret = as02_mr_epoch_init(&p->epoch, floor);
    if (ret)
        return ret;
    mutex_init(&p->lock);
    spin_lock_init(&p->fast_lock);
    INIT_LIST_HEAD(&p->mappings);
    p->ibdev = ibdev;
    get_device(&ibdev->dev);
    p->hw = hw;
    p->hw_context = ctx;
    WRITE_ONCE(p->initialized, true);
    return 0;
}

int as02_mr_pool_start_epoch(struct as02_mr_pool *p, u32 floor)
{
    struct as02_mr_epoch_proof proof = {};
    unsigned long flags;
    u64 cookie;
    int ret;
    if (!p || !READ_ONCE(p->initialized))
        return -EINVAL;
    mutex_lock(&p->lock);
    if (!p->initialized || p->stopping || p->mapping_count) {
        ret = -EBUSY;
        goto out;
    }
    /* Even a failed reset/seed command may have reached hardware. Stop new
     * preparation until a matching closed-QP/invalid-table/drained proof.
     */
    spin_lock_irqsave(&p->fast_lock, flags);
    if (p->client_count) {
        spin_unlock_irqrestore(&p->fast_lock, flags);
        ret = -EBUSY;
        goto out;
    }
    p->ready = false;
    p->fast_ready = false;
    spin_unlock_irqrestore(&p->fast_lock, flags);
    if (floor >= AS02_MR_MAX_GENERATION || floor < p->epoch.highest ||
        (p->epoch.configured && floor <= p->epoch.floor)) {
        ret = -ESTALE;
        goto out;
    }
    ret = next_cookie(p, &cookie);
    if (ret)
        goto out;
    ret = p->hw->reset_epoch(p->hw_context, cookie, floor, &proof);
    if (!ret)
        ret = as02_mr_epoch_confirm(&p->epoch, cookie, floor, &proof);
    if (!ret)
        set_ready(p, true);
out:
    mutex_unlock(&p->lock);
    return ret;
}

struct as02_user_mr *as02_user_mr_prepare(struct as02_mr_pool *p, u64 start,
                                        u64 iova, u64 length, u16 pd,
                                        u32 access, u32 supported_access)
{
    struct as02_user_mr *m;
    struct ib_block_iter iter;
    unsigned int slot, index = 0;
    unsigned long flags;
    u64 cookie, end;
    int ret;
    if (!p || !READ_ONCE(p->initialized))
        return ERR_PTR(-EINVAL);
    if (!current->mm || start > ULONG_MAX || length > SIZE_MAX ||
        check_add_overflow(start, length, &end) || end > ULONG_MAX ||
        (access & ~supported_access) || (access & ~AS02_MR_ACCESS_MASK))
        return ERR_PTR(-EOPNOTSUPP);
    mutex_lock(&p->lock);
    if (!p->initialized || !p->ready || p->stopping || (!pd && p->pd_zero_reserved)) {
        ret = -ESHUTDOWN;
        goto unlock;
    }
    for (slot = 0; slot < AS02_MR_SLOTS; slot++)
        if (!p->slots[slot])
            break;
    if (slot == AS02_MR_SLOTS) {
        ret = -ENOSPC;
        goto unlock;
    }
    ret = next_cookie(p, &cookie);
    if (ret)
        goto unlock;
    m = kzalloc(sizeof(*m), GFP_KERNEL);
    if (!m) {
        ret = -ENOMEM;
        goto unlock;
    }
    ret = as02_mr_layout_init(&m->layout, start, iova, length, pd, access, slot, cookie);
    if (ret)
        goto free_mapping;
    if (!try_module_get(THIS_MODULE)) {
        ret = -ENODEV;
        goto free_mapping;
    }
    get_device(&p->ibdev->dev);
    /* RDMA core owns FOLL_LONGTERM, memlock/mm accounting, DMA SG mapping and
     * dirty unpin. Do NOT use virt_to_phys or assume pages are contiguous.
     * Unsupported relaxed-ordering/ODP/DMABUF/MW flags were rejected above.
     */
    m->umem = ib_umem_get(p->ibdev, (unsigned long)start, (size_t)length, access);
    if (IS_ERR(m->umem)) {
        ret = PTR_ERR(m->umem);
        goto put_references;
    }
    /* Keep umem->iova at its original user address. The iterator AND release
     * page accounting use it. Remote IOVA and user first-byte offset are
     * separate layout fields, including when their page offsets differ.
     */
    if (PAGE_SIZE < AS02_MR_PAGE_SIZE ||
        ib_umem_num_dma_blocks(m->umem, AS02_MR_PAGE_SIZE) != m->layout.page_count) {
        ret = -EINVAL;
        goto release_umem;
    }
    rdma_umem_for_each_dma_block(m->umem, &iter, AS02_MR_PAGE_SIZE) {
        ret = as02_mr_set_page(&m->layout, index++, rdma_block_iter_dma_address(&iter));
        if (ret)
            goto release_umem;
    }
    ret = as02_mr_seal(&m->layout);
    if (ret)
        goto release_umem;
    m->pool = p;
    refcount_set(&m->work_refs, 1);
    spin_lock_irqsave(&p->fast_lock, flags);
    p->slots[slot] = m;
    spin_unlock_irqrestore(&p->fast_lock, flags);
    list_add_tail(&m->node, &p->mappings);
    p->mapping_count++;
    mutex_unlock(&p->lock);
    return m;
release_umem:
    /* No hardware callback has occurred on this preparation-only path. */
    ib_umem_release(m->umem);
put_references:
    put_device(&p->ibdev->dev);
    module_put(THIS_MODULE);
free_mapping:
    kfree(m);
unlock:
    mutex_unlock(&p->lock);
    return ERR_PTR(ret);
}

int as02_user_mr_publish(struct as02_user_mr *m)
{
    struct as02_mr_pool *p;
    struct as02_mr_publish_proof proof = {};
    unsigned long flags;
    int ret;
    if (!m || !m->pool)
        return -EINVAL;
    p = m->pool;
    mutex_lock(&p->lock);
    if (!p->ready || p->stopping || m->closing) {
        ret = -ESHUTDOWN;
        goto out;
    }
    ret = as02_mr_begin_publish(&m->layout, &p->epoch);
    if (ret)
        goto out;
    ret = p->hw->publish(p->hw_context, &m->layout, &proof);
    if (!ret)
        ret = as02_mr_confirm_publish(&m->layout, &p->epoch, &proof);
    if (ret) {
        /* Never drop the pool's object/pin references on ambiguous failure. */
        m->quarantined = true;
        set_ready(p, false);
    } else {
        spin_lock_irqsave(&p->fast_lock, flags);
        m->fast_live = true;
        spin_unlock_irqrestore(&p->fast_lock, flags);
    }
out:
    mutex_unlock(&p->lock);
    return ret;
}

int as02_user_mr_close(struct as02_user_mr *m)
{
    struct as02_mr_pool *p;
    struct as02_mr_revoke_proof proof = {};
    struct ib_device *ibdev;
    unsigned long flags;
    int ret = 0;
    if (!m || !m->pool)
        return -EINVAL;
    p = m->pool;
    mutex_lock(&p->lock);
    spin_lock_irqsave(&p->fast_lock, flags);
    m->closing = true;
    m->fast_live = false;
    if (refcount_read(&m->work_refs) != 1) {
        /* Stop new getters, but do NOT revoke/unpin live queued/in-flight
         * memory. Caller retries after real completions/recovery put refs.
         */
        spin_unlock_irqrestore(&p->fast_lock, flags);
        mutex_unlock(&p->lock);
        return -EBUSY;
    }
    spin_unlock_irqrestore(&p->fast_lock, flags);
    if (!as02_mr_can_unpin(&m->layout)) {
        ret = as02_mr_begin_revoke(&m->layout);
        if (!ret)
            ret = p->hw->invalidate_and_drain(p->hw_context, &m->layout, &proof);
        if (!ret)
            ret = as02_mr_confirm_revoke(&m->layout, &p->epoch, &proof);
        if (ret) {
            m->quarantined = true;
            set_ready(p, false);
            mutex_unlock(&p->lock);
            return ret;
        }
    }
    /* No timeout/error/reset path reaches release without the contract's
     * never-published OR explicit invalidation+DMA-drain ownership proof.
     */
    if (!as02_mr_can_unpin(&m->layout)) {
        mutex_unlock(&p->lock);
        return -EBUSY;
    }
    ibdev = p->ibdev;
    spin_lock_irqsave(&p->fast_lock, flags);
    p->slots[m->layout.slot] = NULL;
    refcount_dec(&m->work_refs);
    spin_unlock_irqrestore(&p->fast_lock, flags);
    ib_umem_release(m->umem);
    list_del(&m->node);
    p->mapping_count--;
    kfree(m);
    mutex_unlock(&p->lock);
    put_device(&ibdev->dev);
    module_put(THIS_MODULE);
    return 0;
}

int as02_mr_pool_destroy(struct as02_mr_pool *p)
{
    struct ib_device *ibdev;
    unsigned long flags;
    if (!p || !READ_ONCE(p->initialized))
        return -EINVAL;
    mutex_lock(&p->lock);
    spin_lock_irqsave(&p->fast_lock, flags);
    p->stopping = true;
    p->ready = false;
    p->fast_ready = false;
    if (p->mapping_count || p->client_count) {
        spin_unlock_irqrestore(&p->fast_lock, flags);
        mutex_unlock(&p->lock);
        return -EBUSY;
    }
    spin_unlock_irqrestore(&p->fast_lock, flags);
    if (!p->initialized) {
        mutex_unlock(&p->lock);
        return -EINVAL;
    }
    WRITE_ONCE(p->initialized, false);
    ibdev = p->ibdev;
    mutex_unlock(&p->lock);
    put_device(&ibdev->dev);
    return 0;
}

int as02_mr_pool_get_client(struct as02_mr_pool *p)
{
    unsigned long flags;
    int ret = 0;
    if (!p || !READ_ONCE(p->initialized))
        return -EINVAL;
    spin_lock_irqsave(&p->fast_lock, flags);
    if (!p->fast_ready || p->stopping)
        ret = -ESHUTDOWN;
    else if (p->client_count == UINT_MAX)
        ret = -EOVERFLOW;
    else
        p->client_count++;
    spin_unlock_irqrestore(&p->fast_lock, flags);
    return ret;
}

int as02_mr_pool_put_client(struct as02_mr_pool *p)
{
    unsigned long flags;
    int ret = 0;
    if (!p || !READ_ONCE(p->initialized))
        return -EINVAL;
    spin_lock_irqsave(&p->fast_lock, flags);
    if (!p->client_count)
        ret = -EINVAL;
    else
        p->client_count--;
    spin_unlock_irqrestore(&p->fast_lock, flags);
    return ret;
}

struct as02_user_mr *as02_user_mr_get_work(struct as02_mr_pool *p, u16 pd,
                                        u32 key, u64 address, u32 length,
                                        u32 operation)
{
    struct as02_mr_segment checked;
    struct as02_user_mr *m;
    unsigned long flags;
    int ret;
    if (!p || !READ_ONCE(p->initialized))
        return ERR_PTR(-EINVAL);
    if (operation > 1)
        return ERR_PTR(-EOPNOTSUPP);
    spin_lock_irqsave(&p->fast_lock, flags);
    if (!p->fast_ready || p->stopping || !p->client_count) {
        ret = -ESHUTDOWN;
        goto out;
    }
    m = p->slots[key & (AS02_MR_SLOTS-1)];
    if (!m || !m->fast_live || m->closing) {
        ret = -EACCES;
        goto out;
    }
    ret = as02_mr_resolve(&m->layout, pd, key, address, length, operation, &checked);
    if (ret)
        goto out;
    if (refcount_read(&m->work_refs) >= INT_MAX/2 ||
        !refcount_inc_not_zero(&m->work_refs)) {
        ret = -EOVERFLOW;
        goto out;
    }
    spin_unlock_irqrestore(&p->fast_lock, flags);
    return m;
out:
    spin_unlock_irqrestore(&p->fast_lock, flags);
    return ERR_PTR(ret);
}

int as02_user_mr_put_work(struct as02_user_mr *m)
{
    struct as02_mr_pool *p;
    unsigned long flags;
    int ret = 0;
    /* Caller MUST own the work reference; arbitrary/stale pointers are not
     * handles. Future CQ code resolves a trusted slot/epoch/sequence first.
     */
    if (!m || !m->pool)
        return -EINVAL;
    p = m->pool;
    spin_lock_irqsave(&p->fast_lock, flags);
    if (refcount_read(&m->work_refs) <= 1)
        ret = -EINVAL;
    else
        refcount_dec(&m->work_refs);
    spin_unlock_irqrestore(&p->fast_lock, flags);
    return ret;
}

EXPORT_SYMBOL_GPL(as02_mr_pool_get_client);
EXPORT_SYMBOL_GPL(as02_mr_pool_put_client);
EXPORT_SYMBOL_GPL(as02_user_mr_get_work);
EXPORT_SYMBOL_GPL(as02_user_mr_put_work);

MODULE_DESCRIPTION("AS02 native MR/queue/verbs and standard-device support; no automatic probe");
MODULE_LICENSE("Dual BSD/GPL");
