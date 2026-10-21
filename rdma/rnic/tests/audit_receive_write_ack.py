#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Audit shared WRITE/RQ ACK execution, actual MAC, scope and exact failures.

Actual HLS C++ trace replay is NOT live generated-HLS/native/DMA/CQ proof.
The original timing failure and all eleven requirements remain open.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess
import audit_segmented_receive as binding
import probe_receive_write_ack as probe

ROOT=binding.ROOT;digest=binding.digest;candidate=probe.candidate
RUNNER='rdma/rnic/tests/probe_receive_write_ack.py'
FAIL1='rdma/rnic/build/receive-write-ack-001-preimages-WpJcqto9'
FAIL2='rdma/rnic/build/receive-write-ack-002-preimages-dMstVq5Y'


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve all prior evidence')
    good,g=binding.bindings('receive-write-ack-003')
    fail1,f1=binding.bindings('receive-write-ack-001',{RUNNER:FAIL1})
    fail2,f2=binding.bindings('receive-write-ack-002',{RUNNER:FAIL2})
    observed,obs=binding.bindings('receive-write-ack-observer-001')
    hls,h=binding.bindings('segmented-write-owned-diagnostics-001')
    generated,gen=binding.bindings('segmented-write-owned-generated-diagnostics-001')
    masks,m=binding.bindings('CRC-constant-masks-001',{
        'rdma/rnic/tests/probe_segmented_write_rx_frontend.py':'rdma/rnic/build/write-rx-front-004-preimages-4xDD69LD'})
    if not good.get('pass_test')or not good.get('source_unchanged')or fail1.get('pass_test')or fail2.get('pass_test'):
        raise ValueError('actual full execution and immutable failures required')
    if set(good['tests'])!={str(i)for i in probe.MODES}or len(probe.MODES)!=58 or \
       (good['compile_limit_seconds'],good['runtime_limit_seconds'],good['clock_ns'],good['cycle_limit'])!=(10,10,4,100000):
        raise ValueError('all58 exact modes and original bounds required')
    for k,v in good['tests'].items():
        s=v['summary']
        if v['exit']or v['seconds']>10 or not s['pass_test']or s['mode']!=int(k)or s['fault']!=(int(k)>=20):
            raise ValueError('actual expected positive/quarantine result missing:'+k)
    if good['shared_compile_seconds']>10 or any(v['exit']or v['seconds']>10 for v in good['legacy_tests'].values()):
        raise ValueError('all original legacy assertions and limits required')
    for old in [fail1,fail2]:
        if old['legacy_tests']!= {k:v for k,v in old['legacy_tests'].items()}or \
           {k:v['summary']for k,v in old['legacy_tests'].items()}!={k:v['summary']for k,v in good['legacy_tests'].items()}:
            raise ValueError('both old legacy modes/summaries must stay exact')
    if fail1['error']!='compile failed:shared'or fail2['error']!='simulation failed:1'or \
       fail2['tests']['0']['summary']!=good['tests']['0']['summary']:
        raise ValueError('do not relabel original compile/protocol-fixture failures')
    if observed['simulation_exit']!=1 or 'held=1 wr_sent=1 rq_sent=1 wr_VALID=1 wr_READY=0 rq_VALID=0 rq_READY=1 fault=0'not in observed['stdout']:
        raise ValueError('exact read-only READY-not-a-transfer observation required')
    current=(ROOT/RUNNER).read_text();before=(ROOT/FAIL2/RUNNER).read_text()
    for message in ['WRITE retired without real RQ retire','RQ retired without WRITE retire']:
        new='repeat(11)begin tick;if(!busy || s_write_retire_valid && s_write_retire_ready || s_retire_valid && s_retire_ready)\n    $fatal(1,"'+message+'");end'
        old='repeat(11)begin tick;if(!busy || s_write_retire_ready || s_retire_ready)$fatal(1,"'+message+'");end'
        current=candidate.once(current,new,old)
    if current!=before:raise ValueError('only VALID-and-READY transfer assertions may change from002')
    current=current.replace('input integer write_op,notify;','input integer write_op,input integer notify;')
    current=candidate.once(current,'input integer n,notify;','input integer n,input integer notify;')
    if current!=(ROOT/FAIL1/RUNNER).read_text():raise ValueError('only task declaration syntax may change from001')
    # Reconstruct the qualified parent EXACTLY by undoing every explicit
    # extension in reverse order. No whitespace or data normalization.
    changes=[];real_once=candidate.once
    def capture(t,old,new):changes.append((old,new));return real_once(t,old,new)
    candidate.once=capture
    try:text=candidate.derive()
    finally:candidate.once=real_once
    projected=text
    for old,new in reversed(changes):projected=real_once(projected,new,old)
    if projected!=candidate.parent.derive():raise ValueError('qualified parent does not reconstruct byte-for-byte')
    run=ROOT/good['directory'];actual=(run/(candidate.NAME+'.v')).read_text()
    if actual!=text or (run/'tb.v').read_text()!=probe.bench(text):raise ValueError('executed derived source/bench changed')
    if text.count('reg [TAG_SEQUENCE_WIDTH:0] tag_sequence=0;')!=1 or \
       text.count("active_tag<=16'h6000|")!=2 or 'wire private_cpl=s_cpl_tag[15:13]==3\'b011;'not in text:
        raise ValueError('ONE allocator/counter and SAME class6000 required')
    if (run/'lfsr_constant_masks.v').read_text()!=probe.crc.compiletime_lfsr()or \
       not masks['all_state_and_data_output_masks_checked']or masks['coefficients_compared']!=55296:
        raise ValueError('all448 exact original CRC masks and unchanged helper required')
    traced,paths=probe.traces()
    if good['actual_HLS_trace_replay_only']!=traced or any(digest(ROOT/n)!=v for n,v in good['actual_HLS_trace_sha256'].items()):
        raise ValueError('exact HLS trace bodies/tokens, not a live generated-HLS claim')
    mac=good['tests']['5'];log=(run/'5.log').read_text();frames=probe.physical.frames(log)
    expected_tags=list(range(0x6001,0x6006))
    if [t for t,_ in frames]!=expected_tags or mac['summary']!={'pass_test':True,'mode':5,'fault':0,'operations':5,
        'frames':5,'receipts':5,'WRITE_proofs':3,'RQ_proofs':3,'actual_SFDs':5,'cycles':11149}:
        raise ValueError('five actual MAC/FCS/SFD/CDC frames and six independent proofs required')
    def frame_file(name):
        return b''.join(int(v,16).to_bytes(16,'little')for v in (run/name).read_text().split())[:62]
    expected=[frame_file('recv.hex'),*[frame_file('write'+str(i)+'.hex')for i in range(3)],frame_file('recv.hex')]
    if [f for _,f in frames]!=expected:raise ValueError('every actual MAC wire byte must match exact independently framed HLS ACK')
    binaries=list(good['RAM_artifact_sha256'])
    binary=next(Path(n)for n in binaries if Path(n).name=='shared');vvp=binary.read_text()
    counts={n:len(re.findall(r'\.scope module, "[^\"]+" "'+n+r'"',vvp))for n in [candidate.NAME,'axis_xgmii_tx_64','axis_async_fifo_adapter','axis_async_fifo']}
    if counts!={candidate.NAME:1,'axis_xgmii_tx_64':1,'axis_async_fifo_adapter':1,'axis_async_fifo':2}:
        raise ValueError('actual one-allocator/MAC/two-CDC-FIFO elaboration required:'+str(counts))
    for n,v in binding.PROTECTED.items():
        if digest(ROOT/n)!=v:raise ValueError('protected raw source changed:'+n)
    if not hls['audit_passed']or not generated['audit_passed']or generated['timing_status']!='FAIL':
        raise ValueError('retain prior actual HLS proof AND original timing failure')
    lint=subprocess.run(['verilator','--lint-only','--top-module',candidate.NAME,'-GIMMEDIATE_ENABLE=1','-Wno-fatal',str(run/(candidate.NAME+'.v'))],
        cwd=ROOT,capture_output=True,text=True,timeout=10)
    if lint.returncode or re.search(r'%Warning-(UNOPTFLAT|LATCH|MULTIDRIVEN|UNDRIVEN|PINMISSING)',lint.stderr):
        raise ValueError('actual leaf has an unresolved combinational/driver/elaboration issue:'+lint.stderr)
    check=subprocess.run(['bash','scripts/check.sh'],cwd=ROOT,capture_output=True,text=True,timeout=30)
    identities=[g,f1,f2,obs,h,gen,m]
    result=dict(scope=__doc__,audit_passed=True,overall_goal_complete=False,hardware_verified=False,
        actual_shared_ACK=g,failed_compile=f1,failed_fixture_transfer=f2,read_only_observer=obs,
        prior_HLS_consumers=h,prior_generated=gen,exact_CRC_masks=m,verified_bindings=sum(v['bindings_verified']for v in identities),
        source_sha256={str(Path(__file__).relative_to(ROOT)):digest(__file__)},protected_raw_sha256=binding.PROTECTED,
        modes=58,unchanged_legacy_tests=2,maximum_seconds=max(v['seconds']for v in good['tests'].values()),
        actual_MAC_frames=5,actual_MAC_tags=expected_tags,actual_elaborated_modules=counts,
        qualified_parent_reconstructed_byte_for_byte=True,separate_remote424_and_posted620=True,
        one_ACK_sequence_without_tag_class_collision=True,dual_proofs_independently_backpressured=True,
        no_unpaired_retirement_transfer=True,actual_EOF_SFD_receipt_and_1024tail_required=True,
        HLS_receipts_are_exact_trace_replay_not_live_generated_RTL=True,
        modeled_boundaries=['privileged owner/posted-RQ admission','HLS receipt and ACK trace replay','backend visibility/fence','whole CQ and retire consumers','clocks/PTP and PHY pins'],
        native_backend_generated_HLS_MAC_CQ_whole_graph=False,full_native_1MiB=False,live_Linux=False,
        original_timing_met=False,original_HLS_estimate_ns=15.571,
        leaf_lint=dict(exit=lint.returncode,stdout=lint.stdout,stderr=lint.stderr,no_combinational_latch_or_driver_warnings=True,not_board_timing=True),
        inherited_source_check=dict(exit=check.returncode,stdout=check.stdout,stderr=check.stderr,overall_suite_passed=check.returncode==0),
        remaining=['All original11 requirements stay open; this is an actual shared ACK/MAC leaf, not the native endpoint.',
            'Join actual424/456 generated HLS, native backend/DMA/physical nonce/fence and472 ACK proof before remote DONE; independently retire true RQ packet and whole CQ.',
            'Integrate SAME MR/PTE/data/native graph with all prior paths; retain full1MiB/matched software/multiSGE/live Linux and short peer/RNR/MSN/congestion qualification.',
            'Privileged partial-WRITE HLS state teardown is unproved; modeled drained/cancel is not safe unpin/reset proof.',
            'Original4ns/default1.08ns full-board fit/setup/hold/CDC/DRC/routing and short physical qualification remain; timing estimate still fails.',
            'No reboot needed; restore archived RAM caches and prove authenticated exact-thread/goal revival before any necessary reboot.'],
        hardware_install_load_network_fan_BIOS_flash_reboot_actions=[],commit_or_push=False)
    with a.report.open('x')as f:f.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(audit_passed=True,modes=58,legacy=2,actual_MAC_frames=5,verified_bindings=result['verified_bindings'],native=False)),flush=True)


if __name__=='__main__':main()
