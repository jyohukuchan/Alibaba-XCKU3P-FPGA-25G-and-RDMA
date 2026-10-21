#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual packet MR/data/backend/ACK coupling, NOT complete native execution.

Descriptor/host ordering and HLS trace producers remain explicit models.
All11 original requirements, timing failure and exact failures are retained.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess
import audit_segmented_receive as binding
import probe_remote_write_memory as probe

ROOT=binding.ROOT;digest=binding.digest
RUNNER='rdma/rnic/tests/probe_remote_write_memory.py'
PRE={1:'rdma/rnic/build/remote-write-memory-001-preimages-RUG4en4n',
     2:'rdma/rnic/build/remote-write-memory-002-preimages-taynIuAK',
     3:'rdma/rnic/build/remote-write-memory-003-preimages-ffhUQpLN'}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve prior evidence')
    actual,a_id=binding.bindings('remote-write-memory-004')
    failed={};ids=[a_id]
    for n in [1,2,3]:
        r,v=binding.bindings('remote-write-memory-'+str(n).zfill(3),{RUNNER:PRE[n]});failed[n]=r;ids.append(v)
        if r['pass_test']:raise ValueError('do not relabel failed compile/early-data fixture')
    observed,o_id=binding.bindings('remote-write-memory-observer-001');ids.append(o_id)
    prior,p_id=binding.bindings('receive-write-ack-diagnostics-001');ids.append(p_id)
    hls,h_id=binding.bindings('segmented-write-owned-diagnostics-001');ids.append(h_id)
    generated,g_id=binding.bindings('segmented-write-owned-generated-diagnostics-001');ids.append(g_id)
    if not actual['pass_test']or not actual['source_unchanged']or set(actual['tests'])!={str(i)for i in range(14)}or \
       (actual['compile_limit_seconds'],actual['runtime_limit_seconds'],actual['clock_ns'],actual['cycle_limit'])!=(10,10,4,100000):
        raise ValueError('actual same-source14 modes and original bounds required')
    for k,v in actual['tests'].items():
        s=v['summary'];bad=int(k)>=3 and int(k)!=5
        if v['exit']or v['seconds']>10 or not s['pass_test']or s['mode']!=int(k)or s['fault']!=bad:
            raise ValueError('bounded actual expected result missing:'+k)
    if actual['compile_seconds']>10:raise ValueError('unchanged10s compile gate required')
    run=ROOT/actual['directory']
    if (run/'tb.v').read_text()!=probe.bench(probe.ack_test.candidate.derive(),probe.authorization.queue.derive()):
        raise ValueError('exact executed connected graph changed')
    expected=[(8193,5,3,3,3)]*4
    got=[]
    for mode in [0,1,2,5]:
        s=actual['tests'][str(mode)]['summary']
        if (s['packets'],s['completed'])!=(3,3):raise ValueError('all3 real packet completions required')
        got.append(tuple(s[n]for n in ['host_bytes','physical_writes','fences','nonce_commands','ACK_SFDs']))
        frames=probe.ack_test.physical.frames((run/(str(mode)+'.log')).read_text())
        want=[]
        for i in range(3):
            b=b''.join(int(v,16).to_bytes(16,'little')for v in (run/('write'+str(i)+'.hex')).read_text().split())[:62]
            want.append((0x6001+i,b))
        if frames!=want:raise ValueError('every actual XGMII/FCS/SFD/CDC ACK tag and byte required')
    if got!=expected:raise ValueError('all bytes/scattered descriptors/ordered fences/physical nonces/ACK SFD counts required')
    if failed[1]['error']!='connected WRITE compile failed'or failed[2]['error']!='connected WRITE compile failed'or \
       failed[3]['error']!='connected WRITE mode failed:5':raise ValueError('preserve exact failed results')
    for mode in range(5):
        if failed[3]['tests'][str(mode)]['summary']!=actual['tests'][str(mode)]['summary']:
            raise ValueError('old completed cases/oracles changed')
    if observed['simulation_exit']!=1 or \
       'packet=2 remaining=1 wire_remaining=4 KEEP=ffffffffffffffff LAST=0 pad_zero=1 known=1 issued=0 raw_seen=0 fault=0'not in observed['stdout']:
        raise ValueError('exact frozen early-data shape observation required')
    current=(ROOT/RUNNER).read_text()
    current=probe.authorization.queue.once(current,
        'e_s_hls_data=payload[0];e_s_hls_keep=keep((current_length+3)&~3);e_s_hls_last=current_length<=64;e_s_hls_valid=1;',
        "e_s_hls_data=payload[0];e_s_hls_keep=64'hffffffffffffffff;e_s_hls_last=0;e_s_hls_valid=1;")
    if current!=(ROOT/PRE[3]/RUNNER).read_text():raise ValueError('only correct early-data mask/EOF vector changed')
    current=probe.authorization.queue.once(current,
        ",m_status_ready='n_m_status_ready',m_command_ready='n_m_command_ready'))",
        ",m_status_ready='n_m_status_ready'))")
    current=probe.authorization.queue.once(current,'if(e_m_done_valid && done_ready && done_allow)begin','if(e_m_done_valid && e_m_done_ready)begin')
    if current!=(ROOT/PRE[2]/RUNNER).read_text():raise ValueError('only actual net/handshake connection fixed from002')
    current=probe.authorization.queue.once(current,"if target in ['link_m_cpl_valid','retire_token']:continue","if target in ['link_m_cpl_valid']:continue")
    if current!=(ROOT/PRE[1]/RUNNER).read_text():raise ValueError('only duplicate wire declaration fixed from001')
    for n in [1,2,3]:
        if failed[n]['source_sha256'][str(probe.MEMORY.relative_to(ROOT))]!=digest(probe.MEMORY):
            raise ValueError('no DUT change may hide an original fixture failure')
    # Independently inventory actual elaborated modules, not source filenames.
    binary=next(Path(n)for n in actual['RAM_artifact_sha256']if Path(n).name=='test');vvp=binary.read_text()
    names=['rocev2_remote_write_memory','rocev2_remote_write_message_guard','rocev2_mr_table',
        probe.authorization.queue.NAME,probe.ack_test.candidate.NAME,'rocev2_memory_command_nonce',
        'rocev2_paged_memory_backend','rocev2_mr_page_table','rocev2_page_dma_engine','rocev2_corundum_dma_backend',
        'dma_psdpram','dma_client_axis_sink','dma_client_axis_source','axis_xgmii_tx_64','axis_async_fifo_adapter']
    counts={n:len(re.findall(r'\.scope module, "[^\"]+" "'+n+r'"',vvp))for n in names}
    if any(v!=1 for v in counts.values()):raise ValueError('actual one-domain MR/PTE/backend/nonce/ACK/MAC graph missing:'+str(counts))
    for n,h in binding.PROTECTED.items():
        if digest(ROOT/n)!=h:raise ValueError('protected raw source changed:'+n)
    if not all(r['audit_passed']for r in [prior,hls,generated])or generated['timing_status']!='FAIL':
        raise ValueError('retain all actual previous evidence AND timing failure')
    lint=subprocess.run(['verilator','--lint-only','--top-module','rocev2_remote_write_memory','-Wno-fatal',str(probe.MEMORY)],
        cwd=ROOT,capture_output=True,text=True,timeout=10)
    if lint.returncode or re.search(r'%Warning-(UNOPTFLAT|LATCH|MULTIDRIVEN|UNDRIVEN|PINMISSING)',lint.stderr):
        raise ValueError('new memory leaf has unresolved loop/driver/latch/elaboration issue:'+lint.stderr)
    check=subprocess.run(['bash','scripts/check.sh'],cwd=ROOT,capture_output=True,text=True,timeout=30)
    result=dict(scope=__doc__,audit_passed=True,overall_goal_complete=False,hardware_verified=False,
        current=a_id,immutable_failed={str(i):ids[i]for i in [1,2,3]},read_only_observer=o_id,previous_ACK=p_id,
        prior_HLS=h_id,prior_generation=g_id,verified_bindings=sum(v['bindings_verified']for v in ids),
        source_sha256={str(Path(__file__).relative_to(ROOT)):digest(__file__)},protected_raw_sha256=binding.PROTECTED,
        cases=14,maximum_seconds=max(v['seconds']for v in actual['tests'].values()),compile_seconds=actual['compile_seconds'],
        actual_elaborated_modules=counts,actual_8193_host_bytes_and_all_sentinels=True,actual_page_write_descriptors=5,
        actual_fence_commands=3,actual_physical_nonce_commands=3,actual_ACK_MAC_SFD_CDC=3,
        actual_late_RQ_whole_CQ_ticket=True,independent_remote424_and_posted_zero_capacity620=True,
        actual_HLS_ACK_data_are_checked_CPP_trace_replay=True,live_generated_HLS=False,
        complete_native_PCIe_TLP_HLS_CQ_graph=False,full_native_1MiB=False,live_Linux=False,
        modeled_boundaries=['integrity-checked metadata/trusted QP','posted-RQ admission','HLS96/456/data/ACK and whole-RQ HLS producer','PCIe descriptor-engine/host ordering','clocks/PTP/physical pins','whole CQ commit/retire consumers'],
        leaf_lint=dict(exit=lint.returncode,stdout=lint.stdout,stderr=lint.stderr,no_loop_latch_driver_warnings=True,not_full_native_or_timing=True),
        inherited_source_check=dict(exit=check.returncode,stdout=check.stdout,stderr=check.stderr,overall_suite_passed=check.returncode==0),
        original_timing_met=False,original_estimated_ns=15.571,
        remaining=['All original11 requirements stay intact, not a component-only goal.',
            'Integrate this typed packet memory/HLS/ACK bridge into complete native graph, SAME actual MR/PTE/backend/physical nonce instances and all previous paths; replace ENTIRE HLS module/data set with new002.',
            'Prove actual new generated native elaboration/runtime and all original34 regressions plus WRITE/Immediate, real PCIe TLP/whole CQ graph, full1MiB/matched software/multiSGE/live Linux refs.',
            'Preserve independent genuine late-RQ lifetimes and actual MR/PTE guards through whole CQ; privileged partial-message HLS teardown/unpin remains unproved.',
            'Short real-peer recovery/RNR/MSN/congestion and original4ns/default1.08ns full-board fit/setup/hold/CDC/DRC/routing/short supervised physical qualification remain.',
            'No reboot needed; restore all archived RAM caches and prove authenticated exact-thread/active-goal revival before any necessary reboot.'],
        hardware_install_load_network_fan_BIOS_flash_reboot_actions=[],commit_or_push=False)
    with a.report.open('x')as f:f.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(audit_passed=True,cases=14,actual_host_bytes=8193,verified_bindings=result['verified_bindings'],complete_native=False)),flush=True)


if __name__=='__main__':main()
