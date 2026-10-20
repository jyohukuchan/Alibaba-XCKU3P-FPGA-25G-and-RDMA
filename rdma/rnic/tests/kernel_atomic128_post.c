/* SPDX-License-Identifier: BSD-2-Clause-Views */
/* Actual standard Atomic callbacks/SQ/MR/CQ C; every Linux/HW boundary is
 * modeled. Does NOT execute callbacks inside Linux or touch FPGA hardware. */
#define AS02_VERBS_MAIN legacy_verbs_main
#include "kernel_verbs_cases.c"

/* Keep the caller's actual MR wrapper reachable in intentionally quarantined
 * cases. Do not suppress LSan or manufacture a release/drain/cleanup proof. */
static struct ib_mr *volatile quarantined_mr;

static void rejected_profile_cleanup(void)
{
    CHECK(!verbs && !sq.profile_bound && !sq.queue_count && !km.dma_allocs);
    CHECK(!as02_cq_hw_detach(&cqh));CHECK(!as02_sq_pool_destroy(&sq));
    CHECK(!as02_mr_pool_destroy(&mrs));CHECK(!as02_sq_hw_detach(&receive_hw));
    CHECK(!as02_sq_hw_detach(&hw));CHECK(!as02_ctl_detach(&ctl_hw.control));
    CHECK(!atomic_load(&km.heap_live) && !atomic_load(&km.module_refs));
}
static void check_atomic_wc(const struct ib_wc *w,const struct ib_atomic_wr *a)
{
    CHECK(w->wr_id==a->wr.wr_id && w->qp==&qp.ibqp && w->status==IB_WC_SUCCESS &&
        w->opcode==(a->wr.opcode==IB_WR_ATOMIC_CMP_AND_SWP ? IB_WC_COMP_SWAP:IB_WC_FETCH_ADD) &&
        w->byte_len==8 && !w->wc_flags && !w->ex.imm_data);
}
int main(int argc,char **argv)
{
    struct ib_mr *m;struct as02_verbs_mr *owned;struct ib_sge sg;
    struct ib_atomic_wr a,b;struct ib_send_wr tail={.opcode=0x7fff};
    const struct ib_send_wr *bad=NULL;struct ib_wc wc[3];unsigned int n,i;
    if(argc==3 && !strcmp(argv[1],"legacy"))return legacy_verbs_main(2,argv+1);
    CHECK(argc==2);n=strtoul(argv[1],NULL,0);CHECK(n<14);
    qp_tx_feature=retry_feature=send_feature=recv_feature=rnr_feature=recv_retire_feature=true;
    message_cq_feature=request_cq_feature=independent_queues_feature=immediate_feature=true;
    atomic_feature=n!=9;atomic_readonly_mr=n==2;
    if(n>=10)atomic_bad_geometry=n-9;
    setup_verbs();
    if(atomic_bad_geometry){
        rejected_profile_cleanup();
        printf("KERNEL_ATOMIC128_POST {\"pass_test\":true,\"case\":%u,\"rejected_before_queues\":true}\n",n);return 0;
    }
    CHECK(sq.profile_bound && sq.wqe_profile==(atomic_feature ? 3:1));
    m=register_mr();CHECK(!IS_ERR(m));owned=container_of(m,struct as02_verbs_mr,ibmr);
    create_objects();activate();
    CHECK(km.dma_allocs==2 && km.dma[0].bytes==(atomic_feature ? 256:128) &&
        km.dma[1].bytes==(atomic_feature ? 256:128));
    sg=(struct ib_sge){.addr=VA+0x210,.length=8,.lkey=m->lkey};
    a=(struct ib_atomic_wr){.wr={.wr_id=0xf123456789abc001ULL,.sg_list=&sg,.num_sge=1,
        .opcode=IB_WR_ATOMIC_CMP_AND_SWP},.remote_addr=0xe23456789abcd008ULL,
        .compare_add=0xfedcba9876543210ULL,.swap=0x8123456789abcdefULL,.rkey=0x81234567};
    b=a;b.wr.wr_id++;b.wr.opcode=IB_WR_ATOMIC_FETCH_AND_ADD;b.compare_add=0x8000000100000003ULL;
    if(n==9){
        CHECK(verbs->post_send(&qp.ibqp,&a.wr,&bad)==-EOPNOTSUPP && bad==&a.wr);
        CHECK(!model.observed_count && refcount_read(&owned->mapping->work_refs)==1);
        cleanup_verbs(m);puts("KERNEL_ATOMIC128_POST {\"pass_test\":true,\"case\":9,\"legacy_still_refuses_Atomic\":true}");return 0;
    }
    if(n==2){
        CHECK(verbs->post_send(&qp.ibqp,&a.wr,&bad)==-EACCES && bad==&a.wr);
        CHECK(!model.observed_count && refcount_read(&owned->mapping->work_refs)==1);
        cleanup_verbs(m);puts("KERNEL_ATOMIC128_POST {\"pass_test\":true,\"case\":2,\"result_LOCAL_WRITE_required\":true}");return 0;
    }
    if(n==6){
        for(i=0;i<4;i++){
            struct ib_atomic_wr wrong=a;
            if(i==0)wrong.remote_addr++;
            if(i==1)sg.length=9;
            if(i==2)wrong.wr.num_sge=2;
            if(i==3)wrong.wr.send_flags=0x80000000U;
            CHECK(verbs->post_send(&qp.ibqp,&wrong.wr,&bad)<0 && bad==&wrong.wr);
            sg.length=8;
            CHECK(!model.observed_count && refcount_read(&owned->mapping->work_refs)==1);
        }
    }
    if(n==8){
        struct ib_rdma_wr read={.wr={.wr_id=a.wr.wr_id,.sg_list=&sg,.num_sge=1,.opcode=IB_WR_RDMA_READ},
            .remote_addr=a.remote_addr,.rkey=a.rkey};
        struct ib_send_wr send={.wr_id=b.wr.wr_id,.sg_list=&sg,.num_sge=1,.opcode=IB_WR_SEND_WITH_IMM,
            .ex.imm_data=cpu_to_be32(0x89abcdef)};
        read.wr.next=&send;
        CHECK(!verbs->post_send(&qp.ibqp,&read.wr,&bad) && !bad);
        CHECK(!model.observed_atomic[0].compare && !model.observed_atomic[0].swap_add &&
            !model.observed_atomic[1].compare && !model.observed_atomic[1].swap_add);
        hardware_completion(0);CHECK(verbs->poll_cq(&cq.ibcq,1,wc)==1 && wc[0].opcode==IB_WC_RDMA_READ && wc[0].byte_len==8);
        hardware_completion(1);CHECK(verbs->poll_cq(&cq.ibcq,1,wc)==1 && wc[0].opcode==IB_WC_SEND && !wc[0].byte_len);
        cleanup_verbs(m);puts("KERNEL_ATOMIC128_POST {\"pass_test\":true,\"case\":8,\"normal_READ_SEND_IMM_preserved\":true}");return 0;
    }
    if(n==4){struct ib_atomic_wr temp=a;a=b;b=temp;}
    a.wr.next=&b.wr;b.wr.next=&tail;
    CHECK(verbs->post_send(&qp.ibqp,&a.wr,&bad)==-EOPNOTSUPP && bad==&tail);
    CHECK(model.observed_count==2 && refcount_read(&owned->mapping->work_refs)==3);
    for(i=0;i<2;i++){
        const struct ib_atomic_wr *w=i ? &b:&a;struct as02_atomic_wqe *seen=&model.observed_atomic[i];
        CHECK(seen->base.opcode==(w->wr.opcode==IB_WR_ATOMIC_CMP_AND_SWP ? 7U:8U) &&
            seen->base.flags==1 && seen->base.length==8 && seen->base.local_key==m->lkey &&
            seen->base.local_address==sg.addr && seen->base.remote_key==w->rkey && seen->base.remote_address==w->remote_addr &&
            seen->compare==(w->wr.opcode==IB_WR_ATOMIC_CMP_AND_SWP ? w->compare_add:0) &&
            seen->swap_add==(w->wr.opcode==IB_WR_ATOMIC_CMP_AND_SWP ? w->swap:w->compare_add));
    }
    if(n==5){
        struct as02_sq_completion_proof p={.owner=qp.owner,.sequence=1,.flags=3,.status=0};
        CHECK(as02_sq_complete(&sq,&p)==-EOPNOTSUPP && refcount_read(&owned->mapping->work_refs)==3);
    }
    hardware_completion(0);
    if(n==3 || n==4){
        if(n==3)event.compare^=1ULL<<63;else event.swap_add^=1ULL<<63;
        CHECK(as02_cq_hw_poll(&cqh)==-EIO && event_visible && !acknowledged && !cqh.control.pending_ack &&
            refcount_read(&owned->mapping->work_refs)==3 && !cq.pending && !km.dma_frees);
        /* Intentionally retain quarantined owners. No test-forged cleanup. */
        quarantined_mr=m;CHECK(quarantined_mr==m);
        printf("KERNEL_ATOMIC128_POST {\"pass_test\":true,\"case\":%u,\"operand_mismatch_retains_owners\":true,\"owners_intentionally_retained\":true}\n",n);return 0;
    }
    if(n==7){
        atomic_drop_ack=true;CHECK(as02_cq_hw_poll(&cqh)==-EAGAIN && cqh.control.pending_ack);
        CHECK(cq.pending==1 && refcount_read(&owned->mapping->work_refs)==2 && event_visible);
        CHECK(as02_cq_hw_poll(&cqh)==-EAGAIN && cq.pending==1 && refcount_read(&owned->mapping->work_refs)==2);
        atomic_drop_ack=false;CHECK(as02_cq_hw_poll(&cqh)==1 && !cqh.control.pending_ack && !event_visible);
        CHECK(atomic_ack_writes==3 && cq.pending==1 && refcount_read(&owned->mapping->work_refs)==2);
    }else CHECK(as02_cq_hw_poll(&cqh)==1);
    hardware_completion(1);CHECK(as02_cq_hw_poll(&cqh)==1 && refcount_read(&owned->mapping->work_refs)==1);
    if(n==1){
        struct ib_atomic_wr third=a;third.wr.next=NULL;third.wr.wr_id+=2;
        CHECK(!verbs->post_send(&qp.ibqp,&third.wr,&bad) && !bad && model.observed_count==3);
        hardware_completion(2);CHECK(as02_cq_hw_poll(&cqh)==-ENOSPC && event_visible && cq.pending==2 &&
            refcount_read(&owned->mapping->work_refs)==2);
        CHECK(verbs->poll_cq(&cq.ibcq,1,wc)==1);check_atomic_wc(wc,&a);
        CHECK(as02_cq_hw_poll(&cqh)==1 && !event_visible && refcount_read(&owned->mapping->work_refs)==1);
        CHECK(verbs->poll_cq(&cq.ibcq,2,wc)==2);check_atomic_wc(wc,&b);check_atomic_wc(wc+1,&third);
    }else{
        CHECK(verbs->poll_cq(&cq.ibcq,2,wc)==2);check_atomic_wc(wc,&a);check_atomic_wc(wc+1,&b);
    }
    cleanup_verbs(m);
    printf("KERNEL_ATOMIC128_POST {\"pass_test\":true,\"case\":%u,\"actual_standard_callbacks\":true,\"two_128_byte_rings\":true,\"full_operands_and_result_permissions\":true,\"exact_bad_WR_tail\":true,\"actual_CQ_MR_ref_lifecycle\":true,\"Linux_Hardware_boundaries_modeled\":true}\n",n);
    return 0;
}

