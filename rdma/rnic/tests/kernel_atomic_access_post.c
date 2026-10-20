/* SPDX-License-Identifier: BSD-2-Clause-Views */
/* Actual standard callbacks/CSR C, userspace Linux/HW boundary models only. */
#include "kernel_atomic128_post.c"

int main(int argc,char **argv)
{
    struct ib_mr *m;struct as02_verbs_mr *owned;
    struct ib_qp_attr a={},queried={};struct ib_qp_init_attr initial={};
    struct ib_sge sg;struct ib_atomic_wr wr;struct ib_wc wc;const struct ib_send_wr *bad=NULL;
    unsigned int n,i,before;
    int pins_before;
    if(argc==4 && !strcmp(argv[1],"prior") && !strcmp(argv[2],"legacy"))return atomic128_post_main(3,argv+1);
    if(argc==3 && !strcmp(argv[1],"prior"))return atomic128_post_main(2,argv+1);
    CHECK(argc==2);n=strtoul(argv[1],NULL,0);CHECK(n<8);
    qp_tx_feature=retry_feature=send_feature=recv_feature=rnr_feature=recv_retire_feature=true;
    message_cq_feature=request_cq_feature=independent_queues_feature=immediate_feature=atomic_feature=true;
    atomic_access_feature=n!=2;
    atomic_remote_mr=n<2;
    requested_qp_access=n==0 ? 14:6;
    setup_verbs();CHECK(sq.profile_bound && sq.wqe_profile==3);
    pins_before=atomic_load(&km.umem_live);
    if(n==2){
        m=verbs->reg_user_mr(&pd.ibpd,0x10003,8192,VA,15,NULL,NULL);
        CHECK(IS_ERR(m) && PTR_ERR(m)==-EOPNOTSUPP && atomic_load(&km.umem_live)==pins_before && !pd.owners);
    }
    if(n==3){
        /* Remote Atomic, just like remote WRITE, requires local-write pins. */
        m=verbs->reg_user_mr(&pd.ibpd,0x10003,8192,VA,14,NULL,NULL);
        CHECK(IS_ERR(m) && atomic_load(&km.umem_live)==pins_before && !pd.owners);
    }
    m=register_mr();CHECK(!IS_ERR(m));owned=container_of(m,struct as02_verbs_mr,ibmr);
    CHECK(owned->mapping->layout.access==(atomic_remote_mr ? 15U:7U));
    create_objects();
    if(n>=4){
        unsigned int flags[]={0,8,7,15,0x8000000eU};
        before=ctl_commands[AS02_CMD_QP];
        for(i=0;i<sizeof(flags)/sizeof(flags[0]);i++){
            a=(struct ib_qp_attr){.qp_state=IB_QPS_INIT,.port_num=1,.qp_access_flags=flags[i]};
            CHECK(verbs->modify_qp(&qp.ibqp,&a,IB_QP_STATE|IB_QP_PORT|IB_QP_PKEY_INDEX|IB_QP_ACCESS_FLAGS,NULL)==-EOPNOTSUPP);
            CHECK(qp.attributes.qp_state==IB_QPS_RESET && ctl_commands[AS02_CMD_QP]==before);
        }
    }
    if(n==2){
        a=(struct ib_qp_attr){.qp_state=IB_QPS_INIT,.port_num=1,.qp_access_flags=14};
        CHECK(verbs->modify_qp(&qp.ibqp,&a,IB_QP_STATE|IB_QP_PORT|IB_QP_PKEY_INDEX|IB_QP_ACCESS_FLAGS,NULL)==-EOPNOTSUPP);
    }
    if(n==5){
        struct as02_qp_route route={.qpn=2,.pd=pd.number,.peer_qpn=3,.local_ip=1,.peer_ip=2,.access=0};
        CHECK(as02_qp_hw_open(&qph,&route)==-EOPNOTSUPP && !qph.owned && !ctl_commands[AS02_CMD_QP]);
    }
    activate();
    CHECK(qp_access_count==1 && qp_access_commands[0]==(atomic_access_feature ? requested_qp_access:0));
    CHECK(qph.owner.access==(atomic_access_feature ? requested_qp_access:0));
    CHECK(!verbs->query_qp(&qp.ibqp,&queried,IB_QP_ACCESS_FLAGS,&initial));
    CHECK(queried.qp_access_flags==(int)requested_qp_access && queried.qp_state==IB_QPS_RTS);
    before=qp_access_count;
    CHECK(!as02_qp_hw_set_tx(&qph,qp.ibqp.qp_num,pd.number,0xfedcba));
    CHECK(qph.owner.access==(atomic_access_feature ? requested_qp_access:0) && qp_access_count==before);
    if(n==6 || n==7){
        /* Genuine raw controller validation happens BEFORE any posted bell. */
        u32 words[AS02_CTL_STAGE_WORDS]={};struct as02_ctl_reply reply={};
        words[AS02_W_OP]=AS02_CMD_QP;words[AS02_W_COOKIE_LO]=99;words[AS02_W_QP]=2;
        words[AS02_W_PD]=n==6 ? pd.number:0;words[AS02_W_ACCESS]=n==6 ? 0:14;
        CHECK(as02_ctl_execute(&ctl_hw.control,words,&reply)==-EINVAL && !ctl_hw.control.pending && qp_access_count==before);
    }
    /* Outgoing Atomic is independent of the QP's incoming Atomic permission. */
    sg=(struct ib_sge){.addr=VA+0x210,.length=8,.lkey=m->lkey};
    wr=(struct ib_atomic_wr){.wr={.wr_id=0x8123456789abcdefULL,.opcode=IB_WR_ATOMIC_FETCH_AND_ADD,
        .sg_list=&sg,.num_sge=1},.remote_addr=0xf123456789abc008ULL,.rkey=0x81234567,
        .compare_add=0xfedcba9876543210ULL};
    CHECK(!verbs->post_send(&qp.ibqp,&wr.wr,&bad) && !bad && model.observed_count==1);
    hardware_completion(0);CHECK(verbs->poll_cq(&cq.ibcq,1,&wc)==1);check_atomic_wc(&wc,&wr);
    CHECK(refcount_read(&owned->mapping->work_refs)==1);
    cleanup_verbs(m);
    CHECK(qp_access_count==2 && !qp_access_commands[1] && !qph.owner.access);
    printf("KERNEL_ATOMIC_ACCESS {\"pass_test\":true,\"case\":%u,\"actual_standard_MR_QP_SQ_CQ_callbacks\":true,\"QP_access\":%u,\"MR_access\":%u,\"legacy_remote_Atomic_refused\":%s,\"Linux_HW_boundaries_modeled\":true}\n",
        n,requested_qp_access,atomic_remote_mr ? 15:7,n==2 ? "true":"false");
    return 0;
}
