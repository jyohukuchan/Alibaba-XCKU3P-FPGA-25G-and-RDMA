#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Scope WRITE-abort admission/checkpoint work to its actual parser states.

The first abort core emits a large set of repeated pipeline predicates across
unrelated receive states. Keep every owner/checkpoint/table/clear check, but
service the retired checkpoint at META and WRITE_ABORT_FENCE and accept abort
owners only in META. No fabricated proof, relaxed timing or QP/global drain.
This is a separate, unqualified source cohort, never an in-place RTL rewrite.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import segmented_write_abort_transport as parent

ROOT=parent.ROOT;CPP=parent.CPP;NAME=parent.NAME;once=parent.once
PARENT=ROOT/'rdma/rnic/build/native-write-abort-transport-002'

CHECKPOINT=r'''
        // Same actual WRITE-retirement producer and full owner validation.
        // The parser can consume a late checkpoint while waiting in FENCE.
        if(!write_retired.empty()) {
            auto p=write_retired.read();
            if(!as02_write_owner_valid(p.owner)) {abort_fault=true;regWriteAbortFault=1;return;}
            ap_uint<24> q=p.owner.token(423,400);abort_checkpoint[q]=p;abort_checkpoint_valid[q]=true;
        }
'''


def derive():
    out=parent.derive();t=out[CPP]
    # Owner admission was already permitted ONLY in META. Move that entire
    # unchanged predicate/body under the actual case, not a global pipelined
    # early-return branch replicated into every other parser state.
    marker='    if(pe_fsmState==META && !read_active && s_axis_write_owner.empty() && !s_axis_write_abort_owner.empty()) {'
    if parent.ADMISSION.count(marker)!=1:raise ValueError('exact original abort admission required')
    admission=parent.ADMISSION[parent.ADMISSION.index(marker):]
    admission=once(admission,marker,
        '        if(!read_active && s_axis_write_owner.empty() && !s_axis_write_abort_owner.empty()) {')
    t=once(t,parent.ADMISSION,'    if(abort_fault)return;\n')
    # Select the switch belonging to rx_exh_fsm, never another META state.
    a=t.index('void rx_exh_fsm(');b=t.index('\n}',a)+2
    body=t[a:b]
    body=once(body,'\tcase META:', '\tcase META:\n'+CHECKPOINT+admission)
    body=once(body,'    case WRITE_ABORT_FENCE: {',
        '    case WRITE_ABORT_FENCE: {\n'+CHECKPOINT)
    t=t[:a]+body+t[b:];out[CPP]=t
    return out


def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():p.error('preserve all earlier cohorts')
    info=json.loads((PARENT/'source.json').read_text());original=parent.derive()
    if info['HLS_top']!=NAME:raise ValueError('exact actual abort-core parent required')
    before={str(q.relative_to(ROOT)):digest(q)for q in PARENT.rglob('*')if q.is_file()}
    for n,h in info['derived_sources'].items():
        if digest(PARENT/'fns'/n)!=h or hashlib.sha256(original[n].encode()).hexdigest()!=h:
            raise ValueError('actual original abort source changed:'+n)
    files=derive()
    if {n for n in files if files[n]!=original[n]}!={CPP}:
        raise ValueError('only parser-state scheduling may change')
    shutil.copytree(PARENT/'fns',a.output/'fns');shutil.copytree(PARENT/'adapter',a.output/'adapter')
    for n,t in files.items():(a.output/'fns'/n).write_text(t)
    for n,h in before.items():
        if digest(ROOT/n)!=h:raise ValueError('parent changed during derivation:'+n)
    result=dict(info,scope=__doc__,parent_source=str(PARENT),scheduled_parent_tree_sha256=before,
        generator_sha256=digest(__file__),derived_sources={n:hashlib.sha256(t.encode()).hexdigest()for n,t in files.items()},
        abort_control_scoped_to_META_and_FENCE=True,late_actual_checkpoint_still_consumed_in_FENCE=True,
        owner960_receipt992_and_original_validation_unchanged=True,
        actual_CPP_runtime=False,generated_HLS=False,native_integration=False,hardware_verified=False,full_board_timing=False)
    (a.output/'source.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(output=str(a.output),HLS_top=NAME,source_only=True)))


if __name__=='__main__':main()
