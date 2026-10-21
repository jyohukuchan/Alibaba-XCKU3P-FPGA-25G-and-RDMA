#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Audit candidate profile8 semantics/provider and mandatory native build gate.

No kernel module, actual callback ownership, matching new native execution or
installed API proof follows. Old65535 native36 must NOT qualify131071 modules.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import audit_segmented_receive as binding

ROOT=binding.ROOT;digest=binding.digest
sys.path.insert(0,str(ROOT/'rdma/rnic/kernel'))
import derive_segmented_write_kernel as candidate
import build_segmented_write as builder


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve all prior records')
    run=Path(tempfile.mkdtemp(prefix='segmented-write-software-source-audit-',dir=ROOT/'rdma/rnic/build'))
    records={};identities={}
    for name in ['segmented-write-cq-semantics-001','provider-segmented-write-001','segmented-write-profile-native-elaboration-001','segmented-write-native-runtime-diagnostics-001']:
        records[name],identities[name]=binding.bindings(name)
    matrix=records['segmented-write-cq-semantics-001'];provider=records['provider-segmented-write-001']
    if not matrix['pass_test']or matrix['matrix_cases']!=140800 or matrix['old_and_unknown_rows_identical']!=128000 or matrix['new_wide_WRITE_rows']!=20:
        raise ValueError('complete actual old/new CQ policy matrix required')
    if not provider['pass_test']or not provider['source_unchanged']or set(provider['tests'])!={str(i)for i in range(9)} or \
       any(v['exit']for v in provider['tests'].values()):raise ValueError('actual all9 provider identities required')
    wr=provider['tests']['8']['WRITE_receive_summary']
    if not wr['zero_capacity_RQ']or wr['WC_actual_bytes']!=[0,1,4096,4097,8193,1048576]or not wr['network_order_Immediate']:
        raise ValueError('actual provider wide flags3/zeroRQ/WC checks required')
    derived=candidate.derive();old=candidate.base.derive();changed=sorted(q.name for q in derived if derived[q]!=old[q])
    wanted=['atomic_profile.h','cq_io.c','cq_io.h','device.c','native_graph.c','qp_hw.c','rnic_io.c','rnic_regs.h','sq.c','sq_io.c','verbs.c']
    if changed!=wanted:raise ValueError('only reviewed11 private kernel leaves may change')
    k=run/'kernel';k.mkdir()
    for q,t in derived.items():(k/q.name).write_text(t)
    target=run/'must-not-build.json';command=[sys.executable,str(Path(builder.__file__).resolve()),
        '--native-report',str(binding.record('segmented-write-native-full-002')),'--report',str(target)]
    c=subprocess.run(command,capture_output=True,text=True,timeout=10)
    (run/'old-tuple-rejection.log').write_text(c.stdout+c.stderr)
    if not c.returncode or target.exists()or 'exact matching new profile8 and all36 native WRITE/Immediate cases required'not in c.stderr:
        raise ValueError('actual old successful native tuple must not qualify new module build')
    own=[Path(__file__).resolve(),*[Path(m.__file__).resolve()for m in list(sys.modules.values())if getattr(m,'__file__',None)and Path(m.__file__).resolve().is_relative_to(candidate.KERNEL)]]
    result=dict(scope=__doc__,audit_passed=True,directory=str(run.relative_to(ROOT)),evidence=identities,
        verified_bindings=sum(v['bindings_verified']for v in identities.values()),
        source_sha256={str(q.relative_to(ROOT)):digest(q)for q in sorted(set(own))},
        artifact_sha256={str(q.relative_to(ROOT)):digest(q)for q in run.rglob('*')if q.is_file()},
        changed_private_kernel_leaves=changed,private_identity=dict(RNC=131071,CQC=511,SQC=13,RQC=63,profile=8),
        old_profile7_WRITE_max_bytes=4096,new_profile8_WRITE_max_bytes=1048576,
        old_successful_native_tuple_build_rejected=True,all9_provider_identities=True,actual_CQ_predicate_cases=140800,
        kernel_modules_built=False,kernel_callbacks_lifetimes_executed=False,new_matching_native36_proved=False,
        source_candidates_only=True,hardware_verified=False,installed_or_default_changes=False,
        remaining=['Actual matching profile8 native36, real-header module build, actual callback/MR/RQ/CQ retirement and unedited native snapshot consumption.',
            'Full1MiB native/multiSGE/live Linux/provider refs/recovery/partial-HLS cleanup/original timing/physical and all11 requirements remain.'])
    with a.report.open('x')as f:f.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(audit_passed=True,verified_bindings=result['verified_bindings'],old_native_tuple_rejected=True,new_matching_native_proved=False)),flush=True)


if __name__=='__main__':main()
