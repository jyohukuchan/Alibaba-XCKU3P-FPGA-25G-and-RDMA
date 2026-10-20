#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Atomic requester in the SAME complete owned Atomic/Immediate HLS graph.

Checked opt-in derivative, not a second PSN/MSN/MR namespace. Owner748/SQ408
match the128-byte admission candidate; receive owners remain620. Actual
retransmission entries retain both operands. AtomicACK supplies an8-byte
LE local result through the actual memory-data consumer before retirement.
Native protected result DMA/MAC/CQ/driver/provider and timing remain separate.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

import atomic_owned_transport as base

once=base.once;parent=base.parent;CPP=base.CPP;HPP=base.HPP;TOP=base.TOP
RETRANS='hls/ib_transport_protocol/retransmitter/retransmitter.hpp'
JOIN='hls/ib_transport_protocol/as02_request_retire.hpp'
UTILS='hls/ib_transport_protocol/ib_utils.cpp'
NAME='rocev2_native_atomic_request_top'

OWNER=r'''inline bool as02_req_owner_valid(ap_uint<748> n) {
    ap_uint<16> op=n(339,324);ap_uint<32> len=n(307,276);
    ap_uint<65> limit=ap_uint<65>(1)<<64;
    bool send=op==3 || op==5,imm=op==5 || op==6,atomic=op==7 || op==8;
    return as02_req_token_valid(as02_req_token(n)) && n(355,340)!=0 && n(323,309)==0 &&
        n(19,0)==3 && (op==1 || op==2 || op==3 || op==5 || op==6 || atomic) &&
        (atomic ? (len==8 && n(54,52)==0 && (op!=8 || n(683,620)==0)):
                  (len!=0 && len<=4096 && n(747,620)==0)) &&
        (!send || n(115,20)==0) && (imm || n(619,588)==0) &&
        ap_uint<65>(n(243,180))+len<=limit && ap_uint<65>(n(179,116))+len<=limit &&
        ap_uint<65>(n(115,52))+len<=limit;
}'''

ACK_PARSE=r'''
    case ATOMIC_ACK_HEADER:
        static_assert(WIDTH==512,"matched512-bit lanes required");
        if(!input.empty()) {
            auto w=input.read();
            // AtomicACK is AETH4+oldvalue8, not a separate payload. Reject
            // malformed framing/syndrome BEFORE the common RX PSN advances.
            if(!metaWritten) {
                ExHeader<WIDTH> e;e.setRawHeader(w.data(95,0));
                auto a=e.getAckHeader();ap_uint<8> syn=a.getSyndrome();
                bool malformed=w.keep!=ap_uint<64>(0xfff) || !w.last || syn(7,5)!=0;
                exhMetaFifo.write(exhMeta(malformed));metaOut.write(e);metaWritten=true;
            }
            if(w.last)state=META;
        }
        break;
'''

ACK_RESULT=r'''
        case RC_ATOMIC_ACK: {
            auto a=exHeader.getAckHeader();ap_uint<8> syn=a.getSyndrome();
            if(!meta.request_owned || !readReqInit.request_owned ||
               readReqInit.request_token!=meta.request_token ||
               !as02_req_token_valid(meta.request_token) ||
               meta.request_token(23,0)!=meta.dest_qp ||
               !as02_atomic_opcode(ibOpCode(unsigned(readReqInit.request_opcode))) ||
               readReqInit.length!=8 || !readReqInit.lst || syn(7,5)!=0 || udpLength!=36) {
                request_fault=true;regRequestExhFault=1;break;
            }
            // Raw legacy command retains48 address bits; the native guard
            // MUST bind it to the full64-bit saved MR owner/sealed pages.
            memoryWriteCmd.write(as02_duplex_command(
                memCmd(readReqInit.laddr,8,readReqInit.lst,PKG_HOST,meta.dest_qp),true));
            pkgShift s(SHIFT_NONE,meta.dest_qp);s.atomic_result=true;
            s.atomic_value=exHeader.getAtomicOldValue();s.request_owned=true;
            s.request_token=meta.request_token;s.request_psn=meta.psn;s.request_opcode=RC_ATOMIC_ACK;
            rx_pkgShiftTypeFifo.write(s);pe_fsmState=META;break;
        }
'''

TX_ATOMIC=r'''
            case RC_COMPARE_SWAP:
            case RC_FETCH_ADD: {
                // Wire AtomicETH: remoteVA64, fullRKey32, swap/add64, compare64.
                sendWord.data=0;sendWord.data(63,0)=reverse(meta.addr);
                sendWord.data(95,64)=reverse(meta.rkey);
                sendWord.data(159,96)=reverse(meta.swap_add);
                sendWord.data(223,160)=reverse(meta.compare);
                sendWord.keep=ap_uint<64>(0xfffffff);sendWord.last=1;
                info.header_bytes=28;info.isAETH=false;info.hasHeader=true;info.hasPayload=false;
                output.write(sendWord);packetInfoFifo.write(info);lengthFifo.write(44);
                ge_state=META;break;
            }
'''


def derive():
    out=base.derive()
    # Request ports only: NEVER widen posted receive owners/proofs.
    for anchor in ['inline as02ReqToken as02_req_token(', 'inline bool as02_req_owner_valid(',
                   'inline ap_uint<8> as02_req_opcode(', 'struct as02ReqDone']:
        out[HPP]=parent.change(out[HPP],anchor,lambda t:t.replace('ap_uint<620>','ap_uint<748>'))
    out[HPP]=once(out[HPP],'stream<ap_uint<620>>& s_axis_request_owner,',
        'stream<ap_uint<748>>& s_axis_request_owner,')
    for n in [CPP,TOP,JOIN]:out[n]=out[n].replace('ap_uint<620>','ap_uint<748>')
    out[HPP]=parent.change(out[HPP],'inline bool as02_req_owner_valid(',lambda t:OWNER)
    out[HPP]=once(out[HPP],'return op==1 ? ap_uint<8>(RC_RDMA_WRITE_ONLY)',
        'return op==7 ? ap_uint<8>(RC_COMPARE_SWAP):op==8 ? ap_uint<8>(RC_FETCH_ADD):\n'
        '        op==1 ? ap_uint<8>(RC_RDMA_WRITE_ONLY)')
    operands='ap_uint<64> compare=0,swap_add=0;'
    for anchor in ['struct as02ReqInsert {','struct event\n{','struct retransEvent\n{']:
        out[HPP]=parent.change(out[HPP],anchor,lambda t:once(t,'ap_uint<32> immediate=0;',
            'ap_uint<32> immediate=0;'+operands))
    out[HPP]=parent.change(out[HPP],'struct txMeta\n{',lambda t:once(t,'ap_uint<32> immediate=0;',
        'ap_uint<32> immediate=0;\n'
        '    // Preserve ALL lower280 ABI bits, including explicit seven zero padding bits.\n'
        '    ap_uint<7> atomic_padding=0;'+operands))
    out[HPP]=parent.change(out[HPP],'struct retransEvent\n{',lambda t:once(once(t,
        'ap_uint<32> immediate=0)','ap_uint<32> immediate=0,ap_uint<64> compare=0,ap_uint<64> swap_add=0)'),
        ':immediate(immediate),rkey(rkey)',':immediate(immediate),compare(compare),swap_add(swap_add),rkey(rkey)'))
    out[HPP]=parent.change(out[HPP],'struct pkgShift\n{',lambda t:once(t,
        'bool request_owned=false;','bool atomic_result=false;ap_uint<64> atomic_value=0;\n    bool request_owned=false;'))
    out[HPP]=once(out[HPP],'ap_uint<224> getAtomicHeader() {return header;}',
        'ap_uint<224> getAtomicHeader() {return header;}\n'
        '    ap_uint<64> getAtomicOldValue() {return reverse(ap_uint<64>(header(95,32)));}')

    def local(t):
        t=once(t,'ev.rkey_valid = rev.rkey_valid;ev.immediate=rev.immediate;',
            'ev.rkey_valid = rev.rkey_valid;ev.immediate=rev.immediate;ev.compare=rev.compare;ev.swap_add=rev.swap_add;')
        t=once(t,'if (rev.op_code != RC_RDMA_READ_REQUEST)',
            'if (rev.op_code != RC_RDMA_READ_REQUEST && !as02_atomic_opcode(rev.op_code))')
        t=once(t,'meta.immediate!=n(619,588))',
            'meta.immediate!=n(619,588) || meta.atomic_padding!=0 ||\n'
            '           meta.compare!=n(683,620) || meta.swap_add!=n(747,684))')
        t=once(t,'if(meta.op_code == RC_RDMA_READ_REQUEST)',
            'if(meta.op_code == RC_RDMA_READ_REQUEST || as02_atomic_opcode(meta.op_code))')
        if t.count('ev.immediate=meta.immediate;')!=2:raise ValueError('fresh event paths changed')
        t=t.replace('ev.immediate=meta.immediate;',
            'ev.immediate=meta.immediate;ev.compare=meta.compare;ev.swap_add=meta.swap_add;')
        return once(t,'r.immediate=meta.immediate;',
            'r.immediate=meta.immediate;r.compare=meta.compare;r.swap_add=meta.swap_add;')
    out[CPP]=parent.change(out[CPP],'void local_req_handler(',local)
    def tx(t):
        t=once(t,'meta.op_code == RC_RDMA_READ_REQUEST || (meta.request_owned',
            'meta.op_code == RC_RDMA_READ_REQUEST || as02_atomic_opcode(meta.op_code) || (meta.request_owned')
        return once(t,'            case RC_SEND_ONLY_WITH_IMD:',TX_ATOMIC+'\n            case RC_SEND_ONLY_WITH_IMD:')
    out[CPP]=parent.change(out[CPP],'void generate_exh(',tx)
    out[CPP]=parent.change(out[CPP],'void generate_ibh(',lambda t:once(t,
        'header.setDstQP(dstQp);','header.setDstQP(dstQp);\n            if(as02_atomic_opcode(meta.op_code))header.setAckReq(true);'))
    out[UTILS]=parent.change(out.get(UTILS,(parent.qp.BASE/'fns'/UTILS).read_text()),
        'bool checkIfResponse(',lambda t:once(t,'code == RC_ACK);','code == RC_ACK || code == RC_ATOMIC_ACK);'))
    def parse(t):
        t=once(t,'IMMEDIATE_HEADER, ATOMIC_HEADER}','IMMEDIATE_HEADER, ATOMIC_HEADER, ATOMIC_ACK_HEADER}')
        t=once(t,'if(as02_atomic_opcode(opCode))state=ATOMIC_HEADER;',
            'if(opCode==RC_ATOMIC_ACK)state=ATOMIC_ACK_HEADER;\n'
            '            else if(as02_atomic_opcode(opCode))state=ATOMIC_HEADER;')
        return once(t,'    case ATOMIC_HEADER:',ACK_PARSE+'\n    case ATOMIC_HEADER:')
    out[CPP]=parent.change(out[CPP],'void rx_process_exh(',parse)
    def ibh(t):
        t=once(t,'meta.op_code!=RC_ACK && meta.op_code!=RC_RDMA_READ_RESP_ONLY)',
            'meta.op_code!=RC_ACK && meta.op_code!=RC_RDMA_READ_RESP_ONLY && meta.op_code!=RC_ATOMIC_ACK)')
        return once(t,'if (meta.op_code != RC_ACK && meta.op_code != RC_RDMA_READ_REQUEST)',
            'if (meta.op_code != RC_ACK && meta.op_code != RC_RDMA_READ_REQUEST && meta.op_code != RC_ATOMIC_ACK)')
    out[CPP]=parent.change(out[CPP],'void rx_ibh_fsm(',ibh)
    def exh(t):
        t=once(t,'if (meta.op_code == RC_RDMA_READ_RESP_ONLY || meta.op_code == RC_RDMA_READ_RESP_FIRST)',
            'if (meta.op_code == RC_RDMA_READ_RESP_ONLY || meta.op_code == RC_RDMA_READ_RESP_FIRST || meta.op_code==RC_ATOMIC_ACK)')
        return once(t,'        case RC_COMPARE_SWAP:',ACK_RESULT+'\n        case RC_COMPARE_SWAP:')
    out[CPP]=parent.change(out[CPP],'void rx_exh_fsm(',exh)
    def merge(t):
        t=once(t,'RECV_DONE, REQUEST_DONE}','RECV_DONE, REQUEST_DONE, ATOMIC_RESULT}')
        t=once(t,'if (shift.type == SHIFT_AETH)',
            'if(shift.atomic_result)state=ATOMIC_RESULT;\n            else if (shift.type == SHIFT_AETH)')
        return once(t,'    case RECV_DONE:',r'''
    case ATOMIC_RESULT:
        if(!m_axis_mem_write_data.full()) {
            net_axis<WIDTH> w;w.data=0;w.data(63,0)=shift.atomic_value;w.keep=0xff;w.last=1;
            m_axis_mem_write_data.write(w);state=REQUEST_DONE;
        }
        break;
    case RECV_DONE:''')
    out[CPP]=parent.change(out[CPP],'void merge_rx_pkgs(',merge)

    for anchor in ['struct retransAddrLen\n{','struct retransEntry\n{','struct retransMetaEntry\n{']:
        out[RETRANS]=parent.change(out[RETRANS],anchor,lambda t:once(t,'ap_uint<32> immediate=0;',
            'ap_uint<32> immediate=0;'+operands))
    out[RETRANS]=once(out[RETRANS],':immediate(addrlen.immediate),',
        ':immediate(addrlen.immediate),compare(addrlen.compare),swap_add(addrlen.swap_add),')
    out[RETRANS]=once(out[RETRANS],':immediate(e.immediate),',
        ':immediate(e.immediate),compare(e.compare),swap_add(e.swap_add),')
    out[RETRANS]=once(out[RETRANS],'p.immediate=receipt_entry.immediate;',
        'p.immediate=receipt_entry.immediate;p.compare=receipt_entry.compare;p.swap_add=receipt_entry.swap_add;')
    if out[RETRANS].count('meta.host, meta.immediate))')!=2:raise ValueError('replay paths changed')
    out[RETRANS]=out[RETRANS].replace('meta.host, meta.immediate))',
        'meta.host, meta.immediate, meta.compare, meta.swap_add))')
    out[RETRANS]=parent.change(out[RETRANS],'struct retransRdInit\n{',lambda t:once(t,
        'ap_uint<64> laddr;','ap_uint<8> request_opcode=0;ap_uint<32> length=0;\n    ap_uint<64> laddr;'))
    out[RETRANS]=once(out[RETRANS],
        '!((meta.opCode==RC_RDMA_READ_REQUEST && update.op_code==RC_RDMA_READ_RESP_ONLY) ||',
        '!((as02_atomic_opcode(meta.opCode) && update.op_code==RC_ATOMIC_ACK) ||\n'
        '                 (meta.opCode==RC_RDMA_READ_REQUEST && update.op_code==RC_RDMA_READ_RESP_ONLY) ||')
    out[RETRANS]=once(out[RETRANS],
        'if(update.op_code == RC_RDMA_READ_RESP_FIRST || update.op_code == RC_RDMA_READ_RESP_ONLY)',
        'if(update.op_code == RC_RDMA_READ_RESP_FIRST || update.op_code == RC_RDMA_READ_RESP_ONLY || update.op_code==RC_ATOMIC_ACK)')
    out[RETRANS]=once(out[RETRANS],'d.request_token=meta.request_token;retrans2rx_init.write(d);',
        'd.request_token=meta.request_token;d.request_opcode=meta.opCode;d.length=meta.length;retrans2rx_init.write(d);')
    out[JOIN]=once(out[JOIN],'r.rkey!=owner(51,20) || r.immediate!=owner(619,588) ||',
        'r.rkey!=owner(51,20) || r.immediate!=owner(619,588) ||\n'
        '           r.compare!=owner(683,620) || r.swap_add!=owner(747,684) ||')
    out[JOIN]=once(out[JOIN],'bool read=owner(339,324)==2;',
        'bool atomic=owner(339,324)==7 || owner(339,324)==8;bool read=owner(339,324)==2 || atomic;')
    out[JOIN]=once(out[JOIN],'r.opcode!=(read ? RC_RDMA_READ_RESP_ONLY:RC_ACK)',
        'r.opcode!=(atomic ? RC_ATOMIC_ACK:read ? RC_RDMA_READ_RESP_ONLY:RC_ACK)')
    out[TOP]=out[TOP].replace(base.NAME,NAME)
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
        generator_sha256=parent.qp.digest(__file__),derived_sources={n:hashlib.sha256(t.encode()).hexdigest()for n,t in files.items()},
        original_unchanged=True,HLS_top=NAME,request_context_bits=748,request_done_bits=816,
        SQ_bits=408,SQ_padding_bits=[273,279],receive_context_bits=620,
        atomic_requester=True,atomic_service_request_bits=512,atomic_core_done_bits=224,
        shared_PSN_MSN=True,retransmission_operands=True,source_only=True,
        native_integration=False,hardware_verified=False,whole_core_drain_proved=False)
    (a.output/'source.json').write_text(json.dumps(info,indent=2)+'\n')
    print(json.dumps(dict(output=str(a.output),HLS_top=NAME,original_unchanged=True)))


if __name__=='__main__':main()
