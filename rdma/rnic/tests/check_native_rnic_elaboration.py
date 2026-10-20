#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Elaborate the new main parent with real existing generated HLS, not a stub.

Compile only: no simulation, synthesis, programming or runtime completion claim.
The legacy initiator core is preserved; the responder core is shared by remote
requests and native local WRs. This adds no third HLS core or second MR table.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import re
import sys

import test_native_rnic_rtl as main
import wrkey_delivery_sim as delivery

ROOT=main.ROOT


def check(project,report,qp_tx_port_model=False,native_replay_report=None,send_enable=False,recv_enable=False,rnr_enable=False,recv_retire_enable=False,recv_cq_enable=False,request_cq_enable=False,separate_rq_enable=False,recv_cancel_enable=False):
    if report.exists():raise ValueError('refuse to overwrite an existing report')
    if send_enable and not native_replay_report:raise ValueError('SEND requires the matched native retry core')
    if recv_enable and not send_enable:raise ValueError('RECV requires SEND/retry profile')
    if rnr_enable and not recv_enable:raise ValueError('wire RNR requires actual RECV profile')
    if recv_retire_enable and not rnr_enable:raise ValueError('receive receipts require matched RNR profile')
    if recv_cq_enable and not recv_retire_enable:raise ValueError('receive CQ requires actual receive receipts')
    if request_cq_enable and not recv_cq_enable:raise ValueError('request CQ needs complete native profile')
    if separate_rq_enable and not request_cq_enable:raise ValueError('independent queues need complete native CQ profile')
    if recv_cancel_enable and not separate_rq_enable:raise ValueError('receive cancellation needs separate native RQ')
    if shutil.disk_usage(ROOT).free<256*1024*1024:
        raise RuntimeError('insufficient space for small RTL elaboration; HLS/XSIM guards unchanged')
    selected,manifest=delivery.verify_delivery(project)
    tb,_=main.bench(False)
    sources=[p for p in main.original.input_paths(tb)if p.suffix=='.v']
    real,data=delivery.ORIGINAL_MODULES(project)
    sources+=real+[main.TOP,*main.EXTRA]
    sources=list(dict.fromkeys(sources))
    if sources.count(delivery.OLD_BRIDGE)!=1:raise ValueError('ambiguous original bridge')
    sources.remove(delivery.OLD_BRIDGE)
    consumed=sources+data+[manifest,Path(__file__).resolve(),Path(main.__file__).resolve(),
        Path(main.derive.__file__).resolve(),Path(main.derive.recv.__file__).resolve(),main.derive.ORIGINAL]
    native_raw=[];native_info=None
    if native_replay_report:
        if qp_tx_port_model:raise ValueError('actual generated core and port model are exclusive')
        native_info=json.loads(native_replay_report.read_text())
        expected_top='rocev2_native_request_top'if request_cq_enable else'rocev2_native_recv_top'if recv_retire_enable else'rocev2_native_rnr_top'if rnr_enable else'rocev2_native_replay_top'
        if request_cq_enable and not native_info.get('request_retirement'):raise ValueError('actual request synthesis required')
        if recv_retire_enable and not native_info.get('receive_retirement'):raise ValueError('actual receive synthesis required')
        if rnr_enable and (native_info.get('HLS_top')!=expected_top or not native_info.get('native_rnr')):
            raise ValueError('matched actual native RNR synthesis required')
        if not rnr_enable and native_info.get('HLS_top','rocev2_native_replay_top')!='rocev2_native_replay_top':
            raise ValueError('raw core and selected feature do not match')
        if not native_info.get('pass_test') or not native_info.get('source_and_frozen_inputs_unchanged'):
            raise ValueError('actual matched native HLS synthesis evidence required')
        for n,h in native_info['source_sha256'].items():
            if delivery.digest(ROOT/n)!=h:raise ValueError('native HLS source changed: '+n)
        raw=ROOT/native_info['directory']/'project/solution1/syn/verilog'
        for n,h in native_info['generated_sha256'].items():
            path=raw/n
            if delivery.digest(path)!=h:raise ValueError('generated native HLS changed: '+n)
            if path.suffix=='.v':native_raw.append(path)
            else:data.append(path)
        sources+=native_raw
        consumed+=native_raw+[native_replay_report]+[raw/n for n in native_info['generated_sha256']if n.endswith('.dat')]
    if qp_tx_port_model or native_replay_report:
        sys.path.insert(0,str(ROOT/'rdma/rnic/fpga'))
        import derive_qp_tx_bridge as qp_bridge
        consumed += [Path(qp_bridge.__file__).resolve(),Path(qp_bridge.legacy.__file__).resolve(),qp_bridge.legacy.BRIDGE]
    before={str(p.relative_to(ROOT)):delivery.digest(p)for p in consumed}
    run=Path(tempfile.mkdtemp(prefix='native-rnic-elaboration-',dir=ROOT/'rdma/rnic/build'))
    generated=run/'rocev2_shared_protected_responder.v'
    generated.write_text(main.derive.derive(main.derive.ORIGINAL.read_text()))
    command=['iverilog','-g2012','-s','rocev2_native_rnic_endpoint','-o',str(run/'main.vvp'),str(generated),*map(str,sources)]
    if qp_tx_port_model:
        # Compile the real NEW integrity wrapper/ancestry; only the new raw
        # HLS core's ports are modeled. Never label this actual new-HLS proof.
        bridge=run/'qp_bridge.v';bridge.write_text(qp_bridge.derive())
        top=next(p for p in real if p.name=='rocev2_top.v')
        declarations=re.findall(r'^(?:input|output)\s+[^;]+;',top.read_text(),re.M)
        ports=[d.rstrip(';').strip()for d in declarations]
        ports += ['output [79:0] m_axis_qp_apply_TDATA','output m_axis_qp_apply_TVALID','input m_axis_qp_apply_TREADY']
        stub=run/'qptx_port_model.v';stub.write_text('module rocev2_qptx_top('+','.join(ports)+');endmodule\n')
        command += ['-Procev2_native_rnic_endpoint.QP_TX_ENABLE=1',str(bridge),str(stub)]
    elif native_replay_report:
        bridge=run/'qp_bridge.v';bridge.write_text(qp_bridge.derive())
        command += ['-Procev2_native_rnic_endpoint.QP_TX_ENABLE=1',
            '-Procev2_native_rnic_endpoint.RETRY_ENABLE=1',str(bridge)]
        if send_enable:command+=['-Procev2_native_rnic_endpoint.SEND_ENABLE=1']
        if recv_enable:command+=['-Procev2_native_rnic_endpoint.RECV_ENABLE=1']
        if rnr_enable:command+=['-Procev2_native_rnic_endpoint.RNR_ENABLE=1']
        if recv_retire_enable:command+=['-Procev2_native_rnic_endpoint.RECV_RETIRE_ENABLE=1']
        if recv_cq_enable:command+=['-Procev2_native_rnic_endpoint.RECV_CQ_ENABLE=1']
        if request_cq_enable:command+=['-Procev2_native_rnic_endpoint.REQUEST_CQ_ENABLE=1']
        if separate_rq_enable:command+=['-Procev2_native_rnic_endpoint.SEPARATE_RQ_ENABLE=1']
        if recv_cancel_enable:command+=['-Procev2_native_rnic_endpoint.RECV_CANCEL_ENABLE=1']
    result=dict(scope=__doc__,pass_test=False,hardware_verified=False,simulation_run=False,
        full_board_selected_or_built=False,standard_verbs_or_CQ_implemented=False,
        original_HLS_sha256=selected['original_generated_HLS_sha256'],
        delivery_sha256=selected['delivery_sha256'],source_sha256=before,
        generated_responder_sha256=hashlib.sha256(generated.read_bytes()).hexdigest(),
        output_directory=str(run.relative_to(ROOT)),command=command,compile_timeout_seconds=60)
    try:
        started=time.monotonic()
        c=subprocess.run(command,capture_output=True,text=True,timeout=60)
        result['compile_seconds']=time.monotonic()-started
        (run/'compile.log').write_text(c.stdout+c.stderr)
        result['compiler_exit_code']=c.returncode
        if c.returncode:raise RuntimeError('actual-HLS elaboration failed; see '+str(run/'compile.log'))
        compiled=(run/'main.vvp').read_text()
        names=['rocev2_top','rocev2_shared_hls_transport','rocev2_shared_protected_responder',
            'rocev2_native_rnic_endpoint','rocev2_native_sq_endpoint','rocev2_mr_table','rocev2_mr_page_table',
            'rocev2_wqe_memory_executor','rocev2_wqe_response_guard','rocev2_wqe_tx_lifetime','rocev2_cq_mmio']
        counts={n:len(re.findall(r'\.scope module, "[^\"]+" "'+n+r'"',compiled))for n in names}
        if counts['rocev2_top']!=(1 if qp_tx_port_model or native_replay_report else 2) or any(counts[n]!=1 for n in names if n!='rocev2_top'):
            raise ValueError('wrong main-parent shared/legacy HLS or MR multiplicity: '+str(counts))
        if qp_tx_port_model:
            for n in ['rocev2_qptx_top','rocev2_qptx_integrity_transport']:
                counts[n]=len(re.findall(r'\.scope module, "[^\"]+" "'+n+r'"',compiled))
                if counts[n]!=1:raise ValueError('wrong opt-in QP core multiplicity')
        if native_replay_report:
            if separate_rq_enable:
                for n,wanted in [('rocev2_sq_control_regs',2),('rocev2_sq_wqe_admission',2),('rocev2_sq_dma_fetch',1),('rocev2_queue_cfg_arbiter',1)]:
                    counts[n]=len(re.findall(r'\.scope module, "[^\"]+" "'+n+r'"',compiled))
                    if counts[n]!=wanted:raise ValueError('independent queue hierarchy mismatch '+str(counts))
            if recv_cq_enable:
                n='rocev2_receive_ack_tx';counts[n]=len(re.findall(r'\.scope module, "[^\"]+" "'+n+r'"',compiled))
                if counts[n]!=1:raise ValueError('missing actual receive ACK owner')
            for n in [expected_top,'rocev2_qptx_integrity_transport','rocev2_wqe_replay','rocev2_retry_mmio']:
                counts[n]=len(re.findall(r'\.scope module, "[^\"]+" "'+n+r'"',compiled))
                if counts[n]!=1:raise ValueError('wrong actual native replay multiplicity: '+str(counts))
            if recv_enable:
                n='rocev2_receive_queue';counts[n]=len(re.findall(r'\.scope module, "[^\"]+" "'+n+r'"',compiled))
                if counts[n]!=1:raise ValueError('missing actual receive owner queue')
            for n,h in native_info['generated_sha256'].items():
                if delivery.digest(raw/n)!=h:raise ValueError('generated native HLS changed during elaboration')
        delivery.verify_delivery(project)
        if before!={n:delivery.digest(ROOT/n)for n in before}:raise ValueError('consumed source changed')
        result.update(pass_test=True,actual_generated_HLS_elaborated=not qp_tx_port_model,HLS_stub=qp_tx_port_model,
            module_counts=counts,legacy_HLS_cores=1,shared_requester_responder_HLS_cores=1,
            QP_TX_ENABLE=int(qp_tx_port_model or bool(native_replay_report)),RETRY_ENABLE=int(bool(native_replay_report)),
            SEND_ENABLE=int(send_enable),
            RECV_ENABLE=int(recv_enable),
            RNR_ENABLE=int(rnr_enable),
            RECV_RETIRE_ENABLE=int(recv_retire_enable),
            RECV_CQ_ENABLE=int(recv_cq_enable),
            REQUEST_CQ_ENABLE=int(request_cq_enable),
            SEPARATE_RQ_ENABLE=int(separate_rq_enable),
            RECV_CANCEL_ENABLE=int(recv_cancel_enable),
            new_raw_QP_HLS_port_model=qp_tx_port_model,
            generated_new_QP_HLS_verified=bool(native_replay_report),
            native_replay_raw_HLS_sha256=native_info['generated_sha256']if native_info else {},
            third_HLS_core_added=False,source_unchanged=True)
    except Exception as e:
        result.update(error_type=type(e).__name__,error=str(e));raise
    finally:
        with report.open('x')as out:out.write(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--hls-build',required=True,type=Path);p.add_argument('--report',required=True,type=Path)
    p.add_argument('--qp-tx-port-model',action='store_true')
    p.add_argument('--native-replay-report',type=Path)
    p.add_argument('--send-enable',action='store_true')
    p.add_argument('--recv-enable',action='store_true')
    p.add_argument('--rnr-enable',action='store_true')
    p.add_argument('--recv-retire-enable',action='store_true')
    p.add_argument('--recv-cq-enable',action='store_true')
    p.add_argument('--request-cq-enable',action='store_true')
    p.add_argument('--separate-rq-enable',action='store_true')
    p.add_argument('--recv-cancel-enable',action='store_true')
    args=p.parse_args();r=check(args.hls_build.resolve(),args.report.resolve(),args.qp_tx_port_model,
        args.native_replay_report.resolve()if args.native_replay_report else None,args.send_enable,args.recv_enable,args.rnr_enable,args.recv_retire_enable,args.recv_cq_enable,args.request_cq_enable,args.separate_rq_enable,args.recv_cancel_enable)
    print(json.dumps({n:r[n]for n in ['pass_test','compile_seconds','module_counts','output_directory']}))
