#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual requester consumers and complete new native top C++ compile.

Parsed peer/payload/connection models are explicit. Whole generated RTL/native
memory/MAC/CQ tests remain mandatory; this is not Linux or board evidence.
"""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from probe_native_rnr_hls import ROOT, digest


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True);p.add_argument('--report',type=Path,required=True)
    a=p.parse_args()
    if a.report.exists():p.error('preserve previous evidence')
    source=a.source.resolve();bench=ROOT/'rdma/rnic/hls/test_native_request_retire.cpp'
    inputs=[*source.rglob('*'),bench,Path(__file__).resolve(),Path(__file__).with_name('probe_native_rnr_hls.py')]
    inputs += [ROOT/'rdma/rnic/hls'/n for n in ['request_retire_transport.py','recv_retire_transport.py','rnr_transport.py','qp_tx_transport.py']]
    before={str(x.relative_to(ROOT)):digest(x)for x in inputs if x.is_file()}
    run=Path(tempfile.mkdtemp(prefix='native-request-csim-',dir=ROOT/'rdma/rnic/build'))
    flags=['-std=c++17','-O0','-pthread','-Wno-unknown-pragmas','-ffunction-sections','-fdata-sections','-Wl,--gc-sections',
        '-DFNS_DATA_WIDTH=64','-DFNS_ROCE_STACK_MAX_QPS=8','-D__VITIS_HLS__',
        '-I'+str(source/'adapter'),'-I'+str(source/'fns/hls'),'-I/home/user/amd/2025.2/Vitis/include']
    command=[shutil.which('g++-13'),*flags,str(bench),str(source/'fns/hls/ib_transport_protocol/ib_utils.cpp'),
        str(source/'fns/hls/rocev2/rocev2.cpp'),'-o',str(run/'test')]
    report=dict(scope=__doc__,pass_test=False,source_sha256=before,directory=str(run.relative_to(ROOT)),command=command,
        hardware_verified=False,generated_RTL=False,full_top_CPP_compiled=False,simulation_bound_seconds=10)
    try:
        started=time.monotonic();c=subprocess.run(command,capture_output=True,text=True,timeout=120)
        report['compilation_seconds']=time.monotonic()-started;(run/'compile.log').write_text(c.stdout+c.stderr)
        if c.returncode:raise RuntimeError('request C++ compile failed: '+str(run/'compile.log'))
        report['full_top_CPP_compiled']=True
        started=time.monotonic();r=subprocess.run([str(run/'test')],capture_output=True,text=True,timeout=10)
        report['simulation_seconds']=time.monotonic()-started;(run/'simulation.log').write_text(r.stdout+r.stderr)
        if r.returncode:raise RuntimeError('request C++ consumers failed: '+str(run/'simulation.log'))
        rows=[json.loads(l.split(' ',1)[1])for l in r.stdout.splitlines()if l.startswith('REQUEST_RETIRE_HLS ')]
        if len(rows)!=1 or not rows[0]['pass_test']:raise ValueError('missing actual consumer assertions')
        if before!={n:digest(ROOT/n)for n in before}:raise ValueError('consumed source changed')
        report.update(pass_test=True,source_unchanged=True,summary=rows[0])
    except Exception as e:report.update(error=str(e));raise
    finally:
        with a.report.open('x')as f:f.write(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k]for k in ['pass_test','compilation_seconds','simulation_seconds','summary']}))


if __name__=='__main__':main()
