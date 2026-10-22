/* SPDX-License-Identifier: GPL-2.0 OR BSD-2-Clause-Views */
#ifndef AS02_FATAL_IO_H
#define AS02_FATAL_IO_H
#include "mr_contract.h"
#include "fatal_regs.h"

struct as02_fatal_record {
    as02_u32 sequence, word[AS02_FEC_WORDS];
};
struct as02_fatal_decoded {
    struct as02_fatal_record raw;
    as02_u64 serial, cookie, epoch, peer_mac, local_mac;
    as02_u64 message_cookie, address;
    as02_u32 qpn, pd, peer_qpn, peer_ip, local_ip, access;
    as02_u32 syndrome, received_psn, response_psn, msn, partial;
    as02_u32 key, total_bytes, offset, packet_bytes, first_psn, packet_psn, tag, mac_tag;
};
/* From the SAME genuine SQC owner used by native QP configuration binding.
 * This is NOT an RNC command cookie, user WR id or partial-message cookie.
 */
struct as02_fatal_identity {
    as02_u64 cookie, epoch;
    as02_u32 qpn, pd;
};
struct as02_fatal_transport {
    int (*read32)(void *,as02_u32,as02_u32 *);
    int (*write32)(void *,as02_u32,as02_u32);
};
struct as02_fatal_io {
    const struct as02_fatal_transport *io;
    void *context;
    struct as02_fatal_record held;
    as02_u64 last_serial, held_serial;
    as02_u32 acknowledged;
    int initialized, pending_ack, uncertain, detached;
};
/* Validate every reserved/owner/proof/range relationship in selected1000.
 * No IO, object lookup, reference release, standard WC or global drain.
 */
int as02_fatal_decode(struct as02_fatal_decoded *,const struct as02_fatal_record *);
int as02_fatal_identity_matches(const struct as02_fatal_decoded *,const struct as02_fatal_identity *);
int as02_fatal_io_init(struct as02_fatal_io *,const struct as02_fatal_transport *,void *);
/* Serialized, bounded one-event poll. Deliver must bind the actual live QP/
 * SQC cookie+epoch, retain all work/MR/queue references, and record the error
 * atomically before returning0. Nonzero means NOT accepted and is retryable.
 * No synchronous drain or resource release may depend on mailbox ACK.
 * Ambiguous ACK retries never redeliver an already accepted event.
 */
int as02_fatal_io_poll(struct as02_fatal_io *,
    int (*deliver)(void *,const struct as02_fatal_decoded *),void *);
/* Terminal logical detach, NO MMIO/ACK/drain. Retains pending/uncertain state;
 * parent still owns this object, old attachment and every affected reference.
 * Never reinitialize it to adopt a new attachment/reset generation.
 */
int as02_fatal_io_detach(struct as02_fatal_io *);
#endif
