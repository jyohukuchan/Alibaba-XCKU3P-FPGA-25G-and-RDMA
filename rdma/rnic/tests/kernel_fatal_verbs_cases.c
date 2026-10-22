/* SPDX-License-Identifier: BSD-2-Clause-Views */
/* Actual driver/reader/QP callbacks; Linux/certificate/MMIO/hardware models.
 * Constructed certificates below are NOT edited native execution evidence.
 */
#include "kernel_segmented_write_post.c"
#include "fatal_verbs.h"

static struct as02_fatal_verbs fatal_attachment;
static u8 fatal_mmio[AS02_FEC_BYTES];
static struct as02_fatal_record fatal_record;
static unsigned fatal_visible,fatal_ack,fatal_drop_ack,fatal_calls,fatal_writes,fatal_handlers,fatal_bad_abi;
static struct as02_verbs_mr *fatal_owned_mr;
static unsigned fatal_refs,fatal_dma_frees,fatal_case;

u32 readl(const volatile void *p)
{
    uintptr_t address=(uintptr_t)p,base=(uintptr_t)fatal_mmio;
    if(address>=base && address<base+sizeof(fatal_mmio)){
        u32 off=address-base;CHECK(!km_spin_depth);fatal_calls++;
        switch(off){
        case AS02_FEC_ID:return AS02_FEC_ID_VALUE;
        case AS02_FEC_ABI:return fatal_bad_abi ? 0:AS02_FEC_ABI_VALUE;
        case AS02_FEC_FEATURES:return AS02_FEC_FEATURE_VALUE;
        case AS02_FEC_STATUS:return fatal_visible;
        case AS02_FEC_SEQUENCE:return fatal_record.sequence;
        case AS02_FEC_LAST_ACK:return fatal_ack;
        default:
            CHECK(off>=AS02_FEC_RECORD && off<AS02_FEC_BYTES && !(off&3));
            return fatal_visible ? fatal_record.word[(off-AS02_FEC_RECORD)/4]:0;
        }
    }
    return fatal_legacy_readl(p);
}
void writel(u32 value,volatile void *p)
{
    uintptr_t address=(uintptr_t)p,base=(uintptr_t)fatal_mmio;
    if(address>=base && address<base+sizeof(fatal_mmio)){
        CHECK(!km_spin_depth && address-base==AS02_FEC_ACK && fatal_visible && value==fatal_record.sequence);
        fatal_calls++;fatal_writes++;
        if(!fatal_drop_ack){fatal_ack=value;fatal_visible=0;}
        return;
    }
    fatal_legacy_writel(value,p);
}
static void fatal_retained(void)
{
    CHECK(refcount_read(&fatal_owned_mr->mapping->work_refs)==fatal_refs);
    CHECK(km.dma_frees==fatal_dma_frees && qp.initialized && vdev.qp==&qp && pd.owners==2);
    CHECK(qp.owner.cookie && qp.owner.epoch && !qp.sq_closed && qp.hw_owned);
    CHECK(!cq.pending && !recv_cq.pending && !event_visible);
}
static void fatal_handler(struct ib_event *e,void *context)
{
    struct ib_qp_attr attr={.qp_state=IB_QPS_ERR},queried;
    struct ib_qp_init_attr initial;unsigned calls=fatal_calls;
    CHECK(context==&fatal_attachment && e->device==&vdev.ibdev && e->element.qp==&qp.ibqp);
    CHECK(e->event==((fatal_case&1) ? IB_EVENT_QP_REQ_ERR:IB_EVENT_QP_ACCESS_ERR));
    CHECK(!km_spin_depth && !pthread_mutex_trylock(&vdev.lock.native));mutex_unlock(&vdev.lock);
    CHECK(!pthread_mutex_trylock(&fatal_attachment.lock.native));mutex_unlock(&fatal_attachment.lock);
    CHECK(!verbs->query_qp(&qp.ibqp,&queried,0,&initial) && queried.qp_state==IB_QPS_ERR);
    CHECK(qp.fatal_event_callback_pending && qp.fatal_event_callback_active && !qp.fatal_event_notified);
    CHECK(verbs->destroy_qp(&qp.ibqp,NULL)==-EBUSY);
    CHECK(!verbs->modify_qp(&qp.ibqp,&attr,IB_QP_STATE,NULL));
    CHECK(qp.error_progress_status==-EAGAIN && qp.error_pending && qp.error_work.work.pending);
    cm_run_work(&qp.error_work);CHECK(qp.error_progress_status==-EAGAIN && qp.error_pending);
    CHECK(as02_fatal_verbs_poll(&fatal_attachment)==-EBUSY);
    CHECK(as02_fatal_verbs_detach(&fatal_attachment)==-EBUSY && calls==fatal_calls);
    fatal_retained();fatal_handlers++;
}
static void fatal_make_record(void)
{
    unsigned partial=fatal_case&1;u32 psn=0x987654+partial;
    memset(&fatal_record,0,sizeof(fatal_record));fatal_record.sequence=1;
#define P(b,w,v) put_bits(fatal_record.word,b,w,v)
    P(992,8,7);P(780,64,1);P(892,8,partial ? 0x61:0x62);P(868,24,psn);P(844,24,psn);
    P(528,64,qp.owner.cookie);P(464,64,qp.owner.epoch);P(448,16,pd.number);P(424,24,qp.ibqp.qp_num);
    if(partial){
        P(944,8,15);P(928,16,0x6001);P(400,24,qp.ibqp.qp_num);P(384,16,pd.number);
        P(320,64,qp.owner.epoch);P(256,64,0x23456789abcdef01ULL);P(224,32,8);
        P(160,64,0xfedcba9876543210ULL);P(128,32,8193);P(104,24,0x987654);
        P(40,32,4096);P(16,24,0x987654);P(0,16,1);
    }
#undef P
}
static void fatal_empty_cleanup(void)
{
    CHECK(!verbs->dealloc_pd(&pd.ibpd,NULL));CHECK(!as02_verbs_unbind(&vdev));
    CHECK(!as02_cq_hw_detach(&cqh));CHECK(!as02_sq_pool_destroy(&sq));CHECK(!as02_mr_pool_destroy(&mrs));
    CHECK(!as02_sq_hw_detach(&receive_hw));CHECK(!as02_sq_hw_detach(&hw));CHECK(!as02_ctl_detach(&ctl_hw.control));
}
int main(int argc,char **argv)
{
    struct ib_mr *m;struct ib_sge sg;struct ib_recv_wr wr;const struct ib_recv_wr *bad=NULL;
    struct ib_send_wr send={.opcode=IB_WR_SEND};const struct ib_send_wr *bad_send=NULL;
    int ret;unsigned calls;
    if(argc>=3 && !strcmp(argv[1],"prior"))return segmented_write_post_main(argc-1,argv+1);
    CHECK(argc==2);fatal_case=strtoul(argv[1],NULL,0);CHECK(fatal_case<18);
    qp_tx_feature=retry_feature=send_feature=recv_feature=rnr_feature=recv_retire_feature=true;
    message_cq_feature=request_cq_feature=independent_queues_feature=immediate_feature=true;
    atomic_feature=atomic_access_feature=zero_feature=true;
    segmented_write_feature=fatal_case!=14;segmented_receive_feature=fatal_case==14;
    setup_verbs();
    if(fatal_case==13){fatal_visible=1;fatal_record.sequence=1;}
    if(fatal_case==17)fatal_bad_abi=1;
    ret=as02_fatal_verbs_bind(&fatal_attachment,&vdev,fatal_mmio,sizeof(fatal_mmio));
    if(fatal_case==13 || fatal_case==14 || fatal_case==17){
        CHECK(ret==(fatal_case==17 ? -ENODEV:-EBUSY) && !vdev.fatal && !fatal_writes);
        fatal_empty_cleanup();
        printf("KERNEL_FATAL_VERBS_RESULT {\"pass_test\":true,\"case\":%u,\"bind_rejected\":true,\"actual_driver_bodies\":true,\"boundaries_modeled\":true}\n",fatal_case);return 0;
    }
    CHECK(!ret && vdev.fatal==&fatal_attachment && !as02_fatal_verbs_poll(&fatal_attachment));
    if(fatal_case==16){
        CHECK(!verbs->dealloc_pd(&pd.ibpd,NULL) && !vdev.pd_count && !vdev.qp && !vdev.mr_count && !vdev.cq_count);
        CHECK(as02_verbs_unbind(&vdev)==-EBUSY);calls=fatal_calls;
        CHECK(!as02_fatal_verbs_detach(&fatal_attachment) && calls==fatal_calls && vdev.fatal==&fatal_attachment);
        CHECK(as02_verbs_unbind(&vdev)==-EBUSY && vdev.initialized && vdev.stopping);
        puts("KERNEL_FATAL_VERBS_RESULT {\"pass_test\":true,\"case\":16,\"empty_attachment_retained_after_logical_detach\":true,\"actual_driver_bodies\":true,\"boundaries_modeled\":true}");return 0;
    }
    m=register_mr();CHECK(!IS_ERR(m));quarantined_mr=m;fatal_owned_mr=container_of(m,struct as02_verbs_mr,ibmr);
    create_objects();activate();
    sg=(struct ib_sge){.addr=VA+0x210,.length=128,.lkey=m->lkey};
    wr=(struct ib_recv_wr){.wr_id=0xf123456789abc001ULL,.sg_list=&sg,.num_sge=1};
    CHECK(!verbs->post_recv(&qp.ibqp,&wr,&bad) && !bad);
    fatal_refs=refcount_read(&fatal_owned_mr->mapping->work_refs);fatal_dma_frees=km.dma_frees;
    CHECK(fatal_refs==2 && receive_model.producer==1 && !model.producer);
    qp.ibqp.event_handler=fatal_case==2 ? NULL:fatal_handler;qp.ibqp.qp_context=&fatal_attachment;
    fatal_make_record();
    if(fatal_case==4)fatal_record.word[780/32]^=1U<<(780%32);
    /* Keep the record structurally valid/nonzero so these exercise the
     * actual full Linux owner match, not the earlier envelope decoder. */
    if(fatal_case==5)fatal_record.word[(528+63)/32]^=1U<<((528+63)%32);
    if(fatal_case==6)fatal_record.word[(464+63)/32]^=1U<<((464+63)%32);
    if(fatal_case==7){fatal_record.word[449/32]^=1U<<(449%32);fatal_record.word[385/32]^=1U<<(385%32);}
    if(fatal_case==8)fatal_record.word[424/32]^=1U<<(424%32);
    if(fatal_case==9)fatal_record.word[31]|=1U<<8;
    if(fatal_case==15)fatal_record.sequence=2;
    fatal_visible=1;fatal_drop_ack=fatal_case==3 || fatal_case==12;
    ret=as02_fatal_verbs_poll(&fatal_attachment);
    if((fatal_case>=4 && fatal_case<=9) || fatal_case==15){
        CHECK(ret==(fatal_case==5 || fatal_case==6 || fatal_case==7 || fatal_case==8 ? -ESTALE:-EIO));
        CHECK(!fatal_writes && !fatal_handlers && fatal_visible && !qp.fatal_event_recorded && qp.attributes.qp_state==IB_QPS_RTS);
        fatal_retained();
        printf("KERNEL_FATAL_VERBS_RESULT {\"pass_test\":true,\"case\":%u,\"stale_or_malformed_unacked\":true,\"references_retained\":true,\"actual_driver_bodies\":true,\"boundaries_modeled\":true}\n",fatal_case);return 0;
    }
    CHECK(ret==(fatal_drop_ack ? -EAGAIN:1));
    CHECK(fatal_handlers==(fatal_case==2 ? 0:1) && qp.fatal_event_recorded && qp.fatal_event_notified);
    CHECK(!qp.fatal_event_callback_active && !qp.fatal_event_callback_pending && !fatal_attachment.notification_qp);
    CHECK(qp.attributes.qp_state==IB_QPS_ERR && qp.closing && qp.error_pending && qp.error_work.work.pending);
    CHECK(!memcmp(&qp.fatal_event.raw,&fatal_record,sizeof(fatal_record)));
    CHECK(verbs->post_recv(&qp.ibqp,&wr,&bad)==-ESHUTDOWN && bad==&wr);
    CHECK(verbs->post_send(&qp.ibqp,&send,&bad_send)==-ESHUTDOWN && bad_send==&send);
    fatal_retained();
    if(fatal_case==12){
        calls=fatal_calls;CHECK(fatal_attachment.reader.pending_ack);
        CHECK(!as02_fatal_verbs_detach(&fatal_attachment) && fatal_attachment.reader.pending_ack && calls==fatal_calls);
        CHECK(as02_fatal_verbs_poll(&fatal_attachment)==-ENODEV && calls==fatal_calls && vdev.fatal==&fatal_attachment);
    }else{
        if(fatal_drop_ack){fatal_drop_ack=0;CHECK(as02_fatal_verbs_poll(&fatal_attachment)==1 && fatal_handlers==1);}
        CHECK(!as02_fatal_verbs_poll(&fatal_attachment) && !fatal_attachment.reader.pending_ack);
        if(fatal_case==10){
            fatal_record.sequence=2;fatal_visible=1;calls=fatal_handlers;
            CHECK(as02_fatal_verbs_poll(&fatal_attachment)==-EIO && fatal_attachment.reader.uncertain && vdev.stopping);
            CHECK(calls==fatal_handlers && fatal_writes==1);
        }
    }
    /* Real old error worker tries real RNC STOP. Model withholds its reply;
     * no callback/ACK or ERR state is substituted for cancellation/drain.
     */
    ctl_drop_reply=true;cm_run_work(&qp.error_work);
    CHECK(qp.error_progress_status<0 && qp.error_pending);fatal_retained();
    CHECK(verbs->destroy_qp(&qp.ibqp,NULL)<0 && qp.initialized);fatal_retained();
    CHECK(as02_verbs_unbind(&vdev)==-EBUSY && verbs->dereg_mr(m,NULL)==-EBUSY);
    printf("KERNEL_FATAL_VERBS_RESULT {\"pass_test\":true,\"case\":%u,\"actual_driver_bodies\":true,\"boundaries_modeled\":true,\"QP_ERR\":true,\"handler_calls\":%u,\"references_retained\":true,\"no_fake_WC_STOP_unpin\":true}\n",fatal_case,fatal_handlers);
    return 0;
}
