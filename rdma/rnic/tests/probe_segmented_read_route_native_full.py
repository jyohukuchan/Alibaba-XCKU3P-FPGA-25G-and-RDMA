#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Fresh native READ plus all29 old cases with corrected QP_TX route observer.

Keep every original actual SQ/MR/RX/HLS/DMA/nonce/visibility/MAC/CQ oracle and
1200s build/30s runtime bound. Only separately qualified route source selection
changes, plus read-only diagnostics before the original fatal assertion;
no failed model reuse, normalized observations or hardware changes.
"""
import ast
from pathlib import Path
import tempfile
import probe_segmented_read_native_full as parent
import segmented_read_route_native_sources as source

ROOT=source.ROOT;once=source.candidate.once


def runner_source():
    t=parent.runner_source()
    a=t.index('"""');b=t.index('"""',a+3)+3;t=t[:a]+'"""'+__doc__+'"""'+t[b:]
    t=once(t,'import segmented_read_profile_native_sources as source','import segmented_read_route_native_sources as source')
    t=once(t,'import segmented_read_native_fixture as service','import segmented_read_route_native_fixture as service')
    t=once(t,"    for n,h in evidence['source_sha256'].items():",
        "    if evidence['source_sha256'].get(str(source.UNIT.relative_to(ROOT)))!=digest(source.UNIT):\n"
        "        raise ValueError('exact qualified effective-route native elaboration required')\n"
        "    for n,h in evidence['source_sha256'].items():")
    for old,new in [("prefix='segmented-read-native-full-'","prefix='segmented-read-route-native-full-'"),
        ("prefix='as02-segmented-read-native-obj-'","prefix='as02-segmented-read-route-obj-'"),
        ("prefix='as02-segmented-read-native-artifacts-'","prefix='as02-segmented-read-route-artifacts-'")]:t=once(t,old,new)
    t=once(t,'RNC_features=16383,CQC_features=63,kernel_profile_matched=False,',
        'RNC_features=16383,CQC_features=63,kernel_profile_matched=False,accepted_QP_TX_effective_route=True,')
    ast.parse(t);return t


def main():
    run=Path(tempfile.mkdtemp(prefix='segmented-read-route-runner-',dir=ROOT/'rdma/rnic/build'))
    frozen=run/'native_runner.py';frozen.write_text(runner_source())
    exec(compile(frozen.read_text(),str(frozen),'exec'),dict(__name__='__main__',__file__=str(frozen)))


if __name__=='__main__':main()
