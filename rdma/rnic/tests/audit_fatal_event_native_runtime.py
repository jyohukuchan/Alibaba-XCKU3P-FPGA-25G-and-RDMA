#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual native40 FEC readback/ACK and every old40 full outcome except time.

The two fatal outcomes have exactly one additional mailbox result. All old
owner/wire/MR/nonce/host/RQ/quarantine results remain mandatory. Not Linux
callbacks, error WC, QP STOP/recovery, global drain/unpin or physical timing.
"""
import argparse
import json
from pathlib import Path
import re
import audit_segmented_receive as binding
import fatal_event_native_fixture as fixture
import fatal_event_native_sources as selection

ROOT=binding.ROOT;digest=binding.digest
NEW={'LARGE_RX_WRITE_FATAL_ACCESS','LARGE_RX_WRITE_FATAL_PARTIAL'}


class CaseSnapshots:
    def __init__(self,run,name):self.run=run;self.name=name
    def __truediv__(self,leaf):
        suffix={'write-fatal-selected.hex':'selected.hex','write-fatal-rq-owner.hex':'rq-owner.hex',
            'large-write-receive-host.hex':'host.hex','write-fatal-mmio.hex':'mmio.hex'}[leaf]
        return self.run/(self.name+'-'+suffix)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True)
    p.add_argument('--native-record',default='fatal-event-native-full-001');a=p.parse_args()
    if a.report.exists():p.error('preserve earlier evidence')
    if not re.fullmatch(r'fatal-event-native-full-\d{3}',a.native_record):p.error('actual new FEC-native run required')
    names=[a.native_record,'write-abort-event-native-full-001','write-abort-event-native-runtime-diagnostics-001',
        'fatal-event-native-elaboration-002','fatal-event-native-source-diagnostics-002',
        'fatal-event-native-fixture-diagnostics-001','write-abort-event-generated-hls-002',
        'write-abort-event-generated-diagnostics-001']
    records={};ids={}
    for n in names:records[n],ids[n]=binding.bindings(n)
    native,old,old_audit,elab,source,preflight,hls,generated=[records[n]for n in names]
    if not all(r.get('pass_test',r.get('audit_passed'))for r in records.values()):
        raise ValueError('actual complete new native40 and original40/source/fixture/HLS qualification required')
    selection.validate(selection.ELABORATION)
    required=['source_unchanged','actual_generated_HLS','actual_complete_native_graph','both_global_drains_zero',
        'actual_fatal_event_mailbox_MMIO_ACK','all40_prior_cases_retained','complete_native_fatal61_62_selected_runtime']
    if not all(native.get(k)for k in required)or len(native['tests'])!=40 or set(native['tests'])!=set(old['tests']):
        raise ValueError('fresh actual FEC-native graph and all40 complete packet results required')
    if (native['RNC_features'],native['CQC_features'],native['SQC_features'],native['RQC_features'],native['software_profile'])!=(131071,511,13,63,8):
        raise ValueError('unchanged private profile8 required')
    if native['compile_exit'] or native['compile_limit_seconds']!=1200 or native['compilation_seconds']>1200 or \
       native['simulation_limit_seconds']!=30 or any(t['exit']or t['seconds']>30 for t in native['tests'].values())or \
       native['bench_elaborate_seconds']>180 or native['simulation_CXX_optimization']!='-O1' or \
       native['compiler_output_split_cfuncs']!=500000 or not native['compile_owns_process_group']:
        raise ValueError('all original compile/runtime/elaboration/optimization/process-group gates required')
    if not preflight['all419_original_assertions_retained']or not preflight['all40_original_recipes_and_raw_bytes_identical']:
        raise ValueError('all419 original assertions and all40 raw inputs required')
    for name,prior in old['tests'].items():
        current=native['tests'][name]
        allowed={'seconds','fatal_event_mailbox'}if name in NEW else{'seconds'}
        if {k:v for k,v in current.items()if k not in allowed}!={k:v for k,v in prior.items()if k!='seconds'}:
            raise ValueError('original40 full input/data/wire/owner/nonce/summary outcome changed:'+name)
        if current['runtime_input_sha256']!=preflight['all40_authored_runtime_inputs'][name]:
            raise ValueError('runtime input differs from exact authored preflight:'+name)
    run=ROOT/native['directory'];observed={};snapshots=[]
    for name,partial in [('LARGE_RX_WRITE_FATAL_ACCESS',False),('LARGE_RX_WRITE_FATAL_PARTIAL',True)]:
        log=run/(name+'.log');posted=[int(l,16).to_bytes(128,'little')for l in(run/(name+'-receive-records.hex')).read_text().splitlines()]
        checked=fixture.verify_fatal(log.read_text(),posted,partial,CaseSnapshots(run,name))
        if any(native['tests'][name].get(k)!=v for k,v in checked.items()):raise ValueError('real full fatal/MMIO snapshot audit mismatch:'+name)
        nonce=fixture.verify_nonce(log.read_text())
        expected=dict(admitted=int(partial),issued=int(partial),backend_completed=int(partial),logical_completed=int(partial),translated=0,active=0,fault=0)
        if nonce!=expected or native['tests'][name]['actual_common_nonce_backend']!=nonce:
            raise ValueError('actual native tag-rewrite/physical nonce proof changed:'+name)
        observed[name]=checked
        snapshots.extend([log,*[run/(name+'-'+n)for n in ['selected.hex','rq-owner.hex','mmio.hex','host.hex','receive-records.hex','write-fatal-input.hex']]])
        if any((run/(name+'-'+n)).exists()for n in ['event.hex','error-CQ.hex','success-CQ.hex']):
            raise ValueError('mailbox ACK cannot be relabeled error/success WC or lifetime retirement')
    frozen=[ROOT/n for n in native['source_sha256']if n.endswith('/native_runner.py')]
    if len(frozen)!=1 or digest(frozen[0])!=preflight['exact_new_runner_sha256']or digest(run/'tb.v')!=preflight['exact_new_bench_sha256']:
        raise ValueError('actual exact frozen preflight runner/extended bench required')
    if native['binary_sha256']==old['binary_sha256']or native['compile_directory']==old['compile_directory']:
        raise ValueError('fresh actual new objects/binary required')
    vvp=next(Path(n)for n in native['RAM_artifact_sha256']if Path(n).name=='tb.vvp').read_text()
    counts={n:len(re.findall(r'\.scope module, "[^"]+" "'+re.escape(n)+r'"',vvp))for n in elab['module_counts']}
    if counts!=elab['module_counts']:raise ValueError('same sole actual FEC/fanout/HLS/MR/PTE/nonce/MAC/PSN/abort/cancel graph required')
    gen=ROOT/hls['directory']/'project/solution1/syn/verilog'
    if {Path(n).name for n in native['source_sha256']if(ROOT/n).parent==gen}!=set(hls['generated_sha256'])or len(hls['generated_sha256'])!=207:
        raise ValueError('whole exact qualified207-file HLS required')
    if (float(hls['target_clock_period']),float(hls['clock_uncertainty']))!=(4,1.08)or \
       hls['original_effective_period_met']!=(float(hls['estimated_clock_period'])<=2.92):
        raise ValueError('original clocks/uncertainty and factual timing verdict required')
    for n,h in binding.PROTECTED.items():
        if digest(ROOT/n)!=h:raise ValueError('protected raw source changed:'+n)
    r=dict(scope=__doc__,audit_passed=True,evidence=ids,verified_bindings=sum(v['bindings_verified']for v in ids.values()),
        actual_native_cases=40,all40_old_full_outcomes_except_seconds_identical=True,
        only_new_fatal_result_key='fatal_event_mailbox',actual_fatal_cases=observed,
        actual_native_packet_HLS_abort_cancel_FEC_AXI_readback_ACK=True,
        host_ACK_during_observer_stall_does_not_duplicate_or_release_native_authority=True,
        actual_SQC_RQC_native_quarantine_RQ_and_host_payload_retained=True,
        actual_native_module_counts=counts,compilation_seconds=native['compilation_seconds'],
        maximum_case_seconds=max(t['seconds']for t in native['tests'].values()),fresh_binary_sha256=native['binary_sha256'],
        source_sha256={str(q.relative_to(ROOT)):digest(q)for q in [Path(__file__).resolve(),*snapshots]},
        protected_raw_sha256=binding.PROTECTED,UNOPTFLAT_warnings=(run/'compile.log').read_text().count('%Warning-UNOPTFLAT:'),
        warnings_not_timing_or_drain_qualification=True,actual_Linux_callbacks=False,live_Linux_or_physical=False,
        standard_error_CQ_STOP_global_drain_or_unpin=False,original_timing_met=hls['original_effective_period_met'],
        full_board_timing=False,overall_goal_complete=False,hardware_or_default_actions=[],commit_or_push=False)
    with a.report.open('x')as f:f.write(json.dumps(r,indent=2)+'\n')
    print(json.dumps(dict(audit_passed=True,verified_bindings=r['verified_bindings'],actual_native_cases=40,actual_native_FEC_MMIO=True,Linux_or_physical=False)))


if __name__=='__main__':main()
