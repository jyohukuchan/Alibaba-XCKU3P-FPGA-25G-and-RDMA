/* SPDX-License-Identifier: GPL-2.0 OR BSD-2-Clause-Views */
/* Correctly typed standard RECV WR -> full posted capacity; source only. */
#include <linux/errno.h>
#include <linux/export.h>
#include <linux/string.h>
#include <rdma/ib_verbs.h>
#include "atomic_profile.h"
#include "verbs_segmented_receive_wqe.h"

int as02_segmented_receive_wqe_from_ib_recv_wr(as02_byte out[AS02_ATOMIC_WQE_BYTES],
                                              const struct ib_recv_wr *wr,
                                              as02_u64 sequence, as02_u64 epoch)
{
    struct as02_atomic_wqe w = {};
    if (!out)
        return -EINVAL;
    memset(out, 0, AS02_ATOMIC_WQE_BYTES);
    if (!wr)
        return -EINVAL;
    if (wr->num_sge != 1 || !wr->sg_list || wr->sg_list[0].length <= AS02_WQE_MAX_BYTES)
        return as02_zero_wqe_from_ib_recv_wr(out, wr, sequence, epoch);
    w.base = (struct as02_wqe){
        .wr_id=wr->wr_id, .sequence=sequence, .epoch=epoch,
        .local_address=wr->sg_list[0].addr, .local_key=wr->sg_list[0].lkey,
        .length=wr->sg_list[0].length, .opcode=AS02_WQE_RECV,
        .flags=AS02_WQE_SIGNALED,
    };
    return as02_segmented_receive_wqe_encode(out, &w);
}
EXPORT_SYMBOL_GPL(as02_segmented_receive_wqe_from_ib_recv_wr);
