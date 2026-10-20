# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual message CQ publisher, immutable capacity and actual byte-count ABI.

Upstream ticket/commit/retire producers are EXPLICIT MODELS. These snapshots
exercise real CQC RTL and kernel consumers, not a native receive completion,
MAC/HLS drain certificate, physical DMA, ib_device registration or hardware.
"""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

import test_cq_path_rtl as original
from test_wqe_hls_sq_rtl import context

ROOT = original.ROOT
SOURCES = [original.RTL] + [original.AXI / (n + '.v') for n in
    ['axil_reg_if', 'axil_reg_if_rd', 'axil_reg_if_wr']]


def bench():
    # Reuse only the literal production register wiring and bounded AXI tasks.
    # No old lifetime/HLS proof generators are included in this fixture.
    host = original.HOST[:original.HOST.index('task cq_snapshot;')]
    host = host.replace('rocev2_cq_mmio publisher(',
        'rocev2_cq_mmio #(.MESSAGE_ENABLE(1)) publisher(')
    host = host.replace('.s_ticket_received_bytes(32\'d0)',
        '.s_ticket_received_bytes(actual_bytes)')
    ctx = lambda seq, opcode=4: context(id=0xf123456789abc000 + seq,
        sequence=seq, qpn=7, pd=17, tag=seq, lkey=8, opcode=opcode,
        flags=1, length=128 if opcode == 4 else 65, remote=0, rkey=0)
    body = ''.join(f'publish({ctx(seq)},65,{seq},1);\n' for seq in (1, 2))
    body += f'publish({ctx(3, 3)},0,3,0);\n'
    return r'''
`timescale 1ns/1ps
module tb;
reg clk=0,rst=1,parent_fault=0;
reg [587:0] m_cq_context=0;
reg m_cq_valid=0;wire m_cq_ready;
reg [31:0] actual_bytes=0;
wire [587:0] s_cq_commit_context;wire [7:0] s_cq_commit_error;
wire s_cq_commit_valid;reg s_cq_commit_ready=0;
integer cycle=0;
always #2 clk=~clk;
always @(posedge clk)if(!rst)begin
 cycle=cycle+1;if(cycle>20000)$fatal(1,"message CQ bounded deadline");
 if(pub_fault)$fatal(1,"message CQ fault %h",pub_fault_code);
end
''' + host + r'''
reg [587:0] expected;
task publish;
 input [587:0] ctx;input [31:0] bytes;input integer seq;input integer receive;
 begin
  @(negedge clk);m_cq_context=ctx;expected=ctx;actual_bytes=bytes;m_cq_valid=1;
  @(posedge clk);if(!m_cq_ready || pub_guard!==8'h80)$fatal(1,"message ticket owner acceptance");
  @(negedge clk);m_cq_valid=0;m_cq_context=0;actual_bytes=0;
  repeat(17)begin
   @(negedge clk);
   if(!s_cq_commit_valid || s_cq_commit_context!==ctx || s_cq_commit_error ||
      pub_published!=seq-1 || !pub_busy || pub_guard!==8'h80)
    $fatal(1,"message commit identity/capacity under stall");
  end
  cq_read(12'h00c,host_value);if(host_value!==2)$fatal(1,"message visible before commit");
  cq_read(12'h038,host_value);if(host_value)$fatal(1,"early received bytes");
  s_cq_commit_ready=1;@(posedge clk);@(negedge clk);s_cq_commit_ready=0;
  repeat(17)begin
   @(negedge clk);
   if(!pub_retire_valid || pub_retire_context!==ctx || pub_published!=seq-1)
    $fatal(1,"message retire identity under stall");
  end
  cq_read(12'h01c,host_value);if(host_value)$fatal(1,"message proof before retire");
  retire_allowed=1;@(posedge clk);@(negedge clk);retire_allowed=0;
  cq_read(12'h00c,host_value);if(host_value!==3)$fatal(1,"message CQ not visible");
  if(pub_published!=seq || pub_guard!==8'h80)$fatal(1,"message guard handoff");
  if(receive)host_fd=$fopen(seq==1 ? "event1.hex" : "event2.hex","w");
  cq_read(12'h018,host_value);if(host_value!=seq)$fatal(1,"message sequence");
  if(receive)$fdisplay(host_fd,"%08h",host_value);
  cq_read(12'h01c,host_value);if(host_value!=15)$fatal(1,"message proofs");
  if(receive)$fdisplay(host_fd,"%08h",host_value);
  cq_read(12'h028,host_value);if(host_value)$fatal(1,"message success status");
  if(receive)$fdisplay(host_fd,"%08h",host_value);
  cq_read(12'h020,host_value);if(host_value!=1)$fatal(1,"message cookie");
  if(receive)$fdisplay(host_fd,"%08h",host_value);
  cq_read(12'h024,host_value);if(host_value)$fatal(1,"message cookie high");
  if(receive)$fdisplay(host_fd,"%08h",host_value);
  for(host_i=0;host_i<19;host_i=host_i+1)begin
   cq_read(12'h040+host_i*4,host_value);
   if(host_value!==(({20'd0,expected}>>(host_i*32))&32'hffffffff))
    $fatal(1,"message changed original posted context/capacity");
   if(receive)$fdisplay(host_fd,"%08h",host_value);
  end
  cq_read(12'h038,host_value);if(host_value!=bytes)$fatal(1,"actual received byte count");
  if(receive)begin $fdisplay(host_fd,"%08h",host_value);$fclose(host_fd);end
  repeat(17)@(negedge clk);
  if(seq>1)begin
   cq_ack(seq-1);cq_read(12'h00c,host_value);
   if(host_value!==3 || pub_acked!=seq-1)$fatal(1,"old ACK consumed next message");
  end
  cq_ack(seq);cq_read(12'h014,host_value);
  if(host_value!=seq || pub_busy || pub_guard)$fatal(1,"message CQ ACK release");
 end
endtask
initial begin
 repeat(5)@(posedge clk);@(negedge clk);rst=0;
 cq_read(12'h008,host_value);if(host_value!=3)$fatal(1,"message feature ABI");
''' + body + r'''
 $display("MESSAGE_CQ_RESULT {\"pass_test\":true,\"RECV_events\":2,\"SEND_events\":1,\"capacity\":128,\"received_bytes\":65}");
 $finish;
end
endmodule
'''


def simulate(directory):
    p = Path(directory)
    p.mkdir(parents=True, exist_ok=True)
    (p / 'tb.v').write_text(bench())
    c = subprocess.run(['iverilog', '-g2012', '-s', 'tb', '-o', str(p / 'test.vvp'),
        str(p / 'tb.v'), *map(str, SOURCES)], capture_output=True, text=True, timeout=30)
    if c.returncode:
        raise RuntimeError(c.stdout + c.stderr)
    r = subprocess.run(['vvp', str(p / 'test.vvp')], cwd=p,
        capture_output=True, text=True, timeout=10)
    (p / 'simulation.log').write_text(r.stdout + r.stderr)
    if r.returncode:
        raise RuntimeError(r.stdout + r.stderr)
    rows = [json.loads(l.split(' ', 1)[1]) for l in r.stdout.splitlines()
        if l.startswith('MESSAGE_CQ_RESULT ')]
    if len(rows) != 1 or not rows[0]['pass_test']:
        raise ValueError('missing actual message publisher result')
    return rows[0]


class MessageCQTests(unittest.TestCase):
    def test_message_CQ_immutable_capacity_actual_bytes_and_commit_retire_backpressure(self):
        with tempfile.TemporaryDirectory(prefix='as02-message-cq-') as directory:
            self.assertTrue(simulate(directory)['pass_test'])


if __name__ == '__main__':
    unittest.main()
