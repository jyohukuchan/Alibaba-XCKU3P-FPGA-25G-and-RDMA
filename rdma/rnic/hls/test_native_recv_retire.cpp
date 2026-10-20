// SPDX-License-Identifier: BSD-2-Clause-Views
// Actual EXH SEND, payload EOF, ACK/MSN and SAME PSN consumer. Packet/native
// admission and RX-IBH producer input are models here; whole RTL is separate.
#include <cassert>
#include <iostream>
#include "ib_transport_protocol/ib_transport_protocol.cpp"

template<int I> struct Harness {
    hls::stream<ibhMeta> rx_meta,tx_ibh;
    hls::stream<ap_uint<16>> udp,conn,msn_query,length;
    hls::stream<dmaState> msn_rx;
    hls::stream<txMsnRsp> msn_tx;
    hls::stream<ifMsnReq> msn_init;
    hls::stream<rxMsnReq> msn_update;
    hls::stream<retransmission> retrans;
    hls::stream<retransRdInit> read_init;
    hls::stream<ExHeader<512>> ex_header;
    hls::stream<memCmd> commands;
    hls::stream<readRequest> read_requests;
    hls::stream<ackEvent> ack_source,ibh_ack,merged;
    hls::stream<as02RnrEvent> rnr;
    hls::stream<pkgSplit> split;
    hls::stream<pkgShift> shift;
    hls::stream<as02RecvOwner> owners;
    hls::stream<net_axis<512>> aeth,reth,raw,memory,ack_headers;
    hls::stream<as02RecvProof> data_done,ack_done;
    hls::stream<event> read_events,app_events,ack_meta;
    hls::stream<txPacketInfo> info;
    hls::stream<ap_uint<24>> timer,fence_req;
    hls::stream<ap_uint<56>> fence_rsp;
    hls::stream<as02RecvDone> done;
    hls::stream<rxStateReq> rx_state;
    hls::stream<txStateReq> tx_state;
    hls::stream<ifStateReq> qp_state;
    hls::stream<rxStateRsp> rx_rsp;
    hls::stream<stateTableEntry> tx_rsp,qp_rsp;
    ap_uint<1> bind_fault=0,join_fault=0,rnr_fault=0;
    void tick(bool data=true,bool ack=true,bool state=true) {
        rx_exh_fsm<512,I>(rx_meta,udp,msn_rx,retrans,read_init,ex_header,commands,
            read_requests,msn_update,ack_source,split,shift,owners,bind_fault);
        if(data)merge_rx_pkgs<512,I>(shift,aeth,reth,raw,memory,data_done);
        as02_native_rnr_merger<I>(ack_source,ibh_ack,rnr,merged,rnr_fault);
        meta_merger<I>(merged,read_events,app_events,conn,tx_ibh,ack_meta);
        if(ack)generate_exh<512,I>(ack_meta,msn_tx,msn_query,length,info,timer,ack_headers,ack_done);
        msn_table<I>(msn_update,msn_query,msn_init,msn_rx,msn_tx);
        if(state)state_table<I>(rx_state,tx_state,qp_state,rx_rsp,tx_rsp,qp_rsp,fence_req,fence_rsp);
        as02_recv_retire_join<I>(data_done,ack_done,fence_req,fence_rsp,done,join_fault);
    }
    void ticks(unsigned n,bool data=true,bool ack=true,bool state=true) {
        for(unsigned i=0;i<n;i++)tick(data,ack,state);
    }
    void init() {
        msn_init.write(ifMsnReq(2,0x81234567));
        qp_state.write(ifStateReq(2,READY_SEND,0xfffffe,0x987654));ticks(8);
    }
    void send(as02RecvOwner o,unsigned next=0x987655) {
        rx_meta.write(ibhMeta(RC_SEND_ONLY,0xffff,2,0x987654,true));
        ExHeader<512> e;e.setRawHeader(0);ex_header.write(e);udp.write(92);owners.write(o);
        // Explicit modeled RX-IBH producer; actual table consumer is real.
        rx_state.write(rxStateReq(2,next,false));
        net_axis<512> w;w.data=0;w.keep=~ap_uint<64>(0);w.last=0;raw.write(w);
        w.keep=15;w.last=1;raw.write(w);
    }
};
static as02RecvOwner owner() {
    as02RecvOwner o;auto& n=o.context;
    n(587,524)=0xf123456789abc001ULL;n(523,460)=1;n(459,396)=0x9123456700000001ULL;
    n(395,372)=2;n(371,356)=17;n(355,340)=1;n(339,324)=4;n(323,308)=1;
    n(307,276)=128;n(275,244)=8;n(243,180)=0xfedcba9876543210ULL;n(179,116)=0x210;
    n(19,0)=3;o.length=65;o.psn=0x987654;assert(as02_recv_owner_valid(o));return o;
}
int main() {
    static_assert(MAX_QPS==8 && META_TABLE_SIZE==2000,"capacity changed");
    auto o=owner();
    {
        Harness<101> h;h.init();h.send(o);
        h.ticks(32,false,true,false);assert(h.done.empty() && h.data_done.empty() && !h.ack_done.empty());
        assert(!h.commands.empty());auto c=h.commands.read();
        assert(c.addr==0 && c.host==0 && c.len==68 && c.pid==2 && c.vfid==0);
        h.ticks(32,true,true,false);assert(h.done.empty() && !h.fence_req.empty());
        assert(h.memory.size()==2 && !h.bind_fault && !h.join_fault);
        h.ticks(16);assert(h.done.size()==1 && !h.join_fault);
        auto d=h.done.read();assert(!d.error && d.proof.owner.context==o.context &&
            d.proof.owner.length==65 && d.proof.owner.psn==o.psn && d.proof.msn==1);
        auto a=h.ack_headers.read();AckExHeader<512> ah;ah.setRawHeader(a.data(31,0));
        assert(ah.getMsn()==1 && ah.getSyndrome()==0 && a.last && a.keep==15);
        h.ticks(64);assert(h.done.empty()); // no duplicated receipt from retained regs
    }
    {
        Harness<102> h;h.init();h.send(o);h.ticks(32,true,false);
        assert(h.done.empty() && !h.data_done.empty()==false && h.ack_headers.empty());
        h.ticks(32);assert(h.done.size()==1 && !h.join_fault);
    }
    {
        Harness<103> h;h.init();auto bad=o;bad.context(395,372)=0x800002;h.send(bad);h.ticks(64);
        assert(h.bind_fault && h.commands.empty() && h.done.empty() && h.ack_headers.empty());
    }
    {
        Harness<104> h;h.init();h.send(o,0x987660);h.ticks(64);
        assert(!h.bind_fault && h.join_fault && h.done.empty());
    }
    std::cout<<"RECV_RETIRE_HLS {\"pass_test\":true,\"actual_SEND_EXH_payload_ACK_MSN_PSN_consumers\":true,"
        "\"full_native_owner_preserved\":true,\"withheld_payload_ACK_or_PSN_blocks_receipt\":true,"
        "\"high_full_QPN_and_wrong_committed_PSN_quarantined\":true,\"RX_packet_admission_producer_model\":true,"
        "\"whole_core_drain\":false,\"native_CQ_or_unpin\":false}"<<std::endl;
}
