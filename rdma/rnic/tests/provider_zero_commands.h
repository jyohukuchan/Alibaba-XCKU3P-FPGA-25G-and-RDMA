/* SPDX-License-Identifier: BSD-2-Clause-Views */
/* Only syscall replies are modeled. Public libibverbs/provider serialization
 * is real. Empty requests must NOT dereference an unused sg_list pointer;
 * one zero SGE's unused addr/key remain exact standard ABI fields. */
static bool zero_boundary;
static unsigned int zero_n,zero_opcode,zero_sends,zero_receives,zero_polls;
static uint64_t zero_id;
static enum ibv_wc_opcode zero_wc_opcode;
static uint32_t zero_imm;

static ssize_t zero_write(int fd,const void *buffer,size_t bytes)
{
    const struct ib_uverbs_cmd_hdr *h=buffer;
    if(fd!=MODEL_FD)return legacy_provider_write(fd,buffer,bytes);
    CHECK(h->in_words*4==bytes && h->command<64);commands[h->command]++;
    if(h->command==IB_USER_VERBS_CMD_POST_SEND){
        const struct ibv_post_send *q=buffer;
        const struct ib_uverbs_send_wr *w=(const void *)(q+1);
        const struct ibv_sge *s=(const void *)(w+1);
        struct ib_uverbs_post_send_resp *r=(void *)(uintptr_t)q->response;
        CHECK(q->qp_handle==44 && q->wr_count==1 && q->sge_count==zero_n && q->wqe_size==sizeof(*w) &&
            bytes==sizeof(*q)+sizeof(*w)+zero_n*sizeof(*s) && w->wr_id==zero_id &&
            w->opcode==zero_opcode && w->num_sge==zero_n && w->send_flags==IBV_SEND_SIGNALED);
        if(zero_opcode!=IBV_WR_SEND && zero_opcode!=IBV_WR_SEND_WITH_IMM)
            CHECK(w->wr.rdma.remote_addr==UINT64_MAX && w->wr.rdma.rkey==0xfedcba98U);
        if(zero_opcode==IBV_WR_SEND_WITH_IMM || zero_opcode==IBV_WR_RDMA_WRITE_WITH_IMM)
            CHECK(w->ex.imm_data==htonl(zero_imm));
        if(zero_n)CHECK(s->addr==UINT64_MAX && !s->length && s->lkey==UINT32_MAX);
        zero_sends++;r->bad_wr=fail_post ? 1:0;
    }else if(h->command==IB_USER_VERBS_CMD_POST_RECV){
        const struct ibv_post_recv *q=buffer;
        const struct ib_uverbs_recv_wr *w=(const void *)(q+1);
        const struct ibv_sge *s=(const void *)(w+1);
        struct ib_uverbs_post_recv_resp *r=(void *)(uintptr_t)q->response;
        CHECK(q->qp_handle==44 && q->wr_count==1 && q->sge_count==zero_n && q->wqe_size==sizeof(*w) &&
            bytes==sizeof(*q)+sizeof(*w)+zero_n*sizeof(*s) && w->wr_id==zero_id && w->num_sge==zero_n);
        if(zero_n)CHECK(s->addr==UINT64_MAX && !s->length && s->lkey==UINT32_MAX);
        zero_receives++;r->bad_wr=fail_post ? 1:0;
    }else{
        const struct ibv_poll_cq *q=buffer;
        struct ib_uverbs_poll_cq_resp *r=(void *)(uintptr_t)q->response;
        CHECK(h->command==IB_USER_VERBS_CMD_POLL_CQ && q->cq_handle==40 && q->ne==1 && !fail_post);
        memset(r,0,h->out_words*4);r->count=1;r->wc[0].wr_id=zero_id;
        r->wc[0].qp_num=2;r->wc[0].opcode=zero_wc_opcode;zero_polls++;
    }
    if(fail_post){errno=ENOSPC;return -1;}return bytes;
}

static void exercise_zero(struct ibv_qp *qp,struct ibv_cq *cq)
{
    const enum ibv_wr_opcode ops[]={IBV_WR_RDMA_WRITE,IBV_WR_RDMA_READ,IBV_WR_SEND,
        IBV_WR_SEND_WITH_IMM,IBV_WR_RDMA_WRITE_WITH_IMM};
    struct ibv_sge sg={.addr=UINT64_MAX,.length=0,.lkey=UINT32_MAX};
    struct ibv_wc wc;
    zero_boundary=true;
    for(zero_n=0;zero_n<2;zero_n++){
        struct ibv_sge *unused=zero_n ? &sg:(void *)(uintptr_t)1;
        for(unsigned int op=0;op<5;op++){
            struct ibv_send_wr *bad=NULL,w={.wr_id=UINT64_C(0xf123456780000000)+zero_n*16+op,
                .sg_list=unused,.num_sge=(int)zero_n,.opcode=ops[op],.send_flags=IBV_SEND_SIGNALED,
                .imm_data=htonl(0x89abcdefU),.wr.rdma={.remote_addr=UINT64_MAX,.rkey=0xfedcba98U}};
            zero_id=w.wr_id;zero_opcode=ops[op];zero_imm=0x89abcdef;
            zero_wc_opcode=ops[op]==IBV_WR_RDMA_READ ? IBV_WC_RDMA_READ:
                ops[op]==IBV_WR_SEND || ops[op]==IBV_WR_SEND_WITH_IMM ? IBV_WC_SEND:IBV_WC_RDMA_WRITE;
            fail_post=true;CHECK(ibv_post_send(qp,&w,&bad)==ENOSPC && bad==&w);
            fail_post=false;bad=NULL;CHECK(!ibv_post_send(qp,&w,&bad) && !bad);
            memset(&wc,0xa5,sizeof(wc));CHECK(ibv_poll_cq(cq,1,&wc)==1 && wc.wr_id==zero_id &&
                wc.qp_num==2 && wc.opcode==zero_wc_opcode && !wc.byte_len && !wc.status && !wc.wc_flags && !wc.imm_data);
        }
        struct ibv_recv_wr *bad=NULL,w={.wr_id=UINT64_C(0xf123456780000100)+zero_n,.sg_list=unused,.num_sge=(int)zero_n};
        zero_id=w.wr_id;zero_wc_opcode=IBV_WC_RECV;
        fail_post=true;CHECK(ibv_post_recv(qp,&w,&bad)==ENOSPC && bad==&w);
        fail_post=false;bad=NULL;CHECK(!ibv_post_recv(qp,&w,&bad) && !bad);
        memset(&wc,0xa5,sizeof(wc));CHECK(ibv_poll_cq(cq,1,&wc)==1 && wc.wr_id==zero_id &&
            wc.qp_num==2 && wc.opcode==IBV_WC_RECV && !wc.byte_len && !wc.status && !wc.wc_flags && !wc.imm_data);
    }
    zero_boundary=false;
    CHECK(zero_sends==20 && zero_receives==4 && zero_polls==12);
    puts("PROVIDER_ZERO_RESULT {\"pass_test\":true,\"zero_operations\":6,\"num_sge_zero_and_one_zero_SGE\":true,\"unused_pointer_not_dereferenced\":true,\"exact_remote_Immediate_fields\":true,\"exact_bad_WR\":true,\"zero_WC_bytes\":true,\"posts_including_errors\":24,\"polls\":12,\"actual_public_API_and_serializer\":true,\"kernel_syscall_boundary_modeled\":true,\"hardware_verified\":false}");
}
