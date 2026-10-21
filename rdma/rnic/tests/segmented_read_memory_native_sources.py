# SPDX-License-Identifier: BSD-2-Clause-Views
"""New actual READ-memory routing and exact new HLS in the complete graph.

Require every qualified parent source/HLS/profile gate and new mux evidence.
Large READ admission stays CLOSED pending protected RX/MSN/whole-WR lifetime
integration; no runtime/Linux/physical/timing qualification is implied.
"""
import json
from pathlib import Path
import sys
import segmented_profile_native_sources as old
import derive_segmented_read_memory_native as candidate

ROOT=old.ROOT;digest=old.digest
PARENT_HLS=ROOT/'results/2026-10-18/rocev2-rnic-segmented-request-synth-001.json'
UNIT=ROOT/'results/2026-10-18/rocev2-rnic-segmented-read-memory-mux-003.json'
HLS='rocev2_native_segmented_read_top'


def sources(project,immediate_report,owned_report,request_report,run):
    unit=json.loads(UNIT.read_text())
    if not unit.get('pass_test')or(unit.get('methods'),unit.get('cases'))!=(9,17)or not unit.get('all11_original_mux_cases_retained')or not unit.get('actual_common_physical_command_nonce'):
        raise ValueError('all actual old/new routes and common physical nonce evidence required')
    mappings=[unit['source_sha256']]
    for cases in unit['tests'].values():
        for case in cases:
            if not case.get('pass_test'):raise ValueError('all route cases required')
            mappings.extend([case['artifact_sha256'],case['RAM_artifact_sha256']])
    for mapping in mappings:
        for n,h in mapping.items():
            q=Path(n);q=q if q.is_absolute()else ROOT/q
            if digest(q)!=h:raise ValueError('tested route input changed:'+n)
    src,data,before=old.sources(project,immediate_report,owned_report,PARENT_HLS,run)
    prior=candidate.parent.derive();new=candidate.derive()
    changed={p.name for p in new if p not in prior or prior[p]!=new[p]}
    required={'rocev2_native_rnic_endpoint.v','rocev2_integrity_transport.v',candidate.MUX.name,candidate.UNPAD.name,candidate.CHILD_UNPAD.name}
    if changed!=required:raise ValueError('only exact new route/root/HLS selections may change:'+str(changed))
    for p in new:
        if p.name not in changed:continue
        target=run/p.name
        if target not in src:
            if p not in [candidate.MUX,candidate.UNPAD,candidate.CHILD_UNPAD]:raise ValueError('missing parent substitution:'+p.name)
            src.append(target)
        else:
            if target.read_text()!=prior[p]:raise ValueError('actual qualified parent required:'+p.name)
        target.write_text(new[p])
    parent=json.loads(PARENT_HLS.read_text());previous=ROOT/parent['directory']/'project/solution1/syn/verilog'
    prior_rtl={previous/n for n in parent['generated_sha256']if n.endswith('.v')}
    if not prior_rtl.issubset(src):raise ValueError('parent active generated selection changed')
    src=[p for p in src if p not in prior_rtl];data=[p for p in data if p.parent!=previous]
    hls=json.loads(request_report.read_text())
    if hls.get('HLS_top')!=HLS or not all(hls.get(n)for n in ['pass_test','source_and_frozen_inputs_unchanged',
        'wrapper_and_builder_unchanged','true_segmented_READ_wire','one_full_WR_receipt'])or hls.get('large_READ_max_bytes')!=1048576:
        raise ValueError('exact actual READ-generated HLS required')
    if(float(hls['target_clock_period']),float(hls['clock_uncertainty']),hls['MAX_QPS'],hls['metadata_entries'])!=(4.0,1.08,8,2000):
        raise ValueError('original clock/geometry changed')
    raw=ROOT/hls['directory']/'project/solution1/syn/verilog'
    for field,base in [('source_sha256',ROOT),('frozen_sha256',ROOT/hls['directory']/'inputs'),('generated_sha256',raw)]:
        for n,h in hls[field].items():
            if digest(base/n)!=h:raise ValueError('actual READ HLS input changed:'+n)
    src+=[raw/n for n in hls['generated_sha256']if n.endswith('.v')]
    data+=[raw/n for n in hls['generated_sha256']if n.endswith('.dat')]
    src=list(dict.fromkeys([*src,*candidate.EXTRA]));data=list(dict.fromkeys(data))
    helpers=[Path(m.__file__).resolve()for m in list(sys.modules.values())if getattr(m,'__file__',None)and
        (Path(m.__file__).resolve().is_relative_to(ROOT/'rdma/rnic/fpga')or Path(m.__file__).resolve().is_relative_to(ROOT/'rdma/rnic/tests'))]
    before.update({str(p.relative_to(ROOT)):digest(p)for p in [*src,*data,*helpers,UNIT,PARENT_HLS,request_report]})
    return src,data,before
