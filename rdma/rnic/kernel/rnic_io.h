/* SPDX-License-Identifier: GPL-2.0 OR BSD-2-Clause-Views */
#ifndef AS02_RNIC_IO_H
#define AS02_RNIC_IO_H
#include "mr_contract.h"
#include "rnic_regs.h"

/* Explicit transport, serialized by the caller. NO default/no-op backend.
 * Only register metadata moves through this API, never user payload bytes.
 */
struct as02_ctl_transport {
    int (*read32)(void *, as02_u32, as02_u32 *);
    int (*write32)(void *, as02_u32, as02_u32);
    as02_u64 (*time_us)(void *);
    void (*wait)(void *);
};
struct as02_ctl_reply {
    as02_u32 sequence, command;
    as02_u64 cookie;
    as02_u32 slot, key, error, flags;
};
struct as02_ctl {
    const struct as02_ctl_transport *io;
    void *context;
    as02_u32 timeout_us, sequence, features;
    int initialized, pending, uncertain, detached;
    as02_u32 expected[AS02_CTL_STAGE_WORDS];
};
int as02_ctl_init(struct as02_ctl *, const struct as02_ctl_transport *, void *, as02_u32);
int as02_ctl_execute(struct as02_ctl *, const as02_u32 *, struct as02_ctl_reply *);
/* A timeout/unknown write never frees pages or resets hardware. An explicitly
 * matched late reply may resynchronize transport; caller STILL performs the
 * MR invalidation/drain lifecycle. Lost ACK with no reply requires separate
 * proven device recovery; this API deliberately does not guess completion.
 */
int as02_ctl_reconcile(struct as02_ctl *, struct as02_ctl_reply *);
/* Terminal logical detach, serialized with ALL other operations. No MMIO,
 * reset, ACK, sequence reuse or memory-release proof. Pending/expected state
 * is retained. The owner must retain this object/context and page/device
 * references if DMA ownership is unknown; detach does NOT solve hot-unplug.
 * Never reinitialize this object to adopt/revive a new attachment.
 */
int as02_ctl_detach(struct as02_ctl *);
#endif
