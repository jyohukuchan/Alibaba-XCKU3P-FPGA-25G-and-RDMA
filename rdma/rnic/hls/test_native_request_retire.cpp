// SPDX-License-Identifier: BSD-2-Clause-Views
// Actual sender/retransmission/RX/timer/PSN consumers. Parsed peer headers,
// payload source/sink and connection destination are explicit unit models.
#include <cassert>
#include <iostream>
#include "ib_transport_protocol/ib_transport_protocol.cpp"

template<int I> struct Harness {
    hls::stream<ap_uint<588>> owners,admitted;
    hls::stream<as02ReqToken> rx_owners,state_req;
    hls::stream<as02ReqState> state_rsp;
    hls::stream<txMeta> sq;
    hls::stream<event> app,reads,exh_events;
    hls::stream<ackEvent> ack_events,rx_ack_events;
    hls::stream<retransMeta> insert_meta;
    hls::stream<retransAddrLen> insert_addr;
    hls::stream<retransEntry> insert;
    hls::stream<retransUpdate> updates;
    hls::stream<retransmission> retry;
    hls::stream<retransRdInit> read_init;
    hls::stream<retransEvent> retrans_events;
    hls::stream<as02ReqStep> issued,ack_consumed,read_consumed,rx_timer_done;
    hls::stream<as02ReqInsert> inserted;
    hls::stream<as02ReqReclaim> pointer_done,pool_done;
    hls::stream<as02ReqTxTimer> tx_timer,tx_timer_done;
    hls::stream<rxTimerUpdate> rx_timer;
    hls::stream<as02ReqDone> done;
    hls::stream<ap_uint<16>> conn,msn_query,length;
    hls::stream<ap_uint<24>> dest;
    hls::stream<ibhMeta> bth_events,rx_bth,rx_exh_meta;
    hls::stream<BaseTransportHeader<512>> headers;
    hls::stream<txMsnRsp> tx_msn;
    hls::stream<dmaState> rx_msn;
    hls::stream<ifMsnReq> msn_init;
    hls::stream<rxMsnReq> msn_update;
    hls::stream<txPacketInfo> packet_info;
    hls::stream<net_axis<512>> exh_words,aeth,reth,raw,memory;
    hls::stream<as02RecvProof> recv_data,recv_ack;
    hls::stream<as02RecvOwner> recv_owners;
    hls::stream<memCmdInternal> local_mem,remote_mem;
    hls::stream<memCmd> source_cmd,destination_cmd;
    hls::stream<pkgInfo> source_info;
    hls::stream<readRequest> remote_reads;
    hls::stream<exhMeta> rx_exh;
    hls::stream<ExHeader<512>> rx_headers;
    hls::stream<ap_uint<16>> udp;
    hls::stream<bool> dropped;
    hls::stream<fwdPolicy> policy;
    hls::stream<ackMeta> acks;
    hls::stream<psnPkg> psn_debug;
    hls::stream<pkgSplit> split;
    hls::stream<pkgShift> shift;
    hls::stream<rxStateReq> rx_state;
    hls::stream<txStateReq> tx_state;
    hls::stream<ifStateReq> qp_state;
    hls::stream<rxStateRsp> rx_rsp;
    hls::stream<stateTableEntry> tx_rsp,qp_rsp;
    hls::stream<ap_uint<24>> recv_state_req;
    hls::stream<ap_uint<56>> recv_state_rsp;
    ap_uint<1> af=0,rf=0,ef=0,mf=0,tf=0,ff=0,jf=0,recv_fault=0;
    ap_uint<32> retrans_count=0,psn_drops=0;
    void tick(bool timers=true,bool payload=true,bool tables=true) {
        local_req_handler<I>(sq,retrans_events,insert_addr,local_mem,app,retrans_count,
            owners,admitted,rx_owners,af);
        meta_merger<I>(ack_events,reads,app,conn,bth_events,exh_events);
        generate_ibh<512,I>(bth_events,dest,tx_rsp,tx_state,insert_meta,headers,issued);
        generate_exh<512,I>(exh_events,tx_msn,msn_query,length,packet_info,tx_timer,exh_words,recv_ack);
        mem_cmd_merger<512>(remote_mem,local_mem,source_cmd,source_info);
        merge_retrans_request(insert_meta,insert_addr,insert,mf);
        retransmitter<I>(updates,read_init,retry,insert,retrans_events,inserted,pointer_done,pool_done,tf);
        rx_ibh_fsm<I>(rx_bth,rx_exh,rx_rsp,rx_state,rx_exh_meta,rx_ack_events,dropped,policy,acks,
            rx_timer,updates,
#ifdef DBG_IBV_IBH_FSM
            psn_debug,
#endif
            psn_drops,rx_owners,rf);
        rx_exh_fsm<512,I>(rx_exh_meta,udp,rx_msn,retry,read_init,rx_headers,destination_cmd,
            remote_reads,msn_update,rx_ack_events,split,shift,recv_owners,recv_fault,ack_consumed,ef);
        if(payload)merge_rx_pkgs<512,I>(shift,aeth,reth,raw,memory,recv_data,read_consumed);
        if(timers)as02_native_external_replay_timer<I>(rx_timer,tx_timer,rx_timer_done,tx_timer_done,ff);
        msn_table<I>(msn_update,msn_query,msn_init,rx_msn,tx_msn);
        if(tables)state_table<I>(rx_state,tx_state,qp_state,rx_rsp,tx_rsp,qp_rsp,
            recv_state_req,recv_state_rsp,state_req,state_rsp);
        as02_request_retire_join<I>(admitted,issued,inserted,ack_consumed,read_consumed,pointer_done,pool_done,
            tx_timer_done,rx_timer_done,state_req,state_rsp,done,af|rf|ef|mf|tf|ff,jf);
    }
    void ticks(unsigned n,bool timers=true,bool payload=true,bool tables=true) {
        for(unsigned k=0;k<n;k++)tick(timers,payload,tables);
    }
    void init() {
        qp_state.write(ifStateReq(2,READY_SEND,0xfffffe,0x987654));
        msn_init.write(ifMsnReq(2,0x81234567));ticks(2100);
    }
    void post(ap_uint<588> owner) {
        owners.write(owner);ap_uint<192> params=0;
        params(63,0)=owner(243,180);params(127,64)=owner(115,52);
        params(159,128)=owner(307,276);params(191,160)=owner(51,20);
        sq.write(txMeta(ibOpCode(unsigned(as02_req_opcode(owner))),2,1,1,0,params,1));
        dest.write(196);ticks(64);
        assert(!headers.empty() && !af && !mf && !tf && !jf && done.empty());
    }
    void peer(ap_uint<24> psn,bool read) {
        ibOpCode op=read ? RC_RDMA_READ_RESP_ONLY:RC_ACK;
        rx_bth.write(ibhMeta(op,0xffff,2,psn,true));rx_exh.write(exhMeta(false));
        AckExHeader<512> a;a.clear();a.setSyndrome(0);a.setMsn(1);
        ExHeader<512> e;e.setRawHeader(a.getRawHeader());rx_headers.write(e);udp.write(read ? 96:28);
        if(read){net_axis<512> w;w.data=0;w.keep=~ap_uint<64>(0);w.last=0;aeth.write(w);
            w.keep=15;w.last=1;aeth.write(w);}
    }
};
static ap_uint<588> owner(unsigned sequence,unsigned opcode) {
    ap_uint<588> n=0;n(587,524)=0xf123456789abc000ULL+sequence;n(523,460)=sequence;
    n(459,396)=0x9123456700000001ULL;n(395,372)=2;n(371,356)=17;n(355,340)=sequence;
    n(339,324)=opcode;n(323,308)=1;n(307,276)=65;n(275,244)=8;
    n(243,180)=0xfedcba9876543210ULL;n(179,116)=0x210;
    if(opcode!=3){n(115,52)=0xe23456789abcdef0ULL;n(51,20)=0x81234567;}
    n(19,0)=3;assert(as02_req_owner_valid(n));return n;
}
static void mixed_request_response_headers() {
    // SAME real static generator, not reconstructed/normalized wire bytes.
    // State-table responses are explicit unit models; native RTL exercises
    // actual state-table integration and the unmodified ACK/ICRC validators.
    hls::stream<ibhMeta> meta;
    hls::stream<ap_uint<24>> destination;
    hls::stream<stateTableEntry> state_response;
    hls::stream<txStateReq> state_request;
    hls::stream<retransMeta> retrans;
    hls::stream<BaseTransportHeader<512>> headers;
    hls::stream<as02ReqStep> issued;
    auto tick=[&]() {generate_ibh<512,152>(meta,destination,state_response,
        state_request,retrans,headers,issued);};
    const ibOpCode ops[]={RC_SEND_ONLY,RC_ACK,RC_SEND_ONLY,RC_RDMA_READ_RESP_ONLY};
    for(unsigned k=0;k<4;k++) {
        bool request=ops[k]==RC_SEND_ONLY;
        bool valid=k==3;
        ap_uint<24> psn=request ? ap_uint<24>(0xfffffe + k/2):ap_uint<24>(0x987654);
        ibhMeta b(ops[k],0xffff,2,psn,valid);
        b.request_owned=request;
        b.request_token=request ? as02_req_token(owner(k+1,3)):as02ReqToken(0);
        meta.write(b);destination.write(196);tick();
        if(!valid) {
            assert(state_request.size()==1 && headers.empty());
            assert(state_request.read().qpn==2);
            stateTableEntry s={};s.req_next_psn=psn;s.resp_epsn=psn+1;
            state_response.write(s);tick();
        }
        assert(headers.size()==1);
        auto h=headers.read();auto raw=h.getRawHeader();
        assert(h.getOpCode()==ops[k] && h.getPsn()==psn && h.getDstQP()==196);
        assert(raw[71]==request && raw(70,64)==0);
        if(request) {
            assert(state_request.size()==1 && state_request.read().qpn==2);
            assert(retrans.size()==1 && issued.size()==1);
            auto r=retrans.read();auto i=issued.read();
            assert(r.request_owned && r.request_token==b.request_token &&
                i.token==b.request_token && i.psn==psn && i.opcode==ap_uint<8>(ops[k]));
        } else assert(state_request.empty() && retrans.empty() && issued.empty());
    }
}
int main() {
    static_assert(MAX_QPS==8 && META_TABLE_SIZE==2000,"original capacities changed");
    Harness<151> h;h.init();
    const unsigned ops[]={1,2,3};const unsigned psns[]={0xfffffe,0xffffff,0};
    for(unsigned k=0;k<3;k++) {
        auto n=owner(k+1,ops[k]);h.post(n);
        auto b=h.headers.read();assert(b.getPsn()==psns[k] && b.getOpCode()==as02_req_opcode(n));
        h.peer(psns[k],ops[k]==2);
        // Real timer consumer is deliberately withheld. No quiet duration or
        // positive peer packet can substitute for consuming that bookkeeping.
        h.ticks(100,false);assert(h.done.empty() && !h.af && !h.rf && !h.ef && !h.tf && !h.jf);
        h.ticks(100);assert(h.done.size()==1 && !h.jf && !h.ff && !h.psn_drops);
        auto d=h.done.read();assert(d.context==n && d.psn==psns[k] &&
            d.next==ap_uint<24>(ap_uint<25>(psns[k])+1) && d.opcode==as02_req_opcode(n) && !d.error && !d.reserved);
        if(ops[k]==2) {
            assert(h.destination_cmd.size()==1 && h.memory.size()==2);
            auto c=h.destination_cmd.read();assert(c.addr==0xba9876543210ULL && c.len==68 && c.host==1 &&
                c.ctl==1 && c.strm==1 && c.sync==0 && c.tdst==12 && c.pid==2 && c.vfid==0);
        } else {
            assert(!h.source_cmd.empty());auto c=h.source_cmd.read();assert(c.addr==0xba9876543210ULL && c.len==65 && c.host==1 &&
                c.ctl==1 && c.strm==1 && c.sync==0 && c.tdst==12 && c.pid==2 && c.vfid==0);
        }
        h.ticks(16);assert(h.done.empty());
    }
    mixed_request_response_headers();
    std::cout<<"REQUEST_RETIRE_HLS {\"pass_test\":true,\"actual_request_consumers\":true,"
        "\"same_generator_SEND_ACK_SEND_READ_response\":true,\"response_ACK_request_bit_zero\":true,"
        "\"WRITE_READ_SEND\":true,\"full_native_owner\":true,\"same_retrans_record_pointer_pool_consumed\":true,"
        "\"timer_consumption_required\":true,\"same_PSN_readback_and_wrap\":true,"
        "\"parsed_peer_and_payload_models\":true,\"whole_core_drain\":false,\"native_CQ\":false}"<<std::endl;
}
