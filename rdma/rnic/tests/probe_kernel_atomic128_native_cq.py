#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual matched standard callbacks consume096 full-native RTL SQ/CQ bytes.

Do not rerun/relabel native tests. Verify exact successful sources/artifacts,
then consume each unedited real CQ snapshot and compare all128 posted bytes.
Linux/pins/DMA/MMIO/peer are still modeled; no live kernel/RTL coupling or
hardware proof. ASan/UBSan, <=10s each; malformed copies are labeled mutations.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import atomic128_kernel_models as model
import test_kernel_verbs as old
import sys

ROOT=old.ROOT;TESTS=old.TESTS;KERNEL=old.KERNEL
sys.path.insert(0,str(KERNEL))
import build_atomic128 as build
digest=build.digest;once=model.once


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ['kernel-build-report','native-report','report']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args()
    if a.report.exists():p.error('preserve evidence')
    native=json.loads(a.native_report.read_text());kernel=json.loads(a.kernel_build_report.read_text())
    if not native.get('pass_test')or not native.get('source_unchanged')or not kernel.get('pass_test'):
        raise ValueError('actual successful full-native and matched kernel required')
    for key in ['source_sha256','artifact_sha256','RAM_artifact_sha256']:build.old.checked(native[key],ROOT)
    frozen=ROOT/kernel['directory'];build.old.checked(kernel['source_sha256'],ROOT);build.old.checked(kernel['frozen_input_sha256'],frozen)
    native_run=ROOT/native['directory']
    run=Path(tempfile.mkdtemp(prefix='atomic128-kernel-native-cq-',dir=ROOT/'rdma/rnic/build'))
    k=run/'kernel';k.mkdir();m=run/'models';m.mkdir()
    for n in kernel['frozen_input_sha256']:
        if '/'not in n and Path(n).suffix in ['.c','.h']:shutil.copy2(frozen/n,k/n)
    for n in ['kernel_verbs_model.h','kernel_cq_model.h','kernel_sq_hw_model.h','kernel_queue_model.h']:
        shutil.copy2(TESTS/n,m/n)
    (m/'kernel_atomic128_model.h').write_text(model.MODEL)
    (m/'kernel_sq_hw_cases.c').write_text(model.sq_model())
    t=model.verbs_model()
    t=once(t,'    const u64 epochs[8]={0};',"    const u64 epochs[8]={[2]=0x9123456700000000ULL};")
    t=once(t,'    pd.ibpd.device=&vdev.ibdev;CHECK(!verbs->alloc_pd(&pd.ibpd,NULL));CHECK(pd.number==1);',
        '    vdev.next_pd=16;sq.next_cookie=0xfedcba9889abcdeeULL;\n'
        '    pd.ibpd.device=&vdev.ibdev;CHECK(!verbs->alloc_pd(&pd.ibpd,NULL));CHECK(pd.number==17);')
    (m/'kernel_verbs_cases.c').write_text(t);shutil.copy2(TESTS/'kernel_atomic128_native_cq.c',m/'kernel_atomic128_native_cq.c')
    headers=old.original.HEADERS+['linux/io.h','linux/ktime.h','linux/lockdep.h','asm/processor.h',
        'linux/irq_work.h','linux/atomic.h','linux/workqueue.h','linux/jiffies.h','rdma/uverbs_ioctl.h']
    for n in headers:
        h=run/'include'/n;h.parent.mkdir(parents=True,exist_ok=True);h.write_text('#include "kernel_atomic128_model.h"\n')
    sources=[k/p.name for p in old.SOURCES if p.parent==KERNEL]
    sources += [k/'wqe_atomic.c',k/'verbs_atomic_wqe.c',TESTS/'kernel_queue_model.c',m/'kernel_atomic128_native_cq.c']
    snapshots=[native_run/(n+'-'+kind+'.hex')for n in ['CAS','FADD','READ','SEND_IMM']for kind in ['event','records']]
    own=[*sources,*k.glob('*.h'),*m.glob('*'),*snapshots,Path(__file__).resolve(),Path(model.__file__).resolve(),
        Path(old.__file__).resolve(),TESTS/'kernel_atomic128_native_cq.c',TESTS/'kernel_sq_hw_cases.c',
        TESTS/'kernel_verbs_cases.c',a.native_report.resolve(),a.kernel_build_report.resolve(),
        *[TESTS/n for n in ['kernel_verbs_model.h','kernel_cq_model.h','kernel_sq_hw_model.h','kernel_queue_model.h']]]
    before={str(p.relative_to(ROOT)):digest(p)for p in dict.fromkeys(own)}
    report=dict(scope=__doc__,pass_test=False,directory=str(run.relative_to(ROOT)),source_sha256=before,
        actual_standard_C_bodies=True,native_RTL_snapshots_consumed=True,live_kernel_RTL_coupling=False,
        Linux_primitives_pins_DMA_MMIO_peer_models=True,hardware_verified=False,simulation_limit_seconds=10,tests={})
    try:
        command=['cc','-std=c11','-D_GNU_SOURCE','-D__KERNEL__','-O1','-g','-Wall','-Wextra','-Werror','-pthread',
            '-fsanitize=address,undefined','-fno-sanitize-recover=undefined','-I',str(run/'include'),'-I',str(m),'-I',str(k),
            '-include',str(m/'kernel_atomic128_model.h'),*map(str,sources),'-o',str(run/'cases')]
        report['compile_command']=command;start=time.monotonic()
        c=subprocess.run(command,capture_output=True,text=True,timeout=60);(run/'compile.log').write_text(c.stdout+c.stderr)
        report['compile_seconds']=time.monotonic()-start
        if c.returncode:raise ValueError('actual C compile: '+str(run/'compile.log'))
        env=os.environ.copy();env['ASAN_OPTIONS']='detect_leaks=1:halt_on_error=1'
        for name,op in [('CAS',7),('FADD',8),('READ',2),('SEND_IMM',5)]:
            for mutation in range(3):
                label=name+'-'+str(mutation);start=time.monotonic()
                r=subprocess.run([str(run/'cases'),str(native_run/(name+'-event.hex')),
                    str(native_run/(name+'-records.hex')),str(op),str(mutation)],capture_output=True,text=True,env=env,timeout=10)
                (run/(label+'.log')).write_text(r.stdout+r.stderr)
                item=dict(seconds=time.monotonic()-start,exit=r.returncode);report['tests'][label]=item
                if r.returncode:raise ValueError(label+' native CQ/actual C: '+str(run/(label+'.log')))
                rows=[json.loads(l.split(' ',1)[1])for l in r.stdout.splitlines()if l.startswith('KERNEL_ATOMIC128_NATIVE_CQ ')]
                if len(rows)!=1 or not rows[0]['pass_test']:raise ValueError('native callback assertion absent')
                item['summary']=rows[0]
        build.old.checked(before,ROOT)
        for key in ['source_sha256','artifact_sha256','RAM_artifact_sha256']:build.old.checked(native[key],ROOT)
        report.update(pass_test=True,source_unchanged=True)
    except Exception as e:report.update(error_type=type(e).__name__,error=str(e));raise
    finally:
        report['artifact_sha256']={str(p.relative_to(ROOT)):digest(p)for p in run.iterdir()if p.is_file()}
        with a.report.open('x')as f:f.write(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(pass_test=True,compile_seconds=report['compile_seconds'],cases=len(report['tests']))))


if __name__=='__main__':main()

