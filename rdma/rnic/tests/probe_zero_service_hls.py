#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Fresh complete C++ zero WRITE/READ service plus old zero/RQ/Atomic cases.

Actual RETH/owner/RX/MSN/PSN/response consumers execute. Outer QP owner,
peer, connection, memory and physical MAC boundaries are models. No native
RTL, standard API, physical board or timing proof. Each runtime <=30s.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import probe_zero_rq_hls as old

ROOT=old.ROOT;digest=old.digest;once=old.once


def harness():
    t=old.old.harness()
    t=once(t,'    hls::stream<as02AtomicCommit> atomic_commit;',
        '    hls::stream<as02AtomicCommit> atomic_commit;\n'
        '    hls::stream<as02ZeroOwner> zero_owners,zero_data;\n'
        '    hls::stream<as02ZeroDone> zero_done,zero_commit,zero_tx;')
    t=once(t,'exh_words,recv_ack);','exh_words,recv_ack,zero_tx);')
    t=once(t,'atomic_commit,rx_owners,rf);','atomic_commit,rx_owners,rf,zero_owners,zero_done,zero_commit);')
    t=once(t,'recv_fault,ack_consumed,ef);','recv_fault,ack_consumed,ef,zero_data,zero_tx,zero_commit);')
    t=once(t,'read_consumed,pf);','read_consumed,pf,zero_data);')
    return 'static bool zero_rq_ack_enabled=true;\n'+once(t,
        '        generate_exh<512,I>(', '        if(zero_rq_ack_enabled)generate_exh<512,I>(')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True)
    p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve previous evidence')
    source=a.source.resolve();info=json.loads((source/'source.json').read_text())
    if info.get('HLS_top')!='rocev2_native_zero_service_top' or not info.get('normal_zero_responder_WRITE_READ') or \
       (info.get('zero_service_owner_bits'),info.get('zero_service_done_bits'))!=(344,400):
        p.error('matched complete zero service source required')
    for n,h in info['derived_sources'].items():
        if digest(source/'fns'/n)!=h:raise ValueError('generated source changed: '+n)
    hls=ROOT/'rdma/rnic/hls';bench=hls/'test_zero_service.cpp'
    inputs=[*source.rglob('*'),bench,*[hls/n for n in ['test_zero_rq.cpp','test_zero_request.cpp',
        'test_atomic_request.cpp','test_immediate_receive.cpp']],*[Path(m.__file__).resolve()for m in [old,old.old,
        old.old.old,old.old.old.old,old.old.old.old.base]],old.old.old.old.base.TEMPLATE,
        Path(__file__).resolve(),*hls.glob('*transport.py')]
    before={str(x.relative_to(ROOT)):digest(x)for x in inputs if x.is_file()}
    run=Path(tempfile.mkdtemp(prefix='zero-service-csim-',dir=ROOT/'rdma/rnic/build'))
    ram=Path(tempfile.mkdtemp(prefix='as02-zero-service-cxx-',dir='/dev/shm'))
    (run/'atomic_request_base.hpp').write_text(harness())
    t=(hls/'test_immediate_receive.cpp').read_text()
    t=t[t.index('template<int I> struct Endpoint {'):t.index('static ap_uint<620> request_owner(')]
    t=once(t,'void tick(bool retire=true)','void tick(bool retire=true,bool payload=true,bool tables=true)')
    (run/'zero_rq_endpoint.hpp').write_text(once(t,'        h.tick();','        h.tick(true,payload,tables);'))
    for n,main in [('atomic_request','atomic_compat_main'),('zero_request','previous_zero_request_main'),
                   ('zero_rq','previous_zero_rq_main')]:
        (run/(n+'_prior.cpp')).write_text(once((hls/('test_'+n+'.cpp')).read_text(),'int main() {','int '+main+'() {'))
    shutil.copy2(bench,run/'test.cpp')
    flags=['-std=c++17','-O0','-pthread','-Wno-unknown-pragmas','-ffunction-sections','-fdata-sections','-Wl,--gc-sections',
        '-DFNS_DATA_WIDTH=64','-DFNS_ROCE_STACK_MAX_QPS=8','-D__VITIS_HLS__','-I'+str(run),
        '-I'+str(source/'adapter'),'-I'+str(source/'fns/hls'),'-I/home/user/amd/2025.2/Vitis/include']
    cmd=[shutil.which('g++-13'),*flags,str(run/'test.cpp'),str(source/'fns/hls/ib_transport_protocol/ib_utils.cpp'),
        str(source/'fns/hls/rocev2/rocev2.cpp'),'-o',str(ram/'test')]
    report=dict(scope=__doc__,pass_test=False,source_sha256=before,directory=str(run.relative_to(ROOT)),command=cmd,
        simulation_limit_seconds=30,full_top_CPP_compiled=False,generated_HLS_RTL=False,native_integration=False,
        hardware_verified=False,outer_QP_owner_peer_connection_memory_MAC_modeled=True)
    print(json.dumps(dict(directory=report['directory'],phase='compile')),flush=True)
    try:
        env=os.environ.copy();env['TMPDIR']=str(ram);start=time.monotonic()
        c=subprocess.run(cmd,capture_output=True,text=True,timeout=600,env=env)
        report['compile_seconds']=time.monotonic()-start;(run/'compile.log').write_text(c.stdout+c.stderr)
        if c.returncode:raise ValueError('complete zero service compile failed: '+str(run/'compile.log'))
        report.update(full_top_CPP_compiled=True,RAM_artifact_sha256={str(ram/'test'):digest(ram/'test')})
        start=time.monotonic();r=subprocess.run([str(ram/'test')],capture_output=True,text=True,timeout=30)
        report['simulation_seconds']=time.monotonic()-start;(run/'simulation.log').write_text(r.stdout+r.stderr)
        if r.returncode:raise ValueError('actual zero service consumers failed: '+str(run/'simulation.log'))
        summaries={}
        for marker in ['ATOMIC_REQUEST_HLS','ZERO_REQUEST_HLS','ZERO_RQ_HLS','ZERO_SERVICE_HLS']:
            rows=[json.loads(l.split(' ',1)[1])for l in r.stdout.splitlines()if l.startswith(marker+' ')]
            if len(rows)!=1 or not rows[0].get('pass_test'):raise ValueError('missing actual '+marker)
            summaries[marker]=rows[0]
        receipts=[l for l in r.stdout.splitlines()if l.startswith('ZERO_SERVICE_DONE ')]
        packets=[l for l in r.stdout.splitlines()if l.startswith('ZERO_SERVICE_WIRE ')]
        if len(receipts)!=4 or len(packets)!=4 or summaries['ZERO_SERVICE_HLS']['owner_and_RETH_negatives']!=16:
            raise ValueError('incomplete actual service tests')
        if any(digest(ROOT/n)!=h for n,h in before.items()):raise ValueError('consumed source changed')
        report.update(pass_test=True,source_unchanged=True,summaries=summaries,service_receipts=receipts,service_packets=packets)
    except Exception as e:report.update(error_type=type(e).__name__,error=str(e));raise
    finally:
        report['artifact_sha256']={str(x.relative_to(ROOT)):digest(x)for x in run.iterdir()if x.is_file()}
        with a.report.open('x')as f:f.write(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k]for k in ['pass_test','compile_seconds','simulation_seconds','summaries']}))


if __name__=='__main__':main()
