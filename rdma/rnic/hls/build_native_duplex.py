#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Synthesize the complete SAME native duplex core at unchanged geometry/clock.

Original1500MiB free-space guard,4ns/default1.08ns uncertainty,8QP/2000metadata
preserved. This is not full-board timing/DRC/CDC or physical/kernel evidence.
"""
import argparse
import datetime
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
import xml.etree.ElementTree as ET
from build_native_replay import ROOT,digest,verify

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True)
    p.add_argument('--csim-report',type=Path,required=True);p.add_argument('--report',type=Path,required=True)
    p.add_argument('--tool',type=Path,default=Path('/home/user/amd/2025.2/Vitis/bin/vitis-run'));a=p.parse_args()
    if a.report.exists():p.error('preserve previous evidence')
    available=shutil.disk_usage(ROOT).free
    if available<1500*1024*1024:raise RuntimeError('unchanged1500MiB HLS guard: insufficient space')
    source=a.source.resolve();source.relative_to(ROOT/'rdma/rnic/build')
    info=json.loads((source/'source.json').read_text());tested=json.loads(a.csim_report.read_text())
    if not all(info.get(x)for x in ['external_replay','native_rnr','receive_retirement','request_retirement',
        'duplex_memory_provenance','original_unchanged']):raise ValueError('matched duplex source required')
    if not all(tested.get(x)for x in ['pass_test','source_unchanged','full_top_CPP_compiled']):raise ValueError('actual C++ evidence required')
    if tested.get('summary',{}).get('same_core_bidirectional_pending_requests')!=3:
        raise ValueError('all three pending request/receive cases required')
    verify(tested['source_sha256'],ROOT);verify(info['source_sha256'],Path(info['source_base']));verify(info['derived_sources'],source/'fns')
    tcl=Path(__file__).with_name('native_duplex_synth.tcl')
    inputs=[*source.rglob('*'),a.csim_report.resolve(),Path(__file__).resolve(),tcl,Path(__file__).with_name('build_native_replay.py')]
    hashes={str(x.relative_to(ROOT)):digest(x)for x in inputs if x.is_file()}
    run=Path(tempfile.mkdtemp(prefix='native-duplex-hls-',dir=ROOT/'rdma/rnic/build'))
    frozen=run/'inputs';shutil.copytree(source/'fns',frozen/'fns');shutil.copytree(source/'adapter',frozen/'adapter');shutil.copy2(tcl,frozen/'synth.tcl')
    snapshot={str(x.relative_to(frozen)):digest(x)for x in frozen.rglob('*')if x.is_file()}
    (frozen/'inputs.sha256').write_text(''.join(h+'  '+n+'\n'for n,h in sorted(snapshot.items())))
    cmd=[str(a.tool.resolve()),'--mode','hls','--tcl',str(frozen/'synth.tcl')]
    env=os.environ.copy();env['AS02_RNIC_HLS_INPUT']=str(frozen);env['AS02_HLS_BUILD']=str(run/'project')
    result=dict(scope=__doc__,pass_test=False,source_sha256=hashes,frozen_sha256=snapshot,
        source_directory=str(source.relative_to(ROOT)),directory=str(run.relative_to(ROOT)),command=cmd,
        started_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),HLS_top='rocev2_native_duplex_top',
        native_rnr=True,receive_retirement=True,request_retirement=True,duplex_memory_provenance=True,
        HLS_free_space_guard_bytes=1500*1024*1024,free_bytes_at_start=available,hardware_verified=False,
        board_or_bitstream_built=False,standard_verbs=False,whole_core_drain_proved=False)
    print(json.dumps(dict(directory=str(run),started_at=result['started_at'],source_frozen=True,
        HLS_guard_bytes=result['HLS_free_space_guard_bytes'],free_bytes_at_start=available,hardware_will_not_be_programmed=True)),flush=True)
    try:
        start=time.monotonic()
        with(run/'synthesis.log').open('x')as log:r=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,env=env,timeout=7200)
        result.update(exit_code=r.returncode,elapsed_seconds=time.monotonic()-start)
        if r.returncode:raise RuntimeError('HLS failed: '+str(run/'synthesis.log'))
        verify(hashes,ROOT);verify(snapshot,frozen)
        raw=run/'project/solution1/syn/verilog';text=(raw/'rocev2_native_duplex_top.v').read_text()
        for width,name in [(247,'s_axis_sq_meta_TDATA'),(79,'m_axis_qp_apply_TDATA'),(55,'s_axis_rnr_event_TDATA'),
            (647,'s_axis_recv_owner_TDATA'),(679,'m_axis_recv_done_TDATA'),
            (591,'s_axis_request_owner_TDATA'),(655,'m_axis_request_done_TDATA'),
            (95,'m_axis_mem_read_cmd_TDATA'),(95,'m_axis_mem_write_cmd_TDATA')]:
            if not re.search(r'\[\s*'+str(width)+r'\s*:\s*0\s*\]\s*'+name+r'\s*;',text):raise ValueError('wrong generated port width '+name)
        xml=ET.parse(run/'project/solution1/syn/report/rocev2_native_duplex_top_csynth.xml').getroot()
        result.update(pass_test=True,source_and_frozen_inputs_unchanged=True,
            generated_sha256={x.name:digest(x)for x in sorted(raw.iterdir())if x.suffix in ['.v','.dat']},
            estimated_clock_period=xml.findtext('.//EstimatedClockPeriod'),
            resources={n:xml.findtext('.//AreaEstimates/Resources/'+n)for n in ['LUT','FF','BRAM_18K','DSP']},
            memory_command_bits=96,memory_command_origin_bits=[94,95],metadata_entries=2000,MAX_QPS=8)
    except Exception as e:result.update(error_type=type(e).__name__,error=str(e));raise
    finally:
        result['finished_at']=datetime.datetime.now(datetime.timezone.utc).isoformat()
        with a.report.open('x')as f:f.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k]for k in ['pass_test','elapsed_seconds','resources','directory']}),flush=True)

if __name__=='__main__':main()
