/* SPDX-License-Identifier: BSD-2-Clause-Views */
/* Actual public libibverbs/provider/standard command serialization. Only the
 * fake-fd syscall boundary is modeled. No real kernel/NIC or result DMA. */
#define main legacy_provider_main
#define write legacy_provider_write
#include "provider_commands.c"
#undef main
#undef write

static struct ibv_send_wr expected_atomic[2];
static unsigned int atomic_posts,atomic_polls;

ssize_t write(int fd,const void *buffer,size_t bytes)
{
    const struct ib_uverbs_cmd_hdr *h=buffer;
    if(fd!=MODEL_FD || (h->command!=IB_USER_VERBS_CMD_POST_SEND && h->command!=IB_USER_VERBS_CMD_POLL_CQ))
        return legacy_provider_write(fd,buffer,bytes);
    CHECK(h->in_words*4==bytes);commands[h->command]++;
    if(h->command==IB_USER_VERBS_CMD_POST_SEND){
        const struct ibv_post_send *q=buffer;
        struct ib_uverbs_post_send_resp *r=(void *)(uintptr_t)q->response;
        const struct ib_uverbs_send_wr *w=(const void *)(q+1);
        const struct ibv_sge *s=(const void *)(w+q->wr_count);
        CHECK(q->qp_handle==44 && q->wr_count==2 && q->sge_count==2 && q->wqe_size==sizeof(*w) &&
            bytes==sizeof(*q)+2*sizeof(*w)+2*sizeof(*s));
        for(unsigned int i=0;i<2;i++){
            const struct ibv_send_wr *e=&expected_atomic[i];
            CHECK(w[i].wr_id==e->wr_id && w[i].opcode==(uint32_t)e->opcode && w[i].num_sge==1 &&
                w[i].send_flags==IBV_SEND_SIGNALED && w[i].wr.atomic.remote_addr==e->wr.atomic.remote_addr &&
                w[i].wr.atomic.compare_add==e->wr.atomic.compare_add && w[i].wr.atomic.swap==e->wr.atomic.swap &&
                w[i].wr.atomic.rkey==e->wr.atomic.rkey && s[i].addr==VA+0x210 && s[i].length==8 && s[i].lkey==0x81234567);
        }
        atomic_posts++;r->bad_wr=fail_post ? 2:0;
        if(fail_post){errno=ENOSPC;return -1;}
    }else{
        const struct ibv_poll_cq *q=buffer;
        struct ib_uverbs_poll_cq_resp *r=(void *)(uintptr_t)q->response;
        CHECK(q->cq_handle==40 && q->ne==2);memset(r,0,h->out_words*4);r->count=2;
        for(unsigned int i=0;i<2;i++){
            r->wc[i].wr_id=expected_atomic[i].wr_id;r->wc[i].qp_num=2;r->wc[i].byte_len=8;
            r->wc[i].opcode=i ? IBV_WC_FETCH_ADD:IBV_WC_COMP_SWAP;
        }
        atomic_polls++;
    }
    return bytes;
}

int main(int argc,char **argv)
{
    struct ibv_device **list;struct verbs_sysfs_dev sys={.driver_id=RDMA_DRIVER_UNKNOWN,.abi_ver=1,.match=&matches[0]};
    struct verbs_device *d;struct verbs_context *v;struct ibv_context *c;struct ibv_device_attr_ex caps;
    struct ibv_pd *pd;struct ibv_mr *mr;struct ibv_cq *cq,*rq;struct ibv_qp *qp;struct ibv_send_wr *bad;
    struct ibv_sge sg;struct ibv_wc wc[2];
    const uint64_t operands[]={0,UINT64_C(0x8000000100000001),UINT64_MAX};
    CHECK(argc==2);immediate_profile=atoi(argv[1])!=0;
    list=ibv_get_device_list(NULL);CHECK(list);ibv_free_device_list(list);
    snprintf(sys.ibdev_name,sizeof(sys.ibdev_name),"as02_0");CHECK(match_device(&sys));
    d=as02_device_ops.alloc_device(&sys);CHECK(d);d->sysfs=&sys;d->ops=&as02_device_ops;atomic_init(&d->refcount,1);
    d->device.node_type=IBV_NODE_CA;d->device.transport_type=IBV_TRANSPORT_IB;
    v=as02_device_ops.alloc_context(&d->device,MODEL_FD,NULL);CHECK(v);c=&v->context;
    CHECK(!ibv_query_device_ex(c,NULL,&caps) && caps.orig_attr.atomic_cap==IBV_ATOMIC_NONE);
    pd=ibv_alloc_pd(c);CHECK(pd);mr=ibv_reg_mr_iova(pd,(void *)0x10003,8192,VA,7);CHECK(mr);
    cq=ibv_create_cq(c,2,NULL,NULL,0);rq=ibv_create_cq(c,2,NULL,NULL,0);CHECK(cq && rq);
    struct ibv_qp_init_attr initial={.send_cq=cq,.recv_cq=rq,.qp_type=IBV_QPT_RC,
        .cap={.max_send_wr=2,.max_recv_wr=2,.max_send_sge=1,.max_recv_sge=1}};
    qp=ibv_create_qp(pd,&initial);CHECK(qp);
    sg=(struct ibv_sge){.addr=VA+0x210,.length=8,.lkey=mr->lkey};
    for(unsigned int n=0;n<3;n++){
        for(unsigned int i=0;i<2;i++)expected_atomic[i]=(struct ibv_send_wr){
            .wr_id=UINT64_C(0xf123456789abc000)+n*2+i,.sg_list=&sg,.num_sge=1,
            .opcode=i ? IBV_WR_ATOMIC_FETCH_AND_ADD:IBV_WR_ATOMIC_CMP_AND_SWP,.send_flags=IBV_SEND_SIGNALED,
            .wr.atomic={.remote_addr=UINT64_C(0xe23456789abcd008),.rkey=0x92345678,
                .compare_add=operands[n],.swap=i ? 0:operands[n]^UINT64_C(0x8123456789abcdef)}};
        expected_atomic[0].next=&expected_atomic[1];
        fail_post=true;bad=NULL;
        CHECK(ibv_post_send(qp,expected_atomic,&bad)==ENOSPC && bad==expected_atomic+1);
        fail_post=false;bad=NULL;CHECK(!ibv_post_send(qp,expected_atomic,&bad) && !bad);
        CHECK(ibv_poll_cq(cq,2,wc)==2);
        for(unsigned int i=0;i<2;i++)CHECK(wc[i].wr_id==expected_atomic[i].wr_id && wc[i].qp_num==2 &&
            wc[i].opcode==(i ? IBV_WC_FETCH_ADD:IBV_WC_COMP_SWAP) && wc[i].byte_len==8 &&
            wc[i].status==IBV_WC_SUCCESS && !wc[i].wc_flags && !wc[i].imm_data);
    }
    CHECK(atomic_posts==6 && atomic_polls==3 && ioctls);
    CHECK(!ibv_destroy_qp(qp) && !ibv_destroy_cq(rq) && !ibv_destroy_cq(cq));
    CHECK(!ibv_dereg_mr(mr) && !ibv_dealloc_pd(pd) && !ibv_close_device(c));
    CHECK(atomic_load(&d->refcount)==1);as02_device_ops.uninit_device(d);
    printf("PROVIDER_ATOMIC_RESULT {\"pass_test\":true,\"profile1023\":%s,\"actual_public_ibv_and_command_serializer\":true,\"full64bit_CAS_FADD_operands\":true,\"exact_second_bad_WR\":true,\"Atomic_WC_metadata\":true,\"commands\":6,\"polls\":3,\"kernel_syscall_boundary_modeled\":true,\"device_Atomic_cap_still_NONE\":true,\"no_result_DMA_or_hardware_claim\":true}\n",immediate_profile ? "true":"false");
    return 0;
}
