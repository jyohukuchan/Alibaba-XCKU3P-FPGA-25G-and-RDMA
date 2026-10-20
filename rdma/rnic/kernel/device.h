/* SPDX-License-Identifier: GPL-2.0 OR BSD-2-Clause-Views */
#ifndef AS02_STANDARD_DEVICE_H
#define AS02_STANDARD_DEVICE_H
#include "verbs.h"

#define AS02_UVERBS_ABI 1U
#define AS02_GID_ENTRIES 8U
struct as02_ucontext {
    struct ib_ucontext ibucontext;
    bool live, closing;
    int cleanup_error;
};
/* Allocate with IB core, then initialize/bind the SAME actual MR/SQ/RQ/CQ/
 * QP/control graph using the existing APIs. No allocator creates fake queues,
 * enables DMA, resets an epoch, maps a BAR or loads/probes any device.
 */
struct as02_verbs_device *as02_device_alloc(void);
/* Privileged bus owner must already hold the exact parent/BAR/netdev lifetime
 * and satisfy original firmware/timing/CDC/native gates. Netdev must be the
 * actual data port, not an unrelated management interface. Caller establishes
 * the real persistent epochs; publication does not manufacture/reset them.
 * One registration attempt per allocated IB object, even if registration fails.
 */
int as02_device_publish(struct as02_verbs_device *, struct device *parent,
                        struct net_device *, void __iomem *ethernet, size_t);
/* Only empty devices can be unpublished. EBUSY retains registration, pools,
 * contexts and parent/BAR ownership. This is NOT surprise-unplug recovery;
 * a void bus-remove callback cannot substitute for this successful return.
 */
int as02_device_unpublish(struct as02_verbs_device *);
/* Unpublish and unbind/close all genuine pools first. Failed publication also
 * requires normal pool cleanup. IB deallocation releases core netdev refs;
 * own parent/netdev references remain held until that point. Caller retains
 * pool/adapter STORAGE through this call, even after their successful destroy.
 */
int as02_device_free(struct as02_verbs_device *);
extern const struct ib_device_ops as02_device_ops;
#endif
