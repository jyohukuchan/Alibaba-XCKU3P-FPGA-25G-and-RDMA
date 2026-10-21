/* SPDX-License-Identifier: GPL-2.0 OR BSD-2-Clause-Views */
#ifndef AS02_WQE_SEGMENTED_RECEIVE_H
#define AS02_WQE_SEGMENTED_RECEIVE_H
#include "wqe_segmented_immediate.h"
/* Separate65535/255/13/31 source cohort only. No MR/DMA permission or
 * installed/default/kernel/provider capability follows serialization. */
int as02_segmented_receive_wqe_validate(const struct as02_atomic_wqe *);
int as02_segmented_receive_wqe_encode(as02_byte [AS02_ATOMIC_WQE_BYTES], const struct as02_atomic_wqe *);
int as02_segmented_receive_wqe_decode(struct as02_atomic_wqe *, const as02_byte [AS02_ATOMIC_WQE_BYTES]);
#endif
