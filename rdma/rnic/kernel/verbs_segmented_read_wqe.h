/* SPDX-License-Identifier: GPL-2.0 OR BSD-2-Clause-Views */
#ifndef AS02_VERBS_SEGMENTED_READ_WQE_H
#define AS02_VERBS_SEGMENTED_READ_WQE_H
#include "wqe_segmented_read.h"
#ifdef __KERNEL__
struct ib_send_wr;
/* Private profile5 adapter only. No posting/MR/DMA authority; caller MUST
 * bind exact RNC16383/CQC63 and retain actual full-range MR/PD/queue refs. */
int as02_segmented_read_wqe_from_ib_send_wr(as02_byte out[AS02_ATOMIC_WQE_BYTES],
                                          const struct ib_send_wr *,u64,u64);
#endif
#endif
