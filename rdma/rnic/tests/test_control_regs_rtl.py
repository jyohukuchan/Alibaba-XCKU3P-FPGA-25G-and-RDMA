# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual AXI mailbox + Corundum AW/W/R/B adapter, controller MODEL only.

Register addresses/identity are imported from the real kernel ABI header.
No live MMIO/kernel/hardware is accessed.
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
RTL=ROOT/'rdma/rnic/rtl/rocev2_control_regs.v'
HEADER=ROOT/'rdma/rnic/kernel/rnic_regs.h'
SOURCES=[RTL,*[ROOT/'external/corundum/fpga/lib/axi/rtl'/p for p in ('axil_reg_if.v','axil_reg_if_wr.v','axil_reg_if_rd.v')]]
TB=r'''
`timescale 1ns/1ps
module tb;
localparam ADDR_WIDTH=12;
// ABI
// PORTS
rocev2_control_regs dut(.*);
always #2 clk=~clk;
integer scenario=0,dummy,cycles=0,writes=0,reads=0,accepted=0,acked=0,i;
reg [31:0] value,words[0:20];reg [671:0] saved_command;
reg stop_command=0;
always @(negedge clk) if(stop_command && command_valid) command_ready=0;
always @(posedge clk) if(!rst) begin
 cycles=cycles+1;if(cycles>10000) $fatal(1,"deadline");
 if(command_valid && command_ready) accepted=accepted+1;
 if(response_valid && response_ready) begin response_valid<=0;acked=acked+1;end
end
task write_reg;
 input [11:0] address;input [31:0] data;input [3:0] strobe;input integer aw_delay,w_delay;
 begin
  fork
   begin
    repeat(aw_delay) @(negedge clk);@(negedge clk);s_axil_awaddr=address;s_axil_awvalid=1;
    @(posedge clk);while(!s_axil_awready) @(posedge clk);@(negedge clk);s_axil_awvalid=0;
   end
   begin
    repeat(w_delay) @(negedge clk);@(negedge clk);s_axil_wdata=data;s_axil_wstrb=strobe;s_axil_wvalid=1;
    @(posedge clk);while(!s_axil_wready) @(posedge clk);@(negedge clk);s_axil_wvalid=0;
   end
  join
  while(!s_axil_bvalid) @(negedge clk);
  if(s_axil_bresp!=0) $fatal(1,"unexpected adapter response");
  repeat(5) begin @(negedge clk);if(!s_axil_bvalid || s_axil_bresp!=0) $fatal(1,"B response unstable");end
  s_axil_bready=1;@(negedge clk);s_axil_bready=0;writes=writes+1;
 end
endtask
task read_reg;
 input [11:0] address;output [31:0] data;
 reg [31:0] saved;
 begin
  @(negedge clk);s_axil_araddr=address;s_axil_arvalid=1;
  @(posedge clk);while(!s_axil_arready) @(posedge clk);@(negedge clk);s_axil_arvalid=0;
  while(!s_axil_rvalid) @(negedge clk);saved=s_axil_rdata;
  repeat(5) begin @(negedge clk);if(!s_axil_rvalid || s_axil_rdata!==saved || s_axil_rresp!=0) $fatal(1,"R response unstable");end
  data=saved;s_axil_rready=1;@(negedge clk);s_axil_rready=0;reads=reads+1;
 end
endtask
task stage;
 begin
  for(i=0;i<21;i=i+1) begin words[i]=0;end
  words[0]=17;words[1]=2;words[2]=32'h89abcdef;words[3]=32'h12345678;
  words[4]=3;words[5]=0;words[6]=17;words[7]=7;words[8]=32'h76543210;words[9]=32'hfedcba98;
  words[10]=8193;words[11]=4093;words[12]=255;words[13]=32'hfffff000;words[14]=32'hffffffff;
  words[15]=2;words[16]=196;words[17]=32'hc6120b02;words[18]=32'hc6120b01;words[19]=24'h987654;words[20]=24'hfffffe;
  for(i=0;i<21;i=i+1) begin write_reg(AS02_CTL_STAGE+i*4,words[i],15,i%4,(i+2)%4);end
 end
endtask
task model_reply;
 begin
  @(negedge clk);response_command=2;response_sequence=17;response_cookie=64'h1234567889abcdef;
  response_slot=3;response_key=11;response_error=0;response_flags=16;response_valid=1;
 end
endtask
task clear_error;
 begin
  write_reg(AS02_CTL_CLEAR_MMIO_ERROR,1,15,0,1);read_reg(AS02_CTL_STATUS,value);
  if(mmio_error || value[8]) $fatal(1,"safe parser recovery failed");
 end
endtask
initial begin
 #1 rst=1;dummy=$value$plusargs("case=%d",scenario);
 command_ready=1;admission_pause=1;parent_dma_drained=1;endpoint_quiescent=1;
 repeat(5) @(negedge clk);rst=0;
 case(scenario)
  0: begin
   read_reg(AS02_CTL_ID,value);if(value!==AS02_CTL_ID_VALUE) $fatal(1,"ID ABI mismatch");
   read_reg(AS02_CTL_ABI,value);if(value!==AS02_CTL_ABI_VALUE) $fatal(1,"version ABI mismatch");
   read_reg(AS02_CTL_FEATURES,value);if(value!==1) $fatal(1,"capability overclaim");
   stage;
   for(i=0;i<21;i=i+1) begin read_reg(AS02_CTL_STAGE+i*4,value);if(value!==words[i]) $fatal(1,"staging ABI word%d",i);end
   write_reg(AS02_CTL_STAGE+8,32'h55112266,4'b0101,0,4);
   read_reg(AS02_CTL_STAGE+8,value);if(value!==32'h8911cd66) $fatal(1,"byte strobe mismatch %h",value);
   if(accepted || command_valid) $fatal(1,"staging executed command");
  end
  1: begin
   stage;stop_command=1;write_reg(AS02_CTL_DOORBELL,1,15,0,0);
   if(!command_valid || accepted || last_queued_sequence!=17 || command!=2 || command_sequence!=17 ||
      cookie!==64'h1234567889abcdef || slot!=3 || key!=0 || pd!=17 || access!=7 ||
      virtual_address!==64'hfedcba9876543210 || length!=8193 || first_offset!=4093 || page_index!=255 ||
      dma_page!==64'hfffffffffffff000 || qp_number!=2 || peer_qp_number!=196 ||
      local_ip!==32'hc6120b02 || peer_ip!==32'hc6120b01 || rx_psn!=24'h987654 || tx_psn!=24'hfffffe)
    $fatal(1,"snapshot payload mismatch");
   for(i=0;i<21;i=i+1) saved_command[i*32+:32]=dut.snapshot[i];
   for(i=0;i<21;i=i+1) write_reg(AS02_CTL_STAGE+i*4,32'ha5a5a5a5,15,1,0);
   for(i=0;i<21;i=i+1) if(dut.snapshot[i]!==saved_command[i*32+:32]) $fatal(1,"staging changed queued command");
   write_reg(AS02_CTL_DOORBELL,1,15,0,1);if(!mmio_error || !command_valid || accepted) $fatal(1,"busy doorbell overwrote command");
   stop_command=0;command_ready=1;repeat(4) @(negedge clk);
   if(command_valid || accepted!=1) $fatal(1,"command accepted more than once");
   model_reply;write_reg(AS02_CTL_REPLY_ACK,18,15,0,0);
   if(!response_valid || acked || !mmio_error) $fatal(1,"wrong ACK discarded response");
   read_reg(AS02_CTL_REPLY_SEQ,value);if(value!=17) $fatal(1,"reply sequence");
   read_reg(AS02_CTL_REPLY_COOKIE_LO,value);if(value!==32'h89abcdef) $fatal(1,"reply cookie low");
   read_reg(AS02_CTL_REPLY_COOKIE_HI,value);if(value!==32'h12345678) $fatal(1,"reply cookie high");
   read_reg(AS02_CTL_REPLY_KEY,value);if(value!=11) $fatal(1,"reply key");
   write_reg(AS02_CTL_REPLY_ACK,17,15,0,0);if(response_valid || acked!=1) $fatal(1,"exact ACK failed");
   clear_error;
  end
  2: begin
   stage;write_reg(AS02_CTL_STAGE+16,32'h80000003,15,0,0);write_reg(AS02_CTL_DOORBELL,1,15,0,0);
   if(!mmio_error || command_valid || accepted) $fatal(1,"high slot bits aliased");
   parent_dma_drained=0;write_reg(AS02_CTL_CLEAR_MMIO_ERROR,1,15,0,0);if(!mmio_error) $fatal(1,"unproven clear");
   parent_dma_drained=1;clear_error;write_reg(AS02_CTL_STAGE+16,3,15,0,0);
   write_reg(AS02_CTL_DOORBELL,1,4'b0011,0,0);if(!mmio_error || accepted) $fatal(1,"partial doorbell executed");
   clear_error;
  end
  3: begin
   write_reg(AS02_CTL_REPLY_ACK,0,15,0,0);if(!mmio_error || response_ready || acked) $fatal(1,"empty ACK accepted");
   control_busy=1;write_reg(AS02_CTL_CLEAR_MMIO_ERROR,1,15,0,0);if(!mmio_error) $fatal(1,"busy clear");
   control_busy=0;fatal=1;write_reg(AS02_CTL_CLEAR_MMIO_ERROR,1,15,0,0);if(!mmio_error) $fatal(1,"fault cleared");
   fatal=0;clear_error;
  end
  4: begin
   stage;write_reg(12'h824,1,15,0,0);if(!mmio_error || accepted) $fatal(1,"high address alias");
   read_reg(AS02_CTL_STAGE+4,value);if(value!=2) $fatal(1,"high address mutated staging");clear_error;
   write_reg(12'h025,0,15,0,0);if(!mmio_error || accepted) $fatal(1,"unaligned write aliased");clear_error;
   read_reg(12'h025,value);if(value!=0 || !mmio_error) $fatal(1,"unaligned read not diagnosed");clear_error;
  end
  5: begin
   fatal=1;fatal_code=12;epoch_ready=1;qp_configured=1;run_requested=1;building=8'h12;active=8'h34;tainted=8'h56;
   last_sequence=32'habcdef01;
   read_reg(AS02_CTL_STATUS,value);if(value!==32'h6f8) $fatal(1,"status ABI mismatch %h",value);
   read_reg(AS02_CTL_ENTRY_STATE,value);if(value!==32'h563412) $fatal(1,"entry state ABI");
   read_reg(AS02_CTL_LAST_SEQUENCE,value);if(value!==32'habcdef01) $fatal(1,"last sequence ABI");
   read_reg(AS02_CTL_FATAL_CODE,value);if(value!=12) $fatal(1,"fatal code ABI");
  end
  default:$fatal(1,"unknown case");
 endcase
 $display("RESULT {\"pass_test\":true,\"scenario\":%0d,\"cycles\":%0d,\"axi_writes\":%0d,\"axi_reads\":%0d,\"accepted_commands\":%0d,\"acked_responses\":%0d}",scenario,cycles,writes,reads,accepted,acked);
 $finish;
end
endmodule
'''


class ControlRegsRTLTests(unittest.TestCase):
    reports={}

    @classmethod
    def setUpClass(cls):
        cls.paths=[*SOURCES,HEADER,Path(__file__)];cls.before={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in cls.paths}
        ports=RTL.read_text().split(')(\n',1)[1].split('\n);',1)[0];decl=[]
        for line in ports.splitlines():
            m=re.match(r'\s*(input|output) (?:wire|reg) (.*?)(?:=0)?[,]?$',line)
            if m:
                value=m[2].rstrip(',');decl.append(('reg ' if m[1]=='input' else 'wire ')+value+('=0;' if m[1]=='input' else ';'))
        abi=[]
        for name,value in re.findall(r'^#define (AS02_CTL_\w+) (0x[0-9a-fA-F]+|\d+)U$',HEADER.read_text(),re.M):
            abi.append(f"localparam {name}=32'h{int(value,0):x};")
        cls.directory=tempfile.TemporaryDirectory(prefix='as02-control-regs-');cls.path=Path(cls.directory.name)
        source=cls.path/'tb.v';source.write_text(TB.replace('// PORTS','\n'.join(decl)).replace('// ABI','\n'.join(abi)))
        r=subprocess.run(['iverilog','-g2012','-s','tb','-o',str(cls.path/'test.vvp'),str(source),*map(str,SOURCES)],capture_output=True,text=True,timeout=20)
        if r.returncode:raise RuntimeError(r.stdout+r.stderr)

    def case(self,n):
        r=subprocess.run(['vvp',str(self.path/'test.vvp'),f'+case={n}'],capture_output=True,text=True,timeout=10)
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        rows=[json.loads(l[7:]) for l in r.stdout.splitlines() if l.startswith('RESULT ')]
        self.assertEqual(len(rows),1,r.stdout);self.reports[self._testMethodName]=rows[0]

    def test_kernel_abi_staging_byte_strobes_and_independent_aw_w(self):self.case(0)
    def test_snapshot_stall_busy_doorbell_and_exact_reply_ack(self):self.case(1)
    def test_full_width_validation_and_partial_doorbell_denial(self):self.case(2)
    def test_stale_ack_and_unsafe_parser_error_clear_do_not_mutate_proof(self):self.case(3)
    def test_high_and_unaligned_addresses_never_alias_staging(self):self.case(4)
    def test_kernel_abi_status_and_entry_diagnostics(self):self.case(5)

    @classmethod
    def tearDownClass(cls):
        after={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in cls.paths};cls.directory.cleanup()
        if after!=cls.before:raise RuntimeError('control register test sources changed')
        if name:=os.environ.get('AS02_RNIC_CONTROL_REGS_REPORT'):
            p=Path(name)
            if not p.is_absolute():p=ROOT/p
            d=dict(scope='Actual AXI mailbox/Corundum AXI adapter, kernel ABI, controller MODEL',pass_test=len(cls.reports)==6,
                hardware_verified=False,board_integrated=False,completion_claim=False,tests=cls.reports,source_sha256=after)
            with p.open('x') as out:out.write(json.dumps(d,indent=2)+'\n')


if __name__=='__main__':unittest.main()
