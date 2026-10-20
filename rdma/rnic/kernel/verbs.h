/* SPDX-License-Identifier: GPL-2.0 OR BSD-2-Clause-Views */
#ifndef AS02_VERBS_H
#define AS02_VERBS_H
#include "cq.h"
#include "qp_hw.h"
#define AS02_VERBS_QPN 2U
#define AS02_VERBS_MAX_CQS 65535U

struct as02_pd {
    struct ib_pd ibpd;
    u32 number, owners;
    bool live;
};
struct as02_verbs_mr {
    struct ib_mr ibmr;
    struct as02_user_mr *mapping;
    struct as02_pd *pd;
};
struct as02_verbs_qp {
    struct ib_qp ibqp;
    spinlock_t lock;
    struct as02_sq_handle owner;
    struct as02_pd *pd;
    struct ib_ucontext *ucontext;
    struct ib_qp_attr attributes;
    struct ib_qp_init_attr initial;
    struct ib_qp_cap cap;
    struct delayed_work error_work;
    int error_progress_status;
    bool error_requested, error_pending;
    bool initialized, closing, sq_closed, routed, hw_owned, signal_all;
};
struct as02_verbs_device {
    struct ib_device ibdev;
    struct mutex lock;
    struct as02_mr_pool *mrs;
    struct as02_sq_pool *sq;
    struct as02_cq_hw *cq_hw;
    struct as02_qp_hw *qp_hw;
    struct as02_cq_router *router;
    struct as02_verbs_qp *qp;
    struct as02_verbs_mr *orphan_mrs[AS02_MR_SLOTS];
    struct as02_sq_handle orphan_sq;
    struct as02_pd *orphan_sq_pd;
    u32 local_ip, next_pd, pd_count, mr_count, cq_count;
    u8 peer_mac[6];
    bool initialized, stopping;
    /* Standard-device publication has a separate sleepable lifetime lock:
     * IB core registration calls query/GID/context callbacks synchronously.
     * Never hold the ordinary verbs lock across that core call.
     */
    struct mutex device_lock;
    struct device *device_parent;
    struct net_device *netdev;
    void __iomem *ethernet_registers;
    u32 route_epoch, context_count;
    u8 local_mac[6];
    bool core_allocated, registration_attempted, metadata_ready;
    bool published, publishing, accepting_contexts;
};
/* Bind actual initialized SAME-MR/SQ/CQ/control graph to genuine RDMA object
 * callbacks. Takes pool clients. Caller owns ib_device/module/BAR lifetime.
 * Reads exact RNE1 active route, refuses nonempty/mismatched pools. It does
 * NOT register an empty ib_device or expose incomplete RC/user verbs.
 * Complete retry/PSN programming, user provider, native retirement and board
 * gates are still required before the parent may call ib_register_device.
 */
int as02_verbs_bind(struct as02_verbs_device *, struct as02_mr_pool *,
                    struct as02_sq_pool *, struct as02_cq_hw *,
                    struct as02_qp_hw *, struct as02_cq_router *,
                    void __iomem *ethernet_regs, size_t);
int as02_verbs_unbind(struct as02_verbs_device *);
/* Explicit bounded cleanup of failed creations; uses actual drain callbacks.
 * Failure retains all PD/mapping/ring ownership, including core-freed QP
 * allocation failures. Never infer cancellation from the original error.
 */
int as02_verbs_reap(struct as02_verbs_device *);
extern const struct ib_device_ops as02_verbs_ops;
#endif
