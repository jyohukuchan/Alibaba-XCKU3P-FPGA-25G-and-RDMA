/* SPDX-License-Identifier: BSD-2-Clause-Views */
/* Consume UNEDITED CQ snapshots from whole actual-generated-HLS/native RTL.
 * Linux primitives, page pins, DMA, MMIO and controller teardown are modeled.
 * Software posting encodes the exact same WQE bytes as the native run.
 */
#define AS02_CQ_CASES_LIBRARY
#include "kernel_cq_cases.c"

static void compare_native_wqe(const char *path,unsigned int n)
{
    FILE *f=fopen(path,"r");char text[129];u8 expected[64],actual[64];
    unsigned int i,b;
    CHECK(f);
    for(i=0;i<=n;i++)CHECK(fscanf(f,"%128s",text)==1);
    fclose(f);CHECK(strlen(text)==128);
    for(i=0;i<64;i++){
        CHECK(sscanf(text+(63-i)*2,"%2x",&b)==1);expected[i]=b;
    }
    CHECK(model.observed_count==n+1 && !as02_wqe_encode(actual,&model.observed[n]));
    CHECK(!memcmp(expected,actual,sizeof(expected)));
}

int main(int argc,char **argv)
{
    struct ib_cq_init_attr attr={.cqe=1};
    struct as02_sq_handle owner;
    struct ib_sge sg;
    struct ib_recv_wr wr;
    struct ib_wc wc;
    (void)setup_cq;
    CHECK(argc==4);receive_mode=true;separate_receive_cq=true;
    read_event(argv[1],&records[0]);read_event(argv[2],&records[1]);
    CHECK(records[0].cookie==0xfedcba9889abcdefULL && records[1].cookie==records[0].cookie);
    setup();CHECK(!as02_cq_router_init(&router));
    completion_queue.ibcq.device=&ibdev;receive_queue.ibcq.device=&ibdev;
    receive_queue.ibcq.comp_handler=completed_irq;
    CHECK(!as02_cq_create(&completion_queue.ibcq,&attr,NULL));
    CHECK(!as02_cq_create(&receive_queue.ibcq,&attr,NULL));
    CHECK(!as02_cq_hw_init(&completion_hw,&sq,completion_mmio,sizeof(completion_mmio)));
    CHECK(!as02_cq_attach_hardware(&completion_queue,&completion_hw));
    CHECK(!as02_cq_attach_hardware(&receive_queue,&completion_hw));
    actual_qp=(struct ib_qp){.device=&ibdev,.send_cq=&completion_queue.ibcq,
        .recv_cq=&receive_queue.ibcq,.qp_num=2};
    CHECK(!as02_cq_router_bind(&router,&completion_queue,&actual_qp));
    hw.commit_cqe=as02_cq_publish;hw.cq_context=&router;
    /* Privileged owner allocation matches the native controller's complete
     * nonwrapping cookie/epoch/QPN/PD and depth2, not a narrowed WR-id alias. */
    sq.next_cookie=records[0].cookie-1;
    CHECK(!as02_sq_create(&sq,2,17,EPOCH,1,&owner));
    CHECK(owner.cookie==records[0].cookie);
    CHECK(!as02_sq_set_receive_limits(&sq,&owner,1,1));
    sg=(struct ib_sge){.addr=VA+0x210,.length=128,.lkey=mr->layout.key};
    wr=(struct ib_recv_wr){.wr_id=0xf123456789abc001ULL,.sg_list=&sg,.num_sge=1};
    CHECK(!as02_cq_req_notify(&receive_queue.ibcq,IB_CQ_NEXT_COMP));
    CHECK(!as02_sq_post_recv(&sq,&owner,&wr));compare_native_wqe(argv[3],0);
    CHECK(refcount_read(&mr->work_refs)==2);
    load_event(0);cm_run_work(&completion_hw.poll_work);irq_work_sync(&receive_queue.notify);
    CHECK(last_ack==1 && !visible && !completion_queue.pending && receive_queue.pending==1 && notifications==1);
    CHECK(refcount_read(&mr->work_refs)==1);
    wr.wr_id++;
    CHECK(!as02_sq_post_recv(&sq,&owner,&wr));compare_native_wqe(argv[3],1);
    load_event(1);
    CHECK(as02_cq_hw_poll(&completion_hw)==-ENOSPC && last_ack==1 && visible && refcount_read(&mr->work_refs)==2);
    CHECK(as02_cq_poll(&receive_queue.ibcq,1,&wc)==1);check_wc(&wc,1);
    CHECK(last_ack==1 && visible && refcount_read(&mr->work_refs)==2);
    CHECK(as02_cq_poll(&receive_queue.ibcq,1,&wc)==1);check_wc(&wc,2);
    CHECK(last_ack==2 && !visible && !completion_queue.pending && refcount_read(&mr->work_refs)==1);
    cleanup_cq(&owner);
    puts("KERNEL_NATIVE_RECV_CQ_RESULT {\"pass_test\":true,\"native_CQ_snapshots_unedited\":true,\"software_native_WQE_bytes_identical\":true,\"completed_receives\":2,\"capacity\":128,\"received_bytes\":65,\"distinct_recv_cq\":true,\"quota_reused\":true,\"CQ_full_retains_second_MR_reference\":true,\"hardware_verified\":false}");
    return 0;
}
