/* SPDX-License-Identifier: BSD-2-Clause-Views */
/* Actual standard callbacks/real CSR adapters/CQ/MR C. All Linux/HW, memory,
 * wire and core proofs are explicitly modeled here, not native RTL evidence. */
#define AS02_VERBS_MAIN legacy_verbs_main
#include "kernel_verbs_cases.c"

int main(int argc,char **argv)
{
    struct ib_mr *m;struct as02_verbs_mr *owned;
    struct ib_sge sg;
    struct ib_send_wr send,bad_tail={.opcode=0x7fff};
    struct ib_rdma_wr write;
    const struct ib_send_wr *bad=NULL;
    struct ib_wc wc[2];u32 a,b;unsigned int n;
    CHECK(argc==2);n=strtoul(argv[1],NULL,0);CHECK(n<9);
    qp_tx_feature=retry_feature=send_feature=recv_feature=rnr_feature=recv_retire_feature=true;
    message_cq_feature=request_cq_feature=independent_queues_feature=true;
    immediate_feature=n!=8;
    if(n>=2 && n<=7)profile_mismatch=n-1;
    if(profile_mismatch==6)independent_queues_feature=false;
    setup_verbs();
    if(profile_mismatch){
        CHECK(!sq.queue_count && !km.dma_allocs && !sq.wqe_profile && !sq.profile_bound && !verbs);
        CHECK(!as02_cq_hw_detach(&cqh));CHECK(!as02_sq_pool_destroy(&sq));CHECK(!as02_mr_pool_destroy(&mrs));
        if(independent_queues_feature)CHECK(!as02_sq_hw_detach(&receive_hw));
        CHECK(!as02_sq_hw_detach(&hw));CHECK(!as02_ctl_detach(&ctl_hw.control));
        CHECK(!atomic_load(&km.heap_live) && !atomic_load(&km.module_refs));
        printf("KERNEL_IMMEDIATE_POST {\"pass_test\":true,\"mismatch\":%u,\"rejected_before_queues\":true,\"hardware_verified\":false}\n",profile_mismatch);
        return 0;
    }
    CHECK(sq.profile_bound && sq.wqe_profile==(immediate_feature ? AS02_WQE_PROFILE_IMMEDIATE:0));
    m=register_mr();CHECK(!IS_ERR(m));owned=container_of(m,struct as02_verbs_mr,ibmr);
    create_objects();activate();
    sg=(struct ib_sge){.addr=VA+0x210,.length=65,.lkey=m->lkey};
    a=n ? 0x89abcdef:0;b=n ? 0x01234567:0;
    send=(struct ib_send_wr){.wr_id=0xf123456789abc001ULL,.sg_list=&sg,.num_sge=1,
        .opcode=IB_WR_SEND_WITH_IMM,.ex.imm_data=cpu_to_be32(a)};
    write=(struct ib_rdma_wr){.wr={.wr_id=send.wr_id+1,.sg_list=&sg,.num_sge=1,
        .opcode=IB_WR_RDMA_WRITE_WITH_IMM,.ex.imm_data=cpu_to_be32(b)},
        .remote_addr=0xe23456789abcdef0ULL,.rkey=0x81234567};
    send.next=&write.wr;write.wr.next=&bad_tail;
    if(!immediate_feature){
        CHECK(verbs->post_send(&qp.ibqp,&send,&bad)==-EOPNOTSUPP && bad==&send);
        CHECK(!model.observed_count && refcount_read(&owned->mapping->work_refs)==1);
        cleanup_verbs(m);
        puts("KERNEL_IMMEDIATE_POST {\"pass_test\":true,\"legacy_profile_still_denies\":true,\"hardware_verified\":false}");return 0;
    }
    CHECK(verbs->post_send(&qp.ibqp,&send,&bad)==-EOPNOTSUPP && bad==&bad_tail);
    CHECK(model.observed_count==2 && refcount_read(&owned->mapping->work_refs)==3);
    CHECK(model.observed[0].opcode==AS02_WQE_SEND_IMMEDIATE && model.observed[0].immediate==a &&
        !model.observed[0].remote_address && !model.observed[0].remote_key && model.observed[0].flags==AS02_WQE_SIGNALED);
    CHECK(model.observed[1].opcode==AS02_WQE_WRITE_IMMEDIATE && model.observed[1].immediate==b &&
        model.observed[1].remote_address==write.remote_addr && model.observed[1].remote_key==write.rkey &&
        model.observed[1].flags==AS02_WQE_SIGNALED);
    CHECK(as02_sq_bind_transport_profile(&sq,&ctl_hw,&cqh)==-EBUSY);
    hardware_completion(0);CHECK(verbs->poll_cq(&cq.ibcq,2,wc)==1 && wc[0].wr_id==send.wr_id &&
        wc[0].opcode==IB_WC_SEND && !wc[0].byte_len && !wc[0].wc_flags && !wc[0].ex.imm_data);
    CHECK(refcount_read(&owned->mapping->work_refs)==2);
    hardware_completion(1);CHECK(verbs->poll_cq(&cq.ibcq,2,wc)==1 && wc[0].wr_id==write.wr.wr_id &&
        wc[0].opcode==IB_WC_RDMA_WRITE && !wc[0].byte_len && !wc[0].wc_flags && !wc[0].ex.imm_data);
    CHECK(refcount_read(&owned->mapping->work_refs)==1);
    cleanup_verbs(m);
    printf("KERNEL_IMMEDIATE_POST {\"pass_test\":true,\"standard_post_send\":true,\"signal_all_base_SEND_no_RDMA_cast\":true,\"immediate_zero\":%s,\"separate_full_remote_key\":true,\"exact_bad_WR_tail_preserves_prior_posts\":true,\"actual_CQ_and_MR_release\":true,\"hardware_verified\":false}\n",n ? "false":"true");
    return 0;
}
