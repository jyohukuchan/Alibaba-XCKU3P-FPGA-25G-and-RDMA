#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual generated pointer/lock consumer, NOT full retransmission/core drain."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import time

ROOT=Path(__file__).resolve().parents[3]
BENCH=Path(__file__).resolve().with_name('retrans_pointer_fence_tb.v')
TB=BENCH.read_text()

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source-record',type=Path,required=True)
    p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve earlier evidence')
    r=json.loads(a.source_record.read_text());assert r['pass_test'] and r['HLS_constructed']
    directory=ROOT/r['retained_directory'];rtl=directory/'project/solution1/syn/verilog'
    sources=sorted(rtl.glob('*.v'));data=sorted(rtl.glob('*.dat'))
    before={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest()for n in r['generated_sha256']}
    assert before==r['generated_sha256']
    own=[Path(__file__).resolve(),BENCH,a.source_record.resolve()]
    inputs={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in own}
    run=Path(tempfile.mkdtemp(prefix='pointer-fence-RTL-',dir=ROOT/'rdma/rnic/build'))
    (run/'tb.v').write_text(TB)
    import shutil
    shutil.copy2(Path(__file__).resolve(),run/'driver.py')
    shutil.copy2(BENCH,run/BENCH.name)
    for d in data:shutil.copy2(d,run/d.name)
    result=dict(scope=__doc__,pass_test=False,terminal_exit_status=None,retained_directory=str(run.relative_to(ROOT)),
        source_record=str(a.source_record),source_sha256={**before,**inputs},bench_sha256=hashlib.sha256(TB.encode()).hexdigest(),
        actual_generated_HLS=True,four_state_simulation=True,whole_core_drain=False,hardware_verified=False,physical_signoff=False)
    try:
        c=subprocess.run(['iverilog','-g2012','-s','tb','-o',str(run/'test.vvp'),str(run/'tb.v'),*map(str,sources)],capture_output=True,text=True,timeout=30)
        (run/'compile.log').write_text(c.stdout+c.stderr)
        if c.returncode:raise RuntimeError('RTL compile failed; retain '+str(run))
        started=time.monotonic()
        s=subprocess.run(['vvp',str(run/'test.vvp')],cwd=run,capture_output=True,text=True,timeout=30)
        result['simulation_seconds']=time.monotonic()-started
        (run/'simulation.log').write_text(s.stdout+s.stderr)
        if s.returncode:raise RuntimeError('actual pointer RTL failed; retain '+str(run))
        rows=[json.loads(l[len('POINTER_FENCE_RTL '):])for l in s.stdout.splitlines()if l.startswith('POINTER_FENCE_RTL ')]
        if len(rows)!=1 or not rows[0]['pass_test']:raise ValueError('missing actual RTL result')
        assert before=={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest()for n in before}
        assert inputs=={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest()for n in inputs}
        result.update(pass_test=True,terminal_exit_status=0,summary=rows[0])
    except Exception as e:result.update(terminal_exit_status=1,error=str(e),error_type=type(e).__name__);raise
    finally:
        result['artifact_sha256']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in run.iterdir()if p.is_file()}
        with a.report.open('x')as out:out.write(json.dumps(result,indent=2)+'\n')

if __name__=='__main__':main()
