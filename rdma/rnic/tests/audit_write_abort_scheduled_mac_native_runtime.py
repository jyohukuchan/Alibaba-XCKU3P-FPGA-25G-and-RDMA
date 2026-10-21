#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual fixed-MAC/test-actor native40 proof, not a diagnostic-binary reuse.

Every original38 full outcome, real fatal wire/owner/cancel/RQ/quarantine
and source-defined nonce check remains. Not error CQ/STOP/drain/unpin.
"""
import ast
from pathlib import Path
import tempfile
import audit_write_abort_scheduled_native_runtime as parent
from segmented_write_payload_native_fixture import once

ROOT=parent.ROOT


def audit_source():
    t=parent.audit_source();a=t.index('"""');b=t.index('"""',a+3)+3;t=t[:a]+'"""'+__doc__+'"""'+t[b:]
    for old,new in [
        ("'write-abort-scheduled-native-full-001'","'write-abort-scheduled-mac-native-full-001'"),
        ("r'write-abort-scheduled-native-full-\\d{3}'","r'write-abort-scheduled-mac-native-full-\\d{3}'"),
        ("'write-abort-scheduled-native-fixture-diagnostics-001'","'write-abort-scheduled-mac-native-fixture-diagnostics-001'"),
        ('import write_fatal_native_fixture as fixture','import write_abort_scheduled_mac_native_fixture as fixture'),
        ("'all38_prior_cases_retained','new_scheduled_HLS_cohort_runtime']",
         "'all38_prior_cases_retained','new_scheduled_HLS_cohort_runtime','case_specific_fatal_MAC_hold','isolated_fatal_test_actor']"),
        ("ROOT/'rdma/rnic/tests/audit_write_abort_scheduled_native_runtime.py',",
         "ROOT/'rdma/rnic/tests/audit_write_abort_scheduled_mac_native_runtime.py',ROOT/'rdma/rnic/tests/audit_write_abort_scheduled_native_runtime.py',")]:
        t=once(t,old,new)
    ast.parse(t);return t


if __name__=='__main__':
    run=Path(tempfile.mkdtemp(prefix='write-abort-scheduled-mac-runtime-audit-',dir=ROOT/'rdma/rnic/build'))
    frozen=run/'audit.py';frozen.write_text(audit_source())
    exec(compile(frozen.read_text(),str(frozen),'exec'),dict(__name__='__main__',__file__=str(frozen)))
