#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual outer+unchanged native child; backend/CQ endpoints are MODELED.

Full WR identity, per-DMA nonreused tags and exact raw/data/status joins;
replays after final data receipt retain lease until identical CQ retirement.
Not native MR/page/DMA/MAC/CQ integration, HLS runtime or hardware proof.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
import probe_atomic_responder as helper

ROOT=helper.ROOT
sys.path.insert(0,str(ROOT/'rdma/rnic/fpga'))
import derive_segmented_source as source
RTL=ROOT/'rdma/rnic/rtl/rocev2_segmented_source_executor.v'
digest=helper.digest


def owner(op=1,length=8193):
    return (0xf123456789abc007<<524)|(7<<460)|(0x9123456700000001<<396)|(2<<372)|\
        (17<<356)|(9<<340)|(op<<324)|(1<<308)|(length<<276)|(8<<244)|\
        (0xfedcba9876543210<<180)|(0x210<<116)|\
        ((0xe23456789abcdef0<<52)|(0x81234567<<20)if op==1 else 0)|3


TB=r'''
`timescale 1ns/1ps
module tb;
localparam MAX_QPS=8;
// DECLARATIONS
always #2 clk=~clk;
reg [747:0] expected=748'hOWNER;
integer cycle=0,i,b,deadline,output_bytes=0,output_base=0,events=0;
reg [585:0] held;reg stalled=0,stall_source_once=0;
always @(posedge clk)if(!rst)begin
 cycle=cycle+1;if(cycle>20000)$fatal(1,"bounded source test");
 if(stalled && (!m_axis_hls_tvalid || {m_axis_hls_tdata,m_axis_hls_tkeep,m_axis_hls_tlast}!==held[576:0]))$fatal(1,"source beat retracted under stall");
 stalled=m_axis_hls_tvalid&&!m_axis_hls_tready;held={9'd0,m_axis_hls_tdata,m_axis_hls_tkeep,m_axis_hls_tlast};
 if(m_axis_hls_tvalid && m_axis_hls_tready)begin
  for(b=0;b<64;b=b+1)if(m_axis_hls_tkeep[b])begin
   if(m_axis_hls_tdata[b*8+:8]!==((((output_base+output_bytes)*37)^8'ha5)&255))$fatal(1,"actual child source byte");
   output_bytes=output_bytes+1;
  end
 end
 if(m_memory_event_valid && m_memory_event_ready)begin
  if(m_memory_event_context!==expected || m_memory_event_error)$fatal(1,"aggregate whole WR event identity");events=events+1;
 end
end
function [95:0] raw_at;input integer off;
 reg [63:0] va;reg [31:0] bytes,total;
 // Procedural stimulus only; the DUT's continuous validator takes explicit
 // full-owner arguments and does not depend on this testbench function.
 begin total=expected[307:276];va=64'hfedcba9876543210+off;bytes=total-off>4096 ? 4096:total-off;
  raw_at={2'd0,10'd2,va[51:48],1'b1,1'b0,va[52],off+bytes==total,bytes[27:0],va[47:0]};end
endfunction
task bind_owner;
 begin
  @(negedge clk);s_owner_context=expected;s_owner_valid=1;
  @(posedge clk);if(!s_owner_ready)$fatal(1,"full source owner rejected");
  @(negedge clk);s_owner_valid=0;s_owner_context=0;
  if(!busy || queue_guard!==4)$fatal(1,"whole source lease missing");
 end
endtask
task raw_command;input integer off;
 begin
  @(negedge clk);s_hls_command=raw_at(off);s_hls_command_valid=1;deadline=cycle+100;
  @(posedge clk);while(!s_hls_command_ready)begin @(posedge clk);if(cycle>deadline)$fatal(1,"actual child raw timeout %h",fault_code);end
  @(negedge clk);s_hls_command_valid=0;
 end
endtask
task backend_command;input integer off;input integer bytes;input [15:0] nonce;
 reg [144:0] saved;
 begin
  deadline=cycle+100;
  while(!m_memory_command_valid)begin @(negedge clk);if(cycle>deadline)$fatal(1,"actual child command timeout");end
  if(m_memory_command_write || m_memory_command_offset!==64'h210+off || m_memory_command_length!==bytes ||
   m_memory_command_key!==8 || m_memory_command_tag!==nonce)$fatal(1,"child range/key/fresh tag mismatch");
  saved={m_memory_command_write,m_memory_command_offset,m_memory_command_length,m_memory_command_key,m_memory_command_tag};
  repeat(10)begin @(negedge clk);if(!m_memory_command_valid || saved!=={m_memory_command_write,m_memory_command_offset,m_memory_command_length,m_memory_command_key,m_memory_command_tag})$fatal(1,"offered backend command changed");end
  m_memory_command_ready=1;@(posedge clk);@(negedge clk);m_memory_command_ready=0;
 end
endtask
task backend_data;input integer off;input integer bytes;
 integer p,j;
 begin
  output_base=off;output_bytes=0;
  for(p=0;p<bytes;p=p+64)begin
   @(negedge clk);s_axis_memory_tdata=~512'd0;s_axis_memory_tkeep=0;
   if(p==0 && stall_source_once)m_axis_hls_tready=0;
   for(j=0;j<64 && p+j<bytes;j=j+1)begin
    s_axis_memory_tdata[j*8+:8]=((off+p+j)*37)^8'ha5;s_axis_memory_tkeep[j]=1;
   end
   s_axis_memory_tlast=p+64>=bytes;s_axis_memory_tvalid=1;
   @(posedge clk);while(!s_axis_memory_tready)@(posedge clk);
   @(negedge clk);s_axis_memory_tvalid=0;
   if(p==0 && stall_source_once)begin
    repeat(20)begin @(negedge clk);if(!m_axis_hls_tvalid || output_bytes || m_memory_event_valid)$fatal(1,"stalled real source beat lost/premature event");end
    m_axis_hls_tready=1;stall_source_once=0;
   end
  end
  deadline=cycle+100;
  while(output_bytes!=bytes)begin @(negedge clk);if(cycle>deadline)$fatal(1,"actual source data consumer timeout");end
 end
endtask
task status;input [15:0] nonce;
 begin
  @(negedge clk);s_memory_status_tag=nonce;s_memory_status_error=0;s_memory_status_valid=1;
  @(posedge clk);while(!s_memory_status_ready)@(posedge clk);
  @(negedge clk);s_memory_status_valid=0;repeat(5)@(negedge clk);
  if(fault)$fatal(1,"unexpected source fault %h",fault_code);
 end
endtask
task fragment;input integer off;input integer bytes;input [15:0] nonce;
 begin raw_command(off);backend_command(off,bytes,nonce);backend_data(off,bytes);status(nonce);end
endtask
task quarantine;
 begin repeat(10)@(negedge clk);if(!fault || !busy || queue_guard!==255 || retired_count)$fatal(1,"source fault released owner");end
endtask
initial begin
 rst=1;repeat(5)@(negedge clk);rst=0;enable=1;m_axis_hls_tready=1;
 // BODY
 $display("SEGMENTED_SOURCE_UNIT {\"pass_test\":true,\"fragments\":%0d,\"replays\":%0d,\"events\":%0d}",fragment_count,replay_count,events);$finish;
end
endmodule
'''


class SegmentedSource(unittest.TestCase):
    reports={}
    runs=[]
    def simulate(self,body,op=1,tag_width=14):
        run=Path(tempfile.mkdtemp(prefix='segmented-source-',dir=ROOT/'rdma/rnic/build'))
        ram=Path(tempfile.mkdtemp(prefix='as02-segmented-source-',dir='/dev/shm'))
        (run/'child.v').write_text(source.child_source())
        decl=helper.instance(RTL,'dut','',{})
        if tag_width!=14:
            self.assertEqual(decl.count('rocev2_segmented_source_executor dut('),1)
            decl=decl.replace('rocev2_segmented_source_executor dut(',f'rocev2_segmented_source_executor #(.TAG_SEQUENCE_WIDTH({tag_width})) dut(')
        tb=TB.replace('// DECLARATIONS',decl).replace("748'hOWNER",f"748'h{owner(op):0187x}").replace('// BODY',body)
        (run/'tb.v').write_text(tb)
        self.runs.append(run)
        cmd=['iverilog','-g2012','-s','tb','-o',str(ram/'test'),str(run/'tb.v'),str(RTL),str(run/'child.v')]
        c=subprocess.run(cmd,capture_output=True,text=True,timeout=30);(run/'compile.log').write_text(c.stdout+c.stderr)
        self.assertEqual(c.returncode,0,c.stdout+c.stderr)
        self.assertFalse(any('expects'in l and 'bits'in l for l in c.stderr.splitlines()),c.stderr)
        start=time.monotonic();r=subprocess.run(['vvp',str(ram/'test')],cwd=run,capture_output=True,text=True,timeout=10)
        (run/'simulation.log').write_text(r.stdout+r.stderr);self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        self.reports.setdefault(self._testMethodName,[]).append(dict(directory=str(run.relative_to(ROOT)),
            seconds=time.monotonic()-start,artifacts={str(p.relative_to(ROOT)):digest(p)for p in run.iterdir()if p.is_file()},
            RAM_binary_sha256=digest(ram/'test')))

    def test_WRITE_SEND_one_event_and_final_replay_retained_until_exact_CQ(self):
        for op in [1,3]:
            self.simulate(r'''
bind_owner();s_retire_context=expected;s_retire_valid=1;stall_source_once=1;
fragment(0,4096,16'hc001);if(m_memory_event_valid || s_retire_ready)$fatal(1,"partial chunk completed whole WR");
fragment(0,4096,16'hc002);if(m_memory_event_valid || s_retire_ready)$fatal(1,"replay completed whole WR");
fragment(4096,4096,16'hc003);if(m_memory_event_valid || s_retire_ready)$fatal(1,"middle completed whole WR");
fragment(8192,1,16'hc004);
if(!m_memory_event_valid || s_retire_ready || m_memory_event_context!==expected)$fatal(1,"whole event without held lease");
repeat(20)begin @(negedge clk);if(!m_memory_event_valid || m_memory_event_context!==expected || m_memory_event_error || s_retire_ready)$fatal(1,"whole event changed under stall");end
s_retire_valid=0;m_memory_event_ready=1;@(posedge clk);@(negedge clk);m_memory_event_ready=0;
fragment(8192,1,16'hc005);
if(m_memory_event_valid || events!=1 || fragment_count!=3 || replay_count!=2 || !busy || queue_guard!==4)$fatal(1,"post-event replay lost whole WR lease");
s_retire_valid=1;@(posedge clk);if(!s_retire_ready)$fatal(1,"identical genuine CQ not ready");
@(negedge clk);s_retire_valid=0;#1;
if(busy || queue_guard || retired_count!=1 || fault)$fatal(1,"whole owner not released by exact CQ");
''',op)

    def test_nonsequential_raw_and_foreign_retirement_never_authorize(self):
        for body in ["bind_owner();s_hls_command=raw_at(4096);s_hls_command_valid=1;",
                     "bind_owner();s_retire_context=expected^1;s_retire_valid=1;",
                     "expected[396]=1'bx;s_owner_context=expected;s_owner_valid=1;"]:
            self.simulate(body+'quarantine();if(m_memory_command_valid || m_memory_event_valid)$fatal(1,"bad request created DMA/event");')

    def test_stale_backend_status_rejected_during_next_unique_tag(self):
        self.simulate(r'''
bind_owner();fragment(0,4096,16'hc001);raw_command(4096);backend_command(4096,4096,16'hc002);
s_memory_status_tag=16'hc001;s_memory_status_valid=1;quarantine();
if(s_memory_status_ready || m_memory_event_valid)$fatal(1,"old DMA tag retired new fragment");
''')

    def test_parent_fault_retains_whole_owner_and_offered_backend_command(self):
        self.simulate(r'''
bind_owner();raw_command(0);while(!m_memory_command_valid)@(negedge clk);
parent_fault=1;repeat(20)begin @(negedge clk);if(!m_memory_command_valid || m_memory_command_tag!==16'hc001 || m_memory_event_valid)$fatal(1,"late fault retracted command/invented whole success");end
quarantine();
''')

    def test_nonwrapping_tag_exhaustion_quarantines_without_fourth_DMA(self):
        self.simulate(r'''
bind_owner();fragment(0,4096,16'hc001);fragment(0,4096,16'hc002);fragment(4096,4096,16'hc003);
if(!tags_exhausted || m_memory_event_valid)$fatal(1,"tag wrap/partial whole event");
s_hls_command=raw_at(8192);s_hls_command_valid=1;quarantine();
if(m_memory_command_valid || s_hls_command_ready || m_memory_event_valid)$fatal(1,"exhausted tag reused");
''',tag_width=2)

    def test_actual_child_backend_error_never_becomes_whole_success(self):
        self.simulate(r'''
bind_owner();raw_command(0);backend_command(0,4096,16'hc001);
s_memory_status_tag=16'hc001;s_memory_status_error=7;s_memory_status_valid=1;
@(posedge clk);while(!s_memory_status_ready)@(posedge clk);
@(negedge clk);s_memory_status_valid=0;quarantine();
if(!m_memory_event_valid || m_memory_event_context!==expected || m_memory_event_error!==7 || s_retire_ready)$fatal(1,"backend error lost/misreported");
''')

    def test_small_WRITE_SEND_also_retains_replay_authority_until_CQ(self):
        for op in [1,3]:
            self.simulate(r'''
expected[307:276]=8;bind_owner();fragment(0,8,16'hc001);
if(!m_memory_event_valid || !busy)$fatal(1,"small source missing whole event/lease");
m_memory_event_ready=1;@(posedge clk);@(negedge clk);m_memory_event_ready=0;
fragment(0,8,16'hc002);
if(m_memory_event_valid || events!=1 || fragment_count!=1 || replay_count!=1 || !busy || queue_guard!==4)$fatal(1,"small source replay authority lost at memory event");
s_retire_context=expected;s_retire_valid=1;@(posedge clk);if(!s_retire_ready)$fatal(1,"small exact CQ not ready");
@(negedge clk);s_retire_valid=0;#1;
if(busy || queue_guard || retired_count!=1 || fault)$fatal(1,"small whole owner not retired");
''',op)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve prior evidence')
    inputs=[RTL,Path(__file__).resolve(),Path(source.__file__).resolve(),Path(helper.__file__).resolve()]
    before={str(p.relative_to(ROOT)):digest(p)for p in inputs};start=time.monotonic()
    r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(SegmentedSource))
    assert all(digest(ROOT/n)==h for n,h in before.items())
    result=dict(scope=__doc__,pass_test=r.wasSuccessful(),methods=r.testsRun,seconds=time.monotonic()-start,
        source_sha256=before,tests=SegmentedSource.reports,four_state=True,
        all_run_artifact_sha256={str(p.relative_to(ROOT)):digest(p)for run in SegmentedSource.runs for p in run.iterdir()if p.is_file()},
        actual_bounded_native_child=True,backend_and_CQ_endpoints_modeled=True,
        reserved_backend_namespace_globally_integrated=False,native_or_hardware_runtime=False)
    with a.report.open('x')as f:f.write(json.dumps(result,indent=2)+'\n')
    raise SystemExit(not r.wasSuccessful())
