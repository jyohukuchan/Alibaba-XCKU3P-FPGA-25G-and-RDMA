/* SPDX-License-Identifier: BSD-2-Clause-Views */
/* Consume UNEDITED actual profile8 native33-word WRITE CQ and C128 RQ.
 * The Linux/MMIO/pin/coherent-DMA primitives remain explicit models. */
#include "kernel_segmented_receive_native_cq.c"

int main(int argc,char **argv)
{
    struct ib_mr *m;struct as02_verbs_mr *owned;struct ib_recv_wr wr;
    const struct ib_recv_wr *bad=NULL;struct ib_wc wc;unsigned int op,mutation;
    CHECK(argc==7);op=strtoul(argv[3],NULL,0);
    if(op!=40)return receive_native_main(argc,argv);
    CHECK(strtoul(argv[4],NULL,0)==0 && strtoul(argv[6],NULL,0)==0x89abcdefU);
    mutation=strtoul(argv[5],NULL,0);CHECK(mutation<5);
    qp_tx_feature=retry_feature=send_feature=recv_feature=rnr_feature=recv_retire_feature=true;
    message_cq_feature=request_cq_feature=independent_queues_feature=immediate_feature=atomic_feature=true;
    atomic_access_feature=zero_feature=segmented_write_feature=true;
    setup_verbs();CHECK(sq.profile_bound && sq.wqe_profile==8 && sq.zero_length_enabled && pd.number==17);
    m=verbs->reg_user_mr(&pd.ibpd,0x10003,8722,VA,7,NULL,NULL);
    CHECK(!IS_ERR(m));owned=container_of(m,struct as02_verbs_mr,ibmr);
    create_objects();activate();
    CHECK(qp.owner.qpn==2 && qp.owner.pd==17 && qp.owner.epoch==EPOCH && qp.owner.cookie==0xfedcba9889abcdefULL);
    /* Notification owner only. Its zero SGE cannot authorize remote WRITE
     * DMA or acquire/release a fabricated local payload-MR work reference. */
    wr=(struct ib_recv_wr){.wr_id=0xf123456789abc001ULL,.sg_list=(void *)1,.num_sge=0};
    CHECK(!verbs->post_recv(&qp.ibqp,&wr,&bad) && !bad && refcount_read(&owned->mapping->work_refs)==1);
    compare_receive_record(argv[2]);read_receive_event(argv[1]);
    CHECK(event.cookie==pair(receive_model.reply+6) && event.cookie==0xfedcba9889abcdf0ULL &&
        event.received_bytes==8193 && event.notification_flags==3 && event.notification==0x89abcdefU);
    if(mutation==1)event.swap_add^=1ULL<<63;
    if(mutation==2)event.context_extension|=0x1000;
    if(mutation==3)event.context[276/32]^=1U<<(276%32);
    if(mutation==4)event.context[116/32]^=1U<<(116%32);
    event_visible=true;
    if(mutation){
        CHECK(as02_cq_hw_poll(&cqh)==-EIO && event_visible && !acknowledged && !recv_cq.pending && !cq.pending &&
            !cqh.control.pending_ack && refcount_read(&owned->mapping->work_refs)==1 && !km.dma_frees);
        quarantined_mr=m;
        printf("KERNEL_SEGMENTED_NATIVE_CQ {\"pass_test\":true,\"opcode\":40,\"bytes\":8193,\"mutation\":%u,\"owners_intentionally_retained\":true,\"hardware_verified\":false}\n",mutation);return 0;
    }
    CHECK(verbs->poll_cq(&recv_cq.ibcq,1,&wc)==1 && wc.wr_id==wr.wr_id && wc.qp==&qp.ibqp &&
        wc.status==IB_WC_SUCCESS && wc.opcode==IB_WC_RECV_RDMA_WITH_IMM && wc.byte_len==8193 &&
        wc.wc_flags==IB_WC_WITH_IMM && be32_to_cpu(wc.ex.imm_data)==0x89abcdefU);
    CHECK(!event_visible && acknowledged==1 && refcount_read(&owned->mapping->work_refs)==1 && !cq.pending && !km.dma_frees);
    CHECK(!verbs->poll_cq(&recv_cq.ibcq,1,&wc));cleanup_verbs(m);
    puts("KERNEL_SEGMENTED_NATIVE_CQ {\"pass_test\":true,\"opcode\":40,\"bytes\":8193,\"capacity\":0,\"mutation\":0,\"native_RTL_CQ_unedited\":true,\"full128_kernel_native_record_identical\":true,\"actual_standard_WRITE_notification_CQ_MR_lifetime\":true,\"profile8_CQC511\":true,\"Linux_Hardware_boundaries_modeled\":true}");
    return 0;
}
