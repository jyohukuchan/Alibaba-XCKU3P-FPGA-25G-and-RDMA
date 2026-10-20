// SPDX-License-Identifier: BSD-2-Clause-Views
// Actual transport consumers connected by a bounded byte-packet model.
// No IPv4/UDP/ICRC, native MR/PCIe/MAC/CQ or Linux claims in this C++ test.
#include <vector>
#define main preceding_request_main
#include "immediate_request_base.hpp"
#undef main

template<int I> struct Endpoint {
    Harness<I> h;
    hls::stream<net_axis<512>> incoming,bth_forward,exh_in,exh_payload;
    hls::stream<net_axis<512>> aeth_unshifted,reth_unshifted;
    hls::stream<net_axis<512>> mem_source,tx_aeth,tx_reth,tx_raw,tx_assembled;
    hls::stream<ibOpCode> rx_op;
    hls::stream<as02RecvDone> received;
    hls::stream<ackEvent> other_ack;
    hls::stream<as02RnrEvent> rnr;
    ap_uint<1> recv_join_fault=0,rnr_fault=0;ap_uint<32> rx_count=0;
    void tick(bool retire=true) {
        // Harness executes actual admission, BTH/EXH, RX-IBH, PSN/MSN,
        // retransmission, memory-command, timer and request-retire consumers.
        h.tick();
        as02_native_rnr_merger<I>(h.rx_ack_events,other_ack,rnr,h.ack_events,rnr_fault);
        rx_process_ibh<512,I>(
#ifdef DBG_IBV_IBH_PROCESS
            h.psn_debug,
#endif
            incoming,h.rx_bth,rx_op,bth_forward,rx_count);
        rshiftWordByOctet<net_axis<512>,512,11,I>(12,bth_forward,exh_in);
        rx_process_exh<512,I>(exh_in,rx_op,h.rx_exh,h.rx_headers,exh_payload);
        rx_exh_payload<512,I>(h.split,exh_payload,reth_unshifted,aeth_unshifted,h.raw);
        rshiftWordByOctet<net_axis<512>,512,12,I>(16,reth_unshifted,h.reth);
        rshiftWordByOctet<net_axis<512>,512,13,I>(4,aeth_unshifted,h.aeth);
        tx_pkg_arbiter<512,I>(h.source_info,mem_source,tx_aeth,tx_reth,tx_raw);
        append_payload<512,I>(h.packet_info,h.exh_words,tx_aeth,tx_reth,tx_raw,tx_assembled);
        // Withholding is achieved by not running the real retire consumer;
        // no synthetic completion/idle bit is ever inserted.
        if(retire)
            as02_recv_retire_join<I>(h.recv_data,h.recv_ack,h.recv_state_req,h.recv_state_rsp,received,recv_join_fault);
    }
    void init(unsigned remote_psn,unsigned local_psn) {
        h.qp_state.write(ifStateReq(2,READY_SEND,remote_psn,local_psn));
        h.msn_init.write(ifMsnReq(2,0x81234567));
        for(unsigned j=0;j<2100;j++)tick();
    }
    void input(const std::vector<unsigned char>& bytes,unsigned udp_length) {
        h.udp.write(udp_length);
        for(unsigned p=0;p<bytes.size();p+=64) {
            net_axis<512> w;w.data=0;w.keep=0;
            for(unsigned b=0;b<64 && p+b<bytes.size();b++) {
                w.data(8*b+7,8*b)=bytes[p+b];w.keep[b]=1;
            }
            w.last=p+64>=bytes.size();incoming.write(w);
        }
    }
    std::vector<unsigned char> packet(bool pad) {
        assert(h.headers.size()==1 && !tx_assembled.empty());
        auto b=h.headers.read();auto raw=b.getRawHeader();std::vector<unsigned char> bytes;
        for(unsigned j=0;j<12;j++)bytes.push_back(unsigned(raw(j*8+7,j*8)));
        bool last=false;
        while(!tx_assembled.empty()) {
            auto w=tx_assembled.read();assert(!last);
            for(unsigned j=0;j<64;j++)if(w.keep[j])bytes.push_back(unsigned(w.data(j*8+7,j*8)));
            last=w.last;
        }
        assert(last);
        if(pad)while(bytes.size()%4)bytes.push_back(0);
        return bytes;
    }
};

static ap_uint<620> request_owner(unsigned seq,unsigned op,unsigned imm) {
    auto n=owner(seq,op==5 ? 3:1);n(339,324)=op;n(619,588)=imm;
    assert(as02_req_owner_valid(n));return n;
}
static as02RecvOwner receive_owner(unsigned seq,unsigned psn,bool write) {
    as02RecvOwner o;o.context=owner(seq,3);auto& n=o.context;
    n(339,324)=4;n(355,340)=0x100+seq;
    // For WRITE_WITH_IMM the RQ buffer is intentionally SMALLER than data.
    // It is notification ownership, never the remote-write destination.
    n(307,276)=write ? 1:128;o.length=65;o.psn=psn;
    assert(as02_recv_owner_valid(o,write));return o;
}
int main() {
    static_assert(MAX_QPS==8 && META_TABLE_SIZE==2000,"original geometry changed");
    Endpoint<221> tx;Endpoint<222> rx;
    tx.init(0xfffffe,0x123400);rx.init(0x123400,0xfffffe);
    const unsigned values[]={0,0x01234567,0x80000000,0xffffffff};unsigned seq=0;
    for(unsigned op:{5,6})for(unsigned imm:values) {
        auto n=request_owner(++seq,op,imm);bool write=op==6;
        unsigned psn=(0xfffffe + seq - 1)&0xffffff;
        auto posted=receive_owner(seq,psn,write);
        tx.h.owners.write(n);ap_uint<192> p=0;p(63,0)=n(243,180);p(127,64)=n(115,52);
        p(159,128)=n(307,276);p(191,160)=n(51,20);
        txMeta m(ibOpCode(unsigned(as02_req_opcode(n))),2,1,1,0,p,1);m.immediate=imm;
        tx.h.sq.write(m);tx.h.dest.write(2);rx.h.recv_owners.write(posted);
        for(unsigned j=0;j<100;j++){tx.tick();rx.tick();}
        assert(tx.h.source_cmd.size()==1);auto source=tx.h.source_cmd.read();
        assert(source.origin==2 && source.len==65);
        net_axis<512> w;w.data=0;
        for(unsigned b=0;b<64;b++)w.data(b*8+7,b*8)=b^0xa5;
        w.keep=~ap_uint<64>(0);w.last=0;tx.mem_source.write(w);
        w.data=0x5a;w.keep=1;w.last=1;tx.mem_source.write(w);
        for(unsigned j=0;j<100;j++){tx.tick();rx.tick();}
        auto packet=tx.packet(true);assert(packet[0]==unsigned(as02_req_opcode(n)));
        assert(tx.h.length.size()==1);tx.h.length.read();
        rx.input(packet,packet.size()+8+4);rx.h.dest.write(2);
        for(unsigned j=0;j<100;j++){tx.tick();rx.tick(false);}
        assert(rx.received.empty() && tx.h.done.empty());
        assert(rx.h.destination_cmd.size()==1);auto placement=rx.h.destination_cmd.read();
        assert(placement.origin==1 && placement.len==68 && placement.pid==2 &&
            placement.addr==(write ? 0x56789abcdef0ULL:0) && placement.host==unsigned(write));
        std::vector<unsigned char> data;
        while(!rx.h.memory.empty()) {
            auto v=rx.h.memory.read();
            for(unsigned b=0;b<64;b++)if(v.keep[b])data.push_back(unsigned(v.data(b*8+7,b*8)));
        }
        assert(data.size()==68);
        for(unsigned j=0;j<64;j++)assert(data[j]==(j^0xa5));
        assert(data[64]==0x5a && data[65]==0 && data[66]==0 && data[67]==0);
        for(unsigned j=0;j<100;j++){tx.tick();rx.tick();}
        assert(rx.received.size()==1 && !rx.recv_join_fault && !rx.h.recv_fault && !rx.h.rf);
        auto d=rx.received.read();
        assert(!d.error && d.proof.owner.context==posted.context && d.proof.owner.psn==psn &&
            d.proof.owner.length==65 && d.proof.immediate==imm && d.proof.flags==(write ? 3:1) && d.proof.msn==seq);
        auto ack=rx.packet(false);assert(ack[0]==unsigned(RC_ACK) && ack.size()==16);
        assert(rx.h.length.size()==1);rx.h.length.read();tx.input(ack,28);
        for(unsigned j=0;j<200;j++){tx.tick();rx.tick();}
        assert(tx.h.done.size()==1 && !tx.h.jf && !tx.h.rf && !tx.h.ef && !tx.h.tf && !tx.h.ff);
        auto done=tx.h.done.read();assert(done.context==n && done.psn==psn && !done.error);
        assert(rx.received.empty());
    }
    std::cout<<"IMMEDIATE_RECEIVE_HLS {\"pass_test\":true,\"actual_request_opcodes\":2,"
        "\"values_per_opcode\":4,\"actual_BTH_EXH_payload_ACK_and_PSN_consumers\":true,"
        "\"request_and_receive_receipts\":8,\"write_data_not_RQ_buffer\":true,"
        "\"actual_wire_immediate_separate_from_posted_context\":true,\"PSN_wrap\":true,"
        "\"native_RTL_kernel_MR_ICRC_or_physical_verified\":false}"<<std::endl;
    return 0;
}
