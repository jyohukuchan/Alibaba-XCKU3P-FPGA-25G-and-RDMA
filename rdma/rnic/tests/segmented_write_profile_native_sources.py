# SPDX-License-Identifier: BSD-2-Clause-Views
"""Select the exact new private capability graph, not the old runtime binary."""
from pathlib import Path
import audit_segmented_receive as binding

ROOT=binding.ROOT;digest=binding.digest
ELABORATION=binding.record('segmented-write-profile-native-elaboration-001')
BASELINE=binding.record('segmented-write-native-full-002')


def validate(path):
    if path!=ELABORATION:raise ValueError('exact new native identity elaboration required')
    r,rid=binding.bindings('segmented-write-profile-native-elaboration-001')
    actual,aid=binding.bindings('segmented-write-native-runtime-diagnostics-001')
    if not r['pass_test']or not r['source_unchanged']or not r['full_native_elaboration']or \
       not actual['audit_passed']or actual['actual_native_cases']!=36 or \
       (r['RNC_features'],r['CQC_features'],r['SQC_features'],r['RQC_features'],r['software_profile'])!=(131071,511,13,63,8):
        raise ValueError('exact capability graph and actual previous36 payload runtime required')
    return r,dict(new_identity_elaboration=rid,previous_actual_native36=aid)


def sources(path,run):
    r,ids=validate(path);src=[ROOT/n for n in r['selected_RTL']];data=[ROOT/n for n in r['selected_HLS_data']]
    before=dict(r['source_sha256'])
    for q in [*src,*data]:
        if digest(q)!=before[str(q.relative_to(ROOT))]:raise ValueError('new identity actual RTL/data changed')
    for q in [Path(__file__).resolve(),path,BASELINE,binding.record('segmented-write-native-runtime-diagnostics-001')]:before[str(q.relative_to(ROOT))]=digest(q)
    return src,data,before
