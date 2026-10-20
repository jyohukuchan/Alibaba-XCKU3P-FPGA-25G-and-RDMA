#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Per-request completion in the SAME native HLS, not a synthetic idle bit.

Actual admission stamps full QPN/epoch/sequence into real request metadata.
Join actual BTH issue, stored retransmission record, positive RX consumer,
pointer release, freelist return, timer bookkeeping and SAME PSN readback.
Physical memory/MAC/CQ ownership remains the actual native RTL's job.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil

import recv_retire_transport as recv

qp = recv.qp
ROOT = qp.ROOT
once = qp.once
def span(text, anchor):
    # FNS contains unmatched brace examples in // comments. Mask comments
    # and literals while retaining offsets; never edit the licensed prefix.
    masked = re.sub(r'//[^\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'',
        lambda m: ' '*len(m[0]), text)
    start = text.index(anchor)
    left = masked.index('{', start)
    end, depth = left+1, 1
    while depth:
        if masked[end] == '{':
            depth += 1
        elif masked[end] == '}':
            depth -= 1
        end += 1
    return start, end


def change(text, anchor, edit):
    a, b = span(text, anchor)
    return text[:a]+edit(text[a:b])+text[b:]

TYPES = r'''
// Nonwrapping trusted operation identity, not an index, WR-id or current-head
// lookup. The complete588-bit native context stays in the operation join.
typedef ap_uint<152> as02ReqToken;
inline as02ReqToken as02_req_token(ap_uint<588> n) {
    as02ReqToken t=0;t(23,0)=n(395,372);t(87,24)=n(459,396);t(151,88)=n(523,460);return t;
}
inline bool as02_req_token_valid(as02ReqToken t) {
    return t(23,0)<MAX_QPS && t(87,24)!=0 && t(151,88)!=0;
}
inline bool as02_req_owner_valid(ap_uint<588> n) {
    ap_uint<16> op=n(339,324);ap_uint<32> len=n(307,276);
    ap_uint<65> limit=ap_uint<65>(1)<<64;
    return as02_req_token_valid(as02_req_token(n)) && n(355,340)!=0 && n(323,309)==0 &&
        n(19,0)==3 && op>=1 && op<=3 && len!=0 && len<=4096 &&
        (op!=3 || n(115,20)==0) && ap_uint<65>(n(243,180))+len<=limit &&
        ap_uint<65>(n(179,116))+len<=limit && ap_uint<65>(n(115,52))+len<=limit;
}
inline ap_uint<8> as02_req_opcode(ap_uint<588> n) {
    return n(339,324)==1 ? ap_uint<8>(RC_RDMA_WRITE_ONLY) :
        n(339,324)==2 ? ap_uint<8>(RC_RDMA_READ_REQUEST) : ap_uint<8>(RC_SEND_ONLY);
}
struct as02ReqStep {
    as02ReqToken token=0;ap_uint<24> psn=0;ap_uint<8> opcode=0;
    as02ReqStep() {}
    as02ReqStep(as02ReqToken t,ap_uint<24> p,ap_uint<8> o):token(t),psn(p),opcode(o) {}
};
struct as02ReqReclaim {as02ReqStep step;ap_uint<16> index=0;};
struct as02ReqInsert {
    as02ReqReclaim ref;ap_uint<64> local=0,remote=0;
    ap_uint<32> length=0,rkey=0;ap_uint<1> rkey_valid=0,host=0,lst=0;ap_uint<4> offs=0;
};
struct as02ReqRelease {ap_uint<16> index=0;bool owned=false;as02ReqStep step;};
struct as02ReqTxTimer {ap_uint<24> qpn=0;bool owned=false;as02ReqToken token=0;};
struct as02ReqState {as02ReqToken token=0;ap_uint<24> next=0,acked=0;ap_uint<8> error=0;};
// Aggregated656: full context[587:0],issued PSN[611:588],next[635:612],
// request wire opcode[643:636],error[651:644],reserved0[655:652].
struct as02ReqDone {
    ap_uint<588> context=0;ap_uint<24> psn=0,next=0;ap_uint<8> opcode=0,error=0;ap_uint<4> reserved=0;
};
inline bool as02_req_step_equal(as02ReqStep a,as02ReqStep b) {
    return a.token==b.token && a.psn==b.psn && a.opcode==b.opcode;
}
'''

JOIN = r'''
template<int INSTID=0> void as02_request_retire_join(
    stream<ap_uint<588>>& admitted,stream<as02ReqStep>& issued,
    stream<as02ReqInsert>& inserted,stream<as02ReqStep>& ack_consumed,
    stream<as02ReqStep>& read_payload_consumed,stream<as02ReqReclaim>& pointer_released,
    stream<as02ReqReclaim>& pool_returned,stream<as02ReqTxTimer>& tx_timer_consumed,
    stream<as02ReqStep>& rx_timer_consumed,stream<as02ReqToken>& state_req,
    stream<as02ReqState>& state_rsp,stream<as02ReqDone>& output,
    ap_uint<1> input_fault,ap_uint<1>& regFault) {
#pragma HLS pipeline II=1
#pragma HLS inline off
    enum Phase {ADMIT,ISSUE,INSERT,PACKET,POINTER,POOL,TX_TIMER,RX_TIMER,QUERY,STATE,PUBLISH};
    static Phase phase=ADMIT;static ap_uint<588> owner=0;
    static as02ReqStep issued_step;static ap_uint<16> index=0;
    static bool fault=false;regFault=fault;
    if(input_fault){fault=true;regFault=1;return;}
    if(fault)return;
    if(phase==ADMIT && !admitted.empty()) {
        owner=admitted.read();if(!as02_req_owner_valid(owner)){fault=true;return;}phase=ISSUE;
    } else if(phase==ISSUE && !issued.empty()) {
        issued_step=issued.read();
        if(issued_step.token!=as02_req_token(owner) || issued_step.opcode!=as02_req_opcode(owner)) {fault=true;return;}
        phase=INSERT;
    } else if(phase==INSERT && !inserted.empty()) {
        as02ReqInsert r=inserted.read();index=r.ref.index;
        if(!as02_req_step_equal(r.ref.step,issued_step) || index>=META_TABLE_SIZE ||
           r.local!=owner(243,180) || r.remote!=owner(115,52) || r.length!=owner(307,276) ||
           r.rkey!=owner(51,20) || !r.rkey_valid || !r.host || !r.lst || r.offs!=0) {fault=true;return;}
        phase=PACKET;
    } else if(phase==PACKET) {
        bool read=owner(339,324)==2;
        if((read && !read_payload_consumed.empty()) || (!read && !ack_consumed.empty())) {
            as02ReqStep r=read ? read_payload_consumed.read():ack_consumed.read();
            if(r.token!=issued_step.token || r.psn!=issued_step.psn ||
               r.opcode!=(read ? RC_RDMA_READ_RESP_ONLY:RC_ACK)) {fault=true;return;}
            phase=POINTER;
        }
    } else if(phase==POINTER && !pointer_released.empty()) {
        as02ReqReclaim r=pointer_released.read();
        if(r.index!=index || !as02_req_step_equal(r.step,issued_step)){fault=true;return;}phase=POOL;
    } else if(phase==POOL && !pool_returned.empty()) {
        as02ReqReclaim r=pool_returned.read();
        if(r.index!=index || !as02_req_step_equal(r.step,issued_step)){fault=true;return;}phase=TX_TIMER;
    } else if(phase==TX_TIMER && !tx_timer_consumed.empty()) {
        as02ReqTxTimer r=tx_timer_consumed.read();
        if(!r.owned || r.token!=issued_step.token || r.qpn!=owner(395,372)){fault=true;return;}phase=RX_TIMER;
    } else if(phase==RX_TIMER && !rx_timer_consumed.empty()) {
        as02ReqStep r=rx_timer_consumed.read();
        if(r.token!=issued_step.token || r.psn!=issued_step.psn){fault=true;return;}phase=QUERY;
    } else if(phase==QUERY && !state_req.full()) {state_req.write(issued_step.token);phase=STATE;
    } else if(phase==STATE && !state_rsp.empty()) {
        as02ReqState r=state_rsp.read();ap_uint<24> next=ap_uint<25>(issued_step.psn)+1;
        if(r.error || r.token!=issued_step.token || r.next!=next || r.acked!=next){fault=true;return;}
        phase=PUBLISH;
    } else if(phase==PUBLISH && !output.full()) {
        as02ReqDone r;r.context=owner;r.psn=issued_step.psn;r.next=ap_uint<25>(r.psn)+1;
        r.opcode=issued_step.opcode;output.write(r);phase=ADMIT;
    }
}
'''


def derive():
    out = recv.derive()
    hpp = 'hls/ib_transport_protocol/ib_transport_protocol.hpp'
    cpp = 'hls/ib_transport_protocol/ib_transport_protocol.cpp'
    top = 'hls/rocev2/rocev2.cpp'
    retrans = 'hls/ib_transport_protocol/retransmitter/retransmitter.hpp'
    timer = 'hls/ib_transport_protocol/transport_timer.hpp'
    state = 'hls/ib_transport_protocol/state_table.hpp'
    out[hpp] = once(out[hpp], 'struct txMeta\n{', TYPES+'\nstruct txMeta\n{')
    for name in ['event', 'ibhMeta', 'pkgShift']:
        out[hpp] = once(out[hpp], 'struct '+name+'\n{',
            'struct '+name+'\n{\n    bool request_owned=false;as02ReqToken request_token=0;')
    # All top declarations and forwarding gain the actual owner and receipt.
    for name in [hpp, cpp, top]:
        text, count = re.subn(r'(ap_uint<1>& regRecvFault,)([ \t]*\\)?\n',
            lambda m: m[1]+(m[2] or '')+'\n    stream<ap_uint<588>>& s_axis_request_owner,'+(m[2] or '')+
            '\n    stream<as02ReqDone>& m_axis_request_done,'+(m[2] or '')+
            '\n    ap_uint<1>& regRequestFault,'+(m[2] or '')+'\n', out[name])
        if count < 1:
            raise ValueError('missing actual request top declaration '+name)
        if name == top:
            text = text.replace('s_axis_recv_owner,m_axis_recv_done,regRecvFault,',
                's_axis_recv_owner,m_axis_recv_done,regRecvFault,s_axis_request_owner,m_axis_request_done,regRequestFault,')
            text = text.replace('void rocev2_native_recv_top(', 'void rocev2_native_request_top(')
            text = text.replace('#pragma HLS INTERFACE ap_none port=regRecvFault',
                '#pragma HLS INTERFACE ap_none port=regRecvFault\n'
                '#pragma HLS INTERFACE axis register port=s_axis_request_owner\n'
                '#pragma HLS aggregate variable=s_axis_request_owner compact=bit\n'
                '#pragma HLS INTERFACE axis register port=m_axis_request_done\n'
                '#pragma HLS aggregate variable=m_axis_request_done compact=bit\n'
                '#pragma HLS INTERFACE ap_none port=regRequestFault')
        out[name] = text
    out['hls/ib_transport_protocol/as02_request_retire.hpp'] = '// SPDX-License-Identifier: BSD-2-Clause-Views\n#pragma once\n'+JOIN
    out[cpp] = once(out[cpp], '#include "retransmitter/retransmitter.hpp"',
        '#include "retransmitter/retransmitter.hpp"\n#include "as02_request_retire.hpp"')

    out[hpp] = once(out[hpp], 'struct pkgShift\n{\n    bool request_owned=false;as02ReqToken request_token=0;',
        'struct pkgShift\n{\n    bool request_owned=false;as02ReqToken request_token=0;\n'
        '    ap_uint<24> request_psn=0;ap_uint<8> request_opcode=0;')

    def app(t):
        t = once(t, 'ap_uint<32>& regRetransCount)',
            'ap_uint<32>& regRetransCount,stream<ap_uint<588>>& s_axis_request_owner,\n'
            '    stream<ap_uint<588>>& request_admitted,stream<as02ReqToken>& request_rx_owners,ap_uint<1>& regRequestBindFault)')
        t = once(t, 'static ap_uint<32> retransCount = 0;',
            'static ap_uint<32> retransCount = 0;\n'
            '    static bool fault=false;regRequestBindFault=fault;if(fault)return;')
        t = t.replace('!s_axis_sq_meta.empty()', '!s_axis_sq_meta.empty() && !s_axis_request_owner.empty()')
        t = once(t, '\t\ts_axis_sq_meta.read(meta); // (len-32 | remote-64 | local-64)', r'''
        s_axis_sq_meta.read(meta);
        ap_uint<588> n=s_axis_request_owner.read();as02ReqToken token=as02_req_token(n);
        if(!as02_req_owner_valid(n) || meta.qpn!=n(395,372) ||
           ap_uint<8>(meta.op_code)!=as02_req_opcode(n) || !meta.host || !meta.lst || meta.offs!=0 || !meta.rkey_valid ||
           meta.params(63,0)!=n(243,180) || meta.params(127,64)!=n(115,52) ||
           meta.params(159,128)!=n(307,276) || meta.params(191,160)!=n(51,20)) {
            fault=true;regRequestBindFault=1;return;
        }
        request_admitted.write(n);request_rx_owners.write(token);''')
        a = t.index('ap_uint<588> n=s_axis_request_owner.read();')
        prefix, normal = t[:a], t[a:]
        if normal.count('tx_localTxMeta.write(ev);') != 2:
            raise ValueError('unreviewed local event producers')
        normal = normal.replace('tx_localTxMeta.write(ev);',
            'ev.request_owned=true;ev.request_token=token;tx_localTxMeta.write(ev);')
        normal = once(normal,
            'tx2retrans_insertAddrLen.write(retransAddrLen(laddr, raddr, length, lst, offs, meta.params(191,160), meta.rkey_valid, meta.host));',
            'retransAddrLen r(laddr,raddr,length,lst,offs,meta.params(191,160),meta.rkey_valid,meta.host);\n'
            '        r.request_owned=true;r.request_token=token;tx2retrans_insertAddrLen.write(r);')
        return prefix+normal
    out[cpp] = change(out[cpp], 'void local_req_handler(', app)

    def merger(t):
        return once(t, 'tx_ibhMetaFifo.write(ibhMeta(ev.op_code, key, ev.qpn, numPkg));',
            'ibhMeta b(ev.op_code,key,ev.qpn,numPkg);b.request_owned=ev.request_owned;\n'
            '            b.request_token=ev.request_token;tx_ibhMetaFifo.write(b);')
    out[cpp] = change(out[cpp], 'void meta_merger(', merger)

    def issue(t):
        # packetHeader.clear() resets only its streaming cursor, NOT the wire
        # bits. The same physical generator emits requests and responses: an
        # ACK following SEND must not inherit that SEND's ACK-request bit.
        # Requests still assert it in the existing GET_PSN branch below.
        t = once(t, '\t\t\theader.clear();',
            '\t\t\theader.clear();\n\t\t\theader.setAckReq(false);')
        t = once(t, 'stream<BaseTransportHeader<WIDTH> >& tx_ibhHeaderFifo\n',
            'stream<BaseTransportHeader<WIDTH> >& tx_ibhHeaderFifo,stream<as02ReqStep>& request_issued\n')
        t = once(t, 'tx2retrans_insertMeta.write(retransMeta(meta.dest_qp, qpState.req_next_psn, meta.op_code));',
            'retransMeta r(meta.dest_qp,qpState.req_next_psn,meta.op_code);\n'
            '                r.request_owned=meta.request_owned;r.request_token=meta.request_token;tx2retrans_insertMeta.write(r);')
        return once(t, '\t\t\ttx_ibhHeaderFifo.write(header);\n\t\t\tgi_state = META;',
            '\t\t\ttx_ibhHeaderFifo.write(header);\n'
            '            if(meta.request_owned)request_issued.write(as02ReqStep(meta.request_token,qpState.req_next_psn,ap_uint<8>(meta.op_code)));\n'
            '\t\t\tgi_state = META;')
    out[cpp] = change(out[cpp], 'void generate_ibh(', issue)

    def rx_bth(t):
        t = once(t, 'ap_uint<32>&\t\tregInvalidPsnDropCount\n',
            'ap_uint<32>&\t\tregInvalidPsnDropCount,stream<as02ReqToken>& request_rx_owners,ap_uint<1>& regRequestRxFault\n')
        t = once(t, 'static ap_uint<32> droppedPackets = 0;',
            'static ap_uint<32> droppedPackets = 0;\n'
            '    static bool fault=false;regRequestRxFault=fault;if(fault)return;')
        t = once(t, 'if (!stateTable_rsp.empty())',
            'if (!stateTable_rsp.empty() && (!isResponse || !request_rx_owners.empty()))')
        t = once(t, '\t\t\tstateTable_rsp.read(qpState);', r'''
            stateTable_rsp.read(qpState);
            if(isResponse) {
                as02ReqToken token=request_rx_owners.read();
                if(!as02_req_token_valid(token) || token(23,0)!=meta.dest_qp || emeta.isNak ||
                   (meta.op_code!=RC_ACK && meta.op_code!=RC_RDMA_READ_RESP_ONLY)) {
                    fault=true;regRequestRxFault=1;return;
                }
                meta.request_owned=true;meta.request_token=token;
            }''')
        old = 'metaOut.write(ibhMeta(meta.op_code, meta.partition_key, meta.dest_qp, meta.psn, meta.validPSN));'
        if t.count(old) != 2:
            raise ValueError('unreviewed RX BTH forwarding branches')
        t = t.replace(old,
            'ibhMeta b(meta.op_code,meta.partition_key,meta.dest_qp,meta.psn,meta.validPSN);\n'
            '                b.request_owned=meta.request_owned;b.request_token=meta.request_token;metaOut.write(b);')
        t = once(t, 'rx2retrans_upd.write(retransUpdate(meta.dest_qp, meta.psn, meta.op_code));',
            'retransUpdate u(meta.dest_qp,meta.psn,meta.op_code);\n'
            '                    u.request_owned=meta.request_owned;u.request_token=meta.request_token;rx2retrans_upd.write(u);')
        return once(t, 'rxClearTimer_req.write(rxTimerUpdate(meta.dest_qp, meta.psn == qpState.max_forward));',
            'rxTimerUpdate u(meta.dest_qp,meta.psn==qpState.max_forward);u.request_owned=meta.request_owned;\n'
            '                    u.request_token=meta.request_token;u.request_psn=meta.psn;rxClearTimer_req.write(u);')
    out[cpp] = change(out[cpp], 'void rx_ibh_fsm(', rx_bth)

    def rx_exh(t):
        t = once(t, 'ap_uint<1>& regRecvBindFault\n',
            'ap_uint<1>& regRecvBindFault,stream<as02ReqStep>& request_ack_consumed,ap_uint<1>& regRequestExhFault\n')
        t = once(t, 'static bool recv_bind_fault=false;regRecvBindFault=recv_bind_fault;',
            'static bool recv_bind_fault=false;regRecvBindFault=recv_bind_fault;\n'
            '    static bool request_fault=false;regRequestExhFault=request_fault;if(request_fault)return;')
        t = once(t, 'rx_pkgShiftTypeFifo.write(pkgShift(SHIFT_AETH, meta.dest_qp));',
            'if(meta.request_owned && (!readReqInit.request_owned || readReqInit.request_token!=meta.request_token ||\n'
            '               meta.op_code!=RC_RDMA_READ_RESP_ONLY || ackHeader.isNAK())) {request_fault=true;regRequestExhFault=1;return;}\n'
            '            pkgShift s(SHIFT_AETH,meta.dest_qp);s.request_owned=meta.request_owned;s.request_token=meta.request_token;\n'
            '            s.request_psn=meta.psn;s.request_opcode=ap_uint<8>(meta.op_code);rx_pkgShiftTypeFifo.write(s);')
        a = t.index('\t\tcase RC_ACK:')
        b = t.index('\t\tdefault:', a)
        ack = t[a:b]
        ack = once(ack, '\t\t\tpe_fsmState = META;',
            '            if(meta.request_owned) {\n'
            '                if(ackHeader.isNAK()){request_fault=true;regRequestExhFault=1;return;}\n'
            '                request_ack_consumed.write(as02ReqStep(meta.request_token,meta.psn,ap_uint<8>(meta.op_code)));\n'
            '            }\n\t\t\tpe_fsmState = META;')
        return t[:a]+ack+t[b:]
    out[cpp] = change(out[cpp], 'void rx_exh_fsm(', rx_exh)

    def rx_payload(t):
        t = once(t, 'stream<as02RecvProof>& recv_data_done\n',
            'stream<as02RecvProof>& recv_data_done,stream<as02ReqStep>& request_read_consumed\n')
        t = once(t, 'FWD_NONE, RECV_DONE', 'FWD_NONE, RECV_DONE, REQUEST_DONE')
        t = t.replace('shift.receive_owned ? RECV_DONE : IDLE',
            'shift.receive_owned ? RECV_DONE : shift.request_owned ? REQUEST_DONE : IDLE')
        return once(t, '\t}//switch',
            '    case REQUEST_DONE:\n        request_read_consumed.write(as02ReqStep(shift.request_token,shift.request_psn,shift.request_opcode));state=IDLE;break;\n\t}//switch')
    out[cpp] = change(out[cpp], 'void merge_rx_pkgs(', rx_payload)

    def tx_timer(t):
        t = once(t, 'stream<ap_uint<24> >&\ttxSetTimer_req,',
            'stream<as02ReqTxTimer>&\ttxSetTimer_req,')
        t = once(t, 'meta.op_code == RC_RDMA_READ_REQUEST)\n\t\t\t{\n\t\t\t\ttxSetTimer_req.write(meta.qpn);',
            'meta.op_code == RC_RDMA_READ_REQUEST || (meta.request_owned && meta.op_code == RC_SEND_ONLY))\n\t\t\t{\n'
            '                as02ReqTxTimer r;r.qpn=meta.qpn;r.owned=meta.request_owned;r.token=meta.request_token;txSetTimer_req.write(r);')
        return t
    out[cpp] = change(out[cpp], 'void generate_exh(', tx_timer)
    out[cpp] = once(out[cpp], 'static stream<ap_uint<24> > txSetTimer_req("txSetTimer_req");',
        'static stream<as02ReqTxTimer> txSetTimer_req("txSetTimer_req");')

    t = out[timer]
    t = once(t, 'struct rxTimerUpdate\n{',
        'struct rxTimerUpdate\n{\n    bool request_owned=false;as02ReqToken request_token=0;ap_uint<24> request_psn=0;')
    a, b = span(t, 'void as02_native_external_replay_timer(')
    t = t[:a]+r'''void as02_native_external_replay_timer(
    stream<rxTimerUpdate>& rx,stream<as02ReqTxTimer>& tx,
    stream<as02ReqStep>& rx_done,stream<as02ReqTxTimer>& tx_done,ap_uint<1>& regFault) {
#pragma HLS pipeline II=1
#pragma HLS inline off
    static bool fault=false;regFault=fault;if(fault)return;
    if(!rx.empty()) {
        rxTimerUpdate r=rx.read();
        if(r.request_owned) {
            if(!as02_req_token_valid(r.request_token) || r.request_token(23,0)!=r.qpn || !r.stop) {fault=true;regFault=1;return;}
            rx_done.write(as02ReqStep(r.request_token,r.request_psn,0));
        }
    } else if(!tx.empty()) {
        as02ReqTxTimer r=tx.read();
        if(r.owned) {
            if(!as02_req_token_valid(r.token) || r.token(23,0)!=r.qpn){fault=true;regFault=1;return;}
            tx_done.write(r);
        }
    }
}'''+t[b:]
    out[timer] = t
    r = out[retrans]
    for name in ['retransUpdate', 'retransRdInit', 'retransMeta', 'retransAddrLen', 'retransEntry', 'retransMetaEntry']:
        r = once(r, 'struct '+name+'\n{',
            'struct '+name+'\n{\n    bool request_owned=false;as02ReqToken request_token=0;')
    r = once(r, ':rkey(addrlen.rkey), rkey_valid(addrlen.rkey_valid)',
        ':request_owned(meta.request_owned),request_token(meta.request_token),rkey(addrlen.rkey), rkey_valid(addrlen.rkey_valid)')
    r = once(r, ':rkey(e.rkey), rkey_valid(e.rkey_valid)',
        ':request_owned(e.request_owned),request_token(e.request_token),rkey(e.rkey), rkey_valid(e.rkey_valid)')
    r = once(r, 'struct pointerUpdate\n{',
        'struct pointerUpdate\n{\n    bool request_release=false;as02ReqReclaim request_ref;')

    def args(t, extra):
        left = t.index('{')
        end = t.rfind(')', 0, left)
        return t[:end]+',\n    '+extra+t[end:]

    def metadata(t):
        t = args(t, 'stream<as02ReqInsert>& request_inserted,ap_uint<1>& regRequestMetaFault')
        # The new real readback has a loop-carried write/read dependency.
        # Retaining the original "inter false" assertion lets synthesis read
        # the old BRAM row before the preceding insertion reaches memory.
        t = once(t, '#pragma HLS DEPENDENCE variable=meta_table inter false',
            '// Real requester insertion/readback dependency must be preserved.')
        t = once(t, 'static retransMetaEntry meta_table[META_TABLE_SIZE];',
            'static retransMetaEntry meta_table[META_TABLE_SIZE];\n'
            '    static bool request_fault=false;regRequestMetaFault=request_fault;if(request_fault)return;\n'
            '    static ap_uint<2> receipt_phase=0;static ap_uint<16> receipt_index=0;static retransMetaEntry receipt_entry;')
        t = once(t, '\tretransMetaReq req;', r'''
    // Read back the SAME stored record on a subsequent actual invocation.
    // This is not an admission echo, metadata.valid count or shadow table.
    if(receipt_phase==1) {
        receipt_entry=meta_table[receipt_index];receipt_phase=2;return;
    } else if(receipt_phase==2) {
        if(!receipt_entry.request_owned || !receipt_entry.valid || !receipt_entry.isTail ||
           !as02_req_token_valid(receipt_entry.request_token)) {request_fault=true;regRequestMetaFault=1;return;}
        as02ReqInsert p;p.ref.index=receipt_index;
        p.ref.step=as02ReqStep(receipt_entry.request_token,receipt_entry.psn,ap_uint<8>(receipt_entry.opCode));
        p.local=receipt_entry.localAddr;p.remote=receipt_entry.remoteAddr;p.length=receipt_entry.length;
        p.rkey=receipt_entry.rkey;p.rkey_valid=receipt_entry.rkey_valid;p.host=receipt_entry.host;
        p.lst=receipt_entry.lst;p.offs=receipt_entry.offs;request_inserted.write(p);receipt_phase=0;return;
    }
    retransMetaReq req;''')
        t = once(t, 'meta_upd_req.read(req);',
            'meta_upd_req.read(req);\n        if(req.idx>=META_TABLE_SIZE){request_fault=true;regRequestMetaFault=1;return;}')
        return once(t, 'meta_table[req.idx] = req.entry;',
            'meta_table[req.idx] = req.entry;\n'
            '            if(req.entry.request_owned){receipt_index=req.idx;receipt_phase=1;}')
    r = change(r, 'void retrans_meta_table(', metadata)

    def pointer(t):
        t = args(t, 'stream<as02ReqReclaim>& request_pointer_done,ap_uint<1>& regRequestPointerFault')
        t = once(t, 'static retransPointerEntry ptr_table[MAX_QPS];',
            'static retransPointerEntry ptr_table[MAX_QPS];\n'
            '    static bool request_fault=false;regRequestPointerFault=request_fault;if(request_fault)return;\n'
            '    static ap_uint<2> receipt_phase=0;static as02ReqReclaim receipt_ref;static retransPointerEntry receipt_entry;')
        t = once(t, '\tpointerUpdate upd;', r'''
    pointerUpdate upd;
    if(receipt_phase==1) {
        receipt_entry=ptr_table[receipt_ref.step.token(23,0)];receipt_phase=2;return;
    } else if(receipt_phase==2) {
        if(receipt_entry.valid || pt_isLocked || pt_wait){request_fault=true;regRequestPointerFault=1;return;}
        request_pointer_done.write(receipt_ref);receipt_phase=0;return;
    }''')
        t = once(t, 'ptr_table[upd.qpn] = upd.entry;',
            'if(upd.qpn>=MAX_QPS){request_fault=true;regRequestPointerFault=1;return;}\n'
            '        ptr_table[upd.qpn] = upd.entry;\n'
            '        if(upd.request_release) {\n'
            '            if(!as02_req_token_valid(upd.request_ref.step.token) || upd.qpn!=upd.request_ref.step.token(23,0) ||\n'
            '               upd.request_ref.index>=META_TABLE_SIZE || upd.entry.valid){request_fault=true;regRequestPointerFault=1;return;}\n'
            '            receipt_ref=upd.request_ref;receipt_phase=1;\n'
            '        }')
        return t
    r = change(r, 'void retrans_pointer_table(', pointer)

    def process(t):
        t = args(t, 'ap_uint<1>& regRequestProcessFault')
        t = once(t, 'stream<ap_uint<16> >&\t\t\treleaseFifo,',
            'stream<as02ReqRelease>&\t\t\treleaseFifo,')
        t = once(t, 'static retransStateType rt_state = MAIN;',
            'static retransStateType rt_state = MAIN;\n'
            '    static bool request_fault=false;regRequestProcessFault=request_fault;if(request_fault)return;\n'
            '    static ap_uint<16> request_release_index=0;')
        t = once(t, 'retrans2rx_init.write(retransRdInit(meta.localAddr, meta.lst));',
            'retransRdInit d(meta.localAddr,meta.lst);d.request_owned=meta.request_owned;d.request_token=meta.request_token;retrans2rx_init.write(d);')
        a, b = t.index('\tcase UPDATE_1:'), t.index('\tcase RETRANS_0:')
        update = t[a:b]
        update = once(update, 'metaRspFifo.read(meta);', r'''
            metaRspFifo.read(meta);
            if(update.request_owned && (!meta.request_owned || meta.request_token!=update.request_token ||
               !as02_req_token_valid(meta.request_token) || update.qpn!=meta.request_token(23,0) ||
               update.latest_acked_req!=meta.psn || !meta.valid || !meta.isTail ||
               !((meta.opCode==RC_RDMA_READ_REQUEST && update.op_code==RC_RDMA_READ_RESP_ONLY) ||
                 ((meta.opCode==RC_RDMA_WRITE_ONLY || meta.opCode==RC_SEND_ONLY) && update.op_code==RC_ACK)))) {
                request_fault=true;regRequestProcessFault=1;return;
            }''')
        update = once(update, 'releaseFifo.write(curr);',
            'as02ReqRelease r;r.index=curr;r.owned=meta.request_owned;\n'
            '                    r.step=as02ReqStep(meta.request_token,meta.psn,ap_uint<8>(meta.opCode));\n'
            '                    request_release_index=curr;releaseFifo.write(r);')
        update = once(update, 'pointerUpdFifo.write(pointerUpdate(update.qpn, ptrMeta));',
            'pointerUpdate p(update.qpn,ptrMeta);p.request_release=meta.request_owned;\n'
            '            p.request_ref.index=request_release_index;p.request_ref.step=as02ReqStep(meta.request_token,meta.psn,ap_uint<8>(meta.opCode));\n'
            '            pointerUpdFifo.write(p);')
        return t[:a]+update+t[b:]
    r = change(r, 'void process_retransmissions(', process)

    def pool(t):
        t = args(t, 'stream<as02ReqReclaim>& request_pool_done,ap_uint<1>& regRequestPoolFault')
        t = once(t, 'stream<ap_uint<16> >& rt_releaseFifo', 'stream<as02ReqRelease>& rt_releaseFifo')
        t = once(t, 'static ap_uint<16> freeListCounter = 0;',
            'static ap_uint<16> freeListCounter = 0;\n'
            '    static bool request_fault=false,pending=false;static as02ReqReclaim receipt;\n'
            '    regRequestPoolFault=request_fault;if(request_fault)return;\n'
            '    if(pending){request_pool_done.write(receipt);pending=false;return;}')
        return once(t, 'rt_freeListFifo.write(rt_releaseFifo.read());', r'''
        as02ReqRelease r=rt_releaseFifo.read();
        if(r.index>=META_TABLE_SIZE || (r.owned && !as02_req_token_valid(r.step.token))) {
            request_fault=true;regRequestPoolFault=1;return;
        }
        rt_freeListFifo.write(r.index);
        if(r.owned){receipt.index=r.index;receipt.step=r.step;pending=true;}''')
    r = change(r, 'void freelist_handler(', pool)

    def retrans_top(t):
        t = args(t, 'stream<as02ReqInsert>& request_inserted,stream<as02ReqReclaim>& request_pointer_done,\n'
            '    stream<as02ReqReclaim>& request_pool_done,ap_uint<1>& regRequestRetransFault')
        t = once(t, 'static stream<ap_uint<16> > rt_releaseFifo("rt_releaseFifo");',
            'static stream<as02ReqRelease> rt_releaseFifo("rt_releaseFifo");\n'
            '    ap_uint<1> mf=0,pf=0,ff=0,rf=0;')
        t = once(t, 'freelist_handler<INSTID>(rt_releaseFifo, rt_freeListFifo);',
            'freelist_handler<INSTID>(rt_releaseFifo, rt_freeListFifo,request_pool_done,ff);')
        t = once(t, 'retrans_pointer_table<INSTID>(rt_pointerReqFifo, rt_pointerUpdFifo, rt_pointerRspFifo);',
            'retrans_pointer_table<INSTID>(rt_pointerReqFifo, rt_pointerUpdFifo, rt_pointerRspFifo,request_pointer_done,pf);')
        t = once(t, 'rt_metaRspFifo);', 'rt_metaRspFifo,request_inserted,mf);')
        t = once(t, '\t\tretrans2event\n\t);',
            '\t\tretrans2event,rf\n\t);\n    regRequestRetransFault=mf|pf|ff|rf;')
        return t
    out[retrans] = change(r, 'void retransmitter(', retrans_top)

    def merge_request(t):
        t = args(t, 'ap_uint<1>& regRequestMergeFault')
        t = once(t, '\tretransMeta meta;',
            '    static bool fault=false;regRequestMergeFault=fault;if(fault)return;\n\tretransMeta meta;')
        return once(t, 'tx2retrans_insertRequest.write(retransEntry(meta, addrlen));',
            'if(meta.request_owned!=addrlen.request_owned || (meta.request_owned &&\n'
            '           (meta.request_token!=addrlen.request_token || !as02_req_token_valid(meta.request_token) || meta.qpn!=meta.request_token(23,0))))\n'
            '            {fault=true;regRequestMergeFault=1;return;}\n'
            '        tx2retrans_insertRequest.write(retransEntry(meta, addrlen));')
    out[cpp] = change(out[cpp], 'void merge_retrans_request(', merge_request)

    st = out[state]
    if st.count('hls::stream<ap_uint<56>>& recvFence_rsp') != 2:
        raise ValueError('request fence actual state declarations changed')
    st = st.replace('hls::stream<ap_uint<56>>& recvFence_rsp',
        'hls::stream<ap_uint<56>>& recvFence_rsp,\n'
        '    hls::stream<as02ReqToken>& requestFence_req,hls::stream<as02ReqState>& requestFence_rsp')
    def request_state(t):
        return t[:-1]+r'''
    else if(!requestFence_req.empty()) {
        as02ReqToken token=requestFence_req.read();as02ReqState r;r.token=token;
        if(!as02_req_token_valid(token))r.error=1;
        else {
            stateTableEntry e=state_table[token(23,0)];r.next=e.req_next_psn;r.acked=e.req_old_unack;
        }
        requestFence_rsp.write(r);
    }
}'''
    out[state] = change(st, 'void state_table(\t\t\n', request_state)
    channels = r'''
    static stream<ap_uint<588>> request_admitted("request_admitted");
    static stream<as02ReqToken> request_rx_owners("request_rx_owners");
    static stream<as02ReqStep> request_issued("request_issued"),request_ack_consumed("request_ack_consumed");
    static stream<as02ReqStep> request_read_consumed("request_read_consumed"),request_rx_timer_done("request_rx_timer_done");
    static stream<as02ReqInsert> request_inserted("request_inserted");
    static stream<as02ReqReclaim> request_pointer_done("request_pointer_done"),request_pool_done("request_pool_done");
    static stream<as02ReqTxTimer> request_tx_timer_done("request_tx_timer_done");
    static stream<as02ReqToken> requestFence_req("requestFence_req");
    static stream<as02ReqState> requestFence_rsp("requestFence_rsp");
    #pragma HLS STREAM depth=2 variable=request_admitted
    #pragma HLS STREAM depth=2 variable=request_rx_owners
    #pragma HLS STREAM depth=2 variable=request_issued
    #pragma HLS STREAM depth=2 variable=request_ack_consumed
    #pragma HLS STREAM depth=2 variable=request_read_consumed
    #pragma HLS STREAM depth=2 variable=request_rx_timer_done
    #pragma HLS STREAM depth=2 variable=request_inserted
    #pragma HLS STREAM depth=2 variable=request_pointer_done
    #pragma HLS STREAM depth=2 variable=request_pool_done
    #pragma HLS STREAM depth=2 variable=request_tx_timer_done
    #pragma HLS STREAM depth=2 variable=requestFence_req
    #pragma HLS STREAM depth=2 variable=requestFence_rsp
    ap_uint<1> request_app_fault=0,request_rx_fault=0,request_exh_fault=0,request_merge_fault=0;
    ap_uint<1> request_retrans_fault=0,request_timer_fault=0,request_join_fault=0;
'''
    a = out[cpp].index('void ib_transport_protocol(')
    left = out[cpp].index('{', a)
    out[cpp] = out[cpp][:left+1]+channels+out[cpp][left+1:]
    for old, new in [
        ('        regRetransCount\n\t);',
         '        regRetransCount,s_axis_request_owner,request_admitted,request_rx_owners,request_app_fault\n\t);'),
        ('\t\tregInvalidPsnDropCount\n\t);',
         '\t\tregInvalidPsnDropCount,request_rx_owners,request_rx_fault\n\t);'),
        ('rx_pkgShiftTypeFifo,s_axis_recv_owner,recv_bind_fault\n',
         'rx_pkgShiftTypeFifo,s_axis_recv_owner,recv_bind_fault,request_ack_consumed,request_exh_fault\n'),
        ('m_axis_mem_write_data,recv_data_done);',
         'm_axis_mem_write_data,recv_data_done,request_read_consumed);'),
        ('\t\ttx_ibhHeaderFifo\n\t);', '\t\ttx_ibhHeaderFifo,request_issued\n\t);'),
        ('stateTable2qpi_rsp,recvFence_req,recvFence_rsp\n',
         'stateTable2qpi_rsp,recvFence_req,recvFence_rsp,requestFence_req,requestFence_rsp\n'),
        ('merge_retrans_request(tx2retrans_insertMeta, tx2retrans_insertAddrLen, tx2retrans_insertRequest);',
         'merge_retrans_request(tx2retrans_insertMeta, tx2retrans_insertAddrLen, tx2retrans_insertRequest,request_merge_fault);'),
        ('\t\ttxSetTimer_req\n\t);',
         '\t\ttxSetTimer_req,request_rx_timer_done,request_tx_timer_done,request_timer_fault\n\t);'),
        ('\t\tretransmitter2exh_eventFifo\n\t);',
         '\t\tretransmitter2exh_eventFifo,request_inserted,request_pointer_done,request_pool_done,request_retrans_fault\n\t);')
    ]:
        out[cpp] = once(out[cpp], old, new)
    def finish(t):
        return t[:-1]+r'''
    ap_uint<1> request_faults=request_app_fault|request_rx_fault|request_exh_fault|request_merge_fault|request_retrans_fault|request_timer_fault;
    as02_request_retire_join<INSTID>(request_admitted,request_issued,request_inserted,
        request_ack_consumed,request_read_consumed,request_pointer_done,request_pool_done,
        request_tx_timer_done,request_rx_timer_done,requestFence_req,requestFence_rsp,
        m_axis_request_done,request_faults,request_join_fault);
    regRequestFault=request_faults|request_join_fault;
}'''
    out[cpp] = change(out[cpp], 'void ib_transport_protocol(', finish)
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    if a.output.exists():
        p.error('preserve prior source/evidence')
    before = {str(x.relative_to(qp.BASE)): qp.digest(x) for x in qp.BASE.rglob('*') if x.is_file()}
    files = derive()
    shutil.copytree(qp.BASE/'fns', a.output/'fns')
    shutil.copytree(qp.BASE/'adapter', a.output/'adapter')
    for n, text in files.items():
        (a.output/'fns'/n).write_text(text)
    if before != {n: qp.digest(qp.BASE/n) for n in before}:
        raise ValueError('original input changed')
    info = dict(scope=__doc__, source_base=str(qp.BASE), source_sha256=before,
        generator_sha256=qp.digest(__file__), parent_generator_sha256=qp.digest(recv.__file__),
        derived_sources={n: hashlib.sha256(t.encode()).hexdigest() for n, t in files.items()},
        original_unchanged=True, external_replay=True, native_rnr=True,
        receive_retirement=True, request_retirement=True, source_only=True,
        HLS_top='rocev2_native_request_top', whole_core_drain_proved=False, hardware_verified=False)
    (a.output/'source.json').write_text(json.dumps(info, indent=2)+'\n')
    print(json.dumps(dict(output=str(a.output), HLS_top=info['HLS_top'], original_unchanged=True)))


if __name__ == '__main__':
    main()
