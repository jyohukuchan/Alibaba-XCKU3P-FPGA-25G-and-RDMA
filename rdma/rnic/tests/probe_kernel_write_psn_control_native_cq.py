#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Same actual profile8 C consumes native38 PSN-control CQ plus all old100.

UNEDITED whole8193 CQ/genuine zero-SGE C128 RQ; one positive/four corrupt
owner variants. Linux/MMIO/pins/DMA primitive boundaries remain MODELS.
"""
import ast
from pathlib import Path
import probe_kernel_segmented_write_rnr_native_cq as parent
from segmented_write_kernel_models import once

ROOT=parent.ROOT;CASES=[*parent.CASES,('LARGE_RX_WRITE_PSN',40,0)]


def runner_source():
    t=parent.runner_source();a=t.index('"""');b=t.index('"""',a+3)+3;t=t[:a]+'"""'+__doc__+'"""'+t[b:]
    for old,new in [("len(native.get('tests',{}))!=37","len(native.get('tests',{}))!=38"),
        ("prefix='segmented-write-rnr-kernel-native-cq-'","prefix='write-psn-control-kernel-native-cq-'"),
        (f'for n in {[n for n,_,_ in parent.CASES]!r}for kind',f'for n in {[n for n,_,_ in CASES]!r}for kind'),
        (f'for name,op,length in {parent.CASES!r}:',f'for name,op,length in {CASES!r}:'),
        ("name in ['LARGE_RX_SEND_IMM','LARGE_RX_WRITE_IMM','LARGE_RX_WRITE_RNR']",
         "name in ['LARGE_RX_SEND_IMM','LARGE_RX_WRITE_IMM','LARGE_RX_WRITE_RNR','LARGE_RX_WRITE_PSN']"),
        ("len(report['tests'])!=100","len(report['tests'])!=105"),
        ('all20 genuine snapshot pairs andfour mutations each required','all21 genuine snapshot pairs andfour mutations each required'),
        ('exact native37 profile8 and RNR-matched kernel required','exact native38 profile8 and PSN-control-matched kernel required')]:t=once(t,old,new)
    t=once(t,"    frozen=ROOT/kernel['directory'];",'''    if not native.get('complete_native_PSN_control_runtime')or not native.get('all37_prior_cases_retained')or not kernel.get('native_PSN_control_matched'):
        raise ValueError('actual native38 PSN control and exact matched kernel required')
    frozen=ROOT/kernel['directory'];''')
    t=once(t,"    own.extend([TESTS/'probe_kernel_segmented_write_native_cq.py',",
        "    own.extend([TESTS/'probe_kernel_segmented_write_rnr_native_cq.py',TESTS/'probe_kernel_segmented_write_native_cq.py',")
    ast.parse(t);return t


if __name__=='__main__':
    exec(compile(runner_source(),str(Path(__file__).resolve()),'exec'),dict(__name__='__main__',__file__=str(Path(__file__).resolve()),
        send_fixture_source=parent.parent.send_fixture_source,receive_fixture_source=parent.parent.receive_fixture_source))
