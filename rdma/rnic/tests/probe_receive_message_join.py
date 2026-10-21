#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Real HLS whole-receive consumer: two-QP interleave/owner/PSN/MSN failures.

Packet certificates are explicitly modeled on this unit boundary. Full
actual receive consumers are a separate44-mode execution, never replaced
by these unit inputs. No native DMA/MAC/CQ or physical claim.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import shutil
import subprocess
import tempfile
import time

ROOT=Path(__file__).resolve().parents[3]
def digest(p):
    with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def no_core():resource.setrlimit(resource.RLIMIT_CORE,(0,0))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True)
    p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve previous evidence')
    source=a.source.resolve();info=json.loads((source/'source.json').read_text())
    if info.get('HLS_top')!='rocev2_native_segmented_receive_top' or info.get('receive_buffer_max_bytes')!=1048576:
        raise ValueError('exact new complete source required')
    for n,h in info['derived_sources'].items():
        if digest(source/'fns'/n)!=h:raise ValueError('changed source:'+n)
    bench=ROOT/'rdma/rnic/hls/test_receive_message_join.cpp'
    inputs=[*source.rglob('*'),bench,Path(__file__).resolve()]
    before={str(n.relative_to(ROOT)):digest(n)for n in inputs if n.is_file()}
    run=Path(tempfile.mkdtemp(prefix='receive-message-join-',dir=ROOT/'rdma/rnic/build'))
    ram=Path(tempfile.mkdtemp(prefix='as02-receive-message-join-',dir='/dev/shm'));shutil.copy2(bench,run/'test.cpp')
    command=[shutil.which('g++-13'),'-std=c++17','-O0','-Wno-unknown-pragmas','-DFNS_DATA_WIDTH=64',
        '-DFNS_ROCE_STACK_MAX_QPS=8','-D__VITIS_HLS__','-I'+str(source/'adapter'),'-I'+str(source/'fns/hls'),
        '-I/home/user/amd/2025.2/Vitis/include',str(run/'test.cpp'),'-o',str(ram/'test')]
    result=dict(scope=__doc__,pass_test=False,directory=str(run.relative_to(ROOT)),source_sha256=before,
        compile_command=command,compile_limit_seconds=600,case_limit_seconds=10,tests={},
        packet_proof_producer_modeled=True,native_integration=False,hardware_verified=False)
    try:
        env=os.environ.copy();env['TMPDIR']=str(ram);start=time.monotonic()
        c=subprocess.run(command,capture_output=True,text=True,env=env,timeout=600)
        result['compile_seconds']=time.monotonic()-start;(run/'compile.log').write_text(c.stdout+c.stderr)
        if c.returncode:raise ValueError('actual HLS join compile failed:'+str(run/'compile.log'))
        for mode in ['positive',*[str(n)for n in range(17)]]:
            start=time.monotonic();c=subprocess.run([str(ram/'test'),*([]if mode=='positive'else[mode])],
                capture_output=True,text=True,timeout=10,preexec_fn=no_core)
            (run/(mode+'.log')).write_text(c.stdout+c.stderr)
            result['tests'][mode]=dict(exit=c.returncode,seconds=time.monotonic()-start)
            marker='RECEIVE_MESSAGE_JOIN 'if mode=='positive'else'RECEIVE_MESSAGE_JOIN_NEGATIVE '+mode
            if c.returncode or marker not in c.stdout:raise ValueError('actual HLS consumer failed:'+str(run/(mode+'.log')))
        if any(digest(ROOT/n)!=h for n,h in before.items()):raise ValueError('source changed during test')
        result.update(pass_test=True,source_unchanged=True,all18_cases=True)
    except Exception as e:result.update(error_type=type(e).__name__,error=str(e));raise
    finally:
        result['artifact_sha256']={str(n.relative_to(ROOT)):digest(n)for n in run.iterdir()if n.is_file()}
        result['RAM_artifact_sha256']={str(n):digest(n)for n in ram.iterdir()if n.is_file()}
        with a.report.open('x')as f:f.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(pass_test=True,cases=len(result['tests']),compile_seconds=result['compile_seconds'],
        maximum_case_seconds=max(t['seconds']for t in result['tests'].values()))))


if __name__=='__main__':main()
