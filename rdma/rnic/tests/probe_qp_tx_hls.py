#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Short actual QPI/state-consumer C++ execution plus full top C++ compilation.

Not generated-RTL, scheduler/CDC/reset/timing, whole-core retirement, native
hardware or standard verbs proof. No HLS synthesis/XSIM guard is relaxed.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

ROOT=Path(__file__).resolve().parents[3]
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',required=True,type=Path);p.add_argument('--report',required=True,type=Path)
    p.add_argument('--vitis-include',type=Path,default=Path('/home/user/amd/2025.2/Vitis/include'))
    a=p.parse_args()
    if a.report.exists():p.error('preserve prior evidence')
    source=a.source.resolve();bench=ROOT/'rdma/rnic/hls/test_qp_tx_transport.cpp'
    before={str(x.relative_to(ROOT)):digest(x)for x in [*source.rglob('*'),bench,Path(__file__).resolve(),ROOT/'rdma/rnic/hls/qp_tx_transport.py']if x.is_file()}
    run=Path(tempfile.mkdtemp(prefix='qp-tx-csim-',dir=ROOT/'rdma/rnic/build'))
    compiler=shutil.which('g++-13')
    flags=['-std=c++17','-O0','-pthread','-Wno-unknown-pragmas','-ffunction-sections','-fdata-sections','-Wl,--gc-sections',
        '-DFNS_DATA_WIDTH=64','-DFNS_ROCE_STACK_MAX_QPS=8','-D__VITIS_HLS__',
        '-I'+str(source/'adapter'),'-I'+str(source/'fns/hls'),'-I'+str(a.vitis_include.resolve())]
    top=source/'fns/hls/rocev2/rocev2.cpp'
    cmd=[compiler,*flags,str(bench),str(top),'-o',str(run/'test')]
    start=time.monotonic();c=subprocess.run(cmd,capture_output=True,text=True,timeout=120)
    compile_seconds=time.monotonic()-start;(run/'compile.log').write_text(c.stdout+c.stderr)
    result=dict(scope=__doc__,pass_test=False,source_sha256=before,command=cmd,directory=str(run.relative_to(ROOT)),
        compilation_seconds=compile_seconds,compile_returncode=c.returncode,compile_bound_seconds=120,
        hardware_verified=False,generated_RTL=False,full_top_CPP_compiled=c.returncode==0,simulation_bound_seconds=10)
    try:
        if c.returncode:raise RuntimeError('C++ compile failed; '+str(run/'compile.log'))
        start=time.monotonic();r=subprocess.run([str(run/'test')],capture_output=True,text=True,timeout=10)
        result['simulation_seconds']=time.monotonic()-start;(run/'simulation.log').write_text(r.stdout+r.stderr)
        if r.returncode:raise RuntimeError('C++ test failed; '+str(run/'simulation.log'))
        rows=[json.loads(l.split(' ',1)[1])for l in r.stdout.splitlines()if l.startswith('QP_TX_HLS ')]
        if len(rows)!=1 or not rows[0]['pass_test']:raise ValueError('missing actual QPI assertion result')
        if before!={n:digest(ROOT/n)for n in before}:raise ValueError('source changed')
        result.update(pass_test=True,summary=rows[0],source_unchanged=True)
    finally:
        with a.report.open('x')as f:f.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k]for k in ['pass_test','compilation_seconds','simulation_seconds','summary']}))
if __name__=='__main__':main()
