# SPDX-License-Identifier: BSD-2-Clause-Views
"""Exact actually elaborated WRITE-native set, no mixed HLS/helper or stub.

Bind the original34 native runtime baseline and all current selected inputs;
fresh compilation below is mandatory. Historical runtime is NOT new proof.
"""
from pathlib import Path
import audit_segmented_receive as binding

ROOT=binding.ROOT;digest=binding.digest
ELABORATION=binding.record('segmented-write-native-elaboration-001')
BASELINE=binding.record('segmented-receive-native-full-004')


def validate(path):
    if path!=ELABORATION:raise ValueError('exact actually inserted native graph required')
    r,identity=binding.bindings('segmented-write-native-elaboration-001')
    old,old_id=binding.bindings('segmented-receive-native-full-004')
    header,header_id=binding.bindings('native-write-header-gate-001')
    if not old.get('pass_test')or not old.get('source_unchanged')or len(old['tests'])!=34 or \
       any(v['exit']or v['seconds']>30 for v in old['tests'].values()):
        raise ValueError('all34 original actual native runtime checks required')
    if not header.get('pass_test')or not header.get('source_unchanged')or header['summary']['frames']!=512:
        raise ValueError('actual native header gate runtime required')
    if not all(r.get(k)for k in ['pass_test','source_unchanged','actual_generated_HLS','full_native_elaboration',
        'native_controller_inserted','real_native_PSN_commit','shared_native_MR_PTE_backend_nonce','one_ACK_allocator',
        'both_global_HLS_drains_zero'])or r.get('HLS_stub')or r.get('unknown_leaves_ignored')or \
       r.get('HLS_top')!='rocev2_native_segmented_write_owned_top' or \
       (r['RNC_features'],r['CQC_features'],r['SQC_features'],r['RQC_features'])!=(65535,255,13,31):
        raise ValueError('actual complete typed WRITE/HLS/native/PSN/ACK/MR graph required')
    return r,dict(current_elaboration=identity,original34_runtime=old_id,native_header_gate=header_id)


def sources(path,run):
    r,identities=validate(path)
    generated,generated_identity=binding.bindings('segmented-write-owned-generated-hls-001')
    if not generated['pass_test']or not generated['source_and_frozen_inputs_unchanged']or \
       not generated['write_owner424_and_receipt456_verified']or generated['HLS_top']!=r['HLS_top']:
        raise ValueError('actual complete typed generated RTL/data manifest required')
    src=[ROOT/n for n in r['selected_RTL']];data=[ROOT/n for n in r['selected_HLS_data']]
    if any(digest(q)!=r['source_sha256'][str(q.relative_to(ROOT))]for q in src):
        raise ValueError('exact actual whole generated/core data set required')
    genroot=ROOT/generated['directory']/'project/solution1/syn/verilog'
    if set(data)!={genroot/n for n in generated['generated_sha256']if n.endswith('.dat')}:
        raise ValueError('entire actual same-generation HLS data set required')
    if any(digest(q)!=generated['generated_sha256'][q.name]for q in data):
        raise ValueError('actual generated data manifest mismatch')
    before=dict(r['source_sha256'])
    for q in [*data,Path(__file__).resolve(),path,BASELINE,binding.record('native-write-header-gate-001'),
        binding.record('segmented-write-owned-generated-hls-001')]:
        before[str(q.relative_to(ROOT))]=digest(q)
    return src,data,before
