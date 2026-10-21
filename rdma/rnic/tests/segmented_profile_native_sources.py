# SPDX-License-Identifier: BSD-2-Clause-Views
"""Private8191/31 graph, same large data/owner paths plus tested exact identity.

Require four-state register/CQ component evidence and every parent graph/HLS
proof. Exactly two identity-only substitutions; no default selection change.
Not itself native runtime/Linux/physical/timing qualification.
"""
import json
from pathlib import Path
import sys
import segmented_padding_native_sources as old
import derive_segmented_profile as candidate

ROOT=old.ROOT;digest=old.digest
UNIT=ROOT/'results/2026-10-18/rocev2-rnic-segmented-profile-rtl-001.json'


def sources(project,immediate_report,owned_report,request_report,run):
    unit=json.loads(UNIT.read_text())
    if not unit.get('pass_test')or not unit.get('four_state')or len(unit.get('tests',{}))!=27 or \
       (unit.get('RNC_features'),unit.get('CQC_features'),unit.get('owner_bits'))!=(8191,31,748):
        raise ValueError('matched exact identity/full-owner/dependency RTL proof required')
    for mapping in [unit['source_sha256'],unit['artifact_sha256']]:
        for n,h in mapping.items():
            if digest(ROOT/n)!=h:raise ValueError('profile component inputs changed:'+n)
    src,data,before=old.sources(project,immediate_report,owned_report,request_report,run)
    parent=candidate.parent.derive();new=candidate.derive()
    changes=[p for p in new if new[p]!=parent[p]]
    if {p.name for p in changes}!={'rocev2_control_regs.v','rocev2_cq_mmio.v'}:
        raise ValueError('only two exact profile identity leaves may change')
    for p in changes:
        target=run/p.name
        if target not in src or target.read_text()!=parent[p]:raise ValueError('matched parent leaf required:'+p.name)
        target.write_text(new[p])
    helpers=[Path(m.__file__).resolve()for m in list(sys.modules.values())if getattr(m,'__file__',None)and
        (Path(m.__file__).resolve().is_relative_to(ROOT/'rdma/rnic/fpga')or
         Path(m.__file__).resolve().is_relative_to(ROOT/'rdma/rnic/tests'))]
    before.update({str(p.relative_to(ROOT)):digest(p)for p in [*src,*data,*helpers,UNIT]})
    return src,data,before
