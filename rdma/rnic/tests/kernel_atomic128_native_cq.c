/* SPDX-License-Identifier: BSD-2-Clause-Views */
/* Actual matched standard callbacks consume unedited096 native RTL events.
 * Linux/pins/coherent DMA/MMIO/peer/teardown stay modeled, not live hardware. */
#define AS02_VERBS_MAIN legacy_verbs_main
#include "kernel_verbs_cases.c"
static struct ib_mr *volatile quarantined_mr;

static void read_native_event(const char *path)
{
    FILE *f=fopen(path,"r");u32 words[35],extra;unsigned int i;
    CHECK(f);
    for(i=0;i<35;i++)CHECK(fscanf(f,"%x",words+i)==1);
    CHECK(fscanf(f,"%x",&extra)!=1);fclose(f);
    CHECK(words[28]==15 && words[29]==748 && words[30]==0xa0);
    memset(&event,0,sizeof(event));event.sequence=words[0];event.proofs=words[1];event.status=words[2];
    event.cookie=words[3]|((u64)words[4]<<32);memcpy(event.context,words+5,sizeof(event.context));
    event.context_extension=words[24];event.received_bytes=words[25];
    event.notification_flags=words[26];event.notification=words[27];
    event.compare=words[31]|((u64)words[32]<<32);event.swap_add=words[33]|((u64)words[34]<<32);
}
static void compare_native_record(const char *path)
{
    FILE *f=fopen(path,"r");char text[257];u8 expected[128],encoded[128];unsigned int i,value;
    CHECK(f && fscanf(f,"%256s",text)==1);fclose(f);CHECK(strlen(text)==256);
    for(i=0;i<128;i++){CHECK(sscanf(text+(127-i)*2,"%2x",&value)==1);expected[i]=value;}
    CHECK(model.observed_count==1 && km.dma_allocs==2 && km.dma[0].bytes==256);
    CHECK(!as02_atomic_wqe_encode(encoded,&model.observed_atomic[0]));
    CHECK(!memcmp(expected,encoded,128) && !memcmp(expected,km.dma[0].address,128));
}
int main(int argc,char **argv)
{
    struct ib_mr *m;struct as02_verbs_mr *owned;struct ib_sge sg;
    struct ib_atomic_wr a={};struct ib_rdma_wr r={};struct ib_send_wr send={};
    const struct ib_send_wr *wr,*bad=NULL;struct ib_wc wc;
    unsigned int op,mutation,ib_opcode,wc_opcode;
    CHECK(argc==5);op=strtoul(argv[3],NULL,0);mutation=strtoul(argv[4],NULL,0);
    CHECK((op==7 || op==8 || op==2 || op==5) && mutation<3);
    qp_tx_feature=retry_feature=send_feature=recv_feature=rnr_feature=recv_retire_feature=true;
    message_cq_feature=request_cq_feature=independent_queues_feature=immediate_feature=atomic_feature=true;
    setup_verbs();CHECK(sq.profile_bound && sq.wqe_profile==3 && pd.number==17);
    m=register_mr();CHECK(!IS_ERR(m));owned=container_of(m,struct as02_verbs_mr,ibmr);
    create_objects();activate();
    CHECK(qp.owner.qpn==2 && qp.owner.pd==17 && qp.owner.epoch==EPOCH && qp.owner.cookie==0xfedcba9889abcdefULL);
    sg=(struct ib_sge){.addr=VA+0x210,.length=op==7 || op==8 ? 8:65,.lkey=m->lkey};
    ib_opcode=op==7 ? IB_WR_ATOMIC_CMP_AND_SWP:IB_WR_ATOMIC_FETCH_AND_ADD;
    wc_opcode=op==7 ? IB_WC_COMP_SWAP:op==8 ? IB_WC_FETCH_ADD:op==2 ? IB_WC_RDMA_READ:IB_WC_SEND;
    send=(struct ib_send_wr){.wr_id=0xf123456789abc001ULL,.sg_list=&sg,.num_sge=1,
        .opcode=IB_WR_SEND_WITH_IMM,.ex.imm_data=cpu_to_be32(0x89abcdef)};
    if(op==7 || op==8){
        a=(struct ib_atomic_wr){.wr=send,.remote_addr=0xf123456789abc008ULL,.rkey=0x81234567,
            .compare_add=op==7 ? 0xfedcba9876543210ULL:0x8123456789abcdefULL,.swap=0x8123456789abcdefULL};
        a.wr.opcode=ib_opcode;a.wr.ex.imm_data=0;wr=&a.wr;
    }else if(op==2){
        r=(struct ib_rdma_wr){.wr=send,.remote_addr=0xf123456789abc001ULL,.rkey=0};
        r.wr.opcode=IB_WR_RDMA_READ;r.wr.ex.imm_data=0;wr=&r.wr;
    }else wr=&send;
    CHECK(!verbs->post_send(&qp.ibqp,wr,&bad) && !bad && refcount_read(&owned->mapping->work_refs)==2);
    compare_native_record(argv[2]);read_native_event(argv[1]);
    if(mutation==1)event.swap_add^=1ULL<<63;
    if(mutation==2)event.context_extension|=0x1000;
    event_visible=true; /* Exact real RTL snapshot, not a fabricated success. */
    if(mutation){
        CHECK(as02_cq_hw_poll(&cqh)==-EIO && event_visible && !acknowledged && !cq.pending &&
            !cqh.control.pending_ack && refcount_read(&owned->mapping->work_refs)==2 && !km.dma_frees);
        quarantined_mr=m;CHECK(quarantined_mr==m);
        printf("KERNEL_ATOMIC128_NATIVE_CQ {\"pass_test\":true,\"opcode\":%u,\"mutation\":%u,\"owners_intentionally_retained\":true,\"hardware_verified\":false}\n",op,mutation);
        return 0;
    }
    CHECK(verbs->poll_cq(&cq.ibcq,1,&wc)==1 && wc.wr_id==wr->wr_id && wc.qp==&qp.ibqp &&
        wc.status==IB_WC_SUCCESS && wc.opcode==wc_opcode && wc.byte_len==(op==5 ? 0:sg.length) &&
        !wc.wc_flags && !wc.ex.imm_data);
    CHECK(!event_visible && acknowledged==1 && refcount_read(&owned->mapping->work_refs)==1);
    CHECK(!verbs->poll_cq(&cq.ibcq,1,&wc));
    cleanup_verbs(m);
    printf("KERNEL_ATOMIC128_NATIVE_CQ {\"pass_test\":true,\"opcode\":%u,\"mutation\":0,\"native_RTL_CQ_unedited\":true,\"full128_kernel_native_record_identical\":true,\"actual_standard_C_callbacks_CQ_MR_release\":true,\"Linux_Hardware_boundaries_modeled\":true}\n",op);
    return 0;
}

