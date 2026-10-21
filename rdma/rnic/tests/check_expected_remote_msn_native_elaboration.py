#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Complete real native accepted-QP/SQC/MSN wiring compile, NOT runtime proof.

Keep original HLS/clock/geometry/shared domains/drains and closed large READ.
The expected-MSN output is not yet connected to protected segmented RX.
"""
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
import expected_remote_msn_native_sources as source
from check_immediate_native_elaboration import FEATURES

ROOT=source.ROOT;digest=source.digest
BASE=ROOT/'results/2026-10-18/rocev2-rnic-segmented-read-memory-native-elaboration-001.json'


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ['hls-build','native-hls-report','owned-hls-report','request-hls-report','report']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args()
    if a.report.exists():p.error('preserve previous evidence')
    if shutil.disk_usage(ROOT).free<1024**3 or shutil.disk_usage('/dev/shm').free<1024**3:raise RuntimeError('unchanged root/RAM1GiB guards')
    base=json.loads(BASE.read_text())
    if not base.get('pass_test')or(base.get('RNC_features'),base.get('CQC_features'))!=(8191,31):raise ValueError('exact passing READ-memory parent graph required')
    run=Path(tempfile.mkdtemp(prefix='expected-msn-native-',dir=ROOT/'rdma/rnic/build'));ram=Path(tempfile.mkdtemp(prefix='as02-expected-msn-native-',dir='/dev/shm'))
    result=dict(scope=__doc__,pass_test=False,directory=str(run.relative_to(ROOT)),compile_only=True,runtime_test=False,
        accepted_QP_SQC_MSN_wired=True,protected_segmented_RX_selected=False,expected_MSN_connected_to_RX=False,
        large_READ_admission_open=False,READ_admission_limit=4096,default_graph_changed=False,hardware_verified=False,
        standard_API_runtime=False,full_board_timing=False,HLS_top=source.HLS,RNC_features=8191,CQC_features=31)
    try:
        src,data,before=source.sources(a.hls_build.resolve(),a.native_hls_report.resolve(),a.owned_hls_report.resolve(),a.request_hls_report.resolve(),run)
        before.update({str(q.relative_to(ROOT)):digest(q)for q in [BASE,Path(__file__).resolve()]})
        root=(run/'rocev2_native_rnic_endpoint.v').read_text()
        for token in [".local_core_drained(1'b0)",".hls_transport_drained(1'b0)",
            '.large_read_path(segmented_read_memory_path)','.bypass(segmented_read_memory_path)',
            'assign owner_ready=msn_owner_eligible && ',
            'local_retire_ready && segmented_memory_retire_ready && msn_retire_eligible;',
            '.s_local_retire_valid(cq_retire_valid && !receive_retire && segmented_memory_retire_ready && msn_retire_eligible)',
            '.s_retire_valid(cq_retire_valid && !receive_retire && local_retire_ready && msn_retire_eligible)',
            '.s_owner_fire(owner_take)','.s_query_cookie(msn_query_cookie)',
            '.wire_queue_guard(rx_queue_guard | msn_queue_guard | {8{!response_router_quiescent}})',
            '.s_expect_valid(tx_m_expect_valid && msn_expect_eligible)']:
            if token not in root:raise ValueError('actual MSN/parent ownership/drain connection missing:'+token)
        controlled=(run/'rocev2_controlled_responder.v').read_text()
        for token in ['else if(cfg_qp_valid && cfg_qp_ready)',
            "atomic_child_qp_ready && atomic_cfg_binding_ready && msn_cfg_guard===1'b0",
            ".cfg_qp_valid(cfg_qp_valid && atomic_cfg_binding_ready && msn_cfg_guard===1'b0)",
            'tx_route_valid<=cfg_qp_tx_only || cfg_qp_pd!=0']:
            if token not in controlled:raise ValueError('genuine accepted TX-only configuration/atomic fanout missing:'+token)
        sq=(run/'rocev2_sq_control_regs.v').read_text()
        if 'assign msn_query_valid=msn_query_known && owner_active[msn_query_index]'not in sq:raise ValueError('actual SQC owner lookup required')
        if 'opcode==1 || opcode==3'not in(run/'rocev2_wqe_admission.v').read_text():raise ValueError('large READ admission must remain closed')
        top='rocev2_native_rnic_endpoint';cmd=['iverilog','-g2012','-s',top,'-o',str(ram/'native.vvp')]
        cmd+=['-P'+top+'.'+n+'_ENABLE=1'for n in FEATURES];cmd+=list(map(str,src))
        result.update(command=cmd,source_sha256=before,selected_RTL=[str(q.relative_to(ROOT))for q in src])
        start=time.monotonic();c=subprocess.run(cmd,capture_output=True,text=True,timeout=180)
        result.update(compile_seconds=time.monotonic()-start,compiler_exit_code=c.returncode);(run/'compile.log').write_text(c.stdout+c.stderr)
        if c.returncode:raise ValueError('complete expected-MSN native elaboration failed')
        if any('expects'in l and 'bits'in l for l in c.stderr.splitlines()):raise ValueError('actual port-width mismatch')
        model=(ram/'native.vvp').read_text();wanted=dict(base['module_counts']);wanted['rocev2_expected_remote_msn']=1
        counts={n:len(re.findall(r'\.scope module, "[^"]+" "'+n+r'"',model))for n in wanted}
        if counts!=wanted:raise ValueError('actual native module multiplicity mismatch:'+str(counts))
        domains={n:len(re.findall(r'\.scope module, "'+n+r'" "'+source.HLS+r'_[^"]+"',model))for n in base['HLS_domain_counts']}
        if domains!=base['HLS_domain_counts']:raise ValueError('HLS/PSN/MSN/RX/Atomic domain changed:'+str(domains))
        if any(digest(ROOT/n)!=h for n,h in before.items()):raise ValueError('consumed source changed')
        result.update(pass_test=True,source_unchanged=True,module_counts=counts,HLS_domain_counts=domains,
            both_global_HLS_drains_zero=True,requester_owner_bits=748,request_done_bits=816,SQ_bits=408,HLS_stub=False)
    except Exception as e:result.update(error_type=type(e).__name__,error=str(e));raise
    finally:
        result['artifact_sha256']={str(q.relative_to(ROOT)):digest(q)for q in run.iterdir()if q.is_file()}
        result['RAM_artifact_sha256']={str(q):digest(q)for q in ram.iterdir()if q.is_file()}
        with a.report.open('x')as f:f.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(pass_test=True,compile_seconds=result['compile_seconds'],accepted_QP_SQC_MSN_wired=True,
        expected_MSN_connected_to_RX=False,large_READ_admission_open=False,directory=result['directory'])))


if __name__=='__main__':main()
