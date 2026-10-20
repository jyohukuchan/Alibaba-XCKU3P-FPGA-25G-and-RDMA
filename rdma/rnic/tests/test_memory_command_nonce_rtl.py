#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual shared-command nonce RTL; command/status neighbors are MODELED.

No MR/data/fence/physical-backend completion is manufactured or proved here.
"""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
import probe_atomic_responder as helper

ROOT=helper.ROOT;digest=helper.digest
RTL=ROOT/'rdma/rnic/rtl/rocev2_memory_command_nonce.v'
TB=r'''
`timescale 1ns/1ps
module tb;
// DECLARATIONS
always #2 clk=~clk;
integer cycles=0,deadline;
reg [144:0] held_command;reg [23:0] held_status;
reg stalled_command=0,stalled_status=0;
always @(posedge clk)if(!rst)begin
 cycles=cycles+1;if(cycles>3000)$fatal(1,"bounded nonce test");
 if(stalled_command && (!m_command_valid || {m_command_write,m_command_offset,m_command_length,m_command_key,m_command_tag}!==held_command))$fatal(1,"physical command changed under stall");
 stalled_command=m_command_valid&&!m_command_ready;
 held_command={m_command_write,m_command_offset,m_command_length,m_command_key,m_command_tag};
 if(stalled_status && (!m_status_valid || {m_status_tag,m_status_error}!==held_status))$fatal(1,"logical status changed under stall");
 stalled_status=m_status_valid&&!m_status_ready;held_status={m_status_tag,m_status_error};
end
task command;input [15:0] logical;input [15:0] physical;
 begin
  @(negedge clk);s_command_write=logical[0];s_command_offset=64'hf123456789abc000+logical;
  s_command_length=65;s_command_key=32'h81234567;s_command_tag=logical;s_command_valid=1;
  @(posedge clk);if(!s_command_ready)$fatal(1,"known logical command not admitted");
  @(negedge clk);s_command_valid=0;
  if(!m_command_valid || m_command_tag!==physical || m_command_write!==logical[0] ||
   m_command_offset!==64'hf123456789abc000+logical || m_command_length!==65 || m_command_key!==32'h81234567)$fatal(1,"physical nonce/immutable full tuple mismatch");
  s_command_offset=0;s_command_key=0;s_command_tag=0;repeat(10)@(negedge clk);
  if(!busy || !configuration_guard || m_status_valid)$fatal(1,"command lease lost");
 end
endtask
task issue;
 begin @(negedge clk);m_command_ready=1;@(posedge clk);@(negedge clk);m_command_ready=0;end
endtask
task receipt;input [15:0] physical;input [7:0] error;
 begin
  @(negedge clk);s_status_tag=physical;s_status_error=error;s_status_valid=1;
  @(posedge clk);while(!s_status_ready)@(posedge clk);
  @(negedge clk);s_status_valid=0;
 end
endtask
task accept_status;input [15:0] logical;input [7:0] error;
 begin
  if(!m_status_valid || m_status_tag!==logical || m_status_error!==error)$fatal(1,"logical tag/error translation");
  repeat(10)@(negedge clk);m_status_ready=1;@(posedge clk);@(negedge clk);m_status_ready=0;#1;
  if(busy || configuration_guard || fault)$fatal(1,"genuine status did not release command");
 end
endtask
task quarantine;
 begin repeat(10)@(negedge clk);if(!fault || !busy || !configuration_guard)$fatal(1,"bad receipt released command");end
endtask
initial begin
 rst=1;repeat(5)@(negedge clk);rst=0;enable=1;
 // BODY
 $display("MEMORY_NONCE_UNIT {\"pass_test\":true,\"commands\":%0d,\"statuses\":%0d}",command_count,status_count);$finish;
end
endmodule
'''


class Nonce(unittest.TestCase):
    reports={};runs=[]
    def simulate(self,body,width=16):
        run=Path(tempfile.mkdtemp(prefix='memory-nonce-',dir=ROOT/'rdma/rnic/build'))
        ram=Path(tempfile.mkdtemp(prefix='as02-memory-nonce-',dir='/dev/shm'))
        decl=helper.instance(RTL,'dut','',{})
        if width!=16:
            self.assertEqual(decl.count('rocev2_memory_command_nonce dut('),1)
            decl=decl.replace('rocev2_memory_command_nonce dut(',f'rocev2_memory_command_nonce #(.NONCE_WIDTH({width})) dut(')
        (run/'tb.v').write_text(TB.replace('// DECLARATIONS',decl).replace('// BODY',body));self.runs.append(run)
        c=subprocess.run(['iverilog','-g2012','-s','tb','-o',str(ram/'test'),str(run/'tb.v'),str(RTL)],capture_output=True,text=True,timeout=30)
        (run/'compile.log').write_text(c.stdout+c.stderr);self.assertEqual(c.returncode,0,c.stdout+c.stderr)
        self.assertFalse(any('expects'in l and 'bits'in l for l in c.stderr.splitlines()),c.stderr)
        start=time.monotonic();r=subprocess.run(['vvp',str(ram/'test')],cwd=run,capture_output=True,text=True,timeout=10)
        (run/'simulation.log').write_text(r.stdout+r.stderr);self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        self.reports.setdefault(self._testMethodName,[]).append(dict(directory=str(run.relative_to(ROOT)),
            seconds=time.monotonic()-start,RAM_binary_sha256=digest(ram/'test')))

    def test_reused_and_overlapping_logical_tags_keep_distinct_physical_identity(self):
        self.simulate(r'''
command(16'hf123,1);issue();receipt(1,0);accept_status(16'hf123,0);
command(16'hc001,2);issue();receipt(2,7);accept_status(16'hc001,7);
command(16'hf123,3);issue();receipt(3,0);accept_status(16'hf123,0);
if(command_count!=3 || status_count!=3 || retired_count!=3)$fatal(1,"command/status cardinality");
''')

    def test_stale_unknown_duplicate_or_premature_status_never_translates(self):
        for text in ["command(16'hf123,1);receipt(1,0);",
                     "command(16'hf123,1);issue();receipt(2,0);",
                     "command(16'hf123,1);issue();receipt(16'hxxxx,0);",
                     "command(16'hf123,1);issue();receipt(1,0);receipt(1,0);"]:
            self.simulate(text+'quarantine();')
        self.simulate(r'''
command(16'hf123,1);issue();receipt(1,0);accept_status(16'hf123,0);
command(16'hf123,2);issue();receipt(1,0);quarantine();
if(m_status_valid || status_count!=1)$fatal(1,"old physical nonce mapped onto reused logical tag");
''')

    def test_late_fault_preserves_already_offered_command_and_status(self):
        self.simulate(r'''
command(16'hf123,1);parent_fault=1;quarantine();
if(!m_command_valid || m_command_tag!==1)$fatal(1,"late fault retracted physical command");
issue();receipt(1,7);repeat(20)@(negedge clk);
if(!m_status_valid || m_status_tag!==16'hf123 || m_status_error!==7)$fatal(1,"late error status lost");
m_status_ready=1;repeat(5)@(negedge clk);if(!busy || !fault)$fatal(1,"faulty lease released");
''')

    def test_nonce_exhaustion_finishes_last_command_without_wrap(self):
        self.simulate(r'''
command(1,1);issue();receipt(1,0);accept_status(1,0);
command(1,2);issue();receipt(2,0);accept_status(1,0);
command(1,3);issue();receipt(3,0);accept_status(1,0);
if(!exhausted || command_count!=3)$fatal(1,"physical nonce wrapped");
s_command_write=0;s_command_offset=0;s_command_length=8;s_command_key=8;s_command_tag=1;s_command_valid=1;
repeat(20)@(negedge clk);if(s_command_ready || m_command_valid || fault || !configuration_guard)$fatal(1,"exhausted nonce accepted new command");
''',width=2)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve prior evidence')
    inputs=[RTL,Path(__file__).resolve(),Path(helper.__file__).resolve()]
    before={str(n.relative_to(ROOT)):digest(n)for n in inputs};start=time.monotonic()
    r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Nonce))
    assert all(digest(ROOT/n)==h for n,h in before.items())
    result=dict(scope=__doc__,pass_test=r.wasSuccessful(),methods=r.testsRun,seconds=time.monotonic()-start,
        source_sha256=before,tests=Nonce.reports,four_state=True,backend_and_clients_modeled=True,
        actual_MR_data_fence_or_native_integration=False,
        artifact_sha256={str(n.relative_to(ROOT)):digest(n)for run in Nonce.runs for n in run.iterdir()if n.is_file()})
    with a.report.open('x')as f:f.write(json.dumps(result,indent=2)+'\n')
    raise SystemExit(not r.wasSuccessful())
