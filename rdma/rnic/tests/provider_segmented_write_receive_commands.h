/* SPDX-License-Identifier: BSD-2-Clause-Views */
/* Actual libibverbs/private provider marshalling. Syscalls/WC replies only
 * are models; no native/kernel/physical proof is supplied by this fixture. */
static bool write_receive_boundary;
static unsigned int write_receive_posts,write_receive_polls,write_receive_bytes;
static uint32_t write_receive_immediate;
static struct ibv_recv_wr write_receive_expected[2];

static ssize_t write_receive_write(int fd,const void *buffer,size_t bytes)
{
    const struct ib_uverbs_cmd_hdr *h=buffer;
    if(fd!=MODEL_FD)return legacy_provider_write(fd,buffer,bytes);
    CHECK(h->in_words*4==bytes && h->command<64);commands[h->command]++;
    switch(h->command){
    case IB_USER_VERBS_CMD_POST_RECV:{
        const struct ibv_post_recv *q=buffer;const struct ib_uverbs_recv_wr *w=(const void *)(q+1);
        const struct ibv_sge *s=(const void *)(w+2);struct ib_uverbs_post_recv_resp *r=(void *)(uintptr_t)q->response;
        CHECK(q->qp_handle==44 && q->wr_count==2 && q->sge_count==2 && q->wqe_size==sizeof(*w) &&
            bytes==sizeof(*q)+2*sizeof(*w)+2*sizeof(*s));
        for(unsigned int i=0;i<2;i++)CHECK(w[i].wr_id==write_receive_expected[i].wr_id && w[i].num_sge==1 &&
            !s[i].addr && !s[i].length && !s[i].lkey);
        write_receive_posts++;r->bad_wr=fail_post ? 2:0;
        if(fail_post){errno=ENOSPC;return -1;}break;}
    case IB_USER_VERBS_CMD_POLL_CQ:{
        const struct ibv_poll_cq *q=buffer;struct ib_uverbs_poll_cq_resp *r=(void *)(uintptr_t)q->response;
        CHECK(q->cq_handle==41 && q->ne==2 && !fail_post);memset(r,0,h->out_words*4);r->count=2;
        for(unsigned int i=0;i<2;i++){
            r->wc[i].wr_id=write_receive_expected[i].wr_id;r->wc[i].qp_num=2;
            r->wc[i].opcode=IBV_WC_RECV_RDMA_WITH_IMM;r->wc[i].byte_len=write_receive_bytes;
            r->wc[i].wc_flags=IBV_WC_WITH_IMM;r->wc[i].ex.imm_data=htonl(write_receive_immediate);
        }
        write_receive_polls++;break;}
    default:CHECK(false);
    }
    return bytes;
}

static void exercise_write_receive(struct ibv_qp *qp,struct ibv_cq *rq)
{
    const unsigned int lengths[]={0,1,4096,4097,8193,1048576};
    struct ibv_sge sg={.addr=0,.length=0,.lkey=0};struct ibv_recv_wr *bad;struct ibv_wc wc[2];
    write_receive_boundary=true;
    for(unsigned int n=0;n<6;n++){
        for(unsigned int i=0;i<2;i++)write_receive_expected[i]=(struct ibv_recv_wr){
            .wr_id=UINT64_C(0xfedcba9812000000)+n*2+i,.sg_list=&sg,.num_sge=1};
        write_receive_expected[0].next=&write_receive_expected[1];
        write_receive_bytes=lengths[n];write_receive_immediate=n%3==0 ? 0:n%3==1 ? 0x89abcdefU:0xffffffffU;
        bad=NULL;fail_post=true;
        CHECK(ibv_post_recv(qp,write_receive_expected,&bad)==ENOSPC && bad==write_receive_expected+1);
        fail_post=false;bad=NULL;CHECK(!ibv_post_recv(qp,write_receive_expected,&bad) && !bad);
        memset(wc,0xa5,sizeof(wc));CHECK(ibv_poll_cq(rq,2,wc)==2);
        for(unsigned int i=0;i<2;i++)CHECK(wc[i].wr_id==write_receive_expected[i].wr_id && wc[i].qp_num==2 &&
            wc[i].status==IBV_WC_SUCCESS && wc[i].opcode==IBV_WC_RECV_RDMA_WITH_IMM &&
            wc[i].byte_len==lengths[n] && wc[i].wc_flags==IBV_WC_WITH_IMM &&
            ntohl(wc[i].imm_data)==write_receive_immediate);
    }
    CHECK(write_receive_posts==12 && write_receive_polls==6);write_receive_boundary=false;
    puts("PROVIDER_WRITE_RECEIVE_RESULT {\"pass_test\":true,\"zero_capacity_RQ\":true,\"WC_actual_bytes\":[0,1,4096,4097,8193,1048576],\"network_order_Immediate\":true,\"posts_including_errors\":12,\"polls\":6,\"kernel_native_hardware_modeled\":true}");
}
