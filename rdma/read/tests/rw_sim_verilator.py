# SPDX-License-Identifier: BSD-2-Clause-Views
"""Compiled execution of the unchanged combined-app testbench and generated RTL.

This is an additional two-state simulator, not a physical/native gate or a
replacement for Icarus' four-state checks. No protocol clock, timeout, data
extent, assertion, source RTL or board constraint is changed.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import resource
import shutil
import subprocess
import tempfile
import time

import rw_sim as reference

ROOT=reference.ROOT
ethernet_frames=reference.ethernet_frames


def simulate(tb,fixtures,hls_build,wall_timeout=300):
    sources,data=reference.modules(hls_build)
    before=reference.hashes(sources+data)
    tool=os.environ.get('AS02_RW_VERILATOR') or shutil.which('verilator')
    if tool is None or not os.access(tool,os.X_OK):raise RuntimeError('Selected Verilator is not executable')
    version=subprocess.run([tool,'--version'],check=True,capture_output=True,text=True,timeout=10).stdout.strip()
    number=re.search(r'Verilator (\d+)\.(\d+)',version)
    if not number or tuple(map(int,number.groups()))<(5,36):
        raise RuntimeError('Use AS02_RW_VERILATOR with Verilator5.036 or newer;5.020 reproduces a coroutine crash')
    print('VERILATOR_SELECTED '+version+' '+tool,flush=True)
    started=time.monotonic()
    with tempfile.TemporaryDirectory(prefix='as02-rw-compiled-') as directory:
        path=Path(directory);bench=path / 'tb.v'
        bench.write_text(tb)
        for name,values in fixtures.items():
            (path / name).write_text(''.join(f'{value:x}\n' for value in values))
        for item in data:shutil.copy2(item,path / item.name)
        command=[tool,'--binary','--timing','--assert','-Wno-fatal','--error-limit','10',
            '--x-initial','unique','--x-assign','unique','-j','8','--top-module','tb',
            '--Mdir',str(path / 'obj'),'-o','simulation',str(bench),*map(str,sources)]
        compiled=subprocess.run(command,cwd=path,capture_output=True,text=True,timeout=600)
        print('VERILATOR_COMPILE_BEGIN',flush=True)
        print(compiled.stdout+compiled.stderr,flush=True)
        print(f'VERILATOR_COMPILE_END exit_status={compiled.returncode}',flush=True)
        if compiled.returncode:raise RuntimeError('Compiled RTL simulator build failed')
        executable=path / 'obj/simulation'
        binary_sha=hashlib.sha256(executable.read_bytes()).hexdigest()
        simulation_started=time.monotonic()
        runtime=[str(executable),'+verilator+rand+reset+2','+verilator+seed+1']
        result=subprocess.run(runtime,cwd=path,capture_output=True,text=True,timeout=wall_timeout)
        initial_status=result.returncode;stack_limits=resource.getrlimit(resource.RLIMIT_STACK)
        print(f'VERILATOR_RUN_END exit_status={result.returncode} stack_soft_bytes={stack_limits[0]}',flush=True)
        retained=None
        if result.returncode:
            # Retain the exact failed host executable and fixtures for a
            # debugger; never overwrite the original Icarus/compiled evidence.
            retained=Path(tempfile.mkdtemp(prefix='simulator-failure-',dir=ROOT / 'rdma/read/build'))
            for item in [bench,executable,*[path / name for name in fixtures],*[path / item.name for item in data]]:
                shutil.copy2(item,retained / item.name)
            (retained / 'failure.json').write_text(json.dumps(dict(exit_status=result.returncode,
                stdout=result.stdout,stderr=result.stderr,stack_limits=stack_limits,executable_sha256=binary_sha),indent=2)+'\n')
            print('VERILATOR_FAILURE_ARTIFACTS='+str(retained),flush=True)
        if result.returncode or 'ERROR:' in result.stdout or 'ERROR:' in result.stderr:
            raise RuntimeError(f'simulator exit={result.returncode}, retained_artifacts={retained}\n'+result.stdout+result.stderr)
        simulation_seconds=time.monotonic()-simulation_started
    if before!=reference.hashes(sources+data):raise ValueError('Compile inputs changed during compiled simulation')
    rtl=hls_build.resolve() / 'solution1/syn/verilog';aggregate=hashlib.sha256()
    generated=sorted([*rtl.glob('*.v'),*rtl.glob('*.dat')])
    for item in generated:aggregate.update(item.name.encode()+b'\0'+item.read_bytes())
    identities={str(item.relative_to(ROOT)):before[str(item)] for item in sources if item.is_relative_to(ROOT)}
    for item in (Path(__file__),Path(reference.__file__),Path(__file__).with_name('probe_rw_read_compiled.py')):
        identities[str(item.relative_to(ROOT))]=hashlib.sha256(item.read_bytes()).hexdigest()
    return result.stdout,dict(generated_hls_sha256=aggregate.hexdigest(),generated_files=len(generated),
        source_sha256=identities,simulator=dict(name=version,tool_sha256=hashlib.sha256(Path(tool).read_bytes()).hexdigest(),
            tool_binary_sha256=hashlib.sha256((Path(tool).parent / 'verilator_bin').read_bytes()).hexdigest(),
            executable_sha256=binary_sha,testbench_sha256=hashlib.sha256(tb.encode()).hexdigest(),
            unchanged_original_testbench=True,two_state=True,random_initial_state=True,random_seed=1,
            four_state_icarus_pass_claimed=False,compile_exit_status=0,simulation_exit_status=0,
            initial_simulation_exit_status=initial_status,initial_stack_soft_limit_bytes=stack_limits[0],
            stack_limit_experiment_used=False,
            retained_failure_artifacts=str(retained) if retained else None,
            simulated_clock_period_ns=4,original_device_timeout_cycles=250000,
            wall_seconds_in_simulator=simulation_seconds,wall_seconds_including_compile=time.monotonic()-started))
