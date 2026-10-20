#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Synthesize complete owned Atomic HLS after actual service/legacy consumers.

4ns/default1.08ns,8QP,2000entries, original1500MiB guard unchanged.
Not native/physical/timing qualification; does not program or load anything.
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

TOP='rocev2_native_atomic_owned_top'


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ['source','csim-report','legacy-tx-report','legacy-rx-report','report']:
        p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--tool',type=Path,default=Path('/home/user/amd/2025.2/Vitis/bin/vitis-run'));a=p.parse_args()
    if a.report.exists():p.error('preserve previous evidence')
    available=shutil.disk_usage(ROOT).free
    if available<1500*1024*1024:raise RuntimeError('unchanged1500MiB HLS guard: insufficient space')
    source=a.source.resolve();source.relative_to(ROOT/'rdma/rnic/build')
    info=json.loads((source/'source.json').read_text())
    if info.get('HLS_top')!=TOP or not info.get('same_RX_query_channels_readback') or not info.get('original_unchanged') or \
        info.get('atomic_service_request_bits')!=512 or info.get('atomic_core_done_bits')!=224:
        raise ValueError('matched complete owned Atomic source required')
    tested=[]
    for path in [a.csim_report,a.legacy_tx_report,a.legacy_rx_report]:
        r=json.loads(path.read_text())
        if not all(r.get(n)for n in ['pass_test','source_unchanged','full_top_CPP_compiled']):
            raise ValueError('actual full-graph consumer evidence required: '+str(path))
        verify(r['source_sha256'],ROOT);tested.append(r)
        for n,h in info['derived_sources'].items():
            if r['source_sha256'].get(str((source/'fns'/n).relative_to(ROOT)))!=h:
                raise ValueError('tested a different core: '+n)
    if tested[0]['summary'].get('atomic_jobs')!=9 or not all(tested[0]['summary'].get(n)for n in
        ['shared_PSN_MSN','withheld_service_no_advance','withheld_MSN_and_PSN_no_done','immutable_owner_echo',
         'same_table_readback','drop_then_forward_progress']) or not tested[0].get('service_RTL_actual'):
        raise ValueError('actual same-table/owned real RTL service evidence required')
    if tested[1]['summary'].get('actual_immediate_opcodes')!=2 or \
        tested[2]['summary'].get('actual_request_opcodes')!=2 or not tested[2]['summary'].get('write_data_not_RQ_buffer'):
        raise ValueError('Immediate regression evidence required')
    verify(info['source_sha256'],Path(info['source_base']));verify(info['derived_sources'],source/'fns')
    tcl=Path(__file__).with_name('native_duplex_synth.tcl');script=tcl.read_text()
    if script.count('set_top rocev2_native_duplex_top')!=1:raise ValueError('synthesis template changed')
    script=script.replace('set_top rocev2_native_duplex_top','set_top '+TOP).replace('Use build_native_duplex.py','Use build_native_atomic_owned.py')
    inputs=[*source.rglob('*'),a.csim_report.resolve(),a.legacy_tx_report.resolve(),a.legacy_rx_report.resolve(),
        Path(__file__).resolve(),tcl,Path(__file__).with_name('build_native_replay.py')]
    hashes={str(x.relative_to(ROOT)):digest(x)for x in inputs if x.is_file()}
    run=Path(tempfile.mkdtemp(prefix='native-atomic-owned-hls-',dir=ROOT/'rdma/rnic/build'))
    frozen=run/'inputs';shutil.copytree(source/'fns',frozen/'fns');shutil.copytree(source/'adapter',frozen/'adapter')
    (frozen/'synth.tcl').write_text(script)
    snapshot={str(x.relative_to(frozen)):digest(x)for x in frozen.rglob('*')if x.is_file()}
    (frozen/'inputs.sha256').write_text(''.join(h+'  '+n+'\n'for n,h in sorted(snapshot.items())))
    command=[str(a.tool.resolve()),'--mode','hls','--tcl',str(frozen/'synth.tcl')]
    env=os.environ.copy();env['AS02_RNIC_HLS_INPUT']=str(frozen);env['AS02_HLS_BUILD']=str(run/'project')
    result=dict(scope=__doc__,pass_test=False,source_sha256=hashes,frozen_sha256=snapshot,
        source_directory=str(source.relative_to(ROOT)),directory=str(run.relative_to(ROOT)),command=command,
        started_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),HLS_top=TOP,
        HLS_free_space_guard_bytes=1500*1024*1024,free_bytes_at_start=available,
        shared_PSN_MSN=True,native_integration=False,atomic_requester=False,
        hardware_verified=False,board_or_bitstream_built=False,standard_verbs=False,whole_core_drain_proved=False)
    print(json.dumps(dict(directory=str(run),source_frozen=True,HLS_top=TOP,
        free_bytes_at_start=available,HLS_guard_bytes=1500*1024*1024,hardware_will_not_be_programmed=True)),flush=True)
    try:
        start=time.monotonic()
        with(run/'synthesis.log').open('x')as log:
            r=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,env=env,timeout=7200)
        result.update(exit_code=r.returncode,elapsed_seconds=time.monotonic()-start)
        if r.returncode:raise RuntimeError('HLS failed: '+str(run/'synthesis.log'))
        verify(hashes,ROOT);verify(snapshot,frozen)
        raw=run/'project/solution1/syn/verilog';text=(raw/(TOP+'.v')).read_text()
        expected={'m_axis_atomic_request_TDATA':512,'s_axis_atomic_reply_TDATA':392,
            's_axis_atomic_owner_TDATA':144,'m_axis_atomic_done_TDATA':224,
            's_axis_sq_meta_TDATA':280,'m_axis_qp_apply_TDATA':80,'s_axis_rnr_event_TDATA':56,
            's_axis_recv_owner_TDATA':680,'m_axis_recv_done_TDATA':752,
            's_axis_request_owner_TDATA':624,'m_axis_request_done_TDATA':688,
            'm_axis_mem_read_cmd_TDATA':96,'m_axis_mem_write_cmd_TDATA':96}
        for name,width in expected.items():
            if not re.search(r'\[\s*'+str(width-1)+r'\s*:\s*0\s*\]\s*'+name+r'\s*;',text):
                raise ValueError('wrong generated port '+name)
        xml=ET.parse(run/'project/solution1/syn/report'/(TOP+'_csynth.xml')).getroot()
        target=xml.findtext('.//TargetClockPeriod');uncertainty=xml.findtext('.//ClockUncertainty')
        if float(target)!=4.0 or float(uncertainty)!=1.08:raise ValueError('original timing target/uncertainty changed')
        result.update(pass_test=True,source_and_frozen_inputs_unchanged=True,
            generated_sha256={x.name:digest(x)for x in sorted(raw.iterdir())if x.suffix in ['.v','.dat']},
            target_clock_period=target,clock_uncertainty=uncertainty,
            estimated_clock_period=xml.findtext('.//EstimatedClockPeriod'),
            resources={n:xml.findtext('.//AreaEstimates/Resources/'+n)for n in ['LUT','FF','BRAM_18K','DSP']},
            generated_port_bits=expected,metadata_entries=2000,MAX_QPS=8)
    except Exception as e:result.update(error_type=type(e).__name__,error=str(e));raise
    finally:
        result['finished_at']=datetime.datetime.now(datetime.timezone.utc).isoformat()
        with a.report.open('x')as f:f.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k]for k in ['pass_test','elapsed_seconds','resources','estimated_clock_period','directory']}),flush=True)


if __name__=='__main__':main()
