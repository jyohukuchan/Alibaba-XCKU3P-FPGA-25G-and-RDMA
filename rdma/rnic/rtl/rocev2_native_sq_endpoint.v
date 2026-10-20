// SPDX-License-Identifier: BSD-2-Clause-Views
// Copyright (c) 2026 jyohukuchan
// Actual native protected payload + actual coherent SQ fetch share ONE app DMA
// port/router. SQ results feed the SAME existing MR namespace, not copied RAM.
// SQC1 is decoded at0x402000, control-only: no local payload executor/CQ/verbs
// or actual mqnic board-parent selection is implied. Work outputs are leases,
// NOT WR completion. All external work/wire/CQ guards MUST be real owners.
// Reset is not cancellation/unpin; real parent drain/closed work/fresh epochs
// are required outside this module. Original native/rollback sources stay separate.
`resetall
`timescale 1ns/1ps
`default_nettype none
module rocev2_native_sq_endpoint #(
    parameter TX_TAG_WIDTH=16,
    parameter TS_WIDTH=96,
    parameter RX_USER_WIDTH=97,
    parameter RAM_SIZE=8192,
    parameter RAM_ADDR_WIDTH=15,
    parameter SEG_COUNT=2,
    parameter SEG_DATA_WIDTH=256,
    parameter SEG_BE_WIDTH=SEG_DATA_WIDTH/8,
    parameter SEG_ADDR_WIDTH=RAM_ADDR_WIDTH-$clog2(SEG_COUNT*SEG_BE_WIDTH),
    parameter RAM_SEL_WIDTH=1,
    parameter DMA_LEN_WIDTH=16,
    parameter DMA_TAG_WIDTH=16,
    parameter MAX_QPS=8,
    parameter LOCAL_MEMORY_ENABLE=0,
    parameter HLS_SQ_ENABLE=0,
    // Select ONE shared responder core for remote requests and native SQ work.
    parameter EXTERNAL_REPLAY_ENABLE=0,
    parameter QP_TX_ENABLE=0,
    parameter RECV_ENABLE=0,
    parameter RNR_ENABLE=0,
    parameter RECV_RETIRE_ENABLE=0,
    parameter RECV_CQ_ENABLE=0,
    parameter REQUEST_CQ_ENABLE=0,
    parameter DUPLEX_ENABLE=0,
    parameter SEPARATE_RQ_ENABLE=0,
    parameter RECV_CANCEL_ENABLE=0,
    parameter SEND_ENABLE=0,
    parameter SHARED_HLS_ENABLE=0,
    parameter CQ_MMIO_ENABLE=0,
    parameter RETRY_MMIO_ENABLE=0
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
    output wire [587:0] m_recv_post_context,
    output wire m_recv_post_valid,
    input wire m_recv_post_ready,
    input wire [7:0] recv_queue_guard,
    output wire m_recv_cancel_block,output wire m_recv_cancel_valid,
    output wire [23:0] m_recv_cancel_qpn,output wire [15:0] m_recv_cancel_pd,
    output wire [63:0] m_recv_cancel_epoch,input wire s_recv_cancel_ready,
    output wire [11:0] m_axil_cq_awaddr,
    output wire [2:0] m_axil_cq_awprot,
    output wire m_axil_cq_awvalid,
    input wire m_axil_cq_awready,
    output wire [31:0] m_axil_cq_wdata,
    output wire [3:0] m_axil_cq_wstrb,
    output wire m_axil_cq_wvalid,
    input wire m_axil_cq_wready,
    input wire [1:0] m_axil_cq_bresp,
    input wire m_axil_cq_bvalid,
    output wire m_axil_cq_bready,
    output wire [11:0] m_axil_cq_araddr,
    output wire [2:0] m_axil_cq_arprot,
    output wire m_axil_cq_arvalid,
    input wire m_axil_cq_arready,
    input wire [31:0] m_axil_cq_rdata,
    input wire [1:0] m_axil_cq_rresp,
    input wire m_axil_cq_rvalid,
    output wire m_axil_cq_rready,
    output wire [11:0] m_axil_retry_awaddr,
    output wire [2:0] m_axil_retry_awprot,
    output wire m_axil_retry_awvalid,
    input wire m_axil_retry_awready,
    output wire [31:0] m_axil_retry_wdata,
    output wire [3:0] m_axil_retry_wstrb,
    output wire m_axil_retry_wvalid,
    input wire m_axil_retry_wready,
    input wire [1:0] m_axil_retry_bresp,
    input wire m_axil_retry_bvalid,
    output wire m_axil_retry_bready,
    output wire [11:0] m_axil_retry_araddr,
    output wire [2:0] m_axil_retry_arprot,
    output wire m_axil_retry_arvalid,
    input wire m_axil_retry_arready,
    input wire [31:0] m_axil_retry_rdata,
    input wire [1:0] m_axil_retry_rresp,
    input wire m_axil_retry_rvalid,
    output wire m_axil_retry_rready,
    input wire [23:0] owner_query_qpn,
    input wire [15:0] owner_query_opcode,
    output wire [63:0] owner_query_cookie,
    output wire [63:0] owner_query_epoch,
    output wire [15:0] owner_query_pd,
    output wire owner_query_valid,
    input wire [23:0] retry_query_qpn,
    output wire [63:0] retry_query_cookie,
    output wire [63:0] retry_query_epoch,
    output wire [15:0] retry_query_pd,
    output wire retry_query_valid,
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
    input wire [127:0] s_axis_host_tx_tdata,
    input wire [15:0] s_axis_host_tx_tkeep,
    input wire s_axis_host_tx_tvalid,
    output wire s_axis_host_tx_tready,
    input wire s_axis_host_tx_tlast,
    input wire [TX_TAG_WIDTH:0] s_axis_host_tx_tuser,
    output wire [127:0] m_axis_mac_tx_tdata,
    output wire [15:0] m_axis_mac_tx_tkeep,
    output wire m_axis_mac_tx_tvalid,
    input wire m_axis_mac_tx_tready,
    output wire m_axis_mac_tx_tlast,
    output wire [TX_TAG_WIDTH:0] m_axis_mac_tx_tuser,
    input wire [TX_TAG_WIDTH-1:0] s_axis_mac_cpl_tag,
    input wire [TS_WIDTH-1:0] s_axis_mac_cpl_ts,
    input wire s_axis_mac_cpl_valid,
    output wire s_axis_mac_cpl_ready,
    output wire [TX_TAG_WIDTH-1:0] m_axis_host_cpl_tag,
    output wire [TS_WIDTH-1:0] m_axis_host_cpl_ts,
    output wire m_axis_host_cpl_valid,
    input wire m_axis_host_cpl_ready,
    input wire [127:0] s_axis_mac_rx_tdata,
    input wire [15:0] s_axis_mac_rx_tkeep,
    input wire s_axis_mac_rx_tvalid,
    output wire s_axis_mac_rx_tready,
    input wire s_axis_mac_rx_tlast,
    input wire [RX_USER_WIDTH-1:0] s_axis_mac_rx_tuser,
    output wire [127:0] m_axis_host_rx_tdata,
    output wire [15:0] m_axis_host_rx_tkeep,
    output wire m_axis_host_rx_tvalid,
    input wire m_axis_host_rx_tready,
    output wire m_axis_host_rx_tlast,
    output wire [RX_USER_WIDTH-1:0] m_axis_host_rx_tuser,
    output wire qp_ready,
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
    output wire [DMA_TAG_WIDTH-1:0] m_dma_read_tag,
    output wire m_dma_read_valid,
    input wire m_dma_read_ready,
    input wire [DMA_TAG_WIDTH-1:0] s_dma_read_status_tag,
    input wire [3:0] s_dma_read_status_error,
    input wire s_dma_read_status_valid,
    output wire [63:0] m_dma_write_address,
    output wire [RAM_SEL_WIDTH-1:0] m_dma_write_ram_sel,
    output wire [RAM_ADDR_WIDTH-1:0] m_dma_write_ram_address,
    output wire [31:0] m_dma_write_imm,
    output wire m_dma_write_imm_en,
    output wire [DMA_LEN_WIDTH-1:0] m_dma_write_length,
    output wire [DMA_TAG_WIDTH-1:0] m_dma_write_tag,
    output wire m_dma_write_valid,
    input wire m_dma_write_ready,
    input wire [DMA_TAG_WIDTH-1:0] s_dma_write_status_tag,
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
    output wire memory_drained,
    output wire physical_memory_drained,
    output wire [31:0] dma_command_count,
    output wire [31:0] dma_fence_count,
    output wire [31:0] dma_completion_count,
    input wire parent_dma_drained,
    output wire admission_paused,
    output wire control_busy,
    output wire control_fatal,
    output wire control_mmio_error,
    output wire epoch_ready,
    output wire qp_configured,
    output wire run_requested,
    output wire [7:0] building,
    output wire [7:0] active,
    output wire [7:0] tainted,
    output wire config_safe,
    output wire response_tx_quiescent,
    output wire [31:0] request_frame_count,
    output wire [31:0] host_route_count,
    output wire [31:0] request_drop_count,
    output wire [31:0] request_overflow_count,
    output wire [31:0] request_stale_count,
    output wire [15:0] response_pending_frames,
    input wire [23:0] s_axil_awaddr,
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
    input wire [23:0] s_axil_araddr,
    input wire [2:0] s_axil_arprot,
    input wire s_axil_arvalid,
    output wire s_axil_arready,
    output wire [31:0] s_axil_rdata,
    output wire [1:0] s_axil_rresp,
    output wire s_axil_rvalid,
    input wire s_axil_rready,
    output wire ethernet_config_error,
    output wire ethernet_committed,
    output wire ethernet_enabled,
    output wire [31:0] ethernet_epoch,
    output wire [47:0] active_local_mac,
    output wire [47:0] active_peer_mac,
    output wire [31:0] active_local_ip,
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
    input wire enable,
    input wire parent_fault,
    output wire dma_drained,
    input wire [MAX_QPS-1:0] executor_queue_guard,
    // Separate local sender exclusion from the complete management lifetime
    // guard: an idle posted receive must not prevent a new local send.
    input wire [MAX_QPS-1:0] send_execution_queue_guard,
    input wire [MAX_QPS-1:0] wire_queue_guard,
    input wire [MAX_QPS-1:0] completion_queue_guard,
    output wire [MAX_QPS-1:0] admission_queue_guard,
    output wire [63:0] m_work_wr_id,
    output wire [63:0] m_work_sequence,
    output wire [63:0] m_work_epoch,
    output wire [23:0] m_work_qpn,
    output wire [15:0] m_work_pd,
    output wire [15:0] m_work_tag,
    output wire [15:0] m_work_opcode,
    output wire [15:0] m_work_flags,
    output wire [31:0] m_work_length,
    output wire [31:0] m_work_local_key,
    output wire [63:0] m_work_local_address,
    output wire [63:0] m_work_local_offset,
    output wire [63:0] m_work_remote_address,
    output wire [31:0] m_work_remote_key,
    output wire [7:0] m_work_error,
    output wire [1:0] m_work_error_source,
    output wire [7:0] m_work_fetch_error,
    output wire m_work_descriptor_available,
    output wire m_work_authorized,
    output wire m_work_valid,
    // External work ready is used ONLY when HLS_SQ_ENABLE=0. In enabled
    // mode these fields are diagnostics; m_work_handoff is the real capture.
    input wire m_work_ready,
    output wire m_work_handoff,
    // Optional actual per-WR HLS SQ + complete trusted executor context.
    // The receiver MUST hold executor_queue_guard before context ready.
    // This does not provide memory/ACK/READ-response/wire/CQ execution itself.
    output wire [247:0] m_hls_sq_tdata,
    output wire m_hls_sq_tvalid,
    input wire m_hls_sq_tready,
    output wire [587:0] m_executor_context,
    output wire m_executor_context_valid,
    input wire m_executor_context_ready,
    output wire [MAX_QPS-1:0] sq_submission_guard,
    output wire sq_submission_busy,
    output wire sq_submission_fault,
    output wire [7:0] sq_submission_fault_code,
    output wire [31:0] sq_submission_owner_count,
    output wire [31:0] sq_submission_hls_count,
    output wire [MAX_QPS-1:0] sq_queue_guard,
    output wire [MAX_QPS-1:0] sq_queue_active,
    output wire [MAX_QPS-1:0] sq_queue_halted,
    output wire sq_busy,
    output wire sq_tag_exhausted,
    output wire sq_fault,
    output wire [7:0] sq_fault_code,
    output wire [31:0] sq_fetch_count,
    output wire [31:0] sq_result_count,
    output wire sq_dma_drained,
    output wire [31:0] sq_backend_command_count,
    output wire [31:0] sq_backend_fence_count,
    output wire [31:0] sq_backend_completion_count,
    output wire [1:0] router_client_busy,
    output wire router_fault,
    output wire [7:0] router_fault_code,
    output wire router_tag_exhausted,
    output wire [31:0] router_descriptor_count,
    output wire [31:0] router_completion_count,
    output wire [MAX_QPS-1:0] sq_queue_pending,
    output wire sq_control_busy,
    output wire sq_control_response_valid,
    output wire sq_control_fatal,
    output wire sq_control_mmio_error,
    output wire [MAX_QPS-1:0] sq_control_owner_active,
    output wire [MAX_QPS-1:0] sq_control_owner_tainted,
    output wire [31:0] sq_control_last_sequence
);
localparam TAG_WIDTH=DMA_TAG_WIDTH;
initial begin
 if(RAM_SEL_WIDTH!=1 || DMA_TAG_WIDTH!=16 || MAX_QPS<1 || MAX_QPS>8)$fatal(1,"unreviewed native SQ geometry");
 if(CQ_MMIO_ENABLE!=0 && CQ_MMIO_ENABLE!=1)$fatal(1,"CQ window mode must be static");
 if(RETRY_MMIO_ENABLE && !CQ_MMIO_ENABLE)$fatal(1,"replay window requires the complete native CQ parent");
end
wire router_drained;
wire [63:0] net_m_dma_read_address;
wire [RAM_SEL_WIDTH-1:0] net_m_dma_read_ram_sel;
wire [RAM_ADDR_WIDTH-1:0] net_m_dma_read_ram_address;
wire [DMA_LEN_WIDTH-1:0] net_m_dma_read_length;
wire [TAG_WIDTH-1:0] net_m_dma_read_tag;
wire net_m_dma_read_valid;
wire net_m_dma_read_ready;
wire [TAG_WIDTH-1:0] net_s_dma_read_status_tag;
wire [3:0] net_s_dma_read_status_error;
wire net_s_dma_read_status_valid;
wire [63:0] net_m_dma_write_address;
wire [RAM_SEL_WIDTH-1:0] net_m_dma_write_ram_sel;
wire [RAM_ADDR_WIDTH-1:0] net_m_dma_write_ram_address;
wire [31:0] net_m_dma_write_imm;
wire net_m_dma_write_imm_en;
wire [DMA_LEN_WIDTH-1:0] net_m_dma_write_length;
wire [TAG_WIDTH-1:0] net_m_dma_write_tag;
wire net_m_dma_write_valid;
wire net_m_dma_write_ready;
wire [TAG_WIDTH-1:0] net_s_dma_write_status_tag;
wire [3:0] net_s_dma_write_status_error;
wire net_s_dma_write_status_valid;
wire [SEG_COUNT*RAM_SEL_WIDTH-1:0] net_dma_ram_wr_cmd_sel;
wire [SEG_COUNT*SEG_BE_WIDTH-1:0] net_dma_ram_wr_cmd_be;
wire [SEG_COUNT*SEG_ADDR_WIDTH-1:0] net_dma_ram_wr_cmd_addr;
wire [SEG_COUNT*SEG_DATA_WIDTH-1:0] net_dma_ram_wr_cmd_data;
wire [SEG_COUNT-1:0] net_dma_ram_wr_cmd_valid;
wire [SEG_COUNT-1:0] net_dma_ram_wr_cmd_ready;
wire [SEG_COUNT-1:0] net_dma_ram_wr_done;
wire [SEG_COUNT*RAM_SEL_WIDTH-1:0] net_dma_ram_rd_cmd_sel;
wire [SEG_COUNT*SEG_ADDR_WIDTH-1:0] net_dma_ram_rd_cmd_addr;
wire [SEG_COUNT-1:0] net_dma_ram_rd_cmd_valid;
wire [SEG_COUNT-1:0] net_dma_ram_rd_cmd_ready;
wire [SEG_COUNT*SEG_DATA_WIDTH-1:0] net_dma_ram_rd_resp_data;
wire [SEG_COUNT-1:0] net_dma_ram_rd_resp_valid;
wire [SEG_COUNT-1:0] net_dma_ram_rd_resp_ready;
wire [63:0] sq_m_dma_read_address;
wire [RAM_SEL_WIDTH-1:0] sq_m_dma_read_ram_sel;
wire [RAM_ADDR_WIDTH-1:0] sq_m_dma_read_ram_address;
wire [DMA_LEN_WIDTH-1:0] sq_m_dma_read_length;
wire [TAG_WIDTH-1:0] sq_m_dma_read_tag;
wire sq_m_dma_read_valid;
wire sq_m_dma_read_ready;
wire [TAG_WIDTH-1:0] sq_s_dma_read_status_tag;
wire [3:0] sq_s_dma_read_status_error;
wire sq_s_dma_read_status_valid;
wire [63:0] sq_m_dma_write_address;
wire [RAM_SEL_WIDTH-1:0] sq_m_dma_write_ram_sel;
wire [RAM_ADDR_WIDTH-1:0] sq_m_dma_write_ram_address;
wire [31:0] sq_m_dma_write_imm;
wire sq_m_dma_write_imm_en;
wire [DMA_LEN_WIDTH-1:0] sq_m_dma_write_length;
wire [TAG_WIDTH-1:0] sq_m_dma_write_tag;
wire sq_m_dma_write_valid;
wire sq_m_dma_write_ready;
wire [TAG_WIDTH-1:0] sq_s_dma_write_status_tag;
wire [3:0] sq_s_dma_write_status_error;
wire sq_s_dma_write_status_valid;
wire [SEG_COUNT*RAM_SEL_WIDTH-1:0] sq_dma_ram_wr_cmd_sel;
wire [SEG_COUNT*SEG_BE_WIDTH-1:0] sq_dma_ram_wr_cmd_be;
wire [SEG_COUNT*SEG_ADDR_WIDTH-1:0] sq_dma_ram_wr_cmd_addr;
wire [SEG_COUNT*SEG_DATA_WIDTH-1:0] sq_dma_ram_wr_cmd_data;
wire [SEG_COUNT-1:0] sq_dma_ram_wr_cmd_valid;
wire [SEG_COUNT-1:0] sq_dma_ram_wr_cmd_ready;
wire [SEG_COUNT-1:0] sq_dma_ram_wr_done;
wire [SEG_COUNT*RAM_SEL_WIDTH-1:0] sq_dma_ram_rd_cmd_sel;
wire [SEG_COUNT*SEG_ADDR_WIDTH-1:0] sq_dma_ram_rd_cmd_addr;
wire [SEG_COUNT-1:0] sq_dma_ram_rd_cmd_valid;
wire [SEG_COUNT-1:0] sq_dma_ram_rd_cmd_ready;
wire [SEG_COUNT*SEG_DATA_WIDTH-1:0] sq_dma_ram_rd_resp_data;
wire [SEG_COUNT-1:0] sq_dma_ram_rd_resp_valid;
wire [SEG_COUNT-1:0] sq_dma_ram_rd_resp_ready;


wire [63:0] rq_work_wr_id;
wire [63:0] rq_work_sequence;
wire [63:0] rq_work_epoch;
wire [23:0] rq_work_qpn;
wire [15:0] rq_work_pd;
wire [15:0] rq_work_tag;
wire [15:0] rq_work_opcode;
wire [15:0] rq_work_flags;
wire [31:0] rq_work_length;
wire [31:0] rq_work_local_key;
wire [63:0] rq_work_local_address;
wire [63:0] rq_work_local_offset;
wire [63:0] rq_work_remote_address;
wire [31:0] rq_work_remote_key;
wire [7:0] rq_work_error;
wire [1:0] rq_work_error_source;
wire [7:0] rq_work_fetch_error;
wire rq_work_descriptor_available;
wire rq_work_authorized;
wire rq_work_valid;
wire rq_work_ready;
wire [587:0] rq_work_context={rq_work_wr_id,rq_work_sequence,rq_work_epoch,rq_work_qpn,rq_work_pd,rq_work_tag,rq_work_opcode,rq_work_flags,rq_work_length,rq_work_local_key,rq_work_local_address,rq_work_local_offset,rq_work_remote_address,rq_work_remote_key,rq_work_error,rq_work_error_source,rq_work_fetch_error,rq_work_descriptor_available,rq_work_authorized};
wire fetch_result_receive,send_result_ready,receive_result_ready,fetch_cfg_receive;
wire [MAX_QPS-1:0] receive_fetch_guard,receive_queue_active,receive_queue_pending,receive_queue_halted;
wire [MAX_QPS-1:0] rq_admission_guard;
wire rq_admission_busy,rq_admission_fault,rq_admission_configuration_guard;
wire [7:0] rq_admission_fault_code;
wire rq_control_busy,rq_control_response_valid,rq_control_fatal,rq_control_mmio_error;
wire [MAX_QPS-1:0] rq_control_owner_active,rq_control_owner_tainted;
wire [31:0] rq_control_last_sequence;
wire rq_cancel_valid;
assign m_recv_cancel_valid=rq_cancel_valid &&
    receive_fetch_guard[m_recv_cancel_qpn[2:0]]===1'b0 &&
    rq_admission_guard[m_recv_cancel_qpn[2:0]]===1'b0;
initial if(RECV_CANCEL_ENABLE && !SEPARATE_RQ_ENABLE)$fatal(1,"receive cancellation needs separate native RQ");
wire [63:0] sq_owner_query_cookie,sq_owner_query_epoch,rq_owner_query_cookie,rq_owner_query_epoch;
wire [15:0] sq_owner_query_pd,rq_owner_query_pd;
wire sq_owner_query_valid,rq_owner_query_valid;
wire cfg_mux_busy,cfg_mux_fault,mr_mux_busy,mr_mux_fault;
wire [7:0] mr_mux_fault_code;
wire [MAX_QPS-1:0] rq_downstream_queue_guard=rq_admission_guard | recv_queue_guard |
 executor_queue_guard | wire_queue_guard | completion_queue_guard;
wire rq_owner_selected=SEPARATE_RQ_ENABLE && owner_query_opcode==16'd4;
assign owner_query_cookie=rq_owner_selected ? rq_owner_query_cookie : sq_owner_query_cookie;
assign owner_query_epoch=rq_owner_selected ? rq_owner_query_epoch : sq_owner_query_epoch;
assign owner_query_pd=rq_owner_selected ? rq_owner_query_pd : sq_owner_query_pd;
assign owner_query_valid=rq_owner_selected ? rq_owner_query_valid : sq_owner_query_valid;
assign sq_m_result_ready=fetch_result_receive ? receive_result_ready : send_result_ready;
assign rq_work_ready=m_recv_post_ready && recv_post_guard && !fault;

wire local_work_guard;
wire local_configuration_idle;
wire [15:0] s_local_mr_request_pd;
wire [31:0] s_local_mr_request_key;
wire [63:0] s_local_mr_request_address;
wire [31:0] s_local_mr_request_length;
wire [2:0] s_local_mr_request_operation;
wire [15:0] s_local_mr_request_tag;
wire s_local_mr_request_valid;
wire s_local_mr_request_ready;
wire [15:0] m_local_mr_response_tag;
wire [7:0] m_local_mr_response_error;
wire [63:0] m_local_mr_response_offset;
wire [31:0] m_local_mr_response_length;
wire m_local_mr_response_valid;
wire m_local_mr_response_ready;
wire [15:0] sq_mr_request_pd;
wire [31:0] sq_mr_request_key;
wire [63:0] sq_mr_request_address;
wire [31:0] sq_mr_request_length;
wire [2:0] sq_mr_request_operation;
wire [15:0] sq_mr_request_tag;
wire sq_mr_request_valid;
wire sq_mr_request_ready;
wire [15:0] sq_mr_response_tag;
wire [7:0] sq_mr_response_error;
wire [63:0] sq_mr_response_offset;
wire [31:0] sq_mr_response_length;
wire sq_mr_response_valid;
wire sq_mr_response_ready;
wire [15:0] rq_mr_request_pd;
wire [31:0] rq_mr_request_key;
wire [63:0] rq_mr_request_address;
wire [31:0] rq_mr_request_length;
wire [2:0] rq_mr_request_operation;
wire [15:0] rq_mr_request_tag;
wire rq_mr_request_valid;
wire rq_mr_request_ready;
wire [15:0] rq_mr_response_tag;
wire [7:0] rq_mr_response_error;
wire [63:0] rq_mr_response_offset;
wire [31:0] rq_mr_response_length;
wire rq_mr_response_valid;
wire rq_mr_response_ready;
wire net_fault,net_quiescent,net_memory_drained;
wire [7:0] net_fault_code;
wire admission_busy,admission_fault;wire [7:0] admission_fault_code;
wire admission_configuration_guard;
wire [MAX_QPS-1:0] sq_downstream_queue_guard=admission_queue_guard | sq_submission_guard | executor_queue_guard | wire_queue_guard | completion_queue_guard;
assign local_work_guard=rq_admission_configuration_guard || mr_mux_busy || admission_configuration_guard || (|sq_submission_guard) || (|executor_queue_guard) || (|wire_queue_guard) || (|completion_queue_guard);
// Unfetched/raw SQ ownership blocks route COMMIT, NOT pre-authorization MR
// management. Otherwise management pause and an unadmitted result deadlock.
wire route_guard=(|sq_queue_pending) || (|sq_queue_guard) || (|sq_downstream_queue_guard) ||
 admission_configuration_guard || rq_admission_configuration_guard || (|receive_queue_pending) || (|receive_fetch_guard) ||
 rq_control_busy || cfg_mux_busy || sq_control_busy || sq_control_fatal || sq_control_mmio_error || fault;
reg recv_dispatch_fault=0;
assign fault=parent_fault || router_fault || net_fault || sq_fault || sq_control_fatal || admission_fault || sq_submission_fault || recv_dispatch_fault || rq_control_fatal || rq_admission_fault || cfg_mux_fault || mr_mux_fault;
assign fault_code=parent_fault ? 8'hf0 : router_fault ? (router_fault_code|8'hc0) :
 net_fault ? net_fault_code : sq_fault ? (sq_fault_code|8'h80) : sq_control_fatal ? 8'hf1 :
 admission_fault ? admission_fault_code : rq_admission_fault ? rq_admission_fault_code :
 cfg_mux_fault ? 8'hea : mr_mux_fault ? mr_mux_fault_code : rq_control_fatal ? 8'heb :
 recv_dispatch_fault ? 8'he9 : sq_submission_fault_code;
wire native_parent_safe=parent_dma_drained && router_drained && sq_dma_drained && !fault && !rst;
assign dma_drained=native_parent_safe && net_memory_drained;
assign memory_drained=dma_drained;
wire net_physical_memory_drained;
assign physical_memory_drained=native_parent_safe && net_physical_memory_drained;
assign quiescent=net_quiescent && !sq_busy && !admission_busy && !sq_control_busy && !sq_submission_busy &&
 !(|sq_queue_pending) && !(|sq_queue_guard) && !(|sq_downstream_queue_guard) &&
 !(|receive_queue_pending) && !(|receive_fetch_guard) && !rq_admission_busy && !rq_control_busy &&
 !cfg_mux_busy && !mr_mux_busy && !fault && !rst;
wire bridge_work_ready;
wire [587:0] bridge_work_context={m_work_wr_id,m_work_sequence,m_work_epoch,m_work_qpn,m_work_pd,m_work_tag,
 m_work_opcode,m_work_flags,m_work_length,m_work_local_key,m_work_local_address,m_work_local_offset,
 m_work_remote_address,m_work_remote_key,m_work_error,m_work_error_source,m_work_fetch_error,
 m_work_descriptor_available,m_work_authorized};
wire recv_post_selected=RECV_ENABLE && !SEPARATE_RQ_ENABLE && HLS_SQ_ENABLE && m_work_opcode==4;
wire recv_post_guard=(^recv_queue_guard)!==1'bx && m_recv_post_context[395:372]<8 && recv_queue_guard[m_recv_post_context[374:372]];
assign m_recv_post_context=SEPARATE_RQ_ENABLE ? rq_work_context : bridge_work_context;
assign m_recv_post_valid=SEPARATE_RQ_ENABLE ? rq_work_valid : m_work_valid && recv_post_selected;
always @(posedge clk)begin
    if(rst)recv_dispatch_fault<=0;
    else if((m_recv_post_valid && m_recv_post_ready && !recv_post_guard) ||
       (SEPARATE_RQ_ENABLE && rq_work_valid && (!rq_work_authorized || rq_work_opcode!=4 || rq_work_error)))recv_dispatch_fault<=1;
end
assign m_work_handoff=m_work_valid && bridge_work_ready;
initial begin
    if(SEPARATE_RQ_ENABLE && (!REQUEST_CQ_ENABLE || !RETRY_MMIO_ENABLE || !CQ_MMIO_ENABLE))
        $fatal(1,"independent queues need complete requester/receive CQ profile");
    if(HLS_SQ_ENABLE!=0 && HLS_SQ_ENABLE!=1)$fatal(1,"HLS SQ mode must be static0or1");
    if(HLS_SQ_ENABLE && !LOCAL_MEMORY_ENABLE)$fatal(1,"native HLS SQ requires shared payload memory path");
    if(SHARED_HLS_ENABLE && (!HLS_SQ_ENABLE || MAX_QPS!=8))
        $fatal(1,"shared native transport requires enabled SQ and complete eight-QP guards");
end
generate if(HLS_SQ_ENABLE)begin : work_to_hls
    wire send_bridge_ready;
    assign bridge_work_ready=recv_post_selected ? m_recv_post_ready && recv_post_guard : send_bridge_ready;
    // Work was already admitted/authorized upstream. Native MR management
    // pause MUST NOT deadlock that accepted handoff. halt only prevents NEW
    // SQ offers; it never retracts already-visible context or metadata.
    rocev2_wqe_hls_sq #(.MAX_QPS(MAX_QPS)) submission(
        .clk(clk),.rst(rst),.enable(1'b1),.halt(fault),
        .s_work_context(bridge_work_context),.s_work_valid(m_work_valid && !recv_post_selected),.s_work_ready(send_bridge_ready),
        .m_owner_context(m_executor_context),.m_owner_valid(m_executor_context_valid),
        .m_owner_ready(m_executor_context_ready),
        .downstream_queue_guard(SEPARATE_RQ_ENABLE ? send_execution_queue_guard : executor_queue_guard),
        .m_axis_sq_tdata(m_hls_sq_tdata),.m_axis_sq_tvalid(m_hls_sq_tvalid),.m_axis_sq_tready(m_hls_sq_tready),
        .queue_guard(sq_submission_guard),.configuration_guard(),.busy(sq_submission_busy),
        .fault(sq_submission_fault),.fault_code(sq_submission_fault_code),
        .owner_handoff_count(sq_submission_owner_count),.HLS_SQ_handoff_count(sq_submission_hls_count));
end else begin : external_work_owner
    assign bridge_work_ready=m_work_ready;
    assign m_hls_sq_tdata=0;assign m_hls_sq_tvalid=0;
    assign m_executor_context=0;assign m_executor_context_valid=0;
    assign sq_submission_guard=0;assign sq_submission_busy=0;
    assign sq_submission_fault=0;assign sq_submission_fault_code=0;
    assign sq_submission_owner_count=0;assign sq_submission_hls_count=0;
end endgenerate
wire [511:0] sq_m_result_data;
wire [7:0] sq_m_result_error;
wire [23:0] sq_m_result_qpn;
wire [15:0] sq_m_result_pd;
wire [63:0] sq_m_result_epoch;
wire [63:0] sq_m_result_sequence;
wire [15:0] sq_m_result_tag;
wire sq_m_result_valid;
wire sq_m_result_ready;
wire [1:0] sq_cfg_command;
wire [23:0] sq_cfg_qpn;
wire [15:0] sq_cfg_pd;
wire [63:0] sq_cfg_epoch;
wire [63:0] sq_cfg_dma_base;
wire [3:0] sq_cfg_log_depth;
wire [63:0] sq_cfg_producer;
wire sq_cfg_valid;
wire sq_cfg_ready;
wire [7:0] sq_cfg_response_error;
wire [23:0] sq_cfg_response_qpn;
wire [63:0] sq_cfg_response_epoch;
wire [63:0] sq_cfg_response_consumer;
wire sq_cfg_response_valid;
wire sq_cfg_response_ready;

wire [1:0] rq_cfg_command;
wire [23:0] rq_cfg_qpn;
wire [15:0] rq_cfg_pd;
wire [63:0] rq_cfg_epoch;
wire [63:0] rq_cfg_dma_base;
wire [3:0] rq_cfg_log_depth;
wire [63:0] rq_cfg_producer;
wire rq_cfg_valid;
wire rq_cfg_ready;
wire [7:0] rq_cfg_response_error;
wire [23:0] rq_cfg_response_qpn;
wire [63:0] rq_cfg_response_epoch;
wire [63:0] rq_cfg_response_consumer;
wire rq_cfg_response_valid;
wire rq_cfg_response_ready;

wire [1:0] fetch_cfg_command;
wire [23:0] fetch_cfg_qpn;
wire [15:0] fetch_cfg_pd;
wire [63:0] fetch_cfg_epoch;
wire [63:0] fetch_cfg_dma_base;
wire [3:0] fetch_cfg_log_depth;
wire [63:0] fetch_cfg_producer;
wire fetch_cfg_valid;
wire fetch_cfg_ready;
wire [7:0] fetch_cfg_response_error;
wire [23:0] fetch_cfg_response_qpn;
wire [63:0] fetch_cfg_response_epoch;
wire [63:0] fetch_cfg_response_consumer;
wire fetch_cfg_response_valid;
wire fetch_cfg_response_ready;

wire [12-1:0] sq_s_axil_awaddr;
wire [2:0] sq_s_axil_awprot;
wire sq_s_axil_awvalid;
wire sq_s_axil_awready;
wire [31:0] sq_s_axil_wdata;
wire [3:0] sq_s_axil_wstrb;
wire sq_s_axil_wvalid;
wire sq_s_axil_wready;
wire [1:0] sq_s_axil_bresp;
wire sq_s_axil_bvalid;
wire sq_s_axil_bready;
wire [12-1:0] sq_s_axil_araddr;
wire [2:0] sq_s_axil_arprot;
wire sq_s_axil_arvalid;
wire sq_s_axil_arready;
wire [31:0] sq_s_axil_rdata;
wire [1:0] sq_s_axil_rresp;
wire sq_s_axil_rvalid;
wire sq_s_axil_rready;
wire [12-1:0] rq_s_axil_awaddr;
wire [2:0] rq_s_axil_awprot;
wire rq_s_axil_awvalid;
wire rq_s_axil_awready;
wire [31:0] rq_s_axil_wdata;
wire [3:0] rq_s_axil_wstrb;
wire rq_s_axil_wvalid;
wire rq_s_axil_wready;
wire [1:0] rq_s_axil_bresp;
wire rq_s_axil_bvalid;
wire rq_s_axil_bready;
wire [12-1:0] rq_s_axil_araddr;
wire [2:0] rq_s_axil_arprot;
wire rq_s_axil_arvalid;
wire rq_s_axil_arready;
wire [31:0] rq_s_axil_rdata;
wire [1:0] rq_s_axil_rresp;
wire rq_s_axil_rvalid;
wire rq_s_axil_rready;
localparam CONTROL_PORTS=SEPARATE_RQ_ENABLE ? 5 : RETRY_MMIO_ENABLE ? 4 : CQ_MMIO_ENABLE ? 3 : 2;
wire [24*CONTROL_PORTS-1:0] bus_awaddr;
wire [3*CONTROL_PORTS-1:0] bus_awprot;
wire [1*CONTROL_PORTS-1:0] bus_awvalid;
wire [1*CONTROL_PORTS-1:0] bus_awready;
wire [32*CONTROL_PORTS-1:0] bus_wdata;
wire [4*CONTROL_PORTS-1:0] bus_wstrb;
wire [1*CONTROL_PORTS-1:0] bus_wvalid;
wire [1*CONTROL_PORTS-1:0] bus_wready;
wire [2*CONTROL_PORTS-1:0] bus_bresp;
wire [1*CONTROL_PORTS-1:0] bus_bvalid;
wire [1*CONTROL_PORTS-1:0] bus_bready;
wire [24*CONTROL_PORTS-1:0] bus_araddr;
wire [3*CONTROL_PORTS-1:0] bus_arprot;
wire [1*CONTROL_PORTS-1:0] bus_arvalid;
wire [1*CONTROL_PORTS-1:0] bus_arready;
wire [32*CONTROL_PORTS-1:0] bus_rdata;
wire [2*CONTROL_PORTS-1:0] bus_rresp;
wire [1*CONTROL_PORTS-1:0] bus_rvalid;
wire [1*CONTROL_PORTS-1:0] bus_rready;
axil_crossbar #(.S_COUNT(1),.M_COUNT(CONTROL_PORTS),.DATA_WIDTH(32),.ADDR_WIDTH(24),.STRB_WIDTH(4),
 .S_ACCEPT(32'd4),.M_ISSUE({CONTROL_PORTS{32'd4}}),.M_REGIONS(3),
 .M_BASE_ADDR(SEPARATE_RQ_ENABLE ?
  {24'd0,24'd0,24'h405000,24'd0,24'd0,24'h404000,24'd0,24'd0,24'h403000,24'd0,24'd0,24'h402000,24'h401000,24'h400000,24'h000000} : RETRY_MMIO_ENABLE ?
  {24'd0,24'd0,24'h404000,24'd0,24'd0,24'h403000,24'd0,24'd0,24'h402000,24'h401000,24'h400000,24'h000000} : CQ_MMIO_ENABLE ?
  {24'd0,24'd0,24'h403000,24'd0,24'd0,24'h402000,24'h401000,24'h400000,24'h000000} :
  {24'd0,24'd0,24'h402000,24'h401000,24'h400000,24'h000000}),
 .M_ADDR_WIDTH(SEPARATE_RQ_ENABLE ?
  {32'd0,32'd0,32'd12,32'd0,32'd0,32'd12,32'd0,32'd0,32'd12,32'd0,32'd0,32'd12,32'd12,32'd12,32'd20} : RETRY_MMIO_ENABLE ?
  {32'd0,32'd0,32'd12,32'd0,32'd0,32'd12,32'd0,32'd0,32'd12,32'd12,32'd12,32'd20} : CQ_MMIO_ENABLE ?
  {32'd0,32'd0,32'd12,32'd0,32'd0,32'd12,32'd12,32'd12,32'd20} :
  {32'd0,32'd0,32'd12,32'd12,32'd12,32'd20}),
 .S_AW_REG_TYPE(2'd2),.S_W_REG_TYPE(2'd2),.S_B_REG_TYPE(2'd2),
 .S_AR_REG_TYPE(2'd2),.S_R_REG_TYPE(2'd2)) native_sq_decode(
 .clk(clk),.rst(rst), .s_axil_awaddr(s_axil_awaddr),.m_axil_awaddr(bus_awaddr),
 .s_axil_awprot(s_axil_awprot),.m_axil_awprot(bus_awprot),
 .s_axil_awvalid(s_axil_awvalid),.m_axil_awvalid(bus_awvalid),
 .s_axil_awready(s_axil_awready),.m_axil_awready(bus_awready),
 .s_axil_wdata(s_axil_wdata),.m_axil_wdata(bus_wdata),
 .s_axil_wstrb(s_axil_wstrb),.m_axil_wstrb(bus_wstrb),
 .s_axil_wvalid(s_axil_wvalid),.m_axil_wvalid(bus_wvalid),
 .s_axil_wready(s_axil_wready),.m_axil_wready(bus_wready),
 .s_axil_bresp(s_axil_bresp),.m_axil_bresp(bus_bresp),
 .s_axil_bvalid(s_axil_bvalid),.m_axil_bvalid(bus_bvalid),
 .s_axil_bready(s_axil_bready),.m_axil_bready(bus_bready),
 .s_axil_araddr(s_axil_araddr),.m_axil_araddr(bus_araddr),
 .s_axil_arprot(s_axil_arprot),.m_axil_arprot(bus_arprot),
 .s_axil_arvalid(s_axil_arvalid),.m_axil_arvalid(bus_arvalid),
 .s_axil_arready(s_axil_arready),.m_axil_arready(bus_arready),
 .s_axil_rdata(s_axil_rdata),.m_axil_rdata(bus_rdata),
 .s_axil_rresp(s_axil_rresp),.m_axil_rresp(bus_rresp),
 .s_axil_rvalid(s_axil_rvalid),.m_axil_rvalid(bus_rvalid),
 .s_axil_rready(s_axil_rready),.m_axil_rready(bus_rready));
generate if(CQ_MMIO_ENABLE)begin : cq_control_window
    assign m_axil_cq_awaddr=bus_awaddr[48 +: 12];
    assign m_axil_cq_awprot=bus_awprot[6 +: 3];
    assign m_axil_cq_awvalid=bus_awvalid[2 +: 1];
    assign bus_awready[2 +: 1]=m_axil_cq_awready;
    assign m_axil_cq_wdata=bus_wdata[64 +: 32];
    assign m_axil_cq_wstrb=bus_wstrb[8 +: 4];
    assign m_axil_cq_wvalid=bus_wvalid[2 +: 1];
    assign bus_wready[2 +: 1]=m_axil_cq_wready;
    assign bus_bresp[4 +: 2]=m_axil_cq_bresp;
    assign bus_bvalid[2 +: 1]=m_axil_cq_bvalid;
    assign m_axil_cq_bready=bus_bready[2 +: 1];
    assign m_axil_cq_araddr=bus_araddr[48 +: 12];
    assign m_axil_cq_arprot=bus_arprot[6 +: 3];
    assign m_axil_cq_arvalid=bus_arvalid[2 +: 1];
    assign bus_arready[2 +: 1]=m_axil_cq_arready;
    assign bus_rdata[64 +: 32]=m_axil_cq_rdata;
    assign bus_rresp[4 +: 2]=m_axil_cq_rresp;
    assign bus_rvalid[2 +: 1]=m_axil_cq_rvalid;
    assign m_axil_cq_rready=bus_rready[2 +: 1];
end else begin : no_cq_control_window
    assign m_axil_cq_awaddr=0;
    assign m_axil_cq_awprot=0;
    assign m_axil_cq_awvalid=0;
    assign m_axil_cq_wdata=0;
    assign m_axil_cq_wstrb=0;
    assign m_axil_cq_wvalid=0;
    assign m_axil_cq_bready=0;
    assign m_axil_cq_araddr=0;
    assign m_axil_cq_arprot=0;
    assign m_axil_cq_arvalid=0;
    assign m_axil_cq_rready=0;
end endgenerate
generate if(RETRY_MMIO_ENABLE)begin : retry_control_window
    assign m_axil_retry_awaddr=bus_awaddr[72 +: 12];
    assign m_axil_retry_awprot=bus_awprot[9 +: 3];
    assign m_axil_retry_awvalid=bus_awvalid[3 +: 1];
    assign bus_awready[3 +: 1]=m_axil_retry_awready;
    assign m_axil_retry_wdata=bus_wdata[96 +: 32];
    assign m_axil_retry_wstrb=bus_wstrb[12 +: 4];
    assign m_axil_retry_wvalid=bus_wvalid[3 +: 1];
    assign bus_wready[3 +: 1]=m_axil_retry_wready;
    assign bus_bresp[6 +: 2]=m_axil_retry_bresp;
    assign bus_bvalid[3 +: 1]=m_axil_retry_bvalid;
    assign m_axil_retry_bready=bus_bready[3 +: 1];
    assign m_axil_retry_araddr=bus_araddr[72 +: 12];
    assign m_axil_retry_arprot=bus_arprot[9 +: 3];
    assign m_axil_retry_arvalid=bus_arvalid[3 +: 1];
    assign bus_arready[3 +: 1]=m_axil_retry_arready;
    assign bus_rdata[96 +: 32]=m_axil_retry_rdata;
    assign bus_rresp[6 +: 2]=m_axil_retry_rresp;
    assign bus_rvalid[3 +: 1]=m_axil_retry_rvalid;
    assign m_axil_retry_rready=bus_rready[3 +: 1];
end else begin : no_retry_control_window
    assign m_axil_retry_awaddr=0;
    assign m_axil_retry_awprot=0;
    assign m_axil_retry_awvalid=0;
    assign m_axil_retry_wdata=0;
    assign m_axil_retry_wstrb=0;
    assign m_axil_retry_wvalid=0;
    assign m_axil_retry_bready=0;
    assign m_axil_retry_araddr=0;
    assign m_axil_retry_arprot=0;
    assign m_axil_retry_arvalid=0;
    assign m_axil_retry_rready=0;
end endgenerate
assign sq_s_axil_awaddr=bus_awaddr[24 +: 12];
assign sq_s_axil_awprot=bus_awprot[3 +: 3];
assign sq_s_axil_awvalid=bus_awvalid[1 +: 1];
assign bus_awready[1 +: 1]=sq_s_axil_awready;
assign sq_s_axil_wdata=bus_wdata[32 +: 32];
assign sq_s_axil_wstrb=bus_wstrb[4 +: 4];
assign sq_s_axil_wvalid=bus_wvalid[1 +: 1];
assign bus_wready[1 +: 1]=sq_s_axil_wready;
assign bus_bresp[2 +: 2]=sq_s_axil_bresp;
assign bus_bvalid[1 +: 1]=sq_s_axil_bvalid;
assign sq_s_axil_bready=bus_bready[1 +: 1];
assign sq_s_axil_araddr=bus_araddr[24 +: 12];
assign sq_s_axil_arprot=bus_arprot[3 +: 3];
assign sq_s_axil_arvalid=bus_arvalid[1 +: 1];
assign bus_arready[1 +: 1]=sq_s_axil_arready;
assign bus_rdata[32 +: 32]=sq_s_axil_rdata;
assign bus_rresp[2 +: 2]=sq_s_axil_rresp;
assign bus_rvalid[1 +: 1]=sq_s_axil_rvalid;
assign sq_s_axil_rready=bus_rready[1 +: 1];
rocev2_native_endpoint #(.DUPLEX_ENABLE(DUPLEX_ENABLE),.TX_TAG_WIDTH(TX_TAG_WIDTH),.TS_WIDTH(TS_WIDTH),.RX_USER_WIDTH(RX_USER_WIDTH),.RAM_SIZE(RAM_SIZE),.RAM_ADDR_WIDTH(RAM_ADDR_WIDTH),.SEG_COUNT(SEG_COUNT),.SEG_DATA_WIDTH(SEG_DATA_WIDTH),.SEG_BE_WIDTH(SEG_BE_WIDTH),.SEG_ADDR_WIDTH(SEG_ADDR_WIDTH),.RAM_SEL_WIDTH(RAM_SEL_WIDTH),.DMA_LEN_WIDTH(DMA_LEN_WIDTH),.DMA_TAG_WIDTH(DMA_TAG_WIDTH),.LOCAL_WQE_ENABLE(1),.LOCAL_MEMORY_ENABLE(LOCAL_MEMORY_ENABLE),.EXTERNAL_CONFIGURATION_GUARD(1),.SHARED_HLS_ENABLE(SHARED_HLS_ENABLE),.QP_TX_ENABLE(QP_TX_ENABLE),.EXTERNAL_REPLAY_ENABLE(EXTERNAL_REPLAY_ENABLE),.SEND_ENABLE(SEND_ENABLE),.RECV_ENABLE(RECV_ENABLE),.RNR_ENABLE(RNR_ENABLE),.RECV_RETIRE_ENABLE(RECV_RETIRE_ENABLE),.RECV_CQ_ENABLE(RECV_CQ_ENABLE),.REQUEST_CQ_ENABLE(REQUEST_CQ_ENABLE),.SEPARATE_RQ_ENABLE(SEPARATE_RQ_ENABLE)) network(
    .s_recv_context(s_recv_context),
    .s_recv_valid(s_recv_valid),
    .s_recv_ready(s_recv_ready),
    .m_recv_query_qpn(m_recv_query_qpn),
    .m_recv_placement_context(m_recv_placement_context),
    .m_recv_placement_length(m_recv_placement_length),
    .m_recv_placement_valid(m_recv_placement_valid),
    .m_recv_placement_ready(m_recv_placement_ready),
    .recv_owned_guard(recv_owned_guard),
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
    .local_hls_local_ip(local_hls_local_ip),
    .local_hls_peer_ip(local_hls_peer_ip),
    .local_hls_peer_qpn(local_hls_peer_qpn),
 .clk(clk),
 .rst(rst),
 .extra_configuration_guard(route_guard),
 .s_axis_host_tx_tdata(s_axis_host_tx_tdata),
 .s_axis_host_tx_tkeep(s_axis_host_tx_tkeep),
 .s_axis_host_tx_tvalid(s_axis_host_tx_tvalid),
 .s_axis_host_tx_tready(s_axis_host_tx_tready),
 .s_axis_host_tx_tlast(s_axis_host_tx_tlast),
 .s_axis_host_tx_tuser(s_axis_host_tx_tuser),
 .m_axis_mac_tx_tdata(m_axis_mac_tx_tdata),
 .m_axis_mac_tx_tkeep(m_axis_mac_tx_tkeep),
 .m_axis_mac_tx_tvalid(m_axis_mac_tx_tvalid),
 .m_axis_mac_tx_tready(m_axis_mac_tx_tready),
 .m_axis_mac_tx_tlast(m_axis_mac_tx_tlast),
 .m_axis_mac_tx_tuser(m_axis_mac_tx_tuser),
 .s_axis_mac_cpl_tag(s_axis_mac_cpl_tag),
 .s_axis_mac_cpl_ts(s_axis_mac_cpl_ts),
 .s_axis_mac_cpl_valid(s_axis_mac_cpl_valid),
 .s_axis_mac_cpl_ready(s_axis_mac_cpl_ready),
 .m_axis_host_cpl_tag(m_axis_host_cpl_tag),
 .m_axis_host_cpl_ts(m_axis_host_cpl_ts),
 .m_axis_host_cpl_valid(m_axis_host_cpl_valid),
 .m_axis_host_cpl_ready(m_axis_host_cpl_ready),
 .s_axis_mac_rx_tdata(s_axis_mac_rx_tdata),
 .s_axis_mac_rx_tkeep(s_axis_mac_rx_tkeep),
 .s_axis_mac_rx_tvalid(s_axis_mac_rx_tvalid),
 .s_axis_mac_rx_tready(s_axis_mac_rx_tready),
 .s_axis_mac_rx_tlast(s_axis_mac_rx_tlast),
 .s_axis_mac_rx_tuser(s_axis_mac_rx_tuser),
 .m_axis_host_rx_tdata(m_axis_host_rx_tdata),
 .m_axis_host_rx_tkeep(m_axis_host_rx_tkeep),
 .m_axis_host_rx_tvalid(m_axis_host_rx_tvalid),
 .m_axis_host_rx_tready(m_axis_host_rx_tready),
 .m_axis_host_rx_tlast(m_axis_host_rx_tlast),
 .m_axis_host_rx_tuser(m_axis_host_rx_tuser),
 .qp_ready(qp_ready),
 .local_work_guard(local_work_guard),
    .s_local_memory_command_write(s_local_memory_command_write),
    .s_local_memory_command_offset(s_local_memory_command_offset),
    .s_local_memory_command_length(s_local_memory_command_length),
    .s_local_memory_command_key(s_local_memory_command_key),
    .s_local_memory_command_tag(s_local_memory_command_tag),
    .s_local_memory_command_valid(s_local_memory_command_valid),
    .s_local_memory_command_ready(s_local_memory_command_ready),
    .s_axis_local_memory_write_tdata(s_axis_local_memory_write_tdata),
    .s_axis_local_memory_write_tkeep(s_axis_local_memory_write_tkeep),
    .s_axis_local_memory_write_tlast(s_axis_local_memory_write_tlast),
    .s_axis_local_memory_write_tvalid(s_axis_local_memory_write_tvalid),
    .s_axis_local_memory_write_tready(s_axis_local_memory_write_tready),
    .m_axis_local_memory_read_tdata(m_axis_local_memory_read_tdata),
    .m_axis_local_memory_read_tkeep(m_axis_local_memory_read_tkeep),
    .m_axis_local_memory_read_tlast(m_axis_local_memory_read_tlast),
    .m_axis_local_memory_read_tvalid(m_axis_local_memory_read_tvalid),
    .m_axis_local_memory_read_tready(m_axis_local_memory_read_tready),
    .m_local_memory_status_tag(m_local_memory_status_tag),
    .m_local_memory_status_error(m_local_memory_status_error),
    .m_local_memory_status_valid(m_local_memory_status_valid),
    .m_local_memory_status_ready(m_local_memory_status_ready),
    .local_memory_busy(local_memory_busy),
 .local_configuration_idle(local_configuration_idle),
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
 .m_reject_error(m_reject_error),
 .m_reject_qpn(m_reject_qpn),
 .m_reject_psn(m_reject_psn),
 .m_reject_valid(m_reject_valid),
 .m_reject_ready(m_reject_ready),
 .quiescent(net_quiescent),
 .fault(net_fault),
 .fault_code(net_fault_code),
 .accepted_count(accepted_count),
 .rejected_count(rejected_count),
 .completed_count(completed_count),
 .tx_deferred_cycles(tx_deferred_cycles),
 .rx_integrity_good_count(rx_integrity_good_count),
 .rx_integrity_drop_count(rx_integrity_drop_count),
 .m_dma_read_address(net_m_dma_read_address),
 .m_dma_read_ram_sel(net_m_dma_read_ram_sel),
 .m_dma_read_ram_address(net_m_dma_read_ram_address),
 .m_dma_read_length(net_m_dma_read_length),
 .m_dma_read_tag(net_m_dma_read_tag),
 .m_dma_read_valid(net_m_dma_read_valid),
 .m_dma_read_ready(net_m_dma_read_ready),
 .s_dma_read_status_tag(net_s_dma_read_status_tag),
 .s_dma_read_status_error(net_s_dma_read_status_error),
 .s_dma_read_status_valid(net_s_dma_read_status_valid),
 .m_dma_write_address(net_m_dma_write_address),
 .m_dma_write_ram_sel(net_m_dma_write_ram_sel),
 .m_dma_write_ram_address(net_m_dma_write_ram_address),
 .m_dma_write_imm(net_m_dma_write_imm),
 .m_dma_write_imm_en(net_m_dma_write_imm_en),
 .m_dma_write_length(net_m_dma_write_length),
 .m_dma_write_tag(net_m_dma_write_tag),
 .m_dma_write_valid(net_m_dma_write_valid),
 .m_dma_write_ready(net_m_dma_write_ready),
 .s_dma_write_status_tag(net_s_dma_write_status_tag),
 .s_dma_write_status_error(net_s_dma_write_status_error),
 .s_dma_write_status_valid(net_s_dma_write_status_valid),
 .dma_ram_wr_cmd_sel(net_dma_ram_wr_cmd_sel),
 .dma_ram_wr_cmd_be(net_dma_ram_wr_cmd_be),
 .dma_ram_wr_cmd_addr(net_dma_ram_wr_cmd_addr),
 .dma_ram_wr_cmd_data(net_dma_ram_wr_cmd_data),
 .dma_ram_wr_cmd_valid(net_dma_ram_wr_cmd_valid),
 .dma_ram_wr_cmd_ready(net_dma_ram_wr_cmd_ready),
 .dma_ram_wr_done(net_dma_ram_wr_done),
 .dma_ram_rd_cmd_sel(net_dma_ram_rd_cmd_sel),
 .dma_ram_rd_cmd_addr(net_dma_ram_rd_cmd_addr),
 .dma_ram_rd_cmd_valid(net_dma_ram_rd_cmd_valid),
 .dma_ram_rd_cmd_ready(net_dma_ram_rd_cmd_ready),
 .dma_ram_rd_resp_data(net_dma_ram_rd_resp_data),
 .dma_ram_rd_resp_valid(net_dma_ram_rd_resp_valid),
 .dma_ram_rd_resp_ready(net_dma_ram_rd_resp_ready),
 .memory_drained(net_memory_drained),
 .physical_memory_drained(net_physical_memory_drained),
 .dma_command_count(dma_command_count),
 .dma_fence_count(dma_fence_count),
 .dma_completion_count(dma_completion_count),
 .parent_dma_drained(native_parent_safe),
 .admission_paused(admission_paused),
 .control_busy(control_busy),
 .control_fatal(control_fatal),
 .control_mmio_error(control_mmio_error),
 .epoch_ready(epoch_ready),
 .qp_configured(qp_configured),
 .run_requested(run_requested),
 .building(building),
 .active(active),
 .tainted(tainted),
 .config_safe(config_safe),
 .response_tx_quiescent(response_tx_quiescent),
 .request_frame_count(request_frame_count),
 .host_route_count(host_route_count),
 .request_drop_count(request_drop_count),
 .request_overflow_count(request_overflow_count),
 .request_stale_count(request_stale_count),
 .response_pending_frames(response_pending_frames),
 .s_axil_awaddr(bus_awaddr[0 +: 24]),
 .s_axil_awprot(bus_awprot[0 +: 3]),
 .s_axil_awvalid(bus_awvalid[0 +: 1]),
 .s_axil_awready(bus_awready[0 +: 1]),
 .s_axil_wdata(bus_wdata[0 +: 32]),
 .s_axil_wstrb(bus_wstrb[0 +: 4]),
 .s_axil_wvalid(bus_wvalid[0 +: 1]),
 .s_axil_wready(bus_wready[0 +: 1]),
 .s_axil_bresp(bus_bresp[0 +: 2]),
 .s_axil_bvalid(bus_bvalid[0 +: 1]),
 .s_axil_bready(bus_bready[0 +: 1]),
 .s_axil_araddr(bus_araddr[0 +: 24]),
 .s_axil_arprot(bus_arprot[0 +: 3]),
 .s_axil_arvalid(bus_arvalid[0 +: 1]),
 .s_axil_arready(bus_arready[0 +: 1]),
 .s_axil_rdata(bus_rdata[0 +: 32]),
 .s_axil_rresp(bus_rresp[0 +: 2]),
 .s_axil_rvalid(bus_rvalid[0 +: 1]),
 .s_axil_rready(bus_rready[0 +: 1]),
 .ethernet_config_error(ethernet_config_error),
 .ethernet_committed(ethernet_committed),
 .ethernet_enabled(ethernet_enabled),
 .ethernet_epoch(ethernet_epoch),
 .active_local_mac(active_local_mac),.active_peer_mac(active_peer_mac),.active_local_ip(active_local_ip));
rocev2_sq_control_regs #(.MAX_QPS(MAX_QPS)) queue_control(
 .clk(clk),
 .rst(rst),
 .s_axil_awaddr(sq_s_axil_awaddr),
 .s_axil_awprot(sq_s_axil_awprot),
 .s_axil_awvalid(sq_s_axil_awvalid),
 .s_axil_awready(sq_s_axil_awready),
 .s_axil_wdata(sq_s_axil_wdata),
 .s_axil_wstrb(sq_s_axil_wstrb),
 .s_axil_wvalid(sq_s_axil_wvalid),
 .s_axil_wready(sq_s_axil_wready),
 .s_axil_bresp(sq_s_axil_bresp),
 .s_axil_bvalid(sq_s_axil_bvalid),
 .s_axil_bready(sq_s_axil_bready),
 .s_axil_araddr(sq_s_axil_araddr),
 .s_axil_arprot(sq_s_axil_arprot),
 .s_axil_arvalid(sq_s_axil_arvalid),
 .s_axil_arready(sq_s_axil_arready),
 .s_axil_rdata(sq_s_axil_rdata),
 .s_axil_rresp(sq_s_axil_rresp),
 .s_axil_rvalid(sq_s_axil_rvalid),
 .s_axil_rready(sq_s_axil_rready),
 .cfg_command(sq_cfg_command),
 .cfg_qpn(sq_cfg_qpn),
 .cfg_pd(sq_cfg_pd),
 .cfg_epoch(sq_cfg_epoch),
 .cfg_dma_base(sq_cfg_dma_base),
 .cfg_log_depth(sq_cfg_log_depth),
 .cfg_producer(sq_cfg_producer),
 .cfg_valid(sq_cfg_valid),
 .cfg_ready(sq_cfg_ready),
 .cfg_response_error(sq_cfg_response_error),
 .cfg_response_qpn(sq_cfg_response_qpn),
 .cfg_response_epoch(sq_cfg_response_epoch),
 .cfg_response_consumer(sq_cfg_response_consumer),
 .cfg_response_valid(sq_cfg_response_valid),
 .cfg_response_ready(sq_cfg_response_ready),
 .parent_dma_drained(native_parent_safe),
 .endpoint_fault(fault),
 .fetch_queue_guard(sq_queue_guard),
 .work_queue_guard(sq_downstream_queue_guard),
 .wire_queue_guard(wire_queue_guard),
 .completion_queue_guard(completion_queue_guard),
 .busy(sq_control_busy),
 .response_valid(sq_control_response_valid),
 .fatal(sq_control_fatal),
 .mmio_error(sq_control_mmio_error),
 .owner_active(sq_control_owner_active),
 .owner_tainted(sq_control_owner_tainted),
 .last_sequence(sq_control_last_sequence),
 .owner_query_qpn(owner_query_qpn),.owner_query_cookie(sq_owner_query_cookie),
 .owner_query_epoch(sq_owner_query_epoch),.owner_query_pd(sq_owner_query_pd),.owner_query_valid(sq_owner_query_valid),
 .retry_query_qpn(retry_query_qpn),.retry_query_cookie(retry_query_cookie),.retry_query_epoch(retry_query_epoch),
 .retry_query_pd(retry_query_pd),.retry_query_valid(retry_query_valid)
);

rocev2_sq_dma_fetch #(
    .MAX_QPS(MAX_QPS),.SEPARATE_RQ_ENABLE(SEPARATE_RQ_ENABLE),.RECV_CANCEL_ENABLE(RECV_CANCEL_ENABLE),.RAM_SIZE(RAM_SIZE),.RAM_ADDR_WIDTH(RAM_ADDR_WIDTH),.SEG_COUNT(SEG_COUNT),
    .SEG_DATA_WIDTH(SEG_DATA_WIDTH),.SEG_BE_WIDTH(SEG_BE_WIDTH),.SEG_ADDR_WIDTH(SEG_ADDR_WIDTH),
    .RAM_SEL_WIDTH(1),.DMA_LEN_WIDTH(DMA_LEN_WIDTH),.TAG_WIDTH(TAG_WIDTH)
) sq (
    .clk(clk),
    .cfg_receive(fetch_cfg_receive),.admission_available({!rq_admission_busy,!admission_busy}),
    .receive_downstream_guard(rq_downstream_queue_guard),.receive_queue_guard(receive_fetch_guard),
    .receive_queue_active(receive_queue_active),.receive_queue_pending(receive_queue_pending),
    .receive_queue_halted(receive_queue_halted),.m_result_receive(fetch_result_receive),
    .rst(rst),
    .enable(enable && local_configuration_idle && !fault && !m_recv_cancel_block),
    .cfg_command(fetch_cfg_command),
    .cfg_qpn(fetch_cfg_qpn),
    .cfg_pd(fetch_cfg_pd),
    .cfg_epoch(fetch_cfg_epoch),
    .cfg_dma_base(fetch_cfg_dma_base),
    .cfg_log_depth(fetch_cfg_log_depth),
    .cfg_producer(fetch_cfg_producer),
    .cfg_valid(fetch_cfg_valid),
    .cfg_ready(fetch_cfg_ready),
    .cfg_response_error(fetch_cfg_response_error),
    .cfg_response_qpn(fetch_cfg_response_qpn),
    .cfg_response_epoch(fetch_cfg_response_epoch),
    .cfg_response_consumer(fetch_cfg_response_consumer),
    .cfg_response_valid(fetch_cfg_response_valid),
    .cfg_response_ready(fetch_cfg_response_ready),
    .parent_dma_drained(parent_dma_drained && router_drained && !fault),
    .downstream_queue_guard(sq_downstream_queue_guard),
    .queue_guard(sq_queue_guard),
    .queue_active(sq_queue_active),
    .queue_pending(sq_queue_pending),
    .queue_halted(sq_queue_halted),
    .m_result_data(sq_m_result_data),
    .m_result_error(sq_m_result_error),
    .m_result_qpn(sq_m_result_qpn),
    .m_result_pd(sq_m_result_pd),
    .m_result_epoch(sq_m_result_epoch),
    .m_result_sequence(sq_m_result_sequence),
    .m_result_tag(sq_m_result_tag),
    .m_result_valid(sq_m_result_valid),
    .m_result_ready(sq_m_result_ready),
    .busy(sq_busy),
    .tag_exhausted(sq_tag_exhausted),
    .fault(sq_fault),
    .fault_code(sq_fault_code),
    .fetch_count(sq_fetch_count),
    .result_count(sq_result_count),
    .m_dma_read_address(sq_m_dma_read_address),
    .m_dma_read_ram_sel(sq_m_dma_read_ram_sel),
    .m_dma_read_ram_address(sq_m_dma_read_ram_address),
    .m_dma_read_length(sq_m_dma_read_length),
    .m_dma_read_tag(sq_m_dma_read_tag),
    .m_dma_read_valid(sq_m_dma_read_valid),
    .m_dma_read_ready(sq_m_dma_read_ready),
    .s_dma_read_status_tag(sq_s_dma_read_status_tag),
    .s_dma_read_status_error(sq_s_dma_read_status_error),
    .s_dma_read_status_valid(sq_s_dma_read_status_valid),
    .m_dma_write_address(sq_m_dma_write_address),
    .m_dma_write_ram_sel(sq_m_dma_write_ram_sel),
    .m_dma_write_ram_address(sq_m_dma_write_ram_address),
    .m_dma_write_imm(sq_m_dma_write_imm),
    .m_dma_write_imm_en(sq_m_dma_write_imm_en),
    .m_dma_write_length(sq_m_dma_write_length),
    .m_dma_write_tag(sq_m_dma_write_tag),
    .m_dma_write_valid(sq_m_dma_write_valid),
    .m_dma_write_ready(sq_m_dma_write_ready),
    .s_dma_write_status_tag(sq_s_dma_write_status_tag),
    .s_dma_write_status_error(sq_s_dma_write_status_error),
    .s_dma_write_status_valid(sq_s_dma_write_status_valid),
    .dma_ram_wr_cmd_sel(sq_dma_ram_wr_cmd_sel),
    .dma_ram_wr_cmd_be(sq_dma_ram_wr_cmd_be),
    .dma_ram_wr_cmd_addr(sq_dma_ram_wr_cmd_addr),
    .dma_ram_wr_cmd_data(sq_dma_ram_wr_cmd_data),
    .dma_ram_wr_cmd_valid(sq_dma_ram_wr_cmd_valid),
    .dma_ram_wr_cmd_ready(sq_dma_ram_wr_cmd_ready),
    .dma_ram_wr_done(sq_dma_ram_wr_done),
    .dma_ram_rd_cmd_sel(sq_dma_ram_rd_cmd_sel),
    .dma_ram_rd_cmd_addr(sq_dma_ram_rd_cmd_addr),
    .dma_ram_rd_cmd_valid(sq_dma_ram_rd_cmd_valid),
    .dma_ram_rd_cmd_ready(sq_dma_ram_rd_cmd_ready),
    .dma_ram_rd_resp_data(sq_dma_ram_rd_resp_data),
    .dma_ram_rd_resp_valid(sq_dma_ram_rd_resp_valid),
    .dma_ram_rd_resp_ready(sq_dma_ram_rd_resp_ready),
    .dma_drained(sq_dma_drained),
    .backend_command_count(sq_backend_command_count),
    .backend_fence_count(sq_backend_fence_count),
    .backend_completion_count(sq_backend_completion_count)
);

rocev2_dma_client_router #(
    .RAM_ADDR_WIDTH(RAM_ADDR_WIDTH),.SEG_COUNT(SEG_COUNT),.SEG_DATA_WIDTH(SEG_DATA_WIDTH),
    .SEG_BE_WIDTH(SEG_BE_WIDTH),.SEG_ADDR_WIDTH(SEG_ADDR_WIDTH),.DMA_LEN_WIDTH(DMA_LEN_WIDTH),.TAG_WIDTH(TAG_WIDTH)
) router (
    .clk(clk),
    .rst(rst),
    .enable(enable && !fault),
    .s_client_read_address({sq_m_dma_read_address,net_m_dma_read_address}),
    .s_client_read_ram_sel({sq_m_dma_read_ram_sel,net_m_dma_read_ram_sel}),
    .s_client_read_ram_address({sq_m_dma_read_ram_address,net_m_dma_read_ram_address}),
    .s_client_read_length({sq_m_dma_read_length,net_m_dma_read_length}),
    .s_client_read_tag({sq_m_dma_read_tag,net_m_dma_read_tag}),
    .s_client_read_valid({sq_m_dma_read_valid,net_m_dma_read_valid}),
    .s_client_read_ready({sq_m_dma_read_ready,net_m_dma_read_ready}),
    .m_client_read_status_tag({sq_s_dma_read_status_tag,net_s_dma_read_status_tag}),
    .m_client_read_status_error({sq_s_dma_read_status_error,net_s_dma_read_status_error}),
    .m_client_read_status_valid({sq_s_dma_read_status_valid,net_s_dma_read_status_valid}),
    .s_client_write_address({sq_m_dma_write_address,net_m_dma_write_address}),
    .s_client_write_ram_sel({sq_m_dma_write_ram_sel,net_m_dma_write_ram_sel}),
    .s_client_write_ram_address({sq_m_dma_write_ram_address,net_m_dma_write_ram_address}),
    .s_client_write_imm({sq_m_dma_write_imm,net_m_dma_write_imm}),
    .s_client_write_imm_en({sq_m_dma_write_imm_en,net_m_dma_write_imm_en}),
    .s_client_write_length({sq_m_dma_write_length,net_m_dma_write_length}),
    .s_client_write_tag({sq_m_dma_write_tag,net_m_dma_write_tag}),
    .s_client_write_valid({sq_m_dma_write_valid,net_m_dma_write_valid}),
    .s_client_write_ready({sq_m_dma_write_ready,net_m_dma_write_ready}),
    .m_client_write_status_tag({sq_s_dma_write_status_tag,net_s_dma_write_status_tag}),
    .m_client_write_status_error({sq_s_dma_write_status_error,net_s_dma_write_status_error}),
    .m_client_write_status_valid({sq_s_dma_write_status_valid,net_s_dma_write_status_valid}),
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
    .client_ram_wr_cmd_sel({sq_dma_ram_wr_cmd_sel,net_dma_ram_wr_cmd_sel}),
    .client_ram_wr_cmd_be({sq_dma_ram_wr_cmd_be,net_dma_ram_wr_cmd_be}),
    .client_ram_wr_cmd_addr({sq_dma_ram_wr_cmd_addr,net_dma_ram_wr_cmd_addr}),
    .client_ram_wr_cmd_data({sq_dma_ram_wr_cmd_data,net_dma_ram_wr_cmd_data}),
    .client_ram_wr_cmd_valid({sq_dma_ram_wr_cmd_valid,net_dma_ram_wr_cmd_valid}),
    .client_ram_wr_cmd_ready({sq_dma_ram_wr_cmd_ready,net_dma_ram_wr_cmd_ready}),
    .client_ram_wr_done({sq_dma_ram_wr_done,net_dma_ram_wr_done}),
    .client_ram_rd_cmd_sel({sq_dma_ram_rd_cmd_sel,net_dma_ram_rd_cmd_sel}),
    .client_ram_rd_cmd_addr({sq_dma_ram_rd_cmd_addr,net_dma_ram_rd_cmd_addr}),
    .client_ram_rd_cmd_valid({sq_dma_ram_rd_cmd_valid,net_dma_ram_rd_cmd_valid}),
    .client_ram_rd_cmd_ready({sq_dma_ram_rd_cmd_ready,net_dma_ram_rd_cmd_ready}),
    .client_ram_rd_resp_data({sq_dma_ram_rd_resp_data,net_dma_ram_rd_resp_data}),
    .client_ram_rd_resp_valid({sq_dma_ram_rd_resp_valid,net_dma_ram_rd_resp_valid}),
    .client_ram_rd_resp_ready({sq_dma_ram_rd_resp_ready,net_dma_ram_rd_resp_ready}),
    .client_busy(router_client_busy),
    .drained(router_drained),
    .tag_exhausted(router_tag_exhausted),
    .fault(router_fault),
    .fault_code(router_fault_code),
    .descriptor_count(router_descriptor_count),
    .completion_count(router_completion_count)
);

rocev2_sq_wqe_admission #(.MAX_QPS(MAX_QPS),.SEND_ENABLE(SEND_ENABLE),.RECV_ENABLE(RECV_ENABLE && !SEPARATE_RQ_ENABLE)) admission(
 .clk(clk),
 .rst(rst),
 .enable(enable && !fault),
 .configuration_idle(local_configuration_idle),
 .s_fetch_data(sq_m_result_data),
 .s_fetch_error(sq_m_result_error),
 .s_fetch_qpn(sq_m_result_qpn),
 .s_fetch_pd(sq_m_result_pd),
 .s_fetch_epoch(sq_m_result_epoch),
 .s_fetch_sequence(sq_m_result_sequence),
 .s_fetch_tag(sq_m_result_tag),
 .s_fetch_valid(sq_m_result_valid && !fetch_result_receive),
 .s_fetch_ready(send_result_ready),
 .m_mr_request_pd(sq_mr_request_pd),
 .m_mr_request_key(sq_mr_request_key),
 .m_mr_request_address(sq_mr_request_address),
 .m_mr_request_length(sq_mr_request_length),
 .m_mr_request_operation(sq_mr_request_operation),
 .m_mr_request_tag(sq_mr_request_tag),
 .m_mr_request_valid(sq_mr_request_valid),
 .m_mr_request_ready(sq_mr_request_ready),
 .s_mr_response_tag(sq_mr_response_tag),
 .s_mr_response_error(sq_mr_response_error),
 .s_mr_response_offset(sq_mr_response_offset),
 .s_mr_response_length(sq_mr_response_length),
 .s_mr_response_valid(sq_mr_response_valid),
 .s_mr_response_ready(sq_mr_response_ready),
 .m_work_wr_id(m_work_wr_id),
 .m_work_sequence(m_work_sequence),
 .m_work_epoch(m_work_epoch),
 .m_work_qpn(m_work_qpn),
 .m_work_pd(m_work_pd),
 .m_work_tag(m_work_tag),
 .m_work_opcode(m_work_opcode),
 .m_work_flags(m_work_flags),
 .m_work_length(m_work_length),
 .m_work_local_key(m_work_local_key),
 .m_work_local_address(m_work_local_address),
 .m_work_local_offset(m_work_local_offset),
 .m_work_remote_address(m_work_remote_address),
 .m_work_remote_key(m_work_remote_key),
 .m_work_error(m_work_error),
 .m_work_error_source(m_work_error_source),
 .m_work_fetch_error(m_work_fetch_error),
 .m_work_descriptor_available(m_work_descriptor_available),
 .m_work_authorized(m_work_authorized),
 .m_work_valid(m_work_valid),
 .m_work_ready(bridge_work_ready),
 .queue_guard(admission_queue_guard),
 .configuration_guard(admission_configuration_guard),
 .busy(admission_busy),
 .fault(admission_fault),
 .fault_code(admission_fault_code));

generate if(SEPARATE_RQ_ENABLE)begin : independent_receive_frontend
assign rq_s_axil_awaddr=bus_awaddr[96 +: 12];
assign rq_s_axil_awprot=bus_awprot[12 +: 3];
assign rq_s_axil_awvalid=bus_awvalid[4 +: 1];
assign bus_awready[4 +: 1]=rq_s_axil_awready;
assign rq_s_axil_wdata=bus_wdata[128 +: 32];
assign rq_s_axil_wstrb=bus_wstrb[16 +: 4];
assign rq_s_axil_wvalid=bus_wvalid[4 +: 1];
assign bus_wready[4 +: 1]=rq_s_axil_wready;
assign bus_bresp[8 +: 2]=rq_s_axil_bresp;
assign bus_bvalid[4 +: 1]=rq_s_axil_bvalid;
assign rq_s_axil_bready=bus_bready[4 +: 1];
assign rq_s_axil_araddr=bus_araddr[96 +: 12];
assign rq_s_axil_arprot=bus_arprot[12 +: 3];
assign rq_s_axil_arvalid=bus_arvalid[4 +: 1];
assign bus_arready[4 +: 1]=rq_s_axil_arready;
assign bus_rdata[128 +: 32]=rq_s_axil_rdata;
assign bus_rresp[8 +: 2]=rq_s_axil_rresp;
assign bus_rvalid[4 +: 1]=rq_s_axil_rvalid;
assign rq_s_axil_rready=bus_rready[4 +: 1];

rocev2_sq_control_regs #(.MAX_QPS(MAX_QPS),.CONTROL_ID(32'h52514331),.RECV_CANCEL_ENABLE(RECV_CANCEL_ENABLE)) receive_queue_control(
 .clk(clk),
 .rst(rst),
 .s_axil_awaddr(rq_s_axil_awaddr),
 .s_axil_awprot(rq_s_axil_awprot),
 .s_axil_awvalid(rq_s_axil_awvalid),
 .s_axil_awready(rq_s_axil_awready),
 .s_axil_wdata(rq_s_axil_wdata),
 .s_axil_wstrb(rq_s_axil_wstrb),
 .s_axil_wvalid(rq_s_axil_wvalid),
 .s_axil_wready(rq_s_axil_wready),
 .s_axil_bresp(rq_s_axil_bresp),
 .s_axil_bvalid(rq_s_axil_bvalid),
 .s_axil_bready(rq_s_axil_bready),
 .s_axil_araddr(rq_s_axil_araddr),
 .s_axil_arprot(rq_s_axil_arprot),
 .s_axil_arvalid(rq_s_axil_arvalid),
 .s_axil_arready(rq_s_axil_arready),
 .s_axil_rdata(rq_s_axil_rdata),
 .s_axil_rresp(rq_s_axil_rresp),
 .s_axil_rvalid(rq_s_axil_rvalid),
 .s_axil_rready(rq_s_axil_rready),
 .cfg_command(rq_cfg_command),
 .cfg_qpn(rq_cfg_qpn),
 .cfg_pd(rq_cfg_pd),
 .cfg_epoch(rq_cfg_epoch),
 .cfg_dma_base(rq_cfg_dma_base),
 .cfg_log_depth(rq_cfg_log_depth),
 .cfg_producer(rq_cfg_producer),
 .cfg_valid(rq_cfg_valid),
 .cfg_ready(rq_cfg_ready),
 .cfg_response_error(rq_cfg_response_error),
 .cfg_response_qpn(rq_cfg_response_qpn),
 .cfg_response_epoch(rq_cfg_response_epoch),
 .cfg_response_consumer(rq_cfg_response_consumer),
 .cfg_response_valid(rq_cfg_response_valid),
 .cfg_response_ready(rq_cfg_response_ready),
 .parent_dma_drained(native_parent_safe),
 .cancel_block(m_recv_cancel_block),.cancel_valid(rq_cancel_valid),.cancel_qpn(m_recv_cancel_qpn),
 .cancel_pd(m_recv_cancel_pd),.cancel_epoch(m_recv_cancel_epoch),
 .cancel_ready(s_recv_cancel_ready && m_recv_cancel_valid),
 .endpoint_fault(fault),
 .fetch_queue_guard(receive_fetch_guard),
 .work_queue_guard(rq_downstream_queue_guard),
 .wire_queue_guard(wire_queue_guard),
 .completion_queue_guard(completion_queue_guard),
 .busy(rq_control_busy),
 .response_valid(rq_control_response_valid),
 .fatal(rq_control_fatal),
 .mmio_error(rq_control_mmio_error),
 .owner_active(rq_control_owner_active),
 .owner_tainted(rq_control_owner_tainted),
 .last_sequence(rq_control_last_sequence),
 .owner_query_qpn(owner_query_qpn),.owner_query_cookie(rq_owner_query_cookie),
 .owner_query_epoch(rq_owner_query_epoch),.owner_query_pd(rq_owner_query_pd),.owner_query_valid(rq_owner_query_valid),
 .retry_query_qpn(24'd0),.retry_query_cookie(),.retry_query_epoch(),
 .retry_query_pd(),.retry_query_valid()
);

rocev2_sq_wqe_admission #(.MAX_QPS(MAX_QPS),.SEND_ENABLE(0),.RECV_ENABLE(1),.RECV_ONLY(1)) receive_admission(
 .clk(clk),
 .rst(rst),
 .enable(enable && !fault),
 .configuration_idle(local_configuration_idle),
 .s_fetch_data(sq_m_result_data),
 .s_fetch_error(sq_m_result_error),
 .s_fetch_qpn(sq_m_result_qpn),
 .s_fetch_pd(sq_m_result_pd),
 .s_fetch_epoch(sq_m_result_epoch),
 .s_fetch_sequence(sq_m_result_sequence),
 .s_fetch_tag(sq_m_result_tag),
 .s_fetch_valid(sq_m_result_valid && fetch_result_receive),
 .s_fetch_ready(receive_result_ready),
 .m_mr_request_pd(rq_mr_request_pd),
 .m_mr_request_key(rq_mr_request_key),
 .m_mr_request_address(rq_mr_request_address),
 .m_mr_request_length(rq_mr_request_length),
 .m_mr_request_operation(rq_mr_request_operation),
 .m_mr_request_tag(rq_mr_request_tag),
 .m_mr_request_valid(rq_mr_request_valid),
 .m_mr_request_ready(rq_mr_request_ready),
 .s_mr_response_tag(rq_mr_response_tag),
 .s_mr_response_error(rq_mr_response_error),
 .s_mr_response_offset(rq_mr_response_offset),
 .s_mr_response_length(rq_mr_response_length),
 .s_mr_response_valid(rq_mr_response_valid),
 .s_mr_response_ready(rq_mr_response_ready),
 .m_work_wr_id(rq_work_wr_id),
 .m_work_sequence(rq_work_sequence),
 .m_work_epoch(rq_work_epoch),
 .m_work_qpn(rq_work_qpn),
 .m_work_pd(rq_work_pd),
 .m_work_tag(rq_work_tag),
 .m_work_opcode(rq_work_opcode),
 .m_work_flags(rq_work_flags),
 .m_work_length(rq_work_length),
 .m_work_local_key(rq_work_local_key),
 .m_work_local_address(rq_work_local_address),
 .m_work_local_offset(rq_work_local_offset),
 .m_work_remote_address(rq_work_remote_address),
 .m_work_remote_key(rq_work_remote_key),
 .m_work_error(rq_work_error),
 .m_work_error_source(rq_work_error_source),
 .m_work_fetch_error(rq_work_fetch_error),
 .m_work_descriptor_available(rq_work_descriptor_available),
 .m_work_authorized(rq_work_authorized),
 .m_work_valid(rq_work_valid),
 .m_work_ready(rq_work_ready),
 .queue_guard(rq_admission_guard),
 .configuration_guard(rq_admission_configuration_guard),
 .busy(rq_admission_busy),
 .fault(rq_admission_fault),
 .fault_code(rq_admission_fault_code));

rocev2_queue_cfg_arbiter queue_configs(
 .clk(clk),.rst(rst),
 .s_command({rq_cfg_command,rq_cfg_qpn,rq_cfg_pd,rq_cfg_epoch,rq_cfg_dma_base,rq_cfg_log_depth,rq_cfg_producer,sq_cfg_command,sq_cfg_qpn,sq_cfg_pd,sq_cfg_epoch,sq_cfg_dma_base,sq_cfg_log_depth,sq_cfg_producer}),
 .s_valid({rq_cfg_valid,sq_cfg_valid}),.s_ready({rq_cfg_ready,sq_cfg_ready}),
 .s_response({rq_cfg_response_error,rq_cfg_response_qpn,rq_cfg_response_epoch,rq_cfg_response_consumer,sq_cfg_response_error,sq_cfg_response_qpn,sq_cfg_response_epoch,sq_cfg_response_consumer}),
 .s_response_valid({rq_cfg_response_valid,sq_cfg_response_valid}),
 .s_response_ready({rq_cfg_response_ready,sq_cfg_response_ready}),
 .m_command({fetch_cfg_command,fetch_cfg_qpn,fetch_cfg_pd,fetch_cfg_epoch,fetch_cfg_dma_base,fetch_cfg_log_depth,fetch_cfg_producer}),.m_receive(fetch_cfg_receive),
 .m_valid(fetch_cfg_valid),.m_ready(fetch_cfg_ready),
 .m_response({fetch_cfg_response_error,fetch_cfg_response_qpn,fetch_cfg_response_epoch,fetch_cfg_response_consumer}),.m_response_valid(fetch_cfg_response_valid),
 .m_response_ready(fetch_cfg_response_ready),.busy(cfg_mux_busy),.fault(cfg_mux_fault));
rocev2_mr_query_arbiter local_queries(
 .clk(clk),.rst(rst),
 .s_request_pd({rq_mr_request_pd,sq_mr_request_pd}),
 .m_request_pd(s_local_mr_request_pd),
 .s_request_key({rq_mr_request_key,sq_mr_request_key}),
 .m_request_key(s_local_mr_request_key),
 .s_request_address({rq_mr_request_address,sq_mr_request_address}),
 .m_request_address(s_local_mr_request_address),
 .s_request_length({rq_mr_request_length,sq_mr_request_length}),
 .m_request_length(s_local_mr_request_length),
 .s_request_operation({rq_mr_request_operation,sq_mr_request_operation}),
 .m_request_operation(s_local_mr_request_operation),
 .s_request_tag({rq_mr_request_tag,sq_mr_request_tag}),
 .m_request_tag(s_local_mr_request_tag),
 .s_request_valid({rq_mr_request_valid,sq_mr_request_valid}),
 .m_request_valid(s_local_mr_request_valid),
 .s_request_ready({rq_mr_request_ready,sq_mr_request_ready}),
 .m_request_ready(s_local_mr_request_ready),
 .m_response_tag({rq_mr_response_tag,sq_mr_response_tag}),
 .s_response_tag(m_local_mr_response_tag),
 .m_response_error({rq_mr_response_error,sq_mr_response_error}),
 .s_response_error(m_local_mr_response_error),
 .m_response_offset({rq_mr_response_offset,sq_mr_response_offset}),
 .s_response_offset(m_local_mr_response_offset),
 .m_response_length({rq_mr_response_length,sq_mr_response_length}),
 .s_response_length(m_local_mr_response_length),
 .m_response_valid({rq_mr_response_valid,sq_mr_response_valid}),
 .s_response_valid(m_local_mr_response_valid),
 .m_response_ready({rq_mr_response_ready,sq_mr_response_ready}),
 .s_response_ready(m_local_mr_response_ready),
 // Native local lookup returns a logical offset, not a DMA authorization.
 .s_response_dma_address(64'd0),.m_response_dma_address(),
 .busy(mr_mux_busy),.fault(mr_mux_fault),.fault_code(mr_mux_fault_code));
end else begin : legacy_shared_ring
assign m_recv_cancel_block=0;assign rq_cancel_valid=0;
assign m_recv_cancel_qpn=0;assign m_recv_cancel_pd=0;assign m_recv_cancel_epoch=0;
assign fetch_cfg_receive=0;
assign cfg_mux_busy=0;assign cfg_mux_fault=0;assign mr_mux_busy=0;assign mr_mux_fault=0;assign mr_mux_fault_code=0;
assign rq_control_busy=0;assign rq_control_response_valid=0;assign rq_control_fatal=0;assign rq_control_mmio_error=0;
assign rq_control_owner_active=0;assign rq_control_owner_tainted=0;assign rq_control_last_sequence=0;
assign rq_owner_query_cookie=0;assign rq_owner_query_epoch=0;assign rq_owner_query_pd=0;assign rq_owner_query_valid=0;
assign rq_admission_guard=0;assign rq_admission_configuration_guard=0;
assign rq_admission_busy=0;assign rq_admission_fault=0;assign rq_admission_fault_code=0;
assign receive_result_ready=0;assign rq_work_valid=0;
assign rq_cfg_valid=0;assign rq_cfg_response_ready=0;
assign rq_work_wr_id=0;
assign rq_work_sequence=0;
assign rq_work_epoch=0;
assign rq_work_qpn=0;
assign rq_work_pd=0;
assign rq_work_tag=0;
assign rq_work_opcode=0;
assign rq_work_flags=0;
assign rq_work_length=0;
assign rq_work_local_key=0;
assign rq_work_local_address=0;
assign rq_work_local_offset=0;
assign rq_work_remote_address=0;
assign rq_work_remote_key=0;
assign rq_work_error=0;
assign rq_work_error_source=0;
assign rq_work_fetch_error=0;
assign rq_work_descriptor_available=0;
assign rq_work_authorized=0;
assign fetch_cfg_command=sq_cfg_command;assign rq_cfg_command=0;
assign fetch_cfg_qpn=sq_cfg_qpn;assign rq_cfg_qpn=0;
assign fetch_cfg_pd=sq_cfg_pd;assign rq_cfg_pd=0;
assign fetch_cfg_epoch=sq_cfg_epoch;assign rq_cfg_epoch=0;
assign fetch_cfg_dma_base=sq_cfg_dma_base;assign rq_cfg_dma_base=0;
assign fetch_cfg_log_depth=sq_cfg_log_depth;assign rq_cfg_log_depth=0;
assign fetch_cfg_producer=sq_cfg_producer;assign rq_cfg_producer=0;
assign fetch_cfg_valid=sq_cfg_valid;assign sq_cfg_ready=fetch_cfg_ready;assign rq_cfg_ready=0;
assign sq_cfg_response_error=fetch_cfg_response_error;assign rq_cfg_response_error=0;
assign sq_cfg_response_qpn=fetch_cfg_response_qpn;assign rq_cfg_response_qpn=0;
assign sq_cfg_response_epoch=fetch_cfg_response_epoch;assign rq_cfg_response_epoch=0;
assign sq_cfg_response_consumer=fetch_cfg_response_consumer;assign rq_cfg_response_consumer=0;
assign sq_cfg_response_valid=fetch_cfg_response_valid;assign fetch_cfg_response_ready=sq_cfg_response_ready;assign rq_cfg_response_valid=0;
assign s_local_mr_request_pd=sq_mr_request_pd;assign rq_mr_request_pd=0;
assign s_local_mr_request_key=sq_mr_request_key;assign rq_mr_request_key=0;
assign s_local_mr_request_address=sq_mr_request_address;assign rq_mr_request_address=0;
assign s_local_mr_request_length=sq_mr_request_length;assign rq_mr_request_length=0;
assign s_local_mr_request_operation=sq_mr_request_operation;assign rq_mr_request_operation=0;
assign s_local_mr_request_tag=sq_mr_request_tag;assign rq_mr_request_tag=0;
assign s_local_mr_request_valid=sq_mr_request_valid;assign rq_mr_request_valid=0;
assign sq_mr_request_ready=s_local_mr_request_ready;assign rq_mr_request_ready=0;
assign sq_mr_response_tag=m_local_mr_response_tag;assign rq_mr_response_tag=0;
assign sq_mr_response_error=m_local_mr_response_error;assign rq_mr_response_error=0;
assign sq_mr_response_offset=m_local_mr_response_offset;assign rq_mr_response_offset=0;
assign sq_mr_response_length=m_local_mr_response_length;assign rq_mr_response_length=0;
assign sq_mr_response_valid=m_local_mr_response_valid;assign rq_mr_response_valid=0;
assign m_local_mr_response_ready=sq_mr_response_ready;assign rq_mr_response_ready=0;
end endgenerate
endmodule
`resetall
