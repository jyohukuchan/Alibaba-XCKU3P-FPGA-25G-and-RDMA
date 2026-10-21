#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Fresh actual incoming8193 SEND/Immediate + all32 old cases, fixed ingress.

The SAME original full-payload fixture, every34 oracle,1200s/30s bounds,
4ns clocks and data/MR/PTE/nonce/status/fence/ACK-MAC/CQ checks remain.
Only the reviewed production raw-reference gate changes. No old binary or
object reuse, assertion/timeout waiver, installed API or physical/timing claim.
"""
from pathlib import Path
import tempfile
import probe_segmented_receive_native_full as base
import segmented_receive_continuation_native_sources as source

ROOT=source.ROOT;once=source.candidate.once


def runner_source():
    t=base.runner_source();a=t.index('"""');b=t.index('"""',a+3)+3;t=t[:a]+'"""'+__doc__+'"""'+t[b:]
    t=once(t,'import segmented_receive_native_sources as source','import segmented_receive_continuation_native_sources as source')
    t=once(t,"prefix='segmented-receive-native-full-'","prefix='segmented-receive-continuation-native-full-'")
    t=once(t,"prefix='as02-segmented-receive-native-full-obj-'","prefix='as02-segmented-receive-continuation-obj-'")
    t=once(t,"prefix='as02-segmented-receive-native-full-artifacts-'","prefix='as02-segmented-receive-continuation-artifacts-'")
    t=once(t,"    if not evidence.get('full_native_elaboration')",
        "    if not evidence.get('receive_continuation_gate_fixed'):raise ValueError('exact reviewed known-group actual native elaboration required')\n"
        "    if not evidence.get('full_native_elaboration')")
    return t


if __name__=='__main__':
    run=Path(tempfile.mkdtemp(prefix='segmented-receive-continuation-runner-',dir=ROOT/'rdma/rnic/build'))
    frozen=run/'native_runner.py';frozen.write_text(runner_source())
    exec(compile(frozen.read_text(),str(frozen),'exec'),dict(__name__='__main__',__file__=str(frozen)))
