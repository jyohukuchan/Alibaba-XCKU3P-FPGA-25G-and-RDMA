#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Run the real C decoder/reader on actual new native FEC AXI snapshots.

Native packet-to-AXI is proved by the separate new native40 execution/audit.
This second stage replays that exact readback into unchanged C tests; C IO,
delivery and reference callbacks remain MODELS, not live Linux attachment.
"""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile
import time
import audit_segmented_receive as binding

ROOT=binding.ROOT;digest=binding.digest


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True)
    p.add_argument('--native-record',default='fatal-event-native-full-001')
    p.add_argument('--runtime-audit',default='fatal-event-native-runtime-diagnostics-001');a=p.parse_args()
    if a.report.exists():p.error('preserve earlier evidence')
    native,nid=binding.bindings(a.native_record);audit,aid=binding.bindings(a.runtime_audit)
    if not native['pass_test'] or len(native['tests'])!=40 or not audit['audit_passed'] or \
       not audit['actual_native_packet_HLS_abort_cancel_FEC_AXI_readback_ACK'] or \
       audit['evidence'][a.native_record]['report_sha256']!=nid['report_sha256']:
        raise ValueError('same actual complete new native40 and native AXI/ACK runtime audit required')
    files=[Path(__file__).resolve(),ROOT/'rdma/rnic/tests/test_fatal_io.c',
        *[ROOT/'rdma/rnic/kernel'/n for n in ['fatal_io.c','fatal_io.h','fatal_regs.h','mr_contract.h']]]
    inputs=[]
    for name in ['LARGE_RX_WRITE_FATAL_ACCESS','LARGE_RX_WRITE_FATAL_PARTIAL']:
        q=ROOT/native['directory']/(name+'-mmio.hex');inputs.append(q);files.append(q)
        values=[int(l,16)for l in q.read_text().splitlines()]
        if len(values)!=32 or any(not 0<=v<2**32 for v in values)or \
           sum(v<<(32*i)for i,v in enumerate(values))!=int(native['tests'][name]['full_selected1000'],16):
            raise ValueError('all32 actual native AXI words must match full checked selected1000')
    before={str(q.relative_to(ROOT)):digest(q)for q in files}
    run=Path(tempfile.mkdtemp(prefix='fatal-event-native-C-',dir=ROOT/'rdma/rnic/build'))
    ram=Path(tempfile.mkdtemp(prefix='as02-fatal-event-native-C-',dir='/dev/shm'))
    r=dict(scope=__doc__,pass_test=False,directory=str(run.relative_to(ROOT)),source_sha256=before,
        evidence={a.native_record:nid,a.runtime_audit:aid},C_compile_limit_seconds=30,runtime_limit_seconds=10,
        actual_native_AXI_snapshot_inputs=True,C_MMIO_delivery_callbacks_modeled=True,
        live_Linux_QP_callbacks=False,standard_error_CQ_STOP_global_drain_unpin=False,
        hardware_verified=False,full_board_timing=False,overall_goal_complete=False,hardware_or_default_actions=[],commit_or_push=False)
    try:
        cmd=['gcc','-std=gnu11','-O2','-Wall','-Wextra','-Werror','-I'+str(ROOT/'rdma/rnic/kernel'),
            str(files[1]),str(files[2]),'-o',str(ram/'C-test')];r['compile_command']=cmd;start=time.monotonic()
        with(run/'compile.log').open('x')as f:c=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,timeout=30)
        r.update(compile_seconds=time.monotonic()-start,compile_exit=c.returncode)
        if c.returncode:raise ValueError('real unchanged fatal reader C compile failed')
        start=time.monotonic()
        with(run/'runtime.log').open('x')as f:c=subprocess.run([str(ram/'C-test'),*map(str,inputs)],stdout=f,stderr=subprocess.STDOUT,timeout=10)
        r.update(runtime_seconds=time.monotonic()-start,runtime_exit=c.returncode)
        if c.returncode:raise ValueError('real unchanged C reader assertions failed on actual new native AXI snapshots')
        rows=[json.loads(l)for l in(run/'runtime.log').read_text().splitlines()if l.startswith('{')]
        if len(rows)!=1 or not rows[0]['pass_test']or rows[0]['assertions']!=277 or not rows[0]['MMIO_is_model']:
            raise ValueError('all277 real original C assertions and modeled callback boundary required')
        for n,h in before.items():
            if digest(ROOT/n)!=h:raise ValueError('actual source/snapshot changed:'+n)
        r.update(pass_test=True,C_summary=rows[0],actual_native_packet_AXI_snapshot_C_decode_chain=True)
    except Exception as e:r.update(error_type=type(e).__name__,error=str(e));raise
    finally:
        r['artifact_sha256']={str(q.relative_to(ROOT)):digest(q)for q in run.iterdir()if q.is_file()}
        r['RAM_artifact_sha256']={str(q):digest(q)for q in ram.iterdir()if q.is_file()}
        with a.report.open('x')as f:f.write(json.dumps(r,indent=2)+'\n')
    print(json.dumps(dict(pass_test=True,C_assertions=277,actual_native_AXI_inputs=True,live_Linux=False)))


if __name__=='__main__':main()
