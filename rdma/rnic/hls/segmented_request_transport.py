#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""True multi-packet ordinary WRITE/SEND in the SAME owned transport.

Opt-in source candidate: up to1MiB, FIRST/MIDDLE/LAST, one full WR owner and
one final receipt. Stop-and-wait uses actual per-packet ACK/retransmission
release/pool/timer/common-PSN readback, never independent WRITE_ONLY verbs.
READ/Immediate remain4096; Atomic/zero/RQ ABIs and default graphs unchanged.
Native MR/DMA/MAC/CQ/kernel/provider integration and timing remain open.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import zero_service_transport as base

ROOT=base.ROOT;CPP=base.CPP;HPP=base.HPP;TOP=base.TOP
once=base.once;change=base.change;NAME='rocev2_native_segmented_request_top'
JOIN='hls/ib_transport_protocol/as02_request_retire.hpp'
RETRANS='hls/ib_transport_protocol/retransmitter/retransmitter.hpp'

TYPES=r'''
// Full-message identity/authority is retained in the existing748-bit owner.
// The byte offset below is internal transport state, not another WQE/MR grant.
inline bool as02_req_segmented(ap_uint<748> n) {
    return (n(339,324)==1 || n(339,324)==3) && n(307,276)>PMTU;
}
inline ap_uint<32> as02_req_segment_bytes(ap_uint<748> n,ap_uint<32> offset) {
    ap_uint<32> remaining=n(307,276)-offset;
    return remaining>PMTU ? ap_uint<32>(PMTU):remaining;
}
inline bool as02_req_segment_last(ap_uint<748> n,ap_uint<32> offset) {
    return !as02_req_segmented(n) || offset+as02_req_segment_bytes(n,offset)==n(307,276);
}
inline ibOpCode as02_req_segment_opcode(ap_uint<748> n,ap_uint<32> offset) {
    if(!as02_req_segmented(n))return ibOpCode(unsigned(as02_req_opcode(n)));
    bool send=n(339,324)==3;
    if(offset==0)return send ? RC_SEND_FIRST:RC_RDMA_WRITE_FIRST;
    if(as02_req_segment_last(n,offset))return send ? RC_SEND_LAST:RC_RDMA_WRITE_LAST;
    return send ? RC_SEND_MIDDLE:RC_RDMA_WRITE_MIDDLE;
}
'''

EMIT=r'''
template<int INSTID=0> void as02_emit_request_segment(
    ap_uint<748> n,ap_uint<32> offset,bool add_rx_owner,
    stream<memCmdInternal>& memory,stream<event>& events,
    stream<retransAddrLen>& replay,stream<as02ReqToken>& rx_owners) {
#pragma HLS inline
    const as02ReqToken token=as02_req_token(n);
    const ibOpCode op=as02_req_segment_opcode(n,offset);
    const ap_uint<32> bytes=as02_req_segment_bytes(n,offset);
    const ap_uint<64> local=ap_uint<64>(n(243,180))+offset;
    const ap_uint<64> remote=n(339,324)==3 ? ap_uint<64>(0):ap_uint<64>(ap_uint<64>(n(115,52))+offset);
    // FIRST's RETH contains the WHOLE message length. Its memory command is
    // nevertheless just one PMTU, as are all later wire/data fragments.
    const ap_uint<32> event_length=offset==0 && n(339,324)==1 ? ap_uint<32>(n(307,276)):bytes;
    event ev(op,n(395,372),remote,event_length);
    ev.rkey=n(51,20);ev.rkey_valid=1;ev.request_owned=true;ev.request_token=token;
    if(add_rx_owner)rx_owners.write(token);
    events.write(ev);
    memory.write(memCmdInternal(op,n(395,372),local,bytes,1));
    retransAddrLen r(local,remote,event_length,as02_req_segment_last(n,offset),0,n(51,20),1,1);
    r.request_owned=true;r.request_token=token;replay.write(r);
}
'''

CONTINUE=r'''
    if(!request_segment_continue.empty()) {
        as02ReqToken token=request_segment_continue.read();
        if(token!=as02_req_token(segment_owner) || !as02_req_segmented(segment_owner) ||
           segment_offset==0 || segment_offset>=segment_owner(307,276) || segment_offset%PMTU!=0) {
            fault=true;regRequestBindFault=1;return;
        }
        as02_emit_request_segment<INSTID>(segment_owner,segment_offset,true,
            tx_local_memCmdFifo,tx_localTxMeta,tx2retrans_insertAddrLen,request_rx_owners);
        if(as02_req_segment_last(segment_owner,segment_offset))segment_active=false;
        else segment_offset+=PMTU;
    }
'''


def derive():
    out=base.derive()
    out[HPP]=change(out[HPP],'inline bool as02_req_owner_valid(',lambda t:once(t,
        '(len<=4096 && n(747,620)==0 && (len!=0 || n(275,116)==0))',
        '(len<=((op==1 || op==3) ? 1048576U:4096U) && n(747,620)==0 && (len!=0 || n(275,116)==0))'))
    out[HPP]=once(out[HPP],'struct as02ReqStep {',TYPES+'\nstruct as02ReqStep {')
    out[HPP]=once(out[HPP],'struct ibhMeta\n{','struct ibhMeta\n{\n    ap_uint<2> wire_pad=0;')
    out[HPP]=once(out[HPP],'struct txPacketInfo\n{','struct txPacketInfo\n{\n    ap_uint<2> wire_pad=0;')

    def local(t):
        t=once(t,'ap_uint<1>& regRequestBindFault)',
            'ap_uint<1>& regRequestBindFault,stream<as02ReqToken>& request_segment_continue)')
        t=once(t,'static bool fault=false;regRequestBindFault=fault;if(fault)return;',
            'static bool fault=false;regRequestBindFault=fault;if(fault)return;\n'
            '    static bool segment_active=false;static ap_uint<748> segment_owner=0;\n'
            '    static ap_uint<32> segment_offset=0;')
        # Replays must retain priority even while awaiting a real packet ACK.
        t=once(t,'else if (!s_axis_sq_meta.empty() && !s_axis_request_owner.empty())',
            'else if(segment_active) {\n'+CONTINUE+'\n    }\n'
            '    else if (!s_axis_sq_meta.empty() && !s_axis_request_owner.empty())')
        t=once(t,'if (!s_axis_sq_meta.empty() && !s_axis_request_owner.empty())\n#endif',
            'if(segment_active) {\n'+CONTINUE+'\n    }\n'
            '    else if (!s_axis_sq_meta.empty() && !s_axis_request_owner.empty())\n#endif')
        t=once(t,'        offs = meta.offs;',
            '        offs = meta.offs;\n'
            '        if(as02_req_segmented(n)) {\n'
            '            segment_owner=n;segment_offset=PMTU;segment_active=true;\n'
            '            as02_emit_request_segment<INSTID>(n,0,false,tx_local_memCmdFifo,\n'
            '                tx_localTxMeta,tx2retrans_insertAddrLen,request_rx_owners);return;\n'
            '        }')
        return once(t,'memCmdInternal(rev.op_code, rev.qpn, rev.localAddr, rev.length, rev.host, rev.offs)',
            'memCmdInternal(rev.op_code, rev.qpn, rev.localAddr,\n'
            '                rev.op_code==RC_RDMA_WRITE_FIRST ? ap_uint<32>(PMTU):rev.length,rev.host,rev.offs)')
    out[CPP]=change(out[CPP],'void local_req_handler(',local)
    out[CPP]=once(out[CPP],'template <int INSTID = 0>\nvoid local_req_handler(',
        EMIT+'\ntemplate <int INSTID = 0>\nvoid local_req_handler(')
    def meta(t):
        pad='b.wire_pad=(ev.op_code==RC_RDMA_WRITE_LAST || ev.op_code==RC_SEND_LAST) ? ap_uint<2>(-ev.length):ap_uint<2>(0);'
        t=once(t,'b.request_token=ev.request_token;tx_ibhMetaFifo.write(b);',
            'b.request_token=ev.request_token;'+pad+'tx_ibhMetaFifo.write(b);')
        anchor='tx_ibhMetaFifo.write(ibhMeta(ev.op_code, key, ev.qpn, ev.psn, ev.validPsn));'
        end=t.index('\t/*else if (!timer2exhFifo.empty())')
        live=t[:end]
        if live.count(anchor)!=2:raise ValueError('both genuine response/replay BTH branches required')
        return live.replace(anchor,'ibhMeta b(ev.op_code,key,ev.qpn,ev.psn,ev.validPsn);'+pad+'tx_ibhMetaFifo.write(b);')+t[end:]
    out[CPP]=change(out[CPP],'void meta_merger(',meta)
    def ibh(t):
        t=once(t,'header.setAckReq(false);','header.setAckReq(false);header.setPadCount(meta.wire_pad);')
        return once(t,'meta.op_code==RC_SEND_ONLY || meta.op_code==RC_SEND_ONLY_WITH_IMD)header.setAckReq(true);',
            'meta.op_code==RC_SEND_ONLY || meta.op_code==RC_SEND_ONLY_WITH_IMD ||\n'
            '               meta.op_code==RC_RDMA_WRITE_FIRST || meta.op_code==RC_RDMA_WRITE_MIDDLE || meta.op_code==RC_RDMA_WRITE_LAST ||\n'
            '               meta.op_code==RC_SEND_FIRST || meta.op_code==RC_SEND_MIDDLE || meta.op_code==RC_SEND_LAST)header.setAckReq(true);')
    out[CPP]=change(out[CPP],'void generate_ibh(',ibh)
    out[CPP]=change(out[CPP],'void generate_exh(',lambda t:once(t,
        '(meta.request_owned && (meta.op_code == RC_SEND_ONLY || meta.op_code == RC_SEND_ONLY_WITH_IMD))',
        '(meta.request_owned && (meta.op_code == RC_SEND_ONLY || meta.op_code == RC_SEND_ONLY_WITH_IMD ||\n'
        '                meta.op_code==RC_SEND_FIRST || meta.op_code==RC_SEND_MIDDLE || meta.op_code==RC_SEND_LAST))'))
    def padding(t):
        t=once(t,'            info.header_bytes=(meta.op_code==RC_RDMA_WRITE_ONLY || meta.op_code==RC_RDMA_WRITE_FIRST ||',
            '            info.wire_pad=(meta.op_code==RC_RDMA_WRITE_LAST || meta.op_code==RC_SEND_LAST) ? ap_uint<2>(-meta.length):ap_uint<2>(0);\n'
            '            info.header_bytes=(meta.op_code==RC_RDMA_WRITE_ONLY || meta.op_code==RC_RDMA_WRITE_FIRST ||')
        first=t.index('// WRITE_MIDDLE / LAST / SEND:');end=t.index('case RC_RDMA_READ_REQUEST:',first)
        return t[:first]+once(t[first:end],'udpLen = 12+meta.length+4;',
            'udpLen = 12+meta.length+4+info.wire_pad;')+t[end:]
    out[CPP]=change(out[CPP],'void generate_exh(',padding)
    def append(t):
        t=once(t,'ap_uint<1024> joined=ap_uint<1024>(carry)|(ap_uint<1024>(w.data)<<(count*8));',
            'ap_uint<WIDTH> valid_data=w.data;\n'
            '            if(w.last && info.wire_pad!=0)valid_data&=(ap_uint<WIDTH>(1)<<(bytes*8))-1;\n'
            '            ap_uint<1024> joined=ap_uint<1024>(carry)|(ap_uint<1024>(valid_data)<<(count*8));')
        return once(t,'ap_uint<8> total=ap_uint<8>(count)+bytes;',
            'ap_uint<8> total=ap_uint<8>(count)+bytes+(w.last ? info.wire_pad:ap_uint<2>(0));')
    out[CPP]=change(out[CPP],'void append_payload(',append)
    # Owned replay entries are still EXACT singleton tails: the next fragment
    # cannot be inserted until the previous real pointer/pool/ACK has retired.
    out[RETRANS]=change(out[RETRANS],'void process_retransmissions(',lambda t:once(t,
        '((meta.opCode==RC_RDMA_WRITE_ONLY || meta.opCode == RC_RDMA_WRITE_ONLY_WIT_IMD) || (meta.opCode==RC_SEND_ONLY || meta.opCode == RC_SEND_ONLY_WITH_IMD))',
        '(meta.opCode==RC_RDMA_WRITE_ONLY || meta.opCode==RC_RDMA_WRITE_ONLY_WIT_IMD ||\n'
        '                   meta.opCode==RC_SEND_ONLY || meta.opCode==RC_SEND_ONLY_WITH_IMD ||\n'
        '                   meta.opCode==RC_RDMA_WRITE_FIRST || meta.opCode==RC_RDMA_WRITE_MIDDLE || meta.opCode==RC_RDMA_WRITE_LAST ||\n'
        '                   meta.opCode==RC_SEND_FIRST || meta.opCode==RC_SEND_MIDDLE || meta.opCode==RC_SEND_LAST)'))

    t=out[JOIN]
    t=once(t,'ap_uint<1> input_fault,ap_uint<1>& regFault)',
        'ap_uint<1> input_fault,ap_uint<1>& regFault,stream<as02ReqToken>& segment_continue)')
    t=once(t,'QUERY,STATE,PUBLISH};','QUERY,STATE,CONTINUE,PUBLISH};')
    t=once(t,'static as02ReqStep issued_step;static ap_uint<16> index=0;',
        'static as02ReqStep issued_step;static ap_uint<16> index=0;\n'
        '    static ap_uint<32> segment_offset=0;static ap_uint<24> first_psn=0;')
    t=once(t,'owner=admitted.read();if(!as02_req_owner_valid(owner)){fault=true;return;}phase=ISSUE;',
        'owner=admitted.read();if(!as02_req_owner_valid(owner)){fault=true;return;}segment_offset=0;phase=ISSUE;')
    t=once(t,'issued_step.opcode!=as02_req_opcode(owner)',
        'issued_step.opcode!=as02_req_segment_opcode(owner,segment_offset)')
    t=once(t,'        phase=INSERT;',
        '        if(segment_offset==0)first_psn=issued_step.psn;\n'
        '        else if(issued_step.psn!=ap_uint<24>(first_psn+segment_offset/PMTU)){fault=true;return;}\n'
        '        phase=INSERT;')
    t=once(t,'r.local!=owner(243,180) || r.remote!=owner(115,52) || r.length!=owner(307,276)',
        'r.local!=ap_uint<64>(ap_uint<64>(owner(243,180))+segment_offset) ||\n'
        '           r.remote!=(owner(339,324)==3 ? ap_uint<64>(0):ap_uint<64>(ap_uint<64>(owner(115,52))+segment_offset)) ||\n'
        '           r.length!=(as02_req_segmented(owner) && (segment_offset!=0 || owner(339,324)==3) ? as02_req_segment_bytes(owner,segment_offset):ap_uint<32>(owner(307,276)))')
    t=once(t,'!r.rkey_valid || !r.host || !r.lst || r.offs!=0',
        '!r.rkey_valid || !r.host || r.lst!=as02_req_segment_last(owner,segment_offset) || r.offs!=0')
    t=once(t,'        phase=PUBLISH;',
        '        phase=as02_req_segment_last(owner,segment_offset) ? PUBLISH:CONTINUE;')
    t=once(t,'    } else if(phase==PUBLISH && !output.full()) {',r'''
    } else if(phase==CONTINUE && !segment_continue.full()) {
        segment_continue.write(as02_req_token(owner));segment_offset+=PMTU;phase=ISSUE;
    } else if(phase==PUBLISH && !output.full()) {''')
    t=once(t,'r.context=owner;r.psn=issued_step.psn;r.next=ap_uint<25>(r.psn)+1;',
        'r.context=owner;r.psn=first_psn;r.next=ap_uint<24>(issued_step.psn+1);')
    t=once(t,'r.opcode=issued_step.opcode;output.write(r);phase=ADMIT;',
        'r.opcode=as02_req_opcode(owner);output.write(r);phase=ADMIT;')
    out[JOIN]=t
    out[CPP]=once(out[CPP],'static stream<ap_uint<748>> request_admitted("request_admitted");',
        'static stream<as02ReqToken> request_segment_continue("request_segment_continue");\n'
        '    #pragma HLS STREAM depth=2 variable=request_segment_continue\n'
        '    static stream<ap_uint<748>> request_admitted("request_admitted");')
    out[CPP]=once(out[CPP],'request_admitted,request_rx_owners,request_app_fault\n',
        'request_admitted,request_rx_owners,request_app_fault,request_segment_continue\n')
    out[CPP]=once(out[CPP],'m_axis_request_done,request_faults,request_join_fault);',
        'm_axis_request_done,request_faults,request_join_fault,request_segment_continue);')
    out[TOP]=out[TOP].replace(base.NAME,NAME)
    return out


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():p.error('preserve previous source')
    # Reuse the established licensed input layout; every parent remains exact.
    original=base.base.base.base.parent.qp.BASE
    before={str(x.relative_to(original)):hashlib.sha256(x.read_bytes()).hexdigest() for x in original.rglob('*') if x.is_file()}
    files=derive();shutil.copytree(original/'fns',a.output/'fns');shutil.copytree(original/'adapter',a.output/'adapter')
    for n,t in files.items():(a.output/'fns'/n).write_text(t)
    assert before=={n:hashlib.sha256((original/n).read_bytes()).hexdigest() for n in before}
    info=dict(scope=__doc__,source_base=str(original),source_sha256=before,
        generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        derived_sources={n:hashlib.sha256(t.encode()).hexdigest() for n,t in files.items()},
        original_unchanged=True,HLS_top=NAME,source_only=True,large_WRITE_SEND_max_bytes=1048576,
        packet_payload_bytes=4096,stop_and_wait_actual_packet_receipts=True,
        whole_WR_owner_bits=748,request_done_bits=816,SQ_bits=408,
        request_context_bits=748,receive_context_bits=620,shared_PSN_MSN=True,
        zero_length_requester=True,zero_RQ_SEND_and_Immediate=True,
        normal_zero_responder_WRITE_READ=True,zero_service_owner_bits=344,zero_service_done_bits=400,
        atomic_requester=True,atomic_service_request_bits=512,atomic_core_done_bits=224,
        native_integration=False,hardware_verified=False,full_board_timing=False,
        READ_Immediate_max_bytes=4096,multi_SGE_implemented=False)
    (a.output/'source.json').write_text(json.dumps(info,indent=2)+'\n')
    print(json.dumps(dict(output=str(a.output),HLS_top=NAME,source_only=True)))


if __name__=='__main__':main()
