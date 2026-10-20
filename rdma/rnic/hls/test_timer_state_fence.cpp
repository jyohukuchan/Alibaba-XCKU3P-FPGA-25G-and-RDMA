// SPDX-License-Identifier: BSD-2-Clause-Views
// Actual derived timer C++ consumer, not a simulation of a hand-coded model.
#include <ap_int.h>
#include <hls_stream.h>
#include <cassert>
#include <cstdint>
#include <iostream>
void as02_timer_fence_top(hls::stream<ap_uint<176>>&,
    hls::stream<ap_uint<24>>&,hls::stream<ap_uint<40>>&,hls::stream<ap_uint<240>>&);
static hls::stream<ap_uint<176>> rx;
static hls::stream<ap_uint<24>> tx;
static hls::stream<ap_uint<40>> timeout;
static hls::stream<ap_uint<240>> fence;
static unsigned cycles=0,queries=0;
static void tick(unsigned n=1) {
    for(unsigned i=0;i<n;i++) {as02_timer_fence_top(rx,tx,timeout,fence);++cycles;}
}
static ap_uint<176> request(unsigned q,bool stop,bool marker,unsigned psn,
                            uint64_t epoch,uint64_t seq) {
    ap_uint<176> v=0;v(15,0)=q;v[16]=stop;v[17]=marker;v(41,18)=psn;
    v(105,42)=epoch;v(169,106)=seq;return v;
}
static ap_uint<240> reply(unsigned q,unsigned psn,uint64_t epoch,uint64_t seq) {
    for(unsigned i=0;fence.empty() && i<100;i++)tick();
    assert(!fence.empty());ap_uint<240> v=fence.read();++queries;
    assert(v(15,0)==q && v(39,16)==psn && v(103,40)==epoch && v(167,104)==seq);
    assert(v(239,238)==0);return v;
}
static ap_uint<240> query(unsigned q,unsigned psn,uint64_t epoch,uint64_t seq) {
    rx.write(request(q,false,true,psn,epoch,seq));return reply(q,psn,epoch,seq);
}
static unsigned status(ap_uint<240> v){return v(175,168).to_uint();}
static bool active(ap_uint<240> v){return v[177];}
static unsigned time_left(ap_uint<240> v){return v(209,178).to_uint();}
static unsigned retries(ap_uint<240> v){return v(213,210).to_uint();}
static void stop(unsigned q){rx.write(request(q,true,false,0,0,0));tick();}
int main() {
    tick(16);
    for(unsigned q=0;q<8;q++) {
        uint64_t e=0xfedcba9876543210ULL+q,s=0xe123456789abc001ULL+q;
        unsigned psn=(0xfffffeU + q)&0xffffffU;
        tx.write(q);tick();
        auto v=query(q,psn,e,s);
        assert(status(v)==2 && v[176] && active(v));
        assert(time_left(v)>31240 && time_left(v)<=31250 && retries(v)==0);
        stop(q);
        v=query(q,psn,e,s+0x100);
        assert(status(v)==0 && v[176] && !active(v) && time_left(v)==0 && retries(v)==0);
    }
    // A pending TX start is applied before readback; an earlier ACK must not
    // manufacture an inactive certificate while a start waits in its queue.
    stop(2);rx.write(request(2,false,true,0x123456,9,10));tx.write(2);
    auto v=reply(2,0x123456,9,10);
    assert(status(v)==2 && active(v) && time_left(v)>31240);
    // RX update BEHIND a marker cannot overtake it and change its snapshot.
    rx.write(request(2,false,true,0x123457,9,11));
    rx.write(request(2,true,false,0,0,0));
    v=reply(2,0x123457,9,11);assert(status(v)==2 && active(v));
    v=query(2,0x123458,9,12);assert(status(v)==0 && !active(v));
    // Full-width QPN and token validation, never low-bit aliasing.
    v=query(0xffff,0xffffff,UINT64_MAX,UINT64_MAX);
    assert(status(v)==1 && !v[176]);
    v=query(2,0,0,5);assert(status(v)==3);
    v=query(2,0,5,0);assert(status(v)==3);
    // Preserve the REAL 1ms/250MHz/eight-entry timer, not a shortened test.
    tx.write(2);tick();unsigned waited=0;
    while(timeout.empty() && waited<250100) {tick();++waited;}
    assert(!timeout.empty() && waited>=249000);
    auto pending_timeout=timeout.read();assert(pending_timeout(15,0)==2);
    v=query(2,0xfffffe,0x9123456700000001ULL,0xf123456700000001ULL);
    assert(status(v)==2 && !active(v) && time_left(v)==0 && retries(v)==1);
    stop(2);
    v=query(2,0xffffff,0x9123456700000001ULL,0xf123456700000002ULL);
    assert(status(v)==0 && !active(v) && time_left(v)==0 && retries(v)==0);
    // Deliberately retain the pending timeout. Timer-state OK is NOT a whole
    // core-drain proof or a permission to release the WR/MR/CQ.
    assert(pending_timeout(15,0)==2); // held by this explicit downstream model
    // A malformed full24-bit start must fault, NOT index/truncate to QP2.
    tx.write(0x010002);tick();
    v=query(2,1,0x9123456700000001ULL,0xf123456700000003ULL);
    assert(status(v)==4 && v(237,214)==0x010002 && !active(v));
    auto bad=request(2,false,true,2,9,14);bad[175]=1;rx.write(bad);
    v=reply(2,2,9,14);assert(status(v)==4 && v(237,214)==2);
    std::cout<<"{\"pass_test\":true,\"queries\":"<<queries
      <<",\"timer_entries\":8,\"clock_ps\":4000,\"time_1ms_visits\":31250"
      <<",\"actual_timeout_events\":1,\"pending_timeout_intentionally_held\":true"
      <<",\"core_drain_proven\":false,\"cycles\":"<<cycles<<"}\n";
}
