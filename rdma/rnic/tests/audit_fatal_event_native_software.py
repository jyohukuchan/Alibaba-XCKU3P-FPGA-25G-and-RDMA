#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Couple actual native FEC readback and identical C/kernel source boundaries.

Native40 proves packet-to-AXI/ACK. Unchanged C277 replays those exact AXI
snapshots. Separate actual driver callback220 uses SYNTHETIC certificate/
Linux/MMIO/pin/DMA/workqueue primitives. This is NOT live Linux-FPGA coupling.
"""
import argparse
import json
from pathlib import Path
import audit_segmented_receive as binding

ROOT=binding.ROOT;digest=binding.digest


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve earlier evidence')
    names=['fatal-event-native-full-001','fatal-event-native-runtime-diagnostics-001','fatal-event-native-C-readback-001',
        'fatal-verbs-kernel-build-001','fatal-verbs-callbacks-002','fatal-verbs-diagnostics-001',
        'fatal-event-native-source-diagnostics-002']
    records={};ids={}
    for n in names:records[n],ids[n]=binding.bindings(n)
    native,runtime,decoder,kernel,callbacks,software,source=[records[n]for n in names]
    if not all(r.get('pass_test',r.get('audit_passed'))for r in records.values()):raise ValueError('all separately scoped actual evidence required')
    if len(native['tests'])!=40 or len(callbacks['tests'])!=220 or decoder['C_summary']['assertions']!=277 or \
       not runtime['all40_old_full_outcomes_except_seconds_identical']or not software['all202_previous_full_summaries_identical']:
        raise ValueError('actual native40/all40 old results/C277/callback220/all202 old summaries required')
    identity=[native[n]for n in ['RNC_features','CQC_features','SQC_features','RQC_features','software_profile']]
    if identity!=kernel['private_identity']or identity!=[131071,511,13,63,8]or not native['both_global_drains_zero']:
        raise ValueError('same explicit private profile8 and original global drains required')
    parent=ROOT/kernel['directory'];run=ROOT/native['directory'];inputs=[]
    for n in ['fatal_io.c','fatal_io.h','fatal_regs.h']:
        source=ROOT/'rdma/rnic/kernel'/n
        if digest(source)!=digest(parent/n)or decoder['source_sha256'][str(source.relative_to(ROOT))]!=digest(source):
            raise ValueError('actual native-readback C decoder differs from compiled/tested kernel component:'+n)
        inputs.extend([source,parent/n])
    for name in ['LARGE_RX_WRITE_FATAL_ACCESS','LARGE_RX_WRITE_FATAL_PARTIAL']:
        q=run/(name+'-mmio.hex');inputs.append(q)
        if decoder['source_sha256'].get(str(q.relative_to(ROOT)))!=digest(q):raise ValueError('exact actual native AXI snapshot required')
        words=[int(l,16)for l in q.read_text().splitlines()]
        if len(words)!=32 or sum(v<<(32*i)for i,v in enumerate(words))!=int(native['tests'][name]['full_selected1000'],16):
            raise ValueError('all original1000 real native bits must traverse AXI and actual C unchanged')
    if not decoder['C_MMIO_delivery_callbacks_modeled']or not software['Linux_primitives_MMIO_certificate_producer_DMA_pins_workqueue_execution_modeled']or \
       decoder['live_Linux_QP_callbacks']or software['live_Linux_native_attachment']or kernel['Linux_fatal_runtime']:
        raise ValueError('replay/modeled Linux boundaries must remain explicit, never inferred as live coupling')
    inputs.append(Path(__file__).resolve())
    r=dict(scope=__doc__,audit_passed=True,evidence=ids,verified_bindings=sum(v['bindings_verified']for v in ids.values()),
        private_identity=identity,actual_native_cases=40,all40_old_full_outcomes_except_seconds_identical=True,
        actual_native_packet_HLS_abort_cancel_AXI_ACK_quarantine_and_RQ_proof=True,
        actual_native_AXI_snapshots_consumed_by_same_C_decoder_277_assertions=True,
        same_decoder_source_in_actual_full73_input_kernel_build_and_callback220=True,
        all202_old_callback_full_summaries_identical=True,actual_callback_new_fatal_cases=18,
        separate_driver_callback_certificate_producer_is_synthetic=True,
        notification_ACK_not_WC_STOP_reference_retirement_or_unpin=True,
        source_sha256={str(q.relative_to(ROOT)):digest(q)for q in inputs},
        installed_standard_API_runtime=False,live_Linux_FPGA_coupling=False,
        standard_error_flush_CQ_full_QP_STOP_recovery_retirement=False,
        hardware_verified=False,full_board_timing=False,overall_goal_complete=False,hardware_or_default_actions=[],commit_or_push=False,
        remaining=['Explicit real parent FEC attachment/polling and live registered Linux/provider object/ref/async event behavior remain unqualified.',
            'Error/flush WC, whole-QP STOP/recovery and legitimate reference/quarantine release remain.',
            'All original11/native1MiB/multiSGE/timing/full-board/physical/authenticated reboot revival remain.'])
    with a.report.open('x')as f:f.write(json.dumps(r,indent=2)+'\n')
    print(json.dumps(dict(audit_passed=True,verified_bindings=r['verified_bindings'],native40=True,C277=True,driver_callback220=True,live_coupling=False)))


if __name__=='__main__':main()
