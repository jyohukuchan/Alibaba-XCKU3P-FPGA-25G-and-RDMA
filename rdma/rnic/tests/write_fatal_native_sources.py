# SPDX-License-Identifier: BSD-2-Clause-Views
"""Select exact fatal61/62 native graph/whole208 HLS, never old binary/core."""
from pathlib import Path
import audit_segmented_receive as binding
ROOT=binding.ROOT;digest=binding.digest
ELABORATION=binding.record('write-fatal-native-elaboration-001')
BASELINE=binding.record('write-psn-control-native-full-001')


def validate(path):
    if path!=ELABORATION:raise ValueError('exact actual fatal native integration required')
    r,rid=binding.bindings('write-fatal-native-elaboration-001')
    old,oid=binding.bindings('write-psn-control-native-full-001')
    audit,aid=binding.bindings('write-fatal-native-source-diagnostics-001')
    if not all(r.get(k)for k in ['pass_test','source_unchanged','full_native_elaboration','actual_generated_HLS',
        'native_authenticated_fatal61_62_and_selected_abort_cancel_inserted','complete_HLS_cohort_replaced',
        'shared_native_MR_PTE_backend_nonce','one_ACK_allocator','both_global_HLS_drains_zero'])or \
       r['HLS_top']!='rocev2_native_write_abort_top'or not audit['audit_passed']or \
       (r['RNC_features'],r['CQC_features'],r['SQC_features'],r['RQC_features'],r['software_profile'])!=(131071,511,13,63,8):
        raise ValueError('actual protected complete fatal/abort/cancel source graph and source audit required')
    if not old['pass_test']or not old['source_unchanged']or len(old['tests'])!=38:
        raise ValueError('all38 original native PSN/RNR/WRITE/Immediate/Atomic/other cases required')
    return r,dict(actual_fatal_elaboration=rid,actual_fatal_source_audit=aid,original38_runtime=oid)


def sources(path,run):
    r,identities=validate(path)
    generated,gid=binding.bindings('write-abort-generated-hls-001')
    audit,aid=binding.bindings('write-abort-generated-diagnostics-001')
    if not generated['pass_test']or not generated['source_and_frozen_inputs_unchanged']or \
       generated['HLS_top']!=r['HLS_top']or not audit['audit_passed']:
        raise ValueError('same actual complete abort HLS208/port/domain audit required')
    src=[ROOT/n for n in r['selected_RTL']];data=[ROOT/n for n in r['selected_HLS_data']]
    before=dict(r['source_sha256']);genroot=ROOT/generated['directory']/'project/solution1/syn/verilog'
    if len(generated['generated_sha256'])!=208 or {q.name for q in [*src,*data]if q.parent==genroot}!=set(generated['generated_sha256']):
        raise ValueError('every same-generation208 HLS RTL/data file required')
    for q in [*src,*data]:
        if digest(q)!=before[str(q.relative_to(ROOT))]:raise ValueError('actual consumed source changed:'+str(q))
    for q in [Path(__file__).resolve(),path,BASELINE,binding.record('write-abort-generated-hls-001'),
        binding.record('write-abort-generated-diagnostics-001'),binding.record('write-fatal-native-source-diagnostics-001')]:
        before[str(q.relative_to(ROOT))]=digest(q)
    return src,data,before
