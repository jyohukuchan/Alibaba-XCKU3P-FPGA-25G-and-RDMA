#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Elaborate every actual generated Atomic HLS module; compile-only evidence.

No service/native parent, packet execution, device, clock/timing or board
proof. Original fresh-native1GiB free-space guard is retained conservatively.
"""
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
import probe_atomic_shared as shared

ROOT=shared.ROOT


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build-report',type=Path,required=True)
    p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve previous evidence')
    build=json.loads(a.build_report.read_text())
    if not build.get('pass_test') or build.get('HLS_top')!='rocev2_native_atomic_top':p.error('actual completed matched HLS required')
    available=shutil.disk_usage(ROOT).free
    if available<1024**3:raise RuntimeError('unchanged1GiB fresh-native guard')
    raw=ROOT/build['directory']/'project/solution1/syn/verilog';sources=sorted(raw.glob('*.v'))
    before={str((raw/n).relative_to(ROOT)):h for n,h in build['generated_sha256'].items()}
    before.update({str(x.resolve().relative_to(ROOT)):shared.digest(x)for x in [a.build_report,Path(__file__)]})
    if before!={n:shared.digest(ROOT/n)for n in before}:raise ValueError('generated evidence changed')
    run=Path(tempfile.mkdtemp(prefix='atomic-core-elaboration-',dir=ROOT/'rdma/rnic/build'))
    report=dict(scope=__doc__,pass_test=False,source_sha256=before,run=str(run.relative_to(ROOT)),
        compile_only=True,hardware_verified=False,native_integrated=False,generated_modules=len(sources),
        free_bytes_at_start=available,free_space_guard_bytes=1024**3)
    try:
        command=['iverilog','-g2012','-s',build['HLS_top'],'-o',str(run/'core.vvp'),*map(str,sources)]
        start=time.monotonic();c=subprocess.run(command,capture_output=True,text=True,timeout=180)
        report['compile_seconds']=time.monotonic()-start;(run/'compile.log').write_text(c.stdout+c.stderr)
        if c.returncode:raise RuntimeError(c.stdout+c.stderr)
        text=(run/'core.vvp').read_text();top=len(re.findall(r'\.scope module, "[^"]+" "rocev2_native_atomic_top"',text))
        if top!=1:raise ValueError('unexpected generated top multiplicity')
        shared_counts={name:len(re.findall(r'\.scope module, "'+name+r'"',text))for name in
            ['state_table_0_U0','msn_table_0_U0','rx_ibh_fsm_0_U0','rx_exh_fsm_512_0_U0','atomic_commit_U']}
        if not all(v==1 for v in shared_counts.values()):raise ValueError(('duplicate/missing shared consumer',shared_counts))
        if before!={n:shared.digest(ROOT/n)for n in before}:raise ValueError('inputs changed')
        report.update(pass_test=True,source_unchanged=True,actual_top_instances=top,
            actual_shared_consumer_instances=shared_counts,
            artifact_sha256={str((run/'core.vvp').relative_to(ROOT)):shared.digest(run/'core.vvp')})
    except Exception as e:report['error']=str(e);raise
    finally:
        with a.report.open('x')as out:out.write(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k]for k in ['pass_test','compile_seconds','generated_modules','actual_top_instances','run']}))


if __name__=='__main__':main()
