/* SPDX-License-Identifier: GPL-2.0 OR BSD-2-Clause-Views */
/* Matched128-byte SOURCE profile only; not a device capability or DMA proof.
 * Included by checked private kernel derivatives, never the default build.
 * RNC1023 + SQC13/RQC15/CQC15 AND exact geometry must be negotiated before
 * allocating either ring. Profile3 includes the existing Immediate header.
 */
#ifndef AS02_ATOMIC_PROFILE_H
#define AS02_ATOMIC_PROFILE_H
#include "wqe_atomic.h"
#include "sq_regs.h"
#include "cq_regs.h"
#define AS02_WQE_PROFILE_ATOMIC128 3U
#define AS02_SQC_ATOMIC_FEATURE_VALUE 13U
#define AS02_RQC_ATOMIC_FEATURE_VALUE 15U
#define AS02_CQC_ATOMIC_FEATURE_VALUE 15U
#define AS02_SQC_DESCRIPTOR_BYTES 0x020U
#define AS02_CQC_OWNER_BITS 0x094U
#define AS02_CQC_OPERAND_BASE 0x098U
#define AS02_CQC_ATOMIC_OPERANDS 0x0a0U
#define AS02_CQC_ATOMIC_OWNER_BITS 748U

static inline int as02_is_atomic_opcode(as02_u32 op)
{ return op==AS02_WQE_COMPARE_SWAP || op==AS02_WQE_FETCH_ADD; }
static inline as02_u32 as02_profile_descriptor_bytes(as02_u32 profile)
{ return profile==AS02_WQE_PROFILE_ATOMIC128 ? AS02_ATOMIC_WQE_BYTES:AS02_WQE_BYTES; }
#ifdef __KERNEL__
struct ib_send_wr;
struct ib_recv_wr;
int as02_atomic_wqe_from_ib_send_wr(as02_byte out[AS02_ATOMIC_WQE_BYTES],
                                   const struct ib_send_wr *,u64,u64);
int as02_atomic_wqe_from_ib_recv_wr(as02_byte out[AS02_ATOMIC_WQE_BYTES],
                                   const struct ib_recv_wr *,u64,u64);
#endif
#endif
