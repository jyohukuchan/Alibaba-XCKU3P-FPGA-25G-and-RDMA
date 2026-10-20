/* SPDX-License-Identifier: BSD-2-Clause-Views */
/* Real public libibverbs calls, provider and command marshalling. Only the
 * ioctl/write kernel boundary is modeled. Read-only device enumeration
 * initializes the real library's kernel ABI; no real NIC context is opened.
 */
#include <assert.h>
#include <arpa/inet.h>
#include <stdarg.h>
#include <sys/ioctl.h>
#include <sys/syscall.h>
#include <unistd.h>
#include <libibverbs/ibverbs.h>
#include "../provider/as02.c"
#define CHECK(x) do {if(!(x)){fprintf(stderr,"PROVIDER CHECK %d %s\n",__LINE__,#x);abort();}}while(0)
#define MODEL_FD 424242
#define VA 0xfedcba9876543210ULL
static unsigned int commands[64],ioctls;
static bool wrong_profile,fail_post,fail_destroy;
static bool immediate_profile,poll_immediate,poll_write_immediate;
static uint32_t expected_immediate;
static uint32_t next_cq=40;
static void device_response(struct ib_uverbs_query_device_resp *r)
{
    uint64_t profile=immediate_profile ? AS02_FW_IMMEDIATE:AS02_FW;
    r->fw_ver=wrong_profile ? (profile&~256ULL):profile;
    r->vendor_id=0x1234;r->vendor_part_id=0x1001;r->max_qp=1;r->max_qp_wr=256;
    r->max_sge=1;r->max_sge_rd=1;r->max_mr_size=1048576;r->max_mr=8;r->max_cqe=4096;
    r->atomic_cap=IBV_ATOMIC_NONE;r->phys_port_cnt=1;
}
int ioctl(int fd,unsigned long request,...)
{
    va_list args;void *argument;
    va_start(args,request);argument=va_arg(args,void *);va_end(args);
    if(fd==MODEL_FD){ioctls++;errno=ENOTTY;return -1;}
    return syscall(SYS_ioctl,fd,request,argument);
}
ssize_t write(int fd,const void *buffer,size_t bytes)
{
    const struct ib_uverbs_cmd_hdr *h=buffer;
    if(fd!=MODEL_FD)return syscall(SYS_write,fd,buffer,bytes);
    if(h->command&IB_USER_VERBS_CMD_FLAG_EXTENDED){
        const struct ibv_query_device_ex *q=buffer;
        struct ib_uverbs_ex_query_device_resp *r=(void *)(uintptr_t)q->hdr.ex_hdr.response;
        CHECK(h->command==(IB_USER_VERBS_CMD_FLAG_EXTENDED|IB_USER_VERBS_EX_CMD_QUERY_DEVICE) &&
            h->in_words*8+sizeof(struct ex_hdr)==bytes &&
            !q->hdr.ex_hdr.provider_in_words && !q->hdr.ex_hdr.provider_out_words);
        memset(r,0,h->out_words*8);r->response_length=sizeof(*r);device_response(&r->base);
        commands[IB_USER_VERBS_CMD_QUERY_DEVICE]++;return bytes;
    }
    CHECK(h->command<64 && h->in_words*4==bytes);commands[h->command]++;
    switch(h->command){
    case IB_USER_VERBS_CMD_GET_CONTEXT:{
        const struct ibv_get_context *q=buffer;
        struct ib_uverbs_get_context_resp *r=(void *)(uintptr_t)q->response;int channel[2];
        CHECK(bytes==sizeof(*q) && !pipe(channel));close(channel[1]);
        memset(r,0,sizeof(*r));r->async_fd=channel[0];r->num_comp_vectors=1;break;}
    case IB_USER_VERBS_CMD_QUERY_DEVICE:{
        const struct ibv_query_device *q=buffer;
        struct ib_uverbs_query_device_resp *r=(void *)(uintptr_t)q->response;
        memset(r,0,h->out_words*4);device_response(r);break;}
    case IB_USER_VERBS_CMD_QUERY_PORT:{
        const struct ibv_query_port *q=buffer;struct ib_uverbs_query_port_resp *r=(void *)(uintptr_t)q->response;
        CHECK(q->port_num==1);memset(r,0,h->out_words*4);r->state=IBV_PORT_ACTIVE;r->max_mtu=IBV_MTU_4096;
        r->active_mtu=IBV_MTU_4096;r->max_msg_sz=4096;r->gid_tbl_len=8;r->pkey_tbl_len=1;break;}
    case IB_USER_VERBS_CMD_ALLOC_PD:{
        const struct ibv_alloc_pd *q=buffer;struct ib_uverbs_alloc_pd_resp *r=(void *)(uintptr_t)q->response;
        CHECK(bytes==sizeof(*q));r->pd_handle=17;break;}
    case IB_USER_VERBS_CMD_REG_MR:{
        const struct ibv_reg_mr *q=buffer;struct ib_uverbs_reg_mr_resp *r=(void *)(uintptr_t)q->response;
        CHECK(bytes==sizeof(*q) && q->pd_handle==17 && q->start==0x10003 && q->length==8192 && q->hca_va==VA && q->access_flags==7);
        r->mr_handle=18;r->lkey=0x81234567;r->rkey=0x81234567;break;}
    case IB_USER_VERBS_CMD_CREATE_CQ:{
        const struct ibv_create_cq *q=buffer;struct ib_uverbs_create_cq_resp *r=(void *)(uintptr_t)q->response;
        CHECK(bytes==sizeof(*q) && q->cqe==2);r->cq_handle=next_cq++;r->cqe=2;break;}
    case IB_USER_VERBS_CMD_CREATE_QP:{
        const struct ibv_create_qp *q=buffer;struct ib_uverbs_create_qp_resp *r=(void *)(uintptr_t)q->response;
        CHECK(bytes==sizeof(*q) && q->pd_handle==17 && q->send_cq_handle==40 && q->recv_cq_handle==41 &&
            q->qp_type==IBV_QPT_RC && q->max_send_wr==2 && q->max_recv_wr==2);
        memset(r,0,h->out_words*4);r->qp_handle=44;r->qpn=2;
        r->max_send_wr=2;r->max_recv_wr=2;r->max_send_sge=1;r->max_recv_sge=1;break;}
    case IB_USER_VERBS_CMD_MODIFY_QP:{
        const struct ibv_modify_qp *q=buffer;CHECK(q->qp_handle==44 && q->attr_mask==IBV_QP_STATE && q->qp_state==IBV_QPS_RTS);break;}
    case IB_USER_VERBS_CMD_QUERY_QP:{
        const struct ibv_query_qp *q=buffer;struct ib_uverbs_query_qp_resp *r=(void *)(uintptr_t)q->response;
        CHECK(q->qp_handle==44);memset(r,0,h->out_words*4);r->qp_state=IBV_QPS_RTS;break;}
    case IB_USER_VERBS_CMD_POST_RECV:{
        const struct ibv_post_recv *q=buffer;struct ib_uverbs_post_recv_resp *r=(void *)(uintptr_t)q->response;
        const struct ib_uverbs_recv_wr *w=(const void *)(q+1);
        const struct ibv_sge *s=(const void *)(w+1);
        CHECK(q->qp_handle==44 && q->wr_count==1 && q->sge_count==1 && q->wqe_size==sizeof(*w) &&
            w->wr_id==1002 && w->num_sge==1 && s->addr==VA+0x210 && s->length==128 && s->lkey==0x81234567);
        r->bad_wr=0;break;}
    case IB_USER_VERBS_CMD_POST_SEND:{
        const struct ibv_post_send *q=buffer;struct ib_uverbs_post_send_resp *r=(void *)(uintptr_t)q->response;
        const struct ib_uverbs_send_wr *w=(const void *)(q+1);
        const struct ibv_sge *s=(const void *)(w+q->wr_count);
        CHECK(q->qp_handle==44 && q->sge_count==q->wr_count && q->wqe_size==sizeof(*w));
        for(unsigned int i=0;i<q->wr_count;i++){
            CHECK(w[i].num_sge==1 && w[i].send_flags==IBV_SEND_SIGNALED &&
                s[i].addr==VA+0x210 && s[i].length==65 && s[i].lkey==0x81234567);
            if(w[i].opcode!=IBV_WR_SEND && w[i].opcode!=IBV_WR_SEND_WITH_IMM)
                CHECK((w[i].opcode==IBV_WR_RDMA_READ || w[i].opcode==IBV_WR_RDMA_WRITE || w[i].opcode==IBV_WR_RDMA_WRITE_WITH_IMM) &&
                w[i].wr.rdma.remote_addr==0xe23456789abcdef0ULL && w[i].wr.rdma.rkey==0x92345678);
            if(w[i].opcode==IBV_WR_SEND_WITH_IMM || w[i].opcode==IBV_WR_RDMA_WRITE_WITH_IMM)
                CHECK(immediate_profile && w[i].ex.imm_data==htonl(expected_immediate));
        }
        r->bad_wr=fail_post ? 2:0;if(fail_post){errno=ENOSPC;return -1;}break;}
    case IB_USER_VERBS_CMD_POLL_CQ:{
        const struct ibv_poll_cq *q=buffer;struct ib_uverbs_poll_cq_resp *r=(void *)(uintptr_t)q->response;
        CHECK(q->cq_handle==40 && q->ne==2);memset(r,0,h->out_words*4);r->count=2;
        r->wc[0].wr_id=1001;r->wc[0].opcode=IBV_WC_SEND;r->wc[0].qp_num=2;
        r->wc[1].wr_id=1002;r->wc[1].opcode=poll_write_immediate ? IBV_WC_RECV_RDMA_WITH_IMM:IBV_WC_RECV;
        r->wc[1].qp_num=2;r->wc[1].byte_len=65;
        if(poll_immediate){r->wc[1].wc_flags=IBV_WC_WITH_IMM;r->wc[1].ex.imm_data=htonl(expected_immediate);}break;}
    case IB_USER_VERBS_CMD_REQ_NOTIFY_CQ:{
        const struct ibv_req_notify_cq *q=buffer;CHECK(q->cq_handle==40 && !q->solicited_only);break;}
    case IB_USER_VERBS_CMD_DESTROY_QP:{
        const struct ibv_destroy_qp *q=buffer;struct ib_uverbs_destroy_qp_resp *r=(void *)(uintptr_t)q->response;
        CHECK(q->qp_handle==44);if(fail_destroy){errno=EBUSY;return -1;}memset(r,0,sizeof(*r));break;}
    case IB_USER_VERBS_CMD_DESTROY_CQ:{
        const struct ibv_destroy_cq *q=buffer;struct ib_uverbs_destroy_cq_resp *r=(void *)(uintptr_t)q->response;
        CHECK(q->cq_handle==40 || q->cq_handle==41);memset(r,0,sizeof(*r));break;}
    case IB_USER_VERBS_CMD_DEREG_MR:{const struct ibv_dereg_mr *q=buffer;CHECK(q->mr_handle==18);break;}
    case IB_USER_VERBS_CMD_DEALLOC_PD:{const struct ibv_dealloc_pd *q=buffer;CHECK(q->pd_handle==17);break;}
    default:fprintf(stderr,"unmodeled command %u\n",h->command);abort();
    }
    return bytes;
}
int main(int argc,char **argv)
{
    CHECK(argc==1 || (argc==2 && !strcmp(argv[1],"immediate")));immediate_profile=argc==2;
    /* This initializes the genuine library ABI, NOT a fake global version.
     * Enumeration is read-only; no returned physical device is opened.
     */
    struct ibv_device **list=ibv_get_device_list(NULL);CHECK(list);ibv_free_device_list(list);
    struct verbs_sysfs_dev sys={.driver_id=RDMA_DRIVER_UNKNOWN,.abi_ver=1,.match=&matches[0]};
    snprintf(sys.ibdev_name,sizeof(sys.ibdev_name),"as02_0");CHECK(match_device(&sys));
    sys.abi_ver=2;CHECK(!match_device(&sys));sys.abi_ver=1;sys.driver_id=RDMA_DRIVER_RXE;
    CHECK(!match_device(&sys));sys.driver_id=RDMA_DRIVER_UNKNOWN;
    struct verbs_device *device=as02_device_ops.alloc_device(&sys);CHECK(device);
    device->sysfs=&sys;device->ops=&as02_device_ops;atomic_init(&device->refcount,1);
    device->device.node_type=IBV_NODE_CA;device->device.transport_type=IBV_TRANSPORT_IB;
    wrong_profile=true;errno=0;
    CHECK(!as02_device_ops.alloc_context(&device->device,MODEL_FD,NULL) && errno==EPROTONOSUPPORT);
    wrong_profile=false;
    struct verbs_context *v=as02_device_ops.alloc_context(&device->device,MODEL_FD,NULL);CHECK(v);
    struct ibv_context *c=&v->context;struct ibv_device_attr_ex caps;struct ibv_port_attr port;
    CHECK(!ibv_query_device_ex(c,NULL,&caps) && caps.orig_attr.max_qp==1 &&
        !strcmp(caps.orig_attr.fw_ver,immediate_profile ? "00010000.000003ff":"00010000.000001ff"));
    CHECK(!ibv_query_port(c,1,&port) && port.max_msg_sz==4096);
    struct ibv_pd *pd=ibv_alloc_pd(c);CHECK(pd && pd->handle==17);
    struct ibv_mr *mr=ibv_reg_mr_iova(pd,(void *)0x10003,8192,VA,7);CHECK(mr && mr->lkey==0x81234567);
    struct ibv_cq *cq=ibv_create_cq(c,2,NULL,NULL,0),*rq=ibv_create_cq(c,2,NULL,NULL,0);CHECK(cq && rq);
    struct ibv_qp_init_attr initial={.send_cq=cq,.recv_cq=rq,.qp_type=IBV_QPT_RC,
        .cap={.max_send_wr=2,.max_recv_wr=2,.max_send_sge=1,.max_recv_sge=1},.sq_sig_all=0};
    struct ibv_qp *qp=ibv_create_qp(pd,&initial);CHECK(qp && qp->qp_num==2);
    struct ibv_qp_attr a={.qp_state=IBV_QPS_RTS};CHECK(!ibv_modify_qp(qp,&a,IBV_QP_STATE));
    CHECK(!ibv_query_qp(qp,&a,IBV_QP_STATE,&initial) && a.qp_state==IBV_QPS_RTS);
    struct ibv_sge sg={.addr=VA+0x210,.length=128,.lkey=mr->lkey};
    struct ibv_recv_wr receive={.wr_id=1002,.sg_list=&sg,.num_sge=1},*bad_r=NULL;
    CHECK(!ibv_post_recv(qp,&receive,&bad_r) && !bad_r);sg.length=65;
    struct ibv_send_wr read={.wr_id=1003,.sg_list=&sg,.num_sge=1,.opcode=IBV_WR_RDMA_READ,.send_flags=IBV_SEND_SIGNALED,
        .wr.rdma={.remote_addr=0xe23456789abcdef0ULL,.rkey=0x92345678}};
    struct ibv_send_wr send={.wr_id=1001,.sg_list=&sg,.num_sge=1,.opcode=IBV_WR_SEND,.send_flags=IBV_SEND_SIGNALED,.next=&read},*bad_s=NULL;
    fail_post=true;CHECK(ibv_post_send(qp,&send,&bad_s)==ENOSPC && bad_s==&read);
    fail_post=false;send.next=NULL;bad_s=NULL;CHECK(!ibv_post_send(qp,&send,&bad_s) && !bad_s);
    CHECK(!ibv_post_send(qp,&read,&bad_s));read.opcode=IBV_WR_RDMA_WRITE;CHECK(!ibv_post_send(qp,&read,&bad_s));
    struct ibv_wc wc[2];CHECK(ibv_poll_cq(cq,2,wc)==2 && wc[0].wr_id==1001 && wc[0].opcode==IBV_WC_SEND &&
        wc[1].wr_id==1002 && wc[1].opcode==IBV_WC_RECV && wc[1].byte_len==65);
    if(immediate_profile){
        for(unsigned int i=0;i<2;i++){
            expected_immediate=i ? 0x89abcdef:0;
            send.opcode=IBV_WR_SEND_WITH_IMM;send.imm_data=htonl(expected_immediate);
            CHECK(!ibv_post_send(qp,&send,&bad_s));
            expected_immediate=i ? 0x01234567:0;
            read.opcode=IBV_WR_RDMA_WRITE_WITH_IMM;read.imm_data=htonl(expected_immediate);
            CHECK(!ibv_post_send(qp,&read,&bad_s));
        }
        for(unsigned int i=0;i<2;i++){
            poll_immediate=true;poll_write_immediate=i;expected_immediate=i ? 0x89abcdef:0;
            CHECK(ibv_poll_cq(cq,2,wc)==2 && !wc[0].wc_flags && wc[1].wc_flags==IBV_WC_WITH_IMM &&
                wc[1].imm_data==htonl(expected_immediate) && wc[1].byte_len==65 &&
                wc[1].opcode==(i ? IBV_WC_RECV_RDMA_WITH_IMM:IBV_WC_RECV));
        }
    }
    CHECK(!ibv_req_notify_cq(cq,0));fail_destroy=true;CHECK(ibv_destroy_qp(qp)==EBUSY && qp->handle==44);
    fail_destroy=false;CHECK(!ibv_destroy_qp(qp) && !ibv_destroy_cq(rq) && !ibv_destroy_cq(cq));
    CHECK(!ibv_dereg_mr(mr) && !ibv_dealloc_pd(pd));CHECK(!ibv_close_device(c));
    CHECK(atomic_load(&device->refcount)==1);as02_device_ops.uninit_device(device);
    CHECK(commands[IB_USER_VERBS_CMD_POST_SEND]==(immediate_profile ? 8:4) && commands[IB_USER_VERBS_CMD_POST_RECV]==1 && ioctls);
    printf("PROVIDER_IMMEDIATE_RESULT {\"pass_test\":true,\"profile1023\":%s,\"real_libibverbs_SEND_WRITE_IMM_and_WC_serialization\":%s,\"kernel_syscall_boundary_modeled\":true,\"hardware_verified\":false}\n",immediate_profile ? "true":"false",immediate_profile ? "true":"false");
    puts("PROVIDER_COMMANDS_RESULT {\"pass_test\":true,\"real_public_libibverbs_and_command_marshalling\":true,\"SEND_READ_WRITE_RECV\":true,\"full64bit_VA_remote_address_keys\":true,\"bad_WR_pointer_and_busy_destroy_retained\":true,\"kernel_syscall_boundary_modeled\":true,\"read_only_device_enumeration\":true,\"real_NIC_opened\":false,\"hardware_verified\":false}");
}
