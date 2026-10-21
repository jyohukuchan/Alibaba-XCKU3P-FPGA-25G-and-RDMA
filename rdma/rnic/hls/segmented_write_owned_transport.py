#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Typed remote-WRITE packet execution receipts in the actual HLS consumers.

Bind the protected424-bit packet identity to actual parser, payload EOF,
ACK/MSN and SAME PSN-state readback, separate from the posted620-bit RQ.
This does not manufacture native MR/DMA/fence/MAC/CQ authority. Qualified
parents/defaults remain immutable; new generation/native/physical proof is
required independently under the original clocks, geometry and gates.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import segmented_write_receive_transport as base

ROOT=base.ROOT;CPP=base.CPP;HPP=base.HPP;TOP=base.TOP;once=base.once;change=base.change
PARENT=ROOT/'rdma/rnic/build/native-segmented-write-receive-transport-001'
NAME='rocev2_native_segmented_write_owned_top'
JOIN='hls/ib_transport_protocol/as02_write_retire.hpp'
STATE='hls/ib_transport_protocol/state_table.hpp'

TYPES=r'''
// {message320,offset32,length32,PSN24,tag16}, SAME native protected identity.
// Neither this type nor a raw HLS command grants MR or physical DMA access.
struct as02WriteOwner {ap_uint<424> token=0;};
struct as02WriteProof {as02WriteOwner owner;ap_uint<24> msn=0;};
struct as02WriteDone {as02WriteProof proof;ap_uint<8> error=0;};
inline bool as02_write_owner_valid(as02WriteOwner o) {
    auto t=o.token;ap_uint<32> total=t(159,128),off=t(103,72),n=t(71,40);
    ap_uint<33> end=ap_uint<33>(off)+n;
    ap_uint<24> expected=ap_uint<24>(t(127,104))+ap_uint<24>(off>>12);
    return t(423,400)<MAX_QPS && t(399,384)!=0 && t(383,320)!=0 &&
        t(319,256)!=0 && t(255,224)!=0 && t(15,0)!=0 && total>PMTU && total<=1048576 &&
        ap_uint<65>(ap_uint<64>(t(223,160)))+total<=(ap_uint<65>(1)<<64) &&
        off(11,0)==0 && n!=0 && n<=PMTU && end<=total &&
        (end==total || n==PMTU) && ap_uint<24>(t(39,16))==expected;
}
inline bool as02_write_same(as02WriteProof a,as02WriteProof b) {
    return a.owner.token==b.owner.token && a.msn==b.msn;
}
'''

RETIRE=r'''
// Receipts are from ACTUAL payload EOF and ACK/MSN consumers. Query the
// SAME state table after real RX updates, never a delay or global idle bit.
template<int INSTID=0> void as02_write_packet_retire_join(
    stream<as02WriteProof>& data_done,stream<as02WriteProof>& ack_done,
    stream<ap_uint<24>>& state_req,stream<ap_uint<56>>& state_rsp,
    stream<as02WriteDone>& output,ap_uint<1>& regFault) {
#pragma HLS pipeline II=1
#pragma HLS inline off
    enum Phase {DATA,ACK,QUERY,STATE,PUBLISH};static Phase phase=DATA;
    static as02WriteProof saved;static bool fault=false;regFault=fault;
    if(fault)return;
    if(phase==DATA && !data_done.empty()) {
        saved=data_done.read();
        if(!as02_write_owner_valid(saved.owner)){fault=true;regFault=1;return;}
        phase=ACK;
    } else if(phase==ACK && !ack_done.empty()) {
        auto a=ack_done.read();
        if(!as02_write_same(saved,a)){fault=true;regFault=1;return;}
        phase=QUERY;
    } else if(phase==QUERY && !state_req.full()) {
        state_req.write(ap_uint<24>(saved.owner.token(423,400)));phase=STATE;
    } else if(phase==STATE && !state_rsp.empty()) {
        auto a=state_rsp.read();ap_uint<24> next=ap_uint<24>(saved.owner.token(39,16))+1;
        if(a(55,48)!=0 || a(23,0)!=saved.owner.token(423,400) || a(47,24)!=next) {
            fault=true;regFault=1;return;
        }
        phase=PUBLISH;
    } else if(phase==PUBLISH && !output.full()) {
        as02WriteDone d;d.proof=saved;output.write(d);phase=DATA;
    }
}
'''


def derive():
    out=base.derive()
    out[HPP]=once(out[HPP],'struct as02WriteNotify {',TYPES+'\nstruct as02WriteNotify {')
    for name in ['ackEvent','event','pkgShift']:
        out[HPP]=once(out[HPP],'struct '+name+'\n{',
            'struct '+name+'\n{\n    bool write_owned=false;as02WriteProof write_packet;')
    out[HPP]=once(out[HPP],'receive_owned(aev.receive_owned), receive(aev.receive),',
        'write_owned(aev.write_owned),write_packet(aev.write_packet),receive_owned(aev.receive_owned), receive(aev.receive),')
    # All real declarations/macros and both top forwarding layers.
    for name in [HPP,CPP,TOP]:
        text,n=re.subn(r'(ap_uint<1>& regRecvFault,)([ \t]*\\)?\n',
            lambda m:m[1]+(m[2]or'')+'\n    stream<as02WriteOwner>& s_axis_write_owner,'+(m[2]or'')+
            '\n    stream<as02WriteDone>& m_axis_write_done,'+(m[2]or'')+
            '\n    ap_uint<1>& regWriteFault,'+(m[2]or'')+'\n',out[name])
        if not n:raise ValueError('all real WRITE top declarations required:'+name)
        if name==TOP:
            old='m_axis_recv_message,regRecvFault,'
            if text.count(old)<2:raise ValueError('both actual full-top forwarding calls required')
            text=text.replace(old,old+'s_axis_write_owner,m_axis_write_done,regWriteFault,')
            if text.count('#pragma HLS INTERFACE ap_none port=regRecvFault')!=2 or text.count('void '+base.NAME+'(')!=2:
                raise ValueError('both actual top overloads and interfaces required')
            text=text.replace('#pragma HLS INTERFACE ap_none port=regRecvFault',
                '#pragma HLS INTERFACE ap_none port=regRecvFault\n'
                '#pragma HLS INTERFACE axis register port=s_axis_write_owner\n'
                '#pragma HLS aggregate variable=s_axis_write_owner compact=bit\n'
                '#pragma HLS INTERFACE axis register port=m_axis_write_done\n'
                '#pragma HLS aggregate variable=m_axis_write_done compact=bit\n'
                '#pragma HLS INTERFACE ap_none port=regWriteFault')
            text=text.replace('void '+base.NAME+'(','void '+NAME+'(')
        out[name]=text
    def rx(t):
        t=once(t,'stream<as02RecvOwner>& s_axis_recv_owner,',
            'stream<as02RecvOwner>& s_axis_recv_owner,stream<as02WriteOwner>& s_axis_write_owner,')
        t=once(t,'    static bool write_active[MAX_QPS]={};',
            '    static ap_uint<320> write_context[MAX_QPS];\n    static bool write_active[MAX_QPS]={};')
        t=once(t,'            // FIRST/MIDDLE never consume a receive descriptor.',r'''
            // A late RQ must not consume and lose the separately admitted
            // WRITE owner while this actual parser is waiting to execute.
            if(s_axis_write_owner.empty() || (immediate && s_axis_recv_owner.empty()))break;
            auto w=s_axis_write_owner.read();auto wt=w.token;
            if(!as02_write_owner_valid(w) || wt(423,400)!=q || wt(39,16)!=meta.psn ||
               wt(71,40)!=count || wt(103,72)!=offset || wt(159,128)!=total ||
               wt(223,160)!=address || (first ? wt(255,224)!=reth.getRemoteKey():
                   wt(423,104)!=write_context[q])) {
                recv_bind_fault=true;regRecvBindFault=1;break;
            }
            as02WriteProof wp;wp.owner=w;wp.msn=dmaMeta.msn+ap_uint<24>(last);
            // FIRST/MIDDLE never consume a receive descriptor.''')
        t=once(t,'o.psn!=meta.psn || o.length!=count)',
            'o.psn!=meta.psn || o.length!=count || o.context(371,356)!=wt(399,384) ||\n'
            '                   o.context(459,396)!=wt(383,320))')
        t=once(t,'            ackEvent a(q,meta.psn,false);pkgShift s(first ? SHIFT_RETH:SHIFT_NONE,q);',
            '            ackEvent a(q,meta.psn,false);pkgShift s(first ? SHIFT_RETH:SHIFT_NONE,q);\n'
            '            a.write_owned=true;a.write_packet=wp;s.write_owned=true;s.write_packet=wp;')
        t=once(t,'            if(first){write_base[q]=address;',
            '            if(first){write_context[q]=wt(423,104);write_base[q]=address;')
        return t
    out[CPP]=change(out[CPP],'void rx_exh_fsm(',rx)
    def extent(t):
        t=once(t,'    bool receive=shift.receive_owned;',
            '    bool remote_write=shift.write_owned;bool receive=shift.receive_owned;')
        t=once(t,'if(!shift.request_length_checked && !receive)return true;',
            'if(!shift.request_length_checked && !receive && !remote_write)return true;')
        t=once(t,'    ap_uint<32> expected=receive ?',
            '    ap_uint<32> actual=remote_write ? ap_uint<32>(shift.write_packet.owner.token(71,40)):shift.receive.owner.length;\n'
            '    ap_uint<32> expected=remote_write ? ap_uint<32>((actual+3)&ap_uint<32>(0xfffffffc)):receive ?')
        t=once(t,'    // Highest-set-bit plus exact prefix equality',
            '    if(remote_write && (!as02_write_owner_valid(shift.write_packet.owner) || shift.request_owned ||\n'
            '        (receive && shift.receive.owner.length!=actual)))return false;\n'
            '    // Highest-set-bit plus exact prefix equality')
        t=once(t,'if((!receive && !shift.request_owned)', 'if((!receive && !remote_write && !shift.request_owned)')
        t=once(t,'if(receive && next>shift.receive.owner.length)', 'if((receive || remote_write) && next>actual)')
        t=once(t,'copied>=shift.receive.owner.length ? ap_uint<33>(copied):ap_uint<33>(shift.receive.owner.length)',
            'copied>=actual ? ap_uint<33>(copied):ap_uint<33>(actual)')
        return t
    out[CPP]=change(out[CPP],'bool as02_read_payload_extent(',extent)
    def merge(t):
        t=once(t,'stream<as02RecvProof>& recv_data_done,',
            'stream<as02RecvProof>& recv_data_done,stream<as02WriteProof>& write_data_done,')
        t=once(t,'FWD_NONE, RECV_DONE, REQUEST_DONE','FWD_NONE, RECV_DONE, WRITE_DONE, REQUEST_DONE')
        old='state = shift.receive_owned ? RECV_DONE : shift.request_owned ? REQUEST_DONE : IDLE;'
        if t.count(old)!=3:raise ValueError('all actual data EOF consumers required')
        t=t.replace(old,'state = shift.receive_owned ? RECV_DONE : shift.write_owned ? WRITE_DONE : shift.request_owned ? REQUEST_DONE : IDLE;')
        return once(t,'        recv_data_done.write(shift.receive);state=IDLE;break;',
            '        recv_data_done.write(shift.receive);state=shift.write_owned ? WRITE_DONE:IDLE;break;\n'
            '    case WRITE_DONE:\n        write_data_done.write(shift.write_packet);state=IDLE;break;')
    out[CPP]=change(out[CPP],'void merge_rx_pkgs(',merge)
    def exh(t):
        t=once(t,'stream<as02RecvProof>& recv_ack_done,',
            'stream<as02RecvProof>& recv_ack_done,stream<as02WriteProof>& write_ack_done,')
        t=once(t,'PROCESS, RECV_DONE, ZERO_DONE','PROCESS, RECV_DONE, WRITE_DONE, ZERO_DONE')
        t=once(t,'meta.receive_owned ? RECV_DONE : META;',
            'meta.receive_owned ? RECV_DONE : meta.write_owned ? WRITE_DONE : META;')
        return once(t,'        recv_ack_done.write(p);ge_state=META;break;',
            '        recv_ack_done.write(p);ge_state=meta.write_owned ? WRITE_DONE:META;break;\n'
            '    }\n    case WRITE_DONE: {\n        as02WriteProof p=meta.write_packet;p.msn=msnMeta.msn;\n'
            '        write_ack_done.write(p);ge_state=META;break;')
    out[CPP]=change(out[CPP],'void generate_exh(',exh)
    t=out[STATE];anchor='hls::stream<as02ReqState>& requestFence_rsp'
    if t.count(anchor)!=2:raise ValueError('actual state table declaration and consumer required')
    t=t.replace(anchor,anchor+',hls::stream<ap_uint<24>>& writeFence_req,hls::stream<ap_uint<56>>& writeFence_rsp')
    def state(t):
        return t[:-1]+r'''
    else if(!writeFence_req.empty()) {
        ap_uint<24> q=writeFence_req.read();ap_uint<56> a=0;a(23,0)=q;
        // SAME actual table, after every prior RX/TX/QPI/retirement update.
        if(q>=MAX_QPS)a(55,48)=1;else a(47,24)=state_table[q].resp_epsn;
        writeFence_rsp.write(a);
    }
}'''
    out[STATE]=change(t,'void state_table(\t\t\n',state)
    out[JOIN]='// SPDX-License-Identifier: BSD-2-Clause-Views\n#pragma once\n'+RETIRE
    t=once(out[CPP],'#include "as02_recv_retire.hpp"','#include "as02_recv_retire.hpp"\n#include "as02_write_retire.hpp"')
    t=once(t,'    static stream<as02RecvProof> recv_data_done("recv_data_done"),recv_ack_done("recv_ack_done");',r'''
    static stream<as02WriteProof> write_data_done("write_data_done"),write_ack_done("write_ack_done");
    static stream<ap_uint<24>> writeFence_req("writeFence_req");
    static stream<ap_uint<56>> writeFence_rsp("writeFence_rsp");
    #pragma HLS STREAM depth=2 variable=write_data_done
    #pragma HLS STREAM depth=2 variable=write_ack_done
    #pragma HLS STREAM depth=2 variable=writeFence_req
    #pragma HLS STREAM depth=2 variable=writeFence_rsp
    ap_uint<1> write_join_fault;
    static stream<as02RecvProof> recv_data_done("recv_data_done"),recv_ack_done("recv_ack_done");''')
    t=once(t,'atomic_commit,s_axis_recv_owner,write_notify,recv_bind_fault',
        'atomic_commit,s_axis_recv_owner,s_axis_write_owner,write_notify,recv_bind_fault')
    t=once(t,'m_axis_mem_write_data,recv_data_done,request_read_consumed',
        'm_axis_mem_write_data,recv_data_done,write_data_done,request_read_consumed')
    t=once(t,'tx_exh2payFifo,recv_ack_done,zero_tx','tx_exh2payFifo,recv_ack_done,write_ack_done,zero_tx')
    t=once(t,'stateTable2qpi_rsp,recvFence_req,recvFence_rsp,requestFence_req,requestFence_rsp',
        'stateTable2qpi_rsp,recvFence_req,recvFence_rsp,requestFence_req,requestFence_rsp,writeFence_req,writeFence_rsp')
    t=once(t,'    regRecvFault=recv_bind_fault|recv_join_fault|recv_message_fault;',
        '    as02_write_packet_retire_join<INSTID>(write_data_done,write_ack_done,writeFence_req,writeFence_rsp,m_axis_write_done,write_join_fault);\n'
        '    regWriteFault=write_join_fault|recv_bind_fault|request_payload_fault;\n'
        '    regRecvFault=recv_bind_fault|recv_join_fault|recv_message_fault;')
    out[CPP]=t
    return out


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():p.error('preserve all earlier source cohorts')
    info=json.loads((PARENT/'source.json').read_text())
    if info.get('HLS_top')!=base.NAME:raise ValueError('exact qualified WRITE prototype parent required')
    before={str(p.relative_to(PARENT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in PARENT.rglob('*')if p.is_file()}
    original=base.derive()
    for n,h in info['derived_sources'].items():
        if before['fns/'+n]!=h or hashlib.sha256(original[n].encode()).hexdigest()!=h:raise ValueError('qualified parent changed:'+n)
    files=derive();shutil.copytree(PARENT/'fns',a.output/'fns');shutil.copytree(PARENT/'adapter',a.output/'adapter')
    for n,t in files.items():(a.output/'fns'/n).write_text(t)
    if any(hashlib.sha256((PARENT/n).read_bytes()).hexdigest()!=h for n,h in before.items()):raise ValueError('parent changed')
    result=dict(info,scope=__doc__,HLS_top=NAME,parent_source=str(PARENT),parent_tree_sha256=before,
        generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        derived_sources={n:hashlib.sha256(t.encode()).hexdigest()for n,t in files.items()},
        write_packet_owner_bits=424,write_packet_receipt_bits=456,distinct_from_posted620_RQ=True,
        actual_CPP_runtime=False,generated_HLS=False,native_integration=False,hardware_verified=False,full_board_timing=False)
    (a.output/'source.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(output=str(a.output),HLS_top=NAME,source_only=True)))


if __name__=='__main__':main()
