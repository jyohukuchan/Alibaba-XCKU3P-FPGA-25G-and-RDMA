/* SPDX-License-Identifier: BSD-2-Clause-Views */
/* Actual native bootstrap + actual RNC MR/MMIO/SQ/RQ/CQ/device C. IB core,
 * BAR hardware, Linux pins/DMA and completion producer are explicit models.
 * No successful MR hardware callback is substituted for rnic_hw.c.
 */
#include "kernel_native_graph_model.h"
#include "native_graph.h"
#include "mqnic_graph.h"
#define main unused_legacy_sq_main
#define readl legacy_sq_readl
#define writel legacy_sq_writel
#define ktime_get legacy_sq_ktime_get
#define cpu_relax legacy_sq_cpu_relax
#include "kernel_sq_hw_cases.c"
#undef main
#undef readl
#undef writel
#undef ktime_get
#undef cpu_relax

static u8 application[AS02_NATIVE_BAR_BYTES];
static struct model send_controller,receive_controller;
static struct as02_native_graph *active;
static struct net_device netdev;
static struct pci_dev pci_parent;
static struct mqnic_dev mqnic_parent;
static struct mqnic_if mqnic_interface;
static struct mqnic_adev app;
static struct ib_device *allocated;
static struct net_device *core_netdev;
static const struct ib_device_ops *work,*info;
static u32 rnc_stage[21],rnc_reply[8],rnc_last,rnc_generation,rnc_key[8],rnc_pd,rnc_qpn;
static u64 page_values[256],virtual_us;
static bool rnc_pending,rnc_epoch,rnc_run,hide_reply,mapped[8],building[8];
static unsigned int page_count[8],commands[10],rnc_reads,rnc_writes,registrations,unregistrations;
static int register_error;
static struct as02_cq_event cq_event;
static bool cq_visible,hide_cq;
static u32 cq_ack,rrp_stage[8],rrp_reply[8],rrp_last;
static u64 rrp_epoch;
static bool rrp_pending;
static bool immediate_graph;

static u32 rnc_read(u32 off)
{
    rnc_reads++;CHECK(!km_spin_depth);
    if(off>=AS02_CTL_STAGE && off<AS02_CTL_STAGE+84)return rnc_stage[(off-AS02_CTL_STAGE)/4];
    if(off>=AS02_CTL_REPLY_SEQ && off<=AS02_CTL_REPLY_FLAGS)return rnc_reply[(off-AS02_CTL_REPLY_SEQ)/4];
    switch(off){
    case AS02_CTL_ID:return AS02_CTL_ID_VALUE;case AS02_CTL_ABI:return AS02_CTL_ABI_VALUE;
    case AS02_CTL_FEATURES:return immediate_graph ? 1023:511;
    case AS02_CTL_STATUS:return AS02_ST_PARENT_DRAINED|AS02_ST_ENDPOINT_QUIET|
        (rnc_epoch ? AS02_ST_EPOCH:0)|(rnc_pd ? AS02_ST_QP:0)|(rnc_run ? AS02_ST_RUN:AS02_ST_PAUSED)|
        (rnc_pending ? (hide_reply ? AS02_ST_BUSY:AS02_ST_REPLY):AS02_ST_READY);
    case AS02_CTL_LAST_QUEUED:case AS02_CTL_LAST_SEQUENCE:return rnc_last;
    case AS02_CTL_ENTRY_STATE:{u32 s=0;for(unsigned int i=0;i<8;i++)if(mapped[i]||building[i])s|=1U<<i;return s;}
    default:CHECK(0);return 0;
    }
}
static void rnc_write(u32 off,u32 value)
{
    u32 op,slot;
    rnc_writes++;CHECK(!km_spin_depth);
    if(off>=AS02_CTL_STAGE && off<AS02_CTL_STAGE+84){rnc_stage[(off-AS02_CTL_STAGE)/4]=value;return;}
    if(off==AS02_CTL_REPLY_ACK){CHECK(rnc_pending && value==rnc_last);rnc_pending=false;return;}
    CHECK(off==AS02_CTL_DOORBELL && value==1 && !rnc_pending && rnc_stage[0]==rnc_last+1);
    op=rnc_stage[AS02_W_OP];slot=rnc_stage[AS02_W_SLOT];CHECK(op>=1 && op<=9 && slot<8);
    commands[op]++;rnc_last++;rnc_pending=true;memset(rnc_reply,0,sizeof(rnc_reply));
    rnc_reply[0]=rnc_last;rnc_reply[1]=op;rnc_reply[2]=rnc_stage[AS02_W_COOKIE_LO];
    rnc_reply[3]=rnc_stage[AS02_W_COOKIE_HI];rnc_reply[4]=slot;rnc_reply[5]=rnc_stage[AS02_W_KEY];
    if(op==AS02_CMD_EPOCH){CHECK(!rnc_run);rnc_epoch=true;rnc_generation=rnc_stage[AS02_W_KEY];rnc_reply[7]=14;}
    else if(op==AS02_CMD_BEGIN){
        CHECK(rnc_epoch && !mapped[slot] && !building[slot] && rnc_stage[AS02_W_PD] &&
            pair(rnc_stage+AS02_W_VA_LO)==VA && rnc_stage[AS02_W_LENGTH]==8192 && rnc_stage[AS02_W_FIRST]==3);
        building[slot]=true;page_count[slot]=0;rnc_key[slot]=(++rnc_generation<<3)|slot;rnc_reply[5]=rnc_key[slot];
    }else if(op==AS02_CMD_PAGE){
        u32 index=rnc_stage[AS02_W_PAGE_INDEX];u64 dma=pair(rnc_stage+AS02_W_DMA_LO);
        CHECK(building[slot] && rnc_stage[AS02_W_KEY]==rnc_key[slot] && index==page_count[slot] && !(dma&4095));
        CHECK(dma==0x9123456700000000ULL+index*8192ULL);page_values[index]=dma;page_count[slot]++;
    }else if(op==AS02_CMD_SEAL){CHECK(building[slot] && page_count[slot]==3 && rnc_stage[AS02_W_KEY]==rnc_key[slot]);
        building[slot]=false;mapped[slot]=true;rnc_reply[7]=AS02_PROOF_PUBLISHED;
    }else if(op==AS02_CMD_INVALIDATE){CHECK(mapped[slot] && rnc_stage[AS02_W_KEY]==rnc_key[slot]);
        mapped[slot]=false;rnc_reply[5]=rnc_key[slot];rnc_reply[7]=AS02_PROOF_INVALIDATED|AS02_PROOF_DMA_DRAINED;
    }else if(op==AS02_CMD_STOP){rnc_run=false;rnc_reply[7]=AS02_PROOF_DMA_DRAINED;rnc_reply[5]=0;
    }else if(op==AS02_CMD_QP){CHECK(!rnc_run);rnc_qpn=rnc_stage[AS02_W_QP];rnc_pd=rnc_stage[AS02_W_PD];
    }else if(op==AS02_CMD_RUN){CHECK(rnc_epoch && rnc_pd);rnc_run=true;
    }else{CHECK(op==AS02_CMD_QP_TX && rnc_stage[AS02_W_QP]==rnc_qpn && rnc_stage[AS02_W_PD]==rnc_pd);}
}
static u32 queue_read(struct model *m,u32 off)
{struct model saved=model;u32 value;model=*m;CHECK(!model_read(NULL,off,&value));*m=model;model=saved;return value;}
static void queue_write(struct model *m,u32 off,u32 value)
{struct model saved=model;model=*m;CHECK(!model_write(NULL,off,value));*m=model;model=saved;}
u32 readl(const volatile void *p)
{
    uintptr_t address=(uintptr_t)p-(uintptr_t)application;u32 off=address&4095;
    CHECK(address<sizeof(application));
    switch(address&~4095UL){
    case AS02_NATIVE_CONTROL_BASE:return rnc_read(off);
    case AS02_NATIVE_SQ_BASE:CHECK(km_spin_depth);return queue_read(&send_controller,off);
    case AS02_NATIVE_RQ_BASE:CHECK(km_spin_depth);return queue_read(&receive_controller,off);
    case AS02_NATIVE_ETH_BASE:
        switch(off){case AS02_ETH_ID:return AS02_ETH_ID_VALUE;case AS02_ETH_ABI:return AS02_ETH_ABI_VALUE;
        case AS02_ETH_STATUS:return AS02_ETH_ST_ENABLED|AS02_ETH_ST_COMMITTED;case AS02_ETH_EPOCH:return 1;
        case AS02_ETH_ACTIVE:return 1;case AS02_ETH_ACTIVE+4:return 0x0200;
        case AS02_ETH_ACTIVE+8:return 2;case AS02_ETH_ACTIVE+12:return 0x0200;
        case AS02_ETH_ACTIVE+16:return 0xc0000201;case AS02_ETH_ACTIVE+20:return 1;default:CHECK(0);}
        break;
    case AS02_NATIVE_RETRY_BASE:
        if(off>=0x80 && off<0xa0)return rrp_reply[(off-0x80)/4];
        switch(off){case 0:return AS02_RRP_ID;case 4:return AS02_RRP_ABI;case 8:return 1;
        case 12:return rrp_pending ? 6:1;case 24:return rrp_last;case 28:return 4000;
        case 0xa0:return rrp_epoch;case 0xa4:return rrp_epoch>>32;case 0xa8:return 0;default:CHECK(0);}
        break;
    case AS02_NATIVE_CQ_BASE:
        if(off>=AS02_CQC_CONTEXT && off<AS02_CQC_CONTEXT+76)return cq_event.context[(off-AS02_CQC_CONTEXT)/4];
        switch(off){case AS02_CQC_ID:return AS02_CQC_ID_VALUE;case AS02_CQC_ABI:return AS02_CQC_ABI_VALUE;
        case AS02_CQC_FEATURES:return immediate_graph ? 7:3;case AS02_CQC_STATUS:return cq_visible && !hide_cq ? 3:0;
        case AS02_CQC_CONTEXT_EXTENSION:CHECK(immediate_graph);return cq_event.context_extension;
        case AS02_CQC_NOTIFICATION_FLAGS:CHECK(immediate_graph);return cq_event.notification_flags;
        case AS02_CQC_NOTIFICATION:CHECK(immediate_graph);return cq_event.notification;
        case AS02_CQC_LAST_ACK:return cq_ack;case AS02_CQC_SEQUENCE:return cq_visible ? cq_event.sequence:cq_ack;
        case AS02_CQC_PROOFS:return cq_event.proofs;case AS02_CQC_COOKIE_LO:return cq_event.cookie;
        case AS02_CQC_COOKIE_HI:return cq_event.cookie>>32;case AS02_CQC_WC_STATUS:return cq_event.status;
        case AS02_CQC_RECEIVED_BYTES:return cq_event.received_bytes;default:CHECK(0);}
        break;
    default:CHECK(0);
    }return 0;
}
void writel(u32 value,volatile void *p)
{
    uintptr_t address=(uintptr_t)p-(uintptr_t)application;u32 off=address&4095;CHECK(address<sizeof(application));
    switch(address&~4095UL){
    case AS02_NATIVE_CONTROL_BASE:rnc_write(off,value);return;
    case AS02_NATIVE_SQ_BASE:CHECK(km_spin_depth);queue_write(&send_controller,off,value);return;
    case AS02_NATIVE_RQ_BASE:CHECK(km_spin_depth);queue_write(&receive_controller,off,value);return;
    case AS02_NATIVE_CQ_BASE:CHECK(off==AS02_CQC_ACK && cq_visible && value==cq_event.sequence);
        cq_ack=value;cq_visible=false;return;
    case AS02_NATIVE_RETRY_BASE:
        if(off>=0x40 && off<0x60){rrp_stage[(off-0x40)/4]=value;return;}
        if(off==0x10){CHECK(!rrp_pending && value==rrp_last+1 && send_controller.active &&
            rrp_stage[1]==send_controller.reply[2] && rrp_stage[2]==send_controller.reply[3] &&
            pair(rrp_stage+6)==pair(send_controller.reply+6));
            memcpy(rrp_reply,rrp_stage,sizeof(rrp_reply));rrp_epoch=pair(send_controller.reply+4);rrp_last=value;rrp_pending=true;return;}
        CHECK(off==0x14 && rrp_pending && value==rrp_last);rrp_pending=false;return;
    default:CHECK(0);
    }
}
ktime_t ktime_get(void){return ++virtual_us;}
void cpu_relax(void){virtual_us++;}
void usleep_range(unsigned long a,unsigned long b){CHECK(!km_spin_depth && a<=b);virtual_us+=a;}
struct ib_device *device_model_alloc(size_t bytes)
{allocated=kzalloc(bytes,GFP_KERNEL);CHECK(allocated);atomic_store(&allocated->dev.references,1);return allocated;}
void ib_set_device_ops(struct ib_device *d,const struct ib_device_ops *ops)
{CHECK(d==allocated);if(ops->query_device){CHECK(!info);info=ops;}else{CHECK(!work);work=ops;}}
int ib_device_set_netdev(struct ib_device *d,struct net_device *n,u32 port)
{CHECK(d==allocated && n==&netdev && port==1 && !core_netdev);core_netdev=n;dev_hold(n);return 0;}
int ib_get_eth_speed(struct ib_device *d,u32 port,u16 *speed,u8 *width)
{CHECK(d==allocated && port==1);*speed=32;*width=1;return 0;}
int ib_register_device(struct ib_device *d,const char *name,struct device *dma)
{
    struct ib_device_attr a;struct ib_port_attr p;
    CHECK(d==allocated && active && d==&active->device->ibdev && dma==&pci_parent.dev && !strcmp(name,"as02_%d"));
    CHECK(active->mrs.hw==&as02_rnic_mr_hw_ops && active->mrs.hw_context==&active->control &&
        active->mrs.ready && commands[AS02_CMD_EPOCH] && active->sq_hw.receive==&active->rq_hw &&
        active->completions.pool==&active->queues && work==&as02_verbs_ops && info==&as02_device_ops);
    CHECK(!info->query_device(d,&a,NULL) && a.max_qp==1 && !info->query_port(d,1,&p) && p.state==IB_PORT_ACTIVE);
    registrations++;if(register_error)return register_error;CHECK(!info->enable_driver(d));return 0;
}
void ib_unregister_device(struct ib_device *d)
{CHECK(d==allocated && active->device->stopping && !active->device->context_count);unregistrations++;}
void ib_dealloc_device(struct ib_device *d)
{CHECK(d==allocated && atomic_load(&d->dev.references)==1);if(core_netdev){dev_put(core_netdev);core_netdev=NULL;}kfree(d);allocated=NULL;}
static void reset_hardware_model(void)
{
    CHECK(!active && !allocated);fresh();send_controller=model;receive_controller=model;receive_controller.id=AS02_RQC_ID_VALUE;
    if(immediate_graph){send_controller.features=5;receive_controller.features=7;}
    memset(rnc_stage,0,sizeof(rnc_stage));memset(rnc_reply,0,sizeof(rnc_reply));memset(mapped,0,sizeof(mapped));memset(building,0,sizeof(building));
    rnc_last=0;rnc_pending=false;rnc_epoch=false;rnc_run=false;rnc_pd=0;rnc_qpn=0;
    rrp_last=0;rrp_pending=false;cq_ack=0;cq_visible=false;work=NULL;info=NULL;
}
static void complete_work(bool receive)
{
    const struct as02_wqe *w=receive ? &receive_controller.observed[0]:&send_controller.observed[0];
    unsigned int i;CHECK(!cq_visible);memset(&cq_event,0,sizeof(cq_event));
    cq_event.sequence=cq_ack+1;cq_event.proofs=15;cq_event.received_bytes=receive ? 65:0;
    cq_event.cookie=pair((receive ? receive_controller.reply:send_controller.reply)+6);
#define P(start,width,value) do{u64 vv=(value);for(i=0;i<(width);i++)if(vv&(1ULL<<i))cq_event.context[((start)+i)/32]|=1U<<(((start)+i)%32);}while(0)
    P(0,2,3);P(116,64,0x210);P(180,64,w->local_address);P(244,32,w->local_key);P(276,32,w->length);
    P(308,16,w->flags);P(324,16,w->opcode);P(340,16,receive ? 1:2);P(356,16,1);P(372,24,2);
    P(396,64,w->epoch);P(460,64,w->sequence);P(524,64,w->wr_id);
    P(588,20,w->immediate&0xfffff);cq_event.context_extension=w->immediate>>20;
    if(immediate_graph && receive){cq_event.notification=0x01234567;cq_event.notification_flags=1;}
#undef P
    cq_visible=true;
}
static void exercise(unsigned int scenario)
{
    unsigned int previous_unregistrations=unregistrations;
    struct ib_device *d=&active->device->ibdev;struct as02_ucontext ctx={.ibucontext={.device=d}};
    struct ib_uverbs_file file={.context=&ctx.ibucontext};ctx.ibucontext.ufile=&file;
    struct uverbs_attr_bundle attrs={.context=&ctx.ibucontext};
    struct as02_pd pd={.ibpd={.device=d}};struct as02_cq tx={.ibcq={.device=d}},rx={.ibcq={.device=d}};
    struct as02_cq *receive_cq=scenario==9 ? &tx:&rx;
    struct as02_verbs_qp q={.ibqp={.device=d,.pd=&pd.ibpd}};struct ib_wc wc;
    CHECK(!info->alloc_ucontext(&ctx.ibucontext,NULL) && !work->alloc_pd(&pd.ibpd,NULL));
    struct ib_mr *m=work->reg_user_mr(&pd.ibpd,0x10003,8192,VA,7,NULL,NULL);CHECK(!IS_ERR(m));
    CHECK(m->lkey==((active->initial_mr_floor+1)<<3) && page_count[0]==3 && page_values[2]==0x9123456700004000ULL);
    struct ib_cq_init_attr ca={.cqe=scenario>=6 ? 1:2};
    CHECK(!work->create_cq(&tx.ibcq,&ca,scenario>=6 ? &attrs:NULL) &&
          !work->create_cq(&rx.ibcq,&ca,scenario>=6 ? &attrs:NULL));
    struct ib_qp_init_attr qa={.send_cq=&tx.ibcq,.recv_cq=&receive_cq->ibcq,.qp_type=IB_QPT_RC,.sq_sig_type=IB_SIGNAL_ALL_WR,
        .cap={.max_send_wr=2,.max_recv_wr=2,.max_send_sge=1,.max_recv_sge=1}};
    CHECK(!work->create_qp(&q.ibqp,&qa,scenario>=6 ? &attrs.driver_udata:NULL) && q.owner.epoch==active->initial_qp_epochs[2]+1);
    CHECK(q.ucontext==(scenario>=6 ? &ctx.ibucontext:NULL));
    struct ib_qp_attr a={.qp_state=IB_QPS_INIT,.port_num=1,.qp_access_flags=6};
    CHECK(!work->modify_qp(&q.ibqp,&a,IB_QP_STATE|IB_QP_PORT|IB_QP_PKEY_INDEX|IB_QP_ACCESS_FLAGS,NULL));
    struct ib_gid_attr sgid={.device=d,.port_num=1,.gid_type=IB_GID_TYPE_ROCE_UDP_ENCAP,
        .gid={.raw={0,0,0,0,0,0,0,0,0,0,255,255,192,0,2,1}}};
    a=(struct ib_qp_attr){.qp_state=IB_QPS_RTR,.path_mtu=IB_MTU_4096,.dest_qp_num=196,.rq_psn=0x987654,.max_dest_rd_atomic=1,
        .ah_attr={.type=RDMA_AH_ATTR_TYPE_ROCE,.port_num=1,.ah_flags=IB_AH_GRH,.dmac={2,0,0,0,0,2},
            .grh={.sgid_attr=&sgid,.hop_limit=100,.dgid={.raw={0,0,0,0,0,0,0,0,0,0,255,255,192,0,2,2}}}}};
    CHECK(!work->modify_qp(&q.ibqp,&a,IB_QP_STATE|IB_QP_AV|IB_QP_PATH_MTU|IB_QP_DEST_QPN|IB_QP_RQ_PSN|
        IB_QP_MAX_DEST_RD_ATOMIC|IB_QP_MIN_RNR_TIMER,NULL));
    a=(struct ib_qp_attr){.qp_state=IB_QPS_RTS,.sq_psn=0xfffffe,.max_rd_atomic=1,.timeout=1,.retry_cnt=1,.rnr_retry=1};
    CHECK(!work->modify_qp(&q.ibqp,&a,IB_QP_STATE|IB_QP_SQ_PSN|IB_QP_MAX_QP_RD_ATOMIC|IB_QP_TIMEOUT|IB_QP_RETRY_CNT|IB_QP_RNR_RETRY,NULL));
    struct ib_sge sg={.addr=VA+0x210,.length=128,.lkey=m->lkey};
    struct ib_recv_wr receive={.wr_id=101,.sg_list=&sg,.num_sge=1};const struct ib_recv_wr *bad_r=NULL;
    CHECK(!work->post_recv(&q.ibqp,&receive,&bad_r));sg.length=65;
    struct ib_send_wr send={.wr_id=102,.sg_list=&sg,.num_sge=1,
        .opcode=immediate_graph ? IB_WR_SEND_WITH_IMM:IB_WR_SEND,.ex.imm_data=cpu_to_be32(0x89abcdef)};
    const struct ib_send_wr *bad_s=NULL;
    CHECK(!work->post_send(&q.ibqp,&send,&bad_s));
    CHECK(as02_native_graph_close(&active)==-EBUSY && active && active->lease->owner==active && unregistrations==previous_unregistrations);
    if(scenario>=13){
        struct as02_verbs_mr *mr=container_of(m,struct as02_verbs_mr,ibmr);
        struct ib_qp_attr error={.qp_state=IB_QPS_ERR},queried;
        struct ib_qp_init_attr initial;
        unsigned int first_id=101,second_id=103,cancel_bells;
        complete_work(false);CHECK(as02_cq_hw_poll(&active->completions)==1 && tx.pending==1);
        if(scenario==18){
            complete_work(true);CHECK(work->poll_cq(&rx.ibcq,1,&wc)==1 && wc.wr_id==101 && wc.status==IB_WC_SUCCESS);
            first_id=103;second_id=104;
            sg.length=128;receive.wr_id=first_id;CHECK(!work->post_recv(&q.ibqp,&receive,&bad_r));
        }
        if(scenario==14 || scenario==17 || scenario==18){
            sg.length=128;receive.wr_id=second_id;CHECK(!work->post_recv(&q.ibqp,&receive,&bad_r));
        }
        CHECK(!work->req_notify_cq(&rx.ibcq,IB_CQ_NEXT_COMP));
        if(scenario==15)receive_controller.withhold=true;
        if(scenario==16)receive_controller.corrupt_word=6;
        CHECK(!work->modify_qp(&q.ibqp,&error,IB_QP_STATE,NULL));cancel_bells=receive_controller.bells;
        CHECK(!work->query_qp(&q.ibqp,&queried,IB_QP_STATE,&initial) && queried.qp_state==IB_QPS_ERR && q.closing);
        CHECK(work->post_send(&q.ibqp,&send,&bad_s)==-ESHUTDOWN && bad_s==&send);
        CHECK(work->post_recv(&q.ibqp,&receive,&bad_r)==-ESHUTDOWN && bad_r==&receive);
        if(scenario==15 || scenario==16){
            CHECK(q.error_pending && q.error_progress_status<0 && !rx.pending &&
                refcount_read(&mr->mapping->work_refs)==2 && !km.dma_frees &&
                active->rq_hw.control.pending && as02_native_graph_close(&active)==-EBUSY);
            receive_controller.withhold=false;receive_controller.corrupt_word=-1;
            if(scenario==15){CHECK(q.error_work.work.pending);cm_run_work(&q.error_work);}
            else{CHECK(!q.error_work.work.pending);CHECK(!work->modify_qp(&q.ibqp,&error,IB_QP_STATE,NULL));}
        }
        if(scenario==14 || scenario==17 || scenario==18){
            CHECK(q.error_pending && q.error_progress_status==-ENOSPC && rx.pending==1 &&
                refcount_read(&mr->mapping->work_refs)==2 && !km.dma_frees &&
                !receive_controller.active && q.error_work.work.pending &&
                !q.hw_owned && !rnc_run && !rnc_pd);
            if(scenario==17){
                info->ufile_hw_cleanup(&file);
                CHECK(!ctx.cleanup_error && !rx.pending && !tx.pending &&
                    refcount_read(&mr->mapping->work_refs)==1 && !km.dma_frees &&
                    receive_controller.bells==cancel_bells);
                CHECK(!work->destroy_qp(&q.ibqp,NULL) && !q.error_work.work.pending);
                CHECK(!work->destroy_cq(&tx.ibcq,NULL) && !work->destroy_cq(&rx.ibcq,NULL));
                CHECK(!work->dereg_mr(m,NULL) && !work->dealloc_pd(&pd.ibpd,NULL));
                info->dealloc_ucontext(&ctx.ibucontext);return;
            }
            CHECK(work->poll_cq(&rx.ibcq,1,&wc)==1 && wc.wr_id==first_id &&
                wc.status==IB_WC_WR_FLUSH_ERR && wc.opcode==IB_WC_RECV && !wc.byte_len);
            cm_run_work(&q.error_work);
            first_id=second_id;
        }
        CHECK(!q.error_pending && !q.error_progress_status && q.sq_closed && !q.hw_owned &&
            km.dma_frees==2 && refcount_read(&mr->mapping->work_refs)==1 &&
            receive_controller.bells==cancel_bells && !q.error_work.work.pending);
        CHECK(work->poll_cq(&rx.ibcq,1,&wc)==1 && wc.wr_id==first_id &&
            wc.status==IB_WC_WR_FLUSH_ERR && wc.opcode==IB_WC_RECV && !wc.byte_len);
        CHECK(!work->poll_cq(&rx.ibcq,1,&wc));
        CHECK(work->poll_cq(&tx.ibcq,1,&wc)==1 && wc.wr_id==102 && wc.status==IB_WC_SUCCESS);
        CHECK(!work->modify_qp(&q.ibqp,&error,IB_QP_STATE,NULL) && !q.error_pending);
    }else if(scenario>=10){
        struct as02_verbs_mr *mr=container_of(m,struct as02_verbs_mr,ibmr);
        unsigned int dma_frees=km.dma_frees;
        complete_work(false);CHECK(as02_cq_hw_poll(&active->completions)==1 && tx.pending==1);
        CHECK(!cq_visible && refcount_read(&mr->mapping->work_refs)==2);
        if(scenario==11)receive_controller.withhold=true;
        if(scenario==12)receive_controller.corrupt_word=6;
        info->ufile_hw_cleanup(&file);
        if(scenario!=10){
            CHECK(ctx.cleanup_error<0 && active->rq_hw.control.pending &&
                refcount_read(&mr->mapping->work_refs)==2 && km.dma_frees==dma_frees &&
                active->queues.queue_count==1 && active->mrs.mapping_count==1 &&
                as02_native_graph_close(&active)==-EBUSY);
            receive_controller.withhold=false;receive_controller.corrupt_word=-1;
            info->ufile_hw_cleanup(&file);
        }
        CHECK(!ctx.cleanup_error && !cq_visible && !tx.pending && !rx.pending &&
            receive_controller.flags==63 && !receive_controller.active &&
            active->rq_hw.control.sequence==3 && !active->rq_hw.control.pending &&
            refcount_read(&mr->mapping->work_refs)==1 && km.dma_frees==dma_frees);
    }else if(scenario==6 || scenario==7 || scenario==9){
        struct as02_verbs_mr *mr=container_of(m,struct as02_verbs_mr,ibmr);
        unsigned int dma_frees=km.dma_frees;
        CHECK(!work->req_notify_cq(&tx.ibcq,IB_CQ_NEXT_COMP));
        if(receive_cq!=&tx)CHECK(!work->req_notify_cq(&receive_cq->ibcq,IB_CQ_NEXT_COMP));
        complete_work(false);CHECK(as02_cq_hw_poll(&active->completions)==1 && tx.pending==tx.capacity);
        CHECK(tx.notify.pending && (receive_cq==&tx || receive_cq->armed));
        complete_work(true);hide_cq=scenario==7;
        if(scenario==9)CHECK(as02_cq_hw_poll(&active->completions)==-ENOSPC && cq_visible &&
                            refcount_read(&mr->mapping->work_refs)==2);
        CHECK(refcount_read(&mr->mapping->work_refs)==2 && cq_visible);
        info->ufile_hw_cleanup(&file);
        CHECK(ctx.closing && !ctx.cleanup_error && q.closing && !tx.pending && !rx.pending &&
            active->router.abandoning[2] && km.dma_frees==dma_frees);
        CHECK(tx.user_closed && receive_cq->user_closed && !tx.notify.pending && !receive_cq->notify.pending &&
              !tx.armed && !receive_cq->armed && !atomic_read(&active->completions.notify_users));
        CHECK(work->req_notify_cq(&receive_cq->ibcq,IB_CQ_NEXT_COMP)==-ESHUTDOWN);
        CHECK(work->post_send(&q.ibqp,&send,&bad_s)==-ESHUTDOWN && bad_s==&send);
        CHECK(work->post_recv(&q.ibqp,&receive,&bad_r)==-ESHUTDOWN && bad_r==&receive);
        if(scenario==7){
            /* This genuine completion was generated BEFORE cleanup; only
             * its modeled register visibility is delayed. Missing visibility
             * never releases the pending work/ring/MR references.
             */
            CHECK(cq_visible && refcount_read(&mr->mapping->work_refs)==2 &&
                active->queues.queue_count==1 && active->mrs.mapping_count==1 &&
                as02_native_graph_close(&active)==-EBUSY);
            hide_cq=false;info->ufile_hw_cleanup(&file);
        }
        CHECK(!cq_visible && !ctx.cleanup_error && refcount_read(&mr->mapping->work_refs)==1 &&
            !work->poll_cq(&tx.ibcq,1,&wc) && !work->poll_cq(&rx.ibcq,1,&wc));
    }else{
        if(scenario==8){
            struct as02_ucontext other={.ibucontext={.device=d}};
            struct ib_uverbs_file foreign={.context=&other.ibucontext};
            CHECK(!info->alloc_ucontext(&other.ibucontext,NULL));
            info->ufile_hw_cleanup(&foreign);
            CHECK(other.closing && !other.cleanup_error && !q.closing && !active->router.abandoning[2]);
            info->dealloc_ucontext(&other.ibucontext);
        }
        complete_work(false);CHECK(work->poll_cq(&tx.ibcq,1,&wc)==1 && wc.wr_id==102 && wc.opcode==IB_WC_SEND);
        complete_work(true);CHECK(work->poll_cq(&rx.ibcq,1,&wc)==1 && wc.wr_id==101 && wc.opcode==IB_WC_RECV && wc.byte_len==65);
        if(immediate_graph)CHECK(wc.wc_flags==IB_WC_WITH_IMM && wc.ex.imm_data==cpu_to_be32(0x01234567));
    }
    CHECK(!work->destroy_qp(&q.ibqp,NULL) && !work->destroy_cq(&tx.ibcq,NULL) && !work->destroy_cq(&rx.ibcq,NULL));
    CHECK(!work->dereg_mr(m,NULL) && !work->dealloc_pd(&pd.ibpd,NULL));info->dealloc_ucontext(&ctx.ibucontext);
}
int main(int argc,char **argv)
{
    struct as02_native_lease lease={};u64 epochs[8]={0};unsigned int scenario;
    CHECK(argc==2);scenario=strtoul(argv[1],NULL,0);CHECK(scenario<20);immediate_graph=scenario==19;
    netdev=(struct net_device){.dev={.parent=&pci_parent.dev},.dev_addr={2,0,0,0,0,1},
        .mtu=9000,.reg_state=NETREG_REGISTERED,.running=true,.carrier=true};atomic_store(&netdev.dev.references,1);
    /* Pinned private layout itself is a MODEL; real W1 compilation uses
     * the actual upstream mqnic header. Parameter opt-in grants entry only.
     */
    CHECK(as02_mqnic_native_open(NULL,NULL,NULL)==-EACCES);
    *model_parameter_enable_native_attach=true;
    pci_parent=(struct pci_dev){.vendor=0x1234,.device=0x1001,.subsystem_vendor=0x1ce4,.subsystem_device=9};
    atomic_store(&pci_parent.dev.references,1);
    /* The actual PCI parent device is the same object used for DMA/netdev. */
    mqnic_parent=(struct mqnic_dev){.dev=&pci_parent.dev,.pdev=&pci_parent,.app_hw_regs_size=sizeof(application),
        .app_hw_addr=application,.app_id=AS02_NATIVE_APP_ID,.if_count=1};
    mqnic_interface=(struct mqnic_if){.mdev=&mqnic_parent,.ndev_count=1,.ndev={&netdev}};
    mqnic_parent.interface[0]=&mqnic_interface;app.mdev=&mqnic_parent;
    epochs[2]=0x9123456700000000ULL;CHECK(!as02_native_lease_init(&lease,4,epochs));reset_hardware_model();
    if(scenario>=10 && !immediate_graph)receive_controller.features=3;
    if(scenario==1){mqnic_parent.app_id=0x524f4332;CHECK(as02_mqnic_native_open(&app.adev,&lease,&active)==-ENODEV && !active && !lease.owner && !rnc_reads);}
    else if(scenario==2){receive_controller.id=0;CHECK(as02_mqnic_native_open(&app.adev,&lease,&active)==-ENODEV && active && !commands[1]);
        CHECK(!as02_native_graph_close(&active));}
    else if(scenario==3){
        hide_reply=true;CHECK(as02_mqnic_native_open(&app.adev,&lease,&active)==-ETIMEDOUT && active && lease.owner==active);
        CHECK(as02_native_graph_close(&active)==-EBUSY && allocated && atomic_load(&pci_parent.dev.references)>1);
        struct as02_native_graph *other=NULL;CHECK(as02_mqnic_native_open(&app.adev,&lease,&other)==-EBUSY && !other);
        hide_reply=false;struct as02_ctl_reply reply;CHECK(!as02_native_graph_reconcile_control(active,&reply) &&
            reply.command==AS02_CMD_EPOCH && reply.flags==14 && reply.key==4);
        CHECK(!as02_native_graph_close(&active));
    }else if(scenario==4){register_error=-ENOMEM;CHECK(as02_mqnic_native_open(&app.adev,&lease,&active)==-ENOMEM && active && !active->device->published);
        CHECK(!as02_native_graph_close(&active) && !unregistrations);
    }else{
        unsigned int rounds=scenario==5 ? 2:1;
        for(unsigned int i=0;i<rounds;i++){
            CHECK(!as02_mqnic_native_open(&app.adev,&lease,&active));
            if(immediate_graph)CHECK(active->queues.profile_bound && active->queues.wqe_profile==AS02_WQE_PROFILE_IMMEDIATE);
            exercise(immediate_graph ? 0:scenario);CHECK(!as02_native_graph_close(&active));
            CHECK(!active && !lease.owner && lease.mr_floor==5+i && lease.qp_epochs[2]==epochs[2]+1+i);
            CHECK(!atomic_load(&km.heap_live) && !atomic_load(&km.umem_live) && !atomic_load(&km.module_refs));
            if(i+1<rounds)reset_hardware_model();
        }
    }
    CHECK(!active && !lease.owner && !atomic_load(&km.heap_live) && !atomic_load(&km.umem_live) && !atomic_load(&km.module_refs));
    CHECK(atomic_load(&pci_parent.dev.references)==1 && atomic_load(&netdev.dev.references)==1 && km.dma_allocs==km.dma_frees);
    printf("NATIVE_GRAPH_RESULT {\"pass_test\":true,\"scenario\":%u,\"actual_RNC_MR_and_queue_adapters\":true,\"caller_MR_success_backend_substituted\":false,\"Immediate_profile1023\":%s,\"user_file_cleanup_case\":%s,\"epoch_commands\":%u,\"page_commands\":%u,\"registrations\":%u,\"normal_unregistrations\":%u,\"hardware_and_IB_core_boundaries_modeled\":true,\"hardware_verified\":false}\n",scenario,immediate_graph ? "true":"false",scenario>=6 && !immediate_graph ? "true":"false",commands[1],commands[3],registrations,unregistrations);
}
