# SPDX-License-Identifier: BSD-2-Clause-Views
"""Select one actual complete128-byte native requester/responder hierarchy.

Retain legacy delivery definitions but replace the one active native HLS and
the actual native parents/leaves. No behavioral HLS or second MR/PTE domain.
This source selection alone proves neither runtime nor driver/board timing.
"""
import json
from pathlib import Path
import sys
import atomic_native_full_sources as old
import derive_atomic128_native as candidate

ROOT=old.ROOT;digest=old.digest


def sources(project,immediate_report,owned_report,request_report,run):
    src,data,before=old.sources(project,immediate_report,owned_report,run)
    derived=candidate.derive()
    for original,text in derived.items():
        name='rocev2_shared_protected_responder.v'if original==candidate.base.rx.stage.authority.base.responder.ORIGINAL else original.name
        p=run/name
        if p not in src:
            if src.count(original)!=1:raise ValueError('one actual source required for '+name)
            src.remove(original);src.append(p)
        p.write_text(text);before[str(p.relative_to(ROOT))]=digest(p)
    previous=json.loads(owned_report.read_text())
    raw=ROOT/previous['directory']/'project/solution1/syn/verilog'
    old_rtl={raw/n for n in previous['generated_sha256']if n.endswith('.v')}
    if not old_rtl.issubset(src):raise ValueError('prior active native HLS selection changed')
    src=[p for p in src if p not in old_rtl];data=[p for p in data if p.parent!=raw]
    # Keep exact provenance of inputs actually inspected above, including old
    # generation evidence, but do not describe old raw RTL as selected active RTL.
    request=json.loads(request_report.read_text())
    if not request.get('pass_test')or request.get('HLS_top')!='rocev2_native_atomic_request_top':
        raise ValueError('actual completed matching requester HLS required')
    for n,h in request['source_sha256'].items():
        if digest(ROOT/n)!=h:raise ValueError('requester HLS source changed: '+n)
    raw=ROOT/request['directory']/'project/solution1/syn/verilog'
    for n,h in request['generated_sha256'].items():
        if digest(raw/n)!=h:raise ValueError('requester HLS RTL changed: '+n)
    src+=[raw/n for n in request['generated_sha256']if n.endswith('.v')]
    data+=[raw/n for n in request['generated_sha256']if n.endswith('.dat')]
    src=list(dict.fromkeys(src));data=list(dict.fromkeys(data))
    helpers=[Path(m.__file__).resolve()for m in list(sys.modules.values())if getattr(m,'__file__',None)and
        (Path(m.__file__).resolve().is_relative_to(ROOT/'rdma/rnic/fpga')or
         Path(m.__file__).resolve().is_relative_to(ROOT/'rdma/rnic/tests'))]
    before.update({str(p.relative_to(ROOT)):digest(p)for p in [*src,*data,*helpers,request_report]})
    return src,data,before
