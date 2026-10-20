/* SPDX-License-Identifier: GPL-2.0 OR BSD-2-Clause-Views */
#ifndef AS02_SQ_IO_H
#define AS02_SQ_IO_H
#include "mr_contract.h"
#include "sq_regs.h"

/* Explicit serialized register transport. Production wrapper uses actual
 * readl/writel/monotonic time/cpu_relax, NEVER a sleeping/default-success IO.
 * Both time and poll count bound atomic waits, even if a clock stops.
 */
#define AS02_SQC_MAX_POLLS 256U
#define AS02_SQC_MAX_TIMEOUT_US 1000U
struct as02_sqc_transport {
    int (*read32)(void *, as02_u32, as02_u32 *);
    int (*write32)(void *, as02_u32, as02_u32);
    as02_u64 (*time_us)(void *);
    void (*relax)(void *);
};
struct as02_sqc_reply {
    as02_u32 words[AS02_SQC_WORDS], error, flags;
    as02_u64 consumer;
};
struct as02_sqc_io {
    const struct as02_sqc_transport *io;
    void *context;
    as02_u32 timeout_us, sequence, features, expected[AS02_SQC_WORDS];
    int initialized, pending, uncertain, detached;
};
/* Fresh idle SQC1/ABI1/feature1/sequence0 only; no adoption of another owner.
 * Caller must already prove actual native ABI/lifetime/persistent epochs.
 * ID/sequence0 is NOT proof that a prior reset cancelled old DMA or pins.
 */
int as02_sqc_io_init(struct as02_sqc_io *, const struct as02_sqc_transport *, void *, as02_u32);
int as02_sqc_io_init_id(struct as02_sqc_io *, const struct as02_sqc_transport *, void *, as02_u32,
                        as02_u32 expected_id);
/* words[0] is supplied by this transport, never trusted from a caller.
 * Successful return has an owned ACKed reply; nonzero reply.error is a real
 * semantic rejection, NOT a successful hardware operation/release proof.
 * A pre-bell staging failure never consumes a command sequence.
 */
int as02_sqc_io_execute(struct as02_sqc_io *, const as02_u32 words[AS02_SQC_WORDS], struct as02_sqc_reply *);
/* Match an exact late owned reply only. Transport resynchronization does NOT
 * unquarantine SQ/WR/MR owners or manufacture CQE/abort/drain completion.
 */
int as02_sqc_io_reconcile(struct as02_sqc_io *, struct as02_sqc_reply *);
/* Terminal logical detach, no MMIO/free/reset. Keep expected/pending state
 * and all external references while ownership is uncertain. Never reinit.
 */
int as02_sqc_io_detach(struct as02_sqc_io *);
#endif
