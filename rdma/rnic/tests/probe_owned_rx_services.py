#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Bounded C/UBSan actual RX+SAME state/MSN table composition.

Native admission/QPI/TX allocation and read-init are explicit fixtures; no
native host/pool/PCIe/MAC/CQ/ONE shared graph/RTL/physical completion proof.
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
spec=importlib.util.spec_from_file_location('owned_rx_services',ROOT/'rdma/rnic/hls/owned_rx_services_profile.py')
p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)
def sha(q):return hashlib.sha256(q.read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--vitis-include',type=Path,required=True);ap.add_argument('--report',type=Path,required=True);a=ap.parse_args()
    a.report=a.report.resolve();a.vitis_include=a.vitis_include.resolve()
    if a.report.exists():ap.error('preserve earlier evidence')
    if not a.report.is_relative_to(ROOT/'results'):ap.error('report must be in repository results/')
    if not (a.vitis_include/'ap_int.h').is_file():ap.error('actual Vitis include required')
    compiler=shutil.which('g++-13')or shutil.which('g++')
    if not compiler:ap.error('C++ compiler unavailable')
    if shutil.disk_usage(ROOT).free<256*1024*1024:ap.error('small C compile requires256MiB; HLS/XSIM1500MiB guard unchanged')
    fns=p.BASE/'fns/hls';config=p.BASE/'adapter/rocev2_config.hpp'
    own=[Path(__file__).resolve(),ROOT/'rdma/rnic/hls/test_owned_rx_services.cpp',ROOT/'rdma/rnic/hls/test_owned_rx_execution.cpp',config]
    own+=list((ROOT/'rdma/rnic/hls').glob('*.py'))
    own+=sorted(q for q in fns.rglob('*')if q.is_file()and q.suffix in {'.hpp','.h','.cpp'})
    own=list(dict.fromkeys(own));before={str(q.relative_to(ROOT)):sha(q)for q in own}
    generated=p.derive(p.STATE.read_text(),p.MSN.read_text());rx_generated=p.rx.derive(p.rx.CPP.read_text())
    run=Path(tempfile.mkdtemp(prefix='owned-rx-services-',dir=ROOT/'rdma/rnic/build'));inputs=run/'inputs';inputs.mkdir()
    for q in own:
        if q.is_relative_to(fns):dest=inputs/'fns/hls'/q.relative_to(fns)
        elif q==config:dest=inputs/'adapter/rocev2_config.hpp'
        else:dest=inputs/'profile'/q.relative_to(ROOT)
        dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(q,dest);assert sha(dest)==before[str(q.relative_to(ROOT))]
    (inputs/'owned_rx_services.hpp').write_text(generated);(inputs/'owned_rx_execution.hpp').write_text(rx_generated)
    for name in ['test_owned_rx_services.cpp','test_owned_rx_execution.cpp']:shutil.copy2(ROOT/'rdma/rnic/hls'/name,inputs/name)
    frozen={str(q.relative_to(inputs)):sha(q)for q in inputs.rglob('*')if q.is_file()}
    def unchanged():
        assert all(sha(ROOT/n)==h for n,h in before.items())
        assert frozen=={str(q.relative_to(inputs)):sha(q)for q in inputs.rglob('*')if q.is_file()}
    record=dict(scope=__doc__,pass_test=False,terminal_exit_status=None,retained_directory=str(run.relative_to(ROOT)),
        source_sha256=before,frozen_source_sha256=frozen,actual_derived_FNS_RX_state_MSN=True,RX_state_MSN_models=False,
        native_admission_QPI_TXallocation_readinit_models=True,one_actual_state_RAM_and_MSN_RAM_per_instance=True,
        source_and_frozen_inputs_unchanged=False,simulation_wall_bound_seconds=30,clock_period_ns=4,
        state_entries=8,MSN_entries=8,retransmission_metadata_entries=2000,original_clocks_or_capacity_reduced=False,
        HLS_constructed=False,RTL_tested=False,hardware_verified=False,physical_signoff=False,
        actual_pool_readinit=False,ONE_shared_native_graph=False,native_DMA_CQ=False,whole_core_drain=False,WR_MR_refs='HELD')
    command=[compiler,'-std=c++17','-O1','-g0','-pthread','-Wno-unknown-pragmas','-fsanitize=undefined','-fno-sanitize-recover=all',
        '-DFNS_DATA_WIDTH=64','-DFNS_ROCE_STACK_MAX_QPS=8','-D__VITIS_HLS__','-I'+str(inputs/'adapter'),'-I'+str(inputs/'fns/hls'),
        '-I'+str(inputs/'fns/hls/ib_transport_protocol'),'-I'+str(a.vitis_include),str(inputs/'test_owned_rx_services.cpp'),'-o',str(run/'test')]
    (run/'compile-command.json').write_text(json.dumps(command,indent=2)+'\n')
    try:
        unchanged();start=time.monotonic()
        with (run/'compile.log').open('x')as out:result=subprocess.run(command,cwd=run,stdout=out,stderr=subprocess.STDOUT,timeout=180)
        record['compile_seconds']=time.monotonic()-start
        if result.returncode:raise RuntimeError('actual service composition C++ compilation failed')
        start=time.monotonic();result=subprocess.run([str(run/'test')],cwd=run,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=30)
        record['simulation_seconds']=time.monotonic()-start;record['simulation_exit_status']=result.returncode
        (run/'run.stdout.log').write_text(result.stdout)
        if result.returncode:raise RuntimeError('actual service composition assertion/UBSan failed')
        prefix='OWNED_RX_SERVICES ';rows=[json.loads(s[len(prefix):])for s in result.stdout.splitlines()if s.startswith(prefix)]
        assert len(rows)==1 and rows[0]['pass_test'];summary=rows[0]
        assert summary['actual_READ_packets']==34 and summary['actual_WRITE_ACKs']==2 and summary['actual_RX_packets']==36
        assert summary['negative_service_cases']==14 and summary['ordered_state_fences']==2
        assert summary['state_entries']==8 and summary['MSN_entries']==8 and not summary['RX_state_MSN_models']
        assert not summary['RTL_tested']and not summary['native_DMA_CQ']and not summary['whole_core_drain']
        unchanged();record.update(pass_test=True,terminal_exit_status=0,source_and_frozen_inputs_unchanged=True,summary=summary)
        print(json.dumps(dict(record=str(a.report.relative_to(ROOT)),summary=summary,simulation_seconds=record['simulation_seconds'])),flush=True)
    except Exception as error:
        record.update(pass_test=False,terminal_exit_status=1,error_type=type(error).__name__,error=str(error));raise
    finally:
        record['artifact_sha256']={str(q.relative_to(ROOT)):sha(q)for q in run.iterdir()if q.is_file()}
        with a.report.open('x')as out:out.write(json.dumps(record,indent=2)+'\n')
if __name__=='__main__':main()
