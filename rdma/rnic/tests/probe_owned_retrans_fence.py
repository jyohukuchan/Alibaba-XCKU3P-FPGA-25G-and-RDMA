#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Construct actual process/pointer/metadata/pool/output barrier join.

No full shared-core/native/CQ or physical signoff. Actual RTL test is separate.
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
import tempfile
import time
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[3]
spec=importlib.util.spec_from_file_location('owned_fence_profile',ROOT/'rdma/rnic/hls/owned_retrans_fence_profile.py')
profile=importlib.util.module_from_spec(spec);spec.loader.exec_module(profile)
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--vitis-include',type=Path,required=True)
    p.add_argument('--tool',type=Path,required=True);p.add_argument('--report',type=Path,required=True)
    a=p.parse_args()
    if a.report.exists():p.error('preserve earlier evidence')
    run=Path(tempfile.mkdtemp(prefix='owned-retrans-fence-',dir=ROOT/'rdma/rnic/build'))
    inp=run/'inputs';inp.mkdir()
    original={str(q.relative_to(profile.BASE)):digest(q)for q in profile.BASE.rglob('*')if q.is_file()}
    shutil.copytree(profile.BASE/'fns',inp/'fns');shutil.copytree(profile.BASE/'adapter',inp/'adapter')
    derived=inp/'fns/hls/ib_transport_protocol/retransmitter/owned_retrans_fence.hpp'
    derived.write_text(profile.derive(profile.META.read_text()))
    names=['owned_retrans_top.cpp','owned_retrans_synth.tcl']
    own=[Path(__file__).resolve(),Path(profile.__file__).resolve(),Path(profile.base.__file__).resolve(),profile.META,
        ROOT/'rdma/rnic/rtl/rocev2_retrans_pool.v',*[ROOT/'rdma/rnic/hls'/n for n in names]]
    for n in names:shutil.copy2(ROOT/'rdma/rnic/hls'/n,inp/n)
    (inp/'owned_retrans_fence_top.cpp').write_text(profile.derive_top(profile.TOP.read_text()))
    (inp/'owned_retrans_fence_synth.tcl').write_text((inp/'owned_retrans_synth.tcl').read_text().replace('as02_owned_retrans_top','as02_owned_retrans_fence_top').replace('owned_retrans_top.cpp','owned_retrans_fence_top.cpp'))
    (inp/'profile').mkdir()
    for q in own:
        if q.suffix=='.py':shutil.copy2(q,inp/'profile'/q.name)
    shutil.copy2(ROOT/'rdma/rnic/rtl/rocev2_retrans_pool.v',inp/'rocev2_retrans_pool.v')
    before={str(q.relative_to(ROOT)):digest(q)for q in own}
    frozen={str(q.relative_to(inp)):digest(q)for q in inp.rglob('*')if q.is_file()}
    (inp/'inputs.sha256').write_text(''.join(h+'  '+n+'\n'for n,h in sorted(frozen.items())))
    def current():
        assert original=={str(q.relative_to(profile.BASE)):digest(q)for q in profile.BASE.rglob('*')if q.is_file()}
        assert before=={n:digest(ROOT/n)for n in before}
        assert frozen=={n:digest(inp/n)for n in frozen}
        assert derived.read_text()==profile.derive(profile.META.read_text())
        assert (inp/'owned_retrans_fence_top.cpp').read_text()==profile.derive_top(profile.TOP.read_text())
    result=dict(scope=__doc__,pass_test=False,terminal_exit_status=None,retained_directory=str(run.relative_to(ROOT)),
        source_sha256=before,frozen_source_sha256=frozen,source_and_frozen_inputs_unchanged=False,
        metadata_entries=2000,pointer_entries=8,clock_period_ns=4.0,
        actual_FNS_process_derivative=True,actual_process_barrier_join=True,actual_RTL_function_tested=False,
        upstream_FNS_producer_closure=False,
        HLS_constructed=False,whole_core_drain=False,native_CQ_or_standard_verbs=False,
        hardware_verified=False,board_integrated=False,physical_signoff=False)
    try:
        current()
        compiler=shutil.which('g++-13')or shutil.which('g++')
        cmd=[compiler,'-std=c++17','-O2','-pthread','-Wno-unknown-pragmas','-DFNS_DATA_WIDTH=64',
            '-DFNS_ROCE_STACK_MAX_QPS=8','-D__VITIS_HLS__','-I'+str(inp/'adapter'),'-I'+str(inp/'fns/hls'),
            '-I'+str(a.vitis_include.resolve()),'-c',str(inp/'owned_retrans_fence_top.cpp'),'-o',str(run/'top.o')]
        (run/'compile-command.json').write_text(json.dumps(cmd,indent=2)+'\n')
        print(json.dumps(dict(directory=str(run),phase='C++_compile_NOT_function_test')),flush=True)
        t=time.monotonic()
        with(run/'compile.log').open('x')as out:c=subprocess.run(cmd,cwd=run,stdout=out,stderr=subprocess.STDOUT,timeout=120)
        result['compile_seconds']=time.monotonic()-t
        if c.returncode:raise RuntimeError('C++ compile failed; retain '+str(run))
        current();project=run/'project'
        hls=[str(a.tool.resolve()),'--mode','hls','--tcl',str(inp/'owned_retrans_fence_synth.tcl')]
        (run/'hls-command.json').write_text(json.dumps(hls,indent=2)+'\n')
        print(json.dumps(dict(phase='isolated_HLS_construction',project=str(project))),flush=True)
        t=time.monotonic()
        with(run/'synthesis.log').open('x')as out:
            c=subprocess.run(hls,cwd=run,env=dict(os.environ,AS02_OWNED_RETRANS_INPUT=str(inp),AS02_OWNED_RETRANS_BUILD=str(project)),stdout=out,stderr=subprocess.STDOUT)
        result['HLS_construction_seconds']=time.monotonic()-t
        if c.returncode:raise RuntimeError('HLS construction failed; retain '+str(run))
        x=ET.parse(project/'solution1/syn/report/as02_owned_retrans_fence_top_csynth.xml').getroot()
        assert x.findtext('UserAssignments/Part')=='xcku3p-ffvb676-1-e'
        assert float(x.findtext('UserAssignments/TargetClockPeriod'))==4.0
        top=project/'solution1/syn/verilog/as02_owned_retrans_fence_top.v';text=top.read_text()
        for port,width in [('s_insert',416),('s_update',224),('s_retry',192),('s_timer',192),
            ('m_pool_alloc',192),('s_pool_alloc',256),('m_pool_release',256),('s_pool_release',256),('m_event',576),('m_rdinit',320),('s_pool_fence',224),('s_event_accept',192),('s_rdinit_accept',192),('s_fence_accept',192),('m_fence',320)]:
            assert re.search(r'\[\s*'+str(width-1)+r'\s*:\s*0\s*\]\s+'+port+r'_TDATA',text),port
        modules=[q.stem for q in top.parent.glob('*.v')]
        for prefix in ['as02_process_owned_retransmissions','as02_owned_pointer_table','as02_owned_meta_table']:
            # RAM child modules share the function prefix; count the actual
            # selected function module, not its real storage primitives.
            assert modules.count('as02_owned_retrans_fence_top_'+prefix+'_46_s')==1,(prefix,modules)
        assert not any('freelist_handler' in n or 'freeListFifo' in n for n in modules)
        current();result.update(pass_test=True,terminal_exit_status=0,source_and_frozen_inputs_unchanged=True,
            HLS_constructed=True,generated_modules=modules,
            estimated_period_ns=float(x.findtext('PerformanceEstimates/SummaryOfTimingAnalysis/EstimatedClockPeriod')),
            HLS_resources={q.tag:int(q.text)for q in x.find('AreaEstimates/Resources')},
            generated_sha256={str(q.relative_to(ROOT)):digest(q)for q in top.parent.iterdir()if q.suffix in ['.v','.dat']})
        print(json.dumps(dict(phase='HLS_constructed_NOT_physical',estimated_period_ns=result['estimated_period_ns'],resources=result['HLS_resources'])),flush=True)
    except Exception as e:result.update(terminal_exit_status=1,error_type=type(e).__name__,error=str(e));raise
    finally:
        result['artifact_sha256']={str(q.relative_to(ROOT)):digest(q)for q in run.iterdir()if q.is_file()}
        with a.report.open('x')as out:out.write(json.dumps(result,indent=2)+'\n')

if __name__=='__main__':main()
