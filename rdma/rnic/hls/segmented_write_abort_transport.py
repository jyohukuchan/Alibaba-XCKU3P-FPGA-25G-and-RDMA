#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Typed partial-WRITE abort in the SAME actual HLS parser/tables/retire join.

Not a QP/global drain or permission to unpin. Native admission must already
quarantine this QP and bind real backend/fresh MAC proof. This consumer also
requires the ACTUAL positive HLS retire checkpoint, SAME PSN/MSN readbacks
and verification that its own selected partial-message state was cleared.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import segmented_control_response_transport as parent

ROOT=parent.ROOT;CPP=parent.CPP;HPP=parent.HPP;TOP=parent.TOP;once=parent.once;change=parent.change
PARENT=ROOT/'rdma/rnic/build/native-control-response-transport-001'
NAME='rocev2_native_write_abort_top'
STATE=parent.parent.STATE;JOIN=parent.parent.JOIN

TYPES=r'''
// {reserved8,proofFlags8,lastMACtag16,MSN24,control480,lastWritePacket424}.
// flags0 is DISTINCT empty state, requiring no fake positive WRITE owner.
// flags0f carries a privileged native EOF/fence/HLS/MAC certificate; actual
// HLS checkpoint/table/state validation remains independently mandatory.
struct as02WriteAbortOwner {ap_uint<960> token=0;};
struct as02WriteAbortDone {as02WriteAbortOwner owner;ap_uint<24> msn=0;ap_uint<8> error=0;};
'''

VALID=r'''
inline as02ControlOwner as02_abort_control(as02WriteAbortOwner o) {
    as02ControlOwner c;c.token=o.token(903,424);return c;
}
inline as02WriteProof as02_abort_packet(as02WriteAbortOwner o) {
    as02WriteProof p;p.owner.token=o.token(423,0);p.msn=o.token(927,904);return p;
}
inline bool as02_write_abort_valid(as02WriteAbortOwner o) {
    auto t=o.token;auto c=as02_abort_control(o);auto p=as02_abort_packet(o);auto w=p.owner.token;
    ap_uint<8> flags=t(951,944),syn=c.token(475,468);ap_uint<16> mac=t(943,928);
    if(t(959,952)!=0 || !as02_control_owner_valid(c) || (syn!=0x61 && syn!=0x62 && syn!=0x63))return false;
    if(flags==0)return w==0 && mac==0;
    ap_uint<33> end=ap_uint<33>(ap_uint<32>(w(103,72)))+ap_uint<32>(w(71,40));
    return flags==0x0f && as02_write_owner_valid(p.owner) && mac(15,13)==3 && mac(12,0)!=0 &&
        w(423,400)==c.token(23,0) && w(399,384)==c.token(39,24) && w(383,320)==c.token(103,40) &&
        w(71,40)==PMTU && end<ap_uint<32>(w(159,128)) &&
        ap_uint<24>(w(39,16)+1)==c.token(443,420);
}
'''

ADMISSION=r'''
    // A real join checkpoint, never a timer/idle/default-READY substitute.
    // Its queue producer is the SAME actual WRITE retirement consumer.
    if(!write_retired.empty()) {
        auto p=write_retired.read();
        if(!as02_write_owner_valid(p.owner)) {abort_fault=true;regWriteAbortFault=1;return;}
        ap_uint<24> q=p.owner.token(423,400);abort_checkpoint[q]=p;abort_checkpoint_valid[q]=true;
    }
    if(abort_fault)return;
    // An ordinary typed WRITE owner must not be abandoned in the input FIFO.
    // Queue emptiness is ONLY a safety gate, NEVER the abort certificate.
    if(pe_fsmState==META && !read_active && s_axis_write_owner.empty() && !s_axis_write_abort_owner.empty()) {
        abort_owner=s_axis_write_abort_owner.read();auto c=as02_abort_control(abort_owner);
        auto p=as02_abort_packet(abort_owner);auto w=p.owner.token;ap_uint<24> q=c.token(23,0);
        if(!as02_write_abort_valid(abort_owner) || c.token(419,356)<=abort_serial[q] || recv_active[q] ||
           (abort_owner.token(951,944)==0 ? write_active[q]:
            !write_active[q] || write_context[q]!=w(423,104) || write_tag[q]!=w(15,0) ||
            write_bytes[q]!=ap_uint<32>(w(103,72))+ap_uint<32>(w(71,40)) ||
            write_next[q]!=c.token(443,420) || write_total[q]!=w(159,128) || write_base[q]!=w(223,160) ||
            write_key[q]!=w(255,224) || write_first[q]!=w(127,104) || write_msn[q]!=p.msn)) {
            abort_fault=true;regWriteAbortFault=1;return;
        }
        abort_serial[q]=c.token(419,356);pe_fsmState=WRITE_ABORT_FENCE;return;
    }
'''

FSM=r'''
    case WRITE_ABORT_FENCE: {
        auto c=as02_abort_control(abort_owner);ap_uint<24> q=c.token(23,0);
        if(abort_owner.token(951,944)==0 ||
           (abort_checkpoint_valid[q] && as02_write_same(abort_checkpoint[q],as02_abort_packet(abort_owner))))
            pe_fsmState=WRITE_ABORT_PSN_QUERY;
        break;
    }
    case WRITE_ABORT_PSN_QUERY:
        writeAbortFence_req.write(ap_uint<24>(as02_abort_control(abort_owner).token(23,0)));
        pe_fsmState=WRITE_ABORT_PSN_REPLY;break;
    case WRITE_ABORT_PSN_REPLY:
        if(!writeAbortFence_rsp.empty()) {
            auto s=writeAbortFence_rsp.read();auto c=as02_abort_control(abort_owner);
            if(s(55,48)!=0 || s(23,0)!=c.token(23,0) || s(47,24)!=c.token(443,420)) {
                abort_fault=true;regWriteAbortFault=1;break;
            }
            pe_fsmState=WRITE_ABORT_MSN_QUERY;
        }
        break;
    case WRITE_ABORT_MSN_QUERY:
        rxExh2msnTable_upd_req.write(rxMsnReq(ap_uint<16>(as02_abort_control(abort_owner).token(23,0))));
        pe_fsmState=WRITE_ABORT_MSN_REPLY;break;
    case WRITE_ABORT_MSN_REPLY:
        if(!msnTable2rxExh_rsp.empty()) {
            auto m=msnTable2rxExh_rsp.read();
            if(m.msn!=abort_owner.token(927,904) || m.vaddr!=0 || m.dma_length!=0 || m.lst!=0) {
                abort_fault=true;regWriteAbortFault=1;break;
            }
            abort_actual_msn=m.msn;pe_fsmState=WRITE_ABORT_CLEAR;
        }
        break;
    case WRITE_ABORT_CLEAR: {
        ap_uint<24> q=as02_abort_control(abort_owner).token(23,0);
        write_active[q]=false;write_context[q]=0;write_base[q]=0;write_total[q]=0;write_bytes[q]=0;
        write_key[q]=0;write_first[q]=0;write_next[q]=0;write_msn[q]=0;write_tag[q]=0;
        abort_checkpoint_valid[q]=false;abort_checkpoint[q].owner.token=0;abort_checkpoint[q].msn=0;
        pe_fsmState=WRITE_ABORT_VERIFY;break;
    }
    case WRITE_ABORT_VERIFY: {
        ap_uint<24> q=as02_abort_control(abort_owner).token(23,0);
        if(write_active[q] || write_context[q]!=0 || write_base[q]!=0 || write_total[q]!=0 || write_bytes[q]!=0 ||
           write_key[q]!=0 || write_first[q]!=0 || write_next[q]!=0 || write_msn[q]!=0 || write_tag[q]!=0 ||
           abort_checkpoint_valid[q] || abort_checkpoint[q].owner.token!=0 || abort_checkpoint[q].msn!=0) {
            abort_fault=true;regWriteAbortFault=1;break;
        }
        pe_fsmState=WRITE_ABORT_PUBLISH;break;
    }
    case WRITE_ABORT_PUBLISH:
        if(!m_axis_write_abort_done.full()) {
            as02WriteAbortDone d;d.owner=abort_owner;d.msn=abort_actual_msn;
            m_axis_write_abort_done.write(d);pe_fsmState=META;
        }
        break;
'''


def derive():
    out=parent.derive();out[HPP]=once(out[HPP],'struct as02ControlOwner {',TYPES+'\nstruct as02ControlOwner {')
    out[CPP]=once(out[CPP],'template<int INSTID=0> void as02_native_control_merger(',VALID+'\ntemplate<int INSTID=0> void as02_native_control_merger(')
    for name in [HPP,CPP,TOP]:
        text,n=re.subn(r'(ap_uint<1>& regControlFault,)([ \t]*\\)?\n',
            lambda m:m[1]+(m[2]or'')+'\n    stream<as02WriteAbortOwner>& s_axis_write_abort_owner,'+(m[2]or'')+
            '\n    stream<as02WriteAbortDone>& m_axis_write_abort_done,'+(m[2]or'')+
            '\n    ap_uint<1>& regWriteAbortFault,'+(m[2]or'')+'\n',out[name])
        if not n:raise ValueError('every real write-abort top declaration required:'+name)
        if name==TOP:
            anchor='m_axis_control_done,regControlFault,'
            if text.count(anchor)!=3:raise ValueError('all three actual top forwarding calls required')
            text=text.replace(anchor,anchor+'s_axis_write_abort_owner,m_axis_write_abort_done,regWriteAbortFault,')
            anchor='#pragma HLS INTERFACE ap_none port=regControlFault'
            if text.count(anchor)!=2:raise ValueError('both actual top interface sets required')
            text=text.replace(anchor,anchor+'\n#pragma HLS INTERFACE axis register port=s_axis_write_abort_owner\n'
                '#pragma HLS aggregate variable=s_axis_write_abort_owner compact=bit\n'
                '#pragma HLS INTERFACE axis register port=m_axis_write_abort_done\n'
                '#pragma HLS aggregate variable=m_axis_write_abort_done compact=bit\n'
                '#pragma HLS INTERFACE ap_none port=regWriteAbortFault')
            text=text.replace('void '+parent.NAME+'(','void '+NAME+'(')
        out[name]=text
    def rx(t):
        t=once(t,'stream<as02WriteNotify>& write_notify,',r'''stream<as02WriteNotify>& write_notify,
    stream<as02WriteProof>& write_retired,stream<as02WriteAbortOwner>& s_axis_write_abort_owner,
    stream<as02WriteAbortDone>& m_axis_write_abort_done,ap_uint<1>& regWriteAbortFault,
    stream<ap_uint<24>>& writeAbortFence_req,stream<ap_uint<56>>& writeAbortFence_rsp,''')
        t=once(t,'ZERO_MSN_REPLY, ZERO_TX};','ZERO_MSN_REPLY, ZERO_TX, WRITE_ABORT_FENCE, WRITE_ABORT_PSN_QUERY, WRITE_ABORT_PSN_REPLY, WRITE_ABORT_MSN_QUERY, WRITE_ABORT_MSN_REPLY, WRITE_ABORT_CLEAR, WRITE_ABORT_VERIFY, WRITE_ABORT_PUBLISH};')
        t=once(t,'    static bool recv_bind_fault=false;',r'''    static bool abort_fault=false;regWriteAbortFault=abort_fault;
    static as02WriteAbortOwner abort_owner;static ap_uint<24> abort_actual_msn=0;
    static as02WriteProof abort_checkpoint[MAX_QPS];static bool abort_checkpoint_valid[MAX_QPS]={};
    static ap_uint<64> abort_serial[MAX_QPS]={};static ap_uint<16> write_tag[MAX_QPS];
    static bool recv_bind_fault=false;''')
        t=once(t,'    if(recv_bind_fault)return;', '    if(recv_bind_fault)return;\n'+ADMISSION)
        t=once(t,'            write_active[q]=!last;', '            write_tag[q]=wt(15,0);\n            write_active[q]=!last;')
        return once(t,'    case ATOMIC_REPLY:',FSM+'\n    case ATOMIC_REPLY:')
    out[CPP]=change(out[CPP],'void rx_exh_fsm(',rx)
    out[JOIN]=once(out[JOIN],'stream<as02WriteDone>& output,ap_uint<1>& regFault)',
        'stream<as02WriteDone>& output,stream<as02WriteProof>& write_retired,ap_uint<1>& regFault)')
    out[JOIN]=once(out[JOIN],'    } else if(phase==PUBLISH && !output.full()) {',
        '    } else if(phase==PUBLISH && !output.full() && !write_retired.full()) {')
    out[JOIN]=once(out[JOIN],'        as02WriteDone d;d.proof=saved;output.write(d);phase=DATA;',
        '        as02WriteDone d;d.proof=saved;output.write(d);write_retired.write(saved);phase=DATA;')
    t=out[STATE];anchor='hls::stream<ap_uint<56>>& writeFence_rsp'
    if t.count(anchor)!=2:raise ValueError('actual state table declaration and consumer required')
    t=t.replace(anchor,anchor+',hls::stream<ap_uint<24>>& writeAbortFence_req,hls::stream<ap_uint<56>>& writeAbortFence_rsp')
    def state(t):
        return t[:-1]+r'''
    else if(!writeAbortFence_req.empty()) {
        ap_uint<24> q=writeAbortFence_req.read();ap_uint<56> a=0;a(23,0)=q;
        if(q>=MAX_QPS)a(55,48)=1;else a(47,24)=state_table[q].resp_epsn;
        writeAbortFence_rsp.write(a);
    }
}'''
    out[STATE]=change(t,'void state_table(\t\t\n',state)
    out[CPP]=once(out[CPP],'    ap_uint<1> write_join_fault;',r'''    ap_uint<1> write_join_fault;
    static stream<as02WriteProof> write_abort_retired("write_abort_retired");
    static stream<ap_uint<24>> writeAbortFence_req("writeAbortFence_req");
    static stream<ap_uint<56>> writeAbortFence_rsp("writeAbortFence_rsp");
    #pragma HLS STREAM depth=2 variable=write_abort_retired
    #pragma HLS STREAM depth=2 variable=writeAbortFence_req
    #pragma HLS STREAM depth=2 variable=writeAbortFence_rsp''')
    out[CPP]=once(out[CPP],'s_axis_write_owner,write_notify,recv_bind_fault',
        's_axis_write_owner,write_notify,write_abort_retired,s_axis_write_abort_owner,m_axis_write_abort_done,regWriteAbortFault,writeAbortFence_req,writeAbortFence_rsp,recv_bind_fault')
    out[CPP]=once(out[CPP],'writeFence_req,writeFence_rsp\n\t);','writeFence_req,writeFence_rsp,writeAbortFence_req,writeAbortFence_rsp\n\t);')
    out[CPP]=once(out[CPP],'m_axis_write_done,write_join_fault);','m_axis_write_done,write_abort_retired,write_join_fault);')
    return out


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():p.error('preserve all earlier cohorts')
    info=json.loads((PARENT/'source.json').read_text());original=parent.derive()
    if info['HLS_top']!=parent.NAME:raise ValueError('exact actual control-HLS parent required')
    before={str(q.relative_to(PARENT)):hashlib.sha256(q.read_bytes()).hexdigest()for q in PARENT.rglob('*')if q.is_file()}
    for n,h in info['derived_sources'].items():
        if before['fns/'+n]!=h or hashlib.sha256(original[n].encode()).hexdigest()!=h:raise ValueError('actual parent changed:'+n)
    files=derive();shutil.copytree(PARENT/'fns',a.output/'fns');shutil.copytree(PARENT/'adapter',a.output/'adapter')
    for n,t in files.items():(a.output/'fns'/n).write_text(t)
    if any(hashlib.sha256((PARENT/n).read_bytes()).hexdigest()!=h for n,h in before.items()):raise ValueError('parent changed')
    result=dict(info,scope=__doc__,HLS_top=NAME,parent_source=str(PARENT),parent_tree_sha256=before,
        generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),derived_sources={n:hashlib.sha256(t.encode()).hexdigest()for n,t in files.items()},
        write_abort_owner_bits=960,write_abort_receipt_bits=992,abort_is_QP_or_global_drain=False,
        native_fatal_QP_error_or_unpin_qualified=False,actual_CPP_runtime=False,generated_HLS=False,native_integration=False,hardware_verified=False,full_board_timing=False)
    (a.output/'source.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(output=str(a.output),HLS_top=NAME,source_only=True)))


if __name__=='__main__':main()
