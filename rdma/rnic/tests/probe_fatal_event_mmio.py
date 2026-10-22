#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Retained fatal-event RTL/register readback/C decoder using real recorded seeds.

The producer and C MMIO/delivery are MODELS. No live native wiring, Linux verbs
callbacks, error WC, QP recovery/STOP/global drain/unpin or hardware proof.
"""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import audit_segmented_receive as binding

ROOT=binding.ROOT;digest=binding.digest


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve all previous evidence')
    native,nid=binding.bindings('write-abort-scheduled-mac-native-full-001')
    if native['pass_test']or native['tests']['LARGE_SEND_IMM']['exit']!=-6:
        raise ValueError('original incomplete native40 remains a failed regression')
    files=[ROOT/'rdma/rnic/rtl/rocev2_fatal_event_mmio.v',ROOT/'external/corundum/fpga/lib/axi/rtl/axil_reg_if.v',
        ROOT/'external/corundum/fpga/lib/axi/rtl/axil_reg_if_rd.v',ROOT/'external/corundum/fpga/lib/axi/rtl/axil_reg_if_wr.v',
        ROOT/'rdma/rnic/kernel/fatal_io.c',ROOT/'rdma/rnic/kernel/fatal_io.h',ROOT/'rdma/rnic/kernel/fatal_regs.h',
        ROOT/'rdma/rnic/kernel/mr_contract.h',ROOT/'rdma/rnic/tests/test_fatal_io.c',
        ROOT/'rdma/rnic/tests/tb_fatal_event_mmio.v',Path(__file__).resolve()]
    run=Path(tempfile.mkdtemp(prefix='fatal-event-mmio-',dir=ROOT/'rdma/rnic/build'))
    ram=Path(tempfile.mkdtemp(prefix='as02-fatal-event-mmio-',dir='/dev/shm'));seeds={}
    for i,name in enumerate(['LARGE_RX_WRITE_FATAL_ACCESS','LARGE_RX_WRITE_FATAL_PARTIAL']):
        q=ROOT/native['directory']/(name+'-selected.hex');value=int(q.read_text().strip(),16)
        if value!=int(native['tests'][name]['full_selected1000'],16):raise ValueError('every recorded native certificate bit required')
        files.append(q);seeds[name]=f'{value:0250x}'
        (run/('seed'+str(i)+'.hex')).write_text(''.join(f'{(value>>(32*j))&0xffffffff:08x}\n'for j in range(32)))
    before={str(q.relative_to(ROOT)):digest(q)for q in files}
    r=dict(scope=__doc__,pass_test=False,directory=str(run.relative_to(ROOT)),source_sha256=before,
        native_record_evidence=nid,actual_recorded_native_selected1000=seeds,clock_ns=4,
        RTL_compile_limit_seconds=10,runtime_limit_seconds=10,C_compile_limit_seconds=30,cycle_limit=100000,
        four_state=True,live_native_wiring=False,kernel_callbacks_or_standard_verbs=False,
        error_CQ_QP_STOP_global_drain_unpin=False,hardware_verified=False,full_board_timing=False,
        hardware_or_default_actions=[],commit_or_push=False,tests={})
    try:
        cmd=['iverilog','-g2012','-s','tb','-o',str(ram/'test'),str(files[9]),*[str(q)for q in files[:4]]]
        r['RTL_compile_command']=cmd;start=time.monotonic()
        with(run/'RTL-compile.log').open('x')as f:c=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,timeout=10)
        r['RTL_compile_seconds']=time.monotonic()-start
        if c.returncode:raise ValueError('fatal-event actual RTL compile failed')
        for mode in range(11):
            start=time.monotonic()
            with(run/(str(mode)+'.log')).open('x')as f:c=subprocess.run(['vvp',str(ram/'test'),'+MODE='+str(mode)],cwd=run,stdout=f,stderr=subprocess.STDOUT,timeout=10)
            r['tests'][str(mode)]=dict(exit=c.returncode,seconds=time.monotonic()-start)
            if c.returncode:raise ValueError('fatal-event actual RTL assertions failed mode'+str(mode))
            lines=[json.loads(l.split(' ',1)[1])for l in(run/(str(mode)+'.log')).read_text().splitlines()if l.startswith('FATAL_MMIO_RESULT ')]
            if len(lines)!=1 or not lines[0]['pass_test']:raise ValueError('actual bounded RTL summary required')
            r['tests'][str(mode)]['summary']=lines[0]
        for i,name in enumerate(seeds):
            words=[int(l,16)for l in(run/('readback-'+str(i)+'.hex')).read_text().splitlines()]
            if len(words)!=32 or sum(v<<(32*j)for j,v in enumerate(words))!=int(seeds[name],16):
                raise ValueError('actual AXI register readback must retain every original native selected1000 bit')
        cmd=['gcc','-std=gnu11','-O2','-Wall','-Wextra','-Werror','-I'+str(ROOT/'rdma/rnic/kernel'),
            str(files[8]),str(files[4]),'-o',str(ram/'C-test')];r['C_compile_command']=cmd;start=time.monotonic()
        with(run/'C-compile.log').open('x')as f:c=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,timeout=30)
        r['C_compile_seconds']=time.monotonic()-start
        if c.returncode:raise ValueError('fatal-event actual C reader compile failed')
        start=time.monotonic()
        with(run/'C-runtime.log').open('x')as f:c=subprocess.run([str(ram/'C-test'),str(run/'readback-0.hex'),str(run/'readback-1.hex')],stdout=f,stderr=subprocess.STDOUT,timeout=10)
        r['C_seconds']=time.monotonic()-start
        if c.returncode:raise ValueError('fatal-event C reader/decoder assertions failed on actual RTL readback')
        lines=[json.loads(l)for l in(run/'C-runtime.log').read_text().splitlines()if l.startswith('{')]
        if len(lines)!=1 or not lines[0]['pass_test']:raise ValueError('real C summary required')
        for n,h in before.items():
            if digest(ROOT/n)!=h:raise ValueError('original/actual source changed:'+n)
        r.update(pass_test=True,C_summary=lines[0],actual_1000bit_native_seed_RTL_MMIO_readback_C_chain=True,
            original_native_SEND_failure_preserved=True,notification_ACK_is_not_QP_rearm_or_drain=True)
    except Exception as e:r.update(error_type=type(e).__name__,error=str(e));raise
    finally:
        r['artifact_sha256']={str(q.relative_to(ROOT)):digest(q)for q in run.iterdir()if q.is_file()}
        r['RAM_artifact_sha256']={str(q):digest(q)for q in ram.iterdir()if q.is_file()}
        with a.report.open('x')as f:f.write(json.dumps(r,indent=2)+'\n')
    print(json.dumps(dict(pass_test=True,RTL_cases=11,C_assertions=r['C_summary']['assertions'],recorded_native_seeds=2,live_native=False)))


if __name__=='__main__':main()
