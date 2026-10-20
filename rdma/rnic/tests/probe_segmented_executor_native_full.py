#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual dispatcher/source/legacy/common-nonce graph, all27 bounded cases.

Same actual HLS/MR/PTE/DMA/MAC/CQ with new retained-source dispatcher and
atomic CQ fanout; physical endpoints modeled. Large admission/wire remain
closed, so this is not native large-transfer qualification. Each runtime<=30s.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import segmented_executor_native_sources as source
import zero_rq_native_fixture as fixture
import segmented_executor_native_fixture as service
import probe_zero_native_full as legacy
import probe_atomic128_native_full as prior
import atomic_access_native_oracle as access
import atomic_native_full_oracle as responder
import native_request_cq_fixture as wire
import probe_immediate_native_request as tool

ROOT=source.ROOT;digest=source.digest


compile_owned=legacy.compile_owned
verify_zero=legacy.verify_zero


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ['hls-build','native-hls-report','owned-hls-report','request-hls-report','elaboration-report','report']:
        p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args()
    if a.report.exists():p.error('preserve prior evidence')
    if shutil.disk_usage(ROOT).free<1024**3:raise RuntimeError('unchanged fresh native1GiB guard')
    if shutil.disk_usage('/dev/shm').free<4*1024**3:raise RuntimeError('RAM compile4GiB guard')
    evidence=json.loads(a.elaboration_report.read_text())
    if not evidence.get('pass_test')or evidence.get('HLS_top')!='rocev2_native_segmented_request_top'or \
       (evidence.get('requester_owner_bits'),evidence.get('SQ_bits'))!=(748,408):
        raise ValueError('matched complete zero graph elaboration required')
    if (evidence.get('zero_service_owner_bits'),evidence.get('zero_service_done_bits'))!=(344,400):
        raise ValueError('matched ordinary zero service native ABI required')
    if not all(evidence.get(n)for n in ['large_source_DMA_wired','atomic_CQ_retirement_fanout',
        'actual_shared_physical_command_nonce'])or any(evidence.get('module_counts',{}).get(n)!=1 for n in
        ['rocev2_segmented_executor_mux','rocev2_segmented_source_executor','rocev2_segmented_child_executor']):
        raise ValueError('matched actual retained-source/legacy/common-nonce/CQ graph required')
    for n,h in evidence['source_sha256'].items():
        if digest(ROOT/n)!=h:raise ValueError('elaboration source changed: '+n)
    run=Path(tempfile.mkdtemp(prefix='segmented-executor-native-full-',dir=ROOT/'rdma/rnic/build'))
    obj=Path(tempfile.mkdtemp(prefix='as02-zero-native-obj-',dir='/dev/shm'))
    ram=Path(tempfile.mkdtemp(prefix='as02-zero-native-artifacts-',dir='/dev/shm'))
    report=dict(scope=__doc__,pass_test=False,directory=str(run.relative_to(ROOT)),compile_directory=str(obj),
        RAM_artifact_directory=str(ram),actual_generated_HLS=True,actual_complete_native_graph=True,
        two_state_simulation=True,hardware_verified=False,standard_API_runtime=False,full_board_timing=False,
        physical_host_root_peer_PHY_PTP_inputs_modeled=True,simulation_limit_seconds=30,compile_limit_seconds=1200,
        both_global_drains_zero=True,default_hardware_changed=False,RNC_features=4095,
        compiler_output_split_cfuncs=500000,compile_owns_process_group=True,
        incoming_zero_RQ_source_candidate=True,incoming_zero_RQ_runtime_verified=False,
        ordinary_zero_service_candidate=True,ordinary_zero_service_runtime_verified=False,provider4095_implemented=False,
        actual_shared_physical_command_nonce=True,large_native_admission=False,large_source_DMA_wired=True,
        atomic_CQ_retirement_fanout=True,large_native_wire_CQ=False,planned_cases=27,
        ordinary_source_runtime_verified=False,tests={})
    try:
        src,data,before=source.sources(a.hls_build.resolve(),a.native_hls_report.resolve(),
            a.owned_hls_report.resolve(),a.request_hls_report.resolve(),run)
        src=list(dict.fromkeys([*src,*fixture.link.SOURCES]));(run/'tb.v').write_text(service.bench())
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
            '--output-split','20000','--output-split-cfuncs','500000','--output-groups','0','-CFLAGS','-O0',
            '--Mdir',str(obj),str(run/'tb.v'),*map(str,src)]
        report['compile_command']=command;env=os.environ.copy()
        env['TMPDIR']='/dev/shm/as02-native-compiler-tmp-QYQsVyT5'
        print(json.dumps(dict(directory=str(run),compile_directory=str(obj),compile_limit_seconds=1200)),flush=True)
        start=time.monotonic()
        with(run/'compile.log').open('x')as log:
            compile_exit=compile_owned(command,run,log,env)
        report.update(compilation_seconds=time.monotonic()-start,compile_exit=compile_exit)
        if compile_exit:raise ValueError('actual zero native compilation failed: '+str(run/'compile.log'))
        shutil.copy2(obj/'Vtb',ram/'Vtb');report.update(frozen_binary_path=str(ram/'Vtb'),binary_sha256=digest(ram/'Vtb'))
        cases=[('CAS',7,0,['+CAS'],False),('FADD',8,0,['+FADD'],False),('READ',2,0,[],False),
            ('SEND_IMM',5,0x89abcdef,['+SEND_IMM','+IMM=89abcdef'],False),('ATOMIC_MIXED',2,0,['+ATOMIC_ONLY'],False),
            ('CAS_NO_RX_ATOMIC',7,0,['+CAS','+NO_RX_ATOMIC'],False),('QP_DENIED',2,0,['+ATOMIC_ONLY','+QP_DENIED'],False),
            ('MR_DENIED',2,0,['+ATOMIC_ONLY','+MR_DENIED'],False)]
        cases+=[('ZERO_'+name,op,0x89abcdef if op in [5,6]else 0,
            ['+ZERO',*args,*(['+IMM=89abcdef']if op in [5,6]else[])],True)
            for name,op,args in [('WRITE',1,['+WRITE']),('READ',2,[]),('SEND',3,['+SEND']),
                ('SEND_IMM',5,['+SEND_IMM']),('WRITE_IMM',6,['+WRITE_IMM'])]]
        rx_cases=[('RX_'+str(op)+'_CAP'+str(cap),op,0,['+RQ','+RQ_OP='+str(op),*(['+RQ_BUFFER']if cap else[])],False,cap)
            for cap in [128,0]for op in [3,5,6]]
        rx_cases += [('RX_RNR_'+str(op),op,0,['+RQ','+RQ_OP='+str(op),'+RQ_RNR'],False,0)for op in [3,6]]
        service_cases=[('SERVICE_'+name,op,0,['+ZERO_SERVICE','+SERVICE_OP='+str(op)],False,-1)
            for name,op in [('AFTER_WRITE',13),('WRITE',10),('READ',12),('MIXED',0)]]
        cases=[('WRITE',1,0,['+WRITE'],False,None),('SEND',3,0,['+SEND'],False,None)]+\
            service_cases+rx_cases+[(*case,None)for case in cases]
        if len(cases)!=27:raise ValueError('all25 prior cases plus ordinary WRITE/SEND required')
        for name,opcode,immediate,args,zero,capacity in cases:
            words,records,request=fixture.old.variant(opcode,immediate,zero)if capacity is None else fixture.old.variant(2,0,False)
            inputs={'input.hex':''.join(f'{w:x}\n'for w in words),
                'records.hex':''.join(f'{int.from_bytes(r,"little"):0256x}\n'for r in records)}
            if capacity is not None and capacity>=0:
                rx_words,rx_records,packets=fixture.variant(opcode,capacity)
                inputs.update({'receive-input.hex':''.join(f'{w:x}\n'for w in rx_words),
                    'receive-records.hex':''.join(f'{int.from_bytes(r,"little"):0256x}\n'for r in rx_records)})
            if capacity==-1:
                service_words,service_packets=service.variant(opcode)
                inputs['service-input.hex']=''.join(f'{w:037x}\n'for w in service_words)
                if opcode==13:inputs['service-prelude.hex']=''.join(f'{w:037x}\n'for w in service.prelude())
            for n,t in inputs.items():(run/n).write_text(t);(run/(name+'-'+n)).write_text(t)
            start=time.monotonic()
            with(run/(name+'.log')).open('x')as log:
                c=subprocess.run([str(ram/'Vtb'),*args],cwd=run,stdout=log,stderr=subprocess.STDOUT,timeout=30,preexec_fn=tool.no_core)
            result=dict(seconds=time.monotonic()-start,exit=c.returncode,
                runtime_input_sha256={n:digest(run/n)for n in inputs});report['tests'][name]=result
            if c.returncode:raise ValueError(name+' native runtime failed: '+str(run/(name+'.log')))
            output=(run/(name+'.log')).read_text()
            result.update(service.verify(output,opcode,run)if capacity==-1 else
                fixture.verify(output,rx_records,opcode,capacity,'+RQ_RNR'in args,run)if capacity is not None else
                verify_zero(output,records,request,opcode,immediate,run)if zero else
                access.verify(output,name=='QP_DENIED')if name in ['QP_DENIED','MR_DENIED']else
                responder.verify(output)if name=='ATOMIC_MIXED'else prior.verify(output,records,request,opcode,immediate,run))
            result['actual_common_nonce_backend']=service.verify_nonce(output)
            result['actual_source_and_atomic_CQ']=service.verify_executor(output,name,request,
                result.get('full748_bit_CQ_owner'))
            if name in ['WRITE','SEND']:
                result['wire']['physical_MAC_receipt_model']=False
                if result['actual_common_nonce_backend']!=dict(admitted=1,issued=1,backend_completed=1,
                    logical_completed=1,translated=1,active=0,fault=0):
                    raise ValueError('ordinary retained source must use actual translated physical command/status')
            if capacity is not None and capacity>=0:
                for seq in [1,2]:shutil.copy2(run/f'zero-rq-event{seq}.hex',run/(name+f'-event{seq}.hex'))
            elif capacity is None and name not in ['ATOMIC_MIXED','QP_DENIED','MR_DENIED']:shutil.copy2(run/'request-event.hex',run/(name+'-event.hex'))
            print(json.dumps(dict(case=name,pass_test=True,seconds=result['seconds'])),flush=True)
        for n,h in before.items():
            if digest(ROOT/n)!=h:raise ValueError('consumed source changed: '+n)
        report.update(pass_test=True,source_unchanged=True,incoming_zero_RQ_runtime_verified=True,
            ordinary_zero_service_runtime_verified=True,ordinary_source_runtime_verified=True)
    except Exception as e:report.update(error_type=type(e).__name__,error=str(e));raise
    finally:
        report['artifact_sha256']={str(p.relative_to(ROOT)):digest(p)for p in run.iterdir()if p.is_file()}
        report['RAM_artifact_sha256']={str(p):digest(p)for p in ram.iterdir()if p.is_file()}
        with a.report.open('x')as f:f.write(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(pass_test=True,compilation_seconds=report['compilation_seconds'],tests={n:v['seconds']for n,v in report['tests'].items()})))


if __name__=='__main__':main()
