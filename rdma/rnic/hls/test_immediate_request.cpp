// SPDX-License-Identifier: BSD-2-Clause-Views
// Actual immediate requester/MSN/PSN/retransmission/timer/receipt consumers.
// Peer parsed headers and memory source/connection are explicit models.
#include <vector>
#define main preceding_request_main
#include "immediate_request_base.hpp"
#undef main

static ap_uint<620> immediate_owner(unsigned seq,unsigned op,unsigned imm) {
    auto n=owner(seq,op==5 ? 3:1);n(339,324)=op;n(619,588)=imm;
    assert(as02_req_owner_valid(n));return n;
}
static txMeta metadata(ap_uint<620> n) {
    ap_uint<192> p=0;p(63,0)=n(243,180);p(127,64)=n(115,52);
    p(159,128)=n(307,276);p(191,160)=n(51,20);
    txMeta m(ibOpCode(unsigned(as02_req_opcode(n))),2,1,1,0,p,1);m.immediate=n(619,588);return m;
}
int main() {
    static_assert(MAX_QPS==8 && META_TABLE_SIZE==2000,"original geometry changed");
    Harness<211> h;h.init();
    hls::stream<net_axis<512>> memory,aeth,reth,raw,assembled;
    auto tick=[&]() {
        h.tick();
        tx_pkg_arbiter<512,211>(h.source_info,memory,aeth,reth,raw);
        append_payload<512,211>(h.packet_info,h.exh_words,aeth,reth,raw,assembled);
    };
    const unsigned values[]={0,0x01234567,0x80000000,0xffffffff};
    unsigned seq=0;
    for(unsigned op:{5,6})for(unsigned imm:values) {
        auto n=immediate_owner(++seq,op,imm);
        h.owners.write(n);h.sq.write(metadata(n));h.dest.write(196);
        for(unsigned j=0;j<100;j++)tick();
        assert(!h.af && !h.mf && !h.tf && !h.jf && h.headers.size()==1 && h.source_cmd.size()==1);
        auto bth=h.headers.read();assert(bth.getOpCode()==as02_req_opcode(n));
        auto source=h.source_cmd.read();assert(source.origin==2 && source.len==65 && source.addr==0xba9876543210ULL);
        net_axis<512> w;w.data=0;for(unsigned b=0;b<64;b++)w.data(b*8+7,b*8)=b^0xa5;
        w.keep=~ap_uint<64>(0);w.last=0;memory.write(w);
        w.data=0x5a;w.keep=1;w.last=1;memory.write(w);
        for(unsigned j=0;j<100;j++)tick();
        std::vector<unsigned char> bytes;
        bool eof=false;
        while(!assembled.empty()) {
            auto v=assembled.read();unsigned count=0;
            for(unsigned b=0;b<64;b++)if(v.keep[b]){assert(!eof);bytes.push_back(unsigned(v.data(b*8+7,b*8)));count++;}
            assert(count && v.keep==((ap_uint<65>(1)<<count)-1));eof=v.last;
        }
        unsigned header=op==5 ? 4:20;
        assert(eof && bytes.size()==header+65 && h.length.size()==1);
        assert(h.length.read()==12+header+65+4);
        if(op==6) {
            const unsigned char prefix[]={0xe2,0x34,0x56,0x78,0x9a,0xbc,0xde,0xf0,
                0x81,0x23,0x45,0x67,0,0,0,65};
            for(unsigned j=0;j<16;j++)assert(bytes[j]==prefix[j]);
        }
        for(unsigned j=0;j<4;j++)assert(bytes[header-4+j]==((imm>>(24-8*j))&255));
        for(unsigned j=0;j<64;j++)assert(bytes[header+j]==(j^0xa5));
        assert(bytes[header+64]==0x5a && h.done.empty());
        h.peer(bth.getPsn(),false);for(unsigned j=0;j<300;j++)tick();
        assert(h.done.size()==1 && !h.af && !h.rf && !h.ef && !h.tf && !h.ff && !h.jf);
        auto done=h.done.read();assert(done.context==n && done.context(619,588)==imm &&
            done.opcode==as02_req_opcode(n) && done.psn==bth.getPsn() && !done.error);
    }
    // A mismatched32-bit notification must fail BEFORE any actual admission,
    // memory read, PSN issue or retransmission record can be committed.
    Harness<212> bad;bad.init();auto n=immediate_owner(1,6,0x81234567);
    auto m=metadata(n);m.immediate=0x81234566;bad.owners.write(n);bad.sq.write(m);bad.ticks(8);
    assert(bad.af && bad.admitted.empty() && bad.local_mem.empty() && bad.headers.empty() && bad.done.empty());
    std::cout<<"IMMEDIATE_REQUEST_HLS {\"pass_test\":true,\"actual_immediate_opcodes\":2,"
        "\"values_per_opcode\":4,\"real_request_retire_receipts\":8,\"full_remote_key_separate\":true,"
        "\"actual_EXH_and_payload_bytes\":true,\"request_context_bits\":620,"
        "\"native_RTL_kernel_or_RX_immediate_verified\":false}"<<std::endl;
    return 0;
}
