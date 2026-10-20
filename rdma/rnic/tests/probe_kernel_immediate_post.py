#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual standard Immediate post_send/capability/CQ/MR code, modeled boundaries.

Real C callbacks and real CSR adapters under ASan/UBSan. All Linux/pin/DMA/
MMIO and memory/wire/core completion are explicit models, not RTL/hardware.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import test_kernel_verbs as old

ROOT,TESTS,KERNEL=old.ROOT,old.TESTS,old.KERNEL
digest=lambda p:__import__('hashlib').sha256(p.read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve evidence')
    run=Path(tempfile.mkdtemp(prefix='kernel-immediate-post-',dir=ROOT/'rdma/rnic/build'))
    sources=old.SOURCES[:-1]+[TESTS/'kernel_immediate_post.c']
    inputs=sources+list(KERNEL.glob('*.h'))+[TESTS/n for n in ['kernel_verbs_cases.c','kernel_verbs_model.h',
        'kernel_cq_model.h','kernel_sq_hw_model.h','kernel_queue_model.h','kernel_sq_hw_cases.c']]
    inputs += [Path(__file__).resolve(),Path(old.__file__).resolve(),Path(old.original.__file__).resolve()]
    before={str(x.relative_to(ROOT)):digest(x)for x in inputs}
    report=dict(scope=__doc__,pass_test=False,source_sha256=before,directory=str(run.relative_to(ROOT)),
        simulation_limit_seconds=10,actual_standard_callbacks=True,actual_Linux_provider=False,
        Linux_pin_DMA_MMIO_and_core_proofs_models=True,hardware_verified=False,tests={})
    try:
        with tempfile.TemporaryDirectory(prefix='as02-immediate-post-')as directory:
            d=Path(directory)
            for name in old.original.HEADERS+['linux/io.h','linux/ktime.h','linux/lockdep.h','asm/processor.h',
                'linux/irq_work.h','linux/atomic.h','linux/workqueue.h','linux/jiffies.h','rdma/uverbs_ioctl.h']:
                h=d/'include'/name;h.parent.mkdir(parents=True,exist_ok=True);h.write_text('#include "kernel_verbs_model.h"\n')
            cmd=['cc','-std=c11','-D_GNU_SOURCE','-D__KERNEL__','-O1','-g','-Wall','-Wextra','-Werror','-pthread',
                '-fsanitize=address,undefined','-fno-sanitize-recover=undefined','-I',str(d/'include'),
                '-I',str(TESTS),'-I',str(KERNEL),'-include',str(TESTS/'kernel_verbs_model.h'),*map(str,sources),'-o',str(d/'cases')]
            start=time.monotonic();c=subprocess.run(cmd,capture_output=True,text=True,timeout=30)
            report.update(compile_seconds=time.monotonic()-start,command=cmd)
            (run/'compile.log').write_text(c.stdout+c.stderr)
            if c.returncode:raise RuntimeError('Immediate actual callback compile failed: '+str(run/'compile.log'))
            env=os.environ.copy();env['ASAN_OPTIONS']='detect_leaks=1:halt_on_error=1'
            for n in range(9):
                start=time.monotonic();r=subprocess.run([str(d/'cases'),str(n)],capture_output=True,text=True,timeout=10,env=env)
                elapsed=time.monotonic()-start;(run/f'case{n}.log').write_text(r.stdout+r.stderr)
                if r.returncode:raise RuntimeError('Immediate callback case failed '+str(run/f'case{n}.log'))
                rows=[json.loads(l.split(' ',1)[1])for l in r.stdout.splitlines()if l.startswith('KERNEL_IMMEDIATE_POST ')]
                if len(rows)!=1 or not rows[0]['pass_test']:raise ValueError('missing actual assertions')
                report['tests'][str(n)]=dict(seconds=elapsed,summary=rows[0])
        for n,h in before.items():
            if digest(ROOT/n)!=h:raise ValueError('consumed source changed '+n)
        report.update(pass_test=True,source_unchanged=True)
    except Exception as e:report.update(error=str(e));raise
    finally:
        report['artifact_sha256']={str(x.relative_to(ROOT)):digest(x)for x in run.iterdir()if x.is_file()}
        with a.report.open('x')as f:f.write(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k]for k in ['pass_test','compile_seconds','tests']}))


if __name__=='__main__':main()
