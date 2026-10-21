#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Fresh -O1 C++ simulation of the exact corrected READ native graph/all30 cases.

Only host-simulator optimization and read-only progress prints change. RTL, independent
inputs/oracles, original1200s compile/30s runtime limits, FPGA clocks/geometry/
timing/guards/drains remain identical. No failed binary/cache is overwritten
or treated as a newly compiled model; no hardware or native success assumed.
"""
import ast
from pathlib import Path
import tempfile
import probe_segmented_read_route_native_full as parent

ROOT=parent.ROOT;once=parent.once


def runner_source():
    t=parent.runner_source()
    a=t.index('"""');b=t.index('"""',a+3)+3;t=t[:a]+'"""'+__doc__+'"""'+t[b:]
    t=once(t,"'-CFLAGS','-O0'","'-CFLAGS','-O1'")
    t=once(t,'import segmented_read_route_native_fixture as service',
        'import segmented_read_route_progress_native_fixture as service')
    for old,new in [("prefix='segmented-read-route-native-full-'","prefix='segmented-read-route-o1-native-full-'"),
        ("prefix='as02-segmented-read-route-obj-'","prefix='as02-segmented-read-route-o1-obj-'"),
        ("prefix='as02-segmented-read-route-artifacts-'","prefix='as02-segmented-read-route-o1-artifacts-'")]:t=once(t,old,new)
    t=once(t,'accepted_QP_TX_effective_route=True,',
        "accepted_QP_TX_effective_route=True,simulation_CXX_optimization='-O1',FPGA_clock_or_timing_changed=False,")
    ast.parse(t);return t


def main():
    run=Path(tempfile.mkdtemp(prefix='segmented-read-route-o1-runner-',dir=ROOT/'rdma/rnic/build'))
    frozen=run/'native_runner.py';frozen.write_text(runner_source())
    exec(compile(frozen.read_text(),str(frozen),'exec'),dict(__name__='__main__',__file__=str(frozen)))


if __name__=='__main__':main()
