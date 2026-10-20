// SPDX-License-Identifier: BSD-2-Clause-Views
// Copyright (c) 2026 jyohukuchan
// Packet authorization -> bound MR key/offset -> actual paged Corundum backend.
// OFFLINE candidate only; parent PCIe engine, board/CSR and kernel not integrated.
// Host MUST hold cfg_admission_pause across MR-key allocation, all PTE loads,
// seal and successful response consumption. Pause only gates NEW admission;
// accepted packets, memory leases and TX responses always drain normally.
// Global quiescent requires both config paths, memory AND wire response idle.
// Reset is NOT unpin/cancel; requires real parent-engine drain and fresh epochs.
`resetall
`timescale 1ns/1ps
`default_nettype none
module rocev2_paged_responder #(
    parameter RAM_SIZE=8192,
    parameter RAM_ADDR_WIDTH=15,
    parameter SEG_COUNT=2,
    parameter SEG_DATA_WIDTH=256,
    parameter SEG_BE_WIDTH=SEG_DATA_WIDTH/8,
    parameter SEG_ADDR_WIDTH=RAM_ADDR_WIDTH-$clog2(SEG_COUNT*SEG_BE_WIDTH),
    parameter RAM_SEL_WIDTH=4,
    parameter DMA_LEN_WIDTH=16,
    parameter TAG_WIDTH=16,
    // Optional local WQE client of the SAME protected MR table. The caller
    // retains local_work_guard through actual memory/wire/CQ completion.
    parameter LOCAL_MEMORY_ENABLE=0,
    parameter LOCAL_WQE_ENABLE=0,
    // Select ONE shared responder core for remote requests and native SQ work.
    parameter EXTERNAL_REPLAY_ENABLE=0,
    parameter QP_TX_ENABLE=0,
    parameter RECV_ENABLE=0,
    parameter RNR_ENABLE=0,
    parameter RECV_RETIRE_ENABLE=0,
    parameter RECV_CQ_ENABLE=0,
    parameter REQUEST_CQ_ENABLE=0,
    parameter SHARED_HLS_ENABLE=0
)(
    input wire clk,
    input wire rst,
    input wire [587:0] s_recv_context,
    input wire s_recv_valid,
    output wire s_recv_ready,
    output wire [23:0] m_recv_query_qpn,
    output wire [587:0] m_recv_placement_context,
    output wire [31:0] m_recv_placement_length,
    output wire m_recv_placement_valid,
    input wire m_recv_placement_ready,
    input wire recv_owned_guard,
    output wire [23:0] m_recv_placement_psn,
    output wire [679:0] m_recv_core_data,
    output wire m_recv_core_valid,
    input wire m_recv_core_ready,
    output wire [655:0] m_request_done_data,
    output wire m_request_done_valid,
    input wire m_request_done_ready,
    input wire recv_ack_admission_ready,
    input wire [587:0] s_recv_retire_context,
    input wire s_recv_retire_valid,
    output wire s_recv_retire_ready,
    input wire [587:0] s_local_owner_context,
    input wire s_local_owner_valid,
    output wire s_local_owner_ready,
    input wire [247:0] s_local_sq_tdata,
    input wire s_local_sq_tvalid,
    output wire s_local_sq_tready,
    input wire [127:0] s_local_rx_tdata,
    input wire [15:0] s_local_rx_tkeep,
    input wire s_local_rx_tvalid,
    output wire s_local_rx_tready,
    input wire s_local_rx_tlast,
    input wire s_local_rx_tuser,
    output wire [127:0] m_local_tx_tdata,
    output wire [15:0] m_local_tx_tkeep,
    output wire m_local_tx_tvalid,
    input wire m_local_tx_tready,
    output wire m_local_tx_tlast,
    output wire [39:0] m_local_ack_tdata,
    output wire m_local_ack_tvalid,
    input wire m_local_ack_tready,
    output wire [95:0] m_local_write_command,
    output wire m_local_write_command_valid,
    input wire m_local_write_command_ready,
    output wire [511:0] m_local_write_tdata,
    output wire [63:0] m_local_write_tkeep,
    output wire m_local_write_tvalid,
    input wire m_local_write_tready,
    output wire m_local_write_tlast,
    output wire [95:0] m_local_read_command,
    output wire m_local_read_command_valid,
    input wire m_local_read_command_ready,
    input wire [511:0] s_local_read_tdata,
    input wire [63:0] s_local_read_tkeep,
    input wire s_local_read_tvalid,
    output wire s_local_read_tready,
    input wire s_local_read_tlast,
    input wire [587:0] s_local_retire_context,
    input wire s_local_retire_valid,
    output wire s_local_retire_ready,
    input wire local_core_drained,
    output wire [7:0] local_hls_queue_guard,
    output wire local_hls_active,
    output wire shared_hls_fault,
    output wire [7:0] shared_hls_fault_code,
    output wire [31:0] local_hls_local_ip,
    output wire [31:0] local_hls_peer_ip,
    output wire [23:0] local_hls_peer_qpn,
    input wire cfg_admission_pause,
    input wire [127:0] s_axis_rx_tdata,
    input wire [15:0] s_axis_rx_tkeep,
    input wire s_axis_rx_tvalid,
    output wire s_axis_rx_tready,
    input wire s_axis_rx_tlast,
    input wire s_axis_rx_tuser,
    output wire [127:0] m_axis_tx_tdata,
    output wire [15:0] m_axis_tx_tkeep,
    output wire m_axis_tx_tvalid,
    input wire m_axis_tx_tready,
    output wire m_axis_tx_tlast,
    input wire [2:0] cfg_qp_number,
    input wire [23:0] cfg_peer_qp_number,
    input wire [15:0] cfg_qp_pd,
    input wire [31:0] cfg_local_ip,
    input wire [31:0] cfg_peer_ip,
    input wire [23:0] cfg_rx_psn,
    input wire [23:0] cfg_tx_psn,
    input wire cfg_qp_tx_only,
    input wire cfg_qp_valid,
    output wire cfg_qp_ready,
    output wire qp_ready,
    input wire [1:0] cfg_mr_command,
    input wire [2:0] cfg_mr_index,
    input wire [15:0] cfg_mr_pd,
    input wire [31:0] cfg_mr_key,
    input wire [63:0] cfg_mr_virtual_address,
    input wire [63:0] cfg_mr_length,
    input wire [3:0] cfg_mr_access,
    input wire cfg_mr_valid,
    output wire cfg_mr_ready,
    output wire [7:0] cfg_mr_response_error,
    output wire [31:0] cfg_mr_response_key,
    output wire cfg_mr_response_valid,
    input wire cfg_mr_response_ready,
    // Privileged AUTHORIZED local memory client; not MR or WR/CQ completion.
    input wire s_local_memory_command_write,
    input wire [63:0] s_local_memory_command_offset,
    input wire [31:0] s_local_memory_command_length,
    input wire [31:0] s_local_memory_command_key,
    input wire [15:0] s_local_memory_command_tag,
    input wire s_local_memory_command_valid,
    output wire s_local_memory_command_ready,
    input wire [511:0] s_axis_local_memory_write_tdata,
    input wire [63:0] s_axis_local_memory_write_tkeep,
    input wire s_axis_local_memory_write_tlast,
    input wire s_axis_local_memory_write_tvalid,
    output wire s_axis_local_memory_write_tready,
    output wire [511:0] m_axis_local_memory_read_tdata,
    output wire [63:0] m_axis_local_memory_read_tkeep,
    output wire m_axis_local_memory_read_tlast,
    output wire m_axis_local_memory_read_tvalid,
    input wire m_axis_local_memory_read_tready,
    output wire [15:0] m_local_memory_status_tag,
    output wire [7:0] m_local_memory_status_error,
    output wire m_local_memory_status_valid,
    input wire m_local_memory_status_ready,
    output wire local_memory_busy,
    input wire local_work_guard,
    output wire local_configuration_idle,
    input wire [15:0] s_local_mr_request_pd,
    input wire [31:0] s_local_mr_request_key,
    input wire [63:0] s_local_mr_request_address,
    input wire [31:0] s_local_mr_request_length,
    input wire [2:0] s_local_mr_request_operation,
    input wire [15:0] s_local_mr_request_tag,
    input wire s_local_mr_request_valid,
    output wire s_local_mr_request_ready,
    output wire [15:0] m_local_mr_response_tag,
    output wire [7:0] m_local_mr_response_error,
    output wire [63:0] m_local_mr_response_offset,
    output wire [31:0] m_local_mr_response_length,
    output wire m_local_mr_response_valid,
    input wire m_local_mr_response_ready,
    output wire [7:0] m_reject_error,
    output wire [23:0] m_reject_qpn,
    output wire [23:0] m_reject_psn,
    output wire m_reject_valid,
    input wire m_reject_ready,
    output wire quiescent,
    output wire fault,
    output wire [7:0] fault_code,
    output wire [31:0] accepted_count,
    output wire [31:0] rejected_count,
    output wire [31:0] completed_count,
    output wire [31:0] tx_deferred_cycles,
    output wire [31:0] rx_integrity_good_count,
    output wire [31:0] rx_integrity_drop_count,
    output wire [63:0] m_dma_read_address,
    output wire [RAM_SEL_WIDTH-1:0] m_dma_read_ram_sel,
    output wire [RAM_ADDR_WIDTH-1:0] m_dma_read_ram_address,
    output wire [DMA_LEN_WIDTH-1:0] m_dma_read_length,
    output wire [TAG_WIDTH-1:0] m_dma_read_tag,
    output wire m_dma_read_valid,
    input wire m_dma_read_ready,
    input wire [TAG_WIDTH-1:0] s_dma_read_status_tag,
    input wire [3:0] s_dma_read_status_error,
    input wire s_dma_read_status_valid,
    output wire [63:0] m_dma_write_address,
    output wire [RAM_SEL_WIDTH-1:0] m_dma_write_ram_sel,
    output wire [RAM_ADDR_WIDTH-1:0] m_dma_write_ram_address,
    output wire [31:0] m_dma_write_imm,
    output wire m_dma_write_imm_en,
    output wire [DMA_LEN_WIDTH-1:0] m_dma_write_length,
    output wire [TAG_WIDTH-1:0] m_dma_write_tag,
    output wire m_dma_write_valid,
    input wire m_dma_write_ready,
    input wire [TAG_WIDTH-1:0] s_dma_write_status_tag,
    input wire [3:0] s_dma_write_status_error,
    input wire s_dma_write_status_valid,
    input wire [SEG_COUNT*RAM_SEL_WIDTH-1:0] dma_ram_wr_cmd_sel,
    input wire [SEG_COUNT*SEG_BE_WIDTH-1:0] dma_ram_wr_cmd_be,
    input wire [SEG_COUNT*SEG_ADDR_WIDTH-1:0] dma_ram_wr_cmd_addr,
    input wire [SEG_COUNT*SEG_DATA_WIDTH-1:0] dma_ram_wr_cmd_data,
    input wire [SEG_COUNT-1:0] dma_ram_wr_cmd_valid,
    output wire [SEG_COUNT-1:0] dma_ram_wr_cmd_ready,
    output wire [SEG_COUNT-1:0] dma_ram_wr_done,
    input wire [SEG_COUNT*RAM_SEL_WIDTH-1:0] dma_ram_rd_cmd_sel,
    input wire [SEG_COUNT*SEG_ADDR_WIDTH-1:0] dma_ram_rd_cmd_addr,
    input wire [SEG_COUNT-1:0] dma_ram_rd_cmd_valid,
    output wire [SEG_COUNT-1:0] dma_ram_rd_cmd_ready,
    output wire [SEG_COUNT*SEG_DATA_WIDTH-1:0] dma_ram_rd_resp_data,
    output wire [SEG_COUNT-1:0] dma_ram_rd_resp_valid,
    input wire [SEG_COUNT-1:0] dma_ram_rd_resp_ready,
    input wire [2:0] cfg_page_command,
    input wire [2:0] cfg_page_slot,
    input wire [31:0] cfg_page_key,
    input wire [31:0] cfg_page_length,
    input wire [11:0] cfg_page_first_offset,
    input wire [7:0] cfg_page_page_index,
    input wire [63:0] cfg_page_dma_page,
    input wire cfg_page_valid,
    output wire cfg_page_ready,
    output wire [7:0] cfg_page_response_error,
    output wire [31:0] cfg_page_response_key,
    output wire cfg_page_response_valid,
    input wire cfg_page_response_ready,
    output wire memory_drained,
    output wire [31:0] dma_command_count,
    output wire [31:0] dma_fence_count,
    output wire [31:0] dma_completion_count
);
wire m_memory_command_write;
wire [63:0] m_memory_command_address;
wire [31:0] m_memory_command_length;
wire [15:0] m_memory_command_tag;
wire [31:0] m_memory_command_key;
wire [63:0] m_memory_command_offset;
wire m_memory_command_valid;
wire m_memory_command_ready;
wire [511:0] m_axis_memory_write_tdata;
wire [63:0] m_axis_memory_write_tkeep;
wire m_axis_memory_write_tvalid;
wire m_axis_memory_write_tready;
wire m_axis_memory_write_tlast;
wire [511:0] s_axis_memory_read_tdata;
wire [63:0] s_axis_memory_read_tkeep;
wire s_axis_memory_read_tvalid;
wire s_axis_memory_read_tready;
wire s_axis_memory_read_tlast;
wire [15:0] s_memory_status_tag;
wire [7:0] s_memory_status_error;
wire s_memory_status_valid;
wire s_memory_status_ready;
wire guard_fault,guard_quiescent,guard_mr_ready,guard_qp_ready;
wire backend_fault,backend_idle,backend_drained,backend_page_ready;
wire [7:0] guard_fault_code,backend_fault_code;
wire memory_mux_guard,memory_mux_fault;
wire [7:0] memory_mux_fault_code;
wire effective_local_work_guard=local_work_guard || (LOCAL_MEMORY_ENABLE && memory_mux_guard);
wire backend_command_write,backend_command_valid,backend_command_ready;
wire [63:0] backend_command_offset;
wire [31:0] backend_command_length,backend_command_key;
wire [15:0] backend_command_tag;
wire [511:0] backend_write_data,backend_read_data;
wire [63:0] backend_write_keep,backend_read_keep;
wire backend_write_last,backend_write_valid,backend_write_ready;
wire backend_read_last,backend_read_valid,backend_read_ready;
wire [15:0] backend_status_tag;
wire [7:0] backend_status_error;
wire backend_status_valid,backend_status_ready;
wire guard_local_configuration_idle;
reg [31:0] saved_hls_local_ip=0,saved_hls_peer_ip=0;
reg [23:0] saved_hls_peer_qpn=0;
assign local_hls_local_ip=saved_hls_local_ip;
assign local_hls_peer_ip=saved_hls_peer_ip;
assign local_hls_peer_qpn=saved_hls_peer_qpn;
// Observe the SAME accepted privileged QP configuration, never packet fields.
always @(posedge clk)begin
    if(rst)begin saved_hls_local_ip<=0;saved_hls_peer_ip<=0;saved_hls_peer_qpn<=0;end
    else if(cfg_qp_valid && cfg_qp_ready && (!QP_TX_ENABLE || !cfg_qp_tx_only))begin
        saved_hls_local_ip<=cfg_local_ip;saved_hls_peer_ip<=cfg_peer_ip;
        saved_hls_peer_qpn<=cfg_peer_qp_number;
    end
end
// PTE ownership is tracked independently of cfg_ready/quiescence. Those
// signals include the local lease and MUST NOT feed local admission back into
// itself, or a held local result can also deadlock an independent RX lookup.
reg page_configuration_pending=0;
wire page_management_idle=!cfg_page_valid && !page_configuration_pending && !cfg_page_response_valid;
wire shared_admission_pause=cfg_admission_pause || !page_management_idle ||
    cfg_mr_valid || cfg_qp_valid || backend_fault;
assign local_configuration_idle=LOCAL_WQE_ENABLE && guard_local_configuration_idle &&
    page_management_idle && !cfg_mr_valid && !cfg_qp_valid && !fault && !rst;
wire configuration_allowed=cfg_admission_pause && backend_idle && backend_page_ready && !fault && !rst;
assign cfg_mr_ready=guard_mr_ready && configuration_allowed;
assign cfg_qp_ready=guard_qp_ready && configuration_allowed;
// MR management has priority; no PTE capture while an MR command/response or
// QP setup is pending. A PTE command/response in turn blocks MR/QP capture.
assign cfg_page_ready=backend_page_ready && cfg_admission_pause && guard_mr_ready &&
    !cfg_mr_valid && !cfg_qp_valid && !fault && !rst;
assign memory_drained=backend_drained && backend_idle && !local_memory_busy && !fault && !rst;
assign quiescent=guard_quiescent && guard_mr_ready && backend_page_ready && memory_drained;
assign fault=guard_fault || backend_fault || memory_mux_fault;
assign fault_code=guard_fault ? guard_fault_code : backend_fault ? backend_fault_code | 8'h80 :
    memory_mux_fault ? (8'he0 | memory_mux_fault_code[4:0]) : 8'd0;
initial begin
    if(LOCAL_MEMORY_ENABLE!=0 && LOCAL_MEMORY_ENABLE!=1)$fatal(1,"local memory mode must be static0or1");
    if(LOCAL_MEMORY_ENABLE && (!LOCAL_WQE_ENABLE || TAG_WIDTH!=16))
        $fatal(1,"local payload memory requires SAME MR client and complete16-bit tags");
end
generate if(LOCAL_MEMORY_ENABLE)begin : shared_payload_memory
    // This port MUST come from the trusted executor of a SAME-MR-authorized
    // WQE. It is not a public raw-DMA or alternate registration interface.
    // Management pause cannot cancel already-authorized local memory work.
    rocev2_memory_client_arbiter memory_clients (
        .clk(clk),.rst(rst),.enable(!guard_fault && !backend_fault),
        .s_command_write({s_local_memory_command_write,m_memory_command_write}),
        .s_command_offset({s_local_memory_command_offset,m_memory_command_offset}),
        .s_command_length({s_local_memory_command_length,m_memory_command_length}),
        .s_command_key({s_local_memory_command_key,m_memory_command_key}),
        .s_command_tag({s_local_memory_command_tag,m_memory_command_tag}),
        .s_command_valid({s_local_memory_command_valid,m_memory_command_valid}),
        .s_command_ready({s_local_memory_command_ready,m_memory_command_ready}),
        .s_axis_write_tdata({s_axis_local_memory_write_tdata,m_axis_memory_write_tdata}),
        .s_axis_write_tkeep({s_axis_local_memory_write_tkeep,m_axis_memory_write_tkeep}),
        .s_axis_write_tlast({s_axis_local_memory_write_tlast,m_axis_memory_write_tlast}),
        .s_axis_write_tvalid({s_axis_local_memory_write_tvalid,m_axis_memory_write_tvalid}),
        .s_axis_write_tready({s_axis_local_memory_write_tready,m_axis_memory_write_tready}),
        .m_axis_read_tdata({m_axis_local_memory_read_tdata,s_axis_memory_read_tdata}),
        .m_axis_read_tkeep({m_axis_local_memory_read_tkeep,s_axis_memory_read_tkeep}),
        .m_axis_read_tlast({m_axis_local_memory_read_tlast,s_axis_memory_read_tlast}),
        .m_axis_read_tvalid({m_axis_local_memory_read_tvalid,s_axis_memory_read_tvalid}),
        .m_axis_read_tready({m_axis_local_memory_read_tready,s_axis_memory_read_tready}),
        .m_status_tag({m_local_memory_status_tag,s_memory_status_tag}),
        .m_status_error({m_local_memory_status_error,s_memory_status_error}),
        .m_status_valid({m_local_memory_status_valid,s_memory_status_valid}),
        .m_status_ready({m_local_memory_status_ready,s_memory_status_ready}),
        .m_command_write(backend_command_write),.m_command_offset(backend_command_offset),
        .m_command_length(backend_command_length),.m_command_key(backend_command_key),
        .m_command_tag(backend_command_tag),.m_command_valid(backend_command_valid),
        .m_command_ready(backend_command_ready),
        .m_axis_write_tdata(backend_write_data),.m_axis_write_tkeep(backend_write_keep),
        .m_axis_write_tlast(backend_write_last),.m_axis_write_tvalid(backend_write_valid),
        .m_axis_write_tready(backend_write_ready),
        .s_axis_read_tdata(backend_read_data),.s_axis_read_tkeep(backend_read_keep),
        .s_axis_read_tlast(backend_read_last),.s_axis_read_tvalid(backend_read_valid),
        .s_axis_read_tready(backend_read_ready),
        .s_status_tag(backend_status_tag),.s_status_error(backend_status_error),
        .s_status_valid(backend_status_valid),.s_status_ready(backend_status_ready),
        .client_guard(),.busy(local_memory_busy),.configuration_guard(memory_mux_guard),
        .fault(memory_mux_fault),.fault_code(memory_mux_fault_code));
end else begin : dedicated_payload_memory
    assign backend_command_write=m_memory_command_write;
    assign backend_command_offset=m_memory_command_offset;
    assign backend_command_length=m_memory_command_length;
    assign backend_command_key=m_memory_command_key;
    assign backend_command_tag=m_memory_command_tag;
    assign backend_command_valid=m_memory_command_valid;
    assign m_memory_command_ready=backend_command_ready;
    assign backend_write_data=m_axis_memory_write_tdata;
    assign backend_write_keep=m_axis_memory_write_tkeep;
    assign backend_write_last=m_axis_memory_write_tlast;
    assign backend_write_valid=m_axis_memory_write_tvalid;
    assign m_axis_memory_write_tready=backend_write_ready;
    assign s_axis_memory_read_tdata=backend_read_data;
    assign s_axis_memory_read_tkeep=backend_read_keep;
    assign s_axis_memory_read_tlast=backend_read_last;
    assign s_axis_memory_read_tvalid=backend_read_valid;
    assign backend_read_ready=s_axis_memory_read_tready;
    assign s_memory_status_tag=backend_status_tag;
    assign s_memory_status_error=backend_status_error;
    assign s_memory_status_valid=backend_status_valid;
    assign backend_status_ready=s_memory_status_ready;
    assign s_local_memory_command_ready=0;assign s_axis_local_memory_write_tready=0;
    assign m_axis_local_memory_read_tdata=0;assign m_axis_local_memory_read_tkeep=0;
    assign m_axis_local_memory_read_tlast=0;assign m_axis_local_memory_read_tvalid=0;
    assign m_local_memory_status_tag=0;assign m_local_memory_status_error=0;assign m_local_memory_status_valid=0;
    assign local_memory_busy=0;assign memory_mux_guard=0;assign memory_mux_fault=0;assign memory_mux_fault_code=0;
end endgenerate
always @(posedge clk) begin
    if(rst) page_configuration_pending<=0;
    else begin
        if(cfg_page_valid && cfg_page_ready) page_configuration_pending<=1;
        if(cfg_page_response_valid && cfg_page_response_ready) page_configuration_pending<=0;
    end
end
initial if(SHARED_HLS_ENABLE && (!LOCAL_WQE_ENABLE || !LOCAL_MEMORY_ENABLE))
    $fatal(1,"shared HLS requires SAME MR and native local payload memory");
// Only one branch elaborates: this is a transport selection, not a third core.
initial if(QP_TX_ENABLE && !SHARED_HLS_ENABLE)$fatal(1,"QP TX readback requires the selected new shared core");
generate if(SHARED_HLS_ENABLE)begin : shared_hls
rocev2_shared_protected_responder #(.EXTERNAL_ADMISSION_CONTROL(1),.LOCAL_WQE_ENABLE(LOCAL_WQE_ENABLE),.QP_TX_ENABLE(QP_TX_ENABLE),.EXTERNAL_REPLAY_ENABLE(EXTERNAL_REPLAY_ENABLE),.RECV_ENABLE(RECV_ENABLE),.RNR_ENABLE(RNR_ENABLE),.RECV_RETIRE_ENABLE(RECV_RETIRE_ENABLE),.RECV_CQ_ENABLE(RECV_CQ_ENABLE),.REQUEST_CQ_ENABLE(REQUEST_CQ_ENABLE)) guard (
    .s_recv_context(s_recv_context),.s_recv_valid(s_recv_valid),.s_recv_ready(s_recv_ready),
    .m_recv_query_qpn(m_recv_query_qpn),.m_recv_placement_context(m_recv_placement_context),
    .m_recv_placement_length(m_recv_placement_length),.m_recv_placement_valid(m_recv_placement_valid),
    .m_recv_placement_ready(m_recv_placement_ready),.recv_owned_guard(recv_owned_guard),
    .m_recv_placement_psn(m_recv_placement_psn),.m_recv_core_data(m_recv_core_data),.m_recv_core_valid(m_recv_core_valid),.m_recv_core_ready(m_recv_core_ready),
    .m_request_done_data(m_request_done_data),.m_request_done_valid(m_request_done_valid),.m_request_done_ready(m_request_done_ready),
    .recv_ack_admission_ready(recv_ack_admission_ready),
    .s_recv_retire_context(s_recv_retire_context),.s_recv_retire_valid(s_recv_retire_valid),.s_recv_retire_ready(s_recv_retire_ready),
    .s_local_owner_context(s_local_owner_context),
    .s_local_owner_valid(s_local_owner_valid),
    .s_local_owner_ready(s_local_owner_ready),
    .s_local_sq_tdata(s_local_sq_tdata),
    .s_local_sq_tvalid(s_local_sq_tvalid),
    .s_local_sq_tready(s_local_sq_tready),
    .s_local_rx_tdata(s_local_rx_tdata),
    .s_local_rx_tkeep(s_local_rx_tkeep),
    .s_local_rx_tvalid(s_local_rx_tvalid),
    .s_local_rx_tready(s_local_rx_tready),
    .s_local_rx_tlast(s_local_rx_tlast),
    .s_local_rx_tuser(s_local_rx_tuser),
    .m_local_tx_tdata(m_local_tx_tdata),
    .m_local_tx_tkeep(m_local_tx_tkeep),
    .m_local_tx_tvalid(m_local_tx_tvalid),
    .m_local_tx_tready(m_local_tx_tready),
    .m_local_tx_tlast(m_local_tx_tlast),
    .m_local_ack_tdata(m_local_ack_tdata),
    .m_local_ack_tvalid(m_local_ack_tvalid),
    .m_local_ack_tready(m_local_ack_tready),
    .m_local_write_command(m_local_write_command),
    .m_local_write_command_valid(m_local_write_command_valid),
    .m_local_write_command_ready(m_local_write_command_ready),
    .m_local_write_tdata(m_local_write_tdata),
    .m_local_write_tkeep(m_local_write_tkeep),
    .m_local_write_tvalid(m_local_write_tvalid),
    .m_local_write_tready(m_local_write_tready),
    .m_local_write_tlast(m_local_write_tlast),
    .m_local_read_command(m_local_read_command),
    .m_local_read_command_valid(m_local_read_command_valid),
    .m_local_read_command_ready(m_local_read_command_ready),
    .s_local_read_tdata(s_local_read_tdata),
    .s_local_read_tkeep(s_local_read_tkeep),
    .s_local_read_tvalid(s_local_read_tvalid),
    .s_local_read_tready(s_local_read_tready),
    .s_local_read_tlast(s_local_read_tlast),
    .s_local_retire_context(s_local_retire_context),
    .s_local_retire_valid(s_local_retire_valid),
    .s_local_retire_ready(s_local_retire_ready),
    .local_core_drained(local_core_drained),
    .local_hls_queue_guard(local_hls_queue_guard),
    .local_hls_active(local_hls_active),
    .shared_hls_fault(shared_hls_fault),
    .shared_hls_fault_code(shared_hls_fault_code),
    .clk(clk),
    .rst(rst),
    .cfg_admission_pause(LOCAL_WQE_ENABLE ? shared_admission_pause :
        (cfg_admission_pause || !backend_page_ready || backend_fault)),
    .s_axis_rx_tdata(s_axis_rx_tdata),
    .s_axis_rx_tkeep(s_axis_rx_tkeep),
    .s_axis_rx_tvalid(s_axis_rx_tvalid),
    .s_axis_rx_tready(s_axis_rx_tready),
    .s_axis_rx_tlast(s_axis_rx_tlast),
    .s_axis_rx_tuser(s_axis_rx_tuser),
    .m_axis_tx_tdata(m_axis_tx_tdata),
    .m_axis_tx_tkeep(m_axis_tx_tkeep),
    .m_axis_tx_tvalid(m_axis_tx_tvalid),
    .m_axis_tx_tready(m_axis_tx_tready),
    .m_axis_tx_tlast(m_axis_tx_tlast),
    .cfg_qp_number(cfg_qp_number),
    .cfg_peer_qp_number(cfg_peer_qp_number),
    .cfg_qp_pd(cfg_qp_pd),
    .cfg_local_ip(cfg_local_ip),
    .cfg_peer_ip(cfg_peer_ip),
    .cfg_rx_psn(cfg_rx_psn),
    .cfg_tx_psn(cfg_tx_psn),
    .cfg_qp_tx_only(cfg_qp_tx_only),
    .cfg_qp_valid(cfg_qp_valid && configuration_allowed),
    .cfg_qp_ready(guard_qp_ready),
    .qp_ready(qp_ready),
    .cfg_mr_command(cfg_mr_command),
    .cfg_mr_index(cfg_mr_index),
    .cfg_mr_pd(cfg_mr_pd),
    .cfg_mr_key(cfg_mr_key),
    .cfg_mr_virtual_address(cfg_mr_virtual_address),
    .cfg_mr_dma_address(64'd0),
    .cfg_mr_length(cfg_mr_length),
    .cfg_mr_access(cfg_mr_access),
    .cfg_mr_valid(cfg_mr_valid && configuration_allowed),
    .cfg_mr_ready(guard_mr_ready),
    .cfg_mr_response_error(cfg_mr_response_error),
    .cfg_mr_response_key(cfg_mr_response_key),
    .cfg_mr_response_valid(cfg_mr_response_valid),
    .cfg_mr_response_ready(cfg_mr_response_ready),
    .local_work_guard(effective_local_work_guard),
    .local_configuration_idle(guard_local_configuration_idle),
    .s_local_mr_request_pd(s_local_mr_request_pd),
    .s_local_mr_request_key(s_local_mr_request_key),
    .s_local_mr_request_address(s_local_mr_request_address),
    .s_local_mr_request_length(s_local_mr_request_length),
    .s_local_mr_request_operation(s_local_mr_request_operation),
    .s_local_mr_request_tag(s_local_mr_request_tag),
    .s_local_mr_request_valid(s_local_mr_request_valid),
    .s_local_mr_request_ready(s_local_mr_request_ready),
    .m_local_mr_response_tag(m_local_mr_response_tag),
    .m_local_mr_response_error(m_local_mr_response_error),
    .m_local_mr_response_offset(m_local_mr_response_offset),
    .m_local_mr_response_length(m_local_mr_response_length),
    .m_local_mr_response_valid(m_local_mr_response_valid),
    .m_local_mr_response_ready(m_local_mr_response_ready),
    .m_memory_command_write(m_memory_command_write),
    .m_memory_command_address(m_memory_command_address),
    .m_memory_command_length(m_memory_command_length),
    .m_memory_command_tag(m_memory_command_tag),
    .m_memory_command_key(m_memory_command_key),
    .m_memory_command_offset(m_memory_command_offset),
    .m_memory_command_valid(m_memory_command_valid),
    .m_memory_command_ready(m_memory_command_ready),
    .m_axis_memory_write_tdata(m_axis_memory_write_tdata),
    .m_axis_memory_write_tkeep(m_axis_memory_write_tkeep),
    .m_axis_memory_write_tvalid(m_axis_memory_write_tvalid),
    .m_axis_memory_write_tready(m_axis_memory_write_tready),
    .m_axis_memory_write_tlast(m_axis_memory_write_tlast),
    .s_axis_memory_read_tdata(s_axis_memory_read_tdata),
    .s_axis_memory_read_tkeep(s_axis_memory_read_tkeep),
    .s_axis_memory_read_tvalid(s_axis_memory_read_tvalid),
    .s_axis_memory_read_tready(s_axis_memory_read_tready),
    .s_axis_memory_read_tlast(s_axis_memory_read_tlast),
    .s_memory_status_tag(s_memory_status_tag),
    .s_memory_status_error(s_memory_status_error),
    .s_memory_status_valid(s_memory_status_valid),
    .s_memory_status_ready(s_memory_status_ready),
    .m_reject_error(m_reject_error),
    .m_reject_qpn(m_reject_qpn),
    .m_reject_psn(m_reject_psn),
    .m_reject_valid(m_reject_valid),
    .m_reject_ready(m_reject_ready),
    .quiescent(guard_quiescent),
    .fault(guard_fault),
    .fault_code(guard_fault_code),
    .accepted_count(accepted_count),
    .rejected_count(rejected_count),
    .completed_count(completed_count),
    .tx_deferred_cycles(tx_deferred_cycles),
    .rx_integrity_good_count(rx_integrity_good_count),
    .rx_integrity_drop_count(rx_integrity_drop_count)
);

end else begin : legacy_hls
    assign s_local_owner_ready=0;
    assign s_local_sq_tready=0;
    assign s_local_rx_tready=0;
    assign m_local_tx_tdata=0;
    assign m_local_tx_tkeep=0;
    assign m_local_tx_tvalid=0;
    assign m_local_tx_tlast=0;
    assign m_local_ack_tdata=0;
    assign m_local_ack_tvalid=0;
    assign m_local_write_command=0;
    assign m_local_write_command_valid=0;
    assign m_local_write_tdata=0;
    assign m_local_write_tkeep=0;
    assign m_local_write_tvalid=0;
    assign m_local_write_tlast=0;
    assign m_local_read_command=0;
    assign m_local_read_command_valid=0;
    assign s_local_read_tready=0;
    assign s_local_retire_ready=0;
    assign local_hls_queue_guard=0;
    assign local_hls_active=0;
    assign shared_hls_fault=0;
    assign shared_hls_fault_code=0;
rocev2_protected_responder #(.EXTERNAL_ADMISSION_CONTROL(1),.LOCAL_WQE_ENABLE(LOCAL_WQE_ENABLE)) guard (
    .clk(clk),
    .rst(rst),
    .cfg_admission_pause(LOCAL_WQE_ENABLE ? shared_admission_pause :
        (cfg_admission_pause || !backend_page_ready || backend_fault)),
    .s_axis_rx_tdata(s_axis_rx_tdata),
    .s_axis_rx_tkeep(s_axis_rx_tkeep),
    .s_axis_rx_tvalid(s_axis_rx_tvalid),
    .s_axis_rx_tready(s_axis_rx_tready),
    .s_axis_rx_tlast(s_axis_rx_tlast),
    .s_axis_rx_tuser(s_axis_rx_tuser),
    .m_axis_tx_tdata(m_axis_tx_tdata),
    .m_axis_tx_tkeep(m_axis_tx_tkeep),
    .m_axis_tx_tvalid(m_axis_tx_tvalid),
    .m_axis_tx_tready(m_axis_tx_tready),
    .m_axis_tx_tlast(m_axis_tx_tlast),
    .cfg_qp_number(cfg_qp_number),
    .cfg_peer_qp_number(cfg_peer_qp_number),
    .cfg_qp_pd(cfg_qp_pd),
    .cfg_local_ip(cfg_local_ip),
    .cfg_peer_ip(cfg_peer_ip),
    .cfg_rx_psn(cfg_rx_psn),
    .cfg_tx_psn(cfg_tx_psn),
    .cfg_qp_valid(cfg_qp_valid && configuration_allowed),
    .cfg_qp_ready(guard_qp_ready),
    .qp_ready(qp_ready),
    .cfg_mr_command(cfg_mr_command),
    .cfg_mr_index(cfg_mr_index),
    .cfg_mr_pd(cfg_mr_pd),
    .cfg_mr_key(cfg_mr_key),
    .cfg_mr_virtual_address(cfg_mr_virtual_address),
    .cfg_mr_dma_address(64'd0),
    .cfg_mr_length(cfg_mr_length),
    .cfg_mr_access(cfg_mr_access),
    .cfg_mr_valid(cfg_mr_valid && configuration_allowed),
    .cfg_mr_ready(guard_mr_ready),
    .cfg_mr_response_error(cfg_mr_response_error),
    .cfg_mr_response_key(cfg_mr_response_key),
    .cfg_mr_response_valid(cfg_mr_response_valid),
    .cfg_mr_response_ready(cfg_mr_response_ready),
    .local_work_guard(effective_local_work_guard),
    .local_configuration_idle(guard_local_configuration_idle),
    .s_local_mr_request_pd(s_local_mr_request_pd),
    .s_local_mr_request_key(s_local_mr_request_key),
    .s_local_mr_request_address(s_local_mr_request_address),
    .s_local_mr_request_length(s_local_mr_request_length),
    .s_local_mr_request_operation(s_local_mr_request_operation),
    .s_local_mr_request_tag(s_local_mr_request_tag),
    .s_local_mr_request_valid(s_local_mr_request_valid),
    .s_local_mr_request_ready(s_local_mr_request_ready),
    .m_local_mr_response_tag(m_local_mr_response_tag),
    .m_local_mr_response_error(m_local_mr_response_error),
    .m_local_mr_response_offset(m_local_mr_response_offset),
    .m_local_mr_response_length(m_local_mr_response_length),
    .m_local_mr_response_valid(m_local_mr_response_valid),
    .m_local_mr_response_ready(m_local_mr_response_ready),
    .m_memory_command_write(m_memory_command_write),
    .m_memory_command_address(m_memory_command_address),
    .m_memory_command_length(m_memory_command_length),
    .m_memory_command_tag(m_memory_command_tag),
    .m_memory_command_key(m_memory_command_key),
    .m_memory_command_offset(m_memory_command_offset),
    .m_memory_command_valid(m_memory_command_valid),
    .m_memory_command_ready(m_memory_command_ready),
    .m_axis_memory_write_tdata(m_axis_memory_write_tdata),
    .m_axis_memory_write_tkeep(m_axis_memory_write_tkeep),
    .m_axis_memory_write_tvalid(m_axis_memory_write_tvalid),
    .m_axis_memory_write_tready(m_axis_memory_write_tready),
    .m_axis_memory_write_tlast(m_axis_memory_write_tlast),
    .s_axis_memory_read_tdata(s_axis_memory_read_tdata),
    .s_axis_memory_read_tkeep(s_axis_memory_read_tkeep),
    .s_axis_memory_read_tvalid(s_axis_memory_read_tvalid),
    .s_axis_memory_read_tready(s_axis_memory_read_tready),
    .s_axis_memory_read_tlast(s_axis_memory_read_tlast),
    .s_memory_status_tag(s_memory_status_tag),
    .s_memory_status_error(s_memory_status_error),
    .s_memory_status_valid(s_memory_status_valid),
    .s_memory_status_ready(s_memory_status_ready),
    .m_reject_error(m_reject_error),
    .m_reject_qpn(m_reject_qpn),
    .m_reject_psn(m_reject_psn),
    .m_reject_valid(m_reject_valid),
    .m_reject_ready(m_reject_ready),
    .quiescent(guard_quiescent),
    .fault(guard_fault),
    .fault_code(guard_fault_code),
    .accepted_count(accepted_count),
    .rejected_count(rejected_count),
    .completed_count(completed_count),
    .tx_deferred_cycles(tx_deferred_cycles),
    .rx_integrity_good_count(rx_integrity_good_count),
    .rx_integrity_drop_count(rx_integrity_drop_count)
);

end endgenerate
rocev2_paged_memory_backend #(.RAM_SIZE(RAM_SIZE),.RAM_ADDR_WIDTH(RAM_ADDR_WIDTH),
    .SEG_COUNT(SEG_COUNT),.SEG_DATA_WIDTH(SEG_DATA_WIDTH),.SEG_BE_WIDTH(SEG_BE_WIDTH),
    .SEG_ADDR_WIDTH(SEG_ADDR_WIDTH),.RAM_SEL_WIDTH(RAM_SEL_WIDTH),
    .DMA_LEN_WIDTH(DMA_LEN_WIDTH),.TAG_WIDTH(TAG_WIDTH)) memory (
    .clk(clk),
    .rst(rst),
    .enable(1'b1),
    .s_command_write(backend_command_write),
    .s_command_offset(backend_command_offset),
    .s_command_length(backend_command_length),
    .s_command_tag(backend_command_tag),
    .s_command_valid(backend_command_valid),
    .s_command_ready(backend_command_ready),
    .s_axis_write_tdata(backend_write_data),
    .s_axis_write_tkeep(backend_write_keep),
    .s_axis_write_tvalid(backend_write_valid),
    .s_axis_write_tready(backend_write_ready),
    .s_axis_write_tlast(backend_write_last),
    .m_axis_read_tdata(backend_read_data),
    .m_axis_read_tkeep(backend_read_keep),
    .m_axis_read_tvalid(backend_read_valid),
    .m_axis_read_tready(backend_read_ready),
    .m_axis_read_tlast(backend_read_last),
    .m_status_tag(backend_status_tag),
    .m_status_error(backend_status_error),
    .m_status_valid(backend_status_valid),
    .m_status_ready(backend_status_ready),
    .m_dma_read_address(m_dma_read_address),
    .m_dma_read_ram_sel(m_dma_read_ram_sel),
    .m_dma_read_ram_address(m_dma_read_ram_address),
    .m_dma_read_length(m_dma_read_length),
    .m_dma_read_tag(m_dma_read_tag),
    .m_dma_read_valid(m_dma_read_valid),
    .m_dma_read_ready(m_dma_read_ready),
    .s_dma_read_status_tag(s_dma_read_status_tag),
    .s_dma_read_status_error(s_dma_read_status_error),
    .s_dma_read_status_valid(s_dma_read_status_valid),
    .m_dma_write_address(m_dma_write_address),
    .m_dma_write_ram_sel(m_dma_write_ram_sel),
    .m_dma_write_ram_address(m_dma_write_ram_address),
    .m_dma_write_imm(m_dma_write_imm),
    .m_dma_write_imm_en(m_dma_write_imm_en),
    .m_dma_write_length(m_dma_write_length),
    .m_dma_write_tag(m_dma_write_tag),
    .m_dma_write_valid(m_dma_write_valid),
    .m_dma_write_ready(m_dma_write_ready),
    .s_dma_write_status_tag(s_dma_write_status_tag),
    .s_dma_write_status_error(s_dma_write_status_error),
    .s_dma_write_status_valid(s_dma_write_status_valid),
    .dma_ram_wr_cmd_sel(dma_ram_wr_cmd_sel),
    .dma_ram_wr_cmd_be(dma_ram_wr_cmd_be),
    .dma_ram_wr_cmd_addr(dma_ram_wr_cmd_addr),
    .dma_ram_wr_cmd_data(dma_ram_wr_cmd_data),
    .dma_ram_wr_cmd_valid(dma_ram_wr_cmd_valid),
    .dma_ram_wr_cmd_ready(dma_ram_wr_cmd_ready),
    .dma_ram_wr_done(dma_ram_wr_done),
    .dma_ram_rd_cmd_sel(dma_ram_rd_cmd_sel),
    .dma_ram_rd_cmd_addr(dma_ram_rd_cmd_addr),
    .dma_ram_rd_cmd_valid(dma_ram_rd_cmd_valid),
    .dma_ram_rd_cmd_ready(dma_ram_rd_cmd_ready),
    .dma_ram_rd_resp_data(dma_ram_rd_resp_data),
    .dma_ram_rd_resp_valid(dma_ram_rd_resp_valid),
    .dma_ram_rd_resp_ready(dma_ram_rd_resp_ready),
    .idle(backend_idle),
    .dma_drained(backend_drained),
    .fault(backend_fault),
    .fault_code(backend_fault_code),
    .command_count(dma_command_count),
    .fence_count(dma_fence_count),
    .completion_count(dma_completion_count),
    .s_command_key(backend_command_key),
    .cfg_quiescent(guard_quiescent && !guard_fault),
    .cfg_command(cfg_page_command),
    .cfg_slot(cfg_page_slot),
    .cfg_key(cfg_page_key),
    .cfg_length(cfg_page_length),
    .cfg_first_offset(cfg_page_first_offset),
    .cfg_page_index(cfg_page_page_index),
    .cfg_dma_page(cfg_page_dma_page),
    .cfg_valid(cfg_page_valid && cfg_admission_pause && guard_mr_ready && !cfg_mr_valid && !cfg_qp_valid && !fault),
    .cfg_ready(backend_page_ready),
    .cfg_response_error(cfg_page_response_error),
    .cfg_response_key(cfg_page_response_key),
    .cfg_response_valid(cfg_page_response_valid),
    .cfg_response_ready(cfg_page_response_ready)
);
endmodule
`resetall

