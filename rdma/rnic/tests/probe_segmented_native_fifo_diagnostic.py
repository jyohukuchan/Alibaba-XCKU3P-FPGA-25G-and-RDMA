#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Inspect the unchanged failed large-native001 model at its original fatal.

Relink only the existing archive/runtime objects with diagnostic type symbols.
No state mutation, assertion suppression, DUT rebuild or native-pass claim.
Preserve original fixture/probe bytes and hash-check every failed-run binding.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[3]
FAILED = ROOT/'results/2026-10-18/rocev2-rnic-segmented-wire-native-full-001.json'
INCLUDE = Path('/home/user/fpga-rocev2-research/verilator-v5.036-install/share/verilator/include')


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        parser.error('preserve earlier evidence')
    failed = json.loads(FAILED.read_text())
    if failed['pass_test'] or set(failed['tests']) != {'LARGE_WRITE'} or failed['tests']['LARGE_WRITE']['exit'] != -6:
        raise ValueError('exact first failed large WRITE required')
    bindings = {str(FAILED.relative_to(ROOT)): digest(FAILED)}
    count = 0
    for field in ['source_sha256', 'artifact_sha256', 'RAM_artifact_sha256']:
        for name, expected in failed[field].items():
            if digest(ROOT/name) != expected:
                raise ValueError('failed-run binding changed: '+name)
            count += 1
    run = Path(tempfile.mkdtemp(prefix='segmented-native-fifo-diagnostic-', dir=ROOT/'rdma/rnic/build'))
    ram = Path(tempfile.mkdtemp(prefix='as02-segmented-fifo-debug-', dir='/dev/shm'))
    for name in ['segmented_wire_native_fixture.py', 'probe_segmented_wire_native_full.py']:
        p = ROOT/'rdma/rnic/tests'/name
        bindings[str(p.relative_to(ROOT))] = digest(p)
        shutil.copy2(p, run/name)
    obj = Path(failed['compile_directory'])
    if not obj.is_absolute():
        obj = ROOT/obj
    tests = ROOT/'rdma/rnic/tests'
    inputs = [tests/'zero_native_debug_main.cpp', tests/'segmented_native_debug_fifo.gdb', Path(__file__).resolve(),
              obj/'Vtb___024root.h', obj/'Vtb__ALL.a', *[obj/n for n in ['verilated.o', 'verilated_timing.o', 'verilated_threads.o']]]
    bindings.update({str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p): digest(p) for p in inputs})
    report = dict(scope=__doc__, diagnostic_completed=False, native_runtime_pass=False,
                  failed_bindings_verified=count, directory=str(run.relative_to(ROOT)), source_sha256=bindings)
    try:
        binary = ram/'Vtb-debug'
        cmd = ['g++', '-std=c++20', '-g', '-O0', '-fcoroutines', '-I'+str(obj), '-I'+str(INCLUDE),
               '-I'+str(INCLUDE/'vltstd'), str(tests/'zero_native_debug_main.cpp'),
               *map(str, [obj/'Vtb__ALL.a', obj/'verilated.o', obj/'verilated_timing.o', obj/'verilated_threads.o']),
               '-pthread', '-lpthread', '-latomic', '-o', str(binary)]
        start = time.monotonic()
        c = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        (run/'link.log').write_text(c.stdout+c.stderr)
        report.update(link_command=cmd, link_exit=c.returncode, link_seconds=time.monotonic()-start)
        if c.returncode:
            raise ValueError('diagnostic-only link failed')
        cmd = ['gdb', '-q', '-batch', '-x', str(tests/'segmented_native_debug_fifo.gdb'), str(binary)]
        start = time.monotonic()
        c = subprocess.run(cmd, cwd=ROOT/failed['directory'], capture_output=True, text=True, timeout=30)
        output = c.stdout+c.stderr
        (run/'fatal-inspection.log').write_text(output)
        report.update(debug_command=cmd, debug_exit=c.returncode, debug_seconds=time.monotonic()-start)
        if c.returncode or 'SEGMENTED_NATIVE_ACTUAL_FIFO_FATAL' not in output:
            raise ValueError('original fatal not inspected')
        values = {}
        for line in output.splitlines():
            if line.startswith('tb__DOT__') and ' = ' in line:
                key, value = line.split(' = ', 1)
                if value.isdigit():
                    values[key] = int(value)
        report['actual_fatal_fields'] = values
        needed = {'actual_tx_fifo__DOT__fifo_inst__DOT__overflow_reg': 1,
                  'actual_tx_fifo__DOT__fifo_inst__DOT__bad_frame_reg': 0,
                  'actual_mac__DOT__error_underflow_reg': 0,
                  'actual_timestamp_fifo__DOT__overflow_reg': 0,
                  'actual_SFD_count': 0, 'local_committed_count': 0, 'fault': 0}
        if any(values.get('tb__DOT__'+name) != value for name, value in needed.items()):
            raise ValueError('fatal cause differs from hypothesized small whole-frame FIFO overflow')
        report.update(diagnostic_completed=True, cause='actual inherited 1024-byte whole-frame TX FIFO overflow; no MAC SFD or CQ')
    except Exception as error:
        report.update(error_type=type(error).__name__, error=str(error))
        raise
    finally:
        report['artifact_sha256'] = {str(p.relative_to(ROOT)): digest(p) for p in run.iterdir() if p.is_file()}
        report['RAM_artifact_sha256'] = {str(p): digest(p) for p in ram.iterdir() if p.is_file()}
        args.report.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({key: report[key] for key in ['diagnostic_completed', 'cause', 'debug_seconds', 'directory']}))


if __name__ == '__main__':
    main()
