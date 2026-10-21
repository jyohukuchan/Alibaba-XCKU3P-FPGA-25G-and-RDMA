// SPDX-License-Identifier: BSD-2-Clause-Views
// Read-only observer. No drives, forces, altered assertions or deadlines.
`timescale 1ns/1ps
module remote_write_observe;
integer sample=0;
always @(negedge tb.clk)begin
 if(sample<100)begin
  $display("MR_NOTICE_OBSERVE time%0t rst%0b state%0d cfgvalid%0b ready%0b response%0b response_ready%0b quiescent%0b guard_fault%0b rq_fault%0b queries%0d grants%0d guard_state%0d notice%0b/%0b head%0b/%0b held%0b badnotice%0b basic%0b match%0b",
   $time,tb.rst,tb.actual_mr.state,tb.cfg_valid,tb.cfg_ready,tb.cfg_response_valid,
   tb.cfg_response_ready,!tb.configuration_guard && !tb.q_active && tb.q_queue_guard==0,
   tb.fault,tb.q_fault,tb.queries,tb.grants,tb.dut.state,tb.m_notice_valid,tb.m_notice_ready,
   tb.s_rq_valid,tb.actual_rq.m_head_ready,tb.q_active,tb.actual_rq.bad_notice,
   tb.actual_rq.notice_basic,tb.actual_rq.notice_RQ_match);
 end
 sample=sample+1;
end
endmodule
