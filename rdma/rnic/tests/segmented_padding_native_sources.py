# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual segmented native graph with exact pre-padded LAST contract.

Require independent padding/ICRC component evidence plus every parent
source/HLS/owner proof. Only one private integrity-wrapper selection changes.
"""
import json
from pathlib import Path
import sys
import segmented_wire_native_sources as old
import derive_segmented_padding as candidate

ROOT=old.ROOT;digest=old.digest
UNIT=ROOT/'results/2026-10-18/rocev2-rnic-segmented-padding-002.json'


def sources(project,immediate_report,owned_report,request_report,run):
    unit=json.loads(UNIT.read_text())
    if not unit.get('pass_test')or unit.get('methods')!=6 or len(unit.get('tests',{}))!=6 or \
       not unit.get('all_three_original_padding_tests_retained')or not unit.get('original_padding_and_integrity_unchanged'):
        raise ValueError('all original padding cases and strict new LAST/integrity evidence required')
    for mapping in [unit['source_sha256'],*[case['artifact_sha256']for cases in unit['tests'].values()for case in cases]]:
        for n,h in mapping.items():
            if digest(ROOT/n)!=h:raise ValueError('padding/ICRC component inputs changed:'+n)
    src,data,before=old.sources(project,immediate_report,owned_report,request_report,run)
    text=candidate.derive()[candidate.TRANSPORT]
    transport=run/candidate.TRANSPORT.name
    if transport not in src:raise ValueError('one actual private requester integrity wrapper required')
    transport.write_text(text)
    src=list(dict.fromkeys([*src,candidate.PAD]))
    helpers=[Path(m.__file__).resolve()for m in list(sys.modules.values())if getattr(m,'__file__',None)and
        (Path(m.__file__).resolve().is_relative_to(ROOT/'rdma/rnic/fpga')or
         Path(m.__file__).resolve().is_relative_to(ROOT/'rdma/rnic/tests'))]
    before.update({str(p.relative_to(ROOT)):digest(p)for p in [*src,*data,*helpers,UNIT]})
    return src,data,before
