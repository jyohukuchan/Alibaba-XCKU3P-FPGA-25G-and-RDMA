#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Fresh actual large Immediate and ALL30 previous native cases.

True8193 SEND/WRITE Immediate, all bytes/full owner/PSN/MR/PTE/DMA/nonces/
status/real board-MAC/CQ. Physical host/root/peer/PHY/PTP remain models.
Original1200s build/30s runtime/clock/drain/tail/oracle gates remain; no old
binary, hardware/kernel/provider or original timing qualification is reused.
"""
import ast
from pathlib import Path
import tempfile
import probe_segmented_read_command_queue_native_full as parent
import segmented_immediate_native_sources as source

ROOT=source.ROOT;once=source.candidate.once


def runner_source():
    t=parent.runner_source();a=t.index('"""');b=t.index('"""',a+3)+3;t=t[:a]+'"""'+__doc__+'"""'+t[b:]
    for old,new in [('import segmented_read_command_queue_native_sources as source','import segmented_immediate_native_sources as source'),
        ('import segmented_read_command_queue_native_fixture as service','import segmented_immediate_native_fixture as service'),
        ("evidence.get('HLS_top')!='rocev2_native_segmented_read_top'","evidence.get('HLS_top')!='rocev2_native_segmented_immediate_top'"),
        ("!=(16383,63)or not all(evidence.get(n)","!=(32767,127)or not all(evidence.get(n)"),
        ("prefix='segmented-read-command-queue-native-full-'","prefix='segmented-immediate-native-full-'"),
        ("prefix='as02-segmented-read-command-queue-obj-'","prefix='as02-segmented-immediate-native-obj-'"),
        ("prefix='as02-segmented-read-command-queue-artifacts-'","prefix='as02-segmented-immediate-native-artifacts-'"),
        ('RNC_features=16383,CQC_features=63','RNC_features=32767,CQC_features=127'),
        ('planned_cases=30','planned_cases=32'),
        ("'wqe_segmented_read.c','wqe_segmented_read.h']]","'wqe_segmented_read.c','wqe_segmented_read.h','wqe_segmented_immediate.c','wqe_segmented_immediate.h']]")]:t=once(t,old,new)
    t=once(t,"    if evidence['source_sha256'].get(str(source.UNIT.relative_to(ROOT)))!=digest(source.UNIT):\n        raise ValueError('exact qualified effective-route native elaboration required')",
        "    if(evidence.get('Immediate_admission_limit'),evidence.get('receive_buffer_limit'))!=(1048576,4096):raise ValueError('exact Immediate/RQ limits required')\n"
        "    for unit in [source.parent.UNIT,*source.EVIDENCE.values()]:\n"
        "        if evidence['source_sha256'].get(str(unit.relative_to(ROOT)))!=digest(unit):raise ValueError('every exact old/new native component binding required:'+str(unit))\n"
        "    if evidence['module_counts'].get(source.HLS)!=1 or evidence['module_counts'].get('rocev2_native_segmented_read_top')!=0:raise ValueError('one genuine new HLS root required')")
    t=once(t,"        cases=[('LARGE_READ',2,0,['+LARGE_READ'],False,None),",
        "        cases=[('LARGE_SEND_IMM',5,0x89abcdef,['+SEND_IMM','+IMM=89abcdef','+SEGMENTED'],False,None),\n"
        "            ('LARGE_WRITE_IMM',6,0x89abcdef,['+WRITE_IMM','+IMM=89abcdef','+SEGMENTED'],False,None),\n"
        "            ('LARGE_READ',2,0,['+LARGE_READ'],False,None),")
    t=once(t,"if len(cases)!=30:raise ValueError('all29 prior cases plus actual8193 READ required')",
        "if len(cases)!=32:raise ValueError('all30 previous cases plus two actual8193 Immediate cases required')")
    t=once(t,"            is_large=name in ['LARGE_WRITE','LARGE_SEND']",
        "            is_large_immediate=name in ['LARGE_SEND_IMM','LARGE_WRITE_IMM']\n"
        "            is_large=name in ['LARGE_WRITE','LARGE_SEND','LARGE_SEND_IMM','LARGE_WRITE_IMM']")
    t=once(t,'            elif is_large:words,records,request,large_acks=service.large_variant(opcode)',
        '            elif is_large_immediate:words,records,request,large_acks=service.large_immediate_variant(opcode,immediate)\n'
        '            elif is_large:words,records,request,large_acks=service.large_variant(opcode)')
    t=once(t,'                service.verify_large(output,records,request,opcode,run)if is_large else',
        '                service.verify_large_immediate(output,records,request,opcode,run)if is_large_immediate else\n'
        '                service.verify_large(output,records,request,opcode,run)if is_large else')
    t=once(t,"            if name in ['WRITE','SEND']:","            if name in ['WRITE','SEND','SEND_IMM']:")
    t=once(t,'            large_source_runtime_verified=True,large_native_wire_CQ=True)',
        '            large_source_runtime_verified=True,large_native_wire_CQ=True,large_Immediate_native_runtime=True,all30_prior_cases_retained=True)')
    ast.parse(t);return t


if __name__=='__main__':
    run=Path(tempfile.mkdtemp(prefix='segmented-immediate-native-runner-',dir=ROOT/'rdma/rnic/build'))
    frozen=run/'native_runner.py';frozen.write_text(runner_source())
    exec(compile(frozen.read_text(),str(frozen),'exec'),dict(__name__='__main__',__file__=str(frozen)))
