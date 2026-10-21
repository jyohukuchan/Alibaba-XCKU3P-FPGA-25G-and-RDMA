# SPDX-License-Identifier: BSD-2-Clause-Views
"""Qualified READ graph with an effective-route-preserving QP_TX observer.

All exact previous HLS/MSN/RX/MR/admission/lifetime/profile gates remain.
Require actual-controller reproduction and all corrected configuration cases;
change only the controlled-responder route observer, never its guards/child.
"""
import json
from pathlib import Path
import sys
import segmented_read_profile_native_sources as parent
import derive_segmented_read_route as candidate

ROOT=parent.ROOT;digest=parent.digest;HLS=parent.HLS
UNIT=ROOT/'results/2026-10-18/rocev2-rnic-segmented-read-config-route-003.json'


def sources(project,immediate_report,owned_report,request_report,run):
    unit=json.loads(UNIT.read_text())
    if not unit.get('pass_test')or unit.get('cases')!=6 or not unit.get('source_unchanged'):
        raise ValueError('all six unchanged-source configuration-route cases required')
    if not all(unit.get(n)for n in ['actual_MR_controller','actual_MR_and_PTE','exact_native_route_observer',
        'actual_MSN_predictor','old_native_failure_preserved','accepted_TX_only_preserves_effective_route']):
        raise ValueError('actual accepted configuration/observer/MSN evidence required')
    if unit.get('SQC_identity_supplied')or unit.get('WRs_issued')!=0:
        raise ValueError('isolated no-invented-identity configuration proof required')
    parent.parent.verify_mapping(unit['source_sha256'])
    parent.parent.verify_mapping(unit['artifact_sha256'])
    if set(unit['tests'])!={str(n)for n in range(6)}or not all(c.get('pass_test')for c in unit['tests'].values()):
        raise ValueError('every original/corrected route case required')
    old=unit['tests']['0']['summary'];fixed=unit['tests']['1']['summary']
    if (old['MSN_fault'],old['MSN_fault_code'],old['observed_peer'],old['actual_QP_TX_configs'])!=(1,162,0,1):
        raise ValueError('original accepted-QP_TX route-erasure fault must remain reproduced')
    if (fixed['MSN_fault'],fixed['MSN_fault_code'],fixed['observed_peer'],fixed['actual_QP_TX_configs'],fixed['applied_TX_PSN'])!=(0,0,196,1,0x89abcd):
        raise ValueError('same real command must preserve route and still accept TX PSN')
    src,data,before=parent.sources(project,immediate_report,owned_report,request_report,run)
    prior=candidate.parent.derive();new=candidate.derive()
    changed={p.name for p in new if new[p]!=prior[p]}
    if changed!={'rocev2_controlled_responder.v'}:raise ValueError('only accepted-route observer may change')
    p=candidate.RTL/'rocev2_controlled_responder.v';target=run/p.name
    if target not in src or target.read_text()!=prior[p]:raise ValueError('exact qualified READ profile parent required')
    target.write_text(new[p])
    helpers=[Path(m.__file__).resolve()for m in list(sys.modules.values())if getattr(m,'__file__',None)and
        (Path(m.__file__).resolve().is_relative_to(ROOT/'rdma/rnic/fpga')or Path(m.__file__).resolve().is_relative_to(ROOT/'rdma/rnic/tests'))]
    before.update({str(p.relative_to(ROOT)):digest(p)for p in [*src,*helpers,UNIT]})
    return src,data,before
