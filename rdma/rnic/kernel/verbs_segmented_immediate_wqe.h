/* SPDX-License-Identifier: GPL-2.0 OR BSD-2-Clause-Views */
#ifndef AS02_VERBS_SEGMENTED_IMMEDIATE_WQE_H
#define AS02_VERBS_SEGMENTED_IMMEDIATE_WQE_H
#include "wqe_segmented_immediate.h"
#ifdef __KERNEL__
struct ib_send_wr;
/* Private profile6 serialization only. Actual posting retains MR/PD/ranges,
 * queue refs and exact32767/127/13/15/128 geometry binding. */
int as02_segmented_immediate_wqe_from_ib_send_wr(as02_byte [AS02_ATOMIC_WQE_BYTES],
                                               const struct ib_send_wr *,u64,u64);
#endif
#endif
