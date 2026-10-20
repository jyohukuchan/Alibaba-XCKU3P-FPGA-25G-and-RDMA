// SPDX-License-Identifier: BSD-2-Clause-Views
#include <ap_int.h>
#include <hls_stream.h>
#include <cassert>
#include <cstdint>
#include <iostream>
void as02_pointer_fence_top(hls::stream<ap_uint<224>>&,hls::stream<ap_uint<224>>&,
    hls::stream<ap_uint<40>>&,hls::stream<ap_uint<288>>&);
static hls::stream<ap_uint<224>> req,upd;
static hls::stream<ap_uint<40>> normal;
static hls::stream<ap_uint<288>> fence;
static unsigned calls=0,queries=0;
static void tick(unsigned n=1){while(n--){as02_pointer_fence_top(req,upd,normal,fence);++calls;}}
static ap_uint<224> request(unsigned q,bool lock=false){ap_uint<224> m=0;m(15,0)=q;m[49]=lock;return m;}
static ap_uint<224> update(unsigned q,unsigned h,unsigned t,bool valid){auto m=request(q);m(31,16)=h;m(47,32)=t;m[48]=valid;return m;}
static ap_uint<224> marker(unsigned q,unsigned p,uint64_t e,uint64_t s){auto m=request(q);m[50]=1;m(74,51)=p;m(138,75)=e;m(202,139)=s;return m;}
static ap_uint<288> reply(unsigned q,unsigned p,uint64_t e,uint64_t s,unsigned status){
    for(unsigned i=0;fence.empty()&&i<200;i++)tick();assert(!fence.empty());auto r=fence.read();++queries;
    assert(r(15,0)==q && r(39,16)==p && r(103,40)==e && r(167,104)==s && r(175,168)==status);
    assert(r(177,176)==3 && r(287,263)==0);return r;
}
static ap_uint<288> query(unsigned q,unsigned p,uint64_t e,uint64_t s,unsigned status,bool reverse=false){
    auto m=marker(q,p,e,s);if(reverse)upd.write(m);else req.write(m);
    tick(17);assert(fence.empty());if(reverse)req.write(m);else upd.write(m);return reply(q,p,e,s,status);
}
static void entry(ap_uint<288> r,unsigned h,unsigned t,bool valid,bool locked=false,unsigned lockq=0){
    assert(r[178] && r(194,179)==h && r(210,195)==t && r[211]==valid && r[212]==locked && !r[213]);
    assert(r(229,214)==lockq && r(245,230)==0);
}
static ap_uint<40> normal_reply(){for(unsigned i=0;normal.empty()&&i<200;i++)tick();assert(!normal.empty());return normal.read();}
int main(){
    // Inputs may queue during real eight-entry BRAM initialization, never
    // return an invented data snapshot before the actual writes completed.
    auto r=query(7,0xffffff,UINT64_MAX,UINT64_MAX,0);entry(r,0,0,false);
    for(unsigned q=0;q<8;q++){
        unsigned p=(0xfffffeU+q)&0xffffffU;uint64_t e=0xf123456789abc001ULL+q,s=0xe123456789abc001ULL+q;
        r=query(q,p,e,s,0,q&1);entry(r,0,0,false);
        upd.write(update(q,1999,1999-q,true));tick(4);req.write(request(q,true));
        auto n=normal_reply();assert(n(15,0)==1999 && n(31,16)==1999-q && n[32]);
        r=query(q,p,e,s+0x100,2,q&1);entry(r,1999,1999-q,true,true,q);
        upd.write(update(q,1999,1999-q,false));tick(4);
        r=query(q,p,e,s+0x200,0,q&1);entry(r,1999,1999-q,false);
    }
    req.write(request(2,true));normal_reply();
    req.write(request(3,true));tick(17);assert(normal.empty());
    auto m=marker(3,0xffffff,0x9123456789abcdefULL,0xf123456789abcdefULL);
    req.write(m);tick(17);assert(fence.empty());
    // Earlier waiting lock request MUST finish through the actual update /
    // wait branch before the marker behind it can be consumed.
    upd.write(update(2,1999,1997,false));upd.write(m);
    r=reply(3,0xffffff,0x9123456789abcdefULL,0xf123456789abcdefULL,2);entry(r,1999,1996,false,true,3);
    assert(!normal.empty());
    upd.write(update(3,1999,1996,false));tick(4);r=query(3,0,9,10,0);entry(r,1999,1996,false);
    // Actual normal response is deliberately retained downstream. State OK
    // does NOT prove metadata/free-list/event/output or whole-core drain.
    assert(!normal.empty());auto held=normal.read();assert(held(15,0)==1999 && !held[32]);
    req.write(request(2));tick(8);r=query(2,0,9,11,0);assert(!normal.empty());normal_reply();
    r=query(0xffff,0,9,12,1);assert(!r[178]);r=query(2,0,0,13,3);r=query(2,0,9,0,3);
    upd.write(update(2,2000,1999,true));tick(4);r=query(2,1,9,14,4);entry(r,1999,1997,false);
    assert(r[246] && r(262,247)==2);
    req.write(request(0xffff));tick(4);r=query(2,2,9,15,4);assert(!r[246] && r(262,247)==0xffff);
    req.write(marker(2,3,9,16));tick(17);upd.write(marker(2,3,9,16^(1ULL<<63)));
    r=reply(2,3,9,16,4);assert(r[246] && r(262,247)==2);
    auto bad=marker(2,4,9,17);bad[223]=1;req.write(bad);tick(17);upd.write(marker(2,4,9,17));
    r=reply(2,4,9,17,4);assert(!r[246] && r(262,247)==2);
    std::cout<<std::dec<<"{\"pass_test\":true,\"queries\":"<<queries<<",\"table_entries\":8,\"metadata_capacity\":2000,\"ordered_producers\":2,\"actual_lock_wait_release_checked\":true,\"normal_response_held_after_pointer_OK\":true,\"whole_core_drain\":false,\"calls\":"<<calls<<"}\n";
}
