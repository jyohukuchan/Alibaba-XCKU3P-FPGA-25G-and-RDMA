// SPDX-License-Identifier: BSD-2-Clause-Views
// One trusted nonzero WRITE/SEND owner -> actual bounded child DMA executors.
// A child context is derived ONLY from the saved full WR, never a narrowed
// HLS address. Each read/re-read has a fresh nonwrapping C001..ffff tag.
// Integration MUST isolate physical identity with the shared nonreusing
// command translator (or reserve this namespace against every other client).
// Last-fragment replays remain owned even after the aggregate memory event;
// only the identical genuine whole-WR CQ retirement can release this lease.
// This component is not native wire/CQ integration or physical qualification.
`resetall
`timescale 1ns/1ps
`default_nettype none
module rocev2_segmented_source_executor #(
 parameter MAX_QPS=8,parameter TAG_SEQUENCE_WIDTH=14
)(
 input wire clk,input wire rst,input wire enable,input wire parent_fault,
 input wire [747:0] s_owner_context,input wire s_owner_valid,output wire s_owner_ready,
 input wire [95:0] s_hls_command,input wire s_hls_command_valid,output wire s_hls_command_ready,
 output wire [511:0] m_axis_hls_tdata,output wire [63:0] m_axis_hls_tkeep,
 output wire m_axis_hls_tlast,output wire m_axis_hls_tvalid,input wire m_axis_hls_tready,
 output wire m_memory_command_write,output wire [63:0] m_memory_command_offset,
 output wire [31:0] m_memory_command_length,output wire [31:0] m_memory_command_key,
 output wire [15:0] m_memory_command_tag,output wire m_memory_command_valid,input wire m_memory_command_ready,
 input wire [511:0] s_axis_memory_tdata,input wire [63:0] s_axis_memory_tkeep,
 input wire s_axis_memory_tlast,input wire s_axis_memory_tvalid,output wire s_axis_memory_tready,
 input wire [15:0] s_memory_status_tag,input wire [7:0] s_memory_status_error,
 input wire s_memory_status_valid,output wire s_memory_status_ready,
 output wire [747:0] m_memory_event_context,output reg [7:0] m_memory_event_error=0,
 output reg m_memory_event_valid=0,input wire m_memory_event_ready,
 input wire [747:0] s_retire_context,input wire s_retire_valid,output wire s_retire_ready,
 output wire [MAX_QPS-1:0] queue_guard,output wire busy,
 output reg fault=0,output reg [7:0] fault_code=0,output reg tags_exhausted=0,
 output reg [31:0] owner_count=0,output reg [31:0] fragment_count=0,
 output reg [31:0] replay_count=0,output reg [31:0] retired_count=0
);
localparam PICK=0,ARM=1,OFFER=2,TRANSFER=3;
reg active=0;reg [1:0] state=PICK;
reg [747:0] owner=0,child_context=0;
reg [31:0] next_offset=0,previous_offset=0,selected_offset=0;
reg previous_valid=0,selected_replay=0,whole_complete=0,event_sent=0;
reg [95:0] held_raw=0;
reg [TAG_SEQUENCE_WIDTH-1:0] next_tag=1;
wire stopped=fault || parent_fault!==1'b0;
wire [23:0] in_qpn=s_owner_context[395:372];
wire [15:0] in_opcode=s_owner_context[339:324];
wire [31:0] in_length=s_owner_context[307:276];
wire [64:0] va_end={1'b0,s_owner_context[243:180]}+{33'd0,in_length};
wire [64:0] offset_end={1'b0,s_owner_context[179:116]}+{33'd0,in_length};
wire [64:0] remote_end={1'b0,s_owner_context[115:52]}+{33'd0,in_length};
wire owner_ok=(^s_owner_context)!==1'bx && in_qpn<MAX_QPS &&
 s_owner_context[459:396]!=0 && s_owner_context[523:460]!=0 && s_owner_context[355:340]!=0 &&
 (in_opcode==1 || (in_opcode==3 && s_owner_context[115:20]==0)) &&
 s_owner_context[747:588]==0 && s_owner_context[323:309]==0 && s_owner_context[19:0]==3 &&
 in_length!=0 && in_length<=1048576 &&
 va_end<=65'h10000000000000000 && offset_end<=65'h10000000000000000 && remote_end<=65'h10000000000000000;
assign s_owner_ready=enable && !active && !stopped && !rst && !tags_exhausted && owner_ok;
wire [23:0] qpn=owner[395:372];wire [31:0] length=owner[307:276];
function [31:0] bytes_at;input [31:0] total;input [31:0] off;
 begin bytes_at=total-off>4096 ? 4096:total-off;end
endfunction
function [95:0] raw_at;input [747:0] context_value;input [31:0] off;
 reg [63:0] va;reg [31:0] bytes,total;reg [23:0] local_qpn;reg last;
 begin
  total=context_value[307:276];local_qpn=context_value[395:372];
  va=context_value[243:180]+off;bytes=bytes_at(total,off);last=off+bytes==total;
  raw_at={2'd0,local_qpn[9:0],va[51:48],1'b1,1'b0,va[52],last,bytes[27:0],va[47:0]};
 end
endfunction
wire raw_known=(^s_hls_command)!==1'bx;
wire next_match=next_offset<length && raw_known && s_hls_command==raw_at(owner,next_offset);
wire previous_match=previous_valid && raw_known && s_hls_command==raw_at(owner,previous_offset);
wire pick_ok=active && state==PICK && !stopped && !rst && !tags_exhausted && (next_match || previous_match);
wire [31:0] picked_offset=next_match ? next_offset:previous_offset;
wire [31:0] picked_length=bytes_at(length,picked_offset);
reg [747:0] picked_context;
always @*begin
 picked_context=owner;
 picked_context[355:340]=16'hc000|{{(16-TAG_SEQUENCE_WIDTH){1'b0}},next_tag};
 picked_context[307:276]=picked_length;
 picked_context[243:180]=owner[243:180]+picked_offset;
 picked_context[179:116]=owner[179:116]+picked_offset;
 picked_context[115:52]=owner[339:324]==3 ? 64'd0:owner[115:52]+picked_offset;
end
wire child_owner_ready,child_raw_ready,child_busy,child_fault;
wire [7:0] child_fault_code;wire [MAX_QPS-1:0] child_guard;
wire [747:0] child_event;wire [7:0] child_error;wire child_event_valid;
wire child_event_match=(^child_event)!==1'bx && child_event==child_context;
wire child_event_ready=active && state==TRANSFER && child_event_match && !rst;
wire offer_raw=active && state==OFFER;
// The outer validator checked the real HLS whole-WR ctl bit. A child is one
// COMPLETE bounded DMA transaction, so only its ctl bit is translated to1.
wire [95:0] child_raw=held_raw|96'h000010000000000000000000;
assign s_hls_command_ready=offer_raw && s_hls_command_valid && s_hls_command==held_raw && child_raw_ready && !rst;
wire held_bad=offer_raw && (s_hls_command_valid!==1'b1 || s_hls_command!==held_raw);
wire retire_match=(^s_retire_context)!==1'bx && s_retire_context==owner;
assign s_retire_ready=active && state==PICK && whole_complete && event_sent && !child_busy &&
 s_hls_command_valid===1'b0 && retire_match && !stopped && !bad_offer && !rst;
assign m_memory_event_context=owner;
assign busy=active || child_busy || stopped || bad_offer;
wire [MAX_QPS-1:0] owned_guard=active ? ({{(MAX_QPS-1){1'b0}},1'b1}<<qpn):{MAX_QPS{1'b0}};
wire [MAX_QPS-1:0] offered_guard=s_owner_valid && owner_ok ?
 ({{(MAX_QPS-1){1'b0}},1'b1}<<in_qpn):{MAX_QPS{1'b0}};
assign queue_guard=(stopped || child_fault || bad_offer) ? {MAX_QPS{1'b1}}:owned_guard|offered_guard|child_guard;
wire bad_offer=(s_owner_valid!==1'b0 && s_owner_valid!==1'b1) ||
 (s_hls_command_valid!==1'b0 && s_hls_command_valid!==1'b1) ||
 (s_retire_valid!==1'b0 && s_retire_valid!==1'b1) ||
 (!active && s_owner_valid && !owner_ok) ||
 (s_hls_command_valid && (!active || (state==PICK && (!pick_ok || tags_exhausted)))) || held_bad ||
 (s_retire_valid && (!active || !retire_match)) ||
 (child_event_valid && (!active || state!=TRANSFER || !child_event_match));
rocev2_segmented_child_executor #(.MAX_QPS(MAX_QPS)) child(
 .clk(clk),.rst(rst),.enable(enable),.halt(stopped),
 .s_owner_context(child_context),.s_owner_valid(active && state==ARM),.s_owner_ready(child_owner_ready),
 .s_read_response_context(748'd0),.s_read_response_valid(1'b0),.s_read_response_ready(),
 .s_hls_read_command(child_raw),.s_hls_read_command_valid(offer_raw),.s_hls_read_command_ready(child_raw_ready),
 .s_hls_write_command(96'd0),.s_hls_write_command_valid(1'b0),.s_hls_write_command_ready(),
 .s_axis_hls_write_tdata(512'd0),.s_axis_hls_write_tkeep(64'd0),.s_axis_hls_write_tlast(1'b0),
 .s_axis_hls_write_tvalid(1'b0),.s_axis_hls_write_tready(),
 .m_axis_hls_read_tdata(m_axis_hls_tdata),.m_axis_hls_read_tkeep(m_axis_hls_tkeep),
 .m_axis_hls_read_tlast(m_axis_hls_tlast),.m_axis_hls_read_tvalid(m_axis_hls_tvalid),.m_axis_hls_read_tready(m_axis_hls_tready),
 .m_memory_command_write(m_memory_command_write),.m_memory_command_offset(m_memory_command_offset),
 .m_memory_command_length(m_memory_command_length),.m_memory_command_key(m_memory_command_key),
 .m_memory_command_tag(m_memory_command_tag),.m_memory_command_valid(m_memory_command_valid),.m_memory_command_ready(m_memory_command_ready),
 .m_axis_memory_write_tdata(),.m_axis_memory_write_tkeep(),.m_axis_memory_write_tlast(),.m_axis_memory_write_tvalid(),.m_axis_memory_write_tready(1'b0),
 .s_axis_memory_read_tdata(s_axis_memory_tdata),.s_axis_memory_read_tkeep(s_axis_memory_tkeep),
 .s_axis_memory_read_tlast(s_axis_memory_tlast),.s_axis_memory_read_tvalid(s_axis_memory_tvalid),.s_axis_memory_read_tready(s_axis_memory_tready),
 .s_memory_status_tag(s_memory_status_tag),.s_memory_status_error(s_memory_status_error),
 .s_memory_status_valid(s_memory_status_valid),.s_memory_status_ready(s_memory_status_ready),
 .m_memory_event_context(child_event),.m_memory_event_error(child_error),.m_memory_event_valid(child_event_valid),.m_memory_event_ready(child_event_ready),
 .downstream_queue_guard(owned_guard),.queue_guard(child_guard),.busy(child_busy),.fault(child_fault),.fault_code(child_fault_code),
 .owner_count(),.command_count(),.memory_status_count());
initial if(MAX_QPS<1 || MAX_QPS>8 || TAG_SEQUENCE_WIDTH<1 || TAG_SEQUENCE_WIDTH>14)
 $fatal(1,"unreviewed segmented source QP/tag capacity");
always @(posedge clk)begin
 if(rst)begin
  active<=0;state<=PICK;owner<=0;child_context<=0;next_offset<=0;previous_offset<=0;
  selected_offset<=0;previous_valid<=0;selected_replay<=0;whole_complete<=0;event_sent<=0;held_raw<=0;
  next_tag<=1;tags_exhausted<=0;fault<=0;fault_code<=0;m_memory_event_valid<=0;m_memory_event_error<=0;
  owner_count<=0;fragment_count<=0;replay_count<=0;retired_count<=0;
 end else begin
  if(s_owner_valid && s_owner_ready)begin
   owner<=s_owner_context;active<=1;state<=PICK;next_offset<=0;previous_offset<=0;
   previous_valid<=0;whole_complete<=0;event_sent<=0;m_memory_event_error<=0;owner_count<=owner_count+1'b1;
  end
  if(s_hls_command_valid && pick_ok)begin
   child_context<=picked_context;selected_offset<=picked_offset;selected_replay<=!next_match;
   held_raw<=s_hls_command;state<=ARM;
   if(&next_tag)tags_exhausted<=1;else next_tag<=next_tag+1'b1;
  end
  if(active && state==ARM && child_owner_ready)state<=OFFER;
  if(offer_raw && child_raw_ready)state<=TRANSFER;
  if(child_event_valid && child_event_ready)begin
   if(child_error==0 && !stopped && !child_fault && !bad_offer)begin
    if(selected_replay)replay_count<=replay_count+1'b1;
    else begin
     previous_offset<=selected_offset;previous_valid<=1;next_offset<=selected_offset+bytes_at(length,selected_offset);
     fragment_count<=fragment_count+1'b1;
     if(selected_offset+bytes_at(length,selected_offset)==length)begin whole_complete<=1;m_memory_event_valid<=1;end
    end
    state<=PICK;
   end else if(child_error!=0 && !event_sent && !m_memory_event_valid)begin m_memory_event_error<=child_error;m_memory_event_valid<=1;end
  end
  if(m_memory_event_valid && m_memory_event_ready)begin m_memory_event_valid<=0;event_sent<=1;end
  if(s_retire_valid && s_retire_ready)begin active<=0;retired_count<=retired_count+1'b1;end
  if(!fault)begin
   if(parent_fault!==1'b0)begin fault<=1;fault_code<=8'hd1;end
   else if(child_fault)begin fault<=1;fault_code<=child_fault_code;end
   else if(bad_offer)begin fault<=1;fault_code<=8'hd2;end
   else if(child_event_valid && child_event_ready && child_error!=0)begin fault<=1;fault_code<=8'hd3;end
  end
 end
end
endmodule
`resetall
