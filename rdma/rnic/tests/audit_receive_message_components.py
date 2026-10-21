#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Exact message-RQ/real ACK/real CQ component evidence, not full native proof.

Retain failed fixture evidence/preimages and label -i syntax results as
syntax only. Actual new generated HLS, MR/DMA/physical integration and the
original timing gates remain separate mandatory work, never inferred here.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[3];PREFIX=ROOT/'results/2026-10-18'
sys.path.insert(0,str(ROOT/'rdma/rnic/fpga'))
import derive_segmented_receive as graph
SUCCESS=['receive-message-queue-003','receive-message-ack-001','receive-message-cq-001','receive-message-graph-syntax-002']
HISTORICAL={
    'receive-message-queue-001':('rdma/rnic/tests/probe_receive_message_queue.py','rdma/rnic/build/receive-message-queue-001-preimages-EW54l6kg'),
    'receive-message-queue-002':('rdma/rnic/tests/probe_receive_message_queue.py','rdma/rnic/build/receive-message-queue-002-preimages-AUngYnYw'),
    'receive-message-graph-syntax-001':('rdma/rnic/tests/check_receive_message_graph.py','rdma/rnic/build/receive-message-graph-syntax-001-preimages-KmtsTO2P'),
}
def digest(p):
    with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def bindings(name,preimage=None):
    path=PREFIX/('rocev2-rnic-'+name+'.json');r=json.loads(path.read_text());count=0;resolved=[]
    for key,entries in r.items():
        if not isinstance(entries,dict)or'sha256'not in key:continue
        for rel,h in entries.items():
            p=Path(rel);p=p if p.is_absolute()else ROOT/p
            if not p.is_file()or digest(p)!=h:
                if not preimage or key!='source_sha256' or rel!=preimage[0]:raise ValueError('changed recorded source/artifact:'+str(p))
                p=ROOT/preimage[1]/rel
                if digest(p)!=h:raise ValueError('exact preimage missing:'+str(p))
                resolved.append(rel)
            count+=1
    return r,dict(bindings_verified=count,report_sha256=digest(path),exact_preimage_resolutions=resolved)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve earlier evidence')
    good={};old={};rpts={}
    for n in SUCCESS:
        r,v=bindings(n)
        if not r.get('pass_test')or not r.get('source_unchanged'):raise ValueError('actual successful unchanged component required:'+n)
        good[n]=v;rpts[n]=r
    for n,preimage in HISTORICAL.items():
        r,v=bindings(n,preimage)
        if n.endswith('syntax-001'):
            if not r.get('syntax_only')or r.get('full_native_elaboration'):raise ValueError('prior subset syntax must not become whole elaboration')
            v['scope']='Historical default-parameter syntax-only subset; current002 explicitly selects all11 complete-profile flags. Neither includes actual new HLS.'
        elif r.get('pass_test'):raise ValueError('failed fixture cannot be relabeled')
        old[n]=v
    q=rpts[SUCCESS[0]];ack=rpts[SUCCESS[1]];cq=rpts[SUCCESS[2]];syntax=rpts[SUCCESS[3]]
    if q['planned_cases']!=48 or len(q['tests'])!=48 or any(v['exit']!=0 or v['seconds']>10 for v in q['tests'].values()):
        raise ValueError('all48 bounded actual message-RQ cases required')
    if (ack['summary']['ACK_frames'],ack['summary']['fresh_receipts'],ack['summary']['packet_releases'],ack['summary']['posted_owners'])!=(3,3,3,1):
        raise ValueError('actual3 ACK frame/fresh receipt/per-packet release and retained single RQ required')
    if not cq.get('full_CQ_AXI_snapshot')or (cq.get('actual_published_events'),cq.get('actual_host_ACKs'),cq.get('actual_received_bytes'),cq.get('posted_capacity'))!=(1,1,8193,1048576):
        raise ValueError('actual CQ publisher, complete AXI context and host-ACK guard release required')
    if not syntax.get('unknown_leaves_ignored')or syntax.get('full_native_elaboration')or len(syntax.get('explicit_profile_parameters',{}))!=11:
        raise ValueError('syntax-only scope and explicit complete source parameter tuple required')
    protected={'rdma/rnic/rtl/rocev2_protected_responder.v':'d3a2325dd925a9a742d2239295fc4022cdf00078a8d9496d43c72bd879a8287c',
        'rdma/rtl/rocev2_ipv4_icrc.v':'f8cea29d8980e00835694cd0808f849b4eb8bcb0c9326deb7cf505f03a89def3',
        'rdma/rnic/rtl/rocev2_responder_ethernet_rx.v':'76cff3a4284393a2d83c87fb2084ffe8a3eae8b837634943efb030b3a63b18f4'}
    for n,h in protected.items():
        if digest(ROOT/n)!=h:raise ValueError('protected raw source changed:'+n)
    before=graph.parent.derive();after=graph.derive()
    changed=sorted(p.name for p in after if p not in before or after[p]!=before[p])
    check=subprocess.run(['bash','scripts/check.sh'],cwd=ROOT,capture_output=True,text=True,timeout=30)
    result=dict(scope=__doc__,audit_passed=True,overall_goal_complete=False,hardware_verified=False,
        successful=good,historical=old,successful_bindings_verified=sum(v['bindings_verified']for v in good.values()),
        historical_bindings_verified=sum(v['bindings_verified']for v in old.values()),
        message_RQ=dict(cases=48,four_state=True,owner_max_bytes=1048576,per_packet_max_bytes=4096,
            genuine_whole_owner_vs_packet_release=True,full620_owner_retained=True,
            payload_and_HLS_MR_backend_and_MAC_producers_modeled=True),
        actual_RQ_ACK=dict(bytes=8193,posted_capacity=1048576,frames=3,fresh_MAC_receipts=3,packet_releases=3,
            actual_ACK_capture_full_proof_tag_EOF_receipt_1024_tail=True,simulation_seconds=ack['simulation_seconds'],
            whole_CQ_field_in_this_prior_report_means_ticket_only=True),
        actual_RQ_ACK_CQ=dict(bytes=8193,frames=3,fresh_receipts=3,whole_published_events=1,host_ACKs=1,
            full24word_CQ_AXI_snapshot=True,posted_capacity_preserved=1048576,actual_count_not_capacity=True,
            actual_commit_retire_and_RQ_to_CQ_guard_handoff=True,simulation_seconds=cq['simulation_seconds'],
            HLS_MR_DMA_PHY_and_host_boundaries_modeled=True),
        source_graph=dict(cohort_RNC=65535,CQC=255,SQC=13,RQC=31,derived_bodies=len(after),changed_leaves=changed,
            whole776_port_forwarded_no_constant_ready=True,packet_and_whole_retire_fanouts_distinct=True,
            native_fullrange_MR_and_saved_offset_authority=True,syntax_only=True,unknown_leaves_ignored=True,
            actual_generated_HLS_elaboration=False,native_runtime=False,matched_kernel_provider=False),
        protected_raw_sha256=protected,
        auditor_source_sha256={str(Path(__file__).relative_to(ROOT)):digest(__file__)},
        inherited_source_check=dict(exit=check.returncode,stdout=check.stdout,stderr=check.stderr,overall_suite_passed=check.returncode==0),
        remaining=['All11 original requirements retained',
            'Actual new HLS generation still separate; revalidate live job74092, no new native-HLS port/RTL/timing qualification inferred',
            'Actual protected same MR/PTE/backend/physical nonce/status/fence native large RX and all old regressions not executed',
            'New source graph65535/255/13/31 is not installed or matched to new codec/kernel/provider; current native/software profile6 RQ4096 unchanged',
            'Segmented WRITE Immediate remote MR plus late notification RQ, multi-SGE, recovery/loss/RNR/congestion/real peer MSN policy remain',
            'Live Linux/pins/page tables/original full-board timing/CDC/DRC/routing and physical qualification remain',
            'No reboot needed; authenticated exact-thread/goal restoration unproved; restore all archived caches first'],
        hardware_install_load_network_fan_BIOS_flash_reboot_actions=[],commit_or_push=False)
    with a.report.open('x')as f:f.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(audit_passed=True,successful_bindings=result['successful_bindings_verified'],historical_bindings=result['historical_bindings_verified'],
        derived_bodies=len(after),changed_leaves=len(changed),full_native=False)))


if __name__=='__main__':main()
