#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Bind actual native ACK stall to metadata/status rendezvous and new C++ proof.

All140 prior outcomes/oracles and the original2000-call initialization gate
remain. The candidate is NOT generated/native/physical/timing qualified.
"""
import argparse
import json
from pathlib import Path
import re
import sys
import audit_segmented_receive as binding
import write_abort_scheduled_mac_native_fixture as fixture

ROOT=binding.ROOT;digest=binding.digest
sys.path.insert(0,str(ROOT/'rdma/rnic/hls'))
import segmented_write_abort_event_transport as candidate
from build_native_write_abort import verify_abort_evidence

PREIMAGE={1:'write-abort-ack-diagnostic-001-preimages-RlwO5MIE',
    2:'write-abort-ack-diagnostic-002-preimages-yhgEzJNA',3:'write-abort-ack-diagnostic-003-preimages-I5TCmWTn',
    4:'write-abort-ack-baseline-diagnostic-002-preimages-SwQxqee6'}
OBSERVER='rdma/rnic/tests/probe_write_abort_native_ack_diagnostic.py'


def diagnostic(name,number=None):
    p=binding.record(name);r=json.loads(p.read_text());count=0;resolved=[]
    for key,entries in r.items():
        if 'sha256'not in key or not isinstance(entries,dict):continue
        for n,h in entries.items():
            if not isinstance(h,str)or not re.fullmatch('[0-9a-f]{64}',h):raise ValueError('malformed diagnostic binding')
            path=Path(n)if Path(n).is_absolute()else ROOT/n
            if digest(path)!=h:
                if key!='source_sha256'or path!=ROOT/OBSERVER or number not in PREIMAGE:
                    raise ValueError('changed original diagnostic input:'+n)
                path=ROOT/'rdma/rnic/build'/PREIMAGE[number]/OBSERVER
                if digest(path)!=h:raise ValueError('missing exact observer preimage')
                resolved.append(str(path.relative_to(ROOT)))
            count+=1
    if not r['diagnostic_completed']or not r['original_assertions_unchanged']or r['signal_injection']or r['fresh_native40_qualified']:
        raise ValueError('actual original-object observation, not a replacement native proof, required')
    source=(ROOT/r['directory']/'observer.cpp').read_text()
    if re.search(r'rootp->\w+\s*(?:=|\+=|\+\+|-=|--)',source):raise ValueError('observer must never write DUT fields')
    return r,dict(report_sha256=digest(p),bindings_verified=count,exact_preimage_paths=resolved)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve all previous evidence')
    names=['write-abort-event-hls-001','write-abort-event-compat-001','retrans-meta-events-001',
        'write-abort-scheduled-hls-001','write-abort-scheduled-compat-001',
        'write-abort-scheduled-mac-native-full-001','write-psn-control-native-full-001',
        'write-abort-scheduled-generated-hls-001','write-abort-native-ack-baseline-startup-001',
        'write-abort-event-audit-startup-001','write-abort-event-generated-source-startup-001']
    records={};ids={}
    for n in names:records[n],ids[n]=binding.bindings(n)
    new,compat,unit,old,oldcompat,native,baseline,gen,startup,audit_startup,guard_startup=[records[n]for n in names]
    verify_abort_evidence(new)
    if not all(r['pass_test']for r in [new,compat,unit,old,oldcompat,baseline,gen])or any(r['pass_test']for r in [native,startup,audit_startup,guard_startup]):
        raise ValueError('exact success AND failure evidence required')
    fields=0
    for mode,t in old['tests'].items():
        for k,v in t.items():
            if k=='summaries'or'oracle'in k:
                if new['tests'][mode].get(k)!=v:raise ValueError('original140 outcome/oracle changed:'+mode+':'+k)
                fields+=1
    if fields!=160 or compat['summaries']!=oldcompat['summaries']:
        raise ValueError('all160 original fields and real legacy services required')
    if not unit['summary']['original_2000_call_admission_gate']or unit['summary']['normal_zero_reads']!=2001 or \
       unit['summary']['actual_out_of_range_fault_events']!=1:
        raise ValueError('real full reset sweep, every field and sticky actual-error event required')
    observations=[]
    for i in range(1,4):
        n=f'write-abort-native-ack-diagnostic-{i:03d}';d,ids[n]=diagnostic(n,i);observations.append(d)
        if d['exit']!=-6 or d['original_native_report']!=names[5]or not d['actual_original_failure_reproduced']:
            raise ValueError('same actual original failing case required')
    n='write-abort-native-ack-baseline-diagnostic-003';good,ids[n]=diagnostic(n)
    if good['exit']or good['original_native_report']!=names[6]:raise ValueError('actual old-object baseline required')
    n='write-abort-native-ack-baseline-diagnostic-002';mixed,ids[n]=diagnostic(n,4)
    mixed_log=(ROOT/mixed['directory']/'ack.log').read_text()
    if mixed['exit']or not any('AS02_ACK_OBSERVATION'in l and not l.startswith('AS02_ACK_OBSERVATION ')for l in mixed_log.splitlines()):
        raise ValueError('original mixed-output failure must remain intact, not silently stripped')
    original=ROOT/baseline['directory'];out=(ROOT/good['directory']/'ack.log').read_text()
    words,posted,frames,_=fixture.large_immediate_variant(5,0x89abcdef)
    fixture.verify_large_immediate(out,posted,frames,5,ROOT/good['directory'])
    last=observations[-1]['observations'][-1];prior=good['observations'][-1]
    prefix='HLS_retrans_meta_table_0_U0__DOT__'
    if last[prefix+'clear_complete']or last[prefix+'clear_index']!=1698 or \
       last['HLS_as02_request_retire_join_0_U0__DOT__phase_2']!=2 or \
       last['HLS_request_ack_consumed_U__DOT__empty_n']!=1 or last['rx_accepted_count']!=1 or \
       last['write_abort_quarantined']or last['HLS_abort_fault']or last['HLS_request_fault']:
        raise ValueError('real accepted ACK pending behind unfinished metadata init, not abort quarantine/fault, required')
    first_done=next(o['time_ps']for o in good['observations']if o[prefix+'clear_complete'])
    if first_done!=55600000 or prior[prefix+'clear_index']!=1999 or prior['tx_frame_count']!=3:
        raise ValueError('actual old initialization and complete three-packet baseline required')
    rtl=ROOT/gen['directory']/'project/solution1/syn/verilog/rocev2_native_write_abort_top.v'
    text=rtl.read_text()
    for token in ['assign retrans_meta_table_0_U0_ap_continue = mf_full_n;',
        'assign retrans_meta_table_0_U0_ap_start = 1\'b1;','mf_empty_n & ff_empty_n',
        'request_exh_fault_empty_n & request_app_fault_empty_n']:
        if token not in text:raise ValueError('actual scalar fault rendezvous evidence missing:'+token)
    source=ROOT/'rdma/rnic/build/native-write-abort-event-transport-001'
    actual=candidate.derive();before=candidate.parent.derive()
    if {n for n in actual if actual[n]!=before[n]}!={candidate.META}:raise ValueError('only metadata fault transport may change')
    for n,t in actual.items():
        if(source/'fns'/n).read_text()!=t:raise ValueError('actual new cohort not exact derived source:'+n)
    meta=actual[candidate.META];oldmeta=before[candidate.META]
    init=oldmeta[oldmeta.index('\tif (!clear_complete)'):oldmeta.index('\n\n\n    // Read back the SAME stored record')]
    if meta.count(init)!=1 or meta.count('meta_fault_events.write(1);return;')!=2 or 'if(request_fault)return;'not in meta:
        raise ValueError('same actual2000 sweep and both real fault sites, never repeated/synthetic status, required')
    inputs=[Path(__file__).resolve(),Path(candidate.__file__).resolve(),source/'source.json',source/'fns'/candidate.META,rtl]
    r=dict(scope=__doc__,audit_passed=True,evidence=ids,verified_bindings=sum(v['bindings_verified']for v in ids.values()),
        source_sha256={str(q.relative_to(ROOT)):digest(q)for q in inputs},
        actual_failed_native_observation=True,actual_unchanged_old_binary_baseline=True,
        original_native_failure_preserved=True,observer_startup_failure_preserved=True,
        actual_old_init_first_observed_complete_ps=first_done,new_init_at_failure_index=1698,
        actual_ack_consumed_pending=True,actual_request_join_waiting_for_stored_insert=True,
        actual_generated_metadata_ap_continue_is_scalar_fault_FIFO_full_n=True,
        candidate_only_metadata_fault_transport_changed=True,original_reset_sweep_identical=True,
        actual_CPP_cases=140,all140_original_summary_and_oracle_fields_identical=fields,
        real_legacy_service_compatibility=True,real_metadata_event_component=True,
        candidate_generated_HLS=False,candidate_native_runtime=False,full_board_timing=False,hardware_verified=False,
        overall_goal_complete=False,hardware_or_default_actions=[],commit_or_push=False,
        remaining=['Generate actual event-status HLS; verify sole real RAM/event collector and original ports/geometry/reset.',
            'Fresh native40, all38 old complete outcomes and fatal61/62, original1200s/30s/4ns gates.',
            'All original11/fatal63/error CQ/STOP/lifetimes/recovery/timing/physical remain.'])
    with a.report.open('x')as f:f.write(json.dumps(r,indent=2)+'\n')
    print(json.dumps(dict(audit_passed=True,verified_bindings=r['verified_bindings'],CPP_cases=140,old_fields_identical=fields,candidate_native_runtime=False)))


if __name__=='__main__':main()
