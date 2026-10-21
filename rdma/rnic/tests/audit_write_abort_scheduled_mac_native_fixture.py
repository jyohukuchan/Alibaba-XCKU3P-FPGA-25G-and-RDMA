#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Exact native40 inputs/checks with corrected access MAC hold/test actor.

Only test-control scheduling and the access-only hold bug change. The DUT,
all419 assertions, partial1100/local71/selected71 stalls and gates remain.
An actor-finished bit is NOT a hardware completion/drain certificate.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import audit_segmented_receive as binding
import audit_segmented_write_rnr_native_sources as recipes
from audit_write_fatal_native_fixture import rendered_inputs
import probe_write_abort_scheduled_native_full as oldrunner
import probe_write_abort_scheduled_mac_native_full as runner
import write_abort_scheduled_mac_native_fixture as fixture
import write_abort_scheduled_native_sources as selection

ROOT=binding.ROOT;digest=binding.digest
PREIMAGE={'rdma/rnic/tests/probe_write_abort_scheduled_partial_diagnostic.py':
    'rdma/rnic/build/write-abort-partial-diagnostic-001-preimages-upXOYXUM'}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve earlier evidence')
    names=['write-abort-scheduled-native-elaboration-001','write-abort-scheduled-generated-diagnostics-001',
        'write-abort-scheduled-native-fixture-diagnostics-001','write-abort-scheduled-native-full-001',
        'write-abort-scheduled-native-partial-diagnostic-001','write-abort-scheduled-native-partial-diagnostic-002',
        'write-psn-control-native-full-001','write-psn-control-native-runtime-diagnostics-001']
    records={};ids={}
    for n in names:records[n],ids[n]=binding.bindings(n,PREIMAGE if n==names[4]else None)
    elab,generated,prior,failed,wrong,partial,old,runtime=[records[n]for n in names]
    if not all(r.get('pass_test',r.get('audit_passed'))for r in [elab,generated,prior,partial,old,runtime])or \
       failed['pass_test']or failed['compile_exit']or failed['compilation_seconds']>1200 or \
       set(failed['tests'])!={'LARGE_RX_WRITE_FATAL_ACCESS'}or failed['tests']['LARGE_RX_WRITE_FATAL_ACCESS']['exit']==0:
        raise ValueError('actual unchanged scheduled core/first-case failure and qualified partial diagnostic required')
    if wrong['pass_test']or wrong['exit']or wrong['error']!='one actual FIRST logical data command/nonce required':
        raise ValueError('original diagnostic post-parser counter-oracle failure must remain a failure')
    nonce=dict(admitted=1,issued=1,backend_completed=1,logical_completed=1,translated=0,active=0,fault=0)
    if partial['actual_common_nonce_backend']!=nonce or partial['original_binary_sha256']!=failed['binary_sha256']or \
       partial['actual_native40_regression_completed']or not partial['same_original_DUT_bench_binary']:
        raise ValueError('same original diagnostic binary/real partial proofs, NOT a fixed-bench/full40 pass required')
    selection.sources(selection.ELABORATION,None)
    original=fixture.parent.bench();actual=(ROOT/failed['directory']/'tb.v').read_text()
    if original!=actual or hashlib.sha256(original.encode()).hexdigest()!=prior['exact_new_bench_sha256']:
        raise ValueError('exact original failed bench required before narrowly defined changes')
    changes=[('reg runtime_write_fatal=0,wrfatal_partial=0;',
        'reg runtime_write_fatal=0,wrfatal_partial=0;\n'+fixture.ACTOR),
        ('reject_ready=0;m_write_fatal_selected_ready=0;lrx_hold_final_MAC=1;',
         'reject_ready=0;m_write_fatal_selected_ready=0;lrx_hold_final_MAC=wrfatal_partial;'),
        ('requester_wire_mode=1;if(runtime_write_fatal)run_write_fatal_native();else run_large_write_native();',
         "requester_wire_mode=1;if(runtime_write_fatal)begin wrfatal_start=1;wait(wrfatal_finished===1'b1);end else run_large_write_native();")]
    expected=original
    for a0,b0 in changes:
        if expected.count(a0)!=1:raise ValueError('exact one original test-control site required')
        expected=expected.replace(a0,b0)
    bench=fixture.bench()
    if bench!=expected or 'force 'in bench:raise ValueError('only the explicit test-control changes, never a DUT/proof injection, are permitted')
    fatal=lambda s:set(re.findall(r'\$fatal\([^,]+,"([^"]+)',s))
    if fatal(bench)!=fatal(original)or len(fatal(bench))!=419 or bench.count('repeat(1100)')!=original.count('repeat(1100)')or \
       bench.count('repeat(71)')!=original.count('repeat(71)'):
        raise ValueError('all419 original fatal checks and every real proof/local/selected stall must remain')
    log=(ROOT/failed['directory']/'LARGE_RX_WRITE_FATAL_ACCESS.log').read_text()
    for marker in ['FATAL_NATIVE_OWNER ','FATAL_NATIVE_HLS ','ACTUAL_MAC_SFD 6001 ','ACTUAL_BOARD_WIRE_EOF 1',
        'FATAL real NAK/HLS abort/local reject deadline fc00 ctl00 abort00']:
        if marker not in log:raise ValueError('actual held-NAK timeout evidence missing:'+marker)
    if any(marker in log for marker in ['FATAL_NATIVE_MAC ','FATAL_NATIVE_ABORT_DONE ','FATAL_NATIVE_SELECTED ']):
        raise ValueError('the original held NAK must not be relabeled as a completed MAC/abort')
    if 'if(expected_nonce_command[15:0]!=expected_nonce_physical)nonce_translated=nonce_translated+1;'not in bench:
        raise ValueError('counter source definition must remain tag rewriting, NOT PTE/address translation')
    for fn in ['fatal_input','large_write_variant','verify_fatal','verify_nonce','verify_large_write_psn','verify_large_write_rnr',
        'verify_large_write','verify_large_receive','verify_large','verify_large_read','verify_large_immediate','verify_rq','verify_atomic','verify_zero']:
        if getattr(fixture,fn)is not getattr(fixture.parent,fn):raise ValueError('an original input/oracle function changed:'+fn)
    previous=oldrunner.runner_source();current=runner.runner_source();before=recipes.cases(previous);after=recipes.cases(current)
    if len(after)!=40 or before!=after:raise ValueError('all40 original exact recipes/order/flags/opcodes/capacities required')
    allinputs={}
    for case in after:
        content=rendered_inputs(current,case)
        if content!=rendered_inputs(previous,case):raise ValueError('raw bytes changed:'+case[0])
        hashes={n:hashlib.sha256(t.encode()).hexdigest()for n,t in content.items()};allinputs[case[0]]=hashes
        if hashes!=prior['all40_authored_runtime_inputs'][case[0]]:raise ValueError('original qualified input hashes changed:'+case[0])
        if case[0]in old['tests']and hashes!=old['tests'][case[0]]['runtime_input_sha256']:
            raise ValueError('actual old38 raw inputs changed:'+case[0])
    for token in ["if shutil.disk_usage(ROOT).free<1024**3:","if shutil.disk_usage('/dev/shm').free<4*1024**3:",
        'simulation_limit_seconds=30,compile_limit_seconds=1200','timeout=180',"'-j','4'",'--output-split-cfuncs','500000',"'-CFLAGS','-O1'",
        "preflight['exact_new_runner_sha256']","preflight['exact_new_bench_sha256']"]:
        if token not in current:raise ValueError('original deadline/resource/optimization/geometry/exact-input gate missing:'+token)
    for n,h in binding.PROTECTED.items():
        if digest(ROOT/n)!=h:raise ValueError('original protected raw source changed:'+n)
    inputs=[Path(__file__).resolve(),Path(runner.__file__).resolve(),Path(fixture.__file__).resolve(),Path(selection.__file__).resolve()]
    oldrun=ROOT/old['directory']
    result=dict(scope=__doc__,audit_passed=True,evidence=ids,verified_bindings=sum(v['bindings_verified']for v in ids.values()),
        planned_native_cases=40,all38_case_recipes_and_raw_inputs_identical=True,all40_original_recipes_and_raw_bytes_identical=True,
        original_fatal_messages_retained=391,new_fatal_messages=28,all419_fatal_messages_unchanged=True,
        original_native40_bench_identical=False,only_case_specific_MAC_hold_and_test_actor_changed=True,
        actual_native_DUT_source_changed=False,real_partial1100_and_all71_stalls_unchanged=True,actor_finished_is_DUT_proof=False,
        original_access_held_NAK_failure_preserved=True,diagnostic_counter_failure_preserved=True,
        counter_definition='translated counts logical-tag != physical nonce, not address/PTE translation; FIRST tag1==nonce1 gives0.',
        same_original_binary_partial_diagnostic_passed=True,new_fixed_bench_runtime_qualified=False,
        all40_authored_runtime_inputs=allinputs,new_fatal_inputs=prior['new_fatal_inputs'],
        old38_input_sha256={str((oldrun/(name+'-'+n)).relative_to(ROOT)):h for name,t in old['tests'].items()for n,h in t['runtime_input_sha256'].items()},
        exact_new_bench_sha256=hashlib.sha256(bench.encode()).hexdigest(),exact_new_runner_sha256=hashlib.sha256(current.encode()).hexdigest(),
        source_sha256={str(q.relative_to(ROOT)):digest(q)for q in inputs},protected_raw_sha256=binding.PROTECTED,
        compile_limit_seconds=1200,runtime_limit_seconds=30,elaboration_limit_seconds=180,FPGA_clock_ns=4,
        root_guard_bytes=1024**3,RAM_guard_bytes=4*1024**3,actual_new_native_runtime=False,
        hardware_verified=False,full_board_timing=False,overall_goal_complete=False,hardware_or_default_actions=[],commit_or_push=False,
        remaining=['Fresh actual fixed-bench binary and all40 runtime; old38 entire outcomes plus real fatal access/partial wire/abort/cancel/RQ/quarantine proofs.',
            'All original11/fatal63/error CQ/STOP/lifetimes/recovery/original timing/physical remain.'])
    with a.report.open('x')as f:f.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(audit_passed=True,verified_bindings=result['verified_bindings'],all419_checks=True,planned_cases=40,new_runtime=False)))


if __name__=='__main__':main()
