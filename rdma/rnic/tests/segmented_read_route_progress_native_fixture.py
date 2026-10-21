# SPDX-License-Identifier: BSD-2-Clause-Views
"""Read-only progress snapshots on the exact actual READ/29-case fixture.

All stimulus, expected values and deadlines are inherited unchanged. Observe
the real child/unpad/status/nonce/backend graph, never supply completion or
change routing/authority to make a stalled operation appear complete.
"""
import segmented_read_route_native_fixture as parent

ROOT=parent.ROOT;once=parent.once


def __getattr__(name):
    return getattr(parent,name)


def bench():
    return once(parent.bench(),'module tb;',r'''
module tb;
always @(posedge clk)if(!rst && runtime_large_read && cycle>=16000 && cycle%1000==0)begin
 $display("READ_GRAPH cycle%0d ctl=%0d off=%0d fragments=%0d input_done=%b child_busy=%b pad_busy=%b child_event=%b/%b raw=%b/%b/%b data=%b/%b/%b status=%b/%b/%h logical=%0d/%0d/%0d RX=%0d bytes=%0d",
  cycle,dut.executor.read_fragments.state,dut.executor.read_fragments.next_offset,dut.executor.read_fragments.fragment_count,
  dut.executor.read_fragments.hls_input_done,dut.executor.read_fragments.child_busy,dut.executor.read_fragments.pad_busy,
  dut.executor.read_fragments.child_event_valid,dut.executor.read_fragments.child_event_ready,
  dut.executor.read_fragments.s_hls_command_valid,dut.executor.read_fragments.s_hls_command_ready,dut.executor.read_fragments.raw_match,
  dut.executor.read_fragments.s_axis_hls_tvalid,dut.executor.read_fragments.s_axis_hls_tready,dut.executor.read_fragments.s_axis_hls_tlast,
  dut.ex_s_memory_status_valid,dut.ex_s_memory_status_ready,dut.ex_s_memory_status_tag,lr_commands,lr_statuses,lr_events,lr_rx,lr_fenced_bytes);
 $display("READ_BACKEND cycle%0d child_active=%b issued=%b done=%b remaining=%0d beat=%b nonce=%b/%b/%b status=%b/%b backend=%0d pages=%0d physical_read=%b/%b",
  cycle,dut.executor.read_fragments.child.active,dut.executor.read_fragments.child.issued,dut.executor.read_fragments.child.data_done,
  dut.executor.read_fragments.child.remaining,dut.executor.read_fragments.child.beat_valid,
  dut.native.network.datapath.responder.endpoint.memory_nonce.active,dut.native.network.datapath.responder.endpoint.memory_nonce.issued,
  dut.native.network.datapath.responder.endpoint.memory_nonce.receipt_seen,
  dut.native.network.datapath.responder.endpoint.memory_nonce.m_status_valid,dut.native.network.datapath.responder.endpoint.memory_nonce.m_status_ready,
  dut.native.network.datapath.responder.endpoint.memory.backend.state,dut.native.network.datapath.responder.endpoint.memory.pages.state,
  m_dma_read_valid,m_dma_read_ready);
end
''')
