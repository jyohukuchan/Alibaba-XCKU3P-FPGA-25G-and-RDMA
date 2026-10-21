#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual scheduled-abort HLS cohort/ALL old ports/domains/size, not native.

Require real140 C++ modes, unchanged owned services and original generation
gates. A smaller representation is not timing, native runtime or drain proof.
"""
import argparse
import json
from pathlib import Path
import re
import audit_segmented_receive as binding

ROOT=binding.ROOT;digest=binding.digest
SOURCE=ROOT/'rdma/rnic/build/native-write-abort-scheduled-transport-001'


def ports(text):
    found=re.findall(r'^\s*(input|output)\s+(?:(?:wire|reg)\s+)?(?:\[\s*(\d+)\s*:\s*(\d+)\s*\]\s*)?(\w+)\s*;',text,re.M)
    declarations=len(re.findall(r'^\s*(?:input|output)\s+',text,re.M))
    if len(found)!=declarations or not found:raise ValueError('every actual HLS port declaration must be understood')
    out={}
    for direction,hi,lo,name in found:
        if name in out or lo and int(lo)!=0:raise ValueError('unique zero-based actual HLS port required:'+name)
        out[name]=(direction,int(hi)+1 if hi else 1)
    return out


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--report',type=Path,required=True)
    p.add_argument('--hls-record',default='write-abort-scheduled-generated-hls-001');a=p.parse_args()
    if a.report.exists():p.error('preserve earlier evidence')
    if not re.fullmatch(r'write-abort-scheduled-generated-hls-\d{3}',a.hls_record):p.error('actual scheduled HLS record required')
    names=[a.hls_record,'write-abort-scheduled-hls-001','write-abort-scheduled-compat-001',
        'write-abort-scheduled-diagnostics-001','write-abort-generated-hls-001','write-abort-generated-diagnostics-001']
    records={};ids={}
    for n in names:records[n],ids[n]=binding.bindings(n)
    hls,cpp,compat,audit,old,old_audit=[records[n]for n in names]
    if not all(r['pass_test']for r in [hls,cpp,compat,old])or not audit['audit_passed']or not old_audit['audit_passed']or \
       not all(hls.get(k)for k in ['source_and_frozen_inputs_unchanged','wrapper_and_builder_unchanged',
           'all140_CPP_modes_required','write_abort_owner960_and_receipt992_verified']):
        raise ValueError('actual completed HLS/same frozen source/full140/real services/audits required')
    if len(cpp['tests'])!=140 or audit['all140_original_summary_and_oracle_fields_identical']!=160 or hls['abort_is_QP_or_global_drain']:
        raise ValueError('every140 old mode/outcome/oracle and distinct non-global abort contract required')
    if hls['HLS_top']!='rocev2_native_write_abort_top'or \
       (float(hls['target_clock_period']),float(hls['clock_uncertainty']),hls['MAX_QPS'],hls['metadata_entries'])!=(4,1.08,8,2000)or \
       hls['elapsed_seconds']>7200 or hls['free_bytes_at_start']<1572864000 or hls['exit_code']:
        raise ValueError('unchanged original HLS top/7200s/1500MiB/4ns/default1.08ns/8QP/2000 gates required')
    run=ROOT/hls['directory'];generated=run/'project/solution1/syn/verilog'
    oldgen=ROOT/old['directory']/'project/solution1/syn/verilog'
    top=generated/(hls['HLS_top']+'.v');oldtop=oldgen/(old['HLS_top']+'.v')
    observed=ports(top.read_text());prior=ports(oldtop.read_text())
    if observed!=prior:raise ValueError('EVERY original actual abort HLS port/direction/width must remain identical')
    required={'s_axis_write_abort_owner_TDATA':('input',960),'m_axis_write_abort_done_TDATA':('output',992),
        's_axis_control_owner_TDATA':('input',480),'m_axis_control_done_TDATA':('output',512),
        's_axis_write_owner_TDATA':('input',424),'m_axis_write_done_TDATA':('output',456),
        'm_axis_recv_message_TDATA':('output',776),'regWriteAbortFault':('output',1)}
    if any(observed.get(n)!=v for n,v in required.items()):raise ValueError('actual complete typed owner/receipt/fault ports required')
    functions=['as02_native_control_merger_0_s','rx_exh_fsm_512_0_s','as02_write_packet_retire_join_0_s',
        'generate_exh_512_0_s','msn_table_0_s','state_table_0_s']
    domains={n:[f for f in hls['generated_sha256']if f.endswith('_'+n+'.v')]for n in functions}
    if any(len(v)!=1 for v in domains.values()):raise ValueError('ONE actual parser/checkpoint/control/ACK/MSN/state domain required')
    definitions=[]
    for name in hls['generated_sha256']:
        if name.endswith('.v'):definitions+=re.findall(r'^\s*module\s+(\w+)\s*(?:#\s*\(|\()', (generated/name).read_text(),re.M)
    if len(definitions)!=len(set(definitions))or definitions.count(hls['HLS_top'])!=1:
        raise ValueError('sole actual top and unique definitions across the ENTIRE new cohort required')
    cpp_path='hls/ib_transport_protocol/ib_transport_protocol.cpp'
    frozen=run/'inputs/fns'/cpp_path
    if digest(frozen)!=digest(SOURCE/'fns'/cpp_path):
        raise ValueError('actual HLS must consume EXACT same scheduled parser validated by140 C++ cases')
    estimate=float(hls['estimated_clock_period'])
    if hls['original_effective_period_met']!=(estimate<=2.92):raise ValueError('original effective2.92ns timing verdict must remain factual')
    total=sum((generated/n).stat().st_size for n in hls['generated_sha256'])
    oldtotal=sum((oldgen/n).stat().st_size for n in old['generated_sha256'])
    parser=generated/domains['rx_exh_fsm_512_0_s'][0]
    oldparser=next(oldgen/n for n in old['generated_sha256']if n.endswith('_rx_exh_fsm_512_0_s.v'))
    for n,h in binding.PROTECTED.items():
        if digest(ROOT/n)!=h:raise ValueError('original protected raw source changed:'+n)
    inputs=[Path(__file__).resolve(),top,oldtop,frozen,SOURCE/'source.json']
    result=dict(scope=__doc__,audit_passed=True,evidence=ids,verified_bindings=sum(v['bindings_verified']for v in ids.values()),
        HLS_top=hls['HLS_top'],actual_generation_seconds=hls['elapsed_seconds'],
        actual_all_port_contracts=observed,all_original_port_contracts_identical=True,
        actual_domain_definition_counts={n:len(v)for n,v in domains.items()},actual_unique_module_definitions=len(definitions),
        actual_generated_RTL_and_data_files=len(hls['generated_sha256']),actual_same_tested_scheduled_parser=True,
        actual_CPP_modes=140,all140_old_outcome_oracle_fields_identical=160,resources=hls['resources'],
        original_total_RTL_data_bytes=oldtotal,new_total_RTL_data_bytes=total,
        original_parser_RTL_bytes=oldparser.stat().st_size,new_parser_RTL_bytes=parser.stat().st_size,
        actual_total_representation_reduced=total<oldtotal,actual_parser_representation_reduced=parser.stat().st_size<oldparser.stat().st_size,
        target_clock_ns=4,default_uncertainty_ns=1.08,effective_ns=2.92,estimated_ns=estimate,
        original_timing_met=hls['original_effective_period_met'],
        source_sha256={str(q.relative_to(ROOT)):digest(q)for q in inputs},protected_raw_sha256=binding.PROTECTED,
        new_native_runtime=False,new_native_compile_under1200s_proven=False,QP_global_drain_or_unpin=False,
        live_Linux_or_physical=False,full_board_timing=False,overall_goal_complete=False,
        hardware_or_default_actions=[],commit_or_push=False,
        remaining=['Fresh actual complete native graph/new binary under original gates, every old38 outcome plus two genuine fatal scenarios; generation/size audit is not native runtime.',
            'All original11/fatal63/error CQ/full QP STOP/reference lifetimes/recovery/real-peer/original timing/physical requirements remain.'])
    with a.report.open('x')as f:f.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(audit_passed=True,verified_bindings=result['verified_bindings'],actual_generated_files=len(hls['generated_sha256']),
        RTL_bytes=total,parser_RTL_bytes=parser.stat().st_size,original_timing_met=result['original_timing_met'],native_runtime=False)))


if __name__=='__main__':main()
