#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Matched profile8 native/kernel/provider/C callback source coupling audit.

Actual RTL produces the untouched snapshots; actual C posts/compares/retires
owners with explicit Linux/MMIO/pin/coherent-DMA primitive models. Provider
uses actual libibverbs with modeled syscalls/WC replies. These are NOT live
Linux/FPGA/provider/physical page/ref/order/timing qualification.
"""
import argparse
import json
from pathlib import Path
import subprocess
import audit_segmented_receive as binding

ROOT=binding.ROOT;digest=binding.digest


def kernel_build_bindings(name):
    # This producer's frozen_input_sha256 names are relative to the ACTUAL
    # frozen build directory, unlike authored/artifact paths relative to ROOT.
    # Read the untouched raw report and verify every entry at its declared base.
    path=binding.record(name);r=json.loads(path.read_text());count=0
    for field,base in [('source_sha256',ROOT),('frozen_input_sha256',ROOT/r['directory']),('artifact_sha256',ROOT)]:
        for name,h in r[field].items():
            if digest(base/name)!=h:raise ValueError('actual kernel binding changed:'+str(base/name))
            count+=1
    return r,dict(bindings_verified=count,report_sha256=digest(path),exact_preimage_resolutions=[])


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve every previous report')
    names=['segmented-write-profile-native-full-001','segmented-write-profile-native-diagnostics-001','segmented-write-kernel-build-001',
        'segmented-write-kernel-post-001','segmented-write-kernel-native-cq-001','provider-segmented-write-001',
        'segmented-write-cq-semantics-001','segmented-write-software-source-diagnostics-001','segmented-receive-kernel-post-002']
    records={};ids={}
    for name in names:
        records[name],ids[name]=kernel_build_bindings(name)if name=='segmented-write-kernel-build-001'else binding.bindings(name)
    native,diag,kernel,post,cq,provider,semantic,source,old=[records[n]for n in names]
    failed_old,ids['segmented-receive-kernel-post-001']=binding.bindings('segmented-receive-kernel-post-001',
        {'rdma/rnic/tests/kernel_segmented_receive_post.c':'rdma/rnic/build/receive-kernel-post-001-preimages-8oxDUI04'})
    if failed_old['pass_test']or len(failed_old['tests'])!=27 or failed_old['tests']['RECV26']['exit']!=-6:
        raise ValueError('original failed old callback fixture must remain a failure, not the successful002 baseline')
    if not all(r.get('pass_test')for r in [native,kernel,post,cq,provider,semantic])or not diag['audit_passed']or not source['audit_passed']:
        raise ValueError('every independently scoped matching proof required')
    if (native['RNC_features'],native['CQC_features'],native['SQC_features'],native['RQC_features'],native['software_profile'])!=(131071,511,13,63,8)or \
       (kernel['matched_RNC_features'],kernel['matched_CQC_features'],kernel['matched_SQC_features'],kernel['matched_RQC_features'],kernel['private_segmented_profile'])!=(131071,511,13,63,8)or \
       (cq['RNC_features'],cq['CQC_features'],cq['software_profile'])!=(131071,511,8):raise ValueError('exact same native/kernel/CQ identity required')
    if len(native['tests'])!=36 or len(post['tests'])!=202 or len(cq['tests'])!=95 or len(provider['tests'])!=9:
        raise ValueError('all36 native/202 callbacks/95 native-CQ/9 provider cases required')
    if not post['all170_prior_cases_retained']or not post['source_unchanged']or not cq['source_unchanged']or \
       not kernel['source_and_frozen_inputs_unchanged']or not cq['native_RTL_snapshots_consumed']:
        raise ValueError('exact old callbacks and actual untouched native producer required')
    if len(old['tests'])!=170 or not old['pass_test']or not set(old['tests']).issubset(post['tests']):
        raise ValueError('every exact old callback case name required')
    for name,r in old['tests'].items():
        if post['tests'][name]['summary']!=r['summary']:raise ValueError('old callback summary/oracle changed:'+name)
    for group in [post,cq]:
        if group['simulation_limit_seconds']!=10 or group['compile_seconds']>30 or any(r['exit']or r['seconds']>10 for r in group['tests'].values()):
            raise ValueError('original compile30s/runtime10s guards required')
    if kernel['compile_exit']or kernel['compile_seconds']>180 or any(kernel[k]for k in ['installed','module_load_performed','default_sources_changed','atomic_cap_advertised']):
        raise ValueError('real-header compile180s only, old default/Atomic_NONE required')
    if semantic['old_and_unknown_rows_identical']!=128000 or semantic['matrix_cases']!=140800 or not source['old_successful_native_tuple_build_rejected']:
        raise ValueError('old behavior and strict non-borrowed native identity gate required')
    run=ROOT/native['directory'];sw=ROOT/cq['directory']
    snapshot=run/'LARGE_RX_WRITE_IMM-event.hex';record=run/'LARGE_RX_WRITE_IMM-receive-records.hex'
    for q in [snapshot,record]:
        key=str(q.relative_to(ROOT))
        if cq['source_sha256'].get(key)!=digest(q):raise ValueError('actual original snapshot not directly bound')
    words=[int(s,16)for s in snapshot.read_text().splitlines()]
    if len(words)!=33 or words[25:29]!=[8193,3,0x89abcdef,511]:raise ValueError('true whole8193 flags3 native33-word event required')
    positive=cq['tests']['LARGE_RX_WRITE_IMM-0']['summary']
    if not all(positive.get(k)for k in ['pass_test','native_RTL_CQ_unedited','full128_kernel_native_record_identical','actual_standard_WRITE_notification_CQ_MR_lifetime','profile8_CQC511'])or \
       positive['capacity']or positive['bytes']!=8193:raise ValueError('actual standard C callback/zero-RQ/whole-WRITE retirement required')
    for mutation in range(1,5):
        r=cq['tests']['LARGE_RX_WRITE_IMM-'+str(mutation)]['summary']
        if not r['owners_intentionally_retained']or r['mutation']!=mutation:raise ValueError('wrong full-owner/CQ must retain lifetime')
    semantic_header=ROOT/semantic['directory']/'kernel/cq_io.h';module_header=ROOT/kernel['directory']/'cq_io.h'
    if semantic_header.read_bytes()!=module_header.read_bytes():raise ValueError('actual module/header policy must match tested semantics')
    for n,h in binding.PROTECTED.items():
        if digest(ROOT/n)!=h:raise ValueError('protected original raw source changed')
    check=subprocess.run(['bash','scripts/check.sh'],cwd=ROOT,capture_output=True,text=True,timeout=30)
    result=dict(scope=__doc__,audit_passed=True,evidence=ids,verified_bindings=sum(v['bindings_verified']for v in ids.values()),
        private_identity=[131071,511,13,63,8],actual_native_cases=36,actual_C_callback_cases=202,all170_prior_callback_summaries_identical=True,
        actual_unedited_native_CQ_cases=95,actual_provider_identities=9,actual_CQ_policy_cases=140800,
        kernel_real_header_build_seconds=kernel['compile_seconds'],callback_compile_seconds=post['compile_seconds'],native_CQ_compile_seconds=cq['compile_seconds'],
        callback_max_seconds=max(v['seconds']for v in post['tests'].values()),native_CQ_max_seconds=max(v['seconds']for v in cq['tests'].values()),
        actual_native_WRITE_snapshot=dict(path=str(snapshot.relative_to(ROOT)),sha256=digest(snapshot),words=33,whole_bytes=8193,flags=3,Immediate=0x89abcdef,
            original_RQ_record_path=str(record.relative_to(ROOT)),original_RQ_record_sha256=digest(record),capacity=0,exact_C128_match=True),
        malformed_native_CQ_mutations_retain_owner=True,semantic_header_matches_real_module=True,old_profile7_WRITE_max_bytes=4096,
        source_sha256={str(Path(__file__).relative_to(ROOT)):digest(__file__)},protected_raw_sha256=binding.PROTECTED,
        inherited_source_check=dict(exit=check.returncode,stdout=check.stdout,stderr=check.stderr,overall_suite_passed=check.returncode==0,original_gate_unchanged=True),
        callback_Linux_MMIO_pins_DMA_models=True,provider_syscall_WC_reply_models=True,live_kernel_RTL_provider_coupling=False,
        standard_installed_API_runtime=False,hardware_verified=False,full_board_timing=False,overall_goal_complete=False,
        remaining=['All11 remain; this matched source/actual-native-snapshot milestone is NOT live installed Linux/native refs or physical PCIe/CPU visibility.',
            'Full1MiB actual native and multiSGE remain.1MiB C policy/CPP or modeled WC is not native payload proof.',
            'Incoming segmented WRITE real wire RNR/NAK/retry, real-peer recovery/MSN/congestion and privileged partial-HLS-message cleanup remain.',
            'Original4ns/default1.08ns/full-board fit/setup/hold/CDC/DRC/routing and short supervised physical work remain; HLS15.571ns FAIL and13 UNOPTFLAT unwaived.',
            'No reboot needed; restore ALL archived RAM caches and prove authenticated exact-thread/goal revival before any necessary reboot.'],
        install_load_program_reboot_fan_BIOS_network_Git_actions=[])
    with a.report.open('x')as f:f.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(audit_passed=True,verified_bindings=result['verified_bindings'],native36=True,callbacks202=True,unedited_native_CQ95=True,live_hardware=False)),flush=True)


if __name__=='__main__':main()
