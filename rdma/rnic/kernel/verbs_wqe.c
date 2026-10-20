/* SPDX-License-Identifier: GPL-2.0 OR BSD-2-Clause-Views */
/* Copyright (c) 2026 jyohukuchan */
#include <linux/errno.h>
#include <linux/export.h>
#include <linux/string.h>
#include <rdma/ib_verbs.h>
#include "wqe.h"

int as02_wqe_from_ib_send_wr_profile(as02_byte out[AS02_WQE_BYTES],
                                    const struct ib_send_wr *wr, u64 sequence, u64 epoch, u32 profile)
{
    const struct ib_rdma_wr *rdma;
    struct as02_wqe w;
    if (!out)
        return -EINVAL;
    if (!wr) {
        memset(out, 0, AS02_WQE_BYTES);
        return -EINVAL;
    }
    if (wr->opcode != IB_WR_RDMA_WRITE && wr->opcode != IB_WR_RDMA_READ && wr->opcode != IB_WR_SEND &&
        (!(profile & AS02_WQE_PROFILE_IMMEDIATE) ||
         (wr->opcode != IB_WR_SEND_WITH_IMM && wr->opcode != IB_WR_RDMA_WRITE_WITH_IMM))) {
        memset(out, 0, AS02_WQE_BYTES);
        return -EOPNOTSUPP;
    }
    if (wr->num_sge != 1 || !wr->sg_list ||
        (wr->send_flags & ~IB_SEND_SIGNALED)) {
        memset(out, 0, AS02_WQE_BYTES);
        return -EOPNOTSUPP;
    }
    memset(&w, 0, sizeof(w));
    w.wr_id = wr->wr_id;
    w.sequence = sequence;
    w.epoch = epoch;
    w.local_address = wr->sg_list[0].addr;
    w.length = wr->sg_list[0].length;
    w.local_key = wr->sg_list[0].lkey;
    if (wr->opcode == IB_WR_SEND || wr->opcode == IB_WR_SEND_WITH_IMM) {
        /* Genuine base WR: never cast/read beyond it as an ib_rdma_wr. */
        w.opcode = wr->opcode == IB_WR_SEND ? AS02_WQE_SEND : AS02_WQE_SEND_IMMEDIATE;
    } else {
        rdma = rdma_wr(wr);
        w.remote_address = rdma->remote_addr;
        w.remote_key = rdma->rkey;
        w.opcode = wr->opcode == IB_WR_RDMA_WRITE ? AS02_WQE_WRITE :
            wr->opcode == IB_WR_RDMA_READ ? AS02_WQE_READ : AS02_WQE_WRITE_IMMEDIATE;
    }
    if (wr->opcode == IB_WR_SEND_WITH_IMM || wr->opcode == IB_WR_RDMA_WRITE_WITH_IMM)
        w.immediate = be32_to_cpu(wr->ex.imm_data);
    w.flags = (wr->send_flags & IB_SEND_SIGNALED) ? AS02_WQE_SIGNALED : 0;
    return as02_wqe_encode_profile(out, &w, profile);
}
EXPORT_SYMBOL_GPL(as02_wqe_from_ib_send_wr_profile);
int as02_wqe_from_ib_send_wr(as02_byte out[AS02_WQE_BYTES],
                            const struct ib_send_wr *wr, u64 sequence, u64 epoch)
{ return as02_wqe_from_ib_send_wr_profile(out, wr, sequence, epoch, 0); }
EXPORT_SYMBOL_GPL(as02_wqe_from_ib_send_wr);
int as02_wqe_from_ib_recv_wr(as02_byte out[AS02_WQE_BYTES],
                            const struct ib_recv_wr *wr, u64 sequence, u64 epoch)
{
    struct as02_wqe w = {};
    if (!out) return -EINVAL;
    memset(out, 0, AS02_WQE_BYTES);
    if (!wr) return -EINVAL;
    if (wr->num_sge != 1 || !wr->sg_list) return -EOPNOTSUPP;
    w.wr_id=wr->wr_id;w.sequence=sequence;w.epoch=epoch;
    w.local_address=wr->sg_list[0].addr;w.local_key=wr->sg_list[0].lkey;
    w.length=wr->sg_list[0].length;w.opcode=AS02_WQE_RECV;w.flags=AS02_WQE_SIGNALED;
    return as02_wqe_encode(out,&w);
}
EXPORT_SYMBOL_GPL(as02_wqe_from_ib_recv_wr);
