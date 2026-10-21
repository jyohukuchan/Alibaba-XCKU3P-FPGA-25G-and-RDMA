/* SPDX-License-Identifier: BSD-2-Clause-Views */
/* Real new adapter/codec; WR types are explicit modeled Linux boundaries. */
#include "segmented_read_adapter_prior.c"
#include "verbs_segmented_immediate_wqe.h"

int main(void)
{
    const u32 lengths[]={4097,8193,65537,1048576},values[]={0,0x89abcdefU,0xffffffffU};
    struct ib_send_wr *send=malloc(sizeof(*send));
    struct ib_rdma_wr rdma={};
    struct ib_atomic_wr atomic={};
    struct ib_sge sg={.addr=0xfedcba9876543210ULL};
    struct as02_atomic_wqe expected={};
    unsigned char out[128],old[128];
    unsigned int op,n,k,flag,positive=0,other=0,negative=0;
    assert(send);assert(!preceding_read_adapter_main());
    for(op=0;op<2;op++)for(n=0;n<4;n++)for(k=0;k<3;k++)for(flag=0;flag<2;flag++) {
        struct ib_send_wr *wr=op ? &rdma.wr:send;
        sg.length=lengths[n];sg.lkey=values[k];
        *wr=(struct ib_send_wr){.wr_id=0xf123456789abc001ULL,.opcode=op ? IB_WR_RDMA_WRITE_WITH_IMM:IB_WR_SEND_WITH_IMM,
            .num_sge=1,.sg_list=&sg,.send_flags=flag ? IB_SEND_SIGNALED:0};
        wr->ex.imm_data=cpu_to_be32(values[k]);
        if(op){rdma.remote_addr=0xe23456789abcdef0ULL;rdma.rkey=values[2-k];}
        expected.base=(struct as02_wqe){.wr_id=wr->wr_id,.sequence=0xfedcba9876543210ULL,
            .epoch=0x9123456700000001ULL,.local_address=sg.addr,.local_key=sg.lkey,.length=sg.length,
            .remote_address=op ? rdma.remote_addr:0,.remote_key=op ? rdma.rkey:0,
            .immediate=values[k],.opcode=op ? AS02_WQE_WRITE_IMMEDIATE:AS02_WQE_SEND_IMMEDIATE,
            .flags=flag ? AS02_WQE_SIGNALED:0};
        assert(!as02_segmented_immediate_wqe_from_ib_send_wr(out,wr,expected.base.sequence,expected.base.epoch));
        compare_expected(out,&expected);
        assert(as02_segmented_read_wqe_from_ib_send_wr(old,wr,1,1)==-EMSGSIZE);check_zero(old);positive++;
    }
    for(op=0;op<2;op++) {
        struct ib_send_wr *wr=op ? &rdma.wr:send;
        *wr=(struct ib_send_wr){.opcode=op ? IB_WR_RDMA_WRITE_WITH_IMM:IB_WR_SEND_WITH_IMM,.sg_list=&sg,.num_sge=1};
        sg=(struct ib_sge){.addr=~0ULL-8192,.length=8193,.lkey=8};
        if(op){rdma.remote_addr=~0ULL-8192;rdma.rkey=0xffffffffU;}
        assert(!as02_segmented_immediate_wqe_from_ib_send_wr(out,wr,1,1));other++;
        for(n=0;n<11;n++) {
            u64 sequence=1,epoch=1;int error;
            sg=(struct ib_sge){.addr=0x1000,.length=8193,.lkey=8};
            *wr=(struct ib_send_wr){.opcode=op ? IB_WR_RDMA_WRITE_WITH_IMM:IB_WR_SEND_WITH_IMM,.sg_list=&sg,.num_sge=1};
            if(op){rdma.remote_addr=0x2000;rdma.rkey=0x81234567;}
            switch(n) {
            case 0:sg.length=1048577;error=-EMSGSIZE;break;
            case 1:wr->send_flags=0x80000000U;error=-EOPNOTSUPP;break;
            case 2:wr->num_sge=2;error=-EOPNOTSUPP;break;
            case 3:wr->num_sge=-1;error=-EOPNOTSUPP;break;
            case 4:wr->sg_list=NULL;error=-EOPNOTSUPP;break;
            case 5:sequence=0;error=-EINVAL;break;
            case 6:epoch=0;error=-EINVAL;break;
            case 7:sg.addr=~0ULL;error=-EFAULT;break;
            case 8:if(op)rdma.remote_addr=~0ULL;else sg.addr=~0ULL;error=-EFAULT;break;
            default:error=-EINVAL;break;
            }
            memset(out,0xa5,sizeof(out));
            assert(as02_segmented_immediate_wqe_from_ib_send_wr(n==10 ? NULL:out,n==9 ? NULL:wr,sequence,epoch)==error);
            if(n!=10)check_zero(out);
            negative++;
        }
    }
    sg=(struct ib_sge){.addr=0x1000,.lkey=8};
    for(op=0;op<5;op++)for(n=0;n<4;n++) {
        struct ib_send_wr *wr=(op==0 || op==3) ? send:&rdma.wr;
        if(op>=3 && n==3)continue; /* only the new >4KiB Immediate policy differs */
        sg.length=n==0 ? 0:n==1 ? 65:n==2 ? 4096:8193;
        *wr=(struct ib_send_wr){.opcode=op==0 ? IB_WR_SEND:op==1 ? IB_WR_RDMA_WRITE:op==2 ? IB_WR_RDMA_READ:
            op==3 ? IB_WR_SEND_WITH_IMM:IB_WR_RDMA_WRITE_WITH_IMM,.sg_list=&sg,.num_sge=1};
        wr->ex.imm_data=cpu_to_be32(0x89abcdefU);
        if(wr==&rdma.wr){rdma.remote_addr=0x2000;rdma.rkey=0x81234567;}
        assert(!as02_segmented_immediate_wqe_from_ib_send_wr(out,wr,1,1));
        assert(!as02_segmented_read_wqe_from_ib_send_wr(old,wr,1,1));assert(!memcmp(out,old,128));other++;
    }
    sg.length=8;
    for(n=0;n<2;n++) {
        atomic=(struct ib_atomic_wr){.wr={.opcode=n ? IB_WR_ATOMIC_FETCH_AND_ADD:IB_WR_ATOMIC_CMP_AND_SWP,
            .sg_list=&sg,.num_sge=1},.remote_addr=0x2000,.rkey=0x81234567,.compare_add=0x8000000000000001ULL,.swap=~0ULL};
        assert(!as02_segmented_immediate_wqe_from_ib_send_wr(out,&atomic.wr,1,1));
        assert(!as02_segmented_read_wqe_from_ib_send_wr(old,&atomic.wr,1,1));assert(!memcmp(out,old,128));other++;
    }
    free(send);assert(positive==48 && other==22 && negative==22);
    printf("SEGMENTED_IMMEDIATE_VERBS_ADAPTER {\"pass_test\":true,\"large_Immediate_cases\":%u,\"other_positive_cases\":%u,\"negative_cases\":%u,\"base_SEND_WITH_IMM_ASan_guarded\":true,\"old_adapters_unchanged\":true,\"actual_posting\":false}\n",positive,other,negative);
    return 0;
}
