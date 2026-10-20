#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""FOUR-STATE generated FNS process/tables + production2000slot pool.

Input producers and diagnostic mux are bench-only, not native producer fences.
Real pool zero with real outputs held explicitly disproves whole-core drain.
No actual board, native memory, RDMA payload/CQ or standard verbs completion.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
ROOT=Path(__file__).resolve().parents[3]
BENCH=Path(__file__).resolve().with_name('owned_retrans_tb.v')
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source-record',type=Path,required=True)
    p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve earlier evidence')
    r=json.loads(a.source_record.read_text());assert r['pass_test'] and r['HLS_constructed']
    rtl=ROOT/r['retained_directory']/'project/solution1/syn/verilog'
    pool=ROOT/'rdma/rnic/rtl/rocev2_retrans_pool.v'
    wrapper=ROOT/'rdma/rnic/rtl/rocev2_owned_retrans.v'
    wrapper_tb=BENCH.with_name('owned_retrans_wrapper_tb.v')
    own=[Path(__file__).resolve(),BENCH,a.source_record.resolve(),pool,wrapper,wrapper_tb]
    before={**r['generated_sha256'],**{str(q.relative_to(ROOT)):digest(q)for q in own}}
    assert before=={n:digest(ROOT/n)for n in before}
    assert digest(pool)==r['source_sha256'][str(pool.relative_to(ROOT))]
    run=Path(tempfile.mkdtemp(prefix='owned-retrans-RTL-',dir=ROOT/'rdma/rnic/build'))
    for q in own:shutil.copy2(q,run/q.name)
    for q in rtl.glob('*.dat'):shutil.copy2(q,run/q.name)
    result=dict(scope=__doc__,pass_test=False,terminal_exit_status=None,retained_directory=str(run.relative_to(ROOT)),
        source_record=str(a.source_record),source_sha256=before,actual_generated_HLS=True,actual_production_pool=True,
        four_state_simulation=True,whole_core_drain=False,hardware_verified=False,physical_signoff=False,
        native_CQ_or_standard_verbs=False,simulations=[])
    try:
        cmd=['iverilog','-g2012','-s','tb','-o',str(run/'test.vvp'),str(run/BENCH.name),str(run/pool.name),*map(str,sorted(rtl.glob('*.v')))]
        (run/'compile-command.json').write_text(json.dumps(cmd,indent=2)+'\n')
        print(json.dumps(dict(directory=str(run),phase='compile_actual_RTL')),flush=True)
        t=time.monotonic();c=subprocess.run(cmd,capture_output=True,text=True,timeout=60)
        result['compile_seconds']=time.monotonic()-t;(run/'compile.log').write_text(c.stdout+c.stderr)
        if c.returncode:raise RuntimeError('actual RTL compile failed; retain '+str(run))
        for case in range(1,7):
            t=time.monotonic();s=subprocess.run(['vvp',str(run/'test.vvp'),'+CASE='+str(case)],cwd=run,capture_output=True,text=True,timeout=30)
            elapsed=time.monotonic()-t;(run/('case-%d.log'%case)).write_text(s.stdout+s.stderr)
            if s.returncode:raise RuntimeError('actual RTL case%d failed; retain %s'%(case,run))
            rows=[json.loads(l[len('OWNED_RETRANS_RTL '):])for l in s.stdout.splitlines()if l.startswith('OWNED_RETRANS_RTL ')]
            assert len(rows)==1 and rows[0]['pass_test'] and rows[0]['case']==case
            result['simulations'].append(dict(case=case,seconds=elapsed,summary=rows[0]))
            print(json.dumps(result['simulations'][-1]),flush=True)
        cmd=['iverilog','-g2012','-s','wrapper_tb','-o',str(run/'wrapper.vvp'),str(run/wrapper_tb.name),
            str(run/wrapper.name),str(run/pool.name),*map(str,sorted(rtl.glob('*.v')))]
        (run/'wrapper-compile-command.json').write_text(json.dumps(cmd,indent=2)+'\n')
        t=time.monotonic();c=subprocess.run(cmd,capture_output=True,text=True,timeout=60)
        result['wrapper_compile_seconds']=time.monotonic()-t;(run/'wrapper-compile.log').write_text(c.stdout+c.stderr)
        if c.returncode:raise RuntimeError('production wrapper compile failed; retain '+str(run))
        t=time.monotonic();s=subprocess.run(['vvp',str(run/'wrapper.vvp')],cwd=run,capture_output=True,text=True,timeout=30)
        elapsed=time.monotonic()-t;(run/'wrapper-simulation.log').write_text(s.stdout+s.stderr)
        if s.returncode:raise RuntimeError('actual production wrapper failed; retain '+str(run))
        rows=[json.loads(l[len('OWNED_RETRANS_WRAPPER_RTL '):])for l in s.stdout.splitlines()if l.startswith('OWNED_RETRANS_WRAPPER_RTL ')]
        assert len(rows)==1 and rows[0]['pass_test'] and not rows[0]['test_pool_mux']
        result['simulations'].append(dict(case='production_wrapper',seconds=elapsed,summary=rows[0]))
        print(json.dumps(result['simulations'][-1]),flush=True)
        assert before=={n:digest(ROOT/n)for n in before}
        result.update(pass_test=True,terminal_exit_status=0,simulation_seconds=sum(q['seconds']for q in result['simulations']))
    except Exception as e:result.update(terminal_exit_status=1,error_type=type(e).__name__,error=str(e));raise
    finally:
        result['artifact_sha256']={str(q.relative_to(ROOT)):digest(q)for q in run.iterdir()if q.is_file()}
        with a.report.open('x')as out:out.write(json.dumps(result,indent=2)+'\n')

if __name__=='__main__':main()
