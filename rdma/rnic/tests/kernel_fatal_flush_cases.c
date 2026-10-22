/* SPDX-License-Identifier: BSD-2-Clause-Views */
/* Actual driver/reader/RQC/CQ/ref bodies; all Linux/MMIO/pin/DMA/certificates
 * are explicit MODELS. These constructed records are NOT native snapshots.
 * The original220 cases still run unchanged at default FEC15.
 */
#include "kernel_fatal_verbs_cases.c"

static void flush_parent_retained(unsigned refs,unsigned frees)
{
    CHECK(refcount_read(&fatal_owned_mr->mapping->work_refs)==refs);
    CHECK(km.dma_frees==frees && qp.initialized && vdev.qp==&qp && pd.owners==2);
    CHECK(qp.hw_owned && !qp.sq_closed && qph.owned && sq.queue_count==1 && mrs.mapping_count==1);
}
static void flush_wc(const struct ib_wc *wc,u64 id)
{
    CHECK(wc->wr_id==id && wc->qp==&qp.ibqp && wc->status==IB_WC_WR_FLUSH_ERR);
    CHECK(wc->opcode==IB_WC_RECV && !wc->byte_len && !wc->wc_flags);
}
int main(int argc,char **argv)
{
    struct ib_mr *m;struct ib_sge sg;struct ib_recv_wr wr;const struct ib_recv_wr *bad=NULL;
    struct ib_send_wr send;const struct ib_send_wr *bad_send=NULL;
    struct ib_qp_attr attr={.qp_state=IB_QPS_ERR};struct ib_wc wc[3];
    unsigned n,refs,frees,bells,handlers,stop_base;int ret;
    if(argc>=3 && !strcmp(argv[1],"prior"))return fatal_legacy_main(argc-1,argv+1);
    CHECK(argc==2);n=strtoul(argv[1],NULL,0);CHECK(n<16);
    qp_tx_feature=retry_feature=send_feature=recv_feature=rnr_feature=recv_retire_feature=true;
    message_cq_feature=request_cq_feature=independent_queues_feature=immediate_feature=true;
    atomic_feature=atomic_access_feature=zero_feature=segmented_write_feature=true;
    flush_fec_features=n==12 ? AS02_FEC_FEATURE_VALUE:n==14 ? 30:n==15 ? 47:AS02_FEC_RQC_CANCEL_FEATURE_VALUE;
    fatal_case=n==1 ? 1:0;setup_verbs();
    ret=as02_fatal_verbs_bind(&fatal_attachment,&vdev,fatal_mmio,sizeof(fatal_mmio));
    if(n>=14){
        CHECK(ret==-ENODEV && !vdev.fatal && !fatal_writes);fatal_empty_cleanup();
        printf("KERNEL_FATAL_FLUSH_RESULT {\"pass_test\":true,\"case\":%u,\"unknown_capability_rejected\":true,\"boundaries_modeled\":true}\n",n);return 0;
    }
    CHECK(!ret && fatal_attachment.reader.features==flush_fec_features);
    m=register_mr();CHECK(!IS_ERR(m));quarantined_mr=m;fatal_owned_mr=container_of(m,struct as02_verbs_mr,ibmr);
    create_objects();activate();
    /* The actual QP-open path already performs its mandatory STOP. The
     * tested error path must add exactly one, never borrow that old proof. */
    stop_base=ctl_commands[AS02_CMD_STOP];CHECK(stop_base==1);
    sg=(struct ib_sge){.addr=VA+0x210,.length=128,.lkey=m->lkey};
    wr=(struct ib_recv_wr){.wr_id=0xf123456789abc001ULL,.sg_list=&sg,.num_sge=1};
    CHECK(!verbs->post_recv(&qp.ibqp,&wr,&bad) && !bad);
    if(n==2){wr.wr_id++;CHECK(!verbs->post_recv(&qp.ibqp,&wr,&bad));}
    if(n==10){
        send=(struct ib_send_wr){.wr_id=0xdeadbeef01234567ULL,.sg_list=&sg,.num_sge=1,.opcode=IB_WR_SEND};
        CHECK(!verbs->post_send(&qp.ibqp,&send,&bad_send) && !bad_send && model.producer==1);
    }
    refs=refcount_read(&fatal_owned_mr->mapping->work_refs);frees=km.dma_frees;
    CHECK(refs==(n==2 || n==10 ? 3:2));
    fatal_refs=refs;fatal_dma_frees=frees;
    qp.ibqp.event_handler=n==9 ? NULL:fatal_handler;qp.ibqp.qp_context=&fatal_attachment;
    if(n==11)CHECK(!verbs->req_notify_cq(&recv_cq.ibcq,IB_CQ_NEXT_COMP));
    ctl_drop_reply=true;
    if(n==13){
        CHECK(!verbs->modify_qp(&qp.ibqp,&attr,IB_QP_STATE,NULL));
        CHECK(qp.error_pending && qp.hw_owned && !qp.fatal_event_recorded && !recv_cq.pending);
        flush_parent_retained(refs,frees);
        printf("KERNEL_FATAL_FLUSH_RESULT {\"pass_test\":true,\"case\":13,\"manual_ERR_no_fatal_authority\":true,\"boundaries_modeled\":true}\n");return 0;
    }
    fatal_make_record();fatal_visible=1;fatal_drop_ack=n==3;
    ret=as02_fatal_verbs_poll(&fatal_attachment);CHECK(ret==(n==3 ? -EAGAIN:1));
    CHECK(qp.fatal_event_recorded && qp.fatal_event_notified && qp.error_pending && qp.error_work.work.pending);
    CHECK(!recv_cq.pending && !cq.pending);handlers=fatal_handlers;
    CHECK(handlers==(n==9 ? 0:1));flush_parent_retained(refs,frees);
    if(n==2){
        struct as02_sq_completion dummy={.wr_id=900,.qpn=qp.ibqp.qp_num,.opcode=AS02_WQE_RECV,.status=IB_WC_SUCCESS};
        /* Explicit software-CQ occupancy model, never a native proof/event. */
        CHECK(!as02_cq_publish(&vr,&dummy) && recv_cq.pending==1);
    }
    if(n==4){receive_model.override=true;receive_model.override_flags=31;}
    if(n==5)receive_model.corrupt_word=13;
    if(n==6)qp.owner.cookie^=1ULL<<63;
    if(n==7){
        fatal_record.sequence=2;fatal_visible=1;
        CHECK(as02_fatal_verbs_poll(&fatal_attachment)==-EIO && fatal_attachment.reader.uncertain && vdev.stopping);
    }
    if(n==8)CHECK(!as02_fatal_verbs_detach(&fatal_attachment));
    cm_run_work(&qp.error_work);bells=receive_model.bells;
    if((n>=4 && n<=8) || n==12){
        CHECK(qp.error_progress_status<0 && qp.error_pending && !recv_cq.pending && !cq.pending);
        flush_parent_retained(refs,frees);
        if(n>=4 && n<=8)CHECK(ctl_commands[AS02_CMD_STOP]==stop_base);
        printf("KERNEL_FATAL_FLUSH_RESULT {\"pass_test\":true,\"case\":%u,\"invalid_or_legacy_authority_retains_WR_refs\":true,\"boundaries_modeled\":true}\n",n);return 0;
    }
    if(n==2){
        CHECK(qp.error_progress_status==-ENOSPC && qp.error_pending && recv_cq.pending==2 && ctl_commands[AS02_CMD_STOP]==stop_base);
        flush_parent_retained(2,frees);
        CHECK(verbs->poll_cq(&recv_cq.ibcq,2,wc)==2 && wc[0].wr_id==900);flush_wc(&wc[1],0xf123456789abc001ULL);
        CHECK(qp.error_work.work.pending);cm_run_work(&qp.error_work);
        CHECK(receive_model.bells==bells && recv_cq.pending==1);flush_parent_retained(1,frees);
        CHECK(verbs->poll_cq(&recv_cq.ibcq,1,wc)==1);flush_wc(&wc[0],0xf123456789abc002ULL);
    }else{
        CHECK(recv_cq.pending==1 && !cq.pending && !receive_model.active && receive_model.flags==63);
        flush_parent_retained(n==10 ? 2:1,frees);
        CHECK(verbs->poll_cq(&recv_cq.ibcq,1,wc)==1);flush_wc(&wc[0],wr.wr_id);
    }
    CHECK(qp.error_progress_status<0 && qp.error_pending && qp.hw_owned && !qp.sq_closed);
    CHECK(ctl_commands[AS02_CMD_STOP]==stop_base+1 && ctl_qp_pd!=0 && !recv_cq.pending && !cq.pending);
    if(n==3){
        CHECK(fatal_attachment.reader.pending_ack);fatal_drop_ack=0;
        CHECK(as02_fatal_verbs_poll(&fatal_attachment)==1 && fatal_handlers==handlers && !recv_cq.pending);
    }
    if(n==11){irq_work_sync(&recv_cq.notify);CHECK(interrupts==1);}
    if(qp.error_work.work.pending)cm_run_work(&qp.error_work);
    CHECK(receive_model.bells==bells && !recv_cq.pending && !cq.pending && fatal_handlers==handlers && qp.hw_owned);
    CHECK(!verbs->poll_cq(&recv_cq.ibcq,2,wc));flush_parent_retained(n==10 ? 2:1,frees);
    printf("KERNEL_FATAL_FLUSH_RESULT {\"pass_test\":true,\"case\":%u,\"real_RQC_certificate_before_ordered_flush\":true,\"QP_STOP_still_unproved\":true,\"boundaries_modeled\":true}\n",n);
    return 0;
}
