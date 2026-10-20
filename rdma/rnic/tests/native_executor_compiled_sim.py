# SPDX-License-Identifier: BSD-2-Clause-Views
"""Additional bounded TWO-STATE run of an unchanged new native executor bench.

Compile600s, simulate30s. Not X/Z/reset/physical qualification and not a pass
for the separate timed-out four-state run. Exact raw HLS bytes are verified.
"""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time
import xml.etree.ElementTree as ET

import fast_transport_sim as fast
import wrkey_delivery_sim as delivery

ROOT=delivery.ROOT


def simulate(tb,fixtures,project,tool,run):
    record,manifest=delivery.verify_delivery(project)
    sources,data=delivery.ORIGINAL_MODULES(project)
    if sources.count(delivery.OLD_BRIDGE)!=1:raise ValueError('ambiguous original bridge')
    sources.remove(delivery.OLD_BRIDGE)
    derived=project.resolve()/'solution1/syn/verilog/rocev2_integrity_transport_wrkey.v'
    if sources.count(derived)!=1:raise ValueError('explicit per-WR bridge missing')
    support=[ROOT/'rdma/rnic/rtl'/n for n in ['rocev2_mr_table.v','rocev2_protected_responder.v']]
    included=[p for p in support if f'`include "{p}"'in tb]
    sources+=[p for p in support if p not in included]
    helpers=[Path(__file__).resolve(),Path(fast.__file__).resolve(),Path(delivery.__file__).resolve(),manifest]
    before=delivery.bounded.rw_sim.hashes(sources+included+data+helpers)
    (run/'tb.v').write_text(tb)
    for name,values in fixtures.items():(run/name).write_text(''.join(f'{v:x}\n'for v in values))
    for p in data:shutil.copy2(p,run/p.name)
    base=[str(tool),'--timing','--top-module','tb','-Wno-fatal']
    xml=base+['--xml-only','--xml-output',str(run/'hierarchy.xml'),str(run/'tb.v'),*map(str,sources)]
    command=base+['--binary','-j','4','--output-split','20000','--output-split-cfuncs','0',
        '--output-groups','0','-CFLAGS','-O0','--Mdir',str(run/'obj'),str(run/'tb.v'),*map(str,sources)]
    (run/'inputs.json').write_text(json.dumps(dict(source_sha256=before,
        testbench_sha256=hashlib.sha256(tb.encode()).hexdigest(),hierarchy_command=xml,compile_command=command,
        compilation_timeout_seconds=600,simulation_timeout_seconds=30),indent=2)+'\n')
    version=subprocess.check_output([str(tool),'--version'],text=True).strip()
    print(json.dumps(dict(directory=str(run),simulator=version,scope=__doc__,compile_limit_seconds=600,simulation_limit_seconds=30)),flush=True)
    started=time.monotonic()
    with(run/'hierarchy.log').open('x')as out:result=fast.bounded(xml,run,60,out)
    if result.returncode:raise RuntimeError('Verilator hierarchy failed; retain '+str(run))
    root=ET.parse(run/'hierarchy.xml').getroot()
    modules={m.get('name'):m.get('origName',m.get('name'))for m in root.findall('.//netlist/module')}
    counts={}
    for cell in root.findall('.//cells//cell'):
        name=modules.get(cell.get('submodname'),cell.get('submodname'))
        counts[name]=counts.get(name,0)+1
    with(run/'compile.log').open('x')as out:result=fast.bounded(command,run,600,out)
    if result.returncode:raise RuntimeError('Verilator compile failed; retain '+str(run))
    compile_seconds=time.monotonic()-started
    started=time.monotonic()
    with(run/'simulation.log').open('x')as out:result=fast.bounded([str(run/'obj/Vtb')],run,30,out)
    seconds=time.monotonic()-started;output=(run/'simulation.log').read_text()
    if result.returncode or'ERROR:'in output:raise RuntimeError('Compiled native executor assertions failed; retain '+str(run))
    if before!=delivery.bounded.rw_sim.hashes(sources+included+data+helpers):raise ValueError('compiled run inputs changed')
    delivery.verify_delivery(project)
    return output,dict(simulator=version,compiled_two_state_additional_only=True,four_state_simulation=False,
        X_Z_behavior_verified=False,original_testbench_assertions_preserved=False,new_finite_bench_not_rewritten=True,
        source_sha256={str(p.relative_to(ROOT)):before[str(p)]for p in sources+included+helpers if p.is_relative_to(ROOT)},
        generated_hls_sha256=record['original_generated_HLS_sha256'],generated_files=138,
        delivery_sha256=record['delivery_sha256'],delivery_files=140,raw_generated_HLS_bytes_unchanged=True,
        compilation_seconds=compile_seconds,simulation_seconds=seconds,simulation_wall_limit_seconds=30,
        hierarchy_module_counts=counts,compiled_binary_sha256=delivery.digest(run/'obj/Vtb'))
