#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual full generated HLS + Atomic guard/service/MR/page/RAM/IP/ICRC RTL.

Two-state compiled RTL; trusted configuration, physical descriptor/host
ordering and native-MAC retirement boundary are EXPLICIT MODELS. Not native
SQ/kernel/provider/physical/board/timing signoff. Each runtime <=30seconds.
No fake core receipt: no-packet drop retains its guard until a future genuine
exported core/native retirement receipt exists. Ordinary native path unchanged.
"""
import argparse
import ipaddress
import json
import os
from pathlib import Path
import resource
import shutil
import struct
import subprocess
import sys
import tempfile
import time

import atomic_generated_fixture as fixture

ROOT=fixture.ROOT
sys.path.insert(0,str(ROOT/'rdma/host'))
import rocev2_wire as wire
TOOL=Path('/home/user/fpga-rocev2-research/verilator-v5.036-install/bin/verilator')


def packet(op,q,psn,operand,compare=0,*,key=8,source='198.18.11.1',flags=0):
    bth=bytes([op,flags])+struct.pack('!H',0xffff)+b'\0'+q.to_bytes(3,'big')+b'\x80'+psn.to_bytes(3,'big')
    body=bth+struct.pack('!QIQQ',0xfedcba9876544000,key,operand,compare)
    ip=bytearray(struct.pack('!BBHHHBBH4s4s',0x45,0,72,0,0x4000,64,17,0,
        ipaddress.IPv4Address(source).packed,ipaddress.IPv4Address('198.18.11.2').packed))
    ip[10:12]=wire.internet_checksum(ip).to_bytes(2,'big')
    raw=bytes(ip)+struct.pack('!HHHH',49152,4791,52,0)+body+bytes(4)
    return raw[:-4]+wire.icrc_ipv4(raw)


def inputs():
    cas=packet(19,2,0xfffffe,0x8123456789abcdef,0xf123456789abcdef)
    crc=bytearray(cas);crc[-1]^=0x80
    frames=[bytes(crc),packet(19,2,0xfffffe,0x8123456789abcdef,0xf123456789abcdef,source='198.18.11.99'),
        packet(19,4,0xfffffe,0x8123456789abcdef,0xf123456789abcdef),
        packet(19,2,0xfffffe,0x8123456789abcdef,0xf123456789abcdef,flags=0x10),
        cas,cas,packet(19,2,0xffffff,0xffffffffffffffff,1),
        packet(20,2,0,0x7edcba9876543211),packet(20,2,2,1),
        packet(19,2,1,0xfeedface12345678,1),packet(19,3,0x123456,0xfedcba9876543210,0),
        packet(19,2,1,0xfeedface12345678,1),packet(20,2,2,0),cas,
        packet(20,2,0xfffffe,1,key=16)]
    words=[]
    for frame in frames:
        if len(frame)!=72:raise ValueError('fixture geometry')
        for offset in range(0,len(frame),16):
            part=frame[offset:offset+16]
            words.append(int.from_bytes(part.ljust(16,b'\0'),'little')|(((1<<len(part))-1)<<128)|
                (int(offset+16>=len(frame))<<144))
    return words,frames


def output_packets(output):
    packets=[];p=bytearray()
    for line in output.splitlines():
        if not line.startswith('ATOMIC_OUT '):continue
        _,data,keep,last=line.split();d=int(data,16).to_bytes(16,'little');k=int(keep,16)
        if k not in [0xffff,0xff]:raise ValueError('actual wire keep')
        p.extend(d[:k.bit_count()])
        if int(last):packets.append(bytes(p));p.clear()
    if p:raise ValueError('truncated actual wire packet')
    return packets


def verify(output,case):
    packets=output_packets(output)
    if case==0:
        expected=[(2,0xfffffe,1,0x1f,0xf123456789abcdef),(2,0xfffffe,1,0x1f,0xf123456789abcdef),
            (2,0xffffff,2,0x1f,0x8123456789abcdef),(2,0,3,0x1f,0x8123456789abcdef),
            (2,1,3,0x60,None),(2,1,4,0x1f,0),(3,0x123456,1,0x1f,0),(2,1,4,0x1f,0),
            (2,2,5,0x1f,0xfedcba9876543210)]
    elif case==1:expected=[(2,0xfffffe,0,0x62,None)]
    else:expected=[]
    if len(packets)!=len(expected):raise ValueError(('missing actual packets',len(packets),len(expected)))
    for p,(q,psn,msn,syndrome,old)in zip(packets,expected):
        size=56 if old is not None else 48
        if len(p)!=size or p[0]!=0x45 or int.from_bytes(p[2:4],'big')!=size or p[9]!=17:
            raise ValueError('actual IPv4 shape')
        if wire.internet_checksum(p[:20])!=0 or p[-4:]!=wire.icrc_ipv4(p):raise ValueError('actual IPv4 checksum/ICRC')
        if p[12:20]!=bytes([198,18,11,2,198,18,11,1]):raise ValueError('trusted reply addresses')
        if int.from_bytes(p[22:24],'big')!=4791 or int.from_bytes(p[24:26],'big')!=size-20:
            raise ValueError('actual UDP shape')
        bth=bytes([18 if old is not None else 17,0x40])+struct.pack('!H',0xffff)
        bth+=struct.pack('!I',0xf12345+q)+struct.pack('!I',psn)
        body=bth+bytes([syndrome])+msn.to_bytes(3,'big')
        if old is not None:body+=struct.pack('!Q',old)
        if p[28:-4]!=body:raise ValueError(('independent Atomic BTH/AETH/old-value wire oracle',p[28:-4].hex(),body.hex()))
    if case==0 and (packets[0][28:-4]!=packets[1][28:-4] or packets[5][28:-4]!=packets[7][28:-4]):
        raise ValueError('real cached response changed')
    rows=[json.loads(l.split(' ',1)[1])for l in output.splitlines()if l.startswith('ATOMIC_GENERATED ')]
    if len(rows)!=1 or not rows[0]['pass_test']:raise ValueError('missing real generated assertions')
    owners=[l.split()[1:]for l in output.splitlines()if l.startswith('ATOMIC_OWNER ')]
    tags=[int(x[-1],16)for x in owners]
    if len(set(tags))!=len(tags)or any(t==0 for t in tags):raise ValueError('duplicate packet cookie')
    jobs=[int(l.split()[1],16)for l in output.splitlines()if l.startswith('ATOMIC_JOB ')]
    if case==0:
        expected_state=[(0xfffffe,0),(0xffffff,1),(0xffffff,1),(0,2),(1,3),(1,3),(0x123456,0),(2,4),(2,4),(3,5)]
        if len(jobs)!=len(expected_state):raise ValueError('missing actual HLS service words')
        for job,(epsn,msn)in zip(jobs,expected_state):
            if (job>>320)&0xffffff!=epsn or job>>344!=msn:raise ValueError('wrong actual shared HLS PSN/MSN')
    return dict(summary=rows[0],actual_IP_UDP_ICRC_packets=[p.hex()for p in packets],
        actual_service_requests=[f'{x:092x}'for x in jobs],unique_real_packet_tags=tags,
        independent_wire_checksum_ICRC_and_atomic_old_value_oracle=True)


def no_core():resource.setrlimit(resource.RLIMIT_CORE,(0,0))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--hls-report',type=Path,required=True)
    p.add_argument('--report',type=Path,required=True)
    p.add_argument('--reuse-compiled-report',type=Path,help='fresh RTL translation with verified identical compiler objects; never reuse test results')
    a=p.parse_args()
    if a.report.exists():p.error('preserve previous evidence')
    if shutil.disk_usage(ROOT).free<1024**3:raise RuntimeError('unchanged fresh-native1GiB guard')
    info=json.loads(a.hls_report.read_text())
    if not info.get('pass_test')or info.get('HLS_top')!='rocev2_native_atomic_top':p.error('matched generated core required')
    raw=ROOT/info['directory']/'project/solution1/syn/verilog'
    for n,h in info['generated_sha256'].items():
        if fixture.prior.digest(raw/n)!=h:raise ValueError('raw generated HLS changed')
    run=Path(tempfile.mkdtemp(prefix='atomic-generated-',dir=ROOT/'rdma/rnic/build'))
    obj=(Path(json.loads(a.reuse_compiled_report.read_text())['compile_directory'])if a.reuse_compiled_report else
        Path(tempfile.mkdtemp(prefix='as02-atomic-generated-obj-',dir='/dev/shm')))
    words,frames=inputs();tb,bridge=fixture.bench(run,len(words));(run/'tb.v').write_text(tb)
    (run/'input.hex').write_text(''.join(f'{w:037x}\n'for w in words))
    axis=ROOT/'external/corundum/fpga/lib/axis/rtl'
    eth=ROOT/'external/corundum/fpga/lib/eth/rtl'
    sources=[*sorted(raw.glob('*.v')),*fixture.prior.rtl.SOURCES,ROOT/'rdma/rnic/rtl/rocev2_atomic_service_adapter.v',
        ROOT/'rdma/rnic/rtl/rocev2_atomic_packet_guard.v',ROOT/'rdma/rtl/rocev2_ipv4_icrc.v',
        ROOT/'rdma/rtl/rocev2_tx_padding.v',axis/'axis_adapter.v',axis/'axis_fifo.v',eth/'lfsr.v',bridge]
    sources=list(dict.fromkeys(sources));data=sorted(raw.glob('*.dat'))
    for item in data:shutil.copy2(item,run/item.name)
    modules=[fixture,fixture.prior,fixture.prior.rtl,fixture.prior.rtl.paged,fixture.bridge,fixture.bridge.base,
        fixture.bridge.base.parent,fixture.bridge.base.parent.bridge,fixture.bridge.base.parent.bridge.legacy]
    own=[Path(m.__file__).resolve()for m in modules]+[Path(__file__).resolve(),a.hls_report.resolve(),
        ROOT/'rdma/rtl/rocev2_integrity_transport.v',ROOT/'rdma/rnic/rtl/rocev2_protected_responder.v',
        ROOT/'rdma/host/rocev2_wire.py',run/'tb.v',run/'input.hex']
    before={str(x.relative_to(ROOT)):fixture.prior.digest(x)for x in [*sources,*data,*own]}
    report=dict(scope=__doc__,pass_test=False,source_sha256=before,directory=str(run.relative_to(ROOT)),
        compile_directory=str(obj),actual_generated_HLS=True,actual_MR_PTE_paged_RAM_IP_UDP_ICRC=True,
        native_integrated=False,hardware_verified=False,two_state=True,simulation_limit_seconds=30,
        physical_host_ordering_and_MAC_boundary_models=True,tests={})
    try:
        command=[str(TOOL),'--binary','--timing','--top-module','tb','-Wno-fatal','-j','4',
            '--output-split','20000','--output-split-cfuncs','0','--output-groups','0',
            '-CFLAGS','-O0','--Mdir',str(obj),str(run/'tb.v'),*map(str,sources)]
        report['compile_command']=command
        print(json.dumps(dict(directory=str(run),compile_directory=str(obj),compile_limit_seconds=1200)),flush=True)
        env=os.environ.copy();env['TMPDIR']='/dev/shm/as02-native-compiler-tmp-QYQsVyT5';start=time.monotonic()
        if a.reuse_compiled_report:
            import atomic_generated_compile_cache as cache
            before[str(Path(cache.__file__).resolve().relative_to(ROOT))]=fixture.prior.digest(Path(cache.__file__).resolve())
            reused=cache.compile(command,run,env,a.reuse_compiled_report.resolve())
            before.update(reused.pop('extra_source_sha256'));report.update(reused)
        else:
            with(run/'compile.log').open('x')as log:
                c=subprocess.run(command,cwd=run,stdout=log,stderr=subprocess.STDOUT,env=env,timeout=1200)
            report['compile_seconds']=time.monotonic()-start
            if c.returncode:raise RuntimeError('actual generated composition compile: '+str(run/'compile.log'))
        shutil.copy2(obj/'Vtb',run/'Vtb')
        for case in range(3):
            start=time.monotonic()
            with(run/f'case-{case}.log').open('x')as log:
                c=subprocess.run([str(run/'Vtb'),f'+case={case}'],cwd=run,stdout=log,stderr=subprocess.STDOUT,
                    timeout=30,preexec_fn=no_core)
            report['tests'][case]=dict(seconds=time.monotonic()-start,exit=c.returncode)
            if c.returncode:raise RuntimeError('generated case failed: '+str(run/f'case-{case}.log'))
            report['tests'][case].update(verify((run/f'case-{case}.log').read_text(),case))
        if before!={n:fixture.prior.digest(ROOT/n)for n in before}:raise ValueError('source changed')
        report.update(pass_test=True,source_unchanged=True)
    except Exception as e:report['error']=str(e);raise
    finally:
        report['artifact_sha256']={str(x.relative_to(ROOT)):fixture.prior.digest(x)for x in run.iterdir()if x.is_file()}
        with a.report.open('x')as out:out.write(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k]for k in ['pass_test','compile_seconds','tests']}),flush=True)


if __name__=='__main__':main()
