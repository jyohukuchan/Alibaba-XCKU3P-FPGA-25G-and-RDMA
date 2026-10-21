#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Audit real typed HLS/native boundary and exact native MR-island execution.

This proves compile plus isolated MR arbitration, NOT integrated WRITE
frontend/DMA/ACK/CQ runtime. All11 original requirements remain open.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess
import audit_segmented_receive as binding
import probe_write_native_mr_gateway as mr

ROOT=binding.ROOT;digest=binding.digest;candidate=mr.candidate
GEN='rdma/rnic/fpga/derive_segmented_write_native_gateway.py'
CHECK='rdma/rnic/tests/check_segmented_write_native_gateway.py'
PROBE='rdma/rnic/tests/probe_write_native_mr_gateway.py'
OBS='rdma/rnic/tests/write_native_mr_observe.v'
PRE1='rdma/rnic/build/write-native-gateway-001-preimages-aotdW0iC'
PRE2='rdma/rnic/build/write-native-gateway-002-preimages-t3XTiZ1M'
MRPRE='rdma/rnic/build/write-native-mr-001-preimages-nmGbqkwQ'
OBSPRE='rdma/rnic/build/write-native-mr-observer-001-preimages-Bp6Fip1P'


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve every previous report')
    spec=[('segmented-write-native-gateway-003',None),('segmented-write-native-gateway-001',{GEN:PRE1,CHECK:PRE1}),
        ('segmented-write-native-gateway-002',{CHECK:PRE2}),('write-native-mr-gateway-002',None),
        ('write-native-mr-gateway-001',{PROBE:MRPRE}),('write-native-mr-observer-001',{OBS:OBSPRE}),
        ('write-native-mr-observer-002',None),('remote-write-memory-diagnostics-001',None)]
    rows={};ids={}
    for name,fallback in spec:rows[name],ids[name]=binding.bindings(name,fallback)
    native=rows[spec[0][0]];failed1=rows[spec[1][0]];failed2=rows[spec[2][0]];actual=rows[spec[3][0]];failedmr=rows[spec[4][0]]
    if not native['pass_test']or not native['full_native_elaboration']or not native['source_unchanged']or \
       native['protected_WRITE_controller_inserted']or native['runtime_test']or native['complete_WRITE_native_runtime']or \
       native['HLS_stub']or native['unknown_leaves_ignored']:
        raise ValueError('actual compile and truthful unintegrated/runtime scope required')
    if native['original_actual_MR_arbiter_count']!=3 or native['module_counts']['rocev2_mr_query_arbiter']!=4 or \
       native['module_counts'].get('rocev2_mr_table')!=1 or native['module_counts'].get(candidate.HLS_TOP)!=1 or \
       native['module_counts'].get('rocev2_native_segmented_receive_top')!=0 or native['actual_typed_WRITE_join_count']!=1 or \
       not native['both_global_HLS_drains_zero']or native['compiler_exit']!=0 or native['compile_seconds']>180:
        raise ValueError('one actual HLS/MR/backend domain and original gates required')
    run=ROOT/native['directory'];protected=(run/'rocev2_shared_protected_responder.v').read_text()
    current=candidate.derive();parent=candidate.parent.derive()
    if protected!=current[candidate.RTL/'rocev2_protected_responder.v']:
        raise ValueError('actual compiled new gateway source changed')
    for n in native['changed_native_leaves']:
        key=next(q for q in current if q.name==n)
        alias='rocev2_shared_protected_responder.v'if n=='rocev2_protected_responder.v'else n
        if (run/alias).read_text()!=current[key]:raise ValueError('actual propagated native boundary changed:'+n)
    if len(native['changed_native_leaves'])!=9:raise ValueError('exact9 reviewed native boundary leaves required')
    islandrun=ROOT/actual['directory'];bench,island,guard=mr.bench(protected)
    for name,text in [('tb.v',bench),('native_mr_island.v.txt',island),('native_write_guard.v.txt',guard),('native_protected.v.txt',protected)]:
        if (islandrun/name).read_text()!=text:raise ValueError('actual MR island must be exact compiled-native bytes:'+name)
    if not actual['pass_test']or not actual['source_unchanged']or len(actual['tests'])!=8 or \
       (actual['compile_limit_seconds'],actual['runtime_limit_seconds'],actual['clock_ns'],actual['cycle_limit'])!=(10,10,4,100000):
        raise ValueError('all8 actual bounded native MR island modes required')
    for k,t in actual['tests'].items():
        s=t['summary'];denied=int(k)in [2,3,6];count=0 if denied else 5 if k=='7'else 4
        if t['exit']or t['seconds']>10 or not s['pass_test']or s['queries']!=count or s['responses']!=count or s['native_guard_denied']!=denied:
            raise ValueError('same-tag native query/denial/invalidation scope mismatch:'+k)
    for k in map(str,range(7)):
        if actual['tests'][k]['summary']!=failedmr['tests'][k]['summary']:raise ValueError('prior completed MR modes changed')
    observed=rows['write-native-mr-observer-002']
    if observed['simulation_exit']!=1 or 'op=2 error=00 key=00000000 quiet=1'not in observed['stdout']:
        raise ValueError('actual INVALIDATE response is zero key, not a forged success')
    fixed=(ROOT/PROBE).read_text().replace("op==3 ? key:op==2 ? 32'd0:32'h80000008","op==3 ? key:32'h80000008")
    if fixed!=(ROOT/MRPRE/PROBE).read_text():raise ValueError('only actual opcode-specific management oracle corrected')
    old=(ROOT/PRE1/GEN).read_text()
    old=candidate.once(old,"return once(t,'    .m_recv_message_data(m_recv_message_data),',connections(HLS_FIELDS,mapping)+'    .m_recv_message_data(m_recv_message_data),')",
        "return once(t,'.m_recv_message_data(core_recv_message_data),',connections(HLS_FIELDS,mapping)+'.m_recv_message_data(core_recv_message_data),')")
    old=candidate.once(old,"        out[p]=once(t,'    .m_recv_message_data(m_recv_message_data),',connections(FIELDS)+'    .m_recv_message_data(m_recv_message_data),')",
        "        anchor='    .m_recv_message_data('+('rq_message_data'if name=='rocev2_native_rnic_endpoint'else'm_recv_message_data')+'),'\n        out[p]=once(t,anchor,connections(FIELDS)+anchor)")
    if old!=(ROOT/GEN).read_text():raise ValueError('only exact real routing anchors fixed from gateway001')
    if failed1['pass_test']or failed2['pass_test']or failedmr['pass_test']or failed2.get('compiler_exit')!=0:
        raise ValueError('preserve generator001, audit-key002 and MR fixture001 failure scope')
    # All unchanged inherited leaves still reconstruct exactly, including
    # request/READ/zero/Atomic and old ACK protection. No capability/default edit.
    changed={p for p in current if current[p]!=parent[p]}
    if len(changed)!=9 or any(current[p]!=parent[p]for p in current if p not in changed):raise ValueError('unreviewed graph edits')
    for n,h in binding.PROTECTED.items():
        if digest(ROOT/n)!=h:raise ValueError('protected raw source changed:'+n)
    check=subprocess.run(['bash','scripts/check.sh'],cwd=ROOT,capture_output=True,text=True,timeout=30)
    result=dict(scope=__doc__,audit_passed=True,overall_goal_complete=False,hardware_verified=False,
        evidence=ids,verified_bindings=sum(v['bindings_verified']for v in ids.values()),
        source_sha256={str(Path(__file__).relative_to(ROOT)):digest(__file__)},protected_raw_sha256=binding.PROTECTED,
        actual_new_HLS_native_elaboration=True,compile_seconds=native['compile_seconds'],changed_native_leaves=9,
        one_HLS_MR_backend_nonce_domain=True,old_MR_arbiters=3,new_MR_arbiters=4,
        actual_native_MR_island_cases=8,maximum_MR_seconds=max(t['seconds']for t in actual['tests'].values()),
        same_tag_parallel_normal_SQ_Atomic_WRITE=True,whole_lease_still_guards_invalidation_after_queries=True,
        actual_shared_invalidation_revokes_WRITE_key=True,no_MR_response_model=True,
        native_WRITE_frontend_backend_ACK_CQ_inserted=False,complete_native_WRITE_runtime=False,
        actual_generated_WRITE_payload_runtime=False,full_native_1MiB=False,live_Linux=False,
        modeled_MR_island_boundaries=['caller state/leases and management','normal/SQ/Atomic/WRITE requests/response consumers'],
        original_timing_met=False,original_HLS_estimate_ns=15.571,
        inherited_source_check=dict(exit=check.returncode,stdout=check.stdout,stderr=check.stderr,overall_suite_passed=check.returncode==0),
        remaining=['All11 original requirements retained; this is native boundary elaboration plus MR-island runtime, NOT a complete WRITE implementation.',
            'Connect raw checked classifier/frontend, native expected-PSN completion, packet memory/global backend/physical nonce, ONE ACK/late-RQ/whole-CQ and actual generated typed HLS end to end.',
            'Keep all old paths and exact new full-native compile/all34 regressions plus WRITE/Immediate; then full1MiB/matched software/multiSGE/live Linux refs/short peer recovery/RNR/MSN/congestion.',
            'Safe partial HLS message teardown/unpin and original4ns/default1.08ns board fit/setup/hold/CDC/DRC/routing/short supervised physical remain.',
            'No reboot needed; restore archived RAM caches and prove authenticated exact-thread/active-goal revival before any necessary reboot.'],
        hardware_install_load_network_fan_BIOS_flash_reboot_actions=[],commit_or_push=False)
    with a.report.open('x')as f:f.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(audit_passed=True,bindings=result['verified_bindings'],actual_new_HLS_elaboration=True,MR_cases=8,WRITE_runtime=False)),flush=True)


if __name__=='__main__':main()
