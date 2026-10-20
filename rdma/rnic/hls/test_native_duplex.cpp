// SPDX-License-Identifier: BSD-2-Clause-Views
// One actual requester/RX/MSN/state/retransmission engine. Parsed ingress,
// connection lookup and memory data are models, not a physical native RNIC.
#define main preceding_request_test_main
#include "test_native_request_retire.cpp"
#undef main

int main() {
    static_assert(MAX_QPS==8 && META_TABLE_SIZE==2000,"capacities changed");
    Harness<171> h;h.init();
    hls::stream<as02RecvDone> receives;
    ap_uint<1> recv_join_fault=0;
    auto tick=[&]() {
        // These are the same stream connection as the complete real top.
        if(!h.rx_ack_events.empty())h.ack_events.write(h.rx_ack_events.read());
        h.tick();
        as02_recv_retire_join<171>(h.recv_data,h.recv_ack,h.recv_state_req,
            h.recv_state_rsp,receives,recv_join_fault);
    };
    auto ticks=[&](unsigned n){while(n--)tick();};
    const unsigned ops[]={3,2,1};
    for(unsigned k=0;k<3;k++) {
        auto request=owner(k+1,ops[k]);h.post(request);
        auto request_header=h.headers.read();
        assert(request_header.getOpCode()==as02_req_opcode(request));
        auto request_psn=request_header.getPsn();
        if(ops[k]!=2){
            assert(h.source_cmd.size()==1);auto c=h.source_cmd.read();
            assert(c.origin==2 && c.addr==0xba9876543210ULL && c.len==65);
        }
        // While our request is genuinely unacknowledged, accept the peer's
        // independent SEND on the SAME QPN/state/MSN engine, not another core.
        as02RecvOwner receive;receive.context=owner(k+11,3);
        receive.context(339,324)=4;receive.context(307,276)=128;
        receive.length=65;receive.psn=0x987654+k;
        assert(as02_recv_owner_valid(receive));h.recv_owners.write(receive);
        h.rx_bth.write(ibhMeta(RC_SEND_ONLY,0xffff,2,receive.psn,true));
        h.rx_exh.write(exhMeta(false));ExHeader<512> ex;ex.clear();h.rx_headers.write(ex);
        h.udp.write(92);h.dest.write(196);
        net_axis<512> data;data.data=ap_uint<512>(0x1122334455667788ULL);
        data.keep=~ap_uint<64>(0);data.last=0;h.raw.write(data);
        data.data=0xa5;data.keep=15;data.last=1;h.raw.write(data);
        ticks(300);
        assert(h.done.empty() && receives.size()==1 && !recv_join_fault);
        auto r=receives.read();assert(as02_recv_same(r.proof,as02RecvProof{receive,ap_uint<24>(k+1)}) && !r.error);
        assert(h.destination_cmd.size()==1);auto c=h.destination_cmd.read();
        assert(c.origin==1 && c.addr==0 && c.len==68 && !c.host && c.pid==2);
        assert(h.memory.size()==2 && !h.memory.read().last && h.memory.read().last);
        assert(h.headers.size()==1);auto ack=h.headers.read();
        assert(ack.getOpCode()==RC_ACK && ack.getPsn()==receive.psn);
        // Only now supply the genuine peer response to the outstanding local
        // request. Incoming SEND did not consume or overwrite its owner.
        h.peer(request_psn,ops[k]==2);ticks(300);
        assert(h.done.size()==1);auto done=h.done.read();
        assert(done.context==request && done.psn==request_psn && !done.error);
        if(ops[k]==2){
            assert(h.destination_cmd.size()==1);c=h.destination_cmd.read();
            assert(c.origin==2 && c.addr==0xba9876543210ULL && c.len==68 && c.host);
            assert(h.memory.size()==2);h.memory.read();h.memory.read();
        }
        assert(!h.af && !h.rf && !h.ef && !h.tf && !h.ff && !h.jf && !h.psn_drops);
    }
    // Real command producer arbitration keeps provenance attached even when
    // both memory-read sources offer simultaneously. No current-role mux.
    h.remote_mem.write(memCmdInternal(RC_RDMA_READ_RESP_ONLY,2,0x1234,65,1));
    h.local_mem.write(memCmdInternal(RC_RDMA_WRITE_ONLY,2,0x5678,65,1));
    ticks(8);assert(h.source_cmd.size()==2);
    auto remote=h.source_cmd.read(),local=h.source_cmd.read();
    assert(remote.origin==1 && remote.addr==0x1234 && local.origin==2 && local.addr==0x5678);
    std::cout<<"NATIVE_DUPLEX_HLS {\"pass_test\":true,\"same_core_bidirectional_pending_requests\":3,"
        "\"actual_memory_command_provenance\":true,\"request_receive_receipts\":true,"
        "\"physical_native_or_kernel_verified\":false}"<<std::endl;
    return 0;
}
