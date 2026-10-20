// SPDX-License-Identifier: BSD-2-Clause-Views
// Actual full transport consumers. Peer packets/connection/RQ source are
// explicit models; no native MR, DMA, MAC, CQ, Linux or hardware proof.
#include "zero_request_prior.cpp"
#include "zero_rq_endpoint.hpp"

static void put(std::vector<unsigned char>& v,unsigned p,unsigned n,uint64_t x) {
    for(unsigned i=0;i<n;i++)v[p+i]=(x>>(8*(n-1-i)))&255;
}
static uint64_t get(const std::vector<unsigned char>& v,unsigned p,unsigned n) {
    uint64_t x=0;for(unsigned i=0;i<n;i++)x=(x<<8)|v[p+i];return x;
}
static std::vector<unsigned char> incoming(unsigned op,unsigned psn,unsigned imm) {
    const unsigned ext=op==6 ? 20:op==5 ? 4:0;
    std::vector<unsigned char> v(12+ext,0);v[0]=op==3 ? 4:op==5 ? 5:11;v[1]=0x40;
    put(v,2,2,0xffff);put(v,5,3,2);v[8]=0x80;put(v,9,3,psn);
    if(op==6){put(v,12,8,UINT64_MAX);put(v,20,4,0xfedcba98);put(v,24,4,0);}
    if(op!=3)put(v,op==6 ? 28:12,4,imm);
    return v;
}
static as02RecvOwner posted(unsigned seq,unsigned psn,bool empty) {
    as02RecvOwner o;auto& n=o.context;
    n(587,524)=0xf123456789abc000ULL+seq;n(523,460)=seq;n(459,396)=0x9123456700000001ULL;
    n(395,372)=2;n(371,356)=17;n(355,340)=0x100+seq;n(339,324)=4;n(323,308)=1;n(19,0)=3;
    if(!empty){n(307,276)=128;n(275,244)=8;n(243,180)=0xfedcba9876543210ULL;n(179,116)=0x210;}
    o.length=0;o.psn=psn;assert(as02_recv_owner_valid(o));return o;
}
template<int I> static void ticks(Endpoint<I>& e,unsigned n,bool payload=true,bool tables=true) {
    for(unsigned i=0;i<n;i++)e.tick(true,payload,tables);
}
static void zero_rq_positive() {
    Endpoint<1001> e;e.init(0x123400,0xfffffe);unsigned seq=0,psn=0xfffffe;
    for(bool empty:{true,false})for(unsigned op:{3,5,6}) {
        auto o=posted(++seq,psn,empty);auto p=incoming(op,psn,op==3 ? 0:0x89abcdef);
        e.h.recv_owners.write(o);e.h.dest.write(196);zero_rq_ack_enabled=false;
        e.input(p,p.size()+8+4);ticks(e,100,false);
        // The real stripped empty EOF is present but its real merger is
        // withheld. Neither silence nor ACK scheduling can retire this RQ.
        assert(e.received.empty() && e.h.recv_data.empty() && e.h.recv_ack.empty() &&
            e.h.raw.size()==1 && e.h.destination_cmd.empty() && e.h.memory.empty());
        ticks(e,100);assert(e.received.empty() && e.h.recv_ack.empty() && e.tx_assembled.empty());
        zero_rq_ack_enabled=true;ticks(e,100,true,false);
        assert(e.received.empty() && e.h.recv_state_req.size()==1 && e.h.memory.empty() && e.h.destination_cmd.empty());
        ticks(e,100);assert(e.received.size()==1 && !e.recv_join_fault && !e.h.recv_fault && !e.h.pf);
        auto done=e.received.read();assert(!done.error && done.proof.owner.context==o.context &&
            done.proof.owner.psn==psn && !done.proof.owner.length && done.proof.msn==seq &&
            done.proof.immediate==(op==3 ? 0U:0x89abcdefU) && done.proof.flags==(op==3 ? 0:op==5 ? 1:3));
        auto ack=e.packet(false);assert(ack.size()==16 && ack[0]==RC_ACK && get(ack,5,3)==196 &&
            get(ack,9,3)==psn && ack[12]==0 && get(ack,13,3)==seq);
        assert(e.h.length.size()==1 && e.h.length.read()==20 && e.h.conn.size()==1 && e.h.conn.read()==2);
        assert(e.h.memory.empty() && e.h.destination_cmd.empty() && e.h.source_cmd.empty() &&
            e.h.raw.empty() && e.h.reth.empty() && e.h.aeth.empty() && e.h.done.empty());
        std::cout<<"ZERO_RQ_RECEIPT "<<op<<" "<<empty<<" "<<psn<<" "<<seq<<std::endl;
        psn=(psn+1)&0xffffff;
    }
    ticks(e,100);assert(e.received.empty());
}
template<int I> static void bad_owner(unsigned field) {
    Endpoint<I> e;e.init(0x123400,0xfffffe);auto o=posted(1,0xfffffe,true);
    if(field==0)o.context(275,244)=1;
    if(field==1)o.context(243,180)=1;
    if(field==2)o.context(179,116)=1;
    if(field==3)o.context(395,372)=0x800002;
    assert(!as02_recv_owner_valid(o));e.h.recv_owners.write(o);e.h.dest.write(196);
    auto p=incoming(3,0xfffffe,0);e.input(p,p.size()+12);ticks(e,100);
    assert(e.h.recv_fault && e.received.empty() && e.h.destination_cmd.empty() && e.h.memory.empty() && e.h.headers.empty());
}
template<int I> static void bad_eof(bool nonempty) {
    Harness<I> h;h.init();pkgShift s(SHIFT_NONE,2);s.receive_owned=true;s.zero_receive=true;
    s.receive.owner=posted(1,0x987654,true);s.receive.msn=1;h.shift.write(s);
    net_axis<512> w;w.data=0;w.keep=nonempty ? 1:0;w.last=nonempty;h.raw.write(w);h.ticks(16);
    assert(h.pf && h.recv_data.empty() && h.memory.empty() && h.done.empty());
}
int main() {
    assert(previous_zero_request_main()==0);zero_rq_positive();
    bad_owner<1002>(0);bad_owner<1003>(1);bad_owner<1004>(2);bad_owner<1005>(3);
    bad_eof<1006>(true);bad_eof<1007>(false);
    std::cout<<"ZERO_RQ_HLS {\"pass_test\":true,\"zero_operations\":3,\"posted_zero_and_nonzero_buffer_cases\":6,"
        "\"actual_RX_BTH_EXH_empty_EOF_ACK_MSN_PSN_consumers\":true,\"withheld_real_EOF_ACK_state_blocks_done\":true,"
        "\"no_zero_memory_command_or_data\":true,\"full620_owner_and_wire_Immediate_preserved\":true,"
        "\"PSN_wrap\":true,\"owner_and_EOF_negatives\":6,\"normal_zero_WRITE_READ_responder\":false,"
        "\"native_RTL_kernel_MAC_CQ_hardware\":false}"<<std::endl;
    return 0;
}
