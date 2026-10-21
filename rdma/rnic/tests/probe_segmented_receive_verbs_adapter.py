#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Real-header standard RECV adapter plus actual ASan/UBSan codec execution.

Retain every old WRITE/READ/SEND/Atomic/zero/Immediate adapter assertion,
including base-only SEND allocations. New RECV allocation is also base-only.
No actual post_recv/MR/ref/DMA/CQ/kernel callback, installation or API claim.
"""
import ast
from pathlib import Path
import probe_segmented_immediate_verbs_adapter as base
from segmented_kernel_models import once


def runner_source():
    t=base.runner_source();a=t.index('"""');b=t.index('"""',a+3)+3;t=t[:a]+'"""'+__doc__+'"""'+t[b:]
    t=once(t,"'wqe_segmented_immediate.c','verbs_segmented_immediate_wqe.c']",
        "'wqe_segmented_immediate.c','verbs_segmented_immediate_wqe.c','wqe_segmented_receive.c','verbs_segmented_receive_wqe.c']")
    old="TESTS/'kernel_segmented_immediate_wqe.c'"
    if t.count(old)!=2:raise ValueError('both input binding and actual new test compilation required')
    t=t.replace(old,"TESTS/'kernel_segmented_receive_wqe.c'")
    t=once(t,"TESTS/'kernel_segmented_receive_wqe.c',TESTS/'kernel_segmented_read_wqe.c',",
        "TESTS/'kernel_segmented_receive_wqe.c',TESTS/'kernel_segmented_immediate_wqe.c',TESTS/'kernel_segmented_read_wqe.c',")
    t=once(t,"prefix='segmented-immediate-verbs-adapter-'","prefix='segmented-receive-verbs-adapter-'")
    t=once(t,"wanted = ['as02_segmented_immediate_wqe_from_ib_send_wr'",
        "wanted = ['as02_segmented_receive_wqe_from_ib_recv_wr','as02_segmented_receive_wqe_validate',\n"
        "                  'as02_segmented_receive_wqe_encode','as02_segmented_receive_wqe_decode','as02_segmented_immediate_wqe_from_ib_send_wr'")
    t=once(t,"        headers = run/'include'",
        "        receive_prior=run/'segmented_immediate_adapter_prior.c'\n"
        "        receive_text=(TESTS/'kernel_segmented_immediate_wqe.c').read_text()\n"
        "        if receive_text.count('int main(void)')!=1:raise ValueError('one exact previous Immediate main required')\n"
        "        receive_prior.write_text(receive_text.replace('int main(void)','int preceding_immediate_adapter_main(void)'))\n"
        "        before[str(receive_prior.relative_to(ROOT))]=digest(receive_prior)\n"
        "        headers = run/'include'")
    t=once(t,'        for name, expected in {**before, **frozen_before}.items():',
        "        recv_rows=[json.loads(line.split(' ',1)[1])for line in c.stdout.splitlines()if line.startswith('SEGMENTED_RECEIVE_VERBS_ADAPTER ')]\n"
        "        if recv_rows!=[dict(pass_test=True,large_RECV_cases=12,other_positive_cases=5,negative_cases=9,\n"
        "                            base_RECV_ASan_guarded=True,zero_unused_SGE_not_read=True,actual_posting=False)]:raise ValueError('actual RECV/old compatibility/negative oracles required')\n"
        "        report['RECV_summary']=recv_rows[0]\n"
        '        for name, expected in {**before, **frozen_before}.items():')
    t=once(t,'TESTS/"probe_segmented_read_verbs_adapter.py",',
        'TESTS/"probe_segmented_read_verbs_adapter.py",TESTS/"probe_segmented_immediate_verbs_adapter.py",')
    ast.parse(t);return t


if __name__=='__main__':
    exec(compile(runner_source(),str(Path(__file__).resolve()),'exec'),dict(__name__='__main__',__file__=str(Path(__file__).resolve())))
