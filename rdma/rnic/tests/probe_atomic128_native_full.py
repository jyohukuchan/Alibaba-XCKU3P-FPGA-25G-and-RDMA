#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Fresh full128 native CAS/FADD requester and mixed responder regressions.

Actual generated HLS/PCIe/SQC/MR/PTE/guard/result DMA/fence/replay/CQ.
Atomic requester and responder use actual XGMII/FCS/SFD/CDC MAC receipts.
Host/root/peer/PHY/PTP inputs are models; ordinary READ/Immediate retains
MAC-pin model. Two-state, <=30s/case; no kernel/physical/timing signoff.
Feature compilation <=1200s. No prior test result or executable is reused.
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
import atomic128_native_sources as source
import atomic128_native_fixture as fixture
import atomic_native_full_oracle as responder
import probe_immediate_native_request as tool
from check_immediate_native_elaboration import FEATURES

ROOT=source.ROOT;digest=source.digest


def verify(output,records,request,opcode,immediate,run):
    rows=[json.loads(l.split(' ',1)[1])for l in output.splitlines()if l.startswith('NATIVE_RNIC_RESULT ')]
    if len(rows)!=1 or not rows[0]['pass_test']or rows[0]['HLS_model']or not rows[0]['CQ_committed']:
        raise ValueError('actual native requester CQ proof absent')
    summary=rows[0];length=8 if opcode in [7,8]else 65
    if summary['opcode']!=opcode or summary['payload_bytes']!=length:raise ValueError('wrong actual operation')
    # Existing byte-exact requester/replay/issued-PSN oracle (not test results).
    wire=fixture.old.old.old.verify(output,request,opcode)
    if opcode in [7,8]:
        wire['payload_bytes']=0;wire['result_bytes']=8
        actual=fixture.link.frames(output)
        expected=bytes.fromhex('b8830367c5d08af3fbb975310800')+request
        if actual!=[(0x2001,expected),(0x2002,expected)]:raise ValueError('actual Atomic MAC FCS/SFD/CDC/replay bytes')
        wire.update(actual_XGMII_frames=[dict(tag=t,frame_hex=f.hex())for t,f in actual],
            physical_MAC_receipt_model=False)
    else:wire['physical_MAC_receipt_model']=True
    event=[int(l,16)for l in(run/'request-event.hex').read_text().splitlines()]
    r=records[0]
    def get(n,w):return int.from_bytes(r[n:n+w],'little')
    values=[(64,get(0,8)),(64,get(8,8)),(64,get(56,8)),(24,2),(16,17),(16,1),
        (16,opcode),(16,get(46,2)),(32,length),(32,get(36,4)),(64,get(16,8)),(64,0x210),
        (64,get(24,8)),(32,get(40,4)),(20,3)]
    owner=0
    for width,value in values:owner=(owner<<width)|value
    owner|=immediate<<588;owner|=get(64,8)<<620;owner|=get(72,8)<<684
    wanted=[1,15,0,0x89abcdef,0xfedcba98]+[((owner&((1<<620)-1))>>(i*32))&0xffffffff for i in range(20)]
    wanted += [0,0,0,15,748,0xa0]+[(owner>>(620+i*32))&0xffffffff for i in range(4)]
    if event!=wanted:raise ValueError('independent full CQ header/legacy padding/notification/Atomic operand oracle')
    return dict(summary=summary,wire=wire,actual_C128_codec=True,
        full748_bit_CQ_owner=f'{owner:0187x}',CQ_snapshot_sha256=digest(run/'request-event.hex'))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ['hls-build','native-hls-report','owned-hls-report','request-hls-report','elaboration-report','report']:
        p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args()
    if a.report.exists():p.error('preserve prior evidence')
    if shutil.disk_usage(ROOT).free<1024**3:raise RuntimeError('unchanged fresh native1GiB guard')
    if shutil.disk_usage('/dev/shm').free<4*1024**3:raise RuntimeError('RAM compile4GiB guard')
    evidence=json.loads(a.elaboration_report.read_text())
    if not evidence.get('pass_test')or evidence.get('requester_owner_bits')!=748 or evidence.get('SQ_bits')!=408:
        raise ValueError('matched complete graph elaboration required')
    for n,h in evidence['source_sha256'].items():
        if digest(ROOT/n)!=h:raise ValueError('elaboration source changed: '+n)
    run=Path(tempfile.mkdtemp(prefix='atomic128-native-full-',dir=ROOT/'rdma/rnic/build'))
    obj=Path(tempfile.mkdtemp(prefix='as02-atomic128-native-obj-',dir='/dev/shm'))
    ram=Path(tempfile.mkdtemp(prefix='as02-atomic128-native-artifacts-',dir='/dev/shm'))
    report=dict(scope=__doc__,pass_test=False,directory=str(run.relative_to(ROOT)),compile_directory=str(obj),
        RAM_artifact_directory=str(ram),actual_generated_HLS=True,actual_complete_native_graph=True,
        two_state_simulation=True,hardware_verified=False,standard_API_runtime=False,full_board_timing=False,
        physical_host_root_peer_PHY_PTP_inputs_modeled=True,simulation_limit_seconds=30,compile_limit_seconds=1200,
        both_global_drains_zero=True,default_hardware_changed=False,tests={})
    try:
        src,data,before=source.sources(a.hls_build.resolve(),a.native_hls_report.resolve(),
            a.owned_hls_report.resolve(),a.request_hls_report.resolve(),run)
        src=list(dict.fromkeys([*src,*fixture.link.SOURCES]));(run/'tb.v').write_text(fixture.bench())
        helpers=[Path(m.__file__).resolve()for m in list(sys.modules.values())if getattr(m,'__file__',None)and
            (Path(m.__file__).resolve().is_relative_to(ROOT/'rdma/rnic/tests')or
             Path(m.__file__).resolve().is_relative_to(ROOT/'rdma/rnic/fpga'))]
        own=[*src,*helpers,Path(__file__).resolve(),a.elaboration_report.resolve(),run/'tb.v',
            *[ROOT/'rdma/rnic/kernel'/n for n in ['wqe.c','wqe.h','wqe_atomic.c','wqe_atomic.h']]]
        before.update({str(p.relative_to(ROOT)):digest(p)for p in own});report['source_sha256']=before
        (run/'atomic-input.hex').write_text(fixture.old.fixtures())
        for p in data:shutil.copy2(p,run/p.name)
        # Fail on ANY port truncation/padding in the actual complete bench.
        cmd=['iverilog','-g2012','-s','tb','-o',str(ram/'tb.vvp'),str(run/'tb.v'),*map(str,src)]
        start=time.monotonic();c=subprocess.run(cmd,capture_output=True,text=True,timeout=180)
        (run/'elaborate.log').write_text(c.stdout+c.stderr)
        report.update(bench_elaborate_command=cmd,bench_elaborate_seconds=time.monotonic()-start)
        if c.returncode or any('expects'in l and 'bits'in l for l in c.stderr.splitlines()):
            raise ValueError('full bench elaboration/width mismatch: '+str(run/'elaborate.log'))
        command=[str(tool.TOOL),'--binary','--timing','--top-module','tb','-Wno-fatal','-j','4',
            '--output-split','20000','--output-split-cfuncs','0','--output-groups','0','-CFLAGS','-O0',
            '--Mdir',str(obj),str(run/'tb.v'),*map(str,src)]
        report['compile_command']=command;env=os.environ.copy()
        env['TMPDIR']='/dev/shm/as02-native-compiler-tmp-QYQsVyT5'
        print(json.dumps(dict(directory=str(run),compile_directory=str(obj),compile_limit_seconds=1200)),flush=True)
        start=time.monotonic()
        with(run/'compile.log').open('x')as log:
            c=subprocess.run(command,cwd=run,stdout=log,stderr=subprocess.STDOUT,env=env,timeout=1200)
        report.update(compilation_seconds=time.monotonic()-start,compile_exit=c.returncode)
        if c.returncode:raise ValueError('actual full native compilation failed: '+str(run/'compile.log'))
        shutil.copy2(obj/'Vtb',ram/'Vtb')
        report.update(frozen_binary_path=str(ram/'Vtb'),binary_sha256=digest(ram/'Vtb'))
        cases=[('CAS',7,0,['+CAS']),('FADD',8,0,['+FADD']),('READ',2,0,[]),
            ('SEND_IMM',5,0x89abcdef,['+SEND_IMM','+IMM=89abcdef']),
            ('ATOMIC_MIXED',2,0,['+ATOMIC_ONLY'])]
        for name,opcode,immediate,args in cases:
            words,records,request=fixture.variant(opcode,immediate)
            inputs={'input.hex':''.join(f'{w:x}\n'for w in words),
                'records.hex':''.join(f'{int.from_bytes(r,"little"):0256x}\n'for r in records)}
            for n,t in inputs.items():(run/n).write_text(t);(run/(name+'-'+n)).write_text(t)
            start=time.monotonic()
            with(run/(name+'.log')).open('x')as log:
                c=subprocess.run([str(ram/'Vtb'),*args],cwd=run,stdout=log,stderr=subprocess.STDOUT,
                    timeout=30,preexec_fn=tool.no_core)
            result=dict(seconds=time.monotonic()-start,exit=c.returncode,
                runtime_input_sha256={n:digest(run/n)for n in inputs});report['tests'][name]=result
            if c.returncode:raise ValueError(name+' native runtime failed: '+str(run/(name+'.log')))
            output=(run/(name+'.log')).read_text()
            result.update(responder.verify(output)if name=='ATOMIC_MIXED'else verify(output,records,request,opcode,immediate,run))
            if name!='ATOMIC_MIXED':shutil.copy2(run/'request-event.hex',run/(name+'-event.hex'))
            print(json.dumps(dict(case=name,pass_test=True,seconds=result['seconds'])),flush=True)
        for n,h in before.items():
            if digest(ROOT/n)!=h:raise ValueError('consumed source changed: '+n)
        report.update(pass_test=True,source_unchanged=True)
    except Exception as e:report.update(error_type=type(e).__name__,error=str(e));raise
    finally:
        report['artifact_sha256']={str(p.relative_to(ROOT)):digest(p)for p in run.iterdir()if p.is_file()}
        report['RAM_artifact_sha256']={str(p):digest(p)for p in ram.iterdir()if p.is_file()}
        with a.report.open('x')as f:f.write(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(pass_test=True,compilation_seconds=report['compilation_seconds'],
        tests={n:v['seconds']for n,v in report['tests'].items()})),flush=True)


if __name__=='__main__':main()

