# SPDX-License-Identifier: BSD-2-Clause-Views
"""Unchanged actual READ/29-case checks plus read-only metadata queue prints."""
import segmented_read_route_progress_native_fixture as parent

ROOT=parent.ROOT;once=parent.once


def __getattr__(name):
    return getattr(parent,name)


def bench():
    return once(parent.bench(),'module tb;',r'''
module tb;
always @(posedge clk)if(!rst && runtime_large_read && cycle>=16000 && cycle%1000==0)
 $display("READ_METADATA_QUEUE cycle%0d count=%0d accepted_bytes=%0d placement=%b input=%b/%b bad=%b output=%b/%b",
  cycle,dut.executor.read_cmd_count,dut.executor.read_cmd_offset,dut.executor.read_cmd_placement,
  dut.executor.s_hls_write_command_valid,dut.executor.s_hls_write_command_ready,dut.executor.read_cmd_bad,
  dut.executor.read_cmd_valid,dut.executor.r_s_hls_command_ready);
''')
