#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Bounded actual-HLS wire responder + actual C/local-WQE + shared actual MR.

Physical host/PCIe/local work executor/CQE/verbs are NOT implemented here.
Only the memory backend and downstream local lease are explicit test models.
Uses an exact verified per-WR delivery, default legacy transport key mode;
local WQEs perform real MR authorization but do not submit outgoing HLS work.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time

import shared_mr_fixture as fixture
import test_shared_mr_responder_rtl as shared
import wrkey_delivery_sim as delivery

ROOT=shared.ROOT


def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case',required=True,choices=['namespace','lease','overlap'])
    parser.add_argument('--hls-build',required=True,type=Path)
    parser.add_argument('--report',required=True,type=Path)
    args=parser.parse_args()
    report_path=args.report.resolve()
    if report_path.exists():parser.error('preserve previous evidence; choose a new report')
    selected,path=delivery.verify_delivery(args.hls_build)
    instance=shared.SharedMRResponderRTLTests()
    instance.setUpClass()
    try:
        fixtures,body,cases=getattr(instance,args.case+'_case')()
    finally:instance.directory.cleanup()
    tb=fixture.make_tb(fixtures,body)
    if 'force 'in tb:raise ValueError('internal forcing forbidden')
    sources,data=delivery.ORIGINAL_MODULES(args.hls_build)
    if sources.count(delivery.OLD_BRIDGE)!=1:raise ValueError('bridge exclusion changed')
    sources.remove(delivery.OLD_BRIDGE)
    sources += shared.SOURCES[:4]
    if len(sources)!=len(set(sources)):raise ValueError('duplicate compiler sources')
    own=[Path(__file__).resolve(),Path(shared.__file__).resolve(),Path(fixture.__file__).resolve(),
         Path(shared.codec.__file__).resolve(),shared.codec.KERNEL/'wqe.c',shared.codec.KERNEL/'wqe.h',
         Path(fixture.probe.__file__).resolve(),ROOT/'rdma/read/tests/rw_sim.py',
         ROOT/'rdma/host/rocev2_wire.py',ROOT/'rdma/read/host/read_wire.py',ROOT/'rdma/tests/test_icrc_rtl.py',
         Path(delivery.__file__).resolve(),path]
    before={str(p.relative_to(ROOT)):digest(p)for p in sources+data+own}
    # Retain the exact generated fixture, compiler outputs and raw simulation
    # in a fresh directory, including on failure. No repair/assertion changes.
    import tempfile
    run=Path(tempfile.mkdtemp(prefix='shared-mr-'+args.case+'-',dir=ROOT/'rdma/rnic/build'))
    (run/'tb.v').write_text(tb)
    (run/'input.hex').write_text(''.join(f'{v:x}\n'for v in fixtures))
    for p in data:shutil.copy2(p,run/p.name)
    command=['iverilog','-g2012','-s','tb','-o',str(run/'test.vvp'),str(run/'tb.v'),*map(str,sources)]
    record=dict(scope=__doc__,case=args.case,pass_test=False,terminal_exit_status=None,
        hardware_verified=False,board_integrated=False,standard_verbs_implemented=False,
        native_host_queue_DMA=False,local_WQE_submitted_to_transport=False,
        actual_C_codec=True,actual_single_MR_table=True,actual_local_WQE_frontend=True,
        actual_generated_HLS=True,transport_stub=False,memory_backend_model=True,
        downstream_local_executor_lease_model=True,hls_build=str(args.hls_build.resolve()),
        original_generated_HLS_sha256=selected['original_generated_HLS_sha256'],
        delivery_sha256=selected['delivery_sha256'],generated_files=138,delivery_files=140,
        directory=str(run.relative_to(ROOT)),compiler_command=command,
        compile_timeout_seconds=90,simulation_timeout_seconds=120,source_sha256=before,
        bench_sha256=digest(run/'tb.v'),fixture_sha256=digest(run/'input.hex'))
    started=time.monotonic()
    try:
        c=subprocess.run(command,capture_output=True,text=True,timeout=90)
        (run/'compile.log').write_text(c.stdout+c.stderr)
        record['compiler_returncode']=c.returncode
        if c.returncode:raise RuntimeError(c.stdout+c.stderr)
        sim_started=time.monotonic()
        s=subprocess.run(['vvp',str(run/'test.vvp')],cwd=run,capture_output=True,text=True,timeout=120)
        record['simulation_seconds']=time.monotonic()-sim_started
        (run/'simulation.log').write_text(s.stdout+s.stderr)
        print(s.stdout+s.stderr,flush=True)
        record['simulator_returncode']=s.returncode
        if s.returncode or 'ERROR:'in s.stdout+s.stderr:raise RuntimeError('actual RTL simulation failed')
        rows=[json.loads(line[7:])for line in s.stdout.splitlines()if line.startswith('RESULT ')]
        if len(rows)!=1 or not rows[0]['pass_test']:raise ValueError('missing actual simulation summary')
        local_rows=[json.loads(line[13:])for line in s.stdout.splitlines()if line.startswith('LOCAL_RESULT ')]
        expected_local={'namespace':(11,11,0),'lease':(4,4,1),'overlap':(1,1,0)}[args.case]
        if len(local_rows)!=1 or tuple(local_rows[0][n]for n in ['queries','results','retained_leases'])!=expected_local or local_rows[0]['executor_guard']!=0:
            raise ValueError('actual local MR/work/lease counts differ from expected case')
        expected=[c for c in cases if not c.get('expected_error')and not c.get('expected_integrity_drop')]
        if args.case!='namespace':expected=[dict(operation='write',psn=fixture.probe.PSN)]
        frames=fixture.probe.rw_sim.ethernet_frames(s.stdout)
        if len(frames)!=len(expected) or len(frames)!=rows[0]['commands']:
            raise ValueError('unexpected actual wire response count')
        checked=[]
        for packet,case in zip(frames,expected):
            if fixture.probe.rocev2_wire.internet_checksum(packet[:20])!=0:raise ValueError('bad IPv4 checksum')
            ethernet=bytes.fromhex('b8830367c5d08af3fbb975310800')+packet
            if case['operation']=='read':
                d=fixture.probe.read_wire.decode(ethernet)
                if d['opcode']!=fixture.probe.read_wire.ONLY or d['payload']!=fixture.probe.PAYLOAD or d['syndrome']&0xe0:
                    raise ValueError('bad actual READ response')
            else:
                d=fixture.probe.rocev2_wire.decode_ethernet(ethernet)
                if d['opcode']!=0x11 or not d['icrc_valid'] or d['aeth_syndrome']&0xe0:
                    raise ValueError('bad actual WRITE ACK')
            if d['psn']!=case['psn']or d['destination_qpn']!=196:raise ValueError('wire owner/PSN mismatch')
            checked.append(dict(operation=case['operation'],psn=case['psn'],IPv4_hex=packet.hex(),
                                payload_bytes_verified=65 if case['operation']=='read'else 0))
        delivery.verify_delivery(args.hls_build)
        if before!={n:digest(ROOT/n)for n in before}:raise ValueError('consumed source changed during execution')
        record.update(pass_test=True,terminal_exit_status=0,summary=rows[0],local_summary=local_rows[0],responses=checked,
            original_generated_HLS_bytes_unchanged=True,source_sha256_before_after_equal=True)
    except Exception as e:
        record.update(error_type=type(e).__name__,error=str(e),terminal_exit_status=1)
        raise
    finally:
        record['elapsed_seconds']=time.monotonic()-started
        with report_path.open('x')as f:json.dump(record,f,indent=2);f.write('\n')


if __name__=='__main__':main()
