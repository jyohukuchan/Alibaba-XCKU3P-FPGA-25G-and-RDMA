// SPDX-License-Identifier: BSD-2-Clause-Views
// Actual derived FNS RX FSM C++ tests. Native input and state/MSN responses
// are explicit models, NOT actual ib_umem/MR/refcount/PCIe/MAC/CQ runtime.
#include "owned_rx_execution.hpp"
#include "ib_utils.cpp"
#include <cassert>
#include <iostream>

static unsigned checks=0,transactions=0,negative_cases=0,control_packets=0,aeth_packets=0;
static unsigned full_owner_bit_comparisons=0;

static as02RxExecutionOwner fixture(unsigned op,unsigned native_op,unsigned length,
    unsigned delta=0,unsigned syndrome=0,ap_uint<64> address=ap_uint<64>(0xfedcba9876543210ULL)) {
    as02RxExecutionOwner o;
    const ap_uint<64> epoch=0xf123456789abcdefULL,sequence=0xe23456789abcdef1ULL;
    o.native[0]=1;o.native[1]=1;o.native(51,20)=0;
    o.native(115,52)=0xf123456789abc001ULL;o.native(179,116)=0;
    o.native(243,180)=address;o.native(275,244)=0;o.native(307,276)=length;
    o.native(323,308)=1;o.native(339,324)=native_op;o.native(355,340)=0xabcd;
    o.native(371,356)=0xfedc;o.native(395,372)=2;o.native(459,396)=epoch;
    o.native(523,460)=sequence;o.native(587,524)=0xc3456789abcdef02ULL;
    ap_uint<248> lease=0;lease(15,0)=1999;lease(79,16)=0xd456789abcdef012ULL;
    lease(95,80)=2;lease(119,96)=0xfffffe;lease(183,120)=epoch;lease(247,184)=sequence;
    o.packet(247,0)=lease;o.packet(271,248)=2;o.packet(295,272)=ap_uint<24>(0xfffffe + delta);
    o.packet(303,296)=op;o.packet(367,304)=epoch;o.packet(391,368)=delta;
    o.packet(411,400)=3;o.packet(419,412)=syndrome;
    bool has=op!=RC_RDMA_READ_RESP_MIDDLE;o.packet[420]=has;o.packet[421]=0;o.packet[422]=1;
    unsigned bytes=0,pad=0;
    if(op!=RC_ACK && syndrome<32) {
        bytes=length-delta*PMTU;if(bytes>PMTU)bytes=PMTU;
        if(op==RC_RDMA_READ_RESP_ONLY || op==RC_RDMA_READ_RESP_LAST)pad=(-bytes)&3;
    }
    BaseTransportHeader<64> b;b.setRawHeader(0);b.setOpCode(static_cast<ibOpCode>(op));
    b.setPartitionKey(0xffff);b.setDstQP(2);b.setPsn(ap_uint<24>(0xfffffe + delta));b.setPadCount(pad);
    o.packet(543,448)=b.getRawHeader();
    if(has) {
        AckExHeader<64> a;a.setRawHeader(0);a.setSyndrome(syndrome);a.setMsn(0xffffff);
        o.packet(671,544)=a.getRawHeader();o.packet[694]=a.isNAK();
    }
    o.packet(693,672)=1;
    ap_uint<320> d=0;d(23,0)=2;d(87,24)=epoch;d(103,88)=(has?16:12)+bytes+pad;
    d[104]=1;d(289,274)=0xffff;o.packet(1015,696)=d;
    return o;
}
static ibhMeta ibh(as02RxExecutionOwner o) {
    BaseTransportHeader<64> b;b.setRawHeader(o.packet(543,448));
    return ibhMeta(b.getOpCode(),b.getPartitionKey(),b.getDstQP(),b.getPsn(),true);
}
template<typename T> static unsigned drain(stream<as02RxOwned<T>>& s,as02RxExecutionOwner o) {
    unsigned n=0;while(!s.empty()) {assert(as02_rx_same_owner(s.read().owner,o));++n;++checks;}return n;
}
template<int ID> struct Harness {
    stream<as02RxOwned<ibhMeta>> in,meta;
    stream<as02RxOwned<exhMeta>> exh;
    stream<as02RxOwned<rxStateRsp>> sr;
    stream<as02RxOwned<rxStateReq>> sq;
    stream<as02RxOwned<ackEvent>> ia,ea;
    stream<as02RxOwned<bool>> drop;
    stream<as02RxOwned<fwdPolicy>> policy;
    stream<as02RxOwned<ackMeta>> ack;
    stream<as02RxOwned<rxTimerUpdate>> timer;
    stream<as02RxOwned<retransUpdate>> update;
    stream<as02RxOwned<psnPkg>> dbg;
    stream<as02RxOwned<ap_uint<8>>> control;
    stream<as02RxOwned<dmaState>> mr;
    stream<as02RxOwned<retransmission>> retry;
    stream<as02RxOwned<retransRdInit>> init;
    stream<as02RxOwned<readRequest>> read;
    stream<as02RxOwned<rxMsnReq>> mq;
    stream<as02RxOwned<pkgSplit>> split;
    stream<as02RxOwned<pkgShift>> shift;
    stream<as02RxMemoryEffect> memory;
    ap_uint<32> dropped=0,ibh_fault=0,exh_fault=0;
    void ti() {as02_owned_rx_ibh_fsm<ID>(in,exh,sr,sq,meta,ia,drop,policy,ack,timer,update,dbg,dropped,control,ibh_fault);}
    void te() {as02_owned_rx_exh_fsm<64,ID>(meta,mr,retry,init,memory,read,mq,ea,split,shift,exh_fault);}
    void input(as02RxExecutionOwner o) {
        in.write(as02_rx_tag(ibh(o),o));exh.write(as02_rx_tag(exhMeta(bool(o.packet[694]),1),o));
    }
    void state(as02RxExecutionOwner o) {
        ti();assert(!sq.empty());auto q=sq.read();assert(!q.normal.write && q.normal.qpn==2 && as02_rx_same_owner(q.owner,o));
        sr.write(as02_rx_tag(rxStateRsp(ap_uint<24>(o.packet(295,272)),0xfffffd,ap_uint<24>(o.packet(295,272)),7),o));ti();
    }
    void msn(as02RxExecutionOwner o,int bad=0) {
        te();assert(!mq.empty());auto q=mq.read();assert(!q.normal.write && as02_rx_same_owner(q.owner,o));
        dmaState dm{};dm.msn=0xfedcba;dm.vaddr=as02_rx_address(o);dm.lst=1;
        as02RxExecutionOwner response=o;if(bad==1)response.native[587]=!response.native[587];
        if(bad==2)dm.vaddr=as02_rx_address(o)+1;
        mr.write(as02_rx_tag(dm,response));
        unsigned op=ap_uint<8>(o.packet(303,296)).to_uint();
        if(op==RC_RDMA_READ_RESP_FIRST || op==RC_RDMA_READ_RESP_ONLY) {
            auto own=o;if(bad==3)own.packet[421]=!own.packet[421];
            init.write(as02_rx_tag(retransRdInit(as02_rx_va(o)+(bad==4?1:0),1),own));
        }
        te();te();
    }
};

template<int ID> static void positive(as02RxExecutionOwner o) {
    assert(as02_rx_execution_valid(o));Harness<ID> h;h.input(o);h.state(o);h.msn(o);
    unsigned op=ap_uint<8>(o.packet(303,296)).to_uint();
    assert(h.ibh_fault==0 && h.exh_fault==0 && h.control.empty());
    assert(drain(h.sq,o)==1 && drain(h.update,o)==1 && drain(h.policy,o)==1);
    drain(h.ia,o);drain(h.drop,o);drain(h.ack,o);drain(h.timer,o);drain(h.dbg,o);
    if(op==RC_ACK) {assert(h.memory.empty() && h.mq.empty() && h.split.empty() && h.shift.empty());}
    else {
        assert(!h.memory.empty());auto e=h.memory.read();
        assert(as02_rx_same_owner(e.owner,o) && as02_rx_memory_valid(e));
        assert(e.address==as02_rx_address(o) && e.address>ap_uint<64>(0xffffffffffffULL));
        assert(e.length==ap_uint<33>(e.payload_length)+e.pad_bytes && e.pad_bytes==o.packet(461,460));
        auto corrupted=e;corrupted.payload_length=e.payload_length+1;assert(!as02_rx_memory_valid(corrupted));
        assert(e.qpn==2 && e.host==PKG_HOST);++checks;
        assert(drain(h.split,o)==1 && drain(h.shift,o)==1);
        assert(!h.mq.empty());auto msn=h.mq.read();
        assert(msn.normal.write && as02_rx_same_owner(msn.owner,o));
        assert(msn.normal.vaddr==ap_uint<64>(e.address+e.payload_length) && msn.normal.dma_length==e.payload_length);
        assert(h.mq.empty());
    }
    assert(h.meta.empty() && h.memory.empty() && h.retry.empty() && h.ea.empty() && h.read.empty());
    ++transactions;
}

template<int ID> static void all_syndromes(unsigned op,unsigned native_op,unsigned start=0) {
    Harness<ID> h;unsigned initial_controls=control_packets;
    for(unsigned syn=start;syn<256;syn++) {
        auto o=fixture(op,native_op,65,0,syn);assert(as02_rx_execution_valid(o));h.input(o);h.ti();
        if(syn>=32) {
            assert(h.sq.empty() && h.meta.empty() && h.timer.empty() && h.update.empty() && h.ack.empty() && h.policy.empty());
            assert(!h.control.empty());auto c=h.control.read();assert(c.normal==syn && as02_rx_same_owner(c.owner,o));++control_packets;
        } else {
            assert(drain(h.sq,o)==1);
            h.sr.write(as02_rx_tag(rxStateRsp(0xfffffe,0xfffffd,0xfffffe,7),o));h.ti();
            assert(drain(h.sq,o)==1 && drain(h.meta,o)==1 && drain(h.timer,o)==1 && drain(h.update,o)==1 && drain(h.ack,o)==1);
            assert(drain(h.policy,o)==1 && h.control.empty());
            drain(h.dbg,o);drain(h.drop,o);assert(h.ia.empty());
        }
        assert(!h.ibh_fault);++checks;++aeth_packets;
    }
    assert(control_packets-initial_controls==224);
}

template<int ID> static void bad_exh_response(int bad) {
    unsigned op=bad==2?RC_RDMA_READ_RESP_LAST:RC_RDMA_READ_RESP_ONLY;
    auto o=fixture(op,2,bad==2?PMTU+65:65,bad==2?1:0);Harness<ID> h;h.input(o);h.state(o);h.msn(o,bad);h.te();
    assert(h.exh_fault==(bad==1?64:(bad==2?65:66)) && h.memory.empty() && h.mq.empty() && h.split.empty() && h.shift.empty());++negative_cases;
}
static void negatives() {
    auto o=fixture(RC_RDMA_READ_RESP_ONLY,2,65);
    {Harness<101> h;h.in.write(as02_rx_tag(ibh(o),o));auto wrong=o;wrong.native[587]=!wrong.native[587];
     h.exh.write(as02_rx_tag(exhMeta(false,1),wrong));h.ti();h.ti();assert(h.ibh_fault==61 && h.sq.empty() && h.meta.empty() && h.timer.empty() && h.update.empty());++negative_cases;}
    {Harness<102> h;h.input(o);h.ti();assert(drain(h.sq,o)==1);auto wrong=o;wrong.native[459]=!wrong.native[459];
     h.sr.write(as02_rx_tag(rxStateRsp(0xfffffe,0xfffffd,0xfffffe,7),wrong));h.ti();h.ti();assert(h.ibh_fault==62 && h.sq.empty() && h.meta.empty() && h.timer.empty() && h.update.empty());++negative_cases;}
    {Harness<103> h;auto wrong=o;wrong.native(395,372)=0x10002;h.input(wrong);h.ti();h.ti();assert(h.ibh_fault==61 && h.sq.empty() && h.meta.empty());++negative_cases;}
    {Harness<104> h;auto ctrl=fixture(RC_ACK,1,65,0,0x20);h.meta.write(as02_rx_tag(ibh(ctrl),ctrl));h.te();h.te();assert(h.exh_fault==63 && h.mq.empty() && h.memory.empty());++negative_cases;}
    bad_exh_response<105>(1);bad_exh_response<106>(2);bad_exh_response<107>(3);bad_exh_response<108>(4);
    for(unsigned bit=0;bit<1612;bit++) {
        auto wrong=o;if(bit<1024)wrong.packet[bit]=!wrong.packet[bit];else wrong.native[bit-1024]=!wrong.native[bit-1024];
        assert(!as02_rx_same_owner(o,wrong));++full_owner_bit_comparisons;
    }
    auto wrong=o;wrong.packet[120]=!wrong.packet[120];assert(!as02_rx_execution_valid(wrong));++negative_cases;
    wrong=o;wrong.packet[422]=0;assert(!as02_rx_execution_valid(wrong));++negative_cases;
    wrong=o;wrong.native[396]=!wrong.native[396];assert(!as02_rx_execution_valid(wrong));++negative_cases;
    wrong=o;wrong.packet(799,784)=16+67;assert(!as02_rx_execution_valid(wrong));++negative_cases;
    wrong=o;wrong.packet[460]=!wrong.packet[460];assert(!as02_rx_execution_valid(wrong));++negative_cases;
    wrong=o;wrong.native(307,276)=0;assert(!as02_rx_execution_valid(wrong));++negative_cases;
    wrong=o;wrong.packet(399,392)=2;assert(!as02_rx_execution_valid(wrong));++negative_cases;
    wrong=o;wrong.native(243,180)=ap_uint<64>(0xffffffffffffffc0ULL);assert(!as02_rx_execution_valid(wrong));++negative_cases;
    wrong=fixture(RC_RDMA_READ_RESP_ONLY,1,65,0,0x20);assert(!as02_rx_execution_valid(wrong));++negative_cases;
}
static void admission_pair() {
    stream<ap_uint<1024>> frames;stream<ap_uint<588>> natives;
    stream<as02RxOwned<ibhMeta>> b;stream<as02RxOwned<exhMeta>> e;ap_uint<32> fault=0;
    auto o=fixture(RC_RDMA_READ_RESP_ONLY,2,65);frames.write(o.packet);
    as02_rx_execution_admit(frames,natives,b,e,fault);assert(!frames.empty() && b.empty() && e.empty());
    natives.write(o.native);as02_rx_execution_admit(frames,natives,b,e,fault);
    assert(!fault && frames.empty() && natives.empty());
    auto bm=b.read();auto em=e.read();assert(as02_rx_same_owner(bm.owner,o) && as02_rx_same_owner(em.owner,o));
    assert(as02_rx_ibh_matches(bm.normal,o) && !em.normal.isNak && em.normal.numPkg==1);++checks;
    // Last test poisons admission permanently; no reset/release is fabricated.
    auto wrong=o;wrong.native(523,460)=0;frames.write(o.packet);natives.write(wrong.native);
    as02_rx_execution_admit(frames,natives,b,e,fault);as02_rx_execution_admit(frames,natives,b,e,fault);
    assert(fault==60 && b.empty() && e.empty());++negative_cases;
}
#ifndef RNIC_RX_EXECUTION_FIXTURES_ONLY
int main() {
    static_assert(PMTU==4096 && MAX_QPS==8 && META_TABLE_SIZE==2000,"original geometry");
    positive<1>(fixture(RC_RDMA_READ_RESP_ONLY,2,65));
    positive<2>(fixture(RC_RDMA_READ_RESP_FIRST,2,PMTU*2+65,0));
    positive<3>(fixture(RC_RDMA_READ_RESP_MIDDLE,2,PMTU*2+65,1));
    positive<4>(fixture(RC_RDMA_READ_RESP_LAST,2,PMTU*2+65,2));
    positive<5>(fixture(RC_ACK,1,0)); // Zero-length WRITE ACK is not zero-length READ support.
    positive<6>(fixture(RC_ACK,1,0xffffffff));
    positive<7>(fixture(RC_RDMA_READ_RESP_FIRST,2,0xffffffff,0));
    positive<8>(fixture(RC_RDMA_READ_RESP_LAST,2,0xffffffff,(uint64_t(0xffffffff)+PMTU-1)/PMTU-1));
    positive<9>(fixture(RC_RDMA_READ_RESP_ONLY,2,65,0,0,ap_uint<64>(0xffffffffffffffbfULL)));
    positive<10>(fixture(RC_RDMA_READ_RESP_ONLY,2,66));
    positive<11>(fixture(RC_RDMA_READ_RESP_ONLY,2,67));
    positive<12>(fixture(RC_RDMA_READ_RESP_ONLY,2,64));
    all_syndromes<900>(RC_ACK,1);all_syndromes<901>(RC_RDMA_READ_RESP_ONLY,2);
    all_syndromes<902>(RC_ACK,2,32);negatives();admission_pair();
    std::cout<<std::dec<<"OWNED_RX_EXECUTION {\"pass_test\":true,\"positive_transactions\":"<<transactions
      <<",\"AETH_values\":256,\"AETH_packets\":"<<aeth_packets<<",\"nonpositive_control_packets\":"<<control_packets
      <<",\"negative_cases\":"<<negative_cases<<",\"full_owner_bit_comparisons\":"<<full_owner_bit_comparisons
      <<",\"owner_effect_checks\":"<<checks
      <<",\"full64_native_address\":true,\"full32_WR_length\":true,\"raw_padding_separate_from_DMA_length\":true,\"C_models_only\":true,\"RTL_tested\":false,\"native_DMA_CQ\":false}"<<std::endl;
}
#endif
