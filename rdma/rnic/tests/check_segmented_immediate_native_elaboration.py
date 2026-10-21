#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Complete actual large READ/WRITE/SEND/Immediate graph compile, not runtime.

Retain READ parent's strict source/width/shared-domain/module/drain/clock
checks. New exact32767/127 source profile and new actual HLS; no installed
kernel/provider, native payload/CQ execution, timing or physical claim.
"""
import ast
from pathlib import Path
import tempfile
import check_segmented_read_profile_native_elaboration as parent

ROOT=parent.ROOT


def runner_source():
    t=Path(parent.__file__).read_text();once=parent.source.candidate.once
    t=once(t,'import segmented_read_profile_native_sources as source','import segmented_immediate_native_sources as source')
    t=once(t,"BASE=ROOT/'results/2026-10-18/rocev2-rnic-segmented-read-lifetime-native-elaboration-001.json'",
        "BASE=ROOT/'results/2026-10-18/rocev2-rnic-segmented-read-command-queue-native-elaboration-001.json'")
    for old,new in [("prefix='read-profile-native-'","prefix='segmented-immediate-native-'"),
        ("prefix='as02-read-profile-native-'","prefix='as02-segmented-immediate-native-'"),
        ('RNC_features=16383,CQC_features=63','RNC_features=32767,CQC_features=127'),
        ("+op+'==2 || '+op+'==3) ? 1048576:4096)'","+op+'==2 || '+op+'==3 || '+op+'==5 || '+op+'==6) ? 1048576:4096)'"),
        ("'| 4096 | 8192;'","'| 4096 | 8192 | 16384;'"),("'8:rd=63;'","'8:rd=127;'")]:
        if old not in t:raise ValueError('strict new checker anchor missing:'+old)
        t=t.replace(old,new)
    t=once(t,"model=(ram/'native.vvp').read_text();wanted=base['module_counts']",
        "model=(ram/'native.vvp').read_text();wanted=dict(base['module_counts'])\n"
        "        if wanted.get('rocev2_native_segmented_read_top')!=1 or source.HLS in wanted:raise ValueError('exact original single HLS root required')\n"
        "        wanted['rocev2_native_segmented_read_top']=0;wanted[source.HLS]=1")
    metadata='large_READ_admission_open=True,READ_admission_limit=1048576,'
    if t.count(metadata)!=2:raise ValueError('both exact result/summary metadata anchors required')
    t=t.replace(metadata,metadata+'Immediate_admission_limit=1048576,receive_buffer_limit=4096,')
    ast.parse(t);return t


if __name__=='__main__':
    run=Path(tempfile.mkdtemp(prefix='segmented-immediate-native-runner-',dir=ROOT/'rdma/rnic/build'))
    frozen=run/'runner.py';frozen.write_text(runner_source())
    exec(compile(frozen.read_text(),str(frozen),'exec'),dict(__name__='__main__',__file__=str(frozen)))
