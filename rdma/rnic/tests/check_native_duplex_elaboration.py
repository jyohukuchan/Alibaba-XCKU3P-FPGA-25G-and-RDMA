#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Elaborate actual duplex HLS inside the complete native main memory/MAC graph.

Compile only; not simulation, physical timing, kernel/provider or runtime proof.
The original legacy initiator remains, with exactly one shared native core/MR.
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
import test_native_rnic_rtl as main
import wrkey_delivery_sim as delivery

ROOT=main.ROOT
sys.path.insert(0,str(ROOT/'rdma/rnic/fpga'))
import derive_duplex_transport as duplex

def run(project,hls_report,report):
    if report.exists():raise ValueError('preserve evidence')
    if shutil.disk_usage(ROOT).free<256*1024*1024:raise RuntimeError('unchanged small elaboration guard')
    selected,manifest=delivery.verify_delivery(project)
    info=json.loads(hls_report.read_text())
    if not all(info.get(x)for x in ['pass_test','source_and_frozen_inputs_unchanged','native_rnr',
        'receive_retirement','request_retirement','duplex_memory_provenance']):raise ValueError('matched successful duplex synthesis required')
    if info['HLS_top']!='rocev2_native_duplex_top':raise ValueError('wrong selected top')
    for n,h in info['source_sha256'].items():
        if delivery.digest(ROOT/n)!=h:raise ValueError('HLS consumed source changed: '+n)
    raw=ROOT/info['directory']/'project/solution1/syn/verilog'
    for n,h in info['generated_sha256'].items():
        if delivery.digest(raw/n)!=h:raise ValueError('actual generated RTL changed: '+n)
    tb,_=main.bench(False)
    real,data=delivery.ORIGINAL_MODULES(project)
    sources=list(dict.fromkeys([*[x for x in main.original.input_paths(tb)if x.suffix=='.v'],
        *real,main.TOP,*main.EXTRA]))
    for old in [delivery.OLD_BRIDGE,duplex.ORIGINAL]:
        if sources.count(old)!=1:raise ValueError('ambiguous preserved source: '+str(old))
        sources.remove(old)
    sources += [raw/n for n in info['generated_sha256']if n.endswith('.v')]+duplex.EXTRA
    data += [raw/n for n in info['generated_sha256']if n.endswith('.dat')]
    consumed=sources+data+[manifest,hls_report,Path(__file__).resolve(),Path(main.__file__).resolve(),
        Path(main.derive.__file__).resolve(),Path(main.derive.recv.__file__).resolve(),main.derive.ORIGINAL,
        duplex.ORIGINAL,Path(duplex.__file__).resolve(),Path(duplex.bridge.__file__).resolve(),
        Path(duplex.bridge.legacy.__file__).resolve(),duplex.bridge.legacy.BRIDGE]
    before={str(x.relative_to(ROOT)):delivery.digest(x)for x in consumed}
    directory=Path(tempfile.mkdtemp(prefix='native-duplex-elaboration-',dir=ROOT/'rdma/rnic/build'))
    generated=directory/'responder.v';generated.write_text(main.derive.derive(main.derive.ORIGINAL.read_text()))
    shared=directory/'shared.v';shared.write_text(duplex.derive())
    bridge=directory/'bridge.v';bridge.write_text(duplex.derive_bridge())
    generated_hashes={str(x.relative_to(ROOT)):delivery.digest(x)for x in [generated,shared,bridge]}
    before.update(generated_hashes)
    command=['iverilog','-g2012','-s','rocev2_native_rnic_endpoint','-o',str(directory/'main.vvp')]
    for feature in ['DUPLEX','QP_TX','RETRY','SEND','RECV','RNR','RECV_RETIRE','RECV_CQ','REQUEST_CQ','SEPARATE_RQ','RECV_CANCEL']:
        command+=['-Procev2_native_rnic_endpoint.'+feature+'_ENABLE=1']
    command+=list(map(str,[generated,shared,bridge,*sources]))
    result=dict(scope=__doc__,pass_test=False,source_sha256=before,output_directory=str(directory.relative_to(ROOT)),
        command=command,hardware_verified=False,simulation_run=False,full_board_selected_or_built=False,
        duplex_routing_selected=True,original_HLS_sha256=selected['original_generated_HLS_sha256'])
    try:
        start=time.monotonic();c=subprocess.run(command,capture_output=True,text=True,timeout=60)
        result.update(compile_seconds=time.monotonic()-start,compiler_exit_code=c.returncode)
        (directory/'compile.log').write_text(c.stdout+c.stderr)
        if c.returncode:raise RuntimeError('actual duplex hierarchy failed: '+str(directory/'compile.log'))
        compiled=(directory/'main.vvp').read_text()
        wanted={n:1 for n in ['rocev2_top','rocev2_native_duplex_top','rocev2_shared_hls_transport',
            'rocev2_shared_protected_responder','rocev2_native_rnic_endpoint','rocev2_native_sq_endpoint',
            'rocev2_mr_table','rocev2_mr_page_table','rocev2_duplex_rx_mux','rocev2_duplex_tx_router',
            'rocev2_receive_queue','rocev2_receive_ack_tx','rocev2_wqe_memory_executor','rocev2_wqe_response_guard',
            'rocev2_wqe_tx_lifetime','rocev2_cq_mmio','rocev2_qptx_integrity_transport','rocev2_wqe_replay','rocev2_retry_mmio']}
        wanted['rocev2_memory_origin_router']=2;wanted['rocev2_sq_control_regs']=2
        counts={n:len(re.findall(r'\.scope module, "[^\"]+" "'+n+r'"',compiled))for n in wanted}
        if counts!=wanted:raise ValueError('native core/MR/routing multiplicity mismatch '+str(counts))
        for n,h in before.items():
            if delivery.digest(ROOT/n)!=h:raise ValueError('consumed source changed: '+n)
        result.update(pass_test=True,source_unchanged=True,module_counts=counts,HLS_stub=False,
            actual_generated_HLS_elaborated=True,generated_new_QP_HLS_verified=True,
            legacy_HLS_cores=1,shared_requester_responder_HLS_cores=1,third_HLS_core_added=False,
            native_replay_raw_HLS_sha256=info['generated_sha256'])
        for feature in ['DUPLEX','QP_TX','RETRY','SEND','RECV','RNR','RECV_RETIRE','RECV_CQ','REQUEST_CQ','SEPARATE_RQ','RECV_CANCEL']:
            result[feature+'_ENABLE']=1
    except Exception as e:result.update(error_type=type(e).__name__,error=str(e));raise
    finally:
        with report.open('x')as f:f.write(json.dumps(result,indent=2)+'\n')
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--hls-build',type=Path,required=True)
    p.add_argument('--native-hls-report',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    result=run(a.hls_build.resolve(),a.native_hls_report.resolve(),a.report.resolve())
    print(json.dumps({n:result[n]for n in ['pass_test','compile_seconds','module_counts','output_directory']}))
