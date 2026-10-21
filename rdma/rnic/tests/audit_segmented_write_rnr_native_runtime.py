#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual fresh native37 RNR/retry and all36 old regressions, not hardware.

Same generated HLS/MR/PTE/PCIe/nonce/fence/MAC/PSN/whole CQ execute together.
Physical host/root/peer/PHY/PTP are modeled; original timing/all11 remain.
"""
import argparse
import json
from pathlib import Path
import re
import audit_segmented_receive as binding

ROOT=binding.ROOT;digest=binding.digest


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve every previous report')
    names=['segmented-write-rnr-native-full-002','segmented-write-profile-native-full-001',
        'segmented-write-rnr-native-elaboration-001','segmented-write-rnr-native-source-diagnostics-001',
        'segmented-write-owned-generated-hls-001']
    records={};ids={}
    for n in names:records[n],ids[n]=binding.bindings(n)
    native,old,elab,source,hls=[records[n]for n in names]
    if not all(native.get(k)for k in ['pass_test','source_unchanged','actual_generated_HLS','actual_complete_native_graph',
        'both_global_drains_zero','native_controller_inserted','complete_native_RNR_retry_runtime','all36_prior_cases_retained']):
        raise ValueError('actual fresh complete native RNR/samePSN retry required')
    if len(native['tests'])!=37 or len(old['tests'])!=36 or set(native['tests'])!=set(old['tests'])|{'LARGE_RX_WRITE_RNR'}:
        raise ValueError('every exact36 old case plus new RNR case required')
    if (native['RNC_features'],native['CQC_features'],native['SQC_features'],native['RQC_features'],native['software_profile'])!=(131071,511,13,63,8):
        raise ValueError('same explicit private identity required')
    if native['compile_exit']or native['compile_limit_seconds']!=1200 or native['simulation_limit_seconds']!=30 or native['compilation_seconds']>1200 or \
       any(r['exit']or r['seconds']>30 for r in native['tests'].values()):raise ValueError('original bounded compile/runtime gates required')
    for n,r in old['tests'].items():
        if native['tests'][n]['runtime_input_sha256']!=r['runtime_input_sha256']or ('summary'in r and native['tests'][n].get('summary')!=r['summary']):
            raise ValueError('old raw inputs or summary oracle changed:'+n)
    test=native['tests']['LARGE_RX_WRITE_RNR'];wanted=dict(pass_test=True,bytes=8193,packets=3,MR_queries=5,commands=3,
        fences=3,native_PSN_commits=3,WRITE_Immediate=1,notification_capacity=0,RNR=1,same_PSN_retry=1,fresh_ACKs=4)
    if test['summary']!=wanted or not all(test.get(k)for k in ['every_payload_and_sentinel_byte','actual_native_RNR_and_same_PSN_retry','zero_capacity_genuine_RQ']):
        raise ValueError('actual RNR/retained MR/PSN/true zero-RQ/whole CQ scope required')
    if test['runtime_input_sha256']!=old['tests']['LARGE_RX_WRITE_IMM']['runtime_input_sha256']:
        raise ValueError('identical raw LAST input and posted C128 records required')
    frames=test['actual_XGMII_frames']
    if len(frames)!=4 or [r['tag']for r in frames]!=[0x6001,0x6002,0x6003,0x6004]:raise ValueError('one shared fresh-tag negative/positive sequence required')
    decoded=[bytes.fromhex(r['frame_hex'])for r in frames]
    if [(r[54],int.from_bytes(r[51:54],'big'),int.from_bytes(r[55:58],'big'))for r in decoded]!=[
        (0,0x987654,0),(0,0x987655,0),(0x20,0x987656,0),(0,0x987656,1)]:raise ValueError('actual negative/positive syndrome/PSN/MSN required')
    run=ROOT/native['directory'];oldrun=ROOT/old['directory']
    snapshot=run/'LARGE_RX_WRITE_RNR-event.hex';rq=run/'LARGE_RX_WRITE_RNR-receive-records.hex'
    for new,previous in [(snapshot,oldrun/'LARGE_RX_WRITE_IMM-event.hex'),(rq,oldrun/'LARGE_RX_WRITE_IMM-receive-records.hex')]:
        if new.read_bytes()!=previous.read_bytes():raise ValueError('unedited wholeCQ/RQ bytes must retain exact source ABI')
    if native['binary_sha256']==old['binary_sha256']or native['compile_directory']==old['compile_directory']:
        raise ValueError('fresh actual executable/object directory required')
    vvp=next(Path(n)for n in native['RAM_artifact_sha256']if Path(n).name=='tb.vvp').read_text()
    counts={n:len(re.findall(r'\.scope module, "[^"]+" "'+n+r'"',vvp))for n in elab['module_counts']}
    if counts!=elab['module_counts']:raise ValueError('actual executable sole native namespaces/controller/ACK hierarchy required')
    genroot=ROOT/hls['directory']/'project/solution1/syn/verilog'
    if {Path(n).name for n in native['source_sha256']if(ROOT/n).parent==genroot}!=set(hls['generated_sha256']):
        raise ValueError('entire SAME-generation HLS RTL/data required')
    if not source['audit_passed']or source['original_fatal_messages_retained']!=364 or hls['original_effective_period_met']:
        raise ValueError('original regression/timing boundaries must remain')
    for n,h in binding.PROTECTED.items():
        if digest(ROOT/n)!=h:raise ValueError('protected original raw source changed')
    result=dict(scope=__doc__,audit_passed=True,evidence=ids,verified_bindings=sum(v['bindings_verified']for v in ids.values()),
        actual_native_cases=37,all36_old_inputs_and_summary_oracles_identical=True,actual_RNR_and_same_PSN_retry=True,
        actual_generated_HLS_MR_PTE_PCIe_nonce_fence_MAC_PSN_CQ=True,actual_native_module_counts=counts,
        compilation_seconds=native['compilation_seconds'],maximum_case_seconds=max(r['seconds']for r in native['tests'].values()),
        fresh_binary_sha256=native['binary_sha256'],unedited_CQ_matches_prior_ABI=True,zero_capacity_RQ_record_matches_prior_ABI=True,
        source_sha256={str(Path(__file__).relative_to(ROOT)):digest(__file__),str(snapshot.relative_to(ROOT)):digest(snapshot),str(rq.relative_to(ROOT)):digest(rq)},
        protected_raw_sha256=binding.PROTECTED,UNOPTFLAT_warnings=(run/'compile.log').read_text().count('%Warning-UNOPTFLAT:'),warning_waivers=False,
        live_Linux_or_physical=False,real_peer_RNR_retry=False,full_board_timing=False,overall_goal_complete=False,
        remaining=['All11/full1MiB native/multiSGE/live Linux/provider refs/real-peer NAK/RNR/retry/MSN/congestion/safe partial-HLS cleanup/original timing/physical remain.'])
    with a.report.open('x')as f:f.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(audit_passed=True,verified_bindings=result['verified_bindings'],actual_native_cases=37,physical=False)),flush=True)


if __name__=='__main__':main()
