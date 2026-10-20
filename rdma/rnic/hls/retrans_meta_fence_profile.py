#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual2000entry metadata commit/readback; NOT active/free/core/CQ proof."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT/'rdma/rnic/build/wrkey-hls-p037tedt/inputs'
META=BASE/'fns/hls/ib_transport_protocol/retransmitter/retransmitter.hpp'
def once(s,a,b):
    if s.count(a)!=1:raise ValueError('metadata anchor changed: '+a)
    return s.replace(a,b,1)
def block(s,a):
    start=s.index(a);left=s.index('{',start);d=1;end=left+1
    while d:
        if s[end]=='{':d+=1
        elif s[end]=='}':d-=1
        end+=1
    return start,left,end

TYPES=r'''
// A record's valid bit is NOT allocator ownership. Original ACK release
// does not erase it. This private snapshot cannot authorize WR/MR/CQ release.
struct as02MetaMsg {
    retransMetaReq normal;
    bool marker,bad;
    ap_uint<16> qpn;ap_uint<24> psn;ap_uint<64> epoch,sequence;
    as02MetaMsg():marker(false),bad(false),qpn(0),psn(0),epoch(0),sequence(0) {
        normal.idx=0;normal.write=false;normal.append=false;
        normal.entry.rkey=0;normal.entry.rkey_valid=0;normal.entry.host=PKG_INT;
        normal.entry.psn=0;normal.entry.next=0;normal.entry.opCode=static_cast<ibOpCode>(0);
        normal.entry.localAddr=0;normal.entry.remoteAddr=0;normal.entry.length=0;
        normal.entry.lst=0;normal.entry.offs=0;normal.entry.valid=false;normal.entry.isTail=false;
    }
};
struct as02MetaReadback {
    as02MetaMsg token;
    ap_uint<8> status;
    bool snapshot_valid;
    retransMetaEntry entry;
    ap_uint<16> failed_idx;
    as02MetaReadback():status(0),snapshot_valid(false),failed_idx(0) {
        entry=token.normal.entry;
    }
};
'''

CONTROL=r'''
    if(pending) {
        if(phase==0) {
            as02MetaReadback out;out.token=token;out.failed_idx=failed_idx;
            if(token.normal.idx<META_TABLE_SIZE && token.qpn<MAX_QPS) {
                out.entry=meta_table[token.normal.idx];out.snapshot_valid=true;
            }
            sampled=out;phase=1;
        } else if(phase==1) {
            if(input_fault)sampled.status=4;
            else if(token.normal.idx>=META_TABLE_SIZE)sampled.status=1;
            else if(token.qpn>=MAX_QPS)sampled.status=2;
            else if(token.epoch==0 || token.sequence==0)sampled.status=3;
            else sampled.status=0; // committed DATA only, NEVER active/free
            phase=2;
        } else if(!readbacks.full()) {
            readbacks.write(sampled);pending=false;phase=0;
        }
    }
    else '''

def derive(original):
    start,_,end=block(original,'void retrans_meta_table(')
    start=original.rfind('template <int INSTID = 0>',0,start)
    if start<0:raise ValueError('metadata template anchor changed')
    f=original[start:end]
    f=once(f,'void retrans_meta_table(','void as02_retrans_meta_fence_consumer(')
    f=once(f,'stream<retransMetaReq>&','stream<as02MetaMsg>&')
    f=once(f,'stream<retransMetaEntry>&\t\tmeta_rsp)',
        'stream<retransMetaEntry>&\t\tmeta_rsp,\n    stream<as02MetaReadback>& readbacks)')
    f=once(f,'\t#pragma HLS DEPENDENCE variable=meta_table inter false',
        '// Real same-index WRITE/APPEND/READ RAW/WAW/WAR dependencies are required.')
    f=once(f,'\tretransMetaReq req;',r'''
    static bool pending=false,input_fault=false;
    static ap_uint<2> phase=0;
    static as02MetaMsg token;
    static as02MetaReadback sampled;
    static ap_uint<16> failed_idx=0;
    static as02MetaMsg work;
    static bool have_work=false;
    bool executing=have_work;
    bool capture_allowed=!pending && (!executing || !work.marker);
    have_work=false;
    retransMetaReq req;
''')
    _,left,end=block(f,'if (!meta_upd_req.empty())')
    _,normal=f[left+1:end-1].split('meta_upd_req.read(req);',1)
    body=r'''
        as02MetaMsg m=work;
        if(m.marker) {
            token=m;pending=true;
            if(m.bad || m.normal.write || m.normal.append) {
                input_fault=true;failed_idx=m.normal.idx;
            }
        } else if(m.bad || m.normal.idx>=META_TABLE_SIZE ||
            (m.normal.write && m.normal.append) ||
            (m.normal.append && m.normal.entry.next>=META_TABLE_SIZE) ||
            (m.normal.write && m.normal.entry.valid && !m.normal.entry.isTail && m.normal.entry.next>=META_TABLE_SIZE)) {
            input_fault=true;failed_idx=m.normal.idx;
        } else {
            req=m.normal;
'''+normal+'\n        }\n'
    f=f[:left+1]+body+f[end-1:]
    f=once(f,'    if (!meta_upd_req.empty())',CONTROL+'if (executing)')
    f=f[:-1]+r'''
    // Register actual requests before range/encoding checks and BRAM
    // accesses. No current-result feedback enters FIFO admission, and a
    // marker dispatch cannot capture a later message in the same call.
    if(capture_allowed && !meta_upd_req.empty()) {
        work=meta_upd_req.read();have_work=true;
    }
}
'''
    # Exact original header remains unselected. Only the explicitly named
    # derivative is instantiated, with original2000entries/clear sweep.
    return original+'\n'+TYPES+'\n'+f+'\n'
