#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Exact generated actual TX graph, bounded FOUR-STATE; not native/physical."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import time
from fast_transport_sim import bounded
ROOT=Path(__file__).resolve().parents[3]
def digest(f):return hashlib.sha256(Path(f).read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--hls-report',type=Path,required=True);p.add_argument('--report',type=Path,required=True)
    a=p.parse_args()
    if a.report.exists():p.error('preserve earlier evidence')
    h=json.loads(a.hls_report.read_text());assert h['pass_test'] and h['terminal_exit_status']==0 and h['HLS_constructed']
    before={**h['source_sha256'],str(a.hls_report):digest(a.hls_report)}
    bench=ROOT/'rdma/rnic/tests/owned_wire_tx_tb.v'
    before.update({str(f.relative_to(ROOT)):digest(f)for f in [Path(__file__).resolve(),bench]})
    generated={n:v for n,v in h['generated_sha256'].items()}
    for n,v in {**before,**generated}.items():assert digest(ROOT/n)==v,n
    inp=ROOT/h['retained_directory']/'inputs'
    for n,v in h['frozen_source_sha256'].items():assert digest(inp/n)==v,n
    run=Path(tempfile.mkdtemp(prefix='owned-wire-tx-RTL-',dir=ROOT/'rdma/rnic/build'))
    (run/'inputs').mkdir()
    for f in [Path(__file__).resolve(),bench]:shutil.copy2(f,run/'inputs'/f.name)
    rtl=[ROOT/n for n in generated if n.endswith('.v')]
    for n in generated:
        if n.endswith('.dat'):shutil.copy2(ROOT/n,run/Path(n).name)
    result=dict(scope=__doc__,pass_test=False,terminal_exit_status=None,retained_directory=str(run.relative_to(ROOT)),
        source_sha256=before,component_generated_sha256=generated,
        frozen_source_sha256={f.name:digest(f)for f in(run/'inputs').iterdir()},
        source_and_generated_inputs_unchanged=False,simulations=[],four_state=True,
        actual_FNS_selected_TX_functions=5,clock_period_ns=4.0,cycle_bound=3000,simulation_wall_bound_seconds=30,
        native_admission_connected=False,RX_context_lookup=False,MAC_SFD_verified=False,
        allocator_or_actual_timer_joined=False,full_wire_producer_fence=False,
        native_CQ=False,whole_core_drain=False,physical_signoff=False,hardware_verified=False)
    def current():
        for n,v in {**before,**generated}.items():assert digest(ROOT/n)==v,n
        for n,v in h['frozen_source_sha256'].items():assert digest(inp/n)==v,n
    try:
        command=[shutil.which('iverilog'),'-g2012','-s','tb','-o',str(run/'sim'),str(run/'inputs'/bench.name),*map(str,rtl)]
        (run/'compile-command.json').write_text(json.dumps(command,indent=2)+'\n')
        print(json.dumps(dict(phase='compile_exact_generated_FOUR_STATE',directory=str(run))),flush=True)
        t=time.monotonic()
        with(run/'compile.log').open('x')as log:c=bounded(command,run,120,log)
        result['compile_seconds']=time.monotonic()-t
        if c.returncode:raise RuntimeError('Icarus compile failed; retain '+str(run/'compile.log'))
        binary=digest(run/'sim');result['compiled_binary_sha256']=binary
        for case in range(1,6):
            current();assert digest(run/'sim')==binary
            t=time.monotonic();r=bounded([shutil.which('vvp'),str(run/'sim'),'+CASE='+str(case)],run,30)
            seconds=time.monotonic()-t;(run/f'case-{case}.log').write_text(r.stdout+r.stderr)
            if r.returncode:raise RuntimeError('FOUR-STATE case failed: '+str(case))
            rows=[json.loads(s)for s in r.stdout.splitlines()if s.startswith('{')]
            assert len(rows)==1 and rows[0]['pass_test'] and rows[0]['case']==case and rows[0]['four_state']
            assert digest(run/'sim')==binary;current()
            result['simulations'].append(dict(case=case,seconds=seconds,summary=rows[0],binary_unchanged=True))
            print(json.dumps(dict(case=case,seconds=seconds,summary=rows[0])),flush=True)
        assert len(result['simulations'])==5
        result.update(pass_test=True,terminal_exit_status=0,source_and_generated_inputs_unchanged=True)
    except Exception as error:
        result.update(terminal_exit_status=1,error=str(error),error_type=type(error).__name__);raise
    finally:
        result['artifact_sha256']={str(f.relative_to(ROOT)):digest(f)for f in run.iterdir()if f.is_file()}
        with a.report.open('x')as out:out.write(json.dumps(result,indent=2)+'\n')
if __name__=='__main__':main()
