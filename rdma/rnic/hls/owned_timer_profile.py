#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Couple the real timer producer to actual owned insert/ACK/head/replay FSMs.

Not a complete full-FNS producer binding, shared-core drain or native CQ.
Progress041/042 and original timer/retransmission sources remain untouched.
"""
import importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
spec=importlib.util.spec_from_file_location('owned_fence_base',Path(__file__).with_name('owned_retrans_fence_profile.py'))
base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
BASE=base.BASE;META=base.META;TOP=base.TOP;once=base.once;block=base.block
TIMER=BASE/'fns/hls/ib_transport_protocol/transport_timer.hpp'

TYPES=r'''
struct as02OwnedTimerTx {
    ap_uint<248> lease=0;bool retry=false,marker=false;ap_uint<168> owner=0;
    as02OwnedTimerTx() {}
    as02OwnedTimerTx(ap_uint<248> l,bool r):lease(l),retry(r) {}
};
struct as02OwnedTimerCtrl {
    ap_uint<248> old_lease=0,next_lease=0;
    bool next_valid=false,advance=false,marker=false;ap_uint<168> owner=0;
    as02OwnedTimerCtrl() {}
    as02OwnedTimerCtrl(ap_uint<248> o,ap_uint<248> n,bool v,bool a)
        :old_lease(o),next_lease(n),next_valid(v),advance(a) {}
};
struct as02OwnedTimerEntry {
    ap_uint<32> time=0;ap_uint<4> retries=0;bool active=false,bound=false;
    ap_uint<248> head_lease=0;
    ap_uint<64> epoch=0,retired_sequence=0,latest_tx_sequence=0;
};
inline bool as02_timer_lease_valid(ap_uint<248> l) {
    return l(15,0)<META_TABLE_SIZE && l(79,16)!=0 && l(95,80)<MAX_QPS &&
        l(183,120)!=0 && l(247,184)!=0;
}
'''

TIMER_IMPL=r'''
// Original countdown and backoff decisions are retained. Control validation,
// normalization, head/time calculation, horizons and commit use REAL states;
// only ordinary idle RUN performs the original one-QP-per-cycle scan.
template<int INSTID=0>
void as02_owned_transport_timer(stream<as02OwnedTimerCtrl>& controls,
    stream<as02OwnedTimerTx>& starts,stream<as02OwnedRetry>& timer2retrans_req,
    stream<ap_uint<256>>& timer_barriers,stream<ap_uint<192>>& resumes,
    stream<ap_uint<32>>& faults) {
#pragma HLS pipeline II=1
#pragma HLS inline off
    static as02OwnedTimerEntry transportTimerTable[MAX_QPS];
#pragma HLS array_partition variable=transportTimerTable complete dim=1
#pragma HLS reset variable=transportTimerTable
    static ap_uint<16> tt_currPosition=0;
    enum TimerState {RUN,CTRL_READ,CTRL_CHECK,CTRL_EPOCH,CTRL_TIME,CTRL_RETIRE,
        CTRL_LATEST,CTRL_COMMIT,TX_READ,TX_CHECK,TX_EPOCH,TX_BIND,TX_LATEST,
        TX_TIME,TX_COMMIT,CTRL_MARK_CHECK,TX_MARK_CHECK,HALT_EMIT,
        HALT_WAIT_TX,SAMPLE,EMIT,WAIT_RESUME,RESUME_CHECK};
    static TimerState state=RUN;
    static as02OwnedTimerCtrl ctrl;
    static as02OwnedTimerTx tx;
    static ap_uint<2> seen=0;
    static ap_uint<168> token=0;
    static ap_uint<256> sampled=0;
    static ap_uint<192> resume_token=0;
    static bool marker_bad=false;
    static ap_uint<32> error=0,stale_controls=0,stale_starts=0;
    static as02OwnedTimerEntry entry;
    static ap_uint<16> setQP=0;
    ap_uint<16> checkQP;
    if(error!=0) {if(!faults.full())faults.write(error);return;}
    switch(state) {
    case RUN:
        if(!seen[0] && !controls.empty()) {ctrl=controls.read();state=CTRL_READ;}
        else if(!seen[1] && !starts.empty()) {tx=starts.read();state=TX_READ;}
        else {
ORIGINAL_SCAN
        }
        break;
    case CTRL_READ: {
        if(ctrl.marker) {
            marker_bad=ctrl.old_lease!=0 || ctrl.next_lease!=0 || ctrl.next_valid || ctrl.advance;
            state=CTRL_MARK_CHECK;break;
        }
        if(!as02_timer_lease_valid(ctrl.old_lease) ||
            (!ctrl.advance && (ctrl.next_valid || ctrl.next_lease!=0)) ||
            (ctrl.advance && ctrl.next_valid && (!as02_timer_lease_valid(ctrl.next_lease) ||
                ctrl.next_lease(95,80)!=ctrl.old_lease(95,80) ||
                ctrl.next_lease(183,120)!=ctrl.old_lease(183,120) ||
                ctrl.next_lease(247,184)<ctrl.old_lease(247,184) ||
                ctrl.next_lease(79,16)<=ctrl.old_lease(79,16))) ||
            (ctrl.advance && !ctrl.next_valid && ctrl.next_lease!=0)) {error=20;break;}
        setQP=ctrl.old_lease(95,80);entry=transportTimerTable[setQP];
        state=CTRL_CHECK;break;
    }
    case CTRL_CHECK: {
        ap_uint<64> epoch=ctrl.old_lease(183,120),seq=ctrl.old_lease(247,184);
        if(epoch<entry.epoch || (epoch==entry.epoch && seq<=entry.retired_sequence) ||
            (entry.bound && entry.head_lease!=ctrl.old_lease)) {
            stale_controls++;state=RUN;break; // do NOT clear a new owner
        }
        if(epoch>entry.epoch && entry.bound) {error=21;break;}
        state=CTRL_EPOCH;break;
    }
    case CTRL_EPOCH: {
        ap_uint<64> epoch=ctrl.old_lease(183,120);
        if(epoch>entry.epoch) {
            entry.epoch=epoch;entry.retired_sequence=0;entry.latest_tx_sequence=0;
        }
        state=CTRL_TIME;break;
    }
    case CTRL_TIME:
        entry.retries=0;
        if(ctrl.advance && !ctrl.next_valid) {
            entry.time=0;entry.active=false;entry.bound=false;entry.head_lease=0;
        } else {
            entry.head_lease=ctrl.advance?ctrl.next_lease:ctrl.old_lease;
            entry.bound=true;entry.active=true;entry.time=TIME_1ms;
        }
        state=CTRL_RETIRE;break;
    case CTRL_RETIRE: {
        ap_uint<64> seq=ctrl.old_lease(247,184),nextseq=entry.head_lease(247,184);
        if(ctrl.advance && (!ctrl.next_valid || nextseq!=seq) && seq>entry.retired_sequence)
            entry.retired_sequence=seq;
        state=CTRL_LATEST;break;
    }
    case CTRL_LATEST: {
        ap_uint<64> nextseq=entry.head_lease(247,184);
        if(entry.bound && nextseq>entry.latest_tx_sequence)entry.latest_tx_sequence=nextseq;
        state=CTRL_COMMIT;break;
    }
    case CTRL_COMMIT:
        transportTimerTable[setQP]=entry;state=RUN;break;
    case CTRL_MARK_CHECK:
        if(marker_bad) {error=20;break;}
        as02_seen_marker(ctrl.owner,seen,token,error,0);state=HALT_EMIT;break;
    case TX_READ: {
        if(tx.marker) {
            marker_bad=tx.lease!=0 || tx.retry;state=TX_MARK_CHECK;break;
        }
        if(!as02_timer_lease_valid(tx.lease)) {error=20;break;}
        setQP=tx.lease(95,80);entry=transportTimerTable[setQP];
        state=TX_CHECK;break;
    }
    case TX_CHECK: {
        ap_uint<64> epoch=tx.lease(183,120),seq=tx.lease(247,184);
        bool stale=epoch<entry.epoch || (epoch==entry.epoch && seq<=entry.retired_sequence) ||
            (entry.bound && epoch==entry.epoch && seq<entry.head_lease(247,184));
        if(stale) {stale_starts++;state=seen[0]?HALT_WAIT_TX:RUN;break;}
        if(epoch>entry.epoch && entry.bound) {error=21;break;}
        state=TX_EPOCH;break;
    }
    case TX_EPOCH: {
        ap_uint<64> epoch=tx.lease(183,120);
        if(epoch>entry.epoch) {
            entry.epoch=epoch;entry.retired_sequence=0;entry.latest_tx_sequence=0;
        }
        state=TX_BIND;break;
    }
    case TX_BIND:
        if(!entry.bound) {entry.head_lease=tx.lease;entry.bound=true;}
        state=TX_LATEST;break;
    case TX_LATEST: {
        // Appending a later WR NEVER retags the timer for the oldest WR.
        ap_uint<64> seq=tx.lease(247,184);
        if(seq>entry.latest_tx_sequence)entry.latest_tx_sequence=seq;
        state=TX_TIME;break;
    }
    case TX_TIME:
ORIGINAL_TX
        state=TX_COMMIT;break;
    case TX_COMMIT:
        transportTimerTable[setQP]=entry;
        state=seen[0]?HALT_WAIT_TX:RUN;break;
    case TX_MARK_CHECK:
        if(marker_bad) {error=20;break;}
        as02_seen_marker(tx.owner,seen,token,error,1);
        state=seen[0]?SAMPLE:RUN;break;
    case HALT_EMIT: {
        // Close SCANNING first, after all earlier timeout outputs. This
        // samequeue marker lets the actual process finish prior replay work
        // and then send TX marker; waiting for TX first would form a cycle.
        as02OwnedRetry r;r.normal.qpn=token(15,0);r.normal.psn=token(39,16);
        r.epoch=token(103,40);r.sequence=token(167,104);r.bad=false;r.marker=true;
        timer2retrans_req.write(r);state=seen[1]?SAMPLE:HALT_WAIT_TX;break;
    }
    case HALT_WAIT_TX:
        if(seen[1])state=SAMPLE;
        else if(!starts.empty()) {tx=starts.read();state=TX_READ;}
        break;
    case SAMPLE: {
        entry=transportTimerTable[token(15,0)];
        bool target=entry.bound && entry.head_lease(95,80)==token(15,0) &&
            entry.head_lease(183,120)==token(103,40) && entry.head_lease(247,184)==token(167,104);
        ap_uint<256> r=0;r(167,0)=token;r(175,168)=target?2:0;r[176]=1;
        r[177]=entry.bound;r[178]=entry.active;r(210,179)=entry.time;
        r(214,211)=entry.retries;r[215]=target;r(255,216)=0;
        sampled=r;state=EMIT;break;
    }
    case EMIT:timer_barriers.write(sampled);state=WAIT_RESUME;break;
    case WAIT_RESUME:
        if(!resumes.empty()) {resume_token=resumes.read();state=RESUME_CHECK;}
        break;
    case RESUME_CHECK:
        if(resume_token(167,0)!=token || resume_token(191,168)!=0) {error=22;break;}
        seen=0;state=RUN;
        break;
    }
}
'''

def derive_timer(original):
    _,left,end=block(original,'else if (!txSetTimer_req.empty())')
    tx=original[left+1:end-1];tx=tx[tx.index('        if (!entry.active)'):]
    tx=once(tx,'transportTimerTable[setQP] = entry;',
        '// Real table commit is the following explicit TX_COMMIT state.')
    # Capture the exact original round-robin countdown, retry cap and backoff.
    start=original.index('// perform round robin to check whether it has timed out')
    left=original.rfind('{',0,start);depth=1;end=left+1
    while depth:
        if original[end]=='{':depth+=1
        elif original[end]=='}':depth-=1
        end+=1
    scan=original[left+1:end-1]
    scan=once(scan,'timer2retrans_req.write(retransmission(checkQP));',r'''
                    as02OwnedRetry r;r.normal.qpn=checkQP;r.normal.psn=entry.head_lease(119,96);
                    r.epoch=entry.head_lease(183,120);r.sequence=entry.head_lease(247,184);
                    r.marker=false;r.bad=false;timer2retrans_req.write(r);''')
    implementation=TIMER_IMPL.replace('ORIGINAL_SCAN',scan).replace('ORIGINAL_TX',tx)
    # Original timer declarations/algorithm remain unselected, with their
    # complete license; avoid re-including duplicate raw retrans declarations.
    original=once(original,'#include "retransmitter/retransmitter.hpp"',
        '// Complete original retransmission types are already in the owned header.')
    return '#include "retransmitter/owned_retrans_fence.hpp"\n'+original+'\n'+implementation

def derive(original):
    s=base.derive(original)
    a,_,e=block(s,'void as02_process_owned_retransmissions(');f=s[a:e]
    f=once(f,'    stream<ap_uint<320>>& fences,',r'''    stream<ap_uint<320>>& fences,
    stream<as02OwnedTimerTx>& timer_starts,stream<as02OwnedTimerCtrl>& timer_controls,
    stream<ap_uint<256>>& timer_barriers,stream<ap_uint<192>>& timer_resumes,
    stream<ap_uint<32>>& timer_faults,''')
    f=once(f,'FENCE_ACCEPT};','FENCE_ACCEPT,TIMER_CLOSE,TIMER_TX_MARK,HEAD_WAIT,HEAD_CHECK,HEAD_EMIT};')
    f=once(f,'static ap_uint<5> replies_seen=0','static ap_uint<6> replies_seen=0')
    f=once(f,'    static bool have_insert=false,barrier_busy=false;',r'''
    static bool have_insert=false,barrier_busy=false,timer_closed=false;
    static ap_uint<248> next_head_lease=0;
    static bool replay_started=false;
    static ap_uint<64> replay_sequence=0;
    static ap_uint<8> timer_state=0;
''')
    f=once(f,'if(pool_fault_in || !pointer_faults.empty() || !metadata_faults.empty())',
        'if(pool_fault_in || !pointer_faults.empty() || !metadata_faults.empty() || !timer_faults.empty())')
    f=once(f,'        if(!pointer_faults.empty())pointer_faults.read();',
        '        if(!timer_faults.empty())timer_faults.read();\n        if(!pointer_faults.empty())pointer_faults.read();')
    f=once(f,'if(seen==15 && !have_insert) {replies_seen=0;barrier_busy=false;state=FENCE_PREQ;}',
        'if(seen==15 && !have_insert) {replies_seen=0;barrier_busy=false;state=TIMER_TX_MARK;}\n        else if((seen & 11)==11 && !have_insert && !timer_closed) {state=TIMER_CLOSE;}')
    # Both real insertion sites retain the actual allocation's full lease.
    f=f.replace('pupd.write(pointerUpdate(insert.normal.qpn,ptr));ninsert++;state=MAIN;',
        'pupd.write(pointerUpdate(insert.normal.qpn,ptr));timer_starts.write(as02OwnedTimerTx(new_lease,false));ninsert++;state=MAIN;')
    f=once(f,'pupd.write(pointerUpdate(update.normal.qpn,ptr));npartial++;state=MAIN;',r'''
                pupd.write(pointerUpdate(update.normal.qpn,ptr));
                if(ap_uint<8>(static_cast<unsigned>(update.normal.op_code))!=ap_uint<8>(RC_RDMA_READ_RESP_MIDDLE))
                    timer_controls.write(as02OwnedTimerCtrl(meta.lease,0,false,false));
                npartial++;state=MAIN;''')
    f=once(f,'pupd.write(pointerUpdate(update.normal.qpn,ptr));nrelease++;state=MAIN;',r'''
            pupd.write(pointerUpdate(update.normal.qpn,ptr));nrelease++;
            next_head_lease=0;
            if(ptr.valid) {mreq.write(as02OwnedMetaReq(ptr.head));state=HEAD_WAIT;}
            else state=HEAD_EMIT;''')
    f=once(f,'preq.write(pointerReq(retry.normal.qpn));state=timer_request?TIMER_RETRANS_0:RETRANS_0;break;',
        'replay_started=false;replay_sequence=retry.sequence;\n        preq.write(pointerReq(retry.normal.qpn));state=timer_request?TIMER_RETRANS_0:RETRANS_0;break;')
    f=once(f,'!as02_wr_matches(meta.lease,retry.normal.qpn,retry.epoch,retry.sequence))',r'''
                (!replay_started && !as02_wr_matches(meta.lease,retry.normal.qpn,retry.epoch,retry.sequence)) ||
                (replay_started && (meta.lease(95,80)!=retry.normal.qpn || meta.lease(183,120)!=retry.epoch ||
                    meta.lease(247,184)<replay_sequence || meta.lease(79,16)==0)))''')
    # The replacement above consumes the original closing parenthesis itself.
    f=once(f,'bool emit=!seeking || meta.psn==retry.normal.psn;',
        'replay_started=true;replay_sequence=meta.lease(247,184);\n            bool emit=!seeking || meta.psn==retry.normal.psn;')
    f=once(f,'    case RETRANS_CHECK: {',r'''    case RETRANS_CHECK: {
            // A genuinely queued old timeout is not retagged to a new head.
            // Ignore only provably older timer epochs/WR sequences; unknown
            // or future/wrong-QP identities retain fail-closed validation.
            if(timer_request && !replay_started && meta.valid && meta.lease(15,0)==curr &&
                meta.lease(95,80)==retry.normal.qpn &&
                (meta.lease(183,120)>retry.epoch || (meta.lease(183,120)==retry.epoch &&
                    meta.lease(247,184)>retry.sequence))) {state=MAIN;break;}
''')
    f=once(f,'            state=MAIN;\n            if(!meta.isTail)',
        '            if(emit)timer_starts.write(as02OwnedTimerTx(meta.lease,true));\n            state=MAIN;\n            if(!meta.isTail)')
    f=once(f,'if(replies_seen==31)','if(replies_seen==63)')
    f=once(f,'        break;\n    case FENCE_CHECK:',
        '        else if(!replies_seen[5] && !timer_barriers.empty()) {barrier_reply=timer_barriers.read();reply_kind=5;state=FENCE_CHECK;}\n        break;\n    case FENCE_CHECK:')
    f=once(f,'        } else {\n            if(barrier_reply(255,168)!=0)',r'''
        } else if(reply_kind==5) {
            ap_uint<8> status=barrier_reply(175,168);
            if(!barrier_reply[176] || (status!=0 && status!=2) ||
                ((status==2)!=bool(barrier_reply[215])) || barrier_reply(255,216)!=0) {error=12;break;}
            if(status==2)barrier_busy=true;
            timer_state=0;timer_state[0]=barrier_reply[177];timer_state[1]=barrier_reply[178];
            timer_state(5,2)=barrier_reply(214,211);timer_state[6]=barrier_reply(210,179)!=0;
        } else {
            if(barrier_reply(255,168)!=0)''')
    f=once(f,'r(179,176)=seen;r(184,180)=replies_seen;r[185]=1;',
        'r(179,176)=seen;r(184,180)=replies_seen(4,0);r[185]=1;')
    f=once(f,'r[301]=1;\n        fences.write(r);',
        'r[301]=1;r[302]=replies_seen[5];r(309,303)=timer_state(6,0);\n        fences.write(r);')
    f=once(f,'seen=0;replies_seen=0;state=MAIN;',
        'timer_resumes.write(r);seen=0;replies_seen=0;timer_closed=false;state=MAIN;')
    f=f[:-1].rstrip();assert f.endswith('    }')
    f=f[:-5]+r'''
    case TIMER_CLOSE: {
        as02OwnedTimerCtrl r;r.marker=true;r.owner=token;timer_controls.write(r);
        timer_closed=true;state=MAIN;break;
    }
    case TIMER_TX_MARK: {
        as02OwnedTimerTx r;r.marker=true;r.owner=token;timer_starts.write(r);state=FENCE_PREQ;break;
    }
    case HEAD_WAIT:
        if(!mrsp.empty()) {meta=mrsp.read();state=HEAD_CHECK;}
        break;
    case HEAD_CHECK:
        if(!meta.valid || meta.lease(15,0)!=ptr.head || meta.lease(79,16)==0 ||
            meta.lease(95,80)!=return_lease(95,80) || meta.lease(183,120)!=return_lease(183,120) ||
            meta.lease(247,184)<return_lease(247,184) || meta.lease(79,16)<=return_lease(79,16)) {error=23;break;}
        next_head_lease=meta.lease;state=HEAD_EMIT;break;
    case HEAD_EMIT:
        timer_controls.write(as02OwnedTimerCtrl(return_lease,next_head_lease,ptr.valid,true));state=MAIN;break;
    }
}
'''
    # Timer types precede the selected process; all original licensed types
    # and the real pointer/metadata implementations remain unchanged.
    return s[:len(original)]+'\n'+TYPES+s[len(original):a]+f+s[e:]

def derive_top(original):
    s=base.derive_top(original)
    s=once(s,'#include "ib_transport_protocol/retransmitter/owned_retrans_fence.hpp"',
        '#include "ib_transport_protocol/owned_timer.hpp"')
    s=s.replace('as02_owned_retrans_fence_top','as02_owned_timer_retrans_top')
    s=once(s,'hls::stream<ap_uint<192>>& s_retry,hls::stream<ap_uint<192>>& s_timer,',
        'hls::stream<ap_uint<192>>& s_retry,')
    s=once(s,'#pragma HLS interface axis register port=s_timer\n','')
    s=once(s,'owned_retry_decode<0>(s_retry,retries);owned_retry_decode<1>(s_timer,timers);',r'''
    owned_retry_decode<0>(s_retry,retries);
    static hls::stream<as02OwnedTimerTx> timer_starts("timer_starts");
    static hls::stream<as02OwnedTimerCtrl> timer_controls("timer_controls");
    static hls::stream<ap_uint<256>> timer_barriers("timer_barriers");
    static hls::stream<ap_uint<192>> timer_resumes("timer_resumes");
    static hls::stream<ap_uint<32>> timer_faults("timer_faults");
#pragma HLS stream variable=timer_starts depth=2
#pragma HLS stream variable=timer_controls depth=2
#pragma HLS stream variable=timer_barriers depth=2
#pragma HLS stream variable=timer_resumes depth=2
#pragma HLS stream variable=timer_faults depth=2
#pragma HLS aggregate variable=timer_starts compact=bit
#pragma HLS aggregate variable=timer_controls compact=bit
    as02_owned_transport_timer<47>(timer_controls,timer_starts,timers,timer_barriers,timer_resumes,timer_faults);''')
    s=once(s,'s_fence_accept,m_fence,pool_credit',
        's_fence_accept,m_fence,timer_starts,timer_controls,timer_barriers,timer_resumes,timer_faults,pool_credit')
    return s
