#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Exact old40 raw inputs/oracles/444 checks plus two real RQC receipt cases.

Preflight only; not successful new packet execution or CQ/STOP/global unpin.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import textwrap
import audit_segmented_receive as binding
import audit_segmented_write_rnr_native_sources as recipes
from audit_write_fatal_native_fixture import rendered_inputs as previous_inputs
import probe_fatal_event_native_full as previous_runner
import probe_fatal_rq_cancel_native_full as runner
import fatal_rq_cancel_native_fixture as fixture
import fatal_rq_cancel_native_sources as selection

ROOT=binding.ROOT;digest=binding.digest


def rendered_inputs(source,case):
    if '            is_fatal_cancel='not in source:return previous_inputs(source,case)
    ns=dict(__name__='native_fixture_preflight_only',__file__=str(Path(runner.__file__).resolve()))
    exec(compile(source,'<read-only new descriptors>','exec'),ns)
    ns.update(zip(['name','opcode','immediate','args','zero','capacity'],case))
    a=source.index('            is_fatal_cancel=');b=source.index('            for n,t in inputs.items():',a)
    exec(compile(textwrap.dedent(source[a:b]),'<pure new authored case inputs>','exec'),ns)
    return ns['inputs']


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve earlier evidence')
    names=['fatal-rq-cancel-native-elaboration-001','fatal-rq-cancel-native-source-diagnostics-001',
        'fatal-event-native-full-001','fatal-event-native-runtime-diagnostics-001',
        'fatal-event-native-fixture-diagnostics-001']
    records={};ids={}
    for n in names:records[n],ids[n]=binding.bindings(n)
    elab,source,old,runtime,prior=[records[n]for n in names]
    if not all(r.get('pass_test',r.get('audit_passed'))for r in records.values())or len(old['tests'])!=40:
        raise ValueError('actual old40 and new complete source qualification required')
    selection.sources(selection.ELABORATION,None)
    before=fixture.parent.bench();bench=fixture.bench();run=ROOT/old['directory']
    if (run/'tb.v').read_text()!=before:raise ValueError('exact actual executed FEC-native40 bench required')
    restored=bench.replace('module tb;\n'+fixture.additions(before),'module tb;',1)
    restored=restored.replace(' if(runtime_fatal_rq_cancel)run_write_fatal_rq_cancel();else run_write_fatal_native();',
        ' run_write_fatal_native();',1)
    restored=restored.replace('if(value!==31)$fatal(1,"FEC actual native aperture features");',
        'if(value!==15)$fatal(1,"FEC actual native aperture features");',1)
    if restored!=before or 'force 'in bench:raise ValueError('all old bench retained except explicit FEC31 read; no DUT force')
    fatal=lambda s:set(re.findall(r'\$fatal\([^,]+,"([^"]+)',s))
    if len(fatal(before))!=444 or fatal(before)-fatal(bench):raise ValueError('every original419 plus25 FEC check required')
    previous=previous_runner.runner_source();current=runner.runner_source()
    oldcases=recipes.cases(previous);cases=recipes.cases(current)
    if len(cases)!=42 or cases[:40]!=oldcases:raise ValueError('all40 exact original recipes/order must remain')
    newcases=[('FATAL_RQC_ACCESS',9,0x89abcdef,['+LARGE_WRITE_RX','+LARGE_RX_OP=5','+WRITE_FATAL_ACCESS','+FATAL_RQ_CANCEL'],False,-3),
        ('FATAL_RQC_PARTIAL',9,0x89abcdef,['+LARGE_WRITE_RX','+LARGE_RX_OP=5','+WRITE_FATAL_PARTIAL','+FATAL_RQ_CANCEL'],False,-3)]
    if cases[40:]!=newcases:raise ValueError('two explicit genuine fatal RQC scenarios required')
    raw={}
    for case in cases:
        content=rendered_inputs(current,case);raw[case[0]]={n:hashlib.sha256(t.encode()).hexdigest()for n,t in content.items()}
        if case in oldcases and (content!=rendered_inputs(previous,case)or raw[case[0]]!=old['tests'][case[0]]['runtime_input_sha256']):
            raise ValueError('actual old authored packet/descriptor byte changed:'+case[0])
    for new,oldname in [('FATAL_RQC_ACCESS','LARGE_RX_WRITE_FATAL_ACCESS'),('FATAL_RQC_PARTIAL','LARGE_RX_WRITE_FATAL_PARTIAL')]:
        if raw[new]!=raw[oldname]:raise ValueError('new cancellation uses exact actual old raw fatal packets/descriptors')
    for fn in ['fatal_input','future_input','verify_fatal','verify_large_write_psn','verify_large_write_rnr','verify_large_write',
        'verify_large_receive','verify_large','verify_large_read','verify_large_immediate','verify_rq','verify_atomic','verify_zero','verify_nonce']:
        if getattr(fixture,fn)is not getattr(fixture.parent,fn):raise ValueError('old independent generator/oracle changed:'+fn)
    for token in ["if shutil.disk_usage(ROOT).free<1024**3:","if shutil.disk_usage('/dev/shm').free<4*1024**3:",
        'simulation_limit_seconds=30,compile_limit_seconds=1200','timeout=180',"'-j','4'",'--output-split-cfuncs','500000',"'-CFLAGS','-O1'",
        "preflight['exact_new_runner_sha256']","preflight['exact_new_bench_sha256']"]:
        if token not in current:raise ValueError('original preflight/resource/compile/runtime gate missing:'+token)
    for token in ['repeat(77)','repeat(71)','repeat(1100)','stall<1100','fatal_rqc_cancel_handshakes!=1',
        'read_reg(24\'h405140,value)','value!==63','RQC.snapshot[1]==4'.replace('RQC.',fixture.RQC+'.')]:
        if token not in bench:raise ValueError('original withholding/new actual cancel/full reply proof missing:'+token)
    # The entire old task, including its original post-error replay, remains.
    aa=before.index('task run_write_fatal_native;');bb=before.index('endtask',aa)+7
    if before[aa:bb]not in bench:raise ValueError('old fatal control/replay task must stay byte-identical')
    for n,h in binding.PROTECTED.items():
        if digest(ROOT/n)!=h:raise ValueError('protected original raw source changed:'+n)
    inputs=[Path(__file__).resolve(),Path(runner.__file__).resolve(),Path(selection.__file__).resolve(),Path(fixture.__file__).resolve()]
    r=dict(scope=__doc__,audit_passed=True,evidence=ids,verified_bindings=sum(v['bindings_verified']for v in ids.values()),
        planned_native_cases=42,all38_case_recipes_and_raw_inputs_identical=True,
        all40_original_recipes_raw_bytes_and_oracles_identical=True,all444_original_assertions_retained=True,
        old_fatal_control_task_including_replay_byte_identical=True,only_old_bench_change_explicit_FEC_feature15_to31=True,
        original_partial1100_local_selected71_and_FEC77_stalls_retained=True,
        all42_authored_runtime_inputs=raw,original_fatal_messages_retained=444,new_fatal_messages=len(fatal(bench)-fatal(before)),
        exact_new_bench_sha256=hashlib.sha256(bench.encode()).hexdigest(),exact_new_runner_sha256=hashlib.sha256(current.encode()).hexdigest(),
        source_sha256={str(q.relative_to(ROOT)):digest(q)for q in inputs},protected_raw_sha256=binding.PROTECTED,
        compile_limit_seconds=1200,runtime_limit_seconds=30,elaboration_limit_seconds=180,FPGA_clock_ns=4,
        root_guard_bytes=1024**3,RAM_guard_bytes=4*1024**3,actual_new_native_runtime=False,
        hardware_verified=False,full_board_timing=False,overall_goal_complete=False,hardware_or_default_actions=[],commit_or_push=False)
    with a.report.open('x')as f:f.write(json.dumps(r,indent=2)+'\n')
    print(json.dumps(dict(audit_passed=True,verified_bindings=r['verified_bindings'],original_checks=444,new_checks=r['new_fatal_messages'],planned_cases=42)))


if __name__=='__main__':main()
