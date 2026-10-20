// SPDX-License-Identifier: BSD-2-Clause-Views
// Real full2000entry metadata consumer, not active/free ownership model.
#include <ap_int.h>
#include <hls_stream.h>
#include <cassert>
#include <cstdint>
#include <iostream>
#include "ib_transport_protocol/retransmitter/retrans_meta_fence.hpp"
void as02_meta_fence_top(hls::stream<ap_uint<480>>&,hls::stream<ap_uint<288>>&,hls::stream<ap_uint<512>>&);
void meta_decode(hls::stream<ap_uint<480>>&,hls::stream<as02MetaMsg>&);
void meta_normal_encode(hls::stream<retransMetaEntry>&,hls::stream<ap_uint<288>>&);
static hls::stream<ap_uint<480>> input;
static hls::stream<ap_uint<288>> normal;
static hls::stream<ap_uint<512>> fence;
static unsigned calls=0,queries=0,reads=0;
static void tick(unsigned n=1){while(n--){as02_meta_fence_top(input,normal,fence);++calls;}}
static ap_uint<273> pattern(unsigned idx){
    ap_uint<273> d=0;d(31,0)=idx==0?0U:(0xfedcba98U^idx);d[32]=1;d[33]=1;
    d(57,34)=(0xfffffeU+idx)&0xffffffU;d(73,58)=(idx+1)%2000;d(105,74)=10;
    d(169,106)=0xfedcba9876543210ULL+idx;d(233,170)=0x9123456789abcdefULL+idx;
    d(265,234)=0xf1234567U+idx;d[266]=idx&1;d(270,267)=idx&15;d[271]=1;d[272]=1;return d;
}
static ap_uint<480> request(unsigned idx,bool wr=false,bool append=false,ap_uint<273> d=0){
    ap_uint<480> m=0;m(15,0)=idx;m[16]=wr;m[17]=append;m(459,187)=d;return m;
}
static ap_uint<480> marker(unsigned idx,unsigned q,unsigned psn,uint64_t e,uint64_t s){
    auto m=request(idx);m[18]=1;m(34,19)=q;m(58,35)=psn;m(122,59)=e;m(186,123)=s;return m;
}
static ap_uint<512> reply(unsigned idx,unsigned q,unsigned p,uint64_t e,uint64_t s,unsigned status){
    for(unsigned i=0;fence.empty()&&i<5000;i++)tick();assert(!fence.empty());auto r=fence.read();++queries;
    assert(r(15,0)==idx && r(31,16)==q && r(55,32)==p && r(119,56)==e && r(183,120)==s);
    assert(r(191,184)==status && r(511,482)==0);return r;
}
static ap_uint<512> query(unsigned idx,unsigned q,unsigned p,uint64_t e,uint64_t s,unsigned status){
    input.write(marker(idx,q,p,e,s));return reply(idx,q,p,e,s,status);
}
static ap_uint<288> read(unsigned idx){
    input.write(request(idx));for(unsigned i=0;normal.empty()&&i<5000;i++)tick();assert(!normal.empty());++reads;return normal.read();
}
static void data(ap_uint<512> r,ap_uint<273> expected){assert(r[192] && r(465,193)==expected);}
static void codec_check(){
    // Inspect actual typed fields independently, not only an encode/decode
    // roundtrip which could hide two symmetric field-swapping mistakes.
    hls::stream<ap_uint<480>> raw;hls::stream<as02MetaMsg> typed;
    hls::stream<retransMetaEntry> entries;hls::stream<ap_uint<288>> words;
    for(unsigned idx:{0U,1999U}){
        raw.write(request(idx,true,false,pattern(idx)));
        for(unsigned n=0;typed.empty()&&n<20;n++)meta_decode(raw,typed);
        assert(!typed.empty());auto m=typed.read();assert(m.normal.idx==idx && m.normal.write && !m.bad && !m.marker);
        auto e=m.normal.entry;
        assert(e.rkey==(idx==0?0U:(0xfedcba98U^idx)) && e.rkey_valid==1 && e.host==PKG_HOST);
        assert(e.psn==((0xfffffeU+idx)&0xffffffU) && e.next==(idx+1)%2000 && e.opCode==RC_RDMA_WRITE_ONLY);
        assert(e.localAddr==0xfedcba9876543210ULL+idx && e.remoteAddr==0x9123456789abcdefULL+idx);
        assert(e.length==0xf1234567U+idx && e.lst==(idx&1) && e.offs==(idx&15) && e.valid && e.isTail);
        retransMetaEntry independent;
        independent.rkey=idx==0?0U:(0xfedcba98U^idx);independent.rkey_valid=1;independent.host=PKG_HOST;
        independent.psn=(0xfffffeU+idx)&0xffffffU;independent.next=(idx+1)%2000;independent.opCode=RC_RDMA_WRITE_ONLY;
        independent.localAddr=0xfedcba9876543210ULL+idx;independent.remoteAddr=0x9123456789abcdefULL+idx;
        independent.length=0xf1234567U+idx;independent.lst=idx&1;independent.offs=idx&15;independent.valid=true;independent.isTail=true;
        entries.write(independent);meta_normal_encode(entries,words);assert(!words.empty() && words.read()==ap_uint<288>(pattern(idx)));
    }
    auto invalid=pattern(0);invalid(105,74)=0xffffffffU;raw.write(request(0,true,false,invalid));
    for(unsigned n=0;typed.empty()&&n<20;n++)meta_decode(raw,typed);
    assert(!typed.empty());auto m=typed.read();assert(m.bad && static_cast<unsigned>(m.normal.entry.opCode)==0);
    meta_decode(raw,typed);assert(raw.empty() && typed.empty());
}
int main(){
    codec_check();
    auto r=query(1999,7,0xffffff,UINT64_MAX,UINT64_MAX,0);data(r,0);assert(calls>=2000);
    // ALL actual2000entries, not a reduced-capacity representative subset.
    for(unsigned idx=0;idx<2000;idx++)assert(read(idx)==0);
    const unsigned indices[]={0,1,1023,1998,1999};
    for(unsigned idx:indices){
        auto d=pattern(idx);uint64_t e=0xf123456789abc001ULL+idx,s=0xe123456789abc001ULL+idx;
        input.write(request(idx,true,false,d));r=query(idx,idx%8,0xffffff,e,s,0);data(r,d);
        // Consecutive same-index append/read/marker must observe real RAW /
        // WAW behavior; selected derivative removes false DEPENDENCE pragma.
        ap_uint<273> append=0;append(73,58)=(idx+17)%2000;
        input.write(request(idx,false,true,append));input.write(request(idx));
        r=query(idx,idx%8,0,e,s+1,0);d(73,58)=(idx+17)%2000;d[272]=0;data(r,d);
        assert(!normal.empty());auto held=normal.read();++reads;assert(held(272,0)==d && held(287,273)==0);
        // The record can be valid while commit-status OK; allocator/free /
        // process/event ownership is emphatically NOT inferred from valid.
        assert(r[192] && r[193+271]);
    }
    auto a=pattern(2),b=pattern(3);input.write(request(2,true,false,a));
    input.write(marker(2,2,0x123456,9,10));input.write(request(2,true,false,b));
    r=reply(2,2,0x123456,9,10,0);data(r,a);r=query(2,2,0x123457,9,11,0);data(r,b);
    r=query(2000,2,0,9,12,1);assert(!r[192]);r=query(0xffff,2,0,9,13,1);assert(!r[192]);
    r=query(2,0xffff,0,9,14,2);assert(!r[192]);r=query(2,2,0,0,15,3);r=query(2,2,0,9,0,3);
    input.write(request(0xffff,true,false,pattern(0)));r=query(2,2,1,9,16,4);assert(r(481,466)==0xffff);data(r,b);
    ap_uint<273> bad=0;bad(73,58)=2000;input.write(request(0,false,true,bad));
    r=query(0,0,2,9,17,4);assert(r(481,466)==0);auto expected=pattern(0);expected(73,58)=17;expected[272]=0;data(r,expected);
    bad=pattern(0);bad[272]=0;bad(73,58)=2000;input.write(request(0,true,false,bad));
    r=query(0,0,3,9,18,4);data(r,expected);
    bad=pattern(0);bad(105,74)=0xffffffffU;input.write(request(0,true,false,bad));r=query(0,0,4,9,19,4);data(r,expected);
    auto m=marker(0,0,5,9,20);m[479]=1;input.write(m);r=reply(0,0,5,9,20,4);data(r,expected);
    std::cout<<std::dec<<"{\"pass_test\":true,\"queries\":"<<queries<<",\"normal_reads\":"<<reads
      <<",\"metadata_entries\":2000,\"all_entries_zero_checked\":true,\"actual_same_index_RAW\":true,\"independent_typed_codec_checks\":3,\"valid_data_with_commit_OK\":true,\"whole_core_drain\":false,\"calls\":"<<calls<<"}\n";
}
