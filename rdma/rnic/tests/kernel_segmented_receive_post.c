/* SPDX-License-Identifier: BSD-2-Clause-Views */
/* Actual RECV/MR/RQ/CQ C; Linux/MMIO/pins/DMA/completions are models only. */
#include "kernel_segmented_immediate_post.c"

static void receive_model_completion(unsigned int i,u32 bytes,u32 flags,u32 value)
{
    zero_event(i,true);
    event.received_bytes=bytes;event.notification_flags=flags;event.notification=value;
}
static void receive_wqe_bytes(const struct ib_recv_wr *wr,u64 sequence,u64 epoch)
{
    u8 expected[128]={};unsigned int i;u64 value;
    const struct ib_sge *sg=wr->num_sge ? wr->sg_list:NULL;
#define LE(at,n,v) do { value=(v);for(i=0;i<(n);i++)expected[(at)+i]=(u8)(value>>(8*i)); }while(0)
    LE(0,8,wr->wr_id);LE(8,8,sequence);LE(56,8,epoch);
    LE(16,8,sg && sg->length ? sg->addr:0);LE(32,4,sg ? sg->length:0);
    LE(36,4,sg && sg->length ? sg->lkey:0);LE(44,2,AS02_WQE_RECV);LE(46,2,AS02_WQE_SIGNALED);
#undef LE
    CHECK(!memcmp((u8 *)km.dma[1].address+((sequence-1)&1)*128,expected,128));
}
int main(int argc,char **argv)
{
    struct ib_mr *m;struct as02_verbs_mr *owned;
    struct ib_sge sg;struct ib_recv_wr wr={},tail={};const struct ib_recv_wr *bad=NULL;
    struct ib_wc wc[3];unsigned int n,capacity,bytes,offset,registered,i,refs;int access=7;
    u32 notification=0,notification_flags=0;
    if(argc>=3 && !strcmp(argv[1],"prior"))return segmented_immediate_post_main(argc-1,argv+1);
    CHECK(argc==2);n=strtoul(argv[1],NULL,0);CHECK(n<36);
    qp_tx_feature=retry_feature=send_feature=recv_feature=rnr_feature=recv_retire_feature=true;
    message_cq_feature=request_cq_feature=independent_queues_feature=immediate_feature=true;
    atomic_feature=atomic_access_feature=zero_feature=true;
    segmented_receive_feature=n!=4 && n!=8;segmented_immediate_feature=n==4 || n==8;
    if(n>=6 && n<=8)segmented_receive_bad_tuple=n-5;
    if(n>=9 && n<=12)atomic_bad_geometry=n-8;
    setup_verbs();
    if(segmented_receive_bad_tuple || atomic_bad_geometry){
        rejected_profile_cleanup();
        printf("KERNEL_SEGMENTED_RECEIVE_POST {\"pass_test\":true,\"case\":%u,\"rejected_before_queues\":true}\n",n);return 0;
    }
    CHECK(sq.profile_bound && sq.wqe_profile==(segmented_receive_feature ? 7:6) && sq.zero_length_enabled);
    capacity=n==1 ? 1048576:n==2 ? 4097:n==3 ? 65537:n==19 ? 0:n==20 ? 1:n==21 ? 4096:8194;
    bytes=n==1 ? 1048575:n==2 ? 4097:n==3 ? 65536:n==19 || n==33 ? 0:n==20 ? 1:n==21 ? 4095:n==35 ? 8194:8193;
    offset=capacity==1048576 || !capacity ? 0:0x210;
    registered=n==5 ? 8192:capacity ? capacity+offset:4096;
    if(n==13)access=4;
    m=verbs->reg_user_mr(&pd.ibpd,capacity==1048576 ? 0x10000:0x10003,registered,VA,access,NULL,NULL);
    CHECK(!IS_ERR(m));owned=container_of(m,struct as02_verbs_mr,ibmr);
    create_objects();activate();
    CHECK(km.dma_allocs==2 && km.dma[0].bytes==256 && km.dma[1].bytes==256);
    sg=(struct ib_sge){.addr=VA+offset,.length=capacity,.lkey=m->lkey};
    wr=(struct ib_recv_wr){.wr_id=0xf123456789abc001ULL,.sg_list=capacity ? &sg:(void *)1,.num_sge=capacity ? 1:0};
    if(n==14)sg.lkey^=0x80000000U;
    if(n==15)sg.addr++;
    if(n==16)sg.length=1048577;
    if(n==17)wr.num_sge=2;
    if(n==18)wr.num_sge=-1;
    if(n==4 || n==5 || (n>=13 && n<=18)){
        CHECK(verbs->post_recv(&qp.ibqp,&wr,&bad)<0 && bad==&wr);
        CHECK(!model.observed_count && !receive_model.observed_count && !receive_model.producer &&
            refcount_read(&owned->mapping->work_refs)==1 && sq.queue_count==1);
        cleanup_verbs(m);
        printf("KERNEL_SEGMENTED_RECEIVE_POST {\"pass_test\":true,\"case\":%u,\"refused_before_RQ_producer_and_MR_ref\":true}\n",n);return 0;
    }
    if(n==29){
        receive_model.drop_ack=true;
        CHECK(verbs->post_recv(&qp.ibqp,&wr,&bad)==-ETIMEDOUT && bad==&wr && receive_hw.control.pending && receive_hw.control.uncertain);
        CHECK(refcount_read(&owned->mapping->work_refs)==2 && sq.queue_count==1 && !km.dma_frees);
        CHECK(verbs->dereg_mr(m,NULL)==-EBUSY);quarantined_mr=m;
        puts("KERNEL_SEGMENTED_RECEIVE_POST {\"pass_test\":true,\"ambiguous_RQ_producer_retains_MR_queue\":true}");return 0;
    }
    if(n==34){
        tail=wr;tail.wr_id++;tail.sg_list=NULL;tail.num_sge=1;wr.next=&tail;
        CHECK(verbs->post_recv(&qp.ibqp,&wr,&bad)<0 && bad==&tail);
    }else CHECK(!verbs->post_recv(&qp.ibqp,&wr,&bad) && !bad);
    refs=capacity ? 2:1;
    CHECK(!model.observed_count && !model.producer && receive_model.observed_count==1 && receive_model.producer==1);
    CHECK(receive_model.observed_atomic[0].base.length==capacity &&
        receive_model.observed_atomic[0].base.opcode==AS02_WQE_RECV && !receive_model.observed_atomic[0].compare && !receive_model.observed_atomic[0].swap_add);
    receive_wqe_bytes(&wr,1,qp.owner.epoch);
    CHECK(refcount_read(&owned->mapping->work_refs)==refs && !verbs->poll_cq(&recv_cq.ibcq,1,wc));
    if(n>=30 && n<=32){notification_flags=1;notification=n==30 ? 0x89abcdefU:n==31 ? 0:0xffffffffU;}
    receive_model_completion(0,bytes,notification_flags,notification);
    if(n>=22 && n<=27){
        if(n==22)event.context[276/32]^=1U<<(276%32);
        if(n==23)event.context[116/32]^=1U<<(116%32);
        if(n==24)event.cookie^=1ULL<<63;
        if(n==25)event.received_bytes=capacity+1;
        /* Keep a nonzero, well-formed epoch: low-bit1->0 would test the
         * decoder's canonical-form rejection, not stale-owner rejection. */
        if(n==26)event.context[(396+63)/32]^=1U<<((396+63)%32);
        if(n==27)event.notification_flags=2;
        CHECK(as02_cq_hw_poll(&cqh)==(n==24 || n==26 ? -ESTALE:-EIO) && event_visible && !acknowledged && !recv_cq.pending && !cq.pending);
        CHECK(refcount_read(&owned->mapping->work_refs)==refs && !km.dma_frees);quarantined_mr=m;
        printf("KERNEL_SEGMENTED_RECEIVE_POST {\"pass_test\":true,\"case\":%u,\"bad_full_CQ_retains_RQ_MR\":true}\n",n);return 0;
    }
    if(n==28){
        CHECK(as02_cq_hw_poll(&cqh)==1 && recv_cq.pending==1 && refcount_read(&owned->mapping->work_refs)==1);
        for(i=1;i<3;i++){
            wr.wr_id++;CHECK(!verbs->post_recv(&qp.ibqp,&wr,&bad));receive_wqe_bytes(&wr,i+1,qp.owner.epoch);
            receive_model_completion(i,bytes,0,0);
            if(i==1)CHECK(as02_cq_hw_poll(&cqh)==1 && recv_cq.pending==2);
        }
        CHECK(as02_cq_hw_poll(&cqh)==-ENOSPC && event_visible && recv_cq.pending==2 && refcount_read(&owned->mapping->work_refs)==2);
        CHECK(verbs->poll_cq(&recv_cq.ibcq,1,wc)==1);CHECK(as02_cq_hw_poll(&cqh)==1 && !event_visible);
        CHECK(refcount_read(&owned->mapping->work_refs)==1 && verbs->poll_cq(&recv_cq.ibcq,3,wc)==2);
    }else{
        CHECK(verbs->poll_cq(&recv_cq.ibcq,1,wc)==1 && wc[0].wr_id==wr.wr_id && wc[0].status==IB_WC_SUCCESS &&
            wc[0].opcode==IB_WC_RECV && wc[0].byte_len==bytes && wc[0].wc_flags==(notification_flags ? IB_WC_WITH_IMM:0));
        if(notification_flags)CHECK(be32_to_cpu(wc[0].ex.imm_data)==notification);
        CHECK(!verbs->poll_cq(&recv_cq.ibcq,1,wc) && !verbs->poll_cq(&cq.ibcq,1,wc) && refcount_read(&owned->mapping->work_refs)==1);
    }
    cleanup_verbs(m);
    printf("KERNEL_SEGMENTED_RECEIVE_POST {\"pass_test\":true,\"case\":%u,\"capacity\":%u,\"received_bytes\":%u,\"independent_128_byte_RQ_oracle\":true,\"actual_standard_RECV_callbacks_refs\":true,\"Linux_HW_boundaries_modeled\":true}\n",n,capacity,bytes);
    return 0;
}
