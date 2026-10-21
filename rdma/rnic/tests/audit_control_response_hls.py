#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual control CPP105/legacy RTL compatibility, not generated/native proof.

Original87 outcomes/oracles, full480 owner/512 header receipt, genuine MSN1
and same actual PSN table are required. Preserve all original failures/gates.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import audit_segmented_receive as binding

ROOT=binding.ROOT;digest=binding.digest
sys.path.insert(0,str(ROOT/'rdma/rnic/hls'))
from build_native_control_response import verify_control_evidence

PREIMAGES={
 'control-response-hls-001':{'rdma/rnic/hls/test_control_response.cpp':'rdma/rnic/build/control-response-hls-001-preimages-eY693sKD'},
 'control-response-hls-002':{'rdma/rnic/hls/test_control_response.cpp':'rdma/rnic/build/control-response-hls-002-preimages-Q79yEJSF'},
}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve previous evidence')
    names=['control-response-hls-003','control-response-compat-001','segmented-write-owned-hls-001',
        'control-response-source-startup-001','control-response-builder-startup-001',*PREIMAGES]
    records={};ids={}
    for n in names:records[n],ids[n]=binding.bindings(n,PREIMAGES.get(n))
    cpp,compat,old=[records[n]for n in names[:3]]
    if not cpp['pass_test']or not cpp['source_unchanged']or not cpp['full_top_CPP_compiled']or not compat['pass_test']or \
       not compat['service_RTL_actual']or not compat['compatibility_runner_unchanged']:
        raise ValueError('real current105 CPP and unchanged actual legacy service RTL required')
    verify_control_evidence(cpp)
    if (cpp['compile_limit_seconds'],cpp['runtime_limit_seconds'])!=(600,30)or cpp['compile_seconds']>600 or \
       any(t['exit']or t['seconds']>30 for t in cpp['tests'].values()):raise ValueError('all original compile/runtime bounds required')
    if compat['compile_seconds']>600 or compat['simulation_seconds']>30:raise ValueError('original service compatibility bounds required')
    for n in names[3:]:
        if records[n]['pass_test']:raise ValueError('every original failure must stay failed:'+n)
    if records['control-response-hls-001']['tests']or len(records['control-response-hls-002']['tests'])!=101:
        raise ValueError('original fixture compile and hexadecimal-log failures must remain exact')
    failed=records['control-response-hls-002'];log=ROOT/failed['directory']/'control-bad10.log'
    if failed['tests']['control-bad10']['exit']or 'CONTROL_NEGATIVE a'not in log.read_text():
        raise ValueError('actual failed decimal witness retained, not a changed rejection assertion')
    source=ROOT/'rdma/rnic/build/native-control-response-transport-001';info=json.loads((source/'source.json').read_text())
    if info['HLS_top']!='rocev2_native_control_response_top'or (info['control_owner_bits'],info['control_receipt_bits'])!=(480,512)or \
       info['control_response_is_payload_completion']:
        raise ValueError('separate control480/512, never data execution authority')
    for n,h in info['derived_sources'].items():
        if digest(source/'fns'/n)!=h:raise ValueError('actual complete new source changed:'+n)
    for n,h in binding.PROTECTED.items():
        if digest(ROOT/n)!=h:raise ValueError('protected original raw source changed')
    inputs=[Path(__file__).resolve(),ROOT/'rdma/rnic/hls/segmented_control_response_transport.py',
        ROOT/'rdma/rnic/hls/test_control_response.cpp',ROOT/'rdma/rnic/hls/build_native_control_response.py',
        ROOT/'rdma/rnic/tests/probe_control_response_hls.py',ROOT/'rdma/rnic/tests/probe_control_response_compat.py',source/'source.json']
    check=subprocess.run(['bash','scripts/check.sh'],cwd=ROOT,capture_output=True,text=True,timeout=30)
    result=dict(scope=__doc__,audit_passed=True,evidence=ids,verified_bindings=sum(v['bindings_verified']for v in ids.values()),
        actual_CPP_modes=105,all87_original_summaries_and_independent_oracles_identical=True,
        compile_seconds=cpp['compile_seconds'],maximum_case_seconds=max(t['seconds']for t in cpp['tests'].values()),
        new_control_CPP_modes=18,control_ACK_headers=cpp['tests']['control-headers']['independent_control_oracles'],
        actual_MSN_from_existing_table=1,same_actual_PSN_table_unchanged=True,control_owner_bits=480,control_header_receipt_bits=512,
        actual_legacy_owned_service_RTL=True,compatibility_compile_seconds=compat['compile_seconds'],compatibility_runtime_seconds=compat['simulation_seconds'],
        source_sha256={str(q.relative_to(ROOT)):digest(q)for q in inputs},protected_raw_sha256=binding.PROTECTED,
        inherited_source_check=dict(exit=check.returncode,stdout=check.stdout,stderr=check.stderr,overall_suite_passed=check.returncode==0),
        primary_behavioral_references=[
            dict(url='https://raw.githubusercontent.com/torvalds/linux/v6.17/drivers/infiniband/sw/rxe/rxe_resp.c',
                used_for='check_psn/duplicate_request/prepare_ack_packet: future PSN NAK uses expected PSN; duplicate WRITE ACK uses last accepted PSN; AETH takes actual responder MSN; no Linux code copied.'),
            dict(url='https://github.com/torvalds/linux/blob/v6.17/drivers/infiniband/sw/rxe/rxe_hdr.h',
                used_for='AETH constants: duplicate unlimited ACK1f and NAK60/61/62/63; these are control responses, never memory execution grants.')],
        generated_HLS_qualified=False,native_control_response_integration=False,real_peer_or_physical=False,full_board_timing=False,overall_goal_complete=False,
        remaining=['Actual generated new480/512 core and original HLS clocks/geometry/legacy port gates; fresh native wiring/runtime of all37 old cases plus authenticated control/retry/duplicate cases.',
            'Native full-context authentication, fresh nonwrapping serial, exact typed control-HLS proof plus real MAC EOF/SFD/tail and same shared ACK allocator; fatal-QP quarantine/safe teardown must not be invented.',
            'All11/full1MiB native/multiSGE/live registered refs/real-peer NAK/RNR/MSN/congestion/partial-HLS cleanup/original timing/physical remain.'],
        hardware_or_default_actions=[],commit_or_push=False)
    with a.report.open('x')as f:f.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(audit_passed=True,verified_bindings=result['verified_bindings'],actual_CPP_modes=105,native_or_physical=False)),flush=True)


if __name__=='__main__':main()
