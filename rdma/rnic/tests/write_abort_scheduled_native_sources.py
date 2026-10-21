# SPDX-License-Identifier: BSD-2-Clause-Views
"""Select exact whole scheduled206 HLS and unchanged real fatal native graph."""
from pathlib import Path
import audit_segmented_receive as binding

ROOT=binding.ROOT;digest=binding.digest
ELABORATION=binding.record('write-abort-scheduled-native-elaboration-001')
BASELINE=binding.record('write-psn-control-native-full-001')


def validate(path):
    if path!=ELABORATION:raise ValueError('exact actual scheduled native integration required')
    names=['write-abort-scheduled-native-elaboration-001','write-abort-scheduled-generated-diagnostics-001',
        'write-abort-scheduled-diagnostics-001','write-fatal-native-source-diagnostics-001',
        'write-psn-control-native-full-001','write-fatal-native-full-001']
    records={};ids={}
    for n in names:records[n],ids[n]=binding.bindings(n)
    r,generated,consumer,source,old,failed=[records[n]for n in names]
    required=['pass_test','source_unchanged','full_native_elaboration','actual_generated_HLS',
        'native_authenticated_fatal61_62_and_selected_abort_cancel_inserted','complete_HLS_cohort_replaced',
        'original_non_HLS_native_leaves_unchanged','shared_native_MR_PTE_backend_nonce','one_ACK_allocator','both_global_HLS_drains_zero']
    if not all(r.get(k)for k in required)or not all(a['audit_passed']for a in [generated,consumer,source])or \
       not generated['all_original_port_contracts_identical']or not generated['actual_same_tested_scheduled_parser']or \
       (r['RNC_features'],r['CQC_features'],r['SQC_features'],r['RQC_features'],r['software_profile'])!=(131071,511,13,63,8):
        raise ValueError('actual complete scheduled core/unchanged native wiring/ports/domains/profile8 required')
    if not old['pass_test']or not old['source_unchanged']or len(old['tests'])!=38:
        raise ValueError('all actual original38 regressions required')
    if failed['pass_test']or failed['error_type']!='TimeoutExpired'or failed['compile_limit_seconds']!=1200 or failed['tests']:
        raise ValueError('first original1200s timeout/zero cases must stay a failure')
    return r,ids


def sources(path,run):
    r,identities=validate(path)
    hls,gid=binding.bindings('write-abort-scheduled-generated-hls-001')
    audit,aid=binding.bindings('write-abort-scheduled-generated-diagnostics-001')
    if not hls['pass_test']or not hls['source_and_frozen_inputs_unchanged']or not audit['audit_passed']or \
       hls['HLS_top']!=r['HLS_top']or len(hls['generated_sha256'])!=audit['actual_generated_RTL_and_data_files']:
        raise ValueError('same entire actual scheduled HLS cohort and port/domain audit required')
    src=[ROOT/n for n in r['selected_RTL']];data=[ROOT/n for n in r['selected_HLS_data']]
    before=dict(r['source_sha256']);gen=ROOT/hls['directory']/'project/solution1/syn/verilog'
    if {q.name for q in [*src,*data]if q.parent==gen}!=set(hls['generated_sha256']):
        raise ValueError('every same-generation scheduled RTL/data file required; no mixed/stub core')
    for q in [*src,*data]:
        if digest(q)!=before[str(q.relative_to(ROOT))]:raise ValueError('actual consumed source changed:'+str(q))
    for q in [Path(__file__).resolve(),path,BASELINE,binding.record('write-abort-scheduled-generated-hls-001'),
        binding.record('write-abort-scheduled-generated-diagnostics-001'),binding.record('write-abort-scheduled-diagnostics-001'),
        binding.record('write-fatal-native-source-diagnostics-001'),binding.record('write-fatal-native-full-001')]:
        before[str(q.relative_to(ROOT))]=digest(q)
    return src,data,before
