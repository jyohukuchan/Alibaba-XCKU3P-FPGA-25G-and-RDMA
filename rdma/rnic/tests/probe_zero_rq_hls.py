#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Fresh same-core zero RQ consumers and all prior zero/Atomic requesters.

Actual C++ top compiles; actual RX parser/empty EOF, ACK/MSN/PSN/retirement
consumers execute with peer/RQ/connection/memory boundary models. No native
RTL/DMA/MAC/CQ/Linux or HLS generation/timing/physical claim. <=30s runtime.
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
import probe_zero_request_hls as old

ROOT=old.ROOT;digest=old.digest;once=old.old.old.once


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True)
    p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve previous evidence')
    source=a.source.resolve();info=json.loads((source/'source.json').read_text())
    if info.get('HLS_top')!='rocev2_native_zero_rq_top'or not info.get('zero_RQ_SEND_and_Immediate')or \
       (info.get('request_context_bits'),info.get('SQ_bits'),info.get('receive_context_bits'))!=(748,408,620):
        p.error('matched complete zero RQ source required')
    hls=ROOT/'rdma/rnic/hls';bench=hls/'test_zero_rq.cpp';atomic=hls/'test_atomic_request.cpp';zero=hls/'test_zero_request.cpp';endpoint=hls/'test_immediate_receive.cpp'
    files=[*source.rglob('*'),bench,atomic,zero,endpoint,Path(__file__).resolve(),Path(old.__file__).resolve(),
        Path(old.old.__file__).resolve(),Path(old.old.old.__file__).resolve(),Path(old.old.old.base.__file__).resolve(),
        old.old.old.base.TEMPLATE,*list(hls.glob('*transport.py'))]
    before={str(p.relative_to(ROOT)):digest(p)for p in files if p.is_file()}
    run=Path(tempfile.mkdtemp(prefix='zero-rq-csim-',dir=ROOT/'rdma/rnic/build'))
    ram=Path(tempfile.mkdtemp(prefix='as02-zero-rq-cxx-',dir='/dev/shm'))
    harness='static bool zero_rq_ack_enabled=true;\n'+once(old.harness(),
        '        generate_exh<512,I>(', '        if(zero_rq_ack_enabled)generate_exh<512,I>(')
    (run/'atomic_request_base.hpp').write_text(harness)
    t=endpoint.read_text();t=t[t.index('template<int I> struct Endpoint {'):t.index('static ap_uint<620> request_owner(')]
    t=once(t,'void tick(bool retire=true)', 'void tick(bool retire=true,bool payload=true,bool tables=true)')
    t=once(t,'        h.tick();','        h.tick(true,payload,tables);')
    (run/'zero_rq_endpoint.hpp').write_text(t)
    (run/'atomic_request_prior.cpp').write_text(once(atomic.read_text(),'int main() {','int atomic_compat_main() {'))
    (run/'zero_request_prior.cpp').write_text(once(zero.read_text(),'int main() {','int previous_zero_request_main() {'))
    shutil.copy2(bench,run/'test.cpp')
    flags=['-std=c++17','-O0','-pthread','-Wno-unknown-pragmas','-ffunction-sections','-fdata-sections','-Wl,--gc-sections',
        '-DFNS_DATA_WIDTH=64','-DFNS_ROCE_STACK_MAX_QPS=8','-D__VITIS_HLS__','-I'+str(run),
        '-I'+str(source/'adapter'),'-I'+str(source/'fns/hls'),'-I/home/user/amd/2025.2/Vitis/include']
    cmd=[shutil.which('g++-13'),*flags,str(run/'test.cpp'),str(source/'fns/hls/ib_transport_protocol/ib_utils.cpp'),
        str(source/'fns/hls/rocev2/rocev2.cpp'),'-o',str(ram/'test')]
    report=dict(scope=__doc__,pass_test=False,source_sha256=before,directory=str(run.relative_to(ROOT)),command=cmd,
        simulation_limit_seconds=30,full_top_CPP_compiled=False,generated_HLS_RTL=False,native_integration=False,
        hardware_verified=False,peer_RQ_connection_memory_boundaries_modeled=True)
    print(json.dumps(dict(directory=report['directory'],phase='compile')),flush=True)
    try:
        env=os.environ.copy();env['TMPDIR']=str(ram);start=time.monotonic()
        c=subprocess.run(cmd,capture_output=True,text=True,timeout=600,env=env)
        report['compile_seconds']=time.monotonic()-start;(run/'compile.log').write_text(c.stdout+c.stderr)
        if c.returncode:raise ValueError('zero RQ full-top compile failed: '+str(run/'compile.log'))
        report.update(full_top_CPP_compiled=True,RAM_artifact_sha256={str(ram/'test'):digest(ram/'test')})
        start=time.monotonic();r=subprocess.run([str(ram/'test')],capture_output=True,text=True,timeout=30)
        report['simulation_seconds']=time.monotonic()-start;(run/'simulation.log').write_text(r.stdout+r.stderr)
        if r.returncode:raise ValueError('actual zero RQ consumers failed: '+str(run/'simulation.log'))
        summaries={}
        for marker in ['ATOMIC_REQUEST_HLS','ZERO_REQUEST_HLS','ZERO_RQ_HLS']:
            rows=[json.loads(l.split(' ',1)[1])for l in r.stdout.splitlines()if l.startswith(marker+' ')]
            if len(rows)!=1 or not rows[0].get('pass_test'):raise ValueError('missing actual '+marker)
            summaries[marker]=rows[0]
        receipts=[l for l in r.stdout.splitlines()if l.startswith('ZERO_RQ_RECEIPT ')]
        if len(receipts)!=6 or summaries['ZERO_RQ_HLS']['owner_and_EOF_negatives']!=6:raise ValueError('incomplete zero RQ tests')
        if before!={n:digest(ROOT/n)for n in before}:raise ValueError('consumed source changed')
        report.update(pass_test=True,source_unchanged=True,summaries=summaries,zero_RQ_receipts=receipts)
    except Exception as e:report.update(error_type=type(e).__name__,error=str(e));raise
    finally:
        report['artifact_sha256']={str(p.relative_to(ROOT)):digest(p)for p in run.iterdir()if p.is_file()}
        with a.report.open('x')as f:f.write(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k]for k in ['pass_test','compile_seconds','simulation_seconds','summaries']}))


if __name__=='__main__':main()
