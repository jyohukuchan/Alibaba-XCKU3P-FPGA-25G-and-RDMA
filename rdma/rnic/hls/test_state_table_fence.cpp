// SPDX-License-Identifier: BSD-2-Clause-Views
// Actual derived state-table C++, not a shadow behavioral table.
#include <ap_int.h>
#include <hls_stream.h>
#include <cassert>
#include <cstdint>
#include <iostream>
void as02_state_fence_top(hls::stream<ap_uint<224>>&,hls::stream<ap_uint<224>>&,
    hls::stream<ap_uint<224>>&,hls::stream<ap_uint<80>>&,
    hls::stream<ap_uint<128>>&,hls::stream<ap_uint<128>>&,hls::stream<ap_uint<336>>&);
static hls::stream<ap_uint<224>> rx,tx,qpi;
static hls::stream<ap_uint<80>> rr;
static hls::stream<ap_uint<128>> tr,qr;
static hls::stream<ap_uint<336>> fr;
static unsigned calls=0,queries=0;
static void tick(unsigned n=1){while(n--){as02_state_fence_top(rx,tx,qpi,rr,tr,qr,fr);++calls;}}
static ap_uint<224> request(unsigned q,unsigned a=0,unsigned b=0,unsigned rc=0,
    bool write=false,bool response=false,bool marker=false,uint64_t epoch=0,uint64_t seq=0){
    ap_uint<224> r=0;r(15,0)=q;r(39,16)=a;r(63,40)=b;r(66,64)=rc;
    r[67]=write;r[68]=response;r[69]=marker;r(133,70)=epoch;r(197,134)=seq;return r;
}
static ap_uint<224> marker(unsigned q,unsigned psn,uint64_t e,uint64_t s){return request(q,psn,0,0,false,false,true,e,s);}
static void send(unsigned source,ap_uint<224> m){if(source==0)rx.write(m);else if(source==1)tx.write(m);else qpi.write(m);}
static ap_uint<336> readback(unsigned q,unsigned psn,uint64_t e,uint64_t s,unsigned status){
    for(unsigned i=0;fr.empty() && i<200;i++)tick();assert(!fr.empty());auto r=fr.read();++queries;
    assert(r(15,0)==q && r(39,16)==psn && r(103,40)==e && r(167,104)==s);
    assert(r(175,168)==status && r(179,177)==7 && r(335,321)==0);return r;
}
static ap_uint<336> query(unsigned q,unsigned psn,uint64_t e,uint64_t s,unsigned status,unsigned order=0){
    static const unsigned permutations[6][3]={{0,1,2},{0,2,1},{1,0,2},{1,2,0},{2,0,1},{2,1,0}};
    auto m=marker(q,psn,e,s);send(permutations[order%6][0],m);tick(17);assert(fr.empty());
    send(permutations[order%6][1],m);tick(17);assert(fr.empty());
    send(permutations[order%6][2],m);return readback(q,psn,e,s,status);
}
static void state(ap_uint<336> r,unsigned resp,unsigned old,unsigned next,unsigned unack,unsigned valid,unsigned rc){
    assert(r[176] && r(203,180)==resp && r(227,204)==old && r(251,228)==next &&
        r(275,252)==unack && r(299,276)==valid && r(302,300)==rc);
}
int main(){
    tick(8);auto r=query(7,0xffffff,UINT64_MAX,UINT64_MAX,5);assert(!r[176]);
    for(unsigned q=0;q<8;q++){
        unsigned p=(0xfffffeU+q)&0xffffffU,l=(0x912345U+q)&0xffffffU;
        uint64_t e=0xf123456789abc001ULL+q,s=0xe123456789abc001ULL+q;
        qpi.write(request(q,p,l,0,true));tick(4);
        r=query(q,p,e,s,0,q);state(r,l,l,p,p,p,7);
        tx.write(request(q,(p+1)&0xffffffU,0,0,true));tick(4);
        r=query(q,p,e,s+0x100,2,q+1);state(r,l,l,(p+1)&0xffffffU,p,p,7);
        rx.write(request(q,(p+1)&0xffffffU,0,0,true,true));tick(4);
        rx.write(request(q,(l+1)&0xffffffU,0,q&7,true));tick(4);
        r=query(q,p,e,s+0x200,0,q+2);state(r,(l+1)&0xffffffU,l,(p+1)&0xffffffU,(p+1)&0xffffffU,p,q&7);
        // Original ordinary reads remain actual table consumers/responses.
        rx.write(request(q,0,0,0,false,true));tx.write(request(q));qpi.write(request(q));tick(12);
        assert(!rr.empty() && !tr.empty() && !qr.empty());auto x=rr.read();auto y=tr.read(),z=qr.read();
        assert(x(23,0)==((p+1)&0xffffffU) && x(47,24)==p && x(71,48)==p);
        assert(y==z && y(23,0)==((l+1)&0xffffffU) && y(71,48)==((p+1)&0xffffffU));
    }
    // RX marker cannot certify completion before a late actual TX update and
    // TX marker. A later RX ACK is held BEHIND its marker, not applied early.
    auto m=marker(2,0xffffff,0x923456789abcdef0ULL,0xf23456789abcdef0ULL);
    rx.write(m);rx.write(request(2,77,0,0,true,true));tick(17);assert(fr.empty());
    tx.write(request(2,77,0,0,true));tx.write(m);tick(17);assert(fr.empty());
    qpi.write(m);r=readback(2,0xffffff,0x923456789abcdef0ULL,0xf23456789abcdef0ULL,2);
    assert(r(251,228)==77 && r(275,252)==1);
    tick(8);r=query(2,0,9,10,0);assert(r(251,228)==77 && r(275,252)==77);
    r=query(0xffff,0,9,11,1);assert(!r[176]);
    r=query(2,0,0,12,3);r=query(2,0,9,0,3);
    // A full64-bit sequence mismatch is sticky fault, never a wildcard join.
    rx.write(marker(2,1,9,13));tx.write(marker(2,1,9,13^(1ULL<<63)));qpi.write(marker(2,1,9,13));
    r=readback(2,1,9,13,4);assert(r(304,303)==1 && r(320,305)==2);
    auto bad=marker(2,2,9,14);bad[223]=1;rx.write(bad);tx.write(marker(2,2,9,14));qpi.write(marker(2,2,9,14));
    r=readback(2,2,9,14,4);assert(r(304,303)==0 && r(320,305)==2);
    // Original QPI debug output sets std::hex on this shared ostream.
    // Restore decimal explicitly so machine-readable counts are truthful.
    std::cout<<std::dec<<"{\"pass_test\":true,\"queries\":"<<queries<<",\"table_entries\":8,\"ordered_producers\":3,\"missing_marker_withheld\":true,\"late_TX_and_later_RX_stop_checked\":true,\"whole_core_drain\":false,\"calls\":"<<calls<<"}\n";
}
