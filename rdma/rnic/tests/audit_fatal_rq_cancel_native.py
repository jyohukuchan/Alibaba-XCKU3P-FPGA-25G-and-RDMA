#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Bind exact full fatal RQC variant and unchanged guards/core/defaults.

Source/elaboration proof only. Authority33 has modeled inputs, and the new
full native cancellation receipt/runtime/error CQ/STOP/unpin remain unproven.
"""
import argparse
import json
from pathlib import Path
import re
import audit_segmented_receive as binding
import check_fatal_rq_cancel_native as checker

ROOT=binding.ROOT;digest=binding.digest;candidate=checker.candidate
NAMES=['fatal-rq-cancel-native-elaboration-001','fatal-event-native-elaboration-002',
    'fatal-event-native-full-001','fatal-event-native-runtime-diagnostics-001',
    'fatal-rq-authority-001','write-abort-event-generated-hls-002']


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve all earlier evidence')
    records={};ids={}
    for n in NAMES:records[n],ids[n]=binding.bindings(n)
    native,parent,old,runtime,component,hls=[records[n]for n in NAMES]
    if not all(r.get('pass_test',r.get('audit_passed'))for r in records.values()):
        raise ValueError('actual full40/authority33/source evidence required')
    before=[ROOT/n for n in parent['selected_RTL']];after=[ROOT/n for n in native['selected_RTL']]
    ot,os,oc,of=[next(p for p in before if p.name==n)for n in [
        'rocev2_native_rnic_endpoint.v','rocev2_native_sq_endpoint.v','rocev2_sq_control_regs.v','rocev2_fatal_event_mmio.v']]
    nt,ns,nc,nf=[next(p for p in after if p.name==n)for n in [ot.name,os.name,'rocev2_fatal_rq_control_regs.v',of.name]]
    texts=candidate.derive(*[p.read_text()for p in [ot,os,oc,of]])
    if [p.read_text()for p in [nt,ns,nc,nf]]!=list(texts):raise ValueError('exact four-leaf derivation required')
    replace={ot:nt,os:ns,of:nf}
    if after!=[replace.get(p,p)for p in before]+[nc,candidate.AUTHORITY]:
        raise ValueError('only three replacements plus variant/authority allowed; original SQC control stays')
    if len(after)!=465 or native['selected_HLS_data']!=parent['selected_HLS_data']:
        raise ValueError('complete465 RTL/eight unchanged data leaves required')
    gen=ROOT/hls['directory']/'project/solution1/syn/verilog'
    if len(hls['generated_sha256'])!=207 or \
       {p.name for p in [*after,*[ROOT/n for n in native['selected_HLS_data']]]if p.parent==gen}!=set(hls['generated_sha256']):
        raise ValueError('whole exact qualified207-file HLS required')
    wanted=dict(parent['module_counts']);assert wanted['rocev2_sq_control_regs']==2
    wanted.update(rocev2_sq_control_regs=1,rocev2_fatal_rq_control_regs=1,rocev2_fatal_rq_cancel_authority=1)
    if native['module_counts']!=wanted:raise ValueError('unchanged sole HLS/MR/PTE/backend/nonce/ACK graph required')
    top,sq,control,fec=texts
    guard='.wire_queue_guard(wire_queue_guard | atomic_binding_queue_guard | fatal_event_queue_guard | s_fatal_quarantined),'
    if sq.count(guard)!=2 or os.read_text().count(guard)!=2:
        raise ValueError('both complete SQC/RQC quarantine configuration guards remain')
    old=oc.read_text();start=old.index('wire stage_safe=');end=old.index('wire command_safe=',start)
    if old[start:end]not in control:raise ValueError('allocation/retirement stage-safe gate changed')
    for marker in ['.event_taken(fatal_join_valid && fatal_join_ready)',
        '.trusted_valid(m_write_native_context_valid),.trusted_context(m_write_native_context),.trusted_psn(m_write_expected_psn)',
        '.quarantined(write_abort_quarantined),.noncontrol_lease_guard(fatal_cancel_other_lease_guard)',
        "assign atomic_lease_guard=s_control_held || fatal_cancel_other_lease_guard;",
        ".local_core_drained(1'b0)",".hls_transport_drained(1'b0)"]:
        if marker not in top:raise ValueError('real join/current context/lease/drain identity missing:'+marker)
    original=ot.read_text();a0=original.index('assign atomic_lease_guard=s_control_held || ');b0=original.index(';',a0)
    other=original[a0+len('assign atomic_lease_guard=s_control_held || '):b0]
    if 'assign fatal_cancel_other_lease_guard='+other+';'not in top:
        raise ValueError('every actual noncontrol Atomic/zero/RNR lease must remain')
    for marker in ['wire command_safe=parent_dma_drained && !fetch_queue_guard[qi] && !work_queue_guard[qi] &&',
        "snapshot[1]==4 && s_fatal_cancel_authorized[qi]===1'b1",
        "s_fatal_cancel_wire_guard[qi]===1'b0:!wire_queue_guard[qi]",
        '!completion_queue_guard[qi] && !endpoint_fault;',
        '4:if(!RECV_CANCEL_ENABLE || owner_match!==1\'b1 || sn==0 || sp!==owner_producer[si])stage_error=ERR_OWNER;',
        'assign cfg_valid=state==OFFER && (snapshot[1]!=4 || command_safe===1\'b1) && !rst;']:
        if marker not in control:raise ValueError('real command/owner/nonce/parent/fetch/work/CQ gate missing:'+marker)
    if "8:rd=32'h0000001f;"not in fec or native['FEC_features']!=31 or \
       (native['RNC_features'],native['CQC_features'],native['software_profile'])!=(131071,511,8) or \
       not native['both_global_HLS_drains_zero']or native['default_or_driver_capability_changed']:
        raise ValueError('explicit private FEC31 with unchanged original profiles/global drains/defaults required')
    if len(records['fatal-event-native-full-001']['tests'])!=40 or len(component['tests'])!=33 or \
       native['actual_RQC_cancellation_receipt']or native['actual_new_native_packet_runtime']:
        raise ValueError('no component/source-to-packet inference')
    failed,fail_id=binding.bindings('fatal-rq-cancel-native-startup-001',
        {'rdma/rnic/tests/check_fatal_rq_cancel_native.py':'rdma/rnic/build/fatal-rq-cancel-startup-001-preimages-RMZkqC0y'})
    if failed['pass_test']or failed['native_compile_started']:raise ValueError('startup failure must remain false')
    for n,h in binding.PROTECTED.items():
        if digest(ROOT/n)!=h:raise ValueError('protected original source changed:'+n)
    inputs=[Path(__file__).resolve(),Path(checker.__file__).resolve(),Path(candidate.__file__).resolve(),candidate.AUTHORITY,nt,ns,nc,nf]
    r=dict(scope=__doc__,audit_passed=True,evidence=ids,failed_startup=fail_id,
        verified_bindings=sum(v['bindings_verified']for v in ids.values())+fail_id['bindings_verified'],
        source_sha256={str(p.relative_to(ROOT)):digest(p)for p in inputs},
        exact_four_leaf_derivation=True,whole_qualified_HLS207_unchanged=True,
        both_full_SQC_RQC_configuration_guards_unchanged=True,all_other_actual_leases_unchanged=True,
        actual_join_after_both_receivers=True,only_RQC_command4_distinction=True,
        parent_fetch_work_wire_CQ_and_full_owner_nonce_proofs_retained=True,FEC_features=31,
        actual_new_native_packet_runtime=False,actual_RQC_cancellation_receipt=False,
        error_CQ_STOP_global_drain_unpin=False,hardware_verified=False,full_board_timing=False,
        overall_goal_complete=False,hardware_or_default_actions=[],commit_or_push=False)
    with a.report.open('x')as f:f.write(json.dumps(r,indent=2)+'\n')
    print(json.dumps(dict(audit_passed=True,verified_bindings=r['verified_bindings'],native_source_only=True)))


if __name__=='__main__':main()
