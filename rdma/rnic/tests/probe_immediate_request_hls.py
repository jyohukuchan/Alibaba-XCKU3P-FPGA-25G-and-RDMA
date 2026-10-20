#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Complete new immediate-request top compile and actual producer consumers.

Use the existing harness template at the new620-bit context geometry; peer
headers, connection and memory data remain models. Not generated/native RTL,
RX immediate notification, kernel/provider, physical or timing evidence.
"""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from probe_native_rnr_hls import ROOT,digest

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True)
    p.add_argument('--report',type=Path,required=True)
    p.add_argument('--receive',action='store_true',help='actual Immediate TX-to-RX transport consumers; still not native RTL')
    a=p.parse_args()
    if a.report.exists():p.error('preserve previous evidence')
    source=a.source.resolve();info=json.loads((source/'source.json').read_text())
    if not info.get('request_immediate')or info.get('request_context_bits')!=620:p.error('matched immediate source required')
    if a.receive and not info.get('receive_immediate'):p.error('matched Immediate receive source required')
    bench=ROOT/'rdma/rnic/hls'/('test_immediate_receive.cpp' if a.receive else 'test_immediate_request.cpp')
    template=ROOT/'rdma/rnic/hls/test_native_request_retire.cpp'
    inputs=[*source.rglob('*'),bench,template,Path(__file__).resolve()]
    inputs += [ROOT/'rdma/rnic/hls'/n for n in ['immediate_request_transport.py','duplex_transport.py',
        'request_retire_transport.py','recv_retire_transport.py','rnr_transport.py','qp_tx_transport.py']]
    if a.receive:inputs += [ROOT/'rdma/rnic/hls/immediate_transport.py']
    before={str(x.relative_to(ROOT)):digest(x)for x in inputs if x.is_file()}
    run=Path(tempfile.mkdtemp(prefix='immediate-request-csim-',dir=ROOT/'rdma/rnic/build'))
    (run/'immediate_request_base.hpp').write_text(template.read_text().replace('ap_uint<588>','ap_uint<620>'))
    flags=['-std=c++17','-O0','-pthread','-Wno-unknown-pragmas','-ffunction-sections','-fdata-sections','-Wl,--gc-sections',
        '-DFNS_DATA_WIDTH=64','-DFNS_ROCE_STACK_MAX_QPS=8','-D__VITIS_HLS__',
        '-I'+str(run),'-I'+str(source/'adapter'),'-I'+str(source/'fns/hls'),'-I/home/user/amd/2025.2/Vitis/include']
    command=[shutil.which('g++-13'),*flags,str(bench),str(source/'fns/hls/ib_transport_protocol/ib_utils.cpp'),
        str(source/'fns/hls/rocev2/rocev2.cpp'),'-o',str(run/'test')]
    result=dict(scope=__doc__,pass_test=False,source_sha256=before,directory=str(run.relative_to(ROOT)),command=command,
        hardware_verified=False,generated_RTL=False,native_integration=False,full_top_CPP_compiled=False,simulation_limit_seconds=10)
    try:
        start=time.monotonic();c=subprocess.run(command,capture_output=True,text=True,timeout=120)
        result['compilation_seconds']=time.monotonic()-start;(run/'compile.log').write_text(c.stdout+c.stderr)
        if c.returncode:raise RuntimeError('immediate request compile failed: '+str(run/'compile.log'))
        result['full_top_CPP_compiled']=True
        start=time.monotonic();r=subprocess.run([str(run/'test')],capture_output=True,text=True,timeout=10)
        result['simulation_seconds']=time.monotonic()-start;(run/'simulation.log').write_text(r.stdout+r.stderr)
        if r.returncode:raise RuntimeError('immediate request consumers failed: '+str(run/'simulation.log'))
        prefix='IMMEDIATE_RECEIVE_HLS ' if a.receive else 'IMMEDIATE_REQUEST_HLS '
        rows=[json.loads(l.split(' ',1)[1])for l in r.stdout.splitlines()if l.startswith(prefix)]
        if len(rows)!=1 or not rows[0]['pass_test']:raise ValueError('missing actual immediate assertions')
        if before!={n:digest(ROOT/n)for n in before}:raise ValueError('consumed source changed')
        result.update(pass_test=True,source_unchanged=True,summary=rows[0],derived_harness_sha256=digest(run/'immediate_request_base.hpp'))
    except Exception as e:result.update(error=str(e));raise
    finally:
        with a.report.open('x')as f:f.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k]for k in ['pass_test','compilation_seconds','simulation_seconds','summary']}))

if __name__=='__main__':main()
