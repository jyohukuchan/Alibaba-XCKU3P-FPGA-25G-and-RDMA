#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Freeze and test actual ordered timer-state consumer; NOT whole-core drain.

Optional isolated HLS construction preserves eight slots, 4ns and real1ms.
Neither C simulation nor HLS construction is generated-RTL/physical signoff.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET

import fast_transport_sim as fast
ROOT=Path(__file__).resolve().parents[3]
spec=importlib.util.spec_from_file_location('timer_profile',ROOT/'rdma/rnic/hls/timer_state_fence_profile.py')
profile=importlib.util.module_from_spec(spec);spec.loader.exec_module(profile)


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--vitis-include',type=Path,required=True);p.add_argument('--report',type=Path,required=True)
    p.add_argument('--synthesize',action='store_true');p.add_argument('--tool',type=Path)
    a=p.parse_args()
    if a.report.exists():p.error('preserve earlier evidence')
    if a.synthesize and not a.tool:p.error('--tool required for synthesis')
    run=Path(tempfile.mkdtemp(prefix='timer-state-fence-',dir=ROOT/'rdma/rnic/build'))
    inp=run/'inputs';inp.mkdir()
    original={str(q.relative_to(profile.BASE)):digest(q)for q in profile.BASE.rglob('*')if q.is_file()}
    shutil.copytree(profile.BASE/'fns',inp/'fns');shutil.copytree(profile.BASE/'adapter',inp/'adapter')
    derived=inp/'fns/hls/ib_transport_protocol/transport_timer_fence.hpp'
    derived.write_text(profile.derive(profile.TIMER.read_text()))
    files=[ROOT/'rdma/rnic/hls'/n for n in ['timer_state_fence_top.cpp','test_timer_state_fence.cpp','timer_state_fence_synth.tcl']]
    for f in files:shutil.copy2(f,inp/f.name)
    own=[Path(__file__).resolve(),Path(profile.__file__).resolve(),Path(fast.__file__).resolve(),*files,profile.TIMER]
    # Retain the generator/driver themselves, not only the emitted C++/RTL.
    # Later source changes must not erase exact historical provenance.
    (inp/'profile').mkdir()
    for f in own:
        if f.suffix=='.py':shutil.copy2(f,inp/'profile'/f.name)
    before={str(f.relative_to(ROOT)):digest(f)for f in own}
    frozen={str(f.relative_to(inp)):digest(f)for f in inp.rglob('*')if f.is_file()}
    (inp/'inputs.sha256').write_text(''.join(h+'  '+n+'\n'for n,h in sorted(frozen.items())))
    def current():
        assert original=={str(q.relative_to(profile.BASE)):digest(q)for q in profile.BASE.rglob('*')if q.is_file()}
        assert before=={n:digest(ROOT/n)for n in before}
        assert frozen=={n:digest(inp/n)for n in frozen}
        assert derived.read_text()==profile.derive(profile.TIMER.read_text())
    current()
    result=dict(scope=__doc__,pass_test=False,terminal_exit_status=None,retained_directory=str(run.relative_to(ROOT)),
        source_sha256=before,frozen_source_sha256=frozen,source_and_frozen_inputs_unchanged=False,
        timer_entries=8,clock_period_ns=4.0,actual_timer_state_consumer=True,whole_core_drain=False,
        hardware_verified=False,board_integrated=False,native_CQ_or_standard_verbs=False,
        actual_RTL_function_tested=False,HLS_synthesis_requested=a.synthesize)
    compiler=shutil.which('g++-13')or shutil.which('g++')
    flags=['-std=c++17','-O2','-pthread','-Wno-unknown-pragmas','-ffunction-sections','-fdata-sections','-Wl,--gc-sections',
        '-DFNS_DATA_WIDTH=64','-DFNS_ROCE_STACK_MAX_QPS=8','-D__VITIS_HLS__','-I'+str(inp/'adapter'),'-I'+str(inp/'fns/hls'),'-I'+str(a.vitis_include.resolve())]
    command=[compiler,*flags,str(inp/'timer_state_fence_top.cpp'),str(inp/'test_timer_state_fence.cpp'),'-o',str(run/'test')]
    (run/'compile-command.json').write_text(json.dumps(command,indent=2)+'\n')
    print(json.dumps(dict(directory=str(run),phase='actual_C_function_test',simulation_limit_seconds=15)),flush=True)
    try:
        started=time.monotonic()
        with(run/'compile.log').open('x')as out:c=fast.bounded(command,run,120,out)
        result['compile_seconds']=time.monotonic()-started
        if c.returncode:raise RuntimeError('actual timer C++ compile failed; retain '+str(run))
        started=time.monotonic()
        with(run/'csim.log').open('x')as out:c=fast.bounded([str(run/'test')],run,15,out)
        result['C_simulation_seconds']=time.monotonic()-started
        if c.returncode:raise RuntimeError('actual timer C++ assertions failed; retain '+str(run))
        rows=[json.loads(s)for s in (run/'csim.log').read_text().splitlines()if s.startswith('{')]
        if len(rows)!=1 or not rows[0]['pass_test']:raise ValueError('missing actual C summary')
        result['C_summary']=rows[0]
        assert rows[0]['timer_entries']==8 and rows[0]['clock_ps']==4000 and rows[0]['time_1ms_visits']==31250
        current()
        print(json.dumps(dict(phase='actual_C_pass',summary=rows[0],simulation_seconds=result['C_simulation_seconds'])),flush=True)
        if a.synthesize:
            project=run/'project';hls=[str(a.tool.resolve()),'--mode','hls','--tcl',str(inp/'timer_state_fence_synth.tcl')]
            (run/'hls-command.json').write_text(json.dumps(hls,indent=2)+'\n')
            print(json.dumps(dict(phase='isolated_HLS_construction',project=str(project))),flush=True)
            started=time.monotonic()
            with(run/'synthesis.log').open('x')as out:
                c=subprocess.run(hls,cwd=run,env=dict(os.environ,AS02_TIMER_FENCE_INPUT=str(inp),AS02_TIMER_FENCE_BUILD=str(project)),stdout=out,stderr=subprocess.STDOUT)
            result['HLS_construction_seconds']=time.monotonic()-started
            if c.returncode:raise RuntimeError('isolated HLS failed; retain '+str(run))
            xml=project/'solution1/syn/report/as02_timer_fence_top_csynth.xml'
            x=ET.parse(xml).getroot()
            assert x.findtext('UserAssignments/Part')=='xcku3p-ffvb676-1-e'
            assert float(x.findtext('UserAssignments/TargetClockPeriod'))==4.0
            top=project/'solution1/syn/verilog/as02_timer_fence_top.v'
            text=top.read_text()
            for port,width in [('s_rx',176),('s_tx',24),('m_timeout',40),('m_fence',240)]:
                assert re.search(r'\[\s*'+str(width-1)+r'\s*:\s*0\s*\]\s+'+port+r'_TDATA',text),port
            result.update(HLS_constructed=True,estimated_period_ns=float(x.findtext('PerformanceEstimates/SummaryOfTimingAnalysis/EstimatedClockPeriod')),
                HLS_resources={q.tag:int(q.text)for q in x.find('AreaEstimates/Resources')},
                generated_sha256={str(q.relative_to(ROOT)):digest(q)for q in (top.parent).iterdir()if q.suffix in ['.v','.dat']})
        current();result.update(pass_test=True,terminal_exit_status=0,source_and_frozen_inputs_unchanged=True)
    except Exception as e:
        result.update(terminal_exit_status=1,error_type=type(e).__name__,error=str(e));raise
    finally:
        result['artifact_sha256']={str(q.relative_to(ROOT)):digest(q)for q in run.iterdir()if q.is_file()}
        with a.report.open('x')as out:out.write(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':main()
