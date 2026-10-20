#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual BTH M0/M1 parser/MR/integrity/unchanged HLS protected responses.

Finite synthetic valid-ICRC input packets, actual authorization and HLS, but
backend memory/visibility and physical peer are MODELS. No native coherent SQ,
PCIe, local executor/CQ, path migration or hardware/runtime proof.
"""
import argparse
import json
from pathlib import Path
import re
import tempfile

import test_bth_migreq_rtl as fixture
import wrkey_delivery_sim as delivery

ROOT=fixture.ROOT


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--case',choices=['positive','protection'],required=True)
    p.add_argument('--hls-build',type=Path,required=True);p.add_argument('--report',type=Path,required=True)
    args=p.parse_args()
    if args.report.exists():p.error('preserve prior evidence; choose fresh report')
    paths=[Path(__file__).resolve(),Path(fixture.__file__).resolve(),Path(fixture.protected.__file__).resolve(),
        Path(fixture.probe.__file__).resolve(),ROOT/'rdma/rnic/rtl/rocev2_protected_responder.v',
        ROOT/'rdma/rnic/rtl/rocev2_mr_table.v',ROOT/'rdma/host/rocev2_wire.py',ROOT/'rdma/read/host/read_wire.py']
    before={str(q.relative_to(ROOT)):delivery.digest(q)for q in paths}
    tb,words,cases=fixture.fixture(args.case)
    run=Path(tempfile.mkdtemp(prefix='bth-migreq-hls-',dir=ROOT/'rdma/rnic/build'))
    report=dict(scope=__doc__,case=args.case,pass_test=False,terminal_exit_status=None,source_sha256=before,
        retained_directory=str(run.relative_to(ROOT)),HLS_transport_stub=False,
        backend_memory_and_peer_models=True,path_migration_implemented=False,
        native_WQE_DMA_executor_CQ_or_verbs=False,hardware_verified=False,board_integrated=False)
    previous=delivery.bounded.tempfile
    class ExistingRun:
        @staticmethod
        def mkdtemp(**kwargs):return str(run)
    try:
        delivery.bounded.tempfile=ExistingRun
        output,identity=delivery.simulate(tb,{'input.hex':words},args.hls_build)
        identity.update(original_testbench_assertions_preserved=False,
            supplied_NEW_MigReq_case_not_rewritten_by_runner=True)
        report['actual_HLS_identity']=identity
        vvp=(run/'test.vvp').read_text()
        names=['rocev2_protected_responder','rocev2_mr_table','rocev2_top','rocev2_integrity_transport']
        counts={n:len(re.findall(r'\.scope module, "[^\"]+" "'+n+r'"',vvp))for n in names}
        if not all(v==1 for v in counts.values()):raise ValueError('actual parser/MR/HLS hierarchy '+str(counts))
        report['actual_elaborated_module_counts']=counts
        good=[c for c in cases if not c['expected_error']and not c['expected_integrity_drop']]
        packets=fixture.probe.rw_sim.ethernet_frames(output)
        if len(packets)!=len(good):raise ValueError('wrong number of actual HLS protected replies')
        checked=[]
        for packet,case in zip(packets,good):
            ethernet=bytes.fromhex('b8830367c5d08af3fbb975310800')+packet
            if(fixture.probe.rocev2_wire.internet_checksum(packet[:20])or
                packet[-4:]!=fixture.probe.rocev2_wire.icrc_ipv4(packet)):
                raise ValueError('actual reply IPv4/ICRC mismatch')
            if case['operation']=='read':
                d=fixture.probe.read_wire.decode(ethernet)
                if d['opcode']!=fixture.probe.read_wire.ONLY or d['payload']!=fixture.probe.PAYLOAD or d['syndrome']&0xe0:
                    raise ValueError('actual M0/M1 READ payload/ACK')
            else:
                d=fixture.probe.rocev2_wire.decode_ethernet(ethernet)
                if d['opcode']!=0x11 or not d['icrc_valid']or d['aeth_syndrome']&0xe0:
                    raise ValueError('actual M0/M1 WRITE ACK')
            if d['psn']!=case['psn']or d['destination_qpn']!=196:raise ValueError('actual reply trusted peer/PSN changed')
            checked.append(dict(case=case['name'],MigReq=case['MigReq'],operation=case['operation'],IP_hex=packet.hex(),
                payload_bytes_checked=65 if case['operation']=='read'else 0,IPv4_ICRC_QPN_PSN_ACK_checked=True))
        rows=[json.loads(l[7:])for l in output.splitlines()if l.startswith('RESULT ')]
        if len(rows)!=1 or not rows[0]['pass_test']or rows[0]['completed']!=len(good)or rows[0]['rejected']!=(8 if args.case=='protection'else 0)or rows[0]['rx_bad']!=int(args.case=='protection'):
            raise ValueError('actual parser/HLS authority/result counts')
        data=bytearray()
        for line in output.splitlines():
            if line.startswith('DATA '):
                _,last,keep,hex_data=line.split();part=bytes.fromhex(hex_data)
                if int(keep,16)!=(1<<len(part))-1:raise ValueError('actual WRITE byte shape')
                data.extend(part)
        writes=sum(c['operation']=='write'for c in good)
        if data!=fixture.probe.PAYLOAD*writes:raise ValueError('actual incoming WRITE bytes')
        if before!={n:delivery.digest(ROOT/n)for n in before}:raise ValueError('source changed during probe')
        report.update(pass_test=True,terminal_exit_status=0,summary=rows[0],cases=cases,responses=checked,
            four_state_simulation=True,simulation_seconds=identity['simulation_seconds'],simulation_timeout_seconds=120,
            WRITE_payload_bytes_checked=65*writes,READ_payload_bytes_checked=sum(c['payload_bytes_checked']for c in checked),
            source_sha256_before_after_equal=True,SE_TVers_PKey_pad_peer_QP_PSN_PD_key_range_integrity_gates_not_waived=True)
    except Exception as error:
        report.update(error_type=type(error).__name__,error=str(error),terminal_exit_status=1);raise
    finally:
        delivery.bounded.tempfile=previous
        report['artifact_sha256']={str(q.relative_to(ROOT)):delivery.digest(q)for q in run.iterdir()if q.is_file()}
        with args.report.open('x')as out:json.dump(report,out,indent=2);out.write('\n')


if __name__=='__main__':main()
