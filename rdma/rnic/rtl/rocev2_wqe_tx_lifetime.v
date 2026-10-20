// SPDX-License-Identifier: BSD-2-Clause-Views
// Production positive-WQE composition: one atomic full owner feeds the real
// issued-PSN/lifetime observer AND real native-role MAC framer/tag mapper.
// MAC proof/drain are connected hardware, not copied contexts/constant1.
// Actual same-core HLS drain, memory/RX/ACK proofs and the REAL CQ publisher
// remain caller responsibilities. Not a board selection or Linux RDMA device.
// Whole parent reset only; no abort/unpin/reset/tag-reuse qualification.
`resetall
`timescale 1ns/1ps
`default_nettype none
module rocev2_wqe_tx_lifetime #(
    parameter MAX_QPS=8,
    parameter TX_TAG_WIDTH=16,
    parameter TS_WIDTH=96,
    parameter TAG_SEQUENCE_WIDTH=13,
    parameter TAIL_CYCLES=1024,
    parameter REAL_MAC_COMPLETION_ENABLE=1,
    parameter RETRY_ENABLE=0,
    parameter NATIVE_RECV_CPL_ENABLE=0,
    parameter REQUEST_CQ_ENABLE=0,
    parameter CLOCK_PERIOD_PS=4000
)(
    input wire clk,
    input wire rst,
    input wire enable,
    input wire parent_fault,
    input wire [587:0] s_owner_context,
    input wire [31:0] s_owner_local_ip,
    input wire [31:0] s_owner_peer_ip,
    input wire [23:0] s_owner_peer_qpn,
    input wire [47:0] s_owner_local_mac,
    input wire [47:0] s_owner_peer_mac,
    input wire s_owner_valid,
    output wire s_owner_ready,
    input wire [127:0] s_axis_ip_tdata,
    input wire [15:0] s_axis_ip_tkeep,
    input wire s_axis_ip_tvalid,
    output wire s_axis_ip_tready,
    input wire s_axis_ip_tlast,
    input wire s_axis_ip_tuser,
    input wire [127:0] s_axis_native_tdata,
    input wire [15:0] s_axis_native_tkeep,
    input wire s_axis_native_tvalid,
    output wire s_axis_native_tready,
    input wire s_axis_native_tlast,
    input wire [TX_TAG_WIDTH:0] s_axis_native_tuser,
    output wire [127:0] m_axis_mac_tdata,
    output wire [15:0] m_axis_mac_tkeep,
    output wire m_axis_mac_tvalid,
    input wire m_axis_mac_tready,
    output wire m_axis_mac_tlast,
    output wire [TX_TAG_WIDTH:0] m_axis_mac_tuser,
    input wire [TX_TAG_WIDTH-1:0] s_mac_cpl_tag,
    input wire [TS_WIDTH-1:0] s_mac_cpl_ts,
    input wire s_mac_cpl_valid,
    output wire s_mac_cpl_ready,
    output wire [TX_TAG_WIDTH-1:0] m_native_cpl_tag,
    output wire [TS_WIDTH-1:0] m_native_cpl_ts,
    output wire m_native_cpl_valid,
    input wire m_native_cpl_ready,
    output wire [587:0] m_expect_context,
    output wire [31:0] m_expect_local_ip,
    output wire [31:0] m_expect_peer_ip,
    output wire [23:0] m_expect_psn,
    output wire m_expect_valid,
    input wire m_expect_ready,
    output wire response_admission_ready,
    input wire [587:0] s_memory_context,
    input wire [7:0] s_memory_error,
    input wire s_memory_valid,
    output wire s_memory_ready,
    input wire [587:0] s_response_context,
    input wire [23:0] s_response_psn,
    input wire [7:0] s_response_opcode,
    input wire [7:0] s_response_syndrome,
    input wire s_response_valid,
    output wire s_response_ready,
    input wire [39:0] s_hls_ack,
    input wire s_hls_ack_valid,
    output wire s_hls_ack_ready,
    input wire memory_drained,
    input wire hls_transport_drained,
    input wire [655:0] s_request_done_data,
    input wire s_request_done_valid,
    output wire s_request_done_ready,
    output wire [587:0] m_cq_context,
    output wire m_cq_valid,
    input wire m_cq_ready,
    input wire [587:0] s_cq_commit_context,
    input wire [7:0] s_cq_commit_error,
    input wire s_cq_commit_valid,
    output wire s_cq_commit_ready,
    output wire [MAX_QPS-1:0] queue_guard,
    output wire busy,
    output wire fault,
    output wire [7:0] fault_code,
    output wire [7:0] failed_status,
    output wire [6:0] proof_flags,
    output wire [31:0] committed_count,
    output wire local_tx_drained,
    output wire tags_exhausted,
    output wire [TX_TAG_WIDTH-1:0] active_tag,
    output wire [31:0] frame_count,
    output wire [31:0] receipt_count,
    output wire [31:0] mac_proof_count,
    input wire [23:0] cfg_qpn,
    input wire [15:0] cfg_pd,
    input wire [63:0] cfg_cookie,
    input wire [63:0] cfg_epoch,
    input wire [4:0] cfg_timeout,
    input wire [2:0] cfg_retry,
    input wire [2:0] cfg_rnr_retry,
    input wire cfg_valid,
    output wire cfg_ready,
    output wire [23:0] rsp_qpn,
    output wire [15:0] rsp_pd,
    output wire [63:0] rsp_cookie,
    output wire [63:0] rsp_epoch,
    output wire [4:0] rsp_timeout,
    output wire [2:0] rsp_retry,
    output wire [2:0] rsp_rnr_retry,
    output wire [7:0] rsp_error,
    output wire rsp_valid,
    input wire rsp_ready,
    input wire [587:0] s_control_context,
    input wire [23:0] s_control_psn,
    input wire [7:0] s_control_syndrome,
    input wire s_control_valid,
    output wire s_control_ready,
    output wire [31:0] retry_count,
    output wire [31:0] rnr_count
);
wire life_owner_ready,mac_owner_ready,life_busy,mac_busy,life_fault,mac_fault,mac_fault_now;
wire [7:0] life_fault_code,mac_fault_code;
wire [MAX_QPS-1:0] life_guard,mac_guard;
wire [587:0] mac_context;
wire [7:0] mac_error;
wire mac_valid,mac_ready,life_commit_ready;
wire mac_drained,replay_owner_ready,replay_valid,replay_ready,replay_drained,replay_fault,replay_failed;
wire [7:0] replay_fault_code,replay_status,life_failed_status;
wire [MAX_QPS-1:0] replay_guard;
wire [587:0] replay_context,final_mac_context;
wire [47:0] replay_local_mac,replay_peer_mac;
wire [127:0] mac_ip_data;wire [15:0] mac_ip_keep;
wire mac_ip_valid,mac_ip_ready,mac_ip_last,final_mac_valid,final_mac_ready;
reg binding_fault=0;
reg request_proved=0,request_fault=0;
wire outer_fault=(parent_fault!==1'b0) || binding_fault || request_fault || mac_fault_now || replay_fault || replay_failed;
wire [7:0] request_opcode=m_cq_context[339:324]==1 ? 8'h0a : m_cq_context[339:324]==2 ? 8'h0c : 8'h04;
wire request_match=(^s_request_done_data)!==1'bx && s_request_done_data[587:0]===m_cq_context &&
    s_request_done_data[611:588]===m_expect_psn && s_request_done_data[635:612]==(m_expect_psn+24'd1) &&
    s_request_done_data[643:636]==request_opcode && s_request_done_data[655:644]==0;
// This is the actual producer receipt AND the same WR's existing native
// memory/RX/ACK/MAC witnesses, never a constant/global empty/idle substitute.
assign s_request_done_ready=REQUEST_CQ_ENABLE && life_busy && !request_proved && request_match &&
    proof_flags[5:0]==6'h3f && memory_drained===1'b1 && !outer_fault && !life_fault && !rst;
assign s_owner_ready=life_owner_ready && mac_owner_ready && (parent_fault===1'b0) &&
    replay_owner_ready && !binding_fault && !mac_fault && !life_fault;
wire owner_take=(s_owner_valid===1'b1) && s_owner_ready;
// The mutual READY join offers to BOTH on the SAME edge, never half captures
// one child. Invalid idle owners are caught by this trusted binding itself.
wire bad_idle_owner=enable && !life_busy && !mac_busy && !tags_exhausted &&
    ((s_owner_valid!==1'b0 && s_owner_valid!==1'b1) || (s_owner_valid && (!life_owner_ready || !mac_owner_ready)));
wire commit_gate=!outer_fault && !bad_idle_owner && !life_fault;
assign s_cq_commit_ready=life_commit_ready && commit_gate;
assign queue_guard=(outer_fault || bad_idle_owner || life_fault) ? {MAX_QPS{1'b1}} : life_guard | mac_guard | replay_guard;
assign busy=life_busy || mac_busy || outer_fault || bad_idle_owner;
assign fault=outer_fault || life_fault || bad_idle_owner;
assign fault_code=binding_fault ? 8'he6 : request_fault ? 8'he9 : (parent_fault!==1'b0) ? 8'he7 :
 replay_fault ? replay_fault_code : replay_failed ? 8'he8 : mac_fault_now ? mac_fault_code : life_fault_code;
assign failed_status=replay_failed ? replay_status : life_failed_status;
assign local_tx_drained=mac_drained && replay_drained;
assign replay_ready=mac_owner_ready;
always @(posedge clk)begin
    if(rst)binding_fault<=0;
    else if(bad_idle_owner || parent_fault!==1'b0)binding_fault<=1;
end
always @(posedge clk)begin
    if(rst)begin request_proved<=0;request_fault<=0;end
    else begin
        if(owner_take)request_proved<=0;
        if(s_request_done_valid && s_request_done_ready)request_proved<=1;
        if(REQUEST_CQ_ENABLE && ((s_request_done_valid!==1'b0 && s_request_done_valid!==1'b1) ||
           s_request_done_valid && (!life_busy || request_proved || (proof_flags[5:0]==6'h3f && !request_match))))request_fault<=1;
    end
end
rocev2_wqe_mac_tx #(.MAX_QPS(MAX_QPS),.TX_TAG_WIDTH(TX_TAG_WIDTH),.TS_WIDTH(TS_WIDTH),
    .TAG_SEQUENCE_WIDTH(TAG_SEQUENCE_WIDTH),.TAIL_CYCLES(TAIL_CYCLES),
    .REAL_MAC_COMPLETION_ENABLE(REAL_MAC_COMPLETION_ENABLE),.NATIVE_RECV_CPL_ENABLE(NATIVE_RECV_CPL_ENABLE)) mac_owner(
    .clk(clk),.rst(rst),.enable(enable || (RETRY_ENABLE && life_busy)),.s_owner_context(replay_valid ? replay_context : s_owner_context),
    .s_owner_local_mac(replay_valid ? replay_local_mac : s_owner_local_mac),
    .s_owner_peer_mac(replay_valid ? replay_peer_mac : s_owner_peer_mac),
    .s_owner_valid(owner_take || replay_valid),.s_owner_ready(mac_owner_ready),
    .s_axis_ip_tdata(mac_ip_data),.s_axis_ip_tkeep(mac_ip_keep),
    .s_axis_ip_tvalid(mac_ip_valid),.s_axis_ip_tready(mac_ip_ready),
    .s_axis_ip_tlast(mac_ip_last),.s_axis_ip_tuser(RETRY_ENABLE ? 1'b0 : s_axis_ip_tuser),
    .s_axis_native_tdata(s_axis_native_tdata),.s_axis_native_tkeep(s_axis_native_tkeep),
    .s_axis_native_tvalid(s_axis_native_tvalid),.s_axis_native_tready(s_axis_native_tready),
    .s_axis_native_tlast(s_axis_native_tlast),.s_axis_native_tuser(s_axis_native_tuser),
    .m_axis_mac_tdata(m_axis_mac_tdata),.m_axis_mac_tkeep(m_axis_mac_tkeep),
    .m_axis_mac_tvalid(m_axis_mac_tvalid),.m_axis_mac_tready(m_axis_mac_tready),
    .m_axis_mac_tlast(m_axis_mac_tlast),.m_axis_mac_tuser(m_axis_mac_tuser),
    .s_mac_cpl_tag(s_mac_cpl_tag),.s_mac_cpl_ts(s_mac_cpl_ts),.s_mac_cpl_valid(s_mac_cpl_valid),.s_mac_cpl_ready(s_mac_cpl_ready),
    .m_native_cpl_tag(m_native_cpl_tag),.m_native_cpl_ts(m_native_cpl_ts),
    .m_native_cpl_valid(m_native_cpl_valid),.m_native_cpl_ready(m_native_cpl_ready),
    .m_mac_context(mac_context),.m_mac_error(mac_error),.m_mac_timestamp(),
    .m_mac_valid(mac_valid),.m_mac_ready(mac_ready),.local_tx_drained(mac_drained),
    .queue_guard(mac_guard),.busy(mac_busy),.fault_pending(mac_fault_now),.fault(mac_fault),.fault_code(mac_fault_code),
    .tags_exhausted(tags_exhausted),.active_tag(active_tag),.frame_count(frame_count),.receipt_count(receipt_count),.proof_count(mac_proof_count));
rocev2_wqe_lifetime #(.MAX_QPS(MAX_QPS)) lifetime(
    .clk(clk),.rst(rst),.enable(enable),.s_owner_context(s_owner_context),
    .s_owner_local_ip(s_owner_local_ip),.s_owner_peer_ip(s_owner_peer_ip),.s_owner_peer_qpn(s_owner_peer_qpn),
    .s_owner_valid(owner_take),.s_owner_ready(life_owner_ready),
    .s_tx_data(s_axis_ip_tdata),.s_tx_keep(s_axis_ip_tkeep),.s_tx_last(s_axis_ip_tlast),
    .s_tx_user(s_axis_ip_tuser),.s_tx_valid(s_axis_ip_tvalid),.s_tx_ready(s_axis_ip_tready),
    .m_expect_context(m_expect_context),.m_expect_local_ip(m_expect_local_ip),.m_expect_peer_ip(m_expect_peer_ip),
    .m_expect_psn(m_expect_psn),.m_expect_valid(m_expect_valid),.m_expect_ready(m_expect_ready),
    .response_admission_ready(response_admission_ready),
    .s_memory_context(s_memory_context),.s_memory_error(s_memory_error),.s_memory_valid(s_memory_valid),.s_memory_ready(s_memory_ready),
    .s_response_context(s_response_context),.s_response_psn(s_response_psn),.s_response_opcode(s_response_opcode),
    .s_response_syndrome(s_response_syndrome),.s_response_valid(s_response_valid),.s_response_ready(s_response_ready),
    .s_hls_ack(s_hls_ack),.s_hls_ack_valid(s_hls_ack_valid),.s_hls_ack_ready(s_hls_ack_ready),
    .s_mac_context(final_mac_context),.s_mac_error(RETRY_ENABLE ? 8'd0 : mac_error),
    .s_mac_valid(final_mac_valid),.s_mac_ready(final_mac_ready),
    .memory_drained(memory_drained),.transport_drained((hls_transport_drained || (REQUEST_CQ_ENABLE && request_proved)) && local_tx_drained),
    .m_cq_context(m_cq_context),.m_cq_valid(m_cq_valid),.m_cq_ready(m_cq_ready),
    .s_cq_commit_context(s_cq_commit_context),.s_cq_commit_error(s_cq_commit_error),
    .s_cq_commit_valid(s_cq_commit_valid && commit_gate),.s_cq_commit_ready(life_commit_ready),
    .queue_guard(life_guard),.busy(life_busy),.fault(life_fault),.fault_code(life_fault_code),
    .failed_status(life_failed_status),.proof_flags(proof_flags),.committed_count(committed_count));
generate if(RETRY_ENABLE)begin : retained_replay
rocev2_wqe_replay #(.MAX_QPS(MAX_QPS),.CLOCK_PERIOD_PS(CLOCK_PERIOD_PS)) replay(
    .clk(clk),.rst(rst),.cfg_qpn(cfg_qpn),.cfg_pd(cfg_pd),.cfg_cookie(cfg_cookie),.cfg_epoch(cfg_epoch),
    .cfg_timeout(cfg_timeout),.cfg_retry(cfg_retry),.cfg_rnr_retry(cfg_rnr_retry),.cfg_valid(cfg_valid),.cfg_ready(cfg_ready),
    .rsp_qpn(rsp_qpn),.rsp_pd(rsp_pd),.rsp_cookie(rsp_cookie),.rsp_epoch(rsp_epoch),
    .rsp_timeout(rsp_timeout),.rsp_retry(rsp_retry),.rsp_rnr_retry(rsp_rnr_retry),
    .rsp_error(rsp_error),.rsp_valid(rsp_valid),.rsp_ready(rsp_ready),
    .s_owner_context(s_owner_context),.s_owner_local_mac(s_owner_local_mac),.s_owner_peer_mac(s_owner_peer_mac),
    .s_owner_valid(owner_take),.s_owner_ready(replay_owner_ready),
    .s_axis_ip_tdata(s_axis_ip_tdata),.s_axis_ip_tkeep(s_axis_ip_tkeep),.s_axis_ip_tvalid(s_axis_ip_tvalid),
    .s_axis_ip_tready(s_axis_ip_tready),.s_axis_ip_tlast(s_axis_ip_tlast),.s_axis_ip_tuser(s_axis_ip_tuser),
    .m_axis_ip_tdata(mac_ip_data),.m_axis_ip_tkeep(mac_ip_keep),.m_axis_ip_tlast(mac_ip_last),
    .m_axis_ip_tvalid(mac_ip_valid),.m_axis_ip_tready(mac_ip_ready),
    .m_replay_context(replay_context),.m_replay_local_mac(replay_local_mac),.m_replay_peer_mac(replay_peer_mac),
    .m_replay_valid(replay_valid),.m_replay_ready(replay_ready),
    .s_mac_context(mac_context),.s_mac_error(mac_error),.s_mac_valid(mac_valid),.s_mac_ready(mac_ready),
    .issued_psn(m_expect_psn),.s_positive_context(s_response_context),.s_positive_valid(s_response_valid && s_response_ready),
    .s_control_context(s_control_context),.s_control_psn(s_control_psn),.s_control_syndrome(s_control_syndrome),
    .s_control_valid(s_control_valid),.s_control_ready(s_control_ready),
    .m_done_context(final_mac_context),.m_done_valid(final_mac_valid),.m_done_ready(final_mac_ready),
    .s_retire_context(s_cq_commit_context),.s_retire_valid(s_cq_commit_valid && s_cq_commit_ready),
    .queue_guard(replay_guard),.busy(),.io_drained(replay_drained),
    .failed(replay_failed),.failure_status(replay_status),.fault(replay_fault),.fault_code(replay_fault_code),
    .attempt_count(),.retry_count(retry_count),.rnr_count(rnr_count));
end else begin : no_replay
assign replay_owner_ready=1;assign replay_valid=0;assign replay_context=0;
assign replay_local_mac=0;assign replay_peer_mac=0;assign replay_drained=1;
assign replay_fault=0;assign replay_failed=0;assign replay_fault_code=0;assign replay_status=0;assign replay_guard=0;
assign mac_ip_data=s_axis_ip_tdata;assign mac_ip_keep=s_axis_ip_tkeep;assign mac_ip_valid=s_axis_ip_tvalid;
assign mac_ip_last=s_axis_ip_tlast;assign s_axis_ip_tready=mac_ip_ready;
assign final_mac_context=mac_context;assign final_mac_valid=mac_valid;assign mac_ready=final_mac_ready;
assign cfg_ready=0;assign rsp_qpn=0;assign rsp_pd=0;assign rsp_cookie=0;assign rsp_epoch=0;
assign rsp_timeout=0;assign rsp_retry=0;assign rsp_rnr_retry=0;assign rsp_error=0;assign rsp_valid=0;
assign s_control_ready=0;assign retry_count=0;assign rnr_count=0;
end endgenerate
endmodule
`resetall
