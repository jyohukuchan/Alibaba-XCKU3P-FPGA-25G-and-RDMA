// SPDX-License-Identifier: BSD-2-Clause-Views
// Checked-frame -> actual remote-message MR protection -> owned HLS replay.
// Input MUST be the genuine whole-frame IPv4/ICRC checker output, with the
// same privileged native356 QP context retained by raw RX references.
// MR ports connect to the SAME native MR namespace, not a private table.
// Packet owner admission, backend/HLS/MAC certificates and notice/CQ fanout
// must be real downstream consumers. This module invents NONE of them.
// Separate source component; not yet the qualified full native endpoint.
`resetall
`timescale 1ns/1ps
`default_nettype none
module rocev2_segmented_write_rx_frontend #(
    parameter [63:0] INITIAL_MESSAGE_COOKIE=0,
    parameter [15:0] INITIAL_PACKET_TAG=0
)(
    input wire clk,input wire rst,input wire enable,input wire parent_fault,
    input wire trusted_valid,input wire [355:0] trusted_context,
    input wire [23:0] trusted_expected_psn,
    input wire [127:0] s_axis_tdata,input wire [15:0] s_axis_tkeep,
    input wire s_axis_tvalid,output wire s_axis_tready,input wire s_axis_tlast,
    output wire [127:0] m_axis_tdata,output wire [15:0] m_axis_tkeep,
    output wire m_axis_tvalid,input wire m_axis_tready,output wire m_axis_tlast,
    output wire [15:0] m_mr_pd,output wire [31:0] m_mr_key,
    output wire [63:0] m_mr_address,output wire [31:0] m_mr_length,
    output wire [2:0] m_mr_operation,output wire [15:0] m_mr_tag,
    output wire m_mr_valid,input wire m_mr_ready,
    input wire [15:0] s_mr_tag,input wire [7:0] s_mr_error,
    input wire [63:0] s_mr_offset,s_mr_address,input wire [31:0] s_mr_length,
    input wire s_mr_valid,output wire s_mr_ready,
    input wire [619:0] s_rq_context,input wire s_rq_valid,
    output wire [319:0] m_notice_context,output wire [23:0] m_notice_last_psn,
    output wire m_notice_valid,input wire m_notice_ready,
    // Full typed owner MUST be accepted before the first replay beat.
    output wire [423:0] m_packet_token,output wire [63:0] m_packet_address,
    output wire [63:0] m_packet_mr_offset,m_packet_mr_address,
    output wire [31:0] m_packet_key,m_packet_wire_length,
    output wire m_packet_last,m_packet_notify,output wire [619:0] m_packet_rq_context,
    output wire m_packet_valid,input wire m_packet_ready,
    input wire [423:0] s_done_token,input wire [23:0] s_done_msn,
    input wire [7:0] s_done_proofs,input wire s_done_valid,output wire s_done_ready,
    input wire [319:0] s_notice_retire_context,input wire s_notice_retire_valid,
    output wire s_notice_retire_ready,
    input wire [319:0] s_cancel_context,input wire s_cancel_valid,
    input wire cancel_drained,output wire s_cancel_ready,
    output wire [7:0] m_reject_error,output wire [23:0] m_reject_qpn,m_reject_psn,m_reject_msn,
    output wire m_reject_keep_message,output wire m_reject_valid,input wire m_reject_ready,
    output wire [319:0] message_context,output wire configuration_guard,
    output wire [7:0] queue_guard,output wire message_active,
    output wire [31:0] accepted_packets,completed_packets,completed_messages,cancelled_messages,
    output wire fault,output wire [7:0] fault_code
);
localparam COLLECT=0,PARSE=1,METADATA=2,ADMIT=3,FORWARD=4,WAIT_DONE=5,REJECT=6;
localparam FRAME_WORDS=260;
reg [2:0] state=COLLECT;
reg [127:0] frame_data[0:FRAME_WORDS-1];
reg [15:0] frame_keep[0:FRAME_WORDS-1];
reg [8:0] word_count=0,read_index=0;
reg [15:0] byte_count=0,packet_tag=INITIAL_PACKET_TAG;
reg [511:0] header=0;
reg frame_bad=0,frame_forwarded=0,local_fault=0;
reg [7:0] local_fault_code=0,reject_error=0;
reg [23:0] reject_qpn=0,reject_psn=0;
reg [355:0] frame_context=0;
reg snapshot_valid=0;
wire guard_fault,guard_configuration_guard,metadata_ready,owner_valid,owner_ready;
wire [7:0] guard_fault_code,guard_queue_guard;
wire guard_done_ready,guard_reject_valid,guard_reject_ready;
wire [7:0] guard_reject_error;
wire [23:0] guard_reject_qpn,guard_reject_psn,guard_reject_msn;
wire guard_reject_keep;
wire trusted_known=(^trusted_context)!==1'bx;
wire trusted_ok=trusted_valid===1'b1 && trusted_known && trusted_context[23:0]<24'd8 &&
    trusted_context[39:24]!=0 && trusted_context[103:40]!=0 && trusted_context[167:104]!=0;
wire held=snapshot_valid && (word_count!=0 || state!=COLLECT || message_active);
wire context_stable=!held || trusted_valid===1'b1 && trusted_context===frame_context;
wire halted=local_fault || guard_fault || parent_fault!==1'b0;
assign fault=halted;
assign fault_code=local_fault ? local_fault_code:guard_fault ? guard_fault_code:parent_fault!==1'b0 ? 8'hf0:8'd0;
assign s_axis_tready=state==COLLECT && (word_count!=0 || metadata_ready) && !halted && !rst;
wire frame_offer=state==COLLECT && enable===1'b1 && trusted_valid===1'b1 && s_axis_tvalid===1'b1;
wire buffered=state!=COLLECT || word_count!=0 || m_axis_tvalid || frame_offer;
assign configuration_guard=guard_configuration_guard || buffered || halted;
assign queue_guard=halted ? 8'hff:guard_queue_guard |
    (buffered ? 8'h01<<(snapshot_valid && word_count!=0 ? frame_context[23:0]:trusted_context[23:0]):8'd0);
function [15:0] be16;
 input [511:0] d;input integer n;
 begin be16={d[n*8+:8],d[(n+1)*8+:8]};end
endfunction
function [31:0] be32;
 input [511:0] d;input integer n;
 begin be32={be16(d,n),be16(d,n+2)};end
endfunction
function [63:0] be64;
 input [511:0] d;input integer n;
 begin be64={be32(d,n),be32(d,n+4)};end
endfunction
function [4:0] bytes16;
 input [15:0] keep;integer n;
 begin bytes16=0;for(n=0;n<16;n=n+1)bytes16=bytes16+{4'd0,keep[n]};end
endfunction
wire [7:0] opcode=header[28*8+:8];
wire first=opcode==8'h06,notify=opcode==8'h09;
wire opcode_ok=first || opcode==8'h07 || opcode==8'h08 || notify;
wire [31:0] header_bytes=first ? 32'd60:notify ? 32'd48:32'd44;
wire [1:0] pad=header[29*8+4+:2];
wire [31:0] wire_bytes={16'd0,byte_count}-header_bytes;
wire [31:0] payload_bytes=wire_bytes-{30'd0,pad};
wire [23:0] packet_qpn={header[33*8+:8],header[34*8+:8],header[35*8+:8]};
wire [23:0] packet_psn={header[37*8+:8],header[38*8+:8],header[39*8+:8]};
wire frame_known=(^{header,byte_count})!==1'bx;
wire format_ok=frame_known && !frame_bad && opcode_ok && {16'd0,byte_count}>=header_bytes &&
    header[0+:8]==8'h45 && header[9*8+:8]==8'd17 && be16(header,2)==byte_count &&
    be16(header,24)==byte_count-16'd20 && (be16(header,6)&16'h3fff)==0 &&
    be16(header,22)==16'd4791 && be16(header,26)==0 &&
    (header[29*8+:8]&8'h8f)==0 && be16(header,30)==16'hffff &&
    (header[32*8+:8]&8'h3f)==0 && (header[36*8+:8]&8'h7f)==0;
wire peer_ok=packet_qpn==frame_context[23:0] && be32(header,12)==frame_context[255:224] &&
    be32(header,16)==frame_context[223:192] && frame_context[353]===1'b1;
assign m_packet_valid=owner_valid && state==ADMIT && !halted && !rst;
assign owner_ready=m_packet_ready && state==ADMIT && !halted && !rst;
assign s_done_ready=guard_done_ready && state==WAIT_DONE && frame_forwarded && !halted && !rst;
assign m_reject_valid=!halted && !rst && (state==REJECT || state==ADMIT && guard_reject_valid);
assign guard_reject_ready=state==ADMIT && m_reject_ready && !halted && !rst;
assign m_reject_error=state==REJECT ? reject_error:guard_reject_error;
assign m_reject_qpn=state==REJECT ? reject_qpn:guard_reject_qpn;
assign m_reject_psn=state==REJECT ? reject_psn:guard_reject_psn;
// A local malformed frame never changes the remote message's MSN/position.
// No RNR/MSN is invented here: actual guard rejects provide that metadata.
assign m_reject_msn=state==REJECT ? 24'd0:guard_reject_msn;
assign m_reject_keep_message=state==REJECT ? message_active:guard_reject_keep;
rocev2_remote_write_message_guard #(.INITIAL_MESSAGE_COOKIE(INITIAL_MESSAGE_COOKIE)) protection(
 .clk(clk),.rst(rst),.enable(enable),.parent_fault(parent_fault || local_fault),
 .trusted_valid(trusted_valid),.trusted_qpn(trusted_context[23:0]),.trusted_pd(trusted_context[39:24]),
 .trusted_epoch(trusted_context[103:40]),.trusted_expected_psn(trusted_expected_psn),
 .s_packet_opcode(opcode),.s_packet_qpn(packet_qpn),.s_packet_psn(packet_psn),
 .s_packet_length(payload_bytes),.s_packet_wire_length(wire_bytes),.s_packet_pad(pad),
 .s_packet_reth_valid(first),.s_packet_reth_va(be64(header,40)),.s_packet_reth_key(be32(header,48)),
 .s_packet_reth_length(be32(header,52)),.s_packet_tag(packet_tag+16'd1),
 .s_packet_valid(state==METADATA && !halted),.s_packet_ready(metadata_ready),
 .m_mr_pd(m_mr_pd),.m_mr_key(m_mr_key),.m_mr_address(m_mr_address),.m_mr_length(m_mr_length),
 .m_mr_operation(m_mr_operation),.m_mr_tag(m_mr_tag),.m_mr_valid(m_mr_valid),.m_mr_ready(m_mr_ready),
 .s_mr_tag(s_mr_tag),.s_mr_error(s_mr_error),.s_mr_offset(s_mr_offset),.s_mr_address(s_mr_address),
 .s_mr_length(s_mr_length),.s_mr_valid(s_mr_valid),.s_mr_ready(s_mr_ready),
 .s_rq_context(s_rq_context),.s_rq_valid(s_rq_valid),.m_notice_context(m_notice_context),
 .m_notice_last_psn(m_notice_last_psn),.m_notice_valid(m_notice_valid),.m_notice_ready(m_notice_ready),
 .m_packet_token(m_packet_token),.m_packet_address(m_packet_address),.m_packet_mr_offset(m_packet_mr_offset),
 .m_packet_mr_address(m_packet_mr_address),.m_packet_key(m_packet_key),.m_packet_wire_length(m_packet_wire_length),
 .m_packet_last(m_packet_last),.m_packet_notify(m_packet_notify),.m_packet_rq_context(m_packet_rq_context),
 .m_packet_valid(owner_valid),.m_packet_ready(owner_ready),
 .s_done_token(s_done_token),.s_done_msn(s_done_msn),.s_done_proofs(s_done_proofs),
 .s_done_valid(s_done_valid && state==WAIT_DONE && frame_forwarded),.s_done_ready(guard_done_ready),
 .s_notice_retire_context(s_notice_retire_context),.s_notice_retire_valid(s_notice_retire_valid),
 .s_notice_retire_ready(s_notice_retire_ready),.s_cancel_context(s_cancel_context),.s_cancel_valid(s_cancel_valid),
 .cancel_drained(cancel_drained && state==COLLECT && word_count==0 && !m_axis_tvalid),.s_cancel_ready(s_cancel_ready),
 .m_reject_error(guard_reject_error),.m_reject_qpn(guard_reject_qpn),.m_reject_psn(guard_reject_psn),
 .m_reject_msn(guard_reject_msn),.m_reject_keep_message(guard_reject_keep),
 .m_reject_valid(guard_reject_valid),.m_reject_ready(guard_reject_ready),
 .message_context(message_context),.configuration_guard(guard_configuration_guard),.queue_guard(guard_queue_guard),
 .message_active(message_active),.accepted_packets(accepted_packets),.completed_packets(completed_packets),
 .completed_messages(completed_messages),.cancelled_messages(cancelled_messages),.fault(guard_fault),.fault_code(guard_fault_code));
// Same real register slice as the qualified native replay path. Once a beat
// is offered it stays stable even if upstream admission is later quarantined.
axis_register #(.DATA_WIDTH(128),.KEEP_ENABLE(1),.KEEP_WIDTH(16),.LAST_ENABLE(1),
 .ID_ENABLE(0),.ID_WIDTH(1),.DEST_ENABLE(0),.DEST_WIDTH(1),.USER_ENABLE(0),.USER_WIDTH(1),.REG_TYPE(2)) replay(
 .clk(clk),.rst(rst),.s_axis_tdata(frame_data[read_index]),.s_axis_tkeep(frame_keep[read_index]),
 .s_axis_tvalid(state==FORWARD && !halted),.s_axis_tready(replay_ready),
 .s_axis_tlast(read_index+9'd1==word_count),.s_axis_tid(1'b0),.s_axis_tdest(1'b0),.s_axis_tuser(1'b0),
 .m_axis_tdata(m_axis_tdata),.m_axis_tkeep(m_axis_tkeep),.m_axis_tvalid(m_axis_tvalid),.m_axis_tready(m_axis_tready),
 .m_axis_tlast(m_axis_tlast),.m_axis_tid(),.m_axis_tdest(),.m_axis_tuser());
wire replay_ready;
always @(posedge clk)begin
 if(rst)begin
  state<=COLLECT;word_count<=0;read_index<=0;byte_count<=0;packet_tag<=INITIAL_PACKET_TAG;
  header<=0;frame_bad<=0;frame_forwarded<=0;local_fault<=0;local_fault_code<=0;
  reject_error<=0;reject_qpn<=0;reject_psn<=0;frame_context<=0;snapshot_valid<=0;
 end else begin
  if(parent_fault!==1'b0 || !context_stable ||
     enable===1'b1 && trusted_valid===1'b1 && !trusted_ok ||
     state==COLLECT && enable===1'b1 && s_axis_tvalid!==1'b0 && s_axis_tvalid!==1'b1)begin
   local_fault<=1;local_fault_code<=8'hf1;
  end
  if(s_done_valid && (state!=WAIT_DONE || !frame_forwarded))begin local_fault<=1;local_fault_code<=8'hf2;end
  if(m_axis_tvalid && m_axis_tready && m_axis_tlast)frame_forwarded<=1;
  if(!halted)case(state)
   COLLECT:if(s_axis_tvalid && s_axis_tready)begin
    if(word_count==0)begin frame_context<=trusted_context;snapshot_valid<=1;end
    if(word_count<FRAME_WORDS)begin
     frame_data[word_count]<=s_axis_tdata;frame_keep[word_count]<=s_axis_tkeep;word_count<=word_count+9'd1;
    end else frame_bad<=1;
    if(word_count<4)header[word_count*128+:128]<=s_axis_tdata;
    if(byte_count<16'hfff0)byte_count<=byte_count+{11'd0,bytes16(s_axis_tkeep)};else frame_bad<=1;
    if((^{s_axis_tdata,s_axis_tkeep,s_axis_tlast})===1'bx || s_axis_tkeep==0 ||
       (s_axis_tkeep&(s_axis_tkeep+16'd1))!=0 || (!s_axis_tlast && s_axis_tkeep!=16'hffff))frame_bad<=1;
    if(s_axis_tlast)state<=PARSE;
   end
   PARSE:begin
    reject_qpn<=packet_qpn;reject_psn<=packet_psn;reject_error<=16;state<=REJECT;
    if(enable!==1'b1 || !trusted_ok || !peer_ok)reject_error<=17;
    else if(!format_ok)reject_error<=16;
    else if(packet_psn!=trusted_expected_psn)reject_error<=18;
    else state<=METADATA;
   end
   METADATA:if(metadata_ready)state<=ADMIT;
   ADMIT:begin
    if(m_reject_valid && m_reject_ready)begin state<=COLLECT;word_count<=0;byte_count<=0;header<=0;frame_bad<=0;end
    else if(m_packet_valid && m_packet_ready)begin
     packet_tag<=m_packet_token[15:0];read_index<=0;frame_forwarded<=0;state<=FORWARD;
    end
   end
   FORWARD:if(replay_ready)begin
    if(read_index+9'd1==word_count)state<=WAIT_DONE;else read_index<=read_index+9'd1;
   end
   WAIT_DONE:if(s_done_valid && s_done_ready)begin
    state<=COLLECT;word_count<=0;byte_count<=0;header<=0;frame_bad<=0;frame_forwarded<=0;
   end
   REJECT:if(m_reject_valid && m_reject_ready)begin
    state<=COLLECT;word_count<=0;byte_count<=0;header<=0;frame_bad<=0;
   end
   default:begin local_fault<=1;local_fault_code<=8'hf3;end
  endcase
 end
end
endmodule
`resetall
