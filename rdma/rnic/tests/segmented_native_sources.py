# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual new segmented HLS + one complete native/shared physical nonce graph.

Parent zero-service generation is bound provenance, NOT selected active RTL.
No large native memory/wire/CQ or multi-SGE qualification is implied yet.
"""
import json
from pathlib import Path
import sys
import zero_service_native_sources as old
import derive_segmented_native as candidate

ROOT=old.ROOT;digest=old.digest
PARENT=ROOT/'results/2026-10-18/rocev2-rnic-zero-service-synth-001.json'
HLS='rocev2_native_segmented_request_top'


def sources(project,immediate_report,owned_report,request_report,run):
    src,data,before=old.sources(project,immediate_report,owned_report,PARENT,run)
    for original,text in candidate.derive().items():
        name='rocev2_zero_ipv4_icrc.v'if original==candidate.parent.ICRC else \
            'rocev2_shared_protected_responder.v'if original==candidate.parent.PROTECTED else original.name
        p=run/name
        if p not in src:raise ValueError('one exact native derivative required:'+name)
        p.write_text(text);before[str(p.relative_to(ROOT))]=digest(p)
    parent=json.loads(PARENT.read_text());previous=ROOT/parent['directory']/'project/solution1/syn/verilog'
    old_rtl={previous/n for n in parent['generated_sha256']if n.endswith('.v')}
    if not old_rtl.issubset(src):raise ValueError('previous active selection changed')
    src=[p for p in src if p not in old_rtl];data=[p for p in data if p.parent!=previous]
    r=json.loads(request_report.read_text())
    if r.get('HLS_top')!=HLS or not all(r.get(n)for n in
        ['pass_test','source_and_frozen_inputs_unchanged','wrapper_and_builder_unchanged','true_segmented_wire','one_full_WR_receipt'])or \
       r.get('large_WRITE_SEND_max_bytes')!=1048576:
        raise ValueError('actual matched segmented generation required')
    if (float(r['target_clock_period']),float(r['clock_uncertainty']),r['MAX_QPS'],r['metadata_entries'])!=(4.0,1.08,8,2000):
        raise ValueError('original clock/geometry changed')
    raw=ROOT/r['directory']/'project/solution1/syn/verilog'
    for field,base in [('source_sha256',ROOT),('frozen_sha256',ROOT/r['directory']/'inputs'),('generated_sha256',raw)]:
        for n,h in r[field].items():
            if digest(base/n)!=h:raise ValueError('bound segmented generation changed:'+n)
    src+=[raw/n for n in r['generated_sha256']if n.endswith('.v')]
    data+=[raw/n for n in r['generated_sha256']if n.endswith('.dat')]
    src=list(dict.fromkeys([*src,*candidate.EXTRA]));data=list(dict.fromkeys(data))
    helpers=[Path(m.__file__).resolve()for m in list(sys.modules.values())if getattr(m,'__file__',None)and
        (Path(m.__file__).resolve().is_relative_to(ROOT/'rdma/rnic/fpga')or
         Path(m.__file__).resolve().is_relative_to(ROOT/'rdma/rnic/tests'))]
    before.update({str(p.relative_to(ROOT)):digest(p)for p in [*src,*data,*helpers,request_report]})
    return src,data,before
