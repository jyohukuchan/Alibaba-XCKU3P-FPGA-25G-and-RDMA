#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Native empty-RQ RNR on the SAME actual FNS ACK/MSN/connection pipeline.

Trusted protected admission supplies a full24-bit QPN/PSN and timer code0.
No packet/RQ/PSN/MSN/DMA state is fabricated or advanced by this event.
The original per-WR-key/QP/native-replay sources and licenses are preserved.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

import qp_tx_transport as qp

ROOT=qp.ROOT
once=qp.once

TYPES=r'''
// Only the protected native parser may supply this event AFTER complete
// ICRC/peer/QPN/expected-PSN/length authentication and an actual empty RQ.
// Bit aggregation is qpn[23:0],psn[47:24],syndrome[55:48]. No remote VA/key.
struct as02RnrEvent {
    ap_uint<24> qpn=0,psn=0;
    ap_uint<8> syndrome=0x20; // RNR, min_rnr_timer0; no unconsumed setting
};
'''

MERGER=r'''
template<int INSTID=0> void as02_native_rnr_merger(
    stream<ackEvent>& exh,stream<ackEvent>& ibh,
    stream<as02RnrEvent>& rnr,stream<ackEvent>& output,
    ap_uint<1>& regRnrFault) {
#pragma HLS pipeline II=1
#pragma HLS inline off
    static bool fault=false;
    regRnrFault=fault;
    if(fault || output.full())return;
    // Preserve the original ACK ordering; RNR has no receive packet in the
    // HLS RX pipeline and cannot enqueue an RX PSN/MSN/memory operation.
    if(!exh.empty())output.write(exh.read());
    else if(!ibh.empty())output.write(ibh.read());
    else if(!rnr.empty()) {
        as02RnrEvent e=rnr.read();
        // Validate the FULL field before any table's historical narrowing.
        if(e.qpn>=MAX_QPS || e.syndrome!=0x20) {fault=true;regRnrFault=1;return;}
        ackEvent a(e.qpn,e.psn,false);
        a.syndrome=e.syndrome;a.syndrome_valid=true;output.write(a);
    }
}
'''

def derive():
    output=qp.derive(qp.BASE/'fns',external_replay=True)
    hpp='hls/ib_transport_protocol/ib_transport_protocol.hpp'
    cpp='hls/ib_transport_protocol/ib_transport_protocol.cpp'
    top='hls/rocev2/rocev2.cpp'
    output[hpp]=once(output[hpp],'struct ackEvent\n{',TYPES+'\nstruct ackEvent\n{')
    output[hpp]=once(output[hpp],'struct ackEvent\n{',
        'struct ackEvent\n{\n    ap_uint<8> syndrome=0;\n    bool syndrome_valid=false;')
    output[hpp]=once(output[hpp],'struct event\n{',
        'struct event\n{\n    ap_uint<8> syndrome=0;\n    bool syndrome_valid=false;')
    output[hpp]=once(output[hpp],
        ':op_code(RC_ACK), qpn(aev.qpn), psn(aev.psn), validPsn(aev.validPsn), isNak(aev.isNak) {}',
        ':syndrome(aev.syndrome), syndrome_valid(aev.syndrome_valid), op_code(RC_ACK), qpn(aev.qpn), psn(aev.psn), validPsn(aev.validPsn), isNak(aev.isNak) {}')
    # Extend every real declaration, macro specialization and top forwarding.
    for name in [hpp,cpp,top]:
        text=output[name]
        text=text.replace('stream<as02QpApply>& m_axis_qp_apply,',
            'stream<as02QpApply>& m_axis_qp_apply,\n'
            '    stream<as02RnrEvent>& s_axis_rnr_event,\n'
            '    ap_uint<1>& regRnrFault,') if name==top else text
        if name!=top:
            import re
            text,n=re.subn(r'(stream<as02QpApply>& m_axis_qp_apply,)([ \t]*\\)?\n',
                lambda m:m[1]+(m[2]or'')+'\n    stream<as02RnrEvent>& s_axis_rnr_event,'+
                    (m[2]or'')+'\n    ap_uint<1>& regRnrFault,'+(m[2]or'')+'\n',text)
            if n<1:raise ValueError('missing real RNR declaration '+name)
        else:
            text=text.replace('        m_axis_qp_apply,\n',
                '        m_axis_qp_apply,\n        s_axis_rnr_event,regRnrFault,\n')
            text=text.replace('void rocev2_native_replay_top(', 'void rocev2_native_rnr_top(')
            text=text.replace('#pragma HLS aggregate variable=m_axis_qp_apply compact=bit',
                '#pragma HLS aggregate variable=m_axis_qp_apply compact=bit\n'
                '#pragma HLS INTERFACE axis register port=s_axis_rnr_event\n'
                '#pragma HLS aggregate variable=s_axis_rnr_event compact=bit\n'
                '#pragma HLS INTERFACE ap_none port=regRnrFault')
        output[name]=text
    output[cpp]=once(output[cpp],'template <int WIDTH, int INSTID = 0>\nvoid generate_exh(',
        MERGER+'\ntemplate <int WIDTH, int INSTID = 0>\nvoid generate_exh(')
    output[cpp]=once(output[cpp],
        'stream_merger<ackEvent>(rx_exhEventMetaFifo, rx_ibhEventFifo, rx_ackEventFifo);',
        'as02_native_rnr_merger<INSTID>(rx_exhEventMetaFifo, rx_ibhEventFifo, s_axis_rnr_event, rx_ackEventFifo, regRnrFault);')
    output[cpp]=once(output[cpp],
        '//Check if ACK or NAK\n\t\t\t\tif (!meta.isNak)\n\t\t\t\t{\n\t\t\t\t\tackHeader.setSyndrome(0x00);',
        '//Check if ACK or NAK\n\t\t\t\tif (!meta.isNak)\n\t\t\t\t{\n\t\t\t\t\tackHeader.setSyndrome(meta.syndrome_valid ? meta.syndrome : ap_uint<8>(0x00));')
    return output

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():p.error('preserve prior source/output')
    before={str(x.relative_to(qp.BASE)):qp.digest(x)for x in qp.BASE.rglob('*')if x.is_file()}
    new=derive();shutil.copytree(qp.BASE/'fns',a.output/'fns');shutil.copytree(qp.BASE/'adapter',a.output/'adapter')
    for n,t in new.items():(a.output/'fns'/n).write_text(t)
    if before!={n:qp.digest(qp.BASE/n)for n in before}:raise ValueError('original inputs changed')
    report=dict(scope=__doc__,source_base=str(qp.BASE),source_sha256=before,
        generator_sha256=qp.digest(__file__),parent_generator_sha256=qp.digest(qp.__file__),
        derived_sources={n:hashlib.sha256(t.encode()).hexdigest()for n,t in new.items()},
        original_unchanged=True,source_only=True,external_replay=True,native_rnr=True,
        HLS_top='rocev2_native_rnr_top',whole_core_drain_proved=False,hardware_verified=False)
    (a.output/'source.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(output=str(a.output),HLS_top=report['HLS_top'],original_unchanged=True)))

if __name__=='__main__':main()
