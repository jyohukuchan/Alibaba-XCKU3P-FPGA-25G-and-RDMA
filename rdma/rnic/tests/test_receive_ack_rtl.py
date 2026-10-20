# SPDX-License-Identifier: BSD-2-Clause-Views
"""Real receive ACK owner/tag/EOF/receipt/tail RTL, modeled owner/core/MAC pins.

Whole generated-HLS/native placement/CQ evidence is a separate required test.
No injected proof in this unit is wired into the production native hierarchy.
"""
import json
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

import native_receive_fixture as native
from test_receive_queue_rtl import context

ROOT = native.qp.ROOT
RTL = ROOT / 'rdma/rnic/rtl/rocev2_receive_ack_tx.v'


def bench():
    header = RTL.read_text().split(')(\n', 1)[1].split('\n);', 1)[0]
    ports = re.findall(r'\b(input|output)\s+(?:wire|reg)\s+(\[[^]]+\]\s+)?(\w+)', header)
    declarations = '\n'.join(('reg ' if d == 'input' else 'wire ') + (w or '') + n +
        ('=0;' if d == 'input' else ';') for d, w, n in ports)
    body = ''
    for seq in (1, 2):
        body += f'operation({context(sequence=seq)},24\'h{0x987653+seq:06x},24\'d{seq},16\'h{0x6000+seq:04x});\n'
    return r'''
`timescale 1ns/1ps
module tb;
localparam IMMEDIATE_ENABLE=0;
''' + declarations + r'''
rocev2_receive_ack_tx #(.TAG_SEQUENCE_WIDTH(2)) dut(.*);
always #2 clk=~clk;
reg [127:0] words[0:7];integer cycle=0,deadline,i,which=0;
reg [695:0] held_done;reg [160:0] held_frame;
always @(posedge clk)if(!rst)begin
 cycle=cycle+1;if(cycle>10000)$fatal(1,"ACK bounded deadline");
 if(fault)$fatal(1,"ACK owner fault %h",fault_code);
end
task operation;
 input [587:0] owner;input [23:0] psn;input [23:0] msn;input [15:0] tag;
 begin
  if(which==0)$readmemh("ack1.hex",words);else $readmemh("ack2.hex",words);
  @(negedge clk);s_owner_context=owner;s_owner_valid=1;
  @(posedge clk);if(!s_owner_ready)$fatal(1,"ACK owner admission");
  @(negedge clk);s_owner_valid=0;s_core_valid=0;
  for(i=0;i<4;i=i+1)begin
   s_axis_tdata=words[i];s_axis_tkeep=i==3 ? 16'h3fff:16'hffff;s_axis_tlast=i==3;
   s_axis_tuser={16'h4000,1'b0};s_axis_tvalid=1;
   @(posedge clk);if(!s_axis_tready)$fatal(1,"ACK capture");@(negedge clk);s_axis_tvalid=0;
  end
  repeat(17)begin @(negedge clk);if(m_axis_tvalid || m_done_valid || !busy)$fatal(1,"no core receipt yet");end
  s_core_data={8'd0,msn,4'd0,psn,32'd65,owner};s_core_valid=1;
  deadline=cycle+50;while(!m_axis_tvalid)begin if(cycle>deadline)$fatal(1,"ACK core/wire bind");@(negedge clk);end
  held_frame={m_axis_tdata,m_axis_tkeep,m_axis_tlast,m_axis_tuser};
  repeat(17)begin @(negedge clk);if(!m_axis_tvalid ||
   {m_axis_tdata,m_axis_tkeep,m_axis_tlast,m_axis_tuser}!==held_frame)$fatal(1,"ACK TX backpressure");end
  for(i=0;i<4;i=i+1)begin
   m_axis_tready=1;
   @(posedge clk);
   if(!m_axis_tvalid || m_axis_tdata!==words[i] || m_axis_tuser!=={tag,1'b0} ||
      m_axis_tkeep!==(i==3 ? 16'h3fff:16'hffff) || m_axis_tlast!==(i==3))$fatal(1,"ACK frame/tag changed");
   @(negedge clk);m_axis_tready=0;
  end
  // EOF and any fixed quiet delay cannot substitute for the real receipt.
  repeat(1100)begin @(negedge clk);if(m_done_valid || !busy)$fatal(1,"ACK completed without receipt");end
  s_cpl_tag=tag;s_cpl_ts=96'h123456789abcdef;s_cpl_valid=1;m_cpl_ready=0;
  repeat(17)begin @(negedge clk);if(!m_cpl_valid || m_cpl_tag!==16'h4000 ||
   m_cpl_ts!==s_cpl_ts || s_cpl_ready || m_done_valid)$fatal(1,"ACK CPL translation/stall");end
  m_cpl_ready=1;@(posedge clk);if(!s_cpl_ready)$fatal(1,"real CPL acceptance");
  @(negedge clk);s_cpl_valid=0;
  deadline=cycle+1100;
  while(!m_done_valid)begin if(cycle>deadline)$fatal(1,"ACK real receipt/tail missing");@(negedge clk);end
  if(m_done_data!=={tag,s_core_data})$fatal(1,"ACK proof full identity");
  held_done=m_done_data;
  repeat(17)begin @(negedge clk);if(!m_done_valid || m_done_data!==held_done || !busy)$fatal(1,"ACK proof held");end
  m_done_ready=1;@(posedge clk);@(negedge clk);m_done_ready=0;
  if(!busy || m_done_valid)$fatal(1,"proof acceptance freed owner before CQ");
  s_retire_context=owner;s_retire_valid=1;
  @(posedge clk);if(!s_retire_ready)$fatal(1,"ACK exact CQ retirement");
  @(negedge clk);s_retire_valid=0;s_core_valid=0;which=which+1;
  if(busy || queue_guard || frame_count!=which || receipt_count!=which)$fatal(1,"ACK retirement counters");
 end
endtask
initial begin
 rst=1;repeat(5)@(negedge clk);rst=0;prior_response_drained=1;
 local_mac=48'h8af3fbb97531;peer_mac=48'hb8830367c5d0;
 local_ip=32'hc6120b02;peer_ip=32'hc6120b01;peer_qpn=196;
''' + body + r'''
 $display("RECEIVE_ACK_RESULT {\"pass_test\":true,\"frames\":2,\"receipts\":2,\"tags_nonreused\":true}");
 $finish;
end
endmodule
'''


class ReceiveACKTests(unittest.TestCase):
    def test_same_core_owner_ACK_frame_fresh_tags_real_receipt_tail_and_CQ_retirement(self):
        _, _, _, ack = native.case(True, True)
        with tempfile.TemporaryDirectory(prefix='as02-receive-ack-') as directory:
            p = Path(directory)
            (p / 'tb.v').write_text(bench())
            for seq in (1, 2):
                packet = bytearray(ack)
                packet[37:40] = (0x987653 + seq).to_bytes(3, 'big')
                packet[41:44] = seq.to_bytes(3, 'big')
                packet = native.qp.main.response.repair(packet)
                frame = bytes.fromhex('b8830367c5d08af3fbb975310800') + packet
                (p / f'ack{seq}.hex').write_text(''.join(
                    f'{int.from_bytes(frame[n:n+16].ljust(16, bytes(1)), "little"):032x}\n'
                    for n in range(0, len(frame), 16)))
            c = subprocess.run(['iverilog', '-g2012', '-s', 'tb', '-o', str(p / 'test'),
                str(p / 'tb.v'), str(RTL)], capture_output=True, text=True, timeout=10)
            self.assertEqual(c.returncode, 0, c.stdout + c.stderr)
            r = subprocess.run(['vvp', str(p / 'test')], cwd=p,
                capture_output=True, text=True, timeout=10)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            rows = [json.loads(l.split(' ', 1)[1]) for l in r.stdout.splitlines()
                if l.startswith('RECEIVE_ACK_RESULT ')]
            self.assertEqual(len(rows), 1, r.stdout)
            self.assertTrue(rows[0]['pass_test'])


if __name__ == '__main__':
    unittest.main()
