#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual profile5 SQ/MR/CQ/standard READ callback C, all65 old cases kept.

Real running-header source cohort required. Linux/MMIO/pins/coherent DMA/CQ
hardware completions are models; no actual Linux/RTL/provider/physical run.
ASan/UBSan, original <=10s each; no driver install or load.
"""
import ast
from pathlib import Path
import probe_kernel_segmented_post as parent
import segmented_read_kernel_models as models


def runner_source():
    t=parent.runner_source();once=models.once
    a=t.index('"""');b=t.index('"""',a+3)+3;t=t[:a]+'"""'+__doc__+'"""'+t[b:]
    t=once(t,'import segmented_kernel_models as models','import segmented_read_kernel_models as models')
    t=once(t,"(8191,31,4):","(16383,63,5):")
    t=once(t,"prefix='segmented-kernel-post-'","prefix='segmented-read-kernel-post-'")
    marker="    shutil.copy2(TESTS/'kernel_segmented_post.c',model/'kernel_segmented_post.c')"
    t=once(t,marker,"    large=(TESTS/'kernel_segmented_post.c').read_text()\n"
        "    large=models.once(large,'int main(int argc,char **argv)','int segmented_post_main(int argc,char **argv)')\n"
        "    (model/'kernel_segmented_post.c').write_text(large)\n"
        "    shutil.copy2(TESTS/'kernel_segmented_read_post.c',model/'kernel_segmented_read_post.c')")
    t=once(t,"private/'verbs_segmented_wqe.c',TESTS/'kernel_queue_model.c',model/'kernel_segmented_post.c']",
        "private/'verbs_segmented_wqe.c',private/'wqe_segmented_read.c',private/'verbs_segmented_read_wqe.c',\n"
        "             TESTS/'kernel_queue_model.c',model/'kernel_segmented_read_post.c']")
    t=once(t,"TESTS/'kernel_segmented_post.c',Path(models.old.__file__).resolve(),",
        "TESTS/'kernel_segmented_read_post.c',TESTS/'kernel_segmented_post.c',Path(models.old.__file__).resolve(),\n"
        "        Path(models.old.old.__file__).resolve(),")
    t=once(t,'        for name,args,marker in cases:',
        "        cases=[('READ'+str(n),[str(n)],'KERNEL_SEGMENTED_READ_POST ')for n in range(25)]+\\\n"
        "            [(name,['prior',*args],marker)for name,args,marker in cases]\n"
        "        if len(cases)!=90:raise ValueError('all25 READ and65 inherited cases required')\n"
        '        for name,args,marker in cases:')
    t=once(t,'report.update(pass_test=True,source_unchanged=True,large_cases=18,',
        'report.update(pass_test=True,source_unchanged=True,READ_cases=25,large_cases=18,')
    ast.parse(t);return t


def main():
    exec(compile(runner_source(),str(Path(__file__).resolve()),'exec'),
        dict(__name__='__main__',__file__=str(Path(__file__).resolve())))


if __name__=='__main__':main()
