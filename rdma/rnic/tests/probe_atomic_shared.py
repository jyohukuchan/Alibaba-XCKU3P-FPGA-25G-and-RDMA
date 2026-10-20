#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual SAME-table HLS C++ <-> actual Atomic/MR/paged DMA/RAM RTL co-sim.

Each HLS-emitted service word feeds an independent live RTL simulation with
persistent state; its unedited result is returned to actual HLS consumers.
Only host/physical descriptors/ordering and normal SEND/WRITE sinks/peer are
models. This is not generated HLS RTL, native binding, network/ICRC/MAC/CQ,
Linux/verbs, physical atomicity, timing or a board test. Runtime <=30seconds.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import selectors
import shutil
import struct
import subprocess
import tempfile
import time

import probe_atomic_responder as rtl

ROOT=rtl.ROOT
BENCH=ROOT/'rdma/rnic/hls/test_atomic_shared.cpp'
TEMPLATE=ROOT/'rdma/rnic/hls/test_native_request_retire.cpp'

SERVER=r'''
integer fd,scanned,serial=0;
reg [367:0] job;reg [247:0] completion;
initial begin
 #1 rst=1;
 for(k=0;k<16384;k=k+1)begin host[k]=(k*37)^8'h5a;posted_valid[k]=0;end
 repeat(5)@(negedge clk);rst=0;
 // Intentionally DIFFERENT private PSN/MSN: shared mode must use exactly
 // the actual HLS service word, including normal SEND/WRITE's prior updates.
 configure_qp(2,64'h9123456780000001,17,24'h111111);
 configure_qp(3,64'h9123456780000001,17,24'h222222);
 configure_mr(0,9,8192);configure_mr(1,1,8192);configure_mr(2,9,4091);
 configure_pages(1,0);configure_pages(2,0);configure_pages(2,1);configure_pages(2,2);configure_pages(3,0);
 enable=1;store64(4096,64'hf123456789abcdef);
 fd=$fopen("/dev/stdin","r");if(!fd)$fatal(1,"service input");
 $display("ATOMIC_SERVICE_READY");$fflush();
 forever begin
  scanned=$fscanf(fd,"%h",job);
  if(scanned!=1)$finish;
  @(negedge clk);x_s_hls_request=job;x_s_hls_request_valid=1;
  x_s_owner_qpn=serial==5 ? 3:2;x_s_owner_epoch=64'h9123456780000001;x_s_owner_valid=1;
  @(posedge clk);while(!x_s_hls_request_ready || !x_s_owner_ready)@(posedge clk);
  @(negedge clk);x_s_hls_request_valid=0;x_s_owner_valid=0;
  while(!x_m_hls_reply_valid && !a_fault && !b_fault && !fault && !x_fault)@(negedge clk);
  if(a_fault || b_fault || fault || x_fault)$fatal(1,"service ownership fault %h/%h/%h/%h",a_fault_code,b_fault_code,fault_code,x_fault_code);
  repeat(13)@(negedge clk);
  completion=x_m_hls_reply;
  // Result is captured while genuine ownership is held, then handed off.
  x_m_hls_reply_ready=1;@(negedge clk);x_m_hls_reply_ready=0;
  repeat(4)@(negedge clk);serial=serial+1;
  $display("ATOMIC_COMPLETE %062h %0d %0d %0d %0d %016h",completion,a_executed_count,a_replay_count,a_dropped_count,commands,load64(4096));$fflush();
 end
end
endmodule
'''


def service_bench():
    tb=rtl.bench().replace('rocev2_atomic_responder atomic(',
        'rocev2_atomic_responder #(.SHARED_SEQUENCE_ENABLE(1)) atomic(')
    # Remove only unused direct-register stimulus tasks. Actual configured
    # MR/PTE and physical/RAM models remain; the adapter now owns these wires.
    begin=tb.index('task offer;');end=tb.index('// Physical descriptor/host MODEL;',begin)
    tb=tb[:begin]+tb[end:]
    adapter=rtl.RTL/'rocev2_atomic_service_adapter.v'
    mapping=dict(clk='clk',rst='rst',enable="1'b1")
    for n in ['header','bytes','expected_psn','msn','epoch','valid']:
        mapping['m_execute_'+n]='a_s_request_'+n
    mapping['m_execute_ready']='a_s_request_ready'
    for n in ['header','bytes','qpn','epoch','advance','drop','valid']:
        mapping['s_execute_response_'+n]='a_m_response_'+n
    mapping['s_execute_response_ready']='a_m_response_ready'
    for n in ['s_request_header','s_request_bytes','s_request_expected_psn','s_request_msn',
              's_request_epoch','s_request_valid','m_response_ready']:
        tb=rtl.re.sub(r'reg (\[[^]]+\]\s+)?a_'+n+r'=0;',lambda m:'wire '+(m[1]or'')+'a_'+n+';',tb)
    tb=tb.replace('assign quiet=!a_configuration_guard','assign quiet=!x_configuration_guard && !a_configuration_guard')
    pos=tb.index('integer before_cmd,before_exec,before_read,before_write;')
    return tb[:pos]+rtl.instance(adapter,'adapter','x_',mapping)+SERVER


def harness():
    t=TEMPLATE.read_text().replace('ap_uint<588>','ap_uint<620>')
    t=rtl_once(t,'    hls::stream<ap_uint<620>> owners,admitted;',
        '    hls::stream<as02AtomicRequest> atomic_requests;\n'
        '    hls::stream<as02AtomicReply> atomic_replies;\n'
        '    hls::stream<as02AtomicCommit> atomic_commit;\n'
        '    hls::stream<ap_uint<620>> owners,admitted;')
    t=rtl_once(t,'psn_drops,rx_owners,rf);','psn_drops,atomic_commit,rx_owners,rf);')
    t=rtl_once(t,'shift,recv_owners,recv_fault,ack_consumed,ef);',
        'shift,atomic_requests,atomic_replies,atomic_commit,recv_owners,recv_fault,ack_consumed,ef);')
    # Renaming main removes C++'s implicit return0; the imported preceding
    # test is not executed but must remain a well-formed ordinary function.
    pos=t.rfind('\n}')
    return t[:pos]+'\n    return 0;'+t[pos:]


def rtl_once(t,old,new):
    if t.count(old)!=1:raise ValueError('harness anchor changed: '+old)
    return t.replace(old,new)


class Lines:
    def __init__(self,process):
        self.p=process;self.pending=b'';self.selector=selectors.DefaultSelector()
        self.selector.register(process.stdout,selectors.EVENT_READ)

    def read(self,deadline):
        while b'\n'not in self.pending:
            if time.monotonic()>=deadline:raise TimeoutError('bounded co-simulation deadline')
            if not self.selector.select(min(0.1,deadline-time.monotonic())):continue
            chunk=os.read(self.p.stdout.fileno(),65536)
            if not chunk:
                raise RuntimeError('simulation exited before expected line: '+self.pending.decode(errors='replace'))
            self.pending+=chunk
        line,self.pending=self.pending.split(b'\n',1)
        return line.decode(errors='strict')

    def close(self):self.selector.close()


def oracle(job,result,value,cache):
    raw=(job&((1<<320)-1)).to_bytes(40,'little');op=raw[0]
    q=int.from_bytes(raw[5:8],'big');psn=int.from_bytes(raw[9:12],'big')
    epsn=(job>>320)&0xffffff;msn=job>>344
    address,key,operand,compare=struct.unpack('!QIQQ',raw[12:])
    if address!=0xfedcba9876544000 or key!=8:raise ValueError('unexpected service authority')
    expected_advance=False;drop=False
    if q in cache and cache[q]['psn']==psn:
        old=cache[q]
        if raw!=old['request']:raise ValueError('test duplicate semantic mismatch')
        wire=old['wire']
    elif psn!=epsn:
        if ((psn-epsn)&0xffffff)&0x800000:wire=bytes(24);drop=True
        else:
            wire=bytes([0x11,0])+struct.pack('!HII',0xffff,0xf12345+q,epsn)
            wire+=bytes([0x60])+msn.to_bytes(3,'big')+bytes(8)
    else:
        old=value;expected_advance=True
        value=(value+operand)&((1<<64)-1)if op==20 else operand if value==compare else value
        wire=bytes([0x12,0])+struct.pack('!HII',0xffff,0xf12345+q,psn)
        wire+=bytes([0x1f])+((msn+1)&0xffffff).to_bytes(3,'big')+struct.pack('!Q',old)
        cache[q]=dict(psn=psn,request=raw,wire=wire)
    expected=int.from_bytes(wire,'little')|(q<<192)|(psn<<216)
    expected|=((0 if drop else 24 if wire[0]==18 else 16)<<240)|(int(expected_advance)<<246)|(int(drop)<<247)
    if result!=expected:raise ValueError(('independent shared-service oracle',f'{result:062x}',f'{expected:062x}'))
    return value


def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True)
    p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve previous evidence')
    source=a.source.resolve();info=json.loads((source/'source.json').read_text())
    if info.get('atomic_service_request_bits')!=368 or info.get('atomic_service_reply_bits')!=248:
        p.error('matched Atomic full source required')
    sources=[*rtl.SOURCES,rtl.RTL/'rocev2_atomic_service_adapter.v']
    inputs=[*source.rglob('*'),*sources,Path(rtl.__file__).resolve(),Path(rtl.paged.__file__).resolve(),
        Path(__file__).resolve(),BENCH,TEMPLATE,ROOT/'rdma/rnic/hls/atomic_transport.py']
    before={str(x.relative_to(ROOT)):digest(x)for x in inputs if x.is_file()}
    run=Path(tempfile.mkdtemp(prefix='atomic-shared-',dir=ROOT/'rdma/rnic/build'))
    report=dict(scope=__doc__,pass_test=False,source_sha256=before,directory=str(run.relative_to(ROOT)),
        simulation_limit_seconds=30,hardware_verified=False,generated_HLS_RTL=False,native_integration=False,
        full_top_CPP_compiled=False,shared_PSN_MSN=True,service_RTL_actual=True,
        physical_host_descriptor_ordering_and_normal_payload_peer_models=True)
    processes=[];readers=[]
    try:
        (run/'atomic_request_base.hpp').write_text(harness());tb=service_bench();(run/'service.v').write_text(tb)
        cmd=['iverilog','-g2012','-s','tb','-o',str(run/'service.vvp'),str(run/'service.v'),*map(str,sources)]
        c=subprocess.run(cmd,capture_output=True,text=True,timeout=30);(run/'rtl-compile.log').write_text(c.stdout+c.stderr)
        if c.returncode:raise RuntimeError('actual service RTL compile: '+c.stderr)
        text=(run/'service.vvp').read_text()
        counts={n:len(rtl.re.findall(r'\.scope module, "[^\"]+" "'+n+r'"',text))for n in
            ['rocev2_atomic_service_adapter','rocev2_atomic_responder','rocev2_atomic_memory_bridge',
             'rocev2_memory_client_arbiter','rocev2_mr_table','rocev2_mr_page_table',
             'rocev2_paged_memory_backend','rocev2_corundum_dma_backend','dma_psdpram']}
        if not all(v==1 for v in counts.values()):raise ValueError(('unexpected RTL graph',counts))
        report['actual_elaborated_module_counts']=counts
        flags=['-std=c++17','-O0','-pthread','-Wno-unknown-pragmas','-ffunction-sections','-fdata-sections','-Wl,--gc-sections',
            '-DFNS_DATA_WIDTH=64','-DFNS_ROCE_STACK_MAX_QPS=8','-D__VITIS_HLS__','-I'+str(run),
            '-I'+str(source/'adapter'),'-I'+str(source/'fns/hls'),'-I/home/user/amd/2025.2/Vitis/include']
        cmd=[shutil.which('g++-13'),*flags,str(BENCH),str(source/'fns/hls/ib_transport_protocol/ib_utils.cpp'),
            str(source/'fns/hls/rocev2/rocev2.cpp'),'-o',str(run/'hls')]
        start=time.monotonic()
        with tempfile.TemporaryDirectory(prefix='as02-atomic-cxx-',dir='/dev/shm')as temporary:
            env=os.environ.copy();env['TMPDIR']=temporary
            c=subprocess.run(cmd,capture_output=True,text=True,timeout=180,env=env)
        report['compile_seconds']=time.monotonic()-start;(run/'cpp-compile.log').write_text(c.stdout+c.stderr)
        if c.returncode:raise RuntimeError('complete C++ graph compile failed: '+str(run/'cpp-compile.log'))
        report['full_top_CPP_compiled']=True
        for command in [['vvp',str(run/'service.vvp')],[str(run/'hls')]]:
            proc=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,bufsize=0)
            processes.append(proc);readers.append(Lines(proc))
        service,hls=processes;sr,hr=readers
        start=time.monotonic();deadline=start+30;hlog=[];slog=[];transfers=[];packets=[];cache={};value=0xf123456789abcdef
        while True:
            line=sr.read(deadline);slog.append(line)
            if line=='ATOMIC_SERVICE_READY':break
        while True:
            line=hr.read(deadline);hlog.append(line)
            if line.startswith('ATOMIC_SERVICE '):
                word=line.split()[1];job=int(word,16);service.stdin.write((f'{job:092x}'+'\n').encode())
                while True:
                    line=sr.read(deadline);slog.append(line)
                    if line.startswith('ATOMIC_COMPLETE '):break
                _,reply,executed,replayed,dropped,commands,memory=line.split();result=int(reply,16)
                value=oracle(job,result,value,cache)
                if int(memory,16)!=value:raise ValueError('actual RAM/DMA result disagrees with independent oracle')
                transfers.append(dict(request_hex=word,reply_hex=reply,executed=int(executed),replayed=int(replayed),
                    dropped=int(dropped),commands=int(commands),memory_hex=memory,oracle_pass=True))
                hls.stdin.write((reply+'\n').encode())
            elif line.startswith('ATOMIC_WIRE '):packets.append(line.split()[1])
            elif line.startswith('ATOMIC_SHARED_HLS '):
                summary=json.loads(line.split(' ',1)[1]);break
        hls.stdin.close();service.stdin.close()
        for proc in processes:
            proc.wait(timeout=max(0.1,deadline-time.monotonic()))
            if proc.returncode:raise RuntimeError('co-simulation process failed')
        report['simulation_seconds']=time.monotonic()-start
        if len(transfers)!=9 or len(packets)!=11 or not summary['pass_test']:raise ValueError('incomplete real producer/consumer coverage')
        if before!={n:digest(ROOT/n)for n in before}:raise ValueError('input changed')
        report.update(pass_test=True,source_unchanged=True,summary=summary,transfers=transfers,wire_packets=packets,
            artifact_sha256={str(x.relative_to(ROOT)):digest(x)for x in [run/'hls',run/'service.vvp',run/'service.v',run/'atomic_request_base.hpp']})
    except Exception as e:report['error']=str(e);raise
    finally:
        if 'hlog'in locals():(run/'hls.log').write_text('\n'.join(hlog)+'\n')
        if 'slog'in locals():(run/'service.log').write_text('\n'.join(slog)+'\n')
        for reader in readers:reader.close()
        for proc in processes:
            if proc.poll()is None:proc.kill();proc.wait()
        with a.report.open('x')as out:out.write(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k]for k in ['pass_test','compile_seconds','simulation_seconds','summary']}))


if __name__=='__main__':main()
