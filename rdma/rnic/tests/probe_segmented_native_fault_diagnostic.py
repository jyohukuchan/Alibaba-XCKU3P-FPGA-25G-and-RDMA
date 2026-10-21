#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Read-only original-fatal inspection of frozen native003, not a native pass.

Validate every failed binding BEFORE any fix. Relink the existing archive
and runtime objects with debug types only; no DUT rebuild or state writes.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import probe_segmented_native_fifo_diagnostic as old

ROOT=old.ROOT;digest=old.digest
FAILED=ROOT/'results/2026-10-18/rocev2-rnic-segmented-wire-native-full-003.json'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report',type=Path,required=True);a=parser.parse_args()
    if a.report.exists():parser.error('preserve prior evidence')
    failed=json.loads(FAILED.read_text())
    if failed['pass_test']or set(failed['tests'])!={'LARGE_WRITE'}or failed['tests']['LARGE_WRITE']['exit']!=-6:
        raise ValueError('exact terminal first large WRITE failure required')
    count=0
    for field in ['source_sha256','artifact_sha256','RAM_artifact_sha256']:
        for n,h in failed[field].items():
            if digest(ROOT/n)!=h:raise ValueError('failed bound input changed:'+n)
            count+=1
    run=Path(tempfile.mkdtemp(prefix='segmented-native-fault-diagnostic-',dir=ROOT/'rdma/rnic/build'))
    ram=Path(tempfile.mkdtemp(prefix='as02-segmented-owner-debug-',dir='/dev/shm'))
    obj=Path(failed['compile_directory']);tests=ROOT/'rdma/rnic/tests'
    inputs=[FAILED,Path(__file__).resolve(),Path(old.__file__).resolve(),tests/'zero_native_debug_main.cpp',
            tests/'segmented_native_debug_fault.gdb',*[obj/n for n in ['Vtb___024root.h','Vtb__ALL.a','verilated.o','verilated_timing.o','verilated_threads.o']]]
    for n in ['segmented_wire_native_fixture.py','probe_segmented_wire_native_full.py','segmented_pcie_request_fixture.py']:
        inputs.append(tests/n);shutil.copy2(tests/n,run/n)
    for folder,n in [('fpga','derive_segmented_wire.py'),('rtl','rocev2_segmented_source_executor.v')]:
        p=ROOT/'rdma/rnic'/folder/n;inputs.append(p);shutil.copy2(p,run/n)
    before={str(p.relative_to(ROOT))if p.is_relative_to(ROOT)else str(p):digest(p)for p in inputs}
    report=dict(scope=__doc__,diagnostic_completed=False,native_runtime_pass=False,failed_bindings_verified=count,
                directory=str(run.relative_to(ROOT)),source_sha256=before)
    try:
        binary=ram/'Vtb-debug'
        command=['g++','-std=c++20','-g','-O0','-fcoroutines','-I'+str(obj),'-I'+str(old.INCLUDE),
                 '-I'+str(old.INCLUDE/'vltstd'),str(tests/'zero_native_debug_main.cpp'),
                 *[str(obj/n)for n in ['Vtb__ALL.a','verilated.o','verilated_timing.o','verilated_threads.o']],
                 '-pthread','-lpthread','-latomic','-o',str(binary)]
        start=time.monotonic();c=subprocess.run(command,capture_output=True,text=True,timeout=120)
        (run/'link.log').write_text(c.stdout+c.stderr)
        report.update(link_command=command,link_exit=c.returncode,link_seconds=time.monotonic()-start)
        if c.returncode:raise ValueError('diagnostic-only relink failed')
        command=['gdb','-q','-batch','-x',str(tests/'segmented_native_debug_fault.gdb'),str(binary)]
        env=os.environ.copy();env['AS02_NATIVE_DEBUG_OBJ']=str(obj)
        start=time.monotonic();c=subprocess.run(command,cwd=ROOT/failed['directory'],capture_output=True,text=True,env=env,timeout=30)
        output=c.stdout+c.stderr;(run/'fatal-inspection.log').write_text(output)
        report.update(debug_command=command,debug_exit=c.returncode,debug_seconds=time.monotonic()-start)
        if c.returncode or 'SEGMENTED_NATIVE_ACTUAL_OWNER_FATAL'not in output:raise ValueError('original fatal not inspected')
        values={}
        for line in output.splitlines():
            if line.startswith('tb__DOT__')and' = 'in line:
                n,v=line.split(' = ',1)
                if v.isdigit():values[n]=int(v)
        report['actual_fatal_fields']=values
        if values.get('tb__DOT__fault')!=1:raise ValueError('not original actual RNIC fatal')
        report.update(diagnostic_completed=True)
    except Exception as e:report.update(error_type=type(e).__name__,error=str(e));raise
    finally:
        report['artifact_sha256']={str(p.relative_to(ROOT)):digest(p)for p in run.iterdir()if p.is_file()}
        report['RAM_artifact_sha256']={str(p):digest(p)for p in ram.iterdir()if p.is_file()}
        a.report.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({n:report[n]for n in ['diagnostic_completed','failed_bindings_verified','debug_seconds','directory']}))


if __name__=='__main__':main()
