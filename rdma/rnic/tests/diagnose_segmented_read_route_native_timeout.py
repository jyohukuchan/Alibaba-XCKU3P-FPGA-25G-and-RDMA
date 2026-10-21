#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Same failed frozen native binary/inputs, line-buffered diagnostics <=30s.

No new-source/native success claim: preserve the original timed-out run and
binary, copy exact readmem inputs into a separate directory, observe progress
without changing RTL, inputs, expected results, deadlines or hardware.
"""
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
import probe_immediate_native_request as tool

ROOT=tool.ROOT;digest=tool.digest


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--failed-report',type=Path,required=True);p.add_argument('--report',type=Path,required=True)
    a=p.parse_args()
    if a.report.exists():p.error('preserve prior diagnostic')
    failed=json.loads(a.failed_report.read_text())
    if failed.get('pass_test')or failed.get('error_type')!='TimeoutExpired' or failed.get('simulation_limit_seconds')!=30:
        raise ValueError('exact failed30s frozen runtime required')
    for field in ['source_sha256','artifact_sha256','RAM_artifact_sha256']:
        for n,h in failed[field].items():
            q=Path(n);q=q if q.is_absolute()else ROOT/q
            if digest(q)!=h:raise ValueError('original timed-out input changed:'+n)
    binary=Path(failed['frozen_binary_path'])
    if digest(binary)!=failed['binary_sha256']:raise ValueError('preserved original binary required')
    run=Path(tempfile.mkdtemp(prefix='read-route-timeout-diagnostic-',dir=ROOT/'rdma/rnic/build'))
    inputs=[q for q in (ROOT/failed['directory']).iterdir()if q.suffix in ['.hex','.dat']]
    before={str(q.relative_to(ROOT)):digest(q)for q in [*inputs,Path(__file__).resolve(),a.failed_report.resolve()]}
    for q in inputs:shutil.copy2(q,run/q.name)
    report=dict(scope=__doc__,audit_pass=False,native_pass_claim=False,hardware_verified=False,
        directory=str(run.relative_to(ROOT)),source_sha256=before,binary_path=str(binary),binary_sha256=digest(binary),
        simulation_limit_seconds=30,line_buffered_stdout=True,tests_or_inputs_relaxed=False,
        original_failed_report=str(a.failed_report),original_failed_model_modified=False)
    try:
        command=['stdbuf','-oL','-eL',str(binary),'+LARGE_READ'];report['command']=command
        start=time.monotonic()
        with(run/'simulation.log').open('x')as log:
            try:
                c=subprocess.run(command,cwd=run,stdout=log,stderr=subprocess.STDOUT,timeout=30,preexec_fn=tool.no_core)
                report.update(exit=c.returncode,timed_out=False)
            except subprocess.TimeoutExpired:report.update(exit=None,timed_out=True)
        report['seconds']=time.monotonic()-start
        output=(run/'simulation.log').read_text(errors='replace')
        progress=[int(n)for n in re.findall(r'^MAIN_PROGRESS cycle(\d+)',output,re.M)]
        report.update(last_progress_cycle=progress[-1]if progress else None,
            actual_descriptor_lines=[l for l in output.splitlines()if l.startswith('PAGE_DMA ')],
            TLP_writes=len(re.findall(r'^TLP_WRITE ',output,re.M)),
            fault_lines=[l for l in output.splitlines()if any(s in l for s in ['FATAL','%Fatal','%Error','NATIVE_ROUTE_FAULT','NATIVE_SUBFAULTS'])],
            final_lines=output.splitlines()[-15:])
        if any(digest(ROOT/n)!=h for n,h in before.items())or digest(binary)!=report['binary_sha256']:
            raise ValueError('original failed evidence changed')
        report.update(audit_pass=True,source_and_binary_unchanged=True)
    except Exception as e:report.update(error_type=type(e).__name__,error=str(e));raise
    finally:
        report['artifact_sha256']={str(q.relative_to(ROOT)):digest(q)for q in run.iterdir()if q.is_file()}
        with a.report.open('x')as f:f.write(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k]for k in ['audit_pass','timed_out','last_progress_cycle','TLP_writes','fault_lines','directory']}))


if __name__=='__main__':main()
