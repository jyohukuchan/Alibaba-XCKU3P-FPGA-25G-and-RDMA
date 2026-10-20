/* SPDX-License-Identifier: GPL-2.0 OR BSD-2-Clause-Views */
#ifndef AS02_NATIVE_GRAPH_H
#define AS02_NATIVE_GRAPH_H
#include "device.h"
#include "native_attach.h"
#include "sq_hw.h"

struct as02_native_graph;
/* Caller-owned epoch/attachment lease, initialized from actual persistent
 * state (all0 ONLY for proven first use). This is not an NVRAM implementation
 * or evidence that a reset/driver reload cancelled an older DMA owner.
 * Caller retains this storage and the actual parent BAR until close succeeds.
 */
struct as02_native_lease {
    struct mutex lock;
    u64 sequence, qp_epochs[AS02_SQ_QPS];
    u32 mr_floor;
    struct as02_native_graph *owner;
    bool initialized;
};
struct as02_native_binding {
    struct as02_native_parent identity;
    struct device *parent;
    struct net_device *data_netdev;
    void __iomem *application_bar;
    size_t application_bytes;
};
struct as02_native_graph {
    struct mutex lock;
    struct as02_native_lease *lease;
    struct device *parent;
    struct net_device *netdev;
    struct as02_verbs_device *device;
    struct as02_rnic_hw control;
    struct as02_mr_pool mrs;
    struct as02_sq_hw sq_hw, rq_hw;
    struct as02_sq_pool queues;
    struct as02_cq_hw completions;
    struct as02_cq_router router;
    struct as02_qp_hw qp;
    u64 lease_sequence, initial_qp_epochs[AS02_SQ_QPS];
    u32 initial_mr_floor;
    bool had_mr_pool, had_sq_pool;
    int open_error;
};
int as02_native_lease_init(struct as02_native_lease *, u32 persisted_mr_floor,
                          const u64 persisted_qp_epochs[AS02_SQ_QPS]);
/* Actual native register adapters only: no caller-supplied successful MR,
 * SQ or CQ hardware backend. Does not map/reclaim a BAR or change a netdev.
 * The bus owner must satisfy original physical/private-parent/native gates.
 * On ANY error after claiming a lease, *out remains an owned handle. Do NOT
 * free/unmap it; reconcile if necessary and call close. Before claim, *out
 * stays NULL. No automatic destructive unwind or invented drain proof.
 */
int as02_native_graph_open(const struct as02_native_binding *, struct as02_native_lease *,
                          struct as02_native_graph **out);
/* Consume an actual retained RNC reply; does not resume/reinitialize queues,
 * clear QP uncertainty or turn reconciliation into memory-release proof.
 */
int as02_native_graph_reconcile_control(struct as02_native_graph *, struct as02_ctl_reply *);
/* Empty/known ownership only. Busy/ambiguous retains the full graph/lease,
 * pinned objects and parent/netdev references. Caller serializes its handle
 * against concurrent use; pool storage lives through IB deallocation.
 * On success updates in-memory watermarks, frees graph and clears *handle.
 * A parent void remove callback cannot treat EBUSY as permission to unmap.
 */
int as02_native_graph_close(struct as02_native_graph **handle);
#endif
