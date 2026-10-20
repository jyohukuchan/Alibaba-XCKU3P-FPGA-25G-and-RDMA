#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Isolated actual Vivado synthesis/BRAM/generation-reset wiring checks.

Not placement/routing/full-board timing/CDC, post-synthesis functional replay,
actual FNS integration, hard reconfiguration/power-loss recovery or hardware.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
ROOT=Path(__file__).resolve().parents[3]
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--unit-record',type=Path,required=True);p.add_argument('--tool',type=Path,required=True);p.add_argument('--report',type=Path,required=True)
    p.add_argument('--reuse-synthesis-record',type=Path)
    a=p.parse_args()
    if a.report.exists():p.error('preserve earlier evidence')
    unit=json.loads(a.unit_record.read_text());assert unit['pass_test']and unit['terminal_exit_status']==0 and len(unit['completed_cases'])==16
    assert unit['capacity']==2000 and unit['clock_period_ns']==4.0
    for name,h in unit['source_sha256'].items():assert digest(ROOT/name)==h,name
    run=Path(tempfile.mkdtemp(prefix='retrans-pool-synth-',dir=ROOT/'rdma/rnic/build'));inp=run/'inputs';inp.mkdir()
    files=[ROOT/'rdma/rnic/rtl/rocev2_retrans_pool.v',ROOT/'rdma/rnic/fpga/retrans_pool_synth.tcl',Path(__file__).resolve(),a.unit_record.resolve()]
    replay=None
    if a.reuse_synthesis_record:
        old=json.loads(a.reuse_synthesis_record.read_text())
        replay=ROOT/old['retained_directory']/'outputs/pool-synth.dcp'
        key=str(replay.relative_to(ROOT))
        assert digest(replay)==old['artifact_sha256'][key]
        assert old['source_sha256']['rdma/rnic/rtl/rocev2_retrans_pool.v']==digest(files[0])
        files+=[a.reuse_synthesis_record.resolve(),replay]
    for f in files:shutil.copy2(f,inp/f.name)
    source={str(f.relative_to(ROOT)):digest(f)for f in files};frozen={f.name:digest(f)for f in inp.iterdir()}
    (inp/'inputs.sha256').write_text(''.join(h+'  '+n+'\n'for n,h in sorted(frozen.items())))
    result=dict(scope=__doc__,pass_test=False,terminal_exit_status=None,retained_directory=str(run.relative_to(ROOT)),
        source_sha256=source,frozen_source_sha256=frozen,capacity=2000,clock_period_ns=4.0,
        actual_isolated_synthesis=True,physical_signoff=False,actual_FNS_process_integrated=False,hardware_verified=False)
    result['reused_immutable_synthesis']=replay is not None
    cmd=[str(a.tool.resolve()),'-mode','batch','-nojournal','-nolog','-notrace','-source',str(inp/'retrans_pool_synth.tcl')]
    (run/'command.json').write_text(json.dumps(cmd,indent=2)+'\n')
    print(json.dumps(dict(phase='isolated_synthesis',directory=str(run),NOT_full_board_or_physical_signoff=True)),flush=True)
    try:
        start=time.monotonic()
        env=dict(os.environ,AS02_POOL_SYNTH_INPUT=str(inp),AS02_POOL_SYNTH_OUTPUT=str(run/'outputs'))
        if replay:env['AS02_POOL_SYNTH_REPLAY_DCP']=str(inp/replay.name)
        with(run/'synthesis.log').open('x')as out:
            c=subprocess.run(cmd,cwd=run,env=env,stdout=out,stderr=subprocess.STDOUT,timeout=600)
        result['construction_seconds']=time.monotonic()-start
        if c.returncode:raise RuntimeError('pool synthesis/retention checks failed; retain '+str(run))
        rows=[s.split('\t')for s in(run/'outputs/retention.tsv').read_text().splitlines()]
        counts={r[0]:int(r[1])for r in rows if len(r)==2}
        assert counts['generation_registers']==counts['generation_reset_pins']==64
        assert counts['lease_BRAM_primitives']>0 and counts['ring_BRAM_primitives']>0
        assert all(r[-1]in['1','true']for r in rows if r[0]=='generation_pin')
        usage={}
        for line in(run/'outputs/utilization.rpt').read_text().splitlines():
            m=re.match(r'\|\s*([^|]+?)\s*\|\s*([0-9.]+)\s*\|',line)
            if m:usage[m[1]]=float(m[2])
        assert source=={n:digest(ROOT/n)for n in source};assert frozen=={n:digest(inp/n)for n in frozen}
        result.update(pass_test=True,terminal_exit_status=0,retention_wiring=counts,utilization=usage,
            all64_generation_reset_pins_constant_ground=True,actual_lease_and_ring_BRAM=True,
            post_synthesis_functional_replay=False)
    except Exception as e:result.update(terminal_exit_status=1,error=str(e),error_type=type(e).__name__);raise
    finally:
        result['artifact_sha256']={str(f.relative_to(ROOT)):digest(f)for f in run.rglob('*')if f.is_file()}
        with a.report.open('x')as out:out.write(json.dumps(result,indent=2)+'\n')
if __name__=='__main__':main()
