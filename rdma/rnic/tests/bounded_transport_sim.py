#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Short actual four-state finite transport benches, preserving partial logs.

Unchanged original benches/assertions/cycle bounds; no hardware/long stress.
Icarus compilation30s, simulation120s. A wall timeout has NO protocol result.
No internal forcing, header/data repair, transport or protection substitute.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import time

import fast_transport_sim as owned

ROOT = owned.ROOT
rw_sim = owned.rw_sim


def simulate(tb, fixtures, hls_build, wall_timeout=120):
    sources, data = rw_sim.modules(hls_build)
    # Some unchanged benches explicitly include these support modules, while
    # the native-control bench expects them in the compiler source list.
    # Compile each exact module ONCE; never rewrite the original bench.
    support = [ROOT/'rdma/rnic/rtl'/name for name in ('rocev2_mr_table.v', 'rocev2_protected_responder.v')]
    included = [p for p in support if f'`include "{p}"' in tb]
    sources += [p for p in support if p not in included]
    helpers = [Path(__file__).resolve(), Path(owned.__file__).resolve()]
    before = rw_sim.hashes(sources+included+data+helpers)
    run = Path(tempfile.mkdtemp(prefix='four-state-transport-', dir=ROOT/'rdma/rnic/build'))
    (run/'tb.v').write_text(tb)
    for name, values in fixtures.items():
        (run/name).write_text(''.join(f'{value:x}\n' for value in values))
    for p in data:
        shutil.copy2(p, run/p.name)
    (run/'inputs.json').write_text(json.dumps(dict(source_sha256=before,
        testbench_sha256=hashlib.sha256(tb.encode()).hexdigest()), indent=2)+'\n')
    print(json.dumps(dict(directory=str(run), simulator='Icarus four-state',
        compile_limit_seconds=30, simulation_limit_seconds=120, assertions_unchanged=True)), flush=True)
    started = time.monotonic()
    with (run/'compile.log').open('x') as out:
        compiled = owned.bounded(['/usr/bin/iverilog', '-g2012', '-s', 'tb', '-o', str(run/'test.vvp'),
                                  str(run/'tb.v'), *map(str, sources)], run, 30, out)
    compile_seconds = time.monotonic()-started
    if compiled.returncode:
        raise RuntimeError('Four-state compilation failed; retain '+str(run/'compile.log'))
    started = time.monotonic()
    with (run/'simulation.log').open('x') as out:
        result = owned.bounded(['/usr/bin/vvp', str(run/'test.vvp')], run, 120, out)
    seconds = time.monotonic()-started
    output = (run/'simulation.log').read_text()
    if result.returncode or 'ERROR:' in output:
        raise RuntimeError('Four-state assertions failed; retain '+str(run/'simulation.log'))
    if before != rw_sim.hashes(sources+included+data+helpers):
        raise ValueError('Four-state transport input changed')
    rtl = hls_build.resolve()/'solution1/syn/verilog'
    aggregate = hashlib.sha256()
    for p in sorted([*rtl.glob('*.v'), *rtl.glob('*.dat')]):
        aggregate.update(p.name.encode()+b'\0'+p.read_bytes())
    return output, dict(generated_hls_sha256=aggregate.hexdigest(),
        generated_files=len(list(rtl.glob('*.v')))+len(data),
        source_sha256={str(p.relative_to(ROOT)): before[str(p)] for p in sources+included+helpers if p.is_relative_to(ROOT)},
        simulator='Icarus four-state', four_state_simulation=True,
        original_testbench_assertions_preserved=True, compilation_seconds=compile_seconds,
        simulation_seconds=seconds, simulation_wall_limit_seconds=120, simulation_directory=str(run),
        simulation_log_sha256=hashlib.sha256((run/'simulation.log').read_bytes()).hexdigest())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', choices=['native-control', 'legacy-read', 'legacy-write', 'read-error', 'fence-error'], required=True)
    args, remaining = parser.parse_known_args()
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
