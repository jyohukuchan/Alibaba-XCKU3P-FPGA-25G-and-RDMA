#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual complete zero-RQ/requester/Atomic graph, compile-only, NOT runtime.

One native HLS/PSN/MSN/MR/PTE/fetch domain with full owner/SQ/CQ ABIs and
both original global drains tied LOW. Incoming normal zero WRITE/READ/provider integration,
Linux/physical operation and original board timing remain unqualified.
"""
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
import zero_rq_native_sources as source
from check_immediate_native_elaboration import FEATURES

ROOT=source.ROOT;digest=source.digest;HLS='rocev2_native_zero_rq_top'


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ['hls-build','native-hls-report','owned-hls-report','request-hls-report','report']:
        p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args()
    if a.report.exists():p.error('preserve prior evidence')
    if shutil.disk_usage(ROOT).free<1024**3:raise RuntimeError('unchanged native1GiB free-space guard')
    if shutil.disk_usage('/dev/shm').free<1024**3:raise RuntimeError('RAM artifact1GiB guard')
    run=Path(tempfile.mkdtemp(prefix='zero-rq-native-elaboration-',dir=ROOT/'rdma/rnic/build'))
    ram=Path(tempfile.mkdtemp(prefix='as02-zero-native-elaboration-',dir='/dev/shm'))
    report=dict(scope=__doc__,pass_test=False,directory=str(run.relative_to(ROOT)),
        compile_only=True,runtime_test=False,actual_generated_HLS=True,HLS_top=HLS,
        hardware_verified=False,standard_API_runtime=False,full_board_timing=False,default_graph_changed=False,
        incoming_zero_RQ_source_candidate=True,runtime_tested=False,provider4095_implemented=False)
    try:
        src,data,before=source.sources(a.hls_build.resolve(),a.native_hls_report.resolve(),
            a.owned_hls_report.resolve(),a.request_hls_report.resolve(),run)
        before[str(Path(__file__).resolve().relative_to(ROOT))]=digest(Path(__file__).resolve())
        top='rocev2_native_rnic_endpoint'
        command=['iverilog','-g2012','-s',top,'-o',str(ram/'native.vvp')]
        command+=['-P'+top+'.'+f+'_ENABLE=1'for f in FEATURES]
        command+=list(map(str,src));report.update(command=command,source_sha256=before,
            selected_RTL=[str(p.relative_to(ROOT))for p in src])
        start=time.monotonic();c=subprocess.run(command,capture_output=True,text=True,timeout=180)
        report.update(compile_seconds=time.monotonic()-start,compiler_exit_code=c.returncode)
        (run/'compile.log').write_text(c.stdout+c.stderr)
        if c.returncode:raise ValueError('complete zero native elaboration failed: '+str(run/'compile.log'))
        mismatches=[l for l in c.stderr.splitlines()if 'expects'in l and 'bits'in l]
        report['port_width_warnings']=mismatches
        if mismatches:raise ValueError('actual native port widths must match: '+repr(mismatches))
        text=(ram/'native.vvp').read_text()
        wanted={n:1 for n in ['rocev2_top',HLS,
            'rocev2_native_rnic_endpoint','rocev2_native_sq_endpoint','rocev2_mr_table','rocev2_mr_page_table',
            'rocev2_shared_hls_transport','rocev2_shared_protected_responder','rocev2_atomic_request_integrity_transport',
            'rocev2_wqe_memory_executor','rocev2_wqe_response_guard','rocev2_wqe_tx_lifetime','rocev2_wqe_replay',
            'rocev2_receive_queue','rocev2_receive_ack_tx','rocev2_cq_mmio','rocev2_duplex_rx_mux','rocev2_duplex_tx_router']}
        wanted.update(rocev2_memory_origin_router=2,rocev2_sq_control_regs=2,
            rocev2_sq_dma_fetch=1,rocev2_sq_fetch=1,rocev2_queue_cfg_arbiter=1,rocev2_wqe_admission=2,
            rocev2_native_atomic_request_top=0,rocev2_native_zero_request_top=0,rocev2_zero_ipv4_icrc=3,
            rocev2_zero_rx_padding=1)
        counts={n:len(re.findall(r'\.scope module, "[^"]+" "'+n+r'"',text))for n in wanted}
        if counts!=wanted:raise ValueError('incorrect actual graph multiplicity: '+repr(counts))
        hls_counts={n:len(re.findall(r'\.scope module, "'+n+r'" "'+HLS+r'_[^"]+"',text))for n in
            ['state_table_0_U0','msn_table_0_U0','rx_ibh_fsm_0_U0','rx_exh_fsm_512_0_U0','atomic_commit_U']}
        if any(v!=1 for v in hls_counts.values()):raise ValueError('shared PSN/MSN/RX domain duplicated or absent')
        main=(run/'rocev2_native_rnic_endpoint.v').read_text()
        if ".local_core_drained(1'b0)"not in main or ".hls_transport_drained(1'b0)"not in main:
            raise ValueError('original global drains changed')
        for n,h in before.items():
            if digest(ROOT/n)!=h:raise ValueError('consumed source changed: '+n)
        report.update(pass_test=True,source_unchanged=True,module_counts=counts,HLS_domain_counts=hls_counts,
            requester_owner_bits=748,SQ_bits=408,request_done_bits=816,receive_owner_bits=620,
            receive_done_bits=752,both_global_HLS_drains_zero=True,HLS_stub=False)
    except Exception as e:report.update(error_type=type(e).__name__,error=str(e));raise
    finally:
        report['artifact_sha256']={str(p.relative_to(ROOT)):digest(p)for p in run.iterdir()if p.is_file()}
        report['RAM_artifact_sha256']={str(p):digest(p)for p in ram.iterdir()if p.is_file()}
        with a.report.open('x')as f:f.write(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k]for k in ['pass_test','compile_seconds','module_counts','directory']}))


if __name__=='__main__':main()
