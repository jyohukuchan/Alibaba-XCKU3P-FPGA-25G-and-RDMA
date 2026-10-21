#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Audit exact new receive sources, real executions and immutable failures.

Full HLS generation/consumer proof is not native/RQ/MR/DMA/MAC/CQ/Linux/
physical/original timing qualification. Historical mismatches resolve only
to named exact preimages, never a changed assertion or rewritten report.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT=Path(__file__).resolve().parents[3];PREFIX=ROOT/'results/2026-10-18'
SUCCESS=['segmented-receive-hls-004','segmented-receive-compat-001',
    'receive-message-join-003','segmented-receive-generated-hls-001']
GEN='rdma/rnic/hls/segmented_receive_transport.py';BENCH='rdma/rnic/hls/test_segmented_receive.cpp'
UNIT='rdma/rnic/hls/test_receive_message_join.cpp'
BUILD='rdma/rnic/build/'
HISTORICAL={
    'segmented-receive-source-startup-001':{GEN:BUILD+'segmented-receive-source-startup-001-preimages-mDAzntQS'},
    'segmented-receive-source-startup-002':{GEN:BUILD+'segmented-receive-source-startup-002-preimages-Ji3q58M3'},
    'segmented-receive-hls-001':{GEN:BUILD+'segmented-receive-hls-001-preimages-h1cqzflB',BENCH:BUILD+'segmented-receive-hls-001-preimages-h1cqzflB'},
    'segmented-receive-hls-002':{GEN:BUILD+'segmented-receive-hls-002-preimages-441H6GAi',BENCH:BUILD+'segmented-receive-hls-003-preimages-Nv49LmFc'},
    'segmented-receive-hls-003':{GEN:BUILD+'segmented-receive-hls-003-preimages-Nv49LmFc',BENCH:BUILD+'segmented-receive-hls-003-preimages-Nv49LmFc'},
    'receive-message-join-001':{UNIT:BUILD+'receive-message-join-001-preimages-4xsmX9sz'},
    'receive-message-join-002':{UNIT:BUILD+'receive-message-join-002-preimages-dzp8pnIC'},
}
PROTECTED={
    'rdma/rnic/rtl/rocev2_protected_responder.v':'d3a2325dd925a9a742d2239295fc4022cdf00078a8d9496d43c72bd879a8287c',
    'rdma/rtl/rocev2_ipv4_icrc.v':'f8cea29d8980e00835694cd0808f849b4eb8bcb0c9326deb7cf505f03a89def3',
    'rdma/rnic/rtl/rocev2_responder_ethernet_rx.v':'76cff3a4284393a2d83c87fb2084ffe8a3eae8b837634943efb030b3a63b18f4',
}
def digest(p):
    with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def record(name):return PREFIX/('rocev2-rnic-'+name+'.json')
def bindings(name,fallback=None):
    p=record(name);r=json.loads(p.read_text());count=0;resolved=[]
    for key,entries in r.items():
        if not isinstance(entries,dict) or 'sha256' not in key:continue
        for rel,h in entries.items():
            if not isinstance(h,str)or not re.fullmatch('[0-9a-f]{64}',h):raise ValueError('malformed binding:'+key)
            item=Path(rel)
            if key=='frozen_sha256':item=ROOT/r['directory']/'inputs'/item
            elif key=='generated_sha256':item=ROOT/r['directory']/'project/solution1/syn/verilog'/item
            elif not item.is_absolute():item=ROOT/item
            if not item.is_file() or digest(item)!=h:
                if key!='source_sha256' or not fallback or rel not in fallback:raise ValueError('changed binding:'+str(item))
                item=ROOT/fallback[rel]/rel
                if not item.is_file()or digest(item)!=h:raise ValueError('missing exact preimage:'+str(item))
                resolved.append(rel)
            count+=1
    for path_key,hash_key in [('parent_builder_report','parent_builder_report_sha256'),
        ('checked_request_report_view','checked_request_report_view_sha256'),('raw_runner_report','raw_runner_report_sha256')]:
        if path_key in r:
            if digest(ROOT/r[path_key])!=r[hash_key]:raise ValueError('changed nested record:'+r[path_key])
            count+=1
    return r,dict(bindings_verified=count,report_sha256=digest(p),exact_preimage_resolutions=resolved)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve prior evidence')
    good={};old={};reports={}
    for name in SUCCESS:
        r,v=bindings(name)
        if not r.get('pass_test'):raise ValueError('actual successful execution required:'+name)
        good[name]=v;reports[name]=r
    for name,fallback in HISTORICAL.items():
        r,v=bindings(name,fallback)
        if r.get('pass_test'):raise ValueError('failure must not be relabeled:'+name)
        old[name]=v
    for n,h in PROTECTED.items():
        if digest(ROOT/n)!=h:raise ValueError('protected raw file changed:'+n)
    runtime=reports[SUCCESS[0]];tests=runtime['tests'];hls=reports[SUCCESS[-1]]
    if len(tests)!=44 or any(t['exit']!=0 or t['seconds']>30 for t in tests.values()) or runtime['runtime_limit_seconds']!=30:
        raise ValueError('all44 actual cases within original30s gates required')
    if not all(runtime.get(n)for n in ['source_unchanged','full_top_CPP_compiled','all21_prior_modes_retained']):
        raise ValueError('same complete old/new source required')
    if not hls.get('whole_receive_port776_verified')or (float(hls['target_clock_period']),float(hls['clock_uncertainty']),hls['MAX_QPS'],hls['metadata_entries'])!=(4,1.08,8,2000):
        raise ValueError('original HLS clock/uncertainty/8QP/metadata and actual new whole-message port required')
    top=ROOT/hls['directory']/'project/solution1/syn/verilog/rocev2_native_segmented_receive_top.v'
    if not re.search(r'\[\s*775\s*:\s*0\s*\]\s*m_axis_recv_message_TDATA\s*;',top.read_text()):
        raise ValueError('actual distinct whole-receive output missing')
    check=subprocess.run(['bash','scripts/check.sh'],cwd=ROOT,capture_output=True,text=True,timeout=30)
    result=dict(scope=__doc__,audit_passed=True,overall_goal_complete=False,hardware_verified=False,
        successful=good,historical=old,successful_bindings_verified=sum(v['bindings_verified']for v in good.values()),
        historical_bindings_verified=sum(v['bindings_verified']for v in old.values()),protected_raw_sha256=PROTECTED,
        inherited_source_check=dict(command=['bash','scripts/check.sh'],exit=check.returncode,
            stdout=check.stdout,stderr=check.stderr,overall_suite_passed=check.returncode==0,
            verifier_sha256=digest(ROOT/'scripts/check.sh'),original_gate_unchanged=True),
        whole_receive=dict(source_max_bytes=1048576,actual_HLS_CPP_messages_per_opcode=6,actual_HLS_CPP_packets_per_opcode=284,
            opcodes=['SEND','SEND_WITH_IMMEDIATE'],all44_modes=True,all21_prior_modes_retained=True,
            new_RX_seconds=[tests[n]['seconds']for n in ['rx-send','rx-imm']],
            full620_RQ_identity=True,packet_receipt_bits=752,whole_receipt_bits=772,whole_AXIS_bits=776,
            actual_cumulative_bytes_not_posted_capacity=True,actual_EOF_ACK_MSN_SAME_PSN_required=True,
            MSN_advances_only_LAST=True,packet_padding_preserved_through_both_actual_RX_forwarders=True,
            separate_actual_ACK_MSN_oracles=True,nonzero_corrupt_pad_no_receipt=True,
            packet_RQ_connection_memory_endpoints_modeled=True),
        group_consumer=dict(actual_unit_cases=18,two_interleaved_QPs=True,PSN_and_MSN_wrap=True,
            actual_HLS_helper=True,packet_certificate_producer_modeled=True),
        generated_HLS=dict(pass_test=True,seconds=hls['elapsed_seconds'],resources=hls['resources'],
            estimated_period_ns=float(hls['estimated_clock_period']),target_ns=4,uncertainty_ns=1.08,
            original_effective_period_met=hls['original_effective_period_met'],native_integration=False),
        reference=dict(source='https://raw.githubusercontent.com/torvalds/linux/v6.17/drivers/infiniband/sw/rxe/rxe_resp.c',
            use='Primary behavioral cross-check: execute increments SEND/WRITE MSN at RXE_END_MASK; SEND CQ bytes are actual consumed bytes. No source copied.'),
        remaining=['Full original11 requirements retained, not a reduced completion claim',
            'Actual same-core protected native large RX MR/PTE/DMA/nonces/status/fences, per-packet ACK-MAC release and one whole CQ/retire not wired or run',
            'Current native/software profile6 still limits incoming RQ to4096; no new RNC/CQC or kernel/provider capability advertisement',
            'Segmented WRITE_WITH_IMM remote MR and late notification RQ must remain distinct; not implemented by this SEND path',
            'Real peer interoperability, nonterminal ACK-MSN policy and duplicate/loss/retry/RNR/congestion remain unqualified',
            'Multi-SGE, live Linux/device/pins/page tables, original full-board timing/CDC/DRC/routing and physical work remain',
            'Authentic exact thread/goal reboot restoration unproved; no reboot needed; restore archived caches before any reboot'],
        safety=dict(programmed=False,installed=False,loaded=False,network_or_BIOS_or_fan_changes=False,
            reboot=False,commit_or_push=False,IB_ATOMIC_NONE_unchanged=True),
        auditor_sha256={str(Path(__file__).relative_to(ROOT)):digest(__file__)})
    with a.report.open('x')as f:f.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(audit_passed=True,successful_bindings=result['successful_bindings_verified'],
        historical_bindings=result['historical_bindings_verified'],original_timing_met=result['generated_HLS']['original_effective_period_met'])))


if __name__=='__main__':main()
