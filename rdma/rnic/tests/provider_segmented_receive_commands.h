/* SPDX-License-Identifier: BSD-2-Clause-Views */
/* Real libibverbs/provider standard RECV marshalling; ONLY fake-fd syscalls
 * and WC replies are modeled. No kernel/MR/RQ/payload/CQ execution proof. */
static bool segmented_receive_boundary;
static unsigned int segmented_receive_posts,segmented_receive_polls;
static unsigned int segmented_receive_registrations,segmented_receive_deregistrations;
static struct ibv_recv_wr segmented_receive_expected[2];
static unsigned int segmented_receive_bytes;
static uint32_t segmented_receive_notification;

static ssize_t segmented_receive_write(int fd,const void *buffer,size_t bytes)
{
    const struct ib_uverbs_cmd_hdr *h=buffer;
    if(fd!=MODEL_FD)return legacy_provider_write(fd,buffer,bytes);
    CHECK(h->in_words*4==bytes && h->command<64);commands[h->command]++;
    switch(h->command){
    case IB_USER_VERBS_CMD_REG_MR:{
        const struct ibv_reg_mr *q=buffer;struct ib_uverbs_reg_mr_resp *r=(void *)(uintptr_t)q->response;
        CHECK(bytes==sizeof(*q) && q->pd_handle==17 && q->start==0x10000 &&
            q->length==1048576 && q->hca_va==VA && q->access_flags==IBV_ACCESS_LOCAL_WRITE);
        r->mr_handle=22;r->lkey=0x91234567;r->rkey=0xa2345678;segmented_receive_registrations++;break;}
    case IB_USER_VERBS_CMD_POST_RECV:{
        const struct ibv_post_recv *q=buffer;
        const struct ib_uverbs_recv_wr *w=(const void *)(q+1);
        const struct ibv_sge *s=(const void *)(w+2);
        struct ib_uverbs_post_recv_resp *r=(void *)(uintptr_t)q->response;
        CHECK(q->qp_handle==44 && q->wr_count==2 && q->sge_count==2 && q->wqe_size==sizeof(*w) &&
            bytes==sizeof(*q)+2*sizeof(*w)+2*sizeof(*s));
        for(unsigned int i=0;i<2;i++){
            const struct ibv_recv_wr *e=&segmented_receive_expected[i];
            CHECK(w[i].wr_id==e->wr_id && w[i].num_sge==1 && s[i].addr==e->sg_list->addr &&
                s[i].length==e->sg_list->length && s[i].lkey==0x91234567);
        }
        segmented_receive_posts++;r->bad_wr=fail_post ? 2:0;
        if(fail_post){errno=ENOSPC;return -1;}break;}
    case IB_USER_VERBS_CMD_POLL_CQ:{
        const struct ibv_poll_cq *q=buffer;struct ib_uverbs_poll_cq_resp *r=(void *)(uintptr_t)q->response;
        CHECK(q->cq_handle==41 && q->ne==2 && !fail_post);memset(r,0,h->out_words*4);r->count=2;
        for(unsigned int i=0;i<2;i++){
            r->wc[i].wr_id=segmented_receive_expected[i].wr_id;r->wc[i].qp_num=2;
            r->wc[i].opcode=IBV_WC_RECV;r->wc[i].byte_len=segmented_receive_bytes;
            if(i){r->wc[i].wc_flags=IBV_WC_WITH_IMM;r->wc[i].ex.imm_data=htonl(segmented_receive_notification);}
        }
        segmented_receive_polls++;break;}
    case IB_USER_VERBS_CMD_DEREG_MR:{
        const struct ibv_dereg_mr *q=buffer;CHECK(q->mr_handle==22);segmented_receive_deregistrations++;break;}
    default:CHECK(false);
    }
    return bytes;
}

static void exercise_segmented_receive(struct ibv_pd *pd,struct ibv_qp *qp,struct ibv_cq *rq)
{
    const unsigned int capacities[]={4097,8194,1048576},values[]={0,0x89abcdefU,0xffffffffU};
    struct ibv_mr *mr;struct ibv_recv_wr *bad;struct ibv_wc wc[2];
    segmented_receive_boundary=true;
    mr=ibv_reg_mr_iova(pd,(void *)0x10000,1048576,VA,IBV_ACCESS_LOCAL_WRITE);
    CHECK(mr && mr->handle==22 && mr->lkey==0x91234567 && mr->rkey==0xa2345678);
    for(unsigned int n=0;n<3;n++){
        struct ibv_sge sg={.addr=VA+(n==2 ? 0:0x210),.length=capacities[n],.lkey=mr->lkey};
        for(unsigned int i=0;i<2;i++)segmented_receive_expected[i]=(struct ibv_recv_wr){
            .wr_id=UINT64_C(0xfedcba9871000000)+n*2+i,.sg_list=&sg,.num_sge=1};
        segmented_receive_expected[0].next=&segmented_receive_expected[1];
        segmented_receive_bytes=capacities[n]-1;segmented_receive_notification=values[n];
        bad=NULL;fail_post=true;
        CHECK(ibv_post_recv(qp,segmented_receive_expected,&bad)==ENOSPC && bad==segmented_receive_expected+1);
        fail_post=false;bad=NULL;CHECK(!ibv_post_recv(qp,segmented_receive_expected,&bad) && !bad);
        memset(wc,0xa5,sizeof(wc));CHECK(ibv_poll_cq(rq,2,wc)==2);
        for(unsigned int i=0;i<2;i++)CHECK(wc[i].wr_id==segmented_receive_expected[i].wr_id &&
            wc[i].qp_num==2 && wc[i].opcode==IBV_WC_RECV && wc[i].byte_len==capacities[n]-1 &&
            wc[i].status==IBV_WC_SUCCESS && wc[i].wc_flags==(i ? IBV_WC_WITH_IMM:0) &&
            wc[i].imm_data==(i ? htonl(values[n]):0));
    }
    CHECK(!ibv_dereg_mr(mr));segmented_receive_boundary=false;
    CHECK(segmented_receive_posts==6 && segmented_receive_polls==3 && segmented_receive_registrations==1 && segmented_receive_deregistrations==1);
    puts("PROVIDER_SEGMENTED_RECEIVE_RESULT {\"pass_test\":true,\"RECV_capacities\":[4097,8194,1048576],\"WC_actual_bytes\":[4096,8193,1048575],\"two_WR_chain\":true,\"full64bit_addresses_keys_lengths\":true,\"exact_second_bad_WR\":true,\"distinct_registered_MR_handle_and_keys\":true,\"posts_including_errors\":6,\"polls\":3,\"network_order_Immediate\":true,\"actual_public_API_and_serializer\":true,\"kernel_syscall_and_WC_boundary_modeled\":true,\"actual_Linux_runtime\":false,\"hardware_verified\":false}");
}
