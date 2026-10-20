/* SPDX-License-Identifier: GPL-2.0 OR BSD-2-Clause-Views */
/* Copyright (c) 2026 jyohukuchan */
#ifndef AS02_USER_MR_H
#define AS02_USER_MR_H
#include <linux/list.h>
#include <linux/mutex.h>
#include <linux/refcount.h>
#include <linux/spinlock.h>
#include <rdma/ib_umem.h>
#include "mr_contract.h"

/* Control path only: sleepable, serialized; never post_send/poll_cq callbacks.
 * Hardware callbacks MUST return source-bound actual command/tag/drain proof.
 * There is deliberately no default successful/no-op hardware backend.
 */
struct as02_mr_hw_ops {
    int (*reset_epoch)(void *, u64 cookie, u32 floor, struct as02_mr_epoch_proof *);
    int (*publish)(void *, const struct as02_mr_layout *, struct as02_mr_publish_proof *);
    int (*invalidate_and_drain)(void *, const struct as02_mr_layout *, struct as02_mr_revoke_proof *);
};
struct as02_user_mr;
struct as02_mr_pool {
    /* Control mutex -> fast_lock only. Fast paths NEVER acquire the mutex,
     * call hardware callbacks, allocate, sleep, or release umem/device refs.
     */
    struct mutex lock;
    spinlock_t fast_lock;
    struct list_head mappings;
    struct ib_device *ibdev;
    const struct as02_mr_hw_ops *hw;
    void *hw_context;
    struct as02_mr_epoch epoch;
    struct as02_user_mr *slots[AS02_MR_SLOTS];
    u64 next_cookie;
    unsigned int mapping_count;
    unsigned int client_count;
    bool initialized, ready, stopping, fast_ready, pd_zero_reserved;
};
struct as02_user_mr {
    struct list_head node;
    struct as02_mr_pool *pool;
    struct ib_umem *umem;
    struct as02_mr_layout layout;
    /* Base1 belongs to the pool. Work refs cannot drop/free that base. */
    refcount_t work_refs;
    bool quarantined, fast_live, closing;
};

/* The future real RDMA driver supplies its actual initialized ib_device.
 * No ib_register_device/bus binding exists in this compile-link support target.
 * Caller owns an execution/module reference while calling any entry point.
 */
int as02_mr_pool_init(struct as02_mr_pool *, struct ib_device *,
                     const struct as02_mr_hw_ops *, void *, u32 persisted_floor);
int as02_mr_pool_start_epoch(struct as02_mr_pool *, u32 new_floor);
struct as02_user_mr *as02_user_mr_prepare(struct as02_mr_pool *, u64 start,
                                        u64 iova, u64 length, u16 pd,
                                        u32 access, u32 supported_access);
int as02_user_mr_publish(struct as02_user_mr *);
/* On error the mapping remains pool-owned and pinned. Never kfree it or fake
 * drain via reset. On success this call frees the object; don't reuse pointer.
 */
int as02_user_mr_close(struct as02_user_mr *);
/* EBUSY retains pool/device ownership; caller MUST NOT free the device/pool.
 * Stop/drain actual hardware and close retained mappings, then retry.
 */
int as02_mr_pool_destroy(struct as02_mr_pool *);
/* Queue/client pins the pool storage/device lifetime before entering atomic
 * fast paths. Successful destroy requires ALL clients and mappings gone.
 * Pool owner MUST retain its actual object until destroy succeeds.
 */
int as02_mr_pool_get_client(struct as02_mr_pool *);
int as02_mr_pool_put_client(struct as02_mr_pool *);
/* Non-sleeping LOCAL buffer authorization + owned work reference. PD/key/
 * complete64-bit range/access checked against a published, nonclosing MR.
 * op0local read,1local write ONLY. No CPU payload/DMA-address substitute.
 * Caller retains exactly one returned reference through actual completion/
 * recovery; queue fetch/consumer movement is NOT permission to put it.
 */
struct as02_user_mr *as02_user_mr_get_work(struct as02_mr_pool *, u16 pd,
                                        u32 key, u64 address, u32 length,
                                        u32 operation);
int as02_user_mr_put_work(struct as02_user_mr *);
#endif
