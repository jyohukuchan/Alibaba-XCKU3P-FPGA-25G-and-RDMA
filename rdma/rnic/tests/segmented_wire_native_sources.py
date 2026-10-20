# SPDX-License-Identifier: BSD-2-Clause-Views
"""Select the coordinated segmented-wire candidate in ONE actual native graph.

Requires current component evidence; never changes default selections or
advertises native large-transfer/standard API/hardware/timing qualification.
"""
import json
from pathlib import Path
import sys
import segmented_executor_native_sources as old
import derive_segmented_wire as candidate

ROOT=old.ROOT;digest=old.digest
UNIT=ROOT/'results/2026-10-18/rocev2-rnic-segmented-wire-004.json'


def sources(project,immediate_report,owned_report,request_report,run):
    unit=json.loads(UNIT.read_text())
    if not unit.get('pass_test')or unit.get('methods')!=5 or sum(map(len,unit.get('tests',{}).values()))!=10:
        raise ValueError('matched actual segmented packet-owner/cache/MAC composition evidence required')
    for cases in unit['tests'].values():
        for case in cases:
            if not case.get('pass_test'):raise ValueError('every segmented case must pass')
            for field in ['source_sha256','artifact_sha256']:
                for n,h in case[field].items():
                    if digest(ROOT/n)!=h:raise ValueError('tested segmented inputs changed:'+n)
    src,data,before=old.sources(project,immediate_report,owned_report,request_report,run)
    for original,text in candidate.derive().items():
        name='rocev2_zero_ipv4_icrc.v'if original==candidate.parent.parent.parent.ICRC else \
            'rocev2_shared_protected_responder.v'if original==candidate.parent.parent.parent.PROTECTED else original.name
        p=run/name
        if p not in src:raise ValueError('one exact existing native substitution required:'+name)
        p.write_text(text);before[str(p.relative_to(ROOT))]=digest(p)
    helpers=[Path(m.__file__).resolve()for m in list(sys.modules.values())if getattr(m,'__file__',None)and
        (Path(m.__file__).resolve().is_relative_to(ROOT/'rdma/rnic/fpga')or
         Path(m.__file__).resolve().is_relative_to(ROOT/'rdma/rnic/tests'))]
    before.update({str(p.relative_to(ROOT)):digest(p)for p in [*src,*data,*helpers,UNIT]})
    return src,data,before
