#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Source-bound checked-frame/MR/RQ/replay evidence, not full native proof.

Retain every original failure and exact preimage. The CRC accelerator uses
unchanged vendor masks/XORs; compare all actual coefficients, not just a
wire sample. Do not compose this component with separate HLS/native tests
and call that live native, payload-DMA, Linux,1MiB or physical completion.
"""
import argparse
import json
from pathlib import Path
import subprocess
import audit_segmented_receive as binding
import probe_segmented_write_rx_frontend as current

ROOT=binding.ROOT;PREFIX=binding.PREFIX;digest=binding.digest
RUNNER='rdma/rnic/tests/probe_segmented_write_rx_frontend.py'


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve all earlier evidence')
    raw,r_id=binding.bindings('segmented-write-rx-front-005')
    masks,m_id=binding.bindings('CRC-constant-masks-001',
        {RUNNER:'rdma/rnic/build/write-rx-front-004-preimages-4xDD69LD'})
    prior,p_id=binding.bindings('remote-write-mr-notice-diagnostics-001')
    original,o_id=binding.bindings('remote-write-mr-notice-004')
    failed={}
    for number,suffix in [(1,'c365f6ZJ'),(2,'w70kc7yr'),(3,'ahuKSiDw'),(4,'4xDD69LD')]:
        name='segmented-write-rx-front-'+str(number).zfill(3)
        r,identity=binding.bindings(name,{RUNNER:'rdma/rnic/build/write-rx-front-'+str(number).zfill(3)+'-preimages-'+suffix})
        if r.get('pass_test')or r.get('hardware_verified'):raise ValueError('failed process/report must remain failed')
        failed[name]=dict(identity=identity,error=r.get('error'),tests_observed=len(r['tests']))
    if not all(r.get('pass_test')for r in [raw,masks,original])or not prior.get('audit_passed'):
        raise ValueError('actual new executions and preserved old component evidence required')
    if set(raw['tests'])!={str(i)for i in current.MODES}or len(raw['tests'])!=47 or \
       (raw['case_limit_seconds'],raw['compile_limit_seconds'],raw['clock_ns'],raw['cycle_limit'])!=(10,10,4,100000):
        raise ValueError('all exact47 cases/original10s/4ns/100000 cycles required')
    if any(t['exit']!=0 or t['seconds']>10 for t in raw['tests'].values()):raise ValueError('actual bounded raw executions required')
    for mode in [0,1,3,4,5,38]:
        t=raw['tests'][str(mode)];s=t['protection'];q=t['replay'];images=current.images(mode)
        authorized=images[:-1]if mode==4 else images
        if not t.get('every_input_byte_mask_EOF_unchanged')or \
           (q['replayed_frames'],q['replayed_bytes'],q['CRC_good'],q['CRC_bad'])!=\
           (len(authorized),sum(map(len,authorized)),len(images),0)or s['completed_messages']!=1:
            raise ValueError('complete unchanged authorized bytes and real integrity/owner lifetime required')
    rnr=raw['tests']['4']['protection'];early=raw['tests']['47']['protection'];bad=raw['tests']['49']
    if (rnr['MR_queries'],rnr['grants'],rnr['completed_packets'],rnr['RQ_taken'])!=(5,3,3,1)or \
       (early['grants'],early['completed_packets'],early['fault'],early['message_active'])!=(1,0,1,1)or \
       (bad['replay']['CRC_bad'],bad['protection']['MR_queries'],bad['replay']['replayed_frames'])!=(1,0,0):
        raise ValueError('RNR no duplicate replay, pre-EOF proof retention and real bad-ICRC rejection required')
    large=raw['tests']['46'];s=large['protection']
    if (s['MR_queries'],s['grants'],s['completed_packets'],s['cancelled_messages'],s['completed_messages'])!=(2,1,1,1,0)or \
       large['replay']['replayed_bytes']!=4156 or raw.get('full_raw_or_native_1MiB_transfer'):
        raise ValueError('1MiB FIRST/cancel case is NOT a1MiB transfer proof')
    exact_masks={str(width)+'-'+str(index)for width in [32,64,96,128]for index in range(32+width)}
    if set(masks['tests'])!=exact_masks or masks['coefficients_compared']!=55296 or \
       masks['case_limit_seconds']!=10 or masks['compile_limit_seconds']!=10 or \
       any(t['exit']!=0 or t['seconds']>10 for t in masks['tests'].values()):
        raise ValueError('all448 complete state/data masks55296 coefficients required')
    cached=current.compiletime_lfsr()
    if (ROOT/raw['directory']/'lfsr_const_masks.v').read_text()!=cached or \
       (ROOT/masks['directory']/'lfsr.v').read_text()!=cached or \
       digest(current.LFSR)!=masks['source_sha256'][str(current.LFSR.relative_to(ROOT))]:
        raise ValueError('same exact proven cache and unchanged vendor source required')
    vendor=current.LFSR.read_text();start=vendor.index('function [LFSR_WIDTH+DATA_WIDTH-1:0] lfsr_mask(')
    end=vendor.index('endfunction',start)+len('endfunction')
    if cached.count(vendor[start:end])!=1:raise ValueError('original reference function must remain byte-identical')
    source=(ROOT/raw['directory']/'tb.v').read_text()
    if 'always @(negedge clk)output_ready=(cycle%7)!=0;'not in source or \
       'if(mode!=49)begin\n  i=0;while(!m_mr_valid'not in source or \
       'task expect_fault;\n begin repeat(5)tick;'not in source:
        raise ValueError('phase-correct stimulus with SAME original five-cycle fault/retention assertion required')
    evidence={}
    for name in [
        'rdma/rnic/build/write-rx-front-001-preimages-c365f6ZJ/read-only-observer.log',
        'rdma/rnic/build/write-rx-front-001-preimages-c365f6ZJ/lint.log',
        'rdma/rnic/build/write-rx-front-003-preimages-ahuKSiDw/read-only-observer.log',
        'rdma/rnic/build/write-rx-front-003-preimages-ahuKSiDw/rdma/rnic/tests/segmented_write_rx_front_observe.v',
        'rdma/rnic/tests/segmented_write_rx_front_observe.v']:
        evidence[name]=digest(ROOT/name)
    zero=(ROOT/list(evidence)[0]).read_text();race=(ROOT/list(evidence)[2]).read_text()
    if '2 time steps'not in zero or 'WRITE_FRONT_OBSERVE time' in zero or \
       'owned1 start0 count260 index1 actual0ffff010b12c688881140004001003c100045'not in race:
        raise ValueError('exact read-only original startup/READY-race observations required')
    for n,h in binding.PROTECTED.items():
        if digest(ROOT/n)!=h:raise ValueError('protected raw source changed:'+n)
    check=subprocess.run(['bash','scripts/check.sh'],cwd=ROOT,capture_output=True,text=True,timeout=30)
    identities=[r_id,m_id,p_id,o_id]
    result=dict(scope=__doc__,audit_passed=True,overall_goal_complete=False,hardware_verified=False,
        raw_frontend=r_id,actual_complete_CRC_masks=m_id,prior_guard_audit=p_id,prior_guard46_and_old_RQ62=o_id,
        failures=failed,verified_bindings=sum(v['bindings_verified']for v in identities)+sum(v['identity']['bindings_verified']for v in failed.values()),
        source_sha256={str(Path(__file__).relative_to(ROOT)):digest(__file__)},diagnostic_artifact_sha256=evidence,
        protected_raw_sha256=binding.PROTECTED,new_raw_modes=47,all_mask_rows=448,all_mask_coefficient_bits=55296,
        maximum_raw_seconds=max(t['seconds']for t in raw['tests'].values()),
        actual_IPv4_ICRC_MR_RQ_registered_owned_replay=True,all_authorized_frame_bytes_masks_EOF_unchanged=True,
        bad_ICRC_no_MR_or_replay=True,same_RNR_frame_PSN_tag_retried_without_duplicate_replay=True,
        downstream_owner_before_replay_and_real_replay_EOF_before_receipt=True,
        CRC_vendor_function_and_output_XORs_unchanged=True,CRC_acceleration_simulation_only=True,
        mask_test_runner_exact_preimage='rdma/rnic/build/write-rx-front-004-preimages-4xDD69LD',
        original_failures=['001 original unmodified LFSR masks spend timeout before clocks; only2 time steps observed.',
            '002 naive per-net compile-time mask evaluation also hits original10s compile guard; no runtime was proved.',
            '003 old posedge counter drives READY combinationally and races register-slice sampling; move only stimulus READY to negedge, same full-byte oracle.',
            '004 old metadata-producer reaction phase is checked before full checker/frame admission. Return raw producer at public MR/reject/fault/owner boundary, retain original five-cycle fault assertion and10s/global cycle gates.'],
        producer_boundaries_modeled=['trusted context and management','posted RQ admission','downstream owner consumer',
            'payload DMA/backend fence','HLS/core/readback/whole receipt','actual ACK-MAC/tail','CQ consumers'],
        full_native_integration=False,generated_new_HLS=False,payload_DMA_executed=False,
        full_raw_or_native_1MiB_transfer=False,live_Linux_RTL_coupling=False,matched_new_software=False,original4ns_timing_met=False,
        inherited_source_check=dict(exit=check.returncode,stdout=check.stdout,stderr=check.stderr,overall_suite_passed=check.returncode==0,original_gate_unchanged=True),
        remaining=['All original11 requirements retained; goal incomplete.',
            'Plug this checked-frame frontend into actual protected shared-native MR/PTE/DMA/HLS/RNR/ACK-MAC/whole-CQ graph; its external proof/owner consumers are not yet actual native producers.',
            'Generate exact new HLS; qualify full1MiB, matched new software, multiSGE/live Linux references and short real-peer recovery/MSN/congestion.',
            'Original4ns/default1.08ns full-board fit/setup/hold/CDC/DRC/routing and short physical proof remain. Latest actual HLS15.571ns FAILS.',
            'No reboot needed; restore all archived RAM caches and prove authenticated exact-thread/active-goal revival before any necessary reboot.'],
        hardware_install_load_network_fan_BIOS_flash_reboot_actions=[],commit_or_push=False)
    with a.report.open('x')as f:f.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(audit_passed=True,raw_modes=47,mask_rows=448,verified_bindings=result['verified_bindings'],full_native_or_physical=False)),flush=True)


if __name__=='__main__':main()
