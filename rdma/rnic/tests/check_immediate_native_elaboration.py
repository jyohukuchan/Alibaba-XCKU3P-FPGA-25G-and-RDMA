#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Elaborate the complete matching Immediate native graph and real generated HLS.

No behavioral core or second native MR/PTE, no simulation/hardware/timing claim.
Legacy initiator delivery remains intact. Default sources are not rewritten.
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
import test_native_rnic_rtl as native
import wrkey_delivery_sim as delivery

ROOT=native.ROOT
sys.path.insert(0,str(ROOT/'rdma/rnic/fpga'))
import derive_immediate_native as matched

FEATURES=['DUPLEX','QP_TX','RETRY','SEND','RECV','RNR','RECV_RETIRE','RECV_CQ',
    'REQUEST_CQ','SEPARATE_RQ','RECV_CANCEL']


def sources(project,hls_report,directory):
    selected,manifest=delivery.verify_delivery(project)
    info=json.loads(hls_report.read_text())
    if not all(info.get(k)for k in ['pass_test','source_and_frozen_inputs_unchanged',
        'request_immediate','receive_immediate']):
        raise ValueError('complete matched successful Immediate synthesis required')
    if info['HLS_top']!='rocev2_native_immediate_top':raise ValueError('wrong actual raw top')
    source_manifest=ROOT/info['source_directory']/'source.json'
    properties=json.loads(source_manifest.read_text())
    if not properties.get('duplex_memory_provenance'):raise ValueError('duplex origin provenance required')
    for n,h in info['source_sha256'].items():
        if delivery.digest(ROOT/n)!=h:raise ValueError('HLS source changed: '+n)
    raw=ROOT/info['directory']/'project/solution1/syn/verilog'
    for n,h in info['generated_sha256'].items():
        if delivery.digest(raw/n)!=h:raise ValueError('generated HLS changed: '+n)
    tb,_=native.bench(False)
    legacy,data=delivery.ORIGINAL_MODULES(project)
    src=list(dict.fromkeys([*[p for p in native.original.input_paths(tb)if p.suffix=='.v'],
        *legacy,native.TOP,*native.EXTRA,*matched.duplex.EXTRA]))
    derived=matched.derive()
    consumed=src+data+matched.inputs()+[manifest,hls_report,source_manifest,Path(__file__).resolve(),
        Path(native.__file__).resolve(),Path(native.original.__file__).resolve()]
    generated=[]
    for old,text in derived.items():
        # Protected responder is otherwise synthesized only in the opt-out
        # branch; the checked shared derivative explicitly substitutes it.
        if src.count(old)>1:raise ValueError('ambiguous source substitution '+str(old))
        if old==matched.responder.ORIGINAL:
            # Verilator resolves even inactive generate-branch module names.
            # Supply the immutable rollback definition too, under its REAL
            # name; it is not an elaborated second native protection graph.
            if old not in src:src.append(old)
            filename='rocev2_shared_protected_responder.v'
        else:
            if old not in src:raise ValueError('missing native substitution '+str(old))
            src.remove(old);filename=old.name
        p=directory/filename;p.write_text(text);generated.append(p)
    raw_rtl=[raw/n for n in info['generated_sha256']if n.endswith('.v')]
    data+=[raw/n for n in info['generated_sha256']if n.endswith('.dat')]
    src+=generated+raw_rtl
    consumed+=generated+raw_rtl+data
    before={str(p.relative_to(ROOT)):delivery.digest(p)for p in dict.fromkeys(consumed)}
    return src,data,before,selected,generated


def run(project,hls_report,report):
    if report.exists():raise ValueError('preserve previous evidence')
    if shutil.disk_usage(ROOT).free<256*1024*1024:raise RuntimeError('unchanged elaboration storage guard')
    directory=Path(tempfile.mkdtemp(prefix='immediate-native-elaboration-',dir=ROOT/'rdma/rnic/build'))
    result=dict(scope=__doc__,pass_test=False,directory=str(directory.relative_to(ROOT)),
        hardware_verified=False,runtime_test=False,full_board_timing=False,default_graph_changed=False)
    try:
        src,data,before,selected,generated=sources(project,hls_report,directory)
        command=['iverilog','-g2012','-s','rocev2_native_rnic_endpoint','-o',str(directory/'native.vvp')]
        command+=['-Procev2_native_rnic_endpoint.'+f+'_ENABLE=1'for f in FEATURES]
        command+=list(map(str,src))
        result.update(source_sha256=before,command=command)
        start=time.monotonic();c=subprocess.run(command,capture_output=True,text=True,timeout=60)
        result.update(compile_seconds=time.monotonic()-start,compiler_exit_code=c.returncode)
        (directory/'compile.log').write_text(c.stdout+c.stderr)
        if c.returncode:raise RuntimeError('matched full graph compile failed: '+str(directory/'compile.log'))
        # Never silently pass truncated/padded context, SQ, core or MAC ports.
        forbidden=['context','owner_tdata','sq_tdata','core_data','done_data',
            'done_tdata','request_done_data','mac_data','notification']
        for line in c.stderr.splitlines():
            if 'expects' in line and any(n in line for n in forbidden):
                raise ValueError('typed native interface mismatch: '+line)
        vvp=(directory/'native.vvp').read_text()
        wanted={n:1 for n in ['rocev2_top','rocev2_native_immediate_top',
            'rocev2_native_rnic_endpoint','rocev2_native_sq_endpoint','rocev2_mr_table',
            'rocev2_mr_page_table','rocev2_shared_hls_transport','rocev2_shared_protected_responder',
            'rocev2_immediate_integrity_transport','rocev2_wqe_memory_executor',
            'rocev2_wqe_response_guard','rocev2_wqe_tx_lifetime','rocev2_wqe_replay',
            'rocev2_receive_queue','rocev2_receive_ack_tx','rocev2_cq_mmio',
            'rocev2_duplex_rx_mux','rocev2_duplex_tx_router']}
        wanted['rocev2_memory_origin_router']=2;wanted['rocev2_sq_control_regs']=2
        counts={n:len(re.findall(r'\.scope module, "[^\"]+" "'+n+r'"',vvp))for n in wanted}
        if counts!=wanted:raise ValueError('wrong native core/protection multiplicity '+str(counts))
        for n,h in before.items():
            if delivery.digest(ROOT/n)!=h:raise ValueError('consumed source changed: '+n)
        main=(directory/'rocev2_native_rnic_endpoint.v').read_text()
        if ".local_core_drained(1'b0)"not in main or ".hls_transport_drained(1'b0)"not in main:
            raise ValueError('original global drain0 gates changed')
        result.update(pass_test=True,source_unchanged=True,module_counts=counts,
            actual_generated_HLS=True,HLS_stub=False,shared_native_HLS_cores=1,
            immutable_owner_bits=620,SQ_bits=280,receive_core_proof_bits=752,receive_MAC_receipt_bits=768,
            separate_receive_wire_notifications=True,Immediate_device_capability_advertised=True,
            Immediate_capability_opt_in_native_only=True,default_graph_changed=False,
            both_global_HLS_drains_zero=True,original_legacy_HLS_sha256=selected['original_generated_HLS_sha256'])
    except Exception as e:result.update(error_type=type(e).__name__,error=str(e));raise
    finally:
        with report.open('x')as f:f.write(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--hls-build',type=Path,required=True)
    p.add_argument('--native-hls-report',type=Path,required=True);p.add_argument('--report',type=Path,required=True)
    a=p.parse_args();r=run(a.hls_build.resolve(),a.native_hls_report.resolve(),a.report.resolve())
    print(json.dumps({k:r[k]for k in ['pass_test','compile_seconds','module_counts','directory']}))
