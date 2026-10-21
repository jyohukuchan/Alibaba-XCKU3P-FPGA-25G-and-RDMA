#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""One unchanged partial-fatal case on the actual failed40 run's binary.

Diagnostic only: isolated new files, exact qualified inputs, original30s,
same binary/DUT/bench. NOT a fresh fixed-bench native40 regression pass.
"""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import audit_segmented_receive as binding
import write_fatal_native_fixture as fixture
import probe_immediate_native_request as tool

ROOT=binding.ROOT;digest=binding.digest


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve prior evidence')
    native,nid=binding.bindings('write-abort-scheduled-native-full-001')
    preflight,pid=binding.bindings('write-abort-scheduled-native-fixture-diagnostics-001')
    if native['pass_test']or native['compile_exit']or native['compilation_seconds']>1200 or \
       set(native['tests'])!={'LARGE_RX_WRITE_FATAL_ACCESS'}or native['tests']['LARGE_RX_WRITE_FATAL_ACCESS']['exit']==0 or \
       not preflight['audit_passed']or not preflight['entire_original_native40_bench_identical']:
        raise ValueError('actual completed compiler/first-case failure/exact original qualified fixture required')
    original=ROOT/native['directory'];binary=Path(native['frozen_binary_path'])
    if digest(binary)!=native['binary_sha256']:raise ValueError('exact actual compiled diagnostic binary required')
    run=Path(tempfile.mkdtemp(prefix='write-abort-partial-diagnostic-',dir=ROOT/'rdma/rnic/build'))
    expected=preflight['all40_authored_runtime_inputs']['LARGE_RX_WRITE_FATAL_PARTIAL']
    for n in ['input.hex','records.hex','large-write-receive-input.hex','receive-records.hex']:
        shutil.copy2(original/('LARGE_RX_WRITE_FATAL_ACCESS-'+n),run/n)
    (run/'write-fatal-input.hex').write_text(''.join(f'{w:037x}\n'for w in fixture.fatal_input(True)[0]))
    for n,h in expected.items():
        if digest(run/n)!=h:raise ValueError('every original preflight-qualified partial raw input required:'+n)
    shutil.copy2(original/'atomic-input.hex',run/'atomic-input.hex')
    for f in original.glob('*.dat'):shutil.copy2(f,run/f.name)
    inputs={str((run/n).relative_to(ROOT)):digest(run/n)for n in [*expected,'atomic-input.hex']}
    before={str(q.relative_to(ROOT)):digest(q)for q in [Path(__file__).resolve(),Path(fixture.__file__).resolve(),
        binding.record('write-abort-scheduled-native-full-001'),binding.record('write-abort-scheduled-native-fixture-diagnostics-001')]}
    r=dict(scope=__doc__,pass_test=False,directory=str(run.relative_to(ROOT)),evidence=dict(actual_failed40=nid,actual_preflight=pid),
        source_sha256=before,diagnostic_input_sha256=inputs,RAM_artifact_sha256={str(binary):digest(binary)},
        original_binary_sha256=native['binary_sha256'],same_original_DUT_bench_binary=True,reused_binary_for_diagnostic_only=True,
        compile_limit_seconds=1200,actual_original_compile_seconds=native['compilation_seconds'],runtime_limit_seconds=30,
        actual_native40_regression_completed=False,new_fixed_bench_runtime_qualified=False,
        hardware_verified=False,full_board_timing=False,overall_goal_complete=False,hardware_or_default_actions=[],commit_or_push=False)
    try:
        cmd=[str(binary),'+LARGE_WRITE_RX','+LARGE_RX_OP=5','+WRITE_FATAL_PARTIAL'];r['command']=cmd
        start=time.monotonic()
        with(run/'partial.log').open('x')as log:
            c=subprocess.run(cmd,cwd=run,stdout=log,stderr=subprocess.STDOUT,timeout=30,preexec_fn=tool.no_core)
        r.update(seconds=time.monotonic()-start,exit=c.returncode)
        if c.returncode:raise ValueError('actual unchanged partial diagnostic failed:'+str(run/'partial.log'))
        output=(run/'partial.log').read_text()
        posted=[int(s,16).to_bytes(128,'little')for s in(run/'receive-records.hex').read_text().splitlines()]
        r['actual_partial_case']=fixture.verify_fatal(output,posted,True,run)
        nonce=fixture.verify_nonce(output)
        # 'translated' counts LOGICAL TAG != physical nonce, not PTE/address
        # translation. This FIRST has logical tag1 and fresh physical nonce1:
        # no retag is needed. Full command/page/status checks stay unchanged.
        if nonce!=dict(admitted=1,issued=1,backend_completed=1,logical_completed=1,translated=0,active=0,fault=0):
            raise ValueError('one actual FIRST logical data command/nonce required')
        r['actual_common_nonce_backend']=nonce
        for n,h in {**before,**inputs}.items():
            if digest(ROOT/n)!=h:raise ValueError('diagnostic source/raw input changed:'+n)
        if digest(binary)!=native['binary_sha256']:raise ValueError('actual diagnostic executable changed')
        r.update(pass_test=True,actual_partial_case_runtime_verified=True,
            remaining=['Fresh fixed-bench full40/all original38 outcomes plus fatal62/access and partial61; this existing-binary diagnostic cannot qualify a modified fixture.',
                'All original11/fatal63/error CQ/STOP/lifetimes/recovery/original timing/physical remain.'])
    except Exception as e:r.update(error_type=type(e).__name__,error=str(e));raise
    finally:
        r['artifact_sha256']={str(q.relative_to(ROOT)):digest(q)for q in run.iterdir()if q.is_file()}
        with a.report.open('x')as f:f.write(json.dumps(r,indent=2)+'\n')
    print(json.dumps(dict(pass_test=True,seconds=r['seconds'],same_original_binary=True,full_native40_qualified=False)))


if __name__=='__main__':main()
