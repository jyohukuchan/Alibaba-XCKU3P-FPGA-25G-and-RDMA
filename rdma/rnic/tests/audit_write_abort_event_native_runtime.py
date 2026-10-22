#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual event-status native40, every old38 outcome and genuine fatal2 proof.

No binary/cohort/oracle substitution, error CQ/STOP/global drain/unpin or
physical qualification. Preserve original timing constraints and factual
HLS estimate verdict, without assuming a timing improvement or failure.
"""
import ast
from pathlib import Path
import tempfile
import audit_write_abort_scheduled_mac_native_runtime as parent
from segmented_write_payload_native_fixture import once

ROOT=parent.ROOT


def audit_source():
    t=parent.audit_source();a=t.index('"""');b=t.index('"""',a+3)+3;t=t[:a]+'"""'+__doc__+'"""'+t[b:]
    for old,new in [
        ("'write-abort-scheduled-mac-native-full-001'","'write-abort-event-native-full-001'"),
        ("r'write-abort-scheduled-mac-native-full-\\d{3}'","r'write-abort-event-native-full-\\d{3}'"),
        ("'write-abort-scheduled-native-elaboration-001'","'write-abort-event-native-elaboration-001'"),
        ("'write-abort-scheduled-mac-native-fixture-diagnostics-001'","'write-abort-event-native-fixture-diagnostics-001'"),
        ("'write-abort-scheduled-generated-hls-001'","'write-abort-event-generated-hls-002'"),
        ("'write-abort-scheduled-generated-diagnostics-001'","'write-abort-event-generated-diagnostics-001'"),
        ("'case_specific_fatal_MAC_hold','isolated_fatal_test_actor']","'case_specific_fatal_MAC_hold','isolated_fatal_test_actor','event_status_metadata_runtime']"),
        ("or hls['original_effective_period_met']:","or hls['original_effective_period_met']!=(float(hls['estimated_clock_period'])<=2.92):"),
        ('original timing failure must remain explicit, never waived/reclassified','original timing constraints and factual effective2.92ns estimate verdict must remain explicit'),
        ('original_timing_met=False,full_board_timing=False,overall_goal_complete=False,',
         "original_timing_met=hls['original_effective_period_met'],full_board_timing=False,overall_goal_complete=False,"),
        ("ROOT/'rdma/rnic/tests/audit_write_abort_scheduled_mac_native_runtime.py',",
         "ROOT/'rdma/rnic/tests/audit_write_abort_event_native_runtime.py',ROOT/'rdma/rnic/tests/audit_write_abort_scheduled_mac_native_runtime.py',")]:t=once(t,old,new)
    ast.parse(t);return t


if __name__=='__main__':
    run=Path(tempfile.mkdtemp(prefix='write-abort-event-native-runtime-audit-',dir=ROOT/'rdma/rnic/build'))
    frozen=run/'audit.py';frozen.write_text(audit_source())
    exec(compile(frozen.read_text(),str(frozen),'exec'),dict(__name__='__main__',__file__=str(frozen)))
