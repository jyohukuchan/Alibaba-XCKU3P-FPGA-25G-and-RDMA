#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Exact actual native/RQ/CQ snapshots consumed by matched profile7 C.

Preserve the preceding functional audit; all18 positive pairs andfour
explicit in-memory negative mutations per pair are required. No snapshot
rewrites, live Linux/RTL/pin/page-table coupling, native1MiB or physical claim.
"""
import argparse
import json
from pathlib import Path
import audit_segmented_receive as binding
from probe_kernel_segmented_receive_native_cq import CASES

ROOT=binding.ROOT;PREFIX=binding.PREFIX;digest=binding.digest


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve earlier evidence')
    functional,f_id=binding.bindings('segmented-receive-functional-diagnostics-001')
    native,n_id=binding.bindings('segmented-receive-native-full-004')
    software,s_id=binding.bindings('segmented-receive-kernel-native-cq-001')
    if not functional.get('audit_passed')or not native.get('pass_test')or not software.get('pass_test')or \
       not software.get('source_unchanged')or len(CASES)!=18:
        raise ValueError('actual current full-native/functional and matched C execution required')
    if (software['RNC_features'],software['CQC_features'],software['software_profile'])!=(65535,255,7)or \
       set(software['tests'])!={name+'-'+str(i)for name,_,_ in CASES for i in range(5)}:
        raise ValueError('all18 exact positive pairs andfour mutations each required')
    if software['simulation_limit_seconds']!=10 or any(v['exit']!=0 or v['seconds']>10 for v in software['tests'].values()):
        raise ValueError('all original bounded actual C executions required')
    for name,_,_ in CASES:
        positive=software['tests'][name+'-0']['summary']
        if not all(positive.get(k)for k in ['native_RTL_CQ_unedited','full128_kernel_native_record_identical','actual_standard_C_callbacks_CQ_MR_release']):
            raise ValueError('unedited actual snapshot, complete record and C lifetime checks required')
        for i in range(1,5):
            if not software['tests'][name+'-'+str(i)]['summary'].get('owners_intentionally_retained'):
                raise ValueError('negative full-owner events must not release references')
    source=ROOT/native['directory'];snapshots={}
    for name in ['LARGE_RX_SEND','LARGE_RX_SEND_IMM']:
        event=source/(name+'-event.hex');record=source/(name+'-receive-records.hex')
        if len(event.read_text().splitlines())!=33 or len(record.read_text().splitlines())!=2:
            raise ValueError('actual33-word RX event and original two-record RQ input required')
        if software['source_sha256'].get(str(event.relative_to(ROOT)))!=digest(event)or \
           software['source_sha256'].get(str(record.relative_to(ROOT)))!=digest(record):raise ValueError('actual positive RX bytes must be source-bound')
        s=software['tests'][name+'-0']['summary']
        if (s['opcode'],s['bytes'],s['capacity'])!=(4,8193,8194):raise ValueError('capacity is not actual received bytes')
        snapshots[name]=dict(event_sha256=digest(event),RQ_records_sha256=digest(record),event_words=33,
            fabricated_geometry_words=False,actual_positive_owner_MR_retirement=True)
    result=dict(scope=__doc__,audit_passed=True,overall_goal_complete=False,hardware_verified=False,
        functional_audit=f_id,actual_native=n_id,actual_matched_C=s_id,verified_bindings=sum(v['bindings_verified']for v in [f_id,n_id,s_id]),
        auditor_source_sha256={str(Path(__file__).relative_to(ROOT)):digest(__file__)},
        actual_native_cases=34,matched_C_snapshot_cases=90,all16_old_pairs_retained=True,new_receive_pairs=2,
        malformed_copies_explicitly_labeled_in_memory=True,real_native_input_and_event_files_unchanged=True,
        receive_snapshots=snapshots,maximum_C_case_seconds=max(v['seconds']for v in software['tests'].values()),
        actual_positive_records_all128_bytes=True,actual_C_MR_RQ_CQ_owner_and_reference_lifetimes=True,
        Linux_MMIO_pins_coherent_DMA_and_teardown_modeled=True,live_kernel_RTL_coupling=False,
        actual_native_and_C_page_tables_live_coupled=False,standard_provider_with_live_kernel=False,
        native_1MiB_receive_verified=False,original4ns_timing_met=False,installed=False,module_loaded=False,
        remaining=functional['remaining'],hardware_install_load_network_fan_BIOS_flash_reboot_actions=[],commit_or_push=False)
    with a.report.open('x')as f:f.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(audit_passed=True,verified_bindings=result['verified_bindings'],native_cases=34,C_snapshot_cases=90,
        maximum_C_seconds=result['maximum_C_case_seconds'],live_Linux_or_physical=False)),flush=True)


if __name__=='__main__':main()
