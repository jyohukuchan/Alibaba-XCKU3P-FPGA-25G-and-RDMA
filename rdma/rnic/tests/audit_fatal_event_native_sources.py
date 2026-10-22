#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Exact real selected1000/mailbox/SQC-RQC guard and optional AXI source graph.

Source/elaboration proof ONLY. New FEC-native packet/MMIO and actual Linux
delivery/async callbacks are not inferred from a compiled graph or replay.
"""
import argparse
import json
from pathlib import Path
import re
import audit_segmented_receive as binding
import check_fatal_event_native as candidate

ROOT=binding.ROOT;digest=binding.digest


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True)
    p.add_argument('--native-record',default='fatal-event-native-elaboration-002');a=p.parse_args()
    if a.report.exists():p.error('preserve all earlier evidence')
    if not re.fullmatch(r'fatal-event-native-elaboration-\d{3}',a.native_record):p.error('exact actual native FEC elaboration record required')
    names=[a.native_record,'fatal-event-mmio-diagnostics-001',
        'write-abort-event-native-elaboration-001','write-abort-event-native-full-001',
        'write-abort-event-native-runtime-diagnostics-001','write-abort-event-generated-hls-002','fatal-event-fanout-001']
    records={};ids={}
    for n in names:records[n],ids[n]=binding.bindings(n)
    native,component,parent,old,runtime,hls,fanout=[records[n]for n in names]
    if not all(r.get('pass_test',r.get('audit_passed'))for r in records.values())or \
       native['actual_mailbox_native_runtime']or component['new_mailbox_native_wiring']or len(old['tests'])!=40:
        raise ValueError('exact full native40 baseline, separate component and new source—not packet—proof required')
    oldfiles=[ROOT/n for n in parent['selected_RTL']];newfiles=[ROOT/n for n in native['selected_RTL']]
    ot=next(p for p in oldfiles if p.name=='rocev2_native_rnic_endpoint.v')
    os=next(p for p in oldfiles if p.name=='rocev2_native_sq_endpoint.v')
    nt=next(p for p in newfiles if p.name==ot.name);ns=next(p for p in newfiles if p.name==os.name)
    top,sq=candidate.derive(ot.read_text(),os.read_text())
    if nt.read_text()!=top or ns.read_text()!=sq or \
       [p for p in newfiles if p not in [nt,ns,candidate.FEC,candidate.FANOUT]]!=[p for p in oldfiles if p not in [ot,os]]:
        raise ValueError('only exact two new native leaves and same actual tested FEC/fanout leaves allowed')
    gen=ROOT/hls['directory']/'project/solution1/syn/verilog'
    if {p.name for p in newfiles if p.parent==gen}|{Path(n).name for n in native['selected_HLS_data']}!=set(hls['generated_sha256']):
        raise ValueError('whole identical actual207-file HLS cohort required')
    if len(hls['generated_sha256'])!=207 or native['module_counts']['rocev2_fatal_event_mmio']!=1 or native['module_counts']['rocev2_fatal_event_fanout']!=1:
        raise ValueError('sole real mailbox/tracked fanout and whole actual core required')
    for marker in ['.m_done(fatal_join_selected)',
        'rocev2_fatal_event_fanout fatal_event_split(',
        '.s_data(fatal_join_selected),.s_valid(fatal_join_valid),.s_ready(fatal_join_ready)',
        '.s_fatal_selected(fatal_mailbox_selected)',
        '.s_fatal_selected_valid(fatal_mailbox_valid)',
        '.s_fatal_quarantined(write_abort_quarantined)']:
        if marker not in top:raise ValueError('actual native join/atomic fanout/quarantine binding missing:'+marker)
    gate='.wire_queue_guard(wire_queue_guard | atomic_binding_queue_guard | fatal_event_queue_guard | s_fatal_quarantined),'
    if sq.count(gate)!=2 or 'assign local_work_guard=fatal_event_guard || (|s_fatal_quarantined) ||'not in sq:
        raise ValueError('both actual SQC/RQC configuration guards must retain native quarantine after mailbox ACK')
    if "{24'd0,24'd0,24'h406000,24'd0,24'd0,24'h405000,"not in sq or 'SEPARATE_RQ_ENABLE ? 6 :'not in sq:
        raise ValueError('one explicit nonoverlapping sixth optional native aperture required')
    if native['selected_HLS_data']!=parent['selected_HLS_data']or native['both_global_HLS_drains_zero']is not True or \
       native['software_profile']!=8 or native['default_or_driver_capability_changed']:
        raise ValueError('original core/data/profile8/drains/default advertisement must remain')
    if digest(candidate.FANOUT)!=fanout['source_sha256'][str(candidate.FANOUT.relative_to(ROOT))]:raise ValueError('same actual tested independent-stall fanout required')
    inputs=[Path(__file__).resolve(),Path(candidate.__file__).resolve(),nt,ns,candidate.FEC,candidate.FANOUT]
    r=dict(scope=__doc__,audit_passed=True,evidence=ids,verified_bindings=sum(v['bindings_verified']for v in ids.values()),
        source_sha256={str(p.relative_to(ROOT)):digest(p)for p in inputs},
        only_two_native_leaves_changed=True,all_other_parent_RTL_and_HLS207_unchanged=True,
        actual_selected1000_join_tracked_fanout=True,actual_SQC_RQC_guards_retain_native_quarantine_after_notification_ACK=True,
        optional_native_aperture=0x406000,aperture_bytes=4096,software_metadata_bytes=192,
        actual_mailbox_native_packet_MMIO_runtime=False,actual_Linux_QP_callbacks=False,
        standard_error_CQ_STOP_global_drain_unpin=False,full_board_timing=False,hardware_verified=False,
        overall_goal_complete=False,hardware_or_default_actions=[],commit_or_push=False,
        remaining=['New real mailbox-native AXI route/readback/ACK/persistent-quarantine runtime with all40 previous regressions.',
            'Actual Linux object/SQC cookie+epoch reference binding and async QP error delivery, genuine error/flush WC/STOP/recovery/lifetime retirement.',
            'All original11/original timing/full-board/physical remain.'])
    with a.report.open('x')as f:f.write(json.dumps(r,indent=2)+'\n')
    print(json.dumps(dict(audit_passed=True,verified_bindings=r['verified_bindings'],native_FEC_source_only=True,actual_mailbox_runtime=False)))


if __name__=='__main__':main()
