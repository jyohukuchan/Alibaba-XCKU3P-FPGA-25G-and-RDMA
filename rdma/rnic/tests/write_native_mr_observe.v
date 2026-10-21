// SPDX-License-Identifier: BSD-2-Clause-Views
// Read-only exact frozen MR001 management response observation.
`timescale 1ns/1ps
module write_native_mr_observe;
always @(tb.cfg_mr_response_valid)if(!tb.rst && tb.cfg_mr_response_valid)
 $display("NATIVE_MR_MANAGEMENT_OBSERVE op=%0d error=%h key=%h quiet=%b",
  tb.cfg_mr_command,tb.cfg_mr_response_error,tb.cfg_mr_response_key,tb.quiescent);
endmodule
