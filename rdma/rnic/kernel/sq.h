/* SPDX-License-Identifier: GPL-2.0 OR BSD-2-Clause-Views */
/* Copyright (c) 2026 jyohukuchan */
#ifndef AS02_KERNEL_SQ_H
#define AS02_KERNEL_SQ_H
#include <linux/device.h>
#include <linux/dma-mapping.h>
#include <rdma/ib_verbs.h>
#include "mr.h"
#include "wqe.h"

#define AS02_SQ_QPS 8U
#define AS02_SQ_ALLOC_ACTIVE 1U
#define AS02_SQ_ALLOC_EMPTY 2U
#define AS02_SQ_ALLOC_PARENT_DRAINED 4U
#define AS02_SQ_CQE_MEMORY_DONE 1U
#define AS02_SQ_CQE_TRANSPORT_DONE 2U
#define AS02_SQ_RETIRED 1U
#define AS02_SQ_FETCH_DRAINED 2U
#define AS02_SQ_WORK_DRAINED 4U
#define AS02_SQ_WIRE_DRAINED 8U
#define AS02_SQ_COMPLETION_DRAINED 16U

struct as02_sq_handle {
    u64 cookie, epoch;
    u32 qpn, pd;
};
struct as02_sq_layout {
    struct as02_sq_handle owner;
    u64 dma_base;
    u32 depth, log_depth;
};
struct as02_sq_alloc_proof {
    struct as02_sq_layout layout;
    u32 flags;
};
struct as02_sq_retire_proof {
    struct as02_sq_handle owner;
    u64 request_cookie, last_producer;
    u32 flags;
};
struct as02_sq_completion_proof {
    struct as02_sq_handle owner;
    u64 sequence;
    u32 flags, status;
};
/* Metadata only; no CPU payload copies. Actual registered CQ/provider is NOT
 * implemented by this library. No untrusted WR identifier becomes a pointer.
 */
struct as02_sq_completion {
    u64 wr_id, sequence, epoch;
    u32 qpn, opcode, status, length;
    u32 notification, notification_flags;
};
struct as02_sq_hw_ops {
    /* Control callbacks may sleep. Must obtain exact actual CSR/tag/drain
     * evidence, never return a default successful/no-op/model backend.
     */
    int (*allocate)(void *, const struct as02_sq_layout *, struct as02_sq_alloc_proof *);
    int (*retire_and_drain)(void *, const struct as02_sq_layout *, u64 producer,
                           u64 request_cookie, struct as02_sq_retire_proof *);
    /* Atomic callbacks, called under the queue pool's IRQ spinlock. Lock order
     * is queue-fast -> MR-fast/CQ; a CQ event handler must NOT hold its CQ
     * lock when entering as02_sq_complete. Publish
     * must perform real queue MMIO after the library's coherent-DMA barrier.
     * ANY publish error is ambiguous: WR/MR/ring remain quarantined, no rollback.
     */
    int (*publish_producer)(void *, const struct as02_sq_layout *, u64 producer);
    /* Commit the actual kernel/user CQ metadata. No sleep; on failure no CQE
     * may have become visible, so the owned completion can be retried. The
     * real CQ handler must not consume its HW event before this succeeds.
     */
    int (*publish_cqe)(void *, const struct as02_sq_completion *);
    /* Optional genuine independent RQC1 controller, never a logical quota
     * over the SQ ring. Capability is not a completion/drain certificate. */
    bool (*receive_supported)(void *);
    int (*allocate_receive)(void *, const struct as02_sq_layout *, struct as02_sq_alloc_proof *);
    int (*publish_receive)(void *, const struct as02_sq_layout *, u64);
    int (*retire_receive)(void *, const struct as02_sq_layout *, u64, u64,
                          struct as02_sq_retire_proof *);
    bool (*receive_cancel_supported)(void *);
    int (*cancel_receive)(void *,const struct as02_sq_layout *,u64,u64,struct as02_sq_retire_proof *);
};
struct as02_sq;
struct as02_sq_pool {
    struct mutex lock;
    spinlock_t fast_lock;
    struct as02_mr_pool *mrs;
    struct device *dma_device;
    const struct as02_sq_hw_ops *hw;
    void *hw_context;
    struct as02_sq *slots[AS02_SQ_QPS];
    u64 epoch_watermark[AS02_SQ_QPS], next_cookie;
    unsigned int queue_count, completion_clients;
    /* Kernel-only, negotiated from the matching real RNC/SQC/RQC/CQC tuple
     * before any queue exists. Never an application flag/codec override. */
    u32 wqe_profile;
    bool profile_bound;
    bool initialized, stopping;
};

/* Caller owns stable device/module/pool execution lifetime and supplies its
 * actual parent DMA device, not ib_device's private dma_device member.
 * Persisted per-queue epoch watermarks are REQUIRED (all0only for first use).
 * Neither this API nor local reset proves reboot/hot-unplug lifetime safety.
 */
int as02_sq_pool_init(struct as02_sq_pool *, struct as02_mr_pool *, struct device *,
                      const struct as02_sq_hw_ops *, void *, const u64 persisted_epochs[AS02_SQ_QPS]);
/* EBUSY keeps pool/client/module/device lifetime. NEVER free owning storage. */
int as02_sq_pool_destroy(struct as02_sq_pool *);
/* Control paths. After ambiguous HW allocation failure handle identifies the
 * pool-owned quarantined queue; it is NOT freed by the error return.
 */
int as02_sq_create(struct as02_sq_pool *, u32 qpn, u16 pd, u64 epoch,
                   u32 log_depth, struct as02_sq_handle *);
int as02_sq_close(struct as02_sq_pool *, const struct as02_sq_handle *);
/* User-file abandonment ONLY, after its router has stopped WC/notification
 * delivery. Real optional RQC1 command4 must revoke never-taken receive owners
 * and unfetched tail, then return exact owner/producer/nonce and flags63.
 * No synthetic success CQE. Pending/timed-out cancellation retains memory and
 * still permits genuine native completions; retry reconciles the same batch.
 * Coherent storage remains until ordinary paired close/real SQ retirement.
 */
int as02_sq_cancel_receive(struct as02_sq_pool *,const struct as02_sq_handle *);
/* Same real cancellation certificate, but publish ordered RECV WCs with
 * IB_WC_WR_FLUSH_ERR. ENOSPC retains unreported refs and the proved batch;
 * retry resumes WC delivery without reissuing an already retired RQC owner.
 */
int as02_sq_flush_receive(struct as02_sq_pool *,const struct as02_sq_handle *);
/* Obtain/cache that same exact cancellation certificate but retain every
 * work/MR ref and publish nothing. ERR control then revokes peer authority
 * with actual QP STOP/tombstone before flush_receive may emit user error WCs.
 */
int as02_sq_prepare_receive_cancel(struct as02_sq_pool *,const struct as02_sq_handle *);
/* Attach a SECOND coherent ring/shadow/producer/completion sequence to the
 * same QPN/PD/epoch, with its own nonwrapping queue cookie, before either
 * direction has been posted. The public handle still closes BOTH. Ambiguous
 * hardware failure retains both rings and their sole cleanup handle. */
bool as02_sq_independent_receive_supported(struct as02_sq_pool *);
int as02_sq_create_receive(struct as02_sq_pool *, const struct as02_sq_handle *,
                            u32 log_depth, u32 receive_limit);
/* Atomic paths. One actual ib_send_wr per call; future registered post_send
 * iterates linked WRs and preserves earlier submissions at its first error.
 * Shape subset follows wqe.c; no capabilities or standard verbs registration
 * are implied. Fetch-consumer movement NEVER releases these owned work refs.
 */
int as02_sq_post(struct as02_sq_pool *, const struct as02_sq_handle *, const struct ib_send_wr *);
/* Shared coherent descriptor submission, separate logical receive quota.
 * Full receive work remains pinned/owned through actual RQ/native placement.
 * Native receive CQ/internal retirement is not implemented by posting. */
int as02_sq_set_receive_limits(struct as02_sq_pool *, const struct as02_sq_handle *, u32 send_limit, u32 receive_limit);
int as02_sq_post_recv(struct as02_sq_pool *, const struct as02_sq_handle *, const struct ib_recv_wr *);
int as02_sq_complete(struct as02_sq_pool *, const struct as02_sq_completion_proof *);
struct as02_cq_decoded;
/* Actual hardware event path: compare the complete original WQE and SAME-MR
 * offset before publishing a WC or releasing a work ref. Legacy proof-only
 * entry above remains for trusted older clients, not the CQC1 event handler.
 */
int as02_sq_complete_event(struct as02_sq_pool *, const struct as02_cq_decoded *);
int as02_sq_pool_get_completion_client(struct as02_sq_pool *);
int as02_sq_pool_put_completion_client(struct as02_sq_pool *);
#endif
