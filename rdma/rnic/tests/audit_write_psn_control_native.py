#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual native hierarchy and certified frontend/controller, NOT native runtime."""
import argparse
import json
from pathlib import Path
import re
import audit_segmented_receive as binding
import write_psn_control_native_sources as selection
import probe_write_psn_frontend as front

ROOT=binding.ROOT;digest=binding.digest
PREIMAGES={
    'write-psn-native-source-startup-001':{'rdma/rnic/fpga/derive_write_psn_control_native.py':
        'rdma/rnic/build/write-psn-native-source-startup-001-preimages-e6kft8t5'},
    'write-psn-front-001':{'rdma/rnic/tests/probe_write_psn_frontend.py':
        'rdma/rnic/build/write-psn-front-001-preimages-KxtWIMsM'},
}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve previous evidence')
    names=['write-psn-control-native-elaboration-001','write-psn-control-001','write-psn-front-002',
        'segmented-write-rx-front-005','receive-control-ack-diagnostics-001','control-response-generated-diagnostics-001',*PREIMAGES]
    records={};ids={}
    for n in names:records[n],ids[n]=binding.bindings(n,PREIMAGES.get(n))
    elab,ctrl,rx,old,ack,hls=[records[n]for n in names[:6]]
    if not all(r.get('pass_test',r.get('audit_passed'))for r in [elab,ctrl,rx,old,ack,hls]):
        raise ValueError('actual hierarchy/controller/frontend/shared ACK/actual HLS evidence required')
    src,data,hashes=selection.sources(selection.ELABORATION,None)
    if len(src)!=449 or len(data)!=8 or len(ctrl['tests'])!=46 or len(rx['tests'])!=47:
        raise ValueError('exact complete449 RTL/8 data/helper46/frontend47 required')
    if (ctrl['clock_ns'],ctrl['runtime_limit_seconds'],ctrl['compile_limit_seconds'],ctrl['cycle_limit'])!=(4,10,10,100000)or \
       any(t['exit']or t['seconds']>10 for t in [*ctrl['tests'].values(),*ctrl['compilations'].values()]):
        raise ValueError('original actual controller gates required')
    if (rx['clock_ns'],rx['case_limit_seconds'],rx['compile_limit_seconds'],rx['cycle_limit'])!=(4,10,10,100000):
        raise ValueError('original actual frontend gates required')
    olddir=ROOT/old['directory'];newdir=ROOT/rx['directory']
    for n,t in old['tests'].items():
        actual=rx['tests'][n]
        if actual['exit']or actual['seconds']>10 or any(actual[k]!=t[k]for k in ['protection','replay']):
            raise ValueError('old47 independent protection/replay outcome changed:'+n)
        if digest(olddir/(n+'-input.hex'))!=digest(newdir/(n+'-input.hex')):
            raise ValueError('old raw input changed:'+n)
        if bool(actual['certification']['cycles'])!=(n=='17'):raise ValueError('only actual native-frontier PSN18 may certify')
    fatals=lambda t:set(re.findall(r'\$fatal\(1,"([^"\n]+)"',t))
    if not fatals((olddir/'tb.v').read_text())<=fatals((newdir/'tb.v').read_text()):
        raise ValueError('an original actual frontend assertion was removed/relaxed')
    frontsrc=newdir/'rocev2_segmented_write_native_frontend.v'
    if frontsrc.read_text()!=front.candidate.frontend()or (ROOT/elab['directory']/frontsrc.name).read_text()!=frontsrc.read_text():
        raise ValueError('actual tested frontend must be the same native selected definition')
    for n in PREIMAGES:
        if records[n]['pass_test']:raise ValueError('previous failure must remain failed:'+n)
    failed=records['write-psn-front-001'];last=failed['tests']['22']
    if last['exit']or 'certification'in last or last['protection']!=old['tests']['22']['protection']:
        raise ValueError('original missing-type fixture failure must retain real old22 outcome')
    failedtb=(ROOT/failed['directory']/'tb.v').read_text()
    if 'trusted_expected_psn=cur_psn;'not in failedtb or 'mode==22 ? 0:24\'hffffff'not in failedtb or \
       'reject_packet(mode==26 ? 36:16,1);'not in failedtb:
        raise ValueError('old22 independently supplies matching native PSN0 and message-position error16')
    for n,h in binding.PROTECTED.items():
        if digest(ROOT/n)!=h:raise ValueError('protected raw source changed:'+n)
    result=dict(scope=__doc__,audit_passed=True,evidence=ids,verified_bindings=sum(v['bindings_verified']for v in ids.values()),
        exact_selected_RTL=449,exact_selected_HLS_data=8,complete_actual_new197_HLS_cohort=True,
        frontend47_all_old_raw_inputs_and_protection_replay_outcomes_identical=True,
        actual_frontend_certificate_only_for_checked_native_frontier_PSN18=True,
        original_frontend_fatal_messages_retained=len(fatals((olddir/'tb.v').read_text())),
        helper46_passed=True,helper_future_duplicate_suppression_epoch_cookie_QPN_serial_wrap_checks=True,
        sole_native_MR_PTE_backend_nonce_ACK_HLS_MSN_state_domains=True,both_global_HLS_drains_zero=True,
        source_sha256={str(n.relative_to(ROOT)):digest(n)for n in [Path(__file__).resolve(),Path(selection.__file__).resolve()]},
        selected_completed_elaboration_input_sha256=hashes,protected_raw_sha256=binding.PROTECTED,
        native_control_packet_runtime=False,fatal_QP_recovery_qualified=False,live_Linux_or_physical=False,
        original_timing_met=False,full_board_timing=False,overall_goal_complete=False,
        remaining=['Fresh actual native38: all37 previous cases plus future-PSN NAK, repeat suppression, proper same-PSN retry and duplicate no-second-DMA/RQ/CQ, with full wire/host/CQ oracles.',
            'All11/full1MiB native/multiSGE/proper fatal-QP safe cleanup/live registered refs/real-peer recovery/congestion/original board timing/physical remain.'],
        hardware_or_default_actions=[],commit_or_push=False)
    with a.report.open('x')as f:f.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(audit_passed=True,verified_bindings=result['verified_bindings'],frontend47=True,helper46=True,native_runtime=False)))


if __name__=='__main__':main()
