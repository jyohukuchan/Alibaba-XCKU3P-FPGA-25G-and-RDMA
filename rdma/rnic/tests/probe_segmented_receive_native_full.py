#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Fresh native8193 SEND/Immediate receive plus ALL32 unchanged old cases.

One real8194-byte coherent RQ owner, three actual MR/PTE/DMA/nonce/status/
fence/HLS/ACK-MAC packet lives and one whole CQ/host ACK. All bytes/padding/
sentinels/wire/owner/MSN/capacity-vs-actual-count oracles are independent.
Physical host/root/peer/PHY/PTP remain models; no1MiB/native Linux/board/
original-clock timing proof. Original1200s build/30s cases and all old gates
remain. No previous binary or compile-object cache is reused.
"""
import ast
from pathlib import Path
import tempfile
import probe_segmented_receive_native_compat as parent
import segmented_receive_native_sources as source

ROOT=source.ROOT;once=source.candidate.once


def runner_source():
    t=parent.runner_source();a=t.index('"""');b=t.index('"""',a+3)+3;t=t[:a]+'"""'+__doc__+'"""'+t[b:]
    for old,new in [
        ('import segmented_receive_native_fixture as service','import segmented_receive_payload_native_fixture as service'),
        ("prefix='segmented-receive-native-compat-'","prefix='segmented-receive-native-full-'"),
        ("prefix='as02-segmented-receive-native-obj-'","prefix='as02-segmented-receive-native-full-obj-'"),
        ("prefix='as02-segmented-receive-native-artifacts-'","prefix='as02-segmented-receive-native-full-artifacts-'"),
        ('new_receive_hierarchy_old32_regressions_only=True','new_receive_hierarchy_old32_regressions_only=False'),
        ('planned_cases=32','planned_cases=34')]:t=once(t,old,new)
    t=once(t,'    evidence=json.loads(a.elaboration_report.read_text())',r'''
    previous_path=ROOT/'results/2026-10-18/rocev2-rnic-segmented-receive-native-compat-001.json'
    previous=json.loads(previous_path.read_text())
    if not previous.get('pass_test')or not previous.get('source_unchanged')or len(previous['tests'])!=32 or any(v['exit']!=0 or v['seconds']>30 for v in previous['tests'].values()):
        raise ValueError('exact successful all32 previous NEW-core native regressions required')
    source.parent.verify_nested(previous)
    evidence=json.loads(a.elaboration_report.read_text())''')
    t=once(t,'        cases=[(\'LARGE_SEND_IMM\',5,',
        "        cases=[('LARGE_RX_SEND',3,0,['+LARGE_RX','+LARGE_RX_OP=3'],False,-2),\n"
        "            ('LARGE_RX_SEND_IMM',5,0x89abcdef,['+LARGE_RX','+LARGE_RX_OP=5'],False,-2),\n"
        "            ('LARGE_SEND_IMM',5,")
    t=once(t,"if len(cases)!=32:raise ValueError('all30 previous cases plus two actual8193 Immediate cases required')",
        "if len(cases)!=34:raise ValueError('all32 prior plus two actual8193 incoming receive cases required')")
    t=once(t,"            is_large_read=name=='LARGE_READ'",
        "            is_large_rx=name in ['LARGE_RX_SEND','LARGE_RX_SEND_IMM']\n"
        "            is_large_read=name=='LARGE_READ'")
    t=once(t,"            inputs={'input.hex':",
        "            if is_large_rx:words,records,rx_records,lrx_words,lrx_frames=service.large_receive_variant(opcode,immediate)\n"
        "            inputs={'input.hex':")
    t=once(t,"            if is_large_read:inputs['large-read-input.hex']",
        "            if is_large_rx:inputs.update({'large-receive-input.hex':''.join(f'{w:037x}\\n'for w in lrx_words),\n"
        "                'receive-records.hex':''.join(f'{int.from_bytes(r,\"little\"):0256x}\\n'for r in rx_records)})\n"
        "            if is_large_read:inputs['large-read-input.hex']")
    t=once(t,'            result.update(service.verify_large_read(output,records,request,run)if is_large_read else',
        '            result.update(service.verify_large_receive(output,rx_records,opcode,immediate,run)if is_large_rx else\n'
        '                service.verify_large_read(output,records,request,run)if is_large_read else')
    t=once(t,"            if capacity is not None and capacity>=0:\n                for seq in [1,2]:",
        "            if is_large_rx:\n"
        "                for suffix in ['event','host']:shutil.copy2(run/f'large-receive-{suffix}.hex',run/(name+'-'+suffix+'.hex'))\n"
        "            if capacity is not None and capacity>=0:\n                for seq in [1,2]:")
    t=once(t,'large_Immediate_native_runtime=True,all30_prior_cases_retained=True)',
        'large_Immediate_native_runtime=True,all30_prior_cases_retained=True,all32_prior_cases_retained=True,\n'
        '            incoming_segmented_SEND_Immediate_runtime=True,new_receive_bytes=8193,new_posted_capacity=8194,native_1MiB_receive_runtime=False)')
    t=once(t,'        before.update({str(p.relative_to(ROOT)):digest(p)for p in own})',
        '        own.append(previous_path)\n        before.update({str(p.relative_to(ROOT)):digest(p)for p in own})')
    ast.parse(t);return t


if __name__=='__main__':
    run=Path(tempfile.mkdtemp(prefix='segmented-receive-payload-native-runner-',dir=ROOT/'rdma/rnic/build'))
    frozen=run/'native_runner.py';frozen.write_text(runner_source())
    exec(compile(frozen.read_text(),str(frozen),'exec'),dict(__name__='__main__',__file__=str(frozen)))
