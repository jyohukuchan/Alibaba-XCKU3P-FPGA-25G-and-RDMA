#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Exact lease-only export, every aggregate guard and whole native/HLS retained.

Source/elaboration only. Original failed native42 remains false; a fresh
whole42 runtime and all old40 outcomes are still required after this fix.
"""
import argparse
import json
from pathlib import Path
import re
import audit_segmented_receive as binding
import check_fatal_rq_lease_native as checker

ROOT=binding.ROOT;digest=binding.digest;candidate=checker.candidate


def assignment(text,name):
    a=text.index('assign '+name+'=');b=text.index(';',a)+1;return text[a:b]


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve earlier evidence')
    names=['fatal-rq-lease-native-elaboration-001','fatal-rq-cancel-native-elaboration-001',
        'fatal-event-native-elaboration-002','fatal-rq-cancel-failure-diagnostics-001',
        'write-abort-event-generated-hls-002']
    records={};ids={}
    for n in names:records[n],ids[n]=binding.bindings(n)
    native,parent,original,diagnostic,hls=[records[n]for n in names]
    if not all(r.get('pass_test',r.get('audit_passed'))for r in records.values()):raise ValueError('actual failed boundary and new full source evidence required')
    before=[ROOT/n for n in parent['selected_RTL']];after=[ROOT/n for n in native['selected_RTL']]
    old={n:next(p for p in before if p.name==n)for n in candidate.LEAVES}
    new={n:next(p for p in after if p.name==n)for n in candidate.LEAVES}
    original_top=next(ROOT/n for n in original['selected_RTL']if Path(n).name==candidate.TOP)
    texts=candidate.derive({n:p.read_text()for n,p in old.items()},original_top.read_text())
    if {n:p.read_text()for n,p in new.items()}!=texts:raise ValueError('exact seven-leaf port/lease-only derivation required')
    replacements={old[n]:new[n]for n in candidate.LEAVES}
    if after!=[replacements.get(p,p)for p in before]or native['selected_HLS_data']!=parent['selected_HLS_data']or \
       native['module_counts']!=parent['module_counts']or len(after)!=465:raise ValueError('same complete465/eight-data/sole native namespace graph required')
    for n in [candidate.CORE,candidate.PAGED]:
        if assignment(old[n].read_text(),'atomic_rx_guard')!=assignment(texts[n],'atomic_rx_guard'):
            raise ValueError('original aggregate RX guards must be byte-identical')
    aggregate=assignment(original_top.read_text(),'atomic_lease_guard')
    if assignment(texts[candidate.TOP],'atomic_lease_guard')!=aggregate:raise ValueError('original full FEC40 aggregate lease guard must be byte-identical')
    rx=assignment(old[candidate.CORE].read_text(),'atomic_rx_guard')
    prefix='assign atomic_rx_guard=control_external_guard || '
    if not rx.startswith(prefix):raise ValueError('exact diagnosed control alias required')
    rest=rx[len(prefix):-1]
    if assignment(texts[candidate.CORE],'fatal_rx_noncontrol_guard')!="assign fatal_rx_noncontrol_guard=(s_control_owner_valid!==1'b0) || "+rest+';':
        raise ValueError('all real RX/write/reference/Atomic/config work AND live control-owner VALID must remain')
    old_other=aggregate[len('assign atomic_lease_guard=s_control_held || '):-1]
    if assignment(texts[candidate.TOP],'fatal_cancel_other_lease_guard')!='assign fatal_cancel_other_lease_guard='+old_other.replace('atomic_rx_guard','fatal_rx_noncontrol_guard')+';':
        raise ValueError('all other actual RNR/zero/MAC/reservation leases unchanged')
    gate='.wire_queue_guard(wire_queue_guard | atomic_binding_queue_guard | fatal_event_queue_guard | s_fatal_quarantined),'
    if texts['rocev2_native_sq_endpoint.v'].count(gate)!=2:raise ValueError('both full SQC/RQC configuration guards must remain')
    for marker in [".local_core_drained(1'b0)",".hls_transport_drained(1'b0)",
        '.event_taken(fatal_join_valid && fatal_join_ready)']:
        if marker not in texts[candidate.TOP]:raise ValueError('real completed join and original global drains required')
    gen=ROOT/hls['directory']/'project/solution1/syn/verilog'
    if len(hls['generated_sha256'])!=207 or {p.name for p in [*after,*[ROOT/n for n in native['selected_HLS_data']]]if p.parent==gen}!=set(hls['generated_sha256']):
        raise ValueError('whole exact qualified207 HLS required')
    if not diagnostic['original_failed_run_still_false']or native['actual_new_native_packet_runtime']or native['actual_RQC_cancellation_receipt']:
        raise ValueError('source fix cannot relabel old failure or become new runtime proof')
    for n,h in binding.PROTECTED.items():
        if digest(ROOT/n)!=h:raise ValueError('protected original raw source changed:'+n)
    inputs=[Path(__file__).resolve(),Path(checker.__file__).resolve(),Path(candidate.__file__).resolve(),*new.values()]
    r=dict(scope=__doc__,audit_passed=True,evidence=ids,verified_bindings=sum(v['bindings_verified']for v in ids.values()),
        source_sha256={str(p.relative_to(ROOT)):digest(p)for p in inputs},exact_seven_leaf_derivation=True,
        original_core_paged_and_aggregate_lease_guards_byte_identical=True,
        all_actual_RX_write_Atomic_memory_reference_work_retained=True,live_control_owner_VALID_retained=True,
        both_full_SQC_RQC_guards_unchanged=True,whole_qualified_HLS207_unchanged=True,
        actual_new_native_packet_runtime=False,actual_RQC_cancellation_receipt=False,
        error_CQ_STOP_global_drain_unpin=False,hardware_verified=False,full_board_timing=False,
        overall_goal_complete=False,hardware_or_default_actions=[],commit_or_push=False)
    with a.report.open('x')as f:f.write(json.dumps(r,indent=2)+'\n')
    print(json.dumps(dict(audit_passed=True,verified_bindings=r['verified_bindings'],original_aggregate_guards_unchanged=True,new_runtime=False)))


if __name__=='__main__':main()
