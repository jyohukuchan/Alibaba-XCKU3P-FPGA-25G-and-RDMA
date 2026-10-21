#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Profile8 C consumes UNEDITED actual new36-native SQ/RQ/CQ snapshots.

Retain all18 old snapshot pairs/four mutations; add the genuine8193 WRITE
notice/zero-RQ pair. Native source is real RTL; Linux/pins/MMIO/DMA remain
primitive models, NOT live Linux/native memory/ref coupling or physical proof.
"""
import ast
from pathlib import Path
import probe_kernel_segmented_receive_native_cq as parent
from segmented_write_kernel_models import once

ROOT=parent.ROOT
CASES=[*parent.CASES,('LARGE_RX_WRITE_IMM',40,0)]


def send_fixture_source():
    t=parent.send_fixture_source()
    for old,new in [('words[28]==255','words[28]==511'),
        ('atomic_access_feature=zero_feature=segmented_receive_feature=true;segmented_immediate_feature=false;',
         'atomic_access_feature=zero_feature=segmented_write_feature=true;segmented_receive_feature=false;segmented_immediate_feature=false;'),
        ('sq.wqe_profile==7','sq.wqe_profile==8'),('profile7_CQC255','profile8_CQC511')]:t=once(t,old,new)
    return t


def receive_fixture_source():
    t=(ROOT/'rdma/rnic/tests/kernel_segmented_receive_native_cq.c').read_text()
    for old,new in [('words[28]==255','words[28]==511'),
        ('atomic_access_feature=zero_feature=segmented_receive_feature=true;',
         'atomic_access_feature=zero_feature=segmented_write_feature=true;segmented_receive_feature=false;'),
        ('sq.wqe_profile==7','sq.wqe_profile==8'),('profile7_CQC255','profile8_CQC511'),
        ('int main(int argc,char **argv)','int receive_native_main(int argc,char **argv)')]:t=once(t,old,new)
    return t


def runner_source():
    t=parent.runner_source();a=t.index('"""');b=t.index('"""',a+3)+3;t=t[:a]+'"""'+__doc__+'"""'+t[b:]
    for old,new in [('import segmented_receive_kernel_models as model','import segmented_write_kernel_models as model'),
        ("len(native.get('tests',{}))!=34","len(native.get('tests',{}))!=36"),
        ("(native.get('RNC_features'),native.get('CQC_features'))!=(65535,255)","(native.get('RNC_features'),native.get('CQC_features'))!=(131071,511)"),
        ("(kernel.get('matched_RNC_features'),kernel.get('matched_CQC_features'),kernel.get('private_segmented_profile'))!=(65535,255,7)",
         "(kernel.get('matched_RNC_features'),kernel.get('matched_CQC_features'),kernel.get('private_segmented_profile'))!=(131071,511,8)"),
        ("prefix='segmented-receive-kernel-native-cq-'","prefix='segmented-write-kernel-native-cq-'"),
        ("shutil.copy2(TESTS/'kernel_segmented_receive_native_cq.c',m/'kernel_segmented_native_cq.c')",
         "(m/'kernel_segmented_receive_native_cq.c').write_text(receive_fixture_source())\n    shutil.copy2(TESTS/'kernel_segmented_write_native_cq.c',m/'kernel_segmented_native_cq.c')"),
        (f'for n in {[n for n,_,_ in parent.CASES]!r}for kind',f'for n in {[n for n,_,_ in CASES]!r}for kind'),
        (f'for name,op,length in {parent.CASES!r}:',f'for name,op,length in {CASES!r}:'),
        ("'-receive-records.hex'if op==4", "'-receive-records.hex'if op in [4,40]"),
        ("0x89abcdef if name=='LARGE_RX_SEND_IMM'else 0","0x89abcdef if name in ['LARGE_RX_SEND_IMM','LARGE_RX_WRITE_IMM']else 0"),
        ('RNC_features=65535,CQC_features=255,software_profile=7,','RNC_features=131071,CQC_features=511,software_profile=8,'),
        ("len(report['tests'])!=90","len(report['tests'])!=95"),
        ('all18 genuine snapshot pairs andfour mutations each required','all19 genuine snapshot pairs andfour mutations each required')]:t=once(t,old,new)
    t=once(t,"    own.append(TESTS/'kernel_segmented_receive_native_cq.c')",
        "    own.extend([TESTS/'kernel_segmented_receive_native_cq.c',TESTS/'kernel_segmented_write_native_cq.c'])")
    ast.parse(t);return t


if __name__=='__main__':
    exec(compile(runner_source(),str(Path(__file__).resolve()),'exec'),dict(__name__='__main__',__file__=str(Path(__file__).resolve()),
        send_fixture_source=send_fixture_source,receive_fixture_source=receive_fixture_source))
