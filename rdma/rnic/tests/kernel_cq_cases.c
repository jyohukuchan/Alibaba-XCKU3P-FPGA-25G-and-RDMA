/* SPDX-License-Identifier: BSD-2-Clause-Views */
/* Actual kernel CQ/MMIO/SQ/MR C, with explicit primitive/pin/DMA models.
 * Event bytes are read from production CQC1 RTL AXI snapshots, not invented
 * success callbacks or user WR-id pointers. No kernel/runtime hardware proof.
 */
#include "kernel_cq_model.h"
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
#include "cq.h"

static struct as02_cq completion_queue;
static struct as02_cq receive_queue;
static bool receive_mode,separate_receive_cq;
static struct as02_cq *target_cq(void)
{ return separate_receive_cq ? &receive_queue : &completion_queue; }
static struct as02_cq_router router;
static struct as02_cq_hw completion_hw;
static struct ib_qp actual_qp;
static u8 completion_mmio[AS02_CQC_BYTES];
static struct as02_cq_event records[2],visible_event;
static u32 last_ack;
static bool visible,drop_next_ack;
static unsigned int notifications,ack_writes;

static void load_event(unsigned int n)
{
    CHECK(n<2 && !visible && records[n].sequence==last_ack+1);
    visible_event=records[n];visible=true;
}
#ifndef AS02_CQ_CUSTOM_MMIO
u32 readl(const volatile void *p)
{
    uintptr_t address=(uintptr_t)p,base=(uintptr_t)completion_mmio;
    u32 off;
    if(address<(uintptr_t)mmio+sizeof(mmio) && address>=(uintptr_t)mmio)return sq_readl(p);
    CHECK(km_spin_depth && address>=base && address<base+sizeof(completion_mmio));off=address-base;
    if(off>=AS02_CQC_CONTEXT && off<AS02_CQC_CONTEXT+AS02_CQC_CONTEXT_WORDS*4)
        return visible ? visible_event.context[(off-AS02_CQC_CONTEXT)/4] : 0;
    switch(off){
    case AS02_CQC_ID:return AS02_CQC_ID_VALUE;
    case AS02_CQC_ABI:return AS02_CQC_ABI_VALUE;
    case AS02_CQC_FEATURES:return receive_mode ? AS02_CQC_MESSAGE_FEATURE_VALUE : AS02_CQC_FEATURE_VALUE;
    case AS02_CQC_STATUS:return visible ? 3:0;
    case AS02_CQC_LAST_ACK:return last_ack;
    case AS02_CQC_SEQUENCE:return visible ? visible_event.sequence:last_ack;
    case AS02_CQC_PROOFS:return visible ? visible_event.proofs:0;
    case AS02_CQC_COOKIE_LO:return visible_event.cookie;
    case AS02_CQC_COOKIE_HI:return visible_event.cookie>>32;
    case AS02_CQC_WC_STATUS:return visible_event.status;
    case AS02_CQC_RECEIVED_BYTES:return visible_event.received_bytes;
    default:CHECK(0);return 0;
    }
}
void writel(u32 value,volatile void *p)
{
    uintptr_t address=(uintptr_t)p,base=(uintptr_t)completion_mmio;
    if(address<(uintptr_t)mmio+sizeof(mmio) && address>=(uintptr_t)mmio){sq_writel(value,p);return;}
    CHECK(km_spin_depth && address==base+AS02_CQC_ACK && visible && value==visible_event.sequence);
    ack_writes++;
    if(drop_next_ack){drop_next_ack=false;return;}
    visible=false;last_ack=value;
}
#endif
ktime_t ktime_get(void) { return sq_ktime_get(); }
void cpu_relax(void) { sq_cpu_relax(); }
static void completed_irq(struct ib_cq *cq,void *unused)
{
    (void)unused;CHECK(!km_spin_depth && cq==&target_cq()->ibcq);notifications++;
}
static void read_event(const char *path,struct as02_cq_event *e)
{
    FILE *f=fopen(path,"r");u32 words[24];unsigned int i;
    CHECK(f);
    for(i=0;i<24;i++)CHECK(fscanf(f,"%x",&words[i])==1);
    if(receive_mode)CHECK(fscanf(f,"%x",&e->received_bytes)==1);
    CHECK(fgetc(f)=='\n' || feof(f));fclose(f);
    e->sequence=words[0];e->proofs=words[1];e->status=words[2];
    e->cookie=words[3]|((u64)words[4]<<32);
    memcpy(e->context,words+5,sizeof(e->context));
}
static struct as02_sq_handle setup_cq(void)
{
    struct ib_cq_init_attr attr={.cqe=1};
    struct as02_sq_handle owner;
    struct ib_sge s;
    struct ib_rdma_wr work;
    unsigned int i;
    setup();CHECK(!as02_cq_router_init(&router));
    completion_queue.ibcq.device=&ibdev;completion_queue.ibcq.comp_handler=completed_irq;
    CHECK(!as02_cq_create(&completion_queue.ibcq,&attr,NULL));
    CHECK(!as02_cq_hw_init(&completion_hw,&sq,completion_mmio,sizeof(completion_mmio)));
    CHECK(!as02_cq_attach_hardware(&completion_queue,&completion_hw));
    if(separate_receive_cq){
        receive_queue.ibcq.device=&ibdev;receive_queue.ibcq.comp_handler=completed_irq;
        CHECK(!as02_cq_create(&receive_queue.ibcq,&attr,NULL));
        CHECK(!as02_cq_attach_hardware(&receive_queue,&completion_hw));
    }
    actual_qp=(struct ib_qp){.device=&ibdev,.send_cq=&completion_queue.ibcq,
        .recv_cq=&target_cq()->ibcq,.qp_num=7};
    CHECK(!as02_cq_router_bind(&router,&completion_queue,&actual_qp));
    CHECK(completion_queue.queue_refs==1 && target_cq()->queue_refs==1);
    hw.commit_cqe=as02_cq_publish;hw.cq_context=&router;
    CHECK(!as02_sq_create(&sq,7,17,EPOCH,receive_mode ? 2:1,&owner));CHECK(owner.cookie==1);
    if(receive_mode)CHECK(!as02_sq_set_receive_limits(&sq,&owner,2,2));
    for(i=0;i<2;i++){
        s=(struct ib_sge){.addr=VA+0x210,.length=receive_mode ? 128:65,.lkey=mr->layout.key};
        if(receive_mode){
            struct ib_recv_wr r={.wr_id=0xf123456789abc001ULL+i,.sg_list=&s,.num_sge=1};
            CHECK(!as02_sq_post_recv(&sq,&owner,&r));continue;
        }
        work=(struct ib_rdma_wr){.wr={.wr_id=0xf123456789abc001ULL+i,.sg_list=&s,.num_sge=1,
            .opcode=IB_WR_RDMA_READ,.send_flags=IB_SEND_SIGNALED},.remote_addr=0xe23456789abcdef0ULL,.rkey=0};
        CHECK(!as02_sq_post(&sq,&owner,&work.wr));
    }
    CHECK(refcount_read(&mr->work_refs)==3 && mr->layout.key==8 && sq.completion_clients==1);
    CHECK(!as02_cq_req_notify(&target_cq()->ibcq,IB_CQ_NEXT_COMP|IB_CQ_REPORT_MISSED_EVENTS));
    return owner;
}
static void check_wc(const struct ib_wc *wc,unsigned int n)
{
    CHECK(wc->wr_id==0xf123456789abc000ULL+n && wc->qp==&actual_qp && wc->status==IB_WC_SUCCESS &&
        wc->opcode==(receive_mode ? IB_WC_RECV:IB_WC_RDMA_READ) && wc->byte_len==65);
}
static void cleanup_cq(const struct as02_sq_handle *owner)
{
    struct ib_wc wc;
    CHECK(!visible && last_ack==2 && refcount_read(&mr->work_refs)==1);
    CHECK(!as02_cq_poll(&completion_queue.ibcq,1,&wc));
    CHECK(!as02_sq_close(&sq,owner));
    CHECK(as02_cq_hw_detach(&completion_hw)==-EBUSY);
    CHECK(!as02_cq_router_unbind(&router,&actual_qp));
    CHECK(!completion_queue.queue_refs && !target_cq()->queue_refs);
    if(separate_receive_cq)CHECK(!as02_cq_destroy(&receive_queue.ibcq,NULL));
    CHECK(!as02_cq_destroy(&completion_queue.ibcq,NULL));
    CHECK(!as02_cq_hw_detach(&completion_hw));
    CHECK(!sq.completion_clients);cleanup();
}
#ifndef AS02_CQ_CASES_LIBRARY
int main(int argc,char **argv)
{
    struct as02_sq_handle owner;
    struct ib_wc wc;
    unsigned int scenario;
    CHECK(argc==4);scenario=strtoul(argv[1],NULL,0);CHECK(scenario<5);
    receive_mode=scenario>=3;separate_receive_cq=scenario==3;
    read_event(argv[2],&records[0]);read_event(argv[3],&records[1]);
    owner=setup_cq();load_event(0);
    if(scenario==2){
        visible_event.context[18]^=1; // full high WR-id bit, not a narrowed id.
        CHECK(as02_cq_hw_poll(&completion_hw)==-EIO && visible && !last_ack &&
            !completion_queue.pending && refcount_read(&mr->work_refs)==3);
        CHECK(as02_sq_pool_destroy(&sq)==-EBUSY && as02_cq_hw_detach(&completion_hw)==-EBUSY);
        puts("KERNEL_CQ_RESULT {\"pass_test\":true,\"retained\":true,\"events\":0}");
        fflush(stdout);_Exit(0); // Deliberately retain uncertain model owners, never fake unpin.
    }
    drop_next_ack=scenario==1;
    if(scenario!=1){
        cm_run_work(&completion_hw.poll_work); // Real worker reaches CQ without application polling.
        CHECK(last_ack==1 && !visible && !atomic_read(&completion_hw.notify_users));
    }else CHECK(as02_cq_hw_poll(&completion_hw)==-EAGAIN);
    CHECK(target_cq()->pending==1 && refcount_read(&mr->work_refs)==2 && !notifications);
    if(separate_receive_cq)CHECK(!completion_queue.pending);
    irq_work_sync(&target_cq()->notify);CHECK(notifications==1);
    CHECK(as02_cq_router_unbind(&router,&actual_qp)==-EBUSY);
    if(scenario==1){
        CHECK(completion_hw.control.pending_ack && visible && last_ack==0);
        CHECK(as02_cq_hw_poll(&completion_hw)==1 && last_ack==1 && !visible &&
            completion_queue.pending==1 && refcount_read(&mr->work_refs)==2);
    }
    load_event(1);
    CHECK(as02_cq_hw_poll(&completion_hw)==-ENOSPC && visible && last_ack==1 && refcount_read(&mr->work_refs)==2);
    CHECK(as02_cq_poll(&target_cq()->ibcq,1,&wc)==1);check_wc(&wc,1);
    CHECK(refcount_read(&mr->work_refs)==2 && visible && target_cq()->pending==0);
    CHECK(as02_cq_poll(&target_cq()->ibcq,1,&wc)==1);check_wc(&wc,2);
    CHECK(refcount_read(&mr->work_refs)==1 && !visible && last_ack==2 && notifications==1);
    cleanup_cq(&owner);
    printf("KERNEL_CQ_RESULT {\"pass_test\":true,\"retained\":false,\"events\":2,\"notifications\":%u,\"ACK_writes\":%u,\"RECV\":%s,\"separate_recv_cq\":%s}\n",
        notifications,ack_writes,receive_mode ? "true":"false",separate_receive_cq ? "true":"false");
    return 0;
}
#endif
