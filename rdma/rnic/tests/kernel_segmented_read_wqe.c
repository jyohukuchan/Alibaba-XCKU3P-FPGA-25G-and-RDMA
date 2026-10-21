/* SPDX-License-Identifier: BSD-2-Clause-Views */
/* Real new Linux-WR adapter/codecs; WR types are explicit boundary models. */
#define main old_segmented_adapter_main
#include "kernel_segmented_wqe.c"
#undef main
#include "verbs_segmented_read_wqe.h"

int main(void)
{
    const u32 lengths[]={4097,8193,65537,1048576},keys[]={0,0x80000008U,0xffffffffU};
    struct ib_sge sg={.addr=0xfedcba9876543210ULL};
    struct ib_rdma_wr wr={};
    struct ib_atomic_wr atomic={};
    struct ib_send_wr *send=malloc(sizeof(*send));
    struct as02_atomic_wqe expected={};
    unsigned char out[128],old[128];
    unsigned int n,k,flag,read_cases=0,other=0,negative=0;
    assert(send);assert(!old_segmented_adapter_main());
    for(n=0;n<4;n++)for(k=0;k<3;k++)for(flag=0;flag<2;flag++) {
        sg.length=lengths[n];sg.lkey=keys[k];
        wr=(struct ib_rdma_wr){.wr={.wr_id=0xf123456789abc001ULL,.opcode=IB_WR_RDMA_READ,
            .num_sge=1,.sg_list=&sg,.send_flags=flag ? IB_SEND_SIGNALED:0},
            .remote_addr=0xe23456789abcdef0ULL,.rkey=keys[2-k]};
        expected.base=(struct as02_wqe){.wr_id=wr.wr.wr_id,.sequence=0xfedcba9876543210ULL,
            .epoch=0x9123456700000001ULL,.local_address=sg.addr,.local_key=sg.lkey,
            .length=sg.length,.remote_address=wr.remote_addr,.remote_key=wr.rkey,
            .opcode=AS02_WQE_READ,.flags=flag ? AS02_WQE_SIGNALED:0};
        assert(!as02_segmented_read_wqe_from_ib_send_wr(out,&wr.wr,expected.base.sequence,expected.base.epoch));
        compare_expected(out,&expected);
        assert(as02_segmented_wqe_from_ib_send_wr(old,&wr.wr,1,1)==-EMSGSIZE);check_zero(old);
        read_cases++;
    }
    for(n=0;n<4;n++) {
        sg.length=8193;sg.addr=n<2 ? ~0ULL-8192+(n&1):0x1000;
        wr.remote_addr=n>=2 ? ~0ULL-8192+(n&1):0x2000;
        assert(as02_segmented_read_wqe_from_ib_send_wr(out,&wr.wr,1,1)==((n&1) ? -EFAULT:0));
        if(n&1){check_zero(out);negative++;}else other++;
    }
    for(n=0;n<12;n++) {
        u64 sequence=1,epoch=1;int error;
        sg=(struct ib_sge){.addr=0x1000,.length=8193,.lkey=8};
        wr=(struct ib_rdma_wr){.wr={.opcode=IB_WR_RDMA_READ,.sg_list=&sg,.num_sge=1},
            .remote_addr=0x2000,.rkey=0x81234567};
        switch(n) {
        case 0:sg.length=1048577;error=-EMSGSIZE;break;
        case 1:wr.wr.send_flags=0x80000000U;error=-EOPNOTSUPP;break;
        case 2:wr.wr.num_sge=2;error=-EOPNOTSUPP;break;
        case 3:wr.wr.num_sge=-1;error=-EOPNOTSUPP;break;
        case 4:wr.wr.sg_list=NULL;error=-EOPNOTSUPP;break;
        case 5:sequence=0;error=-EINVAL;break;
        case 6:epoch=0;error=-EINVAL;break;
        case 7:wr.remote_addr=~0ULL;error=-EFAULT;break;
        case 8:sg.addr=~0ULL;error=-EFAULT;break;
        case 9:error=-EINVAL;break;
        case 10:error=-EINVAL;break;
        default:wr.wr.opcode=IB_WR_RDMA_WRITE_WITH_IMM;error=-EMSGSIZE;break;
        }
        memset(out,0xa5,sizeof(out));
        assert(as02_segmented_read_wqe_from_ib_send_wr(n==10 ? NULL:out,n==9 ? NULL:&wr.wr,sequence,epoch)==error);
        if(n!=10)check_zero(out);
        negative++;
    }
    /* Base-only SEND allocation remains ASan guarded through the NEW entry
     * point; old WRITE/SEND/short/zero READ and Atomic bytes must not change. */
    sg=(struct ib_sge){.addr=0x1000,.lkey=8};
    for(n=0;n<4;n++) {
        sg.length=n==0 ? 0:n==1 ? 65:n==2 ? 4096:8193;
        *send=(struct ib_send_wr){.opcode=IB_WR_SEND,.sg_list=&sg,.num_sge=1};
        assert(!as02_segmented_read_wqe_from_ib_send_wr(out,send,1,1));
        assert(!as02_segmented_wqe_from_ib_send_wr(old,send,1,1));assert(!memcmp(out,old,128));other++;
        wr=(struct ib_rdma_wr){.wr=*send,.remote_addr=0x2000,.rkey=0x81234567};wr.wr.opcode=IB_WR_RDMA_WRITE;
        assert(!as02_segmented_read_wqe_from_ib_send_wr(out,&wr.wr,1,1));
        assert(!as02_segmented_wqe_from_ib_send_wr(old,&wr.wr,1,1));assert(!memcmp(out,old,128));other++;
        if(n<3) {
            wr.wr.opcode=IB_WR_RDMA_READ;
            assert(!as02_segmented_read_wqe_from_ib_send_wr(out,&wr.wr,1,1));
            assert(!as02_segmented_wqe_from_ib_send_wr(old,&wr.wr,1,1));assert(!memcmp(out,old,128));other++;
        }
    }
    sg.length=8;
    for(n=0;n<2;n++) {
        atomic=(struct ib_atomic_wr){.wr={.opcode=n ? IB_WR_ATOMIC_FETCH_AND_ADD:IB_WR_ATOMIC_CMP_AND_SWP,
            .sg_list=&sg,.num_sge=1},.remote_addr=0x2000,.rkey=0x81234567,
            .compare_add=0x8000000000000001ULL,.swap=0xffffffffffffffffULL};
        assert(!as02_segmented_read_wqe_from_ib_send_wr(out,&atomic.wr,1,1));
        assert(!as02_segmented_wqe_from_ib_send_wr(old,&atomic.wr,1,1));assert(!memcmp(out,old,128));other++;
    }
    free(send);assert(read_cases==24 && other==15 && negative==14);
    printf("SEGMENTED_READ_VERBS_ADAPTER {\"pass_test\":true,\"large_READ_cases\":%u,\"other_positive_cases\":%u,\"negative_cases\":%u,\"base_SEND_ASan_guarded\":true,\"old_adapter_unchanged\":true,\"actual_posting\":false}\n",read_cases,other,negative);
    return 0;
}
