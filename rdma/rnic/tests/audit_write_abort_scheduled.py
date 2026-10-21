#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual scheduled-abort C++140/service compatibility; NOT native runtime.

Preserve original native1200s timeout, exact original/new source cohorts and
all140 outcomes/oracles. Generated RTL size/timing improvements are unproven.
"""
import argparse
import json
from pathlib import Path
import sys
import audit_segmented_receive as binding

ROOT=binding.ROOT;digest=binding.digest
sys.path.insert(0,str(ROOT/'rdma/rnic/hls'))
import segmented_write_abort_scheduled_transport as candidate
from build_native_write_abort import verify_abort_evidence


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve prior evidence')
    fallback={'rdma/rnic/hls/segmented_write_abort_scheduled_transport.py':
        'rdma/rnic/build/write-abort-scheduled-source-startup-001-preimages-fclFtbOa'}
    names=['write-abort-scheduled-hls-001','write-abort-scheduled-compat-001',
        'write-abort-hls-003','write-abort-compat-001','write-fatal-native-full-001',
        'write-abort-scheduled-source-startup-001']
    records={};ids={}
    for n in names:records[n],ids[n]=binding.bindings(n,fallback if n==names[-1]else None)
    new,compat,old,oldcompat,failed,startup=[records[n]for n in names]
    verify_abort_evidence(new)
    if not all(r['pass_test']for r in [new,compat,old,oldcompat])or len(new['tests'])!=140:
        raise ValueError('actual complete140 and unchanged real owned services required')
    fields=0
    for mode,t in old['tests'].items():
        for key,value in t.items():
            if key=='summaries'or 'oracle'in key:
                if new['tests'][mode].get(key)!=value:raise ValueError('original140 outcome/oracle changed:'+mode+':'+key)
                fields+=1
    if compat['summaries']!=oldcompat['summaries']:
        raise ValueError('original real Atomic/Immediate service outcomes changed')
    if failed['pass_test']or failed['error_type']!='TimeoutExpired'or failed['compile_limit_seconds']!=1200 or failed['tests']:
        raise ValueError('actual original native compilation timeout/zero cases must remain a failure')
    if startup['pass_test']or not startup['failed_before_cohort_allocation']:
        raise ValueError('strict original source-anchor failure must remain a failure')
    source=ROOT/'rdma/rnic/build/native-write-abort-scheduled-transport-001'
    info=json.loads((source/'source.json').read_text());original=candidate.parent.derive();scheduled=candidate.derive()
    if {n for n in scheduled if scheduled[n]!=original[n]}!={candidate.CPP}:
        raise ValueError('only parser scheduling may change, not top/owner/retire/table contracts')
    for n,text in scheduled.items():
        if (source/'fns'/n).read_text()!=text:raise ValueError('actual tested cohort differs from exact derivation:'+n)
    cpp=scheduled[candidate.CPP];start=cpp.index('void rx_exh_fsm(');end=cpp.index('\n}',start)+2;body=cpp[start:end]
    if body.count(candidate.CHECKPOINT)!=2 or candidate.parent.ADMISSION in body or \
       '\tcase META:\n'+candidate.CHECKPOINT not in body or \
       '    case WRITE_ABORT_FENCE: {\n'+candidate.CHECKPOINT not in body:
        raise ValueError('actual unchanged checkpoint producer consumed in META AND late FENCE required')
    if not all(info.get(k)for k in ['abort_control_scoped_to_META_and_FENCE',
        'late_actual_checkpoint_still_consumed_in_FENCE','owner960_receipt992_and_original_validation_unchanged']):
        raise ValueError('explicit scheduled source identity required')
    for n,h in binding.PROTECTED.items():
        if digest(ROOT/n)!=h:raise ValueError('original protected raw source changed:'+n)
    inputs=[Path(__file__).resolve(),Path(candidate.__file__).resolve(),source/'source.json',source/'fns'/candidate.CPP]
    result=dict(scope=__doc__,audit_passed=True,evidence=ids,
        verified_bindings=sum(v['bindings_verified']for v in ids.values()),actual_CPP_cases=140,
        all140_original_summary_and_oracle_fields_identical=fields,
        unchanged_real_owned_Atomic_Immediate_service=True,
        compile_seconds=new['compile_seconds'],compile_limit_seconds=new['compile_limit_seconds'],
        maximum_case_seconds=max(t['seconds']for t in new['tests'].values()),runtime_limit_seconds=30,
        actual_same_retire_checkpoint_and_PSN_MSN_state_clear_consumers=True,
        late_checkpoint_still_serviced_in_FENCE=True,only_parser_scheduling_changed=True,
        original_native_timeout_retained=True,original_native_cases_run=0,
        source_sha256={str(q.relative_to(ROOT)):digest(q)for q in inputs},protected_raw_sha256=binding.PROTECTED,
        new_generated_HLS=False,new_RTL_size_or_timing_improvement_proven=False,
        new_native_runtime=False,QP_global_drain_or_unpin=False,hardware_verified=False,
        full_board_timing=False,overall_goal_complete=False,hardware_or_default_actions=[],commit_or_push=False,
        remaining=['Generate actual scheduled HLS under original7200s/4ns/default1.08ns/8QP/2000/resources gates; audit every actual port/cohort/domain before fresh full native execution.',
            'All original11, genuine native fatal61/62/63/error CQ/STOP/reference lifetime/legitimate recovery and real-peer/timing/physical requirements remain.'])
    with a.report.open('x')as f:f.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(audit_passed=True,verified_bindings=result['verified_bindings'],actual_CPP_cases=140,native_runtime=False)))


if __name__=='__main__':main()
