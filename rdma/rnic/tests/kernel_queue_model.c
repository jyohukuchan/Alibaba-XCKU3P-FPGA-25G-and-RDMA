/* SPDX-License-Identifier: BSD-2-Clause-Views */
/* Explicit primitive/allocation MODEL, NEVER linked into a kernel module. */
#include "kernel_queue_model.h"
_Thread_local unsigned int km_spin_depth;
struct km_task km_current={.mm=(void *)1};
struct km_statistics km;

void *kzalloc(size_t bytes,int flags)
{
    void *p;
    (void)flags;assert(!km_spin_depth);p=calloc(1,bytes);
    if(p)atomic_fetch_add(&km.heap_live,1);
    return p;
}
void *kcalloc(size_t n,size_t bytes,int flags)
{
    if(n && bytes>SIZE_MAX/n)return NULL;
    return kzalloc(n*bytes,flags);
}
void kfree(void *p)
{
    assert(!km_spin_depth);
    if(p){assert(atomic_fetch_sub(&km.heap_live,1)>0);free(p);}
}
struct device *get_device(struct device *d) { assert(d);atomic_fetch_add(&d->references,1);return d; }
void put_device(struct device *d) { assert(!km_spin_depth);assert(atomic_fetch_sub(&d->references,1)>1); }
bool try_module_get(void *m) { (void)m;atomic_fetch_add(&km.module_refs,1);return true; }
void module_put(void *m) { (void)m;assert(!km_spin_depth);assert(atomic_fetch_sub(&km.module_refs,1)>0); }
struct ib_umem *ib_umem_get(struct ib_device *dev,unsigned long start,size_t length,unsigned int access)
{
    struct ib_umem *u;
    (void)dev;(void)access;assert(!km_spin_depth);
    u=calloc(1,sizeof(*u));if(!u)return ERR_PTR(-ENOMEM);
    u->iova=start;u->length=length;u->blocks=((start&4095)+length+4095)/4096;
    atomic_fetch_add(&km.umem_live,1);return u;
}
void ib_umem_release(struct ib_umem *u) { assert(!km_spin_depth);assert(atomic_fetch_sub(&km.umem_live,1)>0);free(u); }
void *dma_alloc_coherent(struct device *d,size_t bytes,dma_addr_t *dma,int flags)
{
    struct km_dma *a;
    (void)d;(void)flags;assert(!km_spin_depth);assert(km.dma_allocs<64);
    a=&km.dma[km.dma_allocs++];assert(!posix_memalign(&a->address,4096,bytes));
    a->bytes=bytes;a->dma=0x8123456789abc000ULL+(km.dma_allocs-1)*0x10000ULL;
    a->live=true;memset(a->address,0xa5,bytes);*dma=a->dma;return a->address;
}
void dma_free_coherent(struct device *d,size_t bytes,void *p,dma_addr_t dma)
{
    unsigned int i;
    (void)d;assert(!km_spin_depth);
    for(i=0;i<km.dma_allocs;i++)if(km.dma[i].address==p){
        assert(km.dma[i].live && km.dma[i].bytes==bytes && km.dma[i].dma==dma);
        km.dma[i].live=false;free(p);km.dma_frees++;return;
    }
    abort();
}
void dma_wmb(void) { atomic_thread_fence(memory_order_release);km.barriers++; }
