// SPDX-License-Identifier: BSD-2-Clause-Views
// Actual derived RX/state/MSN composition. Native admission/TX allocation and
// read-init are explicit fixtures; no native pins/PCIe/MAC/CQ/RTL proof.
#include "owned_rx_services.hpp"
#define RNIC_RX_EXECUTION_FIXTURES_ONLY
#include "test_owned_rx_execution.cpp"
#include <vector>

static unsigned real_packets=0,read_packets=0,write_ACKs=0,state_reads=0,msn_reads=0,service_negatives=0,state_fences=0;
static const uint64_t SEQ=0xe23456789abcdef1ULL;
static uint64_t epoch(unsigned qp) {return 0xf123456789abcdefULL+qp;}
static as02RxExecutionOwner remap(as02RxExecutionOwner o,unsigned q,uint64_t seq,unsigned base,ap_uint<64> va) {
    o.native(395,372)=q;o.native(459,396)=epoch(q);o.native(523,460)=seq;o.native(243,180)=va;
    o.native(587,524)=seq^0x123456789abcdef0ULL;
    o.packet(15,0)=1999-q;o.packet(79,16)=0xd456789abcdef012ULL+(seq-SEQ)*8+q;
    o.packet(95,80)=q;o.packet(119,96)=base;o.packet(183,120)=epoch(q);o.packet(247,184)=seq;
    o.packet(271,248)=q;o.packet(295,272)=ap_uint<24>(base+as02_rx_delta(o).to_uint());o.packet(367,304)=epoch(q);
    BaseTransportHeader<64> b;b.setRawHeader(o.packet(543,448));b.setDstQP(q);b.setPsn(o.packet(295,272));o.packet(543,448)=b.getRawHeader();
    ap_uint<320> d=o.packet(1015,696);d(23,0)=q;d(87,24)=epoch(q);o.packet(1015,696)=d;
    assert(as02_rx_execution_valid(o));return o;
}
static as02RxExecutionOwner packet(unsigned q,unsigned length,unsigned delta,uint64_t seq,unsigned base,
    ap_uint<64> va=0xfedcba9876543210ULL) {
    uint64_t span=(uint64_t(length)+PMTU-1)/PMTU;
    unsigned op=delta==0?(span==1?RC_RDMA_READ_RESP_ONLY:RC_RDMA_READ_RESP_FIRST):
        (delta==span-1?RC_RDMA_READ_RESP_LAST:RC_RDMA_READ_RESP_MIDDLE);
    return remap(fixture(op,2,length,delta),q,seq,base,va);
}
static as02RxExecutionOwner ack_packet(unsigned q,uint64_t seq,unsigned psn) {
    return remap(fixture(RC_ACK,1,0),q,seq,psn,0xfedcba9876543210ULL);
}
static as02StateReq state_msg(unsigned q,uint64_t seq,bool write=false,unsigned psn=0) {
    as02StateReq r;r.qpn=q;r.epoch=epoch(q);r.sequence=seq;r.write=write;r.a=psn;return r;
}
template<int ID> struct Graph {
    Harness<ID> h;
    stream<as02RxStateMessage> state_rx;
    stream<as02StateReq> state_tx,state_qpi;
    stream<as02RxStateEntry> tx_rsp,qpi_rsp;
    stream<as02StateReadback> readbacks;
    stream<as02MsnTxReq> msn_tx;
    stream<as02MsnInit> msn_qpi;
    stream<as02MsnTxRsp> msn_tx_rsp;
    ap_uint<32> encode_fault=0,state_fault=0,msn_fault=0;
    void step(unsigned n=1) {while(n--) {
        h.ti();h.te();
        as02_owned_rx_state_encode<ID>(h.sq,state_rx,encode_fault);
        as02_owned_rx_state_table<ID>(state_rx,state_tx,state_qpi,h.sr,tx_rsp,qpi_rsp,readbacks,state_fault);
        as02_owned_rx_msn_table<ID>(h.mq,msn_tx,msn_qpi,h.mr,msn_tx_rsp,msn_fault);
    }}
    void healthy() {assert(!h.ibh_fault && !h.exh_fault && !encode_fault && !state_fault && !msn_fault);}
    void init(unsigned q,unsigned base) {
        auto r=state_msg(q,SEQ,true,base);r.b=0xc01234+q;r.state=READY_SEND;state_qpi.write(r);
        as02MsnInit m;m.qpn=q;m.epoch=epoch(q);m.sequence=SEQ;m.rkey=q==2?0:(0xfedcba00U+q);msn_qpi.write(m);
        step(8);healthy();assert(state_qpi.empty() && msn_qpi.empty());
    }
    void allocate(unsigned q,unsigned length,unsigned base,uint64_t seq) {
        unsigned span=(uint64_t(length)+PMTU-1)/PMTU;
        state_tx.write(state_msg(q,seq,true,(base+span)&0xffffffU));step(4);healthy();
    }
    stateTableEntry state_read(unsigned q,uint64_t seq) {
        state_qpi.write(state_msg(q,seq));
        for(unsigned n=0;qpi_rsp.empty()&&n<64;n++)step();assert(!qpi_rsp.empty());auto r=qpi_rsp.read();
        assert(r.request.qpn==q && r.request.epoch==epoch(q) && r.request.sequence==seq);healthy();++state_reads;return r.normal;
    }
    dmaState snapshot(unsigned q,uint64_t seq) {
        // An ACK's MSN read must not overwrite the actual active READ owner.
        auto a=ack_packet(q,seq,0x123456);h.mq.write(as02_rx_tag(rxMsnReq(q),a));
        for(unsigned n=0;h.mr.empty()&&n<32;n++)step();assert(!h.mr.empty());auto r=h.mr.read();
        assert(as02_rx_same_owner(r.owner,a));healthy();++msn_reads;return r.normal;
    }
    void tx_msn_read(unsigned q,uint64_t seq) {
        as02MsnTxReq r;r.qpn=q;r.epoch=epoch(q);r.sequence=seq;msn_tx.write(r);
        for(unsigned n=0;msn_tx_rsp.empty()&&n<32;n++)step();assert(!msn_tx_rsp.empty());auto s=msn_tx_rsp.read();
        assert(s.request.qpn==q && s.request.epoch==epoch(q) && s.request.sequence==seq);
        assert(s.normal.r_key==(q==2?0:(0xfedcba00U+q)));healthy();++msn_reads;
    }
    void run(as02RxExecutionOwner o,bool hold_update=false) {
        h.input(o);unsigned op=ap_uint<8>(o.packet(303,296)).to_uint();
        if(op==RC_RDMA_READ_RESP_FIRST || op==RC_RDMA_READ_RESP_ONLY)
            h.init.write(as02_rx_tag(retransRdInit(as02_rx_va(o),1),o)); // explicit read-init fixture, NOT pool proof
        step(40);healthy();
        if(op==RC_ACK) {assert(h.memory.empty());++write_ACKs;}
        else {
            assert(!h.memory.empty());auto e=h.memory.read();assert(as02_rx_memory_valid(e) && as02_rx_same_owner(e.owner,o));
            assert(e.address==as02_rx_address(o) && e.qpn==as02_rx_qpn(o));++read_packets;
        }
        assert(h.mq.empty() && h.sq.empty() && h.meta.empty() && h.sr.empty() && h.mr.empty());
        drain(h.ia,o);drain(h.ea,o);drain(h.drop,o);drain(h.policy,o);drain(h.ack,o);drain(h.timer,o);drain(h.dbg,o);
        drain(h.split,o);drain(h.shift,o);if(!hold_update)assert(drain(h.update,o)==1);
        ++real_packets;
    }
};

template<int ID> struct MsnUnit {
    stream<as02RxOwned<rxMsnReq>> in;stream<as02MsnTxReq> tx;stream<as02MsnInit> qpi;
    stream<as02RxOwned<dmaState>> out;stream<as02MsnTxRsp> tr;
    ap_uint<32> fault=0;
    void tick(unsigned n=1){while(n--)as02_owned_rx_msn_table<ID>(in,tx,qpi,out,tr,fault);}
    void init(){as02MsnInit r;r.qpn=2;r.epoch=epoch(2);r.sequence=SEQ;r.rkey=0;qpi.write(r);tick();assert(!fault);}
    void query(as02RxExecutionOwner o){in.write(as02_rx_tag(rxMsnReq(2),o));tick();}
    void progress(as02RxExecutionOwner o,bool raw=false,bool owner_mismatch=false) {
        unsigned bytes=as02_rx_length(o).to_uint()-as02_rx_delta(o).to_uint()*PMTU;if(bytes>PMTU)bytes=PMTU;
        auto wrong=o;if(owner_mismatch)wrong.packet[421]=!wrong.packet[421];
        unsigned count=bytes+(raw?ap_uint<2>(o.packet(461,460)).to_uint():0);
        in.write(as02_rx_tag(rxMsnReq(2,0,as02_rx_address(o)+count,count,1),wrong));tick();
    }
};
static void real_graph() {
    Graph<5000> g;
    for(unsigned q=0;q<8;q++){g.init(q,0xfffffe);g.allocate(q,PMTU*2+65,0xfffffe,SEQ+q);g.tx_msn_read(q,SEQ+q);}
    for(unsigned delta=0;delta<3;delta++)for(unsigned q=0;q<8;q++) {
        auto o=packet(q,PMTU*2+65,delta,SEQ+q,0xfffffe);g.run(o);
        auto s=g.snapshot(q,SEQ+100+delta);
        unsigned bytes=delta==2?65:PMTU;
        assert(s.vaddr==as02_rx_address(o)+bytes && s.dma_length==bytes && s.lst==1);
        auto state=g.state_read(q,SEQ+1000+delta);assert(state.req_old_unack==ap_uint<24>(ap_uint<24>(o.packet(295,272))+1));
    }
    unsigned base=1;
    for(unsigned len=64;len<=67;len++,base++) {
        g.allocate(2,len,base,SEQ+100+len);
        auto o=packet(2,len,0,SEQ+100+len,base);g.run(o);
        auto s=g.snapshot(2,SEQ+1000+len);assert(s.vaddr==as02_rx_va(o)+len && s.dma_length==len);
    }
    // Exact2^64 exclusive payload endpoint, not +3 raw padding wrap.
    g.allocate(2,65,base,SEQ+200);auto endpoint=packet(2,65,0,SEQ+200,base,0xffffffffffffffbfULL);g.run(endpoint);
    assert(g.snapshot(2,SEQ+1200).vaddr==0);base++;
    // A second segmented READ on the SAME live QP without reinitialization.
    g.allocate(3,PMTU+65,1,SEQ+201);
    g.run(packet(3,PMTU+65,0,SEQ+201,1));g.run(packet(3,PMTU+65,1,SEQ+201,1));
    assert(g.state_read(3,SEQ+1201).req_old_unack==3);
    // Full32-bit length is admitted; only FIRST is run (no4GiB/long test).
    g.allocate(7,0xffffffff,1,SEQ+202);g.run(packet(7,0xffffffff,0,SEQ+202,1));
    assert(g.snapshot(7,SEQ+1202).dma_length==PMTU);
    // Real state consumer keeps the existing ordered3-producer rendezvous.
    auto marker=state_msg(2,SEQ+2000,false,0xffffff);marker.is_fence=true;
    as02RxStateMessage rxmark;rxmark.normal=marker;g.state_rx.write(rxmark);g.step(12);assert(g.readbacks.empty());
    g.state_tx.write(state_msg(2,SEQ+2001,true,base+1));g.state_tx.write(marker);g.step(12);assert(g.readbacks.empty());
    // A real later ACK's state query is held behind the RX marker.
    auto a=ack_packet(2,SEQ+2002,base);g.h.input(a);g.step(12);assert(g.readbacks.empty() && g.h.meta.empty());
    g.state_qpi.write(marker);for(unsigned n=0;g.readbacks.empty()&&n<64;n++)g.step();assert(!g.readbacks.empty());
    auto rb=g.readbacks.read();assert(rb.seen==7 && rb.status==2 && rb.epoch==epoch(2) && rb.sequence==SEQ+2000);++state_fences;
    g.step(40);g.healthy();assert(g.h.memory.empty());drain(g.h.update,a);drain(g.h.ack,a);drain(g.h.timer,a);drain(g.h.policy,a);drain(g.h.dbg,a);++write_ACKs;++real_packets;
    assert(g.state_read(2,SEQ+2100).req_old_unack==base+1);
    // Private table OK while a real downstream update remains held: NOT drain.
    auto next=ack_packet(2,SEQ+2200,base+1);g.state_tx.write(state_msg(2,SEQ+2200,true,base+2));g.step(4);g.run(next,true);assert(!g.h.update.empty());
    marker=state_msg(2,SEQ+2300,false,0);marker.is_fence=true;rxmark.normal=marker;
    g.state_rx.write(rxmark);g.state_tx.write(marker);g.state_qpi.write(marker);
    for(unsigned n=0;g.readbacks.empty()&&n<64;n++)g.step();assert(!g.readbacks.empty());rb=g.readbacks.read();
    assert(rb.status==0 && rb.seen==7 && !g.h.update.empty());++state_fences;g.healthy();
}
static void wrapped_next() {
    Graph<5001> g;g.init(2,0xfffffe);g.allocate(2,PMTU+65,0xfffffe,SEQ);
    g.run(packet(2,PMTU+65,0,SEQ,0xfffffe));g.run(packet(2,PMTU+65,1,SEQ,0xfffffe));
    auto state=g.state_read(2,SEQ+1000);assert(state.req_next_psn==0 && state.req_old_unack==0);
    auto s=g.snapshot(2,SEQ+1001);assert(s.vaddr==ap_uint<64>(0xfedcba9876543210ULL)+PMTU+65 && s.dma_length==65);
}
static void negative_services() {
    auto first=packet(2,PMTU*2+65,0,SEQ,0xfffffe),middle=packet(2,PMTU*2+65,1,SEQ,0xfffffe);
    {MsnUnit<5100> t;t.query(first);t.tick();assert(t.fault==80 && t.out.empty());++service_negatives;}
    {MsnUnit<5101> t;t.init();t.query(middle);t.tick();assert(t.fault==83 && t.out.empty());++service_negatives;}
    {MsnUnit<5102> t;t.init();t.query(first);assert(!t.out.empty());t.out.read();t.progress(first);auto wrong=packet(2,PMTU*2+65,1,SEQ+1,0xfffffe);t.query(wrong);t.tick();assert(t.fault==83 && t.out.empty());++service_negatives;}
    {MsnUnit<5103> t;t.init();t.query(first);t.out.read();t.progress(first);auto wrong=middle;wrong.packet[16]=!wrong.packet[16];assert(as02_rx_execution_valid(wrong));t.query(wrong);t.tick();assert(t.fault==83 && t.out.empty());++service_negatives;}
    {MsnUnit<5104> t;t.init();t.query(first);t.out.read();t.query(middle);t.tick();assert(t.fault==83 && t.out.empty());++service_negatives;}
    {MsnUnit<5105> t;t.init();t.query(first);t.out.read();t.progress(first,false,true);t.tick();assert(t.fault==84 && t.out.empty());++service_negatives;}
    {MsnUnit<5106> t;t.init();auto only=packet(2,65,0,SEQ,0xfffffe);t.query(only);t.out.read();t.progress(only,true);t.tick();assert(t.fault==84 && t.out.empty());++service_negatives;}
    {MsnUnit<5107> t;t.init();auto only=packet(2,65,0,SEQ,0xfffffe);t.query(only);t.out.read();t.progress(only);t.query(only);t.tick();assert(t.fault==82 && t.out.empty());++service_negatives;}
    {MsnUnit<5108> t;t.init();as02MsnTxReq r;r.qpn=0x10002;r.epoch=epoch(2);r.sequence=SEQ;t.tx.write(r);t.tick(2);assert(t.fault==85 && t.tr.empty());++service_negatives;}
    {MsnUnit<5109> t;t.init();as02MsnTxReq r;r.qpn=2;r.epoch=epoch(2)^(1ULL<<63);r.sequence=SEQ;t.tx.write(r);t.tick(2);assert(t.fault==85 && t.tr.empty());++service_negatives;}
    {MsnUnit<5110> t;t.init();as02MsnInit r;r.qpn=2;r.epoch=epoch(2)+1;r.sequence=SEQ+1;t.qpi.write(r);t.tick(2);assert(t.fault==86);++service_negatives;}
    {MsnUnit<5111> t;t.init();auto a=ack_packet(2,SEQ,0xfffffe);t.in.write(as02_rx_tag(rxMsnReq(2,0),a));t.tick(2);assert(t.fault==81 && t.out.empty());++service_negatives;}
    {Graph<5112> g;g.init(2,0xfffffe);auto raw=as02RxStateMessage();raw.owner=first;raw.normal=state_msg(2,SEQ);raw.normal.response=true;raw.normal.epoch^=1ULL<<63;g.state_rx.write(raw);g.step(4);assert(g.state_fault==72 && g.h.sr.empty());++service_negatives;}
    {Graph<5113> g;auto r=state_msg(2,0);r.epoch=0;r.write=true;r.state=READY_SEND;g.state_qpi.write(r);g.step(4);assert(g.state_fault==74);++service_negatives;}
}
int main() {
    static_assert(MAX_QPS==8 && META_TABLE_SIZE==2000 && PMTU==4096,"original geometry");
    real_graph();wrapped_next();negative_services();
    std::cout<<std::dec<<"OWNED_RX_SERVICES {\"pass_test\":true,\"actual_RX_packets\":"<<real_packets
      <<",\"actual_READ_packets\":"<<read_packets<<",\"actual_WRITE_ACKs\":"<<write_ACKs
      <<",\"actual_state_readbacks\":"<<state_reads<<",\"actual_MSN_readbacks\":"<<msn_reads
      <<",\"negative_service_cases\":"<<service_negatives<<",\"ordered_state_fences\":"<<state_fences
      <<",\"state_entries\":8,\"MSN_entries\":8,\"one_state_and_MSN_per_instance\":true,\"RX_state_MSN_models\":false"
      <<",\"native_admission_and_readinit_models\":true,\"RTL_tested\":false,\"native_DMA_CQ\":false,\"whole_core_drain\":false}"<<std::endl;
}
