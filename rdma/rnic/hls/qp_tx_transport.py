#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Main-transport derivative: independent TX PSN and actual state readback.

Retains the frozen per-WR-key full transport and original licenses/capacity.
The main RTL has a separate opt-in core selection; old delivery/rollback are
not modified. No source/C simulation result authorizes generated RTL or HW.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import tempfile

ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT/'rdma/rnic/build/wrkey-hls-p037tedt/inputs'
TX_ONLY=0x415332545850

def once(text,a,b):
    if text.count(a)!=1:raise ValueError('QP transport anchor changed: '+a)
    return text.replace(a,b,1)

def function(text,anchor):
    start=text.index(anchor);left=text.index('{',start);end=left+1;depth=1
    while depth:
        if text[end]=='{':depth+=1
        elif text[end]=='}':depth-=1
        end+=1
    return start,end

QPI=r'''void qp_interface(
    stream<qpContext>& contextIn,
    stream<stateTableEntry>& stateTable2qpi_rsp,
    stream<ifStateReq>& qpi2stateTable_upd_req,
    stream<ifMsnReq>& if2msnTable_init,
    stream<as02QpApply>& m_axis_qp_apply
) {
#pragma HLS inline off
#pragma HLS pipeline II=1
    enum phaseType { IDLE, BEFORE, VERIFY_REQUEST, VERIFY, PUBLISH };
    static phaseType phase=IDLE;
    static qpContext context;
    static stateTableEntry before;
    static as02QpApply reply;
    static bool tx_only=false;
    if(phase==IDLE) {
        if(!contextIn.empty() && !qpi2stateTable_upd_req.full()) {
            context=contextIn.read();
            tx_only=context.virtual_address==ap_uint<48>(0x415332545850ULL);
            reply.qpn=context.qp_num;reply.flags=0;
            if(context.qp_num>=MAX_QPS) {phase=PUBLISH;return;}
            qpi2stateTable_upd_req.write(ifStateReq(context.qp_num));phase=BEFORE;
        }
    } else if(phase==BEFORE) {
        if(!stateTable2qpi_rsp.empty() && !qpi2stateTable_upd_req.full() &&
            (tx_only || !if2msnTable_init.full())) {
            before=stateTable2qpi_rsp.read();
            qpi2stateTable_upd_req.write(ifStateReq(context.qp_num,context.newState,
                context.remote_psn,context.local_psn,tx_only));
            // Reinitializing MSN here would discard a live responder's
            // receive address/MSN. TX-only NEVER sends that initialization.
            if(!tx_only)if2msnTable_init.write(ifMsnReq(context.qp_num,context.r_key));
            phase=VERIFY_REQUEST;
        }
    } else if(phase==VERIFY_REQUEST) {
        if(!qpi2stateTable_upd_req.full()) {
            // SAME FIFO read follows the real write; input acceptance,
            // port-idle and a fixed delay cannot manufacture this reply.
            qpi2stateTable_upd_req.write(ifStateReq(context.qp_num));phase=VERIFY;
        }
    } else if(phase==VERIFY) {
        if(!stateTable2qpi_rsp.empty()) {
            stateTableEntry after=stateTable2qpi_rsp.read();
            bool rx_ok=tx_only ?
                (after.resp_epsn==before.resp_epsn &&
                 after.resp_old_outstanding==before.resp_old_outstanding &&
                 after.retryCounter==before.retryCounter) :
                (after.resp_epsn==context.local_psn &&
                 after.resp_old_outstanding==context.local_psn);
            bool tx_ok=after.req_next_psn==context.remote_psn &&
                after.req_old_unack==context.remote_psn && after.req_old_valid==context.remote_psn;
            reply.tx_psn=after.req_next_psn;reply.rx_psn=after.resp_epsn;
            reply.flags=(rx_ok && tx_ok ? 1:0) | (tx_only ? 2:0);
            phase=PUBLISH;
        }
    } else if(!m_axis_qp_apply.full()) {m_axis_qp_apply.write(reply);phase=IDLE;}
}
'''

def derive(base,external_replay=False):
    hpp='hls/ib_transport_protocol/ib_transport_protocol.hpp'
    state='hls/ib_transport_protocol/state_table.hpp'
    cpp='hls/ib_transport_protocol/ib_transport_protocol.cpp'
    top='hls/rocev2/rocev2.cpp'
    output={n:(base/n).read_text()for n in [hpp,state,cpp,top]}
    output[hpp]=once(output[hpp],'/* QP connection */',r'''
// Private actual state-consumer readback, NOT whole-core drain/CQ proof.
// Aggregation: qpn[23:0],tx_psn[47:24],rx_psn[71:48],flags[79:72].
struct as02QpApply {
    ap_uint<24> qpn=0,tx_psn=0,rx_psn=0;
    ap_uint<8> flags=0;
};
/* QP connection */''')
    output[state]=once(output[state],'\tbool\t\twrite;\n\tifStateReq()',
        '\tbool\t\twrite;\n bool tx_only=false;\n\tifStateReq()')
    output[state]=once(output[state],
        'ifStateReq(ap_uint<16> qpn, qpState s, ap_uint<24> rpsn, ap_uint<24> lpsn)',
        'ifStateReq(ap_uint<16> qpn, qpState s, ap_uint<24> rpsn, ap_uint<24> lpsn, bool tx_only=false)')
    output[state]=once(output[state],
        ':qpn(qpn), newState(s), remote_psn(rpsn), local_psn(lpsn), write(true) {}',
        ':qpn(qpn), newState(s), remote_psn(rpsn), local_psn(lpsn), write(true), tx_only(tx_only) {}')
    output[state]=once(output[state],
        '\t\t\tstate_table[ifRequest.qpn].resp_epsn = ifRequest.local_psn;',
        '\t\t\tif(!ifRequest.tx_only) {\n\t\t\tstate_table[ifRequest.qpn].resp_epsn = ifRequest.local_psn;')
    output[state]=once(output[state],
        '\t\t\tstate_table[ifRequest.qpn].resp_old_outstanding = ifRequest.local_psn;',
        '\t\t\tstate_table[ifRequest.qpn].resp_old_outstanding = ifRequest.local_psn;\n'
        ' state_table[ifRequest.qpn].retryCounter=0x7;\n }')
    output[state]=once(output[state], '\t\t\tstate_table[ifRequest.qpn].retryCounter = 0xF;', '')
    a,b=function(output[cpp],'void qp_interface(')
    output[cpp]=output[cpp][:a]+QPI+output[cpp][b:]
    output[cpp]=once(output[cpp],
        'qp_interface<INSTID>(s_axis_qp_interface, stateTable2qpi_rsp, qpi2stateTable_upd_req, if2msnTable_init);',
        'qp_interface<INSTID>(s_axis_qp_interface, stateTable2qpi_rsp, qpi2stateTable_upd_req, if2msnTable_init, m_axis_qp_apply);')
    # Extend ALL real transport declarations/instantiations, including macro
    # declarations. Width/QP/key capacities and private normal pipelines stay.
    for name in [hpp,cpp,top]:
        text=output[name]
        text,count=re.subn(r'(stream<ifConnReq>&\s*s_axis_qp_conn_interface,[^\n]*)(\n)',
            lambda m:m[1]+m[2]+'\tstream<as02QpApply>& m_axis_qp_apply,'+
            (' \\\n'if '\\'in m[1]else'\n'),text)
        if count<1:raise ValueError('missing transport QP declaration: '+name)
        if name==top:
            text,count=re.subn(r'(?m)^([ \t]*s_axis_qp_conn_interface,[ \t]*\n)',r'\1        m_axis_qp_apply,\n',text)
            if count!=3:raise ValueError('unreviewed top forwarding count '+str(count))
            text=text.replace('void rocev2_top(','void rocev2_qptx_top(')
            text=text.replace('#pragma HLS INTERFACE axis register port=s_axis_qp_conn_interface',
                '#pragma HLS INTERFACE axis register port=s_axis_qp_conn_interface\n'
                '#pragma HLS INTERFACE axis register port=m_axis_qp_apply\n'
                '#pragma HLS aggregate variable=m_axis_qp_apply compact=bit')
        output[name]=text
    if external_replay:
        timer='hls/ib_transport_protocol/transport_timer.hpp'
        # Retry ownership has MOVED to the actual retained-frame RTL owner,
        # which is selected atomically by EXTERNAL_REPLAY_ENABLE. Only native
        # local WRs use this core; the separate legacy initiator is unchanged.
        # Consume bookkeeping so no abandoned timer FIFO can fill. Do NOT
        # clear retransmitter metadata, fabricate ACKs or claim core drain.
        output[timer]=(base/timer).read_text()+r'''
#define AS02_NATIVE_EXTERNAL_REPLAY 1
template<int INSTID=0> void as02_native_external_replay_timer(
    stream<rxTimerUpdate>& rx,stream<ap_uint<24>>& tx) {
#pragma HLS pipeline II=1
#pragma HLS inline off
    if(!rx.empty())rx.read();
    else if(!tx.empty())tx.read();
}
'''
        output[cpp]=once(output[cpp],'transport_timer<INSTID>(', 'as02_native_external_replay_timer<INSTID>(')
        # The native RTL owns timer retries now. Remove the obsolete HLS
        # timer event CHANNEL, not just its producer: an undriven dataflow
        # stream is not synthesizable. Real RX ACK metadata release and
        # retransmission tables remain intact; this is NOT a drain proof.
        output[cpp]=once(output[cpp],
            '\tstatic stream<retransmission> timer2retrans_req("timer2retrans_req");\n','')
        output[cpp]=once(output[cpp],'\t#pragma HLS STREAM depth=2 variable=timer2retrans_req\n','')
        output[cpp]=once(output[cpp],'\t\ttxSetTimer_req,\n\t\ttimer2retrans_req\n',
            '\t\ttxSetTimer_req\n')
        output[cpp]=once(output[cpp],'\t\ttimer2retrans_req,\n','')
        retrans='hls/ib_transport_protocol/retransmitter/retransmitter.hpp'
        text=(base/retrans).read_text()
        a,b=function(text,'else if (!timer2retrans_req.empty())')
        text=text[:a]+text[b:]
        text=once(text,'\tstream<retransmission>&         timer2retrans_req,\n','')
        text=once(text,'\tstream<retransmission>& timer2retrans_req,\n','')
        text=once(text,'\t\ttimer2retrans_req,\n','')
        if 'timer2retrans_req' in text or 'timer2retrans_req' in output[cpp]:
            raise ValueError('obsolete native timer channel remains')
        output[retrans]=text
        output[top]=output[top].replace('void rocev2_qptx_top(','void rocev2_native_replay_top(')
    return output

def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--external-replay',action='store_true')
    args=parser.parse_args()
    if args.output.exists():parser.error('preserve prior source/output')
    before={str(p.relative_to(BASE)):digest(p)for p in BASE.rglob('*')if p.is_file()}
    new=derive(BASE/'fns',args.external_replay)
    shutil.copytree(BASE/'fns',args.output/'fns')
    shutil.copytree(BASE/'adapter',args.output/'adapter')
    for n,text in new.items():(args.output/'fns'/n).write_text(text)
    if before!={n:digest(BASE/n)for n in before}:raise ValueError('original inputs changed')
    report=dict(scope=__doc__,source_base=str(BASE),source_sha256=before,
        generator_sha256=digest(__file__),derived_sources={n:hashlib.sha256(v.encode()).hexdigest()for n,v in new.items()},
        original_unchanged=True,generated_RTL_or_hardware_verified=False,source_only=True,
        external_replay=args.external_replay,whole_core_drain_proved=False)
    (args.output/'source.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(output=str(args.output),changed_sources=list(new),original_unchanged=True)))

if __name__=='__main__':main()
