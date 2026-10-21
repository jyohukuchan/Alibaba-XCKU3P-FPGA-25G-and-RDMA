#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual generated960/992 WRITE-abort HLS, not native/QP/global drain proof.

Require all140 CPP consumers, same-source legacy compatibility, actual port
widths/one parser/MSN/state domain and original clock/geometry/resource gates.
"""
import argparse
import json
from pathlib import Path
import re
import audit_segmented_receive as binding

ROOT=binding.ROOT;digest=binding.digest


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve earlier evidence')
    names=['write-abort-generated-hls-001','write-abort-hls-003','write-abort-compat-001',
        'write-abort-hls-diagnostics-001','control-response-generated-hls-001']
    records={};ids={}
    for n in names:records[n],ids[n]=binding.bindings(n)
    hls,cpp,compat,audit,old=[records[n]for n in names]
    if not all(r['pass_test']for r in [hls,cpp,compat,old])or not audit['audit_passed']or not hls['source_and_frozen_inputs_unchanged']or \
       not hls['wrapper_and_builder_unchanged']:raise ValueError('actual current generated/full140/legacy service/frozen source required')
    if not hls['all140_CPP_modes_required']or not hls['write_abort_owner960_and_receipt992_verified']or \
       hls['abort_is_QP_or_global_drain']or len(cpp['tests'])!=140:raise ValueError('actual full140 and distinct960/992, never QP/global drain required')
    if hls['HLS_top']!='rocev2_native_write_abort_top'or \
       (float(hls['target_clock_period']),float(hls['clock_uncertainty']),hls['MAX_QPS'],hls['metadata_entries'])!=(4,1.08,8,2000):
        raise ValueError('original HLS clock/uncertainty/8QP/2000 required')
    if hls['elapsed_seconds']>7200 or hls['free_bytes_at_start']<1572864000 or hls['exit_code']:
        raise ValueError('original7200s/1500MiB start gates required')
    generated=ROOT/hls['directory']/'project/solution1/syn/verilog';top=generated/(hls['HLS_top']+'.v');text=top.read_text()
    ports=dict(s_axis_write_abort_owner_TDATA=960,m_axis_write_abort_done_TDATA=992,
        s_axis_control_owner_TDATA=480,m_axis_control_done_TDATA=512,
        s_axis_write_owner_TDATA=424,m_axis_write_done_TDATA=456,m_axis_recv_message_TDATA=776)
    for n,w in ports.items():
        if not re.search(r'\[\s*'+str(w-1)+r'\s*:\s*0\s*\]\s*'+n+r'\s*;',text):raise ValueError('actual generated width:'+n)
    if not all(re.search(r'\b'+n+r'\b',text)for n in ['regWriteAbortFault','regControlFault','regWriteFault']):
        raise ValueError('all actual fault outputs required')
    functions=['as02_native_control_merger_0_s','rx_exh_fsm_512_0_s','as02_write_packet_retire_join_0_s',
        'generate_exh_512_0_s','msn_table_0_s','state_table_0_s']
    domains={n:len([f for f in hls['generated_sha256']if f.endswith('_'+n+'.v')])for n in functions}
    if any(v!=1 for v in domains.values()):raise ValueError('ONE actual parser/checkpoint/ACK/MSN/state domain required:'+str(domains))
    estimate=float(hls['estimated_clock_period'])
    if hls['original_effective_period_met']!=(estimate<=2.92):raise ValueError('original effective2.92ns verdict must remain factual')
    for n,h in binding.PROTECTED.items():
        if digest(ROOT/n)!=h:raise ValueError('protected original raw source changed:'+n)
    result=dict(scope=__doc__,audit_passed=True,evidence=ids,verified_bindings=sum(v['bindings_verified']for v in ids.values()),
        actual_generation_seconds=hls['elapsed_seconds'],HLS_top=hls['HLS_top'],actual_port_widths=ports,
        actual_domain_definition_counts=domains,actual_generated_RTL_and_data_files=len(hls['generated_sha256']),resources=hls['resources'],
        target_clock_ns=4,default_uncertainty_ns=1.08,effective_ns=2.92,estimated_ns=estimate,
        original_timing_met=hls['original_effective_period_met'],actual_CPP_modes=140,all105_previous_modes_retained=True,
        source_sha256={str(Path(__file__).relative_to(ROOT)):digest(__file__),str(top.relative_to(ROOT)):digest(top)},protected_raw_sha256=binding.PROTECTED,
        abort_is_QP_or_global_drain=False,native_error_quarantine_cancel_STOP_CQ_integrated=False,permission_to_unpin=False,
        privileged_native_MAC_fence_management_inputs_modeled=True,live_Linux_or_physical=False,full_board_timing=False,overall_goal_complete=False,
        remaining=['Integrate actual authenticated fatal-QP admission/quarantine, real backend/MAC ownership, selected HLS abort and native message cancel/STOP/error CQ plus retained lifetime refs.',
            'Fresh complete native graph of all38 old cases plus real fatal-QP scenarios; HLS140/generation alone cannot establish native/global drain or safe unpin.',
            'All11/full1MiB native/multiSGE/live registered refs/real-peer recovery/congestion/original timing/physical remain.'],
        hardware_or_default_actions=[],commit_or_push=False)
    with a.report.open('x')as f:f.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(audit_passed=True,verified_bindings=result['verified_bindings'],actual_generated=True,
        original_timing_met=result['original_timing_met'],native_or_global_drain=False)),flush=True)


if __name__=='__main__':main()
