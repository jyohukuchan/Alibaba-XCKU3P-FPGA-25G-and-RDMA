#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Complete native Immediate RX/duplex/RNR with actual HLS, memory and CQ RTL.

One independent coherent SQ/RQ pair. Peer/root/MAC pins/host are models;
no actual Linux/provider/board, X/Z or physical timing qualification.
WRITE_IMM data goes to independently authorized remote MR, not1-byte RQ.
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
import native_immediate_receive_fixture as fixture
import probe_immediate_native_request as request

elaboration=fixture.elaboration
ROOT=elaboration.ROOT
digest=request.digest


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True)
    p.add_argument('--hls-build',type=Path,required=True);p.add_argument('--native-hls-report',type=Path,required=True)
    p.add_argument('--reuse-compiled-report',type=Path,help='verified compiler objects only; changed bench is regenerated')
    a=p.parse_args()
    if a.report.exists():p.error('preserve evidence')
    if shutil.disk_usage(ROOT).free<1024*1024*1024:raise RuntimeError('unchanged fresh native RTL guard')
    run=Path(tempfile.mkdtemp(prefix='immediate-native-receive-',dir=ROOT/'rdma/rnic/build'))
    obj=(Path(json.loads(a.reuse_compiled_report.read_text())['compile_directory'])if a.reuse_compiled_report else
        Path(tempfile.mkdtemp(prefix='as02-immediate-native-rx-obj-',dir='/dev/shm')))
    report=dict(scope=__doc__,pass_test=False,directory=str(run.relative_to(ROOT)),compile_directory=str(obj),
        compile_limit_seconds=1200,simulation_limit_seconds=30,hardware_verified=False,
        actual_generated_HLS=True,actual_Linux_provider=False,two_state_simulation=True,
        physical_host_root_MAC_and_peer_models=True,both_global_drains_zero=True,
        Immediate_device_capability_advertised=True,Immediate_capability_opt_in_native_only=True,
        hardware_or_default_profile_changed=False,tests={})
    try:
        src,data,before,selected,generated=elaboration.sources(a.hls_build.resolve(),a.native_hls_report.resolve(),run)
        tb=fixture.case();(run/'tb.v').write_text(tb)
        helpers=[Path(m.__file__).resolve()for m in list(sys.modules.values())
            if getattr(m,'__file__',None)and Path(m.__file__).resolve().is_relative_to(ROOT/'rdma/rnic/tests')]
        own=[*helpers,Path(__file__).resolve(),run/'tb.v',ROOT/'rdma/rnic/kernel/wqe.c',ROOT/'rdma/rnic/kernel/wqe.h']
        before.update({str(x.relative_to(ROOT)):digest(x)for x in own})
        for x in data:shutil.copy2(x,run/x.name)
        cmd=[str(request.TOOL),'--binary','--timing','--top-module','tb','-Wno-fatal','-j','4',
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
            if c.returncode:raise RuntimeError('native Immediate RX compile failed: '+str(run/'compile.log'))
        shutil.copy2(obj/'Vtb',run/'Vtb');report['binary_sha256']=digest(run/'Vtb')
        cases=[('SEND_IMM_zero',False,0,False),('WRITE_IMM_zero',True,0,False),
            ('SEND_IMM_high_RNR',False,0x89abcdef,True),('WRITE_IMM_mixed_RNR',True,0x01234567,True)]
        for name,write,immediate,empty in cases:
            words,records,rq_records,ack=fixture.variant(write,immediate)
            records=request.encode_records(records);rq_records=request.encode_records(rq_records)
            inputs={'input.hex':''.join(f'{w:x}\n'for w in words),
                'records.hex':''.join(f'{int.from_bytes(r,"little"):0128x}\n'for r in records),
                'receive-records.hex':''.join(f'{int.from_bytes(r,"little"):0128x}\n'for r in rq_records)}
            for n,text in inputs.items():(run/n).write_text(text);(run/(name+'-'+n)).write_text(text)
            args=(['+WRITE_IMM']if write else[])+(['+RNR']if empty else[])+['+IMM='+format(immediate,'x')]
            start=time.monotonic()
            with(run/(name+'.log')).open('x')as log:
                c=subprocess.run([str(run/'Vtb'),*args],cwd=run,stdout=log,stderr=subprocess.STDOUT,
                    timeout=30,preexec_fn=request.no_core)
            elapsed=time.monotonic()-start
            if c.returncode:raise RuntimeError('native RX '+name+' failed: '+str(run/(name+'.log')))
            output=(run/(name+'.log')).read_text()
            rows=[json.loads(l.split(' ',1)[1])for l in output.splitlines()if l.startswith('NATIVE_RNIC_RESULT ')]
            if len(rows)!=1 or not rows[0]['pass_test']or rows[0]['HLS_model']or not rows[0]['CQ_committed']:
                raise ValueError('missing native RX/CQ/placement assertions')
            if rows[0]['buffer_capacity']!=(1 if write else 128):raise ValueError('wrong notification RQ capacity')
            snapshots={}
            for n in ['send-event1.hex','receive-event1.hex','send-event2.hex','receive-event2.hex']:
                if len((run/n).read_text().splitlines())!=29:raise ValueError('missing20-word native CQ '+n)
                shutil.copy2(run/n,run/(name+'-'+n));snapshots[n]=digest(run/n)
            report['tests'][name]=dict(summary=rows[0],simulation_seconds=elapsed,immediate=immediate,
                actual_coherent_SQ_RQ=True,actual_same_MR_PTE_DMA_and_real_memory_fence=True,
                actual_HLS_MAC_CQ=True,RNR_before_RQ_and_PSN_advance_tested=empty,
                WRITE_data_independent_of_RQ_buffer=write,actual_wire_and_lifetimes=fixture.verify(output,ack,write,empty),
                CQ_snapshot_sha256=snapshots,runtime_input_sha256={n:digest(run/n)for n in inputs})
        for n,h in before.items():
            if digest(ROOT/n)!=h:raise ValueError('consumed input changed: '+n)
        report.update(pass_test=True,source_unchanged=True)
    except Exception as e:report.update(error_type=type(e).__name__,error=str(e));raise
    finally:
        report['artifact_sha256']={str(x.relative_to(ROOT)):digest(x)for x in run.iterdir()if x.is_file()}
        with a.report.open('x')as f:f.write(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k]for k in ['pass_test','compilation_seconds','tests']}),flush=True)


if __name__=='__main__':main()
