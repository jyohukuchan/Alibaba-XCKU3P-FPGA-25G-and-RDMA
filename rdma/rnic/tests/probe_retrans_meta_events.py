#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual event-status metadata C++ engine/collector; not RTL scheduling/reset.

Preserves the original2000-call no-admission gate and all stored zero fields.
Withheld status consumption cannot authorize memory or insertion completion.
"""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import audit_segmented_receive as binding

ROOT=binding.ROOT


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True)
    p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve earlier evidence')
    source=a.source.resolve();info=json.loads((source/'source.json').read_text())
    if not info.get('actual_sticky_fault_event_and_collector'):raise ValueError('exact event-status candidate required')
    unit=ROOT/'rdma/rnic/hls/test_retrans_meta_events.cpp'
    inputs=[*[q for q in source.rglob('*')if q.is_file()],unit,Path(__file__).resolve(),ROOT/'rdma/rnic/hls/segmented_write_abort_event_transport.py']
    before={str(q.relative_to(ROOT)):binding.digest(q)for q in inputs}
    for n,h in info['derived_sources'].items():
        if binding.digest(source/'fns'/n)!=h:raise ValueError('derived source changed:'+n)
    run=Path(tempfile.mkdtemp(prefix='retrans-meta-events-',dir=ROOT/'rdma/rnic/build'))
    ram=Path(tempfile.mkdtemp(prefix='as02-retrans-meta-events-',dir='/dev/shm'))
    shutil.copytree(source/'fns',run/'inputs/fns');shutil.copytree(source/'adapter',run/'inputs/adapter');shutil.copy2(unit,run/'inputs/test.cpp')
    frozen={str(q.relative_to(run/'inputs')):binding.digest(q)for q in(run/'inputs').rglob('*')if q.is_file()}
    cmd=[shutil.which('g++-13')or'g++','-std=c++17','-O1','-Wno-unknown-pragmas','-DFNS_DATA_WIDTH=64',
        '-DFNS_ROCE_STACK_MAX_QPS=8','-D__VITIS_HLS__','-I'+str(run/'inputs/adapter'),
        '-I'+str(run/'inputs/fns/hls'),'-I/home/user/amd/2025.2/Vitis/include',str(run/'inputs/test.cpp'),'-o',str(ram/'test')]
    r=dict(scope=__doc__,pass_test=False,directory=str(run.relative_to(ROOT)),source_sha256=before,
        frozen_sha256=frozen,compile_command=cmd,compile_limit_seconds=120,runtime_limit_seconds=10,
        actual_RTL_runtime=False,native_runtime=False,hardware_verified=False,full_board_timing=False)
    try:
        start=time.monotonic()
        with(run/'compile.log').open('x')as f:c=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,timeout=120)
        r.update(compile_seconds=time.monotonic()-start,compile_exit=c.returncode)
        if c.returncode:raise ValueError('actual metadata-event engine compile failed')
        start=time.monotonic()
        with(run/'runtime.log').open('x')as f:c=subprocess.run([str(ram/'test')],stdout=f,stderr=subprocess.STDOUT,timeout=10)
        r.update(seconds=time.monotonic()-start,exit=c.returncode)
        if c.returncode:raise ValueError('actual metadata-event engine assertions failed')
        lines=[json.loads(s)for s in(run/'runtime.log').read_text().splitlines()if s.startswith('{')]
        if len(lines)!=1 or not lines[0]['pass_test']:raise ValueError('one actual independent assertion summary required')
        for n,h in before.items():
            if binding.digest(ROOT/n)!=h:raise ValueError('source changed:'+n)
        r.update(pass_test=True,summary=lines[0])
    except Exception as e:r.update(error_type=type(e).__name__,error=str(e));raise
    finally:
        r['artifact_sha256']={str(q.relative_to(ROOT)):binding.digest(q)for q in run.iterdir()if q.is_file()}
        r['RAM_artifact_sha256']={str(q):binding.digest(q)for q in ram.iterdir()if q.is_file()}
        with a.report.open('x')as f:f.write(json.dumps(r,indent=2)+'\n')
    print(json.dumps(dict(pass_test=True,compile_seconds=r['compile_seconds'],seconds=r['seconds'],summary=r['summary'])))


if __name__=='__main__':main()
