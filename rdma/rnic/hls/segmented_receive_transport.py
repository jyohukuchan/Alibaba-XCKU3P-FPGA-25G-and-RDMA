#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Same full duplex HLS: owned segmented SEND/Immediate and whole RX receipts.

Packet receipts remain separate from the new whole-message output. Neither
is MR authorization, DMA visibility, actual ACK-MAC retirement or native CQ
permission. WRITE-with-Immediate needs a distinct remote-MR/late-RQ path and
is not implemented by treating its RETH destination as a SEND/RQ buffer.
All old/default source, requester and raw protected RTL remain unchanged.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import segmented_immediate_transport as base

ROOT=base.ROOT;CPP=base.CPP;HPP=base.HPP;TOP=base.TOP
JOIN='hls/ib_transport_protocol/as02_recv_retire.hpp'
once=base.once;change=base.change
NAME='rocev2_native_segmented_receive_top'
PARENT=ROOT/'rdma/rnic/build/native-segmented-immediate-transport-001'

SEND=r'''
        case RC_SEND_FIRST:
        case RC_SEND_MIDDLE:
        case RC_SEND_LAST:
        case RC_SEND_LAST_WITH_IMD: {
            if(s_axis_recv_owner.empty())break;
            as02RecvOwner o=s_axis_recv_owner.read();
            bool first=meta.op_code==RC_SEND_FIRST;
            bool last=meta.op_code==RC_SEND_LAST || meta.op_code==RC_SEND_LAST_WITH_IMD;
            bool immediate=meta.op_code==RC_SEND_LAST_WITH_IMD;
            ap_uint<24> q=meta.dest_qp;
            ap_uint<32> padded=(o.length+3)&ap_uint<32>(0xfffffffc);
            // Full QPN is checked BEFORE indexing. Never infer a whole SEND
            // length from posted capacity: BTH contains no total-byte field.
            if(q>=MAX_QPS || !as02_recv_owner_valid(o) || o.context(395,372)!=q ||
               meta.request_owned || meta.zero_owned || o.psn!=meta.psn || !o.length ||
               meta.wire_pad!=ap_uint<2>((-o.length)&3) ||
               ap_uint<32>(udpLength)!=24+(immediate ? 4:0)+padded ||
               (!last && (o.length!=PMTU || meta.wire_pad!=0))) {
                recv_bind_fault=true;regRecvBindFault=1;break;
            }
            ap_uint<32> offset=first ? ap_uint<32>(0):recv_bytes[q];
            ap_uint<33> next=ap_uint<33>(offset)+o.length;
            if((first ? recv_active[q] || o.context(307,276)<=PMTU:
                !recv_active[q] || recv_context[q]!=o.context || recv_next[q]!=meta.psn ||
                recv_msn[q]!=dmaMeta.msn) || next>ap_uint<32>(o.context(307,276)) ||
                next>1048576 || (!last && next>=ap_uint<32>(o.context(307,276)))) {
                recv_bind_fault=true;regRecvBindFault=1;break;
            }
            as02RecvProof p;p.owner=o;p.msn=dmaMeta.msn+ap_uint<24>(last);
            p.flags=first ? 4:last ? (immediate ? 17:16):8;
            if(immediate)p.immediate=exHeader.getImmediate(false);
            // Raw SEND offset/host0 is NOT physical DMA authority. A native
            // guard must independently retain and authorize the full MR/RQ.
            memoryWriteCmd.write(as02_duplex_command(memCmd(offset,padded,last,PKG_INT,q),false));
            rxExh2msnTable_upd_req.write(rxMsnReq(q,p.msn));
            ackEvent a(q,meta.psn,false);a.receive_owned=true;a.receive=p;rx_exhEventMetaFifo.write(a);
            rx_pkgSplitTypeFifo.write(pkgSplit(meta.op_code));
            pkgShift s(SHIFT_NONE,q);s.receive_owned=true;s.receive=p;rx_pkgShiftTypeFifo.write(s);
            recv_active[q]=!last;recv_context[q]=o.context;recv_next[q]=meta.psn+1;
            recv_bytes[q]=next;recv_msn[q]=dmaMeta.msn;pe_fsmState=META;break;
        }
'''

MESSAGE=r'''
// Full posted identity/capacity is preserved; bytes is actual cumulative
// payload, never posted capacity. This is a HLS execution receipt, NOT CQ.
struct as02RecvMessage {
    ap_uint<620> context=0;ap_uint<32> bytes=0;
    ap_uint<24> first_psn=0,last_psn=0,msn=0;
    ap_uint<32> immediate=0;ap_uint<8> flags=0,error=0;
};
inline bool as02_recv_packet_valid(as02RecvProof p) {
    bool flags=p.flags==0 || p.flags==1 || p.flags==3 || p.flags==4 ||
        p.flags==8 || p.flags==16 || p.flags==17;
    return flags && ((p.flags&1)!=0 || p.immediate==0) &&
        as02_recv_owner_valid(p.owner,p.flags==3) &&
        ((p.flags!=4 && p.flags!=8) || p.owner.length==PMTU) &&
        ((p.flags!=16 && p.flags!=17) || p.owner.length!=0);
}
'''

GROUP=r'''
// Consume only REAL data EOF + ACK/MSN + SAME PSN readback certificates.
// Keep per-packet ownership and whole-message ownership distinct. Publishing
// either stream may stall: no skipped consumer, fixed delay or idle proof.
template<int INSTID=0> void as02_recv_message_join(
    stream<as02RecvDone>& input,stream<as02RecvDone>& packets,
    stream<as02RecvMessage>& messages,ap_uint<1>& regFault) {
#pragma HLS pipeline II=1
#pragma HLS inline off
    enum phaseType {TAKE,PACKET,MESSAGE};static phaseType phase=TAKE;
    static bool active[MAX_QPS]={};static ap_uint<620> context[MAX_QPS];
    static ap_uint<32> bytes[MAX_QPS];static ap_uint<24> first_psn[MAX_QPS],next_psn[MAX_QPS],msn[MAX_QPS];
    static as02RecvDone saved;static as02RecvMessage whole;static bool finish=false,fault=false;
    regFault=fault;if(fault)return;
    if(phase==TAKE && !input.empty()) {
        saved=input.read();auto p=saved.proof;ap_uint<24> q=p.owner.context(395,372);
        if(saved.error || !as02_recv_packet_valid(p) || q>=MAX_QPS){fault=true;regFault=1;return;}
        bool first=p.flags==4,middle=p.flags==8,last=p.flags==16 || p.flags==17;
        ap_uint<33> total=p.owner.length;
        finish=!first && !middle;
        if(first) {
            if(active[q] || p.owner.context(307,276)<=PMTU){fault=true;regFault=1;return;}
            active[q]=true;context[q]=p.owner.context;bytes[q]=p.owner.length;
            first_psn[q]=p.owner.psn;next_psn[q]=p.owner.psn+1;msn[q]=p.msn;
        } else if(middle || last) {
            total=ap_uint<33>(bytes[q])+p.owner.length;
            if(!active[q] || context[q]!=p.owner.context || next_psn[q]!=p.owner.psn ||
               p.msn!=ap_uint<24>(msn[q]+ap_uint<24>(last)) || total>1048576 ||
               total>ap_uint<32>(p.owner.context(307,276)) ||
               (middle && total>=ap_uint<32>(p.owner.context(307,276)))) {
                fault=true;regFault=1;return;
            }
            bytes[q]=total;next_psn[q]=p.owner.psn+1;
        } else if(active[q]){fault=true;regFault=1;return;}
        if(finish) {
            whole.context=p.owner.context;whole.bytes=total;whole.first_psn=last ? first_psn[q]:p.owner.psn;
            whole.last_psn=p.owner.psn;whole.msn=p.msn;whole.immediate=p.immediate;whole.flags=p.flags&3;
            whole.error=0;
        }
        phase=PACKET;
    } else if(phase==PACKET && !packets.full()) {
        packets.write(saved);phase=finish ? MESSAGE:TAKE;
    } else if(phase==MESSAGE && !messages.full()) {
        messages.write(whole);active[ap_uint<24>(whole.context(395,372))]=false;phase=TAKE;
    }
}
'''


def derive():
    out=base.derive();t=out[HPP]
    t=once(t,'n(307,276)<=4096','n(307,276)<=1048576')
    t=once(t,'o.length<=4096 && (write || o.length<=n(307,276));',
        'o.length<=4096 && (write || o.length<=n(307,276)) &&\n'
        '        (n(307,276)==0 || (n(275,244)!=0 &&\n'
        '        ap_uint<65>(n(243,180))+ap_uint<32>(n(307,276))<=(ap_uint<65>(1)<<64) &&\n'
        '        ap_uint<65>(n(179,116))+ap_uint<32>(n(307,276))<=(ap_uint<65>(1)<<64)));')
    pos=t.index('\ninline bool as02_recv_same(');t=t[:pos]+MESSAGE+t[pos:];out[HPP]=t
    out[HPP]=once(out[HPP],'\tvoid setPadCount(ap_uint<2> pad_count)',
        '    ap_uint<2> getPadCount() {return header(13,12);}\n\tvoid setPadCount(ap_uint<2> pad_count)')
    def rx(t):
        t=once(t,'    static bool recv_bind_fault=false;',
            '    static bool recv_active[MAX_QPS]={};static ap_uint<620> recv_context[MAX_QPS];\n'
            '    static ap_uint<24> recv_next[MAX_QPS],recv_msn[MAX_QPS];static ap_uint<32> recv_bytes[MAX_QPS];\n'
            '    static bool recv_bind_fault=false;')
        t=once(t,'\t\tswitch(meta.op_code)\n\t\t{',r'''
        if(!checkIfResponse(meta.op_code) &&
            (meta.dest_qp>=MAX_QPS || (recv_active[meta.dest_qp] &&
             meta.op_code!=RC_SEND_MIDDLE && meta.op_code!=RC_SEND_LAST && meta.op_code!=RC_SEND_LAST_WITH_IMD))) {
            recv_bind_fault=true;regRecvBindFault=1;break;
        }
        switch(meta.op_code) {
''')
        start=t.index('\t\t// Last part of a SEND message stream');end=t.index('\t\tcase RC_RDMA_WRITE_ONLY:',start)
        return t[:start]+SEND+t[end:]
    out[CPP]=change(out[CPP],'void rx_exh_fsm(',rx)
    out[CPP]=change(out[CPP],'void rx_process_ibh(',lambda t:once(t,
        'metaOut.write(ibhMeta(bth.getOpCode(), bth.getPartitionKey(), bth.getDstQP(), bth.getPsn(), true));',
        'ibhMeta m(bth.getOpCode(), bth.getPartitionKey(), bth.getDstQP(), bth.getPsn(), true);\n'
        '                m.wire_pad=bth.getPadCount();metaOut.write(m);'))
    def forward(t):
        old='b.request_owned=meta.request_owned;b.request_token=meta.request_token;metaOut.write(b);'
        if t.count(old)!=2:raise ValueError('both fresh and duplicate actual RX forwarders required')
        return t.replace(old,'b.request_owned=meta.request_owned;b.request_token=meta.request_token;b.wire_pad=meta.wire_pad;metaOut.write(b);')
    out[CPP]=change(out[CPP],'void rx_ibh_fsm(',forward)
    # Reuse actual Immediate parser/stripper for the LAST four-byte header.
    for fun in ['void rx_process_exh(','void rx_exh_payload(']:
        out[CPP]=change(out[CPP],fun,lambda t:once(t,
            'opCode==RC_SEND_ONLY_WITH_IMD || opCode==RC_RDMA_WRITE_ONLY_WIT_IMD' if 'opCode=='in t else
            'meta.op_code==RC_SEND_ONLY_WITH_IMD || meta.op_code==RC_RDMA_WRITE_ONLY_WIT_IMD',
            'opCode==RC_SEND_ONLY_WITH_IMD || opCode==RC_SEND_LAST_WITH_IMD || opCode==RC_RDMA_WRITE_ONLY_WIT_IMD' if 'opCode=='in t else
            'meta.op_code==RC_SEND_ONLY_WITH_IMD || meta.op_code==RC_SEND_LAST_WITH_IMD || meta.op_code==RC_RDMA_WRITE_ONLY_WIT_IMD'))
    out[CPP]=change(out[CPP],'void rx_exh_payload(',lambda t:once(t,
        'imm_skip=meta.op_code==RC_SEND_ONLY_WITH_IMD ? 4:20;',
        'imm_skip=meta.op_code==RC_RDMA_WRITE_ONLY_WIT_IMD ? 20:4;'))
    def extent(t):
        t=once(t,'if(!shift.request_length_checked)return true;',r'''
    bool receive=shift.receive_owned;
    if(!shift.request_length_checked && !receive)return true;
    ap_uint<32> expected=receive ? ap_uint<32>((shift.receive.owner.length+3)&ap_uint<32>(0xfffffffc)):shift.request_bytes;
    if(receive && (!as02_recv_packet_valid(shift.receive) || shift.request_owned))return false;''')
        t=once(t,'if(!shift.request_owned || !count || word.keep!=mask || next>shift.request_bytes ||\n       bool(word.last)!=(next==shift.request_bytes))return false;',
            'if((!receive && !shift.request_owned) || !count || word.keep!=mask || next>expected ||\n'
            '       bool(word.last)!=(next==expected))return false;\n'
            '    if(receive)for(unsigned b=0;b<WIDTH/8;b++)\n'
            '        if(word.keep[b] && ap_uint<33>(copied)+b>=shift.receive.owner.length && word.data(8*b+7,8*b)!=0)return false;')
        return t
    out[CPP]=change(out[CPP],'bool as02_read_payload_extent(',extent)
    out[JOIN]=once(out[JOIN],
        '(saved.flags!=0 && saved.flags!=1 && saved.flags!=3) || (saved.flags==0 && saved.immediate!=0) || !as02_recv_owner_valid(saved.owner,saved.flags==3)',
        '!as02_recv_packet_valid(saved)')+GROUP
    t=out[CPP]
    t=once(t,'    ap_uint<1> recv_bind_fault,recv_join_fault;',
        '    ap_uint<1> recv_bind_fault,recv_join_fault,recv_message_fault;\n'
        '    static stream<as02RecvDone> recv_packet_done("recv_packet_done");\n'
        '#pragma HLS STREAM depth=2 variable=recv_packet_done')
    t=once(t,'recvFence_rsp,m_axis_recv_done,recv_join_fault);',
        'recvFence_rsp,recv_packet_done,recv_join_fault);\n'
        '    as02_recv_message_join<INSTID>(recv_packet_done,m_axis_recv_done,m_axis_recv_message,recv_message_fault);')
    t=once(t,'regRecvFault=recv_bind_fault|recv_join_fault;',
        'regRecvFault=recv_bind_fault|recv_join_fault|recv_message_fault;')
    out[CPP]=t
    for n,count in [(CPP,3),(TOP,3),(HPP,1)]:
        t=out[n];old='stream<as02RecvDone>& m_axis_recv_done,'
        if t.count(old)!=count:raise ValueError('exact real/prototype receive signatures required:'+n)
        out[n]=t.replace(old,old+'stream<as02RecvMessage>& m_axis_recv_message,')
    t=out[TOP];old='s_axis_recv_owner,m_axis_recv_done,regRecvFault'
    if t.count(old)!=3:raise ValueError('all actual top forwarders required')
    t=t.replace(old,'s_axis_recv_owner,m_axis_recv_done,m_axis_recv_message,regRecvFault')
    old='#pragma HLS aggregate variable=m_axis_recv_done compact=bit'
    if t.count(old)!=2:raise ValueError('both real top port declarations required')
    t=t.replace(old,old+'\n#pragma HLS INTERFACE axis register port=m_axis_recv_message\n#pragma HLS aggregate variable=m_axis_recv_message compact=bit')
    out[TOP]=t.replace(base.NAME,NAME)
    return out


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():p.error('preserve prior source')
    info=json.loads((PARENT/'source.json').read_text())
    if info.get('HLS_top')!=base.NAME:raise ValueError('exact full READ/Immediate parent required')
    before={str(p.relative_to(PARENT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in PARENT.rglob('*')if p.is_file()}
    for n,h in info['derived_sources'].items():
        if before['fns/'+n]!=h:raise ValueError('parent changed:'+n)
    files=derive();shutil.copytree(PARENT/'fns',a.output/'fns');shutil.copytree(PARENT/'adapter',a.output/'adapter')
    for n,t in files.items():(a.output/'fns'/n).write_text(t)
    if any(hashlib.sha256((PARENT/n).read_bytes()).hexdigest()!=h for n,h in before.items()):raise ValueError('parent changed')
    result=dict(info,scope=__doc__,HLS_top=NAME,parent_source=str(PARENT),parent_tree_sha256=before,
        generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        derived_sources={n:hashlib.sha256(t.encode()).hexdigest()for n,t in files.items()},
        receive_buffer_max_bytes=1048576,segmented_SEND_Immediate_receive=True,segmented_WRITE_Immediate_receive=False,
        receive_packet_done_bits=752,receive_message_bits=772,actual_CPP_runtime=False,
        generated_HLS=False,native_integration=False,hardware_verified=False,full_board_timing=False)
    (a.output/'source.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(output=str(a.output),HLS_top=NAME,source_only=True)))


if __name__=='__main__':main()
