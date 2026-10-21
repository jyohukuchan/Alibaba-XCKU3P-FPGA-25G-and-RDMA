#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Exact original native40 bench/recipes/raw/oracles on qualified scheduled core.

The first native40 compiler timeout remains a failure. This preflight is not
a fresh binary, native packet runtime, timing, error-CQ or drain proof.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import audit_segmented_receive as binding
import audit_segmented_write_rnr_native_sources as recipes
from audit_write_fatal_native_fixture import rendered_inputs
import probe_write_fatal_native_full as original_runner
import probe_write_abort_scheduled_native_full as runner
import write_abort_scheduled_native_sources as selection
import write_fatal_native_fixture as fixture

ROOT=binding.ROOT;digest=binding.digest


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve earlier evidence')
    names=['write-abort-scheduled-native-elaboration-001','write-abort-scheduled-generated-diagnostics-001',
        'write-abort-scheduled-diagnostics-001','write-fatal-native-fixture-diagnostics-001',
        'write-fatal-native-full-001','write-psn-control-native-full-001','write-psn-control-native-runtime-diagnostics-001']
    records={};ids={}
    for n in names:records[n],ids[n]=binding.bindings(n)
    elab,generated,consumer,prior,failed,old,runtime=[records[n]for n in names]
    if not all(r.get('pass_test',r.get('audit_passed'))for r in [elab,generated,consumer,prior,old,runtime])or \
       failed['pass_test']or failed['error_type']!='TimeoutExpired'or failed['tests']:
        raise ValueError('actual scheduled core/audits/qualified prior fixture/old38 and unchanged timeout required')
    selection.sources(selection.ELABORATION,None)
    current=runner.runner_source();original=original_runner.runner_source()
    before=recipes.cases(original);after=recipes.cases(current)
    if len(after)!=40 or before!=after:raise ValueError('EVERY original40 recipe/order/flag/opcode/zero/capacity must remain exact')
    bench=fixture.bench();benchsha=hashlib.sha256(bench.encode()).hexdigest()
    failed_bench=ROOT/failed['directory']/'tb.v'
    if benchsha!=prior['exact_new_bench_sha256']or digest(failed_bench)!=benchsha:
        raise ValueError('EXACT original entire native40 bench including every391+28 check/stall/wire/host oracle required')
    fatal=set(re.findall(r'\$fatal\([^,]+,"([^"]+)',bench))
    if len(fatal)!=419 or prior['original_fatal_messages_retained']!=391 or prior['new_fatal_messages']!=28:
        raise ValueError('all original391+28 independent fatal assertions required')
    inputs={}
    for case in after:
        original_inputs=rendered_inputs(original,case);current_inputs=rendered_inputs(current,case)
        if current_inputs!=original_inputs:raise ValueError('an authored raw input byte changed:'+case[0])
        hashes={n:hashlib.sha256(t.encode()).hexdigest()for n,t in current_inputs.items()};inputs[case[0]]=hashes
        if case[0]in old['tests']and hashes!=old['tests'][case[0]]['runtime_input_sha256']:
            raise ValueError('original actual native38 raw inputs changed:'+case[0])
    if set(inputs)!=set(old['tests'])|{'LARGE_RX_WRITE_FATAL_ACCESS','LARGE_RX_WRITE_FATAL_PARTIAL'}:
        raise ValueError('all38 actual old cases plus genuine fatal62/partial61 required')
    for name in ['LARGE_RX_WRITE_FATAL_ACCESS','LARGE_RX_WRITE_FATAL_PARTIAL']:
        expected=dict(old['tests']['LARGE_RX_WRITE_IMM']['runtime_input_sha256'])
        expected['write-fatal-input.hex']=prior['new_fatal_inputs'][name]['input_sha256']
        if inputs[name]!=expected:raise ValueError('same genuine positive frames/coherent RQ plus exact independent fatal input required')
    for token in ["if shutil.disk_usage(ROOT).free<1024**3:","if shutil.disk_usage('/dev/shm').free<4*1024**3:",
        'simulation_limit_seconds=30,compile_limit_seconds=1200','timeout=180',"'-j','4'",'--output-split-cfuncs',
        '500000',"'-CFLAGS','-O1'","preflight['exact_new_runner_sha256']","preflight['exact_new_bench_sha256']"]:
        if token not in current:raise ValueError('original deadline/resource/geometry/optimization/exact-input gate missing:'+token)
    for n,h in binding.PROTECTED.items():
        if digest(ROOT/n)!=h:raise ValueError('original protected raw source changed:'+n)
    sources=[Path(__file__).resolve(),Path(runner.__file__).resolve(),Path(selection.__file__).resolve(),Path(fixture.__file__).resolve()]
    oldrun=ROOT/old['directory']
    result=dict(scope=__doc__,audit_passed=True,evidence=ids,verified_bindings=sum(v['bindings_verified']for v in ids.values()),
        planned_native_cases=40,all38_case_recipes_and_raw_inputs_identical=True,all40_original_recipes_and_raw_bytes_identical=True,
        entire_original_native40_bench_identical=True,original_fatal_messages_retained=391,new_fatal_messages=28,
        old38_input_sha256={str((oldrun/(name+'-'+n)).relative_to(ROOT)):h for name,t in old['tests'].items()for n,h in t['runtime_input_sha256'].items()},
        all40_authored_runtime_inputs=inputs,new_fatal_inputs=prior['new_fatal_inputs'],
        exact_new_bench_sha256=benchsha,exact_new_runner_sha256=hashlib.sha256(current.encode()).hexdigest(),
        source_sha256={str(q.relative_to(ROOT)):digest(q)for q in sources},protected_raw_sha256=binding.PROTECTED,
        actual_scheduled_generated_files=generated['actual_generated_RTL_and_data_files'],
        original_timeout_unchanged=True,compile_limit_seconds=1200,runtime_limit_seconds=30,elaboration_limit_seconds=180,
        root_guard_bytes=1024**3,RAM_guard_bytes=4*1024**3,FPGA_clock_ns=4,
        actual_new_native_runtime=False,hardware_verified=False,full_board_timing=False,overall_goal_complete=False,
        remaining=['Fresh actual same scheduled-core binary/all40 runtime and every old38 outcome plus genuine fatal wire/backend/HLS/cancel/RQ/quarantine proofs.',
            'Original all11/fatal63/error CQ/STOP/lifetime/full1MiB/multiSGE/live refs/real-peer recovery/congestion/original timing/physical remain.'],
        hardware_or_default_actions=[],commit_or_push=False)
    with a.report.open('x')as f:f.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(audit_passed=True,verified_bindings=result['verified_bindings'],exact_old_cases=38,planned_cases=40,native_runtime=False)))


if __name__=='__main__':main()
