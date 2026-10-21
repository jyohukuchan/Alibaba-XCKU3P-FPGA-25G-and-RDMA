#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual profile7 RECV callbacks/MR/RQ/CQ C, ALL134 old cases retained.

Exact actual-native-gated real-header cohort is required. Linux/MMIO/pins/
coherent DMA/hardware completions are explicit models, not live Linux/RTL
or physical proof. ASan/UBSan, unchanged <=10s each; no install/load.
"""
import ast
from pathlib import Path
import probe_kernel_segmented_immediate_post as parent
import segmented_receive_kernel_models as models


def runner_source():
    t=parent.runner_source();once=models.once
    a=t.index('"""');b=t.index('"""',a+3)+3;t=t[:a]+'"""'+__doc__+'"""'+t[b:]
    t=once(t,'import segmented_immediate_kernel_models as models','import segmented_receive_kernel_models as models')
    t=once(t,'(32767,127,6):','(65535,255,7):')
    t=once(t,"    frozen=ROOT/evidence['directory']",
        "    if evidence.get('matched_RQC_features')!=31:raise ValueError('exact RQC31 cohort required')\n"
        "    frozen=ROOT/evidence['directory']")
    t=once(t,"prefix='segmented-immediate-kernel-post-'","prefix='segmented-receive-kernel-post-'")
    t=once(t,"    shutil.copy2(TESTS/'kernel_segmented_immediate_post.c',model/'kernel_segmented_immediate_post.c')",
        "    previous=(TESTS/'kernel_segmented_immediate_post.c').read_text()\n"
        "    previous=models.once(previous,'int main(int argc,char **argv)','int segmented_immediate_post_main(int argc,char **argv)')\n"
        "    (model/'kernel_segmented_immediate_post.c').write_text(previous)\n"
        "    shutil.copy2(TESTS/'kernel_segmented_receive_post.c',model/'kernel_segmented_receive_post.c')")
    t=once(t,"private/'verbs_segmented_immediate_wqe.c',\n             TESTS/'kernel_queue_model.c',model/'kernel_segmented_immediate_post.c']",
        "private/'verbs_segmented_immediate_wqe.c',private/'wqe_segmented_receive.c',private/'verbs_segmented_receive_wqe.c',\n"
        "             TESTS/'kernel_queue_model.c',model/'kernel_segmented_receive_post.c']")
    t=once(t,"TESTS/'kernel_segmented_immediate_post.c',TESTS/'kernel_segmented_read_post.c',",
        "TESTS/'kernel_segmented_receive_post.c',TESTS/'kernel_segmented_immediate_post.c',TESTS/'kernel_segmented_read_post.c',Path(models.parent.__file__).resolve(),")
    t=once(t,'        for name,args,marker in cases:',
        "        cases=[('RECV'+str(n),[str(n)],'KERNEL_SEGMENTED_RECEIVE_POST ')for n in range(36)]+\\\n"
        "            [(name,['prior',*args],marker)for name,args,marker in cases]\n"
        "        if len(cases)!=170:raise ValueError('all36 new RECV and134 exact inherited cases required')\n"
        '        for name,args,marker in cases:')
    t=once(t,'report.update(pass_test=True,source_unchanged=True,Immediate_cases=44,',
        'report.update(pass_test=True,source_unchanged=True,RECV_cases=36,all134_prior_cases_retained=True,Immediate_cases=44,')
    ast.parse(t);return t


if __name__=='__main__':
    exec(compile(runner_source(),str(Path(__file__).resolve()),'exec'),dict(__name__='__main__',__file__=str(Path(__file__).resolve())))
