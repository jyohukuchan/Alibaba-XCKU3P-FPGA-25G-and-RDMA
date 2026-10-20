#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual independent SQ/RQ/CQ/MR C; optional unedited native CQ snapshots.

Linux, pins/coherent DMA, controller MMIO and teardown hardware are explicit
models. This is not a loaded kernel, ib_device/provider or physical host.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import test_kernel_cq as original

ROOT,TESTS,KERNEL=original.ROOT,original.TESTS,original.KERNEL

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--native-report',type=Path);p.add_argument('--report',required=True,type=Path)
    p.add_argument('--immediate-native-report',type=Path)
    p.add_argument('--flush',action='store_true')
    a=p.parse_args()
    if a.report.exists():p.error('preserve previous evidence')
    if a.immediate_native_report and (a.native_report or a.flush):p.error('select one matched native profile')
    if a.flush and not a.native_report:p.error('flush bridge requires exact native cancellation proof')
    extra=[];cases=[('primitive_model',[])];native=None
    if a.immediate_native_report:
        native=json.loads(a.immediate_native_report.read_text())
        if not all(native.get(n)for n in ['pass_test','source_unchanged','actual_generated_HLS']):
            raise ValueError('current whole generated Immediate receive evidence required')
        if not all(t.get('actual_coherent_SQ_RQ')and t.get('actual_HLS_MAC_CQ')for t in native['tests'].values()):
            raise ValueError('actual independent native memory/MAC/CQ receipts required')
        for n,h in native['source_sha256'].items():
            if digest(ROOT/n)!=h:raise ValueError('native consumed source changed: '+n)
        run=ROOT/native['directory'];cases=[]
        for name in native['tests']:
            snapshots=[run/(name+'-'+n)for n in ['send-event1.hex','receive-event1.hex','send-event2.hex','receive-event2.hex']]
            args=snapshots+[run/(name+'-records.hex'),run/(name+'-receive-records.hex'),'immediate']
            cases.append((name,args));extra+=args[:-1]
            for snapshot in args[:-1]:
                if digest(snapshot)!=native['artifact_sha256'][str(snapshot.relative_to(ROOT))]:
                    raise ValueError('unedited native snapshot changed '+str(snapshot))
        extra+=[a.immediate_native_report.resolve()]
    elif a.native_report:
        native=json.loads(a.native_report.read_text())
        if not all(native.get(n)for n in ['pass_test','source_unchanged','actual_matched_generated_HLS','independent_physical_queues_enabled']):
            raise ValueError('current whole actual-generated independent queues evidence required')
        for n,h in native['source_sha256'].items():
            if digest(ROOT/n)!=h:raise ValueError('native consumed source changed: '+n)
        run=ROOT/native['directory'];cases=[]
        for name in ['posted','empty_then_post']:
            snapshots=[run/(name+'-'+n)for n in ['send-event1.hex','receive-event1.hex','send-event2.hex','receive-event2.hex']]
            args=snapshots+[run/'records.hex',run/'receive-records.hex'];cases.append((name,args));extra+=args
            if native.get('receive_cancellation_enabled'):
                cancel=[run/(name+'-'+n)for n in ['cancel-reply.hex','cancel-record.hex']]
                args+=cancel;extra+=cancel
                if a.flush:args.append('flush')
            elif a.flush:raise ValueError('native cancellation profile required for real flush proof')
        extra+=[a.native_report.resolve()]
    sources=original.SOURCES[:-1]+[TESTS/'kernel_independent_queues.c']
    inputs=sources+list(KERNEL.glob('*.h'))+[TESTS/n for n in ['kernel_cq_cases.c','kernel_cq_model.h',
        'kernel_sq_hw_cases.c','kernel_sq_hw_model.h','kernel_queue_model.h']]+extra+[Path(__file__).resolve()]
    before={str(x.relative_to(ROOT)):digest(x)for x in inputs}
    report=dict(scope=__doc__,pass_test=False,source_sha256=before,native_snapshots=bool(native),
        hardware_verified=False,ib_device_registered=False,real_kernel_primitives=False,
        controller_MMIO_pin_DMA_models=True,simulation_limit_seconds=10)
    try:
        with tempfile.TemporaryDirectory(prefix='as02-kernel-independent-')as directory:
            d=Path(directory)
            for name in original.original.HEADERS+['linux/io.h','linux/ktime.h','linux/lockdep.h','asm/processor.h',
                'linux/irq_work.h','linux/atomic.h','linux/workqueue.h','linux/jiffies.h']:
                h=d/'include'/name;h.parent.mkdir(parents=True,exist_ok=True);h.write_text('#include "kernel_cq_model.h"\n')
            cmd=['cc','-std=c11','-D_GNU_SOURCE','-D__KERNEL__','-O1','-g','-Wall','-Wextra','-Werror',
                '-pthread','-fsanitize=address,undefined','-fno-sanitize-recover=undefined',
                '-I',str(d/'include'),'-I',str(TESTS),'-I',str(KERNEL),'-include',str(TESTS/'kernel_cq_model.h'),
                *map(str,sources),'-Wl,--wrap=dma_alloc_coherent','-o',str(d/'cases')]
            start=time.monotonic();c=subprocess.run(cmd,capture_output=True,text=True,timeout=30)
            report.update(compile_seconds=time.monotonic()-start,compile_command=cmd)
            if c.returncode:raise RuntimeError(c.stdout+c.stderr)
            env=os.environ.copy();env['ASAN_OPTIONS']='detect_leaks=1:halt_on_error=1'
            report['tests']={}
            for name,args in cases:
                start=time.monotonic();r=subprocess.run([str(d/'cases'),*map(str,args)],
                    capture_output=True,text=True,env=env,timeout=10)
                report['tests'][name]=dict(seconds=time.monotonic()-start,output=r.stdout+r.stderr)
                if r.returncode:raise RuntimeError(r.stdout+r.stderr)
                rows=[json.loads(l.split(' ',1)[1])for l in r.stdout.splitlines()if l.startswith('KERNEL_INDEPENDENT_QUEUES_RESULT ')]
                if len(rows)!=1 or not rows[0]['pass_test'] or rows[0]['native_snapshots_unedited']!=bool(native):
                    raise ValueError('missing exact independent kernel queue result')
                if rows[0].get('native_cancel_reply_unedited')!=bool(native and native.get('receive_cancellation_enabled')):
                    raise ValueError('missing exact native cancellation proof bridge')
                if rows[0].get('native_receive_flush_WC')!=a.flush:raise ValueError('missing proved RECV flush WC')
                if rows[0].get('native_Immediate_receive_WC')!=bool(a.immediate_native_report):
                    raise ValueError('missing native Immediate WC mapping')
                report['tests'][name]['summary']=rows[0]
            if before!={n:digest(ROOT/n)for n in before}:raise ValueError('kernel/native consumed source changed')
            report.update(pass_test=True,source_unchanged=True)
    except Exception as e:report.update(error=str(e));raise
    finally:
        with a.report.open('x')as out:out.write(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k]for k in ['pass_test','compile_seconds','tests']}))

if __name__=='__main__':main()
