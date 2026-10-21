#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual fresh native38 NAK/suppression/retry/duplicate, NOT live hardware.

Require every old37 raw/summary oracle and actual same-core control/data/
MR/PTE/PCIe/nonce/fence/MAC/PSN/RQ/CQ execution. Elaboration is not runtime.
"""
import argparse
import json
from pathlib import Path
import re
import audit_segmented_receive as binding

ROOT=binding.ROOT;digest=binding.digest


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True)
    p.add_argument('--native-record',default='write-psn-control-native-full-001');a=p.parse_args()
    if a.report.exists():p.error('preserve previous evidence')
    if not re.fullmatch(r'write-psn-control-native-full-\d{3}',a.native_record):p.error('exact native control runtime record required')
    names=[a.native_record,'segmented-write-rnr-native-full-002','write-psn-control-native-elaboration-001',
        'write-psn-control-native-fixture-diagnostics-002','control-response-generated-hls-001','write-psn-control-native-diagnostics-001']
    records={};ids={}
    for n in names:records[n],ids[n]=binding.bindings(n)
    native,old,elab,fixture,hls,source=[records[n]for n in names]
    if not all(native.get(k)for k in ['pass_test','source_unchanged','actual_generated_HLS','actual_complete_native_graph',
        'both_global_drains_zero','native_controller_inserted','complete_native_PSN_control_runtime','all37_prior_cases_retained']):
        raise ValueError('actual fresh complete native PSN control execution required')
    if len(native['tests'])!=38 or len(old['tests'])!=37 or set(native['tests'])!=set(old['tests'])|{'LARGE_RX_WRITE_PSN'}:
        raise ValueError('every actual37 old case plus complete new PSN control scenario required')
    if (native['RNC_features'],native['CQC_features'],native['SQC_features'],native['RQC_features'],native['software_profile'])!=(131071,511,13,63,8):
        raise ValueError('original explicit private profile8 tuple required')
    if native['compile_exit']or native['compile_limit_seconds']!=1200 or native['simulation_limit_seconds']!=30 or \
       native['compilation_seconds']>1200 or any(t['exit']or t['seconds']>30 for t in native['tests'].values()):
        raise ValueError('all original actual compile/runtime bounds required')
    if not fixture['audit_passed']or not fixture['all37_case_recipes_and_raw_inputs_identical']or \
       fixture['original_fatal_messages_retained']!=378 or not source['audit_passed']:
        raise ValueError('actual exact prior378 checks/old37 recipes/raw inputs and certified frontend/native sources required')
    for n,t in old['tests'].items():
        current=native['tests'][n]
        if current['runtime_input_sha256']!=t['runtime_input_sha256']or ('summary'in t and current.get('summary')!=t['summary']):
            raise ValueError('old raw input or summary oracle changed:'+n)
        for field in ['actual_XGMII_frames','host_snapshot_sha256','full620_CQ_owner']:
            if field in t and current.get(field)!=t[field]:raise ValueError('old independent data/wire/owner oracle changed:'+n+':'+field)
    test=native['tests']['LARGE_RX_WRITE_PSN']
    wanted=dict(pass_test=True,bytes=8193,packets=3,MR_queries=4,commands=3,fences=3,native_PSN_commits=3,
        WRITE_Immediate=1,notification_capacity=0,NAK=1,NAK_suppressed=1,duplicate_ACKs=2,fresh_ACKs=6,local_rejects=4,whole_CQ=1)
    if test['summary']!=wanted or not all(test.get(k)for k in ['every_payload_and_sentinel_byte','actual_native_PSN_control',
        'suppressed_repeat_has_no_wire_proof','duplicate_has_no_second_DMA_RQ_CQ','zero_capacity_genuine_RQ']):
        raise ValueError('actual complete NAK/suppression/same-PSN retry/duplicate-no-repeat cardinality required')
    expected_inputs=dict(old['tests']['LARGE_RX_WRITE_IMM']['runtime_input_sha256'])
    expected_inputs['write-psn-future-input.hex']=fixture['new_future_input_sha256']
    if test['runtime_input_sha256']!=expected_inputs:raise ValueError('same genuine positive frames/RQ plus independent future MID required')
    frames=test['actual_XGMII_frames']
    if len(frames)!=6 or [t['tag']for t in frames]!=list(range(0x6001,0x6007)):
        raise ValueError('one shared actual fresh control/data tag sequence required')
    decoded=[bytes.fromhex(t['frame_hex'])for t in frames]
    if [(f[54],int.from_bytes(f[51:54],'big'),int.from_bytes(f[55:58],'big'))for f in decoded]!=[
        (0,0x987654,0),(0x60,0x987655,0),(0,0x987655,0),(0x1f,0x987655,0),(0,0x987656,1),(0x1f,0x987656,1)]:
        raise ValueError('actual all six wire syndrome/PSN/real-MSN values required')
    run=ROOT/native['directory'];oldrun=ROOT/old['directory']
    cq=run/'LARGE_RX_WRITE_PSN-event.hex';rq=run/'LARGE_RX_WRITE_PSN-receive-records.hex'
    if cq.read_bytes()!=(oldrun/'LARGE_RX_WRITE_IMM-event.hex').read_bytes()or \
       rq.read_bytes()!=(oldrun/'LARGE_RX_WRITE_IMM-receive-records.hex').read_bytes():
        raise ValueError('unedited actual wholeCQ/RQ retains exact previous ABI')
    frozen=next(ROOT/n for n in native['source_sha256']if n.endswith('/native_runner.py'))
    if digest(frozen)!=fixture['exact_new_runner_sha256']or digest(run/'tb.v')!=fixture['exact_new_bench_sha256']:
        raise ValueError('actual compiled/executed fixture must be the exact qualified preflight')
    if native['binary_sha256']==old['binary_sha256']or native['compile_directory']==old['compile_directory']:
        raise ValueError('fresh actual executable/objects required, never old binary reuse')
    vvp=next(Path(n)for n in native['RAM_artifact_sha256']if Path(n).name=='tb.vvp').read_text()
    counts={n:len(re.findall(r'\.scope module, "[^"]+" "'+n+r'"',vvp))for n in elab['module_counts']}
    if counts!=elab['module_counts']:raise ValueError('actual sole native/HLS/MR/PTE/backend/nonce/ACK namespaces required')
    genroot=ROOT/hls['directory']/'project/solution1/syn/verilog'
    if {Path(n).name for n in native['source_sha256']if(ROOT/n).parent==genroot}!=set(hls['generated_sha256'])or \
       hls['HLS_top']!='rocev2_native_control_response_top'or len(hls['generated_sha256'])!=197:
        raise ValueError('entire actual SAME new control HLS RTL/data cohort required')
    if (float(hls['target_clock_period']),float(hls['clock_uncertainty']))!=(4,1.08)or hls['original_effective_period_met']:
        raise ValueError('original timing failure must not be waived or reclassified')
    for n,h in binding.PROTECTED.items():
        if digest(ROOT/n)!=h:raise ValueError('protected raw source changed:'+n)
    result=dict(scope=__doc__,audit_passed=True,evidence=ids,verified_bindings=sum(v['bindings_verified']for v in ids.values()),
        actual_native_cases=38,all37_old_inputs_summary_and_independent_data_wire_owner_oracles_identical=True,
        actual_NAK_suppression_retry_duplicate_no_second_DMA_RQ_CQ=True,actual_full480_512_528_same_owner_proofs=True,
        actual_generated_HLS_MR_PTE_PCIe_nonce_fence_MAC_PSN_CQ=True,actual_native_module_counts=counts,
        compilation_seconds=native['compilation_seconds'],maximum_case_seconds=max(t['seconds']for t in native['tests'].values()),
        fresh_binary_sha256=native['binary_sha256'],unedited_CQ_matches_prior_ABI=True,zero_RQ_matches_prior_ABI=True,
        source_sha256={str(q.relative_to(ROOT)):digest(q)for q in [Path(__file__).resolve(),cq,rq]},protected_raw_sha256=binding.PROTECTED,
        UNOPTFLAT_warnings=(run/'compile.log').read_text().count('%Warning-UNOPTFLAT:'),warning_waivers=False,
        live_Linux_or_physical=False,real_peer_PSN_retry=False,fatal_QP_error_and_teardown_qualified=False,
        original_timing_met=False,full_board_timing=False,overall_goal_complete=False,
        remaining=['All11/full1MiB native/multiSGE/live registered Linux/provider refs/proper fatal-QP quarantine/partial-HLS cleanup/real-peer NAK-RNR-retry-MSN-congestion/original board timing/physical remain.'])
    with a.report.open('x')as f:f.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(audit_passed=True,verified_bindings=result['verified_bindings'],actual_native_cases=38,physical=False)))


if __name__=='__main__':main()
