// SPDX-License-Identifier: BSD-2-Clause-Views
// Read-only observer of the exact frozen failing paired-retirement fixture.
`timescale 1ns/1ps
module receive_write_ack_observe;
always @(posedge tb.clk)if(!tb.rst && (tb.s_write_retire_valid || tb.s_retire_valid))
 $display("ACK_RETIRE_OBSERVE cycle=%0d held=%b wr_sent=%b rq_sent=%b wr_VALID=%b wr_READY=%b rq_VALID=%b rq_READY=%b fault=%b",
  tb.cycle,tb.dut.held,tb.dut.write_proof_sent,tb.dut.proof_sent,
  tb.s_write_retire_valid,tb.s_write_retire_ready,tb.s_retire_valid,tb.s_retire_ready,tb.fault);
endmodule
