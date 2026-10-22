#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Exact fatal native graph with whole event-status HLS, not runtime proof.

Every262 non-HLS leaf/profile/clock/drain and original180s/1GiB gates stay.
Require one real metadata engine/collector and no duplicate old metadata RAM.
"""
import ast
from pathlib import Path
import tempfile
import check_write_abort_scheduled_native as parent
from segmented_write_payload_native_fixture import once

ROOT=parent.ROOT


def checker_source():
    t=Path(parent.__file__).read_text();a=t.index('"""');b=t.index('"""',a+3)+3;t=t[:a]+'"""'+__doc__+'"""'+t[b:]
    t=t.replace('write-abort-scheduled-','write-abort-event-')
    t=once(t,"'write-abort-event-generated-hls-001'","'write-abort-event-generated-hls-002'")
    t=once(t,"not generated['actual_same_tested_scheduled_parser']:",
        "not generated['actual_same_tested_scheduled_parser']or not generated['actual_metadata_engine_scalar_status_barrier_removed']or not generated['actual_one_metadata_engine_and_event_collector']:")
    t=once(t,"Path(__file__).resolve(),*[binding.record(n)for n in names]",
        "Path(__file__).resolve(),ROOT/'rdma/rnic/tests/check_write_abort_event_native.py',ROOT/'rdma/rnic/tests/check_write_abort_scheduled_native.py',*[binding.record(n)for n in names]")
    t=once(t,"wanted=old['module_counts']",'''wanted=dict(old['module_counts'])
        wanted.update(rocev2_native_write_abort_top_as02_retrans_meta_table_event_0_s=1,
            rocev2_native_write_abort_top_as02_retrans_meta_fault_collect_0_s=1,
            rocev2_native_write_abort_top_retrans_meta_table_0_s=0)''')
    t=once(t,'one_ACK_allocator=True,selected_certificate_is_global_drain_or_unpin=False,',
        'one_ACK_allocator=True,event_status_metadata_engine_inserted=True,selected_certificate_is_global_drain_or_unpin=False,')
    ast.parse(t);return t


if __name__=='__main__':
    run=Path(tempfile.mkdtemp(prefix='write-abort-event-native-checker-',dir=ROOT/'rdma/rnic/build'))
    frozen=run/'check.py';frozen.write_text(checker_source())
    exec(compile(frozen.read_text(),str(frozen),'exec'),dict(__name__='__main__',__file__=str(frozen)))
