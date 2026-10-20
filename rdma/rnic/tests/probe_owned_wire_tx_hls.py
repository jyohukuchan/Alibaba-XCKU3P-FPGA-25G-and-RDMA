#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Construct exact C-tested actual TX producer graph; not physical/RTL proof."""
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
from fast_transport_sim import bounded
ROOT=Path(__file__).resolve().parents[3]
def digest(f):return hashlib.sha256(Path(f).read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-report',type=Path,required=True)
    p.add_argument('--vitis-include',type=Path,required=True)
    p.add_argument('--tool',type=Path,required=True);p.add_argument('--report',type=Path,required=True)
    a=p.parse_args()
    if a.report.exists():p.error('preserve previous evidence')
    c=json.loads(a.source_report.read_text());assert c['pass_test'] and c['terminal_exit_status']==0
    assert len(c['simulations'])==16 and c['source_and_frozen_inputs_unchanged']
    before={**c['source_sha256'],str(a.source_report.relative_to(ROOT) if a.source_report.is_absolute() else a.source_report):digest(a.source_report)}
    extras=[Path(__file__).resolve(),ROOT/'rdma/rnic/hls/owned_wire_tx_top.cpp',ROOT/'rdma/rnic/hls/owned_wire_tx_synth.tcl']
    before.update({str(f.relative_to(ROOT)):digest(f)for f in extras})
    for n,h in before.items():assert digest(ROOT/n)==h,n
    source=ROOT/c['retained_directory']/'inputs'
    for n,h in c['frozen_source_sha256'].items():assert digest(source/n)==h,n
    run=Path(tempfile.mkdtemp(prefix='owned-wire-tx-hls-',dir=ROOT/'rdma/rnic/build'));inp=run/'inputs'
    shutil.copytree(source,inp)
    for f in extras:
        dest=inp/'profile'/f.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,dest)
    for n in ['owned_wire_tx_top.cpp','owned_wire_tx_synth.tcl']:shutil.copy2(ROOT/'rdma/rnic/hls'/n,inp/n)
    frozen={str(f.relative_to(inp)):digest(f)for f in inp.rglob('*')if f.is_file()}
    (inp/'inputs.sha256').write_text(''.join(h+'  '+n+'\n'for n,h in sorted(frozen.items())))
    def current():
        assert before=={n:digest(ROOT/n)for n in before}
        assert frozen=={n:digest(inp/n)for n in frozen}
        assert c['frozen_source_sha256']=={n:digest(source/n)for n in c['frozen_source_sha256']}
    result=dict(scope=__doc__,pass_test=False,terminal_exit_status=None,retained_directory=str(run.relative_to(ROOT)),
        source_report=str(a.source_report),source_sha256=before,frozen_source_sha256=frozen,
        source_and_frozen_inputs_unchanged=False,clock_period_ns=4.0,HLS_constructed=False,
        actual_FNS_selected_TX_functions=5,RTL_simulated=False,physical_signoff=False,
        native_admission_connected=False,RX_owner_lookup=False,MAC_SFD_verified=False,
        full_wire_producer_fence=False,shared_native_board_selected=False,whole_core_drain=False,native_CQ=False,hardware_verified=False)
    try:
        compiler=shutil.which('g++-13')or shutil.which('g++')
        cmd=[compiler,'-std=c++17','-O2','-pthread','-Wno-unknown-pragmas','-DFNS_DATA_WIDTH=64','-DFNS_ROCE_STACK_MAX_QPS=8','-D__VITIS_HLS__',
            '-I'+str(inp/'adapter'),'-I'+str(inp/'fns/hls'),'-I'+str(a.vitis_include.resolve()),'-c',str(inp/'owned_wire_tx_top.cpp'),'-o',str(run/'top.o')]
        (run/'compile-command.json').write_text(json.dumps(cmd,indent=2)+'\n')
        print(json.dumps(dict(phase='C++_compile_actual_TX_top',directory=str(run))),flush=True)
        t=time.monotonic()
        with(run/'compile.log').open('x')as log:compiled=bounded(cmd,run,120,log)
        result['compile_seconds']=time.monotonic()-t
        if compiled.returncode:raise RuntimeError('C++ top compile failed: '+str(run/'compile.log'))
        current();project=run/'project'
        command=[str(a.tool.resolve()),'--mode','hls','--tcl',str(inp/'owned_wire_tx_synth.tcl')]
        (run/'hls-command.json').write_text(json.dumps(command,indent=2)+'\n')
        print(json.dumps(dict(phase='HLS_construction_original4ns_NOT_physical',directory=str(run))),flush=True)
        t=time.monotonic()
        with(run/'synthesis.log').open('x')as log:
            hls=subprocess.run(command,cwd=run,env=dict(os.environ,AS02_OWNED_WIRE_INPUT=str(inp),AS02_OWNED_WIRE_BUILD=str(project)),stdout=log,stderr=subprocess.STDOUT)
        result['HLS_seconds']=time.monotonic()-t
        if hls.returncode:raise RuntimeError('HLS construction failed: '+str(run/'synthesis.log'))
        report=project/'solution1/syn/report/as02_owned_wire_tx_top_csynth.xml';x=ET.parse(report).getroot()
        assert x.findtext('UserAssignments/Part')=='xcku3p-ffvb676-1-e'
        assert float(x.findtext('UserAssignments/TargetClockPeriod'))==4.0
        rtl=project/'solution1/syn/verilog';modules=[f.stem for f in rtl.glob('*.v')]
        selected=['local_req_handler','meta_merger','generate_ibh','generate_exh','merge_retrans_request']
        functions={n:[m for m in modules if 'as02_owned_wire_'+n in m]for n in selected}
        assert all(functions.values()),functions
        current();result.update(pass_test=True,terminal_exit_status=0,HLS_constructed=True,
            source_and_frozen_inputs_unchanged=True,selected_function_modules=functions,
            estimated_period_ns=float(x.findtext('PerformanceEstimates/SummaryOfTimingAnalysis/EstimatedClockPeriod')),
            resources={v.tag:int(v.text)for v in x.find('AreaEstimates/Resources')},
            generated_sha256={str(f.relative_to(ROOT)):digest(f)for f in rtl.iterdir()if f.suffix in ['.v','.dat']},
            report_sha256={str(f.relative_to(ROOT)):digest(f)for f in report.parent.glob('*')if f.is_file()})
        print(json.dumps(dict(phase='HLS_constructed_NOT_signoff',estimate_ns=result['estimated_period_ns'],resources=result['resources'])),flush=True)
    except Exception as error:
        result.update(terminal_exit_status=1,error=str(error),error_type=type(error).__name__);raise
    finally:
        result['artifact_sha256']={str(f.relative_to(ROOT)):digest(f)for f in run.iterdir()if f.is_file()}
        with a.report.open('x')as out:out.write(json.dumps(result,indent=2)+'\n')
if __name__=='__main__':main()
