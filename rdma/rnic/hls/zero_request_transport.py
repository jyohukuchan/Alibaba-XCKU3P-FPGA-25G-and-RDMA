#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Zero-length normal requests in the SAME complete Atomic/Immediate HLS.

WRITE/READ/SEND and both Immediate requesters use actual packet/PSN/replay/
ACK/timer/state consumers without any data-memory command. A zero READ still
consumes one actual AETH-only response before its real retirement join.
No local key/address is invented: the zero owner is explicitly canonical.
Not yet native admission/CQ/kernel/provider/hardware/timing qualification.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import atomic_request_transport as base

ROOT=base.parent.ROOT;once=base.once;change=base.parent.change
CPP=base.CPP;HPP=base.HPP;TOP=base.TOP
NAME='rocev2_native_zero_request_top'

ZERO_READ=r'''
            if(meta.request_owned && readReqInit.length==0) {
                // Real response/owner/PSN/header, but there is NO data DMA.
                // Keep the original four AETH bytes until the real downstream
                // consumer verifies them; do not manufacture a payload receipt.
                if(meta.op_code!=RC_RDMA_READ_RESP_ONLY ||
                   readReqInit.request_opcode!=RC_RDMA_READ_REQUEST || udpLength!=28 ||
                   !readReqInit.lst || ackHeader.getSyndrome()(7,5)!=0) {
                    request_fault=true;regRequestExhFault=1;return;
                }
                pkgShift z(SHIFT_NONE,meta.dest_qp);z.zero_read=true;
                z.zero_aeth=ackHeader.getRawHeader();z.request_owned=true;z.request_token=meta.request_token;
                z.request_psn=meta.psn;z.request_opcode=ap_uint<8>(meta.op_code);
                rx_pkgShiftTypeFifo.write(z);
                // The original AETH-only word travels through the actual RAW
                // branch, not a shift that would discard a header-only word.
                rx_pkgSplitTypeFifo.write(pkgSplit(RC_SEND_ONLY));
                pe_fsmState=META;break;
            }
'''


def derive():
    out=base.derive()
    out[HPP]=change(out[HPP],'inline bool as02_req_owner_valid(',lambda t:once(t,
        '(len!=0 && len<=4096 && n(747,620)==0)',
        '(len<=4096 && n(747,620)==0 && (len!=0 || n(275,116)==0))'))
    out[HPP]=change(out[HPP],'struct pkgShift\n{',lambda t:once(t,
        'bool atomic_result=false;', 'bool zero_read=false;ap_uint<32> zero_aeth=0;\n    bool atomic_result=false;'))
    def local(t):
        t=once(t,'if (rev.op_code != RC_RDMA_READ_REQUEST && !as02_atomic_opcode(rev.op_code))',
            'if (rev.length!=0 && rev.op_code != RC_RDMA_READ_REQUEST && !as02_atomic_opcode(rev.op_code))')
        return once(t,'tx_local_memCmdFifo.write(memCmdInternal(meta.op_code, meta.qpn, laddr, length, meta.host));',
            'if(length!=0)tx_local_memCmdFifo.write(memCmdInternal(meta.op_code, meta.qpn, laddr, length, meta.host));')
    out[CPP]=change(out[CPP],'void local_req_handler(',local)
    out[CPP]=change(out[CPP],'void meta_merger(',lambda t:once(t,
        'numPkg = (ev.length+(PMTU-1)) / PMTU;',
        'numPkg = ev.length==0 ? ap_uint<22>(1):ap_uint<22>((ev.length+(PMTU-1)) / PMTU);'))
    out[CPP]=change(out[CPP],'void generate_ibh(',lambda t:once(t,
        'if(as02_atomic_opcode(meta.op_code))header.setAckReq(true);',
        'if(as02_atomic_opcode(meta.op_code) || meta.op_code==RC_RDMA_READ_REQUEST ||\n'
        '               meta.op_code==RC_RDMA_WRITE_ONLY || meta.op_code==RC_RDMA_WRITE_ONLY_WIT_IMD ||\n'
        '               meta.op_code==RC_SEND_ONLY || meta.op_code==RC_SEND_ONLY_WITH_IMD)header.setAckReq(true);'))
    # No-header/no-payload SEND still supplies an actual internal EOF word to
    # prepend_ibh. This empty marker is NOT a memory-data transaction.
    out[CPP]=change(out[CPP],'void append_payload(',lambda t:once(t,
        'phase=info.hasHeader ? HEADER:PAYLOAD;',
        'phase=info.hasHeader ? HEADER:PAYLOAD;\n'
        '        if(!info.hasHeader && !info.hasPayload)phase=FLUSH;\n'
        '        tail=0;tail_count=0;'))
    def exh(t):
        anchor='            pkgShift s(SHIFT_AETH,meta.dest_qp);'
        return once(t,anchor,ZERO_READ+'\n'+anchor)
    out[CPP]=change(out[CPP],'void rx_exh_fsm(',exh)
    def merge(t):
        t=once(t,'stream<as02ReqStep>& request_read_consumed\n',
            'stream<as02ReqStep>& request_read_consumed,ap_uint<1>& regRequestPayloadFault\n')
        t=once(t,'ATOMIC_RESULT};','ATOMIC_RESULT, ZERO_READ, QUARANTINE};')
        t=once(t,'\tstatic pkgShift shift;',
            '\tstatic pkgShift shift;\n    static bool fault=false;regRequestPayloadFault=fault;if(fault)return;')
        t=once(t,'if(shift.atomic_result)state=ATOMIC_RESULT;',
            'if(shift.zero_read)state=ZERO_READ;\n            else if(shift.atomic_result)state=ATOMIC_RESULT;')
        return once(t,'    case ATOMIC_RESULT:',r'''
    case ZERO_READ:
        if(!rx_NoSift2mergerFifo.empty()) {
            auto w=rx_NoSift2mergerFifo.read();
            if(!shift.request_owned || !as02_req_token_valid(shift.request_token) ||
               shift.request_opcode!=RC_RDMA_READ_RESP_ONLY || w.keep!=ap_uint<64>(15) ||
               !w.last || w.data(31,0)!=shift.zero_aeth) {
                fault=true;regRequestPayloadFault=1;state=QUARANTINE;
            } else state=REQUEST_DONE;
        }
        break;
    case QUARANTINE:break;
    case ATOMIC_RESULT:''')
    out[CPP]=change(out[CPP],'void merge_rx_pkgs(',merge)
    out[CPP]=once(out[CPP],'request_retrans_fault=0,request_timer_fault=0,request_join_fault=0;',
        'request_retrans_fault=0,request_timer_fault=0,request_join_fault=0,request_payload_fault=0;')
    out[CPP]=once(out[CPP],'request_exh_fault|request_merge_fault|request_retrans_fault',
        'request_exh_fault|request_payload_fault|request_merge_fault|request_retrans_fault')
    out[CPP]=once(out[CPP],'m_axis_mem_write_data,recv_data_done,request_read_consumed);',
        'm_axis_mem_write_data,recv_data_done,request_read_consumed,request_payload_fault);')
    out[TOP]=out[TOP].replace(base.NAME,NAME)
    return out


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():p.error('preserve prior source')
    original=base.parent.qp.BASE
    before={str(x.relative_to(original)):base.parent.qp.digest(x)for x in original.rglob('*')if x.is_file()}
    files=derive();shutil.copytree(original/'fns',a.output/'fns');shutil.copytree(original/'adapter',a.output/'adapter')
    for n,t in files.items():(a.output/'fns'/n).write_text(t)
    if before!={n:base.parent.qp.digest(original/n)for n in before}:raise ValueError('original source changed')
    info=dict(scope=__doc__,source_base=str(original),source_sha256=before,
        generator_sha256=base.parent.qp.digest(__file__),parent_generator_sha256=base.parent.qp.digest(base.__file__),
        derived_sources={n:hashlib.sha256(t.encode()).hexdigest()for n,t in files.items()},
        original_unchanged=True,HLS_top=NAME,request_context_bits=748,request_done_bits=816,
        SQ_bits=408,SQ_padding_bits=[273,279],receive_context_bits=620,zero_length_requester=True,
        atomic_requester=True,atomic_service_request_bits=512,atomic_core_done_bits=224,
        shared_PSN_MSN=True,retransmission_operands=True,source_only=True,
        native_integration=False,hardware_verified=False,whole_core_drain_proved=False)
    (a.output/'source.json').write_text(json.dumps(info,indent=2)+'\n')
    print(json.dumps(dict(output=str(a.output),HLS_top=NAME,original_unchanged=True)))


if __name__=='__main__':main()
