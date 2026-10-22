#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Exact prior fixed-MAC40 bench/419 checks/raw inputs on new event-status DUT.

No test-only changes. Require actual new HLS/native source qualification;
preflight is not execution success or timing/QP/global drain/unpin proof.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import audit_segmented_receive as binding
import audit_segmented_write_rnr_native_sources as recipes
from audit_write_fatal_native_fixture import rendered_inputs
import probe_write_abort_scheduled_mac_native_full as previous_runner
import probe_write_abort_event_native_full as runner
import write_abort_scheduled_mac_native_fixture as fixture
import write_abort_event_native_sources as selection

ROOT=binding.ROOT;digest=binding.digest


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve all prior evidence')
    names=['write-abort-event-native-elaboration-001','write-abort-event-generated-diagnostics-001',
        'write-abort-event-diagnostics-001','write-abort-scheduled-mac-native-fixture-diagnostics-001',
        'write-abort-scheduled-mac-native-full-001','write-psn-control-native-full-001',
        'write-psn-control-native-runtime-diagnostics-001']
    records={};ids={}
    for n in names:records[n],ids[n]=binding.bindings(n)
    elab,generated,consumer,preflight,failed,old,runtime=[records[n]for n in names]
    if not all(r.get('pass_test',r.get('audit_passed'))for r in [elab,generated,consumer,preflight,old,runtime])or \
       not elab['event_status_metadata_engine_inserted']or not generated['actual_metadata_engine_scalar_status_barrier_removed']:
        raise ValueError('actual entire new source/cohort/elaboration and prior full proof required')
    if failed['pass_test']or failed['compile_exit']or failed['compilation_seconds']>1200 or len(failed['tests'])!=9 or \
       failed['tests']['LARGE_SEND_IMM']['exit']!=-6:
        raise ValueError('actual previous failed SEND regression must remain a failure')
    selection.sources(selection.ELABORATION,None)
    bench=fixture.bench();original=(ROOT/failed['directory']/'tb.v').read_text()
    bh=hashlib.sha256(bench.encode()).hexdigest()
    if bench!=original or bh!=preflight['exact_new_bench_sha256']or 'force 'in bench:
        raise ValueError('ENTIRE actually tested previous bench must stay byte-identical')
    if len(set(re.findall(r'\$fatal\([^,]+,"([^"]+)',bench)))!=419:
        raise ValueError('all419 original independent assertions required')
    before=previous_runner.runner_source();current=runner.runner_source()
    oldcases=recipes.cases(before);newcases=recipes.cases(current)
    if len(newcases)!=40 or newcases!=oldcases:raise ValueError('same all40 original recipes/order/flags required')
    raw={}
    for case in newcases:
        content=rendered_inputs(current,case)
        if content!=rendered_inputs(before,case):raise ValueError('original raw input changed:'+case[0])
        raw[case[0]]={n:hashlib.sha256(t.encode()).hexdigest()for n,t in content.items()}
        if raw[case[0]]!=preflight['all40_authored_runtime_inputs'][case[0]]:
            raise ValueError('actual previous preflight input bytes changed:'+case[0])
        for prior in [old,failed]:
            if case[0]in prior['tests']and raw[case[0]]!=prior['tests'][case[0]]['runtime_input_sha256']:
                raise ValueError('actual old execution input differs:'+case[0])
    for token in ["if shutil.disk_usage(ROOT).free<1024**3:","if shutil.disk_usage('/dev/shm').free<4*1024**3:",
        'simulation_limit_seconds=30,compile_limit_seconds=1200','timeout=180',"'-j','4'",'--output-split-cfuncs','500000',"'-CFLAGS','-O1'",
        "preflight['exact_new_runner_sha256']","preflight['exact_new_bench_sha256']"]:
        if token not in current:raise ValueError('original gate/compile geometry missing:'+token)
    for n,h in binding.PROTECTED.items():
        if digest(ROOT/n)!=h:raise ValueError('original protected raw source changed:'+n)
    inputs=[Path(__file__).resolve(),Path(runner.__file__).resolve(),Path(selection.__file__).resolve(),Path(fixture.__file__).resolve(),Path(previous_runner.__file__).resolve()]
    result=dict(scope=__doc__,audit_passed=True,evidence=ids,verified_bindings=sum(v['bindings_verified']for v in ids.values()),
        planned_native_cases=40,all38_case_recipes_and_raw_inputs_identical=True,all40_original_recipes_and_raw_bytes_identical=True,
        original_fatal_messages_retained=391,new_fatal_messages=28,new_fatal_inputs=preflight['new_fatal_inputs'],
        entire_previous_fixed_MAC_native40_bench_identical=True,all419_fatal_messages_unchanged=True,
        actual_previous_SEND_failure_preserved=True,original_partial1100_and_local_selected71_stalls_unchanged=True,
        all40_authored_runtime_inputs=raw,exact_new_bench_sha256=bh,
        exact_new_runner_sha256=hashlib.sha256(current.encode()).hexdigest(),
        source_sha256={str(q.relative_to(ROOT)):digest(q)for q in inputs},protected_raw_sha256=binding.PROTECTED,
        compile_limit_seconds=1200,runtime_limit_seconds=30,elaboration_limit_seconds=180,FPGA_clock_ns=4,
        root_guard_bytes=1024**3,RAM_guard_bytes=4*1024**3,actual_new_native_runtime=False,
        hardware_verified=False,full_board_timing=False,overall_goal_complete=False,hardware_or_default_actions=[],commit_or_push=False)
    with a.report.open('x')as f:f.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(audit_passed=True,verified_bindings=result['verified_bindings'],all419_checks=True,planned_cases=40,new_runtime=False)))


if __name__=='__main__':main()
