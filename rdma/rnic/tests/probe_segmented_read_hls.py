#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual new READ HLS consumers and every prior segmented WRITE/SEND case.

One genuine READ request/whole receipt, FIRST/MIDDLE/LAST response payloads,
actual pointer/pool/timer/common-state consumers. Peer/connection/memory are
models; no CRC/native DMA/CQ/Linux/physical/timing or trusted MSN-wiring claim.
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
import probe_segmented_request_hls as old

ROOT=old.ROOT;once=old.once;digest=old.digest


def verify_read(output):
    requests=[];packets=[]
    for line in output.splitlines():
        if line.startswith('SEGMENTED_READ_REQUEST '):
            _,length,psn,replay,wire=line.split();length,psn,replay=map(int,[length,psn,replay]);wire=bytes.fromhex(wire)
            expected=bytes([12,0x40,0xff,0xff,0])+int(196).to_bytes(3,'big')+b'\x80'+psn.to_bytes(3,'big')
            expected+=int(0xe23456789abcdef0).to_bytes(8,'big')+int(0x81234567).to_bytes(4,'big')+length.to_bytes(4,'big')
            if wire!=expected:raise ValueError('independent true READ request RETH/BTH oracle')
            requests.append((length,psn,replay))
        elif line.startswith('SEGMENTED_READ_DATA '):
            _,length,offset,data=line.split();length,offset=map(int,[length,offset]);data=bytes.fromhex(data)
            count=min(4096,length-offset);expected=bytes((((offset+i)*37)^0xc3)&255 for i in range(count))+bytes((-count)&3)
            if data!=expected:raise ValueError('independent actual destination payload/zero-pad oracle')
            packets.append((length,offset))
    psn=0xfffffe;req=[];data=[]
    for length in [4097,8193,65537,1048576]:
        req.extend([(length,psn,0),(length,psn,1)])
        for offset in range(0,length,4096):data.append((length,offset));psn=(psn+1)&0xffffff
    if requests!=req or packets!=data:raise ValueError('all request/replay/response extent/order/PSN cases required')
    return dict(requests=len(requests),response_packets=len(packets),independent_wire_payload_oracles=True)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve previous evidence')
    source=a.source.resolve();info=json.loads((source/'source.json').read_text())
    if info.get('HLS_top')!='rocev2_native_segmented_read_top'or info.get('large_READ_max_bytes')!=1048576:raise ValueError('matched new source required')
    for n,h in info['derived_sources'].items():
        if digest(source/'fns'/n)!=h:raise ValueError('derived source changed:'+n)
    run=Path(tempfile.mkdtemp(prefix='segmented-read-hls-',dir=ROOT/'rdma/rnic/build'))
    ram=Path(tempfile.mkdtemp(prefix='as02-segmented-read-hls-',dir='/dev/shm'));hls=ROOT/'rdma/rnic/hls'
    t=once(old.harness(),'hls::stream<as02ReqToken> rx_owners,state_req,segment_continue;',
        'hls::stream<as02ReqRxOwner> rx_owners;hls::stream<as02ReqToken> state_req,segment_continue;')
    (run/'atomic_request_base.hpp').write_text(t)
    t=(hls/'test_immediate_receive.cpp').read_text();t=t[t.index('template<int I> struct Endpoint {'):t.index('static ap_uint<620> request_owner(')]
    t=once(t,'void tick(bool retire=true)','void tick(bool retire=true,bool payload=true,bool tables=true)')
    (run/'zero_rq_endpoint.hpp').write_text(once(t,'        h.tick();','        h.tick(true,payload,tables);'))
    for n,main in [('atomic_request','atomic_compat_main'),('zero_request','previous_zero_request_main'),
                   ('zero_rq','previous_zero_rq_main'),('zero_service','previous_zero_service_main'),('segmented_request','preceding_segmented_main')]:
        t=once((hls/('test_'+n+'.cpp')).read_text(),'int main() {','int '+main+'() {')
        if n=='segmented_request':t=once(t,'segmented_policy_negative<1604>(2,4097);','segmented_policy_negative<1604>(2,1048577);')
        (run/(n.replace('_request','')+'_prior.cpp'if n=='segmented_request'else n+'_prior.cpp')).write_text(t)
    shutil.copy2(hls/'test_segmented_read.cpp',run/'test.cpp')
    inputs=[*source.rglob('*'),*hls.glob('*transport.py'),*[hls/('test_'+n+'.cpp')for n in
        ['segmented_read','segmented_request','zero_service','zero_rq','zero_request','atomic_request','immediate_receive']],
        Path(__file__).resolve(),Path(old.__file__).resolve(),old.old.old.old.old.old.base.TEMPLATE]
    helpers=[old.old,old.old.old,old.old.old.old,old.old.old.old.old,old.old.old.old.old.old,old.old.old.old.old.old.base]
    inputs.extend(Path(m.__file__).resolve()for m in helpers)
    before={str(p.relative_to(ROOT)):digest(p)for p in inputs if p.is_file()}
    flags=['-std=c++17','-O0','-pthread','-Wno-unknown-pragmas','-ffunction-sections','-fdata-sections','-Wl,--gc-sections',
        '-DFNS_DATA_WIDTH=64','-DFNS_ROCE_STACK_MAX_QPS=8','-D__VITIS_HLS__','-I'+str(run),'-I'+str(source/'adapter'),
        '-I'+str(source/'fns/hls'),'-I/home/user/amd/2025.2/Vitis/include']
    command=[shutil.which('g++-13'),*flags,str(run/'test.cpp'),str(source/'fns/hls/ib_transport_protocol/ib_utils.cpp'),
        str(source/'fns/hls/rocev2/rocev2.cpp'),'-o',str(ram/'test')]
    report=dict(scope=__doc__,pass_test=False,directory=str(run.relative_to(ROOT)),source_sha256=before,compile_command=command,
        runtime_limit_seconds=30,compile_limit_seconds=600,generated_HLS=False,native_integration=False,hardware_verified=False,
        trusted_REMOTE_MSN_source_implemented=False,mid_READ_retry_recovery_qualified=False,tests={})
    try:
        start=time.monotonic();env=os.environ.copy();env['TMPDIR']=str(ram)
        c=subprocess.run(command,capture_output=True,text=True,timeout=600,env=env);report['compile_seconds']=time.monotonic()-start
        (run/'compile.log').write_text(c.stdout+c.stderr)
        if c.returncode:raise ValueError('actual new HLS C++ compile failed:'+str(run/'compile.log'))
        for mode in ['prior','read','bad0','bad1','bad2','bad3']:
            start=time.monotonic();r=subprocess.run([str(ram/'test'),mode],capture_output=True,text=True,timeout=30,preexec_fn=old.no_core)
            (run/(mode+'.log')).write_text(r.stdout+r.stderr);item=dict(seconds=time.monotonic()-start,exit=r.returncode);report['tests'][mode]=item
            if r.returncode:raise ValueError(mode+' actual HLS consumer failed:'+str(run/(mode+'.log')))
            if mode=='prior':
                item['prior_wire_oracles']=old.verify_wire(r.stdout)
                markers=['ATOMIC_REQUEST_HLS','ZERO_REQUEST_HLS','ZERO_RQ_HLS','ZERO_SERVICE_HLS','SEGMENTED_REQUEST_HLS','SEGMENTED_REQUEST_POLICY']
            elif mode=='read':item['independent_read_oracles']=verify_read(r.stdout);markers=['SEGMENTED_READ_HLS']
            else:
                if 'SEGMENTED_READ_NEGATIVE '+mode[-1]not in r.stdout:raise ValueError('negative assertion missing')
                markers=[]
            item['summaries']={}
            for marker in markers:
                rows=[json.loads(l.split(' ',1)[1])for l in r.stdout.splitlines()if l.startswith(marker+' ')]
                if len(rows)!=1 or not rows[0]['pass_test']:raise ValueError('actual consumer assertions missing:'+marker)
                item['summaries'][marker]=rows[0]
        if any(digest(ROOT/n)!=h for n,h in before.items()):raise ValueError('consumed source changed')
        report.update(pass_test=True,source_unchanged=True)
    except Exception as e:report.update(error_type=type(e).__name__,error=str(e));raise
    finally:
        report['artifact_sha256']={str(p.relative_to(ROOT)):digest(p)for p in run.iterdir()if p.is_file()}
        report['RAM_artifact_sha256']={str(p):digest(p)for p in ram.iterdir()if p.is_file()}
        a.report.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(pass_test=True,compile_seconds=report['compile_seconds'],tests={n:v['seconds']for n,v in report['tests'].items()})))


if __name__=='__main__':main()
