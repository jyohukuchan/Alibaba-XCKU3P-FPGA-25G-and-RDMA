/* SPDX-License-Identifier: BSD-2-Clause-Views */
/* Actual standard/SQ/CQ code under explicit Linux/MMIO/DMA/pin models. */
#include "kernel_atomic_access_post.c"

static void zero_event(unsigned i,bool receive)
{
    if(receive){
        struct model saved=model;model=receive_model;hardware_completion(i);
        /* The actual allocated RQC owner has its OWN cookie; never echo
         * the SQ's cookie as receive completion authority. */
        event.cookie=pair(model.reply+6);receive_model=model;model=saved;
    }else hardware_completion(i);
}
int main(int argc,char **argv)
{
    struct ib_mr *m;struct as02_verbs_mr *owned=NULL;
    struct ib_sge sg={.addr=~0ULL,.length=0,.lkey=0xffffffffU};
    struct ib_send_wr simple={.wr_id=0xf123456789abc001ULL,.opcode=IB_WR_SEND};
    struct ib_rdma_wr rdma={.wr={.wr_id=0xf123456789abc001ULL,.opcode=IB_WR_RDMA_WRITE},
        .remote_addr=~0ULL,.rkey=0xfedcba98};
    struct ib_recv_wr recv={.wr_id=0xf123456789abc001ULL};
    struct ib_send_wr *wr=&rdma.wr;const struct ib_send_wr *bad=NULL;const struct ib_recv_wr *rbad=NULL;
    struct ib_wc wc[3];struct as02_atomic_wqe *seen;unsigned int n;
    if(argc>=3 && !strcmp(argv[1],"prior"))return atomic_access_post_main(argc-1,argv+1);
    CHECK(argc==2);n=strtoul(argv[1],NULL,0);CHECK(n<10);
    qp_tx_feature=retry_feature=send_feature=recv_feature=rnr_feature=recv_retire_feature=true;
    message_cq_feature=request_cq_feature=independent_queues_feature=immediate_feature=atomic_feature=atomic_access_feature=true;
    zero_feature=n!=5;setup_verbs();CHECK(sq.profile_bound && sq.wqe_profile==3 && sq.zero_length_enabled==zero_feature);
    m=register_mr();CHECK(!IS_ERR(m));create_objects();activate();
    if(n==8)owned=container_of(m,struct as02_verbs_mr,ibmr);
    else{CHECK(!verbs->dereg_mr(m,NULL));m=NULL;CHECK(!vdev.mr_count && !atomic_load(&km.umem_live));}
    if(n==1){rdma.wr.opcode=IB_WR_RDMA_READ;rdma.wr.sg_list=&sg;rdma.wr.num_sge=1;}
    if(n==2 || n==3){wr=&simple;simple.opcode=n==2 ? IB_WR_SEND:IB_WR_SEND_WITH_IMM;}
    if(n==3 || n==4){wr->ex.imm_data=cpu_to_be32(0x89abcdef);if(n==4)wr->opcode=IB_WR_RDMA_WRITE_WITH_IMM;}
    if(n==0)wr->sg_list=(void *)1; /* num_sge0 must not read this pointer. */
    if(n==7 || n==8){
        if(n==8){sg=(struct ib_sge){.addr=VA+0x210,.length=65,.lkey=m->lkey};recv.sg_list=&sg;recv.num_sge=1;}
        CHECK(!verbs->post_recv(&qp.ibqp,&recv,&rbad) && !rbad);
        CHECK(receive_model.observed_count==1 && !model.observed_count);
        if(owned)CHECK(refcount_read(&owned->mapping->work_refs)==2);
        zero_event(0,true);CHECK(verbs->poll_cq(&recv_cq.ibcq,1,wc)==1 && wc[0].opcode==IB_WC_RECV &&
            wc[0].wr_id==recv.wr_id && !wc[0].byte_len && !wc[0].wc_flags);
        if(owned)CHECK(refcount_read(&owned->mapping->work_refs)==1);
        cleanup_verbs(m);printf("KERNEL_ZERO_POST {\"pass_test\":true,\"case\":%u,\"actual_RECV_zero_length_WC\":true,\"Linux_HW_boundaries_modeled\":true}\n",n);return 0;
    }
    if(n==5){
        CHECK(verbs->post_send(&qp.ibqp,wr,&bad)==-EOPNOTSUPP && bad==wr && !model.observed_count);
        cleanup_verbs(m);puts("KERNEL_ZERO_POST {\"pass_test\":true,\"case\":5,\"legacy_zero_refused_before_post\":true}");return 0;
    }
    CHECK(!verbs->post_send(&qp.ibqp,wr,&bad) && !bad && model.observed_count==1);
    seen=&model.observed_atomic[0];CHECK(!seen->base.length && !seen->base.local_key && !seen->base.local_address && !seen->compare && !seen->swap_add);
    CHECK(!vdev.mr_count && !atomic_load(&km.umem_live));zero_event(0,false);
    if(n==6){
        event.context[3]|=1U<<20; /* Actual saved zero local-offset field bit116. */
        CHECK(as02_cq_hw_poll(&cqh)==-EIO && event_visible && !acknowledged && !cq.pending && !km.dma_frees);
        puts("KERNEL_ZERO_POST {\"pass_test\":true,\"case\":6,\"mismatched_offset_retains_queue_and_CQ\":true}");return 0;
    }
    if(n==9){
        CHECK(as02_cq_hw_poll(&cqh)==1 && cq.pending==1);
        wr->wr_id++;CHECK(!verbs->post_send(&qp.ibqp,wr,&bad));zero_event(1,false);CHECK(as02_cq_hw_poll(&cqh)==1 && cq.pending==2);
        wr->wr_id++;CHECK(!verbs->post_send(&qp.ibqp,wr,&bad));zero_event(2,false);
        CHECK(as02_cq_hw_poll(&cqh)==-ENOSPC && event_visible && cq.pending==2 && !km.dma_frees);
        CHECK(verbs->poll_cq(&cq.ibcq,1,wc)==1);CHECK(as02_cq_hw_poll(&cqh)==1);
        CHECK(verbs->poll_cq(&cq.ibcq,3,wc)==2 && !wc[0].byte_len && !wc[1].byte_len);
    }else{
        CHECK(verbs->poll_cq(&cq.ibcq,1,wc)==1 && wc[0].wr_id==wr->wr_id && !wc[0].byte_len && !wc[0].status);
        CHECK(wc[0].opcode==(n==1 ? IB_WC_RDMA_READ:(n==2 || n==3) ? IB_WC_SEND:IB_WC_RDMA_WRITE));
        CHECK(!verbs->poll_cq(&cq.ibcq,1,wc));
    }
    cleanup_verbs(m);
    printf("KERNEL_ZERO_POST {\"pass_test\":true,\"case\":%u,\"actual_standard_zero_SQ_CQ\":true,\"no_registered_MR\":true,\"no_local_reference\":true,\"Linux_HW_boundaries_modeled\":true}\n",n);
    return 0;
}
