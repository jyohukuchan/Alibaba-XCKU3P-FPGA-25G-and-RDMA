/* SPDX-License-Identifier: GPL-2.0 OR BSD-2-Clause-Views */
#ifndef AS02_WQE_SEGMENTED_IMMEDIATE_H
#define AS02_WQE_SEGMENTED_IMMEDIATE_H
#include "wqe_segmented_read.h"
/* Separate source-only codec. No default/profile5 capability is raised. */
int as02_segmented_immediate_wqe_validate(const struct as02_atomic_wqe *);
int as02_segmented_immediate_wqe_encode(as02_byte [AS02_ATOMIC_WQE_BYTES], const struct as02_atomic_wqe *);
int as02_segmented_immediate_wqe_decode(struct as02_atomic_wqe *, const as02_byte [AS02_ATOMIC_WQE_BYTES]);
#endif
