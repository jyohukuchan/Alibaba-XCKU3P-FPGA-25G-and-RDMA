#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Short XSIM FOUR-STATE replay of the exact coupled owned timer candidate.

All six unchanged coupled benches, including actual1ms/two-WR retry, with
explicit test-only X/Z calibration. NOT whole FNS/native/MAC/DMA/CQ proof,
placed/routed timing or exhaustive reset/CDC qualification. No hardware.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import fast_transport_sim as fast
ROOT=Path(__file__).resolve().parents[3]
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ['source-record','comparison-record','tool-dir','report']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args()
    if a.report.exists():p.error('preserve earlier evidence')
    parent=json.loads(a.source_record.read_text());comparison=json.loads(a.comparison_record.read_text())
    assert parent['pass_test']and parent['HLS_constructed']and comparison['pass_test']
    assert comparison['parent_record']==str(a.source_record)
    expected={v['case']:v['summary']for v in comparison['simulations']if v['group']=='coupled'}
    assert set(expected)==set(range(1,7))
    core=ROOT/parent['retained_directory'];rtl=core/'project/solution1/syn/verilog'
    own=[Path(__file__).resolve(),Path(fast.__file__).resolve(),Path(fast.rw_sim.__file__).resolve(),
        a.source_record.resolve(),a.comparison_record.resolve(),ROOT/'rdma/rnic/rtl/rocev2_retrans_pool.v',
        ROOT/'rdma/rnic/rtl/rocev2_owned_timer_retrans.v',ROOT/'rdma/rnic/tests/owned_timer_coupled_tb.v',
        ROOT/'rdma/rnic/tests/xsim_four_state_calibration.v']
    before={**parent['generated_sha256'],**{str(q.relative_to(ROOT)):digest(q)for q in own}}
    assert before=={n:digest(ROOT/n)for n in before}
    for n in ['rdma/rnic/rtl/rocev2_retrans_pool.v','rdma/rnic/rtl/rocev2_owned_timer_retrans.v','rdma/rnic/tests/owned_timer_coupled_tb.v']:
        assert before[n]==comparison['source_sha256'][n]
    run=Path(tempfile.mkdtemp(prefix='owned-timer-XSIM-',dir=ROOT/'rdma/rnic/build'));inp=run/'inputs';inp.mkdir()
    for q in own:shutil.copy2(q,inp/q.name)
    for q in rtl.glob('*.dat'):shutil.copy2(q,run/q.name)
    result=dict(scope=__doc__,pass_test=False,terminal_exit_status=None,retained_directory=str(run.relative_to(ROOT)),
        source_sha256=before,parent_record=str(a.source_record),comparison_record=str(a.comparison_record),
        actual_generated_RTL=True,coupled_subsystem_four_state=True,whole_core_drain=False,
        hardware_verified=False,physical_signoff=False,native_CQ_or_standard_verbs=False,simulations=[])
    snapshot={}
    def current():assert before=={n:digest(ROOT/n)for n in before}
    def invoke(cmd,log,limit):
        (run/(log+'.command.json')).write_text(json.dumps(cmd,indent=2)+'\n')
        t=time.monotonic()
        with(run/log).open('x')as out:c=fast.bounded(cmd,run,limit,out)
        if c.returncode:raise RuntimeError(log+' failed; retain '+str(run))
        return time.monotonic()-t
    try:
        result['simulator_version']=subprocess.check_output([str(a.tool_dir/'xsim'),'--version'],cwd=run,text=True).strip()
        print(json.dumps(dict(directory=str(run),phase='strict_four_state_compile',simulation_limit_seconds=30)),flush=True)
        assert shutil.disk_usage(ROOT).free>1500*1024*1024,'insufficient build headroom; no deletion'
        src=[str(inp/'owned_timer_coupled_tb.v'),str(inp/'xsim_four_state_calibration.v'),
            str(inp/'rocev2_retrans_pool.v'),str(inp/'rocev2_owned_timer_retrans.v'),*map(str,sorted(rtl.glob('*.v')))]
        result['xvlog_seconds']=invoke([str(a.tool_dir/'xvlog'),'--work','work','--sv',*src],'xvlog.stdout.log',180)
        result['xelab_seconds']=invoke([str(a.tool_dir/'xelab'),'work.coupled_tb','work.as02_four_state_calibration',
            '--snapshot','owned_timer_cases','--mt','8','--debug','off'],'xelab.stdout.log',600)
        directory=run/'xsim.dir/owned_timer_cases'
        snapshot={str(q.relative_to(ROOT)):digest(q)for q in directory.rglob('*')if q.is_file()}
        assert snapshot,'actual compiled snapshot missing'
        result['compiled_snapshot_sha256']=snapshot
        for case in range(1,7):
            current();assert snapshot=={n:digest(ROOT/n)for n in snapshot}
            print(json.dumps(dict(phase='four_state_simulation',case=case)),flush=True)
            seconds=invoke([str(a.tool_dir/'xsim'),'owned_timer_cases','--runall','--testplusarg','CASE='+str(case),
                '--onerror','quit','--onfinish','quit','--log','case-%d.xsim.log'%case],
                'case-%d.stdout.log'%case,30)
            log=(run/('case-%d.stdout.log'%case)).read_text();prefix='OWNED_TIMER_COUPLED_RTL '
            assert log.count('XSIM_FOUR_STATE_CALIBRATED')==1,'missing actual X/Z calibration'
            rows=[json.loads(l[len(prefix):])for l in log.splitlines()if l.startswith(prefix)]
            assert len(rows)==1 and rows[0]['pass_test']and rows[0]['case']==case
            # Event-queue ordering of the bench's diagnostic blocking cycle
            # counter can differ by one; ALL semantic counters/fields match.
            semantic=lambda d:{k:v for k,v in d.items()if k!='cycles'}
            assert semantic(rows[0])==semantic(expected[case]),(case,rows[0],expected[case])
            assert snapshot=={n:digest(ROOT/n)for n in snapshot}
            result['simulations'].append(dict(case=case,seconds=seconds,summary=rows[0],four_state=True,
                X_Z_calibration=True,all_semantic_fields_match_compiled_two_state=True))
            print(json.dumps(result['simulations'][-1]),flush=True)
        current();result.update(pass_test=True,terminal_exit_status=0,simulation_seconds=sum(v['seconds']for v in result['simulations']))
    except Exception as e:result.update(terminal_exit_status=1,error_type=type(e).__name__,error=str(e));raise
    finally:
        result['artifact_sha256']={str(q.relative_to(ROOT)):digest(q)for q in [*run.iterdir(),*inp.iterdir()]if q.is_file()}
        result['artifact_sha256'].update({n:digest(ROOT/n)for n in snapshot})
        with a.report.open('x')as out:out.write(json.dumps(result,indent=2)+'\n')

if __name__=='__main__':main()
