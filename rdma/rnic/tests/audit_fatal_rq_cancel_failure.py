#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Bind native001 failure, all40 unchanged controls and actual quarantine alias.

All old40 PASS does not turn native42 green. GDB reads the original unchanged
O1 archive at the same assertion; no DUT rebuild/force/receipt or CQ proof.
"""
import argparse
import json
from pathlib import Path
import re
import audit_segmented_receive as binding

ROOT=binding.ROOT;digest=binding.digest


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve earlier evidence')
    names=['fatal-rq-cancel-native-full-001','fatal-rq-cancel-native-diagnostic-001',
        'fatal-event-native-full-001','fatal-event-native-runtime-diagnostics-001',
        'fatal-rq-cancel-native-elaboration-001','fatal-rq-cancel-native-fixture-diagnostics-001']
    records={};ids={}
    for n in names:records[n],ids[n]=binding.bindings(n)
    native,debug,old,runtime,elab,fixture=[records[n]for n in names]
    if native['pass_test']or not debug['diagnostic_completed']or debug['native_runtime_pass']or \
       len(native['tests'])!=41 or native['tests']['FATAL_RQC_ACCESS']['exit']!=-6 or 'FATAL_RQC_PARTIAL'in native['tests']:
        raise ValueError('original41 attempts/40 PASS/first new failure/second unrun must stay explicit')
    for name,prior in old['tests'].items():
        t=native['tests'][name]
        if t['exit']or {k:v for k,v in t.items()if k!='seconds'}!={k:v for k,v in prior.items()if k!='seconds'}:
            raise ValueError('actual old40 full outcome changed:'+name)
    if native['compile_exit']or native['compilation_seconds']>1200 or native['compile_limit_seconds']!=1200 or \
       native['bench_elaborate_seconds']>180 or native['simulation_limit_seconds']!=30 or \
       any(t['seconds']>30 for t in native['tests'].values()):raise ValueError('original gates unchanged')
    v=debug['actual_fatal_fields']
    expected={'tb__DOT__dut__DOT__atomic_rx_guard':1,'tb__DOT__dut__DOT__fatal_rq_cancel_authorized':0,
        'tb__DOT__dut__DOT__fatal_rq_cancel_authority__DOT__certified':4,
        'tb__DOT__dut__DOT__m_write_native_context_valid':1,'tb__DOT__dut__DOT__write_abort_quarantined':4,
        'tb__DOT__dut__DOT__fatal_rq_cancel_fault':0,'tb__DOT__fault':0}
    if any(v.get(n)!=x for n,x in expected.items())or v['actual_live_context356']!=v['retained_cert_context356']or \
       v['actual_RQ_head620']!=v['expected_RQ_head620']or v['RQC_owner_cookie']!=0xfedcba9889abcdf0 or \
       v['RQC_owner_epoch']!=0x9123456700000001:raise ValueError('actual failing full owner/cert/guard boundary changed')
    files=[ROOT/n for n in elab['selected_RTL']]
    top=next(p for p in files if p.name=='rocev2_native_rnic_endpoint.v')
    core=next(p for p in files if p.name=='rocev2_shared_protected_responder.v')
    text=core.read_text()
    if "wire control_external_guard=s_control_held!==1'b0 || s_control_owner_valid!==1'b0;"not in text or \
       'assign atomic_rx_guard=control_external_guard || 'not in text:
        raise ValueError('actual atomic_rx_guard includes permanent control/quarantine alias')
    a0=top.read_text().index('assign fatal_cancel_other_lease_guard=');b0=top.read_text().index(';',a0)
    if 'atomic_rx_guard'not in top.read_text()[a0:b0]:raise ValueError('actual authority predicate alias path missing')
    cp=ROOT/'results/2026-10-18/rocev2-rnic-progress-188.json';observed=json.loads(cp.read_text())['live_input_sha256'];actual=native['source_sha256']
    if observed!=actual or len(actual)!=686:raise ValueError('actual and observed whole686 input manifests must match exactly')
    for n,h in observed.items():
        if digest(ROOT/n)!=h:raise ValueError('original actual input changed:'+n)
    r=dict(scope=__doc__,audit_passed=True,evidence=ids,verified_bindings=sum(x['bindings_verified']for x in ids.values()),
        source_sha256={str(p.relative_to(ROOT)):digest(p)for p in [Path(__file__).resolve(),top,core,cp]},
        original_failed_run_still_false=True,old40_full_outcomes_except_seconds_identical=True,
        attempted_cases=41,passed_old_cases=40,new_access_failed=True,new_partial_unrun=True,
        compilation_seconds=native['compilation_seconds'],maximum_attempt_seconds=max(t['seconds']for t in native['tests'].values()),
        actual_and_observed_input_manifests_identical=True,observed_inputs=686,actual_inputs=686,common_inputs=686,only_observed=0,only_actual=0,
        actual_guard_alias='atomic_rx_guard contains control_external_guard, which includes permanent s_control_held; it is incorrectly treated as a noncontrol lease by the new predicate.',
        actual_certificate_bit4_and_current_full_context_match=True,actual_authorized_zero=True,
        correction_requirement='Export every genuine other RX/memory/reference/Atomic lease separately from the permanent control-held alias; keep original aggregate guards byte-identical. Do not mask atomic_rx_guard wholesale or bypass parent/fetch/work/wire/CQ/full-owner RQC proof.',
        only_blocker_or_success_after_fix_inferred=False,actual_RQC_receipt=False,error_CQ_STOP_global_drain_unpin=False,
        hardware_verified=False,full_board_timing=False,overall_goal_complete=False,hardware_or_default_actions=[],commit_or_push=False)
    with a.report.open('x')as f:f.write(json.dumps(r,indent=2)+'\n')
    print(json.dumps(dict(audit_passed=True,verified_bindings=r['verified_bindings'],old40_identical=True,new_native42_still_false=True,confirmed_aggregate_guard_alias=True)))


if __name__=='__main__':main()
