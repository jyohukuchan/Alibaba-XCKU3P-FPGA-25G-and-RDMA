# SPDX-License-Identifier: BSD-2-Clause-Views
"""One new-HLS/native graph with actual legacy/retained-source dispatcher.

Large source and atomic CQ fanout are wired; large admission/wire/CQ proof
remain closed. Parent HLS/MR/page/physical-nonce gates stay unchanged.
"""
import json
from pathlib import Path
import sys
import segmented_native_sources as old
import derive_segmented_executor as candidate

ROOT=old.ROOT;digest=old.digest
UNIT=ROOT/'results/2026-10-18/rocev2-rnic-segmented-executor-mux-003.json'


def sources(project,immediate_report,owned_report,request_report,run):
    unit=json.loads(UNIT.read_text())
    if not unit.get('pass_test') or unit.get('methods')!=5 or sum(map(len,unit.get('tests',{}).values()))!=11:
        raise ValueError('actual current dispatcher/source/legacy/nonce unit evidence required')
    for field in ['source_sha256','artifact_sha256']:
        for n,h in unit[field].items():
            if digest(ROOT/n)!=h:raise ValueError('tested dispatcher inputs changed:'+n)
    src,data,before=old.sources(project,immediate_report,owned_report,request_report,run)
    for original,text in candidate.derive().items():
        name='rocev2_zero_ipv4_icrc.v'if original==candidate.parent.parent.ICRC else \
            'rocev2_shared_protected_responder.v'if original==candidate.parent.parent.PROTECTED else original.name
        p=run/name
        if p not in src:
            if original not in [candidate.MUX,candidate.CHILD]:raise ValueError('unexpected missing parent source:'+name)
            src.append(p)
        p.write_text(text);before[str(p.relative_to(ROOT))]=digest(p)
    src=list(dict.fromkeys([*src,*candidate.EXTRA]))
    helpers=[Path(m.__file__).resolve()for m in list(sys.modules.values())if getattr(m,'__file__',None)and
        (Path(m.__file__).resolve().is_relative_to(ROOT/'rdma/rnic/fpga')or
         Path(m.__file__).resolve().is_relative_to(ROOT/'rdma/rnic/tests'))]
    before.update({str(p.relative_to(ROOT)):digest(p)for p in [*src,*helpers,UNIT]})
    return src,data,before
