#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual generated control480/512 HLS and old ports, not native/physical.

Keep original4ns/default1.08ns/8QP/2000/1500MiB-start/7200s gates, all105
actual CPP modes and unchanged legacy service. Generation is not timing fit.
"""
import argparse
import json
from pathlib import Path
import re
import audit_segmented_receive as binding

ROOT=binding.ROOT;digest=binding.digest


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve prior evidence')
    names=['control-response-generated-hls-001','control-response-hls-003',
        'control-response-compat-001','control-response-hls-diagnostics-001','segmented-write-owned-generated-hls-001']
    records={};ids={}
    for n in names:records[n],ids[n]=binding.bindings(n)
    hls,cpp,compat,audit,old=[records[n]for n in names]
    if not all(r['pass_test']for r in [hls,cpp,compat,old])or not audit['audit_passed']or not hls['source_and_frozen_inputs_unchanged']:
        raise ValueError('actual current generation/frozen source/CPP105/legacy service and old core required')
    if not hls['all105_CPP_modes_required']or not hls['control_owner480_and_receipt512_verified']or hls['control_is_payload_completion']or len(cpp['tests'])!=105:
        raise ValueError('actual independent typed control ports and all105 modes required')
    if hls['HLS_top']!='rocev2_native_control_response_top'or (float(hls['target_clock_period']),float(hls['clock_uncertainty']),hls['MAX_QPS'],hls['metadata_entries'])!=(4,1.08,8,2000):
        raise ValueError('original HLS top/clock/uncertainty/geometry required')
    if hls['elapsed_seconds']>7200 or hls['free_bytes_at_start']<1572864000 or hls['exit_code']:
        raise ValueError('original actual synthesis deadline/root1500MiB start gate required')
    generated=ROOT/hls['directory']/'project/solution1/syn/verilog';top=generated/(hls['HLS_top']+'.v');text=top.read_text()
    ports=dict(s_axis_control_owner_TDATA=480,m_axis_control_done_TDATA=512,
        s_axis_write_owner_TDATA=424,m_axis_write_done_TDATA=456,m_axis_recv_message_TDATA=776)
    for name,width in ports.items():
        if not re.search(r'\[\s*'+str(width-1)+r'\s*:\s*0\s*\]\s*'+name+r'\s*;',text):raise ValueError('actual generated port width:'+name)
    if not re.search(r'\bregControlFault\b',text):raise ValueError('actual sticky control fault required')
    functions=['as02_native_control_merger_0_s','generate_exh_512_0_s','msn_table_0_s','state_table_0_s']
    domains={n:len([p for p in hls['generated_sha256']if p.endswith('_'+n+'.v')])for n in functions}
    if any(v!=1 for v in domains.values())or any('as02_native_rnr_merger'in n for n in hls['generated_sha256']):
        raise ValueError('ONE real control/old-ACK/RNR merger and SAME actual ACK/MSN/state domains required')
    if hls['original_effective_period_met']!=(float(hls['estimated_clock_period'])<=2.92):raise ValueError('original timing verdict must remain factual')
    for n,h in binding.PROTECTED.items():
        if digest(ROOT/n)!=h:raise ValueError('protected original raw source changed')
    result=dict(scope=__doc__,audit_passed=True,evidence=ids,verified_bindings=sum(v['bindings_verified']for v in ids.values()),
        actual_generation_seconds=hls['elapsed_seconds'],HLS_top=hls['HLS_top'],actual_port_widths=ports,actual_domain_definition_counts=domains,
        actual_generated_RTL_and_data_files=len(hls['generated_sha256']),resources=hls['resources'],
        target_clock_ns=4,default_uncertainty_ns=1.08,effective_ns=2.92,estimated_ns=float(hls['estimated_clock_period']),
        original_timing_met=hls['original_effective_period_met'],actual_CPP_modes=105,all87_previous_modes_retained=True,
        source_sha256={str(Path(__file__).relative_to(ROOT)):digest(__file__),str(top.relative_to(ROOT)):digest(top)},protected_raw_sha256=binding.PROTECTED,
        native_control_response_integration=False,real_MAC_control_proof=False,fatal_QP_error_and_teardown_qualified=False,
        live_Linux_or_physical=False,full_board_timing=False,overall_goal_complete=False,
        remaining=['Wire actual native full-context authentication and fresh nonwrapping480 control owner to this actual new HLS; shared allocator with typed512 core plus real MAC528 proof, no fake payload/RQ/CQ/PSN grant.',
            'Execute all37 old native cases plus futurePSN NAK, suppression/retry, duplicate ACK without repeated data, and proper fatal-QP quarantine; do not treat CPP or generation as native proof.',
            'All11/full1MiB native/multiSGE/live registered refs/real-peer NAK/RNR/MSN/congestion/safe partial-HLS cleanup/original timing/physical remain.'],
        hardware_or_default_actions=[],commit_or_push=False)
    with a.report.open('x')as f:f.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(audit_passed=True,verified_bindings=result['verified_bindings'],actual_generated=True,original_timing_met=result['original_timing_met'],native=False)),flush=True)


if __name__=='__main__':main()
