// SPDX-License-Identifier: BSD-2-Clause-Views
// Replay genuine recorded selected1000 seeds. Producer/AXI host are models.
`timescale 1ns/1ps
module tb;
reg clk=0,rst=1,parent_fault=0,s_selected_valid=0;
reg [999:0] s_selected=0;
wire s_selected_ready,configuration_guard,fault;
wire [7:0] queue_guard,fault_code;
reg [11:0] s_axil_awaddr=0,s_axil_araddr=0;
reg [2:0] s_axil_awprot=0,s_axil_arprot=0;
reg s_axil_awvalid=0,s_axil_wvalid=0,s_axil_bready=0,s_axil_arvalid=0,s_axil_rready=0;
reg [31:0] s_axil_wdata=0;reg [3:0] s_axil_wstrb=4'hf;
wire s_axil_awready,s_axil_wready,s_axil_bvalid,s_axil_arready,s_axil_rvalid;
wire [1:0] s_axil_bresp,s_axil_rresp;wire [31:0] s_axil_rdata;
rocev2_fatal_event_mmio dut(.*);
always #2 clk=~clk;
integer mode=0,cycles=0,checks=0,n,f;
reg [31:0] seed0[0:31],seed1[0:31],word;
reg [1023:0] original=0;
always @(posedge clk)if(!rst)begin cycles=cycles+1;if(cycles>100000)$fatal(1,"bounded FEC cycle limit");end
task tick;begin @(posedge clk);@(negedge clk);end endtask
task read_reg;input [11:0] addr;output [31:0] value;
 begin
  @(negedge clk);s_axil_araddr=addr;s_axil_arvalid=1;
  @(posedge clk);while(!s_axil_arready)@(posedge clk);
  @(negedge clk);s_axil_arvalid=0;
  while(!s_axil_rvalid)@(negedge clk);
  value=s_axil_rdata;
  if(s_axil_rresp!==0)$fatal(1,"FEC AXI read response");
  repeat(5)begin tick;if(!s_axil_rvalid || s_axil_rdata!==value || s_axil_rresp!==0)$fatal(1,"FEC RDATA lifetime");end
  s_axil_rready=1;tick;s_axil_rready=0;checks=checks+1;
 end
endtask
task write_reg;input [31:0] value;input [3:0] strb;input wfirst;
 begin
  @(negedge clk);s_axil_awaddr=12'h010;s_axil_wdata=value;s_axil_wstrb=strb;
  if(wfirst)begin
   s_axil_wvalid=1;@(posedge clk);while(!s_axil_wready)@(posedge clk);@(negedge clk);s_axil_wvalid=0;
   repeat(17)tick;s_axil_awvalid=1;@(posedge clk);while(!s_axil_awready)@(posedge clk);@(negedge clk);s_axil_awvalid=0;
  end else begin
   s_axil_awvalid=1;@(posedge clk);while(!s_axil_awready)@(posedge clk);@(negedge clk);s_axil_awvalid=0;
   repeat(17)tick;s_axil_wvalid=1;@(posedge clk);while(!s_axil_wready)@(posedge clk);@(negedge clk);s_axil_wvalid=0;
  end
  while(!s_axil_bvalid)@(negedge clk);
  repeat(17)begin tick;if(!s_axil_bvalid || s_axil_bresp!==0)$fatal(1,"FEC BRESP lifetime");end
  s_axil_bready=1;tick;s_axil_bready=0;checks=checks+1;
 end
endtask
task capture;
 begin
  s_selected_valid=1;#1;
  if(!s_selected_ready)$fatal(1,"valid actual recorded selected1000 not accepted");
  tick;s_selected_valid=0;
  if(fault || !configuration_guard || queue_guard!==8'h04 || s_selected_ready)$fatal(1,"FEC retained event guard");
  read_reg(12'h00c,word);if(word!==1)$fatal(1,"FEC visible status");
 end
endtask
task bad;
 begin
  repeat(8)tick;
  if(!fault || !configuration_guard || queue_guard!==8'hff || s_selected_ready)$fatal(1,"FEC bad ownership failed closed");
 end
endtask
initial begin
 if(!$value$plusargs("MODE=%d",mode))mode=0;
 $readmemh("seed0.hex",seed0);$readmemh("seed1.hex",seed1);
 for(n=0;n<32;n=n+1)original[n*32+:32]=mode==1 ? seed1[n]:seed0[n];
 repeat(8)tick;rst=0;repeat(8)tick;
 read_reg(0,word);if(word!==32'h46454331)$fatal(1,"FEC signature");
 read_reg(4,word);if(word!==32'h00010000)$fatal(1,"FEC ABI");
 read_reg(8,word);if(word!==15)$fatal(1,"FEC features are not a WC/drain capability");
 read_reg(12,word);if(word!==0)$fatal(1,"FEC reset status");
 read_reg(12'h018,word);if(word!==0)$fatal(1,"FEC reset event sequence");
 s_selected=original[999:0];
 if(mode==3)begin s_selected[999:992]=0;s_selected_valid=1;bad;end
 else if(mode==4)begin s_selected[500]=1'bx;s_selected_valid=1;bad;end
 else if(mode==5)begin s_selected_valid=1'bx;bad;end
 else begin
  capture;
  if(mode<=1)begin
   f=$fopen(mode==0 ? "readback-0.hex":"readback-1.hex","w");if(!f)$fatal(1,"FEC readback file");
   for(n=0;n<32;n=n+1)begin
    read_reg(12'h040+n*4,word);
    if(word!==original[n*32+:32])$fatal(1,"FEC lost full selected1000 word%0d",n);
    $fdisplay(f,"%08x",word);
   end
   $fclose(f);
   repeat(71)tick;read_reg(12'h018,word);if(word!==1)$fatal(1,"FEC sequence changed without ACK");
   write_reg(1,4'hf,mode==1);read_reg(12'h014,word);if(word!==1)$fatal(1,"FEC exact ACK");
   read_reg(12'h00c,word);if(word!==0 || configuration_guard || fault)$fatal(1,"FEC mailbox ACK—not QP/drain release");
   write_reg(1,4'hf,0);if(fault)$fatal(1,"FEC idempotent exact ACK");
  end else if(mode==2)begin
   write_reg(1,4'hf,0);s_selected_valid=1;bad;
  end else if(mode==6)begin
   parent_fault=1;bad;read_reg(12'h00c,word);if(word!==3)$fatal(1,"FEC parent fault lost retained event");
  end else if(mode==7 || mode==8)begin
   write_reg(mode==7 ? 2:1,mode==8 ? 4'h7:4'hf,0);bad;
   read_reg(12'h018,word);if(word!==1)$fatal(1,"FEC invalid ACK advanced sequence");
   read_reg(12'h014,word);if(word!==0)$fatal(1,"FEC invalid ACK dropped event");
  end else if(mode==9)begin
   // Independent AXI read response remains stable across notification ACK.
   s_axil_araddr=12'h0bc;s_axil_arvalid=1;@(posedge clk);while(!s_axil_arready)@(posedge clk);
   @(negedge clk);s_axil_arvalid=0;while(!s_axil_rvalid)@(negedge clk);
   if(s_axil_rdata!==7)$fatal(1,"FEC read stall initial data");
   write_reg(1,4'hf,1);
   if(!s_axil_rvalid || s_axil_rdata!==7 || s_axil_rresp!==0 || configuration_guard)$fatal(1,"FEC read payload changed on concurrent ACK");
   s_axil_rready=1;tick;s_axil_rready=0;
  end else if(mode==10)begin
   write_reg(1,4'hf,0);
   // Synthetic successor tests mailbox sequencing ONLY, not native QP rearm.
   s_selected[843:780]=2;capture;write_reg(1,4'hf,0);
   read_reg(12'h00c,word);if(word!==1 || fault)$fatal(1,"FEC stale ACK cleared synthetic successor");
   read_reg(12'h018,word);if(word!==2)$fatal(1,"FEC successor sequence");
   write_reg(2,4'hf,0);if(fault)$fatal(1,"FEC successor exact ACK");
  end
 end
 $display("FATAL_MMIO_RESULT {\"pass_test\":true,\"mode\":%0d,\"checks\":%0d,\"full_record_bits\":1000,\"clock_ns\":4,\"native_live_wiring\":false,\"QP_drain_unpin\":false}",mode,checks);
 $finish;
end
endmodule
