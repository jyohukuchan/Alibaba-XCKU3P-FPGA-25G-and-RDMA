// SPDX-License-Identifier: BSD-2-Clause-Views
// Test-only simulator calibration. NEVER forces any DUT signal or memory.
`timescale 1ns/1ps
module as02_four_state_calibration;
reg uninitialized_value;
tri undriven_value;
initial begin
 #1;
 if(uninitialized_value!==1'bx || undriven_value!==1'bz)
  $fatal(1,"four-state X/Z calibration failed");
 $display("XSIM_FOUR_STATE_CALIBRATED");
end
endmodule
