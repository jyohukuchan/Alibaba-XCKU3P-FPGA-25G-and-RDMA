#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual native42 and original40 full outcomes plus two real RQC receipts.

Full owner/nonce/fetch/queue proof and permanent quarantine are required.
No error/flush CQ, whole QP/device STOP, global drain, unpin or physical claim.
"""
import argparse
import json
from pathlib import Path
import re
import audit_segmented_receive as binding
import fatal_rq_cancel_native_fixture as fixture
import fatal_rq_cancel_native_sources as selection

ROOT=binding.ROOT;digest=binding.digest


class CaseSnapshots:
    def __init__(self,run,name):self.run=run;self.name=name
    def __truediv__(self,leaf):
        suffix={'write-fatal-selected.hex':'selected.hex','write-fatal-rq-owner.hex':'rq-owner.hex',
            'large-write-receive-host.hex':'host.hex','write-fatal-mmio.hex':'mmio.hex',
            'fatal-rqc-reply.hex':'rqc-reply.hex'}[leaf]
        return self.run/(self.name+'-'+suffix)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True)
    p.add_argument('--native-record',default='fatal-rq-cancel-native-full-001');a=p.parse_args()
    if a.report.exists():p.error('preserve all earlier evidence')
    if not re.fullmatch(r'fatal-rq-cancel-native-full-\d{3}',a.native_record):p.error('actual new full native run required')
    names=[a.native_record,'fatal-event-native-full-001','fatal-event-native-runtime-diagnostics-001',
        'fatal-rq-cancel-native-elaboration-001','fatal-rq-cancel-native-source-diagnostics-001',
        'fatal-rq-cancel-native-fixture-diagnostics-001','write-abort-event-generated-hls-002']
    records={};ids={}
    for n in names:records[n],ids[n]=binding.bindings(n)
    native,old,old_audit,elab,source,preflight,hls=[records[n]for n in names]
    if not all(r.get('pass_test',r.get('audit_passed'))for r in records.values()):raise ValueError('all actual runtime/source/fixture evidence required')
    selection.validate(selection.ELABORATION)
    if len(native['tests'])!=42 or set(native['tests'])!=set(old['tests'])|{'FATAL_RQC_ACCESS','FATAL_RQC_PARTIAL'}or \
       not all(native.get(k)for k in ['source_unchanged','actual_generated_HLS','actual_complete_native_graph',
           'both_global_drains_zero','actual_fatal_RQC_command4_receipts','actual_fatal_event_mailbox_MMIO_ACK','all40_prior_cases_retained']):
        raise ValueError('all42 real fresh native cases and full old40 required')
    if (native['FEC_features'],native['RNC_features'],native['CQC_features'],native['SQC_features'],native['RQC_features'],native['software_profile'])!=(31,131071,511,13,63,8):
        raise ValueError('explicit FEC31 with unchanged original private queue/profile identity required')
    if native['compile_exit']or native['compile_limit_seconds']!=1200 or native['compilation_seconds']>1200 or \
       native['simulation_limit_seconds']!=30 or native['bench_elaborate_seconds']>180 or \
       any(t['exit']or t['seconds']>30 for t in native['tests'].values())or \
       native['simulation_CXX_optimization']!='-O1'or native['compiler_output_split_cfuncs']!=500000 or not native['compile_owns_process_group']:
        raise ValueError('every original deadline/optimization/process-group gate required')
    if not preflight['all444_original_assertions_retained']or not preflight['all40_original_recipes_raw_bytes_and_oracles_identical']:
        raise ValueError('all original assertions, raw inputs and oracles required')
    for name,prior in old['tests'].items():
        current=native['tests'][name]
        if {k:v for k,v in current.items()if k!='seconds'}!={k:v for k,v in prior.items()if k!='seconds'}:
            raise ValueError('original40 complete outcome changed:'+name)
    for name,t in native['tests'].items():
        if t['runtime_input_sha256']!=preflight['all42_authored_runtime_inputs'][name]:raise ValueError('actual raw input differs from preflight:'+name)
    run=ROOT/native['directory'];observed={};snapshots=[]
    for name,partial in [('FATAL_RQC_ACCESS',False),('FATAL_RQC_PARTIAL',True)]:
        log=run/(name+'.log');posted=[int(l,16).to_bytes(128,'little')for l in(run/(name+'-receive-records.hex')).read_text().splitlines()]
        checked=fixture.verify_fatal_cancel(log.read_text(),posted,partial,CaseSnapshots(run,name))
        if any(native['tests'][name].get(k)!=v for k,v in checked.items()):raise ValueError('full fatal/cancellation snapshot mismatch:'+name)
        nonce=fixture.verify_nonce(log.read_text())
        expected=dict(admitted=int(partial),issued=int(partial),backend_completed=int(partial),logical_completed=int(partial),translated=0,active=0,fault=0)
        if nonce!=expected or native['tests'][name]['actual_common_nonce_backend']!=nonce:raise ValueError('actual shared nonce proof changed:'+name)
        observed[name]=checked
        snapshots.extend([log,*[run/(name+'-'+n)for n in ['selected.hex','rq-owner.hex','mmio.hex','rqc-reply.hex','host.hex','receive-records.hex','write-fatal-input.hex']]])
        if any((run/(name+'-'+n)).exists()for n in ['event.hex','error-CQ.hex','success-CQ.hex']):raise ValueError('RQ receipt must not fabricate WC/CQ')
    frozen=[ROOT/n for n in native['source_sha256']if n.endswith('/native_runner.py')]
    if len(frozen)!=1 or digest(frozen[0])!=preflight['exact_new_runner_sha256']or digest(run/'tb.v')!=preflight['exact_new_bench_sha256']:
        raise ValueError('same exact frozen extended runner/bench required')
    if native['binary_sha256']==old['binary_sha256']or native['compile_directory']==old['compile_directory']:raise ValueError('fresh actual binary and objects required')
    vvp=next(Path(n)for n in native['RAM_artifact_sha256']if Path(n).name=='tb.vvp').read_text()
    counts={n:len(re.findall(r'\.scope module, "[^\"]+" "'+re.escape(n)+r'"',vvp))for n in elab['module_counts']}
    if counts!=elab['module_counts']:raise ValueError('same sole actual HLS/MR/PTE/backend/nonce/MAC/abort/RQC graph required')
    gen=ROOT/hls['directory']/'project/solution1/syn/verilog'
    if {Path(n).name for n in native['source_sha256']if(ROOT/n).parent==gen}!=set(hls['generated_sha256'])or len(hls['generated_sha256'])!=207:
        raise ValueError('whole exact qualified207 HLS required')
    if (float(hls['target_clock_period']),float(hls['clock_uncertainty']))!=(4,1.08)or \
       hls['original_effective_period_met']!=(float(hls['estimated_clock_period'])<=2.92):raise ValueError('original timing verdict must remain factual')
    for n,h in binding.PROTECTED.items():
        if digest(ROOT/n)!=h:raise ValueError('protected original source changed:'+n)
    r=dict(scope=__doc__,audit_passed=True,evidence=ids,verified_bindings=sum(v['bindings_verified']for v in ids.values()),
        actual_native_cases=42,all40_old_full_outcomes_except_seconds_identical=True,actual_fatal_RQC_cases=observed,
        actual_native_packet_HLS_abort_FEC_AXI_and_RQC_command4=True,full19_word_owner_nonce_flags63_consumer_receipts=True,
        old_retained_RQ_snapshots_are_precancel_not_final_state=True,permanent_SQC_ingress_quarantine_remains=True,
        actual_native_module_counts=counts,compilation_seconds=native['compilation_seconds'],
        maximum_case_seconds=max(t['seconds']for t in native['tests'].values()),fresh_binary_sha256=native['binary_sha256'],
        source_sha256={str(q.relative_to(ROOT)):digest(q)for q in [Path(__file__).resolve(),*snapshots]},
        protected_raw_sha256=binding.PROTECTED,UNOPTFLAT_warnings=(run/'compile.log').read_text().count('%Warning-UNOPTFLAT:'),
        warnings_not_timing_or_drain_qualification=True,actual_Linux_callbacks=False,live_Linux_or_physical=False,
        standard_error_CQ_STOP_global_drain_or_unpin=False,original_timing_met=hls['original_effective_period_met'],
        full_board_timing=False,overall_goal_complete=False,hardware_or_default_actions=[],commit_or_push=False)
    with a.report.open('x')as f:f.write(json.dumps(r,indent=2)+'\n')
    print(json.dumps(dict(audit_passed=True,verified_bindings=r['verified_bindings'],actual_native_cases=42,actual_RQC_receipts=True,Linux_or_physical=False)))


if __name__=='__main__':main()
