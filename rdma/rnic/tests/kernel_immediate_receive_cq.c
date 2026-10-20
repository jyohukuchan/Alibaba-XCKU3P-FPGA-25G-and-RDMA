/* SPDX-License-Identifier: BSD-2-Clause-Views */
/* Actual RQ/CQ/SQ/MR C consumes unedited actual RTL event files. Linux,
 * coherent DMA, hardware register access and incoming data are models. */
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

static struct as02_cq send_cq,recv_cq;
static struct as02_cq_router router;
static struct as02_cq_hw cq_hw;
static struct ib_qp qp;
static u8 cq_mmio[AS02_CQC_BYTES];
static struct as02_cq_event events[8],visible_event;
static bool visible,lose_ack;
static u32 last_ack;
static const u32 notifications[]={0,0x01234567,0x80000000,0xffffffff};

u32 readl(const volatile void *p)
{
    uintptr_t address=(uintptr_t)p,base=(uintptr_t)cq_mmio;u32 off;
    if(address>=(uintptr_t)mmio && address<(uintptr_t)mmio+sizeof(mmio))return sq_readl(p);
    CHECK(km_spin_depth && address>=base && address<base+sizeof(cq_mmio));off=address-base;
    if(off>=AS02_CQC_CONTEXT && off<AS02_CQC_CONTEXT+AS02_CQC_CONTEXT_WORDS*4)
        return visible ? visible_event.context[(off-AS02_CQC_CONTEXT)/4]:0;
    switch(off){
    case AS02_CQC_ID:return AS02_CQC_ID_VALUE;
    case AS02_CQC_ABI:return AS02_CQC_ABI_VALUE;
    case AS02_CQC_FEATURES:return AS02_CQC_IMMEDIATE_FEATURE_VALUE;
    case AS02_CQC_STATUS:return visible ? 3:0;
    case AS02_CQC_LAST_ACK:return last_ack;
    case AS02_CQC_SEQUENCE:return visible ? visible_event.sequence:last_ack;
    case AS02_CQC_PROOFS:return visible_event.proofs;
    case AS02_CQC_COOKIE_LO:return visible_event.cookie;
    case AS02_CQC_COOKIE_HI:return visible_event.cookie>>32;
    case AS02_CQC_WC_STATUS:return visible_event.status;
    case AS02_CQC_RECEIVED_BYTES:return visible_event.received_bytes;
    case AS02_CQC_CONTEXT_EXTENSION:return visible_event.context_extension;
    case AS02_CQC_NOTIFICATION:return visible_event.notification;
    case AS02_CQC_NOTIFICATION_FLAGS:return visible_event.notification_flags;
    default:CHECK(0);return 0;
    }
}
void writel(u32 value,volatile void *p)
{
    uintptr_t address=(uintptr_t)p,base=(uintptr_t)cq_mmio;
    if(address>=(uintptr_t)mmio && address<(uintptr_t)mmio+sizeof(mmio)){sq_writel(value,p);return;}
    CHECK(km_spin_depth && address==base+AS02_CQC_ACK && visible && value==visible_event.sequence);
    if(lose_ack){lose_ack=false;return;}
    visible=false;last_ack=value;
}
ktime_t ktime_get(void){return sq_ktime_get();}
void cpu_relax(void){sq_cpu_relax();}
static void load_file(const char *path,struct as02_cq_event *e)
{
    u32 words[29];unsigned int i;FILE *f=fopen(path,"r");CHECK(f);
    for(i=0;i<29;i++)CHECK(fscanf(f,"%x",&words[i])==1);
    CHECK(fgetc(f)=='\n' || feof(f));fclose(f);
    CHECK(words[28]==AS02_CQC_IMMEDIATE_FEATURE_VALUE);
    e->sequence=words[0];e->proofs=words[1];e->status=words[2];e->cookie=words[3]|((u64)words[4]<<32);
    memcpy(e->context,words+5,sizeof(e->context));e->context_extension=words[24];
    e->received_bytes=words[25];e->notification_flags=words[26];e->notification=words[27];
}
static void set_bits(struct as02_cq_event *e,unsigned int first,unsigned int width,u32 value)
{
    unsigned int i;
    for(i=0;i<width;i++){
        unsigned int bit=first+i;u32 *word=bit<608 ? &e->context[bit/32]:&e->context_extension;
        *word=(*word&~(1U<<(bit%32)))|(((value>>i)&1U)<<(bit%32));
    }
}
static void decoder_checks(void)
{
    struct as02_cq_decoded d;unsigned int i;
    for(i=0;i<8;i++){
        struct as02_cq_event bad;
        CHECK(!as02_cq_decode_profile(&d,&events[i],1));
        CHECK(d.work.opcode==AS02_WQE_RECV && !d.work.immediate && d.work.length==(i<4 ? 128:1) &&
            d.notification==notifications[i%4] && d.notification_flags==(i<4 ? 1:3) && d.received_bytes==65);
        CHECK(as02_cq_decode(&d,&events[i])==-EIO);
        bad=events[i];bad.notification_flags=2;CHECK(as02_cq_decode_profile(&d,&bad,1)==-EIO);
        bad=events[i];bad.context_extension|=0x1000;CHECK(as02_cq_decode_profile(&d,&bad,1)==-EIO);
        bad=events[i];set_bits(&bad,588,32,1);CHECK(as02_cq_decode_profile(&d,&bad,1)==-EIO);
    }
    /* Semantic decoder-only vectors, never delivered as native completions. */
    for(i=5;i<=6;i++){
        struct as02_cq_event e=events[0];
        set_bits(&e,324,16,i);set_bits(&e,588,32,0x81234567);
        e.notification=e.notification_flags=e.received_bytes=0;
        CHECK(!as02_cq_decode_profile(&d,&e,1) && d.work.immediate==0x81234567 && d.work.opcode==i);
        CHECK(as02_cq_decode(&d,&e)==-EIO);
    }
}
static void check_wc(const struct ib_wc *wc,unsigned int i)
{
    CHECK(wc->qp==&qp && wc->wr_id==0xf123456789abc001ULL+i && wc->status==IB_WC_SUCCESS &&
        wc->byte_len==65 && wc->wc_flags==IB_WC_WITH_IMM &&
        be32_to_cpu(wc->ex.imm_data)==notifications[i%4] &&
        wc->opcode==(i<4 ? IB_WC_RECV:IB_WC_RECV_RDMA_WITH_IMM));
}
int main(int argc,char **argv)
{
    struct as02_sq_handle owner;struct ib_cq_init_attr attr={.cqe=1};
    struct ib_wc wc;unsigned int i;bool corrupt;
    CHECK(argc==10);corrupt=atoi(argv[1])!=0;
    for(i=0;i<8;i++)load_file(argv[i+2],&events[i]);
    decoder_checks();
    setup();CHECK(!as02_cq_router_init(&router));
    send_cq.ibcq.device=&ibdev;recv_cq.ibcq.device=&ibdev;
    CHECK(!as02_cq_create(&send_cq.ibcq,&attr,NULL) && !as02_cq_create(&recv_cq.ibcq,&attr,NULL));
    CHECK(!as02_cq_hw_init(&cq_hw,&sq,cq_mmio,sizeof(cq_mmio)));
    CHECK(!as02_cq_attach_hardware(&send_cq,&cq_hw) && !as02_cq_attach_hardware(&recv_cq,&cq_hw));
    qp=(struct ib_qp){.device=&ibdev,.send_cq=&send_cq.ibcq,.recv_cq=&recv_cq.ibcq,.qp_num=7};
    CHECK(!as02_cq_router_bind(&router,&send_cq,&qp));hw.commit_cqe=as02_cq_publish;hw.cq_context=&router;
    CHECK(!as02_sq_create(&sq,7,17,EPOCH,4,&owner) && owner.cookie==1);
    CHECK(!as02_sq_set_receive_limits(&sq,&owner,1,8));
    for(i=0;i<8;i++){
        struct ib_sge s={.addr=VA+0x210,.length=i<4 ? 128:1,.lkey=mr->layout.key};
        struct ib_recv_wr wr={.wr_id=0xf123456789abc001ULL+i,.sg_list=&s,.num_sge=1};
        CHECK(!as02_sq_post_recv(&sq,&owner,&wr));
    }
    CHECK(refcount_read(&mr->work_refs)==9 && as02_sq_close(&sq,&owner)==-EBUSY);
    /* Close marked the queue stopping, but genuine already-owned native
     * completions still progress; no new post or fake cancellation occurs. */
    visible_event=events[0];visible=true;
    if(corrupt){
        visible_event.notification_flags=2;
        CHECK(as02_cq_hw_poll(&cq_hw)==-EIO && visible && !last_ack && !recv_cq.pending &&
            refcount_read(&mr->work_refs)==9 && as02_sq_pool_destroy(&sq)==-EBUSY);
        puts("IMMEDIATE_KERNEL_CQ {\"pass_test\":true,\"corrupt_notification_retains_all_refs\":true}");fflush(stdout);_Exit(0);
    }
    lose_ack=true;CHECK(as02_cq_hw_poll(&cq_hw)==-EAGAIN && cq_hw.control.pending_ack && recv_cq.pending==1 &&
        refcount_read(&mr->work_refs)==8 && !last_ack);
    CHECK(as02_cq_hw_poll(&cq_hw)==1 && last_ack==1 && !visible && recv_cq.pending==1 && refcount_read(&mr->work_refs)==8);
    for(i=1;i<8;i++){
        visible_event=events[i];visible=true;
        CHECK(as02_cq_hw_poll(&cq_hw)==-ENOSPC && visible && last_ack==i && refcount_read(&mr->work_refs)==9-i);
        CHECK(as02_cq_poll(&recv_cq.ibcq,1,&wc)==1);check_wc(&wc,i-1);
        CHECK(as02_cq_hw_poll(&cq_hw)==1 && !visible && last_ack==i+1 && refcount_read(&mr->work_refs)==8-i);
        CHECK(!send_cq.pending);
    }
    CHECK(as02_cq_poll(&recv_cq.ibcq,1,&wc)==1);check_wc(&wc,7);
    CHECK(!recv_cq.pending && !send_cq.pending && refcount_read(&mr->work_refs)==1);
    CHECK(!as02_sq_close(&sq,&owner) && !as02_cq_router_unbind(&router,&qp));
    CHECK(!as02_cq_destroy(&recv_cq.ibcq,NULL) && !as02_cq_destroy(&send_cq.ibcq,NULL));
    CHECK(!as02_cq_hw_detach(&cq_hw));cleanup();
    puts("IMMEDIATE_KERNEL_CQ {\"pass_test\":true,\"actual_kernel_C_WCs\":8,\"unedited_RTL_events\":true,\"zero_notification_keeps_WITH_IMM\":true,\"WRITE_notification_not_RQ_data\":true,\"ACK_reconcile_and_CQ_backpressure\":true,\"Linux_DMA_MMIO_models\":true}");
    return 0;
}
