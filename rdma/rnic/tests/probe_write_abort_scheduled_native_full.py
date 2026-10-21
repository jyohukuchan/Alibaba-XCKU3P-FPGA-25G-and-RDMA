#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Fresh scheduled-core native40; EXACT original38+fatal2 bench/raw/oracles.

Whole actual scheduled206 HLS, unchanged real native MR/backend/MAC/PSN/
abort/cancel; only host/root/peer/PHY/PTP modeled. Original1200s/30s/4ns.
Not standard error CQ/STOP/global drain/unpin or physical/timing proof.
"""
import ast
from pathlib import Path
import tempfile
import probe_write_fatal_native_full as parent
import write_abort_scheduled_native_sources as source
from segmented_write_payload_native_fixture import once

ROOT=source.ROOT


def runner_source():
    t=parent.runner_source();a=t.index('"""');b=t.index('"""',a+3)+3;t=t[:a]+'"""'+__doc__+'"""'+t[b:]
    for old,new in [
        ('import write_fatal_native_sources as source','import write_abort_scheduled_native_sources as source'),
        ("prefix='write-fatal-native-full-'","prefix='write-abort-scheduled-native-full-'"),
        ("prefix='as02-write-fatal-native-obj-'","prefix='as02-write-abort-scheduled-native-obj-'"),
        ("prefix='as02-write-fatal-native-artifacts-'","prefix='as02-write-abort-scheduled-native-artifacts-'"),
        ('fatal63_or_error_CQ_STOP_global_drain_unpin_qualified=False)',
         'fatal63_or_error_CQ_STOP_global_drain_unpin_qualified=False,new_scheduled_HLS_cohort_runtime=True)')]:
        t=once(t,old,new)
    old="'write-fatal-native-fixture-diagnostics-001'"
    if t.count(old)!=2:raise ValueError('both original strict preflight bindings required')
    t=t.replace(old,"'write-abort-scheduled-native-fixture-diagnostics-001'")
    ast.parse(t);return t


if __name__=='__main__':
    run=Path(tempfile.mkdtemp(prefix='write-abort-scheduled-native-runner-',dir=ROOT/'rdma/rnic/build'))
    frozen=run/'native_runner.py';frozen.write_text(runner_source())
    exec(compile(frozen.read_text(),str(frozen),'exec'),dict(__name__='__main__',__file__=str(frozen)))
