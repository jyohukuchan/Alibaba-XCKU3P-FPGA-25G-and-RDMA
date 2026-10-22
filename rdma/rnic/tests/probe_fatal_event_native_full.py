#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Fresh FEC-native40: actual packet-to-mailbox AXI/ACK with every old oracle.

Whole qualified207 HLS plus tracked-fanout graph002; native guards must
survive host ACK independently of observer retirement. Original1200/30/180s,
4ns/j4/O1/space/process-group gates remain. Not live Linux or drain/unpin.
"""
import ast
from pathlib import Path
import tempfile
import probe_write_abort_event_native_full as parent
import fatal_event_native_sources as source
from segmented_write_payload_native_fixture import once

ROOT=source.ROOT


def runner_source():
    t=parent.runner_source();a=t.index('"""');b=t.index('"""',a+3)+3;t=t[:a]+'"""'+__doc__+'"""'+t[b:]
    for old,new in [
        ('import write_abort_event_native_sources as source','import fatal_event_native_sources as source'),
        ('import write_abort_scheduled_mac_native_fixture as service','import fatal_event_native_fixture as service'),
        ("prefix='write-abort-event-native-full-'","prefix='fatal-event-native-full-'"),
        ("prefix='as02-write-abort-event-native-obj-'","prefix='as02-fatal-event-native-obj-'"),
        ("prefix='as02-write-abort-event-native-artifacts-'","prefix='as02-fatal-event-native-artifacts-'"),
        ("for suffix in ['selected','rq-owner']:","for suffix in ['selected','rq-owner','mmio']:"),
        ('event_status_metadata_runtime=True)',
         'event_status_metadata_runtime=True,actual_fatal_event_mailbox_MMIO_ACK=True,all40_prior_cases_retained=True)')]:t=once(t,old,new)
    old="'write-abort-event-native-fixture-diagnostics-001'"
    if t.count(old)!=2:raise ValueError('both exact new FEC fixture preflight bindings required')
    t=t.replace(old,"'fatal-event-native-fixture-diagnostics-001'")
    ast.parse(t);return t


if __name__=='__main__':
    run=Path(tempfile.mkdtemp(prefix='fatal-event-native-runner-',dir=ROOT/'rdma/rnic/build'))
    frozen=run/'native_runner.py';frozen.write_text(runner_source())
    exec(compile(frozen.read_text(),str(frozen),'exec'),dict(__name__='__main__',__file__=str(frozen)))
