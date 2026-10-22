# SPDX-License-Identifier: BSD-2-Clause-Views
"""Exact optional FEC31/RQC source graph; never reuse the FEC15 native binary."""
from pathlib import Path
import audit_segmented_receive as binding
import check_fatal_rq_cancel_native as checker

ROOT=binding.ROOT;digest=binding.digest
ELABORATION=binding.record('fatal-rq-cancel-native-elaboration-001')
BASELINE=binding.record('fatal-event-native-full-001')
NAMES=['fatal-rq-cancel-native-elaboration-001','fatal-rq-cancel-native-source-diagnostics-001',
    'fatal-event-native-full-001','fatal-event-native-runtime-diagnostics-001','fatal-rq-authority-001']


def validate(path):
    if path!=ELABORATION:raise ValueError('exact qualified fatal-RQC source cohort001 required')
    records={};ids={}
    for n in NAMES:records[n],ids[n]=binding.bindings(n)
    r,audit,old,runtime,component=[records[n]for n in NAMES]
    if not all(v.get('pass_test',v.get('audit_passed'))for v in records.values())or \
       len(old['tests'])!=40 or len(component['tests'])!=33 or not component['four_state']:
        raise ValueError('actual native40/authority33 and complete source audit required')
    for key in ['full_native_elaboration','whole_qualified_HLS207_unchanged',
        'only_RQC_command4_quarantine_distinction','permanent_configuration_and_admission_quarantine_preserved',
        'actual_upstream_join_handshake_after_both_receivers','both_global_HLS_drains_zero']:
        if r.get(key)is not True:raise ValueError('actual reviewed complete graph contract missing:'+key)
    if r['actual_new_native_packet_runtime']or r['actual_RQC_cancellation_receipt']or \
       r['default_or_driver_capability_changed']or (r['FEC_features'],r['RNC_features'],r['CQC_features'],r['software_profile'])!=(31,131071,511,8):
        raise ValueError('source-only explicit FEC31/private profile8, never inferred native receipt')
    parent,_=checker.parent_source.validate(checker.parent_source.ELABORATION)
    before=[ROOT/n for n in parent['selected_RTL']];after=[ROOT/n for n in r['selected_RTL']]
    ot,os,oc,of=[next(p for p in before if p.name==n)for n in [
        'rocev2_native_rnic_endpoint.v','rocev2_native_sq_endpoint.v','rocev2_sq_control_regs.v','rocev2_fatal_event_mmio.v']]
    nt,ns,nc,nf=[next(p for p in after if p.name==n)for n in [ot.name,os.name,'rocev2_fatal_rq_control_regs.v',of.name]]
    if [p.read_text()for p in [nt,ns,nc,nf]]!=list(checker.candidate.derive(*[p.read_text()for p in [ot,os,oc,of]])):
        raise ValueError('same exact four generated leaves required')
    replace={ot:nt,os:ns,of:nf}
    if after!=[replace.get(p,p)for p in before]+[nc,checker.candidate.AUTHORITY]or len(after)!=465:
        raise ValueError('complete465 RTL graph with original SQC definition retained required')
    return r,ids


def sources(path,run):
    r,ids=validate(path)
    src=[ROOT/n for n in r['selected_RTL']];data=[ROOT/n for n in r['selected_HLS_data']]
    before=dict(r['source_sha256'])
    for p in [*src,*data]:
        if digest(p)!=before[str(p.relative_to(ROOT))]:raise ValueError('changed actual fatal-RQC input:'+str(p))
    for p in [Path(__file__).resolve(),Path(checker.__file__).resolve(),Path(checker.candidate.__file__).resolve(),
              *[binding.record(n)for n in NAMES]]:
        before[str(p.relative_to(ROOT))]=digest(p)
    return src,data,before
