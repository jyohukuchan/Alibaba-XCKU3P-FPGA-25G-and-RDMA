#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Short C++ proof of actual derived owner-bearing FNS RX IBH/EXH execution.

Native contexts, state/MSN/read-init responses are explicit models. No native
runtime admission/pins/PCIe/MAC/CQ/ONE-shared graph, RTL or physical proof.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

ROOT=Path(__file__).resolve().parents[3]
spec=importlib.util.spec_from_file_location('owned_rx_execution',ROOT/'rdma/rnic/hls/owned_rx_execution_profile.py')
p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--vitis-include',type=Path,required=True)
    ap.add_argument('--report',type=Path,required=True)
    args=ap.parse_args()
    args.report=args.report.resolve()
    if args.report.exists():ap.error('preserve earlier evidence; choose a new report')
    if not (args.vitis_include/'ap_int.h').is_file():ap.error('actual Vitis include/ap_int.h required')
    if not args.report.resolve().is_relative_to(ROOT/'results'):ap.error('report must be under repository results/')
    compiler=shutil.which('g++-13') or shutil.which('g++')
    if not compiler:ap.error('C++ compiler unavailable')
    # This is a small C-only compile, NOT a relaxed HLS/XSIM disk guard.
    # Existing HLS/XSIM1500MiB admission thresholds remain unchanged.
    if shutil.disk_usage(ROOT).free<256*1024*1024:ap.error('C-only fixture requires256MiB free')
    fns=p.source.BASE/'fns/hls';config=p.source.BASE/'adapter/rocev2_config.hpp'
    own=[Path(__file__).resolve(),Path(p.__file__).resolve(),ROOT/'rdma/rnic/hls/test_owned_rx_execution.cpp',config]
    own+=list((ROOT/'rdma/rnic/hls').glob('*.py'))
    own+=sorted(q for q in fns.rglob('*') if q.is_file() and q.suffix in {'.hpp','.h','.cpp'})
    own=list(dict.fromkeys(own))
    before={str(q.relative_to(ROOT)):sha(q)for q in own}
    # Transform the actual retained FNS functions, failing closed on anchors.
    generated=p.derive(p.CPP.read_text())
    run=Path(tempfile.mkdtemp(prefix='owned-rx-execution-',dir=ROOT/'rdma/rnic/build'))
    inputs=run/'inputs';inputs.mkdir()
    for q in own:
        if q.is_relative_to(fns):dest=inputs/'fns/hls'/q.relative_to(fns)
        elif q==config:dest=inputs/'adapter/rocev2_config.hpp'
        else:dest=inputs/'profile'/q.relative_to(ROOT)
        dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(q,dest)
        assert sha(dest)==before[str(q.relative_to(ROOT))]
    header=inputs/'owned_rx_execution.hpp';header.write_text(generated)
    test=inputs/'test_owned_rx_execution.cpp';shutil.copy2(ROOT/'rdma/rnic/hls/test_owned_rx_execution.cpp',test)
    frozen={str(q.relative_to(inputs)):sha(q)for q in inputs.rglob('*') if q.is_file()}
    def unchanged():
        assert all(sha(ROOT/n)==h for n,h in before.items()),'source changed'
        assert frozen=={str(q.relative_to(inputs)):sha(q)for q in inputs.rglob('*') if q.is_file()},'frozen input changed'
    result=dict(scope=__doc__,pass_test=False,terminal_exit_status=None,
        retained_directory=str(run.relative_to(ROOT)),source_sha256=before,frozen_source_sha256=frozen,
        actual_FNS_RX_IBH_EXH_derivatives=True,owner_bits=1612,native_context_bits=588,packet_token_bits=1024,
        immutable_retry_lease_bits=248,full_native_address_bits=64,full_WR_length_bits=32,
        clock_period_ns=4,metadata_entries=2000,pointer_entries=8,PMTU=4096,
        source_and_frozen_inputs_unchanged=False,simulation_wall_bound_seconds=30,
        compiler=str(compiler),Vitis_include=str(args.vitis_include.resolve()),
        actual_native_admission=False,actual_state_MSN_readinit_services=False,
        ONE_shared_native_graph=False,RTL_tested=False,HLS_constructed=False,
        physical_signoff=False,hardware_verified=False,whole_core_drain=False,native_DMA_CQ=False,
        shared_local_core_drained=0,WR_MR_refs='HELD; no CQ/release output')
    command=[compiler,'-std=c++17','-O1','-g0','-pthread','-Wno-unknown-pragmas',
        '-fsanitize=undefined','-fno-sanitize-recover=all','-DFNS_DATA_WIDTH=64','-DFNS_ROCE_STACK_MAX_QPS=8',
        '-D__VITIS_HLS__','-I'+str(inputs/'adapter'),'-I'+str(inputs/'fns/hls'),
        '-I'+str(inputs/'fns/hls/ib_transport_protocol'),'-I'+str(args.vitis_include.resolve()),
        str(test),'-o',str(run/'test')]
    (run/'compile-command.json').write_text(json.dumps(command,indent=2)+'\n')
    try:
        unchanged();start=time.monotonic()
        with (run/'compile.log').open('x')as out:
            built=subprocess.run(command,cwd=run,stdout=out,stderr=subprocess.STDOUT,timeout=180)
        result['compile_seconds']=time.monotonic()-start
        if built.returncode:raise RuntimeError('actual RX execution C++ compilation failed')
        start=time.monotonic()
        simulation=subprocess.run([str(run/'test')],cwd=run,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=30)
        result['simulation_seconds']=time.monotonic()-start
        result['simulation_exit_status']=simulation.returncode
        (run/'run.stdout.log').write_text(simulation.stdout)
        if simulation.returncode:raise RuntimeError('actual RX execution C++ assertions/UBSan failed')
        prefix='OWNED_RX_EXECUTION '
        rows=[json.loads(s[len(prefix):])for s in simulation.stdout.splitlines()if s.startswith(prefix)]
        assert len(rows)==1 and rows[0]['pass_test']
        summary=rows[0]
        assert summary['positive_transactions']==12 and summary['AETH_values']==256 and summary['AETH_packets']==736 and summary['nonpositive_control_packets']==672
        assert summary['full_owner_bit_comparisons']==1612 and summary['negative_cases']>=18
        assert summary['full64_native_address'] and summary['full32_WR_length'] and summary['raw_padding_separate_from_DMA_length'] and not summary['RTL_tested'] and not summary['native_DMA_CQ']
        unchanged();result.update(pass_test=True,terminal_exit_status=0,source_and_frozen_inputs_unchanged=True,summary=summary)
        print(json.dumps(dict(record=str(args.report.relative_to(ROOT)),summary=summary,simulation_seconds=result['simulation_seconds'])),flush=True)
    except Exception as error:
        result.update(pass_test=False,terminal_exit_status=1,error_type=type(error).__name__,error=str(error));raise
    finally:
        result['artifact_sha256']={str(q.relative_to(ROOT)):sha(q)for q in run.iterdir()if q.is_file()}
        with args.report.open('x')as out:out.write(json.dumps(result,indent=2)+'\n')

if __name__=='__main__':main()
