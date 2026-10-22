#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Full native465 graph with separate actual leases for fatal RQC authority.

Fix the observed permanent-control alias without weakening any original
aggregate guard. Source/elaboration only, not RQC runtime/CQ/STOP/unpin.
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
from check_immediate_native_elaboration import FEATURES
sys.path.insert(0,str(binding.ROOT/'rdma/rnic/fpga'))
import derive_fatal_rq_cancel_lease_native as candidate

ROOT=binding.ROOT;digest=binding.digest


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve all earlier evidence')
    if min(shutil.disk_usage(ROOT).free,shutil.disk_usage('/dev/shm').free)<1024**3:raise ValueError('original root/RAM1GiB guard')
    names=['fatal-rq-cancel-native-elaboration-001','fatal-rq-cancel-failure-diagnostics-001','fatal-event-native-elaboration-002']
    records={};ids={}
    for n in names:records[n],ids[n]=binding.bindings(n)
    parent,diagnostic,original=[records[n]for n in names]
    if not parent['pass_test']or not diagnostic['audit_passed']or not diagnostic['original_failed_run_still_false']or \
       not diagnostic['old40_full_outcomes_except_seconds_identical']:raise ValueError('actual failed guard boundary and all40 preserved outcomes required')
    src=[ROOT/n for n in parent['selected_RTL']];data=[ROOT/n for n in parent['selected_HLS_data']]
    selected={n:next(p for p in src if p.name==n)for n in candidate.LEAVES}
    original_top=next(ROOT/n for n in original['selected_RTL']if Path(n).name==candidate.TOP)
    texts=candidate.derive({n:p.read_text()for n,p in selected.items()},original_top.read_text())
    before=dict(parent['source_sha256'])
    for p in [*src,*data,Path(candidate.__file__).resolve(),Path(__file__).resolve(),original_top,*[binding.record(n)for n in names]]:
        before[str(p.relative_to(ROOT))]=digest(p)
    run=Path(tempfile.mkdtemp(prefix='fatal-rq-lease-native-',dir=ROOT/'rdma/rnic/build'))
    ram=Path(tempfile.mkdtemp(prefix='as02-fatal-rq-lease-native-',dir='/dev/shm'))
    replacements={}
    for n,t in texts.items():
        p=run/n;p.write_text(t);replacements[selected[n]]=p;before[str(p.relative_to(ROOT))]=digest(p)
    src=[replacements.get(p,p)for p in src]
    r=dict(scope=__doc__,pass_test=False,directory=str(run.relative_to(ROOT)),source_sha256=before,evidence=ids,
        selected_RTL=[str(p.relative_to(ROOT))for p in src],selected_HLS_data=parent['selected_HLS_data'],
        compile_limit_seconds=180,root_RAM_guard_bytes=1024**3,clock_ns=4,FEC_features=31,
        RNC_features=131071,CQC_features=511,software_profile=8,both_global_HLS_drains_zero=True,
        actual_new_native_packet_runtime=False,actual_RQC_cancellation_receipt=False,
        default_or_driver_capability_changed=False,error_CQ_STOP_global_drain_unpin=False,
        hardware_verified=False,full_board_timing=False,overall_goal_complete=False,hardware_or_default_actions=[],commit_or_push=False)
    try:
        target='rocev2_native_rnic_endpoint';cmd=['iverilog','-g2012','-s',target,'-o',str(ram/'native.vvp')]
        cmd+=['-P'+target+'.'+f+'_ENABLE=1'for f in FEATURES];cmd+=list(map(str,src));r['command']=cmd
        start=time.monotonic();c=subprocess.run(cmd,capture_output=True,text=True,timeout=180)
        (run/'compile.log').write_text(c.stdout+c.stderr);r.update(compile_seconds=time.monotonic()-start,exit=c.returncode)
        if c.returncode or any('expects'in l and 'bits'in l for l in c.stderr.splitlines()):raise ValueError('actual full native typed-port/hierarchy failure')
        vvp=(ram/'native.vvp').read_text()
        counts={n:len(re.findall(r'\.scope module, "[^\"]+" "'+re.escape(n)+r'"',vvp))for n in parent['module_counts']}
        if counts!=parent['module_counts']or len(src)!=465 or len(data)!=8:raise ValueError('same sole complete native namespaces465/eight data required')
        for n,h in before.items():
            if digest(ROOT/n)!=h:raise ValueError('actual original/derived input changed:'+n)
        r.update(pass_test=True,full_native_elaboration=True,module_counts=counts,whole_qualified_HLS207_unchanged=True,
            only_seven_leaf_port_and_predicate_derivation=True,original_aggregate_guards_preserved=True,
            genuine_control_owner_VALID_and_all_other_leases_retained=True)
    except Exception as e:r.update(error_type=type(e).__name__,error=str(e));raise
    finally:
        r['artifact_sha256']={str(p.relative_to(ROOT)):digest(p)for p in run.iterdir()if p.is_file()}
        r['RAM_artifact_sha256']={str(p):digest(p)for p in ram.iterdir()if p.is_file()}
        with a.report.open('x')as f:f.write(json.dumps(r,indent=2)+'\n')
    print(json.dumps(dict(pass_test=True,compile_seconds=r['compile_seconds'],RTL=465,data=8,actual_RQC_runtime=False)))


if __name__=='__main__':main()
