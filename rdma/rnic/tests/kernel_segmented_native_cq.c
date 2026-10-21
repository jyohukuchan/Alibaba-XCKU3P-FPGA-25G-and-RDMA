/* SPDX-License-Identifier: BSD-2-Clause-Views */
/* Real matched C callbacks consume UNEDITED8191 native SQ/CQ snapshots.
 * Linux/pins/coherent DMA/MMIO/peer/teardown remain separate models, not a
 * live kernel/RTL connection or proof that the modeled page tables match. */
#define AS02_VERBS_MAIN legacy_verbs_main
#include "kernel_verbs_cases.c"
static struct ib_mr *volatile quarantined_mr;

static void read_segmented_event(const char *path)
{
    FILE *f=fopen(path,"r");u32 words[35],extra;unsigned int i;
    CHECK(f);
    for(i=0;i<35;i++)CHECK(fscanf(f,"%x",words+i)==1);
    CHECK(fscanf(f,"%x",&extra)!=1);fclose(f);
    CHECK(words[28]==31 && words[29]==748 && words[30]==0xa0);
    memset(&event,0,sizeof(event));event.sequence=words[0];event.proofs=words[1];event.status=words[2];
    event.cookie=words[3]|((u64)words[4]<<32);memcpy(event.context,words+5,sizeof(event.context));
    event.context_extension=words[24];event.received_bytes=words[25];
    event.notification_flags=words[26];event.notification=words[27];
    event.compare=words[31]|((u64)words[32]<<32);event.swap_add=words[33]|((u64)words[34]<<32);
}
static void compare_segmented_record(const char *path)
{
    FILE *f=fopen(path,"r");char text[257];u8 expected[128],encoded[128];unsigned int i,value;
    CHECK(f && fscanf(f,"%256s",text)==1);fclose(f);CHECK(strlen(text)==256);
    for(i=0;i<128;i++){CHECK(sscanf(text+(127-i)*2,"%2x",&value)==1);expected[i]=value;}
    CHECK(model.observed_count==1 && km.dma_allocs==2 && km.dma[0].bytes==256);
    CHECK(!as02_segmented_wqe_encode(encoded,&model.observed_atomic[0]));
    CHECK(!memcmp(expected,encoded,128) && !memcmp(expected,km.dma[0].address,128));
}
int main(int argc,char **argv)
{
    struct ib_mr *m;struct as02_verbs_mr *owned;struct ib_sge sg;
    struct ib_atomic_wr a={};struct ib_rdma_wr r={};struct ib_send_wr send={};
    const struct ib_send_wr *wr,*bad=NULL;struct ib_wc wc;
    unsigned int op,length,mutation,ib_opcode,wc_opcode,refs;
    bool zero;
    CHECK(argc==6);op=strtoul(argv[3],NULL,0);length=strtoul(argv[4],NULL,0);mutation=strtoul(argv[5],NULL,0);
    CHECK((op==1 || op==2 || op==3 || op==5 || op==6 || op==7 || op==8) && mutation<5);
    CHECK(length==0 || length==8 || length==65 || length==8193);
    zero=!length;refs=zero ? 1:2;
    qp_tx_feature=retry_feature=send_feature=recv_feature=rnr_feature=recv_retire_feature=true;
    message_cq_feature=request_cq_feature=independent_queues_feature=immediate_feature=atomic_feature=true;
    atomic_access_feature=zero_feature=segmented_feature=true;
    setup_verbs();CHECK(sq.profile_bound && sq.wqe_profile==4 && sq.zero_length_enabled && pd.number==17);
    m=verbs->reg_user_mr(&pd.ibpd,0x10003,length==8193 ? 8721:8192,VA,7,NULL,NULL);
    CHECK(!IS_ERR(m));owned=container_of(m,struct as02_verbs_mr,ibmr);
    create_objects();activate();
    CHECK(qp.owner.qpn==2 && qp.owner.pd==17 && qp.owner.epoch==EPOCH && qp.owner.cookie==0xfedcba9889abcdefULL);
    sg=(struct ib_sge){.addr=VA+0x210,.length=length,.lkey=m->lkey};
    ib_opcode=op==1 ? IB_WR_RDMA_WRITE:op==2 ? IB_WR_RDMA_READ:op==3 ? IB_WR_SEND:
        op==5 ? IB_WR_SEND_WITH_IMM:op==6 ? IB_WR_RDMA_WRITE_WITH_IMM:
        op==7 ? IB_WR_ATOMIC_CMP_AND_SWP:IB_WR_ATOMIC_FETCH_AND_ADD;
    wc_opcode=op==7 ? IB_WC_COMP_SWAP:op==8 ? IB_WC_FETCH_ADD:op==2 ? IB_WC_RDMA_READ:
        op==3 || op==5 ? IB_WC_SEND:IB_WC_RDMA_WRITE;
    send=(struct ib_send_wr){.wr_id=0xf123456789abc001ULL,.sg_list=zero ? (void *)1:&sg,
        .num_sge=zero ? 0:1,.opcode=ib_opcode,.send_flags=IB_SEND_SIGNALED};
    if(op==5 || op==6)send.ex.imm_data=cpu_to_be32(0x89abcdef);
    if(op==7 || op==8){
        a=(struct ib_atomic_wr){.wr=send,.remote_addr=0xf123456789abc008ULL,.rkey=0x81234567,
            .compare_add=op==7 ? 0xfedcba9876543210ULL:0x8123456789abcdefULL,.swap=0x8123456789abcdefULL};
        wr=&a.wr;
    }else if(op==1 || op==2 || op==6){
        r=(struct ib_rdma_wr){.wr=send,.remote_addr=zero ? ~0ULL:0xf123456789abc001ULL,
            .rkey=zero ? 0xfedcba98:0};wr=&r.wr;
    }else wr=&send;
    CHECK(!verbs->post_send(&qp.ibqp,wr,&bad) && !bad && refcount_read(&owned->mapping->work_refs)==refs);
    compare_segmented_record(argv[2]);read_segmented_event(argv[1]);
    /* These are explicitly labeled in-memory mutations, NEVER edits to the
     * actual native snapshot or synthetic replacements for its positive CQ. */
    if(mutation==1)event.swap_add^=1ULL<<63;
    if(mutation==2)event.context_extension|=0x1000;
    if(mutation==3)event.context[276/32]^=1U<<(276%32);
    if(mutation==4)event.context[116/32]^=1U<<(116%32);
    event_visible=true;
    if(mutation){
        CHECK(as02_cq_hw_poll(&cqh)==-EIO && event_visible && !acknowledged && !cq.pending &&
            !cqh.control.pending_ack && refcount_read(&owned->mapping->work_refs)==refs && !km.dma_frees);
        quarantined_mr=m;
        printf("KERNEL_SEGMENTED_NATIVE_CQ {\"pass_test\":true,\"opcode\":%u,\"bytes\":%u,\"mutation\":%u,\"owners_intentionally_retained\":true,\"hardware_verified\":false}\n",op,length,mutation);
        return 0;
    }
    CHECK(verbs->poll_cq(&cq.ibcq,1,&wc)==1 && wc.wr_id==wr->wr_id && wc.qp==&qp.ibqp &&
        wc.status==IB_WC_SUCCESS && wc.opcode==wc_opcode && wc.byte_len==(op==2 || op==7 || op==8 ? length:0) &&
        !wc.wc_flags && !wc.ex.imm_data);
    CHECK(!event_visible && acknowledged==1 && refcount_read(&owned->mapping->work_refs)==1);
    CHECK(!verbs->poll_cq(&cq.ibcq,1,&wc));cleanup_verbs(m);
    printf("KERNEL_SEGMENTED_NATIVE_CQ {\"pass_test\":true,\"opcode\":%u,\"bytes\":%u,\"mutation\":0,\"native_RTL_CQ_unedited\":true,\"full128_kernel_native_record_identical\":true,\"actual_standard_C_callbacks_CQ_MR_release\":true,\"profile4_CQC31\":true,\"Linux_Hardware_boundaries_modeled\":true}\n",op,length);
    return 0;
}
