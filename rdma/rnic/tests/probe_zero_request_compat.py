#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""SAME new zero-request graph: prior owned Atomic service and Immediate TX/RX.

Execute prior consumer assertions unchanged except request620->748 and
namespacing the independent C++ test mains. Actual owned Atomic/MR/paged
memory RTL supplies service replies, never a Python success replacement.
Physical host descriptors/order and normal payload/peer remain models.
Not generated HLS RTL/native/MAC/CQ/standard API/physical/timing qualification.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

import probe_atomic_owned as old
from probe_zero_request_hls import ROOT,digest,harness
import probe_zero_request_hls as zero


def bench():
    hls=ROOT/'rdma/rnic/hls'
    t='#include <vector>\n#include <string>\n#define main preceding_request_main\n#include "atomic_request_base.hpp"\n#undef main\n'
    for space,path,anchor in [('immediate_tx',hls/'test_immediate_request.cpp','static ap_uint<620> immediate_owner('),
                              ('immediate_rx',hls/'test_immediate_receive.cpp','template<int I> struct Endpoint {')]:
        text=path.read_text();text=text[text.index(anchor):].replace('ap_uint<620>','ap_uint<748>')
        text=text.replace(r'\"request_context_bits\":620',r'\"request_context_bits\":748')
        t+='namespace '+space+' {\n'+text+'\n}\n'
    text=old.bench();text=text[text.index('struct Endpoint {'):]
    pos=text.rfind('\n}');text=text[:pos]+'\n    return 0;'+text[pos:]
    t+='namespace owned_service {\n'+text+'\n}\n'
    return t+'int main(){assert(immediate_tx::main()==0);assert(immediate_rx::main()==0);return owned_service::main();}\n'


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True)
    p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve previous evidence')
    source=a.source.resolve();info=json.loads((source/'source.json').read_text())
    if not info.get('zero_length_requester')or info.get('request_context_bits')!=748 or info.get('SQ_bits')!=408:p.error('matched new full source required')
    sources=[*old.base.rtl.SOURCES,old.RTL]
    inputs=[*source.rglob('*'),*sources,Path(__file__).resolve(),Path(old.__file__).resolve(),
        Path(old.base.__file__).resolve(),Path(old.base.rtl.__file__).resolve(),Path(old.base.rtl.paged.__file__).resolve(),
        old.base.BENCH,old.base.TEMPLATE,ROOT/'rdma/rnic/hls/test_immediate_request.cpp',
        ROOT/'rdma/rnic/hls/test_immediate_receive.cpp',ROOT/'rdma/rnic/tests/probe_atomic_request_hls.py',Path(zero.__file__).resolve(),
        *list((ROOT/'rdma/rnic/hls').glob('*transport.py'))]
    before={str(x.relative_to(ROOT)):digest(x)for x in inputs if x.is_file()}
    run=Path(tempfile.mkdtemp(prefix='zero-request-compat-',dir=ROOT/'rdma/rnic/build'))
    ram=Path(tempfile.mkdtemp(prefix='as02-zero-request-compat-',dir='/dev/shm'))
    (run/'atomic_request_base.hpp').write_text(harness())
    (run/'test.cpp').write_text(bench());(run/'service.v').write_text(old.service_bench())
    report=dict(scope=__doc__,pass_test=False,source_sha256=before,directory=str(run.relative_to(ROOT)),
        simulation_limit_seconds=30,hardware_verified=False,generated_HLS_RTL=False,native_integration=False,
        full_top_CPP_compiled=False,shared_PSN_MSN=True,service_RTL_actual=True)
    processes=[];readers=[];hlog=[];slog=[]
    print(json.dumps(dict(directory=report['directory'],phase='compile')),flush=True)
    try:
        c=subprocess.run(['iverilog','-g2012','-s','tb','-o',str(ram/'service.vvp'),str(run/'service.v'),*map(str,sources)],
            capture_output=True,text=True,timeout=30);(run/'rtl-compile.log').write_text(c.stdout+c.stderr)
        if c.returncode:raise RuntimeError('actual owned service compile: '+str(run/'rtl-compile.log'))
        flags=['-std=c++17','-O0','-pthread','-Wno-unknown-pragmas','-ffunction-sections','-fdata-sections','-Wl,--gc-sections',
            '-DFNS_DATA_WIDTH=64','-DFNS_ROCE_STACK_MAX_QPS=8','-D__VITIS_HLS__','-I'+str(run),
            '-I'+str(source/'adapter'),'-I'+str(source/'fns/hls'),'-I/home/user/amd/2025.2/Vitis/include']
        cmd=[shutil.which('g++-13'),*flags,str(run/'test.cpp'),str(source/'fns/hls/ib_transport_protocol/ib_utils.cpp'),
            str(source/'fns/hls/rocev2/rocev2.cpp'),'-o',str(ram/'test')]
        report['command']=cmd;env=os.environ.copy();env['TMPDIR']=str(ram);start=time.monotonic()
        c=subprocess.run(cmd,capture_output=True,text=True,timeout=600,env=env)
        report['compile_seconds']=time.monotonic()-start;(run/'cpp-compile.log').write_text(c.stdout+c.stderr)
        if c.returncode:raise RuntimeError('new complete graph compatibility compile: '+str(run/'cpp-compile.log'))
        report['full_top_CPP_compiled']=True
        report['RAM_artifact_sha256']={str(x):digest(x)for x in [ram/'test',ram/'service.vvp']}
        print(json.dumps(dict(phase='runtime',compile_seconds=report['compile_seconds'])),flush=True)
        # Do not run the bounded RTL clock while the independent earlier
        # Immediate tests execute. Start the real service at its first job;
        # keep its original cycle deadline and all RTL assertions unchanged.
        hls=subprocess.Popen([str(ram/'test')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,bufsize=0)
        processes.append(hls);hr=old.base.Lines(hls);readers.append(hr);service=None;sr=None
        start=time.monotonic();deadline=start+30
        transfers=[];packets=[];receipts=[];cache={};value=0xf123456789abcdef;summaries={}
        while True:
            line=hr.read(deadline);hlog.append(line)
            if line.startswith('ATOMIC_SERVICE '):
                if service is None:
                    service=subprocess.Popen(['vvp',str(ram/'service.vvp')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,bufsize=0)
                    processes.append(service);sr=old.base.Lines(service);readers.append(sr)
                    while True:
                        line=sr.read(deadline);slog.append(line)
                        if line=='ATOMIC_SERVICE_READY':break
                    line=hlog[-1]
                word=line.split()[1];job=int(word,16);service.stdin.write((f'{job:0128x}'+'\n').encode())
                while True:
                    line=sr.read(deadline);slog.append(line)
                    if line.startswith('ATOMIC_COMPLETE '):break
                _,reply,executed,replayed,dropped,commands,memory=line.split();result=int(reply,16)
                if result>>248!=job>>368:raise ValueError('immutable owner changed')
                value=old.base.oracle(job&((1<<368)-1),result&((1<<248)-1),value,cache)
                if int(memory,16)!=value:raise ValueError('actual RAM disagrees with independent oracle')
                transfers.append(dict(request_hex=word,reply_hex=reply,executed=int(executed),replayed=int(replayed),
                    dropped=int(dropped),commands=int(commands),memory_hex=memory,oracle_pass=True))
                hls.stdin.write((reply+'\n').encode())
            elif line.startswith('ATOMIC_CORE_DONE '):receipts.append(line.split()[1])
            elif line.startswith('ATOMIC_WIRE '):packets.append(line.split()[1])
            elif line.startswith(('IMMEDIATE_REQUEST_HLS ','IMMEDIATE_RECEIVE_HLS ','ATOMIC_OWNED_HLS ')):
                key,data=line.split(' ',1);summaries[key]=json.loads(data)
                if key=='ATOMIC_OWNED_HLS':break
        hls.stdin.close();service.stdin.close()
        for proc in processes:
            proc.wait(timeout=max(0.1,deadline-time.monotonic()))
            if proc.returncode:raise RuntimeError('actual compatibility co-simulation process failed')
        report['simulation_seconds']=time.monotonic()-start
        if len(transfers)!=9 or len(receipts)!=9 or len(packets)!=11 or len(summaries)!=3 or not all(s['pass_test']for s in summaries.values()):
            raise ValueError('incomplete actual compatibility consumers')
        for t,d in zip(transfers,receipts):
            if int(d,16)&((1<<144)-1)!=int(t['request_hex'],16)>>368:raise ValueError('receipt lost owner')
        if before!={n:digest(ROOT/n)for n in before}:raise ValueError('source changed')
        report.update(pass_test=True,source_unchanged=True,summaries=summaries,transfers=transfers,wire_packets=packets,actual_core_receipts=receipts)
    except Exception as e:report['error']=str(e);raise
    finally:
        (run/'hls.log').write_text('\n'.join(hlog)+'\n');(run/'service.log').write_text('\n'.join(slog)+'\n')
        for reader in readers:reader.close()
        for proc in processes:
            if proc.poll()is None:proc.kill();proc.wait()
        report['artifact_sha256']={str(x.relative_to(ROOT)):digest(x)for x in run.iterdir()if x.is_file()}
        with a.report.open('x')as f:f.write(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k]for k in ['pass_test','compile_seconds','simulation_seconds','summaries']}),flush=True)


if __name__=='__main__':main()
