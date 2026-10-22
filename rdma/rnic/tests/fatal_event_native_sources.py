# SPDX-License-Identifier: BSD-2-Clause-Views
"""Select the exact tracked-fanout FEC-native graph, never the old native40 binary."""
from pathlib import Path
import audit_segmented_receive as binding
import check_fatal_event_native as derivation

ROOT=binding.ROOT;digest=binding.digest
ELABORATION=binding.record('fatal-event-native-elaboration-002')
BASELINE=binding.record('write-abort-event-native-full-001')
NAMES=['fatal-event-native-elaboration-002','fatal-event-native-source-diagnostics-002',
    'write-abort-event-native-full-001','write-abort-event-native-runtime-diagnostics-001',
    'write-abort-event-native-elaboration-001','write-abort-event-generated-hls-002',
    'write-abort-event-generated-diagnostics-001','fatal-event-mmio-diagnostics-001','fatal-event-fanout-001']


def validate(path):
    if path!=ELABORATION:raise ValueError('exact tracked-fanout source graph002 required')
    records={};ids={}
    for n in NAMES:records[n],ids[n]=binding.bindings(n)
    r,audit,old,runtime,parent,hls,generated,component,fanout=[records[n]for n in NAMES]
    if not all(v.get('pass_test',v.get('audit_passed'))for v in records.values()):
        raise ValueError('actual native40/old38 regression, components and new source qualification required')
    if r['actual_mailbox_native_runtime'] or audit['actual_mailbox_native_packet_MMIO_runtime'] or \
       len(old['tests'])!=40 or not runtime['all38_old_entire_results_except_seconds_identical']:
        raise ValueError('source-only new graph and real old40 baseline required')
    required=['full_native_elaboration','only_two_native_leaves_changed','whole_qualified_HLS207_unchanged',
        'actual_selected_join_tracked_observer_mailbox_fanout','native_quarantine_not_mailbox_ACK_guards_actual_SQC_RQC',
        'both_global_HLS_drains_zero']
    if not all(r.get(k)for k in required) or r['default_or_driver_capability_changed'] or \
       (r['RNC_features'],r['CQC_features'],r['software_profile'])!=(131071,511,8):
        raise ValueError('real complete source/profile8/quarantine/drain contract required')
    before=[ROOT/n for n in parent['selected_RTL']];after=[ROOT/n for n in r['selected_RTL']]
    ot=next(p for p in before if p.name=='rocev2_native_rnic_endpoint.v')
    os=next(p for p in before if p.name=='rocev2_native_sq_endpoint.v')
    nt=next(p for p in after if p.name==ot.name);ns=next(p for p in after if p.name==os.name)
    top,sq=derivation.derive(ot.read_text(),os.read_text())
    if nt.read_text()!=top or ns.read_text()!=sq or \
       [p for p in after if p not in [nt,ns,derivation.FEC,derivation.FANOUT]]!=[p for p in before if p not in [ot,os]]:
        raise ValueError('only exact two native leaves plus same tested FEC/fanout allowed')
    gen=ROOT/hls['directory']/'project/solution1/syn/verilog'
    selected=[*after,*[ROOT/n for n in r['selected_HLS_data']]]
    if len(hls['generated_sha256'])!=207 or {p.name for p in selected if p.parent==gen}!=set(hls['generated_sha256']):
        raise ValueError('whole actual207-file HLS cohort, no mixed or stub core')
    if not generated['actual_one_metadata_engine_and_event_collector'] or \
       r['module_counts']['rocev2_fatal_event_mmio']!=1 or r['module_counts']['rocev2_fatal_event_fanout']!=1:
        raise ValueError('sole actual HLS/FEC/fanout namespaces required')
    return r,ids


def sources(path,run):
    r,ids=validate(path)
    src=[ROOT/n for n in r['selected_RTL']];data=[ROOT/n for n in r['selected_HLS_data']]
    before=dict(r['source_sha256'])
    for p in [*src,*data]:
        if digest(p)!=before[str(p.relative_to(ROOT))]:raise ValueError('changed actual FEC-native source:'+str(p))
    for p in [Path(__file__).resolve(),Path(derivation.__file__).resolve(),*[binding.record(n)for n in NAMES]]:
        before[str(p.relative_to(ROOT))]=digest(p)
    return src,data,before
