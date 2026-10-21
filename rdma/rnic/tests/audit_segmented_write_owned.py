#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual typed-WRITE HLS consumers and unchanged compatibility provenance.

This audit proves the C++ consumer/source cohort, not generated RTL, native
MR/DMA/MAC/CQ/Linux, original timing or physical completion. RTL generation
is evaluated separately; a live synthesis process is not a successful bitfile.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import audit_segmented_receive as binding
from probe_segmented_write_owned_hls import verify_packet_receipts
from probe_segmented_write_receive_hls import verify_write_receive

ROOT=binding.ROOT;PREFIX=binding.PREFIX;digest=binding.digest
sys.path.insert(0,str(ROOT/'rdma/rnic/hls'))
import segmented_write_owned_transport as candidate


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve all previous evidence')
    actual,a_id=binding.bindings('segmented-write-owned-hls-001')
    compat,c_id=binding.bindings('segmented-write-owned-compat-001')
    old,o_id=binding.bindings('segmented-write-receive-hls-001')
    prior,p_id=binding.bindings('segmented-write-rx-front-diagnostics-001')
    failed,f_id=binding.bindings('write-owned-source-startup-001',
        {'rdma/rnic/hls/segmented_write_owned_transport.py':'rdma/rnic/build/write-owned-startup-001-preimages-14oN9Wmy'})
    if not all(r.get('pass_test')and r.get('source_unchanged')for r in [actual,compat,old])or not prior.get('audit_passed')or failed.get('pass_test'):
        raise ValueError('all actual old/new consumers, compatibility and preserved failure required')
    expected=set(old['tests'])|{'write-owned-hold'}|{'write-owned-bad'+str(i)for i in range(21)}
    if len(old['tests'])!=65 or set(actual['tests'])!=expected or len(expected)!=87 or \
       not actual.get('full_top_CPP_compiled')or not actual.get('all65_prior_modes_retained'):
        raise ValueError('complete exact65 old modes and22 typed-WRITE cases required')
    if (actual['runtime_limit_seconds'],actual['compile_limit_seconds'])!=(30,600)or \
       any(t['exit']!=0 or t['seconds']>30 for t in actual['tests'].values()):raise ValueError('all original consumer bounds required')
    # Every old summary assertion stays identical; new typed evidence is an
    # additional field/consumer, not a replacement for an old wire oracle.
    for mode,t in old['tests'].items():
        for marker,summary in t['summaries'].items():
            if actual['tests'][mode]['summaries'].get(marker)!=summary:raise ValueError('old actual consumer summary changed:'+mode+'/'+marker)
    for mode in ['write-rx','write-rx-imm']:
        t=actual['tests'][mode];log=(ROOT/actual['directory']/(mode+'.log')).read_text()
        if t['independent_write_packet_oracles']!=verify_packet_receipts(log)or \
           t['independent_write_receive_oracles']!=verify_write_receive(log,mode=='write-rx-imm'):
            raise ValueError('complete current raw receipt/data/ACK/MSN/RQ oracles required')
        s=t['summaries']['WRITE_PACKET_HLS']
        if (s['packets'],s['max_bytes'])!=(284,1048576)or not all(s[k]for k in ['full424_owner','actual_payload_EOF_ACK_MSN_same_PSN_table','RQ_not_remote_packet_owner']):
            raise ValueError('same actual data/ACK/table consumers with full424 identity required')
    hold=actual['tests']['write-owned-hold']['summaries']['WRITE_PACKET_HOLD']
    if not all(hold[k]for k in ['missing_owner_blocks','actual_payload_EOF_required','actual_ACK_MSN_required',
        'actual_same_PSN_table_required','consumer_withholding_blocks']):raise ValueError('withholding actual consumers must block456 receipt')
    if compat['simulation_limit_seconds']!=30 or not all(compat.get(k)for k in ['full_top_CPP_compiled','service_RTL_actual',
        'compatibility_runner_unchanged','wrapper_and_harness_unchanged'])or len(compat['transfers'])!=9 or len(compat['actual_core_receipts'])!=9:
        raise ValueError('unchanged real owned-service/memory RTL compatibility required')
    if compat['summaries']['ATOMIC_OWNED_HLS']['atomic_jobs']!=9 or \
       compat['summaries']['IMMEDIATE_REQUEST_HLS']['real_request_retire_receipts']!=8 or \
       compat['summaries']['IMMEDIATE_RECEIVE_HLS']['request_and_receive_receipts']!=8:
        raise ValueError('all actual prior Atomic/Immediate consumers required')
    source=ROOT/'rdma/rnic/build/native-segmented-write-owned-transport-002';info=json.loads((source/'source.json').read_text())
    if info['HLS_top']!=candidate.NAME or (info['write_packet_owner_bits'],info['write_packet_receipt_bits'])!=(424,456):
        raise ValueError('exact new typed424/456 source required')
    for name,h in info['derived_sources'].items():
        if digest(source/'fns'/name)!=h:raise ValueError('actual tested source changed:'+name)
    for name,h in info['parent_tree_sha256'].items():
        if digest(Path(info['parent_source'])/name)!=h:raise ValueError('qualified parent changed:'+name)
    untested=ROOT/'rdma/rnic/build/native-segmented-write-owned-transport-001'
    first=json.loads((untested/'source.json').read_text())
    old_generator=ROOT/'rdma/rnic/build/write-owned-cohort001-preimages-MhQdXyFh/rdma/rnic/hls/segmented_write_owned_transport.py'
    if first['generator_sha256']!=digest(old_generator)or first['actual_CPP_runtime']or first['generated_HLS']:
        raise ValueError('source001 was superseded before execution, not a successful runtime')
    for name,h in first['derived_sources'].items():
        if digest(untested/'fns'/name)!=h:raise ValueError('superseded prototype changed:'+name)
    for n,h in binding.PROTECTED.items():
        if digest(ROOT/n)!=h:raise ValueError('protected raw source changed:'+n)
    check=subprocess.run(['bash','scripts/check.sh'],cwd=ROOT,capture_output=True,text=True,timeout=30)
    identities=[a_id,c_id,o_id,p_id,f_id]
    result=dict(scope=__doc__,audit_passed=True,overall_goal_complete=False,hardware_verified=False,
        actual_HLS_CPP=a_id,actual_compatibility=c_id,old65=o_id,previous_checked_frontend=p_id,original_startup_failure=f_id,
        verified_bindings=sum(v['bindings_verified']for v in identities),
        source_sha256={str(Path(__file__).relative_to(ROOT)):digest(__file__)},protected_raw_sha256=binding.PROTECTED,
        current_modes=87,all65_old_modes_and_summaries_retained=True,new_cases=22,
        compile_seconds=actual['compile_seconds'],maximum_mode_seconds=max(t['seconds']for t in actual['tests'].values()),
        new_WRITE_mode_seconds={m:actual['tests'][m]['seconds']for m in ['write-rx','write-rx-imm']},
        actual_payload_EOF_ACK_MSN_and_same_PSN_table=True,full424_owner_and_actual456_receipt=True,
        packets_per_operation=284,messages_per_operation=6,max_CPP_message_bytes=1048576,
        late_RQ_does_not_consume_or_lose_remote_owner=True,posted620_and_remote424_not_aliased=True,
        no_fixed_delay_global_idle_fake_RQ_or_synthetic_completion=True,
        compatibility=dict(actual_service_RTL=True,Atomic_jobs=9,Immediate_TX=8,Immediate_RX=8,
            compile_seconds=compat['compile_seconds'],runtime_seconds=compat['simulation_seconds']),
        source001_superseded_before_CPP=True,source001_generator_preimage=str(old_generator.relative_to(ROOT)),
        source_only_late_RQ_fix='Require both real remote owner and late posted RQ availability before consuming either; source001 was never executed or synthesized.',
        modeled_boundaries=['protected native424 owner input','peer/connection/input packets','posted RQ','memory source/sink'],
        new_generated_RTL_evaluated_by_this_audit=False,full_native_integration=False,actual_backend_visibility_or_MAC_CQ=False,
        live_Linux_RTL_coupling=False,original4ns_timing_met=False,matched_new_software=False,
        inherited_source_check=dict(exit=check.returncode,stdout=check.stdout,stderr=check.stderr,overall_suite_passed=check.returncode==0,original_gate_unchanged=True),
        remaining=['All original11 requirements remain; this is actual HLS C++ evidence only.',
            'Generate exact new RTL and verify old/new ports, then connect protected frontend/shared MR/PTE/DMA/nonce/fence, typed424 owner, actual456 HLS receipt, real ACK-MAC/SFD/EOF/tail and whole CQ/remote/RQ retire fanout.',
            'Use one disjoint ACK tag allocator for WRITE and real RQ paths, retaining both full identities on LAST Immediate; do not use fake620 owners or collide with existing private MAC tags.',
            'Actual HLS write-message state persists across FIRST/MID; a modeled parent drain/cancel is not proof of safe HLS cancellation or MR unpin. Privileged message teardown still needs real lifetime/drain handling.',
            'Full native1MiB, matched software, multiSGE/live Linux/ref coupling, short real-peer recovery/RNR/MSN/congestion and original4ns/default1.08ns board/physical qualification remain.',
            'No reboot needed; restore ALL archived RAM caches and prove authenticated exact-thread/active-goal revival before any necessary reboot.'],
        hardware_install_load_network_fan_BIOS_flash_reboot_actions=[],commit_or_push=False)
    with a.report.open('x')as f:f.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(audit_passed=True,modes=87,old65=True,verified_bindings=result['verified_bindings'],generated_RTL_or_native_evaluated=False)),flush=True)


if __name__=='__main__':main()
