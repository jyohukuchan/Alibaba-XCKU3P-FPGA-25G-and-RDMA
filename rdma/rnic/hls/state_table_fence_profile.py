#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Opt-in REAL state-table consumer with ordered RX/TX/QPI marker rendezvous.

Not a whole-core fence: upstream admission, retry/timer and downstream output
ownership must still be proved independently before WR/MR/CQ retirement.
"""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT/'rdma/rnic/build/wrkey-hls-p037tedt/inputs'
STATE=BASE/'fns/hls/ib_transport_protocol/state_table.hpp'

def once(text,old,new):
    if text.count(old)!=1:raise ValueError('state-table anchor changed: '+old)
    return text.replace(old,new,1)

def block(text,anchor):
    start=text.index(anchor);left=text.index('{',start);depth=1;end=left+1
    while depth:
        if text[end]=='{':depth+=1
        elif text[end]=='}':depth-=1
        end+=1
    return start,left,end

TYPES=r'''
// Private same-queue markers, not public verbs or completion certificates.
struct as02StateReq {
    ap_uint<16> qpn;
    ap_uint<24> a,b;
    ap_uint<3> rc;
    bool write,response,is_fence;
    ap_uint<64> epoch,sequence;
    ap_uint<3> state;
    bool bad;
    as02StateReq():qpn(0),a(0),b(0),rc(0),write(false),response(false),
        is_fence(false),epoch(0),sequence(0),state(0),bad(false) {}
};
struct as02StateReadback {
    ap_uint<16> qpn;
    ap_uint<24> psn;
    ap_uint<64> epoch,sequence;
    ap_uint<8> status;
    bool snapshot_valid;
    ap_uint<3> seen;
    stateTableEntry entry;
    ap_uint<2> failed_source;
    ap_uint<16> failed_qpn;
    as02StateReadback():qpn(0),psn(0),epoch(0),sequence(0),status(0),
      snapshot_valid(false),seen(0),failed_source(0),failed_qpn(0) {
        entry.resp_epsn=0;entry.resp_old_outstanding=0;entry.req_next_psn=0;
        entry.req_old_unack=0;entry.req_old_valid=0;entry.retryCounter=0;
    }
};
static void as02_state_marker(as02StateReq msg,ap_uint<2> source,
    as02StateReq& token,ap_uint<3>& seen,bool& fault,
    ap_uint<2>& failed_source,ap_uint<16>& failed_qpn) {
#pragma HLS inline
    bool mismatch=seen!=0 && (msg.qpn!=token.qpn || msg.a!=token.a ||
        msg.epoch!=token.epoch || msg.sequence!=token.sequence);
    if(seen==0)token=msg;
    seen[source]=1;
    if(msg.bad || msg.write || msg.response || msg.b!=0 || msg.rc!=0 ||
        msg.state!=0 || mismatch) {
        fault=true;failed_source=source;failed_qpn=msg.qpn;
    }
}
'''

RENDEZVOUS=r'''
    // Markers block only their own producer queue. Other queues must apply
    // all preceding normal work and then present the SAME full token. Their
    // empty/idle signals do not stand in for an actual ordered marker.
    if(seen==7) {
        if(phase==0) {
            as02StateReadback out;
            out.qpn=token.qpn;out.psn=token.a;
            out.epoch=token.epoch;out.sequence=token.sequence;out.seen=seen;
            out.failed_source=failed_source;out.failed_qpn=failed_qpn;
            if(token.qpn<MAX_QPS && initialized[token.qpn]) {
                out.snapshot_valid=true;
                out.entry=state_table[token.qpn];
            }
            sampled=out;phase=1;
        } else if(phase==1) {
            if(input_fault)sampled.status=4;
            else if(token.qpn>=MAX_QPS)sampled.status=1;
            else if(token.epoch==0 || token.sequence==0)sampled.status=3;
            else if(!sampled.snapshot_valid)sampled.status=5;
            else if(sampled.entry.req_next_psn!=sampled.entry.req_old_unack)sampled.status=2;
            else sampled.status=0;
            phase=2;
        } else if(!readbacks.full()) {
            readbacks.write(sampled);
            phase=0;seen=0;
        }
    }
    else '''

def derive(original):
    # Keep every original normal table action, constructor and license. Only
    # the consumer function is derived; no original types/tables are edited.
    start,left,end=block(original,'void state_table(\t\t')
    start=original.rfind('template <int INSTID = 0>',0,start)
    if start<0:raise ValueError('state-table template anchor changed')
    function=original[start:end]
    function=once(function,'void state_table(','void as02_state_table_fence_consumer(')
    for old,new in [('hls::stream<rxStateReq>&','hls::stream<as02StateReq>&'),
                    ('hls::stream<txStateReq>&','hls::stream<as02StateReq>&'),
                    ('hls::stream<ifStateReq>&','hls::stream<as02StateReq>&')]:
        function=once(function,old,new)
    function=once(function,'hls::stream<stateTableEntry>& stateTable2qpi_rsp\n)',
        'hls::stream<stateTableEntry>& stateTable2qpi_rsp,\n    hls::stream<as02StateReadback>& readbacks\n)')
    # Only the init bitmap needs reset; the real BRAM table is inaccessible
    # until original QPI initialization populated ALL its fields.
    function=once(function,'\tstatic stateTableEntry state_table[MAX_QPS];',r'''
    static stateTableEntry state_table[MAX_QPS];
    static ap_uint<MAX_QPS> initialized=0;
    static ap_uint<3> seen=0;
    static ap_uint<2> phase=0;
    static as02StateReq token;
    // One elastic dispatch register. Apply OLD pending work before capturing
    // the next request; normal work can still sustain one dispatch/call.
    // Never capture a later request from a producer after its marker.
    static as02StateReq pending;
    static ap_uint<2> pending_source=0;
    static bool have_pending=false;
    static as02StateReadback sampled;
    static bool input_fault=false;
    static ap_uint<2> failed_source=0;
    static ap_uint<16> failed_qpn=0;
#pragma HLS reset variable=state_table off
    bool executing=have_pending;
    ap_uint<3> committed_seen=seen;
    // Normal work can dispatch/capture together without routing today's
    // range/fault/table decisions back into the FIFO read-enable. A marker
    // dispatch does NOT capture any later work in that same call.
    bool capture_allowed=committed_seen!=7 && (!executing || !pending.is_fence);
    have_pending=false;
''')
    branches=[
      ('if (!rxIbh2stateTable_upd_req.empty())','rxIbh2stateTable_upd_req','rxRequest',0,
       'rxRequest.qpn=msg.qpn;rxRequest.epsn=msg.a;rxRequest.retryCounter=msg.rc;rxRequest.write=msg.write;rxRequest.isResponse=msg.response;',True),
      ('else if (!txIbh2stateTable_upd_req.empty())','txIbh2stateTable_upd_req','txRequest',1,
       'txRequest.qpn=msg.qpn;txRequest.psn=msg.a;txRequest.write=msg.write;',True),
      ('else if (!qpi2stateTable_upd_req.empty())','qpi2stateTable_upd_req','ifRequest',2,
       'ifRequest.qpn=msg.qpn;ifRequest.remote_psn=msg.a;ifRequest.local_psn=msg.b;ifRequest.newState=static_cast<qpState>(msg.state.to_uint());ifRequest.write=msg.write;',False)]
    # Reverse order keeps exact original anchors intact during replacement.
    for anchor,stream,req,source,assign,needs_init in reversed(branches):
        a,l,e=block(function,anchor)
        body=function[l+1:e-1]
        prefix,normal=body.split(stream+'.read('+req+');',1)
        guard='msg.bad || msg.qpn>=MAX_QPS'
        if needs_init:guard+=' || !initialized[msg.qpn]'
        else:guard+=' || msg.state>5 || (!msg.write && !initialized[msg.qpn])'
        replacement='''
        as02StateReq msg=pending;
        if(msg.is_fence) {
            as02_state_marker(msg,'''+str(source)+''',token,seen,input_fault,failed_source,failed_qpn);
        } else if('''+guard+''') {
            input_fault=true;failed_source='''+str(source)+''';failed_qpn=msg.qpn;
        } else {
            '''+assign+normal
        if source==2:replacement+='\n            if(msg.write)initialized[msg.qpn]=1;\n'
        replacement+='\n        }\n'
        function=function[:l+1]+replacement+function[e-1:]
        function=once(function,anchor,anchor.replace('!'+stream+'.empty()', 'executing && pending_source=='+str(source)))
    function=once(function,'\n\tif (executing && pending_source==0)',RENDEZVOUS+'if (executing && pending_source==0)')
    capture=r'''
    // No external-quiet heuristic: a marker is itself dispatched in order.
    // The prior request has already executed before this register is reused.
    if(capture_allowed) {
        if(!committed_seen[0] && !rxIbh2stateTable_upd_req.empty()) {
            pending=rxIbh2stateTable_upd_req.read();pending_source=0;have_pending=true;
        } else if(!committed_seen[1] && !txIbh2stateTable_upd_req.empty()) {
            pending=txIbh2stateTable_upd_req.read();pending_source=1;have_pending=true;
        } else if(!committed_seen[2] && !qpi2stateTable_upd_req.empty()) {
            pending=qpi2stateTable_upd_req.read();pending_source=2;have_pending=true;
        }
    }
'''
    function=function[:-1]+capture+'}\n'
    # The original forward declaration remains harmless; no other function
    # definition exists and no original module/profile is selected implicitly.
    return original[:start]+TYPES+'\n'+function+original[end:]
