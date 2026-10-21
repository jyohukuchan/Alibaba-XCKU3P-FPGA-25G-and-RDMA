#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual native WRITE selector: every256 opcode x2 held-message states.

Classification is NOT integrity/QP/MR authorization. Every data/KEEP/EOF
bit is preserved; stalls and changing force AFTER header cannot reroute a
frame. The upstream checker and downstream real native owners are separate.
"""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile
import time
import probe_segmented_write_controller as controller

ROOT=controller.ROOT;leaves=controller.leaves;digest=controller.prior.digest

TB=r'''
`timescale 1ns/1ps
module tb;
reg clk=0,rst=1,force_write=0;always #2 clk=~clk;
reg [127:0] s_data=0;reg [15:0] s_keep=0;reg s_valid=0,s_last=0;wire s_ready;
wire [127:0] m_normal_data,m_atomic_data;wire [15:0] m_normal_keep,m_atomic_keep;
wire m_normal_valid,m_normal_last,m_atomic_valid,m_atomic_last,configuration_guard,fault;
reg m_normal_ready=0,m_atomic_ready=0;
rocev2_native_write_rx_router dut(.*);
reg [127:0] words[0:4];integer cycle=0,op,held,i,out_count=0,frames=0,write_frames=0,normal_frames=0,deadline;
reg expected=0,stalled=0;reg [145:0] stalled_word;
wire ov=m_normal_valid || m_atomic_valid;
wire oready=m_atomic_valid ? m_atomic_ready:m_normal_ready;
wire [145:0] observed={m_atomic_valid,m_atomic_valid ? m_atomic_last:m_normal_last,
 m_atomic_valid ? m_atomic_keep:m_normal_keep,m_atomic_valid ? m_atomic_data:m_normal_data};
always @(negedge clk)if(!rst)begin m_normal_ready=(cycle%7)!=0;m_atomic_ready=(cycle%5)!=0;end
always @(posedge clk)if(!rst)begin
 cycle=cycle+1;if(cycle>100000)$fatal(1,"original bounded classifier geometry");
 if(fault || m_normal_valid && m_atomic_valid)$fatal(1,"actual classifier fault/dual route");
 if(stalled && (!ov || observed!==stalled_word))$fatal(1,"classification/bytes changed under stall");
 stalled=ov && !oready;stalled_word=observed;
 if(ov && oready)begin
  if(m_atomic_valid!==expected || (m_atomic_valid ? m_atomic_data:m_normal_data)!==words[out_count] ||
     (m_atomic_valid ? m_atomic_keep:m_normal_keep)!==(out_count==4 ? 16'h0007:16'hffff) ||
     (m_atomic_valid ? m_atomic_last:m_normal_last)!==(out_count==4))$fatal(1,"every opcode/force/byte/KEEP/EOF classification oracle");
  out_count=out_count+1;
  if(out_count==5)begin frames=frames+1;if(expected)write_frames=write_frames+1;else normal_frames=normal_frames+1;end
 end
end
initial begin
 repeat(5)@(negedge clk);rst=0;
 for(held=0;held<2;held=held+1)for(op=0;op<256;op=op+1)begin
  force_write=held;expected=held || op>=6 && op<=9;out_count=0;
  for(i=0;i<5;i=i+1)words[i]=128'h0123456789abcdef_fedcba9876543210^(128'h1122334455667788*i)^op;
  words[0][7:0]=8'h45;words[1][103:96]=op;
  for(i=0;i<5;i=i+1)begin
   s_data=words[i];s_keep=i==4 ? 16'h0007:16'hffff;s_last=i==4;s_valid=1;
   @(posedge clk);while(!s_ready)@(posedge clk);@(negedge clk);s_valid=0;
   if(i==1)force_write=!held;
  end
  deadline=cycle+100;while(out_count!=5)begin if(cycle>deadline)$fatal(1,"actual classifier drain deadline");@(negedge clk);end
  #1;if(configuration_guard)$fatal(1,"completed frame retained classifier owner");
 end
 if(frames!=512 || write_frames!=260 || normal_frames!=252)$fatal(1,"full opcode space/normal-Atomic preservation count");
 $display("WRITE_CLASSIFIER_RESULT {\"pass_test\":true,\"frames\":512,\"opcodes\":256,\"force_states\":2,\"WRITE_frames\":260,\"other_frames\":252,\"every_byte_KEEP_EOF\":true,\"cycles\":%0d}",cycle);
 $finish;
end
endmodule
'''


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve previous evidence')
    run=Path(tempfile.mkdtemp(prefix='native-write-classifier-',dir=ROOT/'rdma/rnic/build'))
    ram=Path(tempfile.mkdtemp(prefix='as02-native-write-classifier-',dir='/dev/shm'))
    inputs=[Path(__file__).resolve(),Path(leaves.__file__).resolve(),leaves.ROUTER]
    before={str(q.relative_to(ROOT)):digest(q)for q in inputs}
    result=dict(scope=__doc__,pass_test=False,directory=str(run.relative_to(ROOT)),source_sha256=before,
        compile_limit_seconds=10,runtime_limit_seconds=10,clock_ns=4,cycle_limit=100000,hardware_verified=False,complete_native=False)
    try:
        (run/'router.v').write_text(leaves.router());(run/'tb.v').write_text(TB)
        start=time.monotonic();c=subprocess.run(['iverilog','-g2012','-s','tb','-o',str(ram/'test'),str(run/'tb.v'),str(run/'router.v')],capture_output=True,text=True,timeout=10)
        (run/'compile.log').write_text(c.stdout+c.stderr);result['compile_seconds']=time.monotonic()-start
        if c.returncode:raise ValueError('new classifier compile failed')
        start=time.monotonic();c=subprocess.run(['vvp',str(ram/'test')],cwd=run,capture_output=True,text=True,timeout=10)
        (run/'simulation.log').write_text(c.stdout+c.stderr);result.update(exit=c.returncode,simulation_seconds=time.monotonic()-start)
        if c.returncode:raise ValueError('actual512-frame classifier failed')
        rows=[json.loads(s.split(' ',1)[1])for s in c.stdout.splitlines()if s.startswith('WRITE_CLASSIFIER_RESULT ')]
        if len(rows)!=1 or not rows[0]['pass_test']:raise ValueError('full actual routing assertion missing')
        if any(digest(ROOT/n)!=h for n,h in before.items()):raise ValueError('source changed')
        result.update(pass_test=True,source_unchanged=True,summary=rows[0])
    except Exception as e:result.update(error_type=type(e).__name__,error=str(e));raise
    finally:
        result['artifact_sha256']={str(q.relative_to(ROOT)):digest(q)for q in run.iterdir()if q.is_file()}
        result['RAM_artifact_sha256']={str(q):digest(q)for q in ram.iterdir()if q.is_file()}
        with a.report.open('x')as f:f.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(pass_test=True,frames=512,seconds=result['simulation_seconds'])),flush=True)


if __name__=='__main__':main()
