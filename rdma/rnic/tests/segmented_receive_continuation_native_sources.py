# SPDX-License-Identifier: BSD-2-Clause-Views
"""Exact qualified receive graph plus one reviewed raw-continuation gate.

Retain every original source/component/HLS/MR/nonce/clock/drain gate. Bind the
original actual failure/read-only debugger evidence and real reference unit;
replace only the corresponding raw-reference enable, never pending/owner/
status/MR/HLS/MAC/CQ. Old source graphs and raw protected RTL stay immutable.
"""
import json
from pathlib import Path
import segmented_receive_native_sources as qualified
import derive_segmented_receive_continuation as candidate

ROOT=qualified.ROOT;digest=qualified.digest;HLS=qualified.HLS
# Preserve the public parent evidence interface used by the strict runner.
parent=qualified.parent
PREFIX=ROOT/'results/2026-10-18'
DIAGNOSTIC=PREFIX/'rocev2-rnic-segmented-receive-native-fatal-diagnostics-003.json'
UNIT=PREFIX/'rocev2-rnic-receive-continuation-gate-001.json'
FAILED=PREFIX/'rocev2-rnic-segmented-receive-native-full-003.json'
EVIDENCE={**qualified.EVIDENCE,'continuation_gate':UNIT,'original_fatal_inspection':DIAGNOSTIC}


def sources(project,immediate_report,owned_report,request_report,run):
    diagnostic=json.loads(DIAGNOSTIC.read_text());unit=json.loads(UNIT.read_text())
    failed=json.loads(FAILED.read_text())
    if failed.get('pass_test')or not diagnostic.get('diagnostic_completed')or diagnostic.get('native_runtime_pass')or \
       not diagnostic.get('source_and_objects_unchanged')or diagnostic.get('failed_bindings_verified')!=1913:
        raise ValueError('exact actual failed native/read-only archived-object inspection required')
    qualified.parent.verify_nested(diagnostic)
    if not all(unit.get(k)for k in ['pass_test','source_unchanged','all9_current_cases','old_gate_negative_control_failed_as_expected'])or \
       len(unit['tests'])!=10 or unit['tests']['old-1']['exit']==0:
        raise ValueError('actual production-expression/reference unit and unchanged negative control required')
    qualified.parent.verify_nested(unit)
    fields=diagnostic['actual_fatal_fields']
    guard='tb__DOT__dut__DOT__native__DOT__network__DOT__datapath__DOT__responder__DOT__endpoint__DOT__shared_hls__DOT__guard__DOT__'
    expected={guard+'recv_completion_pending':1,guard+'recv_group_active':1,guard+'normal_checked_ready':1,
        guard+'input_references__DOT__context_ok':1,guard+'input_references__DOT__context_stable':1,
        guard+'input_references__DOT__granted':0,guard+'input_references__DOT__in_frame':0,
        'tb__DOT__lrx_commands':1,'tb__DOT__lrx_fenced_bytes':4096,'tb__DOT__lrx_packet_releases':1}
    if any(fields.get(k)!=v for k,v in expected.items()):raise ValueError('original gate-stall witness changed')
    src,data,before=qualified.sources(project,immediate_report,owned_report,request_report,run)
    prior=candidate.base.derive();current=candidate.derive()
    if {p for p in current if current[p]!=prior[p]}!={candidate.GUARD}:
        raise ValueError('only exact reviewed raw-reference gate may change')
    target=run/'rocev2_shared_protected_responder.v'
    if src.count(target)!=1 or target.read_text()!=prior[candidate.GUARD]:
        raise ValueError('exact qualified single protected native guard required')
    target.write_text(current[candidate.GUARD])
    before.update({str(p.relative_to(ROOT)):digest(p)for p in [target,Path(__file__).resolve(),
        Path(candidate.__file__).resolve(),DIAGNOSTIC,UNIT,FAILED]})
    return src,data,before
