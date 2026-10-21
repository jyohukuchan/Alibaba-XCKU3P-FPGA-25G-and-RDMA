/* SPDX-License-Identifier: BSD-2-Clause-Views */
/* Actual new-profile SQ/MR/CQ/verbs code; Linux/HW boundaries are models. */
#include "kernel_zero_post.c"

int main(int argc,char **argv)
{
    struct ib_mr *m;
    struct as02_verbs_mr *owned;
    struct ib_send_wr *send=calloc(1,sizeof(*send));
    struct ib_sge sg;
    struct ib_rdma_wr rdma={};
    struct ib_send_wr *wr;
    const struct ib_send_wr *bad=NULL;
    struct ib_wc wc[3];
    unsigned int n,length,offset,registered,i;
    CHECK(send);
    if(argc>=3 && !strcmp(argv[1],"prior")){free(send);return zero_post_main(argc-1,argv+1);}
    CHECK(argc==2);n=strtoul(argv[1],NULL,0);CHECK(n<18);
    qp_tx_feature=retry_feature=send_feature=recv_feature=rnr_feature=recv_retire_feature=true;
    message_cq_feature=request_cq_feature=independent_queues_feature=immediate_feature=true;
    atomic_feature=atomic_access_feature=zero_feature=true;
    segmented_feature=n!=4 && n!=7;
    if(n==6)segmented_bad_tuple=1;
    if(n==7)segmented_bad_tuple=2;
    if(n>=8 && n<=11)atomic_bad_geometry=n-7;
    setup_verbs();
    if(segmented_bad_tuple || atomic_bad_geometry){
        rejected_profile_cleanup();free(send);
        printf("KERNEL_SEGMENTED_POST {\"pass_test\":true,\"case\":%u,\"rejected_before_queues\":true}\n",n);return 0;
    }
    CHECK(sq.profile_bound && sq.wqe_profile==(segmented_feature ? 4:3) && sq.zero_length_enabled);
    length=n==2 || n==3 ? 1048576:8193;offset=length==1048576 ? 0:0x210;
    registered=n==5 ? 8192:length+offset;
    m=verbs->reg_user_mr(&pd.ibpd,length==1048576 ? 0x10000:0x10003,registered,VA,7,NULL,NULL);
    CHECK(!IS_ERR(m));owned=container_of(m,struct as02_verbs_mr,ibmr);
    create_objects();activate();
    CHECK(km.dma_allocs==2 && km.dma[0].bytes==256 && km.dma[1].bytes==256);
    sg=(struct ib_sge){.addr=VA+offset,.length=length,.lkey=m->lkey};
    rdma=(struct ib_rdma_wr){.wr={.wr_id=0xf123456789abc001ULL,.opcode=IB_WR_RDMA_WRITE,
        .sg_list=&sg,.num_sge=1},.remote_addr=0xe23456789abcdef0ULL,.rkey=0x81234567};
    *send=(struct ib_send_wr){.wr_id=rdma.wr.wr_id,.opcode=IB_WR_SEND,.sg_list=&sg,.num_sge=1};
    wr=n==1 || n==3 ? send:&rdma.wr;
    if(n==4 || n==5 || n==16 || n==17){
        if(n==16)sg.lkey^=0x80000000U;
        if(n==17)rdma.wr.opcode=IB_WR_RDMA_READ;
        CHECK(verbs->post_send(&qp.ibqp,wr,&bad)<0 && bad==wr);
        CHECK(!model.observed_count && refcount_read(&owned->mapping->work_refs)==1);
        cleanup_verbs(m);free(send);
        printf("KERNEL_SEGMENTED_POST {\"pass_test\":true,\"case\":%u,\"refused_before_producer_and_MR_ref\":true}\n",n);return 0;
    }
    /* Real writel is void: withhold ACK visibility after a consumed producer
     * instead of pretending it can return a synchronous bus-write errno. */
    if(n==15)model.drop_ack=true;
    if(n==15){
        CHECK(verbs->post_send(&qp.ibqp,wr,&bad)==-ETIMEDOUT && bad==wr && hw.control.pending && hw.control.uncertain);
        CHECK(refcount_read(&owned->mapping->work_refs)==2 && sq.queue_count==1 && !km.dma_frees);
        CHECK(verbs->dereg_mr(m,NULL)==-EBUSY);quarantined_mr=m;free(send);
        puts("KERNEL_SEGMENTED_POST {\"pass_test\":true,\"case\":15,\"ambiguous_producer_retains_full_MR_queue\":true}");return 0;
    }
    CHECK(!verbs->post_send(&qp.ibqp,wr,&bad) && !bad && model.observed_count==1);
    CHECK(model.observed_atomic[0].base.length==length && model.observed_atomic[0].base.local_address==sg.addr &&
        model.observed_atomic[0].base.local_key==m->lkey && !model.observed_atomic[0].compare && !model.observed_atomic[0].swap_add);
    CHECK(refcount_read(&owned->mapping->work_refs)==2 && !verbs->poll_cq(&cq.ibcq,1,wc));
    hardware_completion(0);
    if(n==12 || n==13){
        if(n==12)event.context[276/32]^=1U<<(276%32);
        else event.context[116/32]^=1U<<(116%32);
        CHECK(as02_cq_hw_poll(&cqh)==-EIO && event_visible && !acknowledged && !cq.pending);
        CHECK(refcount_read(&owned->mapping->work_refs)==2 && sq.queue_count==1 && !km.dma_frees);
        quarantined_mr=m;free(send);
        printf("KERNEL_SEGMENTED_POST {\"pass_test\":true,\"case\":%u,\"wrong_full_owner_retains_MR_queue_CQ\":true}\n",n);return 0;
    }
    if(n==14){
        CHECK(as02_cq_hw_poll(&cqh)==1 && cq.pending==1 && refcount_read(&owned->mapping->work_refs)==1);
        for(i=1;i<3;i++){
            wr->wr_id++;CHECK(!verbs->post_send(&qp.ibqp,wr,&bad));hardware_completion(i);
            if(i==1)CHECK(as02_cq_hw_poll(&cqh)==1 && cq.pending==2);
        }
        CHECK(as02_cq_hw_poll(&cqh)==-ENOSPC && event_visible && cq.pending==2 && refcount_read(&owned->mapping->work_refs)==2);
        CHECK(verbs->poll_cq(&cq.ibcq,1,wc)==1);CHECK(as02_cq_hw_poll(&cqh)==1 && !event_visible);
        CHECK(refcount_read(&owned->mapping->work_refs)==1 && verbs->poll_cq(&cq.ibcq,3,wc)==2);
    }else{
        CHECK(verbs->poll_cq(&cq.ibcq,1,wc)==1 && wc[0].wr_id==wr->wr_id && wc[0].status==IB_WC_SUCCESS &&
            wc[0].opcode==(wr==send ? IB_WC_SEND:IB_WC_RDMA_WRITE) && !wc[0].byte_len && !wc[0].wc_flags);
        CHECK(!verbs->poll_cq(&cq.ibcq,1,wc) && refcount_read(&owned->mapping->work_refs)==1);
    }
    cleanup_verbs(m);free(send);
    printf("KERNEL_SEGMENTED_POST {\"pass_test\":true,\"case\":%u,\"bytes\":%u,\"actual_standard_callbacks_and_refs\":true,\"Linux_HW_boundaries_modeled\":true}\n",n,length);
    return 0;
}
