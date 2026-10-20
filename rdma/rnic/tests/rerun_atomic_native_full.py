#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Fresh full-native cases after ONLY the Python normal-ACK oracle correction.

No RTL/bench change or new compilation: verify the exact prior frozen binary,
all consumed source/artifact hashes and the one-line verifier diff. Run ALL
three cases fresh, <=30sec each, never reuse a test result or relabel002.
Physical host/root/PHY/peer/PTP input remain models; no Linux/hardware/timing
claim. Ordinary READ/SEND_IMM still use the explicitly modeled MAC pins.
"""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import atomic_native_full_memory_fixture as fixture
import atomic_native_full_oracle as oracle
import probe_immediate_native_request as old

ROOT=fixture.ROOT;digest=fixture.original.source.digest


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--compiled-report',type=Path,required=True)
    p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve prior evidence')
    if shutil.disk_usage(ROOT).free<1024**3:raise RuntimeError('unchanged fresh native1GiB guard')
    prior=json.loads(a.compiled_report.read_text());oldrun=ROOT/prior['directory']
    if oldrun.parent!=ROOT/'rdma/rnic/build' or oldrun.is_symlink():raise ValueError('wrong previous run')
    binary=Path(prior['frozen_binary_path']);directory=binary.parent
    if directory.parent!=Path('/dev/shm') or not directory.name.startswith('as02-atomic-native-artifacts-') or directory.is_symlink():
        raise ValueError('wrong frozen RAM directory')
    if binary.name!='Vtb' or binary.is_symlink() or digest(binary)!=prior['binary_sha256']:raise ValueError('exact frozen binary changed')
    if binary.resolve()==Path(prior['compile_directory'])/'Vtb':raise ValueError('mutable compiler executable')
    oracle_path=Path(oracle.__file__).resolve();oracle_name=str(oracle_path.relative_to(ROOT))
    preimage=oldrun/'oracle-before-normal-ACK-syndrome-fix.py'
    if digest(preimage)!=prior['source_sha256'][oracle_name]:raise ValueError('missing exact previous verifier')
    expected=preimage.read_text().replace('bytes([0x1f])','bytes([0x1f if op==0x12 else 0x00])')
    if expected==preimage.read_text() or oracle_path.read_text()!=expected:raise ValueError('ONLY exact normal-ACK syndrome fix is permitted')
    before=dict(prior['source_sha256'])
    for n,h in before.items():
        path=preimage if n==oracle_name else ROOT/n
        if digest(path)!=h:raise ValueError('previous compiled source changed '+n)
    for key in ['artifact_sha256','RAM_artifact_sha256']:
        for n,h in prior[key].items():
            if digest(ROOT/n)!=h:raise ValueError('previous frozen artifact changed '+n)
    if fixture.bench()!=(oldrun/'tb.v').read_text():raise ValueError('current generated bench differs from compiled bench')
    # Source, not observed bytes, establishes ordinary ACK syndrome0. This
    # exact immutable HLS source is bound to the selected owned-HLS report.
    owned_report=ROOT/'results/2026-10-18/rocev2-rnic-atomic-owned-hls-001.json'
    owned=json.loads(owned_report.read_text())
    cpp=[ROOT/n for n in owned['source_sha256']if n.endswith('/ib_transport_protocol.cpp')]
    if len(cpp)!=1 or digest(cpp[0])!=owned['source_sha256'][str(cpp[0].relative_to(ROOT))]:raise ValueError('owned HLS source identity')
    if 'ackHeader.setSyndrome(meta.syndrome_valid ? meta.syndrome : ap_uint<8>(0x00));'not in cpp[0].read_text():
        raise ValueError('normal ACK source expectation changed')
    before[oracle_name]=digest(oracle_path);before[str(preimage.relative_to(ROOT))]=digest(preimage)
    own=[Path(__file__).resolve(),Path(fixture.__file__).resolve(),oracle_path,Path(old.__file__).resolve(),
        a.compiled_report.resolve(),*cpp]
    before.update({str(path.relative_to(ROOT)):digest(path)for path in own})
    run=Path(tempfile.mkdtemp(prefix='atomic-native-full-rerun-',dir=ROOT/'rdma/rnic/build'))
    report=dict(scope=__doc__,pass_test=False,directory=str(run.relative_to(ROOT)),source_sha256=before,
        frozen_binary_path=str(binary),binary_sha256=prior['binary_sha256'],compile_directory=prior['compile_directory'],
        prior_compiled_report=str(a.compiled_report.resolve().relative_to(ROOT)),prior_compilation_seconds=prior['compilation_seconds'],
        compilation_seconds=0,fresh_translation=False,exact_compiled_RTL_and_bench_reused=True,all_cases_fresh=True,
        corrected_oracle_only=True,actual_generated_HLS=True,Atomic_native_graph_selected=True,
        hardware_verified=False,standard_API_runtime=False,full_board_timing=False,two_state_simulation=True,
        both_global_drains_zero=True,default_hardware_changed=False,simulation_limit_seconds=30,tests={})
    try:
        for n in prior['artifact_sha256']:
            path=ROOT/n
            if path.suffix=='.dat':shutil.copy2(path,run/path.name)
        (run/'atomic-input.hex').write_text(fixture.fixtures())
        for name,opcode,immediate,args in [('ATOMIC_MIXED',2,0,['+ATOMIC_ONLY']),('READ',2,0,[]),
            ('SEND_IMM',5,0x89abcdef,['+SEND_IMM','+IMM=89abcdef'])]:
            words,records,request=fixture.old.old.variant(opcode,immediate);records=old.encode_records(records)
            fixtures={'input.hex':''.join(f'{w:x}\n'for w in words),
                'records.hex':''.join(f'{int.from_bytes(r,"little"):0128x}\n'for r in records)}
            for n,t in fixtures.items():(run/n).write_text(t);(run/(name+'-'+n)).write_text(t)
            start=time.monotonic()
            with(run/(name+'.log')).open('x')as log:
                r=subprocess.run([str(binary),*args],cwd=run,stdout=log,stderr=subprocess.STDOUT,timeout=30,preexec_fn=old.no_core)
            report['tests'][name]=dict(seconds=time.monotonic()-start,exit=r.returncode)
            if r.returncode:raise ValueError(name+' fresh full native run failed '+str(run/(name+'.log')))
            output=(run/(name+'.log')).read_text()
            if name=='ATOMIC_MIXED':report['tests'][name].update(oracle.verify(output))
            else:
                rows=[json.loads(line.split(' ',1)[1])for line in output.splitlines()if line.startswith('NATIVE_RNIC_RESULT ')]
                proof=[json.loads(line.split(' ',1)[1])for line in output.splitlines()if line.startswith('ATOMIC_NATIVE_OWNED_STAGE ')]
                if len(rows)!=1 or not rows[0]['pass_test'] or rows[0]['HLS_model'] or not rows[0]['CQ_committed'] or rows[0]['opcode']!=opcode:
                    raise ValueError('fresh native WR/CQ proof missing')
                if len(proof)!=1 or not all(proof[0][k]for k in ['actual_owned_HLS','actual_SQC_binding','Atomic_RX_selected']):
                    raise ValueError('wrong full native graph scope')
                report['tests'][name].update(summary=rows[0],stage_proof=proof[0],
                    actual_request_wire=fixture.old.old.verify(output,request,opcode),actual_C_profile_codec=True,physical_MAC_pin_model=True)
        for n,h in before.items():
            if digest(ROOT/n)!=h:raise ValueError('source changed during fresh simulations '+n)
        if digest(binary)!=prior['binary_sha256']:raise ValueError('executable changed')
        report.update(pass_test=True,source_unchanged=True)
    except Exception as e:report.update(error_type=type(e).__name__,error=str(e));raise
    finally:
        report['artifact_sha256']={str(path.relative_to(ROOT)):digest(path)for path in run.iterdir()if path.is_file()}
        report['RAM_artifact_sha256']={str(binary):digest(binary)}
        with a.report.open('x')as f:f.write(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(pass_test=True,tests={k:v['seconds']for k,v in report['tests'].items()})),flush=True)


if __name__=='__main__':main()
