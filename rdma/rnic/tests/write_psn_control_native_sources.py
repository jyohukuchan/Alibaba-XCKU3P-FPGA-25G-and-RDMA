# SPDX-License-Identifier: BSD-2-Clause-Views
"""Select exact certified PSN-control native graph, never an old core/binary."""
from pathlib import Path
import audit_segmented_receive as binding

ROOT=binding.ROOT;digest=binding.digest
ELABORATION=binding.record('write-psn-control-native-elaboration-001')
BASELINE=binding.record('segmented-write-rnr-native-full-002')


def validate(path):
    if path!=ELABORATION:raise ValueError('exact actual PSN-control native integration required')
    r,rid=binding.bindings('write-psn-control-native-elaboration-001')
    old,oid=binding.bindings('segmented-write-rnr-native-full-002')
    if not all(r.get(k)for k in ['pass_test','source_unchanged','full_native_elaboration','actual_generated_HLS',
        'native_certified_PSN_controller_inserted','complete_HLS_cohort_replaced','shared_native_MR_PTE_backend_nonce',
        'one_ACK_allocator','both_global_HLS_drains_zero'])or r['HLS_top']!='rocev2_native_control_response_top'or \
       (r['RNC_features'],r['CQC_features'],r['SQC_features'],r['RQC_features'],r['software_profile'])!=(131071,511,13,63,8):
        raise ValueError('actual protected full certified control/HLS/owner graph required')
    if not old['pass_test']or not old['source_unchanged']or len(old['tests'])!=37:
        raise ValueError('all37 actual old RNR/WRITE/Immediate/native cases required')
    return r,dict(actual_control_elaboration=rid,original37_runtime=oid)


def sources(path,run):
    r,identities=validate(path)
    generated,gid=binding.bindings('control-response-generated-hls-001')
    if not generated['pass_test']or not generated['source_and_frozen_inputs_unchanged']or generated['HLS_top']!=r['HLS_top']:
        raise ValueError('same actual complete control HLS generation required')
    src=[ROOT/n for n in r['selected_RTL']];data=[ROOT/n for n in r['selected_HLS_data']]
    before=dict(r['source_sha256']);genroot=ROOT/generated['directory']/'project/solution1/syn/verilog'
    if {q.name for q in [*src,*data]if q.parent==genroot}!=set(generated['generated_sha256']):
        raise ValueError('every same-generation control HLS RTL/data file required')
    for q in [*src,*data]:
        if digest(q)!=before[str(q.relative_to(ROOT))]:raise ValueError('actual consumed native source changed:'+str(q))
    for q in [Path(__file__).resolve(),path,BASELINE,binding.record('control-response-generated-hls-001')]:
        before[str(q.relative_to(ROOT))]=digest(q)
    return src,data,before
