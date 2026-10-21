#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Segmented incoming WRITE/WRITE Immediate, distinct target and late RQ.

Retain the complete READ/WRITE/SEND/Atomic/zero/receive graph. Raw RETH and
HLS commands are NOT MR or DMA authority: native full-message/per-packet
remote MR guards, real backend/MAC retirement and late-RQ coupling remain
required. Existing qualified source007 and defaults are immutable.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import segmented_receive_prefix_transport as base

ROOT=base.ROOT;CPP=base.CPP;HPP=base.HPP;TOP=base.TOP
JOIN=base.base.JOIN;once=base.base.once;change=base.base.change
PARENT=ROOT/'rdma/rnic/build/native-segmented-receive-transport-007'
NAME='rocev2_native_segmented_write_receive_top'

WRITE=r'''
        case RC_RDMA_WRITE_FIRST:
        case RC_RDMA_WRITE_MIDDLE:
        case RC_RDMA_WRITE_LAST:
        case RC_RDMA_WRITE_LAST_WITH_IMD: {
            ap_uint<24> q=meta.dest_qp;
            bool first=meta.op_code==RC_RDMA_WRITE_FIRST;
            bool last=meta.op_code==RC_RDMA_WRITE_LAST || meta.op_code==RC_RDMA_WRITE_LAST_WITH_IMD;
            bool immediate=meta.op_code==RC_RDMA_WRITE_LAST_WITH_IMD;
            unsigned header_bytes=first ? 16:immediate ? 4:0;
            if(q>=MAX_QPS || meta.request_owned || meta.zero_owned ||
               ap_uint<32>(udpLength)<24+header_bytes) {
                recv_bind_fault=true;regRecvBindFault=1;break;
            }
            ap_uint<32> wire=ap_uint<32>(udpLength)-(24+header_bytes);
            ap_uint<32> count=wire-ap_uint<2>(meta.wire_pad);
            auto reth=exHeader.getRdmaHeader();
            ap_uint<32> total=first ? reth.getLength():write_total[q];
            ap_uint<32> offset=first ? ap_uint<32>(0):write_bytes[q];
            ap_uint<64> address=first ? reth.getVirtualAddress():write_base[q];
            ap_uint<33> next=ap_uint<33>(offset)+count;
            if(!count || count>PMTU || wire!=ap_uint<32>((count+3)&ap_uint<32>(0xfffffffc)) ||
               meta.wire_pad!=ap_uint<2>((-count)&3) ||
               (first ? write_active[q] || total<=PMTU || total>1048576 ||
                    reth.getRemoteKey()==0 || ap_uint<65>(address)+total>(ap_uint<65>(1)<<64):
                    !write_active[q] || write_next[q]!=meta.psn || write_msn[q]!=dmaMeta.msn) ||
               next>total || (last ? next!=total:count!=PMTU || meta.wire_pad!=0 || next>=total)) {
                recv_bind_fault=true;regRecvBindFault=1;break;
            }
            // FIRST/MIDDLE never consume a receive descriptor. LAST with
            // Immediate binds ONE independently posted RQ only now; its
            // capacity/address are notification metadata, NOT the target.
            as02RecvProof p;
            if(immediate) {
                if(s_axis_recv_owner.empty())break;
                auto o=s_axis_recv_owner.read();
                if(!as02_recv_owner_valid(o,true) || o.context(395,372)!=q ||
                   o.psn!=meta.psn || o.length!=count) {
                    recv_bind_fault=true;regRecvBindFault=1;break;
                }
                p.owner=o;p.msn=dmaMeta.msn+1;p.flags=3;p.immediate=exHeader.getImmediate(false);
                as02WriteNotify n;n.context=o.context;n.bytes=total;n.first_psn=write_first[q];
                n.last_psn=meta.psn;n.msn=p.msn;n.immediate=p.immediate;write_notify.write(n);
            }
            memoryWriteCmd.write(as02_duplex_command(
                memCmd(ap_uint<64>(address+offset),wire,last,PKG_HOST,q),false));
            ap_uint<24> msn=dmaMeta.msn+ap_uint<24>(last);
            rxExh2msnTable_upd_req.write(rxMsnReq(q,msn));
            ackEvent a(q,meta.psn,false);pkgShift s(first ? SHIFT_RETH:SHIFT_NONE,q);
            if(immediate){a.receive_owned=true;a.receive=p;s.receive_owned=true;s.receive=p;}
            rx_exhEventMetaFifo.write(a);rx_pkgSplitTypeFifo.write(pkgSplit(meta.op_code));
            rx_pkgShiftTypeFifo.write(s);
            write_active[q]=!last;write_bytes[q]=next;write_next[q]=meta.psn+1;
            if(first){write_base[q]=address;write_total[q]=total;write_first[q]=meta.psn;
                write_msn[q]=dmaMeta.msn;write_key[q]=reth.getRemoteKey();}
            pe_fsmState=META;break;
        }
'''


def derive():
    out=base.derive();t=out[HPP]
    t=once(t,'struct as02RecvMessage {',r'''
// Execution metadata from the SAME incoming RETH/PSN/MSN consumer. It must
// join the REAL final packet data/ACK/readback proof before any whole output.
// It does not grant remote MR, DMA, late RQ or CQ authority.
struct as02WriteNotify {
    ap_uint<620> context=0;ap_uint<32> bytes=0;
    ap_uint<24> first_psn=0,last_psn=0,msn=0;ap_uint<32> immediate=0;
};
struct as02RecvMessage {''')
    out[HPP]=t
    def rx(t):
        t=once(t,'stream<as02RecvOwner>& s_axis_recv_owner,',
            'stream<as02RecvOwner>& s_axis_recv_owner,stream<as02WriteNotify>& write_notify,')
        t=once(t,'    static bool recv_bind_fault=false;',r'''
    static bool write_active[MAX_QPS]={};static ap_uint<64> write_base[MAX_QPS];
    static ap_uint<32> write_total[MAX_QPS],write_bytes[MAX_QPS],write_key[MAX_QPS];
    static ap_uint<24> write_first[MAX_QPS],write_next[MAX_QPS],write_msn[MAX_QPS];
    static bool recv_bind_fault=false;''')
        t=once(t,'        switch(meta.op_code) {',r'''
        if(!checkIfResponse(meta.op_code) && write_active[meta.dest_qp] &&
           meta.op_code!=RC_RDMA_WRITE_MIDDLE && meta.op_code!=RC_RDMA_WRITE_LAST &&
           meta.op_code!=RC_RDMA_WRITE_LAST_WITH_IMD) {
            recv_bind_fault=true;regRecvBindFault=1;break;
        }
        switch(meta.op_code) {''')
        # Keep the old ONLY implementation; replace only the segmented branch.
        start=t.index('\t\tcase RC_RDMA_WRITE_ONLY:');end=t.index('\t\tcase RC_RDMA_READ_REQUEST:',start)
        old=t[start:end];a=old.index('\t\tcase RC_RDMA_WRITE_MIDDLE:')
        only=once(old[:a],'\t\tcase RC_RDMA_WRITE_FIRST:\n','')
        t=t[:start]+only+WRITE+'\n'+t[end:]
        # Existing small/zero WRITE Immediate needs the same real metadata
        # join. Its actual packet proof remains unchanged (flags3/length).
        t=once(t,'p.immediate=exHeader.getImmediate(write);p.flags=write ? 3:1;',
            'p.immediate=exHeader.getImmediate(write);p.flags=write ? 3:1;\n'
            '            if(write){as02WriteNotify n;n.context=o.context;n.bytes=o.length;\n'
            '                n.first_psn=n.last_psn=meta.psn;n.msn=p.msn;n.immediate=p.immediate;write_notify.write(n);}')
        return t
    out[CPP]=change(out[CPP],'void rx_exh_fsm(',rx)
    for fun in ['void rx_process_exh(','void rx_exh_payload(']:
        def expand(t):
            for name in ['opCode','meta.op_code']:
                old=name+'==RC_SEND_LAST_WITH_IMD || '+name+'==RC_RDMA_WRITE_ONLY_WIT_IMD'
                if old in t:return once(t,old,name+'==RC_SEND_LAST_WITH_IMD || '+name+'==RC_RDMA_WRITE_LAST_WITH_IMD || '+name+'==RC_RDMA_WRITE_ONLY_WIT_IMD')
            raise ValueError('exact Immediate parser/stripper required')
        out[CPP]=change(out[CPP],fun,expand)
    utils='hls/ib_transport_protocol/ib_utils.cpp'
    out[utils]=change(out[utils],'bool checkIfWrite(',lambda t:once(t,
        'code == RC_RDMA_WRITE_ONLY_WIT_IMD)',
        'code == RC_RDMA_WRITE_ONLY_WIT_IMD || code == RC_RDMA_WRITE_LAST_WITH_IMD)'))
    # New join, leaving the qualified source007 helper itself available and
    # immutable. Same packet proof stays752 bits and whole output776 bits.
    old=out[JOIN];start=old.index('template<int INSTID=0> void as02_recv_message_join(')
    join=old[start:]
    join=once(join,'void as02_recv_message_join(', 'void as02_recv_write_message_join(')
    join=once(join,'stream<as02RecvMessage>& messages,ap_uint<1>& regFault)',
        'stream<as02RecvMessage>& messages,stream<as02WriteNotify>& write_notify,ap_uint<1>& regFault)')
    join=once(join,'enum phaseType {TAKE,PACKET,MESSAGE}', 'enum phaseType {TAKE,WRITE_NOTIFY,PACKET,MESSAGE}')
    join=once(join,'        phase=PACKET;\n    } else if(phase==PACKET',r'''
        phase=p.flags==3 ? WRITE_NOTIFY:PACKET;
    } else if(phase==WRITE_NOTIFY && !write_notify.empty()) {
        auto n=write_notify.read();auto p=saved.proof;
        ap_uint<24> span=n.last_psn-n.first_psn;
        ap_uint<24> expected=n.bytes==0 ? ap_uint<24>(0):ap_uint<24>((n.bytes-1)/PMTU);
        ap_uint<32> last_bytes=n.bytes==0 ? ap_uint<32>(0):ap_uint<32>(((n.bytes-1)%PMTU)+1);
        if(n.context!=p.owner.context || n.last_psn!=p.owner.psn || n.msn!=p.msn ||
           n.immediate!=p.immediate || n.bytes>1048576 || span!=expected || last_bytes!=p.owner.length) {
            fault=true;regFault=1;return;
        }
        whole.context=n.context;whole.bytes=n.bytes;whole.first_psn=n.first_psn;whole.last_psn=n.last_psn;
        whole.msn=n.msn;whole.immediate=n.immediate;whole.flags=3;whole.error=0;phase=PACKET;
    } else if(phase==PACKET''')
    out[JOIN]=old+'\n'+join
    t=out[CPP]
    t=once(t,'    static stream<as02RecvDone> recv_packet_done("recv_packet_done");',
        '    static stream<as02WriteNotify> write_notify("write_notify");\n'
        '#pragma HLS STREAM depth=2 variable=write_notify\n'
        '    static stream<as02RecvDone> recv_packet_done("recv_packet_done");')
    t=once(t,'atomic_commit,s_axis_recv_owner,recv_bind_fault',
        'atomic_commit,s_axis_recv_owner,write_notify,recv_bind_fault')
    t=once(t,'as02_recv_message_join<INSTID>(recv_packet_done,m_axis_recv_done,m_axis_recv_message,recv_message_fault);',
        'as02_recv_write_message_join<INSTID>(recv_packet_done,m_axis_recv_done,m_axis_recv_message,write_notify,recv_message_fault);')
    out[CPP]=t;out[TOP]=out[TOP].replace(base.NAME,NAME)
    return out


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():p.error('preserve previous source')
    info=json.loads((PARENT/'source.json').read_text())
    if info.get('HLS_top')!=base.NAME:raise ValueError('exact source007 complete parent required')
    before={str(p.relative_to(PARENT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in PARENT.rglob('*')if p.is_file()}
    for n,h in info['derived_sources'].items():
        if before['fns/'+n]!=h:raise ValueError('parent changed:'+n)
    files=derive();shutil.copytree(PARENT/'fns',a.output/'fns');shutil.copytree(PARENT/'adapter',a.output/'adapter')
    for n,t in files.items():(a.output/'fns'/n).write_text(t)
    if any(hashlib.sha256((PARENT/n).read_bytes()).hexdigest()!=h for n,h in before.items()):raise ValueError('parent changed')
    result=dict(info,scope=__doc__,HLS_top=NAME,parent_source=str(PARENT),parent_tree_sha256=before,
        generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        derived_sources={n:hashlib.sha256(t.encode()).hexdigest()for n,t in files.items()},
        segmented_WRITE_Immediate_receive=True,late_RQ_distinct_from_remote_RETH=True,
        actual_CPP_runtime=False,generated_HLS=False,native_integration=False,hardware_verified=False,full_board_timing=False)
    (a.output/'source.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(output=str(a.output),HLS_top=NAME,source_only=True)))


if __name__=='__main__':main()
