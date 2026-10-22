/* SPDX-License-Identifier: BSD-2-Clause-Views */
/* Actual full parent/driver C bodies; Linux/MMIO/IB-core/certificates/workqueue
 * are MODELS. Threaded cancellation here is not real-kernel lifetime proof.
 */
#include "kernel_native_graph_cases.c"
#include "fatal_parent.h"

_Thread_local struct work_struct *fp_current_work;
static struct as02_native_lease fp_lease;
static struct as02_pd fp_pd;
static struct as02_cq fp_tx,fp_rx;
static struct as02_verbs_qp fp_qp;
static struct as02_verbs_mr *fp_mr;
static struct as02_fatal_record fp_record;
static unsigned fp_case,fp_reads,fp_writes,fp_visible,fp_ack,fp_bad_abi,fp_drop_ack,fp_handlers,fp_refs,fp_frees;
static pthread_mutex_t fp_gate=PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t fp_condition=PTHREAD_COND_INITIALIZER;
static bool fp_handler_entered,fp_handler_release;
static int fp_stop_result;

u32 readl(const volatile void *p)
{
    uintptr_t address=(uintptr_t)p-(uintptr_t)application;
    if(address>=AS02_NATIVE_FATAL_BASE && address<AS02_NATIVE_FATAL_BASE+AS02_NATIVE_FATAL_BYTES){
        u32 off=address-AS02_NATIVE_FATAL_BASE;CHECK(!km_spin_depth);
    if(!fp_reads){CHECK(!commands[AS02_CMD_EPOCH]);}fp_reads++;
        switch(off){
        case AS02_FEC_ID:return AS02_FEC_ID_VALUE;
        case AS02_FEC_ABI:return fp_bad_abi ? 0:AS02_FEC_ABI_VALUE;
        case AS02_FEC_FEATURES:return AS02_FEC_FEATURE_VALUE;
        case AS02_FEC_STATUS:return fp_visible;
        case AS02_FEC_SEQUENCE:return fp_record.sequence;
        case AS02_FEC_LAST_ACK:return fp_ack;
        default:CHECK(off>=AS02_FEC_RECORD && off<AS02_FEC_BYTES && !(off&3));
            return fp_visible ? fp_record.word[(off-AS02_FEC_RECORD)/4]:0;
        }
    }
    return fp_legacy_readl(p);
}
void writel(u32 value,volatile void *p)
{
    uintptr_t address=(uintptr_t)p-(uintptr_t)application;
    if(address>=AS02_NATIVE_FATAL_BASE && address<AS02_NATIVE_FATAL_BASE+AS02_NATIVE_FATAL_BYTES){
        CHECK(!km_spin_depth && address-AS02_NATIVE_FATAL_BASE==AS02_FEC_ACK && fp_visible && value==fp_record.sequence);
        fp_writes++;if(!fp_drop_ack){fp_ack=value;fp_visible=0;}return;
    }
    fp_legacy_writel(value,p);
}
static void fp_retained(void)
{
    CHECK(active && fp_lease.owner==active && active->device->fatal==&active->fatal.verbs);
    CHECK(atomic_load(&pci_parent.dev.references)>1 && atomic_load(&netdev.dev.references)>1);
    CHECK(active->device->initialized && active->device->published && !unregistrations && km.dma_frees==fp_frees);
    if(fp_mr)CHECK(refcount_read(&fp_mr->mapping->work_refs)==fp_refs && fp_qp.initialized && !fp_qp.sq_closed && fp_pd.owners==2);
}
static void fp_handler(struct ib_event *e,void *context)
{
    struct ib_qp_attr queried;struct ib_qp_init_attr initial;
    CHECK(context==active && e->device==&active->device->ibdev && e->element.qp==&fp_qp.ibqp);
    CHECK(current_work()==&active->fatal.poll_work.work && !km_spin_depth);
    CHECK(!pthread_mutex_trylock(&active->lock.native));mutex_unlock(&active->lock);
    CHECK(!pthread_mutex_trylock(&fp_lease.lock.native));mutex_unlock(&fp_lease.lock);
    CHECK(!pthread_mutex_trylock(&active->fatal.lock.native));mutex_unlock(&active->fatal.lock);
    CHECK(!work->query_qp(&fp_qp.ibqp,&queried,0,&initial) && queried.qp_state==IB_QPS_ERR);
    CHECK(work->destroy_qp(&fp_qp.ibqp,NULL)==-EBUSY && as02_native_graph_close(&active)==-EBUSY);
    CHECK(as02_native_graph_stop_fatal_polling(active)==-EDEADLK);
    fp_retained();fp_handlers++;
    if(fp_case==10){
        CHECK(!pthread_mutex_lock(&fp_gate));fp_handler_entered=true;CHECK(!pthread_cond_broadcast(&fp_condition));
        while(!fp_handler_release)CHECK(!pthread_cond_wait(&fp_condition,&fp_gate));
        CHECK(!pthread_mutex_unlock(&fp_gate));
    }
}
static void fp_create_qp(void)
{
    struct ib_device *d=&active->device->ibdev;
    struct ib_cq_init_attr ca={.cqe=2};
    fp_pd.ibpd.device=d;CHECK(!work->alloc_pd(&fp_pd.ibpd,NULL));
    struct ib_mr *m=work->reg_user_mr(&fp_pd.ibpd,0x10003,8192,VA,7,NULL,NULL);CHECK(!IS_ERR(m));
    fp_mr=container_of(m,struct as02_verbs_mr,ibmr);
    fp_tx.ibcq.device=fp_rx.ibcq.device=d;
    CHECK(!work->create_cq(&fp_tx.ibcq,&ca,NULL) && !work->create_cq(&fp_rx.ibcq,&ca,NULL));
    struct ib_qp_init_attr qa={.send_cq=&fp_tx.ibcq,.recv_cq=&fp_rx.ibcq,.qp_type=IB_QPT_RC,.sq_sig_type=IB_SIGNAL_ALL_WR,
        .cap={.max_send_wr=2,.max_recv_wr=2,.max_send_sge=1,.max_recv_sge=1}};
    fp_qp.ibqp.device=d;fp_qp.ibqp.pd=&fp_pd.ibpd;CHECK(!work->create_qp(&fp_qp.ibqp,&qa,NULL));
    struct ib_qp_attr a={.qp_state=IB_QPS_INIT,.port_num=1,.qp_access_flags=6};
    CHECK(!work->modify_qp(&fp_qp.ibqp,&a,IB_QP_STATE|IB_QP_PORT|IB_QP_PKEY_INDEX|IB_QP_ACCESS_FLAGS,NULL));
    struct ib_gid_attr sgid={.device=d,.port_num=1,.gid_type=IB_GID_TYPE_ROCE_UDP_ENCAP,
        .gid={.raw={0,0,0,0,0,0,0,0,0,0,255,255,192,0,2,1}}};
    a=(struct ib_qp_attr){.qp_state=IB_QPS_RTR,.path_mtu=IB_MTU_4096,.dest_qp_num=196,.rq_psn=0x987654,.max_dest_rd_atomic=1,
        .ah_attr={.type=RDMA_AH_ATTR_TYPE_ROCE,.port_num=1,.ah_flags=IB_AH_GRH,.dmac={2,0,0,0,0,2},
            .grh={.sgid_attr=&sgid,.hop_limit=100,.dgid={.raw={0,0,0,0,0,0,0,0,0,0,255,255,192,0,2,2}}}}};
    CHECK(!work->modify_qp(&fp_qp.ibqp,&a,IB_QP_STATE|IB_QP_AV|IB_QP_PATH_MTU|IB_QP_DEST_QPN|IB_QP_RQ_PSN|
        IB_QP_MAX_DEST_RD_ATOMIC|IB_QP_MIN_RNR_TIMER,NULL));
    a=(struct ib_qp_attr){.qp_state=IB_QPS_RTS,.sq_psn=0xfffffe,.max_rd_atomic=1,.timeout=1,.retry_cnt=1,.rnr_retry=1};
    CHECK(!work->modify_qp(&fp_qp.ibqp,&a,IB_QP_STATE|IB_QP_SQ_PSN|IB_QP_MAX_QP_RD_ATOMIC|IB_QP_TIMEOUT|IB_QP_RETRY_CNT|IB_QP_RNR_RETRY,NULL));
    struct ib_sge sg={.addr=VA+0x210,.length=128,.lkey=m->lkey};
    struct ib_recv_wr receive={.wr_id=101,.sg_list=&sg,.num_sge=1};const struct ib_recv_wr *bad=NULL;
    CHECK(!work->post_recv(&fp_qp.ibqp,&receive,&bad) && !bad);
    fp_refs=refcount_read(&fp_mr->mapping->work_refs);fp_frees=km.dma_frees;CHECK(fp_refs==2);
    fp_qp.ibqp.event_handler=fp_handler;fp_qp.ibqp.qp_context=active;
}
static void fp_make_event(void)
{
    unsigned partial=fp_case&1;unsigned i;memset(&fp_record,0,sizeof(fp_record));fp_record.sequence=1;
#define P(start,width,value) do{u64 v=(value);for(i=0;i<(width);i++)if(v&(1ULL<<i))fp_record.word[((start)+i)/32]|=1U<<(((start)+i)%32);}while(0)
    P(992,8,7);P(780,64,1);P(892,8,partial ? 0x61:0x62);P(868,24,0x987654+partial);P(844,24,0x987654+partial);
    P(528,64,fp_case==14 ? 0xfedcba9889abcdefULL:fp_qp.owner.cookie);
    P(464,64,fp_case==14 ? 0x9123456700000001ULL:fp_qp.owner.epoch);
    P(448,16,fp_case==14 ? 17:fp_pd.number);P(424,24,fp_case==14 ? 2:fp_qp.ibqp.qp_num);
    if(partial){P(944,8,15);P(928,16,0x6001);P(400,24,2);P(384,16,fp_pd.number);P(320,64,fp_qp.owner.epoch);
        P(256,64,0x23456789abcdef01ULL);P(224,32,8);P(160,64,0xfedcba9876543210ULL);P(128,32,8193);
        P(104,24,0x987654);P(40,32,4096);P(16,24,0x987654);P(0,16,1);}
#undef P
    fp_visible=1;
}
static void *fp_worker_thread(void *unused)
{(void)unused;cm_run_work(&active->fatal.poll_work);return NULL;}
static void *fp_stop_thread(void *unused)
{(void)unused;fp_stop_result=as02_native_graph_stop_fatal_polling(active);return NULL;}
int main(int argc,char **argv)
{
    u64 epochs[8]={0};unsigned calls;
    if(argc==3 && !strcmp(argv[1],"prior")){int ret=old_native_graph_main(argc-1,argv+1);CHECK(!fp_reads && !fp_writes);return ret;}
    CHECK(argc==2);fp_case=strtoul(argv[1],NULL,0);CHECK(fp_case<16);fatal_profile=true;
    netdev=(struct net_device){.dev={.parent=&pci_parent.dev},.dev_addr={2,0,0,0,0,1},.mtu=9000,
        .reg_state=NETREG_REGISTERED,.running=true,.carrier=true};atomic_store(&netdev.dev.references,1);
    CHECK(!*model_parameter_enable_fatal_events && as02_mqnic_native_open(NULL,NULL,NULL)==-EACCES);
    *model_parameter_enable_native_attach=true;*model_parameter_enable_fatal_events=fp_case!=12;
    pci_parent=(struct pci_dev){.vendor=0x1234,.device=0x1001,.subsystem_vendor=0x1ce4,.subsystem_device=9};atomic_store(&pci_parent.dev.references,1);
    mqnic_parent=(struct mqnic_dev){.dev=&pci_parent.dev,.pdev=&pci_parent,.app_hw_regs_size=sizeof(application),
        .app_hw_addr=application,.app_id=AS02_NATIVE_APP_ID,.if_count=1};
    mqnic_interface=(struct mqnic_if){.mdev=&mqnic_parent,.ndev_count=1,.ndev={&netdev}};mqnic_parent.interface[0]=&mqnic_interface;app.mdev=&mqnic_parent;
    epochs[2]=0x9123456700000000ULL;CHECK(!as02_native_lease_init(&fp_lease,4,epochs));reset_hardware_model();
    if(fp_case==3)fp_bad_abi=1;
    if(fp_case==4){fp_visible=1;fp_record.sequence=1;}
    if(fp_case==5)register_error=-ENOMEM;
    int ret=as02_mqnic_native_open(&app.adev,&fp_lease,&active);
    if(fp_case==3 || fp_case==4){
        CHECK(ret==(fp_case==3 ? -ENODEV:-EBUSY) && active && !commands[AS02_CMD_EPOCH] && !rnc_writes && !fp_writes);
        CHECK(!as02_native_graph_close(&active) && !fp_lease.owner);
        printf("FATAL_PARENT_RESULT {\"pass_test\":true,\"case\":%u,\"rejected_before_epoch_write\":true,\"boundaries_modeled\":true}\n",fp_case);return 0;
    }
    if(fp_case==5){
        CHECK(ret==-ENOMEM && active && active->fatal.initialized && !active->fatal.started && !active->device->published);
        CHECK(as02_fatal_parent_start(&active->fatal)==-EBUSY && as02_native_graph_close(&active)==-EBUSY);
        CHECK(!as02_native_graph_stop_fatal_polling(active) && as02_native_graph_close(&active)==-EBUSY);
        printf("FATAL_PARENT_RESULT {\"pass_test\":true,\"case\":%u,\"failed_publication_retains_attachment_lease\":true,\"boundaries_modeled\":true}\n",fp_case);return 0;
    }
    CHECK(!ret && active->device->published && active->queues.wqe_profile==8);
    if(fp_case==12){CHECK(!fp_reads && !active->fatal.initialized && !as02_native_graph_close(&active));
        puts("FATAL_PARENT_RESULT {\"pass_test\":true,\"case\":12,\"disabled_no_FEC_probe_normal_close\":true,\"boundaries_modeled\":true}");return 0;}
    CHECK(active->fatal.started && active->fatal.poll_work.work.pending && !atomic_read(&active->completions.notify_users));
    if(fp_case==6 || fp_case==11 || fp_case==15){
        if(fp_case==15){calls=fp_reads+fp_writes;CHECK(as02_fatal_parent_start(&active->fatal)==-EBUSY && calls==fp_reads+fp_writes);}
        unsigned ticks=fp_case==11 ? 0:6;
        for(unsigned i=0;i<ticks;i++){cm_run_work(&active->fatal.poll_work);CHECK(active->fatal.poll_work.work.pending && !fp_handlers && !fp_writes);}
        CHECK(!as02_native_graph_stop_fatal_polling(active));calls=fp_reads+fp_writes;
        CHECK(!active->fatal.poll_work.work.pending && active->fatal.stopped && active->fatal.verbs.detached && active->device->stopping);
        CHECK(!as02_native_graph_stop_fatal_polling(active) && as02_fatal_parent_start(&active->fatal)==-EBUSY && calls==fp_reads+fp_writes);
        CHECK(as02_native_graph_close(&active)==-EBUSY);fp_retained();
        printf("FATAL_PARENT_RESULT {\"pass_test\":true,\"case\":%u,\"empty_ticks_no_CQ_arming\":%u,\"duplicate_start_checked\":%s,\"logical_stop_no_release\":true,\"boundaries_modeled\":true}\n",fp_case,ticks,fp_case==15 ? "true":"false");return 0;
    }
    if(fp_case==14){fp_make_event();cm_run_work(&active->fatal.poll_work);
        CHECK(active->fatal.terminal && active->fatal.last_error==-ESTALE && !fp_handlers && !fp_writes && fp_visible && !active->device->qp);
        CHECK(as02_native_graph_close(&active)==-EBUSY);fp_retained();
        puts("FATAL_PARENT_RESULT {\"pass_test\":true,\"case\":14,\"unbound_QP_event_unacked\":true,\"boundaries_modeled\":true}");return 0;}
    fp_create_qp();fp_make_event();
    if(fp_case==7)fp_record.word[(528+63)/32]^=1U<<((528+63)%32);
    if(fp_case==8)fp_record.word[31]|=1U<<8;
    if(fp_case==13)fp_record.sequence=2;
    fp_drop_ack=fp_case==2 || fp_case==10;
    if(fp_case==10){
        pthread_t worker,stopper;CHECK(!pthread_create(&worker,NULL,fp_worker_thread,NULL));
        CHECK(!pthread_mutex_lock(&fp_gate));while(!fp_handler_entered)CHECK(!pthread_cond_wait(&fp_condition,&fp_gate));CHECK(!pthread_mutex_unlock(&fp_gate));
        CHECK(!pthread_create(&stopper,NULL,fp_stop_thread,NULL));
        struct work_struct *w=&active->fatal.poll_work.work;CHECK(!pthread_mutex_lock(&w->model_lock));
        while(!w->cancel_waiters){CHECK(!pthread_cond_wait(&w->model_condition,&w->model_lock));}
        CHECK(w->running);CHECK(!pthread_mutex_unlock(&w->model_lock));
        CHECK(as02_native_graph_close(&active)==-EBUSY);fp_retained();
        CHECK(!pthread_mutex_lock(&fp_gate));fp_handler_release=true;CHECK(!pthread_cond_broadcast(&fp_condition));CHECK(!pthread_mutex_unlock(&fp_gate));
        CHECK(!pthread_join(worker,NULL) && !pthread_join(stopper,NULL) && !fp_stop_result);
        CHECK(active->fatal.stopped && !active->fatal.poll_work.work.pending && active->fatal.verbs.reader.pending_ack && fp_handlers==1);
    }else{
        cm_run_work(&active->fatal.poll_work);
        if(fp_case==7 || fp_case==8 || fp_case==13){
            CHECK(active->fatal.terminal && !active->fatal.started && !active->fatal.poll_work.work.pending && active->device->stopping);
            CHECK(active->fatal.last_error==(fp_case==7 ? -ESTALE:-EIO) && !fp_handlers && !fp_writes && fp_visible);
            CHECK(as02_fatal_parent_start(&active->fatal)==-EBUSY);fp_retained();
            printf("FATAL_PARENT_RESULT {\"pass_test\":true,\"case\":%u,\"unknown_event_halts_unacked_refs_retained\":true,\"boundaries_modeled\":true}\n",fp_case);return 0;
        }
        CHECK(fp_handlers==1 && fp_qp.attributes.qp_state==IB_QPS_ERR && active->fatal.poll_work.work.pending);
        if(fp_drop_ack){CHECK(active->fatal.verbs.reader.pending_ack);fp_drop_ack=0;cm_run_work(&active->fatal.poll_work);CHECK(fp_handlers==1 && !active->fatal.verbs.reader.pending_ack);}
        CHECK(!as02_native_graph_stop_fatal_polling(active) && !active->fatal.poll_work.work.pending);
    }
    calls=fp_reads+fp_writes;CHECK(!as02_native_graph_stop_fatal_polling(active) && calls==fp_reads+fp_writes);
    CHECK(as02_native_graph_close(&active)==-EBUSY && !unregistrations);fp_retained();
    printf("FATAL_PARENT_RESULT {\"pass_test\":true,\"case\":%u,\"parent_to_QP_handler\":true,\"handler_calls\":%u,\"no_CQ_arming\":true,\"stop_join_retains_refs\":true,\"boundaries_modeled\":true}\n",fp_case,fp_handlers);return 0;
}
