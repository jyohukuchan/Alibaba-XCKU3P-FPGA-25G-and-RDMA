#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual same-table lookup/real pool/timer, bounded XSIM FOUR-STATE.

Not genuine packet/connection admission, RX IBH/EXH execution, native CQ,
physical timing/CDC or safe reset/recovery. No hardware access.
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
    for n in ['source-record','tool-dir','report']:p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--cases',default='1,2,3,4,5,6,7,8')
    p.add_argument('--reuse-snapshot-record',type=Path)
    a=p.parse_args()
    if a.report.exists():p.error('preserve earlier evidence')
    cases=[int(v)for v in a.cases.split(',')]
    assert cases and len(set(cases))==len(cases) and set(cases)<=set(range(1,9))
    parent=json.loads(a.source_record.read_text());assert parent['pass_test']and parent['HLS_constructed']
    core=ROOT/parent['retained_directory'];rtl=core/'project/solution1/syn/verilog'
    own=[Path(__file__).resolve(),Path(fast.__file__).resolve(),Path(fast.rw_sim.__file__).resolve(),
        a.source_record.resolve(),ROOT/'rdma/rnic/rtl/rocev2_retrans_pool.v',
        ROOT/'rdma/rnic/rtl/rocev2_owned_rx_lookup.v',ROOT/'rdma/rnic/tests/owned_rx_lookup_tb.v',
        ROOT/'rdma/rnic/tests/xsim_four_state_calibration.v']
    before={**parent['source_sha256'],**parent['generated_sha256'],**{str(q.relative_to(ROOT)):digest(q)for q in own}}
    reused=None
    if a.reuse_snapshot_record:
        reused=json.loads(a.reuse_snapshot_record.read_text())
        assert reused['parent_record']==str(a.source_record)
        archived=ROOT/reused['retained_directory'];old_driver=archived/'inputs'/Path(__file__).name
        for n,h in reused['source_sha256'].items():
            f=old_driver if n==str(Path(__file__).resolve().relative_to(ROOT))else ROOT/n
            assert digest(f)==h,n
        for n,h in reused['compiled_snapshot_sha256'].items():assert digest(ROOT/n)==h,n
        own.append(a.reuse_snapshot_record.resolve())
        before[str(a.reuse_snapshot_record.resolve().relative_to(ROOT))]=digest(a.reuse_snapshot_record)
        before[str(old_driver.relative_to(ROOT))]=digest(old_driver)
    for n,h in before.items():assert digest(ROOT/n)==h,n
    for n,h in parent['frozen_source_sha256'].items():assert digest(core/'inputs'/n)==h,n
    run=Path(tempfile.mkdtemp(prefix='owned-rx-lookup-XSIM-',dir=ROOT/'rdma/rnic/build'));inp=run/'inputs';inp.mkdir()
    for q in own:shutil.copy2(q,inp/q.name)
    for q in rtl.glob('*.dat'):shutil.copy2(q,run/q.name)
    result=dict(scope=__doc__,pass_test=False,terminal_exit_status=None,retained_directory=str(run.relative_to(ROOT)),
        source_sha256=before,parent_record=str(a.source_record),
        actual_generated_RTL=True,coupled_subsystem_four_state=True,actual_pool_and_timer=True,
        metadata_entries=2000,pointer_entries=8,clock_period_ns=4.0,simulation_wall_bound_seconds=30,
        requested_cases=cases,omitted_cases=sorted(set(range(1,9))-set(cases)),
        full_eight_case_suite_pass=False,reused_compiled_snapshot_only=bool(reused),
        reused_snapshot_record=str(a.reuse_snapshot_record)if reused else None,
        actual_packet_QP_epoch_admission=False,full_RX_IBH_EXH_producer_binding=False,
        whole_core_drain=False,hardware_verified=False,physical_signoff=False,native_CQ_or_standard_verbs=False,simulations=[])
    snapshot={}
    def current():
        for n,h in before.items():assert digest(ROOT/n)==h,n
        for n,h in parent['frozen_source_sha256'].items():assert digest(core/'inputs'/n)==h,n
    def invoke(cmd,log,limit):
        (run/(log+'.command.json')).write_text(json.dumps(cmd,indent=2)+'\n')
        t=time.monotonic()
        with(run/log).open('x')as out:c=fast.bounded(cmd,run,limit,out)
        if c.returncode:raise RuntimeError(log+' failed; retain '+str(run))
        return time.monotonic()-t
    try:
        result['simulator_version']=subprocess.check_output([str(a.tool_dir/'xsim'),'--version'],cwd=run,text=True).strip()
        print(json.dumps(dict(directory=str(run),phase='strict_four_state_compile',simulation_limit_seconds=30)),flush=True)
        assert shutil.disk_usage(ROOT).free>1500*1024*1024,'insufficient headroom; no deletion'
        src=[str(inp/'owned_rx_lookup_tb.v'),str(inp/'xsim_four_state_calibration.v'),
            str(inp/'rocev2_retrans_pool.v'),str(inp/'rocev2_owned_rx_lookup.v'),*map(str,sorted(rtl.glob('*.v')))]
        directory=run/'xsim.dir/owned_rx_lookup_cases'
        if reused:
            source=ROOT/reused['retained_directory']/'xsim.dir/owned_rx_lookup_cases'
            shutil.copytree(source,directory)
            result['xvlog_seconds']=None;result['xelab_seconds']=None
            result['reused_snapshot_exact_file_sha256']={str(q.relative_to(directory)):digest(q)for q in directory.rglob('*')if q.is_file()}
            assert all(digest(directory/Path(n).name)==h for n,h in reused['compiled_snapshot_sha256'].items())
        else:
            result['xvlog_seconds']=invoke([str(a.tool_dir/'xvlog'),'--work','work','--sv',*src],'xvlog.stdout.log',180)
            result['xelab_seconds']=invoke([str(a.tool_dir/'xelab'),'work.rx_lookup_tb','work.as02_four_state_calibration',
                '--snapshot','owned_rx_lookup_cases','--mt','8','--debug','off'],'xelab.stdout.log',600)
        snapshot={str(q.relative_to(ROOT)):digest(q)for q in directory.rglob('*')if q.is_file()}
        assert snapshot;result['compiled_snapshot_sha256']=snapshot
        for case in cases:
            current();assert snapshot=={n:digest(ROOT/n)for n in snapshot}
            print(json.dumps(dict(phase='four_state_simulation',case=case)),flush=True)
            seconds=invoke([str(a.tool_dir/'xsim'),'owned_rx_lookup_cases','--runall','--testplusarg','CASE='+str(case),
                '--onerror','quit','--onfinish','quit','--log','case-%d.xsim.log'%case],
                'case-%d.stdout.log'%case,30)
            log=(run/('case-%d.stdout.log'%case)).read_text();prefix='OWNED_RX_LOOKUP_RTL '
            assert log.count('XSIM_FOUR_STATE_CALIBRATED')==1,'actual X/Z calibration missing'
            rows=[json.loads(line[len(prefix):])for line in log.splitlines()if line.startswith(prefix)]
            assert len(rows)==1 and rows[0]['pass_test']and rows[0]['case']==case
            assert snapshot=={n:digest(ROOT/n)for n in snapshot};current()
            result['simulations'].append(dict(case=case,seconds=seconds,summary=rows[0],four_state=True,X_Z_calibration=True))
            print(json.dumps(result['simulations'][-1]),flush=True)
        assert len(result['simulations'])==len(cases)
        current();result.update(pass_test=True,terminal_exit_status=0,full_eight_case_suite_pass=set(cases)==set(range(1,9)),simulation_seconds=sum(v['seconds']for v in result['simulations']))
    except Exception as error:result.update(terminal_exit_status=1,error_type=type(error).__name__,error=str(error));raise
    finally:
        result['artifact_sha256']={str(q.relative_to(ROOT)):digest(q)for q in [*run.iterdir(),*inp.iterdir()]if q.is_file()}
        result['artifact_sha256'].update({n:digest(ROOT/n)for n in snapshot})
        with a.report.open('x')as out:out.write(json.dumps(result,indent=2)+'\n')
if __name__=='__main__':main()
