#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual scheduled-core native40 and exact original38/fatal2 runtime proof.

Retain the full original runtime auditor, changing only qualified cohort/
fixture record selection. Not error CQ/STOP/global drain/unpin or timing.
"""
import ast
from pathlib import Path
import tempfile
import audit_write_fatal_native_runtime as parent
from segmented_write_payload_native_fixture import once

ROOT=parent.ROOT


def audit_source():
    t=Path(parent.__file__).read_text();a=t.index('"""');b=t.index('"""',a+3)+3;t=t[:a]+'"""'+__doc__+'"""'+t[b:]
    for old,new in [
        ("'write-fatal-native-full-001'","'write-abort-scheduled-native-full-001'"),
        ("r'write-fatal-native-full-\\d{3}'","r'write-abort-scheduled-native-full-\\d{3}'"),
        ("'write-fatal-native-elaboration-001'","'write-abort-scheduled-native-elaboration-001'"),
        ("'write-fatal-native-fixture-diagnostics-001'","'write-abort-scheduled-native-fixture-diagnostics-001'"),
        ("'write-abort-generated-hls-001'","'write-abort-scheduled-generated-hls-001'"),
        ("'write-abort-generated-diagnostics-001'","'write-abort-scheduled-generated-diagnostics-001'"),
        ("'complete_native_fatal61_62_selected_runtime','all38_prior_cases_retained']",
         "'complete_native_fatal61_62_selected_runtime','all38_prior_cases_retained','new_scheduled_HLS_cohort_runtime']"),
        ('len(selected)!=208',"len(selected)!=generated['actual_generated_RTL_and_data_files']"),
        # The observer counts tag REWRITES, not address translations. Empty
        # case has no command; partial FIRST has logical tag1==physical nonce1.
        ('logical_completed=int(partial),translated=int(partial),active=0,fault=0)',
         'logical_completed=int(partial),translated=0,active=0,fault=0)'),
        ("ENTIRE same actual208 abort HLS cohort required; no old/new core mixture",
         "ENTIRE same actual scheduled abort HLS cohort required; no old/new core mixture"),
        ('[Path(__file__).resolve(),*snapshot_paths]',
         "[Path(__file__).resolve(),ROOT/'rdma/rnic/tests/audit_write_abort_scheduled_native_runtime.py',"
         "ROOT/'rdma/rnic/tests/audit_write_fatal_native_runtime.py',*snapshot_paths]")]:
        t=once(t,old,new)
    ast.parse(t);return t


if __name__=='__main__':
    run=Path(tempfile.mkdtemp(prefix='write-abort-scheduled-runtime-audit-',dir=ROOT/'rdma/rnic/build'))
    frozen=run/'audit.py';frozen.write_text(audit_source())
    exec(compile(frozen.read_text(),str(frozen),'exec'),dict(__name__='__main__',__file__=str(frozen)))
