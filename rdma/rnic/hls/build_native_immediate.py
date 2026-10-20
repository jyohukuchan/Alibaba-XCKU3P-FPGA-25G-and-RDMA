#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Synthesize the matched Immediate TX/RX core, never install/program it.

Unchanged original1500MiB guard,4ns clock/default uncertainty,8QP/2000entries.
This candidate changes typed ports and MUST NOT replace the duplex delivery
until native full-key/RQ/CQ/MMIO and kernel/provider support is matched.
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

TOP='rocev2_native_immediate_top'

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['source','csim-report','report']:p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--tool',type=Path,default=Path('/home/user/amd/2025.2/Vitis/bin/vitis-run'));a=p.parse_args()
    if a.report.exists():p.error('preserve previous evidence')
    available=shutil.disk_usage(ROOT).free
    if available<1500*1024*1024:raise RuntimeError('unchanged1500MiB HLS guard: insufficient space')
    source=a.source.resolve();source.relative_to(ROOT/'rdma/rnic/build')
    info=json.loads((source/'source.json').read_text());tested=json.loads(a.csim_report.read_text())
    if info.get('HLS_top')!=TOP or not all(info.get(n)for n in ['external_replay','native_rnr','receive_retirement',
        'request_retirement','duplex_memory_provenance','original_unchanged','request_immediate','receive_immediate']):
        raise ValueError('matched complete Immediate source required')
    if not all(tested.get(n)for n in ['pass_test','source_unchanged','full_top_CPP_compiled']):
        raise ValueError('current actual C++ execution required')
    summary=tested.get('summary',{})
    if summary.get('actual_request_opcodes')!=2 or summary.get('values_per_opcode')!=4 or not all(summary.get(n)for n in
        ['actual_BTH_EXH_payload_ACK_and_PSN_consumers','write_data_not_RQ_buffer','actual_wire_immediate_separate_from_posted_context','PSN_wrap']):
        raise ValueError('both actual Immediate TX/RX operation consumers required')
    verify(tested['source_sha256'],ROOT);verify(info['source_sha256'],Path(info['source_base']));verify(info['derived_sources'],source/'fns')
    tcl=Path(__file__).with_name('native_duplex_synth.tcl')
    script=tcl.read_text()
    if script.count('set_top rocev2_native_duplex_top')!=1:raise ValueError('review changed synthesis template')
    script=script.replace('set_top rocev2_native_duplex_top','set_top '+TOP).replace('Use build_native_duplex.py','Use build_native_immediate.py')
    inputs=[*source.rglob('*'),a.csim_report.resolve(),Path(__file__).resolve(),tcl,Path(__file__).with_name('build_native_replay.py')]
    hashes={str(x.relative_to(ROOT)):digest(x)for x in inputs if x.is_file()}
    run=Path(tempfile.mkdtemp(prefix='native-immediate-hls-',dir=ROOT/'rdma/rnic/build'))
    frozen=run/'inputs';shutil.copytree(source/'fns',frozen/'fns');shutil.copytree(source/'adapter',frozen/'adapter')
    (frozen/'synth.tcl').write_text(script)
    snapshot={str(x.relative_to(frozen)):digest(x)for x in frozen.rglob('*')if x.is_file()}
    (frozen/'inputs.sha256').write_text(''.join(h+'  '+n+'\n'for n,h in sorted(snapshot.items())))
    cmd=[str(a.tool.resolve()),'--mode','hls','--tcl',str(frozen/'synth.tcl')]
    env=os.environ.copy();env['AS02_RNIC_HLS_INPUT']=str(frozen);env['AS02_HLS_BUILD']=str(run/'project')
    result=dict(scope=__doc__,pass_test=False,source_sha256=hashes,frozen_sha256=snapshot,
        source_directory=str(source.relative_to(ROOT)),directory=str(run.relative_to(ROOT)),command=cmd,
        started_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),HLS_top=TOP,
        request_immediate=True,receive_immediate=True,native_integration=False,
        HLS_free_space_guard_bytes=1500*1024*1024,free_bytes_at_start=available,
        hardware_verified=False,board_or_bitstream_built=False,standard_verbs=False,whole_core_drain_proved=False)
    print(json.dumps(dict(directory=str(run),source_frozen=True,HLS_top=TOP,
        HLS_guard_bytes=result['HLS_free_space_guard_bytes'],free_bytes_at_start=available,
        hardware_will_not_be_programmed=True)),flush=True)
    try:
        start=time.monotonic()
        with(run/'synthesis.log').open('x')as log:r=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,env=env,timeout=7200)
        result.update(exit_code=r.returncode,elapsed_seconds=time.monotonic()-start)
        if r.returncode:raise RuntimeError('HLS failed: '+str(run/'synthesis.log'))
        verify(hashes,ROOT);verify(snapshot,frozen)
        raw=run/'project/solution1/syn/verilog';text=(raw/(TOP+'.v')).read_text()
        expected={'s_axis_sq_meta_TDATA':280,'m_axis_qp_apply_TDATA':80,'s_axis_rnr_event_TDATA':56,
            's_axis_recv_owner_TDATA':680,'m_axis_recv_done_TDATA':752,
            's_axis_request_owner_TDATA':624,'m_axis_request_done_TDATA':688,
            'm_axis_mem_read_cmd_TDATA':96,'m_axis_mem_write_cmd_TDATA':96}
        for name,width in expected.items():
            if not re.search(r'\[\s*'+str(width-1)+r'\s*:\s*0\s*\]\s*'+name+r'\s*;',text):
                raise ValueError('wrong generated port width '+name)
        xml=ET.parse(run/'project/solution1/syn/report'/(TOP+'_csynth.xml')).getroot()
        result.update(pass_test=True,source_and_frozen_inputs_unchanged=True,
            generated_sha256={x.name:digest(x)for x in sorted(raw.iterdir())if x.suffix in ['.v','.dat']},
            estimated_clock_period=xml.findtext('.//EstimatedClockPeriod'),
            resources={n:xml.findtext('.//AreaEstimates/Resources/'+n)for n in ['LUT','FF','BRAM_18K','DSP']},
            generated_port_bits=expected,metadata_entries=2000,MAX_QPS=8)
    except Exception as e:result.update(error_type=type(e).__name__,error=str(e));raise
    finally:
        result['finished_at']=datetime.datetime.now(datetime.timezone.utc).isoformat()
        with a.report.open('x')as f:f.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k]for k in ['pass_test','elapsed_seconds','resources','directory']}),flush=True)

if __name__=='__main__':main()
