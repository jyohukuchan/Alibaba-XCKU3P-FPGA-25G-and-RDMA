#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual full75-input parent/driver bootstrap, worker and close C under models.

Re-execute all36 unchanged parent scenarios on the paired FEC15/31 source.
Linux/threaded-workqueue/MMIO/certificate/IB-core/pins/DMA are explicit models;
no real registered Linux/native lifetime or hardware qualification.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import audit_segmented_receive as binding
import fatal_parent_kernel_models as models
import test_kernel_verbs as old

ROOT=binding.ROOT;TESTS=ROOT/'rdma/rnic/tests';digest=binding.digest


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve all earlier evidence')
    kernel,kid=binding.bindings('fatal-flush-kernel-build-001')
    if not kernel['pass_test']or kernel['actual_total_inputs']!=75 or not kernel['source_and_derived_inputs_unchanged']:
        raise ValueError('same actual complete75-input real-header build required')
    run=Path(tempfile.mkdtemp(prefix='fatal-flush-parent-graph-',dir=ROOT/'rdma/rnic/build'));private=run/'kernel';private.mkdir();model=run/'models';model.mkdir()
    for n in kernel['derived_sha256']:
        q=ROOT/n;rel=q.relative_to(ROOT/kernel['directory'])
        if len(rel.parts)==1 and q.suffix in ['.c','.h']:shutil.copy2(q,private/q.name)
    for n in ['kernel_queue_model.h','kernel_sq_hw_model.h','kernel_device_model.h']:
        shutil.copy2(TESTS/n,model/n)
    (model/'kernel_verbs_model.h').write_text(models.parent.verbs_header())
    (model/'kernel_cq_model.h').write_text(models.cq_header())
    (model/'kernel_atomic128_model.h').write_text(models.MODEL)
    graph_header=(TESTS/'kernel_native_graph_model.h').read_text()
    graph_header=models.once(graph_header,'#include "kernel_device_model.h"','#include "kernel_device_model.h"\n#include "kernel_atomic128_model.h"')
    graph_header=models.once(graph_header,'extern bool *model_parameter_enable_native_attach;',
        'extern bool *model_parameter_enable_native_attach;\nextern bool *model_parameter_enable_fatal_events;')
    (model/'kernel_native_graph_model.h').write_text(graph_header)
    (model/'kernel_sq_hw_cases.c').write_text(models.parent.sq_model())
    (model/'kernel_native_graph_cases.c').write_text(models.graph_model())
    shutil.copy2(TESTS/'kernel_fatal_parent_cases.c',model/'kernel_fatal_parent_cases.c')
    headers=old.original.HEADERS+['linux/io.h','linux/ktime.h','linux/lockdep.h','asm/processor.h',
        'linux/irq_work.h','linux/atomic.h','linux/workqueue.h','linux/jiffies.h','rdma/uverbs_ioctl.h',
        'linux/etherdevice.h','linux/netdevice.h','rdma/ib_user_verbs.h','linux/delay.h','linux/auxiliary_bus.h','linux/pci.h','mqnic.h']
    for n in headers:
        q=run/'include'/n;q.parent.mkdir(parents=True,exist_ok=True);q.write_text('#include "kernel_native_graph_model.h"\n')
    src=[private/q.name for q in old.SOURCES if q.parent==old.KERNEL]
    src += [private/n for n in ['wqe_atomic.c','verbs_atomic_wqe.c','wqe_zero.c','verbs_zero_wqe.c',
        'wqe_segmented.c','verbs_segmented_wqe.c','wqe_segmented_read.c','verbs_segmented_read_wqe.c',
        'wqe_segmented_immediate.c','verbs_segmented_immediate_wqe.c','wqe_segmented_receive.c','verbs_segmented_receive_wqe.c',
        'rnic_hw.c','device.c','native_attach.c','native_graph.c','mqnic_graph.c','fatal_io.c','fatal_verbs.c','fatal_parent.c']]
    src += [TESTS/'kernel_queue_model.c',model/'kernel_fatal_parent_cases.c']
    own=[Path(__file__).resolve(),Path(models.__file__).resolve(),Path(models.parent.__file__).resolve(),
        TESTS/'kernel_fatal_parent_cases.c',TESTS/'kernel_native_graph_cases.c',TESTS/'kernel_native_graph_model.h',
        TESTS/'kernel_verbs_model.h',TESTS/'kernel_cq_model.h',TESTS/'kernel_sq_hw_cases.c',*src,*private.glob('*.h'),*model.glob('*')]
    before={str(q.relative_to(ROOT)):digest(q)for q in dict.fromkeys(own)}
    r=dict(scope=__doc__,pass_test=False,directory=str(run.relative_to(ROOT)),source_sha256=before,evidence={'fatal-flush-kernel-build-001':kid},
        compile_limit_seconds=30,runtime_limit_seconds=10,actual_parent_driver_C_bodies=True,actual_running_kernel_execution=False,
        Linux_workqueue_MMIO_IB_core_certificate_pins_DMA_modeled=True,hardware_verified=False,full_board_timing=False,
        overall_goal_complete=False,hardware_or_default_actions=[],commit_or_push=False,tests={})
    try:
        cmd=['cc','-std=c11','-D_GNU_SOURCE','-D__KERNEL__','-O1','-g','-Wall','-Wextra','-Werror','-pthread',
            '-fsanitize=address,undefined','-fno-sanitize-recover=undefined','-I',str(run/'include'),'-I',str(model),'-I',str(private),
            '-include',str(model/'kernel_native_graph_model.h'),*map(str,src),'-o',str(run/'cases')]
        r['compiler_command']=cmd;start=time.monotonic()
        with(run/'compile.log').open('x')as f:c=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,timeout=30)
        r.update(compile_seconds=time.monotonic()-start,compile_exit=c.returncode)
        if c.returncode:raise ValueError('actual full parent/driver C model compile failed:'+str(run/'compile.log'))
        env=os.environ.copy();env['ASAN_OPTIONS']='detect_leaks=1:halt_on_error=1'
        cases=[('FATAL_PARENT'+str(n),[str(n)],'FATAL_PARENT_RESULT ')for n in range(16)]+\
            [('GRAPH'+str(n),['prior',str(n)],'NATIVE_GRAPH_RESULT ')for n in range(20)]
        for n,args,marker in cases:
            start=time.monotonic()
            with(run/(n+'.log')).open('x')as f:c=subprocess.run([str(run/'cases'),*args],stdout=f,stderr=subprocess.STDOUT,timeout=10,env=env)
            r['tests'][n]=dict(exit=c.returncode,seconds=time.monotonic()-start)
            if c.returncode:raise ValueError('actual parent/driver model assertions failed:'+n)
            rows=[json.loads(l.split(' ',1)[1])for l in(run/(n+'.log')).read_text().splitlines()if l.startswith(marker)]
            if len(rows)!=1 or not rows[0]['pass_test']:raise ValueError('actual parent/driver bounded summary absent:'+n)
            r['tests'][n]['summary']=rows[0]
        for n,h in before.items():
            if digest(ROOT/n)!=h:raise ValueError('actual consumed source changed:'+n)
        r.update(pass_test=True,source_unchanged=True,new_fatal_parent_cases=16,all20_original_graph_cases_retained=True,
            actual_parent_poll_to_QP_handler_and_threaded_stop_join=True,logical_poll_stop_never_graph_lifetime_release=True)
    except Exception as e:r.update(error_type=type(e).__name__,error=str(e));raise
    finally:
        r['artifact_sha256']={str(q.relative_to(ROOT)):digest(q)for q in run.iterdir()if q.is_file()}
        with a.report.open('x')as f:f.write(json.dumps(r,indent=2)+'\n')
    print(json.dumps(dict(pass_test=True,compile_seconds=r['compile_seconds'],cases=len(r['tests']),live_Linux=False)))


if __name__=='__main__':main()
