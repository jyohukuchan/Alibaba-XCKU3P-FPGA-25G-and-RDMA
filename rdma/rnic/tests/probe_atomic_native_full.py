#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual shared native graph: ordinary READ/Immediate and mixed Atomic/WRITE.

Real owned HLS, SQC, shared MR/PTE/DMA and outer Atomic MAC. Atomic case uses
actual XGMII/FCS/SFD/CDC, with NO test retirement or posted WQE/RQ/CQ. The
ordinary requester regression retains its MAC-pin model. Physical host/root,
PHY/peer/PTP input are models. No standard Linux, hardware or timing claim.
Each runtime <=30s. Feature compilation <=1200s; no HLS synthesis required.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import atomic_native_full_sources as source
import atomic_native_full_memory_fixture as fixture
import atomic_native_full_compile_cache as cache
import atomic_native_full_oracle as oracle
import probe_immediate_native_request as old

ROOT=source.ROOT;digest=source.digest


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--hls-build',type=Path,required=True)
    p.add_argument('--native-hls-report',type=Path,required=True);p.add_argument('--owned-hls-report',type=Path,required=True)
    p.add_argument('--reuse-compiled-report',type=Path,required=True);p.add_argument('--report',type=Path,required=True)
    a=p.parse_args()
    if a.report.exists():p.error('preserve prior evidence')
    if shutil.disk_usage(ROOT).free<1024**3:raise RuntimeError('unchanged fresh native1GiB guard')
    if shutil.disk_usage('/dev/shm').free<4*1024**3:raise RuntimeError('RAM4GiB compilation/artifact headroom required')
    run=Path(tempfile.mkdtemp(prefix='atomic-native-full-',dir=ROOT/'rdma/rnic/build'))
    ram=Path(tempfile.mkdtemp(prefix='as02-atomic-native-artifacts-',dir='/dev/shm'))
    obj=Path(json.loads(a.reuse_compiled_report.read_text())['compile_directory'])
    report=dict(scope=__doc__,pass_test=False,directory=str(run.relative_to(ROOT)),compile_directory=str(obj),
        RAM_artifact_directory=str(ram),actual_generated_HLS=True,Atomic_native_graph_selected=True,
        hardware_verified=False,standard_API_runtime=False,full_board_timing=False,two_state_simulation=True,
        physical_host_root_PHY_peer_PTP_input_models=True,simulation_limit_seconds=30,compile_limit_seconds=1200,
        both_global_drains_zero=True,default_hardware_changed=False,tests={})
    try:
        src,data,before=source.sources(a.hls_build.resolve(),a.native_hls_report.resolve(),a.owned_hls_report.resolve(),run)
        src=list(dict.fromkeys([*src,*fixture.link.SOURCES]));(run/'tb.v').write_text(fixture.bench())
        own=[Path(m.__file__).resolve()for m in [fixture,cache,oracle,old]]
        own += [Path(__file__).resolve(),ROOT/'rdma/host/rocev2_wire.py',ROOT/'rdma/rnic/kernel/wqe.c',ROOT/'rdma/rnic/kernel/wqe.h',run/'tb.v']
        before.update({str(p.relative_to(ROOT)):digest(p)for p in [*src,*own]});report['source_sha256']=before
        (run/'atomic-input.hex').write_text(fixture.fixtures())
        for p in data:shutil.copy2(p,run/p.name)
        command=[str(old.TOOL),'--binary','--timing','--top-module','tb','-Wno-fatal','-j','4',
            '--output-split','20000','--output-split-cfuncs','0','--output-groups','0','-CFLAGS','-O0',
            '--Mdir',str(obj),str(run/'tb.v'),*map(str,src)]
        env=os.environ.copy();env['TMPDIR']='/dev/shm/as02-native-compiler-tmp-QYQsVyT5'
        print(json.dumps(dict(directory=str(run),compile_directory=str(obj),compile_limit_seconds=1200)),flush=True)
        reused=cache.compile(command,run,env,a.reuse_compiled_report.resolve())
        before.update(reused.pop('extra_source_sha256'));report.update(reused)
        shutil.copy2(obj/'Vtb',ram/'Vtb');report.update(frozen_binary_path=str(ram/'Vtb'),binary_sha256=digest(ram/'Vtb'))
        for name,opcode,immediate,args in [('ATOMIC_MIXED',2,0,['+ATOMIC_ONLY']),('READ',2,0,[]),
            ('SEND_IMM',5,0x89abcdef,['+SEND_IMM','+IMM=89abcdef'])]:
            words,records,request=fixture.old.old.variant(opcode,immediate);records=old.encode_records(records)
            fixtures={'input.hex':''.join(f'{w:x}\n'for w in words),
                'records.hex':''.join(f'{int.from_bytes(r,"little"):0128x}\n'for r in records)}
            for n,t in fixtures.items():(run/n).write_text(t);(run/(name+'-'+n)).write_text(t)
            start=time.monotonic()
            with(run/(name+'.log')).open('x')as log:
                r=subprocess.run([str(ram/'Vtb'),*args],cwd=run,stdout=log,stderr=subprocess.STDOUT,timeout=30,preexec_fn=old.no_core)
            report['tests'][name]=dict(seconds=time.monotonic()-start,exit=r.returncode)
            if r.returncode:raise ValueError(name+' actual native run failed: '+str(run/(name+'.log')))
            output=(run/(name+'.log')).read_text()
            if name=='ATOMIC_MIXED':report['tests'][name].update(oracle.verify(output))
            else:
                rows=[json.loads(l.split(' ',1)[1])for l in output.splitlines()if l.startswith('NATIVE_RNIC_RESULT ')]
                proof=[json.loads(l.split(' ',1)[1])for l in output.splitlines()if l.startswith('ATOMIC_NATIVE_OWNED_STAGE ')]
                if len(rows)!=1 or not rows[0]['pass_test']or rows[0]['HLS_model']or not rows[0]['CQ_committed']or rows[0]['opcode']!=opcode:
                    raise ValueError('missing native WR/CQ proof')
                if len(proof)!=1 or not all(proof[0][k]for k in ['actual_owned_HLS','actual_SQC_binding','Atomic_RX_selected']):
                    raise ValueError('wrong integrated graph scope')
                report['tests'][name].update(summary=rows[0],stage_proof=proof[0],
                    actual_request_wire=fixture.old.old.verify(output,request,opcode),actual_C_profile_codec=True,
                    physical_MAC_pin_model=True)
        for n,h in before.items():
            if digest(ROOT/n)!=h:raise ValueError('consumed source changed: '+n)
        report.update(pass_test=True,source_unchanged=True)
    except Exception as e:report.update(error_type=type(e).__name__,error=str(e));raise
    finally:
        report['artifact_sha256']={str(p.relative_to(ROOT)):digest(p)for p in run.iterdir()if p.is_file()}
        report['RAM_artifact_sha256']={str(p):digest(p)for p in ram.iterdir()if p.is_file()}
        with a.report.open('x')as f:f.write(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(pass_test=True,compilation_seconds=report['compilation_seconds'],tests={k:v['seconds']for k,v in report['tests'].items()})),flush=True)


if __name__=='__main__':main()
