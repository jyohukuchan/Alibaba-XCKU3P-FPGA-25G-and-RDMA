// SPDX-License-Identifier: BSD-2-Clause-Views
// Actual shared whole-RX consumer, explicit packet-proof producer model.
// This does NOT replace/prove per-packet EOF/ACK/PSN/MR/MAC/CQ consumers.
#include <cassert>
#include <iostream>
#include <string>
#include "ib_transport_protocol/ib_transport_protocol.hpp"
#include "ib_transport_protocol/msn_table.hpp"
#include "ib_transport_protocol/retransmitter/retransmitter.hpp"
#include "ib_transport_protocol/as02_recv_retire.hpp"

struct JoinBench {
    hls::stream<as02RecvDone> input,packets;hls::stream<as02RecvMessage> messages;
    ap_uint<1> fault=0;
    void tick(unsigned n=12){for(unsigned i=0;i<n;i++)as02_recv_message_join<5601>(input,packets,messages,fault);}
    void send(as02RecvDone d){input.write(d);tick();}
};
static as02RecvDone packet(unsigned q,unsigned psn,unsigned length,unsigned flags,unsigned msn,unsigned capacity=1048576) {
    as02RecvDone d;auto& p=d.proof;auto& n=p.owner.context;
    n(587,524)=0xf123456789abc001ULL+q;n(523,460)=1;n(459,396)=0x9123456700000001ULL;
    n(395,372)=q;n(371,356)=17;n(355,340)=1;n(339,324)=4;n(323,308)=1;
    n(307,276)=capacity;n(275,244)=8;n(243,180)=0xfedcba9876543210ULL;n(179,116)=0x210;n(19,0)=3;
    p.owner.length=length;p.owner.psn=psn;p.flags=flags;p.msn=msn;
    return d;
}
static void positive() {
    JoinBench b;auto a=packet(2,0xfffffe,4096,4,0xffffff);auto c=packet(3,17,4096,4,7);
    b.send(a);assert(b.packets.size()==1 && b.messages.empty());b.packets.read();
    b.send(c);assert(b.packets.size()==1 && b.messages.empty());b.packets.read();
    auto mid=a;mid.proof.owner.psn=0xffffff;mid.proof.flags=8;b.send(mid);
    assert(b.packets.size()==1 && b.messages.empty());b.packets.read();
    auto end=c;end.proof.owner.psn=18;end.proof.owner.length=5;end.proof.flags=17;end.proof.msn=8;
    end.proof.immediate=0x89abcdef;b.send(end);assert(b.packets.size()==1 && b.messages.size()==1);b.packets.read();
    auto m=b.messages.read();assert(m.context==c.proof.owner.context && m.bytes==4101 && m.first_psn==17 &&
        m.last_psn==18 && m.msn==8 && m.immediate==0x89abcdef && m.flags==1 && !m.error);
    end=a;end.proof.owner.psn=0;end.proof.owner.length=1;end.proof.flags=16;end.proof.msn=0;
    b.send(end);assert(b.packets.size()==1 && b.messages.size()==1);b.packets.read();m=b.messages.read();
    assert(m.context==a.proof.owner.context && m.bytes==8193 && m.first_psn==0xfffffe && m.last_psn==0 &&
        m.msn==0 && !m.immediate && !m.flags && !m.error);
    // WRITE_IMM notification owner is intentionally smaller than data.
    auto small=packet(2,1,65,3,1,1);small.proof.immediate=0xffffffff;
    b.send(small);assert(!b.fault && b.packets.size()==1 && b.messages.size()==1);b.packets.read();m=b.messages.read();
    assert(m.context==small.proof.owner.context && m.bytes==65 && m.flags==3 && m.immediate==0xffffffff);
    auto zero=packet(2,2,0,0,2,0);zero.proof.owner.context(275,116)=0;
    b.send(zero);assert(!b.fault && b.packets.size()==1 && b.messages.size()==1);b.packets.read();m=b.messages.read();
    assert(m.context==zero.proof.owner.context && !m.bytes && m.first_psn==2 && m.last_psn==2 && m.msn==2);
    b.tick(32);assert(b.messages.empty() && b.packets.empty());
    std::cout<<"RECEIVE_MESSAGE_JOIN {\"pass_test\":true,\"interleaved_QPs\":2,\"whole_messages\":4,"
        "\"full_owner_and_actual_bytes\":true,\"PSN_MSN_wrap\":true,\"small_WRITE_Immediate_and_zero_preserved\":true,"
        "\"packet_proof_producer_modeled\":true,\"native_or_physical\":false}"<<std::endl;
}
static void negative(unsigned kind) {
    JoinBench b;auto first=packet(2,0xfffffe,4096,4,7,kind==10 ? 4097:1048576);
    if(kind!=12 && kind!=13){b.send(first);assert(!b.fault && b.messages.empty());b.packets.read();}
    auto bad=first;bad.proof.owner.psn=0xffffff;bad.proof.owner.length=1;bad.proof.flags=17;bad.proof.msn=8;
    if(kind==0)bad.proof.owner.context(523,460)=2;
    if(kind==1)bad.proof.owner.context(459,396)=0x9123456700000002ULL;
    if(kind==2)bad.proof.owner.context(371,356)=18;
    if(kind==3)bad.proof.owner.context(275,244)=9;
    if(kind==4)bad.proof.owner.psn=0;
    if(kind==5)bad.proof.msn=7;
    if(kind==6)bad.proof.flags=4;
    if(kind==7)bad.proof.flags=8;
    if(kind==8){bad.proof.flags=16;bad.proof.immediate=1;}
    if(kind==9)bad.proof.owner.reserved=1;
    if(kind==10)bad.proof.owner.length=2;
    if(kind==11)bad.error=1;
    if(kind==12)bad.proof.owner.context(395,372)=0x800002;
    if(kind==13)bad.proof.owner.context(395,372)=8;
    if(kind==14)bad.proof.owner.context(587,524)=0xf123456789abc999ULL;
    if(kind==15)bad.proof.owner.context(179,116)=0x211;
    if(kind==16)bad.proof.flags=0;
    b.send(bad);assert(b.fault && b.messages.empty() && b.packets.empty());
    b.input.write(first);b.tick(32);assert(b.fault && b.input.size()==1 && b.messages.empty() && b.packets.empty());
    std::cout<<"RECEIVE_MESSAGE_JOIN_NEGATIVE "<<kind<<std::endl;
}
int main(int argc,char **argv) {
    static_assert(MAX_QPS==8 && META_TABLE_SIZE==2000,"original geometry changed");
    if(argc==1)positive();else negative(std::stoul(argv[1]));return 0;
}
