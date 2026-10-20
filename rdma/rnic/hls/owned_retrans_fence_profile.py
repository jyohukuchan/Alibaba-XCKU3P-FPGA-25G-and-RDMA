#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Real owned-process queue/barrier join, NOT whole shared-core retirement.

Derive the selected process/tables from the exact Progress041 implementation.
Original header and Progress041 sources remain untouched/unselected here.
"""
import importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
spec=importlib.util.spec_from_file_location('owned_base',Path(__file__).with_name('owned_retrans_profile.py'))
base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
BASE=base.BASE;META=base.META;once=base.once;block=base.block
TOP=Path(__file__).with_name('owned_retrans_top.cpp')

TYPES=r'''
// Internal actual same-queue markers, never an external idle/drain assertion.
struct as02FencePointerReq {
    pointerReq normal;bool marker=false;ap_uint<168> owner=0;
    as02FencePointerReq() {normal.qpn=0;normal.lock=false;}
    as02FencePointerReq(pointerReq n):normal(n) {}
};
struct as02FencePointerUpdate {
    pointerUpdate normal;bool marker=false;ap_uint<168> owner=0;
    as02FencePointerUpdate() {normal.qpn=0;normal.entry.head=0;normal.entry.tail=0;normal.entry.valid=false;}
    as02FencePointerUpdate(pointerUpdate n):normal(n) {}
};
template<int N>
inline void as02_seen_marker(ap_uint<168> owner,ap_uint<N>& seen,ap_uint<168>& token,
    ap_uint<32>& error,unsigned source) {
    if(owner(15,0)>=MAX_QPS || owner(103,40)==0 || owner(167,104)==0 ||
        (seen!=0 && owner!=token))error=11;
    if(seen==0)token=owner;
    seen[source]=1;
}
'''

DIGEST=r'''
// Forces actual ALL-field BRAM readback through the barrier; digest is NOT
// active/free ownership or a cryptographic identity. Metadata.valid persists.
inline ap_uint<64> as02_owned_record_digest(as02OwnedMetaEntry e) {
    ap_uint<576> r=0;
    r(31,0)=e.rkey;r[32]=e.rkey_valid;r[33]=e.host;r(57,34)=e.psn;r(73,58)=e.next;
    r(105,74)=static_cast<unsigned>(e.opCode);r(169,106)=e.localAddr;r(233,170)=e.remoteAddr;
    r(265,234)=e.length;r[266]=e.lst;r(270,267)=e.offs;r[271]=e.valid;r[272]=e.isTail;
    r(520,273)=e.lease;ap_uint<64> d=0;
    for(unsigned i=0;i<9;i++) {
#pragma HLS unroll
        ap_uint<64> word=r(63,0);d^=word;r>>=64;
    }
    return d;
}
'''

META_CONTROL=r'''
    static bool barrier=false;
    static ap_uint<168> barrier_owner=0;
    static ap_uint<16> barrier_index=0;
    static ap_uint<2> barrier_phase=0;
    static as02OwnedMetaEntry sampled_record;
    static ap_uint<64> barrier_digest=0;
    if(barrier) {
        if(barrier_phase==0) {
            // Actual read of EVERY full record, no metadata-valid/free proxy.
            sampled_record=meta_table[barrier_index];barrier_phase=1;
        } else if(barrier_phase==1) {
            barrier_digest^=as02_owned_record_digest(sampled_record);
            if(barrier_index==META_TABLE_SIZE-1)barrier_phase=2;
            else {barrier_index++;barrier_phase=0;}
        } else if(!barriers.full()) {
            ap_uint<256> r=0;r(167,0)=barrier_owner;r[176]=1;
            r(240,177)=barrier_digest;r(252,241)=META_TABLE_SIZE;
            barriers.write(r);barrier=false;barrier_phase=0;
        }
        return;
    }
'''

POINTER_CONTROL=r'''
    static ap_uint<2> seen=0;
    static ap_uint<168> barrier_owner=0;
    static ap_uint<1> barrier_phase=0;
    static ap_uint<224> sampled=0;
    if(seen==3) {
        if(barrier_phase==0) {
            retransPointerEntry p=ptr_table[barrier_owner(15,0)];
            ap_uint<224> r=0;r(167,0)=barrier_owner;r[176]=1;
            r[177]=p.valid;r[178]=pt_isLocked;r[179]=pt_wait;
            r(195,180)=p.head;r(211,196)=p.tail;
            r(175,168)=(p.valid || pt_isLocked || pt_wait)?2:0;
            sampled=r;barrier_phase=1;
        } else if(!barriers.full()) {barriers.write(sampled);seen=0;barrier_phase=0;}
        return;
    }
'''

FENCE_STATES=r'''
    case FENCE_PREQ: {
        as02FencePointerReq r;r.marker=true;r.owner=token;preq.write(r);state=FENCE_PUPD;break;
    }
    case FENCE_PUPD: {
        as02FencePointerUpdate r;r.marker=true;r.owner=token;pupd.write(r);state=FENCE_META;break;
    }
    case FENCE_META: {
        as02OwnedMetaReq r;r.idx=0;r.write=false;r.append=false;r.marker=true;r.owner=token;
        mreq.write(r);state=FENCE_ALLOC;break;
    }
    case FENCE_ALLOC: {
        ap_uint<192> r=0;r(167,0)=token;r[168]=1;alloc_req.write(r);state=FENCE_RELEASE;break;
    }
    case FENCE_RELEASE: {
        ap_uint<256> r=0;r(247,80)=token;r[248]=1;release_req.write(r);state=FENCE_EVENT;break;
    }
    case FENCE_EVENT: {
        as02OwnedEvent r;r.marker=true;r.owner=token;events.write(r);state=FENCE_RDINIT;break;
    }
    case FENCE_RDINIT: {
        as02OwnedRdInit r;r.marker=true;r.owner=token;rdinit.write(r);state=FENCE_WAIT;break;
    }
    case FENCE_WAIT:
        if(replies_seen==31)state=FENCE_EMIT;
        else if(!replies_seen[0] && !pointer_barriers.empty()) {barrier_reply=pointer_barriers.read();reply_kind=0;state=FENCE_CHECK;}
        else if(!replies_seen[1] && !metadata_barriers.empty()) {barrier_reply=metadata_barriers.read();reply_kind=1;state=FENCE_CHECK;}
        else if(!replies_seen[2] && !pool_barriers.empty()) {barrier_reply=pool_barriers.read();reply_kind=2;state=FENCE_CHECK;}
        else if(!replies_seen[3] && !event_accepts.empty()) {barrier_reply=event_accepts.read();reply_kind=3;state=FENCE_CHECK;}
        else if(!replies_seen[4] && !rdinit_accepts.empty()) {barrier_reply=rdinit_accepts.read();reply_kind=4;state=FENCE_CHECK;}
        break;
    case FENCE_CHECK: {
        if(barrier_reply(167,0)!=token) {error=12;break;}
        if(reply_kind==0) {
            ap_uint<8> status=barrier_reply(175,168);
            if(!barrier_reply[176] || (status!=0 && status!=2) || barrier_reply(255,212)!=0 ||
                ((barrier_reply(179,177)!=0)!=(status==2))) {error=12;break;}
            if(status==2)barrier_busy=true;pointer_state=barrier_reply(179,177);
        } else if(reply_kind==1) {
            if(barrier_reply(175,168)!=0 || !barrier_reply[176] || barrier_reply(252,241)!=META_TABLE_SIZE ||
                barrier_reply(255,253)!=0) {error=12;break;}
            metadata_digest=barrier_reply(240,177);metadata_reads=barrier_reply(252,241);
        } else if(reply_kind==2) {
            ap_uint<8> status=barrier_reply(211,204);
            ap_uint<12> own=barrier_reply(179,168),active=barrier_reply(191,180),free=barrier_reply(203,192);
            if(!barrier_reply[212] || barrier_reply(255,213)!=0 || (status!=0 && status!=2) ||
                ((own==0)!=(status==0)) || own>active || active>META_TABLE_SIZE ||
                (ap_uint<13>(active)+free)!=META_TABLE_SIZE) {error=12;break;}
            if(status==2)barrier_busy=true;pool_owned=own;pool_active=active;pool_free=free;
        } else {
            if(barrier_reply(255,168)!=0) {error=12;break;}
        }
        replies_seen[reply_kind]=1;state=FENCE_WAIT;break;
    }
    case FENCE_EMIT: {
        ap_uint<320> r=0;r(167,0)=token;r(175,168)=barrier_busy?2:0;
        r(179,176)=seen;r(184,180)=replies_seen;r[185]=1;
        r(197,186)=pool_owned;r(209,198)=pool_active;r(221,210)=pool_free;
        r(285,222)=metadata_digest;r(297,286)=metadata_reads;r(300,298)=pointer_state;r[301]=1;
        fences.write(r);state=FENCE_ACCEPT;break;
    }
    case FENCE_ACCEPT:
        // PRIVATE acknowledgement generated ONLY by actual RTL external
        // fence response handshake, not this AXIS encoder's buffered write.
        if(!fence_accepts.empty()) {
            ap_uint<192> r=fence_accepts.read();
            if(r(167,0)!=token || r(191,168)!=0) {error=12;break;}
            seen=0;replies_seen=0;state=MAIN;
        }
        break;
'''

def derive(original):
    suffix=base.derive(original)[len(original):]
    suffix=TYPES+suffix
    suffix=suffix.replace('bool bad; };','bool bad; bool marker=false; };')
    suffix=suffix.replace('retransEvent normal;ap_uint<248> lease;',
        'retransEvent normal;ap_uint<248> lease;bool marker=false;ap_uint<168> owner=0;')
    suffix=suffix.replace('retransRdInit normal;ap_uint<248> lease;',
        'retransRdInit normal;ap_uint<248> lease;bool marker=false;ap_uint<168> owner=0;')
    suffix=once(suffix,'struct as02OwnedMetaReq\n{','struct as02OwnedMetaReq\n{\n    bool marker=false;ap_uint<168> owner=0;')
    # Actual pointer consumer: TWO same-queue markers, not one quiet signal.
    a,_,e=block(suffix,'void as02_owned_pointer_table(');f=suffix[a:e]
    f=once(f,'stream<pointerReq>&','stream<as02FencePointerReq>&')
    f=once(f,'stream<pointerUpdate>&','stream<as02FencePointerUpdate>&')
    f=once(f,'stream<ap_uint<32>>& faults)','stream<ap_uint<32>>& faults,stream<ap_uint<224>>& barriers)')
    anchor='    if(error!=0) {if(!faults.full())faults.write(error);return;}'
    f=once(f,anchor,anchor+'\n'+POINTER_CONTROL)
    f=once(f,'if (!pointerUpdFifo.empty())','if (!seen[1] && !pointerUpdFifo.empty())')
    f=once(f,'else if (!pointerReqFifo.empty() && !pt_wait)','else if (!seen[0] && !pointerReqFifo.empty() && !pt_wait)')
    f=once(f,'pointerUpdFifo.read(upd);',r'''as02FencePointerUpdate m=pointerUpdFifo.read();
        if(m.marker) {as02_seen_marker(m.owner,seen,barrier_owner,error,1);return;}
        upd=m.normal;''')
    f=once(f,'pointerReqFifo.read(pt_req);',r'''as02FencePointerReq m=pointerReqFifo.read();
        if(m.marker) {as02_seen_marker(m.owner,seen,barrier_owner,error,0);return;}
        pt_req=m.normal;''')
    suffix=suffix[:a]+f+suffix[e:]
    # Actual ALL2000-entry metadata readback behind the same request queue.
    a,_,e=block(suffix,'void as02_owned_meta_table(');f=suffix[a:e]
    f=once(f,'stream<ap_uint<32>>& faults)','stream<ap_uint<32>>& faults,stream<ap_uint<256>>& barriers)')
    f=once(f,anchor,anchor+'\n'+META_CONTROL)
    f=once(f,'meta_upd_req.read(req);',r'''meta_upd_req.read(req);
        if(req.marker) {
            if(req.idx!=0 || req.write || req.append || req.owner(15,0)>=MAX_QPS ||
                req.owner(103,40)==0 || req.owner(167,104)==0) {error=1;return;}
            barrier_owner=req.owner;barrier=true;barrier_index=0;barrier_phase=0;barrier_digest=0;return;
        }
''')
    suffix=suffix[:a]+f+suffix[e:]
    suffix=once(suffix,'template <int INSTID = 0>\nvoid as02_owned_meta_table(',
        DIGEST+'\ntemplate <int INSTID = 0>\nvoid as02_owned_meta_table(')
    # Actual process owns marker injection into ALL downstream producer queues.
    a,_,e=block(suffix,'void as02_process_owned_retransmissions(');f=suffix[a:e]
    f=once(f,'stream<pointerReq>& preq,stream<pointerUpdate>& pupd',
        'stream<as02FencePointerReq>& preq,stream<as02FencePointerUpdate>& pupd')
    f=once(f,'stream<as02OwnedEvent>& events,',r'''stream<as02OwnedEvent>& events,
    stream<ap_uint<224>>& pointer_barriers,stream<ap_uint<256>>& metadata_barriers,stream<ap_uint<224>>& pool_barriers,
    stream<ap_uint<192>>& event_accepts,stream<ap_uint<192>>& rdinit_accepts,stream<ap_uint<192>>& fence_accepts,
    stream<ap_uint<320>>& fences,''')
    f=once(f,'RETRANS_0,RETRANS_1,RETRANS_2,RETRANS_CHECK,TIMER_RETRANS_0};',
        'RETRANS_0,RETRANS_1,RETRANS_2,RETRANS_CHECK,TIMER_RETRANS_0,\n        FENCE_PREQ,FENCE_PUPD,FENCE_META,FENCE_ALLOC,FENCE_RELEASE,FENCE_EVENT,FENCE_RDINIT,FENCE_WAIT,FENCE_CHECK,FENCE_EMIT,FENCE_ACCEPT};')
    f=once(f,'    static State state=MAIN;',r'''    static State state=MAIN;
    static ap_uint<4> seen=0;static ap_uint<5> replies_seen=0;
    static ap_uint<168> token=0;static ap_uint<256> barrier_reply=0;
    static ap_uint<3> reply_kind=0,pointer_state=0;
    static ap_uint<64> metadata_digest=0;
    static ap_uint<12> metadata_reads=0,pool_owned=0,pool_active=0,pool_free=0;
    static bool have_insert=false,barrier_busy=false;''')
    m=f.index('    case MAIN:');n=f.index('    case UPDATE_START:',m)
    f=f[:m]+r'''
    case MAIN:
        if(seen==15 && !have_insert) {replies_seen=0;barrier_busy=false;state=FENCE_PREQ;}
        else if(!seen[0] && !updates.empty()) {update=updates.read();state=UPDATE_START;}
        else if(!seen[1] && !rx_retry.empty()) {retry=rx_retry.read();timer_request=false;state=RETRY_START;}
        else if(!seen[2] && !timer_retry.empty()) {retry=timer_retry.read();timer_request=true;state=RETRY_START;}
        else if(have_insert && insert.marker) {
            if(insert.bad) {error=11;break;}
            as02_seen_marker(as02_owner(insert.normal.qpn,insert.normal.psn,insert.epoch,insert.sequence),seen,token,error,3);
            have_insert=false;
        } else if(have_insert && pool_initialized && credit!=0) {have_insert=false;state=ALLOC_START;}
        else if(!seen[3] && !have_insert && !inserts.empty()) {insert=inserts.read();have_insert=true;}
        // A retained normal insert at credit0 NEVER hides ACK processing;
        // its same-queue marker CANNOT overtake that pending real operation.
        break;
'''+f[n:]
    f=once(f,'    case UPDATE_START:\n',r'''    case UPDATE_START:
        if(update.marker) {
            if(update.bad) {error=11;break;}
            as02_seen_marker(as02_owner(update.normal.qpn,update.normal.latest_acked_req,update.epoch,update.sequence),seen,token,error,0);
            state=MAIN;break;
        }
''')
    f=once(f,'    case RETRY_START:\n',r'''    case RETRY_START:
        if(retry.marker) {
            if(retry.bad) {error=11;break;}
            as02_seen_marker(as02_owner(retry.normal.qpn,retry.normal.psn,retry.epoch,retry.sequence),seen,token,error,timer_request?2:1);
            state=MAIN;break;
        }
''')
    f=f[:-1].rstrip();end=f.rfind('    }\n}')
    # block() includes the closing function brace; insert inside its switch.
    if end>=0:raise ValueError('unexpected process brace shape')
    if not f.endswith('    }'):raise ValueError('process switch anchor changed')
    f=f[:-5]+FENCE_STATES+'    }\n}\n'
    suffix=suffix[:a]+f+suffix[e:]
    # Register BOTH actual pointer queue heads. Preserve update priority even
    # when an earlier update is still waiting to enter its head register.
    a,_,e=block(suffix,'void as02_owned_pointer_table(');f=suffix[a:e]
    f=once(f,'    pointerUpdate upd;',r'''
    static as02FencePointerUpdate held_update;
    static as02FencePointerReq held_request;
    static bool have_update=false,have_request=false;
    bool capture_update=!seen[1] && !(have_update && held_update.marker);
    bool capture_request=!seen[0] && !pt_wait && !(have_request && held_request.marker);
    pointerUpdate upd;
''')
    f=once(f,'if (!seen[1] && !pointerUpdFifo.empty())','if (!seen[1] && have_update)')
    f=once(f,'as02FencePointerUpdate m=pointerUpdFifo.read();','as02FencePointerUpdate m=held_update;have_update=false;')
    f=once(f,'else if (!seen[0] && !pointerReqFifo.empty() && !pt_wait)',r'''
    else if(!seen[1] && !pointerUpdFifo.empty()) {
        // Capture actual higher-priority update below; do not overtake it.
    }
    else if (!seen[0] && have_request && !pt_wait)''')
    f=once(f,'as02FencePointerReq m=pointerReqFifo.read();','as02FencePointerReq m=held_request;have_request=false;')
    f=f[:-1]+r'''
    if(capture_update && !have_update && !pointerUpdFifo.empty()) {
        held_update=pointerUpdFifo.read();have_update=true;
    }
    if(capture_request && !have_request && !pointerReqFifo.empty()) {
        held_request=pointerReqFifo.read();have_request=true;
    }
}
'''
    suffix=suffix[:a]+f+suffix[e:]
    a,_,e=block(suffix,'void as02_owned_meta_table(');f=suffix[a:e]
    f=once(f,'    as02OwnedMetaReq req;',r'''
    static as02OwnedMetaReq held_request;
    static bool have_request=false;
    bool executing=have_request;have_request=false;
    as02OwnedMetaReq req;
''')
    f=once(f,'if (!meta_upd_req.empty())','if (executing)')
    f=once(f,'meta_upd_req.read(req);','req=held_request;')
    f=f[:-1]+r'''
    // A marker execution returns before capturing any later request. During
    // the real scan, this point is not reached; queued later data cannot pass.
    if(!meta_upd_req.empty()) {held_request=meta_upd_req.read();have_request=true;}
}
'''
    suffix=suffix[:a]+f+suffix[e:]
    for opcode in ['RC_RDMA_READ_RESP_FIRST','RC_RDMA_READ_RESP_MIDDLE','RC_RDMA_READ_RESP_LAST','RC_RDMA_READ_RESP_ONLY','RC_ACK']:
        suffix=suffix.replace('update.normal.op_code=='+opcode,
            'ap_uint<8>(static_cast<unsigned>(update.normal.op_code))==ap_uint<8>('+opcode+')')
    return original+'\n'+suffix

def derive_top(original):
    s=once(original,'retransmitter/owned_retrans.hpp','retransmitter/owned_retrans_fence.hpp')
    s=s.replace('as02_owned_retrans_top','as02_owned_retrans_fence_top')
    s=once(s,'m.bad=r(415,399)!=0 || op>RC_ACK;',
        'm.marker=r[399];m.bad=r(415,400)!=0 || op>RC_ACK || (m.marker && r(270,40)!=0);')
    s=once(s,'m.bad=r(223,200)!=0 || op>RC_ACK;',
        'm.marker=r[200];m.bad=r(223,201)!=0 || op>RC_ACK || (m.marker && op!=0);')
    s=once(s,'m.bad=r(191,168)!=0;',
        'm.marker=r[168];m.bad=r(191,169)!=0;')
    s=once(s,'r[279]=e.validPsn;r[280]=e.isNak;r(528,281)=m.lease;out.write(r);',
        'r[279]=e.validPsn;r[280]=e.isNak;r(528,281)=m.lease;\n        if(m.marker) {r=0;r[575]=1;r(167,0)=m.owner;}out.write(r);')
    s=once(s,'r(312,65)=m.lease;out.write(r);',
        'r(312,65)=m.lease;\n        if(m.marker) {r=0;r[319]=1;r(167,0)=m.owner;}out.write(r);')
    s=once(s,'hls::stream<ap_uint<576>>& m_event,hls::stream<ap_uint<320>>& m_rdinit,',r'''hls::stream<ap_uint<576>>& m_event,hls::stream<ap_uint<320>>& m_rdinit,
    hls::stream<ap_uint<224>>& s_pool_fence,hls::stream<ap_uint<192>>& s_event_accept,
    hls::stream<ap_uint<192>>& s_rdinit_accept,hls::stream<ap_uint<192>>& s_fence_accept,
    hls::stream<ap_uint<320>>& m_fence,''')
    s=once(s,'#pragma HLS interface axis register port=m_rdinit',r'''#pragma HLS interface axis register port=m_rdinit
#pragma HLS interface axis register port=s_pool_fence
#pragma HLS interface axis register port=s_event_accept
#pragma HLS interface axis register port=s_rdinit_accept
#pragma HLS interface axis register port=s_fence_accept
#pragma HLS interface axis register port=m_fence''')
    s=s.replace('hls::stream<pointerReq>','hls::stream<as02FencePointerReq>')
    s=s.replace('hls::stream<pointerUpdate>','hls::stream<as02FencePointerUpdate>')
    s=once(s,'    owned_insert_decode(s_insert,inserts);',r'''
    static hls::stream<ap_uint<224>> pointer_barriers("pointer_barriers");
    static hls::stream<ap_uint<256>> metadata_barriers("metadata_barriers");
#pragma HLS stream variable=pointer_barriers depth=2
#pragma HLS stream variable=metadata_barriers depth=2
    owned_insert_decode(s_insert,inserts);''')
    s=once(s,'(preq,pupd,prsp,pointer_faults);','(preq,pupd,prsp,pointer_faults,pointer_barriers);')
    s=once(s,'(mreq,mrsp,metadata_faults);','(mreq,mrsp,metadata_faults,metadata_barriers);')
    s=once(s,'s_pool_release,events,pool_credit',
        's_pool_release,events,pointer_barriers,metadata_barriers,s_pool_fence,s_event_accept,s_rdinit_accept,s_fence_accept,m_fence,pool_credit')
    return s
