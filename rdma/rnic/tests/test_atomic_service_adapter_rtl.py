# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual typed service owner/retirement adapter; HLS/executor are models."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
import probe_atomic_responder as fixture

RTL=fixture.RTL/'rocev2_atomic_service_adapter.v'
TB=r'''
`timescale 1ns/1ps
module tb;
// DECLARATIONS
always #2 clk=~clk;
integer cycle=0;
always @(posedge clk)if(!rst)begin cycle=cycle+1;if(cycle>1000)$fatal(1,"bounded deadline");end
task offer;
 begin
  @(negedge clk);s_hls_request=0;s_hls_request[7:0]=8'h13;
  s_hls_request[63:40]=24'h020000;s_hls_request[95:72]=24'hefcdab;
  s_hls_request[343:320]=24'habcdef;s_hls_request[367:344]=24'hffffff;
  s_owner_qpn=2;s_owner_epoch=64'h8123456700000001;s_owner_valid=1;s_hls_request_valid=1;
 end
endtask
task accept;
 begin
  @(posedge clk);while(!s_hls_request_ready || !s_owner_ready)@(posedge clk);
  @(negedge clk);s_hls_request_valid=0;s_owner_valid=0;
 end
endtask
task response;
 begin
  @(negedge clk);s_execute_response_header=192'hfedcba98765432100123456789abcdef8123456789abcdef;
  s_execute_response_qpn=2;s_execute_response_epoch=64'h8123456700000001;
  s_execute_response_bytes=24;s_execute_response_advance=1;s_execute_response_drop=0;
  s_execute_response_valid=1;
 end
endtask
initial begin
 rst=1;repeat(4)@(negedge clk);rst=0;enable=1;
 // BODY
 $display("ATOMIC_ADAPTER_RESULT {\"pass_test\":true,\"cycles\":%0d}",cycle);$finish;
end
endmodule
'''


class AtomicServiceAdapterTests(unittest.TestCase):
    def simulate(self,body):
        declaration=fixture.instance(RTL,'dut','',{})
        tb=TB.replace('// DECLARATIONS',declaration).replace('// BODY',body)
        before=hashlib.sha256(RTL.read_bytes()).hexdigest()
        with tempfile.TemporaryDirectory(prefix='as02-atomic-adapter-')as directory:
            p=Path(directory);(p/'tb.v').write_text(tb)
            c=subprocess.run(['iverilog','-g2012','-s','tb','-o',str(p/'test.vvp'),str(p/'tb.v'),str(RTL)],
                capture_output=True,text=True,timeout=20)
            self.assertEqual(c.returncode,0,c.stdout+c.stderr)
            r=subprocess.run(['vvp',str(p/'test.vvp')],capture_output=True,text=True,timeout=10)
            self.assertEqual(r.returncode,0,r.stdout+r.stderr)
            rows=[json.loads(l.split(' ',1)[1])for l in r.stdout.splitlines()if l.startswith('ATOMIC_ADAPTER_RESULT ')]
            self.assertEqual(len(rows),1,r.stdout);self.assertTrue(rows[0]['pass_test'])
        self.assertEqual(hashlib.sha256(RTL.read_bytes()).hexdigest(),before)

    def test_full_HLS_word_true_owner_epoch_and_registered_reply_ownership(self):
        self.simulate(r'''
offer();repeat(7)begin @(negedge clk);
 if(!m_execute_valid || s_hls_request_ready || !configuration_guard ||
   m_execute_header!==s_hls_request[319:0] || m_execute_expected_psn!==24'habcdef ||
   m_execute_msn!==24'hffffff || m_execute_epoch!==s_owner_epoch || m_execute_bytes!==40)
  $fatal(1,"request context ownership");
end
m_execute_ready=1;accept();enable=0;
if(!busy || !configuration_guard || m_execute_valid)$fatal(1,"accepted owner lost");
response();@(posedge clk);while(!s_execute_response_ready)@(posedge clk);
@(negedge clk);s_execute_response_valid=0;
repeat(17)begin @(negedge clk);
 if(!m_hls_reply_valid || !busy || !configuration_guard || s_hls_request_ready ||
   m_hls_reply!=={1'b0,1'b1,6'd24,24'habcdef,24'd2,192'hfedcba98765432100123456789abcdef8123456789abcdef})
  $fatal(1,"typed completion truncated/forgot immutable request PSN/QPN");
end
m_hls_reply_ready=1;@(negedge clk);m_hls_reply_ready=0;
if(busy || fault || configuration_guard)$fatal(1,"success owner not retired");
''')

    def test_full_or_unknown_owner_mismatch_never_reaches_execution(self):
        for change in ['s_owner_qpn=3;','s_owner_qpn=24\'h800002;','s_owner_epoch=0;',
                       "s_owner_epoch[63:60]=4'hx;","s_hls_request[367:364]=4'hx;"]:
            with self.subTest(change=change):self.simulate('offer();'+change+r'''
m_execute_ready=1;repeat(6)@(negedge clk);
if(!fault || fault_code!==8'h81 || !busy || !configuration_guard || m_execute_valid ||
 s_hls_request_ready || s_owner_ready || m_hls_reply_valid)$fatal(1,"untrusted owner acquired authority");
''')

    def test_stale_or_unknown_executor_response_cannot_release_the_current_owner(self):
        for change in ['s_execute_response_qpn=3;','s_execute_response_epoch=64\'h8123456700000000;',
                       "s_execute_response_header[191:188]=4'hx;"]:
            with self.subTest(change=change):self.simulate('m_execute_ready=1;offer();accept();response();'+change+r'''
repeat(7)@(negedge clk);
if(!fault || fault_code!==8'h82 || !busy || !configuration_guard || s_execute_response_ready ||
 m_hls_reply_valid || s_hls_request_ready)$fatal(1,"stale executor fabricated completion");
''')

    def test_orphan_response_has_no_completion_or_configuration_release(self):
        self.simulate(r'''
response();repeat(7)@(negedge clk);
if(!fault || fault_code!==8'h82 || !busy || !configuration_guard || m_hls_reply_valid ||
 s_execute_response_ready)$fatal(1,"orphan reply acquired authority");
''')


if __name__=='__main__':unittest.main()
