#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Fresh complete native8193 WRITE/Immediate plus all34 unchanged old cases.

Actual typed generated HLS/native PSN/MR/PTE/PCIe/nonce/fence/ACK/CQ.
Physical host/root/peer/PHY/PTP only modeled. No old executable/object reuse,
clock/geometry/assertion/deadline waiver, software or physical/timing claim.
"""
import ast
from pathlib import Path
import tempfile
import probe_segmented_receive_continuation_native_full as parent
import segmented_write_native_sources as source
from segmented_receive_payload_native_fixture import once

ROOT=source.ROOT


def runner_source():
    t=parent.runner_source();a=t.index('"""');b=t.index('"""',a+3)+3;t=t[:a]+'"""'+__doc__+'"""'+t[b:]
    t=once(t,'import segmented_receive_continuation_native_sources as source','import segmented_write_native_sources as source')
    t=once(t,'import segmented_receive_payload_native_fixture as service','import segmented_write_payload_native_fixture as service')
    t=once(t,"['hls-build','native-hls-report','owned-hls-report','request-hls-report','elaboration-report','report']",
        "['elaboration-report','report']")
    a=t.index('    previous_path=');b=t.index('    run=Path(tempfile.mkdtemp(',a)
    t=t[:a]+'''    previous_path=source.BASELINE
    evidence,evidence_bindings=source.validate(a.elaboration_report.resolve())
'''+t[b:]
    for old,new in [("prefix='segmented-receive-continuation-native-full-'","prefix='segmented-write-native-full-'"),
        ("prefix='as02-segmented-receive-continuation-obj-'","prefix='as02-segmented-write-native-obj-'"),
        ("prefix='as02-segmented-receive-continuation-artifacts-'","prefix='as02-segmented-write-native-artifacts-'"),
        ('planned_cases=34','planned_cases=36')]:t=once(t,old,new)
    t=once(t,'        src,data,before=source.sources(a.hls_build.resolve(),a.native_hls_report.resolve(),\n            a.owned_hls_report.resolve(),a.request_hls_report.resolve(),run)',
        '        src,data,before=source.sources(a.elaboration_report.resolve(),run)\n'
        '        report.update(native_evidence_bindings=evidence_bindings,native_controller_inserted=True,\n'
        '            incoming_segmented_WRITE_runtime=False,all34_prior_cases_retained=False)')
    t=once(t,"env['TMPDIR']='/dev/shm/as02-native-compiler-tmp-QYQsVyT5'",
        "env['TMPDIR']=tempfile.mkdtemp(prefix='as02-write-native-compiler-tmp-',dir='/dev/shm')")
    t=once(t,"        cases=[('LARGE_RX_SEND',3,0,",
        "        cases=[('LARGE_RX_WRITE',8,0,['+LARGE_WRITE_RX','+LARGE_RX_OP=3'],False,-3),\n"
        "            ('LARGE_RX_WRITE_IMM',9,0x89abcdef,['+LARGE_WRITE_RX','+LARGE_RX_OP=5'],False,-3),\n"
        "            ('LARGE_RX_SEND',3,0,")
    t=once(t,"if len(cases)!=34:raise ValueError('all32 prior plus two actual8193 incoming receive cases required')",
        "if len(cases)!=36:raise ValueError('all34 unchanged prior cases plus actual8193 incoming WRITE/Immediate required')")
    t=once(t,"            is_large_rx=name in ['LARGE_RX_SEND','LARGE_RX_SEND_IMM']",
        "            is_large_write=name in ['LARGE_RX_WRITE','LARGE_RX_WRITE_IMM']\n"
        "            is_large_rx=name in ['LARGE_RX_SEND','LARGE_RX_SEND_IMM']")
    t=once(t,"            if is_large_rx:words,records,rx_records,lrx_words,lrx_frames=service.large_receive_variant(opcode,immediate)",
        "            if is_large_rx:words,records,rx_records,lrx_words,lrx_frames=service.large_receive_variant(opcode,immediate)\n"
        "            if is_large_write:words,records,rx_records,wrx_words,wrx_frames=service.large_write_variant(bool(immediate))")
    t=once(t,"            if is_large_read:inputs['large-read-input.hex']",
        "            if is_large_write:inputs.update({'large-write-receive-input.hex':''.join(f'{w:037x}\\n'for w in wrx_words),\n"
        "                'receive-records.hex':''.join(f'{int.from_bytes(r,\"little\"):0256x}\\n'for r in rx_records)})\n"
        "            if is_large_read:inputs['large-read-input.hex']")
    t=once(t,'            result.update(service.verify_large_receive(output,rx_records,opcode,immediate,run)if is_large_rx else',
        '            result.update(service.verify_large_write(output,rx_records,bool(immediate),run)if is_large_write else\n'
        '                service.verify_large_receive(output,rx_records,opcode,immediate,run)if is_large_rx else')
    t=once(t,'if not is_large and not is_large_read:result[',
        'if not is_large and not is_large_read and not is_large_write:result[')
    t=once(t,'            if is_large_rx:\n                for suffix in',
        "            if is_large_write:\n"
        "                for suffix in ['host',*(['event']if immediate else[])]:shutil.copy2(run/f'large-write-receive-{suffix}.hex',run/(name+'-'+suffix+'.hex'))\n"
        '            if is_large_rx:\n                for suffix in')
    t=once(t,'native_1MiB_receive_runtime=False)',
        'native_1MiB_receive_runtime=False,incoming_segmented_WRITE_runtime=True,all34_prior_cases_retained=True,\n'
        '            native_1MiB_WRITE_runtime=False,new_software_capability_advertised=False)')
    ast.parse(t);return t


if __name__=='__main__':
    run=Path(tempfile.mkdtemp(prefix='segmented-write-native-runner-',dir=ROOT/'rdma/rnic/build'))
    frozen=run/'native_runner.py';frozen.write_text(runner_source())
    exec(compile(frozen.read_text(),str(frozen),'exec'),dict(__name__='__main__',__file__=str(frozen)))
