/* SPDX-License-Identifier: GPL-2.0 OR BSD-2-Clause-Views */
/* Copyright (c) 2026 jyohukuchan */
#ifndef AS02_MR_CONTRACT_H
#define AS02_MR_CONTRACT_H
#ifdef __KERNEL__
#include <linux/types.h>
typedef u64 as02_u64;
typedef u32 as02_u32;
#else
#include <stdint.h>
typedef uint64_t as02_u64;
typedef uint32_t as02_u32;
#endif

#define AS02_MR_PAGE_SHIFT 12
#define AS02_MR_PAGE_SIZE 4096U
#define AS02_MR_MAX_PAGES 256U
#define AS02_MR_SLOTS 8U
#define AS02_MR_SLOT_BITS 3
#define AS02_MR_MAX_GENERATION 0x1fffffffU
#define AS02_MR_ACCESS_MASK 15U

enum as02_mr_state {
    AS02_MR_BUILDING=1, AS02_MR_READY, AS02_MR_PUBLISHING,
    AS02_MR_LIVE, AS02_MR_REVOKING, AS02_MR_DRAINED
};
struct as02_mr_epoch {
    as02_u32 floor, highest, last[AS02_MR_SLOTS], configured;
};
struct as02_mr_epoch_proof {
    as02_u64 cookie;
    as02_u32 floor, qps_closed, mr_table_invalid, dma_drained;
};
struct as02_mr_layout {
    as02_u64 user_address, iova, length, cookie;
    as02_u64 pages[AS02_MR_MAX_PAGES];
    as02_u64 present[AS02_MR_MAX_PAGES/64];
    as02_u32 pd, access, slot, page_count, first_offset, pages_written;
    as02_u32 state, key, required_generation;
};
struct as02_mr_publish_proof {
    as02_u64 cookie;
    as02_u32 slot, key;
};
struct as02_mr_revoke_proof {
    as02_u64 cookie;
    as02_u32 slot, generation, invalidated, dma_drained;
};
struct as02_mr_segment {
    as02_u64 dma_address, memory_offset;
    as02_u32 page_index, length;
};

/* Caller serializes these metadata operations. No data is copied by this API.
 * Epoch proof is trusted hardware evidence, not a timer/no-error inference.
 * Across driver/OS lifetimes the caller must retain a generation watermark.
 */
int as02_mr_epoch_init(struct as02_mr_epoch *, as02_u32 persisted_floor);
int as02_mr_epoch_confirm(struct as02_mr_epoch *, as02_u64 expected_cookie,
                         as02_u32 new_floor, const struct as02_mr_epoch_proof *);
int as02_mr_layout_init(struct as02_mr_layout *, as02_u64 user_address,
                        as02_u64 iova, as02_u64 length, as02_u32 pd,
                        as02_u32 access, as02_u32 slot, as02_u64 cookie);
int as02_mr_set_page(struct as02_mr_layout *, as02_u32 index, as02_u64 dma_page);
int as02_mr_seal(struct as02_mr_layout *);
int as02_mr_begin_publish(struct as02_mr_layout *, const struct as02_mr_epoch *);
int as02_mr_confirm_publish(struct as02_mr_layout *, struct as02_mr_epoch *,
                            const struct as02_mr_publish_proof *);
int as02_mr_begin_revoke(struct as02_mr_layout *);
int as02_mr_confirm_revoke(struct as02_mr_layout *, struct as02_mr_epoch *,
                           const struct as02_mr_revoke_proof *);
int as02_mr_can_unpin(const struct as02_mr_layout *);
/* Full request is range-checked BEFORE returning its first page segment.
 * op0 local read,1 local write,2 remote read,3 remote write,4atomic SHAPE only.
 * FPGA SG translator/work queues must implement this contract; CPU resolution
 * in these tests is NOT a software replacement for hardware DMA.
 */
int as02_mr_resolve(const struct as02_mr_layout *, as02_u32 pd, as02_u32 key,
                    as02_u64 address, as02_u32 length, as02_u32 operation,
                    struct as02_mr_segment *);
#endif
