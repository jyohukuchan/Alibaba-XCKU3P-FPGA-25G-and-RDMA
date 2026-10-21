/* SPDX-License-Identifier: BSD-2-Clause-Views */
/* Consume UNEDITED native33-word receive CQ snapshots; Linux/MMIO/pins/
 * coherent DMA/teardown remain separate models, not live Linux/RTL coupling. */
#include "kernel_segmented_send_native_cq.c"

static void read_receive_event(const char *path)
{
    FILE *f=fopen(path,"r");u32 words[33],extra;unsigned int i;
    CHECK(f);for(i=0;i<33;i++)CHECK(fscanf(f,"%x",words+i)==1);
    CHECK(fscanf(f,"%x",&extra)!=1);fclose(f);
    CHECK(words[28]==255 && !words[29] && !words[30] && !words[31] && !words[32]);
    memset(&event,0,sizeof(event));event.sequence=words[0];event.proofs=words[1];event.status=words[2];
    event.cookie=words[3]|((u64)words[4]<<32);memcpy(event.context,words+5,sizeof(event.context));
    event.context_extension=words[24];event.received_bytes=words[25];
    event.notification_flags=words[26];event.notification=words[27];
    /* This native snapshot does NOT contain owner-geometry registers. The
     * separately identified CSR model still returns its explicit geometry. */
}
static void compare_receive_record(const char *path)
{
    FILE *f=fopen(path,"r");char text[257];u8 expected[128];unsigned int i,value;
    CHECK(f && fscanf(f,"%256s",text)==1);fclose(f);CHECK(strlen(text)==256);
    for(i=0;i<128;i++){CHECK(sscanf(text+(127-i)*2,"%2x",&value)==1);expected[i]=value;}
    CHECK(receive_model.observed_count==1 && !model.observed_count && km.dma_allocs==2 && km.dma[1].bytes==256);
    CHECK(!memcmp(expected,km.dma[1].address,128));
}
int main(int argc,char **argv)
{
    struct ib_mr *m;struct as02_verbs_mr *owned;struct ib_sge sg;struct ib_recv_wr wr;
    const struct ib_recv_wr *bad=NULL;struct ib_wc wc;
    unsigned int op,length,mutation;u32 notification;
    CHECK(argc==7);op=strtoul(argv[3],NULL,0);
    if(op!=4)return send_native_main(6,argv);
    length=strtoul(argv[4],NULL,0);mutation=strtoul(argv[5],NULL,0);notification=strtoul(argv[6],NULL,0);
    CHECK(length==8194 && mutation<5 && (notification==0 || notification==0x89abcdefU));
    qp_tx_feature=retry_feature=send_feature=recv_feature=rnr_feature=recv_retire_feature=true;
    message_cq_feature=request_cq_feature=independent_queues_feature=immediate_feature=atomic_feature=true;
    atomic_access_feature=zero_feature=segmented_receive_feature=true;
    setup_verbs();CHECK(sq.profile_bound && sq.wqe_profile==7 && sq.zero_length_enabled && pd.number==17);
    m=verbs->reg_user_mr(&pd.ibpd,0x10003,8722,VA,7,NULL,NULL);
    CHECK(!IS_ERR(m));owned=container_of(m,struct as02_verbs_mr,ibmr);
    create_objects();activate();
    CHECK(qp.owner.qpn==2 && qp.owner.pd==17 && qp.owner.epoch==EPOCH && qp.owner.cookie==0xfedcba9889abcdefULL);
    sg=(struct ib_sge){.addr=VA+0x210,.length=length,.lkey=m->lkey};
    wr=(struct ib_recv_wr){.wr_id=0xf123456789abc001ULL,.sg_list=&sg,.num_sge=1};
    CHECK(!verbs->post_recv(&qp.ibqp,&wr,&bad) && !bad && refcount_read(&owned->mapping->work_refs)==2);
    compare_receive_record(argv[2]);read_receive_event(argv[1]);
    CHECK(event.cookie==pair(receive_model.reply+6) && event.cookie==0xfedcba9889abcdf0ULL);
    if(mutation==1)event.swap_add^=1ULL<<63;
    if(mutation==2)event.context_extension|=0x1000;
    if(mutation==3)event.context[276/32]^=1U<<(276%32);
    if(mutation==4)event.context[116/32]^=1U<<(116%32);
    event_visible=true;
    if(mutation){
        CHECK(as02_cq_hw_poll(&cqh)==-EIO && event_visible && !acknowledged && !recv_cq.pending && !cq.pending &&
            !cqh.control.pending_ack && refcount_read(&owned->mapping->work_refs)==2 && !km.dma_frees);
        quarantined_mr=m;
        printf("KERNEL_SEGMENTED_NATIVE_CQ {\"pass_test\":true,\"opcode\":4,\"bytes\":8193,\"mutation\":%u,\"owners_intentionally_retained\":true,\"hardware_verified\":false}\n",mutation);
        return 0;
    }
    CHECK(verbs->poll_cq(&recv_cq.ibcq,1,&wc)==1 && wc.wr_id==wr.wr_id && wc.qp==&qp.ibqp &&
        wc.status==IB_WC_SUCCESS && wc.opcode==IB_WC_RECV && wc.byte_len==8193 &&
        wc.wc_flags==(notification ? IB_WC_WITH_IMM:0) && be32_to_cpu(wc.ex.imm_data)==notification);
    CHECK(!event_visible && acknowledged==1 && refcount_read(&owned->mapping->work_refs)==1 && !cq.pending);
    CHECK(!verbs->poll_cq(&recv_cq.ibcq,1,&wc));cleanup_verbs(m);
    puts("KERNEL_SEGMENTED_NATIVE_CQ {\"pass_test\":true,\"opcode\":4,\"bytes\":8193,\"capacity\":8194,\"mutation\":0,\"native_RTL_CQ_unedited\":true,\"full128_kernel_native_record_identical\":true,\"actual_standard_C_callbacks_CQ_MR_release\":true,\"profile7_CQC255\":true,\"Linux_Hardware_boundaries_modeled\":true}");
    return 0;
}
