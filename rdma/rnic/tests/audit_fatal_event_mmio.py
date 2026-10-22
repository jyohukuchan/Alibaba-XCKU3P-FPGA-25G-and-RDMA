#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Bind recorded native certificates through actual RTL readback/C/kernel build.

Native producer replay and software IO/delivery are modeled. No live native
MMIO attachment, verbs callback, error CQ, STOP/reference retirement or unpin.
"""
import argparse
import json
from pathlib import Path
import audit_segmented_receive as binding

ROOT=binding.ROOT;digest=binding.digest
TB='rdma/rnic/tests/tb_fatal_event_mmio.v';C='rdma/rnic/tests/test_fatal_io.c'
PREIMAGE={TB:'rdma/rnic/build/fatal-event-mmio-001-preimages-nxoA6VZ4',
    C:'rdma/rnic/build/fatal-event-mmio-002-preimages-XkFtpBsR'}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve earlier evidence')
    names=['fatal-event-mmio-001','fatal-event-mmio-002','fatal-event-mmio-003','fatal-event-kernel-build-001',
        'write-abort-event-native-full-001','write-abort-event-native-runtime-diagnostics-001',
        'write-abort-scheduled-mac-native-full-001']
    records={};ids={}
    for n in names:records[n],ids[n]=binding.bindings(n,PREIMAGE if n in names[:2]else None)
    failed,prior,component,kernel,native,runtime,old=[records[n]for n in names]
    if failed['pass_test']or not all(r['pass_test']for r in [prior,component,kernel,native])or \
       not runtime['audit_passed']or not runtime['all38_old_entire_results_except_seconds_identical']or old['pass_test']:
        raise ValueError('exact success and original failure/native40 evidence required')
    if failed['error']!='fatal-event actual RTL assertions failed mode0'or set(failed['tests'])!={'0'}:
        raise ValueError('original test-control delta failure must remain a failed run')
    oldtb=(ROOT/PREIMAGE[TB]/TB).read_text();tb=(ROOT/TB).read_text()
    if oldtb.count('s_selected_valid=1;\n  if(!s_selected_ready)')!=1 or \
       oldtb.replace('s_selected_valid=1;\n  if(!s_selected_ready)','s_selected_valid=1;#1;\n  if(!s_selected_ready)')!=tb:
        raise ValueError('only before-handshake testbench delta settling may change')
    for n in ['rdma/rnic/rtl/rocev2_fatal_event_mmio.v','rdma/rnic/kernel/fatal_io.c','rdma/rnic/kernel/fatal_io.h','rdma/rnic/kernel/fatal_regs.h']:
        if failed['source_sha256'][n]!=component['source_sha256'][n]:
            raise ValueError('DUT/library changed to hide original test-control failure:'+n)
    if set(component['tests'])!={str(i)for i in range(11)}or any(t['exit']or t['seconds']>10 for t in component['tests'].values())or \
       component['clock_ns']!=4 or component['cycle_limit']!=100000 or not component['four_state']:
        raise ValueError('actual11 bounded four-state4ns/10s/100000 checks required')
    if component['C_summary']['assertions']!=277 or prior['C_summary']['assertions']!=258 or \
       component['C_summary']['actual_recorded_native_seeds']!=2 or component['C_seconds']>10:
        raise ValueError('real strengthened C identity/full-field/failure/replay/exhaustion checks required')
    if kernel['exit']or kernel['seconds']>120 or not kernel['kernel_support_object_only']or kernel['installed']or kernel['loaded']:
        raise ValueError('actual bounded kernel support build only, no install/load, required')
    for n in ['rdma/rnic/kernel/fatal_io.c','rdma/rnic/kernel/fatal_io.h','rdma/rnic/kernel/fatal_regs.h']:
        if kernel['source_sha256'][n]!=component['source_sha256'][n]:
            raise ValueError('kernel/user compile must consume SAME exact new source:'+n)
    proofs={}
    for i,name in enumerate(['LARGE_RX_WRITE_FATAL_ACCESS','LARGE_RX_WRITE_FATAL_PARTIAL']):
        token=native['tests'][name]['full_selected1000']
        if token!=old['tests'][name]['full_selected1000']or token!=component['actual_recorded_native_selected1000'][name]:
            raise ValueError('actual now-qualified native40 certificate must be byte-identical to recorded replay seed:'+name)
        run=ROOT/component['directory'];words=[int(l,16)for l in(run/('readback-'+str(i)+'.hex')).read_text().splitlines()]
        if len(words)!=32 or sum(w<<(32*j)for j,w in enumerate(words))!=int(token,16):
            raise ValueError('every actual AXI-Lite readback word must preserve actual qualified native certificate')
        proofs[name]=dict(selected1000=token,real_RTL_readback=str((run/('readback-'+str(i)+'.hex')).relative_to(ROOT)))
    for n,h in binding.PROTECTED.items():
        if digest(ROOT/n)!=h:raise ValueError('original protected raw source changed:'+n)
    inputs=[Path(__file__).resolve(),ROOT/TB,ROOT/C,ROOT/'rdma/rnic/kernel/fatal_io.c',ROOT/'rdma/rnic/rtl/rocev2_fatal_event_mmio.v']
    r=dict(scope=__doc__,audit_passed=True,evidence=ids,verified_bindings=sum(v['bindings_verified']for v in ids.values()),
        source_sha256={str(p.relative_to(ROOT)):digest(p)for p in inputs},actual_recorded_native_seed_readback_proofs=proofs,
        actual_RTL_cases=11,actual_C_assertions=277,actual_kernel_support_build=True,
        original_failed_test_control_and_SEND_reports_preserved=True,only_failed_TB_delta_control_fixed=True,
        new_mailbox_native_wiring=False,live_Linux_QP_callbacks=False,standard_error_CQ_STOP_global_drain_unpin=False,
        firmware_capability_or_driver_advertisement_changed=False,hardware_verified=False,full_board_timing=False,
        overall_goal_complete=False,hardware_or_default_actions=[],commit_or_push=False,
        remaining=['Wire this actual privileged selected1000 producer to retained optional native AXI-Lite aperture and prove real route/guard/fanout/MMIO ownership.',
            'Bind actual Linux QP/SQC cookie+epoch and kernel async error work; no RNC command/message/WR-id cookie substitutions.',
            'Standard error CQ/full QP STOP/recovery/reference lifetime/quarantine release and all original11/timing/physical remain.'])
    with a.report.open('x')as f:f.write(json.dumps(r,indent=2)+'\n')
    print(json.dumps(dict(audit_passed=True,verified_bindings=r['verified_bindings'],native_seed_proofs=2,RTL_cases=11,C_assertions=277,live_native=False)))


if __name__=='__main__':main()
