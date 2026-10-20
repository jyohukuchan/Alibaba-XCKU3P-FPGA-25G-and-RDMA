/* SPDX-License-Identifier: GPL-2.0 OR BSD-2-Clause-Views */
#ifndef AS02_KERNEL_CQ_H
#define AS02_KERNEL_CQ_H
#include <linux/irq_work.h>
#include <rdma/ib_verbs.h>
#include "cq_hw.h"

/* Genuine kernel CQ storage/callbacks, not an empty ib_device registration.
 * The future complete device allocates this as its ib_cq object and retains
 * actual device/module execution lifetime. No user-payload CPU copy occurs.
 */
#define AS02_CQ_MAX_ENTRIES 4096U
struct as02_cq {
    struct ib_cq ibcq;
    spinlock_t lock;
    struct ib_wc *entries;
    struct as02_cq_hw *hardware;
    struct ib_ucontext *ucontext;
    struct irq_work notify;
    u32 capacity,producer,consumer,pending,queue_refs;
    bool initialized,closing,armed,user_closed;
};
struct as02_cq_router {
    spinlock_t lock;
    struct as02_cq *cq[AS02_SQ_QPS];
    struct as02_cq *recv_cq[AS02_SQ_QPS];
    struct ib_qp *qp[AS02_SQ_QPS];
    bool abandoning[AS02_SQ_QPS];
    bool initialized;
};
int as02_cq_create(struct ib_cq *,const struct ib_cq_init_attr *,struct ib_udata *);
int as02_cq_destroy(struct ib_cq *,struct ib_udata *);
int as02_cq_poll(struct ib_cq *,int,struct ib_wc *);
int as02_cq_req_notify(struct ib_cq *,enum ib_cq_notify_flags);
int as02_cq_attach_hardware(struct as02_cq *,struct as02_cq_hw *);
int as02_cq_router_init(struct as02_cq_router *);
/* Bind both send_cq and recv_cq before posting. A shared CQ owns one queue
 * reference; distinct CQs each own one. Unbind only after real retirement and all
 * queued CQEs have been polled; otherwise QP/CQ pointers remain owned.
 */
int as02_cq_router_bind(struct as02_cq_router *,struct as02_cq *,struct ib_qp *);
int as02_cq_router_unbind(struct as02_cq_router *,struct ib_qp *);
/* Uverbs file-close preparation only. Discard already delivered software
 * WCs for this QP and future WC metadata, NOT its native events, outstanding
 * work/MR references, CQ acknowledgments or retirement obligations. Native
 * event validation still precedes publish; no DMA cancellation is inferred.
 * Router/queue/CQ objects remain owned until normal real teardown succeeds.
 */
int as02_cq_router_abandon(struct as02_cq_router *,struct ib_qp *);
/* Actual SQ hw commit_cqe callback. Full ring returns ENOSPC without any WC
 * visible; hardware event/MR ref stays owned for retry. Never call a consumer
 * or user event handler under SQ/MMIO/CQ locks (irq_work defers notification).
 */
int as02_cq_publish(void *,const struct as02_sq_completion *);
#endif
