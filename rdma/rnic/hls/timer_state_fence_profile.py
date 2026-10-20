#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Exact opt-in derivative of the frozen REAL timer consumer, not core drain.

A typed marker follows RX updates in the SAME queue. It drains pending TX
starts, reads the actual eight-entry timer state, and returns the full token.
No arbitrary quiet delay, timer reset/disable, or invented whole-core success.
"""
import hashlib
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT/'rdma/rnic/build/wrkey-hls-p037tedt/inputs'
TIMER=BASE/'fns/hls/ib_transport_protocol/transport_timer.hpp'


def once(text,a,b):
    if text.count(a)!=1:raise ValueError('timer source anchor changed: '+a)
    return text.replace(a,b,1)


def block(text,anchor):
    start=text.index(anchor);left=text.index('{',start);depth=1;right=left+1
    while depth:
        if text[right]=='{':depth+=1
        elif text[right]=='}':depth-=1
        right+=1
    return start,left,right


TYPES=r'''
// AS02 ordered timer-state readback. These are private HLS transactions,
// NOT a CQE or a certificate covering downstream timeout/replay ownership.
struct as02TimerUpdate
{
    ap_uint<16> qpn;
    bool stop;
    bool is_fence;
    ap_uint<24> psn;
    ap_uint<64> epoch;
    ap_uint<64> sequence;
    bool bad_encoding;
    as02TimerUpdate() :qpn(0),stop(false),is_fence(false),psn(0),epoch(0),sequence(0),bad_encoding(false) {}
    as02TimerUpdate(ap_uint<16> q, bool s)
        :qpn(q),stop(s),is_fence(false),psn(0),epoch(0),sequence(0),bad_encoding(false) {}
};
struct as02TimerStateRsp
{
    ap_uint<16> qpn;
    ap_uint<24> psn;
    ap_uint<64> epoch;
    ap_uint<64> sequence;
    ap_uint<8> status;
    bool snapshot_valid;
    bool active;
    ap_uint<32> time;
    ap_uint<4> retries;
    ap_uint<24> failed_qpn;
    as02TimerStateRsp()
        :qpn(0),psn(0),epoch(0),sequence(0),status(0),snapshot_valid(false),
         active(false),time(0),retries(0),failed_qpn(0) {}
};
#if !defined(AS02_TIMER_REGISTER_TABLE)
#error Ordered timer-state proof requires the existing resettable table with REAL RAW dependencies
#endif
'''


def derive(source):
    # Preserve the complete original license and normal timer algorithm.
    start,left,end=block(source,'struct rxTimerUpdate')
    if source[end:end+1]!=';':raise ValueError('timer struct terminator changed')
    source=source[:start]+TYPES+source[end+1:]
    source=source.replace('stream<rxTimerUpdate>','stream<as02TimerUpdate>')
    source=once(source,'static rxTimerUpdate tt_update;','static as02TimerUpdate tt_update;')
    source=once(source,'void transport_timer(','void as02_timer_state_fence_consumer(')
    source=once(source,'stream<retransmission>&\ttimer2retrans_req\n)',
        'stream<retransmission>&\ttimer2retrans_req,\n    stream<as02TimerStateRsp>& fence_rsp\n)')
    # Extract the actual TX-start branch, including its original backoff tiers.
    ts,tl,te=block(source,'else if (!txSetTimer_req.empty())')
    tx_body=source[tl+1:te-1]
    before,after=tx_body.split('txSetTimer_req.read(setQP);',1)
    guarded_tx=before+'txSetTimer_req.read(setQP);'+r'''
        if(setQP>=MAX_QPS) {input_fault=true;failed_qpn=setQP;}
        else {
'''+after+'\n        }\n'
    source=source[:tl+1]+guarded_tx+source[te-1:]
    rs,rl,re=block(source,'if (!rxClearTimer_req.empty())')
    rx_body=source[rl+1:re-1];before,after=rx_body.split('rxClearTimer_req.read(tt_update);',1)
    guarded_rx=before+'rxClearTimer_req.read(tt_update);'+r'''
        if(tt_update.bad_encoding) {input_fault=true;failed_qpn=tt_update.qpn;}
        if(tt_update.is_fence) {
            fence_request=tt_update;
            fence_pending=true;
        } else if(tt_update.qpn>=MAX_QPS || tt_update.bad_encoding) {
            input_fault=true;failed_qpn=tt_update.qpn;
        } else {
'''+after+'\n        }\n'
    source=source[:rl+1]+guarded_rx+source[re-1:]
    pending=r'''
    // SAME-RX-queue marker cannot overtake earlier ACK/stop updates. While
    // pending, do not consume RX updates behind it. Pending TX starts are
    // actually applied BEFORE readback: a late/stale start yields BUSY,
    // never a fabricated inactive state. Upstream/downstream core fences
    // and closed producer admission remain separate required integration.
    if(fence_pending) {
        if(!txSetTimer_req.empty()) {
TX_BODY
            fence_phase=0; // a late real start invalidates any old snapshot
        } else if(fence_phase==0) {
            as02TimerStateRsp out;
            out.qpn=fence_request.qpn;out.psn=fence_request.psn;
            out.epoch=fence_request.epoch;out.sequence=fence_request.sequence;
            out.failed_qpn=failed_qpn;
            if(fence_request.qpn<MAX_QPS) {
                // Return DATA from the real table; not a fixed-delay boolean.
                transportTimerEntry observed=transportTimerTable[fence_request.qpn];
                out.snapshot_valid=true;out.active=observed.active;
                out.time=observed.time;out.retries=observed.retries;
            }
            // Real sequential boundary: table mux and state classification
            // must not share one long combinational response path.
            fence_observed=out;
            fence_phase=1;
        } else if(fence_phase==1) {
            if(input_fault)fence_observed.status=4;
            else if(fence_request.qpn>=MAX_QPS)fence_observed.status=1;
            else if(fence_request.epoch==0 || fence_request.sequence==0)fence_observed.status=3;
            else if(fence_observed.active || fence_observed.time!=0 || fence_observed.retries!=0)fence_observed.status=2;
            else fence_observed.status=0;
            fence_phase=2;
        } else if(!fence_rsp.full()) {
            fence_rsp.write(fence_observed);
            fence_pending=false;
            fence_phase=0;
        }
    }
    else '''
    pending=pending.replace('TX_BODY',guarded_tx)
    source=once(source,'\n\tif (!rxClearTimer_req.empty())',pending+'if (!rxClearTimer_req.empty())')
    source=once(source,'\tstatic bool tt_WaitForWrite = false;',r'''
    static bool tt_WaitForWrite = false;
    static bool fence_pending=false;
    static as02TimerUpdate fence_request;
    static ap_uint<2> fence_phase=0;
    static as02TimerStateRsp fence_observed;
    static bool input_fault=false;
    static ap_uint<24> failed_qpn=0;
''')
    return source


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
