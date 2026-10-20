#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Re-execute exact compiled READ design with corrected peer-fixture payload.

Only the identified independent-oracle packet-payload correction is allowed.
Every DUT/bench assertion, other fixture, source and compiled binary is frozen.
No failed test is relabeled: fresh <=30s execution and full existing validators
must succeed. This is ordinary input-data replay, not a modified/cached test.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time
import xml.etree.ElementTree as ET

import probe_native_read_hls as probe

ROOT=probe.ROOT


def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--previous-report',type=Path,required=True)
    p.add_argument('--hls-build',type=Path,required=True);p.add_argument('--verilator',type=Path,required=True)
    p.add_argument('--report',type=Path,required=True);args=p.parse_args()
    previous=args.previous_report.resolve();old=json.loads(previous.read_text());build=ROOT/old['retained_directory']
    if old.get('pass_test')or old.get('terminal_exit_status')!=1 or'Compiled native executor assertions failed'not in old.get('error',''):
        raise ValueError('only the identified terminal failed READ design is eligible')
    log=(build/'simulation.log').read_text()
    if'actual HLS READ padded bytes'not in log:raise ValueError('different failure requires diagnosis/fresh build')
    snapshot=ROOT/'results/2026-10-18/rocev2-rnic-native-read002-probe-before-fixturefix.py'
    driver=Path(probe.__file__).resolve();name=str(driver.relative_to(ROOT))
    if digest(snapshot)!=old['source_sha256'][name]:raise ValueError('old exact driver snapshot differs')
    old_line='    good=bytearray(native.response.packet(mig=1,qpn=2));good=native.response.repair(good)'
    new_line='    good=bytearray(native.response.packet(mig=1,qpn=2));good[44:109]=bytes(((i*179)^(i>>7)^0xd3)&255 for i in range(65));good=native.response.repair(good)'
    text=snapshot.read_text()
    if text.count(old_line)!=1 or driver.read_text()!=text.replace(old_line,new_line):raise ValueError('change beyond exact fixture correction requires a fresh build')
    for n,want in old['source_sha256'].items():
        if n!=name and digest(ROOT/n)!=want:raise ValueError('execution source changed '+n)
    for n,want in old['artifact_sha256'].items():
        if digest(ROOT/n)!=want:raise ValueError('failed artifact changed '+n)
    inputs=json.loads((build/'inputs.json').read_text())
    for n,want in inputs['source_sha256'].items():
        if digest(n)!=want:raise ValueError('compiled input/helper changed '+n)
    binary=build/'obj/Vtb';binary_hash=digest(binary)
    if digest(build/'tb.v')!=inputs['testbench_sha256']:raise ValueError('compiled bench changed')
    if not(build/'compile.log').is_file()or not binary.is_file():raise ValueError('no completed compiled design')
    root=ET.parse(build/'hierarchy.xml').getroot();modules={m.get('name'):m.get('origName',m.get('name'))for m in root.findall('.//netlist/module')};counts={}
    for cell in root.findall('.//cells//cell'):
        n=modules.get(cell.get('submodname'),cell.get('submodname'));counts[n]=counts.get(n,0)+1

    def execute(tb,fixtures,project,tool,run):
        if tb.encode()!=(build/'tb.v').read_bytes():raise ValueError('new bench differs from actual compiled bench')
        for n in ['input.hex','records.hex']:
            if ''.join(f'{v:x}\n'for v in fixtures[n])!=(build/n).read_text():raise ValueError('non-peer fixture changed '+n)
        probe.compiled.delivery.verify_delivery(project)
        (run/'tb.v').write_text(tb)
        for n,values in fixtures.items():(run/n).write_text(''.join(f'{v:x}\n'for v in values))
        for n in build.glob('*.dat'):shutil.copy2(n,run/n.name)
        provenance=dict(scope=__doc__,previous_report=str(previous.relative_to(ROOT)),previous_report_sha256=digest(previous),
            original_compilation_inputs_sha256=digest(build/'inputs.json'),unchanged_compiled_binary=str(binary.relative_to(ROOT)),
            unchanged_compiled_binary_sha256=binary_hash,compiled_bench_byte_identical=True,
            WQE_control_fixtures_byte_identical=True,only_peer_payload_and_derived_ICRC_changed=True,
            original_driver_snapshot=str(snapshot.relative_to(ROOT)),original_driver_sha256=digest(snapshot),current_driver_sha256=digest(driver))
        (run/'replay-provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
        started=time.monotonic()
        with(run/'simulation.log').open('x')as out:result=probe.compiled.fast.bounded([str(binary)],run,30,out)
        elapsed=time.monotonic()-started;output=(run/'simulation.log').read_text()
        if result.returncode or'ERROR:'in output:raise RuntimeError('replayed compiled READ assertions failed; retain '+str(run))
        if digest(binary)!=binary_hash:raise ValueError('binary changed during replay')
        for n,want in inputs['source_sha256'].items():
            if digest(n)!=want:raise ValueError('compiled input changed during replay '+n)
        record,manifest=probe.compiled.delivery.verify_delivery(project)
        return output,dict(simulator='Verilator5.036 exact retained compiled READ design',four_state_simulation=False,
            X_Z_behavior_verified=False,compiled_two_state_additional_only=True,new_finite_bench_not_rewritten=True,
            original_testbench_assertions_preserved=False,original_NEW_coupled_READ_bench_byte_identical=True,
            source_sha256={str(Path(n).relative_to(ROOT)):want for n,want in inputs['source_sha256'].items()if Path(n).is_relative_to(ROOT)}|
                {str(Path(__file__).resolve().relative_to(ROOT)):digest(Path(__file__).resolve()),str(snapshot.relative_to(ROOT)):digest(snapshot)},
            generated_hls_sha256=record['original_generated_HLS_sha256'],generated_files=138,delivery_sha256=record['delivery_sha256'],delivery_files=140,
            raw_generated_HLS_bytes_unchanged=True,simulation_seconds=elapsed,simulation_wall_limit_seconds=30,
            hierarchy_module_counts=counts,compiled_binary_sha256=binary_hash,validated_compiled_design_reused=True,replay_provenance=provenance)
    original=probe.compiled.simulate
    try:
        probe.compiled.simulate=execute
        sys.argv=[sys.argv[0],'--hls-build',str(args.hls_build),'--verilator',str(args.verilator),'--report',str(args.report)]
        probe.main()
    finally:probe.compiled.simulate=original


if __name__=='__main__':main()
