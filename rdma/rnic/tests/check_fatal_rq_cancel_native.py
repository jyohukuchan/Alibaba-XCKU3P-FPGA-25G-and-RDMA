#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Elaborate optional fatal-join-authorized RQC cancellation in the full core.

Only RQC command4 may distinguish permanent quarantine from a live lease.
Genuine cancellation/fetch/parent/work/wire/CQ and full owner proofs remain.
Not packet runtime, cancellation receipt, CQ, STOP, global drain or unpin.
"""
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import audit_segmented_receive as binding
import fatal_event_native_sources as parent_source
from check_immediate_native_elaboration import FEATURES

ROOT=binding.ROOT;digest=binding.digest
sys.path.insert(0,str(ROOT/'rdma/rnic/fpga'))
import derive_fatal_rq_cancel_native as candidate

NAMES=['fatal-event-native-full-001','fatal-event-native-runtime-diagnostics-001',
    'fatal-rq-authority-001']


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve earlier evidence')
    if min(shutil.disk_usage(ROOT).free,shutil.disk_usage('/dev/shm').free)<1024**3:
        raise ValueError('original root/RAM1GiB guard')
    parent,parent_ids=parent_source.validate(parent_source.ELABORATION)
    records={};ids={}
    for n in NAMES:records[n],ids[n]=binding.bindings(n)
    native,runtime,component=[records[n]for n in NAMES]
    if not all(r.get('pass_test',r.get('audit_passed'))for r in records.values()) or \
       len(native['tests'])!=40 or len(component['tests'])!=33 or not component['four_state'] or \
       component['actual_new_native_wiring'] or not runtime['all40_old_full_outcomes_except_seconds_identical']:
        raise ValueError('actual full FEC-native40 regression and separate four-state authority33 required')
    src=[ROOT/n for n in parent['selected_RTL']];data=[ROOT/n for n in parent['selected_HLS_data']]
    top,sq,control,fec=[next(q for q in src if q.name==n)for n in [
        'rocev2_native_rnic_endpoint.v','rocev2_native_sq_endpoint.v',
        'rocev2_sq_control_regs.v','rocev2_fatal_event_mmio.v']]
    texts=candidate.derive(*[q.read_text()for q in [top,sq,control,fec]])
    before=dict(parent['source_sha256'])
    for q in [*src,*data,candidate.AUTHORITY,Path(candidate.__file__).resolve(),
              Path(__file__).resolve(),Path(parent_source.__file__).resolve(),*[binding.record(n)for n in NAMES]]:
        before[str(q.relative_to(ROOT))]=digest(q)
    run=Path(tempfile.mkdtemp(prefix='fatal-rq-cancel-native-',dir=ROOT/'rdma/rnic/build'))
    ram=Path(tempfile.mkdtemp(prefix='as02-fatal-rq-cancel-native-',dir='/dev/shm'))
    leaves=[run/n for n in [top.name,sq.name,'rocev2_fatal_rq_control_regs.v',fec.name]]
    for q,t in zip(leaves,texts):q.write_text(t);before[str(q.relative_to(ROOT))]=digest(q)
    replacements={top:leaves[0],sq:leaves[1],fec:leaves[3]}
    selected=[replacements.get(q,q)for q in src]+[leaves[2],candidate.AUTHORITY]
    r=dict(scope=__doc__,pass_test=False,directory=str(run.relative_to(ROOT)),source_sha256=before,
        evidence=ids,parent_evidence=parent_ids,
        selected_RTL=[str(q.relative_to(ROOT))for q in selected],selected_HLS_data=parent['selected_HLS_data'],
        compile_limit_seconds=180,root_RAM_guard_bytes=1024**3,clock_ns=4,software_profile=8,
        RNC_features=parent['RNC_features'],CQC_features=parent['CQC_features'],FEC_features=31,
        default_or_driver_capability_changed=False,both_global_HLS_drains_zero=True,
        actual_new_native_packet_runtime=False,actual_RQC_cancellation_receipt=False,
        error_CQ_STOP_global_drain_unpin=False,hardware_verified=False,full_board_timing=False,
        hardware_or_default_actions=[],commit_or_push=False,overall_goal_complete=False)
    try:
        target='rocev2_native_rnic_endpoint'
        cmd=['iverilog','-g2012','-s',target,'-o',str(ram/'native.vvp')]
        cmd+=['-P'+target+'.'+n+'_ENABLE=1'for n in FEATURES];cmd+=list(map(str,selected));r['command']=cmd
        start=time.monotonic();c=subprocess.run(cmd,capture_output=True,text=True,timeout=180)
        (run/'compile.log').write_text(c.stdout+c.stderr);r.update(compile_seconds=time.monotonic()-start,exit=c.returncode)
        if c.returncode or any('expects'in l and 'bits'in l for l in c.stderr.splitlines()):
            raise ValueError('actual complete native hierarchy/typed width failure')
        wanted=dict(parent['module_counts']);assert wanted['rocev2_sq_control_regs']==2
        wanted.update(rocev2_sq_control_regs=1,rocev2_fatal_rq_control_regs=1,rocev2_fatal_rq_cancel_authority=1)
        vvp=(ram/'native.vvp').read_text()
        counts={n:len(re.findall(r'\.scope module, "[^\"]+" "'+re.escape(n)+r'"',vvp))for n in wanted}
        if counts!=wanted:raise ValueError('sole actual HLS/MR/PTE/nonce/ACK namespaces and one distinct RQC required')
        for n,h in before.items():
            if digest(ROOT/n)!=h:raise ValueError('actual input changed:'+n)
        if len(selected)!=465 or len(data)!=8:raise ValueError('complete465 RTL/8data cohort required')
        r.update(pass_test=True,full_native_elaboration=True,module_counts=counts,
            only_three_parent_leaves_replaced_plus_RQC_variant_and_authority=True,
            whole_qualified_HLS207_unchanged=True,actual_upstream_join_handshake_after_both_receivers=True,
            only_RQC_command4_quarantine_distinction=True,
            permanent_configuration_and_admission_quarantine_preserved=True)
    except Exception as e:r.update(error_type=type(e).__name__,error=str(e));raise
    finally:
        r['artifact_sha256']={str(q.relative_to(ROOT)):digest(q)for q in run.iterdir()if q.is_file()}
        r['RAM_artifact_sha256']={str(q):digest(q)for q in ram.iterdir()if q.is_file()}
        with a.report.open('x')as f:f.write(json.dumps(r,indent=2)+'\n')
    print(json.dumps(dict(pass_test=True,compile_seconds=r['compile_seconds'],RTL=len(selected),data=len(data),
        actual_RQC_cancellation_receipt=False)))


if __name__=='__main__':main()
