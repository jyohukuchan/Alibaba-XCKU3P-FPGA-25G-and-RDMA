#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual complete native WRITE/Immediate36 executions, not a physical release.

All34 old raw input hashes/summary oracles stay exact. New8193-byte WRITE
uses actual generated HLS/native PSN/shared MR/PTE/PCIe/global nonce/fence/
sole ACK/real MAC/CQ. Host/root/peer/PHY/PTP remain models. Original timing,
full1MiB/multiSGE, matched software and real-peer recovery remain open.
"""
import argparse
import datetime
import json
from pathlib import Path
import re
import subprocess
import audit_segmented_receive as binding

ROOT=binding.ROOT;digest=binding.digest


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve every earlier report')
    names=['segmented-write-native-full-002','segmented-receive-native-full-004',
        'segmented-write-native-elaboration-001','native-write-header-gate-001',
        'segmented-write-native-fixture-diagnostics-001','segmented-write-owned-generated-hls-001',
        'segmented-write-controller-diagnostics-001','segmented-write-native-full-001']
    records={};identities={}
    for name in names:records[name],identities[name]=binding.bindings(name)
    native=records[names[0]];old=records[names[1]];elaboration=records[names[2]];generated=records[names[5]]
    if not all(native.get(k)for k in ['pass_test','source_unchanged','actual_generated_HLS','actual_complete_native_graph',
        'both_global_drains_zero','native_controller_inserted','incoming_segmented_WRITE_runtime','all34_prior_cases_retained',
        'incoming_segmented_SEND_Immediate_runtime','large_READ_native_runtime','large_Immediate_native_runtime']):
        raise ValueError('actual fresh complete native WRITE and retained functions required')
    if len(native['tests'])!=36 or set(native['tests'])!=set(old['tests'])|{'LARGE_RX_WRITE','LARGE_RX_WRITE_IMM'}or len(old['tests'])!=34:
        raise ValueError('every exact original34 case plus both real WRITE cases required')
    if native['compile_limit_seconds']!=1200 or native['simulation_limit_seconds']!=30 or native['compile_exit']or native['compilation_seconds']>1200 or \
       any(v['exit']or v['seconds']>30 for v in native['tests'].values()):
        raise ValueError('unchanged actual compile/runtime deadlines required')
    for name,result in old['tests'].items():
        current=native['tests'][name]
        if current['runtime_input_sha256']!=result['runtime_input_sha256']or \
           ('summary'in result and current.get('summary')!=result['summary']):
            raise ValueError('original input bytes or summary oracle changed:'+name)
    if (native['RNC_features'],native['CQC_features'])!=(65535,255)or native['default_hardware_changed']or \
       native['kernel_profile_matched']or native['new_software_capability_advertised']or native['hardware_verified']:
        raise ValueError('private current tuple only, no installed capability/physical claim')
    if native['native_1MiB_WRITE_runtime']or native['native_1MiB_receive_runtime']or generated['original_effective_period_met']:
        raise ValueError('8193 runtime cannot qualify1MiB or failed original timing')
    for name,immediate in [('LARGE_RX_WRITE',False),('LARGE_RX_WRITE_IMM',True)]:
        r=native['tests'][name]
        expected=dict(pass_test=True,bytes=8193,packets=3,MR_queries=4,commands=3,fences=3,native_PSN_commits=3,
            WRITE_Immediate=int(immediate),notification_capacity=0)
        if r['summary']!=expected or not r['every_payload_and_sentinel_byte']or len(r['actual_XGMII_frames'])!=3 or \
           (immediate and (not r['zero_capacity_genuine_RQ']or r['whole_received_bytes']!=8193)):
            raise ValueError('actual full WRITE memory/PSN/wholeCQ scope missing')
    vvp=next(Path(q)for q in native['RAM_artifact_sha256']if Path(q).name=='tb.vvp').read_text()
    counts={name:len(re.findall(r'\.scope module, "[^"]+" "'+name+r'"',vvp))for name in elaboration['module_counts']}
    if counts!=elaboration['module_counts']:raise ValueError('actual executable bench hierarchy differs from native elaboration')
    genroot=ROOT/generated['directory']/'project/solution1/syn/verilog'
    actual={Path(q).name for q in native['source_sha256']if (ROOT/q).parent==genroot}
    if actual!=set(generated['generated_sha256']):raise ValueError('entire SAME-generation HLS RTL/data required')
    run=ROOT/native['directory'];new_log=(run/'compile.log').read_text();old_log=(ROOT/old['directory']/'compile.log').read_text()
    warning=lambda t:[s for s in t.splitlines()if '%Warning-UNOPTFLAT:'in s]
    nodes=lambda t:[s.split('Circular combinational logic:',1)[-1].strip()for s in warning(t)]
    failed=records[names[-1]]
    if failed['pass_test']or failed['error_type']!='KeyError'or '.dat'not in failed['error']or failed['tests']or 'bench_elaborate_command'in failed:
        raise ValueError('original data-manifest startup failure retained, not runtime proof')
    pre=ROOT/'rdma/rnic/build/write-native-full-001-preimages-my3bvptZ'
    failed_sources=[pre/'rdma/rnic/tests'/n for n in ['segmented_write_native_sources.py','probe_segmented_write_native_full.py','segmented_write_payload_native_fixture.py']]
    if not all(q.is_file()for q in failed_sources):raise ValueError('exact failed source preimages required')
    for name,h in binding.PROTECTED.items():
        if digest(ROOT/name)!=h:raise ValueError('protected original raw source changed')
    check=subprocess.run(['bash','scripts/check.sh'],cwd=ROOT,capture_output=True,text=True,timeout=30)
    result=dict(scope=__doc__,audit_passed=True,overall_goal_complete=False,created_UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        evidence=identities,verified_bindings=sum(r['bindings_verified']for r in identities.values()),
        all34_original_inputs_and_summary_oracles_identical=True,actual_native_cases=36,
        compile_seconds=native['compilation_seconds'],maximum_case_seconds=max(r['seconds']for r in native['tests'].values()),
        cases_seconds={name:r['seconds']for name,r in native['tests'].items()},actual_native_module_counts=counts,
        same_generation_RTL_and_data_files=len(actual),fresh_binary_path=native['frozen_binary_path'],binary_sha256=native['binary_sha256'],
        new_WRITE_scope=dict(bytes=8193,packets=3,whole_and_packet_MR_queries=4,physical_page_writes=5,fences=3,actual_ACK_MAC_receipts=3,
            actual_native_PSN_commits=3,genuine_LAST_only_zero_capacity_RQ=True,whole_Immediate_CQ_bytes=8193,whole_Immediate_CQ_flags=3,
            final_MAC_withholding_cycles=1100,every_payload_pad_sentinel_and_ACK_frame_byte=True),
        retained_UNOPTFLAT=dict(old_count=len(warning(old_log)),new_count=len(warning(new_log)),old_nodes=nodes(old_log),new_nodes=nodes(new_log),
            waived=False,loop_or_original_timing_qualification=False),
        source_sha256={str(Path(__file__).relative_to(ROOT)):digest(__file__)},protected_raw_sha256=binding.PROTECTED,
        failed_startup_preimage_sha256={str(q.relative_to(ROOT)):digest(q)for q in failed_sources},
        inherited_source_check=dict(exit=check.returncode,stdout=check.stdout,stderr=check.stderr,overall_suite_passed=check.returncode==0,original_gate_unchanged=True),
        current_software_limit='Exact profile7 CQ flags3 remains<=4096; actual new8193/flags3 native snapshot is NOT yet matched to a new kernel/provider capability tuple.',
        physical_host_root_peer_PHY_PTP_models=True,two_state_native_simulation=True,live_Linux_or_physical=False,full_board_timing=False,
        remaining=['All11 original requirements remain; this actual native milestone is not a smaller completion target.',
            'Full1MiB actual native SEND/WRITE/Immediate/RECV, multiSGE and matched registered kernel/provider/standard API lifetimes remain.',
            'Real-peer nonterminal MSN/interoperability/recovery/NAK/RNR/congestion and safe partial-HLS-message teardown remain.',
            'Original4ns/default1.08ns/full-board fit/setup/hold/CDC/DRC/routing and short supervised physical work remain; HLS15.571ns still FAILS.',
            'No reboot needed; restore ALL RAM-backed archived caches and prove authenticated exact-thread/goal revival before any necessary reboot.'],
        hardware_install_load_network_fan_BIOS_flash_reboot_actions=[],commit_or_push=False)
    with a.report.open('x')as f:f.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(audit_passed=True,verified_bindings=result['verified_bindings'],actual_native_cases=36,native_WRITE_bytes=8193,physical=False)),flush=True)


if __name__=='__main__':main()
