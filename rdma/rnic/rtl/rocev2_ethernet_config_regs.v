// SPDX-License-Identifier: BSD-2-Clause-Views
// Copyright (c) 2026 jyohukuchan
// Privileged atomic Ethernet configuration at the actual whole-path safe
// boundary. No reset/cancel/revoke controls; rejected commit changes NO active
// field. Stage writes are harmless during traffic. This adapter returns AXI
// OKAY even on its timeout: callers MUST inspect sticky error/epoch/readback.
`resetall
`timescale 1ns/1ps
`default_nettype none
module rocev2_ethernet_config_regs #(
    parameter ADDR_WIDTH=12,
    parameter [31:0] EPOCH_MAX=32'hffffffff
)(
    input wire clk,
    input wire rst,
    input wire config_safe,
    output reg cfg_enable=0,
    output reg [31:0] cfg_epoch=0,
    output reg [47:0] cfg_local_mac=0,
    output reg [47:0] cfg_peer_mac=0,
    output reg [31:0] cfg_local_ip=0,
    output reg committed=0,
    output reg mmio_error=0,
    output reg [7:0] last_error=0,
    input wire [ADDR_WIDTH-1:0] s_axil_awaddr,
    input wire [2:0] s_axil_awprot,
    input wire s_axil_awvalid,
    output wire s_axil_awready,
    input wire [31:0] s_axil_wdata,
    input wire [3:0] s_axil_wstrb,
    input wire s_axil_wvalid,
    output wire s_axil_wready,
    output wire [1:0] s_axil_bresp,
    output wire s_axil_bvalid,
    input wire s_axil_bready,
    input wire [ADDR_WIDTH-1:0] s_axil_araddr,
    input wire [2:0] s_axil_arprot,
    input wire s_axil_arvalid,
    output wire s_axil_arready,
    output wire [31:0] s_axil_rdata,
    output wire [1:0] s_axil_rresp,
    output wire s_axil_rvalid,
    input wire s_axil_rready
);
localparam [7:0] ERR_ADDRESS=1,ERR_COMMAND=2,ERR_UNSAFE=3,ERR_FIELDS=4,
    ERR_EXHAUSTED=5,ERR_STICKY=6;
reg [31:0] stage[0:5];
wire [ADDR_WIDTH-1:0] wr_addr,rd_addr;
wire [31:0] wr_data;
wire [3:0] wr_strb;
wire wr_en,rd_en;
reg wr_ack=0,rd_ack=0;
reg [31:0] rd_data=0;
wire exhausted=cfg_epoch==EPOCH_MAX;
wire rd_known=(rd_addr>=32'h20 && rd_addr<=32'h34) ||
    (rd_addr>=32'h40 && rd_addr<=32'h54) ||
    rd_addr==0 || rd_addr==4 || rd_addr==8 || rd_addr==12 ||
    rd_addr==16 || rd_addr==20 || rd_addr==24;
wire bad_read=rd_en && !rd_ack && (rd_addr[1:0]!=0 || !rd_known);
wire [47:0] staged_local={stage[1][15:0],stage[0]};
wire [47:0] staged_peer={stage[3][15:0],stage[2]};
wire fields_valid=stage[1][31:16]==0 && stage[3][31:16]==0 && stage[5]<=1 &&
    (!stage[5][0] || (staged_local!=0 && staged_peer!=0 &&
     !staged_local[40] && !staged_peer[40] && stage[4]!=0 &&
     stage[4]!=32'hffffffff && stage[4][31:28]!=4'he));
initial begin
 if(ADDR_WIDTH<7 || ADDR_WIDTH>24 || EPOCH_MAX==0)
  begin $error("Invalid Ethernet configuration CSR geometry");$finish;end
end
axil_reg_if #(.DATA_WIDTH(32),.ADDR_WIDTH(ADDR_WIDTH),.STRB_WIDTH(4),.TIMEOUT(4)) adapter (
 .clk(clk),.rst(rst),
 .s_axil_awaddr(s_axil_awaddr),.s_axil_awprot(s_axil_awprot),.s_axil_awvalid(s_axil_awvalid),.s_axil_awready(s_axil_awready),
 .s_axil_wdata(s_axil_wdata),.s_axil_wstrb(s_axil_wstrb),.s_axil_wvalid(s_axil_wvalid),.s_axil_wready(s_axil_wready),
 .s_axil_bresp(s_axil_bresp),.s_axil_bvalid(s_axil_bvalid),.s_axil_bready(s_axil_bready),
 .s_axil_araddr(s_axil_araddr),.s_axil_arprot(s_axil_arprot),.s_axil_arvalid(s_axil_arvalid),.s_axil_arready(s_axil_arready),
 .s_axil_rdata(s_axil_rdata),.s_axil_rresp(s_axil_rresp),.s_axil_rvalid(s_axil_rvalid),.s_axil_rready(s_axil_rready),
 .reg_wr_addr(wr_addr),.reg_wr_data(wr_data),.reg_wr_strb(wr_strb),.reg_wr_en(wr_en),.reg_wr_wait(1'b0),.reg_wr_ack(wr_ack),
 .reg_rd_addr(rd_addr),.reg_rd_en(rd_en),.reg_rd_data(rd_data),.reg_rd_wait(1'b0),.reg_rd_ack(rd_ack));
integer i,b;
always @(posedge clk) begin
 wr_ack<=0;rd_ack<=0;
 if(rst) begin
  for(i=0;i<6;i=i+1)stage[i]<=0;
  cfg_enable<=0;cfg_epoch<=0;cfg_local_mac<=0;cfg_peer_mac<=0;cfg_local_ip<=0;
  committed<=0;mmio_error<=0;last_error<=0;rd_data<=0;
 end else begin
  if(wr_en && !wr_ack) begin
   wr_ack<=1;
   if(wr_addr[1:0]!=0) begin mmio_error<=1;last_error<=ERR_ADDRESS;end
   else if(wr_addr>=32'h20 && wr_addr<=32'h34) begin
    for(b=0;b<4;b=b+1)if(wr_strb[b])stage[(wr_addr-32'h20)>>2][b*8+:8]<=wr_data[b*8+:8];
   end else if(wr_addr==32'h10) begin
    if(wr_strb!=4'hf || wr_data!=1)begin mmio_error<=1;last_error<=ERR_COMMAND;end
    else if(!config_safe)begin mmio_error<=1;last_error<=ERR_UNSAFE;end
    else if(mmio_error || bad_read)begin mmio_error<=1;last_error<=ERR_STICKY;end
    else if(exhausted)begin mmio_error<=1;last_error<=ERR_EXHAUSTED;end
    else if(!fields_valid)begin mmio_error<=1;last_error<=ERR_FIELDS;end
    else begin
     cfg_local_mac<=staged_local;cfg_peer_mac<=staged_peer;cfg_local_ip<=stage[4];
     cfg_enable<=stage[5][0];cfg_epoch<=cfg_epoch+1'b1;committed<=1;
    end
   end else if(wr_addr==32'h14) begin
    if(wr_strb==4'hf && wr_data==1 && config_safe)begin mmio_error<=0;last_error<=0;end
    else begin mmio_error<=1;last_error<=ERR_UNSAFE;end
   end else begin mmio_error<=1;last_error<=ERR_ADDRESS;end
  end
  // A concurrent bad read wins over clear, never hides a protocol error.
  if(rd_en && !rd_ack) begin
   rd_ack<=1;rd_data<=0;
   if(rd_addr[1:0]!=0)begin mmio_error<=1;last_error<=ERR_ADDRESS;end
   else if(rd_addr>=32'h20 && rd_addr<=32'h34)rd_data<=stage[(rd_addr-32'h20)>>2];
   else case(rd_addr)
    'h00:rd_data<=32'h524e4531;
    'h04:rd_data<=32'h00010000;
    'h08:rd_data<={27'd0,exhausted,committed,mmio_error,config_safe,cfg_enable};
    'h0c:rd_data<=cfg_epoch;
    'h10,'h14:rd_data<=0;
    'h18:rd_data<={24'd0,last_error};
    'h40:rd_data<=cfg_local_mac[31:0];
    'h44:rd_data<={16'd0,cfg_local_mac[47:32]};
    'h48:rd_data<=cfg_peer_mac[31:0];
    'h4c:rd_data<={16'd0,cfg_peer_mac[47:32]};
    'h50:rd_data<=cfg_local_ip;
    'h54:rd_data<={31'd0,cfg_enable};
    default:begin mmio_error<=1;last_error<=ERR_ADDRESS;end
   endcase
  end
 end
end
endmodule
`resetall
