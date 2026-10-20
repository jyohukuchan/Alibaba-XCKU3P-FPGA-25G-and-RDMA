/* SPDX-License-Identifier: BSD-2-Clause-Views */
/* Actual verbs_wqe.c/codec with modeled Linux WR types, not a post callback. */
#include "kernel_queue_model.h"
#include "wqe.h"
#include <assert.h>
#include <stdio.h>
int main(void)
{
    struct ib_sge s={.addr=0xfedcba9876543210ULL,.length=65,.lkey=0x80000008};
    const u32 values[]={0,0x01234567,0x80000000,0xffffffff};
    unsigned int op,i,j;unsigned char encoded[64];struct as02_wqe w;
    assert(sizeof(w)==64);
    for(op=0;op<2;op++)for(i=0;i<4;i++) {
        struct ib_send_wr send={.wr_id=0xf123456789abc001ULL,.sg_list=&s,.num_sge=1,
            .opcode=IB_WR_SEND_WITH_IMM,.send_flags=IB_SEND_SIGNALED};
        struct ib_rdma_wr rdma={.wr={.wr_id=send.wr_id,.sg_list=&s,.num_sge=1,
            .opcode=IB_WR_RDMA_WRITE_WITH_IMM,.send_flags=IB_SEND_SIGNALED},
            .remote_addr=0xe23456789abcdef0ULL,.rkey=values[i]^0x81234567};
        const struct ib_send_wr *wr=op ? &rdma.wr:&send;
        send.ex.imm_data=cpu_to_be32(values[i]);rdma.wr.ex.imm_data=send.ex.imm_data;
        memset(encoded,0xa5,sizeof(encoded));
        assert(as02_wqe_from_ib_send_wr(encoded,wr,1,0x9123456700000001ULL)==-EOPNOTSUPP);
        for(j=0;j<64;j++)assert(encoded[j]==0);
        assert(as02_wqe_from_ib_send_wr_profile(encoded,wr,1,0x9123456700000001ULL,1)==0);
        assert(as02_wqe_decode_profile(&w,encoded,1)==0);
        assert(w.opcode==(op ? 6:5) && w.immediate==values[i] && w.local_address==s.addr &&
            w.local_key==s.lkey && w.length==65 && w.flags==1 &&
            w.remote_key==(op ? rdma.rkey:0) && w.remote_address==(op ? rdma.remote_addr:0));
        for(j=0;j<4;j++)assert(encoded[48+j]==((values[i]>>(8*j))&255));
        for(j=52;j<56;j++)assert(encoded[j]==0);
    }
    puts("IMMEDIATE_VERBS_WQE {\"pass_test\":true,\"actual_C_adapters_and_codec\":true,\"base_SEND_not_RDMA_cast\":true,\"explicit_profile_cases\":8,\"default_posting_profile_refuses\":true,\"Linux_WR_types_modeled\":true,\"actual_post_send\":false}");
    return 0;
}
