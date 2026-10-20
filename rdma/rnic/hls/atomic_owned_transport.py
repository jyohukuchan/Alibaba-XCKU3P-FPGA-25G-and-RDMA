#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Owned Atomic service and consumed SAME-table PSN/MSN completion.

Checked derivative; previous Atomic/Immediate generators remain rollback.
Uses the existing RX query/write channels in order, with both RX FSM owners
held through their real readbacks. No new sequence table or fake RQ owner.
Core done is NOT positive-response MAC/native retirement or safe reset/unpin.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

import atomic_transport as base

once=base.once;parent=base.parent;CPP=base.CPP;HPP=base.HPP;TOP=base.TOP
NAME='rocev2_native_atomic_owned_top'

TYPES=r'''
// Explicit scalar ABI. Owner144: QPN24,epoch64,requestPSN24,packetNonce32.
// Request512=old368+owner144; reply392=old248+the SAME owner144.
// Done224: owner144,opcode8,actualEPSN24,actualMSN24,flags8,error8,reserved8.
// Flags: bit0 service consumed,bit1 same PSN readback,bit2 same MSN readback,
// bit3 response expected,bit4 fresh advancement,bit5 proven no-packet drop.
// Response packets still need their OWN actual MAC SFD/EOF/tail proof.
typedef ap_uint<144> as02AtomicOwner;
typedef ap_uint<224> as02AtomicDone;
typedef ap_uint<224> as02AtomicCommit;
inline bool as02_atomic_owner_valid(as02AtomicOwner o) {
    return o(23,0)<MAX_QPS && o(87,24)!=0 && o(143,112)!=0;
}
'''

IBH_WAIT=r'''
    case ATOMIC_BIND:
        if(!atomic_owners.empty()) {
            as02AtomicOwner o=atomic_owners.read();
            if(!as02_atomic_owner_valid(o) || o(23,0)!=meta.dest_qp || o(111,88)!=meta.psn) {
                fault=true;regRequestRxFault=1;break;
            }
            meta.atomic_owner=o;
            stateTable_upd_req.write(rxStateReq(meta.dest_qp,false));fsmState=PROCESS;
        }
        break;
    case ATOMIC_WAIT:
        if(!atomic_commit.empty()) {
            auto c=atomic_commit.read();ap_uint<8> flags=c(207,200);
            bool advance=flags[4],drop=flags[5];
            ap_uint<24> expected=advance ? ap_uint<24>(meta.psn+1):meta.atomic_epsn;
            if(c(143,0)!=meta.atomic_owner || c(151,144)!=meta.op_code ||
               c(175,152)!=expected || c(223,208)!=0 ||
               flags(2,0)!=5 || flags(7,6)!=0 || bool(flags[3])==drop || (advance && drop)) {
                fault=true;regRequestRxFault=1;break;
            }
            atomic_pending=c;
            if(advance)stateTable_upd_req.write(rxStateReq(meta.dest_qp,expected,false));
            fsmState=ATOMIC_PSN_QUERY;
        }
        break;
    case ATOMIC_PSN_QUERY:
        // Same FIFO, strictly AFTER the write, and no next RX owner yet.
        stateTable_upd_req.write(rxStateReq(meta.dest_qp,false));fsmState=ATOMIC_PSN_REPLY;
        break;
    case ATOMIC_PSN_REPLY:
        if(!stateTable_rsp.empty()) {
            auto s=stateTable_rsp.read();
            if(s.epsn!=atomic_pending(175,152)) {fault=true;regRequestRxFault=1;break;}
            as02AtomicDone d=atomic_pending;d[201]=1;
            atomic_done.write(d);fsmState=LOAD;
        }
        break;
'''

EXH_WAIT=r'''
    case ATOMIC_REPLY:
        if(!atomic_replies.empty()) {
            auto r=atomic_replies.read();ap_uint<6> bytes=r(245,240);
            bool advance=r[246],drop=r[247];ap_uint<8> op=r(7,0);
            ap_uint<24> response_psn=as02_be24(r(95,72));
            ap_uint<24> response_msn=as02_be24(r(127,104));
            bool base_ok=r(215,192)==meta.dest_qp && r(239,216)==meta.psn && r(391,248)==meta.atomic_owner;
            bool wire_ok=r(15,8)==0 && r(31,16)==0xffff && r(39,32)==0 && r(71,64)==0;
            bool success=op==RC_ATOMIC_ACK && bytes==24 && r(103,96)==0x1f;
            bool nak=op==RC_ACK && bytes==16 && !advance &&
                (r(103,96)==0x60 || r(103,96)==0x61 || r(103,96)==0x62) && r(191,128)==0;
            bool normal_psn=response_psn==meta.psn;
            bool sequence_nak=nak && r(103,96)==0x60 && response_psn==meta.atomic_epsn;
            if(!base_ok || (drop && (advance || bytes!=0 || r(191,0)!=0)) ||
              (!drop && (!wire_ok || (!success && !nak) || (!normal_psn && !sequence_nak))) ||
              (advance && (!success || meta.psn!=meta.atomic_epsn || response_msn!=ap_uint<24>(dmaMeta.msn+1)))) {
                request_fault=true;regRequestExhFault=1;break;
            }
            if(advance)rxExh2msnTable_upd_req.write(rxMsnReq(meta.dest_qp,response_msn));
            if(!drop) {
                ackEvent a(meta.dest_qp,response_psn,false);a.atomic_reply=true;
                a.atomic_opcode=op;a.atomic_bytes=bytes;a.atomic_exh=r(191,96);
                rx_exhEventMetaFifo.write(a);
            }
            // A cached replay's wire MSN may be OLD. The readback must be
            // the CURRENT unchanged common MSN, not that cached AETH value.
            atomic_expected_msn=ap_uint<24>(dmaMeta.msn+ap_uint<24>(advance));
            atomic_flags=5;atomic_flags[3]=!drop;atomic_flags[4]=advance;atomic_flags[5]=drop;
            pe_fsmState=ATOMIC_MSN_QUERY;
        }
        break;
    case ATOMIC_MSN_QUERY:
        rxExh2msnTable_upd_req.write(rxMsnReq(meta.dest_qp));pe_fsmState=ATOMIC_MSN_REPLY;
        break;
    case ATOMIC_MSN_REPLY:
        if(!msnTable2rxExh_rsp.empty()) {
            auto s=msnTable2rxExh_rsp.read();
            if(s.msn!=atomic_expected_msn) {request_fault=true;regRequestExhFault=1;break;}
            as02AtomicCommit c=0;c(143,0)=meta.atomic_owner;c(151,144)=meta.op_code;
            c(175,152)=atomic_flags[4] ? ap_uint<24>(meta.psn+1):meta.atomic_epsn;
            c(199,176)=s.msn;c(207,200)=atomic_flags;
            atomic_commit.write(c);pe_fsmState=META;
        }
        break;
'''


def derive():
    out=base.derive()
    out[HPP]=once(out[HPP],'typedef ap_uint<368> as02AtomicRequest;',
        'typedef ap_uint<512> as02AtomicRequest;')
    out[HPP]=once(out[HPP],'typedef ap_uint<248> as02AtomicReply;',
        'typedef ap_uint<392> as02AtomicReply;')
    out[HPP]=once(out[HPP],'struct as02AtomicCommit {ap_uint<24> qpn=0,psn=0;bool advance=false;};',TYPES)
    out[HPP]=once(out[HPP],'ap_uint<24> atomic_epsn=0;',
        'ap_uint<24> atomic_epsn=0;as02AtomicOwner atomic_owner=0;')
    def ibh(t):
        t=once(t,'stream<as02AtomicCommit>& atomic_commit,',
            'stream<as02AtomicOwner>& atomic_owners,stream<as02AtomicDone>& atomic_done,stream<as02AtomicCommit>& atomic_commit,')
        t=once(t,'{LOAD, PROCESS, ATOMIC_WAIT}',
            '{LOAD, PROCESS, ATOMIC_BIND, ATOMIC_WAIT, ATOMIC_PSN_QUERY, ATOMIC_PSN_REPLY}')
        t=once(t,'static ibhMeta meta;','static ibhMeta meta;static as02AtomicDone atomic_pending=0;')
        t=once(t,'stateTable_upd_req.write(rxStateReq(meta.dest_qp, isResponse));\n\t\t\tfsmState = PROCESS;',
            'if(as02_atomic_opcode(meta.op_code))fsmState=ATOMIC_BIND;\n'
            '            else {stateTable_upd_req.write(rxStateReq(meta.dest_qp,isResponse));fsmState=PROCESS;}')
        t=once(t,'ibhMeta b=meta;b.atomic_epsn=qpState.epsn;',
            'meta.atomic_epsn=qpState.epsn;ibhMeta b=meta;')
        return once(t,base.WAIT,IBH_WAIT)
    out[CPP]=parent.change(out[CPP],'void rx_ibh_fsm(',ibh)
    def exh(t):
        t=once(t,'{META, DMA_META, DATA, ATOMIC_REPLY}',
            '{META, DMA_META, DATA, ATOMIC_REPLY, ATOMIC_MSN_QUERY, ATOMIC_MSN_REPLY}')
        t=once(t,'static dmaState dmaMeta;',
            'static dmaState dmaMeta;static ap_uint<24> atomic_expected_msn=0;static ap_uint<8> atomic_flags=0;')
        t=once(t,'r(343,320)=meta.atomic_epsn;r(367,344)=dmaMeta.msn;',
            'r(343,320)=meta.atomic_epsn;r(367,344)=dmaMeta.msn;r(511,368)=meta.atomic_owner;')
        return once(t,base.EXH_WAIT,EXH_WAIT)
    out[CPP]=parent.change(out[CPP],'void rx_exh_fsm(',exh)
    for name in [HPP,CPP,TOP]:
        out[name]=out[name].replace('stream<as02AtomicRequest>& m_axis_atomic_request,',
            'stream<as02AtomicOwner>& s_axis_atomic_owner,stream<as02AtomicDone>& m_axis_atomic_done,stream<as02AtomicRequest>& m_axis_atomic_request,')
        out[name]=out[name].replace('m_axis_atomic_request,s_axis_atomic_reply,s_axis_rnr_event,',
            's_axis_atomic_owner,m_axis_atomic_done,m_axis_atomic_request,s_axis_atomic_reply,s_axis_rnr_event,')
    out[CPP]=once(out[CPP],'regInvalidPsnDropCount,atomic_commit,request_rx_owners,',
        'regInvalidPsnDropCount,s_axis_atomic_owner,m_axis_atomic_done,atomic_commit,request_rx_owners,')
    if not out[TOP].count('#pragma HLS INTERFACE axis register port=m_axis_atomic_request'):
        raise ValueError('Atomic AXIS top anchor changed')
    out[TOP]=out[TOP].replace('#pragma HLS INTERFACE axis register port=m_axis_atomic_request',
        '#pragma HLS INTERFACE axis register port=s_axis_atomic_owner\n'
        '#pragma HLS INTERFACE axis register port=m_axis_atomic_done\n'
        '#pragma HLS INTERFACE axis register port=m_axis_atomic_request')
    out[TOP]=out[TOP].replace('rocev2_native_atomic_top',NAME)
    return out


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():p.error('preserve previous source')
    original=parent.qp.BASE
    before={str(x.relative_to(original)):parent.qp.digest(x)for x in original.rglob('*')if x.is_file()}
    files=derive();shutil.copytree(original/'fns',a.output/'fns');shutil.copytree(original/'adapter',a.output/'adapter')
    for n,t in files.items():(a.output/'fns'/n).write_text(t)
    if before!={n:parent.qp.digest(original/n)for n in before}:raise ValueError('original changed')
    info=dict(scope=__doc__,source_base=str(original),source_sha256=before,
        generator_sha256=parent.qp.digest(__file__),
        derived_sources={n:hashlib.sha256(t.encode()).hexdigest()for n,t in files.items()},
        original_unchanged=True,HLS_top=NAME,request_context_bits=620,
        request_immediate=True,receive_immediate=True,atomic_service_request_bits=512,
        atomic_service_reply_bits=392,atomic_owner_bits=144,atomic_core_done_bits=224,
        shared_PSN_MSN=True,same_RX_query_channels_readback=True,native_integration=False,
        atomic_requester=False,source_only=True,hardware_verified=False,whole_core_drain_proved=False)
    (a.output/'source.json').write_text(json.dumps(info,indent=2)+'\n')
    print(json.dumps(dict(output=str(a.output),HLS_top=NAME,original_unchanged=True)))


if __name__=='__main__':main()
