#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Coordinated segmented-wire/HLS/MR/PTE/DMA/MAC/CQ graph: COMPILE ONLY.

Large WRITE/SEND admission and packet-owner/cache advance are selected;
actual HLS/native large runtime, kernel/provider/physical and board timing
remain unproven. Same original clocks/geometry and both global drains0.
"""
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
import segmented_wire_native_sources as source
from check_immediate_native_elaboration import FEATURES

ROOT=source.ROOT;digest=source.digest
BASE=ROOT/'results/2026-10-18/rocev2-rnic-segmented-executor-native-elaboration-002.json'
RUNTIME=ROOT/'results/2026-10-18/rocev2-rnic-segmented-executor-native-full-001.json'


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ['hls-build','native-hls-report','owned-hls-report','request-hls-report','report']:
        p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args()
    if a.report.exists():p.error('preserve prior evidence')
    if shutil.disk_usage(ROOT).free<1024**3 or shutil.disk_usage('/dev/shm').free<1024**3:
        raise RuntimeError('unchanged native/root and RAM1GiB guards')
    baseline=json.loads(BASE.read_text());runtime=json.loads(RUNTIME.read_text())
    if not baseline['pass_test']or not runtime['pass_test']or len(runtime['tests'])!=27:
        raise ValueError('qualified prior27-case retained-source graph required')
    run=Path(tempfile.mkdtemp(prefix='segmented-wire-native-elaboration-',dir=ROOT/'rdma/rnic/build'))
    ram=Path(tempfile.mkdtemp(prefix='as02-segmented-wire-elaboration-',dir='/dev/shm'))
    report=dict(scope=__doc__,pass_test=False,directory=str(run.relative_to(ROOT)),compile_only=True,
        runtime_test=False,hardware_verified=False,standard_API_runtime=False,full_board_timing=False,
        actual_generated_HLS=True,HLS_top='rocev2_native_segmented_request_top',
        large_native_admission=True,large_source_DMA_wired=True,atomic_CQ_retirement_fanout=True,
        per_packet_lifetime_and_cache_advance_wired=True,large_native_wire_CQ_runtime=False,default_graph_changed=False)
    try:
        src,data,before=source.sources(a.hls_build.resolve(),a.native_hls_report.resolve(),
            a.owned_hls_report.resolve(),a.request_hls_report.resolve(),run)
        before.update({str(f.relative_to(ROOT)):digest(f)for f in [BASE,RUNTIME,Path(__file__).resolve()]})
        root=run/'rocev2_native_rnic_endpoint.v';prior_root=ROOT/runtime['directory']/root.name
        if digest(root)!=digest(prior_root):raise ValueError('qualified full748 source/CQ/root fanout changed')
        for n in ['rocev2_wqe_admission','rocev2_wqe_hls_sq','rocev2_shared_hls_transport',
                  'rocev2_wqe_lifetime','rocev2_wqe_mac_tx','rocev2_wqe_response_guard','rocev2_cq_mmio']:
            if '1048576'not in (run/(n+'.v')).read_text():raise ValueError('coordinated whole-owner range gate missing:'+n)
        tx=(run/'rocev2_wqe_tx_lifetime.v').read_text()
        for token in ['.m_packet_advance_context(packet_advance_context)',
                      '.s_packet_advance_context(packet_advance_context)',
                      '.packet_drained(local_tx_drained)',
                      '.packet_parent_fault(outer_fault || packet_fault_pending)',
                      's_request_done_data[795:772]==(whole_first_psn+whole_packet_span)']:
            if token not in tx:raise ValueError('actual packet ownership/full-PSN join not connected:'+token)
        text=root.read_text()
        if ".local_core_drained(1'b0)"not in text or ".hls_transport_drained(1'b0)"not in text:
            raise ValueError('original global drains changed')
        top='rocev2_native_rnic_endpoint';command=['iverilog','-g2012','-s',top,'-o',str(ram/'native.vvp')]
        command+=['-P'+top+'.'+f+'_ENABLE=1'for f in FEATURES];command+=list(map(str,src))
        report.update(command=command,source_sha256=before,selected_RTL=[str(f.relative_to(ROOT))for f in src])
        start=time.monotonic();c=subprocess.run(command,capture_output=True,text=True,timeout=180)
        (run/'compile.log').write_text(c.stdout+c.stderr);report.update(compile_seconds=time.monotonic()-start,compiler_exit_code=c.returncode)
        if c.returncode:raise ValueError('complete segmented-wire native elaboration failed:'+str(run/'compile.log'))
        mismatch=[l for l in c.stderr.splitlines()if 'expects'in l and 'bits'in l];report['port_width_warnings']=mismatch
        if mismatch:raise ValueError('actual native port-width mismatch:'+str(mismatch))
        model=(ram/'native.vvp').read_text();wanted=baseline['module_counts']
        counts={n:len(re.findall(r'\.scope module, "[^"]+" "'+n+r'"',model))for n in wanted}
        if counts!=wanted:raise ValueError('one exact native/MR/PTE/HLS/PSN/MAC/nonce/source graph required:'+str(counts))
        for n,h in before.items():
            if digest(ROOT/n)!=h:raise ValueError('consumed input changed:'+n)
        report.update(pass_test=True,source_unchanged=True,module_counts=counts,both_global_HLS_drains_zero=True,
            requester_owner_bits=748,SQ_bits=408,request_done_bits=816)
    except Exception as e:report.update(error_type=type(e).__name__,error=str(e));raise
    finally:
        report['artifact_sha256']={str(f.relative_to(ROOT)):digest(f)for f in run.iterdir()if f.is_file()}
        report['RAM_artifact_sha256']={str(f):digest(f)for f in ram.iterdir()if f.is_file()}
        with a.report.open('x')as f:f.write(json.dumps(report,indent=2)+'\n')
    print(json.dumps({n:report[n]for n in ['pass_test','compile_seconds','directory','runtime_test']}))


if __name__=='__main__':main()
