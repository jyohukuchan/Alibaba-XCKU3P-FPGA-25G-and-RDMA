#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual native37 RNR/retry with same-source kernel and raw-CQ100 checks.

Compare every frozen kernel input byte and every95 previous callback result.
Linux/MMIO/pins/DMA primitives remain MODELS, not installed/live hardware.
"""
import argparse
import json
from pathlib import Path
import audit_segmented_receive as binding
from audit_segmented_write_native_software import kernel_build_bindings

ROOT=binding.ROOT;digest=binding.digest


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve previous evidence')
    names=['segmented-write-rnr-native-full-002','segmented-write-rnr-native-runtime-diagnostics-001',
        'segmented-write-rnr-kernel-build-001','segmented-write-rnr-kernel-native-cq-001',
        'segmented-write-kernel-build-001','segmented-write-kernel-native-cq-001',
        'segmented-write-native-software-diagnostics-001']
    records={};ids={}
    for n in names:records[n],ids[n]=kernel_build_bindings(n)if n in [names[2],names[4]]else binding.bindings(n)
    native,runtime,kernel,cq,oldkernel,oldcq,previous=[records[n]for n in names]
    if not all(r.get('pass_test')for r in [native,kernel,cq,oldkernel,oldcq])or not runtime['audit_passed']or not previous['audit_passed']:
        raise ValueError('independently scoped actual native37/kernel/rawCQ100 and old proofs required')
    if len(native['tests'])!=37 or len(cq['tests'])!=100 or len(oldcq['tests'])!=95 or not kernel['native_RNR_retry_matched']:
        raise ValueError('exact new37 and matched kernel/all100 CQ cases required')
    if kernel['frozen_input_sha256']!=oldkernel['frozen_input_sha256']:
        raise ValueError('ALL exact old/new kernel frozen input bytes, including parent/Makefile, must stay identical')
    for n,h in kernel['frozen_input_sha256'].items():
        for r in [kernel,oldkernel]:
            if digest(ROOT/r['directory']/n)!=h:raise ValueError('actual frozen kernel input changed:'+n)
    if not set(oldcq['tests']).issubset(cq['tests']):raise ValueError('every95 original CQ case name required')
    for n,r in oldcq['tests'].items():
        if cq['tests'][n]['summary']!=r['summary']:raise ValueError('old standard callback outcome changed:'+n)
    for r in [kernel,cq]:
        if r['compile_seconds']>(180 if r is kernel else 30):raise ValueError('original bounded compile gates required')
    if kernel['compile_exit']or any(kernel[n]for n in ['installed','module_load_performed','default_sources_changed','atomic_cap_advertised']):
        raise ValueError('real-header compilation only, old defaults/Atomic_NONE required')
    if cq['simulation_limit_seconds']!=10 or any(r['exit']or r['seconds']>10 for r in cq['tests'].values()):
        raise ValueError('all original bounded actual standard C callback cases required')
    run=ROOT/native['directory'];snapshot=run/'LARGE_RX_WRITE_RNR-event.hex';rq=run/'LARGE_RX_WRITE_RNR-receive-records.hex'
    for path in [snapshot,rq]:
        if cq['source_sha256'].get(str(path.relative_to(ROOT)))!=digest(path):raise ValueError('raw new native CQ/RQ input must be directly bound')
    positive=cq['tests']['LARGE_RX_WRITE_RNR-0']['summary']
    if positive['bytes']!=8193 or positive['capacity']or not all(positive.get(n)for n in ['native_RTL_CQ_unedited',
        'full128_kernel_native_record_identical','actual_standard_WRITE_notification_CQ_MR_lifetime','profile8_CQC511']):
        raise ValueError('real standard zero-RQ/whole8193 WRITE notification semantics required')
    for mutation in range(1,5):
        r=cq['tests']['LARGE_RX_WRITE_RNR-'+str(mutation)]['summary']
        if not r['owners_intentionally_retained']or r['mutation']!=mutation:raise ValueError('malformed whole owner must retain lifetime')
    for report in [kernel,cq]:
        if report['source_sha256'].get(str(binding.record(names[0]).relative_to(ROOT)))!=digest(binding.record(names[0])):
            raise ValueError('actual new native37 raw report, not an old success, must gate the consumer')
    for n,h in binding.PROTECTED.items():
        if digest(ROOT/n)!=h:raise ValueError('protected original raw source changed')
    result=dict(scope=__doc__,audit_passed=True,evidence=ids,verified_bindings=sum(r['bindings_verified']for r in ids.values()),
        actual_native_cases=37,actual_standard_C_native_CQ_cases=100,all95_previous_CQ_outcomes_identical=True,
        exact_frozen_kernel_input_files=len(kernel['frozen_input_sha256']),all_frozen_kernel_inputs_byte_identical=True,
        kernel_compile_seconds=kernel['compile_seconds'],CQ_compile_seconds=cq['compile_seconds'],new_RNR_CQ_summary=positive,
        malformed_native_CQ_mutations_retain_owner=True,source_sha256={str(Path(__file__).relative_to(ROOT)):digest(__file__)},
        protected_raw_sha256=binding.PROTECTED,previous202_callback_runs_not_reexecuted=True,
        primitive_Linux_MMIO_pins_DMA_models=True,installed_kernel_or_physical=False,full_board_timing=False,overall_goal_complete=False,
        remaining=['All11/full1MiB native/multiSGE/live registered Linux/provider refs/real-peer NAK/RNR/retry/MSN/congestion/safe partial-HLS teardown/original timing/physical remain.'],
        install_load_program_reboot_network_fan_BIOS_actions=[],commit_or_push=False)
    with a.report.open('x')as f:f.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(audit_passed=True,verified_bindings=result['verified_bindings'],native37=True,actual_CQ100=True,physical=False)),flush=True)


if __name__=='__main__':main()
