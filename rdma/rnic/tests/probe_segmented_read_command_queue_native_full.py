#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Fresh actual8193 READ/all29 prior cases with checked metadata lookahead.

Exact original HLS/data/DMA/nonce/fence/MAC/CQ oracles/limits retained; -O1
host simulation, unchanged FPGA clocks and default selection. Only qualified
READ metadata queue and read-only queue observations change. No assumed pass.
"""
import ast
from pathlib import Path
import tempfile
import probe_segmented_read_route_o1_native_full as parent
import segmented_read_command_queue_native_sources as source

ROOT=source.ROOT;once=source.candidate.once


def runner_source():
    t=parent.runner_source()
    a=t.index('"""');b=t.index('"""',a+3)+3;t=t[:a]+'"""'+__doc__+'"""'+t[b:]
    t=once(t,'import segmented_read_route_native_sources as source','import segmented_read_command_queue_native_sources as source')
    t=once(t,'import segmented_read_route_progress_native_fixture as service','import segmented_read_command_queue_native_fixture as service')
    for old,new in [("prefix='segmented-read-route-o1-native-full-'","prefix='segmented-read-command-queue-native-full-'"),
        ("prefix='as02-segmented-read-route-o1-obj-'","prefix='as02-segmented-read-command-queue-obj-'"),
        ("prefix='as02-segmented-read-route-o1-artifacts-'","prefix='as02-segmented-read-command-queue-artifacts-'")]:t=once(t,old,new)
    t=once(t,'accepted_QP_TX_effective_route=True,',
        'accepted_QP_TX_effective_route=True,READ_command_queue_depth=2,')
    ast.parse(t);return t


def main():
    run=Path(tempfile.mkdtemp(prefix='segmented-read-command-queue-runner-',dir=ROOT/'rdma/rnic/build'))
    frozen=run/'native_runner.py';frozen.write_text(runner_source())
    exec(compile(frozen.read_text(),str(frozen),'exec'),dict(__name__='__main__',__file__=str(frozen)))


if __name__=='__main__':main()
