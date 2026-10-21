/* SPDX-License-Identifier: BSD-2-Clause-Views */
/* Actual adapters/codecs; Linux WR objects are explicit boundary models. */
#include "segmented_immediate_adapter_prior.c"
#include "verbs_segmented_receive_wqe.h"

int main(void)
{
    const u32 lengths[]={4097,8192,8193,1048576};
    const u32 keys[]={0,0x81234567U,0xffffffffU};
    struct ib_recv_wr *wr=malloc(sizeof(*wr));
    struct ib_sge sg={};
    struct as02_atomic_wqe expected={};
    unsigned char out[128],old[128];
    unsigned int n,k,positive=0,other=0,negative=0;
    assert(wr);assert(!preceding_immediate_adapter_main());
    for(n=0;n<4;n++)for(k=0;k<3;k++) {
        sg=(struct ib_sge){.addr=0xfedcba9876543210ULL,.length=lengths[n],.lkey=keys[k]};
        *wr=(struct ib_recv_wr){.wr_id=0xf123456789abc001ULL,.sg_list=&sg,.num_sge=1};
        expected.base=(struct as02_wqe){.wr_id=wr->wr_id,.sequence=0xfedcba9876543210ULL,
            .epoch=0x9123456700000001ULL,.local_address=sg.addr,.local_key=sg.lkey,
            .length=sg.length,.opcode=AS02_WQE_RECV,.flags=AS02_WQE_SIGNALED};
        assert(!as02_segmented_receive_wqe_from_ib_recv_wr(out,wr,expected.base.sequence,expected.base.epoch));
        compare_expected(out,&expected);
        assert(as02_zero_wqe_from_ib_recv_wr(old,wr,1,1)==-EMSGSIZE);check_zero(old);positive++;
    }
    for(n=0;n<3;n++) {
        sg=(struct ib_sge){.addr=~0ULL,.lkey=0xffffffffU,.length=n==0 ? 0:n==1 ? 65:4096};
        if(n)sg.addr=0x1000;
        *wr=(struct ib_recv_wr){.sg_list=&sg,.num_sge=1};
        assert(!as02_segmented_receive_wqe_from_ib_recv_wr(out,wr,1,1));
        assert(!as02_zero_wqe_from_ib_recv_wr(old,wr,1,1));assert(!memcmp(out,old,128));other++;
    }
    /* No SGE means the invalid unused pointer must never be dereferenced. */
    *wr=(struct ib_recv_wr){.sg_list=(void *)1,.num_sge=0};
    assert(!as02_segmented_receive_wqe_from_ib_recv_wr(out,wr,1,1));
    assert(!as02_zero_wqe_from_ib_recv_wr(old,wr,1,1));assert(!memcmp(out,old,128));other++;
    sg=(struct ib_sge){.addr=~0ULL-8192,.length=8193,.lkey=8};
    *wr=(struct ib_recv_wr){.sg_list=&sg,.num_sge=1};
    assert(!as02_segmented_receive_wqe_from_ib_recv_wr(out,wr,1,1));other++;
    for(n=0;n<9;n++) {
        u64 sequence=1,epoch=1;int error;
        sg=(struct ib_sge){.addr=0x1000,.length=8193,.lkey=8};
        *wr=(struct ib_recv_wr){.sg_list=&sg,.num_sge=1};
        switch(n) {
        case 0:sg.length=1048577;error=-EMSGSIZE;break;
        case 1:sg.addr=~0ULL;error=-EFAULT;break;
        case 2:sequence=0;error=-EINVAL;break;
        case 3:epoch=0;error=-EINVAL;break;
        case 4:wr->num_sge=2;error=-EOPNOTSUPP;break;
        case 5:wr->num_sge=-1;error=-EOPNOTSUPP;break;
        case 6:wr->sg_list=NULL;error=-EOPNOTSUPP;break;
        default:error=-EINVAL;break;
        }
        memset(out,0xa5,sizeof(out));
        assert(as02_segmented_receive_wqe_from_ib_recv_wr(n==8 ? NULL:out,n==7 ? NULL:wr,sequence,epoch)==error);
        if(n!=8)check_zero(out);
        negative++;
    }
    free(wr);assert(positive==12 && other==5 && negative==9);
    printf("SEGMENTED_RECEIVE_VERBS_ADAPTER {\"pass_test\":true,\"large_RECV_cases\":%u,\"other_positive_cases\":%u,\"negative_cases\":%u,\"base_RECV_ASan_guarded\":true,\"zero_unused_SGE_not_read\":true,\"actual_posting\":false}\n",positive,other,negative);
    return 0;
}
