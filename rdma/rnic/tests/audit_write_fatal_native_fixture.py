#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Exact old38/new40 authored native fixture and raw inputs, NOT runtime."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import textwrap
import audit_segmented_receive as binding
import audit_segmented_write_rnr_native_sources as recipes
import write_fatal_native_fixture as fixture
import probe_write_fatal_native_full as runner
import write_fatal_native_sources as selection
ROOT=binding.ROOT;digest=binding.digest


def rendered_inputs(source,case):
    ns=dict(__name__='native_fixture_preflight_only',__file__=str(Path(runner.__file__).resolve()))
    exec(compile(source,'<read-only descriptor module>','exec'),ns)
    ns.update(zip(['name','opcode','immediate','args','zero','capacity'],case))
    a=source.index('            is_fatal=');b=source.index('            for n,t in inputs.items():',a)
    exec(compile(textwrap.dedent(source[a:b]),'<pure authored case inputs>','exec'),ns)
    return ns['inputs']


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve earlier evidence')
    names=['write-fatal-native-elaboration-001','write-fatal-native-source-diagnostics-001',
        'write-abort-generated-diagnostics-001','write-psn-control-native-full-001','write-psn-control-native-runtime-diagnostics-001']
    records={};ids={}
    for n in names:records[n],ids[n]=binding.bindings(n)
    elab,audit,generated,old,runtime=[records[n]for n in names]
    if not all(r.get('pass_test',r.get('audit_passed'))for r in records.values())or len(old['tests'])!=38:
        raise ValueError('actual new hierarchy/same source audit/generated208 and old38 runtime required')
    selection.sources(selection.ELABORATION,None)
    oldbench=fixture.parent.bench();newbench=fixture.bench();olddir=ROOT/old['directory']
    if (olddir/'tb.v').read_text()!=oldbench:raise ValueError('exact actually executed old38 bench required')
    fatal=lambda s:set(re.findall(r'\$fatal\([^,]+,"([^"]+)',s))
    if len(fatal(oldbench))!=391 or fatal(oldbench)-fatal(newbench):raise ValueError('all391 original fatal checks must remain')
    paths=[ROOT/n for n in old['source_sha256']if n.endswith('/native_runner.py')]
    if len(paths)!=1:raise ValueError('one actual frozen old38 runner required')
    oldcases=recipes.cases(paths[0].read_text());current=runner.runner_source();newcases=recipes.cases(current)
    if len(oldcases)!=38 or len(newcases)!=40 or newcases[2:]!=oldcases or set(old['tests'])!={v[0]for v in oldcases}:
        raise ValueError('all38 old exact recipes/order/opcodes/flags/zero/capacity required')
    wanted=[('LARGE_RX_WRITE_FATAL_ACCESS',9,0x89abcdef,['+LARGE_WRITE_RX','+LARGE_RX_OP=5','+WRITE_FATAL_ACCESS'],False,-3),
        ('LARGE_RX_WRITE_FATAL_PARTIAL',9,0x89abcdef,['+LARGE_WRITE_RX','+LARGE_RX_OP=5','+WRITE_FATAL_PARTIAL'],False,-3)]
    if newcases[:2]!=wanted:raise ValueError('two genuine native fatal access/partial cases required')
    old_inputs={}
    for case in oldcases:
        content=rendered_inputs(current,case);hashes={n:hashlib.sha256(t.encode()).hexdigest()for n,t in content.items()}
        if hashes!=old['tests'][case[0]]['runtime_input_sha256']:raise ValueError('old raw case input changed:'+case[0])
        old_inputs[case[0]]=hashes
    added={}
    for case,partial in zip(newcases[:2],[False,True]):
        content=rendered_inputs(current,case);bad=content.pop('write-fatal-input.hex');words,frame=fixture.fatal_input(partial)
        if bad!=''.join(f'{w:037x}\n'for w in words):raise ValueError('actual authored fatal input mismatch')
        if {n:hashlib.sha256(t.encode()).hexdigest()for n,t in content.items()}!=old['tests']['LARGE_RX_WRITE_IMM']['runtime_input_sha256']:
            raise ValueError('genuine exact original positive frames/RQ descriptor inputs required')
        _,_,_,_,frames=fixture.large_write_variant(True)
        if not partial:
            if int.from_bytes(frame[14+48:14+52],'big')!=9 or frame[14+37:14+40]!=bytes.fromhex('987654'):
                raise ValueError('independent wrong FULL RKEY/currentPSN FIRST required')
            if frame[:14+48]!=frames[0][:14+48]or frame[14+52:-4]!=frames[0][14+52:-4]:
                raise ValueError('only key and actual ICRC may differ in invalid-key FIRST')
        elif frame[14+28]!=7 or int.from_bytes(frame[14+37:14+40],'big')!=0x987655 or len(frame)!=4138:
            raise ValueError('actual current-PSN short nonterminal MID, not a PSN18 shortcut required')
        added[case[0]]=dict(frame_hex=frame.hex(),input_sha256=hashlib.sha256(bad.encode()).hexdigest(),words=len(words),partial=partial)
    if fixture.large_write_variant is not fixture.parent.large_write_variant or 'force 'in newbench:
        raise ValueError('old raw generator unchanged; no internal proof/PSN/owner/DMA injection')
    for fn in ['future_input','verify_large_write_psn','verify_large_write_rnr','verify_large_write','verify_large_receive',
        'verify_large','verify_large_read','verify_large_immediate','verify_rq','verify_atomic','verify_zero','verify_nonce']:
        if getattr(fixture,fn)is not getattr(fixture.parent,fn):raise ValueError('old independent oracle changed:'+fn)
    for token in ["if shutil.disk_usage(ROOT).free<1024**3:","if shutil.disk_usage('/dev/shm').free<4*1024**3:",
        'simulation_limit_seconds=30,compile_limit_seconds=1200','timeout=180','--output-split-cfuncs','500000',"'-j','4'",
        "preflight['exact_new_runner_sha256']","preflight['exact_new_bench_sha256']"]:
        if token not in current:raise ValueError('original deadline/resource/clock/parallelism/strict binding missing:'+token)
    if newbench.count('repeat(1100)')<oldbench.count('repeat(1100)')or 'repeat(71)'not in newbench or \
       '.m_write_fatal_selected(m_write_fatal_selected)'not in newbench or 'FATAL_NATIVE_ABORT_DONE'not in newbench:
        raise ValueError('real old MAC stalls and new actual selected/HLS/cancel boundary required')
    for n,h in binding.PROTECTED.items():
        if digest(ROOT/n)!=h:raise ValueError('original protected raw source changed:'+n)
    inputs=[Path(__file__).resolve(),Path(fixture.__file__).resolve(),Path(runner.__file__).resolve(),Path(selection.__file__).resolve()]
    result=dict(scope=__doc__,audit_passed=True,evidence=ids,verified_bindings=sum(v['bindings_verified']for v in ids.values()),
        all38_case_recipes_and_raw_inputs_identical=True,old38_runtime_inputs=old_inputs,
        old38_input_sha256={str((olddir/(case+'-'+n)).relative_to(ROOT)):h for case,entries in old_inputs.items()for n,h in entries.items()},
        original_fatal_messages_retained=len(fatal(oldbench)),new_fatal_messages=len(fatal(newbench)-fatal(oldbench)),
        planned_native_cases=40,new_cases=wanted,new_fatal_inputs=added,genuine_original_positive_frames_and_zero_RQ_records=True,
        exact_new_bench_sha256=hashlib.sha256(newbench.encode()).hexdigest(),exact_new_runner_sha256=hashlib.sha256(current.encode()).hexdigest(),
        compile_limit_seconds=1200,runtime_limit_seconds=30,FPGA_clock_ns=4,root_guard_bytes=1024**3,RAM_guard_bytes=4*1024**3,
        source_sha256={str(n.relative_to(ROOT)):digest(n)for n in inputs},protected_raw_sha256=binding.PROTECTED,
        actual_new_native_runtime=False,hardware_verified=False,full_board_timing=False,overall_goal_complete=False,
        remaining=['Fresh all40 actual new binary execution, exact old38 outcomes and actual full wire/backend/HLS/cancel/RQ/quarantine proofs for61/62.',
            'Original all11/fatal63/error CQ/STOP/lifetime/full1MiB/multiSGE/live refs/real-peer recovery/congestion/original timing/physical remain.'],
        hardware_or_default_actions=[],commit_or_push=False)
    with a.report.open('x')as f:f.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(audit_passed=True,verified_bindings=result['verified_bindings'],old_cases=38,planned_cases=40,native_runtime=False)))


if __name__=='__main__':main()
