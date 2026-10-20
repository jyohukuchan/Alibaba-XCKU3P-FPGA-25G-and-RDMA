#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Real public ibv APIs/provider/installed libibverbs command serialization.

Only fake-fd ioctl/write replies model the kernel. Library ABI initialization
enumerates RDMA devices read-only, but opens NO real NIC context. No provider
installation, kernel load, FPGA, network or hardware runtime test occurs.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
ROOT=Path(__file__).resolve().parents[3]
PIN='bc6b4bc134532e952fe7f8efc251e1f89b912098'
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--rdma-core',type=Path,required=True);p.add_argument('--report',type=Path,required=True)
    p.add_argument('--immediate',action='store_true');a=p.parse_args()
    if a.report.exists():p.error('preserve evidence')
    core=a.rdma_core.resolve();revision=subprocess.check_output(['git','-C',str(core),'rev-parse','HEAD'],text=True).strip()
    if revision!=PIN:raise ValueError('unreviewed upstream revision')
    sources=[ROOT/'rdma/rnic/tests/provider_commands.c',ROOT/'rdma/rnic/provider/as02.c',Path(__file__).resolve()]
    before={str(x.relative_to(ROOT)):digest(x)for x in sources}
    report=dict(scope=__doc__,pass_test=False,source_sha256=before,rdma_core_commit=revision,provider_PABI=34,
        hardware_verified=False,provider_installed=False,kernel_loaded=False,real_NIC_opened=False,simulation_limit_seconds=10)
    try:
        with tempfile.TemporaryDirectory(prefix='as02-provider-commands-')as directory:
            run=Path(directory)
            command=['cc','-std=gnu11','-D_GNU_SOURCE','-Wall','-Wextra','-Werror','-O1','-g',
                '-fsanitize=address,undefined','-fno-sanitize-recover=undefined',
                '-isystem',str(core/'build/include'),'-isystem',str(core),str(sources[0]),
                '-pthread','-Wl,-export-dynamic','-libverbs','-o',str(run/'cases')]
            start=time.monotonic();r=subprocess.run(command,capture_output=True,text=True,timeout=30)
            report.update(compile_seconds=time.monotonic()-start,command=command)
            if r.returncode:raise RuntimeError(r.stdout+r.stderr)
            env=os.environ.copy();env['ASAN_OPTIONS']='detect_leaks=1:halt_on_error=1'
            start=time.monotonic();r=subprocess.run([str(run/'cases')]+(['immediate']if a.immediate else[]),capture_output=True,text=True,env=env,timeout=10)
            report.update(simulation_seconds=time.monotonic()-start,output=r.stdout+r.stderr)
            if r.returncode:raise RuntimeError(r.stdout+r.stderr)
            rows=[json.loads(l.split(' ',1)[1])for l in r.stdout.splitlines()if l.startswith('PROVIDER_COMMANDS_RESULT ')]
            if len(rows)!=1 or not rows[0]['pass_test']:raise ValueError('missing actual API assertions')
            extra=[json.loads(l.split(' ',1)[1])for l in r.stdout.splitlines()if l.startswith('PROVIDER_IMMEDIATE_RESULT ')]
            if len(extra)!=1 or not extra[0]['pass_test']or extra[0]['profile1023']!=a.immediate:
                raise ValueError('missing matched Immediate provider assertions')
            if before!={n:digest(ROOT/n)for n in before}:raise ValueError('source changed')
            report.update(pass_test=True,source_unchanged=True,summary=rows[0],immediate_summary=extra[0])
    except Exception as e:report.update(error=str(e));raise
    finally:
        with a.report.open('x')as f:f.write(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k]for k in ['pass_test','compile_seconds','simulation_seconds','summary']}))
if __name__=='__main__':main()
