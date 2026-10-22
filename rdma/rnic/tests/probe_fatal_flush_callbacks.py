#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual paired FEC15/31 flush C callbacks plus all220 unchanged old cases.

Requires new actual full75-input kernel build after real native42 receipts.
Linux/MMIO/IB-core/certificates/pins/DMA/workqueue boundaries are MODELS.
"""
import ast
from pathlib import Path
import tempfile
import probe_fatal_parent_callbacks as parent
from segmented_write_payload_native_fixture import once

ROOT=parent.ROOT


def runner_source():
    t=parent.runner_source();a=t.index('"""');b=t.index('"""',a+3)+3;t=t[:a]+'"""'+__doc__+'"""'+t[b:]
    old="'fatal-parent-kernel-build-001'"
    if t.count(old)!=2:raise ValueError('both exact new full75 build bindings required')
    t=t.replace(old,"'fatal-flush-kernel-build-001'")
    t=once(t,"prefix='fatal-parent-callbacks-'","prefix='fatal-flush-callbacks-'")
    old="    shutil.copy2(TESTS/'kernel_fatal_verbs_cases.c',model/'kernel_fatal_verbs_cases.c')"
    new="""    fatal_cases=(TESTS/'kernel_fatal_verbs_cases.c').read_text()
    fatal_cases=models.once(fatal_cases,'#include "fatal_verbs.h"','#include "fatal_verbs.h"\\nstatic u32 flush_fec_features=AS02_FEC_FEATURE_VALUE;')
    fatal_cases=models.once(fatal_cases,'case AS02_FEC_FEATURES:return AS02_FEC_FEATURE_VALUE;','case AS02_FEC_FEATURES:return flush_fec_features;')
    fatal_cases=models.once(fatal_cases,'int main(int argc,char **argv)','int fatal_legacy_main(int argc,char **argv)')
    (model/'kernel_fatal_verbs_cases.c').write_text(fatal_cases)
    shutil.copy2(TESTS/'kernel_fatal_flush_cases.c',model/'kernel_fatal_flush_cases.c')"""
    t=once(t,old,new)
    t=once(t,"TESTS/'kernel_queue_model.c',model/'kernel_fatal_verbs_cases.c']",
        "TESTS/'kernel_queue_model.c',model/'kernel_fatal_flush_cases.c']")
    t=once(t,"    own=[TESTS/'kernel_fatal_verbs_cases.c',",
        "    own=[TESTS/'kernel_fatal_flush_cases.c',TESTS/'kernel_fatal_verbs_cases.c',")
    t=once(t,'        for name,args,marker in cases:',
        "        old220=cases\n"
        "        cases=[('FLUSH'+str(n),[str(n)],'KERNEL_FATAL_FLUSH_RESULT ')for n in range(16)]+\\\n"
        "            [(name,['prior',*args],marker)for name,args,marker in old220]\n"
        "        if len(cases)!=236:raise ValueError('all16 new flush cases and all220 old callbacks required')\n"
        '        for name,args,marker in cases:')
    t=once(t,'fatal_cases=18,all202_prior_cases_retained=True,',
        'fatal_cases=18,all202_prior_cases_retained=True,per_RQ_flush_cases=16,all220_prior_cases_retained=True,')
    ast.parse(t);return t


if __name__=='__main__':
    run=Path(tempfile.mkdtemp(prefix='fatal-flush-callback-runner-',dir=ROOT/'rdma/rnic/build'))
    frozen=run/'runner.py';frozen.write_text(runner_source())
    exec(compile(frozen.read_text(),str(frozen),'exec'),dict(__name__='__main__',__file__=str(frozen)))
