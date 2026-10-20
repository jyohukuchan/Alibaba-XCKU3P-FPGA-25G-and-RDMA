# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual router RTL with explicit descriptor/RAM/parent MODELS, no PCIe engine.

No actual backend/host pages/HLS/board/kernel/verbs proof in these units.
Only public input ports are used for fault injection; no internal forcing.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[3]
RTL=ROOT/'rdma/rnic/rtl/rocev2_dma_client_router.v'
TB=r'''
`timescale 1ns/1ps
module tb;
localparam RAM_ADDR_WIDTH=15,SEG_COUNT=2,SEG_DATA_WIDTH=256,SEG_BE_WIDTH=32,SEG_ADDR_WIDTH=9,DMA_LEN_WIDTH=16,TAG_WIDTH=16;
// DECLARATIONS
rocev2_dma_client_router #(.INITIAL_PHYSICAL_TAG(INITIAL_TAG_VALUE)) dut(.*);
always #2 clk=~clk;
integer cycle=0,statuses=0,wr_returns=0,rd_returns=0,k;
reg last_owner=0,last_direction=0;reg [15:0] last_logical_tag=0;reg [3:0] last_error=0;
reg rd_stalled=0,wr_stalled=0,response_stalled=0;
reg [111:0] saved_rd;reg [144:0] saved_wr;reg [513:0] saved_response;
always @(posedge clk)if(!rst)begin
 cycle=cycle+1;if(cycle>5000)$fatal(1,"router cycle deadline");
 if(rd_stalled && (!m_dma_read_valid || {m_dma_read_address,m_dma_read_ram_sel,m_dma_read_ram_address,m_dma_read_length,m_dma_read_tag}!==saved_rd))
  $fatal(1,"physical read descriptor withdrawn/changed");
 if(wr_stalled && (!m_dma_write_valid || {m_dma_write_address,m_dma_write_ram_sel,m_dma_write_ram_address,m_dma_write_length,m_dma_write_tag,m_dma_write_imm,m_dma_write_imm_en}!==saved_wr))
  $fatal(1,"physical write descriptor withdrawn/changed");
 if(response_stalled && {dma_ram_rd_resp_valid,dma_ram_rd_resp_data}!==saved_response)$fatal(1,"held RAM response withdrawn/changed");
 rd_stalled=m_dma_read_valid&&!m_dma_read_ready;wr_stalled=m_dma_write_valid&&!m_dma_write_ready;
 response_stalled=(|dma_ram_rd_resp_valid)&&!(|dma_ram_rd_resp_ready);
 saved_rd={m_dma_read_address,m_dma_read_ram_sel,m_dma_read_ram_address,m_dma_read_length,m_dma_read_tag};
 saved_wr={m_dma_write_address,m_dma_write_ram_sel,m_dma_write_ram_address,m_dma_write_length,m_dma_write_tag,m_dma_write_imm,m_dma_write_imm_en};
 saved_response={dma_ram_rd_resp_valid,dma_ram_rd_resp_data};
 for(k=0;k<2;k=k+1)begin
  if(m_client_read_status_valid[k])begin statuses=statuses+1;last_owner=k;last_direction=0;last_logical_tag=m_client_read_status_tag[k*16+:16];last_error=m_client_read_status_error[k*4+:4];end
  if(m_client_write_status_valid[k])begin statuses=statuses+1;last_owner=k;last_direction=1;last_logical_tag=m_client_write_status_tag[k*16+:16];last_error=m_client_write_status_error[k*4+:4];end
 end
 if(|dma_ram_wr_done)wr_returns=wr_returns+1;
 if(|(dma_ram_rd_resp_valid&dma_ram_rd_resp_ready))rd_returns=rd_returns+1;
 if(drained && ((|client_busy) || (|dma_ram_wr_done) || (|dma_ram_rd_resp_valid)))$fatal(1,"false router drain");
end
task offer;
 input direction,owner;input [15:0] logical_tag;input [63:0] address;input [14:0] ram;input [15:0] length;
 integer deadline;
 begin
  @(negedge clk);
  if(direction)begin s_client_write_address[owner*64+:64]=address;s_client_write_ram_address[owner*15+:15]=ram;
   s_client_write_length[owner*16+:16]=length;s_client_write_tag[owner*16+:16]=logical_tag;s_client_write_valid[owner]=1;end
  else begin s_client_read_address[owner*64+:64]=address;s_client_read_ram_address[owner*15+:15]=ram;
   s_client_read_length[owner*16+:16]=length;s_client_read_tag[owner*16+:16]=logical_tag;s_client_read_valid[owner]=1;end
  deadline=cycle+100;@(posedge clk);
  while(!(direction ? s_client_write_ready[owner]:s_client_read_ready[owner]))begin
   if(cycle>deadline)$fatal(1,"client offer deadline");@(posedge clk);
  end
  @(negedge clk);if(direction)s_client_write_valid[owner]=0;else s_client_read_valid[owner]=0;
 end
endtask
task accept_expected;
 input direction,owner;integer deadline;
 begin
  deadline=cycle+12;@(posedge clk);
  while(!(direction ? (|s_client_write_ready):(|s_client_read_ready)))begin
   if(cycle>deadline)$fatal(1,"bounded round-robin admission deadline");@(posedge clk);
  end
  if((direction ? s_client_write_ready:s_client_read_ready)!==(owner ? 2'b10:2'b01))
   $fatal(1,"round-robin original owner changed/starved");
 end
endtask
task physical;
 input direction,owner;input [15:0] tag;input [63:0] address;input [14:0] ram;input [15:0] length;
 integer deadline;
 begin
  deadline=cycle+100;while(!(direction ? m_dma_write_valid:m_dma_read_valid))begin if(cycle>deadline)$fatal(1,"physical offer deadline");@(negedge clk);end
  if(direction)begin
   if(m_dma_write_tag!==tag || m_dma_write_ram_sel!==owner || m_dma_write_address!==address || m_dma_write_ram_address!==ram || m_dma_write_length!==length || m_dma_write_imm_en)
    $fatal(1,"physical write full tuple mismatch");
  end else if(m_dma_read_tag!==tag || m_dma_read_ram_sel!==owner || m_dma_read_address!==address || m_dma_read_ram_address!==ram || m_dma_read_length!==length)
   $fatal(1,"physical read full tuple mismatch");
  repeat(3)@(negedge clk);
  if(direction)m_dma_write_ready=1;else m_dma_read_ready=1;
  @(posedge clk);@(negedge clk);m_dma_write_ready=0;m_dma_read_ready=0;
 end
endtask
task physical_status;
 input direction;input [15:0] tag;input [3:0] error_code;
 begin
  @(negedge clk);if(direction)begin s_dma_write_status_tag=tag;s_dma_write_status_error=error_code;s_dma_write_status_valid=1;end
  else begin s_dma_read_status_tag=tag;s_dma_read_status_error=error_code;s_dma_read_status_valid=1;end
  @(posedge clk);@(negedge clk);s_dma_read_status_valid=0;s_dma_write_status_valid=0;
 end
endtask
task expect_status;
 input direction,owner;input [15:0] tag;input [3:0] error_code;input integer count;
 integer deadline;
 begin
  deadline=cycle+100;while(statuses<count)begin if(cycle>deadline)$fatal(1,"logical status deadline");@(negedge clk);end
  if(statuses!=count || last_owner!==owner || last_direction!==direction || last_logical_tag!==tag || last_error!==error_code || fault)
   $fatal(1,"logical status owner/tag/error mismatch");
 end
endtask
task write_ram;
 input owner;input [8:0] word;input [511:0] bytes;input cached_status;input [15:0] tag;
 integer deadline;
 begin
  @(negedge clk);dma_ram_wr_cmd_sel={2{owner}};dma_ram_wr_cmd_addr={word,word};
  dma_ram_wr_cmd_be=64'hffffffffffffffff;dma_ram_wr_cmd_data=bytes;dma_ram_wr_cmd_valid=3;
  deadline=cycle+100;@(posedge clk);while(dma_ram_wr_cmd_ready!==3)begin if(cycle>deadline)$fatal(1,"write RAM admission deadline");@(posedge clk);end
  @(negedge clk);dma_ram_wr_cmd_valid=0;
  repeat(5)begin
   if(client_ram_wr_cmd_valid!==(3<<(owner*2)) || client_ram_wr_cmd_data[owner*512+:512]!==bytes || dma_ram_wr_done)
    $fatal(1,"RAM write owner/stall/data mismatch");@(negedge clk);
  end
  client_ram_wr_cmd_ready=3<<(owner*2);@(posedge clk);@(negedge clk);client_ram_wr_cmd_ready=0;
  if(cached_status)begin
   physical_status(0,tag,0);repeat(4)begin @(negedge clk);if((|m_client_read_status_valid) || !client_busy[owner])$fatal(1,"status retired before RAM done");end
  end
  client_ram_wr_done=3<<(owner*2);@(posedge clk);@(negedge clk);client_ram_wr_done=0;
  if(dma_ram_wr_done!==3)$fatal(1,"RAM write done not returned to original request");
  @(negedge clk);
 end
endtask
task read_ram;
 input owner;input [8:0] word;input [511:0] bytes;
 integer deadline;
 begin
  @(negedge clk);dma_ram_rd_cmd_sel={2{owner}};dma_ram_rd_cmd_addr={word,word};dma_ram_rd_cmd_valid=3;
  deadline=cycle+100;@(posedge clk);while(dma_ram_rd_cmd_ready!==3)begin if(cycle>deadline)$fatal(1,"read RAM admission deadline");@(posedge clk);end
  @(negedge clk);dma_ram_rd_cmd_valid=0;
  repeat(5)begin
   if(client_ram_rd_cmd_valid!==(3<<(owner*2)))$fatal(1,"read RAM wrong bank/withdrawn offer");@(negedge clk);
  end
  client_ram_rd_cmd_ready=3<<(owner*2);@(posedge clk);@(negedge clk);client_ram_rd_cmd_ready=0;
  client_ram_rd_resp_data[owner*512+:512]=bytes;client_ram_rd_resp_valid=3<<(owner*2);
  @(posedge clk);if(client_ram_rd_resp_ready!==(3<<(owner*2)))$fatal(1,"response ready to wrong owner");
  @(negedge clk);client_ram_rd_resp_valid=0;
  repeat(5)begin
   if(dma_ram_rd_resp_valid!==3 || dma_ram_rd_resp_data!==bytes)$fatal(1,"read RAM response stall/bytes");@(negedge clk);
  end
  dma_ram_rd_resp_ready=3;@(posedge clk);@(negedge clk);dma_ram_rd_resp_ready=0;
 end
endtask
initial begin
 rst=1;repeat(4)@(negedge clk);rst=0;enable=1;
 // BODY
 $display("DMA_ROUTER_RESULT {\"pass_test\":true,\"cycles\":%0d,\"descriptors\":%0d,\"completions\":%0d,\"statuses\":%0d,\"fault\":%0d}",cycle,descriptor_count,completion_count,statuses,fault);
 $finish;
end
endmodule
'''


def declarations():
    text=RTL.read_text().split(')(\n',1)[1].split('\n);',1)[0]
    ports=re.findall(r'^\s*(input|output)\s+wire\s+(\[[^]]+\]\s+)?(\w+)\s*,?$',text,re.M)
    if len(ports)<80:raise ValueError('incomplete actual router ports')
    return '\n'.join(('reg 'if d=='input'else'wire ')+(w or '')+n+('=0;'if d=='input'else';')for d,w,n in ports)


class DMAClientRouterRTLTests(unittest.TestCase):
    reports={}
    def simulate(self,body,initial_tag=0):
        tb=TB.replace('// DECLARATIONS',declarations()).replace('INITIAL_TAG_VALUE',str(initial_tag)).replace('// BODY',body)
        self.assertNotIn('force ',tb)
        paths=[RTL,Path(__file__).resolve()];before={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in paths}
        with tempfile.TemporaryDirectory(prefix='as02-dma-router-')as directory:
            p=Path(directory);(p/'tb.v').write_text(tb)
            c=subprocess.run(['iverilog','-g2012','-s','tb','-o',str(p/'test.vvp'),str(p/'tb.v'),str(RTL)],capture_output=True,text=True,timeout=20)
            self.assertEqual(c.returncode,0,c.stdout+c.stderr)
            r=subprocess.run(['vvp',str(p/'test.vvp')],capture_output=True,text=True,timeout=10)
            self.assertEqual(r.returncode,0,r.stdout+r.stderr)
            rows=[json.loads(line[18:])for line in r.stdout.splitlines()if line.startswith('DMA_ROUTER_RESULT ')]
            self.assertEqual(len(rows),1,r.stdout);self.assertTrue(rows[0]['pass_test'])
        self.assertEqual(before,{n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest()for n in before})
        self.reports.setdefault(self._testMethodName,[]).append(dict(summary=rows[0],source_sha256=before,bench_sha256=hashlib.sha256(tb.encode()).hexdigest()))

    def test_same_full_logical_tags_two_banks_mixed_directions_reverse_status_and_RAM(self):
        self.simulate(r'''
offer(0,0,16'hffff,64'h8123456789abc000,0,64);physical(0,0,1,64'h8123456789abc000,0,64);
offer(1,1,16'hffff,64'hfedcba9876543000,0,64);physical(1,1,2,64'hfedcba9876543000,0,64);
if(client_busy!==3)$fatal(1,"both banks not active");
read_ram(1,0,512'h9876543210abcdef);physical_status(1,2,0);expect_status(1,1,16'hffff,0,1);
write_ram(0,0,512'hfedcba0123456789,1,1);expect_status(0,0,16'hffff,0,2);
repeat(4)@(negedge clk);if(!drained || descriptor_count!=2 || completion_count!=2 || wr_returns!=1 || rd_returns!=1)$fatal(1,"mixed flow coverage/drain");
''')

    def test_zero_and_high_logical_tag_preserve_error_and_physical_independence(self):
        self.simulate(r'''
offer(0,1,0,64'hffffffffffffffc0,15'd32704,64);physical(0,1,1,64'hffffffffffffffc0,15'd32704,64);
physical_status(0,1,10);expect_status(0,1,0,10,1);
offer(1,0,16'h8000,64'h8123456789abc001,3,62);physical(1,0,2,64'h8123456789abc001,3,62);
read_ram(0,1,512'h1234);physical_status(1,2,0);expect_status(1,0,16'h8000,0,2);
repeat(3)@(negedge clk);if(!drained)$fatal(1,"zero/high tag flow did not drain");
''')

    def test_bad_full_descriptor_range_RAM_selector_or_unsupported_immediate_never_accepted(self):
        for setup in ["s_client_read_length[15:0]=0;","s_client_read_ram_sel[0]=1;",
                      "s_client_read_address[63:0]=64'hffffffffffffffc0;s_client_read_length[15:0]=65;",
                      "s_client_read_ram_address[14:0]=32767;s_client_read_length[15:0]=2;"]:
            with self.subTest(setup=setup):self.simulate(r'''
s_client_read_address[63:0]=64'h8123456789abc000;s_client_read_length[15:0]=64;s_client_read_valid=1;
'''+setup+r'''
repeat(5)@(negedge clk);if(!fault || fault_code!==8'h10 || s_client_read_ready || m_dma_read_valid || statuses || descriptor_count)
 $fatal(1,"invalid descriptor accepted/truncated");
''')
        self.simulate(r'''
s_client_write_address[63:0]=64'h1000;s_client_write_length[15:0]=4;s_client_write_imm_en=1;s_client_write_valid=1;
repeat(5)@(negedge clk);if(!fault || m_dma_write_valid || descriptor_count)$fatal(1,"unsupported immediate silently accepted");
''')

    def test_invalid_RAM_address_bank_direction_byte_mask_and_unsolicited_child_completion(self):
        for ports in ["dma_ram_wr_cmd_addr=18'h201;dma_ram_wr_cmd_be=64'hffffffffffffffff;dma_ram_wr_cmd_valid=3;",
                      'dma_ram_wr_cmd_sel=3;dma_ram_wr_cmd_be=64\'hffffffffffffffff;dma_ram_wr_cmd_valid=3;',
                      'dma_ram_rd_cmd_valid=3;','dma_ram_wr_cmd_valid=3;',
                      'client_ram_wr_done=1;','client_ram_rd_resp_valid=1;']:
            with self.subTest(ports=ports):self.simulate(r'''
offer(0,0,1,64'h1000,0,64);physical(0,0,1,64'h1000,0,64);
'''+ports+r'''
repeat(5)@(negedge clk);if(!fault || fault_code!==8'h12 || statuses || drained || !client_busy[0])$fatal(1,"invalid RAM request released owner");
''')

    def test_unknown_or_duplicate_physical_status_never_completes_a_logical_owner(self):
        for status in ["physical_status(0,16'h8001,0);","physical_status(1,1,0);",
                       "physical_status(0,1,4'bx000);"]:
            with self.subTest(status=status):self.simulate(r'''
offer(0,0,16'h8000,64'h1000,0,64);physical(0,0,1,64'h1000,0,64);
'''+status+r'''
repeat(5)@(negedge clk);if(!fault || statuses || drained || !client_busy[0])$fatal(1,"bad physical status released owner");
''')

    def test_later_fault_does_not_withdraw_accepted_physical_descriptor(self):
        self.simulate(r'''
offer(0,0,16'hffff,64'h8123456789abc000,0,64);physical_status(0,16'h9999,0);
repeat(5)@(negedge clk);if(!fault || !m_dma_read_valid || m_dma_read_address!==64'h8123456789abc000 || m_dma_read_tag!==1)
 $fatal(1,"fault retracted accepted descriptor");
physical(0,0,1,64'h8123456789abc000,0,64);
repeat(5)@(negedge clk);if(!fault || drained || statuses || !client_busy[0])$fatal(1,"fault manufactured completion/drain");
''')

    def test_accepted_RAM_command_and_response_survive_fault_and_backpressure(self):
        self.simulate(r'''
offer(1,1,16'hffff,64'h1000,0,64);physical(1,1,1,64'h1000,0,64);
dma_ram_rd_cmd_sel=3;dma_ram_rd_cmd_valid=3;
@(posedge clk);while(dma_ram_rd_cmd_ready!==3)@(posedge clk);
@(negedge clk);dma_ram_rd_cmd_valid=0;physical_status(0,16'h9999,0);
repeat(4)@(negedge clk);if(!fault || client_ram_rd_cmd_valid!==12)$fatal(1,"accepted RAM offer retracted on fault");
client_ram_rd_cmd_ready=12;@(posedge clk);@(negedge clk);client_ram_rd_cmd_ready=0;
client_ram_rd_resp_data[512+:512]=512'hf123456789abcdef;client_ram_rd_resp_valid=12;
@(posedge clk);@(negedge clk);client_ram_rd_resp_valid=0;
repeat(7)begin @(negedge clk);if(dma_ram_rd_resp_valid!==3 || dma_ram_rd_resp_data!==512'hf123456789abcdef)$fatal(1,"owned response lost on fault");end
dma_ram_rd_resp_ready=3;@(posedge clk);@(negedge clk);dma_ram_rd_resp_ready=0;
if(!fault || drained || statuses || !client_busy[1])$fatal(1,"RAM drain mistaken for DMA/MR completion");
''')

    def test_disable_only_stops_new_admission_not_existing_RAM_or_status(self):
        self.simulate(r'''
offer(0,0,16'h8000,64'h1000,0,64);enable=0;physical(0,0,1,64'h1000,0,64);
write_ram(0,0,512'h1234,0,0);physical_status(0,1,0);expect_status(0,0,16'h8000,0,1);
repeat(4)@(negedge clk);if(!drained || fault)$fatal(1,"disable cancelled existing DMA");
''')

    def test_physical_tag_exhaustion_refuses_wrap_without_shortening_logical_tag(self):
        self.simulate(r'''
offer(0,0,16'hffff,64'h1000,0,64);physical(0,0,16'hffff,64'h1000,0,64);
physical_status(0,16'hffff,0);expect_status(0,0,16'hffff,0,1);
s_client_read_valid=2;s_client_read_length[31:16]=64;
repeat(8)@(negedge clk);if(!tag_exhausted || s_client_read_ready || m_dma_read_valid || descriptor_count!=1 || statuses!=1 || fault || drained)
 $fatal(1,"physical tag wrapped or pending offer pretended drained");
''',65534)

    def test_continuous_two_bank_offers_are_fair_across_read_and_write_ports(self):
        self.simulate(r'''
s_client_read_address={64'hfedcba9876543000,64'h8123456789abc000};s_client_read_length={16'd64,16'd64};
s_client_read_tag={16'hffff,16'hffff};s_client_read_valid=3;
accept_expected(0,0);
@(negedge clk);s_client_read_valid=2;physical(0,0,1,64'h8123456789abc000,0,64);
accept_expected(0,1);
@(negedge clk);s_client_read_valid=0;physical(0,1,2,64'hfedcba9876543000,0,64);
physical_status(0,2,0);expect_status(0,1,16'hffff,0,1);physical_status(0,1,0);expect_status(0,0,16'hffff,0,2);
s_client_write_address={64'hfedcba9876543000,64'h8123456789abc000};s_client_write_length={16'd64,16'd64};
s_client_write_tag={16'h8000,16'h8000};s_client_write_valid=3;
accept_expected(1,0);
@(negedge clk);s_client_write_valid=2;physical(1,0,3,64'h8123456789abc000,0,64);
accept_expected(1,1);
@(negedge clk);s_client_write_valid=0;physical(1,1,4,64'hfedcba9876543000,0,64);
physical_status(1,3,0);expect_status(1,0,16'h8000,0,3);physical_status(1,4,0);expect_status(1,1,16'h8000,0,4);
repeat(4)@(negedge clk);if(!drained || descriptor_count!=4 || completion_count!=4)$fatal(1,"fairness sequence did not drain");
''')

    def test_duplicate_old_status_cannot_release_new_identical_logical_tag_owner(self):
        self.simulate(r'''
offer(0,0,16'hffff,64'h1000,0,64);physical(0,0,1,64'h1000,0,64);
physical_status(0,1,0);expect_status(0,0,16'hffff,0,1);
offer(0,1,16'hffff,64'h2000,0,64);physical(0,1,2,64'h2000,0,64);
physical_status(0,1,0);repeat(5)@(negedge clk);
if(!fault || statuses!=1 || completion_count!=1 || !client_busy[1] || drained)$fatal(1,"old physical status aliased new owner");
''')

    def test_read_response_ready_has_registered_command_boundary_even_for_zero_latency_offer(self):
        self.simulate(r'''
offer(1,0,16'hffff,64'h8123456789abc000,0,64);physical(1,0,1,64'h8123456789abc000,0,64);
@(negedge clk);dma_ram_rd_cmd_sel=0;dma_ram_rd_cmd_addr=0;dma_ram_rd_cmd_valid=3;
@(posedge clk);while(dma_ram_rd_cmd_ready!==3)@(posedge clk);
@(negedge clk);dma_ram_rd_cmd_valid=0;
if(client_ram_rd_cmd_valid!==3 || client_ram_rd_resp_ready!==0)$fatal(1,"response-ready depends on unaccepted command");
client_ram_rd_cmd_ready=3;client_ram_rd_resp_data=1024'h123456789abcdef;client_ram_rd_resp_valid=3;
#1;if(client_ram_rd_resp_ready!==0)$fatal(1,"combinational command-ready to response-ready bypass");
@(posedge clk);@(negedge clk);client_ram_rd_cmd_ready=0;
if(client_ram_rd_cmd_valid || client_ram_rd_resp_ready!==3 || dma_ram_rd_resp_valid)$fatal(1,"registered response ownership missing");
@(posedge clk);@(negedge clk);client_ram_rd_resp_valid=0;
if(dma_ram_rd_resp_valid!==3 || dma_ram_rd_resp_data!==512'h123456789abcdef)$fatal(1,"zero latency response lost/captured before handshake");
dma_ram_rd_resp_ready=3;@(posedge clk);@(negedge clk);dma_ram_rd_resp_ready=0;
physical_status(1,1,0);expect_status(1,0,16'hffff,0,1);
repeat(4)@(negedge clk);if(fault || !drained || completion_count!=1)$fatal(1,"registered RAM boundary did not drain");
''')

    def test_proposal_has_no_acceptance_bypass_and_keeps_original_bank_when_arbiter_changes(self):
        self.simulate(r'''
s_client_read_address[127:64]=64'hfedcba9876543000;s_client_read_length[31:16]=64;
s_client_read_tag[31:16]=16'hffff;s_client_read_valid=2;
#1;if(s_client_read_ready || m_dma_read_valid || descriptor_count)$fatal(1,"unregistered proposal bypass");
@(posedge clk);@(negedge clk);
if(s_client_read_ready || m_dma_read_valid || m_dma_read_tag || descriptor_count || drained || !client_busy[1])$fatal(1,"unchecked proposal became DMA/empty proof");
s_client_read_address[63:0]=64'h8123456789abc000;s_client_read_length[15:0]=64;
s_client_read_tag[15:0]=16'h8000;s_client_read_valid=3;
accept_expected(0,1);@(negedge clk);s_client_read_valid=1;
physical(0,1,1,64'hfedcba9876543000,0,64);
accept_expected(0,0);@(negedge clk);s_client_read_valid=0;
physical(0,0,2,64'h8123456789abc000,0,64);
physical_status(0,1,0);expect_status(0,1,16'hffff,0,1);
physical_status(0,2,0);expect_status(0,0,16'h8000,0,2);
repeat(4)@(negedge clk);if(fault || !drained || descriptor_count!=2)$fatal(1,"registered proposal ownership/drain");
''')

    def test_selected_proposal_mutation_or_withdrawal_never_allocates_tag_or_DMA(self):
        changes=["s_client_write_valid=0;","s_client_write_address[127:64]=64'h7123456789abc000;",
                 "s_client_write_ram_sel=2;","s_client_write_ram_address[29:15]=1;",
                 "s_client_write_length[31:16]=65;","s_client_write_tag[31:16]=16'h7fff;",
                 "s_client_write_imm_en=2;"]
        for change in changes:
            with self.subTest(change=change):self.simulate(r'''
s_client_write_address[127:64]=64'h8123456789abc000;s_client_write_length[31:16]=64;
s_client_write_tag[31:16]=16'hffff;s_client_write_valid=2;
@(posedge clk);@(negedge clk);
if(s_client_write_ready || m_dma_write_valid || tag_exhausted)$fatal(1,"proposal consumed final tag before acceptance");
'''+change+r'''
repeat(6)@(negedge clk);
if(!fault || fault_code!==8'h13 || s_client_write_ready || m_dma_write_valid || m_dma_read_valid ||
   descriptor_count || completion_count || tag_exhausted || drained || !client_busy[1])$fatal(1,"mutated/withdrawn proposal accepted/released");
''',65534)

    def test_unknown_full_proposal_address_length_or_tag_rejected_before_acceptance(self):
        for change in ["s_client_read_address[63:0]=64'h8123456789abcx00;",
                       "s_client_read_length[15:0]=16'h00x0;","s_client_read_tag[15:0]=16'hx000;"]:
            with self.subTest(change=change):self.simulate(r'''
s_client_read_address[63:0]=64'h8123456789abc000;s_client_read_length[15:0]=64;s_client_read_valid=1;
'''+change+r'''
repeat(6)@(negedge clk);if(!fault || fault_code!==8'h10 || s_client_read_ready || m_dma_read_valid || descriptor_count || drained)
 $fatal(1,"unknown proposal address/range/tag accepted");
''')

    def test_disabled_unaccepted_proposal_retains_owner_but_other_issued_completion_drains(self):
        self.simulate(r'''
offer(0,0,16'h8000,64'h1000,0,64);physical(0,0,1,64'h1000,0,64);
@(negedge clk);s_client_write_address[127:64]=64'h2000;s_client_write_length[31:16]=64;
s_client_write_tag[31:16]=16'hffff;s_client_write_valid=2;
@(posedge clk);@(negedge clk);enable=0;
repeat(5)@(negedge clk);if(fault || s_client_write_ready || m_dma_write_valid || drained)$fatal(1,"disable accepted/cancelled preflight");
physical_status(0,1,0);expect_status(0,0,16'h8000,0,1);
if(client_busy!==2 || descriptor_count!=1)$fatal(1,"pending proposal blocked original completion or lost ownership");
enable=1;accept_expected(1,1);@(negedge clk);s_client_write_valid=0;enable=0;
physical(1,1,2,64'h2000,0,64);physical_status(1,2,0);expect_status(1,1,16'hffff,0,2);
repeat(4)@(negedge clk);if(fault || !drained || descriptor_count!=2)$fatal(1,"reenable proposal/current command drain");
''')

    def test_fault_during_unaccepted_proposal_retains_proposal_without_physical_offer(self):
        self.simulate(r'''
s_client_read_address[63:0]=64'h1000;s_client_read_length[15:0]=64;s_client_read_valid=1;
@(posedge clk);@(negedge clk);s_dma_read_status_tag=16'hffff;s_dma_read_status_valid=1;
@(posedge clk);@(negedge clk);s_dma_read_status_valid=0;
repeat(5)@(negedge clk);if(!fault || s_client_read_ready || m_dma_read_valid || descriptor_count || statuses || drained || !client_busy[0])
 $fatal(1,"later fault manufactured proposal acceptance/drain");
''')

    @classmethod
    def tearDownClass(cls):
        if name:=os.environ.get('AS02_DMA_CLIENT_ROUTER_REPORT'):
            p=Path(name);p=p if p.is_absolute()else ROOT/p
            with p.open('x')as out:json.dump(dict(scope=__doc__,pass_test=len(cls.reports)==17 and sum(map(len,cls.reports.values()))==36,methods=len(cls.reports),simulations=sum(map(len,cls.reports.values())),tests=cls.reports,
                hardware_verified=False,actual_PCIe_engine=False,native_host_page_DMA=False,standard_verbs_implemented=False),out,indent=2);out.write('\n')


if __name__=='__main__':unittest.main()
