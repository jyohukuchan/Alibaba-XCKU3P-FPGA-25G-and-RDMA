# SPDX-License-Identifier: BSD-2-Clause-Views
"""Select exact lease-only RX export graph, never the original failed binary."""
from pathlib import Path
import audit_segmented_receive as binding
import check_fatal_rq_lease_native as checker

ROOT=binding.ROOT;digest=binding.digest
ELABORATION=binding.record('fatal-rq-lease-native-elaboration-001')
BASELINE=binding.record('fatal-event-native-full-001')
NAMES=['fatal-rq-lease-native-elaboration-001','fatal-rq-lease-native-source-diagnostics-001',
    'fatal-rq-cancel-failure-diagnostics-001','fatal-event-native-full-001','fatal-event-native-runtime-diagnostics-001',
    'fatal-rq-cancel-native-elaboration-001','fatal-event-native-elaboration-002']


def validate(path):
    if path!=ELABORATION:raise ValueError('exact new lease-export graph001 required')
    records={};ids={}
    for n in NAMES:records[n],ids[n]=binding.bindings(n)
    r,audit,failed,old,runtime,parent,original=[records[n]for n in NAMES]
    if not all(v.get('pass_test',v.get('audit_passed'))for v in records.values())or len(old['tests'])!=40 or \
       not failed['original_failed_run_still_false']or not failed['old40_full_outcomes_except_seconds_identical']:
        raise ValueError('original failure remains false, all40 old outcomes and exact new source qualification required')
    if r['actual_new_native_packet_runtime']or r['actual_RQC_cancellation_receipt']or \
       not audit['original_core_paged_and_aggregate_lease_guards_byte_identical']or \
       not audit['all_actual_RX_write_Atomic_memory_reference_work_retained']or not audit['live_control_owner_VALID_retained']:
        raise ValueError('source-only lease distinction, never weakened aggregate or inferred packet proof')
    if (r['FEC_features'],r['RNC_features'],r['CQC_features'],r['software_profile'])!=(31,131071,511,8)or \
       not r['both_global_HLS_drains_zero']or r['default_or_driver_capability_changed']:
        raise ValueError('original optional profile/clock/drain/default contract required')
    before=[ROOT/n for n in parent['selected_RTL']];after=[ROOT/n for n in r['selected_RTL']]
    previous={n:next(p for p in before if p.name==n)for n in checker.candidate.LEAVES}
    derived={n:next(p for p in after if p.name==n)for n in checker.candidate.LEAVES}
    original_top=next(ROOT/n for n in original['selected_RTL']if Path(n).name==checker.candidate.TOP)
    if {n:p.read_text()for n,p in derived.items()}!=checker.candidate.derive({n:p.read_text()for n,p in previous.items()},original_top.read_text()):
        raise ValueError('same exact seven-leaf actual lease export required')
    substitutions={previous[n]:derived[n]for n in previous}
    if after!=[substitutions.get(p,p)for p in before]or len(after)!=465 or r['module_counts']!=parent['module_counts']:
        raise ValueError('same sole actual complete native graph required')
    return r,ids


def sources(path,run):
    r,ids=validate(path);src=[ROOT/n for n in r['selected_RTL']];data=[ROOT/n for n in r['selected_HLS_data']]
    before=dict(r['source_sha256'])
    for p in [*src,*data]:
        if digest(p)!=before[str(p.relative_to(ROOT))]:raise ValueError('changed actual source:'+str(p))
    for p in [Path(__file__).resolve(),Path(checker.__file__).resolve(),Path(checker.candidate.__file__).resolve(),*[binding.record(n)for n in NAMES]]:
        before[str(p.relative_to(ROOT))]=digest(p)
    return src,data,before
