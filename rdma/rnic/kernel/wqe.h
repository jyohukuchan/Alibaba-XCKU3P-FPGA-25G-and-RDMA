/* SPDX-License-Identifier: GPL-2.0 OR BSD-2-Clause-Views */
/* Copyright (c) 2026 jyohukuchan */
#ifndef AS02_WQE_H
#define AS02_WQE_H
#include "mr_contract.h"
#ifdef __KERNEL__
typedef u8 as02_byte;
#else
typedef uint8_t as02_byte;
#endif

#define AS02_WQE_BYTES 64U
#define AS02_WQE_MAX_BYTES 4096U
#define AS02_WQE_WRITE 1U
#define AS02_WQE_READ 2U
#define AS02_WQE_SEND 3U
#define AS02_WQE_RECV 4U
#define AS02_WQE_SEND_IMMEDIATE 5U
#define AS02_WQE_WRITE_IMMEDIATE 6U
#define AS02_WQE_SIGNALED 1U
#define AS02_WQE_PROFILE_IMMEDIATE 1U

/* Software representation ONLY, never cast onto device memory. The fixed
 * 64-byte wire record is explicitly little-endian:
 * 0 WR id,8 sequence,16 local IOVA,24 remote VA,32 length,36 local key,
 * 40 remote key,44 opcode16,46 flags16,48 immediate32,52 reserved32=0,
 * 56 epoch64. Immediate is logical host-order here, explicitly LE on this
 * descriptor and separately network-order on wire. For all normal operations
 * and the default legacy profile, bytes48..55 MUST remain zero.
 * QP/PD/expected epoch+sequence come from TRUSTED queue context, not the WQE.
 * Remote key0 is an exact key. Local lkey/PD/range authorization is a separate
 * hardware gate, not supplied by encode/decode or CPU DMA-address resolution.
 */
struct as02_wqe {
    as02_u64 wr_id, sequence, local_address, remote_address, epoch;
    as02_u32 length, local_key, remote_key, opcode, flags, immediate;
};

int as02_wqe_validate(const struct as02_wqe *);
/* Failure zeros every output byte/field. Buffers may overlap their input.
 * No descriptor is posted, MR pinned, ownership acquired or completion made.
 */
int as02_wqe_encode(as02_byte out[AS02_WQE_BYTES], const struct as02_wqe *);
int as02_wqe_decode(struct as02_wqe *, const as02_byte in[AS02_WQE_BYTES]);
/* Explicit candidate profile, NOT a hardware capability or a post operation.
 * Existing entry points select profile0 and still refuse Immediate. Real SQ
 * posting must not select the new profile before matched native admission,
 * transport, CQ/MMIO and driver/provider support are available. */
int as02_wqe_validate_profile(const struct as02_wqe *, as02_u32 profile);
int as02_wqe_encode_profile(as02_byte out[AS02_WQE_BYTES], const struct as02_wqe *, as02_u32 profile);
int as02_wqe_decode_profile(struct as02_wqe *, const as02_byte in[AS02_WQE_BYTES], as02_u32 profile);

#ifdef __KERNEL__
struct ib_send_wr;
struct ib_recv_wr;
/* Actual ib_rdma_wr/one SGE -> record adapter, NOT a registered post_send.
 * Unsupported flags/SGE counts/opcodes are refused, never silently ignored.
 * Caller must supply a valid Linux WR object matching its opcode. The future
 * queue path must acquire genuine QP/MR ownership and authorize before DMA.
 */
int as02_wqe_from_ib_send_wr(as02_byte out[AS02_WQE_BYTES],
                            const struct ib_send_wr *, u64 sequence, u64 epoch);
int as02_wqe_from_ib_recv_wr(as02_byte out[AS02_WQE_BYTES],
                            const struct ib_recv_wr *, u64 sequence, u64 epoch);
int as02_wqe_from_ib_send_wr_profile(as02_byte out[AS02_WQE_BYTES],
                                    const struct ib_send_wr *, u64 sequence, u64 epoch, u32 profile);
#endif
#endif
