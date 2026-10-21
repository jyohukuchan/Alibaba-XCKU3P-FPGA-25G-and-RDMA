/* SPDX-License-Identifier: GPL-2.0 OR BSD-2-Clause-Views */
/* Private Linux WR adapter, never a default/installed/posting callback. */
#include <linux/errno.h>
#include <linux/export.h>
#include <linux/string.h>
#include <rdma/ib_verbs.h>
#include "verbs_segmented_read_wqe.h"
#include "verbs_segmented_wqe.h"

int as02_segmented_read_wqe_from_ib_send_wr(as02_byte out[AS02_ATOMIC_WQE_BYTES],
                                          const struct ib_send_wr *wr,u64 sequence,u64 epoch)
{
    struct as02_atomic_wqe w = {};
    const struct ib_rdma_wr *rdma;

    if (!out)
        return -EINVAL;
    if (!wr) {
        memset(out,0,AS02_ATOMIC_WQE_BYTES);
        return -EINVAL;
    }
    if (wr->opcode != IB_WR_RDMA_READ || wr->num_sge != 1 || !wr->sg_list ||
        wr->sg_list[0].length <= AS02_WQE_MAX_BYTES)
        return as02_segmented_wqe_from_ib_send_wr(out,wr,sequence,epoch);

    memset(out,0,AS02_ATOMIC_WQE_BYTES);
    if (wr->send_flags & ~IB_SEND_SIGNALED)
        return -EOPNOTSUPP;
    /* Access the extended RDMA object ONLY after proving the real WR kind.
     * Base-only SEND and all old opcodes go through the unchanged adapter. */
    rdma=rdma_wr(wr);
    w.base=(struct as02_wqe){
        .wr_id=wr->wr_id,.sequence=sequence,.epoch=epoch,
        .local_address=wr->sg_list[0].addr,.length=wr->sg_list[0].length,
        .local_key=wr->sg_list[0].lkey,.remote_address=rdma->remote_addr,
        .remote_key=rdma->rkey,.opcode=AS02_WQE_READ,
        .flags=(wr->send_flags & IB_SEND_SIGNALED) ? AS02_WQE_SIGNALED:0,
    };
    return as02_segmented_read_wqe_encode(out,&w);
}
EXPORT_SYMBOL_GPL(as02_segmented_read_wqe_from_ib_send_wr);
