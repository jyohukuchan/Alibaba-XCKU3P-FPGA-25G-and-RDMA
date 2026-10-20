/* SPDX-License-Identifier: BSD-2-Clause-Views */
/* Actual mr.c/sq.c/codec execution, EXPLICIT kernel/DMA/HW/CQ MODELS. */
#include "kernel_queue_model.h"
#include "sq.h"

#define VA 0xfedcba9876543000ULL
#define EPOCH 0x9123456700000001ULL
#define CHECK(x) do { if(!(x)){fprintf(stderr,"CASE_CHECK %s:%d %s\n",__FILE__,__LINE__,#x);abort();} } while(0)
struct context {
    bool bad_publish,bad_revoke,bad_allocate,bad_retire,publish_error,cq_full;
    unsigned int reset_calls,revoke_calls,allocate_calls,retire_calls,publish_calls,cqes,last_barrier;
    u32 generations[8];
    struct as02_wqe observed[8][257];
    struct as02_sq_completion completions[256];
};
static struct context ctx;
static struct ib_device ibdev;
static struct device dma_dev;
static struct as02_mr_pool mrs;
static struct as02_sq_pool queues;

static int hw_epoch(void *opaque,u64 cookie,u32 floor,struct as02_mr_epoch_proof *out)
{
    struct context *c=opaque;unsigned int i;
    CHECK(!km_spin_depth);c->reset_calls++;
    for(i=0;i<8;i++)c->generations[i]=floor;
    *out=(struct as02_mr_epoch_proof){.cookie=cookie,.floor=floor,.qps_closed=1,.mr_table_invalid=1,.dma_drained=1};return 0;
}
static int hw_publish(void *opaque,const struct as02_mr_layout *m,struct as02_mr_publish_proof *out)
{
    struct context *c=opaque;
    CHECK(!km_spin_depth);c->generations[m->slot]++;
    *out=(struct as02_mr_publish_proof){.cookie=m->cookie,.slot=m->slot,.key=(c->generations[m->slot]<<3)|m->slot};
    if(c->bad_publish)out->cookie^=1;
    return 0;
}
static int hw_revoke(void *opaque,const struct as02_mr_layout *m,struct as02_mr_revoke_proof *out)
{
    struct context *c=opaque;
    CHECK(!km_spin_depth);c->revoke_calls++;
    *out=(struct as02_mr_revoke_proof){.cookie=m->cookie,.slot=m->slot,.generation=c->generations[m->slot],
        .invalidated=1,.dma_drained=!c->bad_revoke};return 0;
}
static const struct as02_mr_hw_ops mr_hw={.reset_epoch=hw_epoch,.publish=hw_publish,.invalidate_and_drain=hw_revoke};

static int sq_allocate(void *opaque,const struct as02_sq_layout *layout,struct as02_sq_alloc_proof *out)
{
    struct context *c=opaque;CHECK(!km_spin_depth);c->allocate_calls++;
    *out=(struct as02_sq_alloc_proof){.layout=*layout,.flags=7};
    if(c->bad_allocate)out->layout.dma_base^=64;
    return 0;
}
static int sq_retire(void *opaque,const struct as02_sq_layout *layout,u64 producer,u64 cookie,struct as02_sq_retire_proof *out)
{
    struct context *c=opaque;CHECK(!km_spin_depth);c->retire_calls++;
    *out=(struct as02_sq_retire_proof){.owner=layout->owner,.request_cookie=cookie,.last_producer=producer,.flags=31};
    if(c->bad_retire)out->flags=AS02_SQ_RETIRED|AS02_SQ_FETCH_DRAINED;
    return 0;
}
static int sq_publish(void *opaque,const struct as02_sq_layout *layout,u64 producer)
{
    struct context *c=opaque;struct km_dma *a=NULL;unsigned int i,index;
    CHECK(km_spin_depth && producer && producer<=256 && layout->owner.qpn<8);
    CHECK(km.barriers>c->last_barrier);c->last_barrier=km.barriers;
    for(i=0;i<km.dma_allocs;i++)if(km.dma[i].live && km.dma[i].dma==layout->dma_base)a=&km.dma[i];
    CHECK(a && a->bytes==layout->depth*64U);
    index=(producer-1)&(layout->depth-1);
    CHECK(!as02_wqe_decode(&c->observed[layout->owner.qpn][producer],(u8 *)a->address+index*64));
    CHECK(c->observed[layout->owner.qpn][producer].sequence==producer);
    CHECK(c->observed[layout->owner.qpn][producer].epoch==layout->owner.epoch);
    c->publish_calls++;
    return c->publish_error ? -EIO : 0;
}
static int sq_cqe(void *opaque,const struct as02_sq_completion *completion)
{
    struct context *c=opaque;
    CHECK(km_spin_depth && completion->qpn<8 && completion->sequence<=256);
    CHECK(completion->wr_id==c->observed[completion->qpn][completion->sequence].wr_id);
    if(c->cq_full)return -ENOSPC;
    CHECK(c->cqes<256);c->completions[c->cqes++]=*completion;return 0;
}
static const struct as02_sq_hw_ops sq_hw={.allocate=sq_allocate,.retire_and_drain=sq_retire,
    .publish_producer=sq_publish,.publish_cqe=sq_cqe};

static void setup(bool queue_pool)
{
    const u64 epochs[8]={0};
    atomic_store(&ibdev.dev.references,1);atomic_store(&dma_dev.references,1);
    CHECK(!as02_mr_pool_init(&mrs,&ibdev,&mr_hw,&ctx,0));
    CHECK(!as02_mr_pool_start_epoch(&mrs,0));
    if(queue_pool)CHECK(!as02_sq_pool_init(&queues,&mrs,&dma_dev,&sq_hw,&ctx,epochs));
}
static struct as02_user_mr *mapping(u32 access,bool publish)
{
    struct as02_user_mr *m=as02_user_mr_prepare(&mrs,0x10003,VA,8192,17,access,15);
    CHECK(!IS_ERR(m));CHECK(m->umem->iova==0x10003 && m->layout.page_count==3);
    if(publish)CHECK(!as02_user_mr_publish(m));
    return m;
}
static struct ib_rdma_wr request(struct ib_sge *sge,u32 key,u32 opcode,bool signaled,u64 wr_id)
{
    *sge=(struct ib_sge){.addr=VA+1,.length=65,.lkey=key};
    return (struct ib_rdma_wr){.wr={.wr_id=wr_id,.sg_list=sge,.num_sge=1,.opcode=opcode,
        .send_flags=signaled ? IB_SEND_SIGNALED:0},.remote_addr=0xe23456789abcd002ULL,.rkey=0};
}
static struct as02_sq_handle create(u32 qpn,u16 pd,u64 epoch,u32 log_depth)
{
    struct as02_sq_handle h;
    CHECK(!as02_sq_create(&queues,qpn,pd,epoch,log_depth,&h));return h;
}
static int complete(const struct as02_sq_handle *h,u64 sequence,u32 status)
{
    struct as02_sq_completion_proof proof={.owner=*h,.sequence=sequence,.flags=3,.status=status};
    return as02_sq_complete(&queues,&proof);
}
static void cleanup(struct as02_user_mr *m,bool queue_pool)
{
    if(queue_pool)CHECK(!as02_sq_pool_destroy(&queues));
    CHECK(!as02_user_mr_close(m));CHECK(!as02_mr_pool_destroy(&mrs));
    CHECK(!atomic_load(&km.heap_live) && !atomic_load(&km.umem_live) && !atomic_load(&km.module_refs));
    CHECK(km.dma_allocs==km.dma_frees);
    CHECK(atomic_load(&ibdev.dev.references)==1 && atomic_load(&dma_dev.references)==1);
}

static void case_mr_refs(void)
{
    struct as02_user_mr *m,*a,*b;
    setup(false);m=mapping(7,true);
    CHECK(IS_ERR(as02_user_mr_get_work(&mrs,17,m->layout.key,VA+1,65,0)));
    CHECK(!as02_mr_pool_get_client(&mrs));
    CHECK(as02_mr_pool_start_epoch(&mrs,1)==-EBUSY);
    a=as02_user_mr_get_work(&mrs,17,m->layout.key,VA+1,65,0);CHECK(a==m);
    b=as02_user_mr_get_work(&mrs,17,m->layout.key,VA+4095,4096,1);CHECK(b==m);
    CHECK(refcount_read(&m->work_refs)==3);
    CHECK(PTR_ERR(as02_user_mr_get_work(&mrs,18,m->layout.key,VA+1,65,0))==-EACCES);
    CHECK(PTR_ERR(as02_user_mr_get_work(&mrs,17,m->layout.key^0x80000000U,VA+1,65,0))==-EACCES);
    CHECK(PTR_ERR(as02_user_mr_get_work(&mrs,17,m->layout.key,VA+8191,65,0))==-EFAULT);
    CHECK(PTR_ERR(as02_user_mr_get_work(&mrs,17,m->layout.key,VA+1,65,2))==-EOPNOTSUPP);
    CHECK(as02_user_mr_close(m)==-EBUSY && ctx.revoke_calls==0 && atomic_load(&km.umem_live)==1);
    CHECK(IS_ERR(as02_user_mr_get_work(&mrs,17,m->layout.key,VA+1,65,0)));
    CHECK(!as02_user_mr_put_work(a) && !as02_user_mr_put_work(b));
    CHECK(as02_user_mr_put_work(m)==-EINVAL);
    CHECK(!as02_mr_pool_put_client(&mrs));cleanup(m,false);
}
static void case_mr_quarantine(void)
{
    struct as02_user_mr *m;
    setup(false);m=mapping(7,false);CHECK(!as02_mr_pool_get_client(&mrs));
    CHECK(IS_ERR(as02_user_mr_get_work(&mrs,17,8,VA+1,65,0)));
    ctx.bad_publish=true;CHECK(as02_user_mr_publish(m)<0 && m->quarantined);
    CHECK(IS_ERR(as02_user_mr_get_work(&mrs,17,8,VA+1,65,0)));
    ctx.bad_revoke=true;CHECK(as02_user_mr_close(m)<0 && atomic_load(&km.umem_live)==1);
    ctx.bad_revoke=false;CHECK(!as02_mr_pool_put_client(&mrs));cleanup(m,false);
}
static pthread_barrier_t acquired,release_refs;
static void *mr_worker(void *opaque)
{
    struct as02_user_mr *m=opaque,*held=as02_user_mr_get_work(&mrs,17,m->layout.key,VA+1,65,0);
    CHECK(held==m);pthread_barrier_wait(&acquired);pthread_barrier_wait(&release_refs);
    CHECK(IS_ERR(as02_user_mr_get_work(&mrs,17,m->layout.key,VA+1,65,0)));
    CHECK(!as02_user_mr_put_work(held));return NULL;
}
static void case_mr_threads(void)
{
    struct as02_user_mr *m;pthread_t threads[4];unsigned int i;
    setup(false);m=mapping(7,true);CHECK(!as02_mr_pool_get_client(&mrs));
    CHECK(!pthread_barrier_init(&acquired,NULL,5) && !pthread_barrier_init(&release_refs,NULL,5));
    for(i=0;i<4;i++)CHECK(!pthread_create(&threads[i],NULL,mr_worker,m));
    pthread_barrier_wait(&acquired);CHECK(refcount_read(&m->work_refs)==5);
    CHECK(as02_user_mr_close(m)==-EBUSY && !ctx.revoke_calls);
    pthread_barrier_wait(&release_refs);for(i=0;i<4;i++)CHECK(!pthread_join(threads[i],NULL));
    CHECK(!as02_mr_pool_put_client(&mrs));cleanup(m,false);
}
static void case_sq_normal(void)
{
    struct as02_user_mr *m;struct as02_sq_handle h;struct ib_sge sge;struct ib_rdma_wr wr;
    setup(true);m=mapping(7,true);h=create(0,17,EPOCH,1);
    wr=request(&sge,m->layout.key,IB_WR_RDMA_WRITE,true,0xf123456789abcdefULL);
    CHECK(!as02_sq_post(&queues,&h,&wr.wr));wr.wr.wr_id=0;
    wr.wr.opcode=IB_WR_RDMA_READ;wr.rkey=0xffffffff;CHECK(!as02_sq_post(&queues,&h,&wr.wr));
    CHECK(refcount_read(&m->work_refs)==3 && ctx.publish_calls==2);
    CHECK(as02_sq_post(&queues,&h,&wr.wr)==-ENOSPC && refcount_read(&m->work_refs)==3);
    ctx.cq_full=true;CHECK(complete(&h,1,0)==-ENOSPC && refcount_read(&m->work_refs)==3 && ctx.cqes==0);
    ctx.cq_full=false;CHECK(!complete(&h,1,0) && refcount_read(&m->work_refs)==2);
    wr.wr.wr_id=0x8000000000000000ULL;wr.rkey=0x80000000;CHECK(!as02_sq_post(&queues,&h,&wr.wr));
    CHECK(as02_sq_close(&queues,&h)==-EBUSY && !ctx.retire_calls);
    CHECK(!complete(&h,2,0) && !complete(&h,3,0));
    CHECK(ctx.cqes==3 && ctx.observed[0][1].remote_key==0 && ctx.observed[0][2].remote_key==0xffffffff && ctx.observed[0][3].remote_key==0x80000000);
    CHECK(!as02_sq_close(&queues,&h));cleanup(m,true);
}
static void case_sq_permissions(void)
{
    struct as02_user_mr *m;struct as02_sq_handle h;struct ib_sge sge;struct ib_rdma_wr wr;
    setup(true);m=mapping(4,true);h=create(7,17,EPOCH,1);
    wr=request(&sge,m->layout.key,IB_WR_RDMA_READ,false,1);
    CHECK(as02_sq_post(&queues,&h,&wr.wr)==-EACCES && ctx.publish_calls==0);
    wr.wr.opcode=IB_WR_RDMA_WRITE;CHECK(!as02_sq_post(&queues,&h,&wr.wr));
    CHECK(refcount_read(&m->work_refs)==2);CHECK(!complete(&h,1,0) && !ctx.cqes);
    sge.lkey^=0x80000000;CHECK(as02_sq_post(&queues,&h,&wr.wr)==-EACCES);
    CHECK(!as02_sq_close(&queues,&h));cleanup(m,true);
}
static void case_sq_bad_completion(void)
{
    struct as02_user_mr *m;struct as02_sq_handle h;struct ib_sge sge;struct ib_rdma_wr wr;
    struct as02_sq_completion_proof p;
    setup(true);m=mapping(7,true);h=create(0,17,EPOCH,1);wr=request(&sge,m->layout.key,0,true,1);
    CHECK(!as02_sq_post(&queues,&h,&wr.wr));
    p=(struct as02_sq_completion_proof){.owner=h,.sequence=1,.flags=3,.status=0};p.owner.epoch^=1;
    CHECK(as02_sq_complete(&queues,&p)==-ESTALE && refcount_read(&m->work_refs)==2);
    p.owner=h;p.flags=AS02_SQ_CQE_MEMORY_DONE;
    CHECK(as02_sq_complete(&queues,&p)==-EIO && refcount_read(&m->work_refs)==2);
    CHECK(as02_sq_post(&queues,&h,&wr.wr)==-ESHUTDOWN && complete(&h,1,0)==-ESTALE);
    CHECK(as02_sq_close(&queues,&h)==-EBUSY && as02_user_mr_close(m)==-EBUSY);
    CHECK(as02_sq_pool_destroy(&queues)==-EBUSY && km.dma_frees==0 && !ctx.cqes);
    /* Deliberately retained global owners remain reachable. There is NO fake
     * abort/reset/completion merely to make a leak checker/cleanup pass.
     */
}
static void case_sq_ambiguous_publish(void)
{
    struct as02_user_mr *m;struct as02_sq_handle h;struct ib_sge sge;struct ib_rdma_wr wr;
    setup(true);m=mapping(7,true);h=create(0,17,EPOCH,1);wr=request(&sge,m->layout.key,0,true,1);
    ctx.publish_error=true;CHECK(as02_sq_post(&queues,&h,&wr.wr)==-EIO);
    CHECK(ctx.publish_calls==1 && refcount_read(&m->work_refs)==2);
    CHECK(as02_sq_close(&queues,&h)==-EBUSY && as02_user_mr_close(m)==-EBUSY && km.dma_frees==0);
    CHECK(as02_sq_pool_destroy(&queues)==-EBUSY && as02_mr_pool_destroy(&mrs)==-EBUSY);
}
static void case_sq_allocate_and_retire_proofs(void)
{
    struct as02_user_mr *m;struct as02_sq_handle h,bad;
    setup(true);m=mapping(7,true);
    CHECK(as02_sq_create(&queues,0x100000,17,EPOCH,1,&h)==-EINVAL && !km.dma_allocs);
    ctx.bad_allocate=true;CHECK(as02_sq_create(&queues,0,17,EPOCH,1,&h)==-EIO && h.cookie && queues.queue_count==1);
    ctx.bad_retire=true;CHECK(as02_sq_close(&queues,&h)==-EIO && !km.dma_frees);
    bad=h;bad.cookie++;CHECK(as02_sq_close(&queues,&bad)==-ESTALE);
    ctx.bad_retire=false;CHECK(!as02_sq_close(&queues,&h) && km.dma_frees==1);
    ctx.bad_allocate=false;CHECK(as02_sq_create(&queues,0,17,EPOCH,1,&h)==-ESTALE);
    h=create(0,17,EPOCH+1,1);CHECK(!as02_sq_close(&queues,&h));cleanup(m,true);
}
static void case_sq_teardown_order(void)
{
    struct as02_user_mr *m;struct as02_sq_handle h;struct ib_sge sge;struct ib_rdma_wr wr;
    setup(true);m=mapping(7,true);h=create(0,17,EPOCH,1);wr=request(&sge,m->layout.key,0,false,1);
    CHECK(!as02_sq_post(&queues,&h,&wr.wr));
    CHECK(as02_mr_pool_destroy(&mrs)==-EBUSY && as02_sq_pool_destroy(&queues)==-EBUSY);
    CHECK(as02_sq_post(&queues,&h,&wr.wr)==-ESHUTDOWN);
    CHECK(!complete(&h,1,IB_WC_WR_FLUSH_ERR) && ctx.cqes==1);
    CHECK(!as02_sq_close(&queues,&h));cleanup(m,true);
}
struct poster { struct as02_sq_handle owner;u32 key,index; };
static void *sq_worker(void *opaque)
{
    struct poster *p=opaque;struct ib_sge sge;struct ib_rdma_wr wr;unsigned int i;
    for(i=0;i<8;i++){
        wr=request(&sge,p->key,i&1 ? IB_WR_RDMA_READ:IB_WR_RDMA_WRITE,true,0x8000000000000000ULL+((u64)p->index<<32)+i);
        CHECK(!as02_sq_post(&queues,&p->owner,&wr.wr));
    }
    return NULL;
}
static void case_sq_threads(void)
{
    struct as02_user_mr *m;struct as02_sq_handle h;struct poster args[2];pthread_t threads[2];unsigned int i;
    setup(true);m=mapping(7,true);h=create(0,17,EPOCH,4);
    for(i=0;i<2;i++){args[i]=(struct poster){.owner=h,.key=m->layout.key,.index=i};CHECK(!pthread_create(&threads[i],NULL,sq_worker,&args[i]));}
    for(i=0;i<2;i++)CHECK(!pthread_join(threads[i],NULL));
    CHECK(ctx.publish_calls==16 && refcount_read(&m->work_refs)==17);
    for(i=1;i<=16;i++)CHECK(!complete(&h,i,0));
    CHECK(ctx.cqes==16 && refcount_read(&m->work_refs)==1);
    CHECK(!as02_sq_close(&queues,&h));cleanup(m,true);
}

int main(int argc,char **argv)
{
    int which;
    CHECK(argc==2);which=atoi(argv[1]);
    switch(which){
    case 0:case_mr_refs();break;
    case 1:case_mr_quarantine();break;
    case 2:case_mr_threads();break;
    case 3:case_sq_normal();break;
    case 4:case_sq_permissions();break;
    case 5:case_sq_bad_completion();break;
    case 6:case_sq_ambiguous_publish();break;
    case 7:case_sq_allocate_and_retire_proofs();break;
    case 8:case_sq_teardown_order();break;
    case 9:case_sq_threads();break;
    default:abort();
    }
    printf("KERNEL_QUEUE_RESULT {\"pass_test\":true,\"case\":%d,\"heap_live\":%d,\"umem_live\":%d,\"module_refs\":%d,\"dma_allocs\":%u,\"dma_frees\":%u,\"producer_callbacks\":%u,\"CQ_callbacks_committed\":%u,\"barriers\":%u}\n",
           which,atomic_load(&km.heap_live),atomic_load(&km.umem_live),atomic_load(&km.module_refs),km.dma_allocs,km.dma_frees,ctx.publish_calls,ctx.cqes,km.barriers);
    return 0;
}
