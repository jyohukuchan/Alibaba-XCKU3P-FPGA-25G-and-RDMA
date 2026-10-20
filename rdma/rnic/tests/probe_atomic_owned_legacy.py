#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Existing Immediate consumers on complete owned Atomic HLS source, C++ only."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import probe_atomic_owned as owned

ROOT=owned.ROOT


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True)
    p.add_argument('--report',type=Path,required=True);p.add_argument('--receive',action='store_true');a=p.parse_args()
    if a.report.exists():p.error('preserve prior evidence')
    source=a.source.resolve();bench=ROOT/'rdma/rnic/hls'/('test_immediate_receive.cpp'if a.receive else'test_immediate_request.cpp')
    inputs=[*source.rglob('*'),bench,owned.base.TEMPLATE,Path(__file__).resolve(),Path(owned.__file__).resolve(),
        Path(owned.base.__file__).resolve()]
    before={str(x.relative_to(ROOT)):owned.base.digest(x)for x in inputs if x.is_file()}
    run=Path(tempfile.mkdtemp(prefix='atomic-owned-legacy-',dir=ROOT/'rdma/rnic/build'))
    (run/'immediate_request_base.hpp').write_text(owned.harness())
    flags=['-std=c++17','-O0','-pthread','-Wno-unknown-pragmas','-ffunction-sections','-fdata-sections','-Wl,--gc-sections',
        '-DFNS_DATA_WIDTH=64','-DFNS_ROCE_STACK_MAX_QPS=8','-D__VITIS_HLS__','-I'+str(run),'-I'+str(source/'adapter'),
        '-I'+str(source/'fns/hls'),'-I/home/user/amd/2025.2/Vitis/include']
    command=[shutil.which('g++-13'),*flags,str(bench),str(source/'fns/hls/ib_transport_protocol/ib_utils.cpp'),
        str(source/'fns/hls/rocev2/rocev2.cpp'),'-o',str(run/'test')]
    report=dict(scope=__doc__,pass_test=False,source_sha256=before,directory=str(run.relative_to(ROOT)),
        hardware_verified=False,generated_RTL=False,native_integration=False,full_top_CPP_compiled=False,
        simulation_limit_seconds=10,receive=a.receive)
    try:
        with tempfile.TemporaryDirectory(prefix='as02-atomic-owned-legacy-cxx-',dir='/dev/shm')as temporary:
            env=os.environ.copy();env['TMPDIR']=temporary;start=time.monotonic()
            c=subprocess.run(command,capture_output=True,text=True,timeout=180,env=env)
        report['compile_seconds']=time.monotonic()-start;(run/'compile.log').write_text(c.stdout+c.stderr)
        if c.returncode:raise RuntimeError('full graph/old consumer compile: '+str(run/'compile.log'))
        report['full_top_CPP_compiled']=True;start=time.monotonic()
        r=subprocess.run([str(run/'test')],capture_output=True,text=True,timeout=10)
        report['simulation_seconds']=time.monotonic()-start;(run/'simulation.log').write_text(r.stdout+r.stderr)
        if r.returncode:raise RuntimeError('old consumers: '+str(run/'simulation.log'))
        prefix='IMMEDIATE_RECEIVE_HLS 'if a.receive else'IMMEDIATE_REQUEST_HLS '
        rows=[json.loads(l.split(' ',1)[1])for l in r.stdout.splitlines()if l.startswith(prefix)]
        if len(rows)!=1 or not rows[0]['pass_test']:raise ValueError('missing consumer assertions')
        if before!={n:owned.base.digest(ROOT/n)for n in before}:raise ValueError('inputs changed')
        report.update(pass_test=True,source_unchanged=True,summary=rows[0],
            artifact_sha256={str(x.relative_to(ROOT)):owned.base.digest(x)for x in [run/'test',run/'immediate_request_base.hpp']})
    except Exception as e:report['error']=str(e);raise
    finally:
        with a.report.open('x')as out:out.write(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k]for k in ['pass_test','compile_seconds','simulation_seconds','summary']}))


if __name__=='__main__':main()
