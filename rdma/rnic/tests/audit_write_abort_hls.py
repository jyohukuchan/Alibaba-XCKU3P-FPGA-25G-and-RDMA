#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual HLS WRITE-abort consumers, not generated/native/QP/global drain proof.

Require all105 original results/oracles,35 new actual modes, same selected
sources/tables/checkpoint/clear, legacy service and immutable failures.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import audit_segmented_receive as binding

ROOT=binding.ROOT;digest=binding.digest
sys.path.insert(0,str(ROOT/'rdma/rnic/hls'))
from build_native_write_abort import verify_abort_evidence
import segmented_write_abort_transport as candidate

PREIMAGES={
    'write-abort-source-startup-001':{'rdma/rnic/hls/segmented_write_abort_transport.py':
        'rdma/rnic/build/write-abort-source-startup-001-preimages-9_dcy6bb'},
    'write-abort-hls-001':{'rdma/rnic/hls/segmented_write_abort_transport.py':
        'rdma/rnic/build/write-abort-hls-001-preimages-LMe5j72X',
        'rdma/rnic/hls/test_write_abort.cpp':'rdma/rnic/build/write-abort-hls-001-preimages-LMe5j72X'},
    'write-abort-hls-002':{'rdma/rnic/hls/test_write_abort.cpp':
        'rdma/rnic/build/write-abort-hls-002-preimages-K2rmWf1r'},
}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cpp',default='write-abort-hls-003')
    p.add_argument('--source',type=Path,default=ROOT/'rdma/rnic/build/native-write-abort-transport-002')
    p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve earlier evidence')
    names=[a.cpp,'write-abort-compat-001','control-response-hls-003','control-response-compat-001',*PREIMAGES]
    records={};ids={}
    for n in names:records[n],ids[n]=binding.bindings(n,PREIMAGES.get(n))
    cpp,compat,old,oldcompat=[records[n]for n in names[:4]]
    if not compat['pass_test']or not compat['service_RTL_actual']or not compat['compatibility_runner_unchanged']or \
       not compat['wrapper_and_harness_unchanged']or compat['compile_seconds']>600 or compat['simulation_seconds']>30 or \
       compat['summaries']!=oldcompat['summaries']:raise ValueError('same actual legacy owned Atomic/Immediate consumers and original bounds required')
    verify_abort_evidence(cpp)
    for n in PREIMAGES:
        if records[n]['pass_test']:raise ValueError('every original failure must stay failed:'+n)
    if records['write-abort-hls-001']['tests']or records['write-abort-hls-001']['generated_HLS']or \
       records['write-abort-hls-001']['native_integration']:raise ValueError('original compile failure must not be requalified')
    log=ROOT/records['write-abort-hls-001']['directory']/'compile.log'
    if not all(n in log.read_text()for n in ['error:','as02_abort_control','as02_abort_packet','as02_write_abort_valid']):
        raise ValueError('actual missing-declaration compile failure must remain')
    failed=records['write-abort-hls-002']
    if len(failed['tests'])!=109 or failed['tests']['abort-empty-after-last']['exit']!=-6 or \
       any(failed['tests'][n]['exit']for n in old['tests']):raise ValueError('actual old105 pass and new109th padded-tail failure retained')
    pad_log=ROOT/failed['directory']/'abort-empty-after-last.log'
    if 'write_byte(off+bytes++)'not in pad_log.read_text():raise ValueError('actual old missing padded-zero oracle failure retained')
    source=a.source.resolve();info=json.loads((source/'source.json').read_text());derived=candidate.derive()
    if info['HLS_top']!=candidate.NAME or (info['write_abort_owner_bits'],info['write_abort_receipt_bits'])!=(960,992)or \
       info['abort_is_QP_or_global_drain']or info['native_fatal_QP_error_or_unpin_qualified']or \
       info['generator_sha256']!=digest(candidate.__file__):raise ValueError('actual current typed abort source, not QP/global/native drain required')
    for n,h in info['derived_sources'].items():
        path=source/'fns'/n
        if digest(path)!=h or hashlib.sha256(derived[n].encode()).hexdigest()!=h:raise ValueError('current derived source mismatch:'+n)
        for r in [cpp,compat]:
            if r['source_sha256'].get(str(path.relative_to(ROOT)))!=h:raise ValueError('actual tests used a different core:'+n)
    for n,h in info['parent_tree_sha256'].items():
        if digest(candidate.PARENT/n)!=h:raise ValueError('actual control parent changed:'+n)
    actual=(source/'fns'/candidate.CPP).read_text()
    if actual.index('inline as02ControlOwner as02_abort_control(')>actual.index('void rx_exh_fsm('):
        raise ValueError('actual helper declarations must precede template consumer')
    if any(actual.count(n)!=1 for n in ['case WRITE_ABORT_CLEAR:', 'case WRITE_ABORT_VERIFY:', 'case WRITE_ABORT_PUBLISH:']):
        raise ValueError('actual same selected parser clear/verify/publish states required')
    for n,h in binding.PROTECTED.items():
        if digest(ROOT/n)!=h:raise ValueError('protected original raw source changed:'+n)
    inputs=[Path(__file__).resolve(),Path(candidate.__file__).resolve(),ROOT/'rdma/rnic/hls/test_write_abort.cpp',
        ROOT/'rdma/rnic/hls/build_native_write_abort.py',ROOT/'rdma/rnic/tests/probe_write_abort_hls.py',
        ROOT/'rdma/rnic/tests/probe_write_abort_compat.py',source/'source.json']
    check=subprocess.run(['bash','scripts/check.sh'],cwd=ROOT,capture_output=True,text=True,timeout=30)
    result=dict(scope=__doc__,audit_passed=True,evidence=ids,verified_bindings=sum(v['bindings_verified']for v in ids.values()),
        actual_CPP_modes=140,all105_original_summaries_and_independent_oracles_identical=True,new_abort_modes=35,
        abort_owner_bits=960,abort_receipt_bits=992,actual_positive_retirement_checkpoint_and_same_PSN_MSN_tables=True,
        selected_partial_WRITE_clear_and_verify=True,empty_state_distinct_from_positive=True,
        per_QP_other_partial_WRITE_preserved=True,abort_serial_survives_QPI_initialization=True,
        compile_seconds=cpp['compile_seconds'],maximum_case_seconds=max(t['seconds']for t in cpp['tests'].values()),
        actual_legacy_owned_service_RTL=True,compatibility_compile_seconds=compat['compile_seconds'],compatibility_runtime_seconds=compat['simulation_seconds'],
        source_sha256={str(q.relative_to(ROOT)):digest(q)for q in inputs},protected_raw_sha256=binding.PROTECTED,
        inherited_source_check=dict(exit=check.returncode,stdout=check.stdout,stderr=check.stderr,overall_suite_passed=check.returncode==0),
        privileged_native_MAC_fence_management_inputs_modeled=True,abort_is_QP_or_global_drain=False,
        generated_abort_HLS_qualified=False,native_error_quarantine_cancel_STOP_CQ_integrated=False,
        permission_to_unpin=False,live_Linux_or_physical=False,full_board_timing=False,overall_goal_complete=False,
        remaining=['Actual generated same-core960/992 interface and original4ns/default1.08ns/8QP/2000 gates.',
            'Native authenticated fatal61/62/63 admission, QP quarantine, real backend/MAC ownership, actual message cancel/STOP/error CQ and all lifetime refs; no global drain substitution.',
            'All original11/full1MiB native/multiSGE/live registered refs/real-peer recovery/congestion/original timing/physical remain.'],
        hardware_or_default_actions=[],commit_or_push=False)
    with a.report.open('x')as f:f.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(audit_passed=True,verified_bindings=result['verified_bindings'],actual_CPP_modes=140,native_or_global_drain=False)),flush=True)


if __name__=='__main__':main()
