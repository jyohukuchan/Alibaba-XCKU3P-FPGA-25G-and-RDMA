# SPDX-License-Identifier: BSD-2-Clause-Views
"""Exact checked READ graph plus owner-checked two-command lookahead.

Retain all prior native/HLS/MSN/MR/RX/lifetime/admission/route gates and all17
previous mux cases. Only one mux leaf changes; no default/timing/runtime claim.
"""
import json
from pathlib import Path
import sys
import segmented_read_route_native_sources as parent
import derive_segmented_read_command_queue as candidate

ROOT=parent.ROOT;digest=parent.digest;HLS=parent.HLS
UNIT=ROOT/'results/2026-10-18/rocev2-rnic-segmented-read-command-queue-001.json'


def sources(project,immediate_report,owned_report,request_report,run):
    unit=json.loads(UNIT.read_text())
    if not unit.get('pass_test')or not unit.get('source_unchanged')or (unit.get('methods'),unit.get('cases'))!=(12,23):
        raise ValueError('all23 actual queue/mux cases required')
    if not all(unit.get(n)for n in ['all17_prior_mux_cases_retained','actual_common_physical_command_nonce',
        'modeled_HLS_command_data_dependency','original_child_and_unpad_unchanged'])or unit.get('READ_command_queue_depth')!=2:
        raise ValueError('original child/nonce/CQ and exact bounded metadata proof required')
    verify=parent.parent.parent.verify_mapping
    verify(unit['source_sha256'])
    for cases in unit['tests'].values():
        for case in cases:
            if not case.get('pass_test'):raise ValueError('every queue and old mux case must pass')
            verify(case['artifact_sha256']);verify(case['RAM_artifact_sha256'])
    src,data,before=parent.sources(project,immediate_report,owned_report,request_report,run)
    prior=candidate.parent.derive();new=candidate.derive()
    if {p.name for p in new if new[p]!=prior[p]}!={candidate.MUX.name}:
        raise ValueError('only owner-checked READ metadata mux may change')
    target=run/candidate.MUX.name
    if target not in src or target.read_text()!=prior[candidate.MUX]:raise ValueError('exact qualified route parent required')
    target.write_text(new[candidate.MUX])
    helpers=[Path(m.__file__).resolve()for m in list(sys.modules.values())if getattr(m,'__file__',None)and
        (Path(m.__file__).resolve().is_relative_to(ROOT/'rdma/rnic/fpga')or Path(m.__file__).resolve().is_relative_to(ROOT/'rdma/rnic/tests'))]
    before.update({str(p.relative_to(ROOT)):digest(p)for p in [*src,*helpers,UNIT]})
    return src,data,before
