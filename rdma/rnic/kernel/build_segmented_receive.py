#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Private exact profile7 modules, gated by ALL34 actual corrected native cases.

Running-header compile/link only. Full incoming SEND/Immediate native success
is mandatory before building a matched cohort; no install/load/live API or
original-clock/physical qualification follows this build.
"""
import ast
from pathlib import Path
import build_segmented_immediate as base
import derive_segmented_receive_kernel as candidate


def runner_source():
    t=base.runner_source();once=candidate.once
    a=t.index('"""');b=t.index('"""',a+3)+3;t=t[:a]+'"""'+__doc__+'"""'+t[b:]
    t=once(t,'import derive_segmented_immediate_kernel as candidate','import derive_segmented_receive_kernel as candidate')
    t=once(t,"'verbs_segmented_immediate_wqe.c','verbs_segmented_immediate_wqe.h']))",
        "'verbs_segmented_immediate_wqe.c','verbs_segmented_immediate_wqe.h','wqe_segmented_receive.c','wqe_segmented_receive.h',"
        "'verbs_segmented_receive_wqe.c','verbs_segmented_receive_wqe.h']))")
    t=once(t,"prefix='segmented-immediate-kernel-frozen-'","prefix='segmented-receive-kernel-frozen-'")
    t=once(t,'private_segmented_profile=6,matched_RNC_features=32767,matched_CQC_features=127,',
        'private_segmented_profile=7,matched_RNC_features=65535,matched_CQC_features=255,matched_RQC_features=31,receive_buffer_max_bytes=1048576,')
    t=once(t,"wanted=['as02_segmented_immediate_wqe_validate'",
        "wanted=['as02_segmented_receive_wqe_validate','as02_segmented_receive_wqe_encode','as02_segmented_receive_wqe_decode',\n"
        "            'as02_segmented_receive_wqe_from_ib_recv_wr','as02_segmented_immediate_wqe_validate'")
    t=once(t,"len(native.get('tests',{}))!=32","len(native.get('tests',{}))!=34")
    t=once(t,"!=(32767,127)or not all(native.get(n)for n in ['large_READ_native_runtime','large_Immediate_native_runtime','all30_prior_cases_retained']):",
        "!=(65535,255)or not all(native.get(n)for n in ['large_READ_native_runtime','large_Immediate_native_runtime','all30_prior_cases_retained','all32_prior_cases_retained','incoming_segmented_SEND_Immediate_runtime']):")
    t=once(t,"raise ValueError('exact actual all30 native READ profile required')",
        "raise ValueError('exact actual all34 incoming SEND/Immediate and prior native cases required')")
    t=once(t,"    for field in ['source_sha256','artifact_sha256','RAM_artifact_sha256']:",
        "    prior=json.loads((ROOT/'results/2026-10-18/rocev2-rnic-segmented-receive-native-compat-001.json').read_text())\n"
        "    if set(native['tests'])!=set(prior['tests'])|{'LARGE_RX_SEND','LARGE_RX_SEND_IMM'} or any(v['exit']!=0 or v['seconds']>30 for v in native['tests'].values()):\n"
        "        raise ValueError('every exact prior case and both real incoming cases must pass unchanged30s bounds')\n"
        "    gate=ROOT/'rdma/rnic/fpga/derive_segmented_receive_continuation.py'\n"
        "    if native['source_sha256'].get(str(gate.relative_to(ROOT)))!=digest(gate):raise ValueError('exact corrected continuation source must be native-proved')\n"
        "    for field in ['source_sha256','artifact_sha256','RAM_artifact_sha256']:")
    ast.parse(t);return t


if __name__=='__main__':
    exec(compile(runner_source(),str(Path(__file__).resolve()),'exec'),dict(__name__='__main__',__file__=str(Path(__file__).resolve())))
