#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual profile6 standard Immediate callbacks/refs/SQ/CQ and all90 old cases.

Require the exact real-header source cohort. Linux/MMIO/pins/coherent DMA/
hardware CQ completions remain models, not live Linux/RTL/physical proof.
ASan/UBSan and original <=10s cases retained, nothing installed or loaded.
"""
import ast
from pathlib import Path
import probe_kernel_segmented_read_post as base
import segmented_immediate_kernel_models as models


def runner_source():
    t=base.runner_source();once=models.once
    a=t.index('"""');b=t.index('"""',a+3)+3;t=t[:a]+'"""'+__doc__+'"""'+t[b:]
    t=once(t,'import segmented_read_kernel_models as models','import segmented_immediate_kernel_models as models')
    t=once(t,'(16383,63,5):','(32767,127,6):')
    t=once(t,"prefix='segmented-read-kernel-post-'","prefix='segmented-immediate-kernel-post-'")
    t=once(t,"    shutil.copy2(TESTS/'kernel_segmented_read_post.c',model/'kernel_segmented_read_post.c')",
        "    previous=(TESTS/'kernel_segmented_read_post.c').read_text()\n"
        "    previous=models.once(previous,'int main(int argc,char **argv)','int segmented_read_post_main(int argc,char **argv)')\n"
        "    (model/'kernel_segmented_read_post.c').write_text(previous)\n"
        "    shutil.copy2(TESTS/'kernel_segmented_immediate_post.c',model/'kernel_segmented_immediate_post.c')")
    t=once(t,"private/'verbs_segmented_read_wqe.c',\n             TESTS/'kernel_queue_model.c',model/'kernel_segmented_read_post.c']",
        "private/'verbs_segmented_read_wqe.c',private/'wqe_segmented_immediate.c',private/'verbs_segmented_immediate_wqe.c',\n"
        "             TESTS/'kernel_queue_model.c',model/'kernel_segmented_immediate_post.c']")
    t=once(t,"TESTS/'kernel_segmented_read_post.c',TESTS/'kernel_segmented_post.c',",
        "TESTS/'kernel_segmented_immediate_post.c',TESTS/'kernel_segmented_read_post.c',TESTS/'kernel_segmented_post.c',")
    t=once(t,'Path(models.old.__file__).resolve(),','Path(models.base.__file__).resolve(),')
    t=once(t,'Path(models.old.old.__file__).resolve(),',
        'Path(models.base.old.__file__).resolve(),Path(models.base.old.old.__file__).resolve(),')
    t=once(t,'        for name,args,marker in cases:',
        "        cases=[('IMMEDIATE'+str(n),[str(n)],'KERNEL_SEGMENTED_IMMEDIATE_POST ')for n in range(44)]+\\\n"
        "            [(name,['prior',*args],marker)for name,args,marker in cases]\n"
        "        if len(cases)!=134:raise ValueError('all44 new Immediate and90 inherited cases required')\n"
        '        for name,args,marker in cases:')
    t=once(t,'report.update(pass_test=True,source_unchanged=True,READ_cases=25,',
        'report.update(pass_test=True,source_unchanged=True,Immediate_cases=44,READ_cases=25,')
    ast.parse(t);return t


if __name__=='__main__':
    exec(compile(runner_source(),str(Path(__file__).resolve()),'exec'),dict(__name__='__main__',__file__=str(Path(__file__).resolve())))
