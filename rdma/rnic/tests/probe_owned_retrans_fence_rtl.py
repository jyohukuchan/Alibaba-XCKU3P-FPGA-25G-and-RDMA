#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Short FOUR-STATE actual process/tables/pool/output boundary-fence tests.

Actual process emits both pool producer markers; production wrapper alone
generates receipts from actual normal-output / final-response handshakes.
Upstream input producers are bench models. NOT full shared-core/native/CQ.
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
BENCH=Path(__file__).resolve().with_name('owned_retrans_fence_tb.v')
BASE_BENCH=BENCH.with_name('owned_retrans_tb.v')
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def legacy_bench(text):
    assert text.count('as02_owned_retrans_top dut(')==1
    text=text.replace('as02_owned_retrans_top dut(','as02_owned_retrans_fence_top dut(')
    text=text.replace(' .fault(fault),.phase(phase),',r'''
 .s_pool_fence_TDATA(224'd0),.s_pool_fence_TVALID(1'b0),.s_pool_fence_TREADY(),
 .s_event_accept_TDATA(192'd0),.s_event_accept_TVALID(1'b0),.s_event_accept_TREADY(),
 .s_rdinit_accept_TDATA(192'd0),.s_rdinit_accept_TVALID(1'b0),.s_rdinit_accept_TREADY(),
 .s_fence_accept_TDATA(192'd0),.s_fence_accept_TVALID(1'b0),.s_fence_accept_TREADY(),
 .m_fence_TDATA(),.m_fence_TVALID(),.m_fence_TREADY(1'b0),
 .fault(fault),.phase(phase),''')
    assert '.s_pool_fence_TDATA'in text
    return text

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source-record',type=Path,required=True)
    p.add_argument('--verilator',type=Path,required=True)
    p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve earlier evidence')
    r=json.loads(a.source_record.read_text());assert r['pass_test']and r['HLS_constructed']
    rtl=ROOT/r['retained_directory']/'project/solution1/syn/verilog'
    pool=ROOT/'rdma/rnic/rtl/rocev2_retrans_pool.v';wrapper=ROOT/'rdma/rnic/rtl/rocev2_owned_retrans_fenced.v'
    own=[Path(__file__).resolve(),BENCH,BASE_BENCH,a.source_record.resolve(),pool,wrapper]
    before={**r['generated_sha256'],**{str(q.relative_to(ROOT)):digest(q)for q in own}}
    assert before=={n:digest(ROOT/n)for n in before}
    assert digest(pool)==r['source_sha256'][str(pool.relative_to(ROOT))]
    run=Path(tempfile.mkdtemp(prefix='owned-retrans-fence-RTL-',dir=ROOT/'rdma/rnic/build'))
    for q in own:shutil.copy2(q,run/q.name)
    for q in rtl.glob('*.dat'):shutil.copy2(q,run/q.name)
    adapted=legacy_bench(BASE_BENCH.read_text());(run/'normal-regression-tb.v').write_text(adapted)
    result=dict(scope=__doc__,pass_test=False,terminal_exit_status=None,retained_directory=str(run.relative_to(ROOT)),
        source_record=str(a.source_record),source_sha256=before,actual_generated_HLS=True,actual_production_pool=True,
        four_state_fence_tests=True,normal_regression_compiled_two_state_only=True,
        whole_core_drain=False,hardware_verified=False,physical_signoff=False,
        native_CQ_or_standard_verbs=False,simulations=[],normal_bench_derivation_sha256=hashlib.sha256(adapted.encode()).hexdigest())
    try:
        for name,top,bench,prefix,cases in [
            ('fence','fence_tb',run/BENCH.name,'OWNED_RETRANS_FENCE_RTL ',range(1,6)),
            ('normal','tb',run/'normal-regression-tb.v','OWNED_RETRANS_RTL ',range(1,7))]:
            binary=run/(name+'.vvp')
            sources=[str(bench),str(run/pool.name),str(run/wrapper.name),*map(str,sorted(rtl.glob('*.v')))]
            cmd=['iverilog','-g2012','-s',top,'-o',str(binary),*sources]
            if name=='normal':
                binary=run/'obj/test'
                cmd=[str(a.verilator.resolve()),'--binary','--timing','--top-module',top,'-Wno-fatal',
                    '--Mdir',str(run/'obj'),'-o','test','-j','8','--output-split','20000',
                    '--output-split-cfuncs','0','--output-groups','0','-CFLAGS','-O0',*sources]
            (run/(name+'-compile-command.json')).write_text(json.dumps(cmd,indent=2)+'\n')
            print(json.dumps(dict(directory=str(run),phase='compile_actual_'+name+'_RTL')),flush=True)
            t=time.monotonic();c=subprocess.run(cmd,cwd=run,capture_output=True,text=True,timeout=600 if name=='normal'else 60)
            result[name+'_compile_seconds']=time.monotonic()-t;(run/(name+'-compile.log')).write_text(c.stdout+c.stderr)
            if c.returncode:raise RuntimeError(name+' RTL compile failed; retain '+str(run))
            for case in cases:
                command=([str(binary)]if name=='normal'else['vvp',str(binary)])+['+CASE='+str(case)]
                t=time.monotonic()
                try:s=subprocess.run(command,cwd=run,capture_output=True,text=True,timeout=30)
                except subprocess.TimeoutExpired as exc:
                    (run/('%s-case-%d-TIMEOUT.log'%(name,case))).write_text(str(exc.stdout or '')+str(exc.stderr or ''))
                    raise
                elapsed=time.monotonic()-t;(run/('%s-case-%d.log'%(name,case))).write_text(s.stdout+s.stderr)
                if s.returncode:raise RuntimeError('%s actual RTL case%d failed; retain %s'%(name,case,run))
                rows=[json.loads(l[len(prefix):])for l in s.stdout.splitlines()if l.startswith(prefix)]
                assert len(rows)==1 and rows[0]['pass_test']and rows[0]['case']==case
                result['simulations'].append(dict(group=name,case=case,seconds=elapsed,summary=rows[0],four_state=name=='fence'))
                print(json.dumps(result['simulations'][-1]),flush=True)
        assert before=={n:digest(ROOT/n)for n in before}
        assert (run/'normal-regression-tb.v').read_text()==legacy_bench(BASE_BENCH.read_text())
        result.update(pass_test=True,terminal_exit_status=0,simulation_seconds=sum(v['seconds']for v in result['simulations']))
    except Exception as e:result.update(terminal_exit_status=1,error_type=type(e).__name__,error=str(e));raise
    finally:
        result['artifact_sha256']={str(q.relative_to(ROOT)):digest(q)for q in run.iterdir()if q.is_file()}
        with a.report.open('x')as out:out.write(json.dumps(result,indent=2)+'\n')

if __name__=='__main__':main()
