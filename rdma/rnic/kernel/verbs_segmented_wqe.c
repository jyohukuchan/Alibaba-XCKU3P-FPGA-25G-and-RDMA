/* SPDX-License-Identifier: GPL-2.0 OR BSD-2-Clause-Views */
/* Private Linux WR adapter; not selected by any default/installed callback.
 * Exactly one SGE; base SEND is never read as an extended RDMA/Atomic WR.
 * Existing zero/Atomic/READ/Immediate and <=4096 policies remain unchanged.
 */
#include <linux/errno.h>
#include <linux/export.h>
#include <linux/string.h>
#include <rdma/ib_verbs.h>
#include "verbs_segmented_wqe.h"

int as02_segmented_wqe_from_ib_send_wr(as02_byte out[AS02_ATOMIC_WQE_BYTES],
                                     const struct ib_send_wr *wr, u64 sequence, u64 epoch)
{
    struct as02_atomic_wqe w = {};
    const struct ib_rdma_wr *rdma;

    if (!out)
        return -EINVAL;
    if (!wr) {
        memset(out, 0, AS02_ATOMIC_WQE_BYTES);
        return -EINVAL;
    }
    if ((wr->opcode != IB_WR_RDMA_WRITE && wr->opcode != IB_WR_SEND) ||
        wr->num_sge != 1 || !wr->sg_list ||
        wr->sg_list[0].length <= AS02_WQE_MAX_BYTES)
        return as02_zero_wqe_from_ib_send_wr(out, wr, sequence, epoch);

    memset(out, 0, AS02_ATOMIC_WQE_BYTES);
    if (wr->send_flags & ~IB_SEND_SIGNALED)
        return -EOPNOTSUPP;
    w.base = (struct as02_wqe){
        .wr_id = wr->wr_id, .sequence = sequence, .epoch = epoch,
        .local_address = wr->sg_list[0].addr,
        .length = wr->sg_list[0].length, .local_key = wr->sg_list[0].lkey,
        .opcode = wr->opcode == IB_WR_SEND ? AS02_WQE_SEND : AS02_WQE_WRITE,
        .flags = (wr->send_flags & IB_SEND_SIGNALED) ? AS02_WQE_SIGNALED : 0,
    };
    if (wr->opcode == IB_WR_RDMA_WRITE) {
        rdma = rdma_wr(wr);
        w.base.remote_address = rdma->remote_addr;
        w.base.remote_key = rdma->rkey;
    }
    return as02_segmented_wqe_encode(out, &w);
}
EXPORT_SYMBOL_GPL(as02_segmented_wqe_from_ib_send_wr);
