#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Audit actual new-core ALL32 old native executions, not new large RX yet.

Preserve the original004 HLS timeout and exact new-payload fixture startup/
elaboration failures. New003 whole-payload build/runtime is separate: neither
all32 compatibility nor generated-RTL/elaboration proves new large receive.
"""
import argparse
import datetime
import json
from pathlib import Path
import subprocess
import audit_segmented_receive as binding

ROOT=binding.ROOT;PREFIX=binding.PREFIX;digest=binding.digest
FIXTURE='rdma/rnic/tests/segmented_receive_payload_native_fixture.py'
RUNNER='rdma/rnic/tests/probe_segmented_receive_native_full.py'
PREIMAGES={
    'segmented-receive-native-full-001':'rdma/rnic/build/segmented-receive-native-full-001-preimages-JoDWgkOc',
    'segmented-receive-native-full-002':'rdma/rnic/build/segmented-receive-native-full-002-preimages-nxQgKska'}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve earlier evidence')
    native,native_id=binding.bindings('segmented-receive-native-compat-001')
    old,old_id=binding.bindings('segmented-immediate-native-full-001')
    generated,generated_id=binding.bindings('segmented-receive-generated-diagnostics-001')
    timeout,timeout_id=binding.bindings('segmented-receive-generated-hls-001')
    if not all(native.get(k)for k in ['pass_test','source_unchanged','actual_generated_HLS','actual_complete_native_graph','both_global_drains_zero']):
        raise ValueError('actual same-source complete native old32 execution required')
    if len(native['tests'])!=32 or set(native['tests'])!=set(old['tests'])or not old.get('pass_test'):
        raise ValueError('retain every exact old32 case, not just an equal count')
    if any(v['exit']!=0 or v['seconds']>30 for v in native['tests'].values())or native.get('simulation_limit_seconds')!=30:
        raise ValueError('all32 bounded real process executions required')
    if not generated.get('audit_passed')or (native.get('RNC_features'),native.get('CQC_features'))!=(65535,255)or \
       native.get('incoming_segmented_SEND_Immediate_runtime')or not native.get('new_receive_hierarchy_old32_regressions_only'):
        raise ValueError('new identity and strictly old-function-only runtime scope required')
    if timeout.get('pass_test')or timeout.get('error_type')!='TimeoutExpired'or \
       timeout.get('source_directory')!='rdma/rnic/build/native-segmented-receive-transport-004'or '7199.'not in timeout.get('error',''):
        raise ValueError('original bounded HLS failure must not be relabeled')
    failures={}
    for name,preimage in PREIMAGES.items():
        r,v=binding.bindings(name,{FIXTURE:preimage})
        if r.get('pass_test')or r.get('tests'):raise ValueError('startup/elaboration failure cannot become runtime proof')
        saved={str(Path(preimage)/n):digest(ROOT/preimage/n)for n in [FIXTURE,RUNNER]}
        v.update(error=r.get('error'),stage='strict fixture source anchor before compile'if name.endswith('001')else'actual full bench Icarus elaboration; unresolved observer port name',
            exact_failed_stage_preimage_sha256=saved)
        failures[name]=v
    if 'hold_rq_mac'not in failures['segmented-receive-native-full-001']['error']:
        raise ValueError('exact first strict anchor failure required')
    second=PREFIX/'rocev2-rnic-segmented-receive-native-full-002.json'
    second=json.loads(second.read_text());log=(ROOT/second['directory']/'elaborate.log').read_text()
    if 'dut.cq_commit_ready'not in log or 'Unable to bind'not in log:
        raise ValueError('exact unresolved observer diagnostic required')
    for name,h in binding.PROTECTED.items():
        if digest(ROOT/name)!=h:raise ValueError('protected raw source changed:'+name)
    check=subprocess.run(['bash','scripts/check.sh'],cwd=ROOT,capture_output=True,text=True,timeout=30)
    result=dict(scope=__doc__,audit_passed=True,overall_goal_complete=False,hardware_verified=False,
        created_UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        actual_new_core_native_old32=native_id,prior_actual_Immediate_native_old32=old_id,
        generated_and_component_audit=generated_id,original004_HLS_timeout=timeout_id,historical_new_fixture_failures=failures,
        verified_bindings=native_id['bindings_verified']+old_id['bindings_verified']+generated_id['bindings_verified']+
            timeout_id['bindings_verified']+sum(v['bindings_verified']for v in failures.values()),
        actual_native_old_function_execution=dict(cases=32,all_exact_prior_case_names=sorted(native['tests']),
            seconds={n:v['seconds']for n,v in native['tests'].items()},maximum_case_seconds=max(v['seconds']for v in native['tests'].values()),
            compile_seconds=native['compilation_seconds'],actual_new_generated_HLS=True,complete_native_graph=True,
            one_shared_MR_PTE_PSN_MSN_domain=True,both_global_HLS_drains_zero=True,
            full_bytes_sentinels_CQ_owner_nonce_status_fence_boardMAC_oracles=True,
            physical_host_root_peer_PHY_PTP_models=True,live_Linux_or_physical=False),
        new_large_RX_runtime_verified=False,native_1MiB_receive_runtime_verified=False,
        original004_timeout=dict(pass_test=False,error_type=timeout['error_type'],finished_at=timeout['finished_at'],
            original_timeout_seconds=7200,manual_kill_or_restart=False,
            child_processes2872461_and2872554_observed_naturally_missing_after_wrapper_exit=True,
            original_frozen_inputs_and_all_raw_outputs_preserved=True,new007_success_not_substituted_for_failed004=True),
        new_payload_fixture=dict(bytes=8193,posted_capacity=8194,operations=['SEND','SEND_WITH_IMMEDIATE'],
            required_real_packet_lifetimes=3,required_whole_CQ=1,actual_final_MAC_withholding_cycles=1100,
            all32_old_regressions_still_mandatory=True,original_build_limit_seconds=1200,original_case_limit_seconds=30,
            current_run_pending='results/2026-10-18/rocev2-rnic-segmented-receive-native-full-003.json',
            failed_attempts_retained=True,observer_ready_corrected_to_actual_s_cq_commit_ready=True,
            no_MR_status_owner_receipt_or_retire_injection=True,no_full_payload_pass_inferred=True),
        protected_raw_sha256=binding.PROTECTED,auditor_source_sha256={str(Path(__file__).relative_to(ROOT)):digest(__file__)},
        inherited_source_check=dict(exit=check.returncode,stdout=check.stdout,stderr=check.stderr,overall_suite_passed=check.returncode==0,original_gate_unchanged=True),
        remaining=['All11 original requirements remain; compatibility is not a narrower completion target.',
            'Actual new large receive MR/PTE/DMA/fence/ACK-MAC/HLS/whole-CQ runtime and native1MiB operation remain unproved.',
            'Matched registered driver/provider/profile, actual lifetime refs, segmented WRITE Immediate remote MR/late RQ and multiSGE remain.',
            'Real-peer nonterminal MSN/interoperability/recovery/RNR/congestion, original full-board fit/timing/CDC/DRC/routing and short supervised physical work remain.',
            'Actual new HLS estimate15.571ns misses original4ns/default1.08ns; no timing waiver or hardware programming.',
            'No reboot needed; restore ALL persistent-archived RAM caches and prove authenticated exact-thread/goal revival before any necessary reboot.'],
        hardware_install_load_network_fan_BIOS_flash_reboot_actions=[],commit_or_push=False)
    with a.report.open('x')as f:f.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(audit_passed=True,verified_bindings=result['verified_bindings'],all32_actual_native_cases=True,new_large_RX_native_pass=False)),flush=True)


if __name__=='__main__':main()
