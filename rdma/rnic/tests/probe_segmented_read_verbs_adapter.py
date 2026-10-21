#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Real-header READ Linux-WR adapter plus ASan/UBSan modeled-WR execution.

Keep all54 positive/14 negative old tests, add exact large READ/full64 ranges/
flags/SGE/null refusal and NEW-entry base-only SEND/old-op compatibility.
No actual Linux posting/MR/SQ/DMA/CQ or installed/hardware qualification.
"""
import ast
from pathlib import Path
import probe_segmented_verbs_adapter as parent


def runner_source():
    t=Path(parent.__file__).read_text()
    from segmented_kernel_models import once
    a=t.index('"""');b=t.index('"""',a+3)+3;t=t[:a]+'"""'+__doc__+'"""'+t[b:]
    t=once(t,"'verbs_atomic_wqe.c', 'verbs_zero_wqe.c', 'verbs_segmented_wqe.c']",
        "'verbs_atomic_wqe.c', 'verbs_zero_wqe.c', 'verbs_segmented_wqe.c',\n"
        "         'wqe_segmented_read.c','verbs_segmented_read_wqe.c']")
    t=t.replace("TESTS/'kernel_segmented_wqe.c'","TESTS/'kernel_segmented_read_wqe.c'")
    t=once(t,"TESTS/'kernel_segmented_read_wqe.c',\n",
        "TESTS/'kernel_segmented_read_wqe.c',TESTS/'kernel_segmented_wqe.c',\n")
    t=once(t,"prefix='segmented-verbs-adapter-'","prefix='segmented-read-verbs-adapter-'")
    t=once(t,"wanted = ['as02_segmented_wqe_from_ib_send_wr'",
        "wanted = ['as02_segmented_read_wqe_from_ib_send_wr','as02_segmented_read_wqe_validate',\n"
        "                  'as02_segmented_read_wqe_encode','as02_segmented_read_wqe_decode','as02_segmented_wqe_from_ib_send_wr'")
    t=once(t,'        for name, expected in {**before, **frozen_before}.items():',
        "        read_rows=[json.loads(line.split(' ',1)[1])for line in c.stdout.splitlines()\n"
        "                   if line.startswith('SEGMENTED_READ_VERBS_ADAPTER ')]\n"
        "        if read_rows!=[dict(pass_test=True,large_READ_cases=24,other_positive_cases=15,negative_cases=14,\n"
        "                            base_SEND_ASan_guarded=True,old_adapter_unchanged=True,actual_posting=False)]:\n"
        "            raise ValueError('all new exact READ/compatibility/error oracles required')\n"
        "        report['READ_summary']=read_rows[0]\n"
        '        for name, expected in {**before, **frozen_before}.items():')
    t=once(t,'Path(__file__).resolve(), Path(model.__file__).resolve(),',
        'Path(__file__).resolve(), TESTS/"probe_segmented_verbs_adapter.py", Path(model.__file__).resolve(),')
    ast.parse(t);return t


def main():
    exec(compile(runner_source(),str(Path(__file__).resolve()),'exec'),
        dict(__name__='__main__',__file__=str(Path(__file__).resolve())))


if __name__=='__main__':main()
