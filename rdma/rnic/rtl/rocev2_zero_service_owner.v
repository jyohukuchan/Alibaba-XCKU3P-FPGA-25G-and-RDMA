// SPDX-License-Identifier: BSD-2-Clause-Views
// Genuine admitted ordinary zero WRITE/READ owner; reserve MAC FIRST, then
// deliver identical344-bit owner to the SAME real HLS. No RQ/Atomic alias.
`resetall
`timescale 1ns/1ps
`default_nettype none
module rocev2_zero_service_owner (
 input wire clk,input wire rst,input wire parent_fault,
 input wire [527:0] s_owner,input wire s_valid,output wire s_ready,
 output wire [527:0] m_mac_owner,output wire m_mac_valid,input wire m_mac_ready,
 output wire [343:0] m_hls_owner,output wire m_hls_valid,input wire m_hls_ready,
 output wire configuration_guard,output wire [7:0] queue_guard,
 output reg fault=0,output reg [31:0] reserved_count=0,output reg [31:0] delivered_count=0
);
localparam IDLE=0,MAC=1,HLS=2;
reg [1:0] state=IDLE;reg [527:0] owner=0;
wire halted=fault || parent_fault!==1'b0;
wire owner_ok=(^s_owner)!==1'bx && s_owner[23:0]<8 && s_owner[103:40]!=0 &&
 s_owner[167:104]!=0 && s_owner[183:168]!=0 && s_owner[343:312]==0 &&
 (s_owner[215:208]==8'h0a || s_owner[215:208]==8'h0c) &&
 s_owner[527:480]!=0 && !s_owner[520] && s_owner[479:432]!=0 && !s_owner[472];
wire bad_offer=(s_valid!==1'b0 && s_valid!==1'b1) || (state==IDLE && s_valid && !owner_ok);
assign s_ready=state==IDLE && owner_ok && !halted && !rst;
assign m_mac_owner=owner;assign m_hls_owner=owner[343:0];
// Once offered, preserve valid and immutable data through a late fault.
assign m_mac_valid=state==MAC && !rst;assign m_hls_valid=state==HLS && !rst;
assign configuration_guard=state!=IDLE || halted || s_valid!==1'b0;
assign queue_guard=(halted || bad_offer) ? 8'hff : state!=IDLE ? 8'h01<<owner[23:0] :
 (s_valid && owner_ok) ? 8'h01<<s_owner[23:0]:8'd0;
always @(posedge clk)begin
 if(rst)begin state<=IDLE;owner<=0;fault<=0;reserved_count<=0;delivered_count<=0;end
 else begin
  if(s_valid && s_ready)begin owner<=s_owner;state<=MAC;end
  if(m_mac_valid && m_mac_ready)begin state<=HLS;reserved_count<=reserved_count+1'b1;end
  if(m_hls_valid && m_hls_ready)begin
   state<=IDLE;delivered_count<=delivered_count+1'b1;
   if(halted || bad_offer)fault<=1;else owner<=0;
  end
  if(parent_fault!==1'b0 || bad_offer)fault<=1;
 end
end
endmodule
`resetall
