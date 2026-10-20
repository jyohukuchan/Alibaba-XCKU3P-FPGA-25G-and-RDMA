/* SPDX-License-Identifier: BSD-2-Clause-Views */
/* Explicit USERSPACE kernel-primitive/DMA/umem MODEL for unchanged actual
 * mr.c/sq.c/verbs_wqe.c execution. NOT a Linux ABI or native pin/DMA proof.
 * Real running-header compile/link is a separate mandatory evidence gate.
 */
#ifndef AS02_KERNEL_QUEUE_TEST_MODEL_H
#define AS02_KERNEL_QUEUE_TEST_MODEL_H
#include <assert.h>
#include <errno.h>
#include <limits.h>
#include <pthread.h>
#include <stdatomic.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
typedef uint64_t u64;
typedef uint64_t dma_addr_t;
#define U64_MAX UINT64_MAX
#define U32_MAX UINT32_MAX
#define PAGE_SIZE 4096UL
#define GFP_KERNEL 0
#define THIS_MODULE ((void *)1)
#define MODULE_DESCRIPTION(x)
#define MODULE_LICENSE(x)
#define EXPORT_SYMBOL_GPL(x)
#define READ_ONCE(x) __atomic_load_n(&(x),__ATOMIC_ACQUIRE)
#define WRITE_ONCE(x,value) __atomic_store_n(&(x),(value),__ATOMIC_RELEASE)
#define check_add_overflow(a,b,out) __builtin_add_overflow((a),(b),(out))
#define ERR_PTR(x) ((void *)(intptr_t)(x))
#define PTR_ERR(x) ((long)(intptr_t)(x))
#define IS_ERR(x) ((uintptr_t)(void *)(x) >= (uintptr_t)-4095L)
#define container_of(ptr,type,member) ((type *)((char *)(ptr)-offsetof(type,member)))

extern _Thread_local unsigned int km_spin_depth;
struct mutex { pthread_mutex_t native; };
typedef struct { pthread_mutex_t native; } spinlock_t;
static inline void mutex_init(struct mutex *m) { assert(!pthread_mutex_init(&m->native,NULL)); }
static inline void mutex_lock(struct mutex *m) { assert(!km_spin_depth);assert(!pthread_mutex_lock(&m->native)); }
static inline void mutex_unlock(struct mutex *m) { assert(!pthread_mutex_unlock(&m->native)); }
static inline void spin_lock_init(spinlock_t *s) { assert(!pthread_mutex_init(&s->native,NULL)); }
#define spin_lock_irqsave(s,flags) do { (flags)=0;assert(!pthread_mutex_lock(&(s)->native));km_spin_depth++; } while(0)
#define spin_unlock_irqrestore(s,flags) do { (void)(flags);assert(km_spin_depth);km_spin_depth--;assert(!pthread_mutex_unlock(&(s)->native)); } while(0)
typedef struct { atomic_uint value; } refcount_t;
static inline void refcount_set(refcount_t *r,unsigned int n) { atomic_store(&r->value,n); }
static inline unsigned int refcount_read(const refcount_t *r) { return atomic_load(&r->value); }
static inline bool refcount_inc_not_zero(refcount_t *r) { unsigned int n=atomic_load(&r->value);if(!n)return false;atomic_fetch_add(&r->value,1);return true; }
static inline void refcount_dec(refcount_t *r) { assert(atomic_fetch_sub(&r->value,1)>0); }

struct list_head { struct list_head *next,*prev; };
#define INIT_LIST_HEAD(h) do { (h)->next=(h);(h)->prev=(h); } while(0)
static inline void list_add_tail(struct list_head *n,struct list_head *h) { n->prev=h->prev;n->next=h;h->prev->next=n;h->prev=n; }
static inline void list_del(struct list_head *n) { n->prev->next=n->next;n->next->prev=n->prev; }

struct device { atomic_int references; struct device *parent; };
struct ib_device {
    struct device dev;
    char node_desc[64];u64 node_guid,uverbs_cmd_mask;
    u32 node_type,phys_port_cnt,num_comp_vectors,local_dma_lkey;
};
struct km_task { void *mm; };
extern struct km_task km_current;
#define current (&km_current)
struct ib_umem { u64 iova,length;u32 blocks; };
struct ib_block_iter { struct ib_umem *umem;u32 index; };
#define rdma_umem_for_each_dma_block(u,it,bytes) for((it)->umem=(u),(it)->index=0;(it)->index<(u)->blocks;(it)->index++)
static inline u64 rdma_block_iter_dma_address(struct ib_block_iter *it) { return 0x9123456700000000ULL+it->index*8192ULL; }
static inline unsigned int ib_umem_num_dma_blocks(struct ib_umem *u,unsigned int bytes) { (void)bytes;return u->blocks; }

#define IB_WR_RDMA_WRITE 0
#define IB_WR_SEND 2
#define IB_WR_SEND_WITH_IMM 3
#define IB_WR_RDMA_WRITE_WITH_IMM 1
#if __BYTE_ORDER__ == __ORDER_LITTLE_ENDIAN__
#define be32_to_cpu(value) __builtin_bswap32((u32)(value))
#define cpu_to_be32(value) __builtin_bswap32((u32)(value))
#else
#define be32_to_cpu(value) ((u32)(value))
#define cpu_to_be32(value) ((u32)(value))
#endif
#define IB_WR_RDMA_READ 4
#define IB_SEND_SIGNALED 2
#define IB_WC_SUCCESS 0U
#define IB_WC_WR_FLUSH_ERR 5U
#define IB_WC_GENERAL_ERR 21U
struct ib_sge { u64 addr;u32 length,lkey; };
struct ib_send_wr { struct ib_send_wr *next;u64 wr_id;struct ib_sge *sg_list;int num_sge;u32 opcode,send_flags;union {u32 imm_data;} ex; };
struct ib_recv_wr { struct ib_recv_wr *next;u64 wr_id;struct ib_sge *sg_list;int num_sge; };
struct ib_rdma_wr { struct ib_send_wr wr;u64 remote_addr;u32 rkey; };
static inline const struct ib_rdma_wr *rdma_wr(const struct ib_send_wr *wr) { return container_of(wr,const struct ib_rdma_wr,wr); }

struct km_dma { void *address;dma_addr_t dma;size_t bytes;bool live; };
struct km_statistics {
    atomic_int heap_live,umem_live,module_refs;
    unsigned int dma_allocs,dma_frees,barriers;
    struct km_dma dma[64];
};
extern struct km_statistics km;
void *kzalloc(size_t,int);
void *kcalloc(size_t,size_t,int);
void kfree(void *);
struct device *get_device(struct device *);
void put_device(struct device *);
bool try_module_get(void *);
void module_put(void *);
struct ib_umem *ib_umem_get(struct ib_device *,unsigned long,size_t,unsigned int);
void ib_umem_release(struct ib_umem *);
void *dma_alloc_coherent(struct device *,size_t,dma_addr_t *,int);
void dma_free_coherent(struct device *,size_t,void *,dma_addr_t);
void dma_wmb(void);
#endif
