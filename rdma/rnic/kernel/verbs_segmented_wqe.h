/* SPDX-License-Identifier: GPL-2.0 OR BSD-2-Clause-Views */
#ifndef AS02_VERBS_SEGMENTED_WQE_H
#define AS02_VERBS_SEGMENTED_WQE_H
#include "wqe_segmented.h"
#ifdef __KERNEL__
struct ib_send_wr;
/* Private adapter only. Caller must negotiate the matched large transport
 * before posting, and acquire the actual full-range MR/PD/SQ references.
 * Does not post, access payload memory, grant DMA or advertise capabilities.
 */
int as02_segmented_wqe_from_ib_send_wr(as02_byte out[AS02_ATOMIC_WQE_BYTES],
                                     const struct ib_send_wr *, u64, u64);
#endif
#endif
