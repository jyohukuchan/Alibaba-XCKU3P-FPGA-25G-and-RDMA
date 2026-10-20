#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual Immediate RQ/MAC/CQC RTL -> unedited snapshots -> real kernel C WC.

Admitted wire placement, HLS receipt, physical visibility and MAC pins are
MODELS. Kernel primitives, coherent DMA and MMIO are models. NOT generated
HLS/native graph, actual data placement, Linux/provider or physical support.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import immediate_receive_cq_fixture as fixture
import test_kernel_cq as kernel

ROOT=fixture.ROOT;TESTS=ROOT/'rdma/rnic/tests';KERNEL=ROOT/'rdma/rnic/kernel'
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve previous evidence')
    sources=kernel.SOURCES[:-1]+[TESTS/'kernel_immediate_receive_cq.c']
    inputs=[*sources,*KERNEL.glob('*.h'),*fixture.SOURCES,Path(__file__).resolve(),Path(fixture.__file__).resolve(),
        Path(fixture.ack.__file__).resolve(),Path(fixture.cq.__file__).resolve(),TESTS/'test_receive_queue_rtl.py',
        TESTS/'kernel_sq_hw_cases.c',TESTS/'kernel_cq_model.h',TESTS/'kernel_sq_hw_model.h',TESTS/'kernel_queue_model.h']
    before={str(x.relative_to(ROOT)):digest(x)for x in inputs}
    run=Path(tempfile.mkdtemp(prefix='immediate-receive-cq-',dir=ROOT/'rdma/rnic/build'))
    (run/'tb.v').write_text(fixture.bench())
    _,_,_,ack=fixture.ack.native.case(True,True)
    for seq in range(1,9):
        packet=bytearray(ack);packet[37:40]=(0x987653+seq).to_bytes(3,'big');packet[41:44]=seq.to_bytes(3,'big')
        packet=fixture.ack.native.qp.main.response.repair(packet)
        frame=bytes.fromhex('b8830367c5d08af3fbb975310800')+packet
        (run/f'ack{seq}.hex').write_text(''.join(f'{int.from_bytes(frame[i:i+16].ljust(16,bytes(1)),"little"):032x}\n'for i in range(0,len(frame),16)))
    result=dict(scope=__doc__,pass_test=False,source_sha256=before,directory=str(run.relative_to(ROOT)),
        hardware_verified=False,generated_HLS_or_native_parent=False,actual_RQ_MAC_CQC_RTL=True,
        actual_kernel_CQ_SQ_MR_C=True,actual_Linux_provider_or_DMA=False,
        upstream_wire_core_visibility_MAC_pins_and_Linux_MMIO_models=True,simulation_limit_seconds=15)
    print(json.dumps(dict(directory=str(run),hardware_untouched=True,simulation_limit_seconds=15)),flush=True)
    try:
        command=['iverilog','-g2012','-s','tb','-o',str(run/'test.vvp'),str(run/'tb.v'),*map(str,fixture.SOURCES)]
        start=time.monotonic();c=subprocess.run(command,capture_output=True,text=True,timeout=30)
        result['RTL_compile_seconds']=time.monotonic()-start;(run/'compile.log').write_text(c.stdout+c.stderr)
        if c.returncode:raise RuntimeError('Immediate RQ/MAC/CQC compile failed: '+str(run/'compile.log'))
        start=time.monotonic();r=subprocess.run(['vvp',str(run/'test.vvp')],cwd=run,capture_output=True,text=True,timeout=15)
        result['RTL_simulation_seconds']=time.monotonic()-start;(run/'simulation.log').write_text(r.stdout+r.stderr)
        if r.returncode:raise RuntimeError('Immediate RQ/MAC/CQC failed: '+str(run/'simulation.log'))
        rows=[json.loads(l.split(' ',1)[1])for l in r.stdout.splitlines()if l.startswith('IMMEDIATE_RECEIVE_CQ ')]
        if len(rows)!=1 or not rows[0]['pass_test']:raise ValueError('missing actual RTL ownership assertions')
        result['RTL_summary']=rows[0]
        events=[run/f'event{seq}.hex'for seq in range(1,9)];snapshots={str(x.relative_to(ROOT)):digest(x)for x in events}
        for name in kernel.original.HEADERS+['linux/io.h','linux/ktime.h','linux/lockdep.h','asm/processor.h',
            'linux/irq_work.h','linux/atomic.h','linux/workqueue.h','linux/jiffies.h']:
            path=run/'include'/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('#include "kernel_cq_model.h"\n')
        command=['cc','-std=c11','-D_GNU_SOURCE','-D__KERNEL__','-O1','-g','-Wall','-Wextra','-Werror','-pthread',
            '-fsanitize=address,undefined','-fno-sanitize-recover=undefined','-I',str(run/'include'),'-I',str(TESTS),'-I',str(KERNEL),
            '-include',str(TESTS/'kernel_cq_model.h'),*map(str,sources),'-o',str(run/'kernel-test')]
        start=time.monotonic();c=subprocess.run(command,capture_output=True,text=True,timeout=30)
        result['kernel_C_compile_seconds']=time.monotonic()-start;(run/'kernel-compile.log').write_text(c.stdout+c.stderr)
        if c.returncode:raise RuntimeError('Immediate kernel C compile failed: '+str(run/'kernel-compile.log'))
        env=os.environ.copy();env['ASAN_OPTIONS']='detect_leaks=1:halt_on_error=1';result['kernel_tests']={}
        for mode in [0,1]:
            start=time.monotonic();r=subprocess.run([str(run/'kernel-test'),str(mode),*map(str,events)],capture_output=True,text=True,env=env,timeout=10)
            elapsed=time.monotonic()-start;(run/f'kernel{mode}.log').write_text(r.stdout+r.stderr)
            if r.returncode:raise RuntimeError('Immediate kernel C failed: '+str(run/f'kernel{mode}.log'))
            rows=[json.loads(l.split(' ',1)[1])for l in r.stdout.splitlines()if l.startswith('IMMEDIATE_KERNEL_CQ ')]
            if len(rows)!=1 or not rows[0]['pass_test']:raise ValueError('missing actual kernel WC/ref assertions')
            result['kernel_tests'][str(mode)]=dict(summary=rows[0],simulation_seconds=elapsed)
        if snapshots!={n:digest(ROOT/n)for n in snapshots}:raise ValueError('actual RTL event bytes were edited')
        if before!={n:digest(ROOT/n)for n in before}:raise ValueError('consumed source changed')
        result.update(pass_test=True,source_unchanged=True,actual_RTL_snapshots_unedited=True,event_sha256=snapshots)
    except Exception as e:result.update(error_type=type(e).__name__,error=str(e));raise
    finally:
        result['artifact_sha256']={str(x.relative_to(ROOT)):digest(x)for x in run.iterdir()if x.is_file()}
        with a.report.open('x')as f:f.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps({n:result[n]for n in ['pass_test','RTL_simulation_seconds','RTL_summary','kernel_tests']}))

if __name__=='__main__':main()
