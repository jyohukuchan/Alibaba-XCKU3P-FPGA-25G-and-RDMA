#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual native fatal source/elaboration plus same tested frontend/control.

NOT fresh native packet runtime/error CQ/STOP/global drain/unpin/physical.
All38 native regressions and actual fatal scenarios remain mandatory.
"""
import argparse
import json
from pathlib import Path
import sys
import audit_segmented_receive as binding
from probe_write_error_control import fatal_oracle
from probe_write_fatal_frontend import FATAL_MODES,ACCESS_MODES,fatal_compare
ROOT=binding.ROOT;digest=binding.digest
sys.path.insert(0,str(ROOT/'rdma/rnic/fpga'))
import derive_write_fatal_native as candidate
PREIMAGES={
    'write-error-control-source-startup-001':{'rdma/rnic/fpga/derive_write_error_control.py':
        'rdma/rnic/build/write-error-control-source-startup-001-preimages-VHBQoVxg'},
    'write-fatal-native-source-startup-001':{'rdma/rnic/tests/check_write_fatal_native.py':
        'rdma/rnic/build/write-fatal-native-source-startup-001-preimages-kam9gPbo'},
    'write-fatal-front-001':{'rdma/rnic/tests/probe_write_fatal_frontend.py':
        'rdma/rnic/build/write-fatal-front-001-preimages-H2zSQMso'},
}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve previous evidence')
    names=['write-fatal-native-elaboration-001','write-fatal-front-002','write-error-control-001',
        'write-abort-control-004','write-abort-control-diagnostics-001','write-abort-generated-hls-001',
        'write-abort-generated-diagnostics-001','write-psn-control-001',*PREIMAGES]
    records={};ids={}
    for n in names:records[n],ids[n]=binding.bindings(n,PREIMAGES.get(n))
    elab,front,ctrl,bridge,bridge_audit,hls,generated,oldctrl=[records[n]for n in names[:8]]
    if not all(r.get('pass_test',r.get('audit_passed'))for r in [elab,front,ctrl,bridge,bridge_audit,hls,generated,oldctrl]):
        raise ValueError('actual complete generated HLS/native hierarchy/real frontend/merged control/selected bridge required')
    if elab['compile_seconds']>180 or not elab['compile_only']or elab['runtime_test']or \
       not elab['native_authenticated_fatal61_62_and_selected_abort_cancel_inserted']or not elab['both_global_HLS_drains_zero']or \
       elab['selected_certificate_is_global_drain_or_unpin']or elab['native_fatal63_implemented']or elab['error_CQ_STOP_lifetime_implemented']:
        raise ValueError('exact compile-only scope/original limits and retained incomplete full QP lifetime required')
    if len(front['tests'])!=47 or not front['actual_IPv4_ICRC']or not front['actual_remote_MR']or \
       not all(front.get(k)for k in ['all47_raw_inputs_and_replay_identical','other45_protection_identical','zero_key_overflow_actual_MR_classified']):
        raise ValueError('actual all47 exact raw/replay and explicitly changed zero-key/range MR denial required')
    fatal_compare(front,ROOT/front['directory'])
    for n,t in front['tests'].items():
        mode=int(n);f=t['fatal_certification']
        if t['exit']or t['seconds']>10 or bool(f['cycles'])!=(mode in FATAL_MODES)or \
           f['consumed']!=(1 if mode in FATAL_MODES else 0)or \
           f['syndrome']!=(0x62 if mode in ACCESS_MODES else 0x61 if mode in FATAL_MODES else 0):
            raise ValueError('actual peer/PSN/format/CRC/MR fatal certification mismatch:'+n)
    if len(ctrl['tests'])!=81 or not ctrl['one_PSN_fatal_nonwrapping_serial']or not ctrl['all46_old_summaries_identical']or \
       any(t['exit']or t['seconds']>10 for t in ctrl['tests'].values()):raise ValueError('all81 actual merged consumers and original bounds required')
    for n,t in oldctrl['tests'].items():
        if ctrl['tests'][n]['summary']!=t['summary']:raise ValueError('actual old46 control summary changed:'+n)
    for mode in range(100,106):
        if ctrl['tests'][str(mode)]['independent_fatal_oracles']!=fatal_oracle((ROOT/ctrl['directory']/(str(mode)+'.log')).read_text(),mode):
            raise ValueError('independent every480 fatal owner/shared serial required')
    run=ROOT/elab['directory'];derived=candidate.derive()
    for path,text in derived.items():
        alias='rocev2_shared_protected_responder.v'if path.name=='rocev2_protected_responder.v'else path.name
        copied=run/alias
        # Unchanged inherited definitions are selected at their exact old
        # paths; every modified/new definition is copied in this actual run.
        if copied.exists()and copied.read_text()!=text:raise ValueError('actual derived selected source changed:'+alias)
    same=[(candidate.native.leaves.FRONT_NAME+'.v',ROOT/front['directory']),
        (candidate.GUARD_NAME+'.v',ROOT/front['directory']),
        (candidate.error.NAME+'.v',ROOT/ctrl['directory']),
        (candidate.BRIDGE.name,ROOT/bridge['directory'])]
    for name,tested in same:
        if digest(run/name)!=digest(tested/name):raise ValueError('actual native consumes a different tested leaf:'+name)
    genroot=ROOT/hls['directory']/'project/solution1/syn/verilog'
    selected={Path(n).name for n in elab['selected_RTL']+elab['selected_HLS_data']if (ROOT/n).parent==genroot}
    if selected!=set(hls['generated_sha256'])or len(selected)!=208:raise ValueError('entire SAME actual208 HLS, never old/new mixture required')
    for n in PREIMAGES:
        if records[n]['pass_test']:raise ValueError('original failure must not be relabeled:'+n)
    failed=records['write-fatal-front-001']
    if len(failed['tests'])!=20 or failed['tests']['20']['exit']==0 or \
       'independent actual remote-MR request oracle query0'not in (ROOT/failed['directory']/'20.log').read_text():
        raise ValueError('actual first zero-key MR query/test-oracle failure retained')
    for n,h in binding.PROTECTED.items():
        if digest(ROOT/n)!=h:raise ValueError('original protected raw source changed:'+n)
    inputs=[Path(__file__).resolve(),Path(candidate.__file__).resolve(),Path(candidate.error.__file__).resolve(),candidate.BRIDGE,candidate.GUARD,
        ROOT/'rdma/rnic/tests/probe_write_fatal_frontend.py',ROOT/'rdma/rnic/tests/probe_write_error_control.py',ROOT/'rdma/rnic/tests/check_write_fatal_native.py']
    result=dict(scope=__doc__,audit_passed=True,evidence=ids,verified_bindings=sum(v['bindings_verified']for v in ids.values()),
        native_elaboration_seconds=elab['compile_seconds'],actual_selected_RTL=len(elab['selected_RTL']),actual_selected_HLS_data=len(elab['selected_HLS_data']),
        actual_same_generation_HLS_files=208,actual_same_tested_frontend_guard_control_bridge=True,
        actual_frontend_cases=47,all47_raw_inputs_and_replay_identical=True,other45_protection_identical=True,
        explicit_zero_key_overflow_change='Both now query the unchanged actual whole MR namespace once and reject1/4 ->NAK62 certification before any data/RQ/replay; old pre-MR semantic16 not silently normalized.',
        qualified_fatal_cases={str(n):front['tests'][str(n)]['fatal_certification']for n in sorted(FATAL_MODES)},
        actual_control_cases=81,all46_original_control_summaries_identical=True,actual_bridge_cases=66,
        native_module_counts=elab['module_counts'],estimated_HLS_ns=float(hls['estimated_clock_period']),original_timing_met=hls['original_effective_period_met'],
        source_sha256={str(q.relative_to(ROOT)):digest(q)for q in inputs},protected_raw_sha256=binding.PROTECTED,
        actual_native_fatal_packet_runtime=False,original38_rerun_on_new_graph=False,full_QP_error_CQ_STOP_or_lifetime_qualified=False,
        fatal63_implemented=False,QP_global_drain_or_unpin=False,live_Linux_or_physical=False,full_board_timing=False,overall_goal_complete=False,
        remaining=['Fresh actual full new graph: all38 old exact inputs/oracles plus genuine first-MR fatal62 and partial-WRITE fatal61, real wire/MSN/FCS/backend/native/HLS cancel and persistent quarantine.',
            'Actual fatal63/standard error CQ/QP STOP/pinned-reference retirement and legitimate quarantine release; selected1000 is not global drain or safe unpin.',
            'Original all11/native1MiB/multiSGE/live Linux-provider/real-peer recovery/congestion/original timing/physical remain.'],
        hardware_or_default_actions=[],commit_or_push=False)
    with a.report.open('x')as f:f.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(audit_passed=True,verified_bindings=result['verified_bindings'],actual_RTL=result['actual_selected_RTL'],actual_front_cases=47,native_runtime=False)))


if __name__=='__main__':main()
