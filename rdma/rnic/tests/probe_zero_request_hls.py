#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Full compiled actual Atomic/Immediate/zero requester HLS C++ consumers.

No modeled no-data completion: real stored replay, parser, header/timer/state
consumers and common retire join. Peer/memory/connection endpoints are models.
All previous Atomic requester cases run fresh on this same modified source.
Not generated RTL, native protection/CQ, Linux, hardware or timing proof.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import probe_atomic_request_hls as old

ROOT=old.ROOT;digest=old.digest


def harness():
    t=old.old.harness().replace('ap_uint<620>','ap_uint<748>')
    t=old.old.once(t,'ap_uint<1> af=0,rf=0,ef=0,mf=0,tf=0,ff=0,jf=0,recv_fault=0;',
        'ap_uint<1> af=0,rf=0,ef=0,mf=0,tf=0,ff=0,jf=0,recv_fault=0,pf=0;')
    t=old.old.once(t,'raw,memory,recv_data,read_consumed);','raw,memory,recv_data,read_consumed,pf);')
    return old.old.once(t,'af|rf|ef|mf|tf|ff,jf);','af|rf|ef|mf|tf|ff|pf,jf);')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True)
    p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve prior evidence')
    source=a.source.resolve();info=json.loads((source/'source.json').read_text())
    if not info.get('zero_length_requester')or info.get('HLS_top')!='rocev2_native_zero_request_top':p.error('matched zero source required')
    bench=ROOT/'rdma/rnic/hls/test_zero_request.cpp';prior=ROOT/'rdma/rnic/hls/test_atomic_request.cpp'
    inputs=[*source.rglob('*'),bench,prior,Path(__file__).resolve(),Path(old.__file__).resolve(),Path(old.old.__file__).resolve(),
        Path(old.old.base.__file__).resolve(),old.old.base.TEMPLATE,*list((ROOT/'rdma/rnic/hls').glob('*transport.py'))]
    before={str(p.relative_to(ROOT)):digest(p)for p in inputs if p.is_file()}
    run=Path(tempfile.mkdtemp(prefix='zero-request-csim-',dir=ROOT/'rdma/rnic/build'))
    ram=Path(tempfile.mkdtemp(prefix='as02-zero-request-cxx-',dir='/dev/shm'))
    (run/'atomic_request_base.hpp').write_text(harness())
    text=old.old.once(prior.read_text(),'int main() {','int atomic_compat_main() {')
    (run/'atomic_request_prior.cpp').write_text(text);shutil.copy2(bench,run/'test.cpp')
    flags=['-std=c++17','-O0','-pthread','-Wno-unknown-pragmas','-ffunction-sections','-fdata-sections','-Wl,--gc-sections',
        '-DFNS_DATA_WIDTH=64','-DFNS_ROCE_STACK_MAX_QPS=8','-D__VITIS_HLS__','-I'+str(run),
        '-I'+str(source/'adapter'),'-I'+str(source/'fns/hls'),'-I/home/user/amd/2025.2/Vitis/include']
    cmd=[shutil.which('g++-13'),*flags,str(run/'test.cpp'),str(source/'fns/hls/ib_transport_protocol/ib_utils.cpp'),
        str(source/'fns/hls/rocev2/rocev2.cpp'),'-o',str(ram/'test')]
    report=dict(scope=__doc__,pass_test=False,source_sha256=before,directory=str(run.relative_to(ROOT)),command=cmd,
        simulation_limit_seconds=30,full_top_CPP_compiled=False,generated_HLS_RTL=False,native_integration=False,
        hardware_verified=False,physical_peer_memory_connection_modeled=True,request_context_bits=748,SQ_bits=408)
    print(json.dumps(dict(directory=str(run),phase='compile',RAM_directory=str(ram))),flush=True)
    try:
        env=os.environ.copy();env['TMPDIR']=str(ram);start=time.monotonic()
        c=subprocess.run(cmd,capture_output=True,text=True,timeout=600,env=env)
        report['compile_seconds']=time.monotonic()-start;(run/'compile.log').write_text(c.stdout+c.stderr)
        if c.returncode:raise ValueError('zero request full-top compile failed: '+str(run/'compile.log'))
        report.update(full_top_CPP_compiled=True,RAM_artifact_sha256={str(ram/'test'):digest(ram/'test')})
        print(json.dumps(dict(phase='runtime',compile_seconds=report['compile_seconds'])),flush=True)
        start=time.monotonic();r=subprocess.run([str(ram/'test')],capture_output=True,text=True,timeout=30)
        report['simulation_seconds']=time.monotonic()-start;(run/'simulation.log').write_text(r.stdout+r.stderr)
        if r.returncode:raise ValueError('actual zero consumers failed: '+str(run/'simulation.log'))
        summaries={}
        for marker in ['ATOMIC_REQUEST_HLS','ZERO_REQUEST_HLS']:
            rows=[json.loads(l.split(' ',1)[1])for l in r.stdout.splitlines()if l.startswith(marker+' ')]
            if len(rows)!=1 or not rows[0].get('pass_test'):raise ValueError('missing actual '+marker)
            summaries[marker]=rows[0]
        zero=[l.split(' ',2)[1:]for l in r.stdout.splitlines()if l.startswith('ZERO_REQUEST_WIRE ')]
        atomic=[l.split(' ',2)[1:]for l in r.stdout.splitlines()if l.startswith('ATOMIC_REQUEST_WIRE ')]
        if len(zero)!=13 or len(atomic)!=18:raise ValueError('incomplete wire oracle coverage')
        if any(digest(ROOT/n)!=h for n,h in before.items()):raise ValueError('source changed')
        report.update(pass_test=True,source_unchanged=True,summary=summaries['ATOMIC_REQUEST_HLS'],
            zero_summary=summaries['ZERO_REQUEST_HLS'],zero_wire_packets=zero,wire_packets=atomic)
    except Exception as e:report.update(error_type=type(e).__name__,error=str(e));raise
    finally:
        report['artifact_sha256']={str(p.relative_to(ROOT)):digest(p)for p in run.iterdir()if p.is_file()}
        with a.report.open('x')as f:f.write(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k]for k in ['pass_test','compile_seconds','simulation_seconds','zero_summary']}),flush=True)


if __name__=='__main__':main()
