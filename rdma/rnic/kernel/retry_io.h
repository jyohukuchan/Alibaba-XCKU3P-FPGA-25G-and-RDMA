/* SPDX-License-Identifier: GPL-2.0 OR BSD-2-Clause-Views */
#ifndef AS02_RETRY_IO_H
#define AS02_RETRY_IO_H
#include "sq_io.h"
#define AS02_RRP_BYTES 0x100U
#define AS02_RRP_ID 0x52525031U
#define AS02_RRP_ABI 0x00010000U
struct as02_retry_policy {
    as02_u64 cookie, epoch;
    as02_u32 qpn, pd, timeout, retry, rnr_retry;
};
struct as02_retry_io {
    const struct as02_sqc_transport *io;
    void *context;
    struct as02_retry_policy held;
    as02_u32 sequence, timeout_us, clock_period_ps;
    int initialized, pending, uncertain;
};
/* Same bounded MMIO/time callbacks as SQC1. Native RRP1 must actually read
 * back the retained replay owner's policy and trusted SQC1 cookie/epoch/PD.
 * No shadow CSR echo, old firmware fallback or fake success is supported.
 * Any ambiguous posted bell/ACK retains this full owner and caller refs.
 */
int as02_retry_io_init(struct as02_retry_io *, const struct as02_sqc_transport *,
                       void *, as02_u32 timeout_us);
int as02_retry_io_configure(struct as02_retry_io *, const struct as02_retry_policy *);
#endif
