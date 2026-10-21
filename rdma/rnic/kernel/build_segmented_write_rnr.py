#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Same profile8 modules ONLY after actual native37 RNR/retry and all36 old.

No kernel feature/source/layout change, install or load. Preserve original
180s build deadline, exact cohort, all cases and unchanged native timing gates.
"""
import ast
from pathlib import Path
import build_segmented_write as parent

ROOT=parent.candidate.ROOT;once=parent.candidate.once


def runner_source():
    t=parent.runner_source();a=t.index('"""');b=t.index('"""',a+3)+3;t=t[:a]+'"""'+__doc__+'"""'+t[b:]
    for old,new in [("prefix='segmented-write-kernel-frozen-'","prefix='segmented-write-rnr-kernel-frozen-'"),
        ("len(native.get('tests',{}))!=36","len(native.get('tests',{}))!=37"),
        ("'all34_prior_cases_retained','private_WRITE_profile_identity']):",
         "'all34_prior_cases_retained','private_WRITE_profile_identity','complete_native_RNR_retry_runtime','all36_prior_cases_retained']):"),
        ('exact matching new profile8 and all36 native WRITE/Immediate cases required',
         'exact matching profile8/native37 RNR/retry plus all36 old cases required'),
        ("{'LARGE_RX_SEND','LARGE_RX_SEND_IMM','LARGE_RX_WRITE','LARGE_RX_WRITE_IMM'}",
         "{'LARGE_RX_SEND','LARGE_RX_SEND_IMM','LARGE_RX_WRITE','LARGE_RX_WRITE_IMM','LARGE_RX_WRITE_RNR'}"),
        ('WRITE_notice_max_bytes=1048576,','WRITE_notice_max_bytes=1048576,native_RNR_retry_matched=True,')]:t=once(t,old,new)
    ast.parse(t);return t


if __name__=='__main__':
    exec(compile(runner_source(),str(Path(__file__).resolve()),'exec'),dict(__name__='__main__',__file__=str(Path(__file__).resolve())))
