#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Checked RNR components/native wiring/37-case fixture, NOT native runtime.

Preserve all36 old cases and364 fatal messages, original failed fixtures,
single actual namespaces and original clocks/deadlines. No physical claim.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess
import textwrap
import audit_segmented_receive as binding
import segmented_write_rnr_native_fixture as fixture
import probe_segmented_write_rnr_native_full as runner

ROOT=binding.ROOT;digest=binding.digest
PREIMAGES={
    'receive-write-rnr-ack-001':{'rdma/rnic/tests/probe_receive_write_rnr_ack.py':'rdma/rnic/build/receive-write-rnr-ack-001-preimages-LOpObDRu'},
    'segmented-write-rnr-control-001':{'rdma/rnic/tests/probe_segmented_write_rnr_control.py':'rdma/rnic/build/write-rnr-control-001-preimages-xkKXfWO0'},
    'segmented-write-rnr-control-002':{'rdma/rnic/tests/probe_segmented_write_rnr_control.py':'rdma/rnic/build/write-rnr-control-002-preimages-BqnQDBka'},
}


def cases(source):
    a=source.index("        cases=[('CAS'");b=source.index('        for name,opcode,immediate,args,zero,capacity in cases:',a)
    ns={};exec(compile(textwrap.dedent(source[a:b]),'<pure frozen case descriptors>','exec'),ns)
    return ns['cases']


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve every previous report')
    records={};ids={}
    for name in ['receive-write-rnr-ack-002','segmented-write-rnr-control-003',
        'write-rnr-control-observer-001','segmented-write-rnr-native-elaboration-001',
        'segmented-write-profile-native-full-001','segmented-write-rnr-native-full-001',*PREIMAGES]:
        records[name],ids[name]=binding.bindings(name,PREIMAGES.get(name))
    ack=records['receive-write-rnr-ack-002'];control=records['segmented-write-rnr-control-003']
    elab=records['segmented-write-rnr-native-elaboration-001'];old=records['segmented-write-profile-native-full-001']
    if not all(r['pass_test']for r in [ack,control,elab,old])or len(ack['tests'])!=78 or len(ack['legacy_tests'])!=2 or len(control['tests'])!=24 or len(old['tests'])!=36:
        raise ValueError('exact real component78+2/controller24/previous actual native36 required')
    if ack['RNR_real_MAC_frames']!=4 or ack['full_native_integration']or control['actual_native_or_HLS_or_MAC']or elab['complete_native_RNR_retry_runtime']:
        raise ValueError('component/elaboration scope must not become native RNR proof')
    if any(records[n]['pass_test']for n in PREIMAGES)or records['segmented-write-rnr-native-full-001']['pass_test']:
        raise ValueError('every original failed report remains failed')
    observer=records['write-rnr-control-observer-001']
    if not observer['diagnostic_completed']or not observer['failed_test_still_failed']or not observer['source_unchanged']:
        raise ValueError('read-only observer is not a positive test result')
    pre=ROOT/PREIMAGES['segmented-write-rnr-control-002']['rdma/rnic/tests/probe_segmented_write_rnr_control.py']/'rdma/rnic/tests/probe_segmented_write_rnr_control.py'
    current=(ROOT/'rdma/rnic/tests/probe_segmented_write_rnr_control.py').read_text()
    replacement='''      // Observe after continuous assignments settle, within the SAME4ns cycle.
      // Frozen002 plus the read-only observer retain the original failure.
      @(negedge clk);s_valid=0;#1;'''
    if pre.read_text().replace('      @(negedge clk);s_valid=0;',replacement,1)!=current:
        raise ValueError('only the checked same-cycle settling observation may change')
    for r in [ack,control]:
        if (r['compile_limit_seconds'],r['runtime_limit_seconds'],r['clock_ns'],r['cycle_limit'])!=(10,10,4,100000):
            raise ValueError('original four-state bounded gates required')
        if any(v['exit']or v['seconds']>10 for v in r['tests'].values()):raise ValueError('all component executions must actually pass')
    oldbench=fixture.parent.bench();newbench=fixture.bench()
    olddir=ROOT/old['directory']
    if (olddir/'tb.v').read_text()!=oldbench:raise ValueError('exact original actual native bench required')
    fatal=lambda s:set(re.findall(r'\$fatal\([^,]+,"([^"]+)',s))
    if len(fatal(oldbench))!=364 or fatal(oldbench)-fatal(newbench):raise ValueError('every364 original fatal message required')
    oldrunner=next(ROOT/n for n in old['source_sha256']if n.endswith('/native_runner.py'))
    oldcases=cases(oldrunner.read_text());newcases=cases(runner.runner_source())
    if len(oldcases)!=36 or len(newcases)!=37 or newcases[1:]!=oldcases or set(old['tests'])!={r[0]for r in oldcases}:
        raise ValueError('all original36 case names/opcodes/order/arguments/zero/capacity recipes must remain exact')
    if newcases[0]!=('LARGE_RX_WRITE_RNR',9,0x89abcdef,['+LARGE_WRITE_RX','+LARGE_RX_OP=5','+WRITE_RNR_RETRY'],False,-3):
        raise ValueError('explicit actual empty-LAST-RQ RNR/same-PSN retry recipe required')
    if fixture.large_write_variant is not fixture.parent.large_write_variant or 'force 'in newbench:
        raise ValueError('unchanged raw packet generation and no internal injection required')
    failed=records['segmented-write-rnr-native-full-001']
    if failed['tests']or 'bench_elaborate_command'in failed or failed['error_type']!='ValueError'or 'source derivation anchor changed:'not in failed['error']:
        raise ValueError('original fixture startup failure cannot be runtime proof')
    pre_root=ROOT/'rdma/rnic/build/write-rnr-native-full-001-preimages-DPPmoAxn'
    frozen=[pre_root/'rdma/rnic/tests'/n for n in ['segmented_write_rnr_native_fixture.py','probe_segmented_write_rnr_native_full.py','segmented_write_rnr_native_sources.py']]
    if not all(q.is_file()for q in frozen):raise ValueError('exact failed native fixture preimages required')
    for n,h in binding.PROTECTED.items():
        if digest(ROOT/n)!=h:raise ValueError('protected original raw source changed')
    check=subprocess.run(['bash','scripts/check.sh'],cwd=ROOT,capture_output=True,text=True,timeout=30)
    sources=[Path(__file__).resolve(),Path(fixture.__file__).resolve(),Path(runner.__file__).resolve(),
        ROOT/'rdma/rnic/tests/segmented_write_rnr_native_sources.py']
    result=dict(scope=__doc__,audit_passed=True,overall_goal_complete=False,evidence=ids,
        verified_bindings=sum(v['bindings_verified']for v in ids.values()),actual_ACK_component_modes=78,actual_legacy_fixtures=2,
        actual_new_MAC_mixed_frames=4,actual_RNR_controller_cases=24,actual_native_elaboration_seconds=elab['compile_seconds'],
        previous_actual_native_cases=36,new_planned_native_cases=37,all36_prior_case_recipes_identical=True,
        original_fatal_messages_retained=len(fatal(oldbench)),new_fatal_messages=len(fatal(newbench)-fatal(oldbench)),
        exact_previous_native_bench_sha256=digest(olddir/'tb.v'),all_raw_WRITE_inputs_unchanged=True,
        same_cycle_observation_fix_only=True,original_failures_preserved=True,source_sha256={str(q.relative_to(ROOT)):digest(q)for q in sources},
        failed_native_fixture_preimage_sha256={str(q.relative_to(ROOT)):digest(q)for q in frozen},protected_raw_sha256=binding.PROTECTED,
        inherited_source_check=dict(exit=check.returncode,stdout=check.stdout,stderr=check.stderr,overall_suite_passed=check.returncode==0),
        native_RNR_runtime_qualified=False,full_board_timing=False,hardware_verified=False,
        remaining=['Actual fresh native37 runtime; no component/fixture/elaboration proof substitutes for it.',
            'All11/full1MiB/multiSGE/live Linux/provider refs/real-peer NAK/RNR/retry/MSN/congestion/partial-HLS cleanup/original timing/physical remain.'],
        hardware_or_default_actions=[],commit_or_push=False)
    with a.report.open('x')as f:f.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(audit_passed=True,verified_bindings=result['verified_bindings'],old_cases=36,planned_cases=37,native_RNR_runtime=False)),flush=True)


if __name__=='__main__':main()
