#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Fresh event-status native40; exact prior fixed-MAC bench/inputs/oracles.

Entire new real HLS/native graph; unchanged1200s/30s/180s/4ns/j4/O1/gates.
No reused simulator binary or error-CQ/STOP/global-drain/unpin qualification.
"""
import ast
from pathlib import Path
import tempfile
import probe_write_abort_scheduled_mac_native_full as parent
import write_abort_event_native_sources as source
from segmented_write_payload_native_fixture import once

ROOT=source.ROOT


def runner_source():
    t=parent.runner_source();a=t.index('"""');b=t.index('"""',a+3)+3;t=t[:a]+'"""'+__doc__+'"""'+t[b:]
    for old,new in [
        ('import write_abort_scheduled_native_sources as source','import write_abort_event_native_sources as source'),
        ("prefix='write-abort-scheduled-mac-native-full-'","prefix='write-abort-event-native-full-'"),
        ("prefix='as02-write-abort-scheduled-mac-native-obj-'","prefix='as02-write-abort-event-native-obj-'"),
        ("prefix='as02-write-abort-scheduled-mac-native-artifacts-'","prefix='as02-write-abort-event-native-artifacts-'"),
        ('isolated_fatal_test_actor=True)','isolated_fatal_test_actor=True,event_status_metadata_runtime=True)')]:t=once(t,old,new)
    old="'write-abort-scheduled-mac-native-fixture-diagnostics-001'"
    if t.count(old)!=2:raise ValueError('both exact preflight bindings required')
    t=t.replace(old,"'write-abort-event-native-fixture-diagnostics-001'")
    ast.parse(t);return t


if __name__=='__main__':
    run=Path(tempfile.mkdtemp(prefix='write-abort-event-native-runner-',dir=ROOT/'rdma/rnic/build'))
    frozen=run/'native_runner.py';frozen.write_text(runner_source())
    exec(compile(frozen.read_text(),str(frozen),'exec'),dict(__name__='__main__',__file__=str(frozen)))
