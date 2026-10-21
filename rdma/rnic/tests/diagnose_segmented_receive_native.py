#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Read-only original large RX fatal using identical archived DUT objects.

Only the diagnostic main/debug types are relinked. Copy original exact
readmem inputs to a fresh directory, stop at the unchanged original fatal,
and inspect fields. No DUT compilation, assertion/deadline/input/state change
or producer/MR/DMA/status/HLS/MAC/CQ injection, and no native pass claim.
"""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
import probe_segmented_native_fifo_diagnostic as old

ROOT=old.ROOT;digest=old.digest
FAILED=ROOT/'results/2026-10-18/rocev2-rnic-segmented-receive-native-full-003.json'


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve earlier evidence')
    failed=json.loads(FAILED.read_text())
    if failed.get('pass_test')or set(failed['tests'])!={'LARGE_RX_SEND'}or failed['tests']['LARGE_RX_SEND']['exit']!=-6:
        raise ValueError('exact terminal original incoming SEND failure required')
    count=0
    for key in ['source_sha256','artifact_sha256','RAM_artifact_sha256']:
        for n,h in failed[key].items():
            path=Path(n);path=path if path.is_absolute()else ROOT/path
            if digest(path)!=h:raise ValueError('original failed binding changed:'+n)
            count+=1
    obj=Path(failed['compile_directory']);tests=ROOT/'rdma/rnic/tests'
    run=Path(tempfile.mkdtemp(prefix='receive-native-fatal-diagnostic-',dir=ROOT/'rdma/rnic/build'))
    ram=Path(tempfile.mkdtemp(prefix='as02-receive-native-debug-',dir='/dev/shm'))
    data=[p for p in(ROOT/failed['directory']).iterdir()if p.suffix in ['.hex','.dat']]
    for path in data:shutil.copy2(path,run/path.name)
    inputs=[FAILED,Path(__file__).resolve(),Path(old.__file__).resolve(),tests/'zero_native_debug_main.cpp',
        tests/'segmented_receive_native_debug.gdb',*data,
        *[obj/n for n in ['Vtb___024root.h','Vtb__ALL.a','verilated.o','verilated_timing.o','verilated_threads.o']]]
    before={str(p.relative_to(ROOT))if p.is_relative_to(ROOT)else str(p):digest(p)for p in inputs}
    result=dict(scope=__doc__,diagnostic_completed=False,native_runtime_pass=False,hardware_verified=False,
        failed_bindings_verified=count,directory=str(run.relative_to(ROOT)),source_sha256=before,
        diagnostic_runtime_limit_seconds=30,DUT_objects_unchanged=True,all_original_assertions_and_limits_unchanged=True)
    try:
        binary=ram/'Vtb-debug'
        command=['g++','-std=c++20','-g','-O0','-fcoroutines','-I'+str(obj),'-I'+str(old.INCLUDE),
            '-I'+str(old.INCLUDE/'vltstd'),str(tests/'zero_native_debug_main.cpp'),
            *[str(obj/n)for n in ['Vtb__ALL.a','verilated.o','verilated_timing.o','verilated_threads.o']],
            '-pthread','-lpthread','-latomic','-o',str(binary)]
        start=time.monotonic();c=subprocess.run(command,capture_output=True,text=True,timeout=120)
        (run/'link.log').write_text(c.stdout+c.stderr);result.update(link_command=command,link_exit=c.returncode,link_seconds=time.monotonic()-start)
        if c.returncode:raise ValueError('diagnostic-only main link failed')
        command=['gdb','-q','-batch','-x',str(tests/'segmented_receive_native_debug.gdb'),str(binary)]
        env=os.environ.copy();env['AS02_NATIVE_DEBUG_OBJ']=str(obj);start=time.monotonic()
        c=subprocess.run(command,cwd=run,capture_output=True,text=True,env=env,timeout=30)
        output=c.stdout+c.stderr;(run/'fatal-inspection.log').write_text(output)
        result.update(debug_command=command,debug_exit=c.returncode,debug_seconds=time.monotonic()-start)
        if c.returncode or 'SEGMENTED_RECEIVE_ORIGINAL_FATAL'not in output:raise ValueError('original fatal not inspected')
        fields={}
        for line in output.splitlines():
            if line.startswith('RX_FATAL_FIELD '):
                record=json.loads(line.split(' ',1)[1]);fields[record['name']]=record['value']
        result['actual_fatal_fields']=fields
        messages=[line.split(' ',1)[1]for line in output.splitlines()if line.startswith('RX_FATAL_MESSAGE ')]
        result['original_fatal_messages']=messages
        lines=[int(line.split()[1])for line in output.splitlines()if line.startswith('RX_FATAL_SOURCE_LINE ')]
        original=(ROOT/failed['directory']/'LARGE_RX_SEND.log').read_text()
        expected=re.findall(r'tb\.v:(\d+): Assertion failed in tb.run_large_receive_native: large RX real per-packet data/HLS/MAC release deadline packet1',original)
        result['original_fatal_source_lines']=lines
        if messages!=['Verilog $stop']or len(expected)!=1 or lines!=[int(expected[0])]or \
           fields.get('tb__DOT__lrx_commands')!=1 or fields.get('tb__DOT__lrx_packet_releases')!=1:
            raise ValueError('not the exact original middle-packet stall')
        if any(digest(Path(n)if Path(n).is_absolute()else ROOT/n)!=h for n,h in before.items()):
            raise ValueError('original failed inputs or archived objects changed')
        result.update(diagnostic_completed=True,actual_fatal_fields=fields,source_and_objects_unchanged=True)
    except Exception as e:result.update(error_type=type(e).__name__,error=str(e));raise
    finally:
        result['artifact_sha256']={str(p.relative_to(ROOT)):digest(p)for p in run.iterdir()if p.is_file()}
        result['RAM_artifact_sha256']={str(p):digest(p)for p in ram.iterdir()if p.is_file()}
        with a.report.open('x')as f:f.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(diagnostic_completed=True,failed_bindings_verified=count,debug_seconds=result['debug_seconds'],actual_fatal_fields=result['actual_fatal_fields'])),flush=True)


if __name__=='__main__':main()
