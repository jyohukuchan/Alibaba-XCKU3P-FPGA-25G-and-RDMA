# SPDX-License-Identifier: BSD-2-Clause-Views
"""Select real zero-RQ HLS in ONE complete Atomic-access native hierarchy.

Parent Atomic generation remains inspected provenance, never selected active
RTL. Full source/frozen/generated hashes are checked before using zero HLS.
No fake HLS or duplicated native MR/PTE/PSN/MSN domain is introduced.
"""
import json
from pathlib import Path
import sys
import atomic_access_native_sources as old
import derive_zero_rq_native as candidate

ROOT=old.ROOT;digest=old.digest
PARENT_REQUEST=ROOT/'results/2026-10-18/rocev2-rnic-atomic-request-synth-001.json'


def sources(project,immediate_report,owned_report,request_report,run):
    src,data,before=old.sources(project,immediate_report,owned_report,PARENT_REQUEST,run)
    for original,text in candidate.derive().items():
        name='rocev2_zero_ipv4_icrc.v'if original==candidate.ICRC else \
            'rocev2_shared_protected_responder.v'if original==candidate.PROTECTED else original.name
        p=run/name
        if original==candidate.ICRC:
            if src.count(original)!=1 or p in src:raise ValueError('retain one immutable original integrity definition')
            src.append(p)
        elif p not in src:
            if src.count(original)!=1:raise ValueError('one actual zero source required: '+name)
            src.remove(original);src.append(p)
        p.write_text(text);before[str(p.relative_to(ROOT))]=digest(p)
    parent=json.loads(PARENT_REQUEST.read_text())
    previous=ROOT/parent['directory']/'project/solution1/syn/verilog'
    old_rtl={previous/n for n in parent['generated_sha256']if n.endswith('.v')}
    if not old_rtl.issubset(src):raise ValueError('parent active requester selection changed')
    src=[p for p in src if p not in old_rtl];data=[p for p in data if p.parent!=previous]
    report=json.loads(request_report.read_text())
    if not all(report.get(n)for n in ['pass_test','zero_length_requester','zero_RQ_SEND_and_Immediate','source_and_frozen_inputs_unchanged'])or \
       report.get('HLS_top')!='rocev2_native_zero_rq_top':
        raise ValueError('fresh actual zero requester HLS generation required')
    if (float(report['target_clock_period']),float(report['clock_uncertainty']),report['MAX_QPS'],report['metadata_entries'])!=(4.0,1.08,8,2000):
        raise ValueError('original clock/uncertainty/capacity changed')
    raw=ROOT/report['directory']/'project/solution1/syn/verilog'
    for field,base in [('source_sha256',ROOT),('frozen_sha256',ROOT/report['directory']/'inputs'),('generated_sha256',raw)]:
        for n,h in report[field].items():
            if digest(base/n)!=h:raise ValueError('changed zero HLS '+field+': '+n)
    src+=[raw/n for n in report['generated_sha256']if n.endswith('.v')]
    data+=[raw/n for n in report['generated_sha256']if n.endswith('.dat')]
    src=list(dict.fromkeys([*src,*candidate.EXTRA]));data=list(dict.fromkeys(data))
    helpers=[Path(m.__file__).resolve()for m in list(sys.modules.values())if getattr(m,'__file__',None)and
        (Path(m.__file__).resolve().is_relative_to(ROOT/'rdma/rnic/fpga')or
         Path(m.__file__).resolve().is_relative_to(ROOT/'rdma/rnic/tests'))]
    before.update({str(p.relative_to(ROOT)):digest(p)for p in [*src,*data,*helpers,request_report]})
    return src,data,before
