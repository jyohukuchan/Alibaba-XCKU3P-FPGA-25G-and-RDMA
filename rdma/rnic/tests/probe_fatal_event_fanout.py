#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual1000-bit two-consumer RTL fanout, independent bounded backpressure.

Producer/receivers are models, not a native error certificate or drain proof.
"""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile
import time
import audit_segmented_receive as binding
ROOT=binding.ROOT;digest=binding.digest;DUT=ROOT/'rdma/rnic/rtl/rocev2_fatal_event_fanout.v'
TB=r'''
`timescale 1ns/1ps
module tb;
reg clk=0,rst=1,s_valid=0,m_observer_ready=0,m_mailbox_ready=0;
reg [999:0] s_data=0;
wire s_ready,m_observer_valid,m_mailbox_valid;
wire [999:0] m_observer_data,m_mailbox_data;
rocev2_fatal_event_fanout dut(.*);
always #2 clk=~clk;
integer up=0,ob=0,mb=0,cycles=0,i;
reg [999:0] expected;
always @(posedge clk)if(!rst)begin
 cycles=cycles+1;if(cycles>100000)$fatal(1,"fanout cycle limit");
 if(s_valid && s_ready)up=up+1;
 if(m_observer_valid && m_observer_ready)begin
  if(m_observer_data!==expected)$fatal(1,"observer full1000 ownership");ob=ob+1;
 end
 if(m_mailbox_valid && m_mailbox_ready)begin
  if(m_mailbox_data!==expected)$fatal(1,"mailbox full1000 ownership");mb=mb+1;
 end
end
task tick;begin @(posedge clk);@(negedge clk);end endtask
initial begin
 repeat(8)tick;rst=0;
 for(i=0;i<1000;i=i+1)expected[i]=(i%7==0 || i%11==0);
 s_data=expected;s_valid=1;m_mailbox_ready=1;tick;
 if(up || ob || mb!=1)$fatal(1,"early source lease release");
 repeat(71)begin
  m_mailbox_ready=~m_mailbox_ready;tick;
  if(!m_observer_valid || m_observer_data!==expected || m_mailbox_valid || up || ob || mb!=1)
   $fatal(1,"observer stall lost valid/data or duplicated mailbox");
 end
 m_observer_ready=1;tick;s_valid=0;
 if(up!=1 || ob!=1 || mb!=1)$fatal(1,"first exact join");
 repeat(8)tick;
 expected=~expected;s_data=expected;s_valid=1;m_mailbox_ready=0;tick;
 if(up!=1 || ob!=2 || mb!=1)$fatal(1,"mailbox-full source lease");
 repeat(77)begin
  m_observer_ready=~m_observer_ready;tick;
  if(!m_mailbox_valid || m_mailbox_data!==expected || m_observer_valid || up!=1 || ob!=2 || mb!=1)
   $fatal(1,"mailbox stall lost valid/data or duplicated observer");
 end
 m_mailbox_ready=1;tick;s_valid=0;
 if(up!=2 || ob!=2 || mb!=2)$fatal(1,"second exact join");
 expected=1000'h1;s_data=expected;m_observer_ready=1;s_valid=1;tick;s_valid=0;
 if(up!=3 || ob!=3 || mb!=3)$fatal(1,"simultaneous direct transfer");
 repeat(17)tick;if(up!=3 || ob!=3 || mb!=3)$fatal(1,"idle fabricated event");
 $display("FATAL_FANOUT_RESULT {\"pass_test\":true,\"events\":3,\"bits\":1000,\"independent_stalls\":true,\"one_accept_per_receiver\":true,\"upstream_lease_held_until_both\":true}");
 $finish;
end
endmodule
'''


def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
 if a.report.exists():p.error('preserve all earlier evidence')
 before={str(q.relative_to(ROOT)):digest(q)for q in[DUT,Path(__file__).resolve()]}
 run=Path(tempfile.mkdtemp(prefix='fatal-event-fanout-',dir=ROOT/'rdma/rnic/build'));ram=Path(tempfile.mkdtemp(prefix='as02-fatal-fanout-',dir='/dev/shm'))
 (run/'tb.v').write_text(TB)
 r=dict(scope=__doc__,pass_test=False,directory=str(run.relative_to(ROOT)),source_sha256=before,
  clock_ns=4,runtime_limit_seconds=10,compile_limit_seconds=10,cycle_limit=100000,four_state=True,
  native_or_Linux_runtime=False,hardware_verified=False,full_board_timing=False,QP_global_drain_unpin=False)
 try:
  start=time.monotonic()
  with(run/'compile.log').open('x')as f:c=subprocess.run(['iverilog','-g2012','-s','tb','-o',str(ram/'test'),str(run/'tb.v'),str(DUT)],stdout=f,stderr=subprocess.STDOUT,timeout=10)
  r['compile_seconds']=time.monotonic()-start
  if c.returncode:raise ValueError('actual fanout compile failed')
  start=time.monotonic()
  with(run/'runtime.log').open('x')as f:c=subprocess.run(['vvp',str(ram/'test')],stdout=f,stderr=subprocess.STDOUT,timeout=10)
  r.update(seconds=time.monotonic()-start,exit=c.returncode)
  if c.returncode:raise ValueError('actual fanout RTL assertion failed')
  lines=[json.loads(l.split(' ',1)[1])for l in(run/'runtime.log').read_text().splitlines()if l.startswith('FATAL_FANOUT_RESULT ')]
  if len(lines)!=1 or not lines[0]['pass_test']:raise ValueError('one actual RTL summary required')
  for n,h in before.items():
   if digest(ROOT/n)!=h:raise ValueError('actual source changed:'+n)
  r.update(pass_test=True,summary=lines[0])
 except Exception as e:r.update(error_type=type(e).__name__,error=str(e));raise
 finally:
  r['artifact_sha256']={str(q.relative_to(ROOT)):digest(q)for q in run.iterdir()if q.is_file()}
  r['RAM_artifact_sha256']={str(q):digest(q)for q in ram.iterdir()if q.is_file()}
  with a.report.open('x')as f:f.write(json.dumps(r,indent=2)+'\n')
 print(json.dumps(dict(pass_test=True,seconds=r['seconds'],events=3,bits=1000)))


if __name__=='__main__':main()
