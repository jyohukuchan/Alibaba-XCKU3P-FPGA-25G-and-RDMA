#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Exact old40 inputs/419 checks plus actual FEC AXI/ACK/quarantine extension.

Preflight only, not packet execution/Linux/STOP/drain/unpin/timing proof.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import audit_segmented_receive as binding
import audit_segmented_write_rnr_native_sources as recipes
from audit_write_fatal_native_fixture import rendered_inputs
import probe_write_abort_event_native_full as previous_runner
import probe_fatal_event_native_full as runner
import fatal_event_native_fixture as fixture
import fatal_event_native_sources as selection

ROOT=binding.ROOT;digest=binding.digest


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve earlier evidence')
    names=['fatal-event-native-elaboration-002','fatal-event-native-source-diagnostics-002',
        'write-abort-event-native-full-001','write-abort-event-native-runtime-diagnostics-001',
        'write-abort-event-native-fixture-diagnostics-001']
    records={};ids={}
    for n in names:records[n],ids[n]=binding.bindings(n)
    elab,source,old,runtime,prior=[records[n]for n in names]
    if not all(r.get('pass_test',r.get('audit_passed'))for r in records.values())or len(old['tests'])!=40:
        raise ValueError('actual old40 and separately reviewed FEC graph002 required')
    selection.sources(selection.ELABORATION,None)
    before=fixture.parent.bench();bench=fixture.bench();run=ROOT/old['directory']
    if (run/'tb.v').read_text()!=before:raise ValueError('exact actually executed old40 bench required')
    restored=bench.replace('module tb;\n'+fixture.DECLARATIONS,'module tb;',1)
    restored=restored.replace('  fec_read_and_ack;\n','',1).replace('  fec_finish;\n','',1)
    if restored!=before or 'force 'in bench:raise ValueError('extension must be additive only; no old bench/input/authority injection')
    fatal=lambda s:set(re.findall(r'\$fatal\([^,]+,"([^"]+)',s))
    if len(fatal(before))!=419 or fatal(before)-fatal(bench):raise ValueError('all419 original independent assertions required')
    previous=previous_runner.runner_source();current=runner.runner_source()
    oldcases=recipes.cases(previous);cases=recipes.cases(current)
    if cases!=oldcases or len(cases)!=40:raise ValueError('all40 exact original recipes/order/flags required')
    raw={}
    for case in cases:
        content=rendered_inputs(current,case)
        if content!=rendered_inputs(previous,case):raise ValueError('original raw input changed:'+case[0])
        raw[case[0]]={n:hashlib.sha256(t.encode()).hexdigest()for n,t in content.items()}
        if raw[case[0]]!=old['tests'][case[0]]['runtime_input_sha256']:raise ValueError('actual old execution input changed:'+case[0])
    for fn in ['fatal_input','future_input','verify_large_write_psn','verify_large_write_rnr','verify_large_write',
        'verify_large_receive','verify_large','verify_large_read','verify_large_immediate','verify_rq','verify_atomic','verify_zero','verify_nonce']:
        if getattr(fixture,fn)is not getattr(fixture.parent,fn):raise ValueError('old independent generator/oracle changed:'+fn)
    for token in ["if shutil.disk_usage(ROOT).free<1024**3:","if shutil.disk_usage('/dev/shm').free<4*1024**3:",
        'simulation_limit_seconds=30,compile_limit_seconds=1200','timeout=180',"'-j','4'",'--output-split-cfuncs','500000',"'-CFLAGS','-O1'",
        "preflight['exact_new_runner_sha256']","preflight['exact_new_bench_sha256']"]:
        if token not in current:raise ValueError('original compile/runtime/resource/preflight gate missing:'+token)
    for token in ['repeat(77)','read_reg(24\'h406040+4*i,value)','write_reg(24\'h406010,1,15,7,2)',
        'write_reg(24\'h406010,1,15,2,7)','dut.native.queue_control.wire_queue_guard[2]',
        'dut.native.independent_receive_frontend.receive_queue_control.wire_queue_guard[2]']:
        if token not in bench:raise ValueError('new actual FEC wire/readback/ACK/retained guard check missing:'+token)
    for n,h in binding.PROTECTED.items():
        if digest(ROOT/n)!=h:raise ValueError('original protected raw source changed:'+n)
    inputs=[Path(__file__).resolve(),Path(runner.__file__).resolve(),Path(selection.__file__).resolve(),
        Path(fixture.__file__).resolve(),Path(previous_runner.__file__).resolve()]
    r=dict(scope=__doc__,audit_passed=True,evidence=ids,verified_bindings=sum(v['bindings_verified']for v in ids.values()),
        planned_native_cases=40,all38_case_recipes_and_raw_inputs_identical=True,all40_original_recipes_and_raw_bytes_identical=True,
        all419_original_assertions_retained=True,entire_old_bench_restored_by_removing_only_additions=True,
        original_fatal_messages_retained=419,new_fatal_messages=len(fatal(bench)-fatal(before)),
        new_fatal_inputs=prior['new_fatal_inputs'],all40_authored_runtime_inputs=raw,
        original_partial1100_and_local_selected71_stalls_unchanged=True,new_observer_stall_after_host_ACK=77,
        exact_new_bench_sha256=hashlib.sha256(bench.encode()).hexdigest(),exact_new_runner_sha256=hashlib.sha256(current.encode()).hexdigest(),
        source_sha256={str(q.relative_to(ROOT)):digest(q)for q in inputs},protected_raw_sha256=binding.PROTECTED,
        compile_limit_seconds=1200,runtime_limit_seconds=30,elaboration_limit_seconds=180,FPGA_clock_ns=4,
        root_guard_bytes=1024**3,RAM_guard_bytes=4*1024**3,actual_new_native_runtime=False,
        hardware_verified=False,full_board_timing=False,overall_goal_complete=False,hardware_or_default_actions=[],commit_or_push=False)
    with a.report.open('x')as f:f.write(json.dumps(r,indent=2)+'\n')
    print(json.dumps(dict(audit_passed=True,verified_bindings=r['verified_bindings'],original_checks=419,new_checks=r['new_fatal_messages'],planned_cases=40,native_runtime=False)))


if __name__=='__main__':main()
