/* SPDX-License-Identifier: GPL-2.0 OR BSD-2-Clause-Views */
#ifndef AS02_CQ_IO_H
#define AS02_CQ_IO_H
#include "wqe.h"
#include "cq_regs.h"

struct as02_cq_event {
    as02_u32 sequence, proofs, status, context[AS02_CQC_CONTEXT_WORDS];
    /* Separate from the immutable posted buffer capacity in context. */
    as02_u32 received_bytes;
    as02_u64 cookie;
    /* Profile1 only: word20 of immutable620-bit owner plus independent
     * wire notification. Legacy19-word publisher/reader stays unchanged. */
    as02_u32 context_extension, notification, notification_flags;
};
struct as02_cq_decoded {
    struct as02_wqe work;
    as02_u64 cookie, local_offset;
    as02_u32 event_sequence, qpn, pd, tag, proofs, status, received_bytes;
    as02_u32 profile, notification, notification_flags;
};
struct as02_cq_transport {
    int (*read32)(void *, as02_u32, as02_u32 *);
    int (*write32)(void *, as02_u32, as02_u32);
};
struct as02_cq_io {
    const struct as02_cq_transport *io;
    void *context;
    struct as02_cq_event held;
    as02_u32 acknowledged, features;
    int initialized, pending_ack, detached, uncertain;
};
/* Decode EVERY bit of the hardware's full 588-bit owner, not a WR-id pointer.
 * No completion or memory reference is released by decoding alone.
 */
int as02_cq_decode(struct as02_cq_decoded *, const struct as02_cq_event *);
int as02_cq_decode_profile(struct as02_cq_decoded *, const struct as02_cq_event *, as02_u32 profile);
/* Shared semantic check for decoded-event consumers; no proof/ref release. */
static inline int as02_cq_notification_valid(const struct as02_cq_decoded *d)
{
    as02_u32 flags;
    if(!d || (d->profile & ~AS02_WQE_PROFILE_IMMEDIATE))return 0;
    flags=d->notification_flags;
    if(!d->profile && (flags || d->notification))return 0;
    if(flags!=0 && flags!=1 && flags!=3)return 0;
    if((!flags && d->notification) || (flags && d->status))return 0;
    if(d->work.opcode!=AS02_WQE_RECV)return !flags && !d->notification && !d->received_bytes;
    if(!d->received_bytes || d->received_bytes>AS02_WQE_MAX_BYTES)return 0;
    return flags==3 || d->received_bytes<=d->work.length;
}
int as02_cq_io_init(struct as02_cq_io *, const struct as02_cq_transport *, void *);
/* Non-sleeping, bounded single event. Deliver returns 0 ONLY after actual
 * SQ/CQ metadata publication and work-reference retirement. Backpressure
 * leaves the event visible. Once delivered, ambiguous ACK is reconciled
 * without ever delivering that event twice. No polling loop or fake CQE.
 * Returns 1 for one acknowledged event, 0 empty, negative on failure.
 */
int as02_cq_io_poll(struct as02_cq_io *,
    int (*deliver)(void *, const struct as02_cq_decoded *), void *);
int as02_cq_io_detach(struct as02_cq_io *);
#endif
