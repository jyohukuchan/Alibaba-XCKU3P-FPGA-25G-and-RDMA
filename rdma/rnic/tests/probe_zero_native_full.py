#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Fresh complete native zero requester plus all Atomic-access regressions.

Actual generated zero HLS, SQ/PCIe/MR/PTE/response/replay/MAC/CQ graph.
All five zero operations use actual XGMII/FCS/SFD/CDC, including SEND MAC
minimum padding. Physical host/root/peer/PHY/PTP remain modeled. Each test
<=30s; feature compilation <=1200s. No Linux/board/timing qualification.
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
import zero_native_sources as source
import zero_native_fixture as fixture
import probe_atomic128_native_full as prior
import atomic_access_native_oracle as access
import atomic_native_full_oracle as responder
import native_request_cq_fixture as wire
import probe_immediate_native_request as tool

ROOT=source.ROOT;digest=source.digest


def verify_zero(output,records,request,opcode,immediate,run):
    def row(prefix):
        values=[json.loads(l.split(' ',1)[1])for l in output.splitlines()if l.startswith(prefix+' ')]
        if len(values)!=1:raise ValueError('one actual '+prefix+' result required')
        return values[0]
    summary=row('NATIVE_RNIC_RESULT');zero=row('ZERO_NATIVE_RESULT')
    wanted=dict(pass_test=True,local_MR_queries=0,memory_commands=0,memory_status=0,actual_MAC_SFD=2)
    if zero!=wanted or not summary.get('pass_test')or summary['opcode']!=opcode or summary['payload_bytes']!=0 or \
       summary['HLS_model']or not summary['CQ_committed']or \
       [summary[n]for n in ['descriptors','read_TLPs','write_TLPs','fences']]!=[1,1,0,0]:
        raise ValueError('zero native no-data/owner/CQ proof mismatch')
    # Existing independent full IP/UDP/BTH/RETH/Immediate/ICRC/replay/owner
    # oracle is byte exact and does not call the legacy nonempty READ decoder.
    result=wire.verify(output,request,opcode);result['payload_bytes']=0
    expected=(bytes.fromhex('b8830367c5d08af3fbb975310800')+request).ljust(60,bytes(1))
    frames=fixture.link.frames(output)
    if frames!=[(0x2001,expected),(0x2002,expected)]:raise ValueError('actual zero XGMII/FCS/padding/replay mismatch')
    r=records[0];get=lambda n,w:int.from_bytes(r[n:n+w],'little')
    fields=[(64,get(0,8)),(64,get(8,8)),(64,get(56,8)),(24,2),(16,17),(16,1),
        (16,opcode),(16,get(46,2)),(32,0),(32,0),(64,0),(64,0),(64,get(24,8)),(32,get(40,4)),(20,3)]
    owner=0
    for width,value in fields:owner=(owner<<width)|value
    owner|=immediate<<588
    wanted=[1,15,0,0x89abcdef,0xfedcba98]+[(owner>>(i*32))&0xffffffff for i in range(20)]
    wanted += [0,0,0,15,748,0xa0]+[0]*4
    event=[int(l,16)for l in(run/'request-event.hex').read_text().splitlines()]
    if event!=wanted:raise ValueError('independent zero full748 CQ byte/owner/notification oracle')
    return dict(summary=summary,zero=zero,wire=result,actual_C128_zero_codec=True,
        full748_bit_CQ_owner=f'{owner:0187x}',CQ_snapshot_sha256=digest(run/'request-event.hex'),
        actual_XGMII_frames=[dict(tag=t,frame_hex=f.hex())for t,f in frames],physical_MAC_receipt_model=False)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ['hls-build','native-hls-report','owned-hls-report','request-hls-report','elaboration-report','report']:
        p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args()
    if a.report.exists():p.error('preserve prior evidence')
    if shutil.disk_usage(ROOT).free<1024**3:raise RuntimeError('unchanged fresh native1GiB guard')
    if shutil.disk_usage('/dev/shm').free<4*1024**3:raise RuntimeError('RAM compile4GiB guard')
    evidence=json.loads(a.elaboration_report.read_text())
    if not evidence.get('pass_test')or evidence.get('HLS_top')!='rocev2_native_zero_request_top'or \
       (evidence.get('requester_owner_bits'),evidence.get('SQ_bits'))!=(748,408):
        raise ValueError('matched complete zero graph elaboration required')
    for n,h in evidence['source_sha256'].items():
        if digest(ROOT/n)!=h:raise ValueError('elaboration source changed: '+n)
    run=Path(tempfile.mkdtemp(prefix='zero-native-full-',dir=ROOT/'rdma/rnic/build'))
    obj=Path(tempfile.mkdtemp(prefix='as02-zero-native-obj-',dir='/dev/shm'))
    ram=Path(tempfile.mkdtemp(prefix='as02-zero-native-artifacts-',dir='/dev/shm'))
    report=dict(scope=__doc__,pass_test=False,directory=str(run.relative_to(ROOT)),compile_directory=str(obj),
        RAM_artifact_directory=str(ram),actual_generated_HLS=True,actual_complete_native_graph=True,
        two_state_simulation=True,hardware_verified=False,standard_API_runtime=False,full_board_timing=False,
        physical_host_root_peer_PHY_PTP_inputs_modeled=True,simulation_limit_seconds=30,compile_limit_seconds=1200,
        both_global_drains_zero=True,default_hardware_changed=False,RNC_features=4095,
        incoming_zero_RQ_implemented=False,provider4095_implemented=False,tests={})
    try:
        src,data,before=source.sources(a.hls_build.resolve(),a.native_hls_report.resolve(),
            a.owned_hls_report.resolve(),a.request_hls_report.resolve(),run)
        src=list(dict.fromkeys([*src,*fixture.link.SOURCES]));(run/'tb.v').write_text(fixture.bench())
        helpers=[Path(m.__file__).resolve()for m in list(sys.modules.values())if getattr(m,'__file__',None)and
            (Path(m.__file__).resolve().is_relative_to(ROOT/'rdma/rnic/tests')or
             Path(m.__file__).resolve().is_relative_to(ROOT/'rdma/rnic/fpga'))]
        own=[*src,*helpers,Path(__file__).resolve(),a.elaboration_report.resolve(),run/'tb.v',
            *[ROOT/'rdma/rnic/kernel'/n for n in ['wqe.c','wqe.h','wqe_atomic.c','wqe_atomic.h','wqe_zero.c','wqe_zero.h']]]
        before.update({str(p.relative_to(ROOT)):digest(p)for p in own});report['source_sha256']=before
        (run/'atomic-input.hex').write_text(fixture.fixtures())
        for f in data:shutil.copy2(f,run/f.name)
        cmd=['iverilog','-g2012','-s','tb','-o',str(ram/'tb.vvp'),str(run/'tb.v'),*map(str,src)]
        start=time.monotonic();c=subprocess.run(cmd,capture_output=True,text=True,timeout=180)
        (run/'elaborate.log').write_text(c.stdout+c.stderr)
        report.update(bench_elaborate_command=cmd,bench_elaborate_seconds=time.monotonic()-start)
        if c.returncode or any('expects'in l and 'bits'in l for l in c.stderr.splitlines()):
            raise ValueError('complete zero bench elaboration/width mismatch: '+str(run/'elaborate.log'))
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
        if c.returncode:raise ValueError('actual zero native compilation failed: '+str(run/'compile.log'))
        shutil.copy2(obj/'Vtb',ram/'Vtb');report.update(frozen_binary_path=str(ram/'Vtb'),binary_sha256=digest(ram/'Vtb'))
        cases=[('CAS',7,0,['+CAS'],False),('FADD',8,0,['+FADD'],False),('READ',2,0,[],False),
            ('SEND_IMM',5,0x89abcdef,['+SEND_IMM','+IMM=89abcdef'],False),('ATOMIC_MIXED',2,0,['+ATOMIC_ONLY'],False),
            ('CAS_NO_RX_ATOMIC',7,0,['+CAS','+NO_RX_ATOMIC'],False),('QP_DENIED',2,0,['+ATOMIC_ONLY','+QP_DENIED'],False),
            ('MR_DENIED',2,0,['+ATOMIC_ONLY','+MR_DENIED'],False)]
        cases+=[('ZERO_'+name,op,0x89abcdef if op in [5,6]else 0,
            ['+ZERO',*args,*(['+IMM=89abcdef']if op in [5,6]else[])],True)
            for name,op,args in [('WRITE',1,['+WRITE']),('READ',2,[]),('SEND',3,['+SEND']),
                ('SEND_IMM',5,['+SEND_IMM']),('WRITE_IMM',6,['+WRITE_IMM'])]]
        for name,opcode,immediate,args,zero in cases:
            words,records,request=fixture.variant(opcode,immediate,zero)
            inputs={'input.hex':''.join(f'{w:x}\n'for w in words),
                'records.hex':''.join(f'{int.from_bytes(r,"little"):0256x}\n'for r in records)}
            for n,t in inputs.items():(run/n).write_text(t);(run/(name+'-'+n)).write_text(t)
            start=time.monotonic()
            with(run/(name+'.log')).open('x')as log:
                c=subprocess.run([str(ram/'Vtb'),*args],cwd=run,stdout=log,stderr=subprocess.STDOUT,timeout=30,preexec_fn=tool.no_core)
            result=dict(seconds=time.monotonic()-start,exit=c.returncode,
                runtime_input_sha256={n:digest(run/n)for n in inputs});report['tests'][name]=result
            if c.returncode:raise ValueError(name+' native runtime failed: '+str(run/(name+'.log')))
            output=(run/(name+'.log')).read_text()
            result.update(verify_zero(output,records,request,opcode,immediate,run)if zero else
                access.verify(output,name=='QP_DENIED')if name in ['QP_DENIED','MR_DENIED']else
                responder.verify(output)if name=='ATOMIC_MIXED'else prior.verify(output,records,request,opcode,immediate,run))
            if name not in ['ATOMIC_MIXED','QP_DENIED','MR_DENIED']:shutil.copy2(run/'request-event.hex',run/(name+'-event.hex'))
            print(json.dumps(dict(case=name,pass_test=True,seconds=result['seconds'])),flush=True)
        for n,h in before.items():
            if digest(ROOT/n)!=h:raise ValueError('consumed source changed: '+n)
        report.update(pass_test=True,source_unchanged=True)
    except Exception as e:report.update(error_type=type(e).__name__,error=str(e));raise
    finally:
        report['artifact_sha256']={str(p.relative_to(ROOT)):digest(p)for p in run.iterdir()if p.is_file()}
        report['RAM_artifact_sha256']={str(p):digest(p)for p in ram.iterdir()if p.is_file()}
        with a.report.open('x')as f:f.write(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(pass_test=True,compilation_seconds=report['compilation_seconds'],tests={n:v['seconds']for n,v in report['tests'].items()})))


if __name__=='__main__':main()
