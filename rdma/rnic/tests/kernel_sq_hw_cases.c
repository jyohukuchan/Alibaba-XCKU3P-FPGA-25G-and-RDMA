/* SPDX-License-Identifier: BSD-2-Clause-Views */
/* Actual SQ/IO/HW/WR/MR C, EXPLICIT MMIO/clock/CQ/umem/DMA models. */
#include "kernel_sq_hw_model.h"
#include "sq_hw.h"
#define CHECK(x) do { if(!(x)){fprintf(stderr,"CHECK %d %s\n",__LINE__,#x);abort();} } while(0)
#define VA 0xfedcba9876543000ULL
#define EPOCH 0x9123456700000001ULL
static u8 mmio[AS02_SQC_BYTES];
struct model {
    u32 id,abi,features,last,stage[15],reply[15],error,flags;
    u64 consumer,producer,now;
    bool active,pending,stop_clock,drop_ack,withhold,cq_full,bad_consumer;
    int corrupt_word,corrupt_stage,read_error,write_error;
    unsigned int delay,polls,reads,writes,bells,acks,relaxes,cqes,last_barrier;
    u32 override_error,override_flags;bool override,unsafe_retire;
    u32 observed_count;struct as02_wqe observed[256];
} model;
static struct as02_sq_hw hw;
static struct as02_mr_pool mrs;
static struct as02_sq_pool sq;
static struct ib_device ibdev;
static struct device dma_dev;
static u32 generation;
static struct as02_user_mr *mr;
static u64 pair(const u32 *p) { return p[0]|((u64)p[1]<<32); }
static void fresh(void)
{
    memset(&model,0,sizeof(model));model.id=AS02_SQC_ID_VALUE;model.abi=AS02_SQC_ABI_VALUE;model.features=1;
    model.corrupt_word=-1;model.corrupt_stage=-1;model.read_error=-1;model.write_error=-1;
}
static u32 state(void)
{
    if(model.pending) {
        model.polls++;
        if(model.withhold || model.polls<=model.delay)return model.last==0xffffffffU ? 32:0;
        return AS02_SQC_RESPONSE|(model.last==0xffffffffU ? AS02_SQC_EXHAUSTED:0);
    }
    return model.last==0xffffffffU ? AS02_SQC_EXHAUSTED:AS02_SQC_AVAILABLE;
}
static int model_read(void *unused,u32 off,u32 *value)
{
    (void)unused;model.reads++;
    if(model.read_error==(int)off){model.read_error=-1;return -EIO;}
    *value=0;
    if(off>=AS02_SQC_STAGE && off<AS02_SQC_STAGE+60) {
        unsigned int i=(off-AS02_SQC_STAGE)/4;*value=model.stage[i];
        if(model.corrupt_stage==(int)i)*value^=0x80000000U;
    } else if(off>=AS02_SQC_REPLY && off<AS02_SQC_REPLY+60) {
        unsigned int i=(off-AS02_SQC_REPLY)/4;*value=model.reply[i];
        if(model.corrupt_word==(int)i)*value^=0x80000000U;
    } else switch(off) {
    case AS02_SQC_ID:*value=model.id;break;
    case AS02_SQC_ABI:*value=model.abi;break;
    case AS02_SQC_FEATURES:*value=model.features;break;
    case AS02_SQC_STATUS:*value=state();break;
    case AS02_SQC_LAST_SEQUENCE:*value=model.last;break;
    case AS02_SQC_REPLY_ERROR:*value=model.error;break;
    case AS02_SQC_REPLY_FLAGS:*value=model.flags;break;
    case AS02_SQC_REPLY_CONSUMER_LO:*value=model.consumer+(model.bad_consumer ? 1:0);break;
    case AS02_SQC_REPLY_CONSUMER_HI:*value=model.consumer>>32;break;
    default:CHECK(0);
    }
    return 0;
}
static int model_write(void *unused,u32 off,u32 value)
{
    (void)unused;model.writes++;
    if(model.write_error==(int)off){model.write_error=-1;return -EIO;}
    if(off>=AS02_SQC_STAGE && off<AS02_SQC_STAGE+60)model.stage[(off-AS02_SQC_STAGE)/4]=value;
    else if(off==AS02_SQC_DOORBELL) {
        u32 op=model.stage[1];CHECK(!model.pending && value==model.last+1 && value==model.stage[0] && value);
        memcpy(model.reply,model.stage,sizeof(model.reply));model.last=value;model.bells++;model.pending=true;
        model.polls=0;model.error=0;model.flags=0;
        if(op==1){CHECK(!model.active);model.active=true;model.producer=0;model.consumer=0;model.flags=7;}
        else if(op==2){
            unsigned int i;CHECK(model.active && pair(model.reply+11)==model.producer+1);
            model.producer=pair(model.reply+11);model.consumer=model.producer;
            if(km.dma_allocs) {
                struct km_dma *mapping=NULL;struct as02_wqe work;
                CHECK(km_spin_depth>=2 && km.barriers>model.last_barrier);model.last_barrier=km.barriers;
                for(i=0;i<km.dma_allocs;i++)if(km.dma[i].live && km.dma[i].dma==pair(model.reply+8))mapping=&km.dma[i];
                CHECK(mapping && mapping->bytes==(64U<<model.reply[10]));
                CHECK(!as02_wqe_decode_profile(&work,(u8 *)mapping->address+((model.producer-1)&((1U<<model.reply[10])-1))*64,
                    (model.features&AS02_SQC_IMMEDIATE_FEATURE) ? AS02_WQE_PROFILE_IMMEDIATE:0));
                CHECK(work.sequence==model.producer && work.epoch==pair(model.reply+4));
                CHECK(model.observed_count<256);model.observed[model.observed_count++]=work;
            }
        } else if(op==3){
            CHECK(model.active && pair(model.reply+11)==model.producer && pair(model.reply+13));
            if(model.unsafe_retire)model.error=35;
            else {model.active=false;model.flags=31;}
        } else if(op==4){
            CHECK(model.id==AS02_RQC_ID_VALUE && (model.features&AS02_RQC_CANCEL_FEATURE) && model.active &&
                pair(model.reply+11)==model.producer && pair(model.reply+13));
            model.active=false;model.consumer=model.producer;model.flags=63;
        } else CHECK(0);
        if(model.override){model.error=model.override_error;model.flags=model.override_flags;}
    } else if(off==AS02_SQC_REPLY_ACK){
        CHECK(model.pending && value==model.last);model.acks++;
        if(!model.drop_ack)model.pending=false;
    } else CHECK(0);
    return 0;
}
static u64 model_time(void *unused) { (void)unused;return model.stop_clock ? model.now:model.now++; }
static void model_relax(void *unused) { (void)unused;model.relaxes++; }
static const struct as02_sqc_transport model_io={.read32=model_read,.write32=model_write,.time_us=model_time,.relax=model_relax};
u32 readl(const volatile void *p)
{
    u32 value=0;ptrdiff_t off=(const volatile u8 *)p-mmio;
    CHECK(km_spin_depth && off>=0 && off<AS02_SQC_BYTES);CHECK(!model_read(NULL,off,&value));return value;
}
void writel(u32 v,volatile void *p)
{
    ptrdiff_t off=(volatile u8 *)p-mmio;CHECK(km_spin_depth && off>=0 && off<AS02_SQC_BYTES);
    CHECK(!model_write(NULL,off,v));
}
ktime_t ktime_get(void) { CHECK(km_spin_depth);return model_time(NULL); }
void cpu_relax(void) { CHECK(km_spin_depth);model.relaxes++; }
static int cq_commit(void *unused,const struct as02_sq_completion *c)
{
    (void)unused;CHECK(km_spin_depth>=2 && c->sequence && c->sequence<=model.observed_count);
    CHECK(c->wr_id==model.observed[c->sequence-1].wr_id);
    if(model.cq_full)return -ENOSPC;
    model.cqes++;return 0;
}
static int epoch(void *unused,u64 cookie,u32 floor,struct as02_mr_epoch_proof *out)
{
    (void)unused;CHECK(!km_spin_depth);generation=floor;
    *out=(struct as02_mr_epoch_proof){.cookie=cookie,.floor=floor,.qps_closed=1,.mr_table_invalid=1,.dma_drained=1};return 0;
}
static int publish_mr(void *unused,const struct as02_mr_layout *m,struct as02_mr_publish_proof *out)
{
    (void)unused;CHECK(!km_spin_depth);generation++;
    *out=(struct as02_mr_publish_proof){.cookie=m->cookie,.slot=m->slot,.key=(generation<<3)|m->slot};return 0;
}
static int revoke_mr(void *unused,const struct as02_mr_layout *m,struct as02_mr_revoke_proof *out)
{
    (void)unused;CHECK(!km_spin_depth);
    *out=(struct as02_mr_revoke_proof){.cookie=m->cookie,.slot=m->slot,.generation=generation,.invalidated=1,.dma_drained=1};return 0;
}
static const struct as02_mr_hw_ops mr_ops={.reset_epoch=epoch,.publish=publish_mr,.invalidate_and_drain=revoke_mr};
static void setup(void)
{
    const u64 epochs[8]={0};fresh();atomic_store(&ibdev.dev.references,1);atomic_store(&dma_dev.references,1);
    CHECK(!as02_sq_hw_init(&hw,mmio,sizeof(mmio),30,cq_commit,NULL));
    CHECK(!as02_mr_pool_init(&mrs,&ibdev,&mr_ops,NULL,0));CHECK(!as02_mr_pool_start_epoch(&mrs,0));
    mr=as02_user_mr_prepare(&mrs,0x10003,VA,8192,17,7,15);CHECK(!IS_ERR(mr));CHECK(!as02_user_mr_publish(mr));
    CHECK(!as02_sq_pool_init(&sq,&mrs,&dma_dev,&as02_sqc_sq_hw_ops,&hw,epochs));
}
static void cleanup(void)
{
    CHECK(!as02_sq_pool_destroy(&sq));CHECK(!as02_user_mr_close(mr));CHECK(!as02_mr_pool_destroy(&mrs));
    CHECK(!atomic_load(&km.heap_live) && !atomic_load(&km.umem_live) && !atomic_load(&km.module_refs));
    CHECK(km.dma_allocs==km.dma_frees);CHECK(!as02_sq_hw_detach(&hw));
    CHECK(atomic_load(&ibdev.dev.references)==1 && atomic_load(&dma_dev.references)==1);
}
static struct ib_rdma_wr wr(struct ib_sge *s,u64 id)
{
    *s=(struct ib_sge){.addr=VA+1,.length=65,.lkey=mr->layout.key};
    return (struct ib_rdma_wr){.wr={.wr_id=id,.sg_list=s,.num_sge=1,.opcode=IB_WR_RDMA_WRITE,.send_flags=IB_SEND_SIGNALED},
        .remote_addr=0xe23456789abcd002ULL,.rkey=0};
}
static int complete(const struct as02_sq_handle *h,u64 seq)
{
    struct as02_sq_completion_proof p={.owner=*h,.sequence=seq,.flags=3,.status=IB_WC_SUCCESS};
    return as02_sq_complete(&sq,&p);
}
static void words(u32 *w,u32 op,u64 producer,u64 nonce)
{
    memset(w,0,60);w[1]=op;w[2]=7;w[3]=17;w[4]=(u32)EPOCH;w[5]=EPOCH>>32;
    w[6]=0x89abcdef;w[7]=0xfedcba98;w[8]=0x76543000;w[9]=0xfedcba98;w[10]=1;
    w[11]=producer;w[12]=producer>>32;w[13]=nonce;w[14]=nonce>>32;
}
static void io_init(struct as02_sqc_io *c) { fresh();CHECK(!as02_sqc_io_init(c,&model_io,NULL,30)); }
static void retained(void)
{
    CHECK(atomic_load(&km.heap_live)>0 && atomic_load(&km.umem_live)==1 && km.dma_allocs==1 && !km.dma_frees);
    CHECK(refcount_read(&mr->work_refs)==2 && as02_user_mr_close(mr)==-EBUSY);
    CHECK(as02_sq_pool_destroy(&sq)==-EBUSY && as02_mr_pool_destroy(&mrs)==-EBUSY);
}
static void normal(void)
{
    struct as02_sq_handle h;struct ib_sge s;struct ib_rdma_wr work;
    setup();CHECK(!as02_sq_create(&sq,7,17,EPOCH,1,&h));work=wr(&s,0xf123456789abcdefULL);
    CHECK(!as02_sq_post(&sq,&h,&work.wr));CHECK(refcount_read(&mr->work_refs)==2 && model.consumer==1 && !model.cqes);
    CHECK(model.observed[0].remote_key==0 && model.observed[0].remote_address==work.remote_addr);
    model.cq_full=true;CHECK(complete(&h,1)==-ENOSPC && refcount_read(&mr->work_refs)==2);
    model.cq_full=false;CHECK(!complete(&h,1) && refcount_read(&mr->work_refs)==1);
    work.wr.wr_id++;CHECK(!as02_sq_post(&sq,&h,&work.wr));CHECK(!complete(&h,2));
    CHECK(!as02_sq_close(&sq,&h));CHECK(model.bells==4 && model.acks==4 && model.cqes==2);cleanup();
}
static void corrupt_allocate(int n)
{
    struct as02_sq_handle h;struct as02_sqc_reply late;
    setup();model.corrupt_word=n;CHECK(as02_sq_create(&sq,7,17,EPOCH,1,&h)==-EPROTO);
    CHECK(hw.control.pending && hw.control.uncertain && model.bells==1 && !model.acks && !km.dma_frees);
    model.corrupt_word=-1;CHECK(!as02_sq_hw_reconcile(&hw,&late));
    CHECK(late.flags==7 && !hw.control.pending);CHECK(!as02_sq_close(&sq,&h));cleanup();
}
static void timeout_post(bool lost_ack)
{
    struct as02_sq_handle h;struct ib_sge s;struct ib_rdma_wr work;struct as02_sqc_reply late;unsigned int rw;
    setup();CHECK(!as02_sq_create(&sq,7,17,EPOCH,1,&h));work=wr(&s,0x8123456789abcdefULL);
    model.drop_ack=lost_ack;model.withhold=!lost_ack;
    CHECK(as02_sq_post(&sq,&h,&work.wr)==-ETIMEDOUT && hw.control.pending && hw.control.uncertain);
    CHECK(as02_sq_close(&sq,&h)==-EBUSY);retained();
    model.drop_ack=false;model.withhold=false;CHECK(!as02_sq_hw_reconcile(&hw,&late));
    CHECK(complete(&h,1)==-ESTALE && !model.cqes && as02_sq_close(&sq,&h)==-EBUSY);retained();
    rw=model.reads+model.writes;CHECK(!as02_sq_hw_detach(&hw));CHECK(as02_sq_hw_reconcile(&hw,&late)==-ENODEV);
    CHECK(as02_sq_hw_init(&hw,mmio,sizeof(mmio),30,cq_commit,NULL)==-ENODEV);
    CHECK(model.reads+model.writes==rw);retained();
}
static void bad_flags(int n)
{
    struct as02_sqc_io c={0};struct as02_sqc_reply r;u32 w[15];
    io_init(&c);words(w,1,0,0);model.override=true;
    model.override_error=n==0 ? 255:(n==1 ? 35:0);model.override_flags=n==1 ? 7:3;
    if(n==3){model.override_flags=7;model.bad_consumer=true;}
    if(n==4){model.override_error=128;model.override_flags=0;}
    CHECK(as02_sqc_io_execute(&c,w,&r)==-EPROTO && c.pending && c.uncertain && !model.acks);
    CHECK(!r.words[0] && !r.flags);
}
static void prebell(int n)
{
    struct as02_sqc_io c={0};struct as02_sqc_reply r;u32 w[15];
    io_init(&c);words(w,1,0,0);
    if(n==0)model.write_error=AS02_SQC_STAGE+28;
    if(n==1)model.read_error=AS02_SQC_STAGE+28;
    if(n==2)model.corrupt_stage=7;
    CHECK(as02_sqc_io_execute(&c,w,&r)==-EIO && !c.pending && !c.uncertain && !c.sequence && !model.bells);
    model.corrupt_stage=-1;CHECK(!as02_sqc_io_execute(&c,w,&r));CHECK(c.sequence==1 && model.last==1 && model.acks==1);
}
static void known_retire_error(void)
{
    struct as02_sq_handle h;setup();CHECK(!as02_sq_create(&sq,7,17,EPOCH,1,&h));
    model.unsafe_retire=true;CHECK(as02_sq_close(&sq,&h)==-EIO);
    CHECK(model.active && !km.dma_frees && !hw.control.pending && model.acks==2);
    model.unsafe_retire=false;CHECK(!as02_sq_close(&sq,&h));cleanup();
}
static void foreign(void)
{
    struct as02_sqc_io c={0};struct as02_sqc_reply r;u32 w[15];unsigned int rw;
    io_init(&c);model.last=1;words(w,1,0,0);CHECK(as02_sqc_io_execute(&c,w,&r)==-EPROTO);
    CHECK(c.uncertain && !c.pending && !model.writes);rw=model.reads;
    CHECK(as02_sqc_io_execute(&c,w,&r)==-EBUSY && model.reads==rw);
    CHECK(!as02_sqc_io_detach(&c));CHECK(as02_sqc_io_init(&c,&model_io,NULL,30)==-ENODEV && model.reads==rw);
}
static void final_sequence(void)
{
    struct as02_sqc_io c={0};struct as02_sqc_reply r;u32 w[15];unsigned int rw;
    io_init(&c);c.sequence=0xfffffffeU;model.last=0xfffffffeU;words(w,1,0,0);
    CHECK(!as02_sqc_io_execute(&c,w,&r) && c.sequence==0xffffffffU && !c.pending);
    rw=model.reads+model.writes;words(w,2,1,0);CHECK(as02_sqc_io_execute(&c,w,&r)==-ENOSPC);
    CHECK(model.reads+model.writes==rw && model.bells==1);
}
static void shape(int n)
{
    struct as02_sqc_io c={0};struct as02_sqc_reply r;u32 w[15];unsigned int rw;
    io_init(&c);words(w,1,0,0);
    switch(n){case 0:w[2]=0x80000007;break;case 1:w[3]=0x10011;break;case 2:w[4]=w[5]=0;break;
    case 3:w[6]=w[7]=0;break;case 4:w[8]|=1;break;case 5:w[8]=0xffffffc0;w[9]=0xffffffff;break;
    case 6:w[10]=9;break;case 7:w[11]=1;break;case 8:w[13]=1;break;case 9:w[1]=4;break;
    case 10:w[1]=2;break;case 11:w[1]=3;break;case 12:w[8]=0xffffff80;w[9]=0xffffffff;break;}
    rw=model.reads+model.writes;
    if(n==12)CHECK(!as02_sqc_io_execute(&c,w,&r));
    else {CHECK(as02_sqc_io_execute(&c,w,&r)<0);CHECK(!model.bells && model.reads+model.writes==rw && !r.flags);}
}
static struct as02_sq_handle threaded_owner;
static void *poster(void *opaque)
{
    unsigned int i;struct ib_sge s;struct ib_rdma_wr work=wr(&s,(u64)(uintptr_t)opaque<<32);
    for(i=0;i<8;i++){work.wr.wr_id++;CHECK(!as02_sq_post(&sq,&threaded_owner,&work.wr));}return NULL;
}
static void threads(void)
{
    pthread_t a,b;unsigned int i;setup();CHECK(!as02_sq_create(&sq,7,17,EPOCH,4,&threaded_owner));
    CHECK(!pthread_create(&a,NULL,poster,(void *)1) && !pthread_create(&b,NULL,poster,(void *)2));
    CHECK(!pthread_join(a,NULL) && !pthread_join(b,NULL));CHECK(model.observed_count==16 && refcount_read(&mr->work_refs)==17);
    for(i=1;i<=16;i++)CHECK(!complete(&threaded_owner,i));
    CHECK(model.cqes==16 && refcount_read(&mr->work_refs)==1);CHECK(!as02_sq_close(&sq,&threaded_owner));cleanup();
}
int main(int argc,char **argv)
{
    int n=argc>2 ? atoi(argv[2]):0,scenario=argc>1 ? atoi(argv[1]):-1;
    switch(scenario){
    case 0:{struct as02_sq_hw x={0};fresh();CHECK(as02_sq_hw_init(&x,mmio,sizeof(mmio),30,NULL,NULL)==-EINVAL && !model.reads);
        if(n==0)model.id^=1;
        if(n==1)model.abi^=1;
        if(n==2)model.features=3;
        if(n==3)model.last=1;
        CHECK(as02_sq_hw_init(&x,mmio,sizeof(mmio),30,cq_commit,NULL)<0 && !model.writes);break;}
    case 1:normal();break;case 2:corrupt_allocate(n);break;case 3:bad_flags(n);break;
    case 4:timeout_post(false);break;case 5:timeout_post(true);break;case 6:prebell(n);break;
    case 7:known_retire_error();break;case 8:foreign();break;case 9:final_sequence();break;case 10:shape(n);break;case 11:threads();break;
    case 12:{struct as02_sqc_io c={0};struct as02_sqc_reply r;u32 w[15];io_init(&c);model.stop_clock=true;model.withhold=true;words(w,1,0,0);
        CHECK(as02_sqc_io_execute(&c,w,&r)==-ETIMEDOUT && model.relaxes==AS02_SQC_MAX_POLLS && c.pending && !model.acks);break;}
    default:CHECK(0);
    }
    printf("SQC_HW_RESULT {\"pass_test\":true,\"case\":%d,\"subcase\":%d,\"reads\":%u,\"writes\":%u,\"bells\":%u,\"ACKs\":%u,\"CQEs\":%u,\"heap_live\":%d,\"umem_live\":%d,\"dma_allocs\":%u,\"dma_frees\":%u}\n",
        scenario,n,model.reads,model.writes,model.bells,model.acks,model.cqes,atomic_load(&km.heap_live),atomic_load(&km.umem_live),km.dma_allocs,km.dma_frees);
    return 0;
}
