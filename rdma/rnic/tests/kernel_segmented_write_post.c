/* SPDX-License-Identifier: BSD-2-Clause-Views */
/* Real standard callbacks/ref/replay/CQ code; explicit Linux/HW models only. */
#include "kernel_segmented_receive_post.c"

int main(int argc,char **argv)
{
    struct ib_mr *m;struct as02_verbs_mr *owned;struct ib_sge sg;
    struct ib_recv_wr wr={},tail={};const struct ib_recv_wr *bad=NULL;struct ib_wc wc[3];
    unsigned int n,capacity,bytes,i,refs;u32 notification;
    if(argc>=3 && !strcmp(argv[1],"prior"))return segmented_receive_post_main(argc-1,argv+1);
    CHECK(argc==2);n=strtoul(argv[1],NULL,0);CHECK(n<32);
    qp_tx_feature=retry_feature=send_feature=recv_feature=rnr_feature=recv_retire_feature=true;
    message_cq_feature=request_cq_feature=independent_queues_feature=immediate_feature=true;
    atomic_feature=atomic_access_feature=zero_feature=true;
    segmented_write_feature=n!=2 && n!=3 && n!=14;segmented_receive_feature=n==2 || n==3 || n==14;
    if(n<4)segmented_write_bad_tuple=n+1;
    if(n>=4 && n<=7)atomic_bad_geometry=n-3;
    setup_verbs();
    if(segmented_write_bad_tuple || atomic_bad_geometry){
        rejected_profile_cleanup();
        printf("KERNEL_SEGMENTED_WRITE_POST {\"pass_test\":true,\"case\":%u,\"rejected_before_queues\":true}\n",n);return 0;
    }
    CHECK(sq.profile_bound && sq.wqe_profile==(segmented_write_feature ? 8:7) && sq.zero_length_enabled);
    capacity=n==12 || n==13 || n==26 || n==27 ? 128:0;
    bytes=n==8 ? 0:n==9 ? 1:n==10 ? 4096:n==11 || n==14 ? 4097:n==15 ? 1048576:8193;
    notification=n==9 ? 0:n==10 ? 0xffffffffU:0x89abcdefU;
    m=verbs->reg_user_mr(&pd.ibpd,0x10003,4096,VA,7,NULL,NULL);
    CHECK(!IS_ERR(m));owned=container_of(m,struct as02_verbs_mr,ibmr);
    create_objects();activate();refs=capacity ? 2:1;
    sg=(struct ib_sge){.addr=VA+0x210,.length=capacity,.lkey=m->lkey};
    wr=(struct ib_recv_wr){.wr_id=0xf123456789abc001ULL,.sg_list=capacity ? &sg:(void *)1,.num_sge=capacity ? 1:0};
    if(n==28)wr.num_sge=2;
    if(n==29){wr.num_sge=1;wr.sg_list=NULL;}
    if(n==28 || n==29){
        CHECK(verbs->post_recv(&qp.ibqp,&wr,&bad)<0 && bad==&wr && !receive_model.producer &&
            !receive_model.observed_count && refcount_read(&owned->mapping->work_refs)==1);
        cleanup_verbs(m);printf("KERNEL_SEGMENTED_WRITE_POST {\"pass_test\":true,\"case\":%u,\"bad_WR_before_owner\":true}\n",n);return 0;
    }
    if(n==30){
        receive_model.drop_ack=true;
        CHECK(verbs->post_recv(&qp.ibqp,&wr,&bad)==-ETIMEDOUT && bad==&wr && receive_hw.control.pending && receive_hw.control.uncertain &&
            refcount_read(&owned->mapping->work_refs)==refs && !km.dma_frees);
        quarantined_mr=m;puts("KERNEL_SEGMENTED_WRITE_POST {\"pass_test\":true,\"ambiguous_RQ_owner_retained\":true}");return 0;
    }
    if(n==31){tail=wr;tail.wr_id++;tail.num_sge=1;tail.sg_list=NULL;wr.next=&tail;}
    if(n==31)CHECK(verbs->post_recv(&qp.ibqp,&wr,&bad)<0 && bad==&tail);
    else CHECK(!verbs->post_recv(&qp.ibqp,&wr,&bad) && !bad);
    CHECK(!model.observed_count && !model.producer && receive_model.observed_count==1 && receive_model.producer==1);
    receive_wqe_bytes(&wr,1,qp.owner.epoch);
    CHECK(receive_model.observed_atomic[0].base.length==capacity && refcount_read(&owned->mapping->work_refs)==refs && !km.dma_frees);
    receive_model_completion(0,bytes,3,notification);
    if(n>=16 && n<=25){
        if(n==16)event.context[276/32]^=1U<<(276%32);
        if(n==17)event.context[116/32]^=1U<<(116%32);
        if(n==18)event.cookie^=1ULL<<63;
        if(n==19)event.context[(396+63)/32]^=1U<<((396+63)%32);
        if(n==20)event.received_bytes=1048577;
        if(n==21)event.notification_flags=2;
        if(n==22)event.context_extension|=0x1000;
        if(n==23)event.swap_add^=1ULL<<63;
        if(n==24)event.proofs^=8;
        if(n==25)event.status=1;
    }
    if(n==14 || (n>=16 && n<=25)){
        CHECK(as02_cq_hw_poll(&cqh)==(n==18 || n==19 ? -ESTALE:-EIO) && event_visible && !acknowledged &&
            !recv_cq.pending && !cq.pending && refcount_read(&owned->mapping->work_refs)==refs && !km.dma_frees);
        quarantined_mr=m;printf("KERNEL_SEGMENTED_WRITE_POST {\"pass_test\":true,\"case\":%u,\"bad_owner_or_old_profile_retained\":true}\n",n);return 0;
    }
    if(n==26 || n==27){
        CHECK(as02_cq_hw_poll(&cqh)==1 && recv_cq.pending==1 && refcount_read(&owned->mapping->work_refs)==1);
        for(i=1;i<3;i++){
            wr.wr_id++;CHECK(!verbs->post_recv(&qp.ibqp,&wr,&bad));receive_wqe_bytes(&wr,i+1,qp.owner.epoch);
            receive_model_completion(i,bytes,3,notification);if(i==1)CHECK(as02_cq_hw_poll(&cqh)==1 && recv_cq.pending==2);
        }
        CHECK(as02_cq_hw_poll(&cqh)==-ENOSPC && event_visible && recv_cq.pending==2 && refcount_read(&owned->mapping->work_refs)==2);
        CHECK(verbs->poll_cq(&recv_cq.ibcq,1,wc)==1 && as02_cq_hw_poll(&cqh)==1 && !event_visible);
        CHECK(refcount_read(&owned->mapping->work_refs)==1 && verbs->poll_cq(&recv_cq.ibcq,3,wc)==2);
    }else{
        CHECK(verbs->poll_cq(&recv_cq.ibcq,1,wc)==1 && wc[0].wr_id==wr.wr_id && wc[0].qp==&qp.ibqp &&
            wc[0].status==IB_WC_SUCCESS && wc[0].opcode==IB_WC_RECV_RDMA_WITH_IMM && wc[0].byte_len==bytes &&
            wc[0].wc_flags==IB_WC_WITH_IMM && be32_to_cpu(wc[0].ex.imm_data)==notification);
        CHECK(!event_visible && acknowledged==1 && refcount_read(&owned->mapping->work_refs)==1 && !cq.pending && !km.dma_frees);
        CHECK(!verbs->poll_cq(&recv_cq.ibcq,1,wc));
    }
    cleanup_verbs(m);
    printf("KERNEL_SEGMENTED_WRITE_POST {\"pass_test\":true,\"case\":%u,\"capacity\":%u,\"WRITE_bytes\":%u,\"actual_standard_callbacks_refs\":true,\"Linux_HW_boundaries_modeled\":true}\n",n,capacity,bytes);
    return 0;
}
