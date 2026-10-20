#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Opt-in FNS retransmission process with real external pool leases.

Preserves the complete licensed frozen header as an unselected prefix.
The selected process retains original pointer/list/READ/retry actions, but
never recycles a bare index. NOT a producer fence, CQ or whole-core drain.
"""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT/'rdma/rnic/build/wrkey-hls-p037tedt/inputs'
META=BASE/'fns/hls/ib_transport_protocol/retransmitter/retransmitter.hpp'

def once(s,a,b):
    if s.count(a)!=1:raise ValueError('owned retransmission anchor changed: '+a)
    return s.replace(a,b,1)

def block(s,a):
    start=s.index(a);left=s.index('{',start);d=1;end=left+1
    while d:
        if s[end]=='{':d+=1
        elif s[end]=='}':d-=1
        end+=1
    return start,left,end

TYPES=r'''
struct as02OwnedInsert { retransEntry normal; ap_uint<64> epoch,sequence; bool bad; };
struct as02OwnedUpdate { retransUpdate normal; ap_uint<64> epoch,sequence; bool bad; };
struct as02OwnedRetry { retransmission normal; ap_uint<64> epoch,sequence; bool bad; };
struct as02OwnedEvent {
    retransEvent normal;ap_uint<248> lease;
    as02OwnedEvent() {}
    as02OwnedEvent(retransEvent n,ap_uint<248> l):normal(n),lease(l) {}
};
struct as02OwnedRdInit {
    retransRdInit normal;ap_uint<248> lease;
    as02OwnedRdInit() {}
    as02OwnedRdInit(retransRdInit n,ap_uint<248> l):normal(n),lease(l) {}
};
inline ap_uint<168> as02_owner(ap_uint<16> qpn,ap_uint<24> psn,ap_uint<64> epoch,ap_uint<64> seq) {
    ap_uint<168> r=0;r(15,0)=qpn;r(39,16)=psn;r(103,40)=epoch;r(167,104)=seq;return r;
}
inline bool as02_owner_valid(ap_uint<16> qpn,ap_uint<64> epoch,ap_uint<64> seq) {
    return qpn<MAX_QPS && epoch!=0 && seq!=0;
}
inline bool as02_wr_matches(ap_uint<248> lease,ap_uint<16> qpn,ap_uint<64> epoch,ap_uint<64> seq) {
    return lease(79,16)!=0 && lease(95,80)==qpn && lease(183,120)==epoch && lease(247,184)==seq;
}
'''

PROCESS=r'''
// Derived from process_retransmissions in the retained licensed prefix.
// Deliberate changes: trusted full WR context; real offer/return handshakes;
// immutable lease retained through mutable READ PSNs; fail-closed guards.
template <int INSTID=0>
void as02_process_owned_retransmissions(
    stream<as02OwnedUpdate>& updates,stream<as02OwnedRdInit>& rdinit,
    stream<as02OwnedRetry>& rx_retry,stream<as02OwnedRetry>& timer_retry,
    stream<as02OwnedInsert>& inserts,
    stream<pointerReq>& preq,stream<pointerUpdate>& pupd,stream<retransPointerEntry>& prsp,
    stream<as02OwnedMetaReq>& mreq,stream<as02OwnedMetaEntry>& mrsp,
    stream<ap_uint<192>>& alloc_req,stream<ap_uint<256>>& alloc_rsp,
    stream<ap_uint<256>>& release_req,stream<ap_uint<256>>& release_rsp,
    stream<as02OwnedEvent>& events,
    ap_uint<12> credit,bool pool_initialized,bool pool_fault_in,
    stream<ap_uint<32>>& pointer_faults,stream<ap_uint<32>>& metadata_faults,
    ap_uint<32>& fault,ap_uint<8>& phase,
    ap_uint<32>& inserted,ap_uint<32>& released,ap_uint<32>& partial) {
#pragma HLS pipeline II=1
#pragma HLS inline off
    enum State {MAIN,UPDATE_START,RETRY_START,ALLOC_START,ALLOC_WAIT,ALLOC_CHECK,
        INSERT_0,INSERT_1,UPDATE_0,UPDATE_1,UPDATE_CHECK,RELEASE_WAIT,RELEASE_CHECK,
        RETRANS_0,RETRANS_1,RETRANS_2,RETRANS_CHECK,TIMER_RETRANS_0};
    static State state=MAIN;
    static as02OwnedInsert insert;
    static as02OwnedUpdate update;
    static as02OwnedRetry retry;
    static as02OwnedMetaEntry meta;
    static ap_uint<256> reply=0;
    static bool timer_request=false,seeking=false;
    static retransPointerEntry ptr;
    static ap_uint<16> curr=0,new_index=0;
    static ap_uint<248> new_lease=0,return_lease=0;
    static ap_uint<32> error=0,ninsert=0,nrelease=0,npartial=0;
    fault=error;phase=state;inserted=ninsert;released=nrelease;partial=npartial;
    if(error!=0)return; // quarantine; never fabricate retirement/CQ/unpin
    // Separate persistent-state dispatch from current fault classification.
    // A fault still prevents ALL normal side effects in this invocation.
    // Avoid a chain of current FIFO-dependent error assignments feeding the
    // entire switch through a new-error mux and a second zero comparison.
    if(pool_fault_in || !pointer_faults.empty() || !metadata_faults.empty()) {
        if(!pointer_faults.empty())pointer_faults.read();
        if(!metadata_faults.empty())metadata_faults.read();
        error=1;return;
    }
    switch(state) {
    case MAIN:
        if(!updates.empty()) {
            update=updates.read();state=UPDATE_START;
        } else if(!rx_retry.empty()) {
            retry=rx_retry.read();timer_request=false;state=RETRY_START;
        } else if(!timer_retry.empty()) {
            retry=timer_retry.read();timer_request=true;state=RETRY_START;
        } else if(pool_initialized && credit!=0 && !inserts.empty()) {
            // This process is the sole real allocation-request producer.
            // Do NOT start an unfillable request at credit0: ACKs must run
            // in MAIN to return the slots that will allow the next insert.
            insert=inserts.read();state=ALLOC_START;
        }
        break;
    case UPDATE_START:
        if(update.bad || !as02_owner_valid(update.normal.qpn,update.epoch,update.sequence)) {error=2;break;}
        preq.write(pointerReq(update.normal.qpn,true));state=UPDATE_0;break;
    case RETRY_START:
        if(retry.bad || !as02_owner_valid(retry.normal.qpn,retry.epoch,retry.sequence)) {error=timer_request?4:3;break;}
        preq.write(pointerReq(retry.normal.qpn));state=timer_request?TIMER_RETRANS_0:RETRANS_0;break;
    case ALLOC_START: {
        if(insert.bad || !as02_owner_valid(insert.normal.qpn,insert.epoch,insert.sequence)) {error=5;break;}
        ap_uint<192> r=0;r(167,0)=as02_owner(insert.normal.qpn,insert.normal.psn,insert.epoch,insert.sequence);
        alloc_req.write(r);state=ALLOC_WAIT;break;
    }
    case ALLOC_WAIT:
        if(!alloc_rsp.empty()) {reply=alloc_rsp.read();state=ALLOC_CHECK;}
        break;
    case ALLOC_CHECK: {
            ap_uint<256> r=reply;
            if(r(255,248)!=0 || r(15,0)>=META_TABLE_SIZE || r(79,16)==0 ||
                r(247,80)!=as02_owner(insert.normal.qpn,insert.normal.psn,insert.epoch,insert.sequence)) {error=6;break;}
            new_index=r(15,0);new_lease=r(247,0);
            preq.write(pointerReq(insert.normal.qpn,true));state=INSERT_0;
        break;
    }
    case INSERT_0:
        if(!prsp.empty()) {
            ptr=prsp.read();
            if(!ptr.valid) {
                ptr.valid=true;ptr.head=new_index;ptr.tail=new_index;
                mreq.write(as02OwnedMetaReq(new_index,as02OwnedMetaEntry(insert.normal,new_lease)));
                pupd.write(pointerUpdate(insert.normal.qpn,ptr));ninsert++;state=MAIN;
            } else {
                mreq.write(as02OwnedMetaReq(ptr.tail,new_index));ptr.tail=new_index;state=INSERT_1;
            }
        }
        break;
    case INSERT_1:
        mreq.write(as02OwnedMetaReq(new_index,as02OwnedMetaEntry(insert.normal,new_lease)));
        pupd.write(pointerUpdate(insert.normal.qpn,ptr));ninsert++;state=MAIN;break;
    case UPDATE_0:
        if(!prsp.empty()) {
            ptr=prsp.read();
            if(ptr.valid) {curr=ptr.head;mreq.write(as02OwnedMetaReq(curr));state=UPDATE_1;}
            else {pupd.write(pointerUpdate(update.normal.qpn,ptr));state=MAIN;}
        }
        break;
    case UPDATE_1:
        if(!mrsp.empty()) {meta=mrsp.read();state=UPDATE_CHECK;}
        break;
    case UPDATE_CHECK: {
            bool read_first=update.normal.op_code==RC_RDMA_READ_RESP_FIRST;
            bool read_middle=update.normal.op_code==RC_RDMA_READ_RESP_MIDDLE;
            bool read_last=update.normal.op_code==RC_RDMA_READ_RESP_LAST;
            bool read_only=update.normal.op_code==RC_RDMA_READ_RESP_ONLY;
            bool read_response=read_first || read_middle || read_last || read_only;
            if(!meta.valid || meta.lease(15,0)!=curr ||
                !as02_wr_matches(meta.lease,update.normal.qpn,update.epoch,update.sequence) ||
                meta.psn!=update.normal.latest_acked_req ||
                (read_response && meta.opCode!=RC_RDMA_READ_REQUEST) ||
                (!read_response && update.normal.op_code!=RC_ACK) ||
                (!read_response && meta.opCode==RC_RDMA_READ_REQUEST) ||
                ((read_first || read_middle) && meta.length<=PMTU) ||
                ((read_last || read_only) && meta.length>PMTU)) {error=7;break;}
            if(read_first || read_only)
                rdinit.write(as02OwnedRdInit(retransRdInit(meta.localAddr,meta.lst),meta.lease));
            if(read_first || read_middle) {
                meta.localAddr+=PMTU;meta.remoteAddr+=PMTU;meta.length-=PMTU;meta.psn+=1;
                // The implicit copy keeps ALL248 immutable lease bits.
                mreq.write(as02OwnedMetaReq(ptr.head,as02OwnedMetaEntry(meta)));
                pupd.write(pointerUpdate(update.normal.qpn,ptr));npartial++;state=MAIN;
            } else {
                ptr.head=meta.next;ptr.valid=!meta.isTail;
                return_lease=meta.lease;ap_uint<256> r=0;r(247,0)=return_lease;
                release_req.write(r);state=RELEASE_WAIT;
                // Keep the actual pointer lock until the exact real pool
                // return acknowledgement. No index-only free or default OK.
            }
        break;
    }
    case RELEASE_WAIT:
        if(!release_rsp.empty()) {reply=release_rsp.read();state=RELEASE_CHECK;}
        break;
    case RELEASE_CHECK: {
            ap_uint<256> r=reply;
            if(r(255,248)!=0 || r(247,0)!=return_lease) {error=8;break;}
            pupd.write(pointerUpdate(update.normal.qpn,ptr));nrelease++;state=MAIN;
        break;
    }
    case RETRANS_0:
    case TIMER_RETRANS_0:
        if(!prsp.empty()) {
            ptr=prsp.read();bool timer=state==TIMER_RETRANS_0;state=MAIN;
            if(ptr.valid) {curr=ptr.head;mreq.write(as02OwnedMetaReq(curr));state=timer?RETRANS_2:RETRANS_1;}
        }
        break;
    case RETRANS_1:
    case RETRANS_2:
        if(!mrsp.empty()) {meta=mrsp.read();seeking=state==RETRANS_1;state=RETRANS_CHECK;}
        break;
    case RETRANS_CHECK: {
            if(!meta.valid || meta.lease(15,0)!=curr ||
                !as02_wr_matches(meta.lease,retry.normal.qpn,retry.epoch,retry.sequence)) {error=9;break;}
            bool emit=!seeking || meta.psn==retry.normal.psn;
            if(emit)events.write(as02OwnedEvent(retransEvent(meta.opCode,retry.normal.qpn,
                meta.localAddr,meta.remoteAddr,meta.length,meta.psn,meta.lst,meta.offs,
                meta.rkey,meta.rkey_valid,meta.host),meta.lease));
            state=MAIN;
            if(!meta.isTail) {
                curr=meta.next;mreq.write(as02OwnedMetaReq(curr));state=emit?RETRANS_2:RETRANS_1;
            } else if(!emit)error=10; // no fake replay if requested PSN absent
        break;
    }
    }
}
'''

def derive(original):
    s,_,e=block(original,'struct retransMetaEntry\n')
    entry=original[s:e+1].replace('retransMetaEntry','as02OwnedMetaEntry')
    entry=once(entry,'\tbool valid;','\tap_uint<248> lease = 0;\n\tbool valid;')
    entry=once(entry,'as02OwnedMetaEntry() {}',
        'as02OwnedMetaEntry():rkey(0),rkey_valid(0),host(PKG_INT),psn(0),next(0),opCode(static_cast<ibOpCode>(0)),localAddr(0),remoteAddr(0),length(0),lst(0),offs(0),lease(0),valid(false),isTail(false) {}')
    entry=once(entry,'as02OwnedMetaEntry(retransEntry& e)','as02OwnedMetaEntry(retransEntry& e, ap_uint<248> token)')
    entry=once(entry,'valid(true), isTail(true)','lease(token), valid(true), isTail(true)')
    entry=once(entry,':next(next) {}',':as02OwnedMetaEntry() { this->next=next; }')
    s,_,e=block(original,'struct retransMetaReq\n')
    req=original[s:e+1].replace('retransMetaReq','as02OwnedMetaReq').replace('retransMetaEntry','as02OwnedMetaEntry')
    s,_,e=block(original,'void retrans_meta_table(')
    s=original.rfind('template <int INSTID = 0>',0,s)
    meta=original[s:e].replace('retrans_meta_table','as02_owned_meta_table').replace('retransMetaReq','as02OwnedMetaReq').replace('retransMetaEntry','as02OwnedMetaEntry')
    meta=once(meta,'meta_rsp)','meta_rsp, stream<ap_uint<32>>& faults)')
    meta=once(meta,'\t#pragma HLS DEPENDENCE variable=meta_table inter false',
        '// Preserve actual RAW/WAW/WAR dependencies, no false-dependence waiver.')
    meta=once(meta,'\tas02OwnedMetaReq req;',r'''
    static ap_uint<32> error=0;
    if(error!=0) {if(!faults.full())faults.write(error);return;}
    as02OwnedMetaReq req;
''')
    meta=once(meta,'meta_upd_req.read(req);',r'''meta_upd_req.read(req);
        if(req.idx>=META_TABLE_SIZE || (req.write && req.append) ||
            (req.append && req.entry.next>=META_TABLE_SIZE) ||
            (req.write && (req.entry.lease(15,0)!=req.idx || req.entry.lease(79,16)==0 ||
                !as02_owner_valid(req.entry.lease(95,80),req.entry.lease(183,120),req.entry.lease(247,184)) ||
                (!req.entry.isTail && req.entry.next>=META_TABLE_SIZE)))) {error=1;return;}
''')
    s,_,e=block(original,'void retrans_pointer_table(')
    s=original.rfind('template <int INSTID = 0>',0,s)
    pointer=original[s:e].replace('retrans_pointer_table','as02_owned_pointer_table')
    pointer=once(pointer,'pointerRspFifo)','pointerRspFifo, stream<ap_uint<32>>& faults)')
    pointer=once(pointer,'\tpointerUpdate upd;',r'''
    static ap_uint<16> clear_idx=0;
    static bool clear_done=false;
    static ap_uint<32> error=0;
#pragma HLS reset variable=ptr_table off
    if(!clear_done) {
        retransPointerEntry zero;zero.head=0;zero.tail=0;zero.valid=false;
        ptr_table[clear_idx]=zero;
        if(clear_idx==MAX_QPS-1)clear_done=true;else clear_idx++;
        return;
    }
    if(error!=0) {if(!faults.full())faults.write(error);return;}
    pointerUpdate upd;
''')
    pointer=once(pointer,'pointerUpdFifo.read(upd);',r'''pointerUpdFifo.read(upd);
        if(upd.qpn>=MAX_QPS || (upd.entry.valid && (upd.entry.head>=META_TABLE_SIZE || upd.entry.tail>=META_TABLE_SIZE))) {error=1;return;}
''')
    pointer=once(pointer,'pointerReqFifo.read(pt_req);','pointerReqFifo.read(pt_req);\n        if(pt_req.qpn>=MAX_QPS) {error=2;return;}')
    return original+'\n'+TYPES+'\n'+entry+'\n'+req+'\n'+pointer+'\n'+meta+'\n'+PROCESS
