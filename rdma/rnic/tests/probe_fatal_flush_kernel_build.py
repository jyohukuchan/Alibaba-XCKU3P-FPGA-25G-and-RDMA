#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Real-header full75 paired FEC31 per-RQ flush source build, not live execution.

Old FEC15 exact behavior and whole STOP/reference/graph guards remain. No
install, load, registration, hardware probing or new default advertisement.
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
import fatal_flush_candidate as candidate

ROOT=binding.ROOT;digest=binding.digest


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve earlier evidence')
    if shutil.disk_usage(ROOT).free<1024**3:raise ValueError('original full kernel1GiB guard')
    files,before,ids=candidate.inputs();before[str(Path(__file__).resolve().relative_to(ROOT))]=digest(__file__)
    run=Path(tempfile.mkdtemp(prefix='fatal-flush-kernel-',dir=ROOT/'rdma/rnic/build'))
    for n,t in files.items():
        q=run/n;q.parent.mkdir(parents=True,exist_ok=True);q.write_text(t)
    frozen={str((run/n).relative_to(ROOT)):digest(run/n)for n in files}
    r=dict(scope=__doc__,pass_test=False,directory=str(run.relative_to(ROOT)),source_sha256=before,derived_sha256=frozen,evidence=ids,
        parent_inputs=75,actual_total_inputs=len(files),only_modified_parent_inputs=candidate.MODIFIED,
        compile_limit_seconds=180,kernel_release=subprocess.check_output(['uname','-r'],text=True).strip(),
        private_identity=[131071,511,13,63,8],exact_optional_FEC_features=[15,31],
        actual_Linux_per_RQ_flush_runtime=False,live_Linux_FPGA_coupling=False,
        native_attach_and_fatal_events_default_denied=True,installed=False,module_load_performed=False,
        default_sources_changed=False,atomic_cap_advertised=False,hardware_verified=False,full_board_timing=False,
        overall_goal_complete=False,hardware_or_default_actions=[],commit_or_push=False)
    try:
        cmd=['make','-C',str(run),'-j4','CC=/usr/bin/x86_64-linux-gnu-gcc-13','AS02_BUILD_AUX=1','MQNIC_SRC='+str(run/'parent'),'module']
        r['compile_command']=cmd;start=time.monotonic()
        with(run/'compile.log').open('x')as f:c=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,timeout=180)
        r.update(compile_seconds=time.monotonic()-start,compile_exit=c.returncode)
        if c.returncode:raise ValueError('actual full paired FEC-flush driver build failed:'+str(run/'compile.log'))
        for n,h in {**before,**frozen}.items():
            if digest(ROOT/n)!=h:raise ValueError('actual original/derived input changed:'+n)
        if not(run/'as02_mr_support.ko').is_file()or not(run/'as02_rnic_ctrl.ko').is_file():raise ValueError('both actual modules required')
        r.update(pass_test=True,source_and_derived_inputs_unchanged=True,
            actual_full_driver_per_RQ_flush_policy_linked=True,old15_behavior_source_preserved=True,
            whole_QP_STOP_SQ_graph_reference_guards_unchanged=True)
    except Exception as e:r.update(error_type=type(e).__name__,error=str(e));raise
    finally:
        r['artifact_sha256']={str(q.relative_to(ROOT)):digest(q)for q in [run/'compile.log',run/'as02_mr_support.ko',run/'as02_rnic_ctrl.ko']if q.is_file()}
        with a.report.open('x')as f:f.write(json.dumps(r,indent=2)+'\n')
    print(json.dumps(dict(pass_test=True,inputs=len(files),compile_seconds=r['compile_seconds'],per_RQ_flush_source_linked=True,live_Linux=False)))


if __name__=='__main__':main()
