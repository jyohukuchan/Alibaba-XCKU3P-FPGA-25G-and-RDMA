/* SPDX-License-Identifier: GPL-2.0 OR BSD-2-Clause-Views */
#ifndef AS02_WQE_SEGMENTED_READ_H
#define AS02_WQE_SEGMENTED_READ_H
#include "wqe_segmented.h"
/* Explicit serialization-only private READ profile. Never MR authorization,
 * posting, DMA, a driver/provider capability or default profile selection.
 * Requires independently matched RNC16383/CQC63 native/software qualification.
 * WRITE/SEND and every old zero/Immediate/Atomic policy remain unchanged. */
int as02_segmented_read_wqe_validate(const struct as02_atomic_wqe *);
int as02_segmented_read_wqe_encode(as02_byte out[AS02_ATOMIC_WQE_BYTES],const struct as02_atomic_wqe *);
int as02_segmented_read_wqe_decode(struct as02_atomic_wqe *,const as02_byte in[AS02_ATOMIC_WQE_BYTES]);
#endif
