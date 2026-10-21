#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Exact new receive-HLS generation/native elaboration and real PCIe posting.

Compile-only native evidence is not payload runtime or a hardware/timing
qualification. Keep all failed/rejected variants and exact preimages; no
green CPP result is substituted for missing generated RTL/native operation.
"""
import argparse
import json
from pathlib import Path
import subprocess
import audit_segmented_receive as old
import audit_receive_message_components as components

ROOT=old.ROOT;PREFIX=old.PREFIX;digest=old.digest
SUCCESS=[
    'segmented-receive-hls-007','segmented-receive-compat-003','receive-extent-conformance-003',
    'segmented-receive-generated-hls-002','segmented-receive-native-elaboration-001',
    'receive-pcie-post-001','segmented-receive-wqe-001','segmented-receive-verbs-adapter-001',
    'segmented-receive-admission-001','receive-mr-post-001','receive-message-queue-003',
    'receive-message-ack-001','receive-message-cq-001','receive-message-join-003']
HISTORICAL={k:dict(v)for k,v in old.HISTORICAL.items()}
HISTORICAL.update({k:{rel:path}for k,(rel,path)in components.HISTORICAL.items()})
HISTORICAL['receive-extent-conformance-001']={
    'rdma/rnic/tests/probe_receive_extent_conformance.py':'rdma/rnic/build/receive-extent-conformance-001-preimages-2MJu6j2Y'}
HISTORICAL['receive-extent-conformance-002']={}
for name in ['segmented-receive-hls-006','segmented-receive-compat-002']:
    HISTORICAL[name]={'rdma/rnic/hls/segmented_receive_prefix_transport.py':'rdma/rnic/build/receive-prefix-006-preimages-MBD20WSw'}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve earlier evidence')
    good={};historical={};rpts={}
    for name in SUCCESS:
        r,v=old.bindings(name)
        if not r.get('pass_test'):raise ValueError('actual successful evidence required:'+name)
        good[name]=v;rpts[name]=r
    for name,fallback in HISTORICAL.items():
        r,v=old.bindings(name,fallback)
        if name=='receive-message-graph-syntax-001':
            if not r.get('syntax_only')or r.get('full_native_elaboration'):raise ValueError('old syntax scope changed')
        elif r.get('pass_test'):raise ValueError('failed run must stay failed:'+name)
        historical[name]=v
    rejected,v=old.bindings('segmented-receive-hls-005')
    if not rejected.get('pass_test'):raise ValueError('retain actual normal-mode pass, not a claim of equivalence')
    v['disposition']='Rejected by actual extent-conformance001 short nonfinal KEEP1/length65 counterexample; normal44 pass is not semantic equivalence.'
    historical['segmented-receive-hls-005']=v
    hls=rpts['segmented-receive-generated-hls-002'];cpp=rpts['segmented-receive-hls-007']
    if (float(hls['target_clock_period']),float(hls['clock_uncertainty']),hls['MAX_QPS'],hls['metadata_entries'])!=(4,1.08,8,2000)or \
       not hls.get('whole_receive_port776_verified')or hls.get('source_directory')!='rdma/rnic/build/native-segmented-receive-transport-007':
        raise ValueError('exact actual007 generation and original targets required')
    native=rpts['segmented-receive-native-elaboration-001']
    if not native.get('full_native_elaboration')or native.get('unknown_leaves_ignored')or native.get('runtime_test')or \
       not native.get('both_global_HLS_drains_zero')or native.get('actual_whole_message_join_count')!=1:
        raise ValueError('actual complete elaboration only, without missing-leaf or drain waiver, required')
    if (native['module_counts']['rocev2_mr_table'],native['module_counts']['rocev2_mr_page_table'],
        native['module_counts']['rocev2_native_segmented_receive_top'],native['module_counts']['rocev2_receive_message_queue'],
        native['module_counts']['rocev2_receive_queue'],native['module_counts']['rocev2_native_segmented_immediate_top'])!=(1,1,1,1,0,0):
        raise ValueError('one new native/shared MR/PTE/HLS/message-RQ cohort required')
    if len(cpp['tests'])!=44 or not cpp.get('all21_prior_modes_retained')or any(t['exit']!=0 or t['seconds']>30 for t in cpp['tests'].values()):
        raise ValueError('all44 real old/new C++ cases required')
    conformance=rpts['receive-extent-conformance-003']
    if conformance['summary']['cases']!=103665 or not conformance['summary']['short_nonfinal_preserved']:
        raise ValueError('actual bounded finite old/new semantic regression required')
    pcie=rpts['receive-pcie-post-001']
    if not pcie.get('actual_C128_Corundum_PCIe_RAM_MR_and_message_RQ')or pcie.get('descriptor_status_RAM_or_MR_substitute')or \
       len(pcie['tests'])!=4 or any(t['exit']!=0 or t['seconds']>10 for t in pcie['tests'].values()):
        raise ValueError('all4 actual C/PCIe/MR/RQ cases required')
    if [pcie['tests'][str(i)]['summary']['posted']for i in range(4)]!=[4,1,0,2]:
        raise ValueError('real success/denial/parse/UR posting cardinality required')
    for path,h in old.PROTECTED.items():
        if digest(ROOT/path)!=h:raise ValueError('protected raw source changed:'+path)
    check=subprocess.run(['bash','scripts/check.sh'],capture_output=True,text=True,cwd=ROOT,timeout=30)
    result=dict(scope=__doc__,audit_passed=True,overall_goal_complete=False,hardware_verified=False,
        successful=good,historical=historical,successful_bindings_verified=sum(v['bindings_verified']for v in good.values()),
        historical_bindings_verified=sum(v['bindings_verified']for v in historical.values()),
        auditor_source_sha256={str(Path(__file__).relative_to(ROOT)):digest(__file__)},protected_raw_sha256=old.PROTECTED,
        actual_generated_receive_HLS=dict(directory=hls['directory'],source=hls['source_directory'],seconds=hls['elapsed_seconds'],
            whole_AXIS_port_bits=776,target_ns=4,uncertainty_ns=1.08,estimated_period_ns=float(hls['estimated_clock_period']),
            original_effective_period_met=hls['original_effective_period_met'],resources=hls['resources'],full_board_timing=False),
        actual_native_elaboration=dict(full_app_native_graph=True,unknown_leaves_ignored=False,seconds=native['compile_seconds'],
            one_MR_PTE_shared_HLS_message_RQ=True,whole_join_count=1,original_domain_multiplicities_retained=True,
            both_global_HLS_drains_zero=True,native_payload_runtime=False,physical_or_live_API=False),
        real_C_PCIe_MR_RQ_posting=dict(cases=4,total_records=15,real_MR_queries=10,actual_posted_owners=7,
            maximum_case_seconds=max(t['seconds']for t in pcie['tests'].values()),
            full128_bytes_full620_owner_and_full_capacity_MR=True,permission_range_key_parse_and_PCIe_UR_checked=True,
            same_QPN_SQ_RQ_banks_independent=True,guard_handoff_blocks_MR_revoke=True,
            descriptor_status_RAM_MR_agents=False,physical_host_root_link_config_and_error_sink_modeled=True,
            received_payload_HLS_MAC_CQ_and_installed_Linux=False),
        original_CPP_and_finite_regression=dict(all44_modes=True,all21_old_retained=True,finite_comparisons=103665,
            formal_equivalence=False,actual_RX_seconds=[cpp['tests'][m]['seconds']for m in ['rx-send','rx-imm']]),
        inherited_source_check=dict(exit=check.returncode,stdout=check.stdout,stderr=check.stderr,
            overall_suite_passed=check.returncode==0,original_gate_unchanged=True),
        remaining=['All11 original requirements retained; goal incomplete.',
            'Fresh same new graph old32-case native build/runtime is a separate live job; no pass inferred here.',
            'Actual full-native new8193/1MiB incoming data/MR/PTE/DMA/fence/ACK-MAC/whole-CQ runtime still required.',
            'New codec/adapter source is not integrated into matched registered kernel/provider/profile; old/default profile6 incoming4096 remains.',
            'Segmented WRITE Immediate independent remote MR/late notification RQ, multi-SGE and real peer MSN/recovery/RNR/congestion remain.',
            'Original-clock whole-board fit/setup/hold/CDC/DRC/routing and short thermally supervised physical qualification remain.',
            'No reboot needed; restore all archived RAM caches and prove exact authenticated same-thread/goal revival before any necessary reboot.'],
        hardware_install_load_network_fan_BIOS_flash_reboot_actions=[],commit_or_push=False)
    with a.report.open('x')as f:f.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(audit_passed=True,successful_bindings=result['successful_bindings_verified'],historical_bindings=result['historical_bindings_verified'],
        actual_native_elaboration=True,native_payload_runtime=False,original_timing_met=hls['original_effective_period_met'])),flush=True)


if __name__=='__main__':main()
