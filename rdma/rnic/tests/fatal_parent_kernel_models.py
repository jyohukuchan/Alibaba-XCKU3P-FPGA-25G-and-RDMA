# SPDX-License-Identifier: BSD-2-Clause-Views
"""Explicit thread/workqueue/register/IB-core models, not real Linux execution."""
from pathlib import Path
import fatal_verbs_kernel_models as parent
ROOT=parent.ROOT;once=parent.once;MODEL=parent.MODEL


def cq_header():
    t=(ROOT/'rdma/rnic/tests/kernel_cq_model.h').read_text();start=t.index('struct work_struct {')
    return t[:start]+r'''
struct work_struct {
 void (*fn)(struct work_struct *);bool pending,running;
 pthread_mutex_t model_lock;pthread_cond_t model_condition;unsigned cancel_waiters;
};
struct delayed_work { struct work_struct work; };
extern _Thread_local struct work_struct *fp_current_work;
static inline struct work_struct *current_work(void){return fp_current_work;}
#define INIT_DELAYED_WORK(w,f) do { (w)->work.fn=(f);(w)->work.pending=false;(w)->work.running=false;(w)->work.cancel_waiters=0; \
 assert(!pthread_mutex_init(&(w)->work.model_lock,NULL));assert(!pthread_cond_init(&(w)->work.model_condition,NULL)); }while(0)
static inline struct delayed_work *to_delayed_work(struct work_struct *w){return container_of(w,struct delayed_work,work);}
static inline bool schedule_delayed_work(struct delayed_work *w,unsigned long ticks){
 bool old;(void)ticks;assert(!pthread_mutex_lock(&w->work.model_lock));old=w->work.pending;w->work.pending=true;
 assert(!pthread_mutex_unlock(&w->work.model_lock));return !old;
}
static inline bool cancel_delayed_work_sync(struct delayed_work *w){
 bool pending;assert(!km_spin_depth && current_work()!=&w->work);
 assert(!pthread_mutex_lock(&w->work.model_lock));pending=w->work.pending;w->work.pending=false;
 if(w->work.running){w->work.cancel_waiters++;assert(!pthread_cond_broadcast(&w->work.model_condition));
  while(w->work.running)assert(!pthread_cond_wait(&w->work.model_condition,&w->work.model_lock));}
 w->work.pending=false;assert(!pthread_mutex_unlock(&w->work.model_lock));return pending;
}
static inline unsigned long msecs_to_jiffies(unsigned int ms){return ms;}
static inline void cm_run_work(struct delayed_work *w){
 struct work_struct *old=fp_current_work;assert(!km_spin_depth);
 assert(!pthread_mutex_lock(&w->work.model_lock));assert(w->work.pending && !w->work.running);
 w->work.pending=false;w->work.running=true;assert(!pthread_mutex_unlock(&w->work.model_lock));
 fp_current_work=&w->work;w->work.fn(&w->work);fp_current_work=old;
 assert(!pthread_mutex_lock(&w->work.model_lock));w->work.running=false;
 assert(!pthread_cond_broadcast(&w->work.model_condition));assert(!pthread_mutex_unlock(&w->work.model_lock));
}
#endif
'''


def graph_model():
    t=(ROOT/'rdma/rnic/tests/kernel_native_graph_cases.c').read_text()
    t=once(t,'static bool immediate_graph;','static bool immediate_graph,fatal_profile;')
    t=once(t,'case AS02_CTL_FEATURES:return immediate_graph ? 1023:511;',
        'case AS02_CTL_FEATURES:return fatal_profile ? 131071:immediate_graph ? 1023:511;')
    t=once(t,'case AS02_CQC_FEATURES:return immediate_graph ? 7:3;',
        'case AS02_CQC_FEATURES:return fatal_profile ? 511:immediate_graph ? 7:3;')
    t=once(t,'case AS02_CQC_CONTEXT_EXTENSION:CHECK(immediate_graph);',
        'case AS02_CQC_OWNER_BITS:return 748;case AS02_CQC_OPERAND_BASE:return 0xa0;\n'
        '        case AS02_CQC_ATOMIC_OPERANDS:case AS02_CQC_ATOMIC_OPERANDS+4:\n'
        '        case AS02_CQC_ATOMIC_OPERANDS+8:case AS02_CQC_ATOMIC_OPERANDS+12:return 0;\n'
        '        case AS02_CQC_CONTEXT_EXTENSION:CHECK(immediate_graph || fatal_profile);')
    t=once(t,'case AS02_CQC_NOTIFICATION_FLAGS:CHECK(immediate_graph);','case AS02_CQC_NOTIFICATION_FLAGS:CHECK(immediate_graph || fatal_profile);')
    t=once(t,'case AS02_CQC_NOTIFICATION:CHECK(immediate_graph);','case AS02_CQC_NOTIFICATION:CHECK(immediate_graph || fatal_profile);')
    t=once(t,'    if(immediate_graph){send_controller.features=5;receive_controller.features=7;}',
        '    if(immediate_graph){send_controller.features=5;receive_controller.features=7;}\n'
        '    if(fatal_profile){send_controller.features=13;receive_controller.features=63;}')
    t=once(t,'u32 readl(const volatile void *p)','u32 fp_legacy_readl(const volatile void *p)')
    t=once(t,'void writel(u32 value,volatile void *p)','void fp_legacy_writel(u32 value,volatile void *p)')
    t=once(t,'    registrations++;if(register_error)',
        '    if(fatal_profile && *model_parameter_enable_fatal_events)CHECK(active->fatal.initialized && !active->fatal.started &&\n'
        '        active->device->fatal==&active->fatal.verbs && !active->device->qp);\n'
        '    registrations++;if(register_error)')
    t=once(t,'int main(int argc,char **argv)','int old_native_graph_main(int argc,char **argv)')
    # Original C main implicitly returns0. Preserve that exact behavior after
    # renaming it to a callable legacy entry; keep all assertions unchanged.
    if not t.endswith('\n}\n'):raise ValueError('exact original final main body required')
    return t[:-3]+'    return 0;\n}\n'
