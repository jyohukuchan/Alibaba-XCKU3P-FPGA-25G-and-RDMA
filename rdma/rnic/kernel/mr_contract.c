/* SPDX-License-Identifier: GPL-2.0 OR BSD-2-Clause-Views */
/* Copyright (c) 2026 jyohukuchan */
#include "mr_contract.h"
#ifdef __KERNEL__
#include <linux/errno.h>
#include <linux/string.h>
#else
#include <errno.h>
#include <string.h>
#endif

int as02_mr_epoch_init(struct as02_mr_epoch *e, as02_u32 floor)
{
    unsigned int i;
    if (!e || floor >= AS02_MR_MAX_GENERATION)
        return -EINVAL;
    memset(e, 0, sizeof(*e));
    e->floor = floor;
    e->highest = floor;
    for (i = 0; i < AS02_MR_SLOTS; i++)
        e->last[i] = floor;
    return 0;
}

int as02_mr_epoch_confirm(struct as02_mr_epoch *e, as02_u64 cookie,
                         as02_u32 floor, const struct as02_mr_epoch_proof *p)
{
    unsigned int i;
    if (!e || !p || !cookie || p->cookie != cookie || p->floor != floor)
        return -ESTALE;
    if (!p->qps_closed || !p->mr_table_invalid || !p->dma_drained)
        return -EBUSY;
    if (floor >= AS02_MR_MAX_GENERATION)
        return -ENOSPC;
    if (floor < e->highest || (e->configured && floor <= e->floor))
        return -ESTALE;
    e->floor = floor;
    e->highest = floor;
    e->configured = 1;
    for (i = 0; i < AS02_MR_SLOTS; i++)
        e->last[i] = floor;
    return 0;
}

int as02_mr_layout_init(struct as02_mr_layout *m, as02_u64 user,
                        as02_u64 iova, as02_u64 length, as02_u32 pd,
                        as02_u32 access, as02_u32 slot, as02_u64 cookie)
{
    as02_u32 offset = user & (AS02_MR_PAGE_SIZE-1);
    /* A zero-initialized NEW object is required. Reinitializing a live or
     * uncertain mapping must not manufacture permission to unpin its pages.
     */
    if (m && m->state)
        return -EBUSY;
    if (!m || !cookie || slot >= AS02_MR_SLOTS || pd > 65535 || !length ||
        access & ~AS02_MR_ACCESS_MASK || ((access & 10) && !(access & 1)))
        return -EINVAL;
    if (length-1 > ~(as02_u64)0-iova || length-1 > ~(as02_u64)0-user ||
        length > (as02_u64)AS02_MR_MAX_PAGES*AS02_MR_PAGE_SIZE-offset)
        return -EOVERFLOW;
    memset(m, 0, sizeof(*m));
    m->user_address = user;
    m->iova = iova;
    m->length = length;
    m->cookie = cookie;
    m->pd = pd;
    m->access = access;
    m->slot = slot;
    m->first_offset = offset;
    m->page_count = ((length-1+offset) >> AS02_MR_PAGE_SHIFT)+1;
    m->state = AS02_MR_BUILDING;
    return 0;
}

int as02_mr_set_page(struct as02_mr_layout *m, as02_u32 index, as02_u64 dma)
{
    as02_u64 bit;
    if (!m || m->state != AS02_MR_BUILDING)
        return -EBUSY;
    if (index >= m->page_count || dma & (AS02_MR_PAGE_SIZE-1))
        return -EINVAL;
    bit = (as02_u64)1 << (index % 64);
    if (m->present[index/64] & bit)
        return -EEXIST;
    m->pages[index] = dma;
    m->present[index/64] |= bit;
    m->pages_written++;
    return 0;
}

int as02_mr_seal(struct as02_mr_layout *m)
{
    if (!m || m->state != AS02_MR_BUILDING || m->pages_written != m->page_count)
        return -EINVAL;
    m->state = AS02_MR_READY;
    return 0;
}

int as02_mr_begin_publish(struct as02_mr_layout *m, const struct as02_mr_epoch *e)
{
    if (!m || !e || !e->configured || m->state != AS02_MR_READY || m->slot >= AS02_MR_SLOTS)
        return -EINVAL;
    if (e->last[m->slot] == AS02_MR_MAX_GENERATION)
        return -ENOSPC;
    m->required_generation = e->last[m->slot];
    /* BEFORE the first hardware callback: even a failed/timed-out publish
     * may already be visible to DMA and must not release pinned pages.
     */
    m->state = AS02_MR_PUBLISHING;
    return 0;
}

int as02_mr_confirm_publish(struct as02_mr_layout *m, struct as02_mr_epoch *e,
                            const struct as02_mr_publish_proof *p)
{
    as02_u32 generation;
    if (!m || !e || !p || m->state != AS02_MR_PUBLISHING || m->slot >= AS02_MR_SLOTS ||
        p->cookie != m->cookie || p->slot != m->slot ||
        (p->key & (AS02_MR_SLOTS-1)) != m->slot)
        return -ESTALE;
    generation = p->key >> AS02_MR_SLOT_BITS;
    if (!e->configured || generation <= m->required_generation ||
        generation <= e->last[m->slot] || generation <= e->floor)
        return -ESTALE;
    e->last[m->slot] = generation;
    if (generation > e->highest)
        e->highest = generation;
    m->key = p->key;
    m->state = AS02_MR_LIVE;
    return 0;
}

int as02_mr_begin_revoke(struct as02_mr_layout *m)
{
    if (!m || (m->state != AS02_MR_PUBLISHING && m->state != AS02_MR_LIVE &&
               m->state != AS02_MR_REVOKING))
        return -EINVAL;
    m->state = AS02_MR_REVOKING;
    return 0;
}

int as02_mr_confirm_revoke(struct as02_mr_layout *m, struct as02_mr_epoch *e,
                           const struct as02_mr_revoke_proof *p)
{
    if (!m || !e || !p || m->state != AS02_MR_REVOKING || m->slot >= AS02_MR_SLOTS ||
        p->cookie != m->cookie || p->slot != m->slot)
        return -ESTALE;
    if (!p->invalidated || !p->dma_drained)
        return -EBUSY;
    if (p->generation < m->required_generation ||
        p->generation < e->last[m->slot] || p->generation > AS02_MR_MAX_GENERATION ||
        (m->key && p->generation != m->key >> AS02_MR_SLOT_BITS))
        return -ESTALE;
    e->last[m->slot] = p->generation;
    if (p->generation > e->highest)
        e->highest = p->generation;
    m->state = AS02_MR_DRAINED;
    m->key = 0;
    return 0;
}

int as02_mr_can_unpin(const struct as02_mr_layout *m)
{
    return m && (m->state == AS02_MR_BUILDING || m->state == AS02_MR_READY ||
                 m->state == AS02_MR_DRAINED);
}

int as02_mr_resolve(const struct as02_mr_layout *m, as02_u32 pd, as02_u32 key,
                    as02_u64 address, as02_u32 length, as02_u32 operation,
                    struct as02_mr_segment *out)
{
    as02_u64 offset, linear;
    as02_u32 page, page_offset, chunk;
    if (!out)
        return -EINVAL;
    memset(out, 0, sizeof(*out));
    if (!m || m->state != AS02_MR_LIVE || key != m->key || pd != m->pd)
        return -EACCES;
    if (operation > 4)
        return -EOPNOTSUPP;
    if ((operation == 1 && !(m->access & 1)) ||
        (operation == 2 && !(m->access & 4)) ||
        (operation == 3 && !(m->access & 2)) ||
        (operation == 4 && !(m->access & 8)))
        return -EACCES;
    if (!length || address < m->iova)
        return -EFAULT;
    offset = address-m->iova;
    if (offset > m->length || length > m->length-offset)
        return -EFAULT;
    linear = m->first_offset+offset;
    page = linear >> AS02_MR_PAGE_SHIFT;
    page_offset = linear & (AS02_MR_PAGE_SIZE-1);
    if (page >= m->page_count || page >= AS02_MR_MAX_PAGES || !(m->present[page/64] & ((as02_u64)1 << (page%64))))
        return -EFAULT;
    if (operation == 4 && (length != 8 || address & 7 || (m->pages[page]+page_offset) & 7))
        return -EINVAL;
    chunk = AS02_MR_PAGE_SIZE-page_offset;
    if (chunk > length)
        chunk = length;
    out->dma_address = m->pages[page]+page_offset;
    out->memory_offset = offset;
    out->page_index = page;
    out->length = chunk;
    return 0;
}
