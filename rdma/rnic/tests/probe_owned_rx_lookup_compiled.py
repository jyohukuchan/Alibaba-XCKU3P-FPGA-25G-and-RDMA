#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Additional TWO-STATE diagnostics of exact lookup/pool/timer RTL.

Not replacement for FOUR-STATE/X/Z, native/physical or runtime recovery proof.
Same unchanged bench assertions/cycle and30second wall bounds.
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
    for n in ['source-record','verilator','report']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args()
    if a.report.exists():p.error('preserve earlier evidence')
    parent=json.loads(a.source_record.read_text());assert parent['pass_test']and parent['HLS_constructed']
    core=ROOT/parent['retained_directory'];rtl=core/'project/solution1/syn/verilog'
    own=[Path(__file__).resolve(),Path(fast.__file__).resolve(),Path(fast.rw_sim.__file__).resolve(),a.source_record.resolve(),
        ROOT/'rdma/rnic/rtl/rocev2_retrans_pool.v',ROOT/'rdma/rnic/rtl/rocev2_owned_rx_lookup.v',ROOT/'rdma/rnic/tests/owned_rx_lookup_tb.v']
    before={**parent['source_sha256'],**parent['generated_sha256'],**{str(q.relative_to(ROOT)):digest(q)for q in own}}
    for n,h in before.items():assert digest(ROOT/n)==h,n
    run=Path(tempfile.mkdtemp(prefix='owned-rx-lookup-compiled-',dir=ROOT/'rdma/rnic/build'));inp=run/'inputs';inp.mkdir()
    for q in own:shutil.copy2(q,inp/q.name)
    for q in rtl.glob('*.dat'):shutil.copy2(q,run/q.name)
    result=dict(scope=__doc__,pass_test=False,terminal_exit_status=None,retained_directory=str(run.relative_to(ROOT)),
        source_sha256=before,parent_record=str(a.source_record),simulations=[],four_state=False,
        simulator_optimizer_workaround='-fno-dfg only; exact FPGA RTL/constraints unchanged',
        original_assertions_and_cycle_bounds_preserved=True,simulation_wall_bound_seconds=30,
        native_CQ=False,hardware_verified=False,whole_core_drain=False,physical_signoff=False)
    def current():
        for n,h in before.items():assert digest(ROOT/n)==h,n
    try:
        assert shutil.disk_usage(ROOT).free>1500*1024*1024,'insufficient headroom; no deletion'
        result['simulator_version']=subprocess.check_output([str(a.verilator),'--version'],text=True).strip()
        src=[str(inp/'owned_rx_lookup_tb.v'),str(inp/'rocev2_retrans_pool.v'),str(inp/'rocev2_owned_rx_lookup.v'),*map(str,sorted(rtl.glob('*.v')))]
        cmd=[str(a.verilator.resolve()),'-fno-dfg','--binary','--timing','--top-module','rx_lookup_tb','-Wno-fatal',
            '--Mdir',str(run/'obj'),'-o','test','-j','8','--output-split','20000','--output-split-cfuncs','0',
            '--output-groups','0','-CFLAGS','-O2',*src]
        (run/'compile-command.json').write_text(json.dumps(cmd,indent=2)+'\n')
        print(json.dumps(dict(phase='compile_additional_TWO_STATE',directory=str(run))),flush=True)
        t=time.monotonic()
        with(run/'compile.log').open('x')as out:r=fast.bounded(cmd,run,600,out)
        result['compile_seconds']=time.monotonic()-t
        if r.returncode:raise RuntimeError('compiler failed')
        binary=run/'obj/test';sha=digest(binary);result['compiled_binary_sha256']=sha
        for case in range(1,9):
            current();assert digest(binary)==sha
            print(json.dumps(dict(phase='additional_TWO_STATE',case=case)),flush=True)
            t=time.monotonic()
            with(run/f'case-{case}.log').open('x')as out:r=fast.bounded([str(binary),'+CASE='+str(case)],run,30,out)
            seconds=time.monotonic()-t
            if r.returncode:raise RuntimeError('actual case failed: '+str(case))
            prefix='OWNED_RX_LOOKUP_RTL ';text=(run/f'case-{case}.log').read_text()
            rows=[json.loads(line[len(prefix):])for line in text.splitlines()if line.startswith(prefix)]
            assert len(rows)==1 and rows[0]['pass_test']and rows[0]['case']==case
            current();assert digest(binary)==sha
            result['simulations'].append(dict(case=case,seconds=seconds,summary=rows[0],four_state=False))
            print(json.dumps(result['simulations'][-1]),flush=True)
        assert len(result['simulations'])==8
        result.update(pass_test=True,terminal_exit_status=0,simulation_seconds=sum(s['seconds']for s in result['simulations']))
    except Exception as error:result.update(terminal_exit_status=1,error_type=type(error).__name__,error=str(error));raise
    finally:
        result['artifact_sha256']={str(q.relative_to(ROOT)):digest(q)for q in [*run.iterdir(),*inp.iterdir()]if q.is_file()}
        with a.report.open('x')as out:out.write(json.dumps(result,indent=2)+'\n')
if __name__=='__main__':main()
