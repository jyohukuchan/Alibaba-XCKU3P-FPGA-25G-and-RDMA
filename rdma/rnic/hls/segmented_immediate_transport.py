#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""True segmented SEND/WRITE Immediate in the same READ-capable transport.

One retained748-bit WR, ordinary FIRST/MIDDLE packets and Immediate only in
LAST. Every fragment retains its exact replay metadata and must retire via
actual ACK/pointer/pool/timer/common-PSN consumers. This separate source
candidate does not raise old/default or receive-buffer limits, grant MR/DMA
authority, or claim native/Linux/physical/timing qualification.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import segmented_read_transport as base

ROOT=base.ROOT;CPP=base.CPP;HPP=base.HPP;TOP=base.TOP
JOIN=base.JOIN;RETRANS=base.RETRANS;once=base.once;change=base.change
NAME='rocev2_native_segmented_immediate_top'
PARENT=ROOT/'rdma/rnic/build/native-segmented-read-transport-003'


def derive():
    out=base.derive()
    t=out[HPP]
    t=once(t,'(op==1 || op==2 || op==3) ? 1048576U:4096U',
        '(op==1 || op==2 || op==3 || op==5 || op==6) ? 1048576U:4096U')
    t=once(t,'return (n(339,324)==1 || n(339,324)==3) && n(307,276)>PMTU;',
        'return (n(339,324)==1 || n(339,324)==3 || n(339,324)==5 || n(339,324)==6) && n(307,276)>PMTU;')
    t=change(t,'inline ibOpCode as02_req_segment_opcode(',lambda s:once(
        once(s,'bool send=n(339,324)==3;',
            'bool send=n(339,324)==3 || n(339,324)==5;\n    bool immediate=n(339,324)==5 || n(339,324)==6;'),
        'if(as02_req_segment_last(n,offset))return send ? RC_SEND_LAST:RC_RDMA_WRITE_LAST;',
        'if(as02_req_segment_last(n,offset))return immediate ?\n'
        '        (send ? RC_SEND_LAST_WITH_IMD:RC_RDMA_WRITE_LAST_WITH_IMD):\n'
        '        (send ? RC_SEND_LAST:RC_RDMA_WRITE_LAST);'))
    out[HPP]=t

    def emit(s):
        s=once(s,'n(339,324)==3 ? ap_uint<64>(0)',
            '(n(339,324)==3 || n(339,324)==5) ? ap_uint<64>(0)')
        s=once(s,'offset==0 && n(339,324)==1 ?',
            'offset==0 && (n(339,324)==1 || n(339,324)==6) ?')
        s=once(s,'ev.rkey=n(51,20);ev.rkey_valid=1;',
            'ev.immediate=n(619,588);ev.rkey=n(51,20);ev.rkey_valid=1;')
        return once(s,'r.request_owned=true;r.request_token=token;',
            'r.immediate=n(619,588);r.request_owned=true;r.request_token=token;')
    out[CPP]=change(out[CPP],'void as02_emit_request_segment(',emit)

    def memory(s):
        # LAST Immediate has four header bytes for both SEND and WRITE;
        # WRITE's RETH exists ONLY on FIRST. Use the existing unshifted lane
        # appender's AETH data input, not an invented memory command channel.
        return once(s,'if(cmd.op_code==RC_SEND_ONLY_WITH_IMD || cmd.op_code==RC_RDMA_WRITE_ONLY_WIT_IMD) {',r'''
        if(cmd.op_code==RC_SEND_LAST_WITH_IMD || cmd.op_code==RC_RDMA_WRITE_LAST_WITH_IMD) {
            if(cmd.sync)out.write(as02_duplex_command(memCmd(cmd.addr,cmd.len,PKG_F,SYNC,cmd.host,cmd.offs,cmd.qpn),true));
            else out.write(as02_duplex_command(memCmd(cmd.addr,cmd.len,PKG_F,cmd.host,cmd.qpn),true));
            pkgInfoFifo.write(pkgInfo(AETH,(cmd.len+WIDTH/8-1)/(WIDTH/8)));return;
        }
        if(cmd.op_code==RC_SEND_ONLY_WITH_IMD || cmd.op_code==RC_RDMA_WRITE_ONLY_WIT_IMD) {''')
    out[CPP]=change(out[CPP],'void mem_cmd_merger(',memory)

    final='(meta.op_code==RC_RDMA_WRITE_LAST || meta.op_code==RC_SEND_LAST)'
    expanded='(meta.op_code==RC_RDMA_WRITE_LAST || meta.op_code==RC_SEND_LAST || meta.op_code==RC_RDMA_WRITE_LAST_WITH_IMD || meta.op_code==RC_SEND_LAST_WITH_IMD)'
    def exh(s):
        s=once(s,final,expanded)
        s=once(s,'meta.op_code==RC_SEND_FIRST || meta.op_code==RC_SEND_MIDDLE || meta.op_code==RC_SEND_LAST)))',
            'meta.op_code==RC_SEND_FIRST || meta.op_code==RC_SEND_MIDDLE || meta.op_code==RC_SEND_LAST ||\n'
            '                meta.op_code==RC_SEND_LAST_WITH_IMD || meta.op_code==RC_RDMA_WRITE_LAST_WITH_IMD)))')
        return once(s,'            case RC_SEND_ONLY_WITH_IMD:',r'''
            case RC_SEND_LAST_WITH_IMD:
            case RC_RDMA_WRITE_LAST_WITH_IMD: {
                sendWord.data=0;
                sendWord.data(7,0)=meta.immediate(31,24);sendWord.data(15,8)=meta.immediate(23,16);
                sendWord.data(23,16)=meta.immediate(15,8);sendWord.data(31,24)=meta.immediate(7,0);
                info.header_bytes=4;info.isAETH=true;info.hasHeader=true;info.hasPayload=true;
                sendWord.keep=15;sendWord.last=1;output.write(sendWord);packetInfoFifo.write(info);
                lengthFifo.write(ap_uint<16>(12+4+meta.length+info.wire_pad+4));ge_state=META;break;
            }
            case RC_SEND_ONLY_WITH_IMD:''')
    out[CPP]=change(out[CPP],'void generate_exh(',exh)
    def meta(s):
        old='(ev.op_code==RC_RDMA_WRITE_LAST || ev.op_code==RC_SEND_LAST)'
        if s.count(old)!=3:raise ValueError('all three actual BTH fresh/replay paths required')
        return s.replace(old,'(ev.op_code==RC_RDMA_WRITE_LAST || ev.op_code==RC_SEND_LAST || ev.op_code==RC_RDMA_WRITE_LAST_WITH_IMD || ev.op_code==RC_SEND_LAST_WITH_IMD)')
    out[CPP]=change(out[CPP],'void meta_merger(',meta)
    out[CPP]=change(out[CPP],'void generate_ibh(',lambda s:once(s,
        'meta.op_code==RC_SEND_FIRST || meta.op_code==RC_SEND_MIDDLE || meta.op_code==RC_SEND_LAST)header.setAckReq(true);',
        'meta.op_code==RC_SEND_FIRST || meta.op_code==RC_SEND_MIDDLE || meta.op_code==RC_SEND_LAST ||\n'
        '               meta.op_code==RC_SEND_LAST_WITH_IMD || meta.op_code==RC_RDMA_WRITE_LAST_WITH_IMD)header.setAckReq(true);'))
    out[RETRANS]=change(out[RETRANS],'void process_retransmissions(',lambda s:once(s,
        'meta.opCode==RC_SEND_FIRST || meta.opCode==RC_SEND_MIDDLE || meta.opCode==RC_SEND_LAST)',
        'meta.opCode==RC_SEND_FIRST || meta.opCode==RC_SEND_MIDDLE || meta.opCode==RC_SEND_LAST ||\n'
        '                   meta.opCode==RC_SEND_LAST_WITH_IMD || meta.opCode==RC_RDMA_WRITE_LAST_WITH_IMD)'))
    t=out[JOIN]
    for old,new in [('owner(339,324)==3 ? ap_uint<64>(0)',
                     '(owner(339,324)==3 || owner(339,324)==5) ? ap_uint<64>(0)'),
                    ('segment_offset!=0 || owner(339,324)==3)',
                     'segment_offset!=0 || owner(339,324)==3 || owner(339,324)==5)')]:
        t=once(t,old,new)
    out[JOIN]=t
    out[TOP]=out[TOP].replace(base.NAME,NAME)
    return out


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():p.error('preserve prior source')
    info=json.loads((PARENT/'source.json').read_text())
    if info.get('HLS_top')!=base.NAME:raise ValueError('exact READ-capable source parent required')
    before={str(p.relative_to(PARENT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in PARENT.rglob('*')if p.is_file()}
    for n,h in info['derived_sources'].items():
        if before['fns/'+n]!=h:raise ValueError('parent body changed:'+n)
    files=derive();shutil.copytree(PARENT/'fns',a.output/'fns');shutil.copytree(PARENT/'adapter',a.output/'adapter')
    for n,t in files.items():(a.output/'fns'/n).write_text(t)
    if any(hashlib.sha256((PARENT/n).read_bytes()).hexdigest()!=h for n,h in before.items()):raise ValueError('parent changed')
    result=dict(info,scope=__doc__,HLS_top=NAME,parent_source=str(PARENT),parent_tree_sha256=before,
        generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        derived_sources={n:hashlib.sha256(t.encode()).hexdigest()for n,t in files.items()},
        Immediate_max_bytes=1048576,receive_buffer_max_bytes=4096,
        actual_CPP_runtime=False,generated_HLS=False,native_integration=False,hardware_verified=False,full_board_timing=False)
    (a.output/'source.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(output=str(a.output),HLS_top=NAME,source_only=True)))


if __name__=='__main__':main()
