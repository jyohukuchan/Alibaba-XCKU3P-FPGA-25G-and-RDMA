#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Full owned Atomic-request HLS C++ compile and actual transport consumers.

Actual local bind/TX headers/retransmission records/RX header parser/result
data/retire join/timers/common PSN table. Peer, connection and physical memory
endpoints are models. No native protected DMA/MAC/CQ/provider/RTL/timing claim.
Compile is a permitted feature build; each runtime is bounded to30seconds.
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

import probe_atomic_owned as old

ROOT=old.ROOT


def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True)
    p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve prior evidence')
    source=a.source.resolve();info=json.loads((source/'source.json').read_text())
    if (info.get('request_context_bits'),info.get('SQ_bits'),info.get('receive_context_bits'))!=(748,408,620):
        p.error('matched complete Atomic-request source required')
    bench=ROOT/'rdma/rnic/hls/test_atomic_request.cpp'
    inputs=[*source.rglob('*'),bench,Path(__file__).resolve(),Path(old.__file__).resolve(),
        Path(old.base.__file__).resolve(),old.base.TEMPLATE,*list((ROOT/'rdma/rnic/hls').glob('*transport.py'))]
    before={str(x.relative_to(ROOT)):digest(x)for x in inputs if x.is_file()}
    run=Path(tempfile.mkdtemp(prefix='atomic-request-csim-',dir=ROOT/'rdma/rnic/build'))
    ram=Path(tempfile.mkdtemp(prefix='as02-atomic-request-cxx-',dir='/dev/shm'))
    # Previous proof-bound harness stays unchanged; request types ONLY are
    # widened. The actual source retains the620-bit receive ABI independently.
    harness=old.harness().replace('ap_uint<620>','ap_uint<748>')
    (run/'atomic_request_base.hpp').write_text(harness)
    shutil.copy2(bench,run/'test.cpp')
    flags=['-std=c++17','-O0','-pthread','-Wno-unknown-pragmas','-ffunction-sections','-fdata-sections','-Wl,--gc-sections',
        '-DFNS_DATA_WIDTH=64','-DFNS_ROCE_STACK_MAX_QPS=8','-D__VITIS_HLS__','-I'+str(run),
        '-I'+str(source/'adapter'),'-I'+str(source/'fns/hls'),'-I/home/user/amd/2025.2/Vitis/include']
    cmd=[shutil.which('g++-13'),*flags,str(run/'test.cpp'),str(source/'fns/hls/ib_transport_protocol/ib_utils.cpp'),
        str(source/'fns/hls/rocev2/rocev2.cpp'),'-o',str(ram/'test')]
    report=dict(scope=__doc__,pass_test=False,source_sha256=before,directory=str(run.relative_to(ROOT)),command=cmd,
        simulation_limit_seconds=30,full_top_CPP_compiled=False,generated_HLS_RTL=False,native_integration=False,
        hardware_verified=False,physical_peer_memory_connection_modeled=True,request_context_bits=748,SQ_bits=408)
    print(json.dumps(dict(directory=report['directory'],phase='compile',RAM_directory=str(ram))),flush=True)
    try:
        env=os.environ.copy();env['TMPDIR']=str(ram);start=time.monotonic()
        c=subprocess.run(cmd,capture_output=True,text=True,timeout=600,env=env)
        report['compile_seconds']=time.monotonic()-start;(run/'compile.log').write_text(c.stdout+c.stderr)
        if c.returncode:raise RuntimeError('Atomic-request full-top compile: '+str(run/'compile.log'))
        report['full_top_CPP_compiled']=True;report['RAM_artifact_sha256']={str(ram/'test'):digest(ram/'test')}
        print(json.dumps(dict(phase='runtime',compile_seconds=report['compile_seconds'])),flush=True)
        start=time.monotonic();r=subprocess.run([str(ram/'test')],capture_output=True,text=True,timeout=30)
        report['simulation_seconds']=time.monotonic()-start;(run/'simulation.log').write_text(r.stdout+r.stderr)
        if r.returncode:raise RuntimeError('Atomic-request actual consumers: '+str(run/'simulation.log'))
        rows=[json.loads(l.split(' ',1)[1])for l in r.stdout.splitlines()if l.startswith('ATOMIC_REQUEST_HLS ')]
        if len(rows)!=1 or not rows[0].get('pass_test'):raise ValueError('missing actual producer/consumer assertions')
        packets=[l.split(' ',2)[1:]for l in r.stdout.splitlines()if l.startswith('ATOMIC_REQUEST_WIRE ')]
        # Nine positive fresh requests, four actual replays, four negative
        # response-class/syndrome/length requests; full wire bytes asserted.
        if len(packets)!=17:raise ValueError('incomplete actual wire cases')
        if before!={n:digest(ROOT/n)for n in before}:raise ValueError('source changed during test')
        report.update(pass_test=True,summary=rows[0],wire_packets=packets,source_unchanged=True)
    except Exception as e:report['error']=str(e);raise
    finally:
        report['artifact_sha256']={str(x.relative_to(ROOT)):digest(x)for x in run.iterdir()if x.is_file()}
        with a.report.open('x')as f:f.write(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k]for k in ['pass_test','compile_seconds','simulation_seconds','summary']}))


if __name__=='__main__':main()
