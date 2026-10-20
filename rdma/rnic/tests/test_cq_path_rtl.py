# SPDX-License-Identifier: BSD-2-Clause-Views
"""Real MAC/lifetime -> CQC1 publisher -> AXI event snapshots for driver tests.

Physical MAC pins, HLS/memory/RX proof inputs and core retirement are MODELS.
The CQ publisher, actual TX tag/framer/EOF/tail and lifetime are production
RTL. No genuine internal-HLS drain, main-parent CQ completion or hardware
claim: production main keeps that unproved certificate at zero.
"""
import json
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

import test_wqe_tx_lifetime_rtl as tx

ROOT=tx.ROOT
RTL=ROOT/'rdma/rnic/rtl/rocev2_cq_mmio.v'
AXI=ROOT/'external/corundum/fpga/lib/axi/rtl'
SOURCES=tx.mac.SOURCES+[tx.life.RTL,tx.RTL,RTL]+[AXI/(n+'.v')for n in ['axil_reg_if','axil_reg_if_rd','axil_reg_if_wr']]

HOST=r'''
reg retire_allowed=0;
wire [587:0] pub_retire_context;wire pub_retire_valid;
wire [7:0] pub_guard,pub_fault_code;wire pub_busy,pub_fault;
wire [31:0] pub_published,pub_acked;
reg [11:0] host_awaddr=0,host_araddr=0;reg [2:0] host_awprot=0,host_arprot=0;
reg host_awvalid=0,host_wvalid=0,host_bready=0,host_arvalid=0,host_rready=0;
reg [31:0] host_wdata=0;reg [3:0] host_wstrb=0;
wire host_awready,host_wready,host_bvalid,host_arready,host_rvalid;
wire [1:0] host_bresp,host_rresp;wire [31:0] host_rdata;
rocev2_cq_mmio publisher(
 .clk(clk),.rst(rst),.parent_fault(parent_fault),
 .s_ticket_context(m_cq_context),.s_ticket_valid(m_cq_valid),.s_ticket_ready(m_cq_ready),
 .s_ticket_received_bytes(32'd0),
 .s_owner_cookie(64'd1),.s_owner_epoch(64'h9123456700000001),.s_owner_pd(16'd17),.s_owner_valid(1'b1),
 .m_commit_context(s_cq_commit_context),.m_commit_error(s_cq_commit_error),
 .m_commit_valid(s_cq_commit_valid),.m_commit_ready(s_cq_commit_ready),
 .m_retire_context(pub_retire_context),.m_retire_valid(pub_retire_valid),.m_retire_ready(retire_allowed),
 .queue_guard(pub_guard),.busy(pub_busy),.fault(pub_fault),.fault_code(pub_fault_code),
 .published_count(pub_published),.acknowledged_count(pub_acked),
 .s_axil_awaddr(host_awaddr),.s_axil_awprot(host_awprot),.s_axil_awvalid(host_awvalid),.s_axil_awready(host_awready),
 .s_axil_wdata(host_wdata),.s_axil_wstrb(host_wstrb),.s_axil_wvalid(host_wvalid),.s_axil_wready(host_wready),
 .s_axil_bresp(host_bresp),.s_axil_bvalid(host_bvalid),.s_axil_bready(host_bready),
 .s_axil_araddr(host_araddr),.s_axil_arprot(host_arprot),.s_axil_arvalid(host_arvalid),.s_axil_arready(host_arready),
 .s_axil_rdata(host_rdata),.s_axil_rresp(host_rresp),.s_axil_rvalid(host_rvalid),.s_axil_rready(host_rready));
integer host_deadline,host_fd,host_i;reg [31:0] host_value;
task cq_read;
 input [11:0] address;output [31:0] value;
 begin
  host_deadline=cycle+100;
  @(negedge clk);host_araddr=address;host_arvalid=1;
  @(posedge clk);while(!host_arready)begin if(cycle>host_deadline)$fatal(1,"CQ AR deadline");@(posedge clk);end
  @(negedge clk);host_arvalid=0;
  while(!host_rvalid)begin if(cycle>host_deadline)$fatal(1,"CQ R deadline");@(negedge clk);end
  value=host_rdata;if(host_rresp)$fatal(1,"CQ read response");
  repeat(3)begin @(negedge clk);if(!host_rvalid || host_rdata!==value)$fatal(1,"CQ AXI read stall changed");end
  host_rready=1;@(posedge clk);@(negedge clk);host_rready=0;
 end
endtask
task cq_ack;
 input [31:0] seq;
 begin
  fork
   begin @(negedge clk);host_awaddr=12'h010;host_awvalid=1;
    @(posedge clk);while(!host_awready)@(posedge clk);@(negedge clk);host_awvalid=0;end
   begin @(negedge clk);host_wdata=seq;host_wstrb=15;host_wvalid=1;
    @(posedge clk);while(!host_wready)@(posedge clk);@(negedge clk);host_wvalid=0;end
  join
  host_deadline=cycle+100;
  while(!host_bvalid)begin if(cycle>host_deadline)$fatal(1,"CQ B deadline");@(negedge clk);end
  if(host_bresp)$fatal(1,"CQ ACK response");
  repeat(3)@(negedge clk);host_bready=1;@(posedge clk);@(negedge clk);host_bready=0;
 end
endtask
task cq_snapshot;
 input integer seq;
 begin
  cq_read(12'h00c,host_value);if(host_value!==3)$fatal(1,"CQ event not visible/owned");
  if(pub_guard!==8'h80 || !pub_busy || busy || queue_guard || committed_count!=seq || pub_fault)
   $fatal(1,"CQ handoff lost actual lifetime/MAC ownership");
  host_fd=$fopen(seq==1 ? "event1.hex" : "event2.hex","w");
  cq_read(12'h018,host_value);if(host_value!=seq)$fatal(1,"CQ event sequence");$fdisplay(host_fd,"%08h",host_value);
  cq_read(12'h01c,host_value);if(host_value!=15)$fatal(1,"CQ actual commit/core proofs");$fdisplay(host_fd,"%08h",host_value);
  cq_read(12'h028,host_value);$fdisplay(host_fd,"%08h",host_value);
  cq_read(12'h020,host_value);if(host_value!=1)$fatal(1,"CQ full SQ cookie");$fdisplay(host_fd,"%08h",host_value);
  cq_read(12'h024,host_value);$fdisplay(host_fd,"%08h",host_value);
  for(host_i=0;host_i<19;host_i=host_i+1)begin
   cq_read(12'h040+host_i*4,host_value);$fdisplay(host_fd,"%08h",host_value);
   if(host_value!==(({20'd0,expected_owner}>>(host_i*32))&32'hffffffff))$fatal(1,"CQ changed a full owner word");
  end
  $fclose(host_fd);
  repeat(17)@(negedge clk);
  if(!pub_busy || pub_guard!==8'h80 || pub_acked!=seq-1)$fatal(1,"host backpressure lost CQ event");
 end
endtask
task cq_retire;
 input integer seq;
 begin
  memory_drained=1;repeat(5)@(negedge clk);
  if(m_cq_valid || pub_busy)$fatal(1,"memory drain substituted for HLS drain");
  // Explicit test-only HLS/core certificate MODEL, never wired true in main.
  hls_transport_drained=1;deadline=cycle+100;
  while(!pub_retire_valid)begin if(cycle>deadline)$fatal(1,"CQ lifetime commit deadline");@(negedge clk);end
  if(pub_retire_context!==expected_owner || committed_count!=seq || pub_published!=seq-1)$fatal(1,"CQ exact commit handoff");
  cq_read(12'h00c,host_value);if(host_value!==2)$fatal(1,"CQ visible before actual core retire");
  cq_read(12'h01c,host_value);if(host_value)$fatal(1,"CQ early proof publication");
  retire_allowed=1;@(posedge clk);@(negedge clk);retire_allowed=0;
 end
endtask
always @(posedge clk)if(!rst && (pub_fault || fault))$fatal(1,"CQ/lifetime fault %h/%h",pub_fault_code,fault_code);
'''


def bench():
    ctx=lambda seq:tx.life.context(id=0xf123456789abc000+seq,sequence=seq,pd=17,tag=seq,lkey=8,opcode=2)
    body=r'''
cq_read(0,host_value);if(host_value!==32'h43514331)$fatal(1,"CQ ID");
cq_read(12'h00c,host_value);if(host_value)$fatal(1,"fresh CQ not empty");
'''
    for seq,psn in [(1,0xfffffe),(2,0xffffff)]:
        if seq==2:body+='enable=1;memory_drained=0;hls_transport_drained=0;$readmemh("request2.hex",words);\n'
        body+=f'owner({ctx(seq)});transmit(60);expectation(24\'h{psn:06x});'
        body+=tx.life.proofs(psn=psn)+f'cq_retire({seq});cq_snapshot({seq});\n'
        if seq==2:
            body+='cq_ack(1);cq_read(12\'h00c,host_value);if(host_value!==3 || pub_acked!=1)$fatal(1,"late ACK cleared successor");\n'
        body+=f'cq_ack({seq});cq_read(12\'h014,host_value);if(host_value!={seq} || pub_busy || pub_guard)$fatal(1,"CQ final ACK owner");\n'
    body+='$display("CQ_PATH_RESULT {\\"pass_test\\":true,\\"events\\":%0d,\\"acknowledgements\\":%0d,\\"actual_lifetime_commits\\":%0d}",pub_published,pub_acked,committed_count);'
    tb=tx.bench(body)
    for name in ['ticket','take_ticket','commit']:
        a=tb.index('task '+name+';');b=tb.index('endtask',a)+len('endtask');tb=tb[:a]+tb[b:]
    for n in ['m_cq_ready','s_cq_commit_context','s_cq_commit_error','s_cq_commit_valid']:
        tb,count=re.subn(r'\breg (\[[^]]+\]\s+)?'+n+r'=0;',lambda m:'wire '+(m[1]or'')+n+';',tb)
        if count!=1:raise ValueError('CQ model driver changed '+n)
    # Adapt the existing real MAC task to two sequential non-reused tags.
    tb=tb.replace('frame_count!=1','frame_count!=committed_count+1').replace('receipt_count!=1 || mac_proof_count!=1 || active_tag!=16\'h2001',
        'receipt_count!=committed_count+1 || mac_proof_count!=committed_count+1 || active_tag!=16\'h2001+committed_count')
    return tb.replace('reg [127:0] words',HOST+'\nreg [127:0] words',1)


def simulate(directory):
    p=Path(directory);p.mkdir(parents=True,exist_ok=True)
    tb=bench();(p/'tb.v').write_text(tb)
    for seq,psn in [(1,0xfffffe),(2,0xffffff)]:
        pkt=tx.life.request(psn=psn)
        (p/('request.hex'if seq==1 else'request2.hex')).write_text(''.join(
            f'{int.from_bytes(pkt[n:n+16].ljust(16,bytes([0])),"little"):032x}\n'for n in range(0,len(pkt),16)))
    c=subprocess.run(['iverilog','-g2012','-s','tb','-o',str(p/'test.vvp'),str(p/'tb.v'),*map(str,SOURCES)],capture_output=True,text=True,timeout=30)
    if c.returncode:raise RuntimeError(c.stdout+c.stderr)
    r=subprocess.run(['vvp',str(p/'test.vvp')],cwd=p,capture_output=True,text=True,timeout=10)
    (p/'simulation.log').write_text(r.stdout+r.stderr)
    if r.returncode:raise RuntimeError(r.stdout+r.stderr)
    rows=[json.loads(l.split(' ',1)[1])for l in r.stdout.splitlines()if l.startswith('CQ_PATH_RESULT ')]
    if len(rows)!=1 or rows[0]!=dict(pass_test=True,events=2,acknowledgements=2,actual_lifetime_commits=2):
        raise ValueError('missing real CQ path summary')
    return rows[0]


class CQPathTests(unittest.TestCase):
    def test_actual_MAC_lifetime_commit_retire_and_MMIO_publication(self):
        with tempfile.TemporaryDirectory(prefix='as02-cq-path-')as d:self.assertTrue(simulate(d)['pass_test'])


if __name__=='__main__':unittest.main()
