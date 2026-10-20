/* SPDX-License-Identifier: BSD-2-Clause-Views */
/* Actual two-ring SQ/RQ/CQ/MR/MMIO C. Linux, pins/DMA, register hardware and
 * controller teardown are explicit models. Optional native snapshots are
 * consumed unedited; no loaded ib_device/physical host claim. */
#define AS02_CQ_CASES_LIBRARY
#define AS02_CQ_CUSTOM_MMIO
#include "kernel_cq_cases.c"

static u8 receive_mmio[AS02_SQC_BYTES];
static struct model receive_model;
static struct as02_sq_hw receive_hw;
static bool native_cancel;
static bool native_immediate;
static u32 native_cancel_reply[19];
/* Explicit DMA-mapper MODEL: use the same two actual host-model ring IOVAs
 * as the unedited native transcript. No real Linux mapping is changed and no
 * caller supplies a DMA address to production code. Other tests keep the
 * original model allocator addresses. */
void *__real_dma_alloc_coherent(struct device *,size_t,dma_addr_t *,int);
void *__wrap_dma_alloc_coherent(struct device *d,size_t bytes,dma_addr_t *dma,int flags)
{
    void *p=__real_dma_alloc_coherent(d,bytes,dma,flags);
    if(p && (native_cancel || native_immediate)){
        unsigned int n=km.dma_allocs-1;CHECK(n<2);
        km.dma[n].dma=n ? 0xfedcba9876542000ULL:0xfedcba9876543000ULL;
        *dma=km.dma[n].dma;
    }
    return p;
}

static u32 rq_read(u32 off)
{
    struct model *m=&receive_model;
    m->reads++;
    if(off>=AS02_SQC_STAGE && off<AS02_SQC_STAGE+60)return m->stage[(off-AS02_SQC_STAGE)/4];
    if(off>=AS02_SQC_REPLY && off<AS02_SQC_REPLY+60)return m->reply[(off-AS02_SQC_REPLY)/4];
    switch(off){
    case AS02_SQC_ID:return AS02_RQC_ID_VALUE;case AS02_SQC_ABI:return AS02_SQC_ABI_VALUE;
    case AS02_SQC_FEATURES:return native_cancel ? 3:1;case AS02_SQC_STATUS:return m->pending ? 2:1;
    case AS02_SQC_LAST_SEQUENCE:return m->last;case AS02_SQC_REPLY_ERROR:return m->error;
    case AS02_SQC_REPLY_FLAGS:return m->flags;
    case AS02_SQC_REPLY_CONSUMER_LO:return m->consumer;
    case AS02_SQC_REPLY_CONSUMER_HI:return m->consumer>>32;
    default:CHECK(0);return 0;
    }
}
static void rq_write(u32 off,u32 value)
{
    struct model *m=&receive_model;
    m->writes++;
    if(off>=AS02_SQC_STAGE && off<AS02_SQC_STAGE+60){m->stage[(off-AS02_SQC_STAGE)/4]=value;return;}
    if(off==AS02_SQC_REPLY_ACK){CHECK(m->pending && value==m->last);m->pending=false;m->acks++;return;}
    CHECK(off==AS02_SQC_DOORBELL && !m->pending && value==m->last+1 && value==m->stage[0]);
    memcpy(m->reply,m->stage,sizeof(m->reply));m->last=value;m->bells++;m->pending=true;m->error=0;m->flags=0;
    if(m->stage[1]==1){CHECK(!m->active);m->active=true;m->producer=0;m->consumer=0;m->flags=7;}
    else if(m->stage[1]==2){
        struct km_dma *mapping=NULL;struct as02_wqe w;unsigned int i;
        CHECK(m->active && pair(m->reply+11)==m->producer+1 && km.barriers>m->last_barrier);
        m->last_barrier=km.barriers;m->producer=pair(m->reply+11);m->consumer=m->producer;
        for(i=0;i<km.dma_allocs;i++)if(km.dma[i].live && km.dma[i].dma==pair(m->reply+8))mapping=&km.dma[i];
        CHECK(mapping && mapping->bytes==(64U<<m->reply[10]));
        CHECK(!as02_wqe_decode(&w,(u8 *)mapping->address+((m->producer-1)&((1U<<m->reply[10])-1))*64));
        CHECK(w.sequence==m->producer && w.epoch==pair(m->reply+4) && w.opcode==AS02_WQE_RECV);
        CHECK(m->observed_count<256);m->observed[m->observed_count++]=w;
    }else if(m->stage[1]==4){
        CHECK(native_cancel && m->active && !memcmp(m->stage,native_cancel_reply,sizeof(m->stage)));
        /* Do not synthesize or edit these proof words: they are captured
         * from the actual full generated-HLS/native RQC AXI reply. */
        memcpy(m->reply,native_cancel_reply,sizeof(m->reply));
        m->error=native_cancel_reply[15];m->flags=native_cancel_reply[16];
        m->consumer=pair(native_cancel_reply+17);
        CHECK(!m->error && m->flags==63);m->active=false;
    }else{
        CHECK(m->stage[1]==3 && m->active && pair(m->reply+11)==m->producer && pair(m->reply+13));
        m->active=false;m->flags=31;
    }
}
u32 readl(const volatile void *p)
{
    uintptr_t a=(uintptr_t)p,b=(uintptr_t)receive_mmio;u32 off;
    if(a>=b && a<b+sizeof(receive_mmio)){CHECK(km_spin_depth);return rq_read(a-b);}
    if(a>=(uintptr_t)mmio && a<(uintptr_t)mmio+sizeof(mmio))return sq_readl(p);
    b=(uintptr_t)completion_mmio;CHECK(km_spin_depth && a>=b && a<b+sizeof(completion_mmio));off=a-b;
    if(off>=AS02_CQC_CONTEXT && off<AS02_CQC_CONTEXT+AS02_CQC_CONTEXT_WORDS*4)
        return visible ? visible_event.context[(off-AS02_CQC_CONTEXT)/4]:0;
    switch(off){
    case AS02_CQC_ID:return AS02_CQC_ID_VALUE;case AS02_CQC_ABI:return AS02_CQC_ABI_VALUE;
    case AS02_CQC_FEATURES:return native_immediate ? AS02_CQC_IMMEDIATE_FEATURE_VALUE:AS02_CQC_MESSAGE_FEATURE_VALUE;
    case AS02_CQC_STATUS:return visible ? 3:0;
    case AS02_CQC_LAST_ACK:return last_ack;case AS02_CQC_SEQUENCE:return visible ? visible_event.sequence:last_ack;
    case AS02_CQC_PROOFS:return visible ? visible_event.proofs:0;case AS02_CQC_COOKIE_LO:return visible_event.cookie;
    case AS02_CQC_COOKIE_HI:return visible_event.cookie>>32;case AS02_CQC_WC_STATUS:return visible_event.status;
    case AS02_CQC_RECEIVED_BYTES:return visible_event.received_bytes;
    case AS02_CQC_CONTEXT_EXTENSION:CHECK(native_immediate);return visible ? visible_event.context_extension:0;
    case AS02_CQC_NOTIFICATION_FLAGS:CHECK(native_immediate);return visible ? visible_event.notification_flags:0;
    case AS02_CQC_NOTIFICATION:CHECK(native_immediate);return visible ? visible_event.notification:0;
    default:CHECK(0);return 0;
    }
}
void writel(u32 v,volatile void *p)
{
    uintptr_t a=(uintptr_t)p,b=(uintptr_t)receive_mmio;
    if(a>=b && a<b+sizeof(receive_mmio)){CHECK(km_spin_depth);rq_write(a-b,v);return;}
    if(a>=(uintptr_t)mmio && a<(uintptr_t)mmio+sizeof(mmio)){sq_writel(v,p);return;}
    CHECK(km_spin_depth && a==(uintptr_t)completion_mmio+AS02_CQC_ACK && visible && v==visible_event.sequence);
    visible=false;last_ack=v;ack_writes++;
}
static void model_completion(const struct as02_sq_handle *owner,unsigned int seq,bool receive)
{
    const struct as02_wqe *w=receive ? &receive_model.observed[seq-1]:&model.observed[seq-1];
    u64 cookie=owner->cookie+(receive ? 1:0);u32 i;
    memset(&records[0],0,sizeof(records[0]));records[0].sequence=last_ack+1;records[0].proofs=15;
    records[0].cookie=cookie;records[0].received_bytes=receive ? 65:0;
#define P(start,width,value) do {u64 vv=(value);for(i=0;i<(width);i++)if(vv&(1ULL<<i))records[0].context[((start)+i)/32]|=1U<<(((start)+i)%32);}while(0)
    P(0,2,3);P(20,32,w->remote_key);P(52,64,w->remote_address);P(116,64,0x210);P(180,64,w->local_address);
    P(244,32,w->local_key);P(276,32,w->length);P(308,16,w->flags);P(324,16,w->opcode);
    P(340,16,receive ? seq*2-1:seq*2);P(356,16,17);P(372,24,2);P(396,64,w->epoch);P(460,64,w->sequence);P(524,64,w->wr_id);
#undef P
}
static void compare_record(const char *path,unsigned int seq,const struct as02_wqe *w)
{
    FILE *f=fopen(path,"r");char text[129];u8 expected[64],actual[64];unsigned int i,v;
    CHECK(f);for(i=0;i<seq;i++)CHECK(fscanf(f,"%128s",text)==1);fclose(f);CHECK(strlen(text)==128);
    for(i=0;i<64;i++){CHECK(sscanf(text+(63-i)*2,"%2x",&v)==1);expected[i]=v;}
    CHECK(!as02_wqe_encode(actual,w) && !memcmp(actual,expected,64));
}
static void read_native_event(const char *path,struct as02_cq_event *e)
{
    FILE *f;u32 words[29];unsigned int n=0,i;char end;
    if(!native_immediate){read_event(path,e);return;}
    f=fopen(path,"r");CHECK(f);
    while(n<29 && fscanf(f,"%x",&words[n])==1)n++;
    CHECK(n==29 && fscanf(f," %c",&end)==EOF && words[28]==AS02_CQC_IMMEDIATE_FEATURE_VALUE);fclose(f);
    memset(e,0,sizeof(*e));e->sequence=words[0];e->proofs=words[1];e->status=words[2];
    e->cookie=pair(words+3);for(i=0;i<AS02_CQC_CONTEXT_WORDS;i++)e->context[i]=words[5+i];
    e->context_extension=words[24];e->received_bytes=words[25];
    e->notification_flags=words[26];e->notification=words[27];
}
int main(int argc,char **argv)
{
    struct ib_cq_init_attr attr={.cqe=2};struct as02_sq_handle owner;struct ib_wc wc;
    struct ib_sge sg;struct ib_recv_wr receive;struct ib_send_wr send;unsigned int seq;
    bool immediate=argc==8,flush=argc==10,native=argc==7 || argc==9 || flush || immediate;
    (void)setup_cq;(void)cleanup_cq;(void)check_wc;(void)drop_next_ack;
    CHECK(argc==1 || native);native_cancel=argc>=9;native_immediate=immediate;
    if(immediate)CHECK(!strcmp(argv[7],"immediate"));
    if(flush)CHECK(!strcmp(argv[9],"flush"));
    if(native_cancel){
        FILE *f=fopen(argv[7],"r");unsigned int i;char end;
        CHECK(f);for(i=0;i<19;i++)CHECK(fscanf(f,"%x",&native_cancel_reply[i])==1);
        CHECK(fscanf(f," %c",&end)==EOF);fclose(f);
    }
    receive_mode=true;separate_receive_cq=true;setup();
    CHECK(!as02_cq_router_init(&router));
    completion_queue.ibcq.device=&ibdev;receive_queue.ibcq.device=&ibdev;receive_queue.ibcq.comp_handler=completed_irq;
    CHECK(!as02_cq_create(&completion_queue.ibcq,&attr,NULL) && !as02_cq_create(&receive_queue.ibcq,&attr,NULL));
    CHECK(!as02_cq_hw_init(&completion_hw,&sq,completion_mmio,sizeof(completion_mmio)));
    CHECK(!as02_cq_attach_hardware(&completion_queue,&completion_hw) && !as02_cq_attach_hardware(&receive_queue,&completion_hw));
    actual_qp=(struct ib_qp){.device=&ibdev,.send_cq=&completion_queue.ibcq,.recv_cq=&receive_queue.ibcq,.qp_num=2};
    CHECK(!as02_cq_router_bind(&router,&completion_queue,&actual_qp));hw.commit_cqe=as02_cq_publish;hw.cq_context=&router;
    CHECK(!as02_sq_hw_init_receive(&receive_hw,&hw,receive_mmio,sizeof(receive_mmio),30));
    CHECK(as02_sq_independent_receive_supported(&sq));sq.next_cookie=0xfedcba9889abcdeeULL;
    CHECK(!as02_sq_create(&sq,2,17,EPOCH,1,&owner) && owner.cookie==0xfedcba9889abcdefULL);
    CHECK(!as02_sq_create_receive(&sq,&owner,1,2));
    CHECK(km.dma_allocs==2 && km.dma[0].address!=km.dma[1].address && km.dma[0].dma!=km.dma[1].dma);
    CHECK(pair(model.reply+6)==owner.cookie && pair(receive_model.reply+6)==owner.cookie+1);
    for(seq=1;seq<=2;seq++){
        sg=(struct ib_sge){.addr=VA+0x210,.length=128,.lkey=8};
        if(immediate){
            struct as02_cq_decoded decoded;
            read_native_event(argv[seq*2],&records[0]);
            CHECK(!as02_cq_decode_profile(&decoded,&records[0],AS02_WQE_PROFILE_IMMEDIATE));
            CHECK(decoded.work.opcode==AS02_WQE_RECV && decoded.work.immediate==0);
            sg.addr=decoded.work.local_address;sg.length=decoded.work.length;
        }
        receive=(struct ib_recv_wr){.wr_id=0xf123456789abc000ULL+seq,.sg_list=&sg,.num_sge=1};
        CHECK(!as02_sq_post_recv(&sq,&owner,&receive));
        CHECK(receive_model.producer==seq && model.producer==seq-1 && refcount_read(&mr->work_refs)==2);
        if(native)compare_record(argv[6],seq,&receive_model.observed[seq-1]);
        sg.addr=VA+0x210;sg.length=65;send=(struct ib_send_wr){.wr_id=0xf223456789abc000ULL+seq,.sg_list=&sg,.num_sge=1,
            .opcode=IB_WR_SEND,.send_flags=IB_SEND_SIGNALED};
        CHECK(!as02_sq_post(&sq,&owner,&send));
        CHECK(model.producer==seq && receive_model.producer==seq && refcount_read(&mr->work_refs)==3);
        if(native){compare_record(argv[5],seq,&model.observed[seq-1]);read_native_event(argv[seq*2-1],&records[0]);}
        else model_completion(&owner,seq,false);
        load_event(0);CHECK(as02_cq_hw_poll(&completion_hw)==1);
        CHECK(as02_cq_poll(&completion_queue.ibcq,1,&wc)==1 && wc.opcode==IB_WC_SEND && wc.wr_id==send.wr_id && wc.byte_len==0);
        CHECK(!wc.wc_flags && !wc.ex.imm_data);
        CHECK(!receive_queue.pending && refcount_read(&mr->work_refs)==2 && last_ack==seq*2-1);
        if(native)read_native_event(argv[seq*2],&records[0]);else model_completion(&owner,seq,true);
        load_event(0);CHECK(as02_cq_hw_poll(&completion_hw)==1);
        CHECK(as02_cq_poll(&receive_queue.ibcq,1,&wc)==1 &&
            wc.opcode==((immediate && records[0].notification_flags==3) ? IB_WC_RECV_RDMA_WITH_IMM:IB_WC_RECV) &&
            wc.wr_id==receive.wr_id && wc.byte_len==65);
        if(immediate)CHECK(wc.wc_flags==IB_WC_WITH_IMM && wc.ex.imm_data==cpu_to_be32(records[0].notification));
        else CHECK(!wc.wc_flags && !wc.ex.imm_data);
        CHECK(!completion_queue.pending && refcount_read(&mr->work_refs)==1 && last_ack==seq*2);
    }
    if(native_cancel){
        sg=(struct ib_sge){.addr=VA+0x210,.length=128,.lkey=8};
        receive=(struct ib_recv_wr){.wr_id=0xf123456789abc003ULL,.sg_list=&sg,.num_sge=1};
        CHECK(!as02_sq_post_recv(&sq,&owner,&receive));
        compare_record(argv[8],1,&receive_model.observed[2]);
        CHECK(refcount_read(&mr->work_refs)==2 && !km.dma_frees && last_ack==4 && !visible);
        if(flush)CHECK(!as02_sq_flush_receive(&sq,&owner));
        else{CHECK(!as02_cq_router_abandon(&router,&actual_qp));CHECK(!as02_sq_cancel_receive(&sq,&owner));}
        if(flush){
            CHECK(as02_cq_poll(&receive_queue.ibcq,1,&wc)==1 && wc.wr_id==receive.wr_id &&
                wc.status==IB_WC_WR_FLUSH_ERR && wc.opcode==IB_WC_RECV && !wc.byte_len);
            CHECK(!as02_cq_poll(&receive_queue.ibcq,1,&wc));
        }
        CHECK(refcount_read(&mr->work_refs)==1 && !km.dma_frees && last_ack==4 && !visible &&
            !receive_queue.pending && !completion_queue.pending && receive_model.last==5 && !receive_model.active);
    }
    CHECK(!as02_sq_close(&sq,&owner) && !model.active && !receive_model.active && km.dma_frees==2);
    CHECK(!as02_cq_router_unbind(&router,&actual_qp));
    CHECK(!as02_cq_destroy(&receive_queue.ibcq,NULL) && !as02_cq_destroy(&completion_queue.ibcq,NULL));
    CHECK(!as02_cq_hw_detach(&completion_hw));CHECK(!as02_sq_hw_detach(&receive_hw));cleanup();
    printf("KERNEL_INDEPENDENT_QUEUES_RESULT {\"pass_test\":true,\"native_snapshots_unedited\":%s,\"native_cancel_reply_unedited\":%s,\"native_receive_flush_WC\":%s,\"native_Immediate_receive_WC\":%s,\"independent_coherent_rings\":true,\"distinct_queue_cookies\":true,\"SEND_before_RECV_same_WQE_sequence\":true,\"completed_SENDs\":2,\"completed_RECVs\":2,\"hardware_verified\":false}\n",native?"true":"false",native_cancel?"true":"false",flush?"true":"false",immediate?"true":"false");
    return 0;
}
