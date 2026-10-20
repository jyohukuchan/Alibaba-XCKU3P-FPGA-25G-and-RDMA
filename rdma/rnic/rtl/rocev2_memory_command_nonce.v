// SPDX-License-Identifier: BSD-2-Clause-Views
// AFTER every memory client, BEFORE the actual shared paged backend. Capture
// the complete immutable logical command; give EACH backend command a fresh
// nonwrapping physical nonce. Only its genuine matching status is translated
// back to the saved logical tag. This does not grant MR/DMA authority or
// replace actual backend data/EOF/fence/descriptor completion requirements.
// Whole-NIC reset is not a safe per-operation cancellation/unpin mechanism.
`resetall
`timescale 1ns/1ps
`default_nettype none
module rocev2_memory_command_nonce #(
 parameter NONCE_WIDTH=16
)(
 input wire clk,input wire rst,input wire enable,input wire parent_fault,
 input wire s_command_write,input wire [63:0] s_command_offset,
 input wire [31:0] s_command_length,input wire [31:0] s_command_key,
 input wire [15:0] s_command_tag,input wire s_command_valid,output wire s_command_ready,
 output reg m_command_write=0,output reg [63:0] m_command_offset=0,
 output reg [31:0] m_command_length=0,output reg [31:0] m_command_key=0,
 output reg [15:0] m_command_tag=0,output reg m_command_valid=0,input wire m_command_ready,
 input wire [15:0] s_status_tag,input wire [7:0] s_status_error,
 input wire s_status_valid,output wire s_status_ready,
 output reg [15:0] m_status_tag=0,output reg [7:0] m_status_error=0,
 output reg m_status_valid=0,input wire m_status_ready,
 output wire busy,output wire configuration_guard,output reg exhausted=0,
 output reg fault=0,output reg [7:0] fault_code=0,
 output reg [31:0] command_count=0,output reg [31:0] status_count=0,output reg [31:0] retired_count=0
);
reg active=0,issued=0,receipt_seen=0;
reg [15:0] logical_tag=0;
reg [NONCE_WIDTH-1:0] next_nonce=1;
wire stopped=fault || parent_fault!==1'b0;
wire command_known=(^{s_command_write,s_command_offset,s_command_length,s_command_key,s_command_tag})!==1'bx;
wire [64:0] command_end={1'b0,s_command_offset}+{33'd0,s_command_length};
wire command_shape=command_known && s_command_tag!=0 && s_command_length!=0 &&
 s_command_length<=4096 && command_end<=65'h10000000000000000;
assign s_command_ready=enable && !active && !exhausted && command_shape && !stopped && !rst;
wire command_fire=m_command_valid && m_command_ready;
wire status_known=(^{s_status_tag,s_status_error})!==1'bx;
wire good_status=active && (issued || command_fire) && !receipt_seen && status_known && s_status_tag==m_command_tag;
// Do not acknowledge an old/foreign receipt as though it belonged to the
// current command. Consume it only into sticky quarantine, with no translation.
assign s_status_ready=!rst && (good_status ? !m_status_valid:1'b1);
wire status_fire=s_status_valid && s_status_ready;
wire bad_offer=(s_command_valid!==1'b0 && s_command_valid!==1'b1) ||
 (s_status_valid!==1'b0 && s_status_valid!==1'b1) ||
 (!active && s_command_valid && !command_shape) || (status_fire && !good_status);
assign busy=active || stopped || bad_offer;
assign configuration_guard=busy || s_command_valid!==1'b0;
initial if(NONCE_WIDTH<1 || NONCE_WIDTH>16)$fatal(1,"unreviewed physical command nonce width");
always @(posedge clk)begin
 if(rst)begin
  active<=0;issued<=0;receipt_seen<=0;logical_tag<=0;next_nonce<=1;
  m_command_write<=0;m_command_offset<=0;m_command_length<=0;m_command_key<=0;
  m_command_tag<=0;m_command_valid<=0;m_status_tag<=0;m_status_error<=0;m_status_valid<=0;
  exhausted<=0;fault<=0;fault_code<=0;command_count<=0;status_count<=0;retired_count<=0;
 end else begin
  if(s_command_valid && s_command_ready)begin
   active<=1;issued<=0;receipt_seen<=0;logical_tag<=s_command_tag;
   m_command_write<=s_command_write;m_command_offset<=s_command_offset;
   m_command_length<=s_command_length;m_command_key<=s_command_key;
   m_command_tag<={{(16-NONCE_WIDTH){1'b0}},next_nonce};m_command_valid<=1;
   command_count<=command_count+1'b1;
   if(&next_nonce)exhausted<=1;else next_nonce<=next_nonce+1'b1;
  end
  // Offered commands and logical statuses remain stable across late faults.
  if(command_fire)begin m_command_valid<=0;issued<=1;end
  if(status_fire && good_status)begin
   receipt_seen<=1;m_status_tag<=logical_tag;m_status_error<=s_status_error;m_status_valid<=1;
   status_count<=status_count+1'b1;
  end
  if(m_status_valid && m_status_ready)begin
   m_status_valid<=0;retired_count<=retired_count+1'b1;
   if(!stopped && !bad_offer)begin active<=0;issued<=0;end
  end
  if(!fault)begin
   if(parent_fault!==1'b0)begin fault<=1;fault_code<=8'hd4;end
   else if(bad_offer)begin fault<=1;fault_code<=8'hd5;end
  end
 end
end
endmodule
`resetall
