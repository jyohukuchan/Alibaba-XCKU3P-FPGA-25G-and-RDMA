#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual same-native-HLS receive operation receipts, not a global idle bit.

Bind the real protected648-bit owner at FNS SEND_ONLY execution, carry it
through real payload EOF and ACK/MSN consumers, then query the SAME PSN table.
This does not replace native memory visibility, MAC receipt/tail, CQ or safe
SQ/RQ ownership. Original full transport/native-RNR delivery is unchanged.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil

import rnr_transport as rnr

qp=rnr.qp;ROOT=qp.ROOT;once=qp.once

TYPES=r'''
// Compact owner648: full native context[587:0],actual bytes[619:588],
// packet PSN[643:620],reserved0[647:644]. None of this is raw DMA authority.
struct as02RecvOwner {
    ap_uint<588> context=0;
    ap_uint<32> length=0;
    ap_uint<24> psn=0;
    ap_uint<4> reserved=0;
};
struct as02RecvProof {as02RecvOwner owner;ap_uint<24> msn=0;};
struct as02RecvDone {as02RecvProof proof;ap_uint<8> error=0;};
inline bool as02_recv_owner_valid(as02RecvOwner o) {
    ap_uint<588> n=o.context;ap_uint<24> q=n(395,372);
    return o.reserved==0 && q<MAX_QPS && n(459,396)!=0 && n(523,460)!=0 &&
        n(355,340)!=0 && n(339,324)==4 && n(323,308)==1 && n(19,0)==3 &&
        n(115,20)==0 && n(307,276)!=0 && n(307,276)<=4096 &&
        o.length!=0 && o.length<=n(307,276);
}
inline bool as02_recv_same(as02RecvProof a,as02RecvProof b) {
    return a.owner.context==b.owner.context && a.owner.length==b.owner.length &&
        a.owner.psn==b.owner.psn && a.owner.reserved==b.owner.reserved && a.msn==b.msn;
}
'''

JOIN=r'''
// No port-idle/fixed-delay/private-pool substitute: these are receipts from
// actual SEND execution, actual payload EOF, actual ACK/MSN consumer, and a
// real lower-priority SAME state-table read after actual RX updates.
template<int INSTID=0> void as02_recv_retire_join(
    stream<as02RecvProof>& data_done,stream<as02RecvProof>& ack_done,
    stream<ap_uint<24>>& state_req,stream<ap_uint<56>>& state_rsp,
    stream<as02RecvDone>& output,ap_uint<1>& regFault) {
#pragma HLS pipeline II=1
#pragma HLS inline off
    enum phaseType {DATA,ACK,QUERY,STATE,PUBLISH};
    static phaseType phase=DATA;static as02RecvProof saved;
    static bool fault=false;regFault=fault;
    if(fault)return;
    if(phase==DATA && !data_done.empty()) {
        saved=data_done.read();
        if(!as02_recv_owner_valid(saved.owner)){fault=true;regFault=1;return;}
        phase=ACK;
    } else if(phase==ACK && !ack_done.empty()) {
        as02RecvProof a=ack_done.read();
        if(!as02_recv_same(saved,a)){fault=true;regFault=1;return;}
        phase=QUERY;
    } else if(phase==QUERY && !state_req.full()) {
        state_req.write(ap_uint<24>(saved.owner.context(395,372)));phase=STATE;
    } else if(phase==STATE && !state_rsp.empty()) {
        ap_uint<56> a=state_rsp.read();ap_uint<24> next=saved.owner.psn+1;
        if(a(55,48)!=0 || a(23,0)!=saved.owner.context(395,372) || a(47,24)!=next) {
            fault=true;regFault=1;return;
        }
        phase=PUBLISH;
    } else if(phase==PUBLISH && !output.full()) {
        as02RecvDone d;d.proof=saved;output.write(d);phase=DATA;
    }
}
'''

SEND=r'''
        case RC_SEND_ONLY:
        {
            if(s_axis_recv_owner.empty())break;
            as02RecvOwner o=s_axis_recv_owner.read();
            ap_uint<24> qpn=o.context(395,372);
            ap_uint<32> wire_length=(o.length+3)&ap_uint<32>(0xfffffffc);
            if(!as02_recv_owner_valid(o) || qpn!=meta.dest_qp || o.psn!=meta.psn ||
                ap_uint<32>(udpLength)!=wire_length+24) {
                recv_bind_fault=true;regRecvBindFault=1;break;
            }
            as02RecvProof p;p.owner=o;p.msn=dmaMeta.msn+1;
            // Original raw SEND shape stays address0/host0. Native saved MR
            // authorization remains the ONLY physical placement authority.
            memoryWriteCmd.write(memCmd(0,wire_length,PKG_F,PKG_INT,meta.dest_qp));
            rxExh2msnTable_upd_req.write(rxMsnReq(meta.dest_qp,p.msn));
            ackEvent a(meta.dest_qp,meta.psn,false);a.receive_owned=true;a.receive=p;
            rx_exhEventMetaFifo.write(a);
            rx_pkgSplitTypeFifo.write(pkgSplit(meta.op_code));
            pkgShift s(SHIFT_NONE,meta.dest_qp);s.receive_owned=true;s.receive=p;
            rx_pkgShiftTypeFifo.write(s);pe_fsmState=META;break;
        }
'''

def change_function(text,anchor,edit):
    a,b=qp.function(text,anchor);return text[:a]+edit(text[a:b])+text[b:]

def derive():
    out=rnr.derive();hpp='hls/ib_transport_protocol/ib_transport_protocol.hpp'
    cpp='hls/ib_transport_protocol/ib_transport_protocol.cpp';state='hls/ib_transport_protocol/state_table.hpp'
    top='hls/rocev2/rocev2.cpp'
    out[hpp]=once(out[hpp],'struct ackEvent\n{',TYPES+'\nstruct ackEvent\n{')
    for name in ['ackEvent','event','pkgShift']:
        out[hpp]=once(out[hpp],'struct '+name+'\n{',
            'struct '+name+'\n{\n    bool receive_owned=false;\n    as02RecvProof receive;')
    out[hpp]=once(out[hpp],':syndrome(aev.syndrome), syndrome_valid(aev.syndrome_valid),',
        ':receive_owned(aev.receive_owned), receive(aev.receive), syndrome(aev.syndrome), syndrome_valid(aev.syndrome_valid),')
    # Extend real declarations/macros and all top forwarding, not a sidecar.
    for name in [hpp,cpp,top]:
        text,n=re.subn(r'(ap_uint<1>& regRnrFault,)([ \t]*\\)?\n',
            lambda m:m[1]+(m[2]or'')+'\n    stream<as02RecvOwner>& s_axis_recv_owner,'+(m[2]or'')+
            '\n    stream<as02RecvDone>& m_axis_recv_done,'+(m[2]or'')+
            '\n    ap_uint<1>& regRecvFault,'+(m[2]or'')+'\n',out[name])
        if n<1:raise ValueError('missing receive top declaration '+name)
        if name==top:
            text=text.replace('s_axis_rnr_event,regRnrFault,','s_axis_rnr_event,regRnrFault,s_axis_recv_owner,m_axis_recv_done,regRecvFault,')
            text=text.replace('void rocev2_native_rnr_top(', 'void rocev2_native_recv_top(')
            text=text.replace('#pragma HLS INTERFACE ap_none port=regRnrFault',
                '#pragma HLS INTERFACE ap_none port=regRnrFault\n'
                '#pragma HLS INTERFACE axis register port=s_axis_recv_owner\n'
                '#pragma HLS aggregate variable=s_axis_recv_owner compact=bit\n'
                '#pragma HLS INTERFACE axis register port=m_axis_recv_done\n'
                '#pragma HLS aggregate variable=m_axis_recv_done compact=bit\n'
                '#pragma HLS INTERFACE ap_none port=regRecvFault')
        out[name]=text
    out['hls/ib_transport_protocol/as02_recv_retire.hpp']='// SPDX-License-Identifier: BSD-2-Clause-Views\n#pragma once\n'+JOIN
    out[cpp]=once(out[cpp],'#include "msn_table.hpp"','#include "msn_table.hpp"\n#include "as02_recv_retire.hpp"')
    def rx(t):
        t=once(t,'stream<pkgShift>& rx_pkgShiftTypeFifo\n',
            'stream<pkgShift>& rx_pkgShiftTypeFifo,\n    stream<as02RecvOwner>& s_axis_recv_owner,\n    ap_uint<1>& regRecvBindFault\n')
        t=once(t,'\tswitch (pe_fsmState)',
            '    static bool recv_bind_fault=false;regRecvBindFault=recv_bind_fault;\n'
            '    if(recv_bind_fault)return;\n\tswitch (pe_fsmState)')
        return once(t,'\t\tcase RC_SEND_ONLY: ',SEND)
    out[cpp]=change_function(out[cpp],'void rx_exh_fsm(',rx)
    def merge(t):
        t=once(t,'stream<net_axis<WIDTH> >& m_axis_mem_write_data\n',
            'stream<net_axis<WIDTH> >& m_axis_mem_write_data,\n    stream<as02RecvProof>& recv_data_done\n')
        t=once(t,'IDLE, FWD_AETH, FWD_RETH, FWD_NONE','IDLE, FWD_AETH, FWD_RETH, FWD_NONE, RECV_DONE')
        t=once(t,'\tpkgShift shift;','\tstatic pkgShift shift;')
        if t.count('\t\t\t\tstate = IDLE;')!=3:raise ValueError('unreviewed payload EOF consumers')
        t=t.replace('\t\t\t\tstate = IDLE;','\t\t\t\tstate = shift.receive_owned ? RECV_DONE : IDLE;')
        return once(t,'\t}//switch',
            '    case RECV_DONE:\n        recv_data_done.write(shift.receive);state=IDLE;break;\n\t}//switch')
    out[cpp]=change_function(out[cpp],'void merge_rx_pkgs(',merge)
    def exh(t):
        t=once(t,'stream<net_axis<WIDTH> >& output\n',
            'stream<net_axis<WIDTH> >& output,\n    stream<as02RecvProof>& recv_ack_done\n')
        t=once(t,'{META, GET_MSN, PROCESS}','{META, GET_MSN, PROCESS, RECV_DONE}')
        t=once(t,'\t\tif (sendWord.last)\n\t\t{\n\t\t\tge_state = META;\n\t\t}',
            '\t\tif (sendWord.last)\n\t\t{\n\t\t\tge_state = meta.receive_owned ? RECV_DONE : META;\n\t\t}')
        return once(t,'\t}//switch',
            '    case RECV_DONE: {\n        as02RecvProof p=meta.receive;p.msn=msnMeta.msn;\n'
            '        recv_ack_done.write(p);ge_state=META;break;\n    }\n\t}//switch')
    out[cpp]=change_function(out[cpp],'void generate_exh(',exh)
    st=out[state]
    if st.count('hls::stream<stateTableEntry>& stateTable2qpi_rsp')!=2:raise ValueError('state declaration changed')
    st=st.replace('hls::stream<stateTableEntry>& stateTable2qpi_rsp',
        'hls::stream<stateTableEntry>& stateTable2qpi_rsp,\n'
        '    hls::stream<ap_uint<24>>& recvFence_req,\n    hls::stream<ap_uint<56>>& recvFence_rsp')
    def state_consumer(t):
        return t[:-1]+r'''
    else if(!recvFence_req.empty()) {
        ap_uint<24> q=recvFence_req.read();ap_uint<56> a=0;a(23,0)=q;
        // Same actual consumer, lower priority than ALL prior RX/TX/QPI
        // updates. Full QPN checked BEFORE indexing the original table.
        if(q>=MAX_QPS)a(55,48)=1;
        else a(47,24)=state_table[q].resp_epsn;
        recvFence_rsp.write(a);
    }
}'''
    out[state]=change_function(st,'void state_table(\t\t\n',state_consumer)
    # Actual top local channels and actual producers/consumers.
    channels=r'''
    static stream<as02RecvProof> recv_data_done("recv_data_done"),recv_ack_done("recv_ack_done");
    static stream<ap_uint<24>> recvFence_req("recvFence_req");
    static stream<ap_uint<56>> recvFence_rsp("recvFence_rsp");
    #pragma HLS STREAM depth=2 variable=recv_data_done
    #pragma HLS STREAM depth=2 variable=recv_ack_done
    #pragma HLS STREAM depth=2 variable=recvFence_req
    #pragma HLS STREAM depth=2 variable=recvFence_rsp
    ap_uint<1> recv_bind_fault,recv_join_fault;
'''
    # Declarations must precede every actual producer in this dataflow body.
    a=out[cpp].index('void ib_transport_protocol(');left=out[cpp].index('{',a)
    out[cpp]=out[cpp][:left+1]+channels+out[cpp][left+1:]
    out[cpp]=once(out[cpp],'\t\trx_pkgShiftTypeFifo\n\t);',
        '\t\trx_pkgShiftTypeFifo,s_axis_recv_owner,recv_bind_fault\n\t);')
    out[cpp]=once(out[cpp],'rx_exhNoShiftFifo, m_axis_mem_write_data);',
        'rx_exhNoShiftFifo, m_axis_mem_write_data,recv_data_done);')
    out[cpp]=once(out[cpp],'\t\ttx_exh2payFifo\n\t);',
        '\t\ttx_exh2payFifo,recv_ack_done\n\t);')
    out[cpp]=once(out[cpp],'\t\tstateTable2qpi_rsp\n\t);',
        '\t\tstateTable2qpi_rsp,recvFence_req,recvFence_rsp\n\t);\n'
        '    as02_recv_retire_join<INSTID>(recv_data_done,recv_ack_done,recvFence_req,recvFence_rsp,m_axis_recv_done,recv_join_fault);\n'
        '    regRecvFault=recv_bind_fault|recv_join_fault;')
    return out

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():p.error('preserve prior sources/output')
    before={str(x.relative_to(qp.BASE)):qp.digest(x)for x in qp.BASE.rglob('*')if x.is_file()}
    new=derive();shutil.copytree(qp.BASE/'fns',a.output/'fns');shutil.copytree(qp.BASE/'adapter',a.output/'adapter')
    for n,t in new.items():(a.output/'fns'/n).write_text(t)
    if before!={n:qp.digest(qp.BASE/n)for n in before}:raise ValueError('original changed')
    info=dict(scope=__doc__,source_base=str(qp.BASE),source_sha256=before,
        generator_sha256=qp.digest(__file__),parent_generator_sha256=qp.digest(rnr.__file__),
        derived_sources={n:hashlib.sha256(t.encode()).hexdigest()for n,t in new.items()},
        original_unchanged=True,source_only=True,external_replay=True,native_rnr=True,receive_retirement=True,
        HLS_top='rocev2_native_recv_top',whole_core_drain_proved=False,hardware_verified=False)
    (a.output/'source.json').write_text(json.dumps(info,indent=2)+'\n')
    print(json.dumps(dict(output=str(a.output),HLS_top=info['HLS_top'],original_unchanged=True)))

if __name__=='__main__':main()
