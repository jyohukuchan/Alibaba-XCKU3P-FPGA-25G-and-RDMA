/* SPDX-License-Identifier: BSD-2-Clause-Views */
/* Explicit userspace Linux-primitive/MMIO/IRQ model, NEVER a kernel ABI. */
#ifndef AS02_KERNEL_CQ_MODEL_H
#define AS02_KERNEL_CQ_MODEL_H
#include "kernel_sq_hw_model.h"
struct ib_cq;
#ifndef AS02_EXTENDED_IB_QP
struct ib_qp { struct ib_device *device;struct ib_cq *send_cq,*recv_cq;u32 qp_num; };
#endif
struct ib_wc { u64 wr_id;u32 status,opcode,vendor_err,byte_len;struct ib_qp *qp;u32 wc_flags;union {u32 imm_data;} ex; };
struct ib_cq {
    struct ib_device *device;
    void (*comp_handler)(struct ib_cq *,void *);
    void *cq_context;
    int cqe;
};
struct ib_cq_init_attr { u32 cqe,comp_vector,flags; };
struct ib_udata { size_t inlen,outlen; };
enum ib_cq_notify_flags { IB_CQ_SOLICITED=1,IB_CQ_NEXT_COMP=2,IB_CQ_REPORT_MISSED_EVENTS=4 };
#define IB_WC_RDMA_WRITE 1U
#define IB_WC_SEND 0U
#define IB_WC_RDMA_READ 2U
#define IB_WC_RECV 128U
#define IB_WC_RECV_RDMA_WITH_IMM 129U
#define IB_WC_WITH_IMM 2U
struct irq_work { void (*func)(struct irq_work *);bool pending; };
static inline void init_irq_work(struct irq_work *w,void (*fn)(struct irq_work *)) { w->func=fn;w->pending=false; }
static inline bool irq_work_queue(struct irq_work *w) { bool old=w->pending;w->pending=true;return !old; }
static inline void irq_work_sync(struct irq_work *w) { assert(!km_spin_depth);if(w->pending){w->pending=false;w->func(w);} }
typedef struct { atomic_int value; } atomic_t;
static inline void atomic_set(atomic_t *a,int n) { atomic_store(&a->value,n); }
static inline int atomic_read(const atomic_t *a) { return atomic_load(&a->value); }
static inline void atomic_inc(atomic_t *a) { atomic_fetch_add(&a->value,1); }
static inline void atomic_dec(atomic_t *a) { assert(atomic_fetch_sub(&a->value,1)>0); }
struct work_struct { void (*fn)(struct work_struct *);bool pending; };
struct delayed_work { struct work_struct work; };
#define INIT_DELAYED_WORK(w,f) do { (w)->work.fn=(f);(w)->work.pending=false; }while(0)
static inline struct delayed_work *to_delayed_work(struct work_struct *w) { return container_of(w,struct delayed_work,work); }
static inline bool schedule_delayed_work(struct delayed_work *w,unsigned long ticks) { bool old=w->work.pending;(void)ticks;w->work.pending=true;return !old; }
static inline void cancel_delayed_work_sync(struct delayed_work *w) { assert(!km_spin_depth);w->work.pending=false; }
static inline unsigned long msecs_to_jiffies(unsigned int ms) { return ms; }
static inline void cm_run_work(struct delayed_work *w) { assert(!km_spin_depth && w->work.pending);w->work.pending=false;w->work.fn(&w->work); }
#endif
