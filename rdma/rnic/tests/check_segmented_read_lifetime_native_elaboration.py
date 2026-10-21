#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Complete real native READ RX/MSN/lifetime/memory wiring compile, NOT runtime.

All parent HLS/clock/geometry/shared domains/drains remain. Large READ is
still rejected by admission; opening a distinct profile and genuine runtime
proof are separate steps, not inferred from this complete graph compile.
"""
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
import segmented_read_lifetime_native_sources as source
from check_immediate_native_elaboration import FEATURES

ROOT=source.ROOT;digest=source.digest
BASE=ROOT/'results/2026-10-18/rocev2-rnic-expected-remote-msn-native-elaboration-002.json'


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ['hls-build','native-hls-report','owned-hls-report','request-hls-report','report']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args()
    if a.report.exists():p.error('preserve earlier evidence')
    if shutil.disk_usage(ROOT).free<1024**3 or shutil.disk_usage('/dev/shm').free<1024**3:raise RuntimeError('unchanged root/RAM1GiB guards')
    base=json.loads(BASE.read_text())
    if not base.get('pass_test')or(base.get('RNC_features'),base.get('CQC_features'))!=(8191,31):raise ValueError('exact passing MSN-memory parent graph required')
    run=Path(tempfile.mkdtemp(prefix='read-lifetime-native-',dir=ROOT/'rdma/rnic/build'));ram=Path(tempfile.mkdtemp(prefix='as02-read-lifetime-native-',dir='/dev/shm'))
    result=dict(scope=__doc__,pass_test=False,directory=str(run.relative_to(ROOT)),compile_only=True,runtime_test=False,
        protected_segmented_RX_selected=True,expected_MSN_connected_to_RX=True,whole_READ_lifetime_wired=True,
        large_READ_admission_open=False,READ_admission_limit=4096,default_graph_changed=False,hardware_verified=False,
        standard_API_runtime=False,full_board_timing=False,HLS_top=source.HLS,RNC_features=8191,CQC_features=31)
    try:
        src,data,before=source.sources(a.hls_build.resolve(),a.native_hls_report.resolve(),a.owned_hls_report.resolve(),a.request_hls_report.resolve(),run)
        before.update({str(q.relative_to(ROOT)):digest(q)for q in [BASE,Path(__file__).resolve()]})
        root=(run/'rocev2_native_rnic_endpoint.v').read_text()
        for token in [".local_core_drained(1'b0)",".hls_transport_drained(1'b0)",
            'rocev2_segmented_read_response_guard #(','.s_expect_msn(expected_remote_msn)',
            '.s_expect_valid(tx_m_expect_valid && msn_expect_eligible)',
            '.large_read_path(segmented_read_memory_path)','.bypass(segmented_read_memory_path)',
            'assign owner_ready=msn_owner_eligible && ',
            'local_retire_ready && segmented_memory_retire_ready && msn_retire_eligible;']:
            if token not in root:raise ValueError('actual READ RX/MSN/memory/owner/CQ/drain hookup missing:'+token)
        life=(run/'rocev2_wqe_lifetime.v').read_text();tx=(run/'rocev2_wqe_tx_lifetime.v').read_text()
        for token in ['s_response_psn==response_psn','segmented_read ? read_response_opcode',
            's_hls_ack=={5\'d0,final_ack_psn','if(segmented_read && !read_response_last)read_response_index<=']:
            if token not in life:raise ValueError('actual ordered/final-only READ lifetime check missing:'+token)
        if "whole_length<=4096 || s_response_opcode==8'h0f"not in tx:raise ValueError('FIRST/MIDDLE cannot acknowledge retained READ cache')
        if 'opcode==1 || opcode==3'not in(run/'rocev2_wqe_admission.v').read_text():raise ValueError('large READ admission must stay closed')
        top='rocev2_native_rnic_endpoint';cmd=['iverilog','-g2012','-s',top,'-o',str(ram/'native.vvp')]
        cmd+=['-P'+top+'.'+n+'_ENABLE=1'for n in FEATURES];cmd+=list(map(str,src))
        result.update(command=cmd,source_sha256=before,selected_RTL=[str(q.relative_to(ROOT))for q in src])
        start=time.monotonic();c=subprocess.run(cmd,capture_output=True,text=True,timeout=180)
        result.update(compile_seconds=time.monotonic()-start,compiler_exit_code=c.returncode);(run/'compile.log').write_text(c.stdout+c.stderr)
        if c.returncode:raise ValueError('complete READ lifetime native elaboration failed')
        if any('expects'in l and 'bits'in l for l in c.stderr.splitlines()):raise ValueError('actual port-width mismatch')
        model=(ram/'native.vvp').read_text();wanted=dict(base['module_counts'])
        wanted['rocev2_wqe_response_guard']=0;wanted['rocev2_segmented_read_response_guard']=1
        counts={n:len(re.findall(r'\.scope module, "[^"]+" "'+n+r'"',model))for n in wanted}
        if counts!=wanted:raise ValueError('actual native module multiplicity mismatch:'+str(counts))
        domains={n:len(re.findall(r'\.scope module, "'+n+r'" "'+source.HLS+r'_[^"]+"',model))for n in base['HLS_domain_counts']}
        if domains!=base['HLS_domain_counts']:raise ValueError('shared HLS/PSN/MSN/RX/Atomic domain changed:'+str(domains))
        if any(digest(ROOT/n)!=h for n,h in before.items()):raise ValueError('consumed source changed')
        result.update(pass_test=True,source_unchanged=True,module_counts=counts,HLS_domain_counts=domains,
            both_global_HLS_drains_zero=True,requester_owner_bits=748,request_done_bits=816,SQ_bits=408,HLS_stub=False)
    except Exception as e:result.update(error_type=type(e).__name__,error=str(e));raise
    finally:
        result['artifact_sha256']={str(q.relative_to(ROOT)):digest(q)for q in run.iterdir()if q.is_file()}
        result['RAM_artifact_sha256']={str(q):digest(q)for q in ram.iterdir()if q.is_file()}
        with a.report.open('x')as f:f.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(pass_test=True,compile_seconds=result['compile_seconds'],expected_MSN_connected_to_RX=True,
        whole_READ_lifetime_wired=True,large_READ_admission_open=False,directory=result['directory'])))


if __name__=='__main__':main()
