#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual profile8 WRITE-notice callbacks/refs/RQ/CQ and all170 prior cases.

Require actual matching-native-gated real-header modules. Linux/MMIO/pins/
coherent DMA/hardware CQ are MODELS; ASan/UBSan and original10s/case remain.
"""
import ast
from pathlib import Path
import probe_kernel_segmented_receive_post as parent
import segmented_write_kernel_models as models


def runner_source():
    t=parent.runner_source();once=models.once
    a=t.index('"""');b=t.index('"""',a+3)+3;t=t[:a]+'"""'+__doc__+'"""'+t[b:]
    for old,new in [('import segmented_receive_kernel_models as models','import segmented_write_kernel_models as models'),
        ('(65535,255,7):','(131071,511,8):'),("evidence.get('matched_RQC_features')!=31","evidence.get('matched_RQC_features')!=63"),
        ("prefix='segmented-receive-kernel-post-'","prefix='segmented-write-kernel-post-'")]:t=once(t,old,new)
    t=once(t,"    shutil.copy2(TESTS/'kernel_segmented_receive_post.c',model/'kernel_segmented_receive_post.c')",
        "    previous=(TESTS/'kernel_segmented_receive_post.c').read_text()\n"
        "    previous=models.once(previous,'int main(int argc,char **argv)','int segmented_receive_post_main(int argc,char **argv)')\n"
        "    (model/'kernel_segmented_receive_post.c').write_text(previous)\n"
        "    shutil.copy2(TESTS/'kernel_segmented_write_post.c',model/'kernel_segmented_write_post.c')")
    t=once(t,"TESTS/'kernel_queue_model.c',model/'kernel_segmented_receive_post.c']",
        "TESTS/'kernel_queue_model.c',model/'kernel_segmented_write_post.c']")
    t=once(t,"TESTS/'kernel_segmented_receive_post.c',TESTS/'kernel_segmented_immediate_post.c',",
        "TESTS/'kernel_segmented_write_post.c',TESTS/'kernel_segmented_receive_post.c',TESTS/'kernel_segmented_immediate_post.c',Path(models.parent.__file__).resolve(),")
    t=once(t,'        for name,args,marker in cases:',
        "        cases=[('WRITE_RECV'+str(n),[str(n)],'KERNEL_SEGMENTED_WRITE_POST ')for n in range(32)]+\\\n"
        "            [(name,['prior',*args],marker)for name,args,marker in cases]\n"
        "        if len(cases)!=202:raise ValueError('all32 new WRITE receive and170 exact inherited cases required')\n"
        '        for name,args,marker in cases:')
    t=once(t,'report.update(pass_test=True,source_unchanged=True,RECV_cases=36,',
        'report.update(pass_test=True,source_unchanged=True,WRITE_receive_cases=32,all170_prior_cases_retained=True,RECV_cases=36,')
    t=once(t,'    before={str(p.relative_to(ROOT)):digest(p)for p in dict.fromkeys(own)}',
        '    own.extend(Path(m.__file__).resolve()for m in list(sys.modules.values())if getattr(m,"__file__",None)and\n'
        '        Path(m.__file__).resolve().is_relative_to(ROOT/"rdma/rnic"))\n'
        '    before={str(p.relative_to(ROOT)):digest(p)for p in dict.fromkeys(own)}')
    ast.parse(t);return t


if __name__=='__main__':
    exec(compile(runner_source(),str(Path(__file__).resolve()),'exec'),dict(__name__='__main__',__file__=str(Path(__file__).resolve())))
