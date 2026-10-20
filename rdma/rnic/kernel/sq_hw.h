/* SPDX-License-Identifier: GPL-2.0 OR BSD-2-Clause-Views */
#ifndef AS02_SQ_HW_H
#define AS02_SQ_HW_H
#include <linux/io.h>
#include <linux/spinlock.h>
#include "sq.h"
#include "sq_io.h"

/* Actual kernel MMIO adapter, NOT a registered bus/ib_device/provider.
 * Caller holds stable BAR/device/module/context lifetime across all callbacks.
 * Lock order: queue-fast -> SQC-fast -> CQ. Never enter as02_sq_complete with
 * the CQ lock held, or reenter these APIs from commit_cqe. No sleeping CQ op.
 */
struct as02_sq_hw {
    spinlock_t lock;
    void __iomem *registers;
    struct as02_sqc_io control;
    int (*commit_cqe)(void *, const struct as02_sq_completion *);
    void *cq_context;
    struct as02_sq_hw *receive, *send_parent;
};
/* REQUIRED actual CQ publisher, no built-in no-op success. Probe actual new
 * SQC1/ABI/clean sequence0 ONLY after native firmware/private ABI/reset/epoch
 * gates. Pointer must be the correctly bounded kernel-owned SQ BAR region,
 * never an arbitrary untrusted DMA/user pointer or the old deployed image.
 */
int as02_sq_hw_init(struct as02_sq_hw *, void __iomem *, size_t,
                    u32 timeout_us, int (*commit_cqe)(void *, const struct as02_sq_completion *), void *);
/* Logical detach only; no DMA cancellation/CQ/unpin or context-free proof. */
int as02_sq_hw_detach(struct as02_sq_hw *);
/* Initialize actual RQC1 MMIO separately and bind its stable caller-owned
 * context to an existing SQ adapter. Detach RQ only AFTER paired queue close;
 * binding does not authorize cancellation, unpin or context destruction. */
int as02_sq_hw_init_receive(struct as02_sq_hw *, struct as02_sq_hw *send,
                            void __iomem *, size_t, u32 timeout_us);
/* Explicit late transport resync only; no automatic SQ/MR unquarantine. */
int as02_sq_hw_reconcile(struct as02_sq_hw *, struct as02_sqc_reply *);
extern const struct as02_sq_hw_ops as02_sqc_sq_hw_ops;
struct as02_rnic_hw;
struct as02_cq_hw;
/* Bind the real matching transport/descriptor/CQ profile before any queue.
 * Re-read actual immutable controller capabilities using their own locks.
 * A CQC format bit alone is never authority for posting Immediate WQEs.
 * No userspace switch and no MMIO write/queue/CQ/drain/ref release here. */
int as02_sq_bind_transport_profile(struct as02_sq_pool *,struct as02_rnic_hw *,struct as02_cq_hw *);
#endif
