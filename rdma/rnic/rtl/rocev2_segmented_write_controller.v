// SPDX-License-Identifier: BSD-2-Clause-Views
// Actual checked-frame/MR/packet-memory/HLS/ACK join for native insertion.
// Native context/MR/backend/HLS/ACK/RQ/PSN/CQ ports MUST connect to the real
// shared instances. This controller does not fabricate their certificates.
// Raw-frame integrity is upstream; byte-for-byte replay is checked again
// by the real HLS integrity bridge. No private MR or DMA namespace is here.
// Partial-message HLS teardown is NOT proved: cancellation stays disabled,
// and reset is never a safe drain/unpin certificate.
`resetall
`timescale 1ns/1ps
`default_nettype none
module rocev2_segmented_write_controller #(
    parameter [63:0] INITIAL_MESSAGE_COOKIE=0,
    parameter [15:0] INITIAL_PACKET_TAG=0
)(
    input wire clk,input wire rst,input wire enable,input wire parent_fault,
    input wire trusted_valid,input wire [355:0] trusted_context,input wire [23:0] trusted_expected_psn,
    input wire [127:0] s_rx_data,input wire [15:0] s_rx_keep,input wire s_rx_valid,output wire s_rx_ready,input wire s_rx_last,
    output wire [127:0] m_hls_rx_data,output wire [15:0] m_hls_rx_keep,output wire m_hls_rx_valid,
    input wire m_hls_rx_ready,output wire m_hls_rx_last,
    output wire [15:0] m_mr_pd,output wire [31:0] m_mr_key,output wire [63:0] m_mr_address,
    output wire [31:0] m_mr_length,output wire [2:0] m_mr_operation,output wire [15:0] m_mr_tag,
    output wire m_mr_valid,input wire m_mr_ready,
    input wire [15:0] s_mr_tag,input wire [7:0] s_mr_error,input wire [63:0] s_mr_offset,s_mr_address,
    input wire [31:0] s_mr_length,input wire s_mr_valid,output wire s_mr_ready,
    input wire [619:0] s_rq_context,input wire s_rq_valid,
    output wire [319:0] m_notice_context,output wire [23:0] m_notice_last_psn,
    output wire m_notice_valid,input wire m_notice_ready,
    input wire [319:0] s_notice_retire_context,input wire s_notice_retire_valid,output wire s_notice_retire_ready,
    output wire [423:0] m_hls_owner,output wire m_hls_owner_valid,input wire m_hls_owner_ready,
    input wire [455:0] s_hls_done,input wire s_hls_done_valid,output wire s_hls_done_ready,
    output wire [679:0] m_hls_rq_owner,output wire m_hls_rq_owner_valid,input wire m_hls_rq_owner_ready,
    output wire [619:0] m_rq_placement_context,output wire [31:0] m_rq_placement_length,m_rq_placement_notification,
    output wire [23:0] m_rq_placement_psn,output wire m_rq_placement_valid,input wire m_rq_placement_ready,
    input wire [95:0] s_hls_command,input wire s_hls_command_valid,output wire s_hls_command_ready,
    input wire [511:0] s_hls_data,input wire [63:0] s_hls_keep,input wire s_hls_last,
    input wire s_hls_valid,output wire s_hls_ready,
    output wire m_command_write,output wire [63:0] m_command_offset,output wire [31:0] m_command_length,m_command_key,
    output wire [15:0] m_command_tag,output wire m_command_valid,input wire m_command_ready,
    output wire [511:0] m_data,output wire [63:0] m_keep,output wire m_last,m_valid,input wire m_ready,
    input wire [15:0] s_status_tag,input wire [7:0] s_status_error,input wire s_status_valid,output wire s_status_ready,
    output wire [423:0] m_ack_owner,output wire m_ack_owner_notify,output wire [619:0] m_ack_owner_rq_context,
    output wire m_ack_owner_valid,input wire m_ack_owner_ready,
    output wire [455:0] m_ack_core,output wire m_ack_core_valid,input wire m_ack_core_ready,
    input wire [471:0] s_ack_done,input wire s_ack_done_valid,output wire s_ack_done_ready,
    output wire [423:0] m_ack_retire_token,output wire m_ack_retire_valid,input wire m_ack_retire_ready,
    // Native shadow PSN and frontend completion transfer MUST happen on the
    // SAME edge. No one-sided PSN advance, no ACK-triggered early owner drop.
    output wire [423:0] m_packet_commit_token,output wire [23:0] m_packet_commit_msn,
    output wire [7:0] m_packet_commit_proofs,output wire m_packet_commit_valid,input wire m_packet_commit_ready,
    // Only real payload EOF + real tagged backend visibility release ACK TX.
    // HLS completion, SFD/quiet or downstream READY are not memory visibility.
    output wire m_tx_release,
    output wire [7:0] m_reject_error,output wire [23:0] m_reject_qpn,m_reject_psn,m_reject_msn,
    output wire m_reject_keep_message,m_reject_valid,input wire m_reject_ready,
    output wire [319:0] message_context,output wire message_active,output wire configuration_guard,
    output wire [7:0] queue_guard,output wire fault,
    output wire [31:0] accepted_packets,completed_packets,completed_messages
);
wire [423:0] packet_token;
wire [63:0] packet_address,packet_mr_offset,packet_mr_address;
wire [31:0] packet_key,packet_wire_length,packet_notification;
wire packet_last,packet_notify,packet_valid,packet_ready;
wire [619:0] packet_rq_context;
wire [423:0] done_token;wire [23:0] done_msn;wire [7:0] done_proofs;
wire done_valid,done_ready,front_done_ready;
wire front_fault,memory_fault,front_guard,memory_guard,memory_busy;
wire [7:0] front_queue_guard,memory_queue_guard;
wire [7:0] front_fault_code,memory_fault_code;
reg notice_pending=0,hls_rq_sent=0,placement_sent=0;
reg [619:0] notify_owner=0;
reg [31:0] notify_length=0,notify_immediate=0;
reg [23:0] notify_psn=0;
wire halted=front_fault || memory_fault || parent_fault!==1'b0;
assign fault=halted;
assign configuration_guard=front_guard || memory_guard || notice_pending || halted;
assign queue_guard=halted ? 8'hff:front_queue_guard | memory_queue_guard |
    (notice_pending ? 8'h01<<notify_owner[395:372]:8'd0);
assign m_hls_rq_owner={4'd0,notify_psn,notify_length,notify_owner};
assign m_hls_rq_owner_valid=notice_pending && !hls_rq_sent && !halted && !rst;
assign m_rq_placement_context=notify_owner;assign m_rq_placement_length=notify_length;
assign m_rq_placement_notification=notify_immediate;assign m_rq_placement_psn=notify_psn;
assign m_rq_placement_valid=notice_pending && hls_rq_sent && !placement_sent && !halted && !rst;
wire notice_ready=!notice_pending || hls_rq_sent && placement_sent;
assign m_packet_commit_token=done_token;assign m_packet_commit_msn=done_msn;
assign m_packet_commit_proofs=done_proofs;
assign m_packet_commit_valid=done_valid && front_done_ready && notice_ready && !halted && !rst;
assign done_ready=front_done_ready && m_packet_commit_ready && notice_ready && !halted && !rst;
assign m_tx_release=memory_busy && done_proofs[1:0]==2'b11 && !halted && !rst;
rocev2_segmented_write_native_frontend #(.INITIAL_MESSAGE_COOKIE(INITIAL_MESSAGE_COOKIE),.INITIAL_PACKET_TAG(INITIAL_PACKET_TAG)) frontend(
 .clk(clk),.rst(rst),.enable(enable),.parent_fault(parent_fault || memory_fault),
 .trusted_valid(trusted_valid),.trusted_context(trusted_context),.trusted_expected_psn(trusted_expected_psn),
 .s_axis_tdata(s_rx_data),.s_axis_tkeep(s_rx_keep),.s_axis_tvalid(s_rx_valid),.s_axis_tready(s_rx_ready),.s_axis_tlast(s_rx_last),
 .m_axis_tdata(m_hls_rx_data),.m_axis_tkeep(m_hls_rx_keep),.m_axis_tvalid(m_hls_rx_valid),.m_axis_tready(m_hls_rx_ready),.m_axis_tlast(m_hls_rx_last),
 .m_mr_pd(m_mr_pd),.m_mr_key(m_mr_key),.m_mr_address(m_mr_address),.m_mr_length(m_mr_length),
 .m_mr_operation(m_mr_operation),.m_mr_tag(m_mr_tag),.m_mr_valid(m_mr_valid),.m_mr_ready(m_mr_ready),
 .s_mr_tag(s_mr_tag),.s_mr_error(s_mr_error),.s_mr_offset(s_mr_offset),.s_mr_address(s_mr_address),
 .s_mr_length(s_mr_length),.s_mr_valid(s_mr_valid),.s_mr_ready(s_mr_ready),
 .s_rq_context(s_rq_context),.s_rq_valid(s_rq_valid),.m_notice_context(m_notice_context),.m_notice_last_psn(m_notice_last_psn),
 .m_notice_valid(m_notice_valid),.m_notice_ready(m_notice_ready),
 .m_packet_token(packet_token),.m_packet_address(packet_address),.m_packet_mr_offset(packet_mr_offset),.m_packet_mr_address(packet_mr_address),
 .m_packet_key(packet_key),.m_packet_wire_length(packet_wire_length),.m_packet_last(packet_last),.m_packet_notify(packet_notify),
 .m_packet_rq_context(packet_rq_context),.m_packet_notification(packet_notification),.m_packet_valid(packet_valid),.m_packet_ready(packet_ready),
 .s_done_token(done_token),.s_done_msn(done_msn),.s_done_proofs(done_proofs),
 .s_done_valid(done_valid && m_packet_commit_ready && notice_ready && !halted),.s_done_ready(front_done_ready),
 .s_notice_retire_context(s_notice_retire_context),.s_notice_retire_valid(s_notice_retire_valid),.s_notice_retire_ready(s_notice_retire_ready),
 .s_cancel_context(320'd0),.s_cancel_valid(1'b0),.cancel_drained(1'b0),.s_cancel_ready(),
 .m_reject_error(m_reject_error),.m_reject_qpn(m_reject_qpn),.m_reject_psn(m_reject_psn),.m_reject_msn(m_reject_msn),
 .m_reject_keep_message(m_reject_keep_message),.m_reject_valid(m_reject_valid),.m_reject_ready(m_reject_ready),
 .message_context(message_context),.message_active(message_active),.configuration_guard(front_guard),.queue_guard(front_queue_guard),
 .accepted_packets(accepted_packets),.completed_packets(completed_packets),.completed_messages(completed_messages),.cancelled_messages(),
 .fault(front_fault),.fault_code(front_fault_code));
rocev2_remote_write_memory packet_memory(
 .clk(clk),.rst(rst),.enable(enable),.parent_fault(parent_fault || front_fault),
 .s_packet_token(packet_token),.s_packet_mr_offset(packet_mr_offset),.s_packet_mr_address(packet_mr_address),
 .s_packet_notify(packet_notify),.s_packet_rq_context(packet_rq_context),.s_packet_valid(packet_valid),.s_packet_ready(packet_ready),
 .m_hls_owner(m_hls_owner),.m_hls_owner_valid(m_hls_owner_valid),.m_hls_owner_ready(m_hls_owner_ready),
 .m_ack_owner(m_ack_owner),.m_ack_owner_notify(m_ack_owner_notify),.m_ack_owner_rq_context(m_ack_owner_rq_context),
 .m_ack_owner_valid(m_ack_owner_valid),.m_ack_owner_ready(m_ack_owner_ready),
 .s_hls_command(s_hls_command),.s_hls_command_valid(s_hls_command_valid),.s_hls_command_ready(s_hls_command_ready),
 .s_hls_data(s_hls_data),.s_hls_keep(s_hls_keep),.s_hls_last(s_hls_last),.s_hls_valid(s_hls_valid),.s_hls_ready(s_hls_ready),
 .m_command_write(m_command_write),.m_command_offset(m_command_offset),.m_command_length(m_command_length),.m_command_key(m_command_key),
 .m_command_tag(m_command_tag),.m_command_valid(m_command_valid),.m_command_ready(m_command_ready),
 .m_data(m_data),.m_keep(m_keep),.m_last(m_last),.m_valid(m_valid),.m_ready(m_ready),
 .s_status_tag(s_status_tag),.s_status_error(s_status_error),.s_status_valid(s_status_valid),.s_status_ready(s_status_ready),
 .s_hls_done(s_hls_done),.s_hls_done_valid(s_hls_done_valid),.s_hls_done_ready(s_hls_done_ready),
 .m_ack_core(m_ack_core),.m_ack_core_valid(m_ack_core_valid),.m_ack_core_ready(m_ack_core_ready),
 .s_ack_done(s_ack_done),.s_ack_done_valid(s_ack_done_valid),.s_ack_done_ready(s_ack_done_ready),
 .m_done_token(done_token),.m_done_msn(done_msn),.m_done_proofs(done_proofs),.m_done_valid(done_valid),.m_done_ready(done_ready),
 .m_ack_retire_token(m_ack_retire_token),.m_ack_retire_valid(m_ack_retire_valid),.m_ack_retire_ready(m_ack_retire_ready),
 .queue_guard(memory_queue_guard),.configuration_guard(memory_guard),.busy(memory_busy),.fault(memory_fault),.fault_code(memory_fault_code),
 .packet_count(),.command_count(),.status_count(),.done_count(),.retired_count());
always @(posedge clk)begin
 if(rst)begin
  notice_pending<=0;hls_rq_sent<=0;placement_sent<=0;notify_owner<=0;notify_length<=0;notify_immediate<=0;notify_psn<=0;
 end else begin
  if(packet_valid && packet_ready)begin
   notice_pending<=packet_notify;hls_rq_sent<=0;placement_sent<=0;notify_owner<=packet_rq_context;
   notify_length<=packet_token[71:40];notify_psn<=packet_token[39:16];notify_immediate<=packet_notification;
  end
  if(m_hls_rq_owner_valid && m_hls_rq_owner_ready)hls_rq_sent<=1;
  if(m_rq_placement_valid && m_rq_placement_ready)placement_sent<=1;
  if(m_ack_retire_valid && m_ack_retire_ready)begin notice_pending<=0;notify_owner<=0;end
 end
end
endmodule
`resetall
