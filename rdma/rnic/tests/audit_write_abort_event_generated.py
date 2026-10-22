#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual event-status HLS domains/ports/metadata independence, not native.

Keep all original121 port contracts and generation/timing/resource gates.
Require one real metadata RAM engine and sticky event collector, with no
per-invocation scalar fault barrier on the actual metadata ap_continue.
"""
import ast
from pathlib import Path
import tempfile
import audit_write_abort_scheduled_generated as parent
from segmented_write_payload_native_fixture import once

ROOT=parent.ROOT


def audit_source():
    t=Path(parent.__file__).read_text();a=t.index('"""');b=t.index('"""',a+3)+3;t=t[:a]+'"""'+__doc__+'"""'+t[b:]
    for old,new in [
        ('native-write-abort-scheduled-transport-001','native-write-abort-event-transport-001'),
        ("default='write-abort-scheduled-generated-hls-001'","default='write-abort-event-generated-hls-002'"),
        ("r'write-abort-scheduled-generated-hls-\\d{3}'","r'write-abort-event-generated-hls-\\d{3}'"),
        ("'write-abort-scheduled-hls-001','write-abort-scheduled-compat-001'","'write-abort-event-hls-001','write-abort-event-compat-001'"),
        ("'write-abort-scheduled-diagnostics-001'","'write-abort-event-diagnostics-001'"),
        ("'generate_exh_512_0_s','msn_table_0_s','state_table_0_s']",
         "'generate_exh_512_0_s','msn_table_0_s','state_table_0_s','as02_retrans_meta_table_event_0_s','as02_retrans_meta_fault_collect_0_s']"),
        ('inputs=[Path(__file__).resolve(),top,oldtop,frozen,SOURCE/\'source.json\']',
         "inputs=[Path(__file__).resolve(),ROOT/'rdma/rnic/tests/audit_write_abort_event_generated.py',ROOT/'rdma/rnic/hls/segmented_write_abort_event_transport.py',top,oldtop,frozen,SOURCE/'source.json',meta_frozen,meta_rtl]"),
        ('actual_CPP_modes=140,all140_old_outcome_oracle_fields_identical=160,',
         'actual_metadata_engine_scalar_status_barrier_removed=True,actual_one_metadata_engine_and_event_collector=True,actual_CPP_modes=140,all140_old_outcome_oracle_fields_identical=160,')]:t=once(t,old,new)
    anchor="    estimate=float(hls['estimated_clock_period'])"
    extra='''    meta_path='hls/ib_transport_protocol/retransmitter/retransmitter.hpp'
    meta_frozen=run/'inputs/fns'/meta_path
    if digest(meta_frozen)!=digest(SOURCE/'fns'/meta_path):
        raise ValueError('same actual tested metadata engine/RAM/collector required')
    if any(n.endswith('_retrans_meta_table_0_s')for n in definitions):
        raise ValueError('old compatibility-wrapper metadata RAM must not be instantiated in parallel')
    engine='as02_retrans_meta_table_event_0_U0'
    for token in ['assign '+engine+"_ap_continue = 1'b1;",'assign '+engine+"_ap_start = 1'b1;"]:
        if token not in top.read_text():raise ValueError('actual metadata process must not rendezvous on successful scalar fault reports:'+token)
    meta_rtl=generated/domains['as02_retrans_meta_table_event_0_s'][0]
    if not all(token in meta_rtl.read_text()for token in ['clear_index','clear_complete','meta_fault_events']):
        raise ValueError('real initialization and event producer must remain in the sole actual metadata engine')
'''
    t=once(t,anchor,extra+anchor);ast.parse(t);return t


if __name__=='__main__':
    run=Path(tempfile.mkdtemp(prefix='write-abort-event-generated-audit-',dir=ROOT/'rdma/rnic/build'))
    frozen=run/'audit.py';frozen.write_text(audit_source())
    exec(compile(frozen.read_text(),str(frozen),'exec'),dict(__name__='__main__',__file__=str(frozen)))
