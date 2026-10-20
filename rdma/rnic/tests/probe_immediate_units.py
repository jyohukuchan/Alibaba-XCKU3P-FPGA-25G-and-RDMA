#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Record bounded actual-C/four-state candidate/default units; NOT full RNIC."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile
import time

ROOT=Path(__file__).resolve().parents[3]
TESTS=ROOT/'rdma/rnic/tests'
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True)
    p.add_argument('--receive',action='store_true');a=p.parse_args()
    if a.report.exists():p.error('preserve previous evidence')
    inputs=[x for d in [ROOT/'rdma/rnic/kernel',ROOT/'rdma/rnic/rtl',TESTS]for x in d.iterdir()
            if x.is_file()and x.suffix in ['.py','.c','.h','.v']]
    before={str(x.relative_to(ROOT)):digest(x)for x in inputs}
    run=Path(tempfile.mkdtemp(prefix='immediate-units-',dir=ROOT/'rdma/rnic/build'))
    command=['python3','-m','unittest','-q','test_wqe_codec','test_wqe_admission_rtl','test_sq_wqe_admission_rtl',
        'test_wqe_hls_sq_rtl','test_kernel_queue_lifecycle','test_immediate_wqe','test_immediate_admission_rtl','test_immediate_hls_sq_rtl']
    if a.receive:command+=['test_receive_queue_rtl','test_receive_ack_rtl','test_message_cq_rtl','test_cq_path_rtl',
        'test_kernel_cq','test_kernel_verbs','test_immediate_receive_lifetime_rtl','test_immediate_cq_context_rtl']
    expected=78 if a.receive else 46
    report=dict(scope=__doc__,pass_test=False,source_sha256=before,directory=str(run.relative_to(ROOT)),command=command,
        hardware_verified=False,full_generated_native_runtime=False,actual_Immediate_post_send=False,
        actual_C_UBSan_and_kernel_library_ASan=True,four_state_leaf_RTL=True,
        models=['Linux primitives/coherent DMA and HW callbacks','SQ fetch result source','HLS/executor in staging-only units'])
    try:
        start=time.monotonic();r=subprocess.run(command,cwd=TESTS,capture_output=True,text=True,timeout=120)
        report['total_seconds']=time.monotonic()-start;(run/'test.log').write_text(r.stdout+r.stderr)
        if r.returncode:raise RuntimeError('short unit suite failed: '+str(run/'test.log'))
        match=re.search(r'Ran (\d+) tests in ([\d.]+)s',r.stdout+r.stderr)
        if not match or int(match[1])!=expected:raise ValueError('missing full'+str(expected)+'-method result')
        if before!={n:digest(ROOT/n)for n in before}:raise ValueError('unit source changed during run')
        report.update(pass_test=True,source_unchanged=True,methods=expected,terminal_exit_status=0,test_log_sha256=digest(run/'test.log'))
    except Exception as e:report.update(error=str(e));raise
    finally:
        with a.report.open('x')as f:f.write(json.dumps(report,indent=2)+'\n')
    print(json.dumps({n:report[n]for n in ['pass_test','methods','total_seconds','directory']}))

if __name__=='__main__':main()
