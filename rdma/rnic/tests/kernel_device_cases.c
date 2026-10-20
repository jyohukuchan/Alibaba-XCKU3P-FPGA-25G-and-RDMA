/* SPDX-License-Identifier: BSD-2-Clause-Views */
/* Actual device publication AND existing native-queue driver C. IB core,
 * netdev, Linux primitives, MMIO/pins/DMA and completion producer are models.
 */
#include "kernel_device_model.h"
#include "device.h"
#define AS02_DYNAMIC_DEVICE_CASES
#define AS02_VERBS_MAIN unused_legacy_verbs_main
#include "kernel_verbs_cases.c"
static struct net_device data_net;
static struct net_device *core_net;
static int registration_error;
static unsigned int allocations,registrations,unregistrations,deallocations;

struct ib_device *device_model_alloc(size_t bytes)
{
    struct ib_device *d=kzalloc(bytes,GFP_KERNEL);CHECK(d);
    atomic_store(&d->dev.references,1);allocations++;return d;
}
int ib_device_set_netdev(struct ib_device *d,struct net_device *n,u32 port)
{
    CHECK(d==&vdev.ibdev && port==1 && !core_net);core_net=n;dev_hold(n);return 0;
}
int ib_get_eth_speed(struct ib_device *d,u32 port,u16 *speed,u8 *width)
{ CHECK(d==&vdev.ibdev && core_net==&data_net && port==1);*speed=32;*width=1;return 0; }
int ib_register_device(struct ib_device *d,const char *name,struct device *dma)
{
    struct ib_device_attr a;struct ib_port_attr p;struct ib_port_immutable imm;u16 key;
    CHECK(d==&vdev.ibdev && dma==&dma_dev && !strcmp(name,"as02_%d"));
    CHECK(core_net && vdev.initialized && vdev.sq==&sq && hw.receive==&receive_hw &&
        vdev.mrs==&mrs && vdev.cq_hw==&cqh && vdev.qp_hw==&qph);
    CHECK(verbs==&as02_verbs_ops && metadata_ops==&as02_device_ops);
    CHECK(d->uverbs_cmd_mask==((1ULL<<28)|(1ULL<<29)|(1ULL<<21)|(1ULL<<23)));
    CHECK(!metadata_ops->query_device(d,&a,NULL) && a.max_qp==1 && a.max_mr==8 &&
        a.max_qp_wr==256 && a.max_send_sge==1 && a.atomic_cap==IB_ATOMIC_NONE);
    CHECK(!metadata_ops->query_port(d,1,&p) && p.state==IB_PORT_ACTIVE && p.max_msg_sz==4096);
    CHECK(!metadata_ops->get_port_immutable(d,1,&imm) &&
        imm.core_cap_flags==(RDMA_CORE_CAP_PROT_ROCE_UDP_ENCAP|RDMA_CORE_CAP_ETH_AH) && !imm.max_mad_size);
    CHECK(!metadata_ops->query_pkey(d,1,0,&key) && key==65535);
    registrations++;
    if(registration_error)return registration_error;
    CHECK(!metadata_ops->enable_driver(d));return 0;
}
void ib_unregister_device(struct ib_device *d)
{
    CHECK(d==&vdev.ibdev && vdev.stopping && !vdev.accepting_contexts && !vdev.context_count &&
        !vdev.pd_count && !vdev.qp && !vdev.cq_count && !vdev.mr_count);
    unregistrations++;
}
void ib_dealloc_device(struct ib_device *d)
{
    CHECK(d==&vdev.ibdev && !vdev.initialized && !vdev.published && !vdev.context_count);
    CHECK(atomic_load(&d->dev.references)==1);
    if(core_net){dev_put(core_net);core_net=NULL;}
    deallocations++;kfree(d);
}
static void graph(bool separate)
{
    const u64 epochs[8]={0};
    qp_tx_feature=retry_feature=send_feature=recv_feature=rnr_feature=
        recv_retire_feature=message_cq_feature=request_cq_feature=true;
    independent_queues_feature=separate;
    fresh();atomic_store(&dma_dev.references,1);
    dynamic_vdev=as02_device_alloc();CHECK(dynamic_vdev);
    data_net=(struct net_device){.dev={.parent=&dma_dev},.dev_addr={2,0,0,0,0,1},
        .mtu=9000,.reg_state=NETREG_REGISTERED,.running=true,.carrier=true};
    atomic_store(&data_net.dev.references,1);
    CHECK(!as02_cq_router_init(&vr));
    CHECK(!as02_sq_hw_init(&hw,mmio,sizeof(mmio),30,as02_cq_publish,&vr));
    if(separate){receive_model=model;receive_model.id=AS02_RQC_ID_VALUE;
        CHECK(!as02_sq_hw_init_receive(&receive_hw,&hw,receive_mmio,sizeof(receive_mmio),30));}
    CHECK(!as02_mr_pool_init(&mrs,&vdev.ibdev,&mmr_ops,NULL,0));CHECK(!as02_mr_pool_start_epoch(&mrs,0));
    CHECK(!as02_sq_pool_init(&sq,&mrs,&dma_dev,&as02_sqc_sq_hw_ops,&hw,epochs));
    CHECK(!as02_cq_hw_init(&cqh,&sq,cqc,sizeof(cqc)));
    mutex_init(&ctl_hw.lock);ctl_hw.registers=eth;
    CHECK(!as02_ctl_init(&ctl_hw.control,&cio,NULL,30));CHECK(!as02_qp_hw_init(&qph,&ctl_hw));
    CHECK(!as02_qp_hw_enable_retry(&qph,rrp,sizeof(rrp),30));
    CHECK(!as02_verbs_bind(&vdev,&mrs,&sq,&cqh,&qph,&vr,eth,sizeof(eth)));
}
static void close_graph(void)
{
    CHECK(!as02_verbs_unbind(&vdev));CHECK(!as02_cq_hw_detach(&cqh));
    CHECK(!as02_sq_pool_destroy(&sq));CHECK(!as02_mr_pool_destroy(&mrs));
    if(independent_queues_feature)CHECK(!as02_sq_hw_detach(&receive_hw));
    CHECK(!as02_sq_hw_detach(&hw));CHECK(!as02_ctl_detach(&ctl_hw.control));
    CHECK(!as02_device_free(&vdev));dynamic_vdev=NULL;
    CHECK(!atomic_load(&km.heap_live) && !atomic_load(&km.umem_live) && !atomic_load(&km.module_refs));
    CHECK(atomic_load(&dma_dev.references)==1 && atomic_load(&data_net.dev.references)==1);
    CHECK(km.dma_allocs==km.dma_frees && allocations==deallocations);
}
static void completion(bool receive)
{
    const struct as02_wqe *w=receive ? &receive_model.observed[0]:&model.observed[0];
    CHECK(!event_visible && w->sequence==1);memset(&event,0,sizeof(event));
    event.sequence=acknowledged+1;event.proofs=15;event.received_bytes=receive ? 65:0;
    event.cookie=receive ? pair(receive_model.reply+6):qp.owner.cookie;
#define P(start,width,value) put_bits(event.context,start,width,value)
    P(0,2,3);P(116,64,0x210);P(180,64,w->local_address);P(244,32,w->local_key);
    P(276,32,w->length);P(308,16,w->flags);P(324,16,w->opcode);P(340,16,receive ? 1:2);
    P(356,16,pd.number);P(372,24,qp.ibqp.qp_num);P(396,64,w->epoch);P(460,64,w->sequence);P(524,64,w->wr_id);
#undef P
    event_visible=true;
}
int main(int argc,char **argv)
{
    struct as02_ucontext context={};struct ib_udata private={.inlen=1};
    struct ib_device_attr a;struct ib_port_attr port;u16 key;void *gid_context=NULL;
    struct ib_gid_attr gid={.port_num=1,.gid_type=IB_GID_TYPE_ROCE_UDP_ENCAP,
        .gid={.raw={0,0,0,0,0,0,0,0,0,0,255,255,192,0,2,1}}};
    unsigned int scenario;CHECK(argc==2);scenario=strtoul(argv[1],NULL,0);CHECK(scenario<5);
    if(scenario==2){
        dynamic_vdev=as02_device_alloc();CHECK(as02_device_publish(&vdev,&dma_dev,&data_net,eth,sizeof(eth))==-EINVAL);
        CHECK(!registrations && !as02_device_free(&vdev) && allocations==deallocations && !atomic_load(&km.heap_live));
        puts("KERNEL_DEVICE_RESULT {\"pass_test\":true,\"empty_device_refused\":true}");return 0;
    }
    graph(scenario!=1);
    if(scenario==1){CHECK(as02_device_publish(&vdev,&dma_dev,&data_net,eth,sizeof(eth))==-EBUSY && !registrations);
        close_graph();puts("KERNEL_DEVICE_RESULT {\"pass_test\":true,\"incomplete_graph_refused\":true}");return 0;}
    if(scenario==3)registration_error=-ENOMEM;
    if(scenario==4){data_net.dev_addr[5]=3;
        CHECK(as02_device_publish(&vdev,&dma_dev,&data_net,eth,sizeof(eth))==-ESTALE && !registrations);
        data_net.dev_addr[5]=1;}
    if(scenario==3){CHECK(as02_device_publish(&vdev,&dma_dev,&data_net,eth,sizeof(eth))==-ENOMEM);
        CHECK(registrations==1 && !vdev.published && vdev.stopping &&
            atomic_load(&data_net.dev.references)==3 && as02_device_free(&vdev)==-EBUSY);
        CHECK(!as02_device_unpublish(&vdev) && !unregistrations);close_graph();
        puts("KERNEL_DEVICE_RESULT {\"pass_test\":true,\"registration_failure_retains_graph_until_cleanup\":true}");return 0;}
    CHECK(!as02_device_publish(&vdev,&dma_dev,&data_net,eth,sizeof(eth)) && vdev.published);
    CHECK(as02_verbs_unbind(&vdev)==-EBUSY && as02_device_free(&vdev)==-EBUSY);
    CHECK(metadata_ops->query_device(&vdev.ibdev,&a,&private)==-EOPNOTSUPP);
    CHECK(!metadata_ops->query_device(&vdev.ibdev,&a,NULL) && a.max_mr_size==1048576 &&
        a.page_size_cap==4096 && !a.device_cap_flags && !a.kernel_cap_flags);
    CHECK(metadata_ops->get_link_layer(&vdev.ibdev,1)==IB_LINK_LAYER_ETHERNET &&
        metadata_ops->get_link_layer(&vdev.ibdev,0)==IB_LINK_LAYER_UNSPECIFIED);
    CHECK(metadata_ops->query_pkey(&vdev.ibdev,1,1,&key)==-EINVAL);
    data_net.carrier=false;CHECK(!metadata_ops->query_port(&vdev.ibdev,1,&port) && port.state==IB_PORT_DOWN);
    data_net.carrier=true;data_net.mtu=1500;
    CHECK(!metadata_ops->query_port(&vdev.ibdev,1,&port) && port.state==IB_PORT_DOWN);data_net.mtu=9000;
    gid.device=&vdev.ibdev;gid.ndev=&data_net;
    CHECK(!metadata_ops->add_gid(&gid,&gid_context) && gid_context==&vdev);
    CHECK(!metadata_ops->del_gid(&gid,&gid_context));gid.gid.raw[15]=2;
    CHECK(metadata_ops->add_gid(&gid,&gid_context)==-EOPNOTSUPP);gid.gid.raw[15]=1;
    context.ibucontext.device=&vdev.ibdev;
    CHECK(metadata_ops->alloc_ucontext(&context.ibucontext,&private)==-EOPNOTSUPP);
    CHECK(!metadata_ops->alloc_ucontext(&context.ibucontext,NULL) && vdev.context_count==1);
    CHECK(as02_device_unpublish(&vdev)==-EBUSY && !unregistrations && vdev.published);
    pd.ibpd.device=&vdev.ibdev;CHECK(!verbs->alloc_pd(&pd.ibpd,NULL));
    struct ib_mr *m=register_mr();CHECK(!IS_ERR(m));create_objects();activate();
    struct ib_sge sg={.addr=VA+0x210,.length=128,.lkey=m->lkey};
    struct ib_recv_wr receive={.wr_id=101,.sg_list=&sg,.num_sge=1};const struct ib_recv_wr *bad_r=NULL;
    CHECK(!verbs->post_recv(&qp.ibqp,&receive,&bad_r) && !bad_r);sg.length=65;
    struct ib_send_wr send={.wr_id=102,.sg_list=&sg,.num_sge=1,.opcode=IB_WR_SEND};const struct ib_send_wr *bad_s=NULL;
    CHECK(!verbs->post_send(&qp.ibqp,&send,&bad_s) && !bad_s);
    struct ib_wc wc;completion(false);CHECK(verbs->poll_cq(&cq.ibcq,1,&wc)==1 && wc.opcode==IB_WC_SEND && wc.wr_id==102);
    completion(true);CHECK(verbs->poll_cq(&recv_cq.ibcq,1,&wc)==1 && wc.opcode==IB_WC_RECV && wc.wr_id==101 && wc.byte_len==65);
    CHECK(!verbs->destroy_qp(&qp.ibqp,NULL));CHECK(!verbs->destroy_cq(&recv_cq.ibcq,NULL));
    CHECK(!verbs->destroy_cq(&cq.ibcq,NULL));CHECK(!verbs->dereg_mr(m,NULL));CHECK(!verbs->dealloc_pd(&pd.ibpd,NULL));
    metadata_ops->dealloc_ucontext(&context.ibucontext);CHECK(!vdev.context_count);
    CHECK(!as02_device_unpublish(&vdev) && unregistrations==1 && !vdev.published);
    CHECK(metadata_ops->alloc_ucontext(&context.ibucontext,NULL)==-ESHUTDOWN);
    close_graph();
    puts("KERNEL_DEVICE_RESULT {\"pass_test\":true,\"actual_register_and_context_entrypoints\":true,\"actual_SEND_RECV_callbacks_and_CQs\":true,\"no_empty_or_unimplemented_capabilities\":true,\"IB_core_netdev_Linux_HW_models\":true,\"hardware_verified\":false}");return 0;
}
