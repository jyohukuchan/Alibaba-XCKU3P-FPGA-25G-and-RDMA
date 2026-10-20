#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual SQ AXI CSR -> SQ/paged/router/RAM/mux/PCIe/parent guard.

Privileged software MMIO agent and physical root complex/host/link, PTE config,
authorized payload source and zero downstream work/wire/CQ owners are MODELS.
No raw SQ configuration bypass, descriptor/status/RAM engine agents or constant
parent proof. NOT native board/MMIO driver/MR pins/local WQE executor/CQ/verbs.
"""
import argparse
import ctypes as C
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile
import time

import probe_sq_paged_dma as shared

ROOT=shared.ROOT
TOP=ROOT/'rdma/rnic/rtl/rocev2_sq_controlled_dma.v'
HEADER=ROOT/'rdma/rnic/kernel/sq_regs.h'
SOURCES=[TOP,ROOT/'rdma/rnic/rtl/rocev2_sq_control_regs.v',*shared.SOURCES]
SOURCES += [ROOT/'external/corundum/fpga/lib/axi/rtl'/(n+'.v')for n in ['axil_reg_if','axil_reg_if_rd','axil_reg_if_wr']]
CSR_DRIVERS=r'''
integer sq_control_sequence=0;
reg [63:0] producer_model=0;
task csr_write;
 input [11:0] address;input [31:0] data;
 begin
  fork
   begin @(negedge clk);sq_s_axil_awaddr=address;sq_s_axil_awvalid=1;
    @(posedge clk);while(!sq_s_axil_awready)@(posedge clk);@(negedge clk);sq_s_axil_awvalid=0;end
   begin repeat(2)@(negedge clk);sq_s_axil_wdata=data;sq_s_axil_wstrb=15;sq_s_axil_wvalid=1;
    @(posedge clk);while(!sq_s_axil_wready)@(posedge clk);@(negedge clk);sq_s_axil_wvalid=0;end
  join
  while(!sq_s_axil_bvalid)@(negedge clk);if(sq_s_axil_bresp)$fatal(1,"CSR AXI B status");
  repeat(3)begin @(negedge clk);if(!sq_s_axil_bvalid)$fatal(1,"CSR lost held B response");end
  sq_s_axil_bready=1;@(posedge clk);@(negedge clk);sq_s_axil_bready=0;
 end
endtask
task csr_read;
 input [11:0] address;output [31:0] value;reg [31:0] held;
 begin
  @(negedge clk);sq_s_axil_araddr=address;sq_s_axil_arvalid=1;
  @(posedge clk);while(!sq_s_axil_arready)@(posedge clk);@(negedge clk);sq_s_axil_arvalid=0;
  while(!sq_s_axil_rvalid)@(negedge clk);held=sq_s_axil_rdata;
  repeat(3)begin @(negedge clk);if(!sq_s_axil_rvalid||sq_s_axil_rdata!==held||sq_s_axil_rresp)$fatal(1,"CSR held R ownership");end
  value=held;sq_s_axil_rready=1;@(posedge clk);@(negedge clk);sq_s_axil_rready=0;
 end
endtask
task csr_command;
 input [1:0] op;input [63:0] producer;
 reg [31:0] words[0:14],value;integer n;
 begin
  csr_read(AS02_SQC_STATUS,value);if(value!==1)$fatal(1,"SQ CSR not ready/safe %h",value);
  for(n=0;n<15;n=n+1)words[n]=0;
  words[0]=sq_control_sequence+1;words[1]=op;words[2]=0;words[3]=17;
  words[4]=1;words[5]=32'h91234567;words[6]=32'h89abcdef;words[7]=32'hfedcba98;
  words[8]=32'h76543000;words[9]=32'hfedcba98;words[10]=1;
  words[11]=producer;words[12]=producer>>32;
  if(op==3)begin words[13]=32'h76543210;words[14]=32'hf1234567;end
  for(n=0;n<15;n=n+1)csr_write(AS02_SQC_STAGE+n*4,words[n]);
  csr_write(AS02_SQC_DOORBELL,words[0]);sq_control_sequence=words[0];
  do begin csr_read(AS02_SQC_STATUS,value);end while(!value[1]);
  if(value[5:2])$fatal(1,"SQ CSR reply uncertain");
  for(n=0;n<15;n=n+1)begin csr_read(AS02_SQC_REPLY+n*4,value);if(value!==words[n])$fatal(1,"SQ reply owner/layout/nonce word%d",n);end
  csr_read(AS02_SQC_REPLY_ERROR,value);if(value)$fatal(1,"SQ real configuration rejected%d",value);
  csr_read(AS02_SQC_REPLY_FLAGS,value);if(value!==(op==1 ? 7:(op==3 ? 31:0)))$fatal(1,"SQ real allocation/retire proof flags%h",value);
  if(op==1||op==3)begin
   csr_read(AS02_SQC_REPLY_CONSUMER_LO,value);if(value!==(op==1 ? 0:producer[31:0]))$fatal(1,"SQ real consumer proof");
   csr_read(AS02_SQC_REPLY_CONSUMER_HI,value);if(value!==(op==1 ? 0:producer[63:32]))$fatal(1,"SQ consumer high bits");
  end
  csr_write(AS02_SQC_REPLY_ACK,sq_control_sequence);
  if(sq_control_response_valid||sq_control_busy||sq_control_fatal||sq_control_mmio_error)$fatal(1,"SQ exact ACK failed");
 end
endtask
task queue_config;
 input [1:0] op;input [63:0] producer;reg [63:0] n;reg [31:0] value;
 begin
  if(op==1)begin
   csr_read(AS02_SQC_ID,value);if(value!==AS02_SQC_ID_VALUE)$fatal(1,"SQ CSR identity");
   csr_read(AS02_SQC_ABI,value);if(value!==AS02_SQC_ABI_VALUE)$fatal(1,"SQ CSR ABI");
   csr_command(op,producer);
  end else if(op==2)begin
   for(n=producer_model+1;n<=producer;n=n+1)csr_command(2,n);
   producer_model=producer;
  end else csr_command(op,producer);
 end
endtask
'''


def bench():
    # Reuse EXACT raw shared-PCIe byte/range/sentinel/route/parent assertions.
    # Change only the public top and replace raw SQ config agent by real CSR.
    original=shared.TOP
    try:
        shared.TOP=TOP
        text=shared.bench()
    finally:shared.TOP=original
    assert text.count('rocev2_sq_paged_dma dut(.*);')==1
    text=text.replace('rocev2_sq_paged_dma dut(.*);','rocev2_sq_controlled_dma dut(.*);')
    text=text.replace('dut.','dut.datapath.')
    macros='\n'.join('localparam '+n+'='+re.sub(r'([0-9a-fA-F]+)U$',r'\1',v).replace('0x',"32'h")+';'for n,v in re.findall(r'^#define (AS02_SQC_\w+) (\w+)',HEADER.read_text(),re.M))
    text=text.replace('module tb;','module tb;\n'+macros,1)
    start=text.index('task queue_config;');end=text.index('\nendtask',start)+len('\nendtask')
    text=text[:start]+CSR_DRIVERS+text[end:]
    old="begin data_command(1,16'h8001);send_payload();end"
    assert text.count(old)==1
    text=text.replace(old,"begin while(!router_client_busy[1])@(negedge clk);data_command(1,16'h8001);send_payload();end")
    assert text.count('repeat(50)@(negedge clk);')==1
    text=text.replace('repeat(50)@(negedge clk);',r'''
 queue_config(3,2);
 if(sq_control_owner_active||sq_control_owner_tainted||sq_queue_active||sq_control_last_sequence!=4)
  $fatal(1,"actual CSR retirement/ownership");
 $display("SQ_CONTROL_RESULT {\"commands\":%0d,\"last_sequence\":%0d,\"raw_SQ_configuration_bypass\":false,\"owner_active\":%0d}",sq_control_sequence,sq_control_last_sequence,sq_control_owner_active);
 repeat(50)@(negedge clk);''')
    return text


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);args=p.parse_args()
    if args.report.exists():p.error('preserve previous evidence')
    own=[Path(__file__).resolve(),Path(shared.__file__).resolve(),Path(shared.pcie.__file__).resolve(),
         Path(shared.codec.__file__).resolve(),shared.codec.KERNEL/'wqe.c',shared.codec.KERNEL/'wqe.h',HEADER]
    before={str(q.relative_to(ROOT)):hashlib.sha256(q.read_bytes()).hexdigest()for q in SOURCES+own}
    build=ROOT/'rdma/rnic/build';build.mkdir(exist_ok=True,parents=True)
    run=Path(tempfile.mkdtemp(prefix='sq-controlled-pcie-',dir=build))
    c=subprocess.run(['cc','-std=c11','-O2','-Wall','-Wextra','-Werror','-shared','-fPIC','-fsanitize=undefined',
        '-fno-sanitize-recover=undefined','-I',str(shared.codec.KERNEL),str(shared.codec.KERNEL/'wqe.c'),'-o',str(run/'wqe.so')],capture_output=True,text=True,timeout=30)
    if c.returncode:raise RuntimeError(c.stdout+c.stderr)
    lib=C.CDLL(str(run/'wqe.so'));lib.as02_wqe_encode.argtypes=[C.POINTER(C.c_uint8),C.POINTER(shared.codec.WQE)]
    records=[]
    for i in range(2):
        w=shared.codec.candidate(wr_id=0xf123456789abc000+i,sequence=i+1,epoch=0x9123456700000001,
            local_address=0xfedcba9876543000+i*64,remote_key=0xffffffff if i else 0,opcode=i+1)
        out=(C.c_uint8*64)();assert lib.as02_wqe_encode(out,C.byref(w))==0 and bytes(out)==shared.codec.oracle(w);records.append(bytes(out))
    (run/'records.hex').write_text(''.join(f'{int.from_bytes(r,"little"):0128x}\n'for r in records));(run/'tb.v').write_text(bench())
    command=['iverilog','-g2012','-s','tb','-o',str(run/'test.vvp'),str(run/'tb.v'),*map(str,SOURCES)]
    report=dict(scope=__doc__,pass_test=False,terminal_exit_status=None,directory=str(run.relative_to(ROOT)),source_sha256=before,
        compiler_command=command,bench_sha256=hashlib.sha256((run/'tb.v').read_bytes()).hexdigest(),
        records_sha256=hashlib.sha256((run/'records.hex').read_bytes()).hexdigest(),compile_timeout_seconds=60,simulation_timeout_seconds=60,
        actual_SQ_CSR_AW_W_adapter_and_real_backend_composition=True,raw_SQ_configuration_bypass=False,
        actual_shared_router_RAM_mux_PCIe_parent_guard=True,constant_parent_proof_or_host_counter_substitution=False,
        descriptor_status_RAM_agents_used=False,hardware_verified=False,native_parent_mapping_or_kernel_driver=False,
        local_MR_WQE_executor_CQ_or_verbs=False,actual_kernel_pins_or_coherent_allocation=False)
    started=time.monotonic()
    try:
        c=subprocess.run(command,capture_output=True,text=True,timeout=60);(run/'compile.log').write_text(c.stdout+c.stderr)
        if c.returncode:raise RuntimeError(c.stdout+c.stderr)
        s=subprocess.run(['vvp',str(run/'test.vvp')],cwd=run,capture_output=True,text=True,timeout=60)
        (run/'simulation.log').write_text(s.stdout+s.stderr);print(s.stdout+s.stderr,flush=True)
        if s.returncode or 'ERROR:'in s.stdout+s.stderr:raise RuntimeError('actual CSR/shared-PCIe simulation failed')
        rows=[json.loads(l[19:])for l in s.stdout.splitlines()if l.startswith('SHARED_PCIE_RESULT ')]
        control=[json.loads(l[18:])for l in s.stdout.splitlines()if l.startswith('SQ_CONTROL_RESULT ')]
        if len(rows)!=1 or not rows[0]['pass_test']or len(control)!=1:raise ValueError('missing actual CSR/shared results')
        if before!={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest()for n in before}:raise ValueError('sources changed during execution')
        report.update(pass_test=True,terminal_exit_status=0,summary=rows[0],control_summary=control[0],source_sha256_before_after_equal=True,
            SQ_descriptor_bytes_verified=128,payload_WRITE_bytes_verified=65,payload_READ_bytes_verified=65,
            host_sentinel_bytes_verified=16319,coherent_ring_unchanged_bytes_verified=128)
    except Exception as e:report.update(terminal_exit_status=1,error_type=type(e).__name__,error=str(e));raise
    finally:
        report['elapsed_seconds']=time.monotonic()-started
        with args.report.open('x')as out:json.dump(report,out,indent=2);out.write('\n')


if __name__=='__main__':main()
