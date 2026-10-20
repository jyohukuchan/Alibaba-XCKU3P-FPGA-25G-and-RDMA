#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""CAS/FADD service in the SAME complete Immediate HLS PSN/MSN/TX graph.

No second sequence table: hold the real RX-IBH owner until the external
protected Atomic service returns. Only an actual successful new execution
advances the existing PSN/MSN. Replay/NAK/drop never advances them. Physical
service DMA/MAC/native owner binding and requester remain separate work.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

import immediate_transport as base

parent=base.parent;once=parent.once;CPP=base.CPP;HPP=base.HPP
TOP='hls/rocev2/rocev2.cpp'

TYPES=r'''
// Explicit compact AXIS ABI, low byte first. Request368: normalized wire
// BTH+AtomicETH[319:0], SAME-table expectedPSN[343:320],MSN[367:344].
// Reply248: BTH+AETH+AtomicACK[191:0],localQPN[215:192],requestPSN[239:216],
// bytes[245:240],advance[246],drop[247]. The outer native guard must bind its
// trusted full epoch/PD/peer/MR owner; none is inferred from packet addresses.
typedef ap_uint<368> as02AtomicRequest;
typedef ap_uint<248> as02AtomicReply;
struct as02AtomicCommit {ap_uint<24> qpn=0,psn=0;bool advance=false;};
inline ap_uint<24> as02_be24(ap_uint<24> x) {
    ap_uint<24> y;y(7,0)=x(23,16);y(15,8)=x(15,8);y(23,16)=x(7,0);return y;
}
inline bool as02_atomic_opcode(ibOpCode op) {return op==RC_COMPARE_SWAP || op==RC_FETCH_ADD;}
'''

IBH=r'''
            if(as02_atomic_opcode(meta.op_code)) {
                // SAME real table read as normal SEND/READ/WRITE. Do not
                // update it until the memory service's genuine commit.
                ibhMeta b=meta;b.atomic_epsn=qpState.epsn;
                metaOut.write(b);ibhDropMetaFifo.write(fwdPolicy(false,false));
                fsmState=ATOMIC_WAIT;break;
            }
'''

WAIT=r'''
    case ATOMIC_WAIT:
        if(!atomic_commit.empty()) {
            auto c=atomic_commit.read();
            if(c.qpn!=meta.dest_qp || c.psn!=meta.psn) {fault=true;regRequestRxFault=1;break;}
            if(c.advance)stateTable_upd_req.write(rxStateReq(meta.dest_qp,meta.psn+ap_uint<24>(1),false));
            fsmState=LOAD;
        }
        break;
'''

EXH=r'''
        case RC_COMPARE_SWAP:
        case RC_FETCH_ADD: {
            if(ap_uint<32>(udpLength)!=52 || meta.dest_qp>=MAX_QPS) {
                request_fault=true;regRequestExhFault=1;break;
            }
            as02AtomicRequest r=0;r(319,96)=exHeader.getAtomicHeader();
            r(7,0)=meta.op_code;r(31,16)=0xffff;
            r(63,40)=as02_be24(meta.dest_qp);r[71]=1;r(95,72)=as02_be24(meta.psn);
            r(343,320)=meta.atomic_epsn;r(367,344)=dmaMeta.msn;
            atomic_requests.write(r);pe_fsmState=ATOMIC_REPLY;break;
        }
'''

EXH_WAIT=r'''
    case ATOMIC_REPLY:
        if(!atomic_replies.empty()) {
            auto r=atomic_replies.read();ap_uint<6> bytes=r(245,240);
            bool advance=r[246],drop=r[247];ap_uint<8> op=r(7,0);
            ap_uint<24> response_psn=as02_be24(r(95,72));
            ap_uint<24> response_msn=as02_be24(r(127,104));
            bool base_ok=r(215,192)==meta.dest_qp && r(239,216)==meta.psn;
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
            as02AtomicCommit c;c.qpn=meta.dest_qp;c.psn=meta.psn;c.advance=advance;
            atomic_commit.write(c);pe_fsmState=META;
        }
        break;
'''

PORTS='stream<as02AtomicRequest>& m_axis_atomic_request,stream<as02AtomicReply>& s_axis_atomic_reply,'
ARGS='m_axis_atomic_request,s_axis_atomic_reply,'


def derive():
    out=base.derive()
    out[HPP]=once(out[HPP],'\tRC_ACK = 0x11,','\tRC_ACK = 0x11,\n'
        '\tRC_ATOMIC_ACK=0x12,RC_COMPARE_SWAP=0x13,RC_FETCH_ADD=0x14,')
    out[HPP]=once(out[HPP],'struct ackEvent',TYPES+'\nstruct ackEvent')
    out[HPP]=once(out[HPP],'struct ibhMeta\n{','struct ibhMeta\n{\n    ap_uint<24> atomic_epsn=0;')
    for name in ['ackEvent','event']:
        out[HPP]=once(out[HPP],'struct '+name+'\n{','struct '+name+'\n{\n'
            '    bool atomic_reply=false;ap_uint<8> atomic_opcode=0;\n'
            '    ap_uint<6> atomic_bytes=0;ap_uint<96> atomic_exh=0;')
    out[HPP]=once(out[HPP],':receive_owned(aev.receive_owned), receive(aev.receive),',
        ':atomic_reply(aev.atomic_reply),atomic_opcode(aev.atomic_opcode),atomic_bytes(aev.atomic_bytes),'
        'atomic_exh(aev.atomic_exh),receive_owned(aev.receive_owned), receive(aev.receive),')
    start=out[HPP].index('class ExHeader:');end=out[HPP].index('\nstruct ImmDt',start)
    part=out[HPP][start:end].replace('packetHeader<W, 160>','packetHeader<W, 224>')
    part=once(part,'    ExHeader() {}','    ExHeader() {}\n'
        '    ap_uint<224> getAtomicHeader() {return header;}')
    out[HPP]=out[HPP][:start]+part+out[HPP][end:]
    def parse(t):
        t=once(t,'NO_HEADER, IMMEDIATE_HEADER','NO_HEADER, IMMEDIATE_HEADER, ATOMIC_HEADER')
        t=once(t,'if(opCode==RC_SEND_ONLY_WITH_IMD',
            'if(as02_atomic_opcode(opCode))state=ATOMIC_HEADER;\n'
            '            else if(opCode==RC_SEND_ONLY_WITH_IMD')
        return once(t,'    case IMMEDIATE_HEADER:',r'''
    case ATOMIC_HEADER:
        if(!input.empty()) {
            auto w=input.read();
            // AtomicETH has no payload. Consume it here, do not enqueue an
            // orphan payload/drop token into the normal memory path.
            if(!metaWritten) {
                ExHeader<WIDTH> e;e.setRawHeader(w.data(223,0));
                exhMetaFifo.write(exhMeta(false));metaOut.write(e);metaWritten=true;
            }
            if(w.last)state=META;
        }
        break;
    case IMMEDIATE_HEADER:''')
    out[CPP]=parent.change(out[CPP],'void rx_process_exh(',parse)
    def ibh(t):
        t=once(t,'stream<as02ReqToken>& request_rx_owners,',
            'stream<as02AtomicCommit>& atomic_commit,stream<as02ReqToken>& request_rx_owners,')
        t=once(t,'{LOAD, PROCESS}', '{LOAD, PROCESS, ATOMIC_WAIT}')
        t=once(t,'            stateTable_rsp.read(qpState);','            stateTable_rsp.read(qpState);'+IBH)
        # Insert inside the outer switch, not an inner state branch.
        pos=t.rfind('\n\t}\n}');
        if pos<0:raise ValueError('RX IBH switch boundary changed')
        return t[:pos]+WAIT+t[pos:]
    out[CPP]=parent.change(out[CPP],'void rx_ibh_fsm(',ibh)
    def exh(t):
        t=once(t,'stream<as02RecvOwner>& s_axis_recv_owner,',
            'stream<as02AtomicRequest>& atomic_requests,stream<as02AtomicReply>& atomic_replies,\n'
            '    stream<as02AtomicCommit>& atomic_commit,stream<as02RecvOwner>& s_axis_recv_owner,')
        t=once(t,'{META, DMA_META, DATA}', '{META, DMA_META, DATA, ATOMIC_REPLY}')
        t=once(t,'        case RC_SEND_ONLY_WITH_IMD:',EXH+'\n        case RC_SEND_ONLY_WITH_IMD:')
        pos=t.rfind('\n\t}')
        if pos<0:raise ValueError('RX EXH switch boundary changed')
        return t[:pos]+EXH_WAIT+t[pos:]
    out[CPP]=parent.change(out[CPP],'void rx_exh_fsm(',exh)
    out[CPP]=parent.change(out[CPP],'void meta_merger(',lambda t:once(t,
        'ibhMeta(RC_ACK, key, aev.qpn, aev.psn, aev.validPsn)',
        'ibhMeta(aev.atomic_reply ? ibOpCode(unsigned(aev.atomic_opcode)):RC_ACK, key, aev.qpn, aev.psn, aev.validPsn)'))
    def generate(t):
        return once(t,'            switch(meta.op_code)',r'''
            if(meta.atomic_reply) {
                sendWord.data=0;sendWord.data(95,0)=meta.atomic_exh;
                info.header_bytes=meta.atomic_bytes-12;info.isAETH=true;
                info.hasHeader=true;info.hasPayload=false;
                sendWord.keep=(ap_uint<64>(1)<<info.header_bytes)-1;sendWord.last=1;
                output.write(sendWord);packetInfoFifo.write(info);
                lengthFifo.write(ap_uint<16>(meta.atomic_bytes+4));ge_state=META;break;
            }
            switch(meta.op_code)''')
    out[CPP]=parent.change(out[CPP],'void generate_exh(',generate)
    # Both top declarations plus the actual dataflow definition preserve every
    # existing owner/retirement port. Add a separate service, not raw fake DMA.
    for n in [HPP,CPP,TOP]:
        out[n]=out[n].replace('stream<as02RnrEvent>& s_axis_rnr_event,',
            PORTS+'stream<as02RnrEvent>& s_axis_rnr_event,')
        out[n]=out[n].replace('s_axis_rnr_event,regRnrFault,',ARGS+'s_axis_rnr_event,regRnrFault,')
    out[CPP]=once(out[CPP],'    static stream<as02RecvProof> recv_data_done',
        '    static stream<as02AtomicCommit> atomic_commit("atomic_commit");\n'
        '    #pragma HLS STREAM depth=2 variable=atomic_commit\n'
        '    static stream<as02RecvProof> recv_data_done')
    out[CPP]=once(out[CPP],'regInvalidPsnDropCount,request_rx_owners,request_rx_fault\n',
        'regInvalidPsnDropCount,atomic_commit,request_rx_owners,request_rx_fault\n')
    out[CPP]=once(out[CPP],'s_axis_recv_owner,recv_bind_fault,request_ack_consumed,request_exh_fault\n',
        'm_axis_atomic_request,s_axis_atomic_reply,atomic_commit,s_axis_recv_owner,recv_bind_fault,request_ack_consumed,request_exh_fault\n')
    # AXIS types carry bit-exact unsigned scalar words; no guessed C struct ABI.
    out[TOP]=out[TOP].replace('#pragma HLS INTERFACE axis register port=s_axis_rnr_event',
        '#pragma HLS INTERFACE axis register port=m_axis_atomic_request\n'
        '#pragma HLS INTERFACE axis register port=s_axis_atomic_reply\n'
        '#pragma HLS INTERFACE axis register port=s_axis_rnr_event')
    out[TOP]=out[TOP].replace('rocev2_native_immediate_top','rocev2_native_atomic_top')
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
        original_unchanged=True,HLS_top='rocev2_native_atomic_top',request_context_bits=620,
        request_immediate=True,receive_immediate=True,atomic_service_request_bits=368,
        atomic_service_reply_bits=248,shared_PSN_MSN=True,native_integration=False,
        atomic_requester=False,source_only=True,hardware_verified=False,whole_core_drain_proved=False)
    (a.output/'source.json').write_text(json.dumps(info,indent=2)+'\n')
    print(json.dumps(dict(output=str(a.output),HLS_top=info['HLS_top'],original_unchanged=True)))


if __name__=='__main__':main()
