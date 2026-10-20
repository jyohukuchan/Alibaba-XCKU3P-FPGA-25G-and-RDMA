#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Short actual-derived-HLS C++ function test, NOT generated RTL or hardware.

Checks exact per-WR RETH keys, metadata initialization/storage/append and
actual retransmitter/local-handler context. C simulation cannot establish
four-state behavior, warm hardware reset, FIFO scheduling, wire ICRC, physical
timing, standard verbs or registered-host-page DMA. Keep those gates open.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import time

from fast_transport_sim import bounded
import fast_transport_sim

ROOT = Path(__file__).resolve().parents[3]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_mapping(mapping, base):
    for name, value in mapping.items():
        if digest(base/name) != value:
            raise ValueError('input hash mismatch: '+str(base/name))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-record', type=Path, required=True)
    parser.add_argument('--vitis-include', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        parser.error('preserve previous evidence')
    record = json.loads(args.source_record.read_text())
    frozen = Path(record['hls_build']).parent/'inputs'
    include = args.vitis_include.resolve()
    verify_mapping(record['source_sha256'], Path(record['source_directory']))
    verify_mapping(record['profile_sha256'], ROOT)
    verify_mapping(record['frozen_sha256'], frozen)
    run = Path(tempfile.mkdtemp(prefix='wrkey-csim-', dir=ROOT/'rdma/rnic/build'))
    bench = ROOT/'rdma/rnic/hls/test_wrkey_context.cpp'
    shutil.copy2(bench, run/'test.cpp')
    own = {str(p.relative_to(ROOT)): digest(p) for p in [bench, Path(__file__).resolve(),
            Path(fast_transport_sim.__file__).resolve(), args.source_record.resolve()]}
    compiler = Path(shutil.which('g++-13') or shutil.which('g++')).resolve()
    flags = ['-std=c++17', '-O0', '-pthread', '-Wno-unknown-pragmas',
             '-ffunction-sections', '-fdata-sections', '-Wl,--gc-sections',
             '-DFNS_DATA_WIDTH=64', '-DFNS_ROCE_STACK_MAX_QPS=8', '-D__VITIS_HLS__',
             '-I'+str(frozen/'adapter'), '-I'+str(frozen/'fns/hls'), '-I'+str(include)]
    dep = bounded([str(compiler), *flags, '-MM', str(run/'test.cpp')], run, 30)
    if dep.returncode:
        raise RuntimeError('dependency preprocessing failed: '+dep.stderr)
    dependencies = [Path(p).resolve() for p in dep.stdout.replace('\\\n', ' ').split()[1:]]
    precompile = {str(p): digest(p) for p in dependencies}
    command = [str(compiler), *flags, str(run/'test.cpp'), '-o', str(run/'test')]
    (run/'inputs.json').write_text(json.dumps(dict(command=command,
        source_sha256=own, actual_include_sha256=precompile,
        compiler_sha256=digest(compiler)), indent=2)+'\n')
    start = time.monotonic()
    with (run/'compile.log').open('x') as log:
        compiled = bounded(command, run, 120, log)
    compile_seconds = time.monotonic()-start
    if compiled.returncode:
        raise RuntimeError('C++ compile failed; retained '+str(run/'compile.log'))
    start = time.monotonic()
    result = bounded([str(run/'test')], run, 15)
    simulation_seconds = time.monotonic()-start
    (run/'simulation.log').write_text(result.stdout+result.stderr)
    if result.returncode:
        raise RuntimeError('actual HLS C++ assertions failed; retained '+str(run/'simulation.log'))
    payload = json.loads(next(s for s in result.stdout.splitlines() if s.startswith('{')))
    if not payload.get('pass_test') or payload['metadata_entries'] != 2000 or payload['metadata_fields'] != 13:
        raise ValueError('missing complete C++ assertions')
    verify_mapping(own, ROOT)
    verify_mapping(precompile, Path('/'))
    verify_mapping(record['source_sha256'], Path(record['source_directory']))
    verify_mapping(record['profile_sha256'], ROOT)
    verify_mapping(record['frozen_sha256'], frozen)
    report = dict(scope=__doc__, **payload, directory=str(run),
        source_record=str(args.source_record), source_sha256=own,
        actual_include_sha256=precompile, dependency_files=len(precompile),
        source_and_frozen_inputs_unchanged=True,
        compiler=str(compiler), compiler_SHA256=digest(compiler),
        compiler_wall_limit_seconds=120, simulation_wall_limit_seconds=15,
        compile_seconds=compile_seconds, simulation_seconds=simulation_seconds,
        artifact_sha256={str(p.relative_to(ROOT)): digest(p)
                        for p in [run/'test', run/'inputs.json', run/'compile.log', run/'simulation.log']},
        generated_RTL_test=False, four_state_simulation=False,
        hardware_warm_reset_tested=False, wire_ICRC_checked=False,
        native_hardware_verified=False, standard_verbs_implemented=False,
        programming_authorized=False, hardware_verified=False)
    with args.report.open('x') as out:
        out.write(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if not k.endswith('sha256')}, indent=2))


if __name__ == '__main__':
    main()
