#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Elaborate exact new generated READ HLS RTL; NOT a runtime/timing pass.

Audit actual source/frozen/generated hashes, checked parent report/view,
original clock/geometry/space/port gates. Preserve every prior report. No
native integration, DMA/CQ, standard API, physical or timing qualification.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile
import time

ROOT=Path(__file__).resolve().parents[3]


def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--generated-report',type=Path,required=True)
    p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve previous evidence')
    report=json.loads(a.generated_report.read_text());top='rocev2_native_segmented_read_top'
    if not all(report.get(n)for n in ['pass_test','source_and_frozen_inputs_unchanged','parent_builder_unchanged',
        'wrapper_and_builder_unchanged'])or report.get('HLS_top')!=top or \
       (float(report['target_clock_period']),float(report['clock_uncertainty']),report['MAX_QPS'],report['metadata_entries'])!=(4.0,1.08,8,2000)or \
       report.get('HLS_free_space_guard_bytes')!=1500*1024*1024 or report['free_bytes_at_start']<1500*1024*1024:
        raise ValueError('original-gated exact generated READ core required')
    run=ROOT/report['directory'];frozen=run/'inputs';raw=run/'project/solution1/syn/verilog'
    inputs={a.generated_report.resolve():digest(a.generated_report),Path(__file__).resolve():digest(Path(__file__))}
    def bind(root,values):
        for n,h in values.items():
            q=root/n
            if digest(q)!=h:raise ValueError('changed evidence:'+str(q))
            if q in inputs and inputs[q]!=h:raise ValueError('conflicting evidence:'+str(q))
            inputs[q]=h
    bind(ROOT,report['source_sha256']);bind(frozen,report['frozen_sha256']);bind(raw,report['generated_sha256'])
    for n in ['parent_builder_report','checked_request_report_view']:
        q=ROOT/report[n]
        if digest(q)!=report[n+'_sha256']:raise ValueError('changed checked builder/report view')
        inputs[q]=digest(q)
    text=(raw/(top+'.v')).read_text()
    for n,width in report['generated_port_bits'].items():
        if not re.search(r'\[\s*'+str(width-1)+r'\s*:\s*0\s*\]\s*'+n+r'\s*;',text):
            raise ValueError('actual generated port width:'+n)
    evidence=Path(tempfile.mkdtemp(prefix='segmented-read-HLS-elaboration-',dir=ROOT/'rdma/rnic/build'))
    ram=Path(tempfile.mkdtemp(prefix='as02-read-HLS-elaboration-',dir='/dev/shm'))
    command=['iverilog','-g2012','-s',top,'-o',str(ram/'top'),*map(str,sorted(raw.glob('*.v')))]
    result=dict(scope=__doc__,pass_test=False,compile_only=True,runtime_test=False,hardware_verified=False,
        native_integration=False,source_sha256={str(n.relative_to(ROOT)):h for n,h in inputs.items()},
        generated_report=str(a.generated_report.resolve().relative_to(ROOT)),HLS_top=top,directory=str(evidence.relative_to(ROOT)),
        command=command,compile_limit_seconds=30,clock_ns=4.0,default_uncertainty_ns=1.08,MAX_QPS=8,metadata_entries=2000,
        actual_generated_port_bits=report['generated_port_bits'],estimated_clock_period=report['estimated_clock_period'],
        original_effective_period_met=report['original_effective_period_met'],full_board_timing=False)
    try:
        start=time.monotonic();c=subprocess.run(command,cwd=raw,capture_output=True,text=True,timeout=30)
        result['compile_seconds']=time.monotonic()-start;result['exit']=c.returncode
        (evidence/'compile.log').write_text(c.stdout+c.stderr)
        if c.returncode:raise ValueError('actual generated RTL elaboration failed')
        if any(re.search(r'(?i)(port .*expects .*bits|port .*got .*bits|wrong number of ports|dangling input port)',line)for line in c.stderr.splitlines()):
            raise ValueError('actual generated port/pin mismatch')
        if any(digest(n)!=h for n,h in inputs.items()):raise ValueError('consumed source changed')
        result.update(pass_test=True,source_unchanged=True,RAM_artifact_sha256={str(ram/'top'):digest(ram/'top')})
    except Exception as e:result.update(error_type=type(e).__name__,error=str(e));raise
    finally:
        result['artifact_sha256']={str(n.relative_to(ROOT)):digest(n)for n in evidence.iterdir()if n.is_file()}
        with a.report.open('x')as f:f.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(pass_test=True,compile_seconds=result['compile_seconds'],bindings=len(inputs),runtime_test=False,
        estimated_clock_period=result['estimated_clock_period'],original_effective_period_met=result['original_effective_period_met'])))


if __name__=='__main__':main()
