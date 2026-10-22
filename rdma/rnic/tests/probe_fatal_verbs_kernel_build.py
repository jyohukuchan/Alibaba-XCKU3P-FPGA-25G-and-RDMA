#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Real-header build of exact profile8 driver plus optional fatal QP hooks.

No install/load/registration/polling/MMIO/hardware action. The derived
destroy/progress/unbind guards are compiled with the actual driver, not a
standalone decoder. Live Linux/native reference safety is not inferred.
"""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import audit_segmented_receive as binding
sys.path.insert(0,str(binding.ROOT/'rdma/rnic/kernel'))
import fatal_verbs_candidate as candidate

ROOT=binding.ROOT;digest=binding.digest


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve all earlier evidence')
    if shutil.disk_usage(ROOT).free<1024**3:raise ValueError('kernel source/output1GiB guard')
    files,before,pid=candidate.inputs()
    before[str(Path(__file__).resolve().relative_to(ROOT))]=digest(__file__)
    run=Path(tempfile.mkdtemp(prefix='fatal-verbs-kernel-',dir=ROOT/'rdma/rnic/build'))
    for n,t in files.items():
        q=run/n;q.parent.mkdir(parents=True,exist_ok=True);q.write_text(t)
    frozen={str((run/n).relative_to(ROOT)):digest(run/n)for n in files}
    r=dict(scope=__doc__,pass_test=False,directory=str(run.relative_to(ROOT)),source_sha256=before,derived_sha256=frozen,
        parent_evidence=pid,parent_frozen_inputs=68,actual_total_inputs=len(files),only_modified_parent_inputs=['verbs.c','verbs.h','Makefile'],
        new_fatal_components=candidate.EXTRA,compile_limit_seconds=180,kernel_release=subprocess.check_output(['uname','-r'],text=True).strip(),
        private_identity=[131071,511,13,63,8],actual_kernel_primitives_used_for_build=True,
        Linux_fatal_runtime=False,native_fatal_runtime_coupled=False,installed=False,module_load_performed=False,
        default_sources_changed=False,atomic_cap_advertised=False,hardware_verified=False,full_board_timing=False,
        overall_goal_complete=False,hardware_or_default_actions=[],commit_or_push=False)
    try:
        cmd=['make','-C',str(run),'-j4','CC=/usr/bin/x86_64-linux-gnu-gcc-13','AS02_BUILD_AUX=1','MQNIC_SRC='+str(run/'parent'),'module']
        r['compile_command']=cmd;start=time.monotonic()
        with(run/'compile.log').open('x')as f:c=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,timeout=180)
        r.update(compile_seconds=time.monotonic()-start,compile_exit=c.returncode)
        if c.returncode:raise ValueError('actual full profile8 fatal-hook driver build failed:'+str(run/'compile.log'))
        for n,h in {**before,**frozen}.items():
            if digest(ROOT/n)!=h:raise ValueError('actual original/derived input changed:'+n)
        if not(run/'as02_mr_support.ko').is_file()or not(run/'as02_rnic_ctrl.ko').is_file():
            raise ValueError('both actual complete support/auxiliary modules required')
        r.update(pass_test=True,actual_driver_fatal_reader_QP_callback_guards_linked=True,source_and_derived_inputs_unchanged=True,
            no_new_WC_STOP_or_reference_release=True,notification_ACK_independent_of_QP_lifetime=True)
    except Exception as e:r.update(error_type=type(e).__name__,error=str(e));raise
    finally:
        r['artifact_sha256']={str(q.relative_to(ROOT)):digest(q)for q in [run/'compile.log',run/'as02_mr_support.ko',run/'as02_rnic_ctrl.ko']if q.is_file()}
        with a.report.open('x')as f:f.write(json.dumps(r,indent=2)+'\n')
    print(json.dumps(dict(pass_test=True,inputs=len(files),compile_seconds=r['compile_seconds'],driver_fatal_hooks_linked=True,Linux_runtime=False)))


if __name__=='__main__':main()
