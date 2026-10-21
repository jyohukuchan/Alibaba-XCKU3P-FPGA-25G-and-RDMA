// SPDX-License-Identifier: BSD-2-Clause-Views
// Read-only frozen failing003 early-data shape diagnostic; no DUT drive.
`timescale 1ns/1ps
module remote_write_memory_observe;
always @(posedge tb.clk)if(!tb.rst && tb.e_s_hls_valid && !tb.packet_memory.input_shape)
 $display("WRITE_MEMORY_OBSERVE packet=%0d remaining=%0d wire_remaining=%0d KEEP=%h LAST=%b pad_zero=%b known=%b issued=%b raw_seen=%b fault=%b",
  tb.packet_index,tb.packet_memory.remaining,tb.packet_memory.wire_remaining,tb.e_s_hls_keep,tb.e_s_hls_last,
  tb.packet_memory.pad_zero,tb.packet_memory.bytes_known,tb.packet_memory.issued,tb.packet_memory.raw_seen,tb.e_fault);
endmodule
