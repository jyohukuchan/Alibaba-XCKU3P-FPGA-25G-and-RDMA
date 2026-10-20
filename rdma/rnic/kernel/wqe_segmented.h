/* SPDX-License-Identifier: GPL-2.0 OR BSD-2-Clause-Views */
#ifndef AS02_WQE_SEGMENTED_H
#define AS02_WQE_SEGMENTED_H
#include "wqe_zero.h"
#define AS02_SEGMENTED_WQE_MAX_BYTES 1048576U
/* Explicit software-only private profile: ordinary WRITE/SEND up to1MiB.
 * All other operations retain their exact zero/Atomic/4096-byte policies.
 * Never a post operation or MR/PD/DMA authorization. Trusted QP/PD/expected
 * sequence/epoch and actual full-range MR/PTE authority remain RTL duties.
 * Do not select for installed/default drivers or unmatched hardware. */
int as02_segmented_wqe_validate(const struct as02_atomic_wqe *);
int as02_segmented_wqe_encode(as02_byte out[AS02_ATOMIC_WQE_BYTES],const struct as02_atomic_wqe *);
int as02_segmented_wqe_decode(struct as02_atomic_wqe *,const as02_byte in[AS02_ATOMIC_WQE_BYTES]);
#endif
