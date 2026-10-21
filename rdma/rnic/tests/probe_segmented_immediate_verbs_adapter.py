#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Real-header new Immediate WR adapter and ASan/UBSan C with modeled WRs.

Keep every old READ/WRITE/SEND/Atomic/zero assertion. New true base-only
SEND_WITH_IMM storage is ASan guarded, with full64 keys/ranges/Immediate.
No actual post/MR/SQ/DMA/CQ/Linux callbacks, install or hardware qualification.
"""
import ast
from pathlib import Path
import probe_segmented_read_verbs_adapter as base
from segmented_kernel_models import once


def runner_source():
    t=base.runner_source();a=t.index('"""');b=t.index('"""',a+3)+3;t=t[:a]+'"""'+__doc__+'"""'+t[b:]
    t=once(t,"'wqe_segmented_read.c','verbs_segmented_read_wqe.c']",
        "'wqe_segmented_read.c','verbs_segmented_read_wqe.c','wqe_segmented_immediate.c','verbs_segmented_immediate_wqe.c']")
    old="TESTS/'kernel_segmented_read_wqe.c'"
    if t.count(old)!=2:raise ValueError('both input binding and actual compile test required')
    t=t.replace(old,"TESTS/'kernel_segmented_immediate_wqe.c'")
    t=once(t,"TESTS/'kernel_segmented_immediate_wqe.c',TESTS/'kernel_segmented_wqe.c',",
        "TESTS/'kernel_segmented_immediate_wqe.c',TESTS/'kernel_segmented_read_wqe.c',TESTS/'kernel_segmented_wqe.c',")
    t=once(t,"prefix='segmented-read-verbs-adapter-'","prefix='segmented-immediate-verbs-adapter-'")
    t=once(t,"wanted = ['as02_segmented_read_wqe_from_ib_send_wr'",
        "wanted = ['as02_segmented_immediate_wqe_from_ib_send_wr','as02_segmented_immediate_wqe_validate',\n"
        "                  'as02_segmented_immediate_wqe_encode','as02_segmented_immediate_wqe_decode','as02_segmented_read_wqe_from_ib_send_wr'")
    t=once(t,"        headers = run/'include'",
        "        prior_fixture=run/'segmented_read_adapter_prior.c'\n"
        "        prior_text=(TESTS/'kernel_segmented_read_wqe.c').read_text()\n"
        "        if prior_text.count('int main(void)')!=1:raise ValueError('one unchanged prior test entry required')\n"
        "        prior_fixture.write_text(prior_text.replace('int main(void)','int preceding_read_adapter_main(void)'))\n"
        "        before[str(prior_fixture.relative_to(ROOT))]=digest(prior_fixture)\n"
        "        headers = run/'include'")
    t=once(t,'        for name, expected in {**before, **frozen_before}.items():',
        "        imm_rows=[json.loads(line.split(' ',1)[1])for line in c.stdout.splitlines()if line.startswith('SEGMENTED_IMMEDIATE_VERBS_ADAPTER ')]\n"
        "        if imm_rows!=[dict(pass_test=True,large_Immediate_cases=48,other_positive_cases=22,negative_cases=22,\n"
        "                           base_SEND_WITH_IMM_ASan_guarded=True,old_adapters_unchanged=True,actual_posting=False)]:raise ValueError('all actual new Immediate/compatibility/error oracles required')\n"
        "        report['Immediate_summary']=imm_rows[0]\n"
        '        for name, expected in {**before, **frozen_before}.items():')
    t=once(t,'TESTS/"probe_segmented_verbs_adapter.py",',
        'TESTS/"probe_segmented_verbs_adapter.py",TESTS/"probe_segmented_read_verbs_adapter.py",')
    ast.parse(t);return t


if __name__=='__main__':
    exec(compile(runner_source(),str(Path(__file__).resolve()),'exec'),dict(__name__='__main__',__file__=str(Path(__file__).resolve())))
