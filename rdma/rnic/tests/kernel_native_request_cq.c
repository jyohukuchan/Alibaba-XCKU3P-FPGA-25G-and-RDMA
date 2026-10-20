/* SPDX-License-Identifier: BSD-2-Clause-Views */
/* Actual kernel posting/CQ/MR code consumes unedited generated-core native
 * requester CQ snapshots. Linux, pins/DMA/MMIO and teardown are models. */
#define AS02_CQ_CASES_LIBRARY
#include "kernel_cq_cases.c"

static void compare_native_request(const char *path)
{
    FILE *f=fopen(path,"r");char text[129];u8 expected[64],actual[64];
    unsigned int i,b;
    CHECK(f && fscanf(f,"%128s",text)==1);fclose(f);CHECK(strlen(text)==128);
    for(i=0;i<64;i++){
        CHECK(sscanf(text+(63-i)*2,"%2x",&b)==1);expected[i]=b;
    }
    CHECK(model.observed_count==1 && !as02_wqe_encode(actual,&model.observed[0]));
    CHECK(!memcmp(expected,actual,sizeof(expected)));
}

int main(int argc,char **argv)
{
    struct ib_cq_init_attr attr={.cqe=1};struct as02_sq_handle owner;
    struct ib_sge sg;struct ib_rdma_wr wr;struct ib_wc wc;unsigned int op;
    (void)setup_cq;(void)cleanup_cq;(void)check_wc;
    CHECK(argc==4);op=strtoul(argv[3],NULL,0);CHECK(op>=1 && op<=3);
    receive_mode=true; /* Actual CQC message feature/25-word ABI, NOT RECV. */
    read_event(argv[1],&records[0]);
    CHECK(records[0].cookie==0xfedcba9889abcdefULL && !records[0].received_bytes);
    setup();CHECK(!as02_cq_router_init(&router));
    completion_queue.ibcq.device=&ibdev;completion_queue.ibcq.comp_handler=completed_irq;
    CHECK(!as02_cq_create(&completion_queue.ibcq,&attr,NULL));
    CHECK(!as02_cq_hw_init(&completion_hw,&sq,completion_mmio,sizeof(completion_mmio)));
    CHECK(!as02_cq_attach_hardware(&completion_queue,&completion_hw));
    actual_qp=(struct ib_qp){.device=&ibdev,.send_cq=&completion_queue.ibcq,
        .recv_cq=&completion_queue.ibcq,.qp_num=2};
    CHECK(!as02_cq_router_bind(&router,&completion_queue,&actual_qp));
    hw.commit_cqe=as02_cq_publish;hw.cq_context=&router;
    sq.next_cookie=records[0].cookie-1;CHECK(!as02_sq_create(&sq,2,17,EPOCH,1,&owner));
    CHECK(owner.cookie==records[0].cookie);
    sg=(struct ib_sge){.addr=VA+0x210,.length=65,.lkey=mr->layout.key};
    wr=(struct ib_rdma_wr){.wr={.wr_id=0xf123456789abc001ULL,.sg_list=&sg,.num_sge=1,
        .opcode=op==1 ? IB_WR_RDMA_WRITE:op==2 ? IB_WR_RDMA_READ:IB_WR_SEND,
        .send_flags=IB_SEND_SIGNALED},.remote_addr=0xf123456789abc001ULL,.rkey=0};
    CHECK(!as02_cq_req_notify(&completion_queue.ibcq,IB_CQ_NEXT_COMP));
    CHECK(!as02_sq_post(&sq,&owner,&wr.wr));compare_native_request(argv[2]);
    CHECK(refcount_read(&mr->work_refs)==2);
    load_event(0);cm_run_work(&completion_hw.poll_work);irq_work_sync(&completion_queue.notify);
    CHECK(last_ack==1 && !visible && completion_queue.pending==1 && notifications==1);
    CHECK(refcount_read(&mr->work_refs)==1);
    CHECK(as02_cq_poll(&completion_queue.ibcq,1,&wc)==1 &&
        wc.wr_id==wr.wr.wr_id && wc.qp==&actual_qp && wc.status==IB_WC_SUCCESS &&
        wc.opcode==(op==1 ? IB_WC_RDMA_WRITE:op==2 ? IB_WC_RDMA_READ:IB_WC_SEND) &&
        wc.byte_len==(op==2 ? 65:0));
    CHECK(!as02_cq_poll(&completion_queue.ibcq,1,&wc));
    CHECK(!as02_sq_close(&sq,&owner));CHECK(as02_cq_hw_detach(&completion_hw)==-EBUSY);
    CHECK(!as02_cq_router_unbind(&router,&actual_qp));
    CHECK(!completion_queue.queue_refs && !as02_cq_destroy(&completion_queue.ibcq,NULL));
    CHECK(!as02_cq_hw_detach(&completion_hw));CHECK(!sq.completion_clients);cleanup();
    printf("KERNEL_NATIVE_REQUEST_CQ_RESULT {\"pass_test\":true,\"opcode\":%u,\"native_CQ_snapshots_unedited\":true,\"software_native_WQE_bytes_identical\":true,\"actual_CQ_and_MR_release\":true,\"hardware_verified\":false}\n",op);
    return 0;
}
