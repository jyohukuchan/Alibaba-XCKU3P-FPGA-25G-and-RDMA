// SPDX-License-Identifier: BSD-2-Clause-Views
// One authorized READ owner/one protected placement -> bounded real unpad/DMA
// children. Full VA/key/relative offset authority comes ONLY from saved owner.
// A001..Afff child tags never wrap. Integration MUST translate these through
// the shared nonreusing physical-command nonce domain (or reserve namespace).
// Every data/status joins before one whole-WR memory event; only identical
// genuine CQ retirement releases the outer lease. No RX/HLS/native/physical
// or memory-visibility proof is implied by modeled token/backend/CQ inputs.
`resetall
`timescale 1ns/1ps
`default_nettype none
module rocev2_segmented_read_executor #(
 parameter MAX_QPS=8,parameter TAG_SEQUENCE_WIDTH=12
)(
 input wire clk,input wire rst,input wire enable,input wire parent_fault,
 input wire [747:0] s_owner_context,input wire s_owner_valid,output wire s_owner_ready,
 input wire [747:0] s_read_response_context,input wire s_read_response_valid,output wire s_read_response_ready,
 input wire [95:0] s_hls_command,input wire s_hls_command_valid,output wire s_hls_command_ready,
 input wire [511:0] s_axis_hls_tdata,input wire [63:0] s_axis_hls_tkeep,
 input wire s_axis_hls_tlast,input wire s_axis_hls_tvalid,output wire s_axis_hls_tready,
 output wire m_memory_command_write,output wire [63:0] m_memory_command_offset,
 output wire [31:0] m_memory_command_length,output wire [31:0] m_memory_command_key,
 output wire [15:0] m_memory_command_tag,output wire m_memory_command_valid,input wire m_memory_command_ready,
 output wire [511:0] m_axis_memory_tdata,output wire [63:0] m_axis_memory_tkeep,
 output wire m_axis_memory_tlast,output wire m_axis_memory_tvalid,input wire m_axis_memory_tready,
 input wire [15:0] s_memory_status_tag,input wire [7:0] s_memory_status_error,
 input wire s_memory_status_valid,output wire s_memory_status_ready,
 output wire [747:0] m_memory_event_context,output reg [7:0] m_memory_event_error=0,
 output reg m_memory_event_valid=0,input wire m_memory_event_ready,
 input wire [747:0] s_retire_context,input wire s_retire_valid,output wire s_retire_ready,
 input wire [MAX_QPS-1:0] downstream_queue_guard,
 output wire [MAX_QPS-1:0] queue_guard,output wire busy,
 output reg fault=0,output reg [7:0] fault_code=0,output reg tags_exhausted=0,
 output reg [31:0] owner_count=0,output reg [31:0] fragment_count=0,
 output reg [31:0] retired_count=0,output wire [31:0] discarded_padding_bytes
);
localparam PICK=0,ARM=1,TOKEN=2,COMMAND=3,TRANSFER=4;
reg [2:0] state=PICK;
reg active=0,placement_seen=0,whole_complete=0,event_sent=0,hls_input_done=0;
reg [747:0] owner=0,child_context=0;
reg [95:0] held_raw=0;
reg [31:0] next_offset=0,selected_bytes=0;
reg [TAG_SEQUENCE_WIDTH-1:0] next_tag=1;
wire stopped=fault || parent_fault!==1'b0;
wire [23:0] in_qpn=s_owner_context[395:372];
wire [31:0] in_length=s_owner_context[307:276];
wire [64:0] va_end={1'b0,s_owner_context[243:180]}+{33'd0,in_length};
wire [64:0] offset_end={1'b0,s_owner_context[179:116]}+{33'd0,in_length};
wire [64:0] remote_end={1'b0,s_owner_context[115:52]}+{33'd0,in_length};
wire owner_ok=(^s_owner_context)!==1'bx && in_qpn<MAX_QPS &&
 s_owner_context[459:396]!=0 && s_owner_context[523:460]!=0 && s_owner_context[355:340]!=0 &&
 s_owner_context[339:324]==2 && s_owner_context[747:588]==0 &&
 s_owner_context[323:309]==0 && s_owner_context[19:0]==3 && in_length!=0 && in_length<=1048576 &&
 va_end<=65'h10000000000000000 && offset_end<=65'h10000000000000000 && remote_end<=65'h10000000000000000;
wire [23:0] qpn=owner[395:372];wire [31:0] length=owner[307:276];
wire guards_known=(^downstream_queue_guard)!==1'bx;
wire held_guard=qpn<MAX_QPS && guards_known && downstream_queue_guard[qpn]===1'b1;
wire placement_match=(^s_read_response_context)!==1'bx && s_read_response_context==owner;
assign s_read_response_ready=active && !placement_seen && placement_match && held_guard && !stopped && !rst;
function [31:0] bytes_at;input [31:0] total;input [31:0] off;
 begin bytes_at=total-off>4096 ? 4096:total-off;end
endfunction
function [95:0] raw_at;input [747:0] context_value;input [31:0] off;
 reg [63:0] va;reg [31:0] bytes,padded,total;reg [23:0] local_qpn;
 begin
  total=context_value[307:276];local_qpn=context_value[395:372];
  va=context_value[243:180]+off;bytes=bytes_at(total,off);padded=(bytes+3)&32'hfffffffc;
  raw_at={2'd0,local_qpn[9:0],va[51:48],1'b1,1'b0,va[52],off+bytes==total,padded[27:0],va[47:0]};
 end
endfunction
wire raw_match=(^s_hls_command)!==1'bx && s_hls_command==raw_at(owner,next_offset);
wire pick_ok=active && placement_seen && state==PICK && next_offset<length && raw_match && !tags_exhausted && !stopped && !rst;
reg [747:0] picked_context;
always @*begin
 picked_context=owner;
 picked_context[355:340]=16'ha000|{{(16-TAG_SEQUENCE_WIDTH){1'b0}},next_tag};
 picked_context[307:276]=bytes_at(length,next_offset);
 picked_context[243:180]=owner[243:180]+next_offset;
 picked_context[179:116]=owner[179:116]+next_offset;
 picked_context[115:52]=owner[115:52]+next_offset;
end
wire child_owner_ready,child_token_ready,child_raw_ready,child_busy,child_fault;
wire [7:0] child_fault_code,child_error;wire [MAX_QPS-1:0] child_guard;
wire [747:0] child_event;wire child_event_valid;
wire child_event_match=(^{child_event,child_error})!==1'bx && child_event==child_context;
wire child_event_ready=active && state==TRANSFER && child_event_match && !rst;
wire pad_context_ready,pad_command_ready,pad_busy,pad_fault;
wire [7:0] pad_fault_code;wire [MAX_QPS-1:0] pad_guard;
wire [95:0] pad_command;wire pad_command_valid;
wire [511:0] pad_data;wire [63:0] pad_keep;wire pad_last,pad_valid,pad_ready,pad_input_ready;
wire arm=active && state==ARM && child_owner_ready && pad_context_ready && !stopped && !bad_offer && !rst;
wire token_offer=active && state==TOKEN && !stopped && !bad_offer;
wire holding=state==ARM || state==TOKEN || state==COMMAND;
wire held_bad=active && holding && (s_hls_command_valid!==1'b1 || s_hls_command!==held_raw);
wire command_offer=active && state==COMMAND && s_hls_command_valid && s_hls_command==held_raw && !held_bad;
// The original96-bit HLS command was validated BEFORE this ctl-only change.
// Each derived child/unpad is a complete <=4096B transaction; its ctl is1.
wire [95:0] child_raw=held_raw|96'h000010000000000000000000;
assign s_hls_command_ready=command_offer && pad_command_ready && !rst;
// Back-to-back next-packet data may wait while the prior status is withheld.
// Never present it as extra data to the completed bounded unpad child.
wire data_offer=active && (state==COMMAND || state==TRANSFER) && !hls_input_done;
assign s_axis_hls_tready=data_offer && pad_input_ready;
wire retire_match=(^s_retire_context)!==1'bx && s_retire_context==owner;
assign s_retire_ready=active && state==PICK && whole_complete && event_sent && !child_busy && !pad_busy &&
 s_hls_command_valid===1'b0 && s_axis_hls_tvalid===1'b0 && retire_match && held_guard && !stopped && !bad_offer && !rst;
assign s_owner_ready=enable && !active && !child_busy && !pad_busy && owner_ok && !tags_exhausted && !stopped && !rst;
assign m_memory_event_context=owner;
wire [MAX_QPS-1:0] owned_guard=active ? ({{(MAX_QPS-1){1'b0}},1'b1}<<qpn):{MAX_QPS{1'b0}};
wire [MAX_QPS-1:0] offered_guard=s_owner_valid && owner_ok ?
 ({{(MAX_QPS-1){1'b0}},1'b1}<<in_qpn):{MAX_QPS{1'b0}};
wire bad_offer=(s_owner_valid!==1'b0 && s_owner_valid!==1'b1) ||
 (s_read_response_valid!==1'b0 && s_read_response_valid!==1'b1) ||
 (s_hls_command_valid!==1'b0 && s_hls_command_valid!==1'b1) ||
 (s_axis_hls_tvalid!==1'b0 && s_axis_hls_tvalid!==1'b1) ||
 (s_retire_valid!==1'b0 && s_retire_valid!==1'b1) ||
 (!active && s_owner_valid && (!owner_ok || tags_exhausted)) ||
 (s_read_response_valid && (!active || placement_seen || !placement_match)) || held_bad ||
 (s_hls_command_valid && (!active || (state==PICK && (!pick_ok || tags_exhausted)))) ||
 (s_axis_hls_tvalid && (!active || whole_complete)) ||
 (s_retire_valid && (!active || !retire_match)) ||
 (active && !held_guard) ||
 (child_event_valid && (!active || state!=TRANSFER || !child_event_match));
assign queue_guard=(stopped || child_fault || pad_fault || bad_offer) ? {MAX_QPS{1'b1}}:
 owned_guard|offered_guard|child_guard|pad_guard;
assign busy=active || child_busy || pad_busy || stopped || bad_offer;
rocev2_segmented_read_child_unpad #(.MAX_QPS(MAX_QPS)) padding(
 .clk(clk),.rst(rst),.enable(enable),
 .s_context(child_context),.s_context_valid(arm),.s_context_ready(pad_context_ready),
 .downstream_queue_guard(owned_guard),
 .s_command(child_raw),.s_command_valid(command_offer),.s_command_ready(pad_command_ready),
 .m_command(pad_command),.m_command_valid(pad_command_valid),.m_command_ready(child_raw_ready),
 .s_axis_tdata(s_axis_hls_tdata),.s_axis_tkeep(s_axis_hls_tkeep),.s_axis_tlast(s_axis_hls_tlast),
 .s_axis_tvalid(data_offer && s_axis_hls_tvalid),.s_axis_tready(pad_input_ready),
 .m_axis_tdata(pad_data),.m_axis_tkeep(pad_keep),.m_axis_tlast(pad_last),.m_axis_tvalid(pad_valid),.m_axis_tready(pad_ready),
 .queue_guard(pad_guard),.busy(pad_busy),.fault(pad_fault),.fault_code(pad_fault_code),
 .context_count(),.command_count(),.discarded_padding_bytes(discarded_padding_bytes));
rocev2_segmented_child_executor #(.MAX_QPS(MAX_QPS)) child(
 .clk(clk),.rst(rst),.enable(enable),.halt(stopped),
 .s_owner_context(child_context),.s_owner_valid(arm),.s_owner_ready(child_owner_ready),
 .s_read_response_context(child_context),.s_read_response_valid(token_offer),.s_read_response_ready(child_token_ready),
 .s_hls_read_command(96'd0),.s_hls_read_command_valid(1'b0),.s_hls_read_command_ready(),
 .s_hls_write_command(pad_command),.s_hls_write_command_valid(pad_command_valid),.s_hls_write_command_ready(child_raw_ready),
 .s_axis_hls_write_tdata(pad_data),.s_axis_hls_write_tkeep(pad_keep),.s_axis_hls_write_tlast(pad_last),
 .s_axis_hls_write_tvalid(pad_valid),.s_axis_hls_write_tready(pad_ready),
 .m_axis_hls_read_tdata(),.m_axis_hls_read_tkeep(),.m_axis_hls_read_tlast(),.m_axis_hls_read_tvalid(),.m_axis_hls_read_tready(1'b0),
 .m_memory_command_write(m_memory_command_write),.m_memory_command_offset(m_memory_command_offset),
 .m_memory_command_length(m_memory_command_length),.m_memory_command_key(m_memory_command_key),
 .m_memory_command_tag(m_memory_command_tag),.m_memory_command_valid(m_memory_command_valid),.m_memory_command_ready(m_memory_command_ready),
 .m_axis_memory_write_tdata(m_axis_memory_tdata),.m_axis_memory_write_tkeep(m_axis_memory_tkeep),
 .m_axis_memory_write_tlast(m_axis_memory_tlast),.m_axis_memory_write_tvalid(m_axis_memory_tvalid),.m_axis_memory_write_tready(m_axis_memory_tready),
 .s_axis_memory_read_tdata(512'd0),.s_axis_memory_read_tkeep(64'd0),.s_axis_memory_read_tlast(1'b0),
 .s_axis_memory_read_tvalid(1'b0),.s_axis_memory_read_tready(),
 .s_memory_status_tag(s_memory_status_tag),.s_memory_status_error(s_memory_status_error),
 .s_memory_status_valid(s_memory_status_valid),.s_memory_status_ready(s_memory_status_ready),
 .m_memory_event_context(child_event),.m_memory_event_error(child_error),.m_memory_event_valid(child_event_valid),.m_memory_event_ready(child_event_ready),
 .downstream_queue_guard(owned_guard),.queue_guard(child_guard),.busy(child_busy),.fault(child_fault),.fault_code(child_fault_code),
 .owner_count(),.command_count(),.memory_status_count());
initial if(MAX_QPS<1 || MAX_QPS>8 || TAG_SEQUENCE_WIDTH<1 || TAG_SEQUENCE_WIDTH>12)
 $fatal(1,"unreviewed segmented READ QP/tag capacity");
always @(posedge clk)begin
 if(rst)begin
  active<=0;state<=PICK;placement_seen<=0;whole_complete<=0;event_sent<=0;hls_input_done<=0;
  owner<=0;child_context<=0;held_raw<=0;next_offset<=0;selected_bytes<=0;
  next_tag<=1;tags_exhausted<=0;fault<=0;fault_code<=0;
  m_memory_event_error<=0;m_memory_event_valid<=0;owner_count<=0;fragment_count<=0;retired_count<=0;
 end else begin
  if(s_owner_valid && s_owner_ready)begin
   owner<=s_owner_context;active<=1;state<=PICK;placement_seen<=0;next_offset<=0;
   whole_complete<=0;event_sent<=0;hls_input_done<=0;m_memory_event_error<=0;owner_count<=owner_count+1'b1;
  end
  if(s_read_response_valid && s_read_response_ready)placement_seen<=1;
  if(s_hls_command_valid && pick_ok)begin
   child_context<=picked_context;held_raw<=s_hls_command;selected_bytes<=bytes_at(length,next_offset);
   state<=ARM;hls_input_done<=0;
   if(&next_tag)tags_exhausted<=1;else next_tag<=next_tag+1'b1;
  end
  if(arm)state<=TOKEN;
  if(token_offer && child_token_ready)state<=COMMAND;
  if(command_offer && pad_command_ready)state<=TRANSFER;
  if(s_axis_hls_tvalid && s_axis_hls_tready && s_axis_hls_tlast)hls_input_done<=1;
  if(child_event_valid && child_event_ready)begin
   if(child_error==0 && !stopped && !child_fault && !pad_fault && !bad_offer && !pad_busy && hls_input_done)begin
    next_offset<=next_offset+selected_bytes;fragment_count<=fragment_count+1'b1;state<=PICK;
    if(next_offset+selected_bytes==length)begin whole_complete<=1;m_memory_event_valid<=1;end
   end else if(child_error!=0 && !event_sent && !m_memory_event_valid)begin
    m_memory_event_error<=child_error;m_memory_event_valid<=1;
   end
  end
  if(m_memory_event_valid && m_memory_event_ready && held_guard && !stopped)begin m_memory_event_valid<=0;event_sent<=1;end
  if(s_retire_valid && s_retire_ready)begin active<=0;retired_count<=retired_count+1'b1;end
  if(!fault)begin
   if(parent_fault!==1'b0)begin fault<=1;fault_code<=8'he1;end
   else if(child_fault)begin fault<=1;fault_code<=child_fault_code;end
   else if(pad_fault)begin fault<=1;fault_code<=pad_fault_code;end
   else if(bad_offer)begin fault<=1;fault_code<=8'he2;end
   else if(child_event_valid && child_event_ready &&
     (child_error!=0 || pad_busy || !hls_input_done))begin fault<=1;fault_code<=8'he3;end
  end
 end
end
endmodule
`resetall
