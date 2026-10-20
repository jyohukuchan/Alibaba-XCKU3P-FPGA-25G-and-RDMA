#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual owned HLS/Atomic/MR/IP + actual25G MAC/SFD/CDC/automatic retirement.

No test-generated positive receipt or retirement. Real framer/shared native
mux, async frame FIFO, XGMII/FCS/SFD tag RTL and timestamp CDC are connected.
Host descriptors/order/PHY pins/PTP time input remain models. Not full native
SQ/kernel/provider/physical/board/timing qualification. Each runtime<=30s.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import atomic_mac_generated_fixture as fixture
import probe_atomic_owned_generated as prior
import test_atomic_mac_tx_rtl as mac

ROOT=fixture.ROOT;digest=fixture.prior.digest


def verify(output,case):
    result=prior.verify(output,case)
    frames=fixture.link.frames(output)
    atomic=[(t,f)for t,f in frames if t!=0 and t<8192]
    native=[(t,f)for t,f in frames if not (t!=0 and t<8192)]
    expected=result['actual_IP_UDP_ICRC_packets']
    if len(atomic)!=len(expected):raise ValueError('actual MAC/frame count differs from actual HLS wire')
    for (tag,frame),packet in zip(atomic,expected):
        if frame!=bytes.fromhex('0200000000010200000000020800'+packet):
            raise ValueError('actual Ethernet/XGMII/FCS bytes differ from actual protected HLS output')
    if case==0:
        if [t for t,_ in atomic]!=list(range(1,10))+[11]or native!=[(0x9234,fixture.NATIVE)]:
            raise ValueError('actual fresh MAC tags, drop tag gap or unrelated native frame changed')
    elif native:raise ValueError('unexpected native frame')
    if result['summary'].get('MAC_boundary_model')or result['summary'].get('positive_MAC_retirement_model'):
        raise ValueError('test still using a modeled MAC receipt')
    return dict(**result,actual_XGMII_Ethernet_frames=[dict(tag=t,frame_hex=f.hex())for t,f in frames],
        actual_SFD_EOF_FCS_CDC_and_automatic_packet_retirement=True,physical_host_and_PHY_still_models=True)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--hls-report',type=Path,required=True)
    p.add_argument('--report',type=Path,required=True)
    p.add_argument('--reuse-compiled-report',type=Path,help='fresh translation, only exact byte-identical compiler inputs reused')
    a=p.parse_args()
    if a.report.exists():p.error('preserve prior evidence')
    if shutil.disk_usage(ROOT).free<1024**3:raise RuntimeError('unchanged fresh-native1GiB guard')
    hls=json.loads(a.hls_report.read_text())
    if not hls.get('pass_test')or hls.get('HLS_top')!='rocev2_native_atomic_owned_top':p.error('matched complete owned raw core required')
    raw=ROOT/hls['directory']/'project/solution1/syn/verilog'
    for n,h in hls['generated_sha256'].items():
        if digest(raw/n)!=h:raise ValueError('raw HLS changed')
    run=Path(tempfile.mkdtemp(prefix='atomic-owned-generated-mac-',dir=ROOT/'rdma/rnic/build'))
    obj=(Path(json.loads(a.reuse_compiled_report.read_text())['compile_directory'])if a.reuse_compiled_report else
        Path(tempfile.mkdtemp(prefix='as02-atomic-owned-generated-obj-mac-',dir='/dev/shm')))
    words,frames=prior.inputs();tb,bridge=fixture.bench(run,len(words))
    if 'w_s_atomic_retire_valid='in tb or 'force 'in tb:raise ValueError('no test-driven retirement/force')
    (run/'tb.v').write_text(tb);(run/'input.hex').write_text(''.join(f'{w:037x}\n'for w in words))
    sources=[*sorted(raw.glob('*.v')),*fixture.prior.rtl.SOURCES,fixture.old.service.RTL,
        ROOT/'rdma/rnic/rtl/rocev2_atomic_packet_guard.v',*mac.SOURCES,*fixture.link.SOURCES,
        ROOT/'rdma/rtl/rocev2_ipv4_icrc.v',ROOT/'rdma/rtl/rocev2_tx_padding.v',
        mac.AXIS/'axis_adapter.v',mac.AXIS/'axis_fifo.v',mac.AXIS/'axis_broadcast.v',mac.ETH/'lfsr.v',bridge]
    sources=list(dict.fromkeys(sources));data=sorted(raw.glob('*.dat'))
    for f in data:shutil.copy2(f,run/f.name)
    helpers=[Path(m.__file__).resolve()for m in list(sys.modules.values())if getattr(m,'__file__',None)and
        (Path(m.__file__).resolve().is_relative_to(ROOT/'rdma/rnic/tests')or Path(m.__file__).resolve().is_relative_to(ROOT/'rdma/rnic/fpga'))]
    own=[*helpers,Path(__file__).resolve(),a.hls_report.resolve(),ROOT/'rdma/host/rocev2_wire.py',
        ROOT/'rdma/rtl/rocev2_integrity_transport.v',ROOT/'rdma/rnic/rtl/rocev2_protected_responder.v',run/'tb.v',run/'input.hex']
    before={str(x.relative_to(ROOT)):digest(x)for x in [*sources,*data,*own]}
    report=dict(scope=__doc__,pass_test=False,source_sha256=before,directory=str(run.relative_to(ROOT)),compile_directory=str(obj),
        actual_generated_HLS=True,two_state=True,actual_Atomic_MR_PTE_paged_RAM_IP_UDP_ICRC=True,
        actual_MAC_XGMII_SFD_FCS_and_receipt_CDC=True,test_produced_positive_MAC_receipt=False,test_driven_packet_retirement=False,
        core_MHz=250,MAC_MHz=390.625,simulation_limit_seconds=30,native_integrated=False,hardware_verified=False,
        physical_host_ordering_descriptor_PHY_and_PTP_clock_input_models=True,tests={})
    try:
        command=[str(prior.old.TOOL),'--binary','--timing','--top-module','tb','-Wno-fatal','-j','8',
            '--output-split','20000','--output-split-cfuncs','0','--output-groups','0','-CFLAGS','-O0',
            '--Mdir',str(obj),str(run/'tb.v'),*map(str,sources)]
        print(json.dumps(dict(directory=str(run),compile_directory=str(obj),compile_limit_seconds=1200)),flush=True)
        env=os.environ.copy();env['TMPDIR']='/dev/shm/as02-native-compiler-tmp-QYQsVyT5';start=time.monotonic()
        if a.reuse_compiled_report:
            import atomic_owned_generated_compile_cache as cache
            before[str(Path(cache.__file__).resolve().relative_to(ROOT))]=digest(Path(cache.__file__).resolve())
            reused=cache.compile(command,run,env,a.reuse_compiled_report.resolve())
            before.update(reused.pop('extra_source_sha256'));report.update(reused)
        else:
            with(run/'compile.log').open('x')as log:
                c=subprocess.run(command,cwd=run,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=1200)
            report.update(compile_seconds=time.monotonic()-start,compile_command=command)
            if c.returncode:raise RuntimeError('generated real-MAC composition compile: '+str(run/'compile.log'))
        shutil.copy2(obj/'Vtb',run/'Vtb')
        for case in range(4):
            start=time.monotonic()
            with(run/f'case-{case}.log').open('x')as log:
                c=subprocess.run([str(run/'Vtb'),f'+case={case}'],cwd=run,stdout=log,stderr=subprocess.STDOUT,
                    timeout=30,preexec_fn=prior.old.no_core)
            report['tests'][case]=dict(seconds=time.monotonic()-start,exit=c.returncode)
            if c.returncode:raise RuntimeError('generated real-MAC case: '+str(run/f'case-{case}.log'))
            report['tests'][case].update(verify((run/f'case-{case}.log').read_text(),case))
        if before!={n:digest(ROOT/n)for n in before}:raise ValueError('source changed during build/test')
        report.update(pass_test=True,source_unchanged=True)
    except Exception as e:report['error']=str(e);raise
    finally:
        report['artifact_sha256']={str(x.relative_to(ROOT)):digest(x)for x in run.iterdir()if x.is_file()}
        with a.report.open('x')as f:f.write(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(pass_test=True,compile_seconds=report['compile_seconds'],tests={k:v['seconds']for k,v in report['tests'].items()})),flush=True)


if __name__=='__main__':main()
