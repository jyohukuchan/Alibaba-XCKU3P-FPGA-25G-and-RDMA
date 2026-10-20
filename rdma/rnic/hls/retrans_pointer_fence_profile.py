#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual retransmission pointer/lock consumer, NOT full retrans/core drain."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT/'rdma/rnic/build/wrkey-hls-p037tedt/inputs'
POINTER=BASE/'fns/hls/ib_transport_protocol/retransmitter/retransmitter.hpp'

def once(s,a,b):
    if s.count(a)!=1:raise ValueError('pointer anchor changed: '+a)
    return s.replace(a,b,1)

def block(s,a):
    start=s.index(a);left=s.index('{',start);d=1;end=left+1
    while d:
        if s[end]=='{':d+=1
        elif s[end]=='}':d-=1
        end+=1
    return start,left,end

TYPES=r'''
// Ordered internal markers. No CQ/WR/MR retirement authority.
struct as02PointerMsg {
    ap_uint<16> qpn,head,tail;
    bool valid,lock,marker;
    ap_uint<24> psn;
    ap_uint<64> epoch,sequence;
    bool bad;
    as02PointerMsg():qpn(0),head(0),tail(0),valid(false),lock(false),marker(false),
        psn(0),epoch(0),sequence(0),bad(false) {}
};
struct as02PointerReadback {
    ap_uint<16> qpn;ap_uint<24> psn;ap_uint<64> epoch,sequence;
    ap_uint<8> status;ap_uint<2> seen;
    bool snapshot_valid;
    retransPointerEntry entry;
    bool locked,waiting;
    ap_uint<16> locked_qpn,waiting_qpn;
    bool failed_source;ap_uint<16> failed_qpn;
    as02PointerReadback():qpn(0),psn(0),epoch(0),sequence(0),status(0),seen(0),
      snapshot_valid(false),locked(false),waiting(false),locked_qpn(0),waiting_qpn(0),failed_source(false),failed_qpn(0) {
        entry.head=0;entry.tail=0;entry.valid=false;
    }
};
static void as02_pointer_marker(as02PointerMsg m,bool source,
    as02PointerMsg& token,ap_uint<2>& seen,bool& fault,bool& failed_source,ap_uint<16>& failed_qpn) {
#pragma HLS inline
    bool mismatch=seen!=0 && (m.qpn!=token.qpn || m.psn!=token.psn || m.epoch!=token.epoch || m.sequence!=token.sequence);
    if(seen==0)token=m;
    seen[source]=1;
    if(m.bad || m.head!=0 || m.tail!=0 || m.valid || m.lock || mismatch) {
        fault=true;failed_source=source;failed_qpn=m.qpn;
    }
}
'''

CONTROL=r'''
    // Real addressed initialization, not a fixed quiet-time completion.
    // No request is consumed until ALL original eight entries were cleared.
    if(!clear_complete) {
        retransPointerEntry zero;zero.head=0;zero.tail=0;zero.valid=false;
        ptr_table[clear_index]=zero;
        if(clear_index==MAX_QPS-1)clear_complete=true;
        else clear_index++;
        return;
    }
    if(marker_pending) {
        as02_pointer_marker(pending_marker,marker_source,token,seen,input_fault,failed_source,failed_qpn);
        marker_pending=false;
    } else if(seen==3) {
        if(phase==0) {
            as02PointerReadback out;
            out.qpn=token.qpn;out.psn=token.psn;out.epoch=token.epoch;out.sequence=token.sequence;out.seen=seen;
            out.failed_source=failed_source;out.failed_qpn=failed_qpn;
            if(token.qpn<MAX_QPS) {out.entry=ptr_table[token.qpn];out.snapshot_valid=true;}
            out.locked=pt_isLocked;out.waiting=pt_wait;
            if(pt_isLocked)out.locked_qpn=pt_lockedQP;
            if(pt_wait)out.waiting_qpn=pt_req.qpn;
            sampled=out;phase=1;
        } else if(phase==1) {
            if(input_fault)sampled.status=4;
            else if(token.qpn>=MAX_QPS)sampled.status=1;
            else if(token.epoch==0 || token.sequence==0)sampled.status=3;
            else if(sampled.entry.valid || sampled.locked || sampled.waiting)sampled.status=2;
            else sampled.status=0;
            phase=2;
        } else if(!readbacks.full()) {
            readbacks.write(sampled);seen=0;phase=0;
        }
    } else '''

def derive(original):
    start,_,end=block(original,'void retrans_pointer_table(')
    start=original.rfind('template <int INSTID = 0>',0,start)
    if start<0:raise ValueError('pointer template anchor changed')
    f=original[start:end]
    f=once(f,'void retrans_pointer_table(','void as02_retrans_pointer_fence_consumer(')
    f=once(f,'stream<pointerReq>&','stream<as02PointerMsg>&')
    f=once(f,'stream<pointerUpdate>&','stream<as02PointerMsg>&')
    f=once(f,'stream<retransPointerEntry>& \tpointerRspFifo)',
        'stream<retransPointerEntry>& \tpointerRspFifo,\n    stream<as02PointerReadback>& readbacks)')
    f=once(f,'static retransPointerEntry ptr_table[MAX_QPS];',r'''
    static retransPointerEntry ptr_table[MAX_QPS];
#pragma HLS reset variable=ptr_table off
    static ap_uint<16> clear_index=0;
    static bool clear_complete=false;
    static ap_uint<2> seen=0,phase=0;
    static as02PointerMsg token,pending_marker;
    static bool marker_pending=false,marker_source=false;
    static bool input_fault=false,failed_source=false;
    static ap_uint<16> failed_qpn=0;
    static as02PointerReadback sampled;
    static as02PointerMsg pending_update;
    static bool update_pending=false;
    bool executing_update=update_pending;
    bool capture_update=clear_complete && !seen[1] && !marker_pending &&
        (!executing_update || !pending_update.marker);
    update_pending=false;
''')
    f=once(f,'static ap_uint<16> pt_lockedQP;','static ap_uint<16> pt_lockedQP=0;')
    branches=[('if (!pointerUpdFifo.empty())','pointerUpdFifo','upd',1,
        'm.bad || m.qpn>=MAX_QPS || m.lock || (m.valid && (m.head>=META_TABLE_SIZE || m.tail>=META_TABLE_SIZE))',
        'upd.qpn=m.qpn;upd.entry.head=m.head;upd.entry.tail=m.tail;upd.entry.valid=m.valid;'),
      ('else if (!pointerReqFifo.empty() && !pt_wait)','pointerReqFifo','pt_req',0,
        'm.bad || m.qpn>=MAX_QPS || m.head!=0 || m.tail!=0 || m.valid',
        'pt_req.qpn=m.qpn;pt_req.lock=m.lock;')]
    for anchor,stream,req,source,guard,assign in reversed(branches):
        _,left,end=block(f,anchor);body=f[left+1:end-1]
        _,normal=body.split(stream+'.read('+req+');',1)
        new='''
        as02PointerMsg m='''+stream+'''.read();
        if(m.marker) {
            pending_marker=m;marker_source='''+str(source)+''';marker_pending=true;
        } else if('''+guard+''') {
            input_fault=true;failed_source='''+str(source)+''';failed_qpn=m.qpn;
        } else {
            '''+assign+normal+'\n        }\n'
        f=f[:left+1]+new+f[end-1:]
        f=once(f,anchor,anchor.replace('!'+stream+'.empty()','!seen['+str(source)+'] && !'+stream+'.empty()'))
    # The ordinary update data/guard -> BRAM write path needs a real register.
    # Preserve update priority, including when an update is queued but has
    # not entered that register yet. Never let a request/wait path overtake it.
    f=once(f,'as02PointerMsg m=pointerUpdFifo.read();','as02PointerMsg m=pending_update;')
    f=once(f,'\n\tif (!seen[1] && !pointerUpdFifo.empty())',CONTROL+'if (!seen[1] && executing_update)')
    f=once(f,'\telse if (!seen[0] && !pointerReqFifo.empty() && !pt_wait)',r'''
    else if(!seen[1] && !pointerUpdFifo.empty()) {
        // Actual earlier update captures below; do not overtake it.
    }
    else if (!seen[0] && !pointerReqFifo.empty() && !pt_wait)''')
    f=f[:-1]+r'''
    if(capture_update && !pointerUpdFifo.empty()) {
        pending_update=pointerUpdFifo.read();update_pending=true;
    }
}
'''
    # Keep original header/functions unmodified and unselected. Instantiate
    # ONLY the derivative in the explicit isolated top; no duplicate table.
    return original+'\n'+TYPES+'\n'+f+'\n'
