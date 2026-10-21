#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Real remote-MR/late-RQ component scope and original failure provenance.

Keep all earlier native/HLS/software scope separate. No component proof
producer is promoted to actual backend/HLS/MAC/native or physical evidence.
The new posted-head peek does not alter a single actual authorization,
take, packet, CQ, retirement or protocol-fault gate in the old queue.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
import audit_segmented_receive as binding

ROOT=binding.ROOT;PREFIX=binding.PREFIX;digest=binding.digest
sys.path.insert(0,str(ROOT/'rdma/rnic/fpga'))
import derive_write_notice_binding_queue as queue


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve all earlier evidence')
    actual,a_id=binding.bindings('remote-write-mr-notice-004')
    old,o_id=binding.bindings('write-notice-queue-001')
    prior,p_id=binding.bindings('segmented-write-receive-diagnostics-001')
    failures={}
    for number,preimage in [(1,'DjmIk9bt'),(2,'fntQPVp3'),(3,'YRo9gUbx')]:
        name='remote-write-mr-notice-'+str(number).zfill(3)
        frozen='rdma/rnic/build/'+name+'-preimages-'+preimage
        r,identity=binding.bindings(name,{n:frozen for n in [
            'rdma/rnic/tests/remote_write_mr_notice_tb.v',
            'rdma/rnic/tests/probe_remote_write_mr_notice.py']})
        if r.get('pass_test')or r.get('hardware_verified'):raise ValueError('original failed report must remain failed')
        failures[name]=dict(identity=identity,error=r.get('error'))
    if not prior.get('audit_passed')or not all(actual.get(k)for k in ['pass_test','source_unchanged',
        'actual_remote_MR_table','actual_late_RQ','MR_response_successes_never_fabricated','four_state']):
        raise ValueError('actual source-bound connected MR/late-RQ component proof required')
    if set(actual['tests'])!={str(i)for i in range(46)}or set(actual['old_queue_tests'])!=set(old['tests'])or len(old['tests'])!=62:
        raise ValueError('all46 new modes and every exact62 prior queue mode required')
    if (actual['case_limit_seconds'],actual['compile_limit_seconds'],actual['original_clock_ns'],actual['cycle_limit'],actual['MAX_QPS'])!=(10,10,4,100000,8):
        raise ValueError('original deadlines/4ns/8QP must remain')
    tests=list(actual['tests'].values())+list(actual['old_queue_tests'].values())
    if any(t['exit']!=0 or t['seconds']>10 for t in tests):raise ValueError('all actual bounded executions must pass')
    for mode,total,imm in [(0,8193,0),(1,8193,1),(2,1048576,1),(3,8192,1),(4,8193,1),(5,4097,1),(38,8193,0)]:
        s=actual['tests'][str(mode)]['summary'];packets=(total+4095)//4096
        if (s['MR_queries'],s['grants'],s['completed_packets'],s['completed_messages'],s['RQ_taken'],s['message_active'],s['fault'])!=\
           (packets+1+(mode==4),packets,packets,1,imm,0,0):raise ValueError('exact full+packet MR and distinct one-RQ lifetime proof required')
    # Byte-exact reconstruction: only module name, observation port and
    # read-only observation assignments were added to the qualified queue.
    parent=queue.parent.derive();derived=queue.derive()
    observed_ports='''
    // Observation only, NEVER a take, MR grant or completion certificate.
    // Independent of this same notice's combinational protocol_fault.
    output wire [619:0] m_notice_head_context,output wire m_notice_head_valid,
'''
    observed_assignments='''
assign held_context=owner;assign active=held;
assign m_notice_head_context=m_head_context;
assign m_notice_head_valid=query_ok && !cancel_target && !fault &&
    parent_fault===1'b0 && !rst && !held && count[query_qpn[2:0]]!=0;'''
    reconstructed=queue.once(derived,'module '+queue.NAME+' #(','module '+queue.parent.NAME+' #(')
    reconstructed=queue.once(reconstructed,observed_ports,'')
    reconstructed=queue.once(reconstructed,observed_assignments,'assign held_context=owner;assign active=held;')
    if reconstructed!=parent:raise ValueError('any old actual protection/take/proof/CQ/retire gate changed')
    evidence={}
    for n in [
        'rdma/rnic/build/remote-write-mr-notice-001-preimages-DjmIk9bt/read-only-observer.log',
        'rdma/rnic/build/remote-write-mr-notice-002-preimages-fntQPVp3/read-only-observer.log',
        'rdma/rnic/build/remote-write-mr-notice-002-preimages-fntQPVp3/read-only-observer-expanded.log',
        'rdma/rnic/build/remote-write-mr-notice-002-preimages-fntQPVp3/lint.log',
        'rdma/rnic/build/remote-write-mr-notice-002-preimages-fntQPVp3/rdma/rnic/tests/remote_write_mr_notice_observe.v',
        'rdma/rnic/tests/remote_write_mr_notice_observe.v']:
        evidence[n]=digest(ROOT/n)
    first=(ROOT/list(evidence)[0]).read_text();expanded=(ROOT/list(evidence)[2]).read_text();lint=(ROOT/list(evidence)[3]).read_text()
    if 'response1 response_ready0 quiescent1 guard_fault0 rq_fault0 queries0 grants0'not in first or \
       'original bounded4ns/100000 cycle guard'not in first:
        raise ValueError('original management-fixture handshake stall evidence required')
    if 'time216000'in expanded and 'queries4 grants2 guard_state4'in expanded and \
       re.search(r'111 time steps',expanded)and 'Circular combinational logic: \'tb.m_notice_valid\''in lint:
        pass
    else:raise ValueError('read-only actual stalled graph and explicit original loop path required')
    if re.search(r'\b(force|assign|release)\b|\$(?:deposit|finish|fatal)',(ROOT/'rdma/rnic/tests/remote_write_mr_notice_observe.v').read_text()):
        raise ValueError('diagnostic observer must not drive or terminate the original DUT')
    for n,h in binding.PROTECTED.items():
        if digest(ROOT/n)!=h:raise ValueError('protected raw source changed:'+n)
    check=subprocess.run(['bash','scripts/check.sh'],cwd=ROOT,capture_output=True,text=True,timeout=30)
    result=dict(scope=__doc__,audit_passed=True,overall_goal_complete=False,hardware_verified=False,
        actual_component=a_id,unchanged_old62=o_id,prior_separate_HLS_and_queue=p_id,failures=failures,
        verified_bindings=sum(v['bindings_verified']for v in [a_id,o_id,p_id])+sum(v['identity']['bindings_verified']for v in failures.values()),
        source_sha256={str(Path(__file__).relative_to(ROOT)):digest(__file__)},diagnostic_artifact_sha256=evidence,
        protected_raw_sha256=binding.PROTECTED,actual_new_modes=46,all62_old_queue_modes_retained=True,
        original_actual_queue_gates_byte_identical=True,read_only_posted_head_peek_is_not_authorization=True,
        first_failure='Original fixture missed a management handshake after reset; real response waited unconsumed. Only edge sampling was corrected.',
        second_failure='Actual old-head VALID to notice VALID to same-notice protocol fault to old-head VALID loop stalled Immediate. New peek breaks the dependency; original actual gates remain.',
        third_failure='Negative transport vector corrupted FIRST query2 while expecting MIDDLE query3 fault; changed only injected phase, same fault/retention assertions.',
        maximum_component_seconds=max(t['seconds']for t in tests),
        real_MR_checks_full_and_per_packet=True,RNR_same_PSN_offset_tag_without_grant=True,
        distinct320_remote_and620_posted_RQ_retained_through_joint_CQ_retire=True,
        producer_boundaries_modeled=['integrity-checked packet metadata','trusted QP and initial MSN','posted RQ admission',
            'backend data/visibility','HLS readback/whole receipt','ACK MAC/tail','CQ consumers'],
        generated_new_HLS=False,new_native_integration=False,matched_new_software=False,
        payload_DMA_executed=False,live_Linux_RTL_coupling=False,original4ns_timing_met=False,
        inherited_source_check=dict(exit=check.returncode,stdout=check.stdout,stderr=check.stderr,overall_suite_passed=check.returncode==0,original_gate_unchanged=True),
        remaining=['All11 original requirements retained; goal incomplete.',
            'Connect actual protected opcode06/07/08/09 parsing, full/per-packet MR refs, PTE/DMA, generated new HLS, actual ACK-MAC/tail and CQ fanout in the native graph.',
            'Qualify native1MiB, exact matched new software profile, multiSGE, short real-peer recovery/RNR/MSN/congestion, live Linux/ref coupling.',
            'Original4ns/default1.08ns full-board fit/setup/hold/CDC/DRC/routing and short physical proof remain. Latest actual HLS15.571ns FAILS.',
            'No reboot needed. Restore all archived RAM caches and prove authenticated exact-thread/active-goal revival before any necessary reboot.'],
        hardware_install_load_network_fan_BIOS_flash_reboot_actions=[],commit_or_push=False)
    with a.report.open('x')as f:f.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(audit_passed=True,new_modes=46,old_modes=62,verified_bindings=result['verified_bindings'],native_or_physical=False)),flush=True)


if __name__=='__main__':main()
