#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Fresh native42 with all actual RX leases distinct from control quarantine.

Same old40 plus two full RQC receipt cases, exact unchanged whole bench and
all original deadlines/clock/optimization/process-group/resource gates.
No reused failed simulator or error CQ/STOP/global unpin qualification.
"""
import ast
from pathlib import Path
import tempfile
import probe_fatal_rq_cancel_native_full as parent
import fatal_rq_lease_native_sources as source
from segmented_write_payload_native_fixture import once

ROOT=source.ROOT


def runner_source():
    t=parent.runner_source();a=t.index('"""');b=t.index('"""',a+3)+3;t=t[:a]+'"""'+__doc__+'"""'+t[b:]
    for old,new in [
        ('import fatal_rq_cancel_native_sources as source','import fatal_rq_lease_native_sources as source'),
        ("prefix='fatal-rq-cancel-native-full-'","prefix='fatal-rq-lease-native-full-'"),
        ("prefix='as02-fatal-rq-cancel-native-obj-'","prefix='as02-fatal-rq-lease-native-obj-'"),
        ("prefix='as02-fatal-rq-cancel-native-artifacts-'","prefix='as02-fatal-rq-lease-native-artifacts-'"),
        ('FEC_features=31)','FEC_features=31,actual_lease_only_RX_export=True)')]:t=once(t,old,new)
    old="'fatal-rq-cancel-native-fixture-diagnostics-001'"
    if t.count(old)!=2:raise ValueError('both exact new fixture preflight bindings required')
    t=t.replace(old,"'fatal-rq-lease-native-fixture-diagnostics-001'")
    ast.parse(t);return t


if __name__=='__main__':
    run=Path(tempfile.mkdtemp(prefix='fatal-rq-lease-native-runner-',dir=ROOT/'rdma/rnic/build'))
    frozen=run/'native_runner.py';frozen.write_text(runner_source())
    exec(compile(frozen.read_text(),str(frozen),'exec'),dict(__name__='__main__',__file__=str(frozen)))
