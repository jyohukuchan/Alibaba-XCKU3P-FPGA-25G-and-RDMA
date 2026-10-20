#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual native bootstrap/RNC MR adapters/queues/device code, short models.

Only register hardware, IB core/netdev and Linux primitives/pins/DMA are
modeled. Real rnic_hw.c and actual RNC command validation execute; no fake
successful MR hardware ops. NO physical bus binding, DMA or runtime proof.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import subprocess
import tempfile
import time
import test_kernel_verbs as old
ROOT,KERNEL,TESTS=old.ROOT,old.KERNEL,old.TESTS
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def no_core():resource.setrlimit(resource.RLIMIT_CORE,(0,0))
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True)
    p.add_argument('--immediate',action='store_true');a=p.parse_args()
    if a.report.exists():p.error('preserve evidence')
    sources=old.SOURCES[:-1]+[KERNEL/n for n in ['rnic_hw.c','device.c','native_attach.c','native_graph.c','mqnic_graph.c']]+[TESTS/'kernel_native_graph_cases.c']
    inputs=sources+list(KERNEL.glob('*.h'))+[TESTS/n for n in ['kernel_native_graph_model.h','kernel_device_model.h',
        'kernel_verbs_model.h','kernel_cq_model.h','kernel_sq_hw_model.h','kernel_queue_model.h','kernel_sq_hw_cases.c']]+[Path(__file__).resolve()]
    before={str(x.relative_to(ROOT)):digest(x)for x in inputs}
    report=dict(scope=__doc__,pass_test=False,source_sha256=before,simulation_limit_seconds=10,
        hardware_verified=False,real_IB_core=False,physical_bus_attached=False)
    try:
        with tempfile.TemporaryDirectory(prefix='as02-native-graph-')as directory:
            d=Path(directory)
            for name in old.original.HEADERS+['linux/io.h','linux/ktime.h','linux/lockdep.h','asm/processor.h',
                'linux/irq_work.h','linux/atomic.h','linux/workqueue.h','linux/jiffies.h','rdma/uverbs_ioctl.h',
                'linux/etherdevice.h','linux/netdevice.h','rdma/ib_user_verbs.h','linux/delay.h',
                'linux/auxiliary_bus.h','linux/pci.h','mqnic.h']:
                f=d/'include'/name;f.parent.mkdir(parents=True,exist_ok=True);f.write_text('#include "kernel_native_graph_model.h"\n')
            cmd=['cc','-std=c11','-D_GNU_SOURCE','-D__KERNEL__','-O1','-g','-Wall','-Wextra','-Werror','-pthread',
                '-fsanitize=address,undefined','-fno-sanitize-recover=undefined','-I',str(d/'include'),'-I',str(TESTS),
                '-I',str(KERNEL),'-include',str(TESTS/'kernel_native_graph_model.h'),*map(str,sources),'-o',str(d/'cases')]
            start=time.monotonic();c=subprocess.run(cmd,capture_output=True,text=True,timeout=30)
            report.update(compile_seconds=time.monotonic()-start,command=cmd)
            if c.returncode:raise RuntimeError(c.stdout+c.stderr)
            report['tests']={};env=os.environ.copy();env['ASAN_OPTIONS']='detect_leaks=1:halt_on_error=1'
            for n in range(20 if a.immediate else 19):
                start=time.monotonic();r=subprocess.run([str(d/'cases'),str(n)],capture_output=True,text=True,timeout=10,env=env,preexec_fn=no_core)
                report['tests'][n]=dict(seconds=time.monotonic()-start,output=r.stdout+r.stderr)
                if r.returncode:raise RuntimeError(r.stdout+r.stderr)
                rows=[json.loads(l.split(' ',1)[1])for l in r.stdout.splitlines()if l.startswith('NATIVE_GRAPH_RESULT ')]
                if len(rows)!=1 or not rows[0]['pass_test']:raise ValueError('missing actual graph assertions')
                report['tests'][n]['summary']=rows[0]
            if before!={n:digest(ROOT/n)for n in before}:raise ValueError('source changed')
            report.update(pass_test=True,source_unchanged=True)
    except Exception as e:report.update(error=str(e));raise
    finally:
        with a.report.open('x')as f:f.write(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k]for k in ['pass_test','compile_seconds','tests']}))
if __name__=='__main__':main()
