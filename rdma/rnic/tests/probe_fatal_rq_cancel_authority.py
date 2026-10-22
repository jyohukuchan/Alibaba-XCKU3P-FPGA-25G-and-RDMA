#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Four-state fatal RQC cancellation-authority RTL on qualified native seeds.

Actual completed native1000 records are replayed. Producer/handshake/current
context/other leases are MODELS; not native cancellation/CQ/STOP/drain/unpin.
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
    if a.report.exists():p.error('preserve all earlier evidence')
    native,nid=binding.bindings('fatal-event-native-full-001');audit,aid=binding.bindings('fatal-event-native-runtime-diagnostics-001')
    if not native['pass_test']or len(native['tests'])!=40 or not audit['audit_passed']:
        raise ValueError('actual full native40/1000 owner/AXI/old40 runtime qualification required')
    files=[ROOT/'rdma/rnic/rtl/rocev2_fatal_rq_cancel_authority.v',ROOT/'rdma/rnic/tests/tb_fatal_rq_cancel_authority.v',Path(__file__).resolve()]
    run=Path(tempfile.mkdtemp(prefix='fatal-rq-authority-',dir=ROOT/'rdma/rnic/build'))
    ram=Path(tempfile.mkdtemp(prefix='as02-fatal-rq-authority-',dir='/dev/shm'))
    for i,n in enumerate(['LARGE_RX_WRITE_FATAL_ACCESS','LARGE_RX_WRITE_FATAL_PARTIAL']):
        q=ROOT/native['directory']/(n+'-mmio.hex');files.append(q)
        words=[int(l,16)for l in q.read_text().splitlines()]
        if len(words)!=32 or sum(v<<(j*32)for j,v in enumerate(words))!=int(native['tests'][n]['full_selected1000'],16):
            raise ValueError('exact unedited real native AXI certificate seed required')
        shutil.copy2(q,run/('seed'+str(i)+'.hex'))
    before={str(q.relative_to(ROOT)):digest(q)for q in files}
    r=dict(scope=__doc__,pass_test=False,directory=str(run.relative_to(ROOT)),source_sha256=before,
        evidence={'fatal-event-native-full-001':nid,'fatal-event-native-runtime-diagnostics-001':aid},clock_ns=4,
        compile_limit_seconds=10,runtime_limit_seconds=10,cycle_limit=100000,four_state=True,
        producer_live_context_and_lease_signals_modeled=True,actual_new_native_wiring=False,
        cancellation_receipt_or_CQ_STOP_global_drain_unpin=False,hardware_verified=False,full_board_timing=False,
        overall_goal_complete=False,hardware_or_default_actions=[],commit_or_push=False,tests={})
    try:
        cmd=['iverilog','-g2012','-s','tb','-o',str(ram/'test'),str(files[1]),str(files[0])];r['compile_command']=cmd;start=time.monotonic()
        with(run/'compile.log').open('x')as f:c=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,timeout=10)
        r.update(compile_seconds=time.monotonic()-start,compile_exit=c.returncode)
        if c.returncode:raise ValueError('actual authority RTL compile failed')
        for mode in range(33):
            start=time.monotonic()
            with(run/(str(mode)+'.log')).open('x')as f:c=subprocess.run(['vvp',str(ram/'test'),'+MODE='+str(mode)],cwd=run,stdout=f,stderr=subprocess.STDOUT,timeout=10)
            r['tests'][str(mode)]=dict(exit=c.returncode,seconds=time.monotonic()-start)
            if c.returncode:raise ValueError('actual four-state cancellation authority assertion failed mode'+str(mode))
            rows=[json.loads(l.split(' ',1)[1])for l in(run/(str(mode)+'.log')).read_text().splitlines()if l.startswith('FATAL_RQ_AUTHORITY_RESULT ')]
            if len(rows)!=1 or not rows[0]['pass_test']:raise ValueError('actual bounded authority result missing')
            r['tests'][str(mode)]['summary']=rows[0]
        for n,h in before.items():
            if digest(ROOT/n)!=h:raise ValueError('original/actual source changed:'+n)
        r.update(pass_test=True,component_cases=33,real_join_receipt_not_host_ACK_is_required=True,
            no_other_lease_can_be_hidden=True,current_full_owner_PSN_quarantine_required=True)
    except Exception as e:r.update(error_type=type(e).__name__,error=str(e));raise
    finally:
        r['artifact_sha256']={str(q.relative_to(ROOT)):digest(q)for q in run.iterdir()if q.is_file()}
        r['RAM_artifact_sha256']={str(q):digest(q)for q in ram.iterdir()if q.is_file()}
        with a.report.open('x')as f:f.write(json.dumps(r,indent=2)+'\n')
    print(json.dumps(dict(pass_test=True,four_state_cases=33,native_seeds=2,actual_cancel_or_drain=False)))


if __name__=='__main__':main()
