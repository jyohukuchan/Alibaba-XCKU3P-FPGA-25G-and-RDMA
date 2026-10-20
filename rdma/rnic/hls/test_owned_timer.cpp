// SPDX-License-Identifier: BSD-2-Clause-Views
// Actual C++ timer array/FSM. Test producers are typed models, NOT native CQ.
#include "ib_transport_protocol/owned_timer.hpp"
#include <cassert>
#include <iostream>
static hls::stream<as02OwnedTimerCtrl> controls;
static hls::stream<as02OwnedTimerTx> starts;
static hls::stream<as02OwnedRetry> retries;
static hls::stream<ap_uint<256>> barriers;
static hls::stream<ap_uint<192>> resumes;
static hls::stream<ap_uint<32>> faults;
static unsigned cycles=0,queries=0;
static void tick(unsigned n=1) {
    for(unsigned i=0;i<n;i++) {as02_owned_transport_timer<47>(controls,starts,retries,barriers,resumes,faults);cycles++;assert(faults.empty());}
}
static ap_uint<248> lease(unsigned index,unsigned generation,ap_uint<24> psn,ap_uint<64> seq) {
    ap_uint<248> r=0;r(15,0)=index;r(79,16)=generation;r(95,80)=7;r(119,96)=psn;
    r(183,120)=ap_uint<64>("0xfedcba9876543210");r(247,184)=seq;return r;
}
static ap_uint<168> owner(ap_uint<248> l) {return l(247,80);}
static void start(ap_uint<248> l,bool retry=false) {starts.write(as02OwnedTimerTx(l,retry));tick(8);}
static ap_uint<256> query(ap_uint<248> l,unsigned status,bool resume=true) {
    as02OwnedTimerCtrl c;c.marker=true;c.owner=owner(l);controls.write(c);tick(12);
    assert(!retries.empty());auto m=retries.read();assert(m.marker && !m.bad);
    assert(as02_owner(m.normal.qpn,m.normal.psn,m.epoch,m.sequence)==owner(l));
    assert(barriers.empty()); // TX marker missing: no snapshot through idleness
    as02OwnedTimerTx t;t.marker=true;t.owner=owner(l);starts.write(t);tick(12);
    assert(!barriers.empty());auto r=barriers.read();assert(r(167,0)==owner(l));
    assert(r(175,168)==status && r[176] && r[215]==(status==2));queries++;
    if(resume) {resumes.write(ap_uint<192>(owner(l)));tick(8);}
    return r;
}
int main() {
    assert(MAX_QPS==8 && TIME_1ms==31250 && AS02_TIMER_CLOCK_PS==4000);
    ap_uint<64> seq=ap_uint<64>("0xe123456789abc001");
    auto a=lease(0,1,0xffffff,seq),b=lease(1,2,0,seq+1);
    start(a);start(b); // appending WR MUST NOT retag the oldest timer
    tick(250100);assert(!retries.empty());
    // Keep the actual old timeout queued while head changes and new work runs.
    controls.write(as02OwnedTimerCtrl(a,b,true,true));tick(8);
    start(a,true);controls.write(as02OwnedTimerCtrl(a,0,false,true));tick(8);
    auto old=retries.read();assert(!old.marker && old.normal.qpn==7 && old.normal.psn==0xffffff);
    assert(old.epoch==a(183,120) && old.sequence==a(247,184));
    auto busy=query(b,2,false);assert(busy[177] && busy[178] && busy(210,179)!=0 && busy(214,211)==0);
    controls.write(as02OwnedTimerCtrl(b,0,false,true));tick(20); // closed window: real stop stays queued
    assert(!controls.empty());resumes.write(ap_uint<192>(owner(b)));tick(12);assert(controls.empty());
    auto clear=query(b,0);assert(!clear[177] && !clear[178] && clear(210,179)==0 && clear(214,211)==0);
    start(b);clear=query(b,0);assert(!clear[177]); // delayed old TX cannot restart retired WR
    auto c=lease(2,3,0xffffff,seq+2);
    controls.write(as02OwnedTimerCtrl(c,0,false,true));starts.write(as02OwnedTimerTx(c,false));tick(16);
    clear=query(c,0);assert(!clear[177]); // actual RX stop BEFORE delayed TX start
    auto d=lease(3,4,0xffffff,seq+3),e=lease(4,5,0,seq+3);
    start(d);start(e);controls.write(as02OwnedTimerCtrl(d,e,true,true));tick(8);
    controls.write(as02OwnedTimerCtrl(d,0,false,true));tick(8); // stale exact old generation/index
    busy=query(e,2);assert(busy[177] && busy[178]);
    controls.write(as02OwnedTimerCtrl(e,0,false,true));tick(8);start(d,true);
    clear=query(e,0);assert(!clear[177]);
    assert(retries.empty() && faults.empty());
    std::cout << std::dec << "{\"pass_test\":true,\"queries\":" << queries
        << ",\"cycles\":" << cycles << ",\"timer_entries\":8,\"TIME_1ms_visits\":31250,"
        "\"old_timeout_identity_held_across_new_head\":true,\"stale_old_controls_do_not_clear_new_head\":true,"
        "\"late_TX_after_retirement_rejected\":true,\"stop_before_TX_race\":true,"
        "\"same_WR_multiple_lease_PSNS\":true,\"whole_core_drain\":false}" << std::endl;
}
