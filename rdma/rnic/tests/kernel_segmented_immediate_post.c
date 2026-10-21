/* SPDX-License-Identifier: BSD-2-Clause-Views */
/* Actual standard callbacks; Linux/MMIO/coherent DMA/completion models only. */
#include "kernel_segmented_read_post.c"

int main(int argc,char **argv)
{
    struct ib_mr *m;struct as02_verbs_mr *owned;
    struct ib_sge sg;struct ib_rdma_wr rdma={};struct ib_send_wr send={};
    struct ib_send_wr *wr;const struct ib_send_wr *bad=NULL;struct ib_wc wc[3];
    unsigned int n,c,op,length,offset,registered,i,refs;int access=7;
    if(argc>=3 && !strcmp(argv[1],"prior"))return segmented_read_post_main(argc-1,argv+1);
    CHECK(argc==2);n=strtoul(argv[1],NULL,0);CHECK(n<44);c=n%22;op=n<22 ? 5:6;
    qp_tx_feature=retry_feature=send_feature=recv_feature=rnr_feature=recv_retire_feature=true;
    message_cq_feature=request_cq_feature=independent_queues_feature=immediate_feature=true;
    atomic_feature=atomic_access_feature=zero_feature=true;
    segmented_read_feature=c==4 || c==7;segmented_immediate_feature=c!=4 && c!=7;
    if(c==6)segmented_immediate_bad_tuple=1;
    if(c==7)segmented_immediate_bad_tuple=2;
    if(c==8 || c==9)atomic_bad_geometry=c-7;
    setup_verbs();
    if(segmented_immediate_bad_tuple || atomic_bad_geometry) {
        rejected_profile_cleanup();
        printf("KERNEL_SEGMENTED_IMMEDIATE_POST {\"pass_test\":true,\"case\":%u,\"rejected_before_queues\":true}\n",n);return 0;
    }
    CHECK(sq.profile_bound && sq.wqe_profile==(segmented_immediate_feature ? 6:5) && sq.zero_length_enabled);
    length=c==1 ? 1048576:c==2 ? 4097:c==3 ? 65537:c==21 ? 0:8193;
    offset=length==1048576 || !length ? 0:0x210;
    registered=c==5 ? 8192:length ? length+offset:4096;
    if(c==20)access=4; /* Source reads do NOT need local-write placement permission. */
    m=verbs->reg_user_mr(&pd.ibpd,length==1048576 ? 0x10000:0x10003,registered,VA,access,NULL,NULL);
    CHECK(!IS_ERR(m));owned=container_of(m,struct as02_verbs_mr,ibmr);
    create_objects();activate();
    CHECK(km.dma_allocs==2 && km.dma[0].bytes==256 && km.dma[1].bytes==256);
    sg=(struct ib_sge){.addr=VA+offset,.length=length,.lkey=m->lkey};
    wr=op==5 ? &send:&rdma.wr;
    *wr=(struct ib_send_wr){.wr_id=0xf123456789abc001ULL,.opcode=op==5 ? IB_WR_SEND_WITH_IMM:IB_WR_RDMA_WRITE_WITH_IMM,
        .sg_list=length ? &sg:(void *)1,.num_sge=length ? 1:0};
    wr->ex.imm_data=cpu_to_be32(0x89abcdefU);
    if(op==6){rdma.remote_addr=0xe23456789abcdef0ULL;rdma.rkey=0x81234567;}
    if(c==14)sg.lkey^=0x80000000U;
    if(c==15)sg.addr++;
    if(c==16){if(op==6)rdma.remote_addr=~0ULL-8191;else sg.addr=~0ULL-8191;}
    if(c==17)sg.length=1048577;
    if(c==18)wr->send_flags=0x80000000U;
    if(c==19)wr->num_sge=2;
    if(c==4 || c==5 || (c>=14 && c<=19)) {
        CHECK(verbs->post_send(&qp.ibqp,wr,&bad)<0 && bad==wr);
        CHECK(!model.observed_count && !model.producer && refcount_read(&owned->mapping->work_refs)==1 && sq.queue_count==1);
        cleanup_verbs(m);
        printf("KERNEL_SEGMENTED_IMMEDIATE_POST {\"pass_test\":true,\"case\":%u,\"refused_before_producer_and_MR_ref\":true}\n",n);return 0;
    }
    if(c==13) {
        model.drop_ack=true;
        CHECK(verbs->post_send(&qp.ibqp,wr,&bad)==-ETIMEDOUT && bad==wr && hw.control.pending && hw.control.uncertain);
        CHECK(refcount_read(&owned->mapping->work_refs)==2 && sq.queue_count==1 && !km.dma_frees);
        CHECK(verbs->dereg_mr(m,NULL)==-EBUSY);quarantined_mr=m;
        puts("KERNEL_SEGMENTED_IMMEDIATE_POST {\"pass_test\":true,\"ambiguous_producer_retains_MR_queue\":true}");return 0;
    }
    refs=length ? 2:1;
    CHECK(!verbs->post_send(&qp.ibqp,wr,&bad) && !bad && model.observed_count==1);
    CHECK(model.observed_atomic[0].base.length==length && model.observed_atomic[0].base.immediate==0x89abcdefU &&
        model.observed_atomic[0].base.opcode==op && model.observed_atomic[0].base.remote_key==(op==6 ? rdma.rkey:0) &&
        model.observed_atomic[0].base.remote_address==(op==6 ? rdma.remote_addr:0));
    CHECK(refcount_read(&owned->mapping->work_refs)==refs && !verbs->poll_cq(&cq.ibcq,1,wc));
    hardware_completion(0);
    if(c==10 || c==11) {
        if(c==10)event.context[276/32]^=1U<<(276%32);else event.context[588/32]^=1U<<(588%32);
        CHECK(as02_cq_hw_poll(&cqh)==-EIO && event_visible && !acknowledged && !cq.pending);
        CHECK(refcount_read(&owned->mapping->work_refs)==refs && sq.queue_count==1 && !km.dma_frees);quarantined_mr=m;
        printf("KERNEL_SEGMENTED_IMMEDIATE_POST {\"pass_test\":true,\"case\":%u,\"wrong_full_owner_retains_MR_queue_CQ\":true}\n",n);return 0;
    }
    if(c==12) {
        CHECK(as02_cq_hw_poll(&cqh)==1 && cq.pending==1 && refcount_read(&owned->mapping->work_refs)==1);
        for(i=1;i<3;i++) {
            wr->wr_id++;CHECK(!verbs->post_send(&qp.ibqp,wr,&bad));hardware_completion(i);
            if(i==1)CHECK(as02_cq_hw_poll(&cqh)==1 && cq.pending==2);
        }
        CHECK(as02_cq_hw_poll(&cqh)==-ENOSPC && event_visible && cq.pending==2 && refcount_read(&owned->mapping->work_refs)==2);
        CHECK(verbs->poll_cq(&cq.ibcq,1,wc)==1);CHECK(as02_cq_hw_poll(&cqh)==1 && !event_visible);
        CHECK(refcount_read(&owned->mapping->work_refs)==1 && verbs->poll_cq(&cq.ibcq,3,wc)==2);
    }else {
        CHECK(verbs->poll_cq(&cq.ibcq,1,wc)==1 && wc[0].wr_id==wr->wr_id && wc[0].status==IB_WC_SUCCESS &&
            wc[0].opcode==(op==5 ? IB_WC_SEND:IB_WC_RDMA_WRITE) && !wc[0].byte_len && !wc[0].wc_flags);
        CHECK(!verbs->poll_cq(&cq.ibcq,1,wc) && refcount_read(&owned->mapping->work_refs)==1);
    }
    cleanup_verbs(m);
    printf("KERNEL_SEGMENTED_IMMEDIATE_POST {\"pass_test\":true,\"case\":%u,\"bytes\":%u,\"actual_standard_Immediate_callbacks_refs\":true,\"Linux_HW_boundaries_modeled\":true}\n",n,length);
    return 0;
}
