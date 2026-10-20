/* SPDX-License-Identifier: BSD-2-Clause-Views */
/* Actual verbs/SQ/MR/CQ/CSR source, explicitly MODELED Linux/HW boundaries. */
#include "kernel_verbs_model.h"
#define main legacy_sq_cases_main
#define readl sq_readl
#define writel sq_writel
#define ktime_get sq_ktime_get
#define cpu_relax sq_cpu_relax
#include "kernel_sq_hw_cases.c"
#undef main
#undef readl
#undef writel
#undef ktime_get
#undef cpu_relax
#include "verbs.h"
#include "native_regs.h"

#ifdef AS02_DYNAMIC_DEVICE_CASES
static struct as02_verbs_device *dynamic_vdev;
#define vdev (*dynamic_vdev)
#else
static struct as02_verbs_device vdev;
#endif
static struct as02_pd pd;
static struct as02_verbs_qp qp;
static struct as02_cq cq;
static struct as02_cq recv_cq;
static struct as02_cq_router vr;
static struct as02_cq_hw cqh;
static struct as02_qp_hw qph;
static struct as02_rnic_hw ctl_hw;
static u8 cqc[AS02_CQC_BYTES],eth[AS02_NATIVE_ETH_BYTES];
static const struct ib_device_ops *verbs;
static const struct ib_device_ops *metadata_ops;
static struct as02_cq_event event;
static u32 acknowledged;
static bool event_visible,fail_mr_publish;
static u32 ctl_stage[21],ctl_reply[8],ctl_last,ctl_qp_pd,ctl_qpn,ctl_tx_psn;
static bool qp_tx_feature;
static bool retry_feature,retry_bad_epoch;
static bool send_feature;
static bool recv_feature;
static bool rnr_feature;
static bool recv_retire_feature;
static bool message_cq_feature;
static bool request_cq_feature;
static bool independent_queues_feature;
/* Optional new-profile tests; baseline15 cases keep all of these0. */
static bool immediate_feature;
static unsigned int profile_mismatch,profile_reads;
static u8 receive_mmio[AS02_SQC_BYTES];
static struct model receive_model;
static struct as02_sq_hw receive_hw;
static u8 rrp[AS02_RRP_BYTES];
static u32 rrp_stage[8],rrp_reply[8],rrp_sequence;
static u64 rrp_epoch;
static bool rrp_pending;
static bool ctl_pending,ctl_run,ctl_drop_reply;
static unsigned int ctl_commands[10],interrupts;

void ib_set_device_ops(struct ib_device *ibdev,const struct ib_device_ops *ops)
{
    CHECK(ibdev==&vdev.ibdev);
    if(ops->query_device){CHECK(verbs && !metadata_ops);metadata_ops=ops;}
    else{CHECK(!verbs);verbs=ops;}
}
u32 readl(const volatile void *p)
{
    uintptr_t address=(uintptr_t)p,base=(uintptr_t)cqc;
    u32 off;
    if(address>=(uintptr_t)receive_mmio && address<(uintptr_t)receive_mmio+sizeof(receive_mmio)){
        struct model saved=model;u32 value;
        CHECK(km_spin_depth && independent_queues_feature);model=receive_model;
        CHECK(!model_read(NULL,address-(uintptr_t)receive_mmio,&value));
        receive_model=model;model=saved;return value;
    }
    if(address>=(uintptr_t)mmio && address<(uintptr_t)mmio+sizeof(mmio))return sq_readl(p);
    if(address>=(uintptr_t)rrp && address<(uintptr_t)rrp+sizeof(rrp)){
        CHECK(!km_spin_depth);off=address-(uintptr_t)rrp;
        if(off>=0x80 && off<0xa0)return rrp_pending ? rrp_reply[(off-0x80)/4]:0;
        switch(off){
        case 0:return AS02_RRP_ID;case 4:return AS02_RRP_ABI;case 8:return 1;
        case 12:return rrp_pending ? 6:1;case 24:return rrp_sequence;case 28:return 4000;
        case 0xa0:return rrp_epoch^(retry_bad_epoch ? 1:0);
        case 0xa4:return rrp_epoch>>32;case 0xa8:return 0;
        default:CHECK(0);return 0;
        }
    }
    if(address>=(uintptr_t)eth && address<(uintptr_t)eth+sizeof(eth)){
        off=address-(uintptr_t)eth;
        switch(off){
        case AS02_ETH_ID:return AS02_ETH_ID_VALUE;
        case AS02_ETH_ABI:return AS02_ETH_ABI_VALUE;
        case AS02_ETH_EPOCH:return 1;
        case AS02_ETH_STATUS:return AS02_ETH_ST_ENABLED|AS02_ETH_ST_COMMITTED;
        case AS02_ETH_ACTIVE:return 1;
        case AS02_ETH_ACTIVE+4:return 0x0200;
        case AS02_ETH_ACTIVE+8:return 0x00000002;
        case AS02_ETH_ACTIVE+12:return 0x0200;
        case AS02_ETH_ACTIVE+16:return 0xc0000201;
        case AS02_ETH_ACTIVE+20:return 1;
        default:CHECK(0);return 0;
        }
    }
    CHECK(km_spin_depth && address>=base && address<base+sizeof(cqc));off=address-base;
    if(off>=AS02_CQC_CONTEXT && off<AS02_CQC_CONTEXT+76)
        return event_visible ? event.context[(off-AS02_CQC_CONTEXT)/4]:0;
    switch(off){
    case AS02_CQC_ID:return AS02_CQC_ID_VALUE;
    case AS02_CQC_ABI:return AS02_CQC_ABI_VALUE;
    case AS02_CQC_FEATURES:return immediate_feature && profile_mismatch!=4 ? AS02_CQC_IMMEDIATE_FEATURE_VALUE:
        message_cq_feature ? AS02_CQC_MESSAGE_FEATURE_VALUE:AS02_CQC_FEATURE_VALUE;
    case AS02_CQC_CONTEXT_EXTENSION:CHECK(immediate_feature);return event_visible ? event.context_extension:0;
    case AS02_CQC_NOTIFICATION_FLAGS:CHECK(immediate_feature);return event_visible ? event.notification_flags:0;
    case AS02_CQC_NOTIFICATION:CHECK(immediate_feature);return event_visible ? event.notification:0;
    case AS02_CQC_STATUS:return event_visible ? 3:0;
    case AS02_CQC_LAST_ACK:return acknowledged;
    case AS02_CQC_SEQUENCE:return event_visible ? event.sequence:acknowledged;
    case AS02_CQC_PROOFS:return event.proofs;
    case AS02_CQC_COOKIE_LO:return event.cookie;
    case AS02_CQC_COOKIE_HI:return event.cookie>>32;
    case AS02_CQC_WC_STATUS:return event.status;
    case AS02_CQC_RECEIVED_BYTES:return event.received_bytes;
    default:CHECK(0);return 0;
    }
}
void writel(u32 value,volatile void *p)
{
    uintptr_t address=(uintptr_t)p;
    if(address>=(uintptr_t)receive_mmio && address<(uintptr_t)receive_mmio+sizeof(receive_mmio)){
        struct model saved=model;
        CHECK(km_spin_depth && independent_queues_feature);model=receive_model;
        CHECK(!model_write(NULL,address-(uintptr_t)receive_mmio,value));
        receive_model=model;model=saved;return;
    }
    if(address>=(uintptr_t)mmio && address<(uintptr_t)mmio+sizeof(mmio)){sq_writel(value,p);return;}
    if(address>=(uintptr_t)rrp && address<(uintptr_t)rrp+sizeof(rrp)){
        u32 off=address-(uintptr_t)rrp;CHECK(!km_spin_depth);
        if(off>=0x40 && off<=0x5c){rrp_stage[(off-0x40)/4]=value;return;}
        if(off==0x10){
            CHECK(!rrp_pending && value==rrp_sequence+1 && value==rrp_stage[0]);
            /* Explicit hardware MODEL uses its actual SQC allocated owner,
             * not a driver shadow as a substitute for the trusted query. */
            CHECK(model.active && rrp_stage[1]==model.reply[2] && rrp_stage[2]==model.reply[3] &&
                pair(rrp_stage+6)==pair(model.reply+6));
            memcpy(rrp_reply,rrp_stage,sizeof(rrp_reply));rrp_epoch=pair(model.reply+4);
            rrp_sequence=value;rrp_pending=true;return;
        }
        CHECK(off==0x14 && rrp_pending && value==rrp_sequence);rrp_pending=false;return;
    }
    CHECK(km_spin_depth && address==(uintptr_t)cqc+AS02_CQC_ACK && event_visible && value==event.sequence);
    event_visible=false;acknowledged=value;
}
ktime_t ktime_get(void) { return km_spin_depth ? sq_ktime_get():model.now++; }
void cpu_relax(void) { if(km_spin_depth)sq_cpu_relax();else model.relaxes++; }
static int control_read(void *unused,u32 off,u32 *out)
{
    (void)unused;CHECK(!km_spin_depth);*out=0;
    if(off>=AS02_CTL_STAGE && off<AS02_CTL_STAGE+84)*out=ctl_stage[(off-AS02_CTL_STAGE)/4];
    else if(off>=AS02_CTL_REPLY_SEQ && off<=AS02_CTL_REPLY_FLAGS)*out=ctl_reply[(off-AS02_CTL_REPLY_SEQ)/4];
    else switch(off){
    case AS02_CTL_ID:*out=AS02_CTL_ID_VALUE;break;
    case AS02_CTL_ABI:*out=AS02_CTL_ABI_VALUE;break;
    case AS02_CTL_FEATURES:
        profile_reads++;
        *out=immediate_feature ? ((profile_mismatch==1 || (profile_mismatch==5 && profile_reads>1)) ? 511:1023):
            (qp_tx_feature ? 3:1)|(send_feature ? 4:0)|(recv_feature ? 8:0)|(rnr_feature ? 16:0)|(recv_retire_feature ? 32:0)|(message_cq_feature ? 64:0)|(request_cq_feature ? 128:0)|(independent_queues_feature ? 256:0);break;
    case AS02_CTL_STATUS:*out=AS02_ST_PARENT_DRAINED|AS02_ST_ENDPOINT_QUIET|
        (ctl_run ? AS02_ST_EPOCH|AS02_ST_QP|AS02_ST_RUN:AS02_ST_PAUSED)|
        (ctl_pending ? (ctl_drop_reply ? AS02_ST_BUSY:AS02_ST_REPLY):AS02_ST_READY);break;
    case AS02_CTL_LAST_SEQUENCE:case AS02_CTL_LAST_QUEUED:*out=ctl_last;break;
    case AS02_CTL_ENTRY_STATE:break;
    default:CHECK(0);
    }
    return 0;
}
static int control_write(void *unused,u32 off,u32 value)
{
    u32 op;
    (void)unused;CHECK(!km_spin_depth);
    if(off>=AS02_CTL_STAGE && off<AS02_CTL_STAGE+84){ctl_stage[(off-AS02_CTL_STAGE)/4]=value;return 0;}
    if(off==AS02_CTL_REPLY_ACK){CHECK(ctl_pending && value==ctl_last);ctl_pending=false;return 0;}
    CHECK(off==AS02_CTL_DOORBELL && value==1 && !ctl_pending);
    op=ctl_stage[AS02_W_OP];CHECK(op>=AS02_CMD_QP && op<=(qp_tx_feature ? AS02_CMD_QP_TX:AS02_CMD_STOP));
    ctl_commands[op]++;ctl_last=ctl_stage[AS02_W_SEQUENCE];ctl_pending=true;
    ctl_reply[0]=ctl_last;ctl_reply[1]=op;ctl_reply[2]=ctl_stage[AS02_W_COOKIE_LO];
    ctl_reply[3]=ctl_stage[AS02_W_COOKIE_HI];ctl_reply[4]=0;ctl_reply[5]=0;ctl_reply[6]=0;
    ctl_reply[7]=op==AS02_CMD_STOP ? AS02_PROOF_DMA_DRAINED:0;
    if(op==AS02_CMD_STOP)ctl_run=false;
    if(op==AS02_CMD_QP){CHECK(!ctl_run);ctl_qp_pd=ctl_stage[AS02_W_PD];ctl_qpn=ctl_stage[AS02_W_QP];}
    if(op==AS02_CMD_RUN){CHECK(ctl_qp_pd);ctl_run=true;}
    if(op==AS02_CMD_QP_TX){CHECK(ctl_stage[AS02_W_QP]==ctl_qpn && ctl_stage[AS02_W_PD]==ctl_qp_pd);
        CHECK(!ctl_stage[AS02_W_RX_PSN] && !ctl_stage[AS02_W_LOCAL_IP] && !ctl_stage[AS02_W_PEER_IP]);
        ctl_tx_psn=ctl_stage[AS02_W_TX_PSN];}
    return 0;
}
static u64 control_time(void *unused) { (void)unused;return model.now++; }
static void control_wait(void *unused) { (void)unused;CHECK(!km_spin_depth); }
static const struct as02_ctl_transport cio={control_read,control_write,control_time,control_wait};
static int mr_publish_fault(void *unused,const struct as02_mr_layout *m,struct as02_mr_publish_proof *proof)
{ return fail_mr_publish ? -ETIMEDOUT:publish_mr(unused,m,proof); }
static const struct as02_mr_hw_ops mmr_ops={epoch,mr_publish_fault,revoke_mr};
static void irq(struct ib_cq *c,void *unused)
{ (void)unused;CHECK(!km_spin_depth && (c==&cq.ibcq || c==&recv_cq.ibcq));interrupts++; }
static void setup_verbs(void)
{
    const u64 epochs[8]={0};
    fresh();atomic_store(&vdev.ibdev.dev.references,1);atomic_store(&dma_dev.references,1);
    if(immediate_feature && profile_mismatch!=2)model.features=AS02_SQC_IMMEDIATE_FEATURE_VALUE;
    CHECK(!as02_cq_router_init(&vr));
    CHECK(!as02_sq_hw_init(&hw,mmio,sizeof(mmio),30,as02_cq_publish,&vr));
    if(independent_queues_feature){
        receive_model=model;receive_model.id=AS02_RQC_ID_VALUE;
        if(immediate_feature)receive_model.features=profile_mismatch==3 ? 3:AS02_RQC_IMMEDIATE_FEATURE_VALUE;
        CHECK(!as02_sq_hw_init_receive(&receive_hw,&hw,receive_mmio,sizeof(receive_mmio),30));
    }
    CHECK(!as02_mr_pool_init(&mrs,&vdev.ibdev,&mmr_ops,NULL,0));CHECK(!as02_mr_pool_start_epoch(&mrs,0));
    CHECK(!as02_sq_pool_init(&sq,&mrs,&dma_dev,&as02_sqc_sq_hw_ops,&hw,epochs));
    CHECK(!as02_cq_hw_init(&cqh,&sq,cqc,sizeof(cqc)));
    mutex_init(&ctl_hw.lock);ctl_hw.registers=eth;
    CHECK(!as02_ctl_init(&ctl_hw.control,&cio,NULL,30));CHECK(!as02_qp_hw_init(&qph,&ctl_hw));
    if(retry_feature)CHECK(!as02_qp_hw_enable_retry(&qph,rrp,sizeof(rrp),30));
    if(profile_mismatch){
        CHECK(as02_verbs_bind(&vdev,&mrs,&sq,&cqh,&qph,&vr,eth,sizeof(eth))==
            (profile_mismatch==5 ? -ESTALE:-EOPNOTSUPP));
        CHECK(!vdev.initialized && !sq.profile_bound && !sq.wqe_profile && !mrs.pd_zero_reserved);
        return;
    }
    CHECK(!as02_verbs_bind(&vdev,&mrs,&sq,&cqh,&qph,&vr,eth,sizeof(eth)));
    CHECK(verbs==&as02_verbs_ops && verbs->size_ib_pd==sizeof(pd) && verbs->size_ib_qp==sizeof(qp));
    pd.ibpd.device=&vdev.ibdev;CHECK(!verbs->alloc_pd(&pd.ibpd,NULL));CHECK(pd.number==1);
    CHECK(IS_ERR(as02_user_mr_prepare(&mrs,0x10000,VA,65,0,7,15)));
}
static struct ib_mr *register_mr(void)
{ return verbs->reg_user_mr(&pd.ibpd,0x10003,8192,VA,7,NULL,NULL); }
static void create_objects(void)
{
    struct ib_cq_init_attr ca={.cqe=2};
    struct ib_qp_init_attr qa={.send_cq=&cq.ibcq,.recv_cq=&cq.ibcq,.cap={.max_send_wr=2,.max_send_sge=1},
        .sq_sig_type=IB_SIGNAL_ALL_WR,.qp_type=IB_QPT_RC};
    if(recv_feature){qa.cap.max_recv_wr=2;qa.cap.max_recv_sge=1;}
    cq.ibcq.device=&vdev.ibdev;cq.ibcq.comp_handler=irq;
    CHECK(!verbs->create_cq(&cq.ibcq,&ca,NULL));
    if(message_cq_feature){
        recv_cq.ibcq.device=&vdev.ibdev;recv_cq.ibcq.comp_handler=irq;
        qa.recv_cq=&recv_cq.ibcq;
        /* A real distinct recv_cq must be initialized and attached before
         * create_qp can expose any queue or PD ownership. */
        qp.ibqp.device=&vdev.ibdev;qp.ibqp.pd=&pd.ibpd;
        CHECK(verbs->create_qp(&qp.ibqp,&qa,NULL)==-EINVAL && !sq.queue_count && pd.owners==1);
        CHECK(!verbs->create_cq(&recv_cq.ibcq,&ca,NULL));
    }
    qp.ibqp.device=&vdev.ibdev;qp.ibqp.pd=&pd.ibpd;
    CHECK(!verbs->create_qp(&qp.ibqp,&qa,NULL));CHECK(qp.ibqp.qp_num==2 && pd.owners==2);
}
static void activate(void)
{
    struct ib_gid_attr sgid={.device=&vdev.ibdev,.port_num=1,.gid_type=IB_GID_TYPE_ROCE_UDP_ENCAP,
        .gid={.raw={0,0,0,0,0,0,0,0,0,0,255,255,192,0,2,1}}};
    struct ib_qp_attr a={.qp_state=IB_QPS_INIT,.port_num=1,.qp_access_flags=6};
    CHECK(!verbs->modify_qp(&qp.ibqp,&a,IB_QP_STATE|IB_QP_PORT|IB_QP_PKEY_INDEX|IB_QP_ACCESS_FLAGS,NULL));
    memset(&a,0,sizeof(a));a.qp_state=IB_QPS_RTR;a.path_mtu=IB_MTU_4096;a.dest_qp_num=0x123456;
    a.rq_psn=0x345678;a.max_dest_rd_atomic=1;
    a.ah_attr=(struct rdma_ah_attr){.type=RDMA_AH_ATTR_TYPE_ROCE,.port_num=1,.ah_flags=IB_AH_GRH,
        .dmac={2,0,0,0,0,2},.grh={.dgid={.raw={0,0,0,0,0,0,0,0,0,0,255,255,192,0,2,2}},.sgid_attr=&sgid,.hop_limit=100}};
    CHECK(!verbs->modify_qp(&qp.ibqp,&a,IB_QP_STATE|IB_QP_AV|IB_QP_PATH_MTU|IB_QP_DEST_QPN|
        IB_QP_RQ_PSN|IB_QP_MAX_DEST_RD_ATOMIC|IB_QP_MIN_RNR_TIMER,NULL));
    CHECK(ctl_run && ctl_qp_pd==pd.number && qph.owner.rx_psn==0x345678 && qph.owner.tx_psn==0);
    a=(struct ib_qp_attr){.qp_state=IB_QPS_RTS,.max_rd_atomic=1};
    if(retry_feature){
        int ret;
        a.sq_psn=0x89abcd;a.timeout=14;a.retry_cnt=3;a.rnr_retry=7;
        ret=verbs->modify_qp(&qp.ibqp,&a,IB_QP_STATE|IB_QP_SQ_PSN|IB_QP_MAX_QP_RD_ATOMIC|
            IB_QP_TIMEOUT|IB_QP_RETRY_CNT|IB_QP_RNR_RETRY,NULL);
        if(retry_bad_epoch){CHECK(ret==-EIO && qp.attributes.qp_state==IB_QPS_ERR);return;}
        CHECK(!ret && !rrp_pending && !qph.retry.pending && !qph.retry.uncertain && rrp_sequence==1);
        CHECK(rrp_reply[3]==14 && rrp_reply[4]==3 && rrp_reply[5]==7 && rrp_epoch==qp.owner.epoch);
        CHECK(qp.attributes.timeout==14 && qp.attributes.retry_cnt==3 && qp.attributes.rnr_retry==7);
        return;
    }
    CHECK(verbs->modify_qp(&qp.ibqp,&a,IB_QP_STATE|IB_QP_SQ_PSN|IB_QP_MAX_QP_RD_ATOMIC|IB_QP_TIMEOUT|IB_QP_RETRY_CNT|IB_QP_RNR_RETRY,NULL)==-EOPNOTSUPP);
    CHECK(qp.attributes.qp_state==IB_QPS_RTR); // Do NOT fake complete standard RC capability.
    if(qp_tx_feature)a.sq_psn=0x89abcd;
    CHECK(!verbs->modify_qp(&qp.ibqp,&a,IB_QP_STATE|IB_QP_SQ_PSN|IB_QP_MAX_QP_RD_ATOMIC,NULL));
    if(qp_tx_feature)CHECK(ctl_tx_psn==0x89abcd && qph.owner.tx_psn==0x89abcd &&
        qph.owner.rx_psn==0x345678 && ctl_commands[AS02_CMD_QP]==1 && ctl_commands[AS02_CMD_QP_TX]==1);
}
static void put_bits(u32 *words,u32 first,u32 width,u64 value)
{
    u32 i;
    for(i=0;i<width;i++)if(value&(1ULL<<i))words[(first+i)/32]|=1U<<((first+i)%32);
}
static void hardware_completion(unsigned int i)
{
    const struct as02_wqe *w=&model.observed[i];
    CHECK(!event_visible && i==acknowledged && w->sequence==i+1);
    memset(&event,0,sizeof(event));event.sequence=i+1;event.proofs=15;event.cookie=qp.owner.cookie;
    event.received_bytes=w->opcode==AS02_WQE_RECV ? 65:0;
#define P(start,width,value) put_bits(event.context,start,width,value)
    P(0,2,3);P(20,32,w->remote_key);P(52,64,w->remote_address);P(116,64,w->local_address-VA);
    P(180,64,w->local_address);P(244,32,w->local_key);P(276,32,w->length);P(308,16,w->flags);
    P(324,16,w->opcode);P(340,16,i+1);P(356,16,pd.number);P(372,24,qp.ibqp.qp_num);
    P(396,64,w->epoch);P(460,64,w->sequence);P(524,64,w->wr_id);
    P(588,20,w->immediate&0xfffff);event.context_extension=w->immediate>>20;
#undef P
    event_visible=true; // Explicit model: memory, wire AND genuine internal core drain.
}
static void cleanup_verbs(struct ib_mr *m)
{
    CHECK(!verbs->destroy_qp(&qp.ibqp,NULL));CHECK(!ctl_run && !ctl_qp_pd && ctl_qpn==2 && !qph.owned);
    if(message_cq_feature)CHECK(!verbs->destroy_cq(&recv_cq.ibcq,NULL));
    CHECK(!verbs->destroy_cq(&cq.ibcq,NULL));CHECK(!verbs->dereg_mr(m,NULL));
    CHECK(!verbs->dealloc_pd(&pd.ibpd,NULL));CHECK(!as02_verbs_unbind(&vdev));
    CHECK(!as02_cq_hw_detach(&cqh));CHECK(!as02_sq_pool_destroy(&sq));CHECK(!as02_mr_pool_destroy(&mrs));
    if(independent_queues_feature)CHECK(!as02_sq_hw_detach(&receive_hw));
    CHECK(!as02_sq_hw_detach(&hw));CHECK(!as02_ctl_detach(&ctl_hw.control));
    CHECK(!atomic_load(&km.heap_live) && !atomic_load(&km.umem_live) && !atomic_load(&km.module_refs));
    CHECK(km.dma_allocs==km.dma_frees && atomic_load(&vdev.ibdev.dev.references)==1 && atomic_load(&dma_dev.references)==1);
}
#ifndef AS02_VERBS_MAIN
#define AS02_VERBS_MAIN main
#endif
int AS02_VERBS_MAIN(int argc,char **argv)
{
    struct ib_mr *m;
    struct as02_verbs_mr *owned;
    struct ib_sge s;
    struct ib_rdma_wr first,second;
    struct ib_send_wr unsupported={.opcode=IB_WR_SEND};
    const struct ib_send_wr *bad=(void *)1;
    struct ib_wc wc[2];
    struct ib_qp_attr queried;
    struct ib_qp_init_attr initial;
    unsigned int scenario;
    CHECK(argc==2);scenario=strtoul(argv[1],NULL,0);CHECK(scenario<15);qp_tx_feature=scenario>=5;
    retry_feature=scenario>=6;retry_bad_epoch=scenario==7;send_feature=scenario>=8;recv_feature=scenario>=9;
    rnr_feature=scenario>=10;recv_retire_feature=scenario>=11;message_cq_feature=scenario>=12;
    request_cq_feature=scenario>=13;independent_queues_feature=scenario==14;
    setup_verbs();fail_mr_publish=scenario==2;
    m=register_mr();
    if(scenario==2){
        CHECK(IS_ERR(m) && PTR_ERR(m)==-ETIMEDOUT && vdev.orphan_mrs[0] && pd.owners==1);
        CHECK(verbs->dealloc_pd(&pd.ibpd,NULL)==-EBUSY && as02_verbs_unbind(&vdev)==-EBUSY);
        CHECK(!as02_verbs_reap(&vdev));CHECK(!pd.owners && !vdev.orphan_mrs[0]);
        CHECK(!verbs->dealloc_pd(&pd.ibpd,NULL));CHECK(!as02_verbs_unbind(&vdev));
        CHECK(!as02_cq_hw_detach(&cqh));CHECK(!as02_sq_pool_destroy(&sq));CHECK(!as02_mr_pool_destroy(&mrs));
        CHECK(!atomic_load(&km.heap_live) && !atomic_load(&km.umem_live));
        puts("KERNEL_VERBS_RESULT {\"pass_test\":true,\"failed_MR_retained_until_real_cleanup_model\":true}");return 0;
    }
    CHECK(!IS_ERR(m) && m->lkey==8 && m->rkey==8);owned=container_of(m,struct as02_verbs_mr,ibmr);
    if(scenario==4){
        struct ib_cq_init_attr ca={.cqe=2};
        struct ib_qp_init_attr qa={.send_cq=&cq.ibcq,.recv_cq=&cq.ibcq,
            .cap={.max_send_wr=2,.max_send_sge=1},.sq_sig_type=IB_SIGNAL_ALL_WR,.qp_type=IB_QPT_RC};
        struct as02_sqc_reply late;
        cq.ibcq.device=&vdev.ibdev;CHECK(!verbs->create_cq(&cq.ibcq,&ca,NULL));
        qp.ibqp.device=&vdev.ibdev;qp.ibqp.pd=&pd.ibpd;model.corrupt_word=7;
        CHECK(verbs->create_qp(&qp.ibqp,&qa,NULL)==-EPROTO && vdev.orphan_sq.cookie && pd.owners==2);
        CHECK(!vdev.qp && !vr.qp[2] && km.dma_frees==0 && as02_verbs_reap(&vdev)==-EBUSY);
        model.corrupt_word=-1;CHECK(!as02_sq_hw_reconcile(&hw,&late));
        CHECK(!as02_verbs_reap(&vdev) && !vdev.orphan_sq.cookie && pd.owners==1 && km.dma_frees==1);
        CHECK(!verbs->destroy_cq(&cq.ibcq,NULL));
        CHECK(!verbs->dereg_mr(m,NULL));CHECK(!verbs->dealloc_pd(&pd.ibpd,NULL));
        CHECK(!as02_verbs_unbind(&vdev));CHECK(!as02_cq_hw_detach(&cqh));
        CHECK(!as02_sq_pool_destroy(&sq));CHECK(!as02_mr_pool_destroy(&mrs));
        CHECK(!atomic_load(&km.heap_live) && !atomic_load(&km.umem_live));
        puts("KERNEL_VERBS_RESULT {\"pass_test\":true,\"failed_QP_creation_owns_cleanup_handle_and_PD\":true}");return 0;
    }
    create_objects();activate();
    if(independent_queues_feature){
        struct ib_sge sg={.addr=VA+0x210,.length=128,.lkey=m->lkey};
        struct ib_recv_wr receive={.sg_list=&sg,.num_sge=1};
        struct ib_send_wr send={.sg_list=&sg,.num_sge=1,.opcode=IB_WR_SEND};
        const struct ib_recv_wr *bad_recv=NULL;
        CHECK(ctl_hw.control.features==511 && km.dma_allocs==2);
        CHECK(!verbs->query_qp(&qp.ibqp,&queried,0,&initial));
        CHECK(initial.cap.max_send_wr==2 && initial.cap.max_recv_wr==2);
        CHECK(pair(model.reply+6)!=pair(receive_model.reply+6) &&
            pair(model.reply+8)!=pair(receive_model.reply+8));
        for(unsigned int seq=1;seq<=2;seq++){
            sg.length=128;receive.wr_id=0xf123456789abc000ULL+seq;
            CHECK(!verbs->post_recv(&qp.ibqp,&receive,&bad_recv) && !bad_recv);
            CHECK(model.producer==seq-1 && receive_model.producer==seq &&
                refcount_read(&owned->mapping->work_refs)==2);
            sg.length=65;send.wr_id=0xf223456789abc000ULL+seq;
            CHECK(!verbs->post_send(&qp.ibqp,&send,&bad) && !bad);
            CHECK(model.observed[seq-1].sequence==seq && receive_model.observed[seq-1].sequence==seq);
            for(unsigned int direction=0;direction<2;direction++){
                const struct as02_wqe *w=direction ? &receive_model.observed[seq-1]:&model.observed[seq-1];
                CHECK(!event_visible);memset(&event,0,sizeof(event));
                event.sequence=acknowledged+1;event.proofs=15;
                event.cookie=direction ? pair(receive_model.reply+6):qp.owner.cookie;
                event.received_bytes=direction ? 65:0;
#define P(start,width,value) put_bits(event.context,start,width,value)
                P(0,2,3);P(116,64,0x210);P(180,64,w->local_address);P(244,32,w->local_key);
                P(276,32,w->length);P(308,16,w->flags);P(324,16,w->opcode);
                P(340,16,seq*2-(direction ? 1:0));P(356,16,pd.number);P(372,24,qp.ibqp.qp_num);
                P(396,64,w->epoch);P(460,64,w->sequence);P(524,64,w->wr_id);
#undef P
                event_visible=true; // Explicit completion producer model.
                CHECK(verbs->poll_cq(direction ? &recv_cq.ibcq:&cq.ibcq,1,wc)==1);
                CHECK(wc[0].wr_id==w->wr_id && wc[0].opcode==(direction ? IB_WC_RECV:IB_WC_SEND) &&
                    wc[0].byte_len==(direction ? 65U:0U));
                CHECK(refcount_read(&owned->mapping->work_refs)==(direction ? 1:2));
                CHECK(!cq.pending && !recv_cq.pending);
            }
        }
        cleanup_verbs(m);CHECK(!model.active && !receive_model.active && km.dma_frees==2);
        puts("KERNEL_VERBS_RESULT {\"pass_test\":true,\"actual_callbacks\":true,\"independent_physical_queues\":true,\"SEND_before_RECV_same_WQE_sequence\":true,\"SEND_completions\":2,\"RECV_completions\":2,\"hardware_completion_producer_modeled\":true}");
        return 0;
    }
    if(message_cq_feature){
        struct ib_sge sg={.addr=VA+0x210,.length=128,.lkey=m->lkey};
        struct ib_recv_wr receive={.wr_id=0xf123456789abc001ULL,.sg_list=&sg,.num_sge=1};
        const struct ib_recv_wr *bad_recv=NULL;
        CHECK(qp.ibqp.recv_cq==&recv_cq.ibcq && cq.queue_refs==1 && recv_cq.queue_refs==1);
        CHECK(!verbs->req_notify_cq(&recv_cq.ibcq,IB_CQ_NEXT_COMP));
        CHECK(!verbs->post_recv(&qp.ibqp,&receive,&bad_recv) && !bad_recv);
        receive.wr_id++;
        CHECK(!verbs->post_recv(&qp.ibqp,&receive,&bad_recv) && !bad_recv);
        CHECK(verbs->post_recv(&qp.ibqp,&receive,&bad_recv)==-ENOSPC && bad_recv==&receive);
        CHECK(refcount_read(&owned->mapping->work_refs)==3 && !cq.pending && !recv_cq.pending);
        /* Explicit completion-producer model, actual driver from full-event
         * decode through real callbacks, reference release and quota reuse. */
        hardware_completion(0);cm_run_work(&cqh.poll_work);irq_work_sync(&recv_cq.notify);
        CHECK(interrupts==1 && !verbs->poll_cq(&cq.ibcq,2,wc));
        CHECK(verbs->poll_cq(&recv_cq.ibcq,2,wc)==1 && wc[0].wr_id==receive.wr_id-1 &&
            wc[0].opcode==IB_WC_RECV && wc[0].byte_len==65 && wc[0].qp==&qp.ibqp);
        CHECK(refcount_read(&owned->mapping->work_refs)==2 && model.observed[0].length==128);
        receive.wr_id++;
        CHECK(!verbs->post_recv(&qp.ibqp,&receive,&bad_recv) && !bad_recv && model.observed_count==3);
        CHECK(refcount_read(&owned->mapping->work_refs)==3 && model.observed[2].length==128);
        for(unsigned int i=1;i<3;i++){
            hardware_completion(i);
            CHECK(verbs->poll_cq(&recv_cq.ibcq,2,wc)==1 && wc[0].wr_id==0xf123456789abc001ULL+i &&
                wc[0].opcode==IB_WC_RECV && wc[0].byte_len==65 && wc[0].qp==&qp.ibqp && !cq.pending);
        }
        /* The sender still completes into send_cq with a separate WC opcode. */
        struct ib_send_wr send={.wr_id=77,.sg_list=&sg,.num_sge=1,.opcode=IB_WR_SEND};
        CHECK(!verbs->post_send(&qp.ibqp,&send,&bad) && !bad);
        hardware_completion(3);
        CHECK(verbs->poll_cq(&cq.ibcq,2,wc)==1 && wc[0].opcode==IB_WC_SEND && wc[0].wr_id==77 &&
            wc[0].byte_len==0 && !recv_cq.pending);
        CHECK(refcount_read(&owned->mapping->work_refs)==1);cleanup_verbs(m);
        puts("KERNEL_VERBS_RESULT {\"pass_test\":true,\"actual_callbacks\":true,\"RECV_completions\":3,\"SEND_completions\":1,\"distinct_recv_cq\":true,\"posted_capacity\":128,\"received_bytes\":65,\"receive_quota_reused\":true,\"hardware_completion_producer_modeled\":true}");
        return 0;
    }
    if(scenario>=9){
        CHECK(ctl_hw.control.features==(recv_retire_feature ? 63:rnr_feature ? 31:15));
        struct ib_sge sg={.addr=VA+0x210,.length=128,.lkey=m->lkey};
        struct ib_recv_wr invalid={.wr_id=99,.sg_list=&sg,.num_sge=2};
        struct ib_recv_wr first_recv={.wr_id=0xf123456789abc001ULL,.sg_list=&sg,.num_sge=1,.next=&invalid};
        const struct ib_recv_wr *bad_recv=NULL;
        CHECK(verbs->post_recv(&qp.ibqp,&first_recv,&bad_recv)==-EOPNOTSUPP && bad_recv==&invalid);
        CHECK(model.observed_count==1 && model.observed[0].opcode==AS02_WQE_RECV &&
            model.observed[0].length==128 && !model.observed[0].remote_address && !model.observed[0].remote_key &&
            model.observed[0].flags==1 && refcount_read(&owned->mapping->work_refs)==2);
        invalid.num_sge=1;CHECK(!verbs->post_recv(&qp.ibqp,&invalid,&bad_recv) && !bad_recv);
        CHECK(model.observed_count==2 && refcount_read(&owned->mapping->work_refs)==3);
        CHECK(verbs->post_recv(&qp.ibqp,&invalid,&bad_recv)==-ENOSPC && bad_recv==&invalid);
        CHECK(!verbs->poll_cq(&cq.ibcq,2,wc) && refcount_read(&owned->mapping->work_refs)==3);
        CHECK(verbs->dereg_mr(m,NULL)==-EBUSY && verbs->destroy_cq(&cq.ibcq,NULL)==-EBUSY &&
            as02_verbs_unbind(&vdev)==-EBUSY && qp.initialized && pd.owners==2 && sq.queue_count==1);
        puts("KERNEL_VERBS_RESULT {\"pass_test\":true,\"real_post_recv_coherent_WQEs\":true,\"exact_bad_wr\":true,\"receive_quota\":true,\"CQ_unproved_references_retained\":true}");
        fflush(stdout);_Exit(0);
    }
    if(scenario==8){
        struct ib_sge sg={.addr=VA+0x210,.length=65,.lkey=m->lkey};
        /* Exact-sized base WR on the ASan stack: no RDMA extension to read. */
        struct ib_send_wr send={.wr_id=0xf123456789abc001ULL,.sg_list=&sg,.num_sge=1,.opcode=IB_WR_SEND};
        CHECK(!verbs->post_send(&qp.ibqp,&send,&bad) && !bad && model.observed_count==1);
        CHECK(model.observed[0].opcode==AS02_WQE_SEND && !model.observed[0].remote_address &&
            !model.observed[0].remote_key && model.observed[0].local_address==sg.addr &&
            model.observed[0].local_key==m->lkey && model.observed[0].flags==AS02_WQE_SIGNALED);
        CHECK(refcount_read(&owned->mapping->work_refs)==2);
        hardware_completion(0);CHECK(verbs->poll_cq(&cq.ibcq,2,wc)==1 && wc[0].wr_id==send.wr_id &&
            wc[0].opcode==IB_WC_SEND && wc[0].byte_len==0 && wc[0].qp==&qp.ibqp);
        CHECK(refcount_read(&owned->mapping->work_refs)==1);cleanup_verbs(m);
        puts("KERNEL_VERBS_RESULT {\"pass_test\":true,\"SEND_base_WR_no_overread\":true,\"real_SQ_and_CQ_path\":true,\"modeled_core_completion\":true}");return 0;
    }
    if(scenario==7){
        CHECK(qp.initialized && qp.closing && qph.uncertain && qph.retry.pending && qph.retry.uncertain &&
            qph.retry.held.cookie==qp.owner.cookie && qph.retry.held.epoch==qp.owner.epoch &&
            rrp_pending && pd.owners==2 && sq.queue_count==1 && !model.observed_count && !km.dma_frees);
        CHECK(as02_verbs_unbind(&vdev)==-EBUSY && verbs->destroy_cq(&cq.ibcq,NULL)==-EBUSY);
        CHECK(verbs->destroy_qp(&qp.ibqp,NULL)==-EBUSY && qph.owned && qp.initialized &&
            pd.owners==2 && sq.queue_count==1 && !km.dma_frees && rrp_pending);
        puts("KERNEL_VERBS_RESULT {\"pass_test\":true,\"retry_bad_epoch_retains_full_SQ_PD_CQ_owner\":true}");
        fflush(stdout);_Exit(0);
    }
    CHECK(!verbs->query_qp(&qp.ibqp,&queried,IB_QP_STATE|IB_QP_CAP|IB_QP_DEST_QPN,&initial));
    CHECK(queried.qp_state==IB_QPS_RTS && queried.cur_qp_state==IB_QPS_RTS &&
        queried.dest_qp_num==0x123456 && initial.cap.max_send_wr==2 && initial.send_cq==&cq.ibcq);
    CHECK(queried.sq_psn==(qp_tx_feature ? 0x89abcd:0));
    if(retry_feature){
        CHECK(!verbs->query_qp(&qp.ibqp,&queried,IB_QP_TIMEOUT|IB_QP_RETRY_CNT|IB_QP_RNR_RETRY,&initial));
        CHECK(queried.timeout==14 && queried.retry_cnt==3 && queried.rnr_retry==7);
    } else CHECK(verbs->query_qp(&qp.ibqp,&queried,IB_QP_TIMEOUT,&initial)==-EOPNOTSUPP);
    if(scenario==3){
        ctl_drop_reply=true;
        CHECK(verbs->destroy_qp(&qp.ibqp,NULL)==-ETIMEDOUT);
        CHECK(qp.initialized && pd.owners==2 && sq.queue_count==1 && km.dma_frees==0);
        CHECK(verbs->dealloc_pd(&pd.ibpd,NULL)==-EBUSY && verbs->destroy_cq(&cq.ibcq,NULL)==-EBUSY);
        puts("KERNEL_VERBS_RESULT {\"pass_test\":true,\"unknown_QP_close_retains_SQ_PD_CQ\":true}");
        fflush(stdout);_Exit(0);
    }
    s=(struct ib_sge){.addr=VA+0x210,.length=65,.lkey=m->lkey};
    first=(struct ib_rdma_wr){.wr={.wr_id=0xf123456789abc001ULL,.sg_list=&s,.num_sge=1,.opcode=IB_WR_RDMA_READ},
        .remote_addr=0xe23456789abcdef0ULL,.rkey=0};
    second=first;second.wr.wr_id++;second.wr.opcode=IB_WR_RDMA_WRITE;
    first.wr.next=scenario==1 ? &unsupported:&second.wr;
    CHECK(!verbs->req_notify_cq(&cq.ibcq,IB_CQ_NEXT_COMP));
    if(scenario==1){CHECK(verbs->post_send(&qp.ibqp,&first.wr,&bad)==-EOPNOTSUPP && bad==&unsupported);
        CHECK(model.observed_count==1 && refcount_read(&owned->mapping->work_refs)==2);}
    else {CHECK(!verbs->post_send(&qp.ibqp,&first.wr,&bad) && !bad && model.observed_count==2);
        CHECK(refcount_read(&owned->mapping->work_refs)==3);}
    CHECK(verbs->dealloc_pd(&pd.ibpd,NULL)==-EBUSY && as02_verbs_unbind(&vdev)==-EBUSY);
    hardware_completion(0);cm_run_work(&cqh.poll_work);irq_work_sync(&cq.notify);CHECK(interrupts==1);
    CHECK(verbs->poll_cq(&cq.ibcq,2,wc)==1 && wc[0].wr_id==first.wr.wr_id && wc[0].qp==&qp.ibqp &&
        wc[0].opcode==IB_WC_RDMA_READ && wc[0].byte_len==65);
    if(scenario==0 || scenario==5 || scenario==6){hardware_completion(1);CHECK(verbs->poll_cq(&cq.ibcq,2,wc)==1 &&
        wc[0].wr_id==second.wr.wr_id && wc[0].opcode==IB_WC_RDMA_WRITE);}
    CHECK(refcount_read(&owned->mapping->work_refs)==1);
    cleanup_verbs(m);
    printf("KERNEL_VERBS_RESULT {\"pass_test\":true,\"actual_callbacks\":true,\"completed_WRs\":%u,\"notifications\":%u,\"TX_PSN\":%u,\"payload_CPU_copy\":false,\"retry_policy_actual_transport\":%s}\n",scenario==0||scenario==5||scenario==6?2:1,interrupts,ctl_tx_psn,retry_feature?"true":"false");
    return 0;
}
