#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Read original failed RQC native001 at its actual assertion, no DUT rebuild.

Reuse exact immutable model archive/runtime objects, relinking only the
existing diagnostic main/debug types. Separate copied runtime inputs; do not
overwrite failed artifacts. Not native PASS, cancellation or CQ/STOP proof.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import audit_segmented_receive as binding
from probe_segmented_native_fifo_diagnostic import INCLUDE

ROOT=binding.ROOT;digest=binding.digest


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve earlier evidence')
    failed,ids=binding.bindings('fatal-rq-cancel-native-full-001')
    if failed['pass_test']or len(failed['tests'])!=41 or failed['tests']['FATAL_RQC_ACCESS']['exit']!=-6 or \
       sum(t['exit']==0 for t in failed['tests'].values())!=40:raise ValueError('exact original40 pass/new RQC failure required')
    old=ROOT/failed['directory'];obj=Path(failed['compile_directory'])
    run=Path(tempfile.mkdtemp(prefix='fatal-rqc-native-diagnostic-',dir=ROOT/'rdma/rnic/build'))
    ram=Path(tempfile.mkdtemp(prefix='as02-fatal-rqc-native-debug-',dir='/dev/shm'))
    testdir=ROOT/'rdma/rnic/tests'
    inputs=[Path(__file__).resolve(),testdir/'zero_native_debug_main.cpp',testdir/'fatal_rq_cancel_native_debug.gdb',
        *[obj/n for n in ['Vtb.h','Vtb___024root.h','Vtb__ALL.a','verilated.o','verilated_timing.o','verilated_threads.o']]]
    for n,h in failed['tests']['FATAL_RQC_ACCESS']['runtime_input_sha256'].items():
        q=old/('FATAL_RQC_ACCESS-'+n)
        if digest(q)!=h:raise ValueError('failed raw input changed:'+n)
        inputs.append(q);shutil.copy2(q,run/n)
    for q in [old/'atomic-input.hex',*old.glob('*.dat')]:inputs.append(q);shutil.copy2(q,run/q.name)
    before={str(q.relative_to(ROOT))if q.is_relative_to(ROOT)else str(q):digest(q)for q in inputs}
    r=dict(scope=__doc__,diagnostic_completed=False,original_native_test_still_failed=True,
        native_runtime_pass=False,directory=str(run.relative_to(ROOT)),failed_evidence=ids,source_sha256=before,
        debug_main_only_compile_link_limit_seconds=120,original_model_objects_not_rebuilt=True,
        original_model_optimization_still_O1=True,runtime_limit_seconds=30,clock_ns=4,
        DUT_state_or_guard_or_assertion_mutation=False,hardware_or_default_actions=[],commit_or_push=False,overall_goal_complete=False)
    try:
        binary=ram/'Vtb-debug'
        cmd=['g++','-std=c++20','-g','-O0','-fcoroutines','-I'+str(obj),'-I'+str(INCLUDE),'-I'+str(INCLUDE/'vltstd'),
            str(testdir/'zero_native_debug_main.cpp'),*[str(obj/n)for n in ['Vtb__ALL.a','verilated.o','verilated_timing.o','verilated_threads.o']],
            '-pthread','-lpthread','-latomic','-o',str(binary)]
        start=time.monotonic();c=subprocess.run(cmd,capture_output=True,text=True,timeout=120)
        (run/'link.log').write_text(c.stdout+c.stderr);r.update(link_command=cmd,link_exit=c.returncode,link_seconds=time.monotonic()-start)
        if c.returncode:raise ValueError('debug-main-only link failed')
        cmd=['gdb','-q','-batch','-x',str(testdir/'fatal_rq_cancel_native_debug.gdb'),str(binary)]
        env=os.environ.copy();env['AS02_FATAL_RQC_DEBUG_OBJ']=str(obj)
        start=time.monotonic();c=subprocess.run(cmd,cwd=run,capture_output=True,text=True,env=env,timeout=30)
        output=c.stdout+c.stderr;(run/'inspection.log').write_text(output)
        r.update(debug_command=cmd,debug_exit=c.returncode,debug_seconds=time.monotonic()-start)
        if c.returncode or 'FATAL_RQC full current posted-RQ/SQC authority must still be held before real cancellation'not in output:
            raise ValueError('same original assertion must still fail under read-only debugger')
        rows=[json.loads(l.split(' ',1)[1])for l in output.splitlines()if l.startswith('FATAL_RQC_DEBUG_VALUES ')]
        if len(rows)!=1:raise ValueError('actual failing-boundary state readback missing')
        r['actual_fatal_fields']=rows[0]
        for n,h in before.items():
            if digest(ROOT/n)!=h:raise ValueError('original model/source changed:'+n)
        binding.bindings('fatal-rq-cancel-native-full-001')
        r.update(diagnostic_completed=True)
    except Exception as e:r.update(error_type=type(e).__name__,error=str(e));raise
    finally:
        r['artifact_sha256']={str(q.relative_to(ROOT)):digest(q)for q in run.iterdir()if q.is_file()}
        r['RAM_artifact_sha256']={str(q):digest(q)for q in ram.iterdir()if q.is_file()}
        with a.report.open('x')as f:f.write(json.dumps(r,indent=2)+'\n')
    print(json.dumps(dict(diagnostic_completed=True,original_failed_test_still_false=True,debug_seconds=r['debug_seconds'],actual_fields=r['actual_fatal_fields'])))


if __name__=='__main__':main()
