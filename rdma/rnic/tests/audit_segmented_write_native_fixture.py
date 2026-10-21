#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Audit36 native case recipes/input geometry, NOT compilation/runtime proof.

Every34 prior recipe/order and original359 fatal messages must survive.
New two8193-byte WRITE inputs have independent full RETH/length/opcode,
real C128 zero-RQ and exact existing sealed-page geometry. Original runtime,
timing, Linux and hardware gates remain separate, never inferred here.
"""
import argparse
import ast
import collections
import json
from pathlib import Path
import re
import sys
import time
import audit_segmented_receive as binding
import probe_segmented_receive_continuation_native_full as parent
import probe_segmented_write_native_full as candidate
import segmented_write_payload_native_fixture as fixture

ROOT=binding.ROOT;digest=binding.digest


def recipes(text):
    main=next(n for n in ast.parse(text).body if isinstance(n,ast.FunctionDef)and n.name=='main')
    tr=next(n for n in main.body if isinstance(n,ast.Try))
    body=[n for n in tr.body if isinstance(n,(ast.Assign,ast.AugAssign))and
        any(isinstance(q,ast.Name)and q.id in ['cases','rx_cases','service_cases']
            for q in ast.walk(n.targets[0]if isinstance(n,ast.Assign)else n.target))]
    # Only the already-authored case-list assignments, not main/runtime code.
    ns={'__builtins__':{'range':range,'str':str}}
    exec(compile(ast.fix_missing_locations(ast.Module(body=body,type_ignores=[])),'case-recipes-only','exec'),ns)
    return ns['cases']


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve every previous record')
    result=dict(scope=__doc__,audit_passed=False,native_compilation_proved=False,native_runtime_proved=False,
        full_board_timing=False,hardware_verified=False,installed_software=False)
    start=time.monotonic()
    try:
        native,native_id=binding.bindings('segmented-write-native-elaboration-001')
        header,header_id=binding.bindings('native-write-header-gate-001')
        if not native['pass_test']or not header['pass_test']:raise ValueError('actual native boundary/header gate evidence required')
        old=recipes(parent.runner_source());new=recipes(candidate.runner_source())
        if len(old)!=34 or len(new)!=36 or new[2:]!=old:raise ValueError('every original native recipe/order must remain')
        fatal=lambda t:collections.Counter(re.findall(r'\$fatal\(1,"([^"]*)"',t))
        old_bench=fixture.parent.bench();new_bench=fixture.bench();old_checks=fatal(old_bench);new_checks=fatal(new_bench)
        if old_checks-new_checks or sum(old_checks.values())!=359:raise ValueError('original native fatal check removed')
        if 'force 'in new_bench:raise ValueError('no internal owner/proof/PSN/MR/DMA injection')
        inputs=[]
        for immediate in [False,True]:
            words,records,posted,encoded,frames=fixture.large_write_variant(immediate)
            counts=[len(fixture.parent.rq.split.encode_frame(f))for f in frames]
            if len(encoded)!=783 or len(records)!=2 or len(posted)!=2 or counts!=[261,260,5 if immediate else 4]:
                raise ValueError('actual complete raw WRITE input geometry')
            for packet,frame in enumerate(frames):
                ip=frame[14:]
                if int.from_bytes(ip[2:4],'big')!=len(ip)or ip[28]!=(6 if packet==0 else 7 if packet==1 else 9 if immediate else 8):
                    raise ValueError('independent raw IP length/WRITE opcode')
                if not packet and ip[40:56]!=bytes.fromhex('fedcba98765432100000000800002001'):
                    raise ValueError('independent full64 RETH/key/total')
            inputs.append(dict(Immediate=immediate,raw_Ethernet_beats=counts,raw_Ethernet_bytes=sum(map(len,frames)),
                true_payload_bytes=8193,MR_relative_offset=528,MR_first_page_offset=3565,
                actual_first_payload_host_offset=4093,required_pages=3,notification_capacity=0))
        sources=[Path(m.__file__).resolve()for m in list(sys.modules.values())if getattr(m,'__file__',None)and
            (Path(m.__file__).resolve().is_relative_to(ROOT/'rdma/rnic/tests')or Path(m.__file__).resolve().is_relative_to(ROOT/'rdma/rnic/fpga'))]
        sources+=[Path(__file__).resolve()]
        result.update(audit_passed=True,source_sha256={str(q.relative_to(ROOT)):digest(q)for q in sorted(set(sources))},
            actual_native_elaboration=native_id,actual_native_header_gate=header_id,
            all34_original_case_recipes_retained=True,planned_cases=36,
            original_bench_fatal_messages_retained=sum(old_checks.values()),new_fatal_checks=sum((new_checks-old_checks).values()),
            no_internal_force=True,inputs=inputs,original_compile_limit_seconds=1200,original_runtime_limit_seconds=30,clock_ns=4)
    except Exception as e:result.update(error_type=type(e).__name__,error=str(e));raise
    finally:
        result['seconds']=time.monotonic()-start
        with a.report.open('x')as f:f.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(audit_passed=True,planned_cases=36,old_fatal_checks=359,native_runtime_proved=False)),flush=True)


if __name__=='__main__':main()
