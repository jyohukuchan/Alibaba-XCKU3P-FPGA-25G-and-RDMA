#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual control144+2 ACK/MAC component evidence, not live HLS/native/physical."""
import argparse
import json
from pathlib import Path
import re
import audit_segmented_receive as binding
import probe_receive_control_ack as probe

ROOT=binding.ROOT;digest=binding.digest
PROBE='rdma/rnic/tests/probe_receive_control_ack.py'
PREIMAGES={
    'receive-control-ack-001':{PROBE:'rdma/rnic/build/receive-control-ack-001-preimages-d8N5ACkp'},
    'receive-control-ack-002':{PROBE:'rdma/rnic/build/receive-control-ack-002-preimages-BuDuHINZ'},
}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve previous evidence')
    names=['receive-control-ack-003','receive-write-rnr-ack-002',*PREIMAGES]
    records={};ids={}
    for n in names:records[n],ids[n]=binding.bindings(n,PREIMAGES.get(n))
    new,old=[records[n]for n in names[:2]]
    modes=[*range(11),*range(20,67),*range(80,100),*range(110,176)]
    if not new['pass_test']or not new['source_unchanged']or list(map(int,new['tests']))!=modes or len(new['legacy_tests'])!=2:
        raise ValueError('actual ALL144 plus both original legacy executions required')
    for k,t in old['tests'].items():
        if new['tests'][k]['summary']!=t['summary']:raise ValueError('old78 summary changed:'+k)
    for k,t in old['legacy_tests'].items():
        if new['legacy_tests'][k]['summary']!=t['summary']:raise ValueError('original legacy outcome changed:'+k)
    if (new['clock_ns'],new['MAC_clock_ns'],new['cycle_limit'],new['runtime_limit_seconds'],new['compile_limit_seconds'])!=(4,2.56,100000,10,10):
        raise ValueError('original clocks/deadlines/cycle limit required')
    if any(t['exit']or t['seconds']>10 for t in [*new['tests'].values(),*new['legacy_tests'].values()]):
        raise ValueError('all actual runtime cases must pass within original10s')
    if any(new[k]>10 for k in ['shared_compile_seconds','legacy-packet_compile_seconds','legacy-message_compile_seconds']):
        raise ValueError('all actual compilations must pass original10s')
    for n in [5,81,111,114]:
        if not any(v is True for k,v in new['tests'][str(n)].items()if k.startswith('actual_')):
            raise ValueError('actual MAC wire/FCS/SFD checks absent:'+str(n))
    text=probe.candidate.derive();oldtext=probe.parent.candidate.derive()
    before=probe.parent.rnr_bench(oldtext);after=probe.control_bench(text)
    fatals=lambda t:set(re.findall(r'\$fatal\(1,"([^"\n]+)"',t))
    if not fatals(before)<=fatals(after):raise ValueError('old assertion removed or relaxed')
    if text.count("tag_sequence<=tag_sequence+1'b1;")!=4 or text.count('reg [TAG_SEQUENCE_WIDTH:0] tag_sequence=0;')!=1:
        raise ValueError('one shared sequence and four genuine ownership alternatives required')
    for n in names[2:]:
        if records[n]['pass_test']:raise ValueError('old failure must remain failed:'+n)
        r=records[n];actual=ROOT/r['directory']/(probe.candidate.NAME+'.v')
        if digest(actual)!=__import__('hashlib').sha256(text.encode()).hexdigest():raise ValueError('DUT changed across fixture-only failures')
    if records[names[2]]['tests']or len(records[names[3]]['tests'])!=143 or records[names[3]]['tests']['174']['exit']==0:
        raise ValueError('original parser and missing-stimulus failures must remain exact')
    for n,h in binding.PROTECTED.items():
        if digest(ROOT/n)!=h:raise ValueError('protected raw source changed:'+n)
    inputs=[Path(__file__).resolve(),Path(probe.__file__).resolve(),Path(probe.candidate.__file__).resolve()]
    result=dict(scope=__doc__,audit_passed=True,evidence=ids,verified_bindings=sum(v['bindings_verified']for v in ids.values()),
        old78_summaries_identical=True,both_original_legacy_summaries_identical=True,
        retained_old_fatal_messages=len(fatals(before)),additional_fatal_messages=len(fatals(after)-fatals(before)),
        actual_component_modes=144,new_control_modes=66,actual_MAC_mixed_control_WRITE_RECV_RNR_control_frames=5,
        actual_MAC_control_five_syndromes_frames=5,one_shared_nonwrapping_tag_allocator=True,
        distinct_control_owner_HLS_MAC_bits=[480,512,528],serial_replay_and_wrap_rejected=True,
        no_RQ_WRITE_RNR_data_completion_for_control=True,clock_ns=4,MAC_clock_ns=2.56,runtime_seconds=10,cycle_limit=100000,
        maximum_case_seconds=max(v['seconds']for v in new['tests'].values()),
        source_sha256={str(n.relative_to(ROOT)):digest(n)for n in inputs},protected_raw_sha256=binding.PROTECTED,
        control_producers_modeled=True,live_generated_HLS=False,native_control_integration=False,
        live_Linux_or_physical=False,full_board_timing=False,overall_goal_complete=False,
        remaining=['Actual native checked receive/full-context certification, nonwrapping serial, real same-generation control HLS and this shared ACK/MAC proof must be connected and executed.',
            'Retain all37 prior native cases; add future-PSN NAK suppression/retry and duplicate-no-second-data/CQ; proper fatal-QP teardown remains separate.',
            'All11/full1MiB native/multiSGE/live registered refs/real peer recovery/congestion/original timing/physical remain.'],
        hardware_or_default_actions=[],commit_or_push=False)
    with a.report.open('x')as f:f.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(audit_passed=True,verified_bindings=result['verified_bindings'],old78_identical=True,native=False)))


if __name__=='__main__':main()
