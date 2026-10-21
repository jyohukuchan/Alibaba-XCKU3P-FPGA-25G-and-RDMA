#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual66 four-state abort RTL consumers, not native/HLS/global drain proof.

Require independent full960/1000, actual retained quarantine/cancel ordering,
immutable failures and unchanged original10s/4ns/100000-cycle gates.
"""
import argparse
import json
from pathlib import Path
import audit_segmented_receive as binding
from probe_write_abort_control import DUT,verify_owner
ROOT=binding.ROOT;digest=binding.digest
SOURCE='rdma/rnic/rtl/rocev2_write_abort_control.v';PROBE='rdma/rnic/tests/probe_write_abort_control.py'
PREIMAGES={
    'write-abort-control-001':'rdma/rnic/build/write-abort-control-001-preimages-IdBr2vAd',
    'write-abort-control-002':'rdma/rnic/build/write-abort-control-002-preimages-la7uSPNL',
    'write-abort-control-003':'rdma/rnic/build/write-abort-control-003-preimages-bHR5H2aw',
}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve previous evidence')
    names=['write-abort-control-004','write-abort-hls-003','write-abort-hls-diagnostics-001',*PREIMAGES]
    records={};ids={}
    for n in names:
        fallback={SOURCE:PREIMAGES[n],PROBE:PREIMAGES[n]}if n in PREIMAGES else None
        records[n],ids[n]=binding.bindings(n,fallback)
    control,cpp,cpp_audit=[records[n]for n in names[:3]]
    modes=[*range(5),*range(20,42),*range(50,89)]
    if not control['pass_test']or not control['source_unchanged']or set(control['tests'])!={str(n)for n in modes}or \
       (control['clock_ns'],control['runtime_limit_seconds'],control['compile_limit_seconds'],control['cycle_limit'])!=(4,10,10,100000)or \
       control['compilation']['exit']or control['compilation']['seconds']>10:
        raise ValueError('actual all66 modes and original bounds required')
    if control['actual_native_or_HLS_or_MAC']or control['QP_global_drain_or_unpin']or not control['producer_boundaries_modeled']:
        raise ValueError('all producer boundaries remain modeled, no native/HLS/global drain/unpin claim')
    run=ROOT/control['directory']
    if digest(run/DUT.name)!=digest(DUT):raise ValueError('actual compiled DUT changed')
    for mode in modes:
        t=control['tests'][str(mode)];s=t['summary']
        if t['exit']or t['seconds']>10 or s['cycles']>100000 or s['mode']!=mode or bool(s['fault'])!=(mode>=20):
            raise ValueError('actual ordered consumer/fail-closed assertions missing:'+str(mode))
        if mode<5:
            if t['independent_oracles']!=verify_owner((run/(str(mode)+'.log')).read_text(),mode)or \
               (s['requests'],s['completions'],s['quarantine'])!=(1,1,4):raise ValueError('all full960/1000 bits and persistent selected quarantine required')
    if not cpp['pass_test']or len(cpp['tests'])!=140 or not cpp_audit['audit_passed']:
        raise ValueError('independent actual HLS CPP140/old105 proof retained, not bridge coupling')
    for n in PREIMAGES:
        if records[n]['pass_test']:raise ValueError('original failure cannot be relabeled:'+n)
    first,second,third=[records[n]for n in PREIMAGES]
    if first['tests']or second['tests']or third['tests']['33']['exit']==0 or len(third['tests'])!=19:
        raise ValueError('original parser/compile startup and actual unknown-MSN failure retained')
    if 'positive_wire[424]=1\'bx'not in (ROOT/third['directory']/'tb.v').read_text():
        raise ValueError('original unknown-MSN stimulus cannot be removed')
    if "wire positive_ok=(^positive_wire)!==1'bx"not in DUT.read_text():
        raise ValueError('actual full wire-known check required, not a weaker changed test')
    for n,h in binding.PROTECTED.items():
        if digest(ROOT/n)!=h:raise ValueError('original protected source changed:'+n)
    result=dict(scope=__doc__,audit_passed=True,evidence=ids,verified_bindings=sum(v['bindings_verified']for v in ids.values()),
        actual_four_state_cases=66,positive_full_owner_oracles=5,invalid_or_ordering_cases=61,
        maximum_case_seconds=max(t['seconds']for t in control['tests'].values()),
        real_consumer_RTL=True,retained_selected_quarantine_and_actual_cancel_readback=True,
        source_sha256={str(q.relative_to(ROOT)):digest(q)for q in [Path(__file__).resolve(),DUT,ROOT/PROBE]},protected_raw_sha256=binding.PROTECTED,
        native_HLS_MAC_backend_quarantine_local_report_producers_modeled=True,
        native_integration=False,actual_generated_HLS_coupling=False,QP_global_drain_or_unpin=False,
        native_fatal_admission_error_CQ_STOP_and_lifetime_complete=False,physical=False,full_board_timing=False,overall_goal_complete=False,
        remaining=['Wire genuine actual native packet/MAC/commit/ACK retirement and authenticated fatal quarantine/error wire/local report to the real same HLS abort960/992; one nonwrapping serial namespace.',
            'Actual full native38 plus genuine fatal cases/error CQ/STOP/pinned references; this component consumer and separate HLS140 are NOT native coupling.',
            'Original all11/native1MiB/multiSGE/live Linux-provider/real-peer recovery/congestion/original board timing/physical remain.'],
        hardware_or_default_actions=[],commit_or_push=False)
    with a.report.open('x')as f:f.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(audit_passed=True,verified_bindings=result['verified_bindings'],actual_cases=66,native=False)))


if __name__=='__main__':main()
