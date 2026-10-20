# SPDX-License-Identifier: BSD-2-Clause-Views
"""Four-state owned adapter; HLS/executor endpoints are explicit models."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
import probe_atomic_owned as fixture

RTL=fixture.RTL
TB=r'''
`timescale 1ns/1ps
module tb;
// DECLARATIONS
always #2 clk=~clk;
integer cycles=0;reg [143:0] owner;
always @(posedge clk)if(!rst)begin cycles=cycles+1;if(cycles>700)$fatal(1,"bounded deadline");end
task offer;
 begin
  @(negedge clk);owner={32'hfedc1234,24'habcdef,64'h9123456780000001,24'd2};
  s_hls_request=0;s_hls_request[511:368]=owner;s_hls_request[7:0]=8'h13;
  s_hls_request[63:40]=24'h020000;s_hls_request[95:72]=24'hefcdab;
  s_hls_request[343:320]=24'habcdef;s_hls_request[367:344]=24'hffffff;s_hls_request_valid=1;
 end
endtask
task accept;
 begin
  @(posedge clk);while(!s_hls_request_ready)@(posedge clk);
  @(negedge clk);s_hls_request_valid=0;s_hls_request=0;
 end
endtask
task response;
 begin
  @(negedge clk);s_execute_response_qpn=2;s_execute_response_epoch=64'h9123456780000001;
  s_execute_response_header=192'hfedcba98765432100123456789abcdef8123456789abcdef;
  s_execute_response_bytes=24;s_execute_response_advance=1;s_execute_response_valid=1;
 end
endtask
initial begin
 rst=1;repeat(4)@(negedge clk);rst=0;enable=1;
 // BODY
 $display("OWNED_ADAPTER_PASS");$finish;
end
endmodule
'''


class AtomicOwnedServiceAdapterTests(unittest.TestCase):
    def simulate(self,body):
        text=TB.replace('// DECLARATIONS',fixture.base.rtl.instance(RTL,'dut','',{})).replace('// BODY',body)
        before=fixture.base.digest(RTL)
        with tempfile.TemporaryDirectory(prefix='as02-atomic-owned-unit-')as temporary:
            p=Path(temporary);(p/'tb.v').write_text(text)
            c=subprocess.run(['iverilog','-g2012','-s','tb','-o',str(p/'tb.vvp'),str(p/'tb.v'),str(RTL)],capture_output=True,text=True,timeout=20)
            self.assertEqual(c.returncode,0,c.stdout+c.stderr)
            r=subprocess.run(['vvp',str(p/'tb.vvp')],capture_output=True,text=True,timeout=10)
            self.assertEqual(r.returncode,0,r.stdout+r.stderr);self.assertIn('OWNED_ADAPTER_PASS',r.stdout)
        self.assertEqual(before,fixture.base.digest(RTL))

    def test_registered_execute_and_reply_keep_nonce_under_disable_and_backpressure(self):
        self.simulate(r'''
offer();accept();enable=0;
repeat(13)begin @(negedge clk);
 if(!m_execute_valid || !busy || !configuration_guard || m_execute_epoch!==owner[87:24] ||
   m_execute_header[95:72]!==24'hefcdab || m_execute_expected_psn!==24'habcdef || m_execute_msn!==24'hffffff)
  $fatal(1,"registered request replaced/retracted");
end
m_execute_ready=1;@(negedge clk);m_execute_ready=0;response();
@(posedge clk);while(!s_execute_response_ready)@(posedge clk);
@(negedge clk);s_execute_response_valid=0;
repeat(17)begin @(negedge clk);
 if(!m_hls_reply_valid || !busy || !configuration_guard || m_hls_reply[391:248]!==owner ||
   m_hls_reply[247:192]!=={1'b0,1'b1,6'd24,24'habcdef,24'd2})$fatal(1,"immutable completion owner lost");
end
m_hls_reply_ready=1;@(negedge clk);m_hls_reply_ready=0;
if(busy || configuration_guard || fault)$fatal(1,"owner handoff failed");
''')

    def test_wrong_or_unknown_owner_never_executes(self):
        changes=["s_hls_request[391:368]=3;","s_hls_request[391:368]=24'h800002;",
            "s_hls_request[455:392]=0;","s_hls_request[479:456]=24'habcdee;",
            "s_hls_request[511:480]=0;","s_hls_request[511:508]=4'hx;","s_hls_request[367:364]=4'hx;"]
        for change in changes:
            with self.subTest(change=change):self.simulate('offer();'+change+r'''
m_execute_ready=1;repeat(7)@(negedge clk);
if(!fault || fault_code!==8'h83 || !configuration_guard || s_hls_request_ready || m_execute_valid || m_hls_reply_valid)
 $fatal(1,"untrusted owned word executed");
''')

    def test_stale_executor_completion_retains_lease(self):
        for change in ["s_execute_response_qpn=3;","s_execute_response_epoch=64'h9123456780000000;",
                       "s_execute_response_header[191:188]=4'hx;"]:
            with self.subTest(change=change):self.simulate('offer();accept();m_execute_ready=1;@(negedge clk);m_execute_ready=0;response();'+change+r'''
repeat(7)@(negedge clk);
if(!fault || fault_code!==8'h84 || !configuration_guard || s_execute_response_ready || m_hls_reply_valid)
 $fatal(1,"stale completion released owner");
''')


if __name__=='__main__':unittest.main()
