#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Owned ordinary zero WRITE/READ responders in the SAME complete HLS.

No posted RQ, Atomic alias, memory command/data or quiet completion. Actual
RETH EOF, response-header consumption and the SAME RX MSN/PSN readbacks are
required. Trusted outer QP/peer/protection owner and physical MAC lifetime
remain native integration work; this source is not Linux/board signoff.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import zero_rq_transport as base

ROOT=base.ROOT;CPP=base.CPP;HPP=base.HPP;TOP=base.TOP
once=base.once;change=base.change;NAME='rocev2_native_zero_service_top'

TYPES=r'''
// Distinct ordinary service ABI, NEVER a posted RECV or Atomic owner.
// Owner344: QPN24,PD16,epoch64,cookie64,lease16,PSN24,wireOpcode8,
// fullRemoteVA64,fullRKey32,length32(0). No field licenses a memory access.
// Done400: owner344,nextPSN24,actualMSN24,flags8. Core flags0xf prove real
// RETH consumption, MSN readback, response-header consumer, PSN readback.
// Physical response MAC/SFD/EOF/tail lifetime is NOT proved by this receipt.
typedef ap_uint<344> as02ZeroOwner;
typedef ap_uint<400> as02ZeroDone;
inline bool as02_zero_owner_valid(as02ZeroOwner o) {
    return o(23,0)<MAX_QPS && o(103,40)!=0 && o(167,104)!=0 && o(183,168)!=0 &&
        (o(215,208)==RC_RDMA_WRITE_ONLY || o(215,208)==RC_RDMA_READ_REQUEST) && o(343,312)==0;
}
inline ibOpCode as02_zero_response(as02ZeroOwner o) {
    return o(215,208)==RC_RDMA_READ_REQUEST ? RC_RDMA_READ_RESP_ONLY:RC_ACK;
}
'''

IBH_STATES=r'''
    case ZERO_BIND:
        if(!zero_owners.empty()) {
            auto o=zero_owners.read();
            if(emeta.zero_bad || !as02_zero_owner_valid(o) || o(23,0)!=meta.dest_qp ||
               o(207,184)!=meta.psn || o(215,208)!=meta.op_code) {
                fault=true;regRequestRxFault=1;break;
            }
            meta.zero_owned=true;meta.zero_owner=o;
            stateTable_upd_req.write(rxStateReq(meta.dest_qp,false));fsmState=PROCESS;
        }
        break;
    case ZERO_WAIT:
        if(!zero_commit.empty()) {
            auto c=zero_commit.read();
            if(c(343,0)!=meta.zero_owner || c(367,344)!=ap_uint<24>(meta.psn+1) || c(399,392)!=7) {
                fault=true;regRequestRxFault=1;break;
            }
            zero_pending=c;
            stateTable_upd_req.write(rxStateReq(meta.dest_qp,ap_uint<24>(meta.psn+1),false));
            fsmState=ZERO_PSN_QUERY;
        }
        break;
    case ZERO_PSN_QUERY:
        stateTable_upd_req.write(rxStateReq(meta.dest_qp,false));fsmState=ZERO_PSN_REPLY;break;
    case ZERO_PSN_REPLY:
        if(!stateTable_rsp.empty()) {
            auto s=stateTable_rsp.read();
            if(s.epsn!=zero_pending(367,344)) {fault=true;regRequestRxFault=1;break;}
            auto d=zero_pending;d[395]=1;zero_done.write(d);fsmState=LOAD;
        }
        break;
'''

EXH_START=r'''
        if(meta.zero_owned) {
            auto o=meta.zero_owner;auto r=exHeader.getRdmaHeader();
            if(!as02_zero_owner_valid(o) || meta.request_owned || o(23,0)!=meta.dest_qp ||
               o(207,184)!=meta.psn || o(215,208)!=meta.op_code || udpLength!=40 ||
               r.getLength()!=0 || r.getVirtualAddress()!=o(279,216) || r.getRemoteKey()!=o(311,280)) {
                request_fault=true;regRequestExhFault=1;break;
            }
            pkgShift s(SHIFT_NONE,meta.dest_qp);s.zero_service=true;s.zero_owner=o;
            s.zero_reth=r.getRawHeader();rx_pkgShiftTypeFifo.write(s);
            // Keep the REAL RETH on the raw branch. A header-only READ must
            // not disappear in the legacy read/header stripping path.
            rx_pkgSplitTypeFifo.write(pkgSplit(RC_SEND_ONLY));pe_fsmState=ZERO_DATA;break;
        }
'''

EXH_STATES=r'''
    case ZERO_DATA:
        if(!zero_data.empty()) {
            auto o=zero_data.read();
            if(o!=meta.zero_owner) {request_fault=true;regRequestExhFault=1;break;}
            zero_msn=dmaMeta.msn+1;
            rxExh2msnTable_upd_req.write(rxMsnReq(meta.dest_qp,zero_msn));pe_fsmState=ZERO_MSN_QUERY;
        }
        break;
    case ZERO_MSN_QUERY:
        rxExh2msnTable_upd_req.write(rxMsnReq(meta.dest_qp));pe_fsmState=ZERO_MSN_REPLY;break;
    case ZERO_MSN_REPLY:
        if(!msnTable2rxExh_rsp.empty()) {
            auto s=msnTable2rxExh_rsp.read();
            if(s.msn!=zero_msn) {request_fault=true;regRequestExhFault=1;break;}
            ackEvent a(meta.dest_qp,meta.psn,false);a.zero_owned=true;
            a.zero_owner=meta.zero_owner;a.zero_msn=s.msn;rx_exhEventMetaFifo.write(a);
            pe_fsmState=ZERO_TX;
        }
        break;
    case ZERO_TX:
        if(!zero_tx.empty()) {
            auto t=zero_tx.read();
            if(t(343,0)!=meta.zero_owner || t(367,344)!=meta.psn || t(391,368)!=zero_msn || t(399,392)!=4) {
                request_fault=true;regRequestExhFault=1;break;
            }
            as02ZeroDone c=0;c(343,0)=meta.zero_owner;c(367,344)=ap_uint<24>(meta.psn+1);
            c(391,368)=zero_msn;c(399,392)=7;zero_commit.write(c);pe_fsmState=META;
        }
        break;
'''


def derive():
    out=base.derive()
    out[HPP]=once(out[HPP],'struct ackEvent\n{',TYPES+'\nstruct ackEvent\n{')
    for name in ['ackEvent','event']:
        out[HPP]=once(out[HPP],'struct '+name+'\n{','struct '+name+'\n{\n'
            '    bool zero_owned=false;as02ZeroOwner zero_owner=0;ap_uint<24> zero_msn=0;')
    out[HPP]=once(out[HPP],':atomic_reply(aev.atomic_reply),',
        ':zero_owned(aev.zero_owned),zero_owner(aev.zero_owner),zero_msn(aev.zero_msn),atomic_reply(aev.atomic_reply),')
    out[HPP]=once(out[HPP],'op_code(RC_ACK), qpn(aev.qpn),',
        'op_code(aev.zero_owned ? as02_zero_response(aev.zero_owner):RC_ACK), addr(0), length(0), qpn(aev.qpn),')
    out[HPP]=once(out[HPP],'struct pkgShift\n{','struct pkgShift\n{\n'
        '    bool zero_service=false;as02ZeroOwner zero_owner=0;ap_uint<128> zero_reth=0;')
    out[HPP]=once(out[HPP],'struct ibhMeta\n{','struct ibhMeta\n{\n'
        '    bool zero_owned=false;as02ZeroOwner zero_owner=0;')
    out[HPP]=once(out[HPP],'struct exhMeta\n{','struct exhMeta\n{\n'
        '    bool zero_service=false,zero_bad=false;')

    def parser(t):
        begin=t.index('\t\t\t\t\t// Decide between READ_REQUEST')
        end=t.index('\t\t\t\t\t// Write out the dissected RDMA',begin)
        t=t[:begin]+r'''
                    bool zero=rdmaHeader.getLength()==0 &&
                        (opCode==RC_RDMA_WRITE_ONLY || opCode==RC_RDMA_READ_REQUEST);
                    ap_uint<22> count=opCode==RC_RDMA_READ_REQUEST ?
                        ap_uint<22>((rdmaHeader.getLength()+(PMTU-1))/PMTU):ap_uint<22>(1);
                    exhMeta e(false,zero ? ap_uint<22>(1):count);e.zero_service=zero;
                    e.zero_bad=zero && (currWord.keep!=ap_uint<64>(0xffff) || !currWord.last);
                    exhMetaFifo.write(e);
'''+t[end:]
        return once(t,'if (checkIfWrite(opCode) && WIDTH > RETH_SIZE)',
            'if ((checkIfWrite(opCode) || (opCode==RC_RDMA_READ_REQUEST && rdmaHeader.getLength()==0)) && WIDTH > RETH_SIZE)')
    out[CPP]=change(out[CPP],'void rx_process_exh(',parser)

    def ibh(t):
        t=once(t,'ap_uint<1>& regRequestRxFault\n',
            'ap_uint<1>& regRequestRxFault,stream<as02ZeroOwner>& zero_owners,stream<as02ZeroDone>& zero_done,stream<as02ZeroDone>& zero_commit\n')
        t=once(t,'ATOMIC_PSN_REPLY};','ATOMIC_PSN_REPLY, ZERO_BIND, ZERO_WAIT, ZERO_PSN_QUERY, ZERO_PSN_REPLY};')
        t=once(t,'static as02AtomicDone atomic_pending=0;',
            'static as02AtomicDone atomic_pending=0;static as02ZeroDone zero_pending=0;')
        t=once(t,'if(as02_atomic_opcode(meta.op_code))fsmState=ATOMIC_BIND;',
            'if(emeta.zero_service)fsmState=ZERO_BIND;\n            else if(as02_atomic_opcode(meta.op_code))fsmState=ATOMIC_BIND;')
        t=once(t,'            if(as02_atomic_opcode(meta.op_code)) {',r'''
            if(meta.zero_owned) {
                if(qpState.epsn!=meta.psn || isResponse) {fault=true;regRequestRxFault=1;break;}
                metaOut.write(meta);ibhDropMetaFifo.write(fwdPolicy(false,false));
                ibhDropFifo.write(false); // Both now carry the real raw RETH.
                fsmState=ZERO_WAIT;break;
            }
            if(as02_atomic_opcode(meta.op_code)) {''')
        return once(t,'    case ATOMIC_BIND:',IBH_STATES+'\n    case ATOMIC_BIND:')
    out[CPP]=change(out[CPP],'void rx_ibh_fsm(',ibh)

    def exh(t):
        t=once(t,'ap_uint<1>& regRequestExhFault\n',
            'ap_uint<1>& regRequestExhFault,stream<as02ZeroOwner>& zero_data,stream<as02ZeroDone>& zero_tx,stream<as02ZeroDone>& zero_commit\n')
        t=once(t,'ATOMIC_MSN_REPLY};','ATOMIC_MSN_REPLY, ZERO_DATA, ZERO_MSN_QUERY, ZERO_MSN_REPLY, ZERO_TX};')
        t=once(t,'static ap_uint<8> atomic_flags=0;',
            'static ap_uint<8> atomic_flags=0;static ap_uint<24> zero_msn=0;')
        t=once(t,'\t\tswitch(meta.op_code)',EXH_START+'\n\t\tswitch(meta.op_code)')
        return once(t,'    case ATOMIC_REPLY:',EXH_STATES+'\n    case ATOMIC_REPLY:')
    out[CPP]=change(out[CPP],'void rx_exh_fsm(',exh)

    def merge(t):
        t=once(t,'ap_uint<1>& regRequestPayloadFault\n',
            'ap_uint<1>& regRequestPayloadFault,stream<as02ZeroOwner>& zero_data\n')
        t=once(t,'ZERO_RECEIVE};','ZERO_RECEIVE, ZERO_SERVICE};')
        t=once(t,'if(shift.zero_receive)state=ZERO_RECEIVE;',
            'if(shift.zero_service)state=ZERO_SERVICE;\n            else if(shift.zero_receive)state=ZERO_RECEIVE;')
        return once(t,'    case ZERO_RECEIVE:',r'''
    case ZERO_SERVICE:
        if(!rx_NoSift2mergerFifo.empty() && !zero_data.full()) {
            auto w=rx_NoSift2mergerFifo.read();
            if(shift.receive_owned || shift.request_owned || !as02_zero_owner_valid(shift.zero_owner) ||
               shift.qpn!=shift.zero_owner(23,0) || w.keep!=ap_uint<64>(0xffff) ||
               !w.last || w.data(127,0)!=shift.zero_reth) {
                fault=true;regRequestPayloadFault=1;state=QUARANTINE;
            } else {zero_data.write(shift.zero_owner);state=IDLE;}
        }
        break;
    case ZERO_RECEIVE:''')
    out[CPP]=change(out[CPP],'void merge_rx_pkgs(',merge)
    out[CPP]=change(out[CPP],'void meta_merger(',lambda t:once(t,
        'aev.atomic_reply ? ibOpCode(unsigned(aev.atomic_opcode)):RC_ACK',
        'aev.zero_owned ? as02_zero_response(aev.zero_owner):aev.atomic_reply ? ibOpCode(unsigned(aev.atomic_opcode)):RC_ACK'))

    def tx(t):
        t=once(t,'stream<as02RecvProof>& recv_ack_done\n',
            'stream<as02RecvProof>& recv_ack_done,stream<as02ZeroDone>& zero_tx\n')
        t=once(t,'{META, GET_MSN, PROCESS, RECV_DONE}',
            '{META, GET_MSN, PROCESS, RECV_DONE, ZERO_DONE}')
        t=once(t,'ge_state = meta.receive_owned ? RECV_DONE : META;',
            'ge_state = meta.zero_owned ? ZERO_DONE : meta.receive_owned ? RECV_DONE : META;')
        return once(t,'    case RECV_DONE: {',r'''
    case ZERO_DONE: {
        as02ZeroDone d=0;d(343,0)=meta.zero_owner;d(367,344)=meta.psn;
        d(391,368)=msnMeta.msn;d(399,392)=4;zero_tx.write(d);ge_state=META;break;
    }
    case RECV_DONE: {''')
    out[CPP]=change(out[CPP],'void generate_exh(',tx)

    # Extend the actual full top and explicit template instances. No sidecar.
    for n in [HPP,CPP,TOP]:
        out[n]=out[n].replace('stream<as02RecvOwner>& s_axis_recv_owner,',
            'stream<as02ZeroOwner>& s_axis_zero_owner,stream<as02ZeroDone>& m_axis_zero_done,stream<as02RecvOwner>& s_axis_recv_owner,')
        out[n]=out[n].replace('s_axis_recv_owner,m_axis_recv_done,',
            's_axis_zero_owner,m_axis_zero_done,s_axis_recv_owner,m_axis_recv_done,')
    # Only the outer full-core API owns the new public ports. The local EXH
    # consumer receives the already bound metadata and internal receipts.
    out[CPP]=change(out[CPP],'void rx_exh_fsm(',lambda t:once(t,
        'stream<as02ZeroOwner>& s_axis_zero_owner,stream<as02ZeroDone>& m_axis_zero_done,stream<as02RecvOwner>& s_axis_recv_owner,',
        'stream<as02RecvOwner>& s_axis_recv_owner,'))
    out[CPP]=once(out[CPP],'    static stream<as02AtomicCommit> atomic_commit',
        '    static stream<as02ZeroOwner> zero_data("zero_data");\n'
        '    static stream<as02ZeroDone> zero_tx("zero_tx"),zero_commit("zero_commit");\n'
        '    #pragma HLS STREAM depth=2 variable=zero_data\n'
        '    #pragma HLS STREAM depth=2 variable=zero_tx\n'
        '    #pragma HLS STREAM depth=2 variable=zero_commit\n'
        '    static stream<as02AtomicCommit> atomic_commit')
    out[CPP]=once(out[CPP],'atomic_commit,request_rx_owners,request_rx_fault',
        'atomic_commit,request_rx_owners,request_rx_fault,s_axis_zero_owner,m_axis_zero_done,zero_commit')
    out[CPP]=once(out[CPP],'recv_bind_fault,request_ack_consumed,request_exh_fault\n',
        'recv_bind_fault,request_ack_consumed,request_exh_fault,zero_data,zero_tx,zero_commit\n')
    out[CPP]=once(out[CPP],'request_read_consumed,request_payload_fault);',
        'request_read_consumed,request_payload_fault,zero_data);')
    out[CPP]=once(out[CPP],'tx_exh2payFifo,recv_ack_done\n','tx_exh2payFifo,recv_ack_done,zero_tx\n')
    anchor='#pragma HLS INTERFACE axis register port=s_axis_recv_owner'
    if out[TOP].count(anchor)!=2:raise ValueError('both original top interface branches required')
    out[TOP]=out[TOP].replace(anchor,
        '#pragma HLS INTERFACE axis register port=s_axis_zero_owner\n'
        '#pragma HLS INTERFACE axis register port=m_axis_zero_done\n'
        '#pragma HLS INTERFACE axis register port=s_axis_recv_owner')
    out[TOP]=out[TOP].replace(base.NAME,NAME)
    return out


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():p.error('preserve previous source')
    original=base.base.base.parent.qp.BASE
    digest=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
    before={str(p.relative_to(original)):digest(p)for p in original.rglob('*')if p.is_file()}
    files=derive();shutil.copytree(original/'fns',a.output/'fns');shutil.copytree(original/'adapter',a.output/'adapter')
    for n,t in files.items():(a.output/'fns'/n).write_text(t)
    if before!={n:digest(original/n)for n in before}:raise ValueError('original source changed')
    info=dict(scope=__doc__,source_base=str(original),source_sha256=before,
        generator_sha256=digest(__file__),parent_generator_sha256=digest(base.__file__),
        derived_sources={n:hashlib.sha256(t.encode()).hexdigest()for n,t in files.items()},
        HLS_top=NAME,original_unchanged=True,request_context_bits=748,SQ_bits=408,request_done_bits=816,
        receive_context_bits=620,receive_owner_bits=680,receive_done_bits=752,
        zero_service_owner_bits=344,zero_service_done_bits=400,
        zero_length_requester=True,zero_RQ_SEND_and_Immediate=True,normal_zero_responder_WRITE_READ=True,
        shared_PSN_MSN=True,native_integration=False,hardware_verified=False,source_only=True,whole_core_drain_proved=False)
    (a.output/'source.json').write_text(json.dumps(info,indent=2)+'\n')
    print(json.dumps(dict(output=str(a.output),HLS_top=NAME,original_unchanged=True)))


if __name__=='__main__':main()
