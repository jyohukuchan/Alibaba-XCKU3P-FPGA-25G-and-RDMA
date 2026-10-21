#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual profile6 C consumes untouched32-case native SQ/CQ snapshots.

Keep all14 old operation pairs/four negative mutations, add two actual8193
Immediate pairs; compare every128 posted byte and real C MR/CQ retirement.
Separate Linux/MMIO/pin/DMA boundaries modeled, not live Linux/RTL/physical
page-table coupling or installed/standard-provider hardware execution.
"""
import ast
from pathlib import Path
import probe_kernel_segmented_read_native_cq as base
from segmented_immediate_kernel_models import once

ROOT=base.ROOT
CASES=[*base.CASES,('LARGE_SEND_IMM',5,8193),('LARGE_WRITE_IMM',6,8193)]


def immediate_fixture_source():
    t=base.read_fixture_source()
    for old,new in [('words[28]==63','words[28]==127'),
        ('atomic_access_feature=zero_feature=segmented_read_feature=true;segmented_feature=false;',
         'atomic_access_feature=zero_feature=segmented_immediate_feature=true;segmented_read_feature=false;segmented_feature=false;'),
        ('sq.wqe_profile==5','sq.wqe_profile==6'),('as02_segmented_read_wqe_encode(encoded,','as02_segmented_immediate_wqe_encode(encoded,'),
        ('profile5_CQC63','profile6_CQC127')]:t=once(t,old,new)
    return t


def runner_source():
    t=base.runner_source();a=t.index('"""');b=t.index('"""',a+3)+3;t=t[:a]+'"""'+__doc__+'"""'+t[b:]
    for old,new in [('import segmented_read_kernel_models as model','import segmented_immediate_kernel_models as model'),
        ("len(native.get('tests',{}))!=30","len(native.get('tests',{}))!=32"),
        ("(native.get('RNC_features'),native.get('CQC_features'))!=(16383,63)",
         "(native.get('RNC_features'),native.get('CQC_features'))!=(32767,127)"),
        ("(kernel.get('matched_RNC_features'),kernel.get('matched_CQC_features'),kernel.get('private_segmented_profile'))!=(16383,63,5)",
         "(kernel.get('matched_RNC_features'),kernel.get('matched_CQC_features'),kernel.get('private_segmented_profile'))!=(32767,127,6)"),
        ("prefix='segmented-read-kernel-native-cq-'","prefix='segmented-immediate-kernel-native-cq-'"),
        ('write_text(read_fixture_source())','write_text(immediate_fixture_source())'),
        ("k/'wqe_segmented_read.c',k/'verbs_segmented_read_wqe.c',",
         "k/'wqe_segmented_read.c',k/'verbs_segmented_read_wqe.c',k/'wqe_segmented_immediate.c',k/'verbs_segmented_immediate_wqe.c',"),
        (f'for n in {[n for n,_,_ in base.CASES]!r}for kind',f'for n in {[n for n,_,_ in CASES]!r}for kind'),
        (f'for name,op,length in {base.CASES!r}:',f'for name,op,length in {CASES!r}:'),
        ('RNC_features=16383,CQC_features=63,software_profile=5,','RNC_features=32767,CQC_features=127,software_profile=6,'),
        ("len(report['tests'])!=70","len(report['tests'])!=80"),
        ('all14 genuine snapshot pairs andfour mutations each required','all16 genuine snapshot pairs andfour mutations each required')]:t=once(t,old,new)
    ast.parse(t);return t


if __name__=='__main__':
    exec(compile(runner_source(),str(Path(__file__).resolve()),'exec'),dict(__name__='__main__',__file__=str(Path(__file__).resolve()),
        immediate_fixture_source=immediate_fixture_source))
