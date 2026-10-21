# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual accepted-QP/SQC remote-MSN observer in the complete READ-memory graph.

Keep every qualified parent HLS/profile/memory gate. This is wiring only;
protected segmented RX/whole-READ lifetime and native runtime remain separate.
"""
import json
from pathlib import Path
import sys
import segmented_read_memory_native_sources as parent
import derive_expected_remote_msn_native as candidate

ROOT=parent.ROOT;digest=parent.digest;HLS=parent.HLS
UNIT=ROOT/'results/2026-10-18/rocev2-rnic-expected-remote-msn-007.json'


def sources(project,immediate_report,owned_report,request_report,run):
    unit=json.loads(UNIT.read_text())
    if not unit.get('pass_test')or(unit.get('methods'),unit.get('cases'))!=(7,12)or not unit.get('actual_SQC_mailbox_and_owner_lookup'):
        raise ValueError('genuine SQC/MSN component evidence required')
    if 'test_two_actual_SQCs_interleave_without_route_reconfiguration'not in unit['tests']:
        raise ValueError('actual two-SQC interleaving without route reconfiguration required')
    maps=[unit['source_sha256']]
    for cases in unit['tests'].values():
        for case in cases:
            if not case.get('pass_test'):raise ValueError('all real-SQC MSN cases required')
            maps.extend([case['artifact_sha256'],case['RAM_artifact_sha256']])
    for mapping in maps:
        for n,h in mapping.items():
            q=Path(n);q=q if q.is_absolute()else ROOT/q
            if digest(q)!=h:raise ValueError('qualified MSN binding changed:'+n)
    src,data,before=parent.sources(project,immediate_report,owned_report,request_report,run)
    prior=candidate.parent.derive();new=candidate.derive()
    changed={p.name for p in new if p not in prior or prior[p]!=new[p]}
    required={n+'.v'for n in ['rocev2_controlled_responder','rocev2_dual_ethernet_endpoint',
        'rocev2_native_endpoint','rocev2_native_sq_endpoint','rocev2_native_rnic_endpoint','rocev2_sq_control_regs']}
    if changed!=required:raise ValueError('only actual MSN configuration/query/lifetime hooks may change:'+str(changed))
    for p in new:
        if p.name not in changed:continue
        target=run/p.name
        if target not in src or target.read_text()!=prior[p]:raise ValueError('exact qualified READ-memory parent required:'+p.name)
        target.write_text(new[p])
    src=list(dict.fromkeys([*src,candidate.PRED]))
    helpers=[Path(m.__file__).resolve()for m in list(sys.modules.values())if getattr(m,'__file__',None)and
        (Path(m.__file__).resolve().is_relative_to(ROOT/'rdma/rnic/fpga')or Path(m.__file__).resolve().is_relative_to(ROOT/'rdma/rnic/tests'))]
    before.update({str(p.relative_to(ROOT)):digest(p)for p in [*src,*helpers,UNIT]})
    return src,data,before
