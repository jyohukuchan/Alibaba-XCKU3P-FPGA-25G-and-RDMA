# SPDX-License-Identifier: BSD-2-Clause-Views
"""Select only the entire qualified event-status HLS/native source cohort."""
from pathlib import Path
import ast
import write_abort_scheduled_native_sources as parent

_text=Path(parent.__file__).read_text().replace('write-abort-scheduled-','write-abort-event-')
_text=_text.replace("'write-abort-event-generated-hls-001'","'write-abort-event-generated-hls-002'")
_text=_text.replace("'original_non_HLS_native_leaves_unchanged','shared_native_MR_PTE_backend_nonce'",
    "'original_non_HLS_native_leaves_unchanged','event_status_metadata_engine_inserted','shared_native_MR_PTE_backend_nonce'")
_text=_text.replace("not generated['all_original_port_contracts_identical']or not generated['actual_same_tested_scheduled_parser']or",
    "not generated['actual_metadata_engine_scalar_status_barrier_removed']or not generated['actual_one_metadata_engine_and_event_collector']or not generated['all_original_port_contracts_identical']or not generated['actual_same_tested_scheduled_parser']or")
_text=_text.replace('Path(__file__).resolve(),path,BASELINE,',
    "Path(__file__).resolve(),ROOT/'rdma/rnic/tests/write_abort_scheduled_native_sources.py',path,BASELINE,")
ast.parse(_text)
exec(compile(_text,str(Path(__file__).resolve()),'exec'))
