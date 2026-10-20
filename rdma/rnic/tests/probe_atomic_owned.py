#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Owned HLS C++/actual protected Atomic RTL, real same-table readback.

Original full graph compiled, immutable144-bit packet identity traverses the
real RX-IBH/EXH/service. Deliberately stop the actual MSN then PSN consumers:
no done is allowed until both readbacks. Replay uses current table MSN, not
cached wire MSN; drop completes and permits later normal/Atomic work.
Physical memory ordering/host descriptors/normal payload and peer are models.
Not generated HLS RTL/native/MAC/CQ/standard verbs/board/timing signoff.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import probe_atomic_shared as base

ROOT=base.ROOT;once=base.rtl_once
RTL=base.rtl.RTL/'rocev2_atomic_owned_service_adapter.v'


def harness():
    t=base.harness()
    t=once(t,'hls::stream<as02AtomicCommit> atomic_commit;',
        'hls::stream<as02AtomicCommit> atomic_commit;\n'
        '    hls::stream<as02AtomicOwner> atomic_owners;hls::stream<as02AtomicDone> atomic_done;\n'
        '    bool atomic_msn_table_enabled=true,atomic_psn_table_enabled=true;')
    t=once(t,'psn_drops,atomic_commit,rx_owners,rf);',
        'psn_drops,atomic_owners,atomic_done,atomic_commit,rx_owners,rf);')
    t=once(t,'        msn_table<I>(', '        if(atomic_msn_table_enabled)msn_table<I>(')
    return once(t,'if(tables)state_table<I>(', 'if(tables && atomic_psn_table_enabled)state_table<I>(')


def bench():
    t=base.BENCH.read_text()
    t=once(t,'put(b,24,8,operand);put(b,32,8,compare);e.packet(b);e.ticks(64);',
        'put(b,24,8,operand);put(b,32,8,compare);\n'
        '    as02AtomicOwner owner=0;owner(23,0)=q;owner(87,24)=0x9123456780000001ULL;\n'
        '    owner(111,88)=psn;owner(143,112)=jobs+1;e.h.atomic_owners.write(owner);\n'
        '    e.packet(b);e.ticks(64);')
    t=once(t,'assert(r(343,320)==expect && r(367,344)==message);',
        'assert(r(343,320)==expect && r(367,344)==message && r(511,368)==owner);')
    t=once(t,'e.h.atomic_replies.write(result);e.ticks(64);jobs++;',r'''
    assert(result(391,248)==owner);
    e.h.atomic_msn_table_enabled=false;e.h.atomic_replies.write(result);e.ticks(32);
    assert(e.h.atomic_done.empty() && e.h.atomic_commit.empty());
    e.h.atomic_psn_table_enabled=false;e.h.atomic_msn_table_enabled=true;e.ticks(32);
    assert(e.h.atomic_done.empty());
    e.h.atomic_psn_table_enabled=true;e.ticks(64);
    assert(e.h.atomic_done.size()==1);auto done=e.h.atomic_done.read();
    ap_uint<8> flags=7;flags[3]=!drop;flags[4]=advance;flags[5]=drop;
    assert(done(143,0)==owner && done(151,144)==op && done(223,208)==0 && done(207,200)==flags);
    assert(done(175,152)==(advance ? ((psn+1)&0xffffff):expect));
    assert(done(199,176)==((message+unsigned(advance))&0xffffff));
    std::cout<<"ATOMIC_CORE_DONE "<<done.to_string(16,false)<<std::endl;
    jobs++;''')
    t=once(t,'ATOMIC_SHARED_HLS ', 'ATOMIC_OWNED_HLS ')
    return once(t,'\\"withheld_service_no_advance\\":true}',
        '\\"withheld_service_no_advance\\":true,\\"withheld_MSN_and_PSN_no_done\\":true,'
        '\\"immutable_owner_echo\\":true,\\"same_table_readback\\":true,\\"drop_then_forward_progress\\":true}')


def service_bench():
    # Reuse exact MR/PTE/RAM/descriptor model, change ONLY service adapter.
    t=base.service_bench();begin=t.index('reg [367:0] x_s_hls_request=0;')
    end=t.index('integer fd,scanned,serial=0;',begin)
    mapping=dict(clk='clk',rst='rst',enable="1'b1")
    for n in ['header','bytes','expected_psn','msn','epoch','valid']:
        mapping['m_execute_'+n]='a_s_request_'+n
    mapping['m_execute_ready']='a_s_request_ready'
    for n in ['header','bytes','qpn','epoch','advance','drop','valid']:
        mapping['s_execute_response_'+n]='a_m_response_'+n
    mapping['s_execute_response_ready']='a_m_response_ready'
    server=base.SERVER.replace('reg [367:0] job;reg [247:0] completion;',
        'reg [511:0] job;reg [391:0] completion;')
    server=server.replace('  x_s_owner_qpn=serial==5 ? 3:2;x_s_owner_epoch=64\'h9123456780000001;x_s_owner_valid=1;\n','')
    server=server.replace(' || !x_s_owner_ready','').replace(';x_s_owner_valid=0;',';')
    server=server.replace('%062h','%098h')
    return t[:begin]+base.rtl.instance(RTL,'adapter','x_',mapping)+server


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True)
    p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve previous evidence')
    source=a.source.resolve();info=json.loads((source/'source.json').read_text())
    if info.get('atomic_service_request_bits')!=512 or info.get('atomic_core_done_bits')!=224:
        p.error('matched complete owned Atomic source required')
    sources=[*base.rtl.SOURCES,RTL]
    inputs=[*source.rglob('*'),*sources,Path(__file__).resolve(),Path(base.__file__).resolve(),
        Path(base.rtl.__file__).resolve(),Path(base.rtl.paged.__file__).resolve(),base.BENCH,base.TEMPLATE,
        ROOT/'rdma/rnic/hls/atomic_owned_transport.py']
    before={str(x.relative_to(ROOT)):base.digest(x)for x in inputs if x.is_file()}
    run=Path(tempfile.mkdtemp(prefix='atomic-owned-',dir=ROOT/'rdma/rnic/build'))
    report=dict(scope=__doc__,pass_test=False,source_sha256=before,directory=str(run.relative_to(ROOT)),
        simulation_limit_seconds=30,hardware_verified=False,generated_HLS_RTL=False,native_integration=False,
        full_top_CPP_compiled=False,shared_PSN_MSN=True,service_RTL_actual=True)
    processes=[];readers=[];hlog=[];slog=[]
    try:
        (run/'atomic_request_base.hpp').write_text(harness());(run/'test.cpp').write_text(bench())
        (run/'service.v').write_text(service_bench())
        c=subprocess.run(['iverilog','-g2012','-s','tb','-o',str(run/'service.vvp'),str(run/'service.v'),*map(str,sources)],
            capture_output=True,text=True,timeout=30);(run/'rtl-compile.log').write_text(c.stdout+c.stderr)
        if c.returncode:raise RuntimeError('owned actual service compile: '+str(run/'rtl-compile.log'))
        flags=['-std=c++17','-O0','-pthread','-Wno-unknown-pragmas','-ffunction-sections','-fdata-sections','-Wl,--gc-sections',
            '-DFNS_DATA_WIDTH=64','-DFNS_ROCE_STACK_MAX_QPS=8','-D__VITIS_HLS__','-I'+str(run),
            '-I'+str(source/'adapter'),'-I'+str(source/'fns/hls'),'-I/home/user/amd/2025.2/Vitis/include']
        cmd=[shutil.which('g++-13'),*flags,str(run/'test.cpp'),str(source/'fns/hls/ib_transport_protocol/ib_utils.cpp'),
            str(source/'fns/hls/rocev2/rocev2.cpp'),'-o',str(run/'hls')]
        start=time.monotonic()
        with tempfile.TemporaryDirectory(prefix='as02-atomic-owned-cxx-',dir='/dev/shm')as temporary:
            env=os.environ.copy();env['TMPDIR']=temporary
            c=subprocess.run(cmd,capture_output=True,text=True,timeout=180,env=env)
        report['compile_seconds']=time.monotonic()-start;(run/'cpp-compile.log').write_text(c.stdout+c.stderr)
        if c.returncode:raise RuntimeError('owned complete graph compile: '+str(run/'cpp-compile.log'))
        report['full_top_CPP_compiled']=True
        for command in [['vvp',str(run/'service.vvp')],[str(run/'hls')]]:
            proc=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,bufsize=0)
            processes.append(proc);readers.append(base.Lines(proc))
        service,hls=processes;sr,hr=readers
        start=time.monotonic();deadline=start+30;transfers=[];packets=[];receipts=[];cache={};value=0xf123456789abcdef
        while True:
            line=sr.read(deadline);slog.append(line)
            if line=='ATOMIC_SERVICE_READY':break
        while True:
            line=hr.read(deadline);hlog.append(line)
            if line.startswith('ATOMIC_SERVICE '):
                word=line.split()[1];job=int(word,16);service.stdin.write((f'{job:0128x}'+'\n').encode())
                while True:
                    line=sr.read(deadline);slog.append(line)
                    if line.startswith('ATOMIC_COMPLETE '):break
                _,reply,executed,replayed,dropped,commands,memory=line.split();result=int(reply,16)
                if result>>248!=job>>368:raise ValueError('immutable owner not echoed')
                value=base.oracle(job&((1<<368)-1),result&((1<<248)-1),value,cache)
                if int(memory,16)!=value:raise ValueError('actual RAM disagrees with independent oracle')
                transfers.append(dict(request_hex=word,reply_hex=reply,executed=int(executed),replayed=int(replayed),
                    dropped=int(dropped),commands=int(commands),memory_hex=memory,oracle_pass=True))
                hls.stdin.write((reply+'\n').encode())
            elif line.startswith('ATOMIC_CORE_DONE '):receipts.append(line.split()[1])
            elif line.startswith('ATOMIC_WIRE '):packets.append(line.split()[1])
            elif line.startswith('ATOMIC_OWNED_HLS '):summary=json.loads(line.split(' ',1)[1]);break
        hls.stdin.close();service.stdin.close()
        for proc in processes:
            proc.wait(timeout=max(0.1,deadline-time.monotonic()))
            if proc.returncode:raise RuntimeError('owned co-simulation process failed')
        report['simulation_seconds']=time.monotonic()-start
        if len(transfers)!=9 or len(receipts)!=9 or len(packets)!=11 or not summary['pass_test']:
            raise ValueError('incomplete real owned producer/consumer coverage')
        for t,d in zip(transfers,receipts):
            if int(d,16)&((1<<144)-1)!=int(t['request_hex'],16)>>368:raise ValueError('core receipt ownership lost')
        if before!={n:base.digest(ROOT/n)for n in before}:raise ValueError('input changed')
        report.update(pass_test=True,source_unchanged=True,summary=summary,transfers=transfers,wire_packets=packets,
            actual_core_receipts=receipts,artifact_sha256={str(x.relative_to(ROOT)):base.digest(x)for x in
                [run/'hls',run/'service.vvp',run/'service.v',run/'atomic_request_base.hpp',run/'test.cpp']})
    except Exception as e:report['error']=str(e);raise
    finally:
        (run/'hls.log').write_text('\n'.join(hlog)+'\n');(run/'service.log').write_text('\n'.join(slog)+'\n')
        for reader in readers:reader.close()
        for proc in processes:
            if proc.poll()is None:proc.kill();proc.wait()
        with a.report.open('x')as out:out.write(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k]for k in ['pass_test','compile_seconds','simulation_seconds','summary']}))


if __name__=='__main__':main()
