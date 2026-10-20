/* SPDX-License-Identifier: GPL-2.0 OR BSD-2-Clause-Views */
/* Checked zero-aware128-byte SOURCE format; never a default capability. */
#ifndef AS02_WQE_ZERO_H
#define AS02_WQE_ZERO_H
#include "wqe_atomic.h"
int as02_zero_wqe_validate(const struct as02_atomic_wqe *);
int as02_zero_wqe_encode(as02_byte out[AS02_ATOMIC_WQE_BYTES],const struct as02_atomic_wqe *);
int as02_zero_wqe_decode(struct as02_atomic_wqe *,const as02_byte in[AS02_ATOMIC_WQE_BYTES]);
#ifdef __KERNEL__
struct ib_send_wr;struct ib_recv_wr;
int as02_zero_wqe_from_ib_send_wr(as02_byte out[AS02_ATOMIC_WQE_BYTES],const struct ib_send_wr *,u64,u64);
int as02_zero_wqe_from_ib_recv_wr(as02_byte out[AS02_ATOMIC_WQE_BYTES],const struct ib_recv_wr *,u64,u64);
#endif
#endif
