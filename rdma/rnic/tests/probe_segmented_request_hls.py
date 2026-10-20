#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Bounded same-core real segmented WRITE/SEND plus all previous consumers.

One operation owner/final receipt, actual stored replays, strict independent
whole-wire reconstruction, per-packet ACK/pointer/pool/timer/PSN readbacks.
Connection, peer and source memory boundaries modeled; not native/HW proof.
"""
import argparse
import json
import os
from pathlib import Path
import resource
import shutil
import struct
import subprocess
import tempfile
import time
import probe_zero_service_hls as old

ROOT=old.ROOT;digest=old.digest;once=old.once


def harness():
    t=old.harness()
    t=once(t,'hls::stream<as02ReqToken> rx_owners,state_req;',
        'hls::stream<as02ReqToken> rx_owners,state_req,segment_continue;')
    t=once(t,'owners,admitted,rx_owners,af);','owners,admitted,rx_owners,af,segment_continue);')
    return once(t,'af|rf|ef|mf|tf|ff|pf,jf);','af|rf|ef|mf|tf|ff|pf,jf,segment_continue);')


def verify_wire(output):
    records=[];fresh={};replays=0
    for line in output.splitlines():
        if not line.startswith('SEGMENT_WIRE '):continue
        _,op,total,offset,psn,replay,hexdata=line.split();op,total,offset,psn,replay=map(int,[op,total,offset,psn,replay])
        actual=bytes.fromhex(hexdata);count=min(4096,total-offset);first=offset==0;last=offset+count==total
        opcode=(0 if first else 2 if last else 1)if op==3 else(6 if first else 8 if last else 7)
        padding=(-count)&3
        expected=bytes([opcode,0x40|(padding<<4),0xff,0xff,0])+int(196).to_bytes(3,'big')+b'\x80'+psn.to_bytes(3,'big')
        if op==1 and first:expected+=struct.pack('!QII',0xe23456789abcdef0,0x81234567,total)
        expected+=bytes((((offset+b)*37)^0xa5)&255 for b in range(count))+bytes(padding)
        if actual!=expected:raise ValueError('independent whole BTH/RETH/payload/padding/PSN oracle')
        key=(op,total,offset,psn)
        if replay:
            if fresh.get(key)!=actual:raise ValueError('real stored replay differs from exact fresh packet')
            replays+=1
        else:
            if key in fresh:raise ValueError('duplicate fresh packet')
            fresh[key]=actual
        records.append(dict(opcode=opcode,WR_opcode=op,total_bytes=total,offset=offset,PSN=psn,
            replay=bool(replay),wire_bytes=len(actual)))
    expected_cases=[(1,4097),(3,8192),(1,12289),(3,8193),(1,65537),(3,1048576)]
    psn=0xfffffe
    expected=[]
    for op,total in expected_cases:
        for offset in range(0,total,4096):expected.append((op,total,offset,psn));psn=(psn+1)&0xffffff
    if list(fresh)!=expected or replays!=7:raise ValueError('all complete message/packet/replay order and PSN span required')
    return records


def no_core():resource.setrlimit(resource.RLIMIT_CORE,(0,0))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True)
    p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve prior evidence')
    source=a.source.resolve();info=json.loads((source/'source.json').read_text())
    if info.get('HLS_top')!='rocev2_native_segmented_request_top' or info.get('large_WRITE_SEND_max_bytes')!=1048576:
        p.error('matched segmented full source required')
    for n,h in info['derived_sources'].items():
        if digest(source/'fns'/n)!=h:raise ValueError('derived source changed:'+n)
    hls=ROOT/'rdma/rnic/hls';bench=hls/'test_segmented_request.cpp'
    parents=[old,old.old,old.old.old,old.old.old.old,old.old.old.old.old,old.old.old.old.old.base]
    inputs=[*source.rglob('*'),bench,*[hls/('test_'+n+'.cpp')for n in
        ['zero_service','zero_rq','zero_request','atomic_request','immediate_receive']],
        *[Path(m.__file__).resolve()for m in parents],old.old.old.old.old.base.TEMPLATE,
        Path(__file__).resolve(),*hls.glob('*transport.py')]
    before={str(x.relative_to(ROOT)):digest(x)for x in inputs if x.is_file()}
    run=Path(tempfile.mkdtemp(prefix='segmented-request-csim-',dir=ROOT/'rdma/rnic/build'))
    ram=Path(tempfile.mkdtemp(prefix='as02-segmented-request-cxx-',dir='/dev/shm'))
    (run/'atomic_request_base.hpp').write_text(harness())
    t=(hls/'test_immediate_receive.cpp').read_text()
    t=t[t.index('template<int I> struct Endpoint {'):t.index('static ap_uint<620> request_owner(')]
    t=once(t,'void tick(bool retire=true)','void tick(bool retire=true,bool payload=true,bool tables=true)')
    (run/'zero_rq_endpoint.hpp').write_text(once(t,'        h.tick();','        h.tick(true,payload,tables);'))
    for n,main in [('atomic_request','atomic_compat_main'),('zero_request','previous_zero_request_main'),
                   ('zero_rq','previous_zero_rq_main'),('zero_service','previous_zero_service_main')]:
        (run/(n+'_prior.cpp')).write_text(once((hls/('test_'+n+'.cpp')).read_text(),'int main() {','int '+main+'() {'))
    shutil.copy2(bench,run/'test.cpp')
    flags=['-std=c++17','-O0','-pthread','-Wno-unknown-pragmas','-ffunction-sections','-fdata-sections','-Wl,--gc-sections',
        '-DFNS_DATA_WIDTH=64','-DFNS_ROCE_STACK_MAX_QPS=8','-D__VITIS_HLS__','-I'+str(run),
        '-I'+str(source/'adapter'),'-I'+str(source/'fns/hls'),'-I/home/user/amd/2025.2/Vitis/include']
    command=[shutil.which('g++-13'),*flags,str(run/'test.cpp'),str(source/'fns/hls/ib_transport_protocol/ib_utils.cpp'),
        str(source/'fns/hls/rocev2/rocev2.cpp'),'-o',str(ram/'test')]
    report=dict(scope=__doc__,pass_test=False,source_sha256=before,directory=str(run.relative_to(ROOT)),command=command,
        simulation_limit_seconds=30,full_top_CPP_compiled=False,generated_HLS_RTL=False,native_integration=False,
        hardware_verified=False,peer_connection_source_memory_modeled=True,multi_SGE_implemented=False)
    print(json.dumps(dict(directory=report['directory'],phase='compile')),flush=True)
    try:
        env=os.environ.copy();env['TMPDIR']=str(ram);start=time.monotonic()
        c=subprocess.run(command,capture_output=True,text=True,timeout=600,env=env)
        report['compile_seconds']=time.monotonic()-start;(run/'compile.log').write_text(c.stdout+c.stderr)
        if c.returncode:raise ValueError('segmented full-top compile failed:'+str(run/'compile.log'))
        report.update(full_top_CPP_compiled=True,RAM_artifact_sha256={str(ram/'test'):digest(ram/'test')})
        start=time.monotonic();r=subprocess.run([str(ram/'test')],capture_output=True,text=True,timeout=30,preexec_fn=no_core)
        report['simulation_seconds']=time.monotonic()-start;(run/'simulation.log').write_text(r.stdout+r.stderr)
        if r.returncode:raise ValueError('actual segmented consumers failed:'+str(run/'simulation.log'))
        summaries={}
        for marker in ['ATOMIC_REQUEST_HLS','ZERO_REQUEST_HLS','ZERO_RQ_HLS','ZERO_SERVICE_HLS','SEGMENTED_REQUEST_HLS','SEGMENTED_REQUEST_POLICY']:
            rows=[json.loads(l.split(' ',1)[1])for l in r.stdout.splitlines()if l.startswith(marker+' ')]
            if len(rows)!=1 or not rows[0].get('pass_test'):raise ValueError('missing actual '+marker)
            summaries[marker]=rows[0]
        if summaries['SEGMENTED_REQUEST_POLICY']['actual_no_issue_negatives']!=5:
            raise ValueError('full unsupported/oversize rejection coverage required')
        wire=verify_wire(r.stdout)
        if any(digest(ROOT/n)!=h for n,h in before.items()):raise ValueError('consumed source changed')
        report.update(pass_test=True,source_unchanged=True,summaries=summaries,wire_oracles=wire)
    except Exception as e:report.update(error_type=type(e).__name__,error=str(e));raise
    finally:
        report['artifact_sha256']={str(x.relative_to(ROOT)):digest(x)for x in run.iterdir()if x.is_file()}
        with a.report.open('x')as f:f.write(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k]for k in ['pass_test','compile_seconds','simulation_seconds','summaries']}))


if __name__=='__main__':main()
