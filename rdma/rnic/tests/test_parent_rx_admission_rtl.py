# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual fatal-admission/AXIS ownership RTL, source/sink ready-valid models."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[3]
RTL=ROOT/'rdma/rnic/rtl/rocev2_parent_rx_admission.v'
TB=r'''
`timescale 1ns/1ps
module tb;
reg clk=0,rst=0,parent_fault=0,s_valid=0,s_last=0,m_ready=0;
wire s_ready,m_valid;
rocev2_parent_rx_admission dut(.*);
always #2 clk=~clk;
integer scenario,dummy;
task step;begin @(negedge clk);end endtask
task blocked;begin #0.1;if(m_valid || s_ready)$fatal(1,"new frame admitted after fault");end endtask
task offered;begin #0.1;if(!m_valid || s_ready!==m_ready)$fatal(1,"offered frame withdrawn");end endtask
initial begin
 dummy=$value$plusargs("CASE=%d",scenario);#1;rst=1;repeat(4)step;rst=0;
 case(scenario)
  0:begin s_valid=1;s_last=0;m_ready=1;offered;step;s_valid=0;step;step;
    s_valid=1;s_last=1;m_ready=0;repeat(4)begin offered;step;end m_ready=1;offered;step;
    s_valid=0;parent_fault=1;blocked;end
  1:begin s_valid=1;s_last=0;m_ready=0;offered;step;parent_fault=1;
    repeat(4)begin offered;step;end m_ready=1;offered;step;s_last=1;offered;step;
    s_last=0;blocked;end
  2:begin s_valid=1;s_last=0;m_ready=1;offered;step;parent_fault=1;s_valid=0;
    repeat(4)step;s_valid=1;s_last=1;offered;step;s_last=0;blocked;end
  3:begin parent_fault=1;s_valid=1;s_last=1;m_ready=1;repeat(6)begin blocked;step;end end
  4:begin s_valid=1;s_last=1;m_ready=0;offered;step;parent_fault=1;
    repeat(4)begin offered;step;end m_ready=1;offered;step;blocked;end
  5:begin parent_fault=1;s_valid=1;s_last=0;m_ready=0;blocked;step;parent_fault=0;
    offered;step;parent_fault=1;m_ready=1;offered;step;s_last=1;offered;step;blocked;end
  default:$fatal;
 endcase
 $display("RX_ADMISSION_RESULT {\"pass_test\":true,\"scenario\":%0d}",scenario);$finish;
end
endmodule
'''


class ParentRXAdmissionTests(unittest.TestCase):
    reports={}
    @classmethod
    def setUpClass(cls):
        cls.before={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [RTL,Path(__file__)]}
        cls.directory=tempfile.TemporaryDirectory(prefix='as02-rx-parent-');cls.path=Path(cls.directory.name)
        (cls.path/'tb.v').write_text(TB)
        r=subprocess.run(['iverilog','-g2012','-s','tb','-o',str(cls.path/'test.vvp'),str(cls.path/'tb.v'),str(RTL)],capture_output=True,text=True,timeout=30)
        if r.returncode:raise RuntimeError(r.stdout+r.stderr)
    def run_case(self,n):
        r=subprocess.run(['vvp',str(self.path/'test.vvp'),f'+CASE={n}'],capture_output=True,text=True,timeout=5)
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        rows=[json.loads(l[20:]) for l in r.stdout.splitlines() if l.startswith('RX_ADMISSION_RESULT ')]
        self.assertEqual(len(rows),1,r.stdout);self.reports[self._testMethodName]=rows[0]
    def test_normal_multibeat_gaps_and_backpressure(self):self.run_case(0)
    def test_first_offered_beat_retained_even_before_acceptance(self):self.run_case(1)
    def test_accepted_frame_drains_across_fault_and_gap(self):self.run_case(2)
    def test_fault_before_offer_blocks_entire_new_frame(self):self.run_case(3)
    def test_stalled_single_last_beat_not_withdrawn(self):self.run_case(4)
    def test_later_admission_owns_frame_through_next_fault(self):self.run_case(5)
    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()
        after={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [RTL,Path(__file__)]}
        if cls.before!=after:raise ValueError('RX admission sources changed')
        if name:=os.environ.get('AS02_RNIC_PARENT_RX_REPORT'):
            target=Path(name);target=target if target.is_absolute() else ROOT/target
            with target.open('x') as out:out.write(json.dumps(dict(scope=__doc__,pass_test=len(cls.reports)==6,
                hardware_verified=False,tests=cls.reports,source_sha256=after),indent=2)+'\n')
