/* SPDX-License-Identifier: GPL-2.0 OR BSD-2-Clause-Views */
#ifndef AS02_VERBS_SEGMENTED_RECEIVE_WQE_H
#define AS02_VERBS_SEGMENTED_RECEIVE_WQE_H
#include "wqe_segmented_receive.h"
struct ib_recv_wr;
int as02_segmented_receive_wqe_from_ib_recv_wr(as02_byte [AS02_ATOMIC_WQE_BYTES],
                                              const struct ib_recv_wr *, as02_u64, as02_u64);
#endif
