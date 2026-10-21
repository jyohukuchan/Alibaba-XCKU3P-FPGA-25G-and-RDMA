# SPDX-License-Identifier: BSD-2-Clause-Views
"""Explicit private large READ admission in the actual coordinated graph.

Keep all lifetime/MSN/RX/memory/HLS parent gates; require real codec/MR/
HLS-SQ/register-CQ evidence. No default/kernel/provider/native runtime claim.
"""
import json
from pathlib import Path
import sys
import segmented_read_lifetime_native_sources as parent
import derive_segmented_read_profile as candidate

ROOT=parent.ROOT;digest=parent.digest;HLS=parent.HLS
PREFIX=ROOT/'results/2026-10-18'
EVIDENCE={
 'codec':PREFIX/'rocev2-rnic-segmented-read-wqe-001.json',
 'admission':PREFIX/'rocev2-rnic-segmented-read-admission-001.json',
 'HLS_SQ':PREFIX/'rocev2-rnic-segmented-read-hls-sq-001.json',
 'profile':PREFIX/'rocev2-rnic-segmented-read-profile-002.json'}


def sources(project,immediate_report,owned_report,request_report,run):
    for name,p in EVIDENCE.items():
        r=json.loads(p.read_text())
        if not r.get('pass_test')or not r.get('source_unchanged'):raise ValueError('passing current READ '+name+' evidence required')
        if name=='codec'and(r.get('methods'),r.get('large_READ_max_bytes'))!=(20,1048576):raise ValueError('actual C128 full-range READ codec required')
        if name=='admission'and((r.get('methods'),r.get('cases'))!=(11,26)or not r.get('actual_MR_table')):raise ValueError('real full-range MR admission required')
        if name=='HLS_SQ'and(r.get('methods'),r.get('cases'))!=(8,21):raise ValueError('actual owner-before-HLS-SQ cases required')
        if name=='profile'and((r.get('RNC_features'),r.get('CQC_features'))!=(16383,63)or len(r['tests'])!=27):raise ValueError('exact actual distinct register/CQ profile required')
        parent.verify_mapping(r['source_sha256'])
        if 'artifact_sha256'in r:parent.verify_mapping(r['artifact_sha256'])
        for items in r.get('tests',{}).values():
            for item in items if isinstance(items,list)else[items]:
                if not item.get('pass_test'):raise ValueError('every READ '+name+' case must pass')
                if 'artifact_sha256'in item:parent.verify_mapping(item['artifact_sha256'])
    src,data,before=parent.sources(project,immediate_report,owned_report,request_report,run)
    prior=candidate.parent.derive();new=candidate.derive()
    changed={p.name for p in new if new[p]!=prior[p]}
    if changed!={'rocev2_wqe_admission.v','rocev2_wqe_hls_sq.v','rocev2_control_regs.v','rocev2_cq_mmio.v'}:
        raise ValueError('only explicit READ admission/identity/CQ may change')
    for p in new:
        if p.name not in changed:continue
        target=run/p.name
        if target not in src or target.read_text()!=prior[p]:raise ValueError('exact qualified READ lifetime parent required:'+p.name)
        target.write_text(new[p])
    helpers=[Path(m.__file__).resolve()for m in list(sys.modules.values())if getattr(m,'__file__',None)and
        (Path(m.__file__).resolve().is_relative_to(ROOT/'rdma/rnic/fpga')or Path(m.__file__).resolve().is_relative_to(ROOT/'rdma/rnic/tests'))]
    before.update({str(p.relative_to(ROOT)):digest(p)for p in [*src,*helpers,*EVIDENCE.values()]})
    return src,data,before
