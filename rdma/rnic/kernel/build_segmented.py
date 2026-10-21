#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Freeze/build matched RNC8191/CQC31/profile4 actual kernel source cohort.

Real running-header compile/link of actual MR/SQ/CQ/verbs/lifecycle code.
Never install/load or claim actual Linux callbacks/DMA/hardware runtime.
"""
import ast
from pathlib import Path
import build_zero as parent
import derive_segmented_kernel as candidate


def runner_source():
    t=Path(parent.__file__).read_text();once=candidate.once
    start=t.index('"""');end=t.index('"""',start+3)+3
    t=t[:start]+'"""'+__doc__+'"""'+t[end:]
    t=once(t,'import os','import os\nimport sys')
    t=once(t,'import derive_zero_kernel as candidate','import derive_segmented_kernel as candidate')
    t=once(t,"'wqe_zero.c','wqe_zero.h','verbs_zero_wqe.c']))",
        "'wqe_zero.c','wqe_zero.h','verbs_zero_wqe.c','wqe_segmented.c','wqe_segmented.h','verbs_segmented_wqe.c','verbs_segmented_wqe.h']))")
    marker="    for n in names:\n        if KERNEL/n in derived:"
    t=once(t,marker,"    helpers=[Path(m.__file__).resolve()for m in list(sys.modules.values())if getattr(m,'__file__',None)and\n"
        "        Path(m.__file__).resolve().is_relative_to(KERNEL)]\n"
        "    before.update({str(p.relative_to(ROOT)):digest(p)for p in helpers})\n"+marker)
    t=once(t,"prefix='zero-kernel-frozen-'","prefix='segmented-kernel-frozen-'")
    t=once(t,'actual_kernel_callback_runtime=False,standard_provider_runtime=False)',
        'actual_kernel_callback_runtime=False,standard_provider_runtime=False,\n'
        '        private_segmented_profile=4,matched_RNC_features=8191,matched_CQC_features=31,large_WRITE_SEND_max_bytes=1048576)')
    t=once(t,"wanted=['as02_zero_wqe_validate'",
        "wanted=['as02_segmented_wqe_validate','as02_segmented_wqe_encode','as02_segmented_wqe_decode',\n"
        "            'as02_segmented_wqe_from_ib_send_wr','as02_zero_wqe_validate'")
    ast.parse(t);return t


def main():
    exec(compile(runner_source(),str(Path(__file__).resolve()),'exec'),
         dict(__name__='__main__',__file__=str(Path(__file__).resolve())))


if __name__=='__main__':main()
