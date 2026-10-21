# SPDX-License-Identifier: BSD-2-Clause-Views
"""Select exact new RX-generated RTL in the complete guarded native graph.

Retain every Immediate/READ/zero/Atomic/legacy source and evidence gate.
Only the fifteen reviewed receive graph leaves and one message RQ change;
the old active generated core is replaced, not retained as a new-core stub.
No installation, runtime, original-clock or hardware qualification implied.
"""
import json
from pathlib import Path
import re
import sys
import segmented_immediate_native_sources as parent
import derive_segmented_receive as candidate

ROOT=parent.ROOT;digest=parent.digest;HLS='rocev2_native_segmented_receive_top'
PREFIX=ROOT/'results/2026-10-18'
IMMEDIATE_HLS=PREFIX/'rocev2-rnic-segmented-immediate-generated-hls-001.json'
EVIDENCE={name:PREFIX/('rocev2-rnic-'+name+'.json')for name in [
    'segmented-receive-hls-007','segmented-receive-compat-003','receive-extent-conformance-003',
    'segmented-receive-wqe-001','segmented-receive-verbs-adapter-001','segmented-receive-admission-001',
    'receive-message-queue-003','receive-message-ack-001','receive-message-cq-001',
    'receive-mr-post-001','receive-pcie-post-001']}
CHANGED={n+'.v'for n in ['rocev2_control_regs','rocev2_controlled_responder','rocev2_cq_mmio',
    'rocev2_dual_ethernet_endpoint','rocev2_integrity_transport','rocev2_native_endpoint',
    'rocev2_native_rnic_endpoint','rocev2_native_sq_endpoint','rocev2_paged_responder',
    'rocev2_protected_responder','rocev2_receive_ack_tx','rocev2_shared_hls_transport',
    'rocev2_sq_control_regs','rocev2_wqe_admission','rocev2_wqe_hls_sq']}


def sources(project,immediate_report,owned_report,request_report,run):
    evidence={name:json.loads(path.read_text())for name,path in EVIDENCE.items()}
    for name,r in evidence.items():
        if not r.get('pass_test')or not(r.get('source_unchanged')or r.get('source_and_frozen_inputs_unchanged')):
            raise ValueError('unchanged actual receive component evidence required:'+name)
        parent.verify_nested(r)
    cpp=evidence['segmented-receive-hls-007']
    if len(cpp['tests'])!=44 or not cpp.get('all21_prior_modes_retained')or \
       any(v['exit']!=0 or v['seconds']>30 for v in cpp['tests'].values()):
        raise ValueError('all44 bounded actual old/new C++ modes required')
    if evidence['receive-extent-conformance-003']['summary'].get('cases')!=103665:
        raise ValueError('finite actual old/new extent comparison required')
    admission=evidence['segmented-receive-admission-001']
    if admission.get('methods')!=31 or not admission.get('actual_MR_table')or \
       sum(len(v)for group in admission['tests'].values()for v in group.values())!=78:
        raise ValueError('all78 actual full-range admission/staging cases required')
    if evidence['segmented-receive-wqe-001'].get('methods')!=37:
        raise ValueError('all37 actual RECV/old codec methods required')
    if len(evidence['receive-message-queue-003']['tests'])!=48:
        raise ValueError('all48 four-state message-RQ cases required')
    for name in ['receive-mr-post-001','receive-pcie-post-001']:
        r=evidence[name]
        if len(r['tests'])!=4 or any(v.get('exit')!=0 or v['seconds']>10 for v in r['tests'].values()):
            raise ValueError('four actual bounded posting cases required:'+name)
    cq=evidence['receive-message-cq-001']
    if not cq.get('full_CQ_AXI_snapshot')or (cq.get('actual_published_events'),cq.get('actual_received_bytes'),cq.get('posted_capacity'))!=(1,8193,1048576):
        raise ValueError('actual per-packet ACK/whole CQ component required')
    src,data,before=parent.sources(project,immediate_report,owned_report,IMMEDIATE_HLS,run)
    previous=candidate.parent.derive();current=candidate.derive()
    if {p.name for p in current if p not in previous or current[p]!=previous[p]}!=CHANGED:
        raise ValueError('only reviewed15 receive graph leaves may change')
    for p in current:
        if p.name not in CHANGED:continue
        alias='rocev2_shared_protected_responder.v'if p.name=='rocev2_protected_responder.v'else p.name
        matches=[q for q in src if q.name==alias]
        if len(matches)!=1 or matches[0].read_text()!=previous[p]:
            raise ValueError('exact single qualified Immediate parent required:'+alias)
        target=run/alias;target.write_text(current[p]);src=[target if q==matches[0]else q for q in src]
    extra=candidate.RTL/'rocev2_receive_message_queue.v'
    if any(q.name==extra.name for q in src):raise ValueError('message RQ must be a single new implementation')
    src.append(extra)
    old=json.loads(IMMEDIATE_HLS.read_text());oldraw=ROOT/old['directory']/'project/solution1/syn/verilog'
    remove={oldraw/n for n in old['generated_sha256']if n.endswith('.v')}
    if not remove.issubset(src):raise ValueError('exact prior generated HLS selection required')
    src=[p for p in src if p not in remove];data=[p for p in data if p.parent!=oldraw]
    hls=json.loads(request_report.read_text())
    if hls.get('HLS_top')!=HLS or not all(hls.get(n)for n in ['pass_test','source_and_frozen_inputs_unchanged',
        'wrapper_and_builder_unchanged','whole_receive_port776_verified','segmented_SEND_Immediate_receive'])or \
       hls.get('receive_buffer_max_bytes')!=1048576:
        raise ValueError('actual new generated receive HLS/whole776 port required')
    if(float(hls['target_clock_period']),float(hls['clock_uncertainty']),hls['MAX_QPS'],hls['metadata_entries'])!=(4,1.08,8,2000):
        raise ValueError('original clock/uncertainty/geometry gates changed')
    raw=ROOT/hls['directory']/'project/solution1/syn/verilog'
    for key,base in [('source_sha256',ROOT),('frozen_sha256',ROOT/hls['directory']/'inputs'),('generated_sha256',raw)]:
        parent.verify(hls[key],base)
    top=(raw/(HLS+'.v')).read_text()
    if not re.search(r'\[\s*775\s*:\s*0\s*\]\s*m_axis_recv_message_TDATA\s*;',top):
        raise ValueError('actual776-bit whole output missing')
    src+=[raw/n for n in hls['generated_sha256']if n.endswith('.v')]
    data+=[raw/n for n in hls['generated_sha256']if n.endswith('.dat')]
    src=list(dict.fromkeys(src));data=list(dict.fromkeys(data))
    helpers=[Path(m.__file__).resolve()for m in list(sys.modules.values())if getattr(m,'__file__',None)and
        (Path(m.__file__).resolve().is_relative_to(ROOT/'rdma/rnic/fpga')or Path(m.__file__).resolve().is_relative_to(ROOT/'rdma/rnic/tests'))]
    before.update({str(p.relative_to(ROOT)):digest(p)for p in [*src,*data,*helpers,*EVIDENCE.values(),IMMEDIATE_HLS,request_report]})
    return src,data,before
