#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual timer C++, standalone FOUR-STATE and coupled TWO-STATE tests.

Timer starts/head advances/replay rearms are ACTUAL process outputs in the
coupled graph, not injected timer requests. Wire producers/native/CQ remain
models/unimplemented; these complementary scopes are NOT full-core proof.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[3]
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['source-record','report','vitis-include','tool','verilator']:p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--reuse-probe-record',type=Path)
    a=p.parse_args()
    if a.report.exists():p.error('preserve earlier evidence')
    r=json.loads(a.source_record.read_text());assert r['pass_test']and r['HLS_constructed']and r['actual_owned_timer_coupled']
    core=ROOT/r['retained_directory'];frozen=core/'inputs';rtl=core/'project/solution1/syn/verilog'
    hls_names=['test_owned_timer.cpp','owned_timer_probe_top.cpp','owned_timer_probe_synth.tcl']
    own=[Path(__file__).resolve(),a.source_record.resolve(),ROOT/'rdma/rnic/rtl/rocev2_retrans_pool.v',
        ROOT/'rdma/rnic/rtl/rocev2_owned_timer_retrans.v',*[ROOT/'rdma/rnic/hls'/n for n in hls_names],
        ROOT/'rdma/rnic/tests/owned_timer_tb.v',ROOT/'rdma/rnic/tests/owned_timer_coupled_tb.v']
    if a.reuse_probe_record:own.append(a.reuse_probe_record.resolve())
    before={**r['generated_sha256'],**{str((frozen/n).relative_to(ROOT)):h for n,h in r['frozen_source_sha256'].items()},
        **{str(q.relative_to(ROOT)):digest(q)for q in own}}
    assert before=={n:digest(ROOT/n)for n in before}
    run=Path(tempfile.mkdtemp(prefix='owned-timer-RTL-',dir=ROOT/'rdma/rnic/build'));inp=run/'inputs';inp.mkdir()
    for q in own:shutil.copy2(q,inp/q.name)
    for q in rtl.glob('*.dat'):shutil.copy2(q,run/q.name)
    result=dict(scope=__doc__,pass_test=False,terminal_exit_status=None,retained_directory=str(run.relative_to(ROOT)),
        source_sha256=before,parent_record=str(a.source_record),whole_core_drain=False,hardware_verified=False,
        physical_signoff=False,native_CQ_or_standard_verbs=False,standalone_four_state_only=True,
        actual_coupled_graph_two_state_only=True,simulations=[])
    def current():assert before=={n:digest(ROOT/n)for n in before}
    def command(cmd,log,limit):
        t=time.monotonic()
        with(run/log).open('x')as out:c=subprocess.run(cmd,cwd=run,stdout=out,stderr=subprocess.STDOUT,timeout=limit)
        if c.returncode:raise RuntimeError(log+' failed; retain '+str(run))
        return time.monotonic()-t
    try:
        print(json.dumps(dict(directory=str(run),phase='actual_C_timer_test')),flush=True)
        flags=['-std=c++17','-O2','-pthread','-Wno-unknown-pragmas','-DFNS_DATA_WIDTH=64','-DFNS_ROCE_STACK_MAX_QPS=8','-D__VITIS_HLS__',
            '-I'+str(frozen/'adapter'),'-I'+str(frozen/'fns/hls'),'-I'+str(a.vitis_include.resolve())]
        cmd=[shutil.which('g++-13')or shutil.which('g++'),*flags,str(inp/'test_owned_timer.cpp'),'-o',str(run/'csim')]
        (run/'csim-command.json').write_text(json.dumps(cmd,indent=2)+'\n')
        result['C_compile_seconds']=command(cmd,'csim-compile.log',120)
        result['C_simulation_seconds']=command([str(run/'csim')],'csim.log',15)
        rows=[json.loads(l)for l in(run/'csim.log').read_text().splitlines()if l.startswith('{')]
        assert len(rows)==1 and rows[0]['pass_test']and rows[0]['queries']==6 and rows[0]['TIME_1ms_visits']==31250
        result['C_summary']=rows[0];current()
        print(json.dumps(dict(phase='actual_C_pass',seconds=result['C_simulation_seconds'],summary=rows[0])),flush=True)
        if a.reuse_probe_record:
            old=json.loads(a.reuse_probe_record.read_text())
            assert old['probe_HLS_estimate_ns']and old['generated_sha256']
            for n,h in old['source_sha256'].items():
                if n!=str(Path(__file__).resolve().relative_to(ROOT)):assert digest(ROOT/n)==h,n
            assert old['generated_sha256']=={n:digest(ROOT/n)for n in old['generated_sha256']}
            probe=ROOT/old['retained_directory']/'probe_project/solution1/syn/verilog'
            result.update(probe_HLS_seconds=0.0,reused_immutable_probe_from_record=str(a.reuse_probe_record),
                probe_HLS_estimate_ns=old['probe_HLS_estimate_ns'],probe_HLS_resources=old['probe_HLS_resources'],generated_sha256=old['generated_sha256'])
            print(json.dumps(dict(phase='reuse_HASH_VERIFIED_actual_probe_RTL_NOT_promote_old_overall_failure')),flush=True)
        else:
            print(json.dumps(dict(phase='actual_timer_probe_HLS_construction')),flush=True)
            env=dict(os.environ,AS02_TIMER_CORE_INPUT=str(frozen),AS02_TIMER_PROBE_SOURCE=str(inp/'owned_timer_probe_top.cpp'),AS02_TIMER_PROBE_BUILD=str(run/'probe_project'))
            t=time.monotonic()
            with(run/'probe-hls.log').open('x')as out:
                c=subprocess.run([str(a.tool.resolve()),'--mode','hls','--tcl',str(inp/'owned_timer_probe_synth.tcl')],cwd=run,env=env,stdout=out,stderr=subprocess.STDOUT)
            result['probe_HLS_seconds']=time.monotonic()-t
            if c.returncode:raise RuntimeError('probe actual HLS failed')
            x=ET.parse(run/'probe_project/solution1/syn/report/as02_owned_timer_probe_top_csynth.xml').getroot()
            assert x.findtext('UserAssignments/Part')=='xcku3p-ffvb676-1-e'and float(x.findtext('UserAssignments/TargetClockPeriod'))==4.0
            probe=run/'probe_project/solution1/syn/verilog'
            result.update(probe_HLS_estimate_ns=float(x.findtext('PerformanceEstimates/SummaryOfTimingAnalysis/EstimatedClockPeriod')),
                probe_HLS_resources={q.tag:int(q.text)for q in x.find('AreaEstimates/Resources')},
                generated_sha256={str(q.relative_to(ROOT)):digest(q)for q in probe.iterdir()if q.suffix in ['.v','.dat']})
        for q in probe.glob('*.dat'):shutil.copy2(q,run/q.name)
        current()
        for group,top,bench,sources,cases,prefix in [
            ('producer','timer_tb','owned_timer_tb.v',sorted(probe.glob('*.v')),range(1,4),'OWNED_TIMER_PRODUCER_RTL '),
            ('coupled','coupled_tb','owned_timer_coupled_tb.v',sorted(rtl.glob('*.v')),range(1,7),'OWNED_TIMER_COUPLED_RTL ')]:
            binary=run/(group+'.vvp');src=[str(inp/bench),*map(str,sources)]
            cmd=['iverilog','-g2012','-s',top,'-o',str(binary),*src]
            if group=='coupled':
                src+=[str(inp/'rocev2_retrans_pool.v'),str(inp/'rocev2_owned_timer_retrans.v')];binary=run/'obj/test'
                result['compiled_simulator_version']=subprocess.check_output([str(a.verilator.resolve()),'--version'],text=True).strip()
                result['compiled_simulator_workaround']='-fno-dfg; compiler optimization only, exact generated RTL unchanged'
                cmd=[str(a.verilator.resolve()),'-fno-dfg','--binary','--timing','--top-module',top,'-Wno-fatal','--Mdir',str(run/'obj'),
                    '-o','test','-j','8','--output-split','20000','--output-split-cfuncs','0','--output-groups','0','-CFLAGS','-O2',*src]
            print(json.dumps(dict(phase='compile_'+group,simulation_limit_seconds=30)),flush=True)
            (run/(group+'-command.json')).write_text(json.dumps(cmd,indent=2)+'\n')
            result[group+'_compile_seconds']=command(cmd,group+'-compile.log',600 if group=='coupled'else 60)
            binary_sha=digest(binary)
            for case in cases:
                cmd=([str(binary)]if group=='coupled'else['vvp',str(binary)])+['+CASE='+str(case)]
                seconds=command(cmd,group+'-%d.log'%case,30)
                rows=[json.loads(l[len(prefix):])for l in(run/(group+'-%d.log'%case)).read_text().splitlines()if l.startswith(prefix)]
                assert len(rows)==1 and rows[0]['pass_test']and rows[0]['case']==case
                assert digest(binary)==binary_sha
                result['simulations'].append(dict(group=group,case=case,seconds=seconds,summary=rows[0],four_state=group=='producer',binary_sha256=binary_sha))
                print(json.dumps(result['simulations'][-1]),flush=True)
            result[group+'_binary']=str(binary.relative_to(ROOT));result[group+'_binary_sha256']=binary_sha
        current();assert result['generated_sha256']=={n:digest(ROOT/n)for n in result['generated_sha256']}
        result.update(pass_test=True,terminal_exit_status=0,simulation_seconds=sum(v['seconds']for v in result['simulations']))
    except Exception as e:result.update(terminal_exit_status=1,error_type=type(e).__name__,error=str(e));raise
    finally:
        arts=[q for q in run.iterdir()if q.is_file()]+[q for q in inp.iterdir()if q.is_file()]
        for n in ['producer_binary','coupled_binary']:
            if n in result:arts.append(ROOT/result[n])
        result['artifact_sha256']={str(q.relative_to(ROOT)):digest(q)for q in arts}
        with a.report.open('x')as out:out.write(json.dumps(result,indent=2)+'\n')

if __name__=='__main__':main()
