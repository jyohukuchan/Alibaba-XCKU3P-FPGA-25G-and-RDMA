#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Private profile8 modules ONLY after matching131071/511/13/63 native36.

Real running-header compile/link, no install/load. A source predicate/provider
pass or old65535 native success cannot qualify the new matched cohort.
Original180s build deadline, all native identities and all36 cases required.
"""
import ast
from pathlib import Path
import build_segmented_receive as base
import derive_segmented_write_kernel as candidate


def runner_source():
    t=base.runner_source();once=candidate.once
    a=t.index('"""');b=t.index('"""',a+3)+3;t=t[:a]+'"""'+__doc__+'"""'+t[b:]
    for old,new in [('import derive_segmented_receive_kernel as candidate','import derive_segmented_write_kernel as candidate'),
        ("prefix='segmented-receive-kernel-frozen-'","prefix='segmented-write-kernel-frozen-'"),
        ('private_segmented_profile=7,matched_RNC_features=65535,matched_CQC_features=255,matched_RQC_features=31,',
         'private_segmented_profile=8,matched_RNC_features=131071,matched_CQC_features=511,matched_RQC_features=63,matched_SQC_features=13,WRITE_notice_max_bytes=1048576,'),
        ("len(native.get('tests',{}))!=34","len(native.get('tests',{}))!=36"),
        ('!=(65535,255)or not all(native.get(n)','!=(131071,511)or not all(native.get(n)'),
        ("'incoming_segmented_SEND_Immediate_runtime']):","'incoming_segmented_SEND_Immediate_runtime','incoming_segmented_WRITE_runtime','all34_prior_cases_retained','private_WRITE_profile_identity']):"),
        ("raise ValueError('exact actual all34 incoming SEND/Immediate and prior native cases required')",
         "raise ValueError('exact matching new profile8 and all36 native WRITE/Immediate cases required')"),
        ("{'LARGE_RX_SEND','LARGE_RX_SEND_IMM'}","{'LARGE_RX_SEND','LARGE_RX_SEND_IMM','LARGE_RX_WRITE','LARGE_RX_WRITE_IMM'}")]:t=once(t,old,new)
    t=once(t,'    for field in [\'source_sha256\',\'artifact_sha256\',\'RAM_artifact_sha256\']:',
        "    if (native.get('SQC_features'),native.get('RQC_features'),native.get('software_profile'))!=(13,63,8):\n"
        "        raise ValueError('new exact SQ/RQ/software identity required')\n"
        "    if native.get('compile_limit_seconds')!=1200 or native.get('simulation_limit_seconds')!=30 or native.get('compilation_seconds',1201)>1200:\n"
        "        raise ValueError('original native compile/runtime bounds required')\n"
        "    for field in ['source_sha256','artifact_sha256','RAM_artifact_sha256']:")
    ast.parse(t);return t


if __name__=='__main__':
    exec(compile(runner_source(),str(Path(__file__).resolve()),'exec'),dict(__name__='__main__',__file__=str(Path(__file__).resolve())))
