#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Bounded actual FNS TX-producer C++ checks; no native/RTL/physical signoff."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import time

from fast_transport_sim import bounded
ROOT=Path(__file__).resolve().parents[3]
spec=importlib.util.spec_from_file_location('wire_tx',ROOT/'rdma/rnic/hls/owned_wire_tx_profile.py')
p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)
def digest(f):return hashlib.sha256(Path(f).read_bytes()).hexdigest()

def main():
    import tempfile
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vitis-include',type=Path,required=True)
    parser.add_argument('--report',type=Path,required=True)
    a=parser.parse_args()
    if a.report.exists():parser.error('preserve earlier evidence; choose a new report')
    originals={str(f.relative_to(p.BASE)):digest(f)for f in p.BASE.rglob('*')if f.is_file()}
    sources=[Path(__file__).resolve(),Path(p.__file__).resolve(),Path(p.owned.__file__).resolve(),
        Path(p.owned.base.__file__).resolve(),Path(p.owned.base.base.__file__).resolve(),
        p.CPP,p.HPP,p.META,ROOT/'rdma/rnic/hls/test_owned_wire_tx.cpp',
        ROOT/'rdma/rnic/tests/fast_transport_sim.py']
    identities={str(f.relative_to(ROOT)):digest(f)for f in sources}
    run=Path(tempfile.mkdtemp(prefix='owned-wire-tx-',dir=ROOT/'rdma/rnic/build'))
    inp=run/'inputs';inp.mkdir()
    # Freeze exact sources even if derivation/compilation fails. Compiler output
    # is generated into this owned run only; raw baseline/rollback untouched.
    shutil.copytree(p.BASE/'fns',inp/'fns');shutil.copytree(p.BASE/'adapter',inp/'adapter')
    (inp/'profile').mkdir()
    for f in sources:
        dest=inp/'profile'/f.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,dest)
    result=dict(scope=__doc__,pass_test=False,terminal_exit_status=None,retained_directory=str(run.relative_to(ROOT)),
        source_sha256=identities,original_source_sha256=originals,simulations=[],
        source_and_frozen_inputs_unchanged=False,actual_selected_FNS_TX_producers=5,
        metadata_entries=2000,pointer_entries=8,original_clock_ns=4,
        RTL_simulated=False,HLS_constructed=False,physical_signoff=False,
        native_admission_connected=False,actual_RX_context_lookup=False,
        actual_ordered_full_wire_producer_fences=False,MAC_SFD_verified=False,
        selected_in_shared_native_or_board=False,whole_core_drain=False,native_CQ=False,hardware_verified=False)
    try:
        (inp/'fns/hls/ib_transport_protocol/retransmitter/owned_retrans_fence.hpp').write_text(p.owned.derive(p.META.read_text()))
        (inp/'fns/hls/ib_transport_protocol/owned_wire_tx.hpp').write_text(p.derive(p.CPP.read_text(),p.HPP.read_text(),p.META.read_text()))
        shutil.copy2(ROOT/'rdma/rnic/hls/test_owned_wire_tx.cpp',inp/'test_owned_wire_tx.cpp')
        frozen={str(f.relative_to(inp)):digest(f)for f in inp.rglob('*')if f.is_file()}
        result['frozen_source_sha256']=frozen
        def current():
            assert originals=={str(f.relative_to(p.BASE)):digest(f)for f in p.BASE.rglob('*')if f.is_file()}
            assert identities=={n:digest(ROOT/n)for n in identities}
            assert frozen=={n:digest(inp/n)for n in frozen}
            assert (inp/'fns/hls/ib_transport_protocol/owned_wire_tx.hpp').read_text()==p.derive(p.CPP.read_text(),p.HPP.read_text(),p.META.read_text())
        current();compiler=shutil.which('g++-13')or shutil.which('g++')
        command=[compiler,'-std=c++17','-O2','-pthread','-Wno-unknown-pragmas',
            '-DFNS_DATA_WIDTH=64','-DFNS_ROCE_STACK_MAX_QPS=8','-D__VITIS_HLS__',
            '-I'+str(inp/'adapter'),'-I'+str(inp/'fns/hls'),'-I'+str(a.vitis_include.resolve()),
            str(inp/'test_owned_wire_tx.cpp'),'-o',str(run/'test')]
        (run/'compile-command.json').write_text(json.dumps(command,indent=2)+'\n')
        print(json.dumps(dict(phase='compile_actual_FNS_producers',retained_directory=str(run))),flush=True)
        started=time.monotonic()
        with(run/'compile.log').open('x')as log:c=bounded(command,run,120,log)
        result['compile_seconds']=time.monotonic()-started
        if c.returncode:raise RuntimeError('C++ compile failed; retain '+str(run/'compile.log'))
        binary=digest(run/'test');result['compiled_binary_sha256']=binary
        for case in range(1,17):
            current();assert digest(run/'test')==binary
            started=time.monotonic();r=bounded([str(run/'test'),str(case)],run,30)
            seconds=time.monotonic()-started
            (run/f'case-{case}.log').write_text(r.stdout+r.stderr)
            if r.returncode:raise RuntimeError('actual producer case failed: '+str(case))
            rows=[json.loads(line)for line in r.stdout.splitlines()if line.startswith('{')]
            assert len(rows)==1 and rows[0]['pass_test'] and rows[0]['case']==case
            assert digest(run/'test')==binary;current()
            result['simulations'].append(dict(case=case,seconds=seconds,summary=rows[0],binary_unchanged=True))
            print(json.dumps(dict(case=case,seconds=seconds,pass_test=True)),flush=True)
        assert len(result['simulations'])==16
        result.update(pass_test=True,terminal_exit_status=0,source_and_frozen_inputs_unchanged=True)
    except Exception as error:
        result.update(error=str(error),error_type=type(error).__name__,terminal_exit_status=1)
        raise
    finally:
        result['artifact_sha256']={str(f.relative_to(ROOT)):digest(f)for f in run.iterdir()if f.is_file()}
        with a.report.open('x')as out:out.write(json.dumps(result,indent=2)+'\n')

if __name__=='__main__':main()
