/* SPDX-License-Identifier: GPL-2.0 OR BSD-2-Clause-Views */
/* Actual correctly typed Linux WR adapters. Zero SGE/one zero-length SGE
 * canonicalize to no local MR/address; never read the unused SGE/address/key.
 * No posting/ref acquisition or capability advertisement is performed here.
 */
#include <linux/errno.h>
#include <linux/export.h>
#include <linux/string.h>
#include <rdma/ib_verbs.h>
#include "atomic_profile.h"
#include "wqe_zero.h"

int as02_zero_wqe_from_ib_send_wr(as02_byte out[AS02_ATOMIC_WQE_BYTES],const struct ib_send_wr *wr,u64 sequence,u64 epoch)
{
    struct as02_atomic_wqe w={};const struct ib_rdma_wr *r;
    if(!out)return -EINVAL;
    memset(out,0,AS02_ATOMIC_WQE_BYTES);if(!wr)return -EINVAL;
    if(wr->opcode==IB_WR_ATOMIC_CMP_AND_SWP || wr->opcode==IB_WR_ATOMIC_FETCH_AND_ADD ||
       (wr->num_sge==1 && wr->sg_list && wr->sg_list[0].length))
        return as02_atomic_wqe_from_ib_send_wr(out,wr,sequence,epoch);
    if((wr->num_sge!=0 && wr->num_sge!=1) || (wr->num_sge && !wr->sg_list) ||
       (wr->send_flags&~IB_SEND_SIGNALED))return -EOPNOTSUPP;
    w.base=(struct as02_wqe){.wr_id=wr->wr_id,.sequence=sequence,.epoch=epoch,
        .flags=(wr->send_flags&IB_SEND_SIGNALED) ? AS02_WQE_SIGNALED:0};
    switch(wr->opcode){
    case IB_WR_SEND:w.base.opcode=AS02_WQE_SEND;break;
    case IB_WR_SEND_WITH_IMM:w.base.opcode=AS02_WQE_SEND_IMMEDIATE;break;
    case IB_WR_RDMA_READ:case IB_WR_RDMA_WRITE:case IB_WR_RDMA_WRITE_WITH_IMM:
        r=rdma_wr(wr);w.base.remote_address=r->remote_addr;w.base.remote_key=r->rkey;
        w.base.opcode=wr->opcode==IB_WR_RDMA_READ ? AS02_WQE_READ:
            wr->opcode==IB_WR_RDMA_WRITE ? AS02_WQE_WRITE:AS02_WQE_WRITE_IMMEDIATE;break;
    default:return -EOPNOTSUPP;
    }
    if(wr->opcode==IB_WR_SEND_WITH_IMM || wr->opcode==IB_WR_RDMA_WRITE_WITH_IMM)
        w.base.immediate=be32_to_cpu(wr->ex.imm_data);
    return as02_zero_wqe_encode(out,&w);
}
int as02_zero_wqe_from_ib_recv_wr(as02_byte out[AS02_ATOMIC_WQE_BYTES],const struct ib_recv_wr *wr,u64 sequence,u64 epoch)
{
    struct as02_atomic_wqe w={};
    if(!out)return -EINVAL;
    memset(out,0,AS02_ATOMIC_WQE_BYTES);if(!wr)return -EINVAL;
    if(wr->num_sge==1 && wr->sg_list && wr->sg_list[0].length)
        return as02_atomic_wqe_from_ib_recv_wr(out,wr,sequence,epoch);
    if((wr->num_sge!=0 && wr->num_sge!=1) || (wr->num_sge && !wr->sg_list))return -EOPNOTSUPP;
    w.base=(struct as02_wqe){.wr_id=wr->wr_id,.sequence=sequence,.epoch=epoch,.opcode=AS02_WQE_RECV,.flags=AS02_WQE_SIGNALED};
    return as02_zero_wqe_encode(out,&w);
}
EXPORT_SYMBOL_GPL(as02_zero_wqe_from_ib_send_wr);
EXPORT_SYMBOL_GPL(as02_zero_wqe_from_ib_recv_wr);
