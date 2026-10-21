/* SPDX-License-Identifier: BSD-2-Clause-Views */
/* Genuine public API/provider/standard marshalling; ONLY fake-fd syscalls
 * and WC replies are models. This does not execute Linux callbacks or DMA.
 * The new MR has a distinct handle/key from the inherited live small MR. */
static bool segmented_boundary;
static unsigned int segmented_posts,segmented_polls,segmented_registrations,segmented_deregistrations;
static struct ibv_send_wr segmented_expected[2];

static ssize_t segmented_write(int fd,const void *buffer,size_t bytes)
{
    const struct ib_uverbs_cmd_hdr *h=buffer;
    if(fd!=MODEL_FD)return legacy_provider_write(fd,buffer,bytes);
    CHECK(h->in_words*4==bytes && h->command<64);commands[h->command]++;
    switch(h->command){
    case IB_USER_VERBS_CMD_REG_MR:{
        const struct ibv_reg_mr *q=buffer;struct ib_uverbs_reg_mr_resp *r=(void *)(uintptr_t)q->response;
        CHECK(bytes==sizeof(*q) && q->pd_handle==17 && q->start==0x10000 &&
            q->length==1048576 && q->hca_va==VA && q->access_flags==15);
        r->mr_handle=19;r->lkey=0xa1234567;r->rkey=0xb1234567;segmented_registrations++;break;}
    case IB_USER_VERBS_CMD_POST_SEND:{
        const struct ibv_post_send *q=buffer;
        const struct ib_uverbs_send_wr *w=(const void *)(q+1);
        const struct ibv_sge *s=(const void *)(w+2);
        struct ib_uverbs_post_send_resp *r=(void *)(uintptr_t)q->response;
        CHECK(q->qp_handle==44 && q->wr_count==2 && q->sge_count==2 && q->wqe_size==sizeof(*w) &&
            bytes==sizeof(*q)+2*sizeof(*w)+2*sizeof(*s));
        for(unsigned int i=0;i<2;i++){
            const struct ibv_send_wr *e=&segmented_expected[i];
            CHECK(w[i].wr_id==e->wr_id && w[i].opcode==(uint32_t)e->opcode &&
                w[i].num_sge==1 && w[i].send_flags==IBV_SEND_SIGNALED &&
                s[i].addr==e->sg_list->addr && s[i].length==e->sg_list->length && s[i].lkey==0xa1234567);
            if(e->opcode==IBV_WR_RDMA_WRITE)CHECK(w[i].wr.rdma.remote_addr==e->wr.rdma.remote_addr &&
                w[i].wr.rdma.rkey==e->wr.rdma.rkey);
        }
        segmented_posts++;r->bad_wr=fail_post ? 2:0;
        if(fail_post){errno=ENOSPC;return -1;}break;}
    case IB_USER_VERBS_CMD_POLL_CQ:{
        const struct ibv_poll_cq *q=buffer;struct ib_uverbs_poll_cq_resp *r=(void *)(uintptr_t)q->response;
        CHECK(q->cq_handle==40 && q->ne==2 && !fail_post);memset(r,0,h->out_words*4);r->count=2;
        for(unsigned int i=0;i<2;i++){
            r->wc[i].wr_id=segmented_expected[i].wr_id;r->wc[i].qp_num=2;
            r->wc[i].opcode=i ? IBV_WC_SEND:IBV_WC_RDMA_WRITE;
        }
        segmented_polls++;break;}
    case IB_USER_VERBS_CMD_DEREG_MR:{
        const struct ibv_dereg_mr *q=buffer;CHECK(q->mr_handle==19);segmented_deregistrations++;break;}
    default:CHECK(false);
    }
    return bytes;
}

static void exercise_segmented(struct ibv_pd *pd,struct ibv_qp *qp,struct ibv_cq *cq)
{
    const unsigned int lengths[]={4097,8193,1048576};
    struct ibv_mr *mr;struct ibv_send_wr *bad;struct ibv_wc wc[2];
    segmented_boundary=true;
    mr=ibv_reg_mr_iova(pd,(void *)0x10000,1048576,VA,15);
    CHECK(mr && mr->handle==19 && mr->lkey==0xa1234567 && mr->rkey==0xb1234567);
    for(unsigned int n=0;n<3;n++){
        struct ibv_sge sg={.addr=VA+(n==2 ? 0:0x210),.length=lengths[n],.lkey=mr->lkey};
        for(unsigned int i=0;i<2;i++)segmented_expected[i]=(struct ibv_send_wr){
            .wr_id=UINT64_C(0xfedcba9870000000)+n*2+i,.sg_list=&sg,.num_sge=1,
            .opcode=i ? IBV_WR_SEND:IBV_WR_RDMA_WRITE,.send_flags=IBV_SEND_SIGNALED};
        segmented_expected[0].wr.rdma.remote_addr=UINT64_C(0xe23456789abcdef0);
        segmented_expected[0].wr.rdma.rkey=0x92345678;
        segmented_expected[0].next=&segmented_expected[1];
        bad=NULL;fail_post=true;
        CHECK(ibv_post_send(qp,segmented_expected,&bad)==ENOSPC && bad==segmented_expected+1);
        fail_post=false;bad=NULL;CHECK(!ibv_post_send(qp,segmented_expected,&bad) && !bad);
        memset(wc,0xa5,sizeof(wc));CHECK(ibv_poll_cq(cq,2,wc)==2);
        for(unsigned int i=0;i<2;i++)CHECK(wc[i].wr_id==segmented_expected[i].wr_id &&
            wc[i].qp_num==2 && wc[i].opcode==(i ? IBV_WC_SEND:IBV_WC_RDMA_WRITE) &&
            !wc[i].byte_len && wc[i].status==IBV_WC_SUCCESS && !wc[i].wc_flags && !wc[i].imm_data);
    }
    CHECK(!ibv_dereg_mr(mr));segmented_boundary=false;
    CHECK(segmented_posts==6 && segmented_polls==3 && segmented_registrations==1 && segmented_deregistrations==1);
    puts("PROVIDER_SEGMENTED_RESULT {\"pass_test\":true,\"WRITE_SEND_lengths\":[4097,8193,1048576],\"two_WR_chain\":true,\"full64bit_addresses_keys_lengths\":true,\"exact_second_bad_WR\":true,\"distinct_registered_MR_handle_and_keys\":true,\"posts_including_errors\":6,\"polls\":3,\"send_WC_zero_bytes\":true,\"actual_public_API_and_serializer\":true,\"kernel_syscall_and_WC_boundary_modeled\":true,\"actual_Linux_runtime\":false,\"hardware_verified\":false}");
}
