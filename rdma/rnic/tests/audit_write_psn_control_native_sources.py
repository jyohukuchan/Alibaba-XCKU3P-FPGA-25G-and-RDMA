#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Exact old37/new38 native fixture and all raw inputs, NOT packet runtime."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import textwrap
import audit_segmented_receive as binding
import audit_segmented_write_rnr_native_sources as recipes
import write_psn_control_native_fixture as fixture
import probe_write_psn_control_native_full as runner
import write_psn_control_native_sources as selection

ROOT=binding.ROOT;digest=binding.digest


def rendered_inputs(source,case):
    ns=dict(__name__='native_fixture_preflight_only',__file__=str(Path(runner.__file__).resolve()))
    exec(compile(source,'<read-only descriptor module>','exec'),ns)
    ns.update(zip(['name','opcode','immediate','args','zero','capacity'],case))
    a=source.index('            is_large_write=');b=source.index('            for n,t in inputs.items():',a)
    exec(compile(textwrap.dedent(source[a:b]),'<pure authored case inputs>','exec'),ns)
    return ns['inputs']


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve previous evidence')
    names=['write-psn-control-native-elaboration-001','write-psn-control-native-diagnostics-001',
        'segmented-write-rnr-native-full-002','segmented-write-rnr-native-runtime-diagnostics-001']
    records={};ids={}
    for n in names:records[n],ids[n]=binding.bindings(n)
    elab,audit,old,runtime=[records[n]for n in names]
    if not all(r.get('pass_test',r.get('audit_passed'))for r in records.values())or len(old['tests'])!=37:
        raise ValueError('actual new hierarchy/components and actual old37 runtime required')
    selection.sources(selection.ELABORATION,None)
    oldbench=fixture.parent.bench();newbench=fixture.bench();olddir=ROOT/old['directory']
    if (olddir/'tb.v').read_text()!=oldbench:raise ValueError('exact actually executed old37 bench required')
    fatal=lambda s:set(re.findall(r'\$fatal\([^,]+,"([^"]+)',s))
    if len(fatal(oldbench))!=378 or fatal(oldbench)-fatal(newbench):raise ValueError('all378 original fatal messages required')
    oldrunner=next(ROOT/n for n in old['source_sha256']if n.endswith('/native_runner.py'))
    previous=oldrunner.read_text();current=runner.runner_source()
    oldcases=recipes.cases(previous);newcases=recipes.cases(current)
    if len(oldcases)!=37 or len(newcases)!=38 or newcases[1:]!=oldcases or set(old['tests'])!={v[0]for v in oldcases}:
        raise ValueError('all37 exact old recipes/order/opcodes/args/zero/capacity required')
    if newcases[0]!=('LARGE_RX_WRITE_PSN',9,0x89abcdef,['+LARGE_WRITE_RX','+LARGE_RX_OP=5','+WRITE_PSN_CONTROL'],False,-3):
        raise ValueError('genuine Immediate/RQ native NAK/retry/duplicate case required')
    old_inputs={}
    for case in oldcases:
        content=rendered_inputs(current,case);hashes={n:hashlib.sha256(t.encode()).hexdigest()for n,t in content.items()}
        if hashes!=old['tests'][case[0]]['runtime_input_sha256']:raise ValueError('old raw case input changed:'+case[0])
        old_inputs[case[0]]=hashes
    added=rendered_inputs(current,newcases[0]);future=added.pop('write-psn-future-input.hex')
    if {n:hashlib.sha256(t.encode()).hexdigest()for n,t in added.items()}!=old['tests']['LARGE_RX_WRITE_IMM']['runtime_input_sha256']:
        raise ValueError('actual same original positive frames/RQ records required')
    words,frame=fixture.future_input()
    if future!=''.join(f'{w:037x}\n'for w in words)or int.from_bytes(frame[14+37:14+40],'big')!=0x987658:
        raise ValueError('independent futurePSN input required')
    if fixture.large_write_variant is not fixture.parent.large_write_variant or 'force 'in newbench:
        raise ValueError('unchanged old raw generator and no internal authority injection required')
    for function in ['verify_large_write_rnr','verify_large_write','verify_large_receive','verify_large','verify_large_read','verify_large_immediate','verify_rq','verify_atomic','verify_zero']:
        if getattr(fixture,function)is not getattr(fixture.parent,function):raise ValueError('old independent oracle changed:'+function)
    for token in ["if shutil.disk_usage(ROOT).free<1024**3:","if shutil.disk_usage('/dev/shm').free<4*1024**3:",
        'simulation_limit_seconds=30,compile_limit_seconds=1200',"timeout=180",'--output-split-cfuncs','500000']:
        if token not in current:raise ValueError('original native source/clock/deadline/resource gate missing:'+token)
    if 'repeat(1100)'not in newbench or 'repeat(71)'not in newbench or "16'h6005"not in newbench:
        raise ValueError('actual LAST receipt and independent local-error stalls must remain')
    for n,h in binding.PROTECTED.items():
        if digest(ROOT/n)!=h:raise ValueError('protected original raw source changed:'+n)
    sources=[Path(__file__).resolve(),Path(fixture.__file__).resolve(),Path(runner.__file__).resolve(),Path(selection.__file__).resolve()]
    result=dict(scope=__doc__,audit_passed=True,evidence=ids,verified_bindings=sum(v['bindings_verified']for v in ids.values()),
        all37_case_recipes_and_raw_inputs_identical=True,old37_runtime_inputs=old_inputs,
        old37_input_sha256={str((olddir/(case+'-'+n)).relative_to(ROOT)):h for case,entries in old_inputs.items()for n,h in entries.items()},
        original_fatal_messages_retained=len(fatal(oldbench)),new_fatal_messages=len(fatal(newbench)-fatal(oldbench)),
        planned_native_cases=38,new_case=newcases[0],genuine_original_positive_frames_and_zero_RQ_records=True,
        new_future_frame_hex=frame.hex(),new_future_input_sha256=hashlib.sha256(future.encode()).hexdigest(),
        exact_new_bench_sha256=hashlib.sha256(newbench.encode()).hexdigest(),exact_new_runner_sha256=hashlib.sha256(current.encode()).hexdigest(),
        compile_limit_seconds=1200,runtime_limit_seconds=30,FPGA_clock_ns=4,root_guard_bytes=1024**3,RAM_guard_bytes=4*1024**3,
        source_sha256={str(n.relative_to(ROOT)):digest(n)for n in sources},protected_raw_sha256=binding.PROTECTED,
        actual_new_native_runtime=False,hardware_verified=False,full_board_timing=False,overall_goal_complete=False,
        remaining=['Fresh native38 actual execution; all37 old raw/summary results plus full wire/owner/MAC/host/PSN/RQ/CQ proof for NAK/suppression/retry/duplicate.',
            'All original11/full1MiB/multiSGE/proper fatal-QP teardown/live refs/real-peer recovery/congestion/original timing/physical remain.'],
        hardware_or_default_actions=[],commit_or_push=False)
    with a.report.open('x')as f:f.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(audit_passed=True,verified_bindings=result['verified_bindings'],old_cases=37,planned_cases=38,native_runtime=False)))


if __name__=='__main__':main()
