#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Exact native four-client MR island: normal/SQ/Atomic/typed-WRITE, ONE table.

Extract the actual gateway's unchanged MR-chain and write guard expressions,
not a duplicate Python/RTL authorization model. Native caller/state/lease
and management boundaries are modeled. No complete native/HLS/DMA runtime.
"""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile
import time
import check_segmented_write_native_gateway as native

ROOT=native.ROOT;candidate=native.candidate;digest=native.digest
MODES=list(range(8))


def bench(protected):
    start=protected.index('wire [7:0] mr_error;');a=protected.index('rocev2_mr_table #',start)
    end=protected.index(');',a)+2;island=protected[start:end]
    x=protected.index('wire write_external_guard=');y=protected.index('assign m_write_native_context=',x)
    guard=protected[x:y]
    declarations=[]
    for d,w,n in candidate.QUERY+candidate.GUARDS:
        declarations.append(('reg 'if d=='input'else'wire ')+(w+' 'if w else'')+n+('=0;'if d=='input'else';'))
    for prefix in ['s_local_mr_request_','atomic_execution_m_mr_']:
        for n,w in [('pd',16),('key',32),('address',64),('length',32),('operation',3),('tag',16),('valid',1)]:
            declarations.append('reg '+('['+str(w-1)+':0] 'if w>1 else'')+prefix+n+'=0;')
    for prefix in ['m_local_mr_response_','atomic_execution_s_mr_']:
        for n,w in [('tag',16),('error',8),('offset',64),('length',32),('valid',1)]:
            declarations.append('wire '+('['+str(w-1)+':0] 'if w>1 else'')+prefix+n+';')
    return r'''
`timescale 1ns/1ps
module tb;
localparam LOCAL_WQE_ENABLE=1,COLLECT=0,LOOKUP=2,MR_WAIT=3;
reg clk=0,rst=1;always #2 clk=~clk;
reg fault=0,recv_data_operation=0,write_operation=1;
reg [3:0] state=COLLECT;
reg [15:0] trusted_pd=17,lease_tag=16'hf122;
reg [31:0] request_key=32'h80000008,request_length=65;
reg [63:0] request_va=64'hfedcba9876543210;
reg [23:0] local_qpn=2;reg [63:0] atomic_context_epoch=64'h9123456700000001;
reg [423:0] s_write_owner=0;reg s_write_owner_valid=0;
wire shared_mr_busy,shared_mr_fault;
reg m_local_mr_response_ready=0,atomic_execution_s_mr_ready=0;
wire s_local_mr_request_ready,atomic_execution_m_mr_ready;
reg [1:0] cfg_mr_command=0;reg [2:0] cfg_mr_index=0;reg [15:0] cfg_mr_pd=17;
reg [31:0] cfg_mr_key=0;reg [63:0] cfg_mr_virtual_address=64'hfedcba9876543000;
reg [63:0] cfg_mr_dma_address=64'h8123456789abc000,cfg_mr_length=8192;
reg [3:0] cfg_mr_access=15;reg cfg_mr_valid=0,cfg_mr_response_ready=0;
wire cfg_mr_ready,cfg_mr_response_valid,mr_epoch_configured;wire [7:0] cfg_mr_response_error;wire [31:0] cfg_mr_response_key;
wire quiescent=!write_external_guard && !write_mr_busy && !atomic_mr_busy && !shared_mr_busy && state==COLLECT && !hold_old_lease;
reg hold_old_lease=0;
'''+ '\n'.join(declarations)+'\n'+guard+'\n'+island+r'''
integer mode=0,cycle=0,queries=0,responses=0,i,limit;reg [3:0] offered=0,taken=0,replied=0;
reg [7:0] expect_error[0:3];reg [63:0] expect_offset[0:3];reg [31:0] expect_length[0:3];
wire [3:0] qv={s_write_mr_request_valid,atomic_execution_m_mr_valid,s_local_mr_request_valid,state==LOOKUP};
wire [3:0] qr={s_write_mr_request_ready,atomic_execution_m_mr_ready,s_local_mr_request_ready,mr_request_ready};
wire [3:0] rv={m_write_mr_response_valid,atomic_execution_s_mr_valid,m_local_mr_response_valid,mr_response_valid};
wire [3:0] rr={m_write_mr_response_ready,atomic_execution_s_mr_ready,m_local_mr_response_ready,state==MR_WAIT};
wire [63:0] rt={m_write_mr_response_tag,atomic_execution_s_mr_tag,m_local_mr_response_tag,mr_tag};
wire [31:0] re={m_write_mr_response_error,atomic_execution_s_mr_error,m_local_mr_response_error,mr_error};
wire [255:0] ro={m_write_mr_response_offset,atomic_execution_s_mr_offset,m_local_mr_response_offset,mr_offset};
wire [127:0] rl={m_write_mr_response_length,atomic_execution_s_mr_length,m_local_mr_response_length,mr_length};
always @(posedge clk)if(!rst)begin
 cycle=cycle+1;if(cycle>100000)$fatal(1,"original bounded native MR probe");
 if(shared_mr_fault || atomic_mr_fault || write_mr_fault)$fatal(1,"actual native arbiter fault");
 if(write_table_request_valid && write_table_request_ready)queries=queries+1;
 for(integer c=0;c<4;c=c+1)begin
  if(qv[c] && qr[c])taken[c]=1;
  if(rv[c])begin
   if(!taken[c] || replied[c] || rt[c*16+:16]!==16'hf123 || re[c*8+:8]!==expect_error[c] ||
      ro[c*64+:64]!==(expect_error[c] ? 64'd0:expect_offset[c]) ||
      rl[c*32+:32]!==(expect_error[c] ? 32'd0:expect_length[c]))$fatal(1,"same-tag response owner/key/PD/permission/range oracle client%0d",c);
   if(c==3 && m_write_mr_response_dma_address!==(expect_error[c] ? 64'd0:cfg_mr_dma_address+expect_offset[c]))
    $fatal(1,"native WRITE full64 translation/denial zeroing");
   if(rr[c])begin replied[c]=1;responses=responses+1;end
  end
 end
end
task tick;begin @(posedge clk);@(negedge clk);end endtask
task configure;
 input [1:0] op;input [31:0] key;
 begin cfg_mr_command=op;cfg_mr_key=key;cfg_mr_valid=1;
 @(posedge clk);while(!cfg_mr_ready)@(posedge clk);@(negedge clk);cfg_mr_valid=0;
 while(!cfg_mr_response_valid)tick;
 if(cfg_mr_response_error || cfg_mr_response_key!==(op==3 ? key:op==2 ? 32'd0:32'h80000008))$fatal(1,"actual native MR management failed");
 cfg_mr_response_ready=1;tick;cfg_mr_response_ready=0;end
endtask
initial begin
 if(!$value$plusargs("MODE=%d",mode))$fatal(1,"mode required");
 repeat(5)@(negedge clk);rst=0;
 if(mode==4)cfg_mr_access=5;
 configure(3,32'h10000000);configure(1,0);
 s_local_mr_request_pd=17;s_local_mr_request_key=32'h80000008;s_local_mr_request_address=cfg_mr_virtual_address+529;
 s_local_mr_request_length=31;s_local_mr_request_operation=0;s_local_mr_request_tag=16'hf123;
 atomic_execution_m_mr_pd=17;atomic_execution_m_mr_key=32'h80000008;atomic_execution_m_mr_address=cfg_mr_virtual_address+536;
 atomic_execution_m_mr_length=8;atomic_execution_m_mr_operation=4;atomic_execution_m_mr_tag=16'hf123;
 s_write_mr_request_pd=17;s_write_mr_request_key=32'h80000008;s_write_mr_request_address=cfg_mr_virtual_address+531;
 s_write_mr_request_length=65;s_write_mr_request_operation=3;s_write_mr_request_tag=16'hf123;
 for(i=0;i<4;i=i+1)expect_error[i]=0;
 expect_offset[0]=528;expect_offset[1]=529;expect_offset[2]=536;expect_offset[3]=531;
 expect_length[0]=65;expect_length[1]=31;expect_length[2]=8;expect_length[3]=65;
 if(mode==1)begin s_write_mr_request_key=32'h00000008;expect_error[3]=1;end
 if(mode==2)s_write_mr_request_pd=18;
 if(mode==3)s_write_mr_request_operation=2;
 if(mode==4)begin expect_error[0]=3;expect_error[2]=3;expect_error[3]=3;end
 if(mode==5)begin s_write_mr_request_address=cfg_mr_virtual_address+8191;s_write_mr_request_length=2;expect_error[3]=4;end
 if(mode==6)s_write_mr_request_pd=16'hxxxx;
 s_write_held=1;s_write_mr_guard=1;s_write_queue_guard=4;hold_old_lease=1;
 if(mode==2 || mode==3 || mode==6)begin
  s_write_mr_request_valid=1;repeat(17)begin tick;
   if(!write_external_bad || s_write_mr_request_ready || m_write_mr_response_valid || queries || cfg_mr_ready)
    $fatal(1,"untrusted native WRITE client queried or revoked MR");end
  s_write_mr_request_valid=0;
 end else begin
  state=LOOKUP;s_local_mr_request_valid=1;atomic_execution_m_mr_valid=1;s_write_mr_request_valid=1;
  limit=cycle+200;
  while(taken!==15)begin
   if(cycle>limit)$fatal(1,"four actual native clients admission deadline");tick;
   if(taken[0])state=COLLECT;if(taken[1])s_local_mr_request_valid=0;
   if(taken[2])atomic_execution_m_mr_valid=0;if(taken[3])s_write_mr_request_valid=0;
   // Release response stalls after a fixed observation window so all nested
   // native arbiters can admit the competing retained upstream offers.
   if(cycle>limit-170)begin
    state=taken[0] && !replied[0] ? MR_WAIT:COLLECT;
    m_local_mr_response_ready=1;atomic_execution_s_mr_ready=1;m_write_mr_response_ready=1;
   end
  end
  state=replied[0] ? COLLECT:MR_WAIT;m_local_mr_response_ready=1;atomic_execution_s_mr_ready=1;m_write_mr_response_ready=1;
  while(replied!==15)begin if(cycle>limit)$fatal(1,"four same-tag responses deadline");tick;if(replied[0])state=COLLECT;end
  m_local_mr_response_ready=0;atomic_execution_s_mr_ready=0;m_write_mr_response_ready=0;
  cfg_mr_command=2;cfg_mr_key=32'h80000008;cfg_mr_valid=1;
  repeat(17)begin tick;if(cfg_mr_ready || cfg_mr_response_valid || quiescent)$fatal(1,"queries complete is NOT whole-message lease release");end
  cfg_mr_valid=0;
  if(queries!=4 || responses!=4)$fatal(1,"exact one native namespace/four actual queries");
  if(mode==7)begin
   s_write_held=0;s_write_mr_guard=0;s_write_queue_guard=0;hold_old_lease=0;repeat(5)tick;
   configure(2,32'h80000008);
   taken=0;replied=0;expect_error[3]=1;expect_offset[3]=0;
   s_write_held=1;s_write_mr_guard=1;s_write_queue_guard=4;s_write_mr_request_valid=1;
   limit=cycle+100;while(!taken[3])begin if(cycle>limit)$fatal(1,"post-invalidation query admission");tick;end
   s_write_mr_request_valid=0;m_write_mr_response_ready=1;
   while(!replied[3])begin if(cycle>limit)$fatal(1,"actual shared invalidation did not revoke WRITE");tick;end
   m_write_mr_response_ready=0;
   if(queries!=5 || responses!=5)$fatal(1,"invalidation namespace count");
  end
 end
 $display("NATIVE_WRITE_MR_RESULT {\"pass_test\":true,\"mode\":%0d,\"queries\":%0d,\"responses\":%0d,\"native_guard_denied\":%0d,\"cycles\":%0d}",mode,queries,responses,write_external_bad,cycle);
 $finish;
end
endmodule
''',island,guard


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve all prior evidence')
    run=Path(tempfile.mkdtemp(prefix='write-native-mr-gateway-',dir=ROOT/'rdma/rnic/build'))
    ram=Path(tempfile.mkdtemp(prefix='as02-write-native-mr-',dir='/dev/shm'))
    inputs=[Path(__file__).resolve(),Path(candidate.__file__).resolve(),candidate.RTL/'rocev2_mr_query_arbiter.v',candidate.RTL/'rocev2_mr_table.v']
    before={str(p.relative_to(ROOT)):digest(p)for p in inputs}
    result=dict(scope=__doc__,pass_test=False,directory=str(run.relative_to(ROOT)),source_sha256=before,tests={},planned_modes=MODES,
        compile_limit_seconds=10,runtime_limit_seconds=10,clock_ns=4,cycle_limit=100000,
        native_MR_island_extracted_exactly=True,MR_response_model=False,outer_native_HLS_DMA_runtime=False,hardware_verified=False)
    try:
        protected=candidate.derive()[candidate.RTL/'rocev2_protected_responder.v'];tb,island,guard=bench(protected)
        for name,text in [('tb.v',tb),('native_mr_island.v.txt',island),('native_write_guard.v.txt',guard),('native_protected.v.txt',protected)]:
            (run/name).write_text(text)
        cmd=['iverilog','-g2012','-s','tb','-o',str(ram/'test'),str(run/'tb.v'),*map(str,inputs[2:])]
        start=time.monotonic();c=subprocess.run(cmd,capture_output=True,text=True,timeout=10)
        (run/'compile.log').write_text(c.stdout+c.stderr);result['compile_seconds']=time.monotonic()-start
        if c.returncode:raise ValueError('exact native MR island compile failed')
        for mode in MODES:
            start=time.monotonic();c=subprocess.run(['vvp',str(ram/'test'),f'+MODE={mode}'],cwd=run,capture_output=True,text=True,timeout=10)
            (run/(str(mode)+'.log')).write_text(c.stdout+c.stderr);item=dict(exit=c.returncode,seconds=time.monotonic()-start);result['tests'][str(mode)]=item
            if c.returncode:raise ValueError('native four-client MR failed:'+str(mode))
            rows=[json.loads(s.split(' ',1)[1])for s in c.stdout.splitlines()if s.startswith('NATIVE_WRITE_MR_RESULT ')]
            if len(rows)!=1 or not rows[0]['pass_test']:raise ValueError('full native MR assertions missing')
            item['summary']=rows[0]
        if any(digest(ROOT/n)!=h for n,h in before.items()):raise ValueError('sources changed')
        result.update(pass_test=True,source_unchanged=True)
    except Exception as e:result.update(error_type=type(e).__name__,error=str(e));raise
    finally:
        result['artifact_sha256']={str(p.relative_to(ROOT)):digest(p)for p in run.iterdir()if p.is_file()}
        result['RAM_artifact_sha256']={str(p):digest(p)for p in ram.iterdir()if p.is_file()}
        with a.report.open('x')as f:f.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(pass_test=True,modes=8,actual_shared_MR_table=1,full_native_runtime=False)),flush=True)


if __name__=='__main__':main()
