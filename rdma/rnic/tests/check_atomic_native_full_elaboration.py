#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Elaborate ONE complete normal+Atomic native graph, actual generated HLS.

No runtime/physical/timing claim. Large derived netlist lives in task-owned
RAM, not the nearly full root filesystem. Source/records stay in repository.
"""
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
import atomic_native_full_sources as source

ROOT=source.ROOT;digest=source.digest


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--hls-build',type=Path,required=True)
    p.add_argument('--native-hls-report',type=Path,required=True);p.add_argument('--owned-hls-report',type=Path,required=True)
    p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve prior evidence')
    if shutil.disk_usage(ROOT).free<256*1024**2:raise RuntimeError('unchanged elaboration256MiB guard')
    if shutil.disk_usage('/dev/shm').free<1024**3:raise RuntimeError('RAM1GiB headroom required')
    run=Path(tempfile.mkdtemp(prefix='atomic-native-full-elaboration-',dir=ROOT/'rdma/rnic/build'))
    ram=Path(tempfile.mkdtemp(prefix='as02-atomic-native-artifacts-',dir='/dev/shm'))
    report=dict(scope=__doc__,pass_test=False,directory=str(run.relative_to(ROOT)),RAM_artifact_directory=str(ram),
        actual_generated_HLS=True,Atomic_native_graph_selected=True,runtime_test=False,hardware_verified=False,
        standard_API_runtime=False,full_board_timing=False)
    try:
        src,_,before=source.sources(a.hls_build.resolve(),a.native_hls_report.resolve(),a.owned_hls_report.resolve(),run)
        before[str(Path(__file__).resolve().relative_to(ROOT))]=digest(Path(__file__).resolve())
        report['source_sha256']=before
        features=['DUPLEX','QP_TX','RETRY','SEND','RECV','RNR','RECV_RETIRE','RECV_CQ','REQUEST_CQ','SEPARATE_RQ','RECV_CANCEL']
        command=['iverilog','-g2012','-s','rocev2_native_rnic_endpoint','-o',str(ram/'native.vvp')]
        command+=['-Procev2_native_rnic_endpoint.'+f+'_ENABLE=1'for f in features]
        command+=list(map(str,src));report['command']=command
        start=time.monotonic();r=subprocess.run(command,capture_output=True,text=True,timeout=60)
        (run/'compile.log').write_text(r.stdout+r.stderr)
        report.update(seconds=time.monotonic()-start,compiler_exit=r.returncode)
        if r.returncode:raise RuntimeError('complete Atomic native graph compile: '+str(run/'compile.log'))
        for line in r.stderr.splitlines():
            if 'expects' in line and any(k in line for k in ['atomic','context','owner','sq_tdata','core','done','mac_data']):
                raise ValueError('typed native port mismatch: '+line)
        netlist=(ram/'native.vvp').read_text()
        wanted={n:1 for n in ['rocev2_native_rnic_endpoint','rocev2_shared_protected_responder',
            'rocev2_native_atomic_owned_top','rocev2_atomic_native_integrity_transport','rocev2_atomic_qp_binding',
            'rocev2_native_rx_refs','rocev2_native_atomic_rx_router','rocev2_atomic_packet_guard',
            'rocev2_atomic_owned_service_adapter','rocev2_atomic_responder','rocev2_atomic_memory_bridge',
            'rocev2_atomic_owner_reservation','rocev2_atomic_mac_tx','rocev2_mr_table','rocev2_mr_page_table',
            'rocev2_top','rocev2_duplex_rx_mux','rocev2_duplex_tx_router']}
        wanted.update(rocev2_sq_control_regs=2,rocev2_mr_query_arbiter=3,rocev2_memory_client_arbiter=2,
            rocev2_memory_origin_router=2)
        counts={n:len(re.findall(r'\.scope module, "[^"]+" "'+n+r'"',netlist))for n in wanted}
        report['module_counts']=counts
        if counts!=wanted:raise ValueError('missing/duplicated actual native authority/core/domain '+str(counts))
        for n,h in before.items():
            if digest(ROOT/n)!=h:raise ValueError('source changed during elaboration: '+n)
        report.update(pass_test=True,source_unchanged=True,both_global_drains_zero=True)
    except Exception as e:report['error']=str(e);raise
    finally:
        report['artifact_sha256']={str(p.relative_to(ROOT)):digest(p)for p in run.iterdir()if p.is_file()}
        report['RAM_artifact_sha256']={str(p):digest(p)for p in ram.iterdir()if p.is_file()}
        with a.report.open('x')as f:f.write(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(pass_test=True,seconds=report['seconds'],directory=str(run),module_counts=counts)),flush=True)


if __name__=='__main__':main()
