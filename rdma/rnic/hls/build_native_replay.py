#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Build the full matched external-native-replay transport, NEVER hardware.

Actual source-bound C++ evidence and original full-capacity source identities
are required. Preserve the 1500MiB HLS/XSIM free-space guard. A completed HLS
build is not generated-wire/reset/board/timing or CQ-retirement qualification.
"""
import argparse
import datetime
import hashlib
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
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def verify(mapping,base):
    for n,h in mapping.items():
        if digest(base/n)!=h:raise ValueError('source changed: '+str(base/n))

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',required=True,type=Path);p.add_argument('--csim-report',required=True,type=Path)
    p.add_argument('--tool',type=Path,default=Path('/home/user/amd/2025.2/Vitis/bin/vitis-run'))
    p.add_argument('--report',required=True,type=Path);a=p.parse_args()
    if a.report.exists():p.error('preserve previous evidence')
    available=shutil.disk_usage(ROOT).free
    if available<1500*1024*1024:raise RuntimeError('original 1500MiB HLS guard: insufficient space')
    source=a.source.resolve();source.relative_to(ROOT/'rdma/rnic/build')
    info=json.loads((source/'source.json').read_text());tested=json.loads(a.csim_report.read_text())
    if not info.get('external_replay') or not info.get('original_unchanged'):
        raise ValueError('not the matched external-native-replay source')
    if not tested.get('pass_test') or not tested.get('source_unchanged') or not tested.get('full_top_CPP_compiled'):
        raise ValueError('actual matched C++ evidence required')
    verify(tested['source_sha256'],ROOT);verify(info['source_sha256'],Path(info['source_base']))
    verify(info['derived_sources'],source/'fns')
    tcl=Path(__file__).with_name('native_replay_synth.tcl')
    originals=[*source.rglob('*'),a.csim_report.resolve(),Path(__file__).resolve(),tcl]
    hashes={str(x.relative_to(ROOT)):digest(x)for x in originals if x.is_file()}
    run=Path(tempfile.mkdtemp(prefix='native-replay-hls-',dir=ROOT/'rdma/rnic/build'))
    frozen=run/'inputs';shutil.copytree(source/'fns',frozen/'fns');shutil.copytree(source/'adapter',frozen/'adapter')
    shutil.copy2(tcl,frozen/'synth.tcl')
    snapshot={str(x.relative_to(frozen)):digest(x)for x in frozen.rglob('*')if x.is_file()}
    (frozen/'inputs.sha256').write_text(''.join(h+'  '+n+'\n'for n,h in sorted(snapshot.items())))
    command=[str(a.tool.resolve()),'--mode','hls','--tcl',str(frozen/'synth.tcl')]
    env=os.environ.copy();env['AS02_RNIC_HLS_INPUT']=str(frozen);env['AS02_HLS_BUILD']=str(run/'project')
    started=datetime.datetime.now(datetime.timezone.utc).isoformat()
    print(json.dumps(dict(directory=str(run),started_at=started,source_frozen=True,HLS_guard_bytes=1500*1024*1024,
        free_bytes_at_start=available,hardware_will_not_be_programmed=True)),flush=True)
    result=dict(scope=__doc__,pass_test=False,source_sha256=hashes,frozen_sha256=snapshot,
        source_directory=str(source.relative_to(ROOT)),directory=str(run.relative_to(ROOT)),started_at=started,
        command=command,HLS_free_space_guard_bytes=1500*1024*1024,free_bytes_at_start=available,
        hardware_verified=False,board_or_bitstream_built=False,standard_verbs=False,whole_core_drain_proved=False)
    start=time.monotonic()
    try:
        with (run/'synthesis.log').open('x')as log:
            r=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,env=env,timeout=7200)
        result['exit_code']=r.returncode;result['elapsed_seconds']=time.monotonic()-start
        if r.returncode:raise RuntimeError('HLS failed; '+str(run/'synthesis.log'))
        verify(hashes,ROOT);verify(snapshot,frozen)
        raw=run/'project/solution1/syn/verilog';top=raw/'rocev2_native_replay_top.v'
        text=top.read_text()
        for width,name in [(247,'s_axis_sq_meta_TDATA'),(79,'m_axis_qp_apply_TDATA')]:
            if not re.search(r'\[\s*'+str(width)+r'\s*:\s*0\s*\]\s*'+name+r'\s*;',text):
                raise ValueError('wrong generated port width '+name)
        xml=ET.parse(run/'project/solution1/syn/report/rocev2_native_replay_top_csynth.xml').getroot()
        result.update(pass_test=True,source_and_frozen_inputs_unchanged=True,
            generated_sha256={x.name:digest(x)for x in sorted(raw.iterdir())if x.suffix in ['.v','.dat']},
            estimated_clock_period=xml.findtext('.//EstimatedClockPeriod'),
            resources={n:xml.findtext('.//AreaEstimates/Resources/'+n)for n in ['LUT','FF','BRAM_18K','DSP']},
            SQ_AXIS_bits=248,QP_apply_AXIS_bits=80)
    except Exception as e:result.update(error_type=type(e).__name__,error=str(e));raise
    finally:
        result['finished_at']=datetime.datetime.now(datetime.timezone.utc).isoformat()
        with a.report.open('x')as f:f.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k]for k in ['pass_test','elapsed_seconds','resources','directory']}),flush=True)
if __name__=='__main__':main()
