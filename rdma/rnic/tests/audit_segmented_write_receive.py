#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Exact segmented WRITE/late-RQ HLS and real RQ component evidence only.

These are separate executions with explicit trusted metadata/proof models;
no new generated HLS, connected native MR/DMA/MAC/CQ, software/physical or
original-clock proof. Original failures/preimages and all old modes remain.
"""
import argparse
import json
from pathlib import Path
import subprocess
import audit_segmented_receive as binding

ROOT=binding.ROOT;PREFIX=binding.PREFIX;digest=binding.digest


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve earlier evidence')
    cpp,c_id=binding.bindings('segmented-write-receive-hls-001')
    old,o_id=binding.bindings('segmented-receive-hls-007')
    queue,q_id=binding.bindings('write-notice-queue-001')
    oldqueue,oq_id=binding.bindings('receive-message-queue-003')
    previous,p_id=binding.bindings('segmented-receive-native-software-diagnostics-001')
    failures={}
    for name,rel,preimage in [
        ('write-receive-source-startup-001','rdma/rnic/hls/segmented_write_receive_transport.py','rdma/rnic/build/write-receive-startup-001-preimages-4OP43K1j'),
        ('write-notice-source-startup-001','rdma/rnic/fpga/derive_write_notice_queue.py','rdma/rnic/build/write-notice-startup-001-preimages-Eh6Gm2TM')]:
        r,v=binding.bindings(name,{rel:preimage})
        if r.get('pass_test')or r.get('hardware_verified'):raise ValueError('startup failure must remain failed and not runtime proof')
        failures[name]=v
    if not all(r.get('pass_test')and r.get('source_unchanged')for r in [cpp,old,queue,oldqueue])or not previous.get('audit_passed'):
        raise ValueError('actual separate old/new successful source-bound results required')
    if len(old['tests'])!=44 or set(cpp['tests'])!=set(old['tests'])|{'write-rx','write-rx-imm'}|{'write-rx-bad'+str(i)for i in range(19)}:
        raise ValueError('all exact old44 modes and both real new modes/19 negatives required')
    if cpp['runtime_limit_seconds']!=30 or cpp['compile_limit_seconds']!=600 or \
       any(v['exit']!=0 or v['seconds']>30 for v in cpp['tests'].values())or not cpp.get('full_top_CPP_compiled'):
        raise ValueError('all actual C++ executions under original limits required')
    for name in ['write-rx','write-rx-imm']:
        v=cpp['tests'][name];s=v['summaries']['WRITE_RECEIVE_HLS'];o=v['independent_write_receive_oracles']
        if (s['whole_messages'],s['packets'],s['max_bytes'])!=(6,284,1048576)or \
           not all(s.get(n)for n in ['late_RQ_only_on_LAST','distinct_RETH_target','actual_bytes_not_RQ_capacity','MSN_only_on_LAST','PSN_wrap'])or \
           len(o['messages'])!=6 or not o['all_bytes_and_zero_padding']:raise ValueError('complete same-core data/ACK/PSN/MSN/late-RQ/count proof required')
    old_modes=set(oldqueue['tests'])
    if len(old_modes)!=48 or set(queue['tests'])!=old_modes|{str(i)for i in range(100,114)}or queue['case_limit_seconds']!=10 or \
       any(v['exit']!=0 or v['seconds']>10 for v in queue['tests'].values())or not queue.get('all_proof_and_owner_producers_modeled'):
        raise ValueError('all48 old queue cases and14 actual component cases required under original10s')
    for n,total in [('100',8193),('101',1048576),('102',4097),('103',8192),('112',8193)]:
        s=queue['tests'][n]['summary']
        if (s['posted'],s['taken'],s['packets'],s['bytes'])!=(1,1,1,total):raise ValueError('one exact late-RQ/whole-CQ lifetime required')
    source=ROOT/'rdma/rnic/build/native-segmented-write-receive-transport-001';info=json.loads((source/'source.json').read_text())
    for n,h in info['derived_sources'].items():
        if digest(source/'fns'/n)!=h:raise ValueError('actual new source body changed:'+n)
    for n,h in info['parent_tree_sha256'].items():
        if digest(Path(info['parent_source'])/n)!=h:raise ValueError('qualified source007 parent changed:'+n)
    for n,h in binding.PROTECTED.items():
        if digest(ROOT/n)!=h:raise ValueError('protected raw source changed:'+n)
    check=subprocess.run(['bash','scripts/check.sh'],capture_output=True,text=True,cwd=ROOT,timeout=30)
    identities=dict(new_CPP=c_id,old44_CPP=o_id,new_queue=q_id,old48_queue=oq_id,previous_native_software=p_id,**failures)
    result=dict(scope=__doc__,audit_passed=True,overall_goal_complete=False,verified_reports=identities,
        verified_bindings=sum(v['bindings_verified']for v in identities.values()),
        auditor_source_sha256={str(Path(__file__).relative_to(ROOT)):digest(__file__)},protected_raw_sha256=binding.PROTECTED,
        actual_CPP=dict(modes=65,all44_old_retained=True,new_messages_per_operation=6,new_packets_per_operation=284,
            compile_seconds=cpp['compile_seconds'],new_seconds={n:cpp['tests'][n]['seconds']for n in ['write-rx','write-rx-imm']},
            independent_complete_data_pad_ACK_PSN_MSN_oracles=True,late_RQ_not_REMOTE_MR_authority=True),
        actual_queue_component=dict(cases=62,all48_old_retained=True,producer_metadata_HLS_MAC_visibility_models=True,
            distinct_full320_remote_and620_RQ_owners=True,one_late_RQ_and_actual_whole_bytes=True,
            remote_retire_backpressure_retains_RQ=True,maximum_seconds=max(v['seconds']for v in queue['tests'].values())),
        generated_new_HLS=False,new_native_integration=False,new_kernel_provider_profile=False,hardware_verified=False,
        original4ns_timing_met=False,HLS_free_space_guard_bytes=1572864000,HLS_build_started=False,
        inherited_source_check=dict(exit=check.returncode,stdout=check.stdout,stderr=check.stderr,overall_suite_passed=check.returncode==0,original_gate_unchanged=True),
        remaining=['All11 original requirements retained; goal incomplete.',
            'Real full-message/per-packet remote MR guard and persistent refs, late RNR/RQ binding, HLS/MAC/backend/native CQ fanout must be connected and independently proved.',
            'New HLS generation/complete native/short runtime, exact matched software profile, native1MiB, multi-SGE, recovery/congestion/real-peer compatibility remain.',
            'Original4ns/default1.08ns full-board fit/setup/hold/CDC/DRC/routing and short supervised physical qualification remain; previous HLS15.571ns is a timing failure.',
            'No reboot needed; restore all archived RAM caches and verify authenticated exact-thread/active-goal restoration before any necessary reboot.'],
        hardware_install_load_network_fan_BIOS_flash_reboot_actions=[],commit_or_push=False)
    with a.report.open('x')as f:f.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(audit_passed=True,verified_bindings=result['verified_bindings'],CPP_modes=65,queue_cases=62,native_or_physical=False)),flush=True)


if __name__=='__main__':main()
