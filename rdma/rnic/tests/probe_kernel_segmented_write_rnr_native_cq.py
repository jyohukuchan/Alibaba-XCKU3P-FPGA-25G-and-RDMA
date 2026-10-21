#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Same profile8 C consumes actual native37 RNR/retry CQ, plus all95 old cases.

UNEDITED native whole8193 CQ and genuine zero-capacity C128 RQ; positive and
four malformed-owner variants. Linux/MMIO/pins/DMA primitives remain MODELS.
"""
import ast
from pathlib import Path
import probe_kernel_segmented_write_native_cq as parent
from segmented_write_kernel_models import once

ROOT=parent.ROOT;CASES=[*parent.CASES,('LARGE_RX_WRITE_RNR',40,0)]


def runner_source():
    t=parent.runner_source();a=t.index('"""');b=t.index('"""',a+3)+3;t=t[:a]+'"""'+__doc__+'"""'+t[b:]
    for old,new in [("len(native.get('tests',{}))!=36","len(native.get('tests',{}))!=37"),
        ("prefix='segmented-write-kernel-native-cq-'","prefix='segmented-write-rnr-kernel-native-cq-'"),
        (f'for n in {[n for n,_,_ in parent.CASES]!r}for kind',f'for n in {[n for n,_,_ in CASES]!r}for kind'),
        (f'for name,op,length in {parent.CASES!r}:',f'for name,op,length in {CASES!r}:'),
        ("name in ['LARGE_RX_SEND_IMM','LARGE_RX_WRITE_IMM']","name in ['LARGE_RX_SEND_IMM','LARGE_RX_WRITE_IMM','LARGE_RX_WRITE_RNR']"),
        ("len(report['tests'])!=95","len(report['tests'])!=100"),
        ('all19 genuine snapshot pairs andfour mutations each required','all20 genuine snapshot pairs andfour mutations each required')]:t=once(t,old,new)
    t=once(t,'exact all29 native8191/31 and matched kernel profile4 required',
        'exact native37 profile8 and RNR-matched kernel required')
    t=once(t,"    frozen=ROOT/kernel['directory'];",'''    if not native.get('complete_native_RNR_retry_runtime')or not native.get('all36_prior_cases_retained')or not kernel.get('native_RNR_retry_matched'):
        raise ValueError('actual matched native37 RNR/retry and same kernel source required')
    frozen=ROOT/kernel['directory'];''')
    t=once(t,"    own.extend([TESTS/'kernel_segmented_receive_native_cq.c',TESTS/'kernel_segmented_write_native_cq.c'])",
        "    own.extend([TESTS/'probe_kernel_segmented_write_native_cq.py',TESTS/'kernel_segmented_receive_native_cq.c',TESTS/'kernel_segmented_write_native_cq.c'])")
    ast.parse(t);return t


if __name__=='__main__':
    exec(compile(runner_source(),str(Path(__file__).resolve()),'exec'),dict(__name__='__main__',__file__=str(Path(__file__).resolve()),
        send_fixture_source=parent.send_fixture_source,receive_fixture_source=parent.receive_fixture_source))
