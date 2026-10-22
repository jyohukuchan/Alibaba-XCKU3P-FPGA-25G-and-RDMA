#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual optional fatal reader/QP callbacks and all202 prior callback cases.

Real full73-input kernel build required. Linux/QP-certificate/MMIO/pins/DMA/
workqueue execution boundaries are MODELS. No live Linux/native coupling.
"""
import ast
from pathlib import Path
import tempfile
import probe_kernel_segmented_write_post as parent
import fatal_verbs_kernel_models as models

ROOT=Path(__file__).resolve().parents[3]


def runner_source():
    t=parent.runner_source();once=models.once
    a=t.index('"""');b=t.index('"""',a+3)+3;t=t[:a]+'"""'+__doc__+'"""'+t[b:]
    t=once(t,'import segmented_write_kernel_models as models','import fatal_verbs_kernel_models as models\nimport audit_segmented_receive as binding')
    start=t.index('    evidence=json.loads(a.kernel_build_report.read_text())');end=t.index('    frozen=ROOT/evidence[\'directory\']',start)
    t=t[:start]+'''    if a.kernel_build_report.resolve()!=binding.record('fatal-verbs-kernel-build-001'):
        raise ValueError('exact actual full optional fatal-hook kernel build required')
    evidence,kernel_id=binding.bindings('fatal-verbs-kernel-build-001')
    if not evidence['pass_test']or not evidence['source_and_derived_inputs_unchanged']or evidence['actual_total_inputs']!=73 or evidence['private_identity']!=[131071,511,13,63,8]:
        raise ValueError('actual complete same73-input profile8 driver build required')
    evidence=dict(evidence,frozen_input_sha256={str(Path(n).relative_to(Path(evidence['directory']))):h for n,h in evidence['derived_sha256'].items()})
'''+t[end:]
    t=once(t,"prefix='segmented-write-kernel-post-'","prefix='fatal-verbs-callbacks-'")
    t=once(t,"    (model/'kernel_atomic128_model.h').write_text(models.MODEL)",
        "    (model/'kernel_verbs_model.h').write_text(models.verbs_header())\n    (model/'kernel_atomic128_model.h').write_text(models.MODEL)")
    t=once(t,"    shutil.copy2(TESTS/'kernel_segmented_write_post.c',model/'kernel_segmented_write_post.c')",
        "    previous=(TESTS/'kernel_segmented_write_post.c').read_text()\n"
        "    previous=models.once(previous,'int main(int argc,char **argv)','int segmented_write_post_main(int argc,char **argv)')\n"
        "    (model/'kernel_segmented_write_post.c').write_text(previous)\n"
        "    shutil.copy2(TESTS/'kernel_fatal_verbs_cases.c',model/'kernel_fatal_verbs_cases.c')")
    t=once(t,"TESTS/'kernel_queue_model.c',model/'kernel_segmented_write_post.c']",
        "private/'fatal_io.c',private/'fatal_verbs.c',TESTS/'kernel_queue_model.c',model/'kernel_fatal_verbs_cases.c']")
    t=once(t,'    own=[Path(__file__).resolve(),',"    own=[TESTS/'kernel_fatal_verbs_cases.c',Path(__file__).resolve(),")
    t=once(t,'        for name,args,marker in cases:',
        "        original_cases=cases\n"
        "        cases=[('FATAL'+str(n),[str(n)],'KERNEL_FATAL_VERBS_RESULT ')for n in range(18)]+\\\n"
        "            [(name,['prior',*args],marker)for name,args,marker in original_cases]\n"
        "        if len(cases)!=220:raise ValueError('all18 new fatal cases and all202 original callbacks required')\n"
        '        for name,args,marker in cases:')
    t=once(t,'timeout=60','timeout=30')
    t=once(t,'report.update(pass_test=True,source_unchanged=True,WRITE_receive_cases=32,',
        'report.update(pass_test=True,source_unchanged=True,fatal_cases=18,all202_prior_cases_retained=True,WRITE_receive_cases=32,')
    ast.parse(t);return t


if __name__=='__main__':
    run=Path(tempfile.mkdtemp(prefix='fatal-verbs-callback-runner-',dir=ROOT/'rdma/rnic/build'))
    frozen=run/'runner.py';frozen.write_text(runner_source())
    exec(compile(frozen.read_text(),str(frozen),'exec'),dict(__name__='__main__',__file__=str(frozen)))
