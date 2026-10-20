#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Short new-main-parent READ/WRITE with LIVE existing generated shared HLS.

Real coherent SQ/SAME MR/PTE, HLS, executor, issued PSN/protected Ethernet RX,
READ unpadding, DMA/RAM/fence and MAC/lifetime join. Host/link/MAC pins and
peer are models. Two-state simulation only; not X/Z, timing, board, kernel,
standard verbs, CQ publication or internal-core-drain qualification.
"""
import argparse
import ctypes as C
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import time
import xml.etree.ElementTree as ET

import native_executor_compiled_sim as compiled
import test_native_rnic_rtl as main

ROOT=main.ROOT


def simulate_cached(tb,fixtures,project,tool,run,cache):
    """Regenerate RTL normally; reuse ONLY byte-identical compiled inputs.

    The previous failed bench/log/fixtures remain untouched. Only its normal
    compiler cache is mutable. GNU make still rebuilds changed C++/headers;
    Verilog prerequisites are already consumed by the completed regeneration.
    """
    cache=cache.resolve()
    if cache.parent!=ROOT/'rdma/rnic/build' or not cache.name.startswith('native-rnic-live-'):
        raise ValueError('cache must be a task-owned native-RNIC build')
    obj=cache/'obj'
    if not obj.is_dir() or obj.is_symlink():raise ValueError('missing real compiler cache')
    selected,manifest=compiled.delivery.verify_delivery(project)
    sources,data=compiled.delivery.ORIGINAL_MODULES(project)
    if sources.count(compiled.delivery.OLD_BRIDGE)!=1:raise ValueError('ambiguous bridge')
    sources.remove(compiled.delivery.OLD_BRIDGE)
    included=[Path(p)for p in re.findall(r'`include "([^\"]+)"',tb)]
    for name in ['rocev2_mr_table.v','rocev2_protected_responder.v']:
        p=ROOT/'rdma/rnic/rtl'/name
        if p not in included:sources.append(p)
    own=[Path(__file__).resolve(),Path(main.__file__).resolve(),manifest]
    before=compiled.delivery.bounded.rw_sim.hashes(sources+included+data+own)
    (run/'tb.v').write_text(tb)
    for name,values in fixtures.items():(run/name).write_text(''.join(f'{v:x}\n'for v in values))
    for p in data:shutil.copy2(p,run/p.name)
    saved={p:(compiled.delivery.digest(p),p.stat().st_atime_ns,p.stat().st_mtime_ns)
        for p in obj.iterdir()if p.suffix in ['.cpp','.h','.mk']}
    base=[str(tool),'--timing','--top-module','tb','-Wno-fatal']
    xml=base+['--xml-only','--xml-output',str(run/'hierarchy.xml'),str(run/'tb.v'),*map(str,sources)]
    generate=base+['--cc','--exe','--main','--output-split','20000','--output-split-cfuncs','0',
        '--output-groups','0','-CFLAGS','-O0 -DVL_TIME_CONTEXT','--Mdir',str(obj),str(run/'tb.v'),*map(str,sources)]
    started=time.monotonic()
    with(run/'hierarchy.log').open('x')as out:r=compiled.fast.bounded(xml,run,60,out)
    if r.returncode:raise RuntimeError('fresh hierarchy failed')
    with(run/'generate.log').open('x')as out:r=compiled.fast.bounded(generate,run,600,out)
    if r.returncode:raise RuntimeError('fresh Verilog translation failed')
    identical=[]
    for p,(sha,atime,mtime)in saved.items():
        if p.is_file()and compiled.delivery.digest(p)==sha:
            os.utime(p,ns=(atime,mtime));identical.append(p)
    # Ignore only already-translated SV and verified byte-identical generated
    # files. Changed headers remain normal dependencies of EVERY object.
    ignored=list(dict.fromkeys([*sources,*included,run/'tb.v',*identical]))
    command=['make','-C',str(obj),'-f','Vtb.mk','-j','4',*[arg for p in ignored for arg in ['-o',str(p)]],'Vtb']
    (run/'inputs.json').write_text(json.dumps(dict(source_sha256=before,generate_command=generate,
        compile_command=command,cache_directory=str(cache),byte_identical_generated_files=[str(p)for p in identical]),indent=2)+'\n')
    with(run/'compile.log').open('x')as out:r=compiled.fast.bounded(command,run,600,out)
    if r.returncode:raise RuntimeError('incremental C++ compilation failed')
    compile_seconds=time.monotonic()-started
    started=time.monotonic()
    with(run/'simulation.log').open('x')as out:r=compiled.fast.bounded([str(obj/'Vtb')],run,30,out)
    seconds=time.monotonic()-started;output=(run/'simulation.log').read_text()
    if r.returncode or 'ERROR:'in output:raise RuntimeError('fresh finite main-path assertions failed')
    if before!=compiled.delivery.bounded.rw_sim.hashes(sources+included+data+own):raise ValueError('consumed source changed')
    compiled.delivery.verify_delivery(project)
    root=ET.parse(run/'hierarchy.xml').getroot()
    modules={m.get('name'):m.get('origName',m.get('name'))for m in root.findall('.//netlist/module')}
    counts={}
    for cell in root.findall('.//cells//cell'):
        n=modules.get(cell.get('submodname'),cell.get('submodname'));counts[n]=counts.get(n,0)+1
    return output,dict(compiled_two_state_additional_only=True,four_state_simulation=False,
        X_Z_behavior_verified=False,source_sha256=before,hierarchy_module_counts=counts,
        compilation_seconds=compile_seconds,simulation_seconds=seconds,simulation_wall_limit_seconds=30,
        generated_hls_sha256=selected['original_generated_HLS_sha256'],raw_generated_HLS_bytes_unchanged=True,
        compiled_binary_sha256=compiled.delivery.digest(obj/'Vtb'),cache_directory=str(cache),
        byte_identical_generated_inputs_reused=len(identical))


def probe(write,project,tool,report,cache=None):
    if report.exists():raise ValueError('preserve existing report')
    # This is compilation of EXISTING Verilog, not HLS synthesis or XSIM.
    # Their original 1500-MiB guards are not changed or bypassed here.
    minimum=(384 if cache else 1024)*1024*1024
    if shutil.disk_usage(ROOT).free<minimum:
        raise RuntimeError('insufficient headroom for selected fresh/cached RTL compilation')
    tb,words=main.bench(write)
    marker=r'\"HLS_model\":true'
    if tb.count(marker)!=1:raise ValueError('ambiguous simulation metadata')
    tb=tb.replace(marker,r'\"HLS_model\":false')
    records=[]
    cls=main.shared.SharedMRResponderRTLTests;obj=cls();obj.setUpClass()
    try:
        for i in range(2):
            w=main.shared.codec.candidate(wr_id=0xf123456789abc001+i,sequence=i+1,epoch=0x9123456700000001,
                local_address=0xfedcba9876543210,local_key=8,remote_address=0xf123456789abc001,
                remote_key=0,opcode=1 if write else 2,flags=1,length=65)
            data=(C.c_uint8*64)()
            if obj.lib.as02_wqe_encode(data,C.byref(w))!=0:raise ValueError('actual C codec rejected WR')
            if bytes(data)!=main.shared.codec.oracle(w):raise ValueError('actual C WQE differs from byte oracle')
            records.append(int.from_bytes(data,'little'))
    finally:obj.directory.cleanup()
    run=Path(tempfile.mkdtemp(prefix='native-rnic-live-'+('write'if write else'read')+'-',dir=ROOT/'rdma/rnic/build'))
    derived=run/'rocev2_shared_protected_responder.v'
    derived.write_text(main.derive.derive(main.derive.ORIGINAL.read_text()))
    existing={Path(p)for p in re.findall(r'`include "([^\"]+)"',tb)}
    includes=[p for p in [derived,main.TOP,*main.EXTRA]if p not in existing]
    tb='\n'.join('`include "'+str(p)+'"'for p in includes)+'\n'+tb
    record=dict(scope=__doc__,pass_test=False,operation='WRITE'if write else'READ',
        hardware_verified=False,full_board_selected_or_built=False,standard_verbs=False,
        actual_CQ_commit=False,core_internal_drain_proved=False,local_role_and_MR_retained=True,
        output_directory=str(run.relative_to(ROOT)))
    try:
        fixtures={'input.hex':words,'records.hex':records}
        output,identity=(simulate_cached(tb,fixtures,project,tool,run,cache)if cache else
            compiled.simulate(tb,fixtures,project,tool,run))
        record['actual_HLS_identity']=identity
        rows=[json.loads(l.split(' ',1)[1])for l in output.splitlines()if l.startswith('NATIVE_RNIC_RESULT ')]
        if len(rows)!=1 or not rows[0]['pass_test'] or rows[0]['HLS_model'] or rows[0]['CQ_committed']:
            raise ValueError('missing actual main-path result')
        counts=identity['hierarchy_module_counts']
        required=['rocev2_native_rnic_endpoint','rocev2_native_sq_endpoint','rocev2_shared_hls_transport',
            'rocev2_shared_protected_responder','rocev2_mr_table','rocev2_mr_page_table','rocev2_wqe_memory_executor',
            'rocev2_wqe_response_guard','rocev2_wqe_read_unpad','rocev2_wqe_tx_lifetime']
        if any(counts.get(n)!=1 for n in required)or counts.get('rocev2_top')!=2:
            raise ValueError('wrong legacy/shared HLS or MR multiplicity')
        record.update(pass_test=True,summary=rows[0],actual_shared_HLS_and_native_memory_graph=True,
            actual_module_counts={n:counts[n]for n in required+['rocev2_top']})
        print(json.dumps(dict(operation=record['operation'],pass_test=True,summary=rows[0],
            simulation_seconds=identity['simulation_seconds'],output_directory=record['output_directory'])),flush=True)
    except Exception as e:
        record.update(error_type=type(e).__name__,error=str(e));raise
    finally:
        with report.open('x')as out:out.write(json.dumps(record,indent=2)+'\n')
    return record


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--operation',required=True,choices=['read','write'])
    p.add_argument('--hls-build',required=True,type=Path)
    p.add_argument('--verilator',type=Path,default=Path('/home/user/fpga-rocev2-research/verilator-v5.036-install/bin/verilator'))
    p.add_argument('--report',required=True,type=Path)
    p.add_argument('--reuse-cache',type=Path)
    a=p.parse_args();probe(a.operation=='write',a.hls_build.resolve(),a.verilator.resolve(),a.report.resolve(),a.reuse_cache)
