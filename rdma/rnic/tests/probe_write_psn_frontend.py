#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Real IPv4/ICRC/MR/RQ frontend47 with certified PSN-only reject metadata.

Retain all47 previous raw stimuli and protection/replay oracles. Additional
formal-output checks ensure only checked trusted-peer/format PSN rejects
produce a full native356/receivedPSN/expectedPSN certificate. Backend/HLS/
ACK/native frontier/context are models; not full native packet execution.
"""
import ast
from pathlib import Path
import probe_segmented_write_rx_frontend as parent
import sys

ROOT=parent.ROOT;once=parent.once
sys.path.insert(0,str(ROOT/'rdma/rnic/fpga'))
import derive_write_psn_control_native as candidate

OBSERVE=r'''
wire m_control_certified;
wire [355:0] m_control_context;
wire [23:0] m_control_received_psn,m_control_expected_psn;
wire [31:0] m_packet_notification;
integer certified_cycles=0,certified_consumed=0;
always @(posedge clk)if(!rst)begin
 if(m_control_certified!==1'b0 && m_control_certified!==1'b1)$fatal(1,"unknown checked PSN certificate VALID");
 if(m_control_certified)begin
  certified_cycles=certified_cycles+1;
  if(!m_reject_valid || m_reject_error!==18 || m_control_context!==native_context ||
    m_control_received_psn!==m_reject_psn || m_control_expected_psn!==trusted_expected_psn ||
    m_reject_qpn!==trusted_qpn || crc_good_count==0 || m_mr_valid || m_packet_valid || output_valid)
   $fatal(1,"certificate not bound to genuine checked trusted peer/format PSN reject or replayed data");
  if(m_reject_ready)certified_consumed=certified_consumed+1;
 end
 if(m_reject_valid && m_reject_error==18 && !m_control_certified)
  $fatal(1,"actual checked PSN mismatch lost native-context certification");
 if((mode==16 || mode==49) && m_control_certified)$fatal(1,"wrong-peer or bad-ICRC frame received control authority");
end
'''


def runner_source():
    t=Path(parent.__file__).read_text();a=t.index('"""');b=t.index('"""',a+3)+3;t=t[:a]+'"""'+__doc__+'"""'+t[b:]
    t=once(t,'def bench():\n    text=', 'def bench():\n    text=')
    t=once(t,"    ports=prior.ports(FRONT.read_text())", "    text=once(text,'module tb;','module tb;\\n'+OBSERVE)\n    ports=prior.ports(FRONT.read_text())")
    t=once(t,"instance='rocev2_segmented_write_rx_frontend #(","instance='rocev2_segmented_write_native_frontend #(")
    t=once(t,' $display("RAW_WRITE_REPLAY_RESULT ',
        ' $display("PSN_CERT_RESULT {\\"mode\\":%0d,\\"cycles\\":%0d,\\"consumed\\":%0d}",mode,certified_cycles,certified_consumed);\n'
        ' $display("RAW_WRITE_REPLAY_RESULT ')
    t=once(t,'def main():\n', 'def main():\n    global FRONT\n')
    t=once(t,"prefix='segmented-write-rx-front-'","prefix='write-psn-front-'")
    t=once(t,"prefix='as02-segmented-write-rx-front-'","prefix='as02-write-psn-front-'")
    t=once(t,'    sources=[FRONT,',"    FRONT=run/'rocev2_segmented_write_native_frontend.v'\n    FRONT.write_text(candidate.frontend())\n    sources=[FRONT,")
    t=once(t,'authored=sources+[Path(__file__).resolve(),',
        'authored=sources+[Path(parent.__file__).resolve(),Path(candidate.__file__).resolve(),Path(candidate.native.leaves.__file__).resolve(),Path(__file__).resolve(),')
    t=once(t,'    for n in sources:shutil.copy2(n,run/n.name)',
        '    for n in sources:\n        if n.resolve()!=(run/n.name).resolve():shutil.copy2(n,run/n.name)')
    t=once(t,"            s=t['protection'];raw=t['replay']",r'''
            certs=[json.loads(s.split(' ',1)[1])for s in c.stdout.splitlines()if s.startswith('PSN_CERT_RESULT ')]
            # Old22 deliberately supplies native expected=received=0, then
            # the message guard rejects its relative position with error16.
            # It is NOT a certified native-frontier PSN18 mismatch (old17 is).
            if len(certs)!=1 or certs[0]['mode']!=mode or bool(certs[0]['cycles'])!=(mode==17):
                raise ValueError('actual checked-frame certificate cardinality/types')
            t['certification']=certs[0]
            s=t['protection'];raw=t['replay']''')
    ast.parse(t);return t


if __name__=='__main__':
    exec(compile(runner_source(),str(Path(__file__).resolve()),'exec'),dict(__name__='__main__',__file__=str(Path(__file__).resolve()),OBSERVE=OBSERVE,candidate=candidate,parent=parent))
