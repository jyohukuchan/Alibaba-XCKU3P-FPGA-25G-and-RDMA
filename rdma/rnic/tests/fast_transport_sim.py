#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Additional compiled TWO-STATE runs of unchanged finite transport benches.

Not a replacement for four-state RTL, X/Z/reset qualification, original
release coverage, native DMA or physical timing. No protocol assertion,
cycle deadline or testbench is removed/rewritten. Compilation is bounded
separately from a30second simulation; there is no hardware access.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'rdma/read/tests'))
import rw_sim

TOOL = None


def bounded(command, directory, seconds, stream=None):
    # Own an isolated process group so a compile timeout cannot leave its
    # make/compiler descendants running. Never signal an unrelated group.
    process = subprocess.Popen(command, cwd=directory, start_new_session=True,
        stdout=stream if stream is not None else subprocess.PIPE,
        stderr=subprocess.STDOUT if stream is not None else subprocess.PIPE, text=True)
    try:
        output, error = process.communicate(timeout=seconds)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.communicate(timeout=5)
        raise RuntimeError(f'Owned compile/simulation group exceeded {seconds}s; retained {directory}') from None
    return subprocess.CompletedProcess(command, process.returncode, output or '', error or '')


def simulate(tb, fixtures, hls_build, wall_timeout=30):
    sources, data = rw_sim.modules(hls_build)
    sources += [ROOT/'rdma/rnic/rtl'/name for name in ('rocev2_mr_table.v', 'rocev2_protected_responder.v')]
    before = rw_sim.hashes(sources+data+[Path(__file__).resolve()])
    run = Path(tempfile.mkdtemp(prefix='compiled-transport-', dir=ROOT/'rdma/rnic/build'))
    (run/'tb.v').write_text(tb)
    for name, values in fixtures.items():
        (run/name).write_text(''.join(f'{value:x}\n' for value in values))
    for item in data:
        shutil.copy2(item, run/item.name)
    version = subprocess.check_output([str(TOOL), '--version'], text=True).strip()
    started = time.monotonic()
    command = [str(TOOL), '--binary', '--timing', '--top-module', 'tb', '-Wno-fatal',
               #5.036's function splitting emitted fork synchronization
               #locals in a DIFFERENT C++ function from their use. Keep
               #C++ file splitting, but do not split function bodies.
               '-j', '4', '--output-split', '20000', '--output-split-cfuncs', '0',
               '--output-groups', '0', '-CFLAGS', '-O0',
               '--Mdir', str(run/'obj'), str(run/'tb.v'), *map(str, sources)]
    print(json.dumps(dict(scope=__doc__, directory=str(run), simulator=version,
                          compile_limit_seconds=600, simulation_limit_seconds=30)), flush=True)
    # Persist source/bench identity even if a compiler fails or hits its bound.
    (run/'inputs.json').write_text(json.dumps(dict(source_sha256=before,
        testbench_sha256=hashlib.sha256(tb.encode()).hexdigest(), command=command), indent=2)+'\n')
    with (run/'compile.log').open('x') as stream:
        compiled = bounded(command, run, 600, stream)
    compile_seconds = time.monotonic()-started
    if compiled.returncode:
        raise RuntimeError('Compiled transport failed; retain '+str(run/'compile.log'))
    started = time.monotonic()
    result = bounded([str(run/'obj/Vtb')], run, 30)
    seconds = time.monotonic()-started
    (run/'simulation.log').write_text(result.stdout+result.stderr)
    if result.returncode or 'ERROR:' in result.stdout or 'ERROR:' in result.stderr:
        raise RuntimeError('Compiled transport assertions failed; retain '+str(run/'simulation.log'))
    if before != rw_sim.hashes(sources+data+[Path(__file__).resolve()]):
        raise ValueError('compiled transport input changed')
    rtl = hls_build.resolve()/'solution1/syn/verilog'
    aggregate = hashlib.sha256()
    for item in sorted([*rtl.glob('*.v'), *rtl.glob('*.dat')]):
        aggregate.update(item.name.encode()+b'\0'+item.read_bytes())
    return result.stdout, dict(generated_hls_sha256=aggregate.hexdigest(),
        generated_files=len(list(rtl.glob('*.v')))+len(data),
        source_sha256={str(item.relative_to(ROOT)): before[str(item)] for item in sources+[Path(__file__).resolve()]
                       if item.is_relative_to(ROOT)}, simulator=version, four_state_simulation=False,
        X_Z_behavior_verified=False, original_testbench_assertions_preserved=True,
        compiled_two_state_additional_only=True, compilation_seconds=compile_seconds,
        simulation_seconds=seconds, compiled_directory=str(run),
        compiled_binary_sha256=hashlib.sha256((run/'obj/Vtb').read_bytes()).hexdigest(),
        compiled_log_sha256=hashlib.sha256((run/'compile.log').read_bytes()).hexdigest(),
        simulation_log_sha256=hashlib.sha256((run/'simulation.log').read_bytes()).hexdigest())


def main():
    global TOOL
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', choices=['native-control', 'legacy-read', 'legacy-write', 'read-error', 'fence-error'], required=True)
    parser.add_argument('--verilator', type=Path, required=True)
    args, remaining = parser.parse_known_args()
    TOOL = args.verilator.resolve()
    sys.argv = [sys.argv[0], *remaining]
    if args.case.startswith('legacy-'):
        import probe_dual_legacy as legacy
        legacy.rw_sim.simulate = simulate
        sys.argv += ['--operation', args.case.split('-', 1)[1]]
        legacy.main()
    else:
        import probe_parent_guard_transport as parent
        parent.ORIGINAL_SIMULATE = simulate
        if args.case.endswith('-error'):
            sys.argv += ['--parent-error', args.case.split('-', 1)[0]]
        parent.main()


if __name__ == '__main__':
    main()
