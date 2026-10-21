#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual matched large SQ/MR/CQ/standard callback C, not Linux execution.

Require real running-header cohort build; explicit primitive/MMIO/pin/DMA/
completion models, ASan/UBSan <=10s each. Retain all47 original cases.
"""
import ast
from pathlib import Path
import probe_kernel_zero_post as parent
import segmented_kernel_models as models


def runner_source():
    t=Path(parent.__file__).read_text();once=models.once
    start=t.index('"""');end=t.index('"""',start+3)+3;t=t[:start]+'"""'+__doc__+'"""'+t[end:]
    t=once(t,'import zero_kernel_models as models','import segmented_kernel_models as models')
    t=once(t,"prefix='zero-kernel-post-'","prefix='segmented-kernel-post-'")
    t=once(t,"    frozen=ROOT/evidence['directory']",
        "    if(evidence.get('matched_RNC_features'),evidence.get('matched_CQC_features'),evidence.get('private_segmented_profile'))!=(8191,31,4):\n"
        "        raise ValueError('exact large kernel cohort build required')\n"
        "    frozen=ROOT/evidence['directory']")
    t=once(t,"    shutil.copy2(TESTS/'kernel_zero_post.c',model/'kernel_zero_post.c')",
        "    zero=(TESTS/'kernel_zero_post.c').read_text()\n"
        "    zero=models.once(zero,'int main(int argc,char **argv)','int zero_post_main(int argc,char **argv)')\n"
        "    (model/'kernel_zero_post.c').write_text(zero)\n"
        "    shutil.copy2(TESTS/'kernel_segmented_post.c',model/'kernel_segmented_post.c')")
    t=once(t,"private/'verbs_zero_wqe.c',TESTS/'kernel_queue_model.c',model/'kernel_zero_post.c']",
        "private/'verbs_zero_wqe.c',private/'wqe_segmented.c',private/'verbs_segmented_wqe.c',TESTS/'kernel_queue_model.c',model/'kernel_segmented_post.c']")
    t=once(t,"        *src,*private.glob('*.h'),*model.glob('*')]",
        "        TESTS/'kernel_segmented_post.c',Path(models.old.__file__).resolve(),*src,*private.glob('*.h'),*model.glob('*')]")
    t=once(t,'        for name,args,marker in cases:',
        "        cases=[('Large'+str(n),[str(n)],'KERNEL_SEGMENTED_POST ')for n in range(18)]+\\\n"
        "            [(name,['prior',*args],marker)for name,args,marker in cases]\n"
        "        if len(cases)!=65:raise ValueError('all18 large and47 inherited cases required')\n"
        '        for name,args,marker in cases:')
    t=once(t,'report.update(pass_test=True,source_unchanged=True,zero_cases=10,',
        'report.update(pass_test=True,source_unchanged=True,large_cases=18,zero_cases=10,')
    ast.parse(t);return t


def main():
    exec(compile(runner_source(),str(Path(__file__).resolve()),'exec'),
         dict(__name__='__main__',__file__=str(Path(__file__).resolve())))


if __name__=='__main__':main()
