#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Execute actual zero-aware standard SQ/CQ C with no zero-length MR reference.

Real running-header compile/link is a prerequisite. Userspace Linux primitive,
MMIO, coherent-DMA/pin and hardware completion models are explicit; not actual
Linux execution, real RTL proof, installed provider or hardware operation.
ASan/UBSan, <=10s each, one/few-queue functional cases only.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import zero_kernel_models as models
import atomic_access_kernel_models as access_models
import atomic128_kernel_models as prior_models
import test_kernel_verbs as old

ROOT=old.ROOT;TESTS=old.TESTS;KERNEL=old.KERNEL
sys.path.insert(0,str(KERNEL))
import build_zero as build
digest=build.digest


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--kernel-build-report',type=Path,required=True)
    p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve prior evidence')
    evidence=json.loads(a.kernel_build_report.read_text())
    if not evidence.get('pass_test')or evidence.get('module_load_performed'):raise ValueError('matching frozen kernel build required')
    frozen=ROOT/evidence['directory']
    build.old.checked(evidence['source_sha256'],ROOT);build.old.checked(evidence['frozen_input_sha256'],frozen)
    run=Path(tempfile.mkdtemp(prefix='zero-kernel-post-',dir=ROOT/'rdma/rnic/build'));private=run/'kernel';private.mkdir()
    model=run/'models';model.mkdir()
    for n in evidence['frozen_input_sha256']:
        src=frozen/n
        if '/'not in n and src.suffix in ['.c','.h']:shutil.copy2(src,private/n)
    for n in ['kernel_verbs_model.h','kernel_cq_model.h','kernel_sq_hw_model.h','kernel_queue_model.h']:
        shutil.copy2(TESTS/n,model/n)
    (model/'kernel_atomic128_model.h').write_text(models.MODEL)
    (model/'kernel_sq_hw_cases.c').write_text(models.sq_model())
    (model/'kernel_verbs_cases.c').write_text(models.verbs_model())
    legacy=(TESTS/'kernel_atomic128_post.c').read_text()
    legacy=build.candidate.once(legacy,'int main(int argc,char **argv)','int atomic128_post_main(int argc,char **argv)')
    (model/'kernel_atomic128_post.c').write_text(legacy)
    access=(TESTS/'kernel_atomic_access_post.c').read_text()
    access=build.candidate.once(access,'int main(int argc,char **argv)','int atomic_access_post_main(int argc,char **argv)')
    (model/'kernel_atomic_access_post.c').write_text(access)
    shutil.copy2(TESTS/'kernel_zero_post.c',model/'kernel_zero_post.c')
    headers=old.original.HEADERS+['linux/io.h','linux/ktime.h','linux/lockdep.h','asm/processor.h',
        'linux/irq_work.h','linux/atomic.h','linux/workqueue.h','linux/jiffies.h','rdma/uverbs_ioctl.h']
    for n in headers:
        h=run/'include'/n;h.parent.mkdir(parents=True,exist_ok=True);h.write_text('#include "kernel_atomic128_model.h"\n')
    src=[private/p.name for p in old.SOURCES if p.parent==KERNEL]
    src += [private/'wqe_atomic.c',private/'verbs_atomic_wqe.c',private/'wqe_zero.c',private/'verbs_zero_wqe.c',TESTS/'kernel_queue_model.c',model/'kernel_zero_post.c']
    own=[Path(__file__).resolve(),Path(models.__file__).resolve(),Path(old.__file__).resolve(),
        TESTS/'kernel_atomic128_post.c',TESTS/'kernel_atomic_access_post.c',TESTS/'kernel_zero_post.c',Path(access_models.__file__).resolve(),Path(prior_models.__file__).resolve(),TESTS/'kernel_sq_hw_cases.c',TESTS/'kernel_verbs_cases.c',a.kernel_build_report.resolve(),
        *[TESTS/n for n in ['kernel_verbs_model.h','kernel_cq_model.h','kernel_sq_hw_model.h','kernel_queue_model.h']],
        *src,*private.glob('*.h'),*model.glob('*')]
    before={str(p.relative_to(ROOT)):digest(p)for p in dict.fromkeys(own)}
    report=dict(scope=__doc__,pass_test=False,directory=str(run.relative_to(ROOT)),source_sha256=before,
        actual_standard_callbacks_and_CSR_C_bodies=True,actual_running_kernel_callback_execution=False,
        Linux_MMIO_DMA_pins_hardware_completion_models=True,actual_RTL_executed=False,
        hardware_verified=False,atomic_cap_advertised=False,simulation_limit_seconds=10,tests={})
    try:
        command=['cc','-std=c11','-D_GNU_SOURCE','-D__KERNEL__','-O1','-g','-Wall','-Wextra','-Werror','-pthread',
            '-fsanitize=address,undefined','-fno-sanitize-recover=undefined',
            '-I',str(run/'include'),'-I',str(model),'-I',str(private),
            '-include',str(model/'kernel_atomic128_model.h'),*map(str,src),'-o',str(run/'cases')]
        report['compiler_command']=command;start=time.monotonic()
        c=subprocess.run(command,capture_output=True,text=True,timeout=60);(run/'compile.log').write_text(c.stdout+c.stderr)
        report['compile_seconds']=time.monotonic()-start
        if c.returncode:raise ValueError('actual matched C bodies compile failed: '+str(run/'compile.log'))
        env=os.environ.copy();env['ASAN_OPTIONS']='detect_leaks=1:halt_on_error=1'
        cases=[('Zero'+str(n),[str(n)],'KERNEL_ZERO_POST ')for n in range(10)]
        cases += [('Access'+str(n),['prior',str(n)],'KERNEL_ATOMIC_ACCESS ')for n in range(8)]
        cases += [('Atomic'+str(n),['prior','prior',str(n)],'KERNEL_ATOMIC128_POST ')for n in range(14)]
        cases += [('Legacy'+str(n),['prior','prior','legacy',str(n)],'KERNEL_VERBS_RESULT ')for n in range(15)]
        for name,args,marker in cases:
            start=time.monotonic()
            r=subprocess.run([str(run/'cases'),*args],capture_output=True,text=True,env=env,timeout=10)
            (run/(name+'.log')).write_text(r.stdout+r.stderr)
            result=dict(seconds=time.monotonic()-start,exit=r.returncode);report['tests'][name]=result
            if r.returncode:raise ValueError(name+' failed: '+str(run/(name+'.log')))
            rows=[json.loads(l.split(' ',1)[1])for l in r.stdout.splitlines()if l.startswith(marker)]
            if len(rows)!=1 or not rows[0]['pass_test']:raise ValueError('actual callback proof absent '+name)
            result['summary']=rows[0]
        build.old.checked(before,ROOT);build.old.checked(evidence['frozen_input_sha256'],frozen)
        report.update(pass_test=True,source_unchanged=True,zero_cases=10,access_permission_cases=8,Atomic_and_geometry_cases=14,legacy_cases=15)
    except Exception as e:report.update(error_type=type(e).__name__,error=str(e));raise
    finally:
        report['artifact_sha256']={str(p.relative_to(ROOT)):digest(p)for p in run.iterdir()if p.is_file()}
        with a.report.open('x')as f:f.write(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(pass_test=True,compile_seconds=report['compile_seconds'],cases=len(report['tests']))))


if __name__=='__main__':main()
