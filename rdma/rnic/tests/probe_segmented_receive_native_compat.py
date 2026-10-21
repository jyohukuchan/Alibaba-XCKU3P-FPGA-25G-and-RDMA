#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Fresh new generated receive-HLS native graph: every32 old runtime cases.

Retain all actual shared MR/PTE/DMA/nonce/status/fence/board-MAC/CQ and full
byte/owner/sentinel checks, original1200s build/30s runtime and4ns clocks.
This is whole-native OLD-function regression on the new graph, not proof of
new large incoming SEND/Immediate, installed Linux or physical operation.
No previous binary or object cache is used as new-source execution proof.
"""
import ast
from pathlib import Path
import tempfile
import probe_segmented_immediate_native_full as parent
import segmented_receive_native_sources as source

ROOT=source.ROOT;once=source.candidate.once


def runner_source():
    t=parent.runner_source();a=t.index('"""');b=t.index('"""',a+3)+3;t=t[:a]+'"""'+__doc__+'"""'+t[b:]
    for old,new in [
        ('import segmented_immediate_native_sources as source','import segmented_receive_native_sources as source'),
        ('import segmented_immediate_native_fixture as service','import segmented_receive_native_fixture as service'),
        ("evidence.get('HLS_top')!='rocev2_native_segmented_immediate_top'","evidence.get('HLS_top')!='rocev2_native_segmented_receive_top'"),
        ("!=(32767,127)or not all(evidence.get(n)","!=(65535,255)or not all(evidence.get(n)"),
        ("!=(1048576,4096):raise ValueError('exact Immediate/RQ limits required')","!=(1048576,1048576):raise ValueError('exact Immediate/large-RQ limits required')"),
        ('[source.parent.UNIT,*source.EVIDENCE.values()]','[source.parent.parent.UNIT,*source.parent.EVIDENCE.values(),*source.EVIDENCE.values()]'),
        ("prefix='segmented-immediate-native-full-'","prefix='segmented-receive-native-compat-'"),
        ("prefix='as02-segmented-immediate-native-obj-'","prefix='as02-segmented-receive-native-obj-'"),
        ("prefix='as02-segmented-immediate-native-artifacts-'","prefix='as02-segmented-receive-native-artifacts-'"),
        ('RNC_features=32767,CQC_features=127','RNC_features=65535,CQC_features=255')]:t=once(t,old,new)
    t=once(t,"    if evidence['module_counts'].get(source.HLS)!=1",
        "    if not evidence.get('full_native_elaboration')or evidence.get('unknown_leaves_ignored')or evidence['module_counts'].get(source.parent.HLS)!=0 or evidence['module_counts'].get('rocev2_receive_message_queue')!=1 or evidence.get('whole_receive_AXIS_bits')!=776:raise ValueError('exact actual new full native/HLS/message-RQ/whole port required')\n"
        "    if evidence['module_counts'].get(source.HLS)!=1")
    t=once(t,'actual_generated_HLS=True,','actual_generated_HLS=True,incoming_segmented_SEND_Immediate_runtime=False,new_receive_hierarchy_old32_regressions_only=True,')
    ast.parse(t);return t


if __name__=='__main__':
    run=Path(tempfile.mkdtemp(prefix='segmented-receive-native-runner-',dir=ROOT/'rdma/rnic/build'))
    frozen=run/'native_runner.py';frozen.write_text(runner_source())
    exec(compile(frozen.read_text(),str(frozen),'exec'),dict(__name__='__main__',__file__=str(frozen)))
