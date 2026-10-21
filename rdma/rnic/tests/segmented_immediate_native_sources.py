# SPDX-License-Identifier: BSD-2-Clause-Views
"""Exact large-Immediate HLS/owner/MR/wire/CQ candidate over qualified READ.

Keep every parent source/evidence gate, then substitute only14 explicit
derived leaves and the exact freshly generated HLS cohort. No default,
kernel/provider capability, native runtime or original timing claim.
"""
import hashlib
import json
from pathlib import Path
import sys
import segmented_read_command_queue_native_sources as parent
import derive_segmented_immediate as candidate

ROOT=parent.ROOT;digest=parent.digest;HLS='rocev2_native_segmented_immediate_top'
PREFIX=ROOT/'results/2026-10-18'
READ_HLS=PREFIX/'rocev2-rnic-segmented-read-generated-hls-001.json'
EVIDENCE={
 'codec':PREFIX/'rocev2-rnic-segmented-immediate-wqe-003.json',
 'wire':PREFIX/'rocev2-rnic-segmented-immediate-wire-001.json',
 'source':PREFIX/'rocev2-rnic-segmented-immediate-source-002.json',
 'admission':PREFIX/'rocev2-rnic-segmented-immediate-admission-002.json',
 'profile':PREFIX/'rocev2-rnic-segmented-immediate-profile-001.json',
 'padding':PREFIX/'rocev2-rnic-segmented-immediate-padding-001.json'}
CHANGED={n+'.v'for n in ['rocev2_wqe_lifetime','rocev2_wqe_mac_tx','rocev2_wqe_tx_lifetime',
 'rocev2_wqe_response_guard','rocev2_wqe_replay','rocev2_shared_hls_transport','rocev2_integrity_transport',
 'rocev2_wqe_admission','rocev2_wqe_hls_sq','rocev2_cq_mmio','rocev2_control_regs',
 'rocev2_segmented_executor_mux','rocev2_segmented_source_executor','rocev2_segmented_tx_padding']}


def verify(mapping,base=ROOT):
    for n,h in mapping.items():
        q=Path(n);q=q if q.is_absolute()else base/q
        if digest(q)!=h:raise ValueError('qualified Immediate input/artifact changed:'+str(q))


def verify_nested(node):
    if isinstance(node,dict):
        for k,v in node.items():
            if k in ['source_sha256','artifact_sha256','all_run_artifact_sha256','RAM_artifact_sha256','artifacts']and isinstance(v,dict):verify(v)
            elif isinstance(v,(dict,list)):verify_nested(v)
    elif isinstance(node,list):
        for value in node:verify_nested(value)


def sources(project,immediate_report,owned_report,request_report,run):
    records={n:json.loads(p.read_text())for n,p in EVIDENCE.items()}
    for name,r in records.items():
        if not r.get('pass_test')or not r.get('source_unchanged'):raise ValueError('current complete Immediate '+name+' proof required')
        verify_nested(r)
    if (records['codec'].get('methods'),records['codec'].get('large_Immediate_max_bytes'))!=(26,1048576):raise ValueError('actual full-range C128 Immediate codec required')
    if records['wire'].get('methods')!=8 or sum(map(len,records['wire']['tests'].values()))!=17:raise ValueError('all17 actual wire/whole-owner/MAC cases required')
    if records['source'].get('methods')!=10 or not records['source'].get('all7_prior_methods_retained'):raise ValueError('old/new real bounded source-child cases required')
    if records['admission'].get('methods')!=25 or not records['admission'].get('actual_MR_table')or not records['admission'].get('actual_C128_Immediate_codec'):raise ValueError('actual C/local-MR/owner-before-HLS proof required')
    if (records['profile'].get('RNC_features'),records['profile'].get('CQC_features'))!=(32767,127)or len(records['profile']['tests'])!=27:raise ValueError('exact27 actual register/CQ cases required')
    if not records['padding'].get('all_prior_padding_methods_retained'):raise ValueError('all original and new pad/ICRC cases required')

    src,data,before=parent.sources(project,immediate_report,owned_report,READ_HLS,run)
    prior=candidate.parent.derive();new=candidate.derive()
    changed={p.name for p in new if p not in prior or new[p]!=prior[p]}
    if changed!=CHANGED:raise ValueError('only explicit coordinated Immediate leaves may change:'+str(changed))
    if hashlib.sha256(new[candidate.PAD].encode()).hexdigest()!=records['padding']['tested_padding_sha256']:
        raise ValueError('actual tested pad body differs from native selection')
    for p in new:
        if p.name not in changed:continue
        matching=[q for q in src if q.name==p.name]
        if len(matching)!=1:raise ValueError('exact single qualified parent leaf required:'+p.name)
        previous=matching[0];expected=prior.get(p,p.read_text()if p.is_file()else None)
        if expected is None or previous.read_text()!=expected:raise ValueError('qualified parent body changed:'+p.name)
        target=run/p.name;target.write_text(new[p]);src=[target if q==previous else q for q in src]
    previous_hls=json.loads(READ_HLS.read_text());previous_raw=ROOT/previous_hls['directory']/'project/solution1/syn/verilog'
    old_rtl={previous_raw/n for n in previous_hls['generated_sha256']if n.endswith('.v')}
    if not old_rtl.issubset(src):raise ValueError('qualified READ generated selection missing')
    src=[q for q in src if q not in old_rtl];data=[q for q in data if q.parent!=previous_raw]
    hls=json.loads(request_report.read_text())
    if hls.get('HLS_top')!=HLS or not all(hls.get(n)for n in ['pass_test','source_and_frozen_inputs_unchanged',
        'wrapper_and_builder_unchanged','true_segmented_Immediate_LAST_only'])or hls.get('Immediate_max_bytes')!=1048576:
        raise ValueError('exact actual new Immediate-generated HLS required')
    if(float(hls['target_clock_period']),float(hls['clock_uncertainty']),hls['MAX_QPS'],hls['metadata_entries'])!=(4.0,1.08,8,2000):
        raise ValueError('original clock/geometry gates changed')
    raw=ROOT/hls['directory']/'project/solution1/syn/verilog'
    verify(hls['source_sha256']);verify(hls['frozen_sha256'],ROOT/hls['directory']/'inputs');verify(hls['generated_sha256'],raw)
    src+=[raw/n for n in hls['generated_sha256']if n.endswith('.v')]
    data+=[raw/n for n in hls['generated_sha256']if n.endswith('.dat')]
    src=list(dict.fromkeys(src));data=list(dict.fromkeys(data))
    helpers=[Path(m.__file__).resolve()for m in list(sys.modules.values())if getattr(m,'__file__',None)and
        (Path(m.__file__).resolve().is_relative_to(ROOT/'rdma/rnic/fpga')or Path(m.__file__).resolve().is_relative_to(ROOT/'rdma/rnic/tests'))]
    before.update({str(q.relative_to(ROOT)):digest(q)for q in [*src,*data,*helpers,*EVIDENCE.values(),READ_HLS,request_report]})
    return src,data,before
