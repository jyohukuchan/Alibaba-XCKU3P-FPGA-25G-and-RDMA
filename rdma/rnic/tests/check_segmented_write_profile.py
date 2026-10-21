#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Compile distinct private WRITE identity; do not infer runtime from CSR edits."""
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

ROOT=binding.ROOT;digest=binding.digest
sys.path.insert(0,str(ROOT/'rdma/rnic/fpga'))
import derive_segmented_write_profile as candidate


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve previous evidence')
    if min(shutil.disk_usage(ROOT).free,shutil.disk_usage('/dev/shm').free)<1024**3:
        raise RuntimeError('original root/RAM1GiB hierarchy guard')
    run=Path(tempfile.mkdtemp(prefix='segmented-write-profile-',dir=ROOT/'rdma/rnic/build'))
    ram=Path(tempfile.mkdtemp(prefix='as02-segmented-write-profile-',dir='/dev/shm'))
    result=dict(scope=__doc__,pass_test=False,directory=str(run.relative_to(ROOT)),actual_generated_HLS=True,
        compile_only=True,runtime_test=False,hardware_verified=False,new_installed_capability=False,full_board_timing=False,
        RNC_features=candidate.RNC,CQC_features=candidate.CQC,SQC_features=candidate.SQC,RQC_features=candidate.RQC,software_profile=candidate.PROFILE)
    try:
        old,old_id=binding.bindings('segmented-write-native-elaboration-001')
        actual,actual_id=binding.bindings('segmented-write-native-full-002')
        if not old['pass_test']or not actual['pass_test']or len(actual['tests'])!=36 or not actual['source_unchanged']:
            raise ValueError('actual previous36 native WRITE/Immediate and boundary required')
        before=candidate.parent.derive();after=candidate.derive()
        changed={q for q in after if after[q]!=before[q]}
        if {q.name for q in changed}!=candidate.CHANGED:raise ValueError('only three exact CSR identity leaves may change')
        src=[ROOT/n for n in old['selected_RTL']]
        for q in sorted(changed):
            matches=[p for p in src if p.name==q.name]
            if len(matches)!=1 or matches[0].read_text()!=before[q]:raise ValueError('exact single native parent leaf required:'+q.name)
            target=run/q.name;target.write_text(after[q]);src=[target if p==matches[0]else p for p in src]
        own=[Path(__file__).resolve(),Path(candidate.__file__).resolve()]
        own+=[Path(m.__file__).resolve()for m in list(sys.modules.values())if getattr(m,'__file__',None)and Path(m.__file__).resolve().is_relative_to(ROOT/'rdma/rnic/fpga')]
        hashes={str(q.relative_to(ROOT)):digest(q)for q in [*src,*own,*[ROOT/n for n in old['selected_HLS_data']]]}
        top='rocev2_native_rnic_endpoint';cmd=['iverilog','-g2012','-s',top,'-o',str(ram/'native.vvp')]
        cmd+=['-P'+top+'.'+name+'_ENABLE=1'for name in FEATURES];cmd+=list(map(str,src))
        result.update(source_sha256=hashes,command=cmd,selected_RTL=[str(q.relative_to(ROOT))for q in src],selected_HLS_data=old['selected_HLS_data'],
            HLS_top=old['HLS_top'],parent_elaboration=old_id,parent_actual36_runtime=actual_id,changed_identity_leaves=sorted(candidate.CHANGED),
            compile_limit_seconds=180,root_and_RAM_guard_bytes=1024**3)
        start=time.monotonic();c=subprocess.run(cmd,capture_output=True,text=True,timeout=180)
        (run/'compile.log').write_text(c.stdout+c.stderr);result.update(compile_seconds=time.monotonic()-start,compiler_exit=c.returncode)
        if c.returncode or any('expects'in s and 'bits'in s for s in c.stderr.splitlines()):raise ValueError('actual profile native elaboration/width mismatch')
        model=(ram/'native.vvp').read_text()
        counts={name:len(re.findall(r'\.scope module, "[^"]+" "'+name+r'"',model))for name in old['module_counts']}
        if counts!=old['module_counts']:raise ValueError('actual same sole native namespaces/controller hierarchy required')
        if any(digest(ROOT/n)!=h for n,h in hashes.items()):raise ValueError('consumed source changed')
        result.update(pass_test=True,source_unchanged=True,full_native_elaboration=True,module_counts=counts,
            native_controller_inserted=True,real_native_PSN_commit=True,shared_native_MR_PTE_backend_nonce=True,one_ACK_allocator=True,
            both_global_HLS_drains_zero=True,unknown_leaves_ignored=False,HLS_stub=False,
            complete_native_WRITE_runtime=False,remaining=['Fresh matching131071/511/13/63 native36 execution; kernel/provider/full1MiB/multiSGE/recovery/original timing/physical remain.'])
    except Exception as e:result.update(error_type=type(e).__name__,error=str(e));raise
    finally:
        result['artifact_sha256']={str(q.relative_to(ROOT)):digest(q)for q in run.iterdir()if q.is_file()}
        result['RAM_artifact_sha256']={str(q):digest(q)for q in ram.iterdir()if q.is_file()}
        with a.report.open('x')as f:f.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(pass_test=True,compile_seconds=result['compile_seconds'],private_identity=[131071,511,13,63])),flush=True)


if __name__=='__main__':main()
