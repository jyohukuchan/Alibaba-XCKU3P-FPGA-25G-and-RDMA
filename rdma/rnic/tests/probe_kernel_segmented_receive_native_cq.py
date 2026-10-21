#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual profile7 C consumes UNEDITED all34-native SQ/RQ/CQ snapshots.

All16 old operation pairs/four mutations retained; add two genuine large RX
pairs. All128 posted bytes, actual8193-vs-capacity8194 and real C CQ/MR
retirement checked. Linux/pins/DMA/MMIO remain MODELS, not live coupling.
"""
import ast
from pathlib import Path
import probe_kernel_segmented_immediate_native_cq as parent
from segmented_receive_kernel_models import once

ROOT=parent.ROOT
CASES=[*parent.CASES,('LARGE_RX_SEND',4,8194),('LARGE_RX_SEND_IMM',4,8194)]


def send_fixture_source():
    t=parent.immediate_fixture_source()
    for old,new in [('words[28]==127','words[28]==255'),
        ('atomic_access_feature=zero_feature=segmented_immediate_feature=true;segmented_read_feature=false;segmented_feature=false;',
         'atomic_access_feature=zero_feature=segmented_receive_feature=true;segmented_immediate_feature=false;segmented_read_feature=false;segmented_feature=false;'),
        ('sq.wqe_profile==6','sq.wqe_profile==7'),('as02_segmented_immediate_wqe_encode(encoded,','as02_segmented_receive_wqe_encode(encoded,'),
        ('profile6_CQC127','profile7_CQC255'),('int main(int argc,char **argv)','int send_native_main(int argc,char **argv)')]:t=once(t,old,new)
    return t


def runner_source():
    t=parent.runner_source();a=t.index('"""');b=t.index('"""',a+3)+3;t=t[:a]+'"""'+__doc__+'"""'+t[b:]
    for old,new in [('import segmented_immediate_kernel_models as model','import segmented_receive_kernel_models as model'),
        ("len(native.get('tests',{}))!=32","len(native.get('tests',{}))!=34"),
        ("(native.get('RNC_features'),native.get('CQC_features'))!=(32767,127)","(native.get('RNC_features'),native.get('CQC_features'))!=(65535,255)"),
        ("(kernel.get('matched_RNC_features'),kernel.get('matched_CQC_features'),kernel.get('private_segmented_profile'))!=(32767,127,6)",
         "(kernel.get('matched_RNC_features'),kernel.get('matched_CQC_features'),kernel.get('private_segmented_profile'))!=(65535,255,7)"),
        ("prefix='segmented-immediate-kernel-native-cq-'","prefix='segmented-receive-kernel-native-cq-'"),
        ("(m/'kernel_segmented_native_cq.c').write_text(immediate_fixture_source())",
         "(m/'kernel_segmented_send_native_cq.c').write_text(send_fixture_source())\n    shutil.copy2(TESTS/'kernel_segmented_receive_native_cq.c',m/'kernel_segmented_native_cq.c')"),
        ("k/'wqe_segmented_immediate.c',k/'verbs_segmented_immediate_wqe.c',",
         "k/'wqe_segmented_immediate.c',k/'verbs_segmented_immediate_wqe.c',k/'wqe_segmented_receive.c',k/'verbs_segmented_receive_wqe.c',"),
        (f'for n in {[n for n,_,_ in parent.CASES]!r}for kind',f'for n in {[n for n,_,_ in CASES]!r}for kind'),
        (f'for name,op,length in {parent.CASES!r}:',f'for name,op,length in {CASES!r}:'),
        ('RNC_features=32767,CQC_features=127,software_profile=6,','RNC_features=65535,CQC_features=255,software_profile=7,'),
        ("len(report['tests'])!=80","len(report['tests'])!=90"),
        ('all16 genuine snapshot pairs andfour mutations each required','all18 genuine snapshot pairs andfour mutations each required')]:t=once(t,old,new)
    # Preserve the real33-word RX snapshot; choose its genuine RQ input file,
    # never a synthetic35-word geometry-expanded event or the unrelated SQ.
    t=once(t,"native_run/(n+'-'+kind+'.hex')",
        "native_run/(n+('-receive-records.hex'if n.startswith('LARGE_RX_')and kind=='records'else'-'+kind+'.hex'))")
    t=once(t,"str(native_run/(name+'-records.hex'))",
        "str(native_run/(name+('-receive-records.hex'if op==4 else'-records.hex')))")
    t=once(t,'str(op),str(length),str(mutation)],',
        "str(op),str(length),str(mutation),str(0x89abcdef if name=='LARGE_RX_SEND_IMM'else 0)],")
    t=once(t,'    before={str(p.relative_to(ROOT)):digest(p)for p in dict.fromkeys(own)}',
        "    own.append(TESTS/'kernel_segmented_receive_native_cq.c')\n"
        '    before={str(p.relative_to(ROOT)):digest(p)for p in dict.fromkeys(own)}')
    ast.parse(t);return t


if __name__=='__main__':
    exec(compile(runner_source(),str(Path(__file__).resolve()),'exec'),dict(__name__='__main__',__file__=str(Path(__file__).resolve()),
        send_fixture_source=send_fixture_source))
