#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Real owned HLS staged in actual native READ/Immediate and SQC route binding.

Atomic RX still disabled: this validates the shared core/native authority
integration, NOT Atomic native packet execution. Physical host/root/MAC/peer
remain models. Two bounded runtime cases <=30s, no hardware or Linux install.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import atomic_native_owned_fixture as fixture
import atomic_native_owned_compile_cache as cache
import probe_immediate_native_request as old

ROOT=fixture.ROOT
digest=fixture.digest


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--hls-build',type=Path,required=True)
    p.add_argument('--native-hls-report',type=Path,required=True);p.add_argument('--owned-hls-report',type=Path,required=True)
    p.add_argument('--reuse-compiled-report',type=Path,required=True);p.add_argument('--report',type=Path,required=True)
    a=p.parse_args()
    if a.report.exists():p.error('preserve evidence')
    if shutil.disk_usage(ROOT).free<1024**3:raise RuntimeError('unchanged fresh native1GiB guard')
    run=Path(tempfile.mkdtemp(prefix='atomic-native-owned-',dir=ROOT/'rdma/rnic/build'))
    obj=Path(json.loads(a.reuse_compiled_report.read_text())['compile_directory'])
    report=dict(scope=__doc__,pass_test=False,directory=str(run.relative_to(ROOT)),compile_directory=str(obj),
        actual_generated_HLS=True,actual_owned_HLS_selected_into_native=True,Atomic_RX_selected=False,
        Atomic_native_datapath_integrated=False,hardware_verified=False,standard_API_runtime=False,
        physical_host_root_MAC_and_peer_models=True,two_state_simulation=True,simulation_limit_seconds=30,
        both_global_drains_zero=True,unrelated_unsafe_Ethernet_reCOMMIT_case_not_repeated=True,tests={})
    try:
        src,data,before=fixture.sources(a.hls_build.resolve(),a.native_hls_report.resolve(),a.owned_hls_report.resolve(),run)
        tb=fixture.bench();(run/'tb.v').write_text(tb)
        if any(p.name.startswith('rocev2_native_immediate_top')for p in src):raise ValueError('old native raw still selected')
        if len([p for p in src if p.name=='rocev2_native_atomic_owned_top.v'])!=1:raise ValueError('one real owned raw core required')
        helpers=[Path(__file__).resolve(),Path(cache.__file__).resolve(),Path(old.__file__).resolve(),
            ROOT/'rdma/rnic/kernel/wqe.c',ROOT/'rdma/rnic/kernel/wqe.h',run/'tb.v']
        before.update({str(p.relative_to(ROOT)):digest(p)for p in helpers});report['source_sha256']=before
        for p in data:shutil.copy2(p,run/p.name)
        command=[str(old.TOOL),'--binary','--timing','--top-module','tb','-Wno-fatal','-j','4',
            '--output-split','20000','--output-split-cfuncs','0','--output-groups','0',
            '-CFLAGS','-O0','--Mdir',str(obj),str(run/'tb.v'),*map(str,src)]
        env=os.environ.copy();env['TMPDIR']='/dev/shm/as02-native-compiler-tmp-QYQsVyT5'
        print(json.dumps(dict(directory=str(run),compile_directory=str(obj),compile_limit_seconds=1200)),flush=True)
        reused=cache.compile(command,run,env,a.reuse_compiled_report.resolve())
        before.update(reused.pop('extra_source_sha256'));report.update(reused)
        shutil.copy2(obj/'Vtb',run/'Vtb');report['binary_sha256']=digest(run/'Vtb')
        for name,opcode,immediate,args in [('READ',2,0,[]),('SEND_IMM',5,0x89abcdef,['+SEND_IMM','+IMM=89abcdef'])]:
            words,records,request=fixture.old.variant(opcode,immediate);records=old.encode_records(records)
            fixtures={'input.hex':''.join(f'{w:x}\n'for w in words),
                'records.hex':''.join(f'{int.from_bytes(r,"little"):0128x}\n'for r in records)}
            for n,t in fixtures.items():(run/n).write_text(t);(run/(name+'-'+n)).write_text(t)
            start=time.monotonic()
            with(run/(name+'.log')).open('x')as log:
                r=subprocess.run([str(run/'Vtb'),*args],cwd=run,stdout=log,stderr=subprocess.STDOUT,
                    timeout=30,preexec_fn=old.no_core)
            report['tests'][name]=dict(seconds=time.monotonic()-start,exit=r.returncode)
            if r.returncode:raise ValueError(name+' actual owned native run failed: '+str(run/(name+'.log')))
            output=(run/(name+'.log')).read_text()
            rows=[json.loads(l.split(' ',1)[1])for l in output.splitlines()if l.startswith('NATIVE_RNIC_RESULT ')]
            proof=[json.loads(l.split(' ',1)[1])for l in output.splitlines()if l.startswith('ATOMIC_NATIVE_OWNED_STAGE ')]
            if len(rows)!=1 or not rows[0]['pass_test']or rows[0]['HLS_model']or not rows[0]['CQ_committed']or rows[0]['opcode']!=opcode:
                raise ValueError('missing actual native WR/CQ assertions')
            if len(proof)!=1 or not proof[0]['actual_owned_HLS']or not proof[0]['actual_SQC_binding']or proof[0]['Atomic_RX_selected']:
                raise ValueError('wrong actual native owned stage proof/scope')
            report['tests'][name].update(summary=rows[0],stage_proof=proof[0],
                actual_request_wire=fixture.old.verify(output,request,opcode),actual_C_profile_codec=True)
        for n,h in before.items():
            if digest(ROOT/n)!=h:raise ValueError('consumed source changed: '+n)
        report.update(pass_test=True,source_unchanged=True)
    except Exception as e:report.update(error_type=type(e).__name__,error=str(e));raise
    finally:
        report['artifact_sha256']={str(p.relative_to(ROOT)):digest(p)for p in run.iterdir()if p.is_file()}
        with a.report.open('x')as f:f.write(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(pass_test=True,compilation_seconds=report['compilation_seconds'],
        tests={k:v['seconds']for k,v in report['tests'].items()})),flush=True)


if __name__=='__main__':main()
