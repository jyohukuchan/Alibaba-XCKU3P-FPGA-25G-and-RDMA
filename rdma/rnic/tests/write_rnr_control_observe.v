// SPDX-License-Identifier: BSD-2-Clause-Views
// Read-only observation of the exact failed002 test: no force or port drive.
`timescale 1ns/1ps
module write_rnr_control_observe;
always @(posedge tb.clk)if(!tb.rst && tb.dut.state==tb.dut.REPORT && tb.s_valid && tb.s_ready)begin
 $display("RNR_OBSERVE actual_REPORT_handshake=1");
 #1;
 $display("RNR_OBSERVE state=%0d requests=%0d proofs=%0d retirements=%0d reports=%0d source_VALID=%0d guard=%0d fault=%0d",
  tb.dut.state,tb.requests,tb.wire_proofs,tb.retirements,tb.reports,tb.s_valid,tb.configuration_guard,tb.fault);
end
endmodule
