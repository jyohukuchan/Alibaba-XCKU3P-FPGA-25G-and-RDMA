#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Private profile6/32767/127 full modules, gated by all32 actual native cases.

Real running-header build/link only; preserve all old/default source and
actual MR/SQ/CQ/verbs/lifecycle code. No install/load/API/hardware claim.
"""
import ast
from pathlib import Path
import build_segmented_read as base
import derive_segmented_immediate_kernel as candidate


def runner_source():
    t=base.runner_source();once=candidate.once
    a=t.index('"""');b=t.index('"""',a+3)+3;t=t[:a]+'"""'+__doc__+'"""'+t[b:]
    t=once(t,'import derive_segmented_read_kernel as candidate','import derive_segmented_immediate_kernel as candidate')
    t=once(t,"'verbs_segmented_read_wqe.c','verbs_segmented_read_wqe.h']))",
        "'verbs_segmented_read_wqe.c','verbs_segmented_read_wqe.h','wqe_segmented_immediate.c','wqe_segmented_immediate.h',"
        "'verbs_segmented_immediate_wqe.c','verbs_segmented_immediate_wqe.h']))")
    t=once(t,"prefix='segmented-read-kernel-frozen-'","prefix='segmented-immediate-kernel-frozen-'")
    t=once(t,'private_segmented_profile=5,matched_RNC_features=16383,matched_CQC_features=63,',
        'private_segmented_profile=6,matched_RNC_features=32767,matched_CQC_features=127,large_Immediate_max_bytes=1048576,')
    t=once(t,"wanted=['as02_segmented_read_wqe_validate'",
        "wanted=['as02_segmented_immediate_wqe_validate','as02_segmented_immediate_wqe_encode','as02_segmented_immediate_wqe_decode',\n"
        "            'as02_segmented_immediate_wqe_from_ib_send_wr','as02_segmented_read_wqe_validate'")
    t=once(t,"len(native.get('tests',{}))!=30","len(native.get('tests',{}))!=32")
    t=once(t,"!=(16383,63)or not native.get('large_READ_native_runtime'):",
        "!=(32767,127)or not all(native.get(n)for n in ['large_READ_native_runtime','large_Immediate_native_runtime','all30_prior_cases_retained']):")
    ast.parse(t);return t


if __name__=='__main__':
    exec(compile(runner_source(),str(Path(__file__).resolve()),'exec'),dict(__name__='__main__',__file__=str(Path(__file__).resolve())))
