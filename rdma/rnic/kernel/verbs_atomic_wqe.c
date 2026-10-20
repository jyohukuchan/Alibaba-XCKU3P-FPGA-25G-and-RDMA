/* SPDX-License-Identifier: GPL-2.0 OR BSD-2-Clause-Views */
/* Actual Linux WR adapter; caller owns genuine correctly typed WR storage.
 * No capability advertisement, posting, MR reference or CPU payload access.
 */
#include <linux/errno.h>
#include <linux/export.h>
#include <linux/string.h>
#include <rdma/ib_verbs.h>
#include "atomic_profile.h"

int as02_atomic_wqe_from_ib_send_wr(as02_byte out[AS02_ATOMIC_WQE_BYTES],
                                   const struct ib_send_wr *wr,u64 sequence,u64 epoch)
{
    struct as02_atomic_wqe w={};
    as02_byte legacy[AS02_WQE_BYTES];
    const struct ib_atomic_wr *a;
    int ret;
    if(!out)return -EINVAL;
    memset(out,0,AS02_ATOMIC_WQE_BYTES);
    if(!wr)return -EINVAL;
    if(wr->opcode!=IB_WR_ATOMIC_CMP_AND_SWP && wr->opcode!=IB_WR_ATOMIC_FETCH_AND_ADD){
        ret=as02_wqe_from_ib_send_wr_profile(legacy,wr,sequence,epoch,AS02_WQE_PROFILE_IMMEDIATE);
        if(ret)return ret;
        ret=as02_wqe_decode_profile(&w.base,legacy,AS02_WQE_PROFILE_IMMEDIATE);
        return ret ? ret:as02_atomic_wqe_encode(out,&w);
    }
    if(wr->num_sge!=1 || !wr->sg_list || (wr->send_flags&~IB_SEND_SIGNALED))return -EOPNOTSUPP;
    a=atomic_wr(wr);
    w.base=(struct as02_wqe){.wr_id=wr->wr_id,.sequence=sequence,.epoch=epoch,
        .local_address=wr->sg_list[0].addr,.length=wr->sg_list[0].length,.local_key=wr->sg_list[0].lkey,
        .remote_address=a->remote_addr,.remote_key=a->rkey,
        .opcode=wr->opcode==IB_WR_ATOMIC_CMP_AND_SWP ? AS02_WQE_COMPARE_SWAP:AS02_WQE_FETCH_ADD,
        .flags=(wr->send_flags&IB_SEND_SIGNALED) ? AS02_WQE_SIGNALED:0};
    w.compare=wr->opcode==IB_WR_ATOMIC_CMP_AND_SWP ? a->compare_add:0;
    w.swap_add=wr->opcode==IB_WR_ATOMIC_CMP_AND_SWP ? a->swap:a->compare_add;
    return as02_atomic_wqe_encode(out,&w);
}
int as02_atomic_wqe_from_ib_recv_wr(as02_byte out[AS02_ATOMIC_WQE_BYTES],
                                   const struct ib_recv_wr *wr,u64 sequence,u64 epoch)
{
    struct as02_atomic_wqe w={};as02_byte legacy[AS02_WQE_BYTES];int ret;
    if(!out)return -EINVAL;
    memset(out,0,AS02_ATOMIC_WQE_BYTES);
    ret=as02_wqe_from_ib_recv_wr(legacy,wr,sequence,epoch);
    if(ret)return ret;
    ret=as02_wqe_decode_profile(&w.base,legacy,AS02_WQE_PROFILE_IMMEDIATE);
    return ret ? ret:as02_atomic_wqe_encode(out,&w);
}
EXPORT_SYMBOL_GPL(as02_atomic_wqe_from_ib_send_wr);
EXPORT_SYMBOL_GPL(as02_atomic_wqe_from_ib_recv_wr);
