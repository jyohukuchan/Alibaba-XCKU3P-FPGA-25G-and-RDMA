#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Fresh actual scheduled native40, case-correct MAC hold/test-control actor.

Same qualified206 HLS/unchanged native wiring, all original40 inputs/checks/
oracles, partial1100 stalls. Original1200s/30s/4ns/j4/O1/cfuncs500000 retained.
Not error CQ/STOP/global drain/unpin or physical/timing qualification.
"""
import ast
from pathlib import Path
import tempfile
import probe_write_abort_scheduled_native_full as parent
import write_abort_scheduled_native_sources as source
from segmented_write_payload_native_fixture import once

ROOT=source.ROOT


def runner_source():
    t=parent.runner_source();a=t.index('"""');b=t.index('"""',a+3)+3;t=t[:a]+'"""'+__doc__+'"""'+t[b:]
    for old,new in [
        ('import write_fatal_native_fixture as service','import write_abort_scheduled_mac_native_fixture as service'),
        ("prefix='write-abort-scheduled-native-full-'","prefix='write-abort-scheduled-mac-native-full-'"),
        ("prefix='as02-write-abort-scheduled-native-obj-'","prefix='as02-write-abort-scheduled-mac-native-obj-'"),
        ("prefix='as02-write-abort-scheduled-native-artifacts-'","prefix='as02-write-abort-scheduled-mac-native-artifacts-'"),
        ('new_scheduled_HLS_cohort_runtime=True)',
         'new_scheduled_HLS_cohort_runtime=True,case_specific_fatal_MAC_hold=True,isolated_fatal_test_actor=True)')]:t=once(t,old,new)
    old="'write-abort-scheduled-native-fixture-diagnostics-001'"
    if t.count(old)!=2:raise ValueError('both strict preflight bindings required')
    t=t.replace(old,"'write-abort-scheduled-mac-native-fixture-diagnostics-001'")
    ast.parse(t);return t


if __name__=='__main__':
    run=Path(tempfile.mkdtemp(prefix='write-abort-scheduled-mac-native-runner-',dir=ROOT/'rdma/rnic/build'))
    frozen=run/'native_runner.py';frozen.write_text(runner_source())
    exec(compile(frozen.read_text(),str(frozen),'exec'),dict(__name__='__main__',__file__=str(frozen)))
