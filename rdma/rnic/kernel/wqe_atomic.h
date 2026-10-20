/* SPDX-License-Identifier: GPL-2.0 OR BSD-2-Clause-Views */
/* Copyright (c) 2026 jyohukuchan */
#ifndef AS02_WQE_ATOMIC_H
#define AS02_WQE_ATOMIC_H
#include "wqe.h"

#define AS02_ATOMIC_WQE_BYTES 128U
#define AS02_WQE_COMPARE_SWAP 7U
#define AS02_WQE_FETCH_ADD 8U

/* Candidate matched128-byte SQ format, NOT a current device capability.
 * Bytes0..63 keep the existing explicit LE Immediate-profile field layout;
 * op7/8 require length8, immediate0 and aligned remote VA. Bytes64..71 carry
 * LE compare (CAS only; FAA must0),72..79 carry LE swap/add,80..127 MUST0.
 * Normal/Immediate/RECV operations use the same header and all-zero extension.
 * Local address/key identify the protected8-byte RESULT, never an operand
 * source or DMA address. Full QPN/PD/expected sequence/epoch remain trusted
 * queue metadata. No MR reference, DMA/WR ownership or completion is acquired
 * by this codec. Default64-byte APIs and IB_ATOMIC_NONE remain unchanged.
 * Software representation only: NEVER cast it onto coherent device memory.
 */
struct as02_atomic_wqe {
    struct as02_wqe base;
    as02_u64 compare, swap_add;
};

int as02_atomic_wqe_validate(const struct as02_atomic_wqe *);
/* Failure zeros output; overlap is supported when caller storage is large
 * enough for the128-byte wire record / complete software structure. */
int as02_atomic_wqe_encode(as02_byte out[AS02_ATOMIC_WQE_BYTES], const struct as02_atomic_wqe *);
int as02_atomic_wqe_decode(struct as02_atomic_wqe *, const as02_byte in[AS02_ATOMIC_WQE_BYTES]);
#endif
