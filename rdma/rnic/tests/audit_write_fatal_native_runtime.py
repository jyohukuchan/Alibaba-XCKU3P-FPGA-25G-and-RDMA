#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual native40 fatal61/62/abort/cancel and exact prior38 regressions.

The selected1000 receipt is NOT standard error CQ, STOP, global drain,
safe unpin, physical interoperability or original full-board timing proof.
"""
import argparse
import json
from pathlib import Path
import re
import audit_segmented_receive as binding
import write_fatal_native_fixture as fixture

ROOT=binding.ROOT;digest=binding.digest
NEW={'LARGE_RX_WRITE_FATAL_ACCESS','LARGE_RX_WRITE_FATAL_PARTIAL'}


class CaseSnapshots:
    """Use each untouched archived case, not the final case's shared files."""
    def __init__(self,run,name):self.run=run;self.name=name
    def __truediv__(self,leaf):
        suffix={'write-fatal-selected.hex':'selected.hex',
            'write-fatal-rq-owner.hex':'rq-owner.hex',
            'large-write-receive-host.hex':'host.hex'}[leaf]
        return self.run/(self.name+'-'+suffix)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--report',type=Path,required=True)
    p.add_argument('--native-record',default='write-fatal-native-full-001')
    a=p.parse_args()
    if a.report.exists():p.error('preserve previous evidence')
    if not re.fullmatch(r'write-fatal-native-full-\d{3}',a.native_record):
        p.error('exact actual fatal native execution record required')
    names=[a.native_record,'write-psn-control-native-full-001',
        'write-fatal-native-elaboration-001','write-fatal-native-fixture-diagnostics-001',
        'write-abort-generated-hls-001','write-abort-generated-diagnostics-001',
        'write-fatal-native-source-diagnostics-001','write-psn-control-native-runtime-diagnostics-001']
    records={};ids={}
    for n in names:records[n],ids[n]=binding.bindings(n)
    native,old,elab,preflight,hls,generated,source,old_audit=[records[n]for n in names]
    required=['pass_test','source_unchanged','actual_generated_HLS','actual_complete_native_graph',
        'native_controller_inserted','both_global_drains_zero',
        'complete_native_fatal61_62_selected_runtime','all38_prior_cases_retained']
    if not all(native.get(k)for k in required)or not old['pass_test']or not old_audit['audit_passed']:
        raise ValueError('fresh complete new native packet execution AND qualified old38 required')
    if len(native['tests'])!=40 or len(old['tests'])!=38 or set(native['tests'])!=set(old['tests'])|NEW:
        raise ValueError('every old38 case plus two genuine native fatal cases required')
    if (native['RNC_features'],native['CQC_features'],native['SQC_features'],native['RQC_features'],native['software_profile'])!=(131071,511,13,63,8):
        raise ValueError('unchanged explicit private profile8 required')
    if native['compile_exit'] or native['compile_limit_seconds']!=1200 or native['compilation_seconds']>1200 or \
       native['simulation_limit_seconds']!=30 or any(t['exit']or t['seconds']>30 for t in native['tests'].values())or \
       native['bench_elaborate_seconds']>180 or native['simulation_CXX_optimization']!='-O1' or \
       native['compiler_output_split_cfuncs']!=500000 or not native['compile_owns_process_group']:
        raise ValueError('original compilation/each runtime/elaboration/optimization/process-group gates required')
    if not all(r['audit_passed']for r in [preflight,generated,source])or not hls['pass_test']or \
       not preflight['all38_case_recipes_and_raw_inputs_identical']or preflight['planned_native_cases']!=40 or \
       preflight['original_fatal_messages_retained']!=391 or preflight['new_fatal_messages']!=28:
        raise ValueError('actual exact prior391 checks/old38 recipes/new40 fixture and source/cohort audits required')
    # Compare every prior result/oracle, not just selected green summaries.
    # Wall-clock seconds are the sole intentionally non-identical field.
    for name,prior in old['tests'].items():
        current=native['tests'][name]
        if {k:v for k,v in current.items()if k!='seconds'}!={k:v for k,v in prior.items()if k!='seconds'}:
            raise ValueError('an original38 input/outcome/data/wire/owner/nonce oracle changed:'+name)
    run=ROOT/native['directory'];observed={};snapshot_paths=[]
    for name,partial in [('LARGE_RX_WRITE_FATAL_ACCESS',False),('LARGE_RX_WRITE_FATAL_PARTIAL',True)]:
        t=native['tests'][name];log=run/(name+'.log')
        posted=[int(line,16).to_bytes(128,'little')for line in (run/(name+'-receive-records.hex')).read_text().splitlines()]
        checked=fixture.verify_fatal(log.read_text(),posted,partial,CaseSnapshots(run,name))
        if any(t.get(k)!=v for k,v in checked.items()):
            raise ValueError('actual case result differs from unedited log/frame/selected/RQ/host snapshots:'+name)
        nonce=fixture.verify_nonce(log.read_text())
        expected_nonce=dict(admitted=int(partial),issued=int(partial),backend_completed=int(partial),
            logical_completed=int(partial),translated=int(partial),active=0,fault=0)
        if nonce!=expected_nonce or t['actual_common_nonce_backend']!=nonce:
            raise ValueError('actual common physical nonce must count only the genuine FIRST data command:'+name)
        inputs=dict(old['tests']['LARGE_RX_WRITE_IMM']['runtime_input_sha256'])
        inputs['write-fatal-input.hex']=preflight['new_fatal_inputs'][name]['input_sha256']
        if t['runtime_input_sha256']!=inputs:
            raise ValueError('same original positive frames/coherent zero-RQ plus authored bad frame required:'+name)
        wire=t['actual_XGMII_frames'];decoded=[bytes.fromhex(v['frame_hex'])for v in wire]
        expected_wire=[(0,0x987654,0),(0x61,0x987655,0)]if partial else[(0x62,0x987654,0)]
        if [v['tag']for v in wire]!=list(range(0x6001,0x6001+len(expected_wire)))or \
           [(f[54],int.from_bytes(f[51:54],'big'),int.from_bytes(f[55:58],'big'))for f in decoded]!=expected_wire:
            raise ValueError('actual positive/fatal wire uses genuine fresh shared tags/current PSN/MSN0:'+name)
        if any((run/(name+'-'+suffix)).exists()for suffix in ['event.hex','success-CQ.hex','error-CQ.hex']):
            raise ValueError('selected proof and retained RQ cannot be relabeled as a success/error CQ:'+name)
        observed[name]=dict(summary=t['summary'],actual_common_nonce_backend=nonce,
            full_control_owner480=t['full_control_owner480'],full_abort_owner960=t['full_abort_owner960'],
            full_selected1000=t['full_selected1000'],full_retained_RQ620=t['full_retained_RQ620'],
            actual_XGMII_frames=wire,host_snapshot_sha256=t['host_snapshot_sha256'])
        snapshot_paths.extend([log,*[run/(name+'-'+suffix)for suffix in ['selected.hex','rq-owner.hex','host.hex','receive-records.hex','write-fatal-input.hex']]])
    frozen=[ROOT/n for n in native['source_sha256']if n.endswith('/native_runner.py')]
    if len(frozen)!=1 or digest(frozen[0])!=preflight['exact_new_runner_sha256']or digest(run/'tb.v')!=preflight['exact_new_bench_sha256']:
        raise ValueError('actual compiled/executed runner and bench must match qualified preflight exactly')
    if native['binary_sha256']==old['binary_sha256']or native['compile_directory']==old['compile_directory']:
        raise ValueError('fresh actual new executable/objects required, never old binary reuse')
    vvp=next(Path(n)for n in native['RAM_artifact_sha256']if Path(n).name=='tb.vvp').read_text()
    counts={n:len(re.findall(r'\.scope module, "[^"]+" "'+re.escape(n)+r'"',vvp))for n in elab['module_counts']}
    if counts!=elab['module_counts']:
        raise ValueError('actual same complete sole HLS/PSN/MSN/ACK/MR/PTE/backend/nonce/cancel namespaces required')
    genroot=ROOT/hls['directory']/'project/solution1/syn/verilog'
    selected={Path(n).name for n in native['source_sha256']if (ROOT/n).parent==genroot}
    if selected!=set(hls['generated_sha256'])or len(selected)!=208 or hls['HLS_top']!='rocev2_native_write_abort_top':
        raise ValueError('ENTIRE same actual208 abort HLS cohort required; no old/new core mixture')
    if (float(hls['target_clock_period']),float(hls['clock_uncertainty']))!=(4,1.08)or hls['original_effective_period_met']:
        raise ValueError('original timing failure must remain explicit, never waived/reclassified')
    for n,h in binding.PROTECTED.items():
        if digest(ROOT/n)!=h:raise ValueError('original protected raw source changed:'+n)
    result=dict(scope=__doc__,audit_passed=True,evidence=ids,
        verified_bindings=sum(v['bindings_verified']for v in ids.values()),actual_native_cases=40,
        all38_old_entire_results_except_seconds_identical=True,actual_fatal_cases=observed,
        actual_full480_512_528_960_992_1000_same_owner_proofs=True,
        actual_generated_HLS_MR_PTE_PCIe_nonce_fence_MAC_PSN_cancel=True,
        genuine_queued_zero_RQ_preserved_without_error_CQ=True,quarantine_persists_after_selected_ACK=True,
        actual_native_module_counts=counts,compilation_seconds=native['compilation_seconds'],
        maximum_case_seconds=max(t['seconds']for t in native['tests'].values()),fresh_binary_sha256=native['binary_sha256'],
        source_sha256={str(q.relative_to(ROOT)):digest(q)for q in [Path(__file__).resolve(),*snapshot_paths]},
        protected_raw_sha256=binding.PROTECTED,UNOPTFLAT_warnings=(run/'compile.log').read_text().count('%Warning-UNOPTFLAT:'),
        warnings_not_timing_or_drain_qualification=True,live_Linux_or_physical=False,real_peer_fatal_recovery=False,
        fatal63_implemented=False,standard_error_CQ_STOP_global_drain_or_unpin=False,
        original_timing_met=False,full_board_timing=False,overall_goal_complete=False,
        remaining=['All original11/full1MiB native/multiSGE/live registered Linux-provider refs/real-peer error-RNR-retry-MSN-congestion/original timing/physical remain.',
            'Fatal63, standard error CQ/full QP STOP/recovery, reference retirement and legitimate quarantine release remain; selected1000 alone is not lifetime release.'],
        hardware_or_default_actions=[],commit_or_push=False)
    with a.report.open('x')as f:f.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(audit_passed=True,verified_bindings=result['verified_bindings'],actual_native_cases=40,physical=False)))


if __name__=='__main__':main()
