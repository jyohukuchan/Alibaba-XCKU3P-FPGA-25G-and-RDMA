#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Elaborate actual new full HLS and matched requester integrity bridge.

Count ONE actual PSN/MSN/RX/retransmission domain. Compile ONLY, not packet
execution or native MR/DMA/MAC/CQ/kernel/provider/physical/timing signoff.
Original fresh-native1GiB guard retained; large artifacts use task-owned RAM.
"""
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
from probe_atomic_request_hls import ROOT,digest

sys.path.insert(0,str(ROOT/'rdma/rnic/fpga'))
import derive_atomic_request_bridge as bridge


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build-report',type=Path,required=True)
    p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve prior evidence')
    build=json.loads(a.build_report.read_text())
    if not build.get('pass_test')or build.get('HLS_top')!='rocev2_native_atomic_request_top':p.error('matched completed full HLS required')
    if shutil.disk_usage(ROOT).free<1024**3:raise RuntimeError('unchanged fresh-native1GiB guard')
    if shutil.disk_usage('/dev/shm').free<1024**3:raise RuntimeError('RAM artifact1GiB guard')
    raw=ROOT/build['directory']/'project/solution1/syn/verilog'
    for n,h in build['generated_sha256'].items():
        if digest(raw/n)!=h:raise ValueError('changed generated HLS '+n)
    run=Path(tempfile.mkdtemp(prefix='atomic-request-elaboration-',dir=ROOT/'rdma/rnic/build'))
    ram=Path(tempfile.mkdtemp(prefix='as02-atomic-request-elaboration-',dir='/dev/shm'))
    wrapper=run/'rocev2_atomic_request_integrity_transport.v';wrapper.write_text(bridge.derive())
    axis=ROOT/'external/corundum/fpga/lib/axis/rtl';eth=ROOT/'external/corundum/fpga/lib/eth/rtl'
    sources=[*sorted(raw.glob('*.v')),wrapper,ROOT/'rdma/rtl/rocev2_ipv4_icrc.v',ROOT/'rdma/rtl/rocev2_tx_padding.v',
        axis/'axis_adapter.v',axis/'axis_fifo.v',axis/'axis_register.v',eth/'lfsr.v']
    own=[a.build_report.resolve(),Path(__file__).resolve(),ROOT/'rdma/rtl/rocev2_integrity_transport.v',
        *[ROOT/'rdma/rnic/fpga'/n for n in ['derive_atomic_request_bridge.py','derive_atomic_native_bridge.py',
            'derive_immediate_bridge.py','derive_duplex_transport.py','derive_qp_tx_bridge.py']]]
    before={str(x.relative_to(ROOT)):digest(x)for x in [*sources,*raw.glob('*.dat'),*own]}
    report=dict(scope=__doc__,pass_test=False,source_sha256=before,directory=str(run.relative_to(ROOT)),
        compile_only=True,generated_HLS_actual=True,native_integrated=False,hardware_verified=False)
    try:
        top='rocev2_atomic_request_integrity_transport'
        command=['iverilog','-g2012','-s',top,'-P',top+'.REQUEST_CQ_ENABLE=1','-P',top+'.LEGACY_QP_KEY=0',
            '-P',top+'.RNR_ENABLE=1','-P',top+'.RECV_RETIRE_ENABLE=1','-o',str(ram/'bridge.vvp'),*map(str,sources)]
        report['command']=command;start=time.monotonic();c=subprocess.run(command,capture_output=True,text=True,timeout=180)
        report['compile_seconds']=time.monotonic()-start;(run/'compile.log').write_text(c.stdout+c.stderr)
        if c.returncode:raise RuntimeError('actual HLS/bridge elaboration: '+str(run/'compile.log'))
        text=(ram/'bridge.vvp').read_text()
        names=['state_table_0_U0','msn_table_0_U0','rx_ibh_fsm_0_U0','rx_exh_fsm_512_0_U0','atomic_commit_U']
        counts={n:len(re.findall(r'\.scope module, "'+n+r'"',text))for n in names}
        if any(x!=1 for x in counts.values()):raise ValueError(('missing or duplicated same domain',counts))
        top=len(re.findall(r'\.scope module, "transport" "rocev2_native_atomic_request_top"',text))
        if top!=1:raise ValueError('unexpected actual HLS top count')
        if before!={n:digest(ROOT/n)for n in before}:raise ValueError('inputs changed')
        report.update(pass_test=True,source_unchanged=True,actual_shared_instances=counts,actual_HLS_instances=top,
            RAM_artifact_sha256={str(ram/'bridge.vvp'):digest(ram/'bridge.vvp')})
    except Exception as e:report['error']=str(e);raise
    finally:
        report['artifact_sha256']={str(x.relative_to(ROOT)):digest(x)for x in run.iterdir()if x.is_file()}
        with a.report.open('x')as f:f.write(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k]for k in ['pass_test','compile_seconds','actual_shared_instances','directory']}))


if __name__=='__main__':main()
