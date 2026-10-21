#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual profile5 kernel C consumes unedited30-case native SQ/CQ snapshots.

Retain all13 old operation pairs/four negative mutations and add actual8193
READ. Compare all128 posted bytes and actual CQ/MR reference retirement.
Separate Linux/MMIO/pin/DMA models, NOT live kernel/RTL or physical proof.
"""
import ast
from pathlib import Path
import probe_kernel_segmented_native_cq as parent
from segmented_read_kernel_models import once

ROOT=Path(__file__).resolve().parents[3]
CASES=[*parent.CASES,('LARGE_READ',2,8193)]


def read_fixture_source():
    t=(ROOT/'rdma/rnic/tests/kernel_segmented_native_cq.c').read_text()
    t=once(t,'words[28]==31','words[28]==63')
    t=once(t,'atomic_access_feature=zero_feature=segmented_feature=true;',
        'atomic_access_feature=zero_feature=segmented_read_feature=true;segmented_feature=false;')
    t=once(t,'sq.wqe_profile==4','sq.wqe_profile==5')
    t=once(t,'as02_segmented_wqe_encode(encoded,','as02_segmented_read_wqe_encode(encoded,')
    t=once(t,'profile4_CQC31','profile5_CQC63')
    return t


def runner_source():
    t=parent.runner_source()
    a=t.index('"""');b=t.index('"""',a+3)+3;t=t[:a]+'"""'+__doc__+'"""'+t[b:]
    t=once(t,'import segmented_kernel_models as model','import segmented_read_kernel_models as model')
    t=once(t,"len(native.get('tests',{}))!=29", "len(native.get('tests',{}))!=30")
    t=once(t,"(native.get('RNC_features'),native.get('CQC_features'))!=(8191,31)",
        "(native.get('RNC_features'),native.get('CQC_features'))!=(16383,63)")
    t=once(t,"(kernel.get('matched_RNC_features'),kernel.get('matched_CQC_features'),kernel.get('private_segmented_profile'))!=(8191,31,4)",
        "(kernel.get('matched_RNC_features'),kernel.get('matched_CQC_features'),kernel.get('private_segmented_profile'))!=(16383,63,5)")
    t=once(t,"prefix='segmented-kernel-native-cq-'","prefix='segmented-read-kernel-native-cq-'")
    t=once(t,"shutil.copy2(TESTS/'kernel_segmented_native_cq.c',m/'kernel_segmented_native_cq.c')",
        "(m/'kernel_segmented_native_cq.c').write_text(read_fixture_source())")
    t=once(t,"k/'wqe_segmented.c',k/'verbs_segmented_wqe.c',",
        "k/'wqe_segmented.c',k/'verbs_segmented_wqe.c',k/'wqe_segmented_read.c',k/'verbs_segmented_read_wqe.c',")
    t=once(t,f'for n in {[n for n,_,_ in parent.CASES]!r}for kind',
        f'for n in {[n for n,_,_ in CASES]!r}for kind')
    t=once(t,f'for name,op,length in {parent.CASES!r}:',f'for name,op,length in {CASES!r}:')
    t=once(t,'RNC_features=8191,CQC_features=31,software_profile=4,',
        'RNC_features=16383,CQC_features=63,software_profile=5,')
    t=once(t,"len(report['tests'])!=65", "len(report['tests'])!=70")
    t=once(t,"all13 genuine snapshot pairs andfour mutations each required",
        "all14 genuine snapshot pairs andfour mutations each required")
    ast.parse(t);return t


def main():
    exec(compile(runner_source(),str(Path(__file__).resolve()),'exec'),
        dict(__name__='__main__',__file__=str(Path(__file__).resolve()),read_fixture_source=read_fixture_source))


if __name__=='__main__':main()
