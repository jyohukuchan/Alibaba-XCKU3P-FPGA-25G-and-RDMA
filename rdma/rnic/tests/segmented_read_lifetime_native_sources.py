# SPDX-License-Identifier: BSD-2-Clause-Views
"""Full private READ RX/MSN/memory/lifetime wiring; admission stays closed.

Require all original native/HLS/MSN/memory, exact protected RX and new whole
READ lifetime evidence. No default, native runtime, Linux or timing claim.
"""
import json
from pathlib import Path
import sys
import expected_remote_msn_native_sources as parent
import derive_segmented_read_lifetime as candidate

ROOT=parent.ROOT;digest=parent.digest;HLS=parent.HLS
UNIT=ROOT/'results/2026-10-18/rocev2-rnic-segmented-read-lifetime-002.json'
RX=ROOT/'results/2026-10-18/rocev2-rnic-segmented-read-response-002.json'


def verify_mapping(mapping):
    for n,h in mapping.items():
        q=Path(n);q=q if q.is_absolute()else ROOT/q
        if digest(q)!=h:raise ValueError('qualified READ lifetime/RX binding changed:'+n)


def sources(project,immediate_report,owned_report,request_report,run):
    unit=json.loads(UNIT.read_text())
    if not unit.get('pass_test')or(unit.get('methods'),unit.get('cases'))!=(10,29)or not unit.get('all_five_original_segmented_wire_methods_retained'):
        raise ValueError('all original and new actual READ lifetime cases required')
    verify_mapping(unit['source_sha256'])
    for cases in unit['tests'].values():
        for case in cases:
            if not case.get('pass_test'):raise ValueError('failed READ lifetime case')
            for field in ['source_sha256','artifact_sha256']:
                if field in case:verify_mapping(case[field])
    rx=json.loads(RX.read_text())
    if not rx.get('pass_test')or rx.get('methods')!=17 or sum(map(len,rx['tests'].values()))!=60:
        raise ValueError('all exact original protected READ RX cases required')
    for cases in rx['tests'].values():
        for case in cases:
            if not case.get('pass_test'):raise ValueError('failed protected RX case')
            for field in ['source_sha256','artifact_sha256','RAM_artifact_sha256']:
                if field in case:verify_mapping(case[field])
    src,data,before=parent.sources(project,immediate_report,owned_report,request_report,run)
    prior=candidate.parent.derive();new=candidate.derive()
    changed={p.name for p in new if p not in prior or prior[p]!=new[p]}
    required={n+'.v'for n in ['rocev2_wqe_lifetime','rocev2_wqe_tx_lifetime','rocev2_wqe_mac_tx',
        'rocev2_shared_hls_transport','rocev2_wqe_response_guard','rocev2_native_rnic_endpoint']}
    if changed!=required:raise ValueError('only actual READ RX/lifetime/PSN wiring may change:'+str(changed))
    for p in new:
        if p.name not in changed:continue
        target=run/p.name
        if target not in src or target.read_text()!=prior[p]:raise ValueError('exact qualified MSN-memory parent required:'+p.name)
        target.write_text(new[p])
    helpers=[Path(m.__file__).resolve()for m in list(sys.modules.values())if getattr(m,'__file__',None)and
        (Path(m.__file__).resolve().is_relative_to(ROOT/'rdma/rnic/fpga')or Path(m.__file__).resolve().is_relative_to(ROOT/'rdma/rnic/tests'))]
    before.update({str(p.relative_to(ROOT)):digest(p)for p in [*src,*helpers,UNIT,RX]})
    return src,data,before
