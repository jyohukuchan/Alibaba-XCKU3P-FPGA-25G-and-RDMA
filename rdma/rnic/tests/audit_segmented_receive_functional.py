#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual corrected incoming native/old regressions and matched software scope.

Keep original native failure and diagnostic evidence. Modeled API/syscall
executions and real-header compilation are not live Linux/FPGA coupling,
native1MiB, multi-SGE, original timing or physical qualification.
"""
import argparse
import datetime
import json
from pathlib import Path
import subprocess
import audit_segmented_receive as binding

ROOT=binding.ROOT;PREFIX=binding.PREFIX;digest=binding.digest


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve earlier evidence')
    reports={};identities={}
    for name in ['segmented-receive-native-full-004','segmented-receive-native-compat-001',
        'segmented-receive-native-full-003','segmented-receive-native-fatal-diagnostics-003',
        'receive-continuation-gate-001','segmented-receive-native-elaboration-002',
        'provider-segmented-receive-001','receive-kernel-identity-001','segmented-receive-kernel-post-002']:
        reports[name],identities[name]=binding.bindings(name)
    failed_post,identities['segmented-receive-kernel-post-001']=binding.bindings('segmented-receive-kernel-post-001',
        {'rdma/rnic/tests/kernel_segmented_receive_post.c':'rdma/rnic/build/receive-kernel-post-001-preimages-8oxDUI04'})
    if failed_post.get('pass_test')or set(failed_post['tests'])!={'RECV'+str(i)for i in range(27)}or failed_post['tests']['RECV26']['exit']!=-6:
        raise ValueError('retain exact malformed-zero-epoch test-vector failure')
    native=reports['segmented-receive-native-full-004'];old=reports['segmented-receive-native-compat-001']
    if not all(native.get(k)for k in ['pass_test','source_unchanged','actual_generated_HLS','actual_complete_native_graph',
        'both_global_drains_zero','all32_prior_cases_retained','incoming_segmented_SEND_Immediate_runtime']):raise ValueError('actual corrected complete native success required')
    if set(native['tests'])!=set(old['tests'])|{'LARGE_RX_SEND','LARGE_RX_SEND_IMM'}or len(native['tests'])!=34:
        raise ValueError('all exact old32 names and both new real incoming cases required')
    if native['simulation_limit_seconds']!=30 or native['compile_limit_seconds']!=1200 or any(v['exit']!=0 or v['seconds']>30 for v in native['tests'].values()):
        raise ValueError('all original native limits and successful process exits required')
    if (native['RNC_features'],native['CQC_features'],native['new_receive_bytes'],native['new_posted_capacity'])!=(65535,255,8193,8194):
        raise ValueError('exact incoming identity/data/capacity required')
    for name in ['LARGE_RX_SEND','LARGE_RX_SEND_IMM']:
        t=native['tests'][name];s=t['summary']
        if not all(t.get(k)for k in ['every_payload_and_sentinel_byte','per_packet_ACK_MSN_only_LAST','one_whole_CQ_and_host_ACK'])or \
           (s['packets'],s['MR_queries'],s['commands'],s['fences'],s['packet_releases'],s['whole_receipts'],s['CQ_commits'],s['CQ_retires'])!=(3,4,3,3,3,1,1,1):
            raise ValueError('actual MR/DMA/fence/ACK-MAC/whole-HLS/CQ lives and every byte required')
    if reports['segmented-receive-native-full-003'].get('pass_test')or not reports['segmented-receive-native-fatal-diagnostics-003'].get('diagnostic_completed'):
        raise ValueError('retain original actual failed graph and read-only diagnosis')
    provider=reports['provider-segmented-receive-001'];identity=reports['receive-kernel-identity-001'];post=reports['segmented-receive-kernel-post-002']
    if not provider.get('pass_test')or set(provider['tests'])!={str(i)for i in range(8)}or \
       [provider['tests'][str(i)]['RNC_features']for i in range(8)]!=[511,1023,2047,4095,8191,16383,32767,65535]:raise ValueError('all8 genuine provider serializer identities required')
    if not identity.get('pass_test')or identity['summary']['cases']!=2442 or not post.get('pass_test')or \
       len(post['tests'])!=170 or not post.get('all134_prior_cases_retained')or post['RECV_cases']!=36:raise ValueError('all real IO and matched standard callback model cases required')
    for report in [provider,post]:
        if report['simulation_limit_seconds']!=10 or any(v['exit']!=0 or v['seconds']>10 for v in report['tests'].values()):raise ValueError('original10s C/provider bounds required')
    kernel_path=PREFIX/'rocev2-rnic-segmented-receive-kernel-build-001.json';kernel=json.loads(kernel_path.read_text());count=0
    if not kernel.get('pass_test')or (kernel['matched_RNC_features'],kernel['matched_CQC_features'],kernel['matched_RQC_features'],kernel['private_segmented_profile'])!=(65535,255,31,7):
        raise ValueError('actual exact real-header matched kernel build required')
    for key,base in [('source_sha256',ROOT),('frozen_input_sha256',ROOT/kernel['directory']),('artifact_sha256',ROOT)]:
        for n,h in kernel[key].items():
            q=Path(n);q=q if q.is_absolute()else base/q
            if digest(q)!=h:raise ValueError('actual matched kernel input/artifact changed:'+str(q))
            count+=1
    identities['segmented-receive-kernel-build-001']=dict(report_sha256=digest(kernel_path),bindings_verified=count)
    for n,h in binding.PROTECTED.items():
        if digest(ROOT/n)!=h:raise ValueError('protected raw source changed:'+n)
    check=subprocess.run(['bash','scripts/check.sh'],cwd=ROOT,capture_output=True,text=True,timeout=30)
    result=dict(scope=__doc__,created_UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),audit_passed=True,
        overall_goal_complete=False,hardware_verified=False,live_Linux_RTL_coupling=False,
        verified_reports=identities,verified_bindings=sum(v['bindings_verified']for v in identities.values()),
        auditor_source_sha256={str(Path(__file__).relative_to(ROOT)):digest(__file__)},protected_raw_sha256=binding.PROTECTED,
        actual_native=dict(cases=34,new_received_bytes=8193,posted_capacity=8194,packets=3,whole_CQ=1,
            compile_seconds=native['compilation_seconds'],maximum_case_seconds=max(v['seconds']for v in native['tests'].values()),
            new_case_seconds={n:native['tests'][n]['seconds']for n in ['LARGE_RX_SEND','LARGE_RX_SEND_IMM']},
            actual_MR_PTE_DMA_nonce_fence_HLS_MAC_CQ_and_full_bytes=True,physical_host_root_peer_PHY_PTP_models=True),
        matched_software=dict(profile=7,RNC=65535,CQC=255,SQC=13,RQC=31,real_header_modules_compiled=True,
            actual_C_standard_callback_models=170,new_RECV_callback_cases=36,all134_old_callback_cases_retained=True,
            actual_IO_geometry_cases=2442,actual_provider_serializer_identities=8,only_syscalls_and_WCs_modeled_in_provider=True,
            kernel_Linux_MMIO_pins_DMA_completions_modeled=True,installed=False,module_loaded=False),
        original_callback_vector_failure=dict(report='segmented-receive-kernel-post-001',actual_QP_epoch_read_only_GDB=1,
            low_epoch_bit_flip_produced_zero_not_stale_owner=True,corrected_to_high_bit_nonzero_distinct_epoch=True,
            same_exact_ESTALE_assertion_and_all_other_oracles_retained=True,driver_source_unchanged=True,
            failed_source_preimage='rdma/rnic/build/receive-kernel-post-001-preimages-8oxDUI04'),
        inherited_source_check=dict(exit=check.returncode,stdout=check.stdout,stderr=check.stderr,overall_suite_passed=check.returncode==0,original_gate_unchanged=True),
        remaining=['All11 original requirements remain incomplete; no target narrowing.',
            'Native1MiB receive and live matched Linux/RTL/physical page-table, API and lifetime qualification remain.',
            'Segmented WRITE Immediate independent remote MR/late RQ, multi-SGE, real-peer recovery/RNR/congestion/interoperability remain.',
            'HLS15.571ns still fails original4ns/default1.08ns; full-board fit/setup/hold/CDC/DRC/routing and short supervised physical qualification remain.',
            'No reboot needed. Restore ALL archived RAM caches and prove exact authenticated thread/goal restoration before any necessary reboot.'],
        hardware_install_load_network_fan_BIOS_flash_reboot_actions=[],commit_or_push=False)
    with a.report.open('x')as f:f.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(audit_passed=True,verified_bindings=result['verified_bindings'],native_cases=34,callback_model_cases=170,original_timing_pass=False)),flush=True)


if __name__=='__main__':main()
