# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual parent-proof RTL with explicit engine/status/RAM/TLP input models."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[3]
RTL=ROOT/'rdma/rnic/rtl/rocev2_pcie_parent_guard.v'
TB=r'''
`timescale 1ns/1ps
module tb;
localparam SEG_COUNT=2,COUNT_WIDTH=2;
// DECLARATIONS
rocev2_pcie_parent_guard #(.SEG_COUNT(2),.COUNT_WIDTH(2)) dut(.*);
always #2 clk=~clk;
integer scenario,dummy,i;
task edge_wait;begin @(negedge clk);end endtask
task rd_issue;begin rd_desc_valid=1;rd_desc_ready=1;#0.1;if(drained)$fatal(1,"offer proof");edge_wait;rd_desc_valid=0;end endtask
task rd_finish;begin rd_status_valid=1;edge_wait;rd_status_valid=0;end endtask
task check_held;begin #0.1;if(drained)$fatal(1,"early parent proof case%0d",scenario);end endtask
task check_idle;begin #0.1;if(!drained || fault)$fatal(1,"missing idle proof case%0d fault%0d",scenario,fault_code);end endtask
initial begin
 dummy=$value$plusargs("CASE=%d",scenario);#1;rst=1;check_held;repeat(4)edge_wait;rst=0;check_idle;
 case(scenario)
  0:begin rd_issue;rd_busy=1;repeat(4)begin check_held;edge_wait;end rd_finish;check_held;rd_busy=0;check_idle;end
  1:begin wr_desc_valid=1;wr_desc_ready=1;check_held;edge_wait;wr_desc_valid=0;wr_busy=1;
    repeat(4)begin check_held;edge_wait;end wr_status_valid=1;edge_wait;wr_status_valid=0;check_held;wr_busy=0;check_idle;end
  2:begin ram_wr_cmd_valid=3;ram_wr_cmd_ready=3;check_held;edge_wait;ram_wr_cmd_valid=0;
    repeat(4)begin check_held;edge_wait;end ram_wr_done=1;edge_wait;ram_wr_done=0;check_held;
    ram_wr_done=2;edge_wait;ram_wr_done=0;check_idle;end
  3:begin ram_rd_cmd_valid=3;ram_rd_cmd_ready=3;edge_wait;ram_rd_cmd_valid=0;
    ram_rd_resp_valid=3;repeat(4)begin check_held;edge_wait;end ram_rd_resp_ready=1;edge_wait;
    ram_rd_resp_valid=2;check_held;ram_rd_resp_ready=2;edge_wait;ram_rd_resp_valid=0;check_idle;end
  4:begin tlp_activity=1;repeat(4)begin check_held;edge_wait;end tlp_activity=0;check_idle;end
  5:begin error_event=1;check_held;edge_wait;error_event=0;repeat(4)edge_wait;
    if(!fault || fault_code!=1)$fatal(1,"missing sticky engine error");check_held;end
  6:begin rd_status_valid=1;check_held;edge_wait;rd_status_valid=0;
    if(!fault || fault_code!=2)$fatal(1,"unowned descriptor completion");check_held;end
  7:begin for(i=0;i<3;i=i+1)rd_issue;rd_desc_valid=1;check_held;edge_wait;rd_desc_valid=0;
    if(!fault || fault_code!=2 || dut.rd_pending!=3)$fatal(1,"descriptor overflow/wrap");check_held;end
  8:begin ram_wr_done=1;check_held;edge_wait;ram_wr_done=0;
    if(!fault || fault_code!=3)$fatal(1,"RAM done underflow");check_held;end
  9:begin ram_rd_resp_valid=1;ram_rd_resp_ready=1;check_held;edge_wait;ram_rd_resp_valid=0;
    if(!fault || fault_code!=3)$fatal(1,"RAM response underflow");check_held;end
  10:begin ram_wr_cmd_valid=1;ram_wr_cmd_ready=1;repeat(3)edge_wait;check_held;edge_wait;ram_wr_cmd_valid=0;
    if(!fault || fault_code!=3 || dut.ram_wr_pending[0]!=3)$fatal(1,"RAM overflow/wrap");check_held;end
  11:begin rd_issue;rd_status_error=10;rd_status_valid=1;check_held;edge_wait;rd_status_valid=0;
    if(!fault || fault_code!=1)$fatal(1,"descriptor error release");check_held;end
  default:$fatal;
 endcase
 $display("PARENT_RESULT {\"pass_test\":true,\"scenario\":%0d,\"fault\":%0d,\"fault_code\":%0d}",scenario,fault,fault_code);$finish;
end
endmodule
'''


class PCIeParentGuardTests(unittest.TestCase):
    reports={}
    @classmethod
    def setUpClass(cls):
        cls.before={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [RTL,Path(__file__)]}
        decl=[]
        for direction,width,name in re.findall(r'^\s*(input|output)\s+(?:wire|reg)\s+(\[[^\]]+\])?\s*(\w+)(?:=0)?[,\n]',RTL.read_text(),re.M):
            decl.append(('reg ' if direction=='input' else 'wire ')+(width or '')+' '+name+('=0;' if direction=='input' else ';'))
        cls.directory=tempfile.TemporaryDirectory(prefix='as02-parent-guard-');cls.path=Path(cls.directory.name)
        (cls.path/'tb.v').write_text(TB.replace('// DECLARATIONS','\n'.join(decl)))
        r=subprocess.run(['iverilog','-g2012','-s','tb','-o',str(cls.path/'test.vvp'),str(cls.path/'tb.v'),str(RTL)],capture_output=True,text=True,timeout=30)
        if r.returncode:raise RuntimeError(r.stdout+r.stderr)
    def run_case(self,n):
        r=subprocess.run(['vvp',str(self.path/'test.vvp'),f'+CASE={n}'],capture_output=True,text=True,timeout=5)
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        rows=[json.loads(l[14:]) for l in r.stdout.splitlines() if l.startswith('PARENT_RESULT ')]
        self.assertEqual(len(rows),1,r.stdout);self.reports[self._testMethodName]=rows[0]
    def test_read_status_and_actual_busy_both_required(self):self.run_case(0)
    def test_write_status_and_actual_busy_both_required(self):self.run_case(1)
    def test_each_segment_write_done_required(self):self.run_case(2)
    def test_each_segment_response_and_stalls_required(self):self.run_case(3)
    def test_current_TLP_offer_blocks_proof(self):self.run_case(4)
    def test_current_and_sticky_engine_error_blocks_proof(self):self.run_case(5)
    def test_unowned_status_faults_before_release(self):self.run_case(6)
    def test_descriptor_counter_never_wraps(self):self.run_case(7)
    def test_unsolicited_RAM_write_done_faults(self):self.run_case(8)
    def test_unsolicited_RAM_read_response_faults(self):self.run_case(9)
    def test_RAM_pending_counter_never_wraps(self):self.run_case(10)
    def test_real_error_completion_never_release_proof(self):self.run_case(11)
    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()
        after={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [RTL,Path(__file__)]}
        if cls.before!=after:raise ValueError('parent guard sources changed')
        if name:=os.environ.get('AS02_RNIC_PARENT_GUARD_REPORT'):
            target=Path(name);target=target if target.is_absolute() else ROOT/target
            with target.open('x') as out:out.write(json.dumps(dict(scope=__doc__,pass_test=len(cls.reports)==12,
                hardware_verified=False,actual_PCIe_engine_exercised=False,tests=cls.reports,source_sha256=after),indent=2)+'\n')
