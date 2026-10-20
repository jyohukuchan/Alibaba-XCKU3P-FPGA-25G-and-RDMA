#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual coherent SQ -> Immediate shared HLS -> native DMA/replay/MAC/CQ.

Full generated core and real RTL, physical host/root/MAC pins/peer are models.
Two-state simulation, not X/Z, actual Linux/provider or hardware/timing proof.
Each runtime case <=30seconds; feature compilation may take longer.
"""
import argparse
import ctypes as C
import json
import os
from pathlib import Path
import resource
import shutil
import subprocess
import tempfile
import time
import native_immediate_request_fixture as fixture
import test_immediate_wqe as codec

elaboration=fixture.elaboration
ROOT=elaboration.ROOT
TOOL=Path('/home/user/fpga-rocev2-research/verilator-v5.036-install/bin/verilator')
digest=elaboration.delivery.digest


def no_core():resource.setrlimit(resource.RLIMIT_CORE,(0,0))


def encode_records(records):
    # Both decode and encode are the actual production C profile APIs.
    result=[];cls=codec.ImmediateWQETests;cls.setUpClass()
    try:
        for raw in records:
            w=codec.base.WQE();inp=(C.c_uint8*64).from_buffer_copy(raw);out=(C.c_uint8*64)()
            if cls.lib.as02_wqe_decode_profile(C.byref(w),inp,1):raise ValueError('actual C rejected input descriptor')
            if cls.lib.as02_wqe_encode_profile(out,C.byref(w),1)or bytes(out)!=raw:
                raise ValueError('actual C/profile oracle mismatch')
            result.append(bytes(out))
    finally:cls.tearDownClass()
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True)
    p.add_argument('--hls-build',type=Path,required=True);p.add_argument('--native-hls-report',type=Path,required=True)
    p.add_argument('--reuse-compiled-report',type=Path,help='rebuild changed bench using verified compiler objects, NOT a cached test result')
    a=p.parse_args()
    if a.report.exists():p.error('preserve evidence')
    # Same fresh native-RTL compilation headroom as preceding launcher.
    if shutil.disk_usage(ROOT).free<1024*1024*1024:raise RuntimeError('unchanged fresh native RTL guard')
    run=Path(tempfile.mkdtemp(prefix='immediate-native-request-',dir=ROOT/'rdma/rnic/build'))
    obj=(Path(json.loads(a.reuse_compiled_report.read_text())['compile_directory'])if a.reuse_compiled_report else
        Path(tempfile.mkdtemp(prefix='as02-immediate-native-obj-',dir='/dev/shm')))
    report=dict(scope=__doc__,pass_test=False,directory=str(run.relative_to(ROOT)),compile_directory=str(obj),
        simulation_limit_seconds=30,compile_limit_seconds=1200,hardware_verified=False,
        actual_generated_HLS=True,actual_Linux_provider=False,two_state_simulation=True,
        physical_host_root_MAC_and_peer_models=True,both_global_drains_zero=True,
        default_profile_unchanged=True,Immediate_device_capability_advertised=True,
        Immediate_capability_opt_in_native_only=True,hardware_or_default_profile_changed=False,tests={})
    try:
        src,data,before,selected,generated=elaboration.sources(a.hls_build.resolve(),a.native_hls_report.resolve(),run)
        tb=fixture.case();(run/'tb.v').write_text(tb)
        own=[Path(__file__).resolve(),Path(fixture.__file__).resolve(),Path(fixture.old.__file__).resolve(),
            Path(fixture.old.parent.__file__).resolve(),Path(fixture.old.send.__file__).resolve(),
            Path(fixture.base.__file__).resolve(),Path(codec.__file__).resolve(),Path(codec.base.__file__).resolve(),
            ROOT/'rdma/rnic/kernel/wqe.c',ROOT/'rdma/rnic/kernel/wqe.h',run/'tb.v']
        before.update({str(x.relative_to(ROOT)):digest(x)for x in own})
        for x in data:shutil.copy2(x,run/x.name)
        cmd=[str(TOOL),'--binary','--timing','--top-module','tb','-Wno-fatal','-j','4',
            '--output-split','20000','--output-split-cfuncs','0','--output-groups','0',
            '-CFLAGS','-O0','--Mdir',str(obj),str(run/'tb.v'),*map(str,src)]
        report.update(source_sha256=before,compile_command=cmd)
        print(json.dumps(dict(directory=str(run),compile_directory=str(obj),compile_limit_seconds=1200)),flush=True)
        env=os.environ.copy();env['TMPDIR']='/dev/shm/as02-native-compiler-tmp-QYQsVyT5'
        start=time.monotonic()
        if a.reuse_compiled_report:
            import immediate_native_compile_cache as cache
            before[str(Path(cache.__file__).resolve().relative_to(ROOT))]=digest(Path(cache.__file__).resolve())
            info=cache.compile(cmd,run,env,a.reuse_compiled_report.resolve())
            before.update(info.pop('extra_source_sha256'));report.update(info)
        else:
            with(run/'compile.log').open('x')as log:
                c=subprocess.run(cmd,cwd=run,stdout=log,stderr=subprocess.STDOUT,timeout=1200,env=env)
            report['compilation_seconds']=time.monotonic()-start
            if c.returncode:raise RuntimeError('actual native Immediate compile failed: '+str(run/'compile.log'))
        shutil.copy2(obj/'Vtb',run/'Vtb');report['binary_sha256']=digest(run/'Vtb')
        cases=[('SEND_IMM_zero',5,0,['+SEND_IMM']),('WRITE_IMM_zero',6,0,['+WRITE_IMM']),
            ('SEND_IMM_high',5,0x89abcdef,['+SEND_IMM']),('WRITE_IMM_mixed',6,0x01234567,['+WRITE_IMM']),
            ('READ',2,0,[]),('WRITE',1,0,['+WRITE']),('SEND',3,0,['+SEND'])]
        for name,opcode,immediate,args in cases:
            words,records,request=fixture.variant(opcode,immediate);records=encode_records(records)
            fixtures={'input.hex':''.join(f'{w:x}\n'for w in words),
                'records.hex':''.join(f'{int.from_bytes(r,"little"):0128x}\n'for r in records)}
            for n,text in fixtures.items():(run/n).write_text(text);(run/(name+'-'+n)).write_text(text)
            start=time.monotonic()
            with(run/(name+'.log')).open('x')as log:
                c=subprocess.run([str(run/'Vtb'),*args,'+IMM='+format(immediate,'x')],cwd=run,
                    stdout=log,stderr=subprocess.STDOUT,timeout=30,preexec_fn=no_core)
            elapsed=time.monotonic()-start
            if c.returncode:raise RuntimeError('native '+name+' failed: '+str(run/(name+'.log')))
            output=(run/(name+'.log')).read_text()
            rows=[json.loads(l.split(' ',1)[1])for l in output.splitlines()if l.startswith('NATIVE_RNIC_RESULT ')]
            if len(rows)!=1 or not rows[0]['pass_test']or rows[0]['HLS_model']or not rows[0]['CQ_committed']:
                raise ValueError('missing actual native completion assertions')
            if rows[0]['opcode']!=opcode:raise ValueError('wrong actual executed opcode')
            snapshot=run/'request-event.hex'
            if len(snapshot.read_text().splitlines())!=29:raise ValueError('missing20-word native CQ snapshot')
            shutil.copy2(snapshot,run/(name+'-event.hex'))
            report['tests'][name]=dict(summary=rows[0],simulation_seconds=elapsed,
                immediate=immediate,actual_C_profile_codec=True,actual_coherent_SQ=True,
                actual_same_MR_PTE_native_DMA=True,actual_MAC_lifetime_and_CQ=True,
                actual_request_wire=fixture.verify(output,request,opcode),
                CQ_snapshot_sha256=digest(snapshot),runtime_input_sha256={n:digest(run/n)for n in fixtures})
        for n,h in before.items():
            if digest(ROOT/n)!=h:raise ValueError('consumed input changed: '+n)
        report.update(pass_test=True,source_unchanged=True)
    except Exception as e:report.update(error_type=type(e).__name__,error=str(e));raise
    finally:
        report['artifact_sha256']={str(x.relative_to(ROOT)):digest(x)for x in run.iterdir()if x.is_file()}
        with a.report.open('x')as out:out.write(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k]for k in ['pass_test','compilation_seconds','tests']}),flush=True)


if __name__=='__main__':main()
