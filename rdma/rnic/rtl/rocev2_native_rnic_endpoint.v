// SPDX-License-Identifier: BSD-2-Clause-Views
// Copyright (c) 2026 jyohukuchan
// Native READ/WRITE vertical integration: coherent SQ -> SAME MR -> existing
// shared responder HLS -> saved-authority executor -> SAME PTE/PCIe backend.
// Issued TX/PSN, protected response, READ unpadding and genuine MAC receipt
// ownership are hardware-connected here, not testbench/CPU substitutions.
// The original native/legacy path remains selected inside the native parent.
// This is SOURCE/OFFLINE integration, not a programmed or timing-closed board.
// Same-core internal drain is NOT proved: tie it LOW, keep the local role and
// WR/MR/CQ references held. The real CQC1 publisher is connected but cannot
// expose a local event until BOTH lifetime commit and actual core retirement.
// Opt-in receive CQ uses an exact per-operation HLS/MAC/placement lifecycle;
// it does NOT assert those still-missing global/requester drain certificates.
// No "idle => complete", external fake CQ commit or unpin.
// Current datapath is one positive <=4096-byte READ/WRITE. Error CQ/recovery,
// SEND/RECV, concurrency, standard verbs/provider and full timing remain work.
`resetall
`timescale 1ns/1ps
`default_nettype none
module rocev2_native_rnic_endpoint #(
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
    // Opt in ONLY with the separately generated QP-TX/state-readback core.
    parameter QP_TX_ENABLE=0,
    parameter RETRY_ENABLE=0,
    parameter SEND_ENABLE=0,
    parameter RECV_ENABLE=0,
    parameter RNR_ENABLE=0,
    parameter RECV_RETIRE_ENABLE=0,
    parameter RECV_CQ_ENABLE=0,
    parameter REQUEST_CQ_ENABLE=0,
    parameter DUPLEX_ENABLE=0,
    parameter SEPARATE_RQ_ENABLE=0,
    parameter RECV_CANCEL_ENABLE=0,
    parameter CLOCK_PERIOD_PS=4000
)(
    input wire clk,
    input wire rst,
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
    input wire enable,
    input wire parent_fault,
    output wire dma_drained,
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
    output wire m_work_handoff,
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
    output wire [31:0] sq_control_last_sequence,
    output wire [587:0] m_cq_context,
    output wire m_cq_valid,
    // Legacy diagnostic ports only: external CQ-ready/commit inputs are NOT
    // release authority. The actual CQC1 publisher now owns these handshakes.
    input wire m_cq_ready,
    input wire [587:0] s_cq_commit_context,
    input wire [7:0] s_cq_commit_error,
    input wire s_cq_commit_valid,
    output wire s_cq_commit_ready,
    output wire [7:0] local_execution_guard,
    output wire [6:0] local_proof_flags,
    output wire [31:0] local_committed_count
);
initial if(MAX_QPS!=8)$fatal(1,"shared native RNIC currently requires eight-bit guards");
initial if(SEND_ENABLE && !RETRY_ENABLE)$fatal(1,"SEND requires native retry/RNR ownership");
initial if(RECV_ENABLE && !SEND_ENABLE)$fatal(1,"RECV requires the matched SEND/retry transport");
initial if(RNR_ENABLE && !RECV_ENABLE)$fatal(1,"wire RNR requires actual RECV ownership");
initial if(RECV_RETIRE_ENABLE && !RNR_ENABLE)$fatal(1,"receive receipts require matched native RNR transport");
initial if(RECV_CQ_ENABLE && !RECV_RETIRE_ENABLE)$fatal(1,"receive CQ requires matched operation receipts");
initial if(SEPARATE_RQ_ENABLE && !REQUEST_CQ_ENABLE)$fatal(1,"independent SQ/RQ needs complete native CQ profile");
initial if(DUPLEX_ENABLE && (!REQUEST_CQ_ENABLE || !SEPARATE_RQ_ENABLE))$fatal(1,"duplex completion needs full independent CQ profile");
initial if(REQUEST_CQ_ENABLE && !RECV_CQ_ENABLE)$fatal(1,"request CQ needs complete matched native HLS/profile");
initial if(RETRY_ENABLE && !QP_TX_ENABLE)$fatal(1,"native replay requires the matched new HLS/state-readback profile");
wire sq_local_memory_busy;
wire physical_memory_drained;
// Do not wait for the OTHER direction's MAC tail to complete this WR. The
// actual physical memory/PCIe/RAM guards remain, and each owner still needs
// its own exact HLS, positive wire, MAC receipt/tail and CQ/retire proofs.
wire completion_memory_drained=DUPLEX_ENABLE ? physical_memory_drained:memory_drained;
wire [247:0] sq_m_hls_sq_tdata;
wire sq_m_hls_sq_tvalid;
wire sq_m_hls_sq_tready;
wire [587:0] sq_m_executor_context;
wire sq_m_executor_context_valid;
wire ex_s_owner_ready;
wire ex_s_read_response_ready;
wire ex_s_hls_read_command_ready;
wire [511:0] ex_m_axis_hls_read_tdata;
wire [63:0] ex_m_axis_hls_read_tkeep;
wire ex_m_axis_hls_read_tlast;
wire ex_m_axis_hls_read_tvalid;
wire ex_m_memory_command_write;
wire [63:0] ex_m_memory_command_offset;
wire [31:0] ex_m_memory_command_length;
wire [31:0] ex_m_memory_command_key;
wire [15:0] ex_m_memory_command_tag;
wire ex_m_memory_command_valid;
wire ex_m_memory_command_ready;
wire [511:0] ex_m_axis_memory_write_tdata;
wire [63:0] ex_m_axis_memory_write_tkeep;
wire ex_m_axis_memory_write_tlast;
wire ex_m_axis_memory_write_tvalid;
wire ex_m_axis_memory_write_tready;
wire [511:0] ex_s_axis_memory_read_tdata;
wire [63:0] ex_s_axis_memory_read_tkeep;
wire ex_s_axis_memory_read_tlast;
wire ex_s_axis_memory_read_tvalid;
wire ex_s_axis_memory_read_tready;
wire [15:0] ex_s_memory_status_tag;
wire [7:0] ex_s_memory_status_error;
wire ex_s_memory_status_valid;
wire ex_s_memory_status_ready;
wire [587:0] ex_m_memory_event_context;
wire [7:0] ex_m_memory_event_error;
wire ex_m_memory_event_valid;
wire [MAX_QPS-1:0] ex_queue_guard;
wire ex_busy;
wire ex_fault;
wire [7:0] ex_fault_code;
wire [31:0] ex_owner_count;
wire [31:0] ex_command_count;
wire [31:0] ex_memory_status_count;
wire tx_s_owner_ready;
wire tx_s_axis_ip_tready;
wire [587:0] tx_m_expect_context;
wire [31:0] tx_m_expect_local_ip;
wire [31:0] tx_m_expect_peer_ip;
wire [23:0] tx_m_expect_psn;
wire tx_m_expect_valid;
wire tx_m_expect_ready;
wire tx_response_admission_ready;
wire tx_s_memory_ready;
wire tx_s_hls_ack_ready;
wire [MAX_QPS-1:0] tx_queue_guard;
wire tx_busy;
wire tx_fault;
wire [7:0] tx_fault_code;
wire [7:0] tx_failed_status;
wire tx_local_tx_drained;
wire tx_tags_exhausted;
wire [TX_TAG_WIDTH-1:0] tx_active_tag;
wire [31:0] tx_frame_count;
wire [31:0] tx_receipt_count;
wire [31:0] tx_mac_proof_count;
wire [587:0] rx_m_read_response_context;
wire rx_m_read_response_valid;
wire [127:0] rx_m_axis_hls_rx_tdata;
wire [15:0] rx_m_axis_hls_rx_tkeep;
wire rx_m_axis_hls_rx_tlast;
wire rx_m_axis_hls_rx_tvalid;
wire rx_m_axis_hls_rx_tready;
wire [587:0] rx_m_response_event_context;
wire [23:0] rx_m_response_event_psn;
wire [7:0] rx_m_response_event_opcode;
wire [7:0] rx_m_response_event_syndrome;
wire rx_m_response_event_valid;
wire [MAX_QPS-1:0] rx_queue_guard;
wire rx_busy;
wire [7:0] rx_m_reject_error;
wire rx_m_reject_valid;
wire rx_fault;
wire [7:0] rx_fault_code;
wire [31:0] rx_accepted_count;
wire [31:0] rx_rejected_count;
wire [31:0] response_integrity_drop_count;
wire [31:0] rx_unowned_drop_count;
wire up_s_context_ready;
wire up_s_command_ready;
wire [95:0] up_m_command;
wire up_m_command_valid;
wire up_s_axis_tready;
wire [511:0] up_m_axis_tdata;
wire [63:0] up_m_axis_tkeep;
wire up_m_axis_tlast;
wire up_m_axis_tvalid;
wire [MAX_QPS-1:0] up_queue_guard;
wire up_busy;
wire up_fault;
wire [7:0] up_fault_code;
wire [31:0] up_context_count;
wire [31:0] up_command_count;
wire [31:0] up_discarded_padding_bytes;
wire h_s_local_owner_ready;
wire [127:0] h_m_local_tx_tdata;
wire [15:0] h_m_local_tx_tkeep;
wire h_m_local_tx_tvalid;
wire h_m_local_tx_tlast;
wire [39:0] h_m_local_ack_tdata;
wire h_m_local_ack_tvalid;
wire [95:0] h_m_local_write_command;
wire h_m_local_write_command_valid;
wire [511:0] h_m_local_write_tdata;
wire [63:0] h_m_local_write_tkeep;
wire h_m_local_write_tvalid;
wire h_m_local_write_tlast;
wire [95:0] h_m_local_read_command;
wire h_m_local_read_command_valid;
wire [7:0] h_local_hls_queue_guard;
wire h_local_hls_active;
wire h_shared_hls_fault;
wire [7:0] h_shared_hls_fault_code;
wire ex_m_axis_hls_read_tready;
wire [127:0] native_tx_tdata;
wire [15:0] native_tx_tkeep;
wire native_tx_tvalid;
wire native_tx_tready;
wire native_tx_tlast;
wire [TX_TAG_WIDTH:0] native_tx_tuser;
wire [TX_TAG_WIDTH-1:0] native_cpl_tag;
wire [TS_WIDTH-1:0] native_cpl_ts;
wire native_cpl_valid;
wire native_cpl_ready;
wire [127:0] native_rx_tdata;
wire [15:0] native_rx_tkeep;
wire native_rx_tvalid;
wire native_rx_tready;
wire native_rx_tlast;
wire [RX_USER_WIDTH-1:0] native_rx_tuser;
wire native_fault;
wire [7:0] native_fault_code;
wire [127:0] response_tdata;
wire [15:0] response_tkeep;
wire response_tvalid;
wire response_tready;
wire response_tlast;
wire response_tuser;
wire response_guard_ready;
wire response_router_quiescent;
wire owner_take;
wire owner_ready;
wire read_token_ready;
wire read_token_take;
wire pipeline_fault;
wire [11:0] cq_awaddr;
wire [2:0] cq_awprot;
wire cq_awvalid;
wire cq_awready;
wire [31:0] cq_wdata;
wire [3:0] cq_wstrb;
wire cq_wvalid;
wire cq_wready;
wire [1:0] cq_bresp;
wire cq_bvalid;
wire cq_bready;
wire [11:0] cq_araddr;
wire [2:0] cq_arprot;
wire cq_arvalid;
wire cq_arready;
wire [31:0] cq_rdata;
wire [1:0] cq_rresp;
wire cq_rvalid;
wire cq_rready;
wire cq_ticket_ready,cq_commit_valid,cq_retire_valid,cq_retire_ready,cq_fault,cq_busy;
wire [587:0] cq_commit_context,cq_retire_context;
wire [7:0] cq_commit_error,cq_fault_code,cq_queue_guard;
wire [63:0] cq_owner_cookie,cq_owner_epoch;
wire [15:0] cq_owner_pd;
wire cq_owner_valid;
wire [11:0] rrp_awaddr;
wire [2:0] rrp_awprot;
wire rrp_awvalid;
wire rrp_awready;
wire [31:0] rrp_wdata;
wire [3:0] rrp_wstrb;
wire rrp_wvalid;
wire rrp_wready;
wire [1:0] rrp_bresp;
wire rrp_bvalid;
wire rrp_bready;
wire [11:0] rrp_araddr;
wire [2:0] rrp_arprot;
wire rrp_arvalid;
wire rrp_arready;
wire [31:0] rrp_rdata;
wire [1:0] rrp_rresp;
wire rrp_rvalid;
wire rrp_rready;
wire [23:0] rrp_cfg_qpn;
wire [15:0] rrp_cfg_pd;
wire [63:0] rrp_cfg_cookie;
wire [63:0] rrp_cfg_epoch;
wire [4:0] rrp_cfg_timeout;
wire [2:0] rrp_cfg_retry;
wire [2:0] rrp_cfg_rnr_retry;
wire rrp_cfg_valid;
wire rrp_cfg_ready;
wire [23:0] rrp_rsp_qpn;
wire [15:0] rrp_rsp_pd;
wire [63:0] rrp_rsp_cookie;
wire [63:0] rrp_rsp_epoch;
wire [4:0] rrp_rsp_timeout;
wire [2:0] rrp_rsp_retry;
wire [2:0] rrp_rsp_rnr_retry;
wire [7:0] rrp_rsp_error;
wire rrp_rsp_valid;
wire rrp_rsp_ready;
wire [23:0] rrp_query_qpn;
wire [63:0] rrp_query_cookie,rrp_query_epoch;
wire [15:0] rrp_query_pd;
wire rrp_query_valid,rrp_fault,rrp_busy;
wire [7:0] rrp_queue_guard;
wire [587:0] rx_control_context;
wire [23:0] rx_control_psn;
wire [7:0] rx_control_syndrome;
wire rx_control_valid,rx_control_ready;
wire [31:0] native_retry_count,native_rnr_count;
wire [587:0] rq_post_context,rq_head_context,rq_placement_context;
wire rq_post_valid,rq_post_ready,rq_head_valid,rq_head_ready,rq_placement_valid,rq_placement_ready;
wire [23:0] rq_query_qpn;
wire [31:0] rq_placement_length,rq_posted_count,rq_taken_count,rq_placement_count,rq_received_bytes;
wire [7:0] rq_queue_guard,rq_fault_code;
wire rq_active,rq_fault;
wire rq_cancel_block,rq_cancel_valid,rq_cancel_ready;
wire [23:0] rq_cancel_qpn;wire [15:0] rq_cancel_pd;wire [63:0] rq_cancel_epoch;
wire [31:0] rq_cancelled_count;
wire [23:0] rq_placement_psn,rq_core_msn;
wire [679:0] rq_core_data;
wire rq_core_valid,rq_core_ready,rq_core_proved;
wire [31:0] rq_core_proof_count;
wire [655:0] h_request_done_data;
wire h_request_done_valid,h_request_done_ready;
wire [587:0] rq_held_context,rq_ticket_context,local_cq_context;
wire [679:0] rq_held_core_data;
wire [31:0] rq_ticket_received_bytes;
wire rq_ticket_valid,rq_ticket_ready,rq_commit_ready,rq_retire_ready;
wire local_cq_valid,local_cq_ready,local_commit_ready,local_retire_ready;
wire recv_hls_retire_ready,recv_hls_retire_valid,recv_ack_retire_ready,recv_ack_retire_valid;
wire recv_ack_owner_ready,recv_ack_fault,recv_ack_busy,recv_mac_valid,recv_mac_ready;
wire [7:0] recv_ack_fault_code,recv_ack_queue_guard;
wire [695:0] recv_mac_data;
wire [127:0] guarded_native_tdata;
wire [15:0] guarded_native_tkeep;
wire guarded_native_tvalid,guarded_native_tready,guarded_native_tlast;
wire [TX_TAG_WIDTH:0] guarded_native_tuser;
wire [TX_TAG_WIDTH-1:0] guarded_cpl_tag;
wire [TS_WIDTH-1:0] guarded_cpl_ts;
wire guarded_cpl_valid,guarded_cpl_ready;
wire receive_commit=RECV_CQ_ENABLE && cq_commit_context[339:324]==4;
wire receive_retire=RECV_CQ_ENABLE && cq_retire_context[339:324]==4;
assign m_cq_context=rq_ticket_valid ? rq_ticket_context : local_cq_context;
assign m_cq_valid=rq_ticket_valid || local_cq_valid;
assign rq_ticket_ready=cq_ticket_ready;
assign local_cq_ready=cq_ticket_ready && !rq_ticket_valid;
assign s_cq_commit_ready=receive_commit ? rq_commit_ready : local_commit_ready;
assign cq_retire_ready=receive_retire ? rq_retire_ready && recv_ack_retire_ready && recv_hls_retire_ready : local_retire_ready;
assign recv_ack_retire_valid=cq_retire_valid && receive_retire && rq_retire_ready && recv_hls_retire_ready;
assign recv_hls_retire_valid=cq_retire_valid && receive_retire && rq_retire_ready && recv_ack_retire_ready;

wire up_m_command_ready;
wire up_m_axis_tready;
wire rx_m_response_event_ready;
// Full owner is captured atomically by ALL three real consumers. Their
// offered/held queue guards cover this SAME edge before HLS SQ can be sent.
assign owner_ready=h_s_local_owner_ready && ex_s_owner_ready && tx_s_owner_ready && !pipeline_fault;
assign owner_take=sq_m_executor_context_valid && owner_ready;
// READ placement and pad removal receive exactly the same protected token.
assign read_token_ready=ex_s_read_response_ready && up_s_context_ready;
assign read_token_take=rx_m_read_response_valid && read_token_ready;
assign response_tready=response_guard_ready && tx_response_admission_ready;
assign pipeline_fault=ex_fault || tx_fault || rx_fault || up_fault || h_shared_hls_fault || cq_fault || rrp_fault || rq_fault || recv_ack_fault;
assign fault=native_fault || pipeline_fault;
assign fault_code=native_fault ? native_fault_code : ex_fault ? ex_fault_code :
    rx_fault ? rx_fault_code : up_fault ? up_fault_code : tx_fault ? tx_fault_code :
    h_shared_hls_fault ? h_shared_hls_fault_code : rrp_fault ? 8'hd8 : rq_fault ? rq_fault_code : recv_ack_fault ? recv_ack_fault_code : cq_fault_code;
assign local_execution_guard=ex_queue_guard | tx_queue_guard | rx_queue_guard | up_queue_guard | h_local_hls_queue_guard | cq_queue_guard | rrp_queue_guard | rq_queue_guard | recv_ack_queue_guard;
// Native response steering is active only while a local role is retained.
// Ordinary Ethernet and incoming requests preserve every native sideband.
rocev2_responder_ethernet_rx #(.USER_WIDTH(RX_USER_WIDTH),.RESPONSE_MODE(1)) response_router (
    .clk(clk),.rst(rst),.enable(ethernet_enabled && h_local_hls_active),.run_id(ethernet_epoch),
    .local_mac(active_local_mac),.peer_mac(active_peer_mac),.local_ip(active_local_ip),
    .s_axis_tdata(s_axis_mac_rx_tdata),.s_axis_tkeep(s_axis_mac_rx_tkeep),
    .s_axis_tvalid(s_axis_mac_rx_tvalid),.s_axis_tready(s_axis_mac_rx_tready),
    .s_axis_tlast(s_axis_mac_rx_tlast),.s_axis_tuser(s_axis_mac_rx_tuser),
    .m_axis_host_tdata(native_rx_tdata),.m_axis_host_tkeep(native_rx_tkeep),
    .m_axis_host_tvalid(native_rx_tvalid),.m_axis_host_tready(native_rx_tready),
    .m_axis_host_tlast(native_rx_tlast),.m_axis_host_tuser(native_rx_tuser),
    .m_axis_roce_tdata(response_tdata),.m_axis_roce_tkeep(response_tkeep),
    .m_axis_roce_tvalid(response_tvalid),.m_axis_roce_tready(response_tready),
    .m_axis_roce_tlast(response_tlast),.m_axis_roce_tuser(response_tuser),
    .quiescent(response_router_quiescent),.host_frame_count(),.roce_frame_count(),
    .drop_frame_count(),.overflow_count(),.stale_frame_count()
);
rocev2_native_sq_endpoint #( .DUPLEX_ENABLE(DUPLEX_ENABLE),.TX_TAG_WIDTH(TX_TAG_WIDTH),.TS_WIDTH(TS_WIDTH),.RX_USER_WIDTH(RX_USER_WIDTH),
    .RAM_SIZE(RAM_SIZE),.RAM_ADDR_WIDTH(RAM_ADDR_WIDTH),.SEG_COUNT(SEG_COUNT),
    .SEG_DATA_WIDTH(SEG_DATA_WIDTH),.SEG_BE_WIDTH(SEG_BE_WIDTH),.SEG_ADDR_WIDTH(SEG_ADDR_WIDTH),
    .RAM_SEL_WIDTH(RAM_SEL_WIDTH),.DMA_LEN_WIDTH(DMA_LEN_WIDTH),.DMA_TAG_WIDTH(DMA_TAG_WIDTH),
    .MAX_QPS(MAX_QPS),.LOCAL_MEMORY_ENABLE(1),.HLS_SQ_ENABLE(1),.SHARED_HLS_ENABLE(1),.CQ_MMIO_ENABLE(1),.QP_TX_ENABLE(QP_TX_ENABLE),.RETRY_MMIO_ENABLE(RETRY_ENABLE),.EXTERNAL_REPLAY_ENABLE(RETRY_ENABLE),.SEND_ENABLE(SEND_ENABLE),.RECV_ENABLE(RECV_ENABLE),.RNR_ENABLE(RNR_ENABLE),.RECV_RETIRE_ENABLE(RECV_RETIRE_ENABLE),.RECV_CQ_ENABLE(RECV_CQ_ENABLE),.REQUEST_CQ_ENABLE(REQUEST_CQ_ENABLE),.SEPARATE_RQ_ENABLE(SEPARATE_RQ_ENABLE),.RECV_CANCEL_ENABLE(RECV_CANCEL_ENABLE)) native (
    .m_recv_cancel_block(rq_cancel_block),.m_recv_cancel_valid(rq_cancel_valid),.m_recv_cancel_qpn(rq_cancel_qpn),
    .m_recv_cancel_pd(rq_cancel_pd),.m_recv_cancel_epoch(rq_cancel_epoch),.s_recv_cancel_ready(rq_cancel_ready),
    .s_recv_context(rq_head_context),.s_recv_valid(rq_head_valid),.s_recv_ready(rq_head_ready),
    .m_recv_query_qpn(rq_query_qpn),.m_recv_placement_context(rq_placement_context),
    .m_recv_placement_length(rq_placement_length),.m_recv_placement_valid(rq_placement_valid),
    .m_recv_placement_ready(rq_placement_ready),.recv_owned_guard(rq_active),
    .m_recv_placement_psn(rq_placement_psn),.m_recv_core_data(rq_core_data),.m_recv_core_valid(rq_core_valid),.m_recv_core_ready(rq_core_ready),
    .m_request_done_data(h_request_done_data),.m_request_done_valid(h_request_done_valid),.m_request_done_ready(h_request_done_ready),
    .recv_ack_admission_ready(recv_ack_owner_ready),
    .s_recv_retire_context(cq_retire_context),.s_recv_retire_valid(recv_hls_retire_valid),.s_recv_retire_ready(recv_hls_retire_ready),
    .m_recv_post_context(rq_post_context),.m_recv_post_valid(rq_post_valid),.m_recv_post_ready(rq_post_ready),
    .recv_queue_guard(rq_queue_guard),
    .m_axil_retry_awaddr(rrp_awaddr),
    .m_axil_retry_awprot(rrp_awprot),
    .m_axil_retry_awvalid(rrp_awvalid),
    .m_axil_retry_awready(rrp_awready),
    .m_axil_retry_wdata(rrp_wdata),
    .m_axil_retry_wstrb(rrp_wstrb),
    .m_axil_retry_wvalid(rrp_wvalid),
    .m_axil_retry_wready(rrp_wready),
    .m_axil_retry_bresp(rrp_bresp),
    .m_axil_retry_bvalid(rrp_bvalid),
    .m_axil_retry_bready(rrp_bready),
    .m_axil_retry_araddr(rrp_araddr),
    .m_axil_retry_arprot(rrp_arprot),
    .m_axil_retry_arvalid(rrp_arvalid),
    .m_axil_retry_arready(rrp_arready),
    .m_axil_retry_rdata(rrp_rdata),
    .m_axil_retry_rresp(rrp_rresp),
    .m_axil_retry_rvalid(rrp_rvalid),
    .m_axil_retry_rready(rrp_rready),
    .retry_query_qpn(rrp_query_qpn),.retry_query_cookie(rrp_query_cookie),.retry_query_epoch(rrp_query_epoch),
    .retry_query_pd(rrp_query_pd),.retry_query_valid(rrp_query_valid),
    .m_axil_cq_awaddr(cq_awaddr),
    .m_axil_cq_awprot(cq_awprot),
    .m_axil_cq_awvalid(cq_awvalid),
    .m_axil_cq_awready(cq_awready),
    .m_axil_cq_wdata(cq_wdata),
    .m_axil_cq_wstrb(cq_wstrb),
    .m_axil_cq_wvalid(cq_wvalid),
    .m_axil_cq_wready(cq_wready),
    .m_axil_cq_bresp(cq_bresp),
    .m_axil_cq_bvalid(cq_bvalid),
    .m_axil_cq_bready(cq_bready),
    .m_axil_cq_araddr(cq_araddr),
    .m_axil_cq_arprot(cq_arprot),
    .m_axil_cq_arvalid(cq_arvalid),
    .m_axil_cq_arready(cq_arready),
    .m_axil_cq_rdata(cq_rdata),
    .m_axil_cq_rresp(cq_rresp),
    .m_axil_cq_rvalid(cq_rvalid),
    .m_axil_cq_rready(cq_rready),
    .owner_query_qpn(m_cq_context[395:372]),.owner_query_opcode(m_cq_context[339:324]),.owner_query_cookie(cq_owner_cookie),
    .owner_query_epoch(cq_owner_epoch),.owner_query_pd(cq_owner_pd),.owner_query_valid(cq_owner_valid),
    .clk(clk),
    .rst(rst),
    .s_local_owner_context(sq_m_executor_context),
    .s_local_owner_valid(owner_take),
    .s_local_owner_ready(h_s_local_owner_ready),
    .s_local_sq_tdata(sq_m_hls_sq_tdata),
    .s_local_sq_tvalid(sq_m_hls_sq_tvalid),
    .s_local_sq_tready(sq_m_hls_sq_tready),
    .s_local_rx_tdata(rx_m_axis_hls_rx_tdata),
    .s_local_rx_tkeep(rx_m_axis_hls_rx_tkeep),
    .s_local_rx_tvalid(rx_m_axis_hls_rx_tvalid),
    .s_local_rx_tready(rx_m_axis_hls_rx_tready),
    .s_local_rx_tlast(rx_m_axis_hls_rx_tlast),
    .s_local_rx_tuser(1'b0),
    .m_local_tx_tdata(h_m_local_tx_tdata),
    .m_local_tx_tkeep(h_m_local_tx_tkeep),
    .m_local_tx_tvalid(h_m_local_tx_tvalid),
    .m_local_tx_tready(tx_s_axis_ip_tready),
    .m_local_tx_tlast(h_m_local_tx_tlast),
    .m_local_ack_tdata(h_m_local_ack_tdata),
    .m_local_ack_tvalid(h_m_local_ack_tvalid),
    .m_local_ack_tready(tx_s_hls_ack_ready),
    .m_local_write_command(h_m_local_write_command),
    .m_local_write_command_valid(h_m_local_write_command_valid),
    .m_local_write_command_ready(up_s_command_ready),
    .m_local_write_tdata(h_m_local_write_tdata),
    .m_local_write_tkeep(h_m_local_write_tkeep),
    .m_local_write_tvalid(h_m_local_write_tvalid),
    .m_local_write_tready(up_s_axis_tready),
    .m_local_write_tlast(h_m_local_write_tlast),
    .m_local_read_command(h_m_local_read_command),
    .m_local_read_command_valid(h_m_local_read_command_valid),
    .m_local_read_command_ready(ex_s_hls_read_command_ready),
    .s_local_read_tdata(ex_m_axis_hls_read_tdata),
    .s_local_read_tkeep(ex_m_axis_hls_read_tkeep),
    .s_local_read_tvalid(ex_m_axis_hls_read_tvalid),
    .s_local_read_tready(ex_m_axis_hls_read_tready),
    .s_local_read_tlast(ex_m_axis_hls_read_tlast),
    .s_local_retire_context(cq_retire_context),
    .s_local_retire_valid(cq_retire_valid && !receive_retire),
    .s_local_retire_ready(local_retire_ready),
    .local_core_drained(1'b0),
    .local_hls_queue_guard(h_local_hls_queue_guard),
    .local_hls_active(h_local_hls_active),
    .shared_hls_fault(h_shared_hls_fault),
    .shared_hls_fault_code(h_shared_hls_fault_code),
    .local_hls_local_ip(local_hls_local_ip),
    .local_hls_peer_ip(local_hls_peer_ip),
    .local_hls_peer_qpn(local_hls_peer_qpn),
    .s_axis_host_tx_tdata(s_axis_host_tx_tdata),
    .s_axis_host_tx_tkeep(s_axis_host_tx_tkeep),
    .s_axis_host_tx_tvalid(s_axis_host_tx_tvalid),
    .s_axis_host_tx_tready(s_axis_host_tx_tready),
    .s_axis_host_tx_tlast(s_axis_host_tx_tlast),
    .s_axis_host_tx_tuser(s_axis_host_tx_tuser),
    .m_axis_mac_tx_tdata(native_tx_tdata),
    .m_axis_mac_tx_tkeep(native_tx_tkeep),
    .m_axis_mac_tx_tvalid(native_tx_tvalid),
    .m_axis_mac_tx_tready(native_tx_tready),
    .m_axis_mac_tx_tlast(native_tx_tlast),
    .m_axis_mac_tx_tuser(native_tx_tuser),
    .s_axis_mac_cpl_tag(native_cpl_tag),
    .s_axis_mac_cpl_ts(native_cpl_ts),
    .s_axis_mac_cpl_valid(native_cpl_valid),
    .s_axis_mac_cpl_ready(native_cpl_ready),
    .m_axis_host_cpl_tag(m_axis_host_cpl_tag),
    .m_axis_host_cpl_ts(m_axis_host_cpl_ts),
    .m_axis_host_cpl_valid(m_axis_host_cpl_valid),
    .m_axis_host_cpl_ready(m_axis_host_cpl_ready),
    .s_axis_mac_rx_tdata(native_rx_tdata),
    .s_axis_mac_rx_tkeep(native_rx_tkeep),
    .s_axis_mac_rx_tvalid(native_rx_tvalid),
    .s_axis_mac_rx_tready(native_rx_tready),
    .s_axis_mac_rx_tlast(native_rx_tlast),
    .s_axis_mac_rx_tuser(native_rx_tuser),
    .m_axis_host_rx_tdata(m_axis_host_rx_tdata),
    .m_axis_host_rx_tkeep(m_axis_host_rx_tkeep),
    .m_axis_host_rx_tvalid(m_axis_host_rx_tvalid),
    .m_axis_host_rx_tready(m_axis_host_rx_tready),
    .m_axis_host_rx_tlast(m_axis_host_rx_tlast),
    .m_axis_host_rx_tuser(m_axis_host_rx_tuser),
    .qp_ready(qp_ready),
    .m_reject_error(m_reject_error),
    .m_reject_qpn(m_reject_qpn),
    .m_reject_psn(m_reject_psn),
    .m_reject_valid(m_reject_valid),
    .m_reject_ready(m_reject_ready),
    .quiescent(quiescent),
    .fault(native_fault),
    .fault_code(native_fault_code),
    .accepted_count(accepted_count),
    .rejected_count(rejected_count),
    .completed_count(completed_count),
    .tx_deferred_cycles(tx_deferred_cycles),
    .rx_integrity_good_count(rx_integrity_good_count),
    .rx_integrity_drop_count(rx_integrity_drop_count),
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
    .memory_drained(memory_drained),
    .physical_memory_drained(physical_memory_drained),
    .dma_command_count(dma_command_count),
    .dma_fence_count(dma_fence_count),
    .dma_completion_count(dma_completion_count),
    .parent_dma_drained(parent_dma_drained),
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
    .s_axil_awaddr(s_axil_awaddr),
    .s_axil_awprot(s_axil_awprot),
    .s_axil_awvalid(s_axil_awvalid),
    .s_axil_awready(s_axil_awready),
    .s_axil_wdata(s_axil_wdata),
    .s_axil_wstrb(s_axil_wstrb),
    .s_axil_wvalid(s_axil_wvalid),
    .s_axil_wready(s_axil_wready),
    .s_axil_bresp(s_axil_bresp),
    .s_axil_bvalid(s_axil_bvalid),
    .s_axil_bready(s_axil_bready),
    .s_axil_araddr(s_axil_araddr),
    .s_axil_arprot(s_axil_arprot),
    .s_axil_arvalid(s_axil_arvalid),
    .s_axil_arready(s_axil_arready),
    .s_axil_rdata(s_axil_rdata),
    .s_axil_rresp(s_axil_rresp),
    .s_axil_rvalid(s_axil_rvalid),
    .s_axil_rready(s_axil_rready),
    .ethernet_config_error(ethernet_config_error),
    .ethernet_committed(ethernet_committed),
    .ethernet_enabled(ethernet_enabled),
    .ethernet_epoch(ethernet_epoch),
    .active_local_mac(active_local_mac),
    .active_peer_mac(active_peer_mac),
    .active_local_ip(active_local_ip),
    .s_local_memory_command_write(ex_m_memory_command_write),
    .s_local_memory_command_offset(ex_m_memory_command_offset),
    .s_local_memory_command_length(ex_m_memory_command_length),
    .s_local_memory_command_key(ex_m_memory_command_key),
    .s_local_memory_command_tag(ex_m_memory_command_tag),
    .s_local_memory_command_valid(ex_m_memory_command_valid),
    .s_local_memory_command_ready(ex_m_memory_command_ready),
    .s_axis_local_memory_write_tdata(ex_m_axis_memory_write_tdata),
    .s_axis_local_memory_write_tkeep(ex_m_axis_memory_write_tkeep),
    .s_axis_local_memory_write_tlast(ex_m_axis_memory_write_tlast),
    .s_axis_local_memory_write_tvalid(ex_m_axis_memory_write_tvalid),
    .s_axis_local_memory_write_tready(ex_m_axis_memory_write_tready),
    .m_axis_local_memory_read_tdata(ex_s_axis_memory_read_tdata),
    .m_axis_local_memory_read_tkeep(ex_s_axis_memory_read_tkeep),
    .m_axis_local_memory_read_tlast(ex_s_axis_memory_read_tlast),
    .m_axis_local_memory_read_tvalid(ex_s_axis_memory_read_tvalid),
    .m_axis_local_memory_read_tready(ex_s_axis_memory_read_tready),
    .m_local_memory_status_tag(ex_s_memory_status_tag),
    .m_local_memory_status_error(ex_s_memory_status_error),
    .m_local_memory_status_valid(ex_s_memory_status_valid),
    .m_local_memory_status_ready(ex_s_memory_status_ready),
    .local_memory_busy(sq_local_memory_busy),
    .enable(enable),
    .parent_fault(parent_fault || pipeline_fault),
    .dma_drained(dma_drained),
    .executor_queue_guard(ex_queue_guard | up_queue_guard | h_local_hls_queue_guard | rq_queue_guard),
    .send_execution_queue_guard(ex_queue_guard | up_queue_guard | h_local_hls_queue_guard),
    .wire_queue_guard(rx_queue_guard | {8{!response_router_quiescent}}),
    .completion_queue_guard(tx_queue_guard | cq_queue_guard | rrp_queue_guard | rq_queue_guard),
    .admission_queue_guard(admission_queue_guard),
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
    .m_work_ready(1'b0),
    .m_work_handoff(m_work_handoff),
    .m_hls_sq_tdata(sq_m_hls_sq_tdata),
    .m_hls_sq_tvalid(sq_m_hls_sq_tvalid),
    .m_hls_sq_tready(sq_m_hls_sq_tready),
    .m_executor_context(sq_m_executor_context),
    .m_executor_context_valid(sq_m_executor_context_valid),
    .m_executor_context_ready(owner_ready),
    .sq_submission_guard(sq_submission_guard),
    .sq_submission_busy(sq_submission_busy),
    .sq_submission_fault(sq_submission_fault),
    .sq_submission_fault_code(sq_submission_fault_code),
    .sq_submission_owner_count(sq_submission_owner_count),
    .sq_submission_hls_count(sq_submission_hls_count),
    .sq_queue_guard(sq_queue_guard),
    .sq_queue_active(sq_queue_active),
    .sq_queue_halted(sq_queue_halted),
    .sq_busy(sq_busy),
    .sq_tag_exhausted(sq_tag_exhausted),
    .sq_fault(sq_fault),
    .sq_fault_code(sq_fault_code),
    .sq_fetch_count(sq_fetch_count),
    .sq_result_count(sq_result_count),
    .sq_dma_drained(sq_dma_drained),
    .sq_backend_command_count(sq_backend_command_count),
    .sq_backend_fence_count(sq_backend_fence_count),
    .sq_backend_completion_count(sq_backend_completion_count),
    .router_client_busy(router_client_busy),
    .router_fault(router_fault),
    .router_fault_code(router_fault_code),
    .router_tag_exhausted(router_tag_exhausted),
    .router_descriptor_count(router_descriptor_count),
    .router_completion_count(router_completion_count),
    .sq_queue_pending(sq_queue_pending),
    .sq_control_busy(sq_control_busy),
    .sq_control_response_valid(sq_control_response_valid),
    .sq_control_fatal(sq_control_fatal),
    .sq_control_mmio_error(sq_control_mmio_error),
    .sq_control_owner_active(sq_control_owner_active),
    .sq_control_owner_tainted(sq_control_owner_tainted),
    .sq_control_last_sequence(sq_control_last_sequence)
);
generate if(RECV_ENABLE)begin : receive_owners
rocev2_receive_queue #(.MAX_QPS(MAX_QPS),.RECV_RETIRE_ENABLE(RECV_RETIRE_ENABLE),.RECV_CQ_ENABLE(RECV_CQ_ENABLE),.RECV_CANCEL_ENABLE(RECV_CANCEL_ENABLE)) owners(
    .cancel_block(rq_cancel_block),.cancel_valid(rq_cancel_valid),.cancel_safe(rq_cancel_valid),
    .cancel_qpn(rq_cancel_qpn),.cancel_pd(rq_cancel_pd),.cancel_epoch(rq_cancel_epoch),
    .cancel_ready(rq_cancel_ready),.cancelled_count(rq_cancelled_count),
    .clk(clk),.rst(rst),.parent_fault(parent_fault || ex_fault || tx_fault || rx_fault || up_fault || h_shared_hls_fault || cq_fault || rrp_fault || recv_ack_fault),
    .s_post_context(rq_post_context),.s_post_valid(rq_post_valid),.s_post_ready(rq_post_ready),
    .query_qpn(rq_query_qpn),.m_head_context(rq_head_context),.m_head_valid(rq_head_valid),.m_head_ready(rq_head_ready),
    .s_placement_context(rq_placement_context),.s_placement_length(rq_placement_length),
    .s_placement_valid(rq_placement_valid),.s_placement_ready(rq_placement_ready),
    .s_placement_psn(rq_placement_psn),.s_core_data(rq_core_data),.s_core_valid(rq_core_valid),.s_core_ready(rq_core_ready),
    .core_proved(rq_core_proved),.core_proof_count(rq_core_proof_count),.core_msn(rq_core_msn),
    .held_context(rq_held_context),.held_core_data(rq_held_core_data),
    .s_mac_data(recv_mac_data),.s_mac_valid(recv_mac_valid),.s_mac_ready(recv_mac_ready),.memory_drained(completion_memory_drained),
    .m_ticket_context(rq_ticket_context),.m_ticket_received_bytes(rq_ticket_received_bytes),.m_ticket_valid(rq_ticket_valid),.m_ticket_ready(rq_ticket_ready),
    .s_commit_context(cq_commit_context),.s_commit_valid(cq_commit_valid && receive_commit),.s_commit_ready(rq_commit_ready),
    .s_retire_context(cq_retire_context),.s_retire_valid(cq_retire_valid && receive_retire && recv_ack_retire_ready && recv_hls_retire_ready),.s_retire_ready(rq_retire_ready),
    .queue_guard(rq_queue_guard),.active(rq_active),.fault(rq_fault),.fault_code(rq_fault_code),
    .posted_count(rq_posted_count),.taken_count(rq_taken_count),.placement_count(rq_placement_count),.received_bytes(rq_received_bytes));
end else begin : no_receive_owners
assign rq_post_ready=0;assign rq_head_context=0;assign rq_head_valid=0;assign rq_placement_ready=0;
assign rq_queue_guard=0;assign rq_active=0;assign rq_fault=0;assign rq_fault_code=0;
assign rq_posted_count=0;assign rq_taken_count=0;assign rq_placement_count=0;assign rq_received_bytes=0;
assign rq_core_ready=0;assign rq_core_proved=0;assign rq_core_proof_count=0;assign rq_core_msn=0;
assign rq_held_context=0;assign rq_held_core_data=0;assign recv_mac_ready=0;
assign rq_ticket_context=0;assign rq_ticket_received_bytes=0;assign rq_ticket_valid=0;assign rq_commit_ready=0;assign rq_retire_ready=0;
assign rq_cancel_ready=0;assign rq_cancelled_count=0;
end endgenerate
generate if(RECV_CQ_ENABLE)begin : receive_ack_lifetime
initial if(TX_TAG_WIDTH!=16 || TS_WIDTH!=96)$fatal(1,"receive ACK sideband geometry");
rocev2_receive_ack_tx ack_owner(
    .clk(clk),.rst(rst),.parent_fault(parent_fault || native_fault || ex_fault || tx_fault || rx_fault || up_fault || h_shared_hls_fault || cq_fault || rrp_fault || rq_fault),
    .prior_response_drained(response_tx_quiescent),
    .s_owner_context(rq_head_context),.s_owner_valid(rq_head_valid && rq_head_ready),.s_owner_ready(recv_ack_owner_ready),
    .local_mac(active_local_mac),.peer_mac(active_peer_mac),.local_ip(local_hls_local_ip),.peer_ip(local_hls_peer_ip),.peer_qpn(local_hls_peer_qpn),
    .s_core_data(rq_held_core_data),.s_core_valid(rq_core_proved),
    .s_axis_tdata(native_tx_tdata),.s_axis_tkeep(native_tx_tkeep),.s_axis_tvalid(native_tx_tvalid),.s_axis_tready(native_tx_tready),.s_axis_tlast(native_tx_tlast),.s_axis_tuser(native_tx_tuser),
    .m_axis_tdata(guarded_native_tdata),.m_axis_tkeep(guarded_native_tkeep),.m_axis_tvalid(guarded_native_tvalid),.m_axis_tready(guarded_native_tready),.m_axis_tlast(guarded_native_tlast),.m_axis_tuser(guarded_native_tuser),
    .s_cpl_tag(guarded_cpl_tag),.s_cpl_ts(guarded_cpl_ts),.s_cpl_valid(guarded_cpl_valid),.s_cpl_ready(guarded_cpl_ready),
    .m_cpl_tag(native_cpl_tag),.m_cpl_ts(native_cpl_ts),.m_cpl_valid(native_cpl_valid),.m_cpl_ready(native_cpl_ready),
    .m_done_data(recv_mac_data),.m_done_valid(recv_mac_valid),.m_done_ready(recv_mac_ready),
    .s_retire_context(cq_retire_context),.s_retire_valid(recv_ack_retire_valid),.s_retire_ready(recv_ack_retire_ready),
    .queue_guard(recv_ack_queue_guard),.busy(recv_ack_busy),.fault(recv_ack_fault),.fault_code(recv_ack_fault_code),
    .active_tag(),.tags_exhausted(),.frame_count(),.receipt_count());
end else begin : no_receive_ack_lifetime
assign recv_ack_owner_ready=1;assign recv_ack_fault=0;assign recv_ack_fault_code=0;assign recv_ack_busy=0;assign recv_ack_queue_guard=0;
assign recv_mac_data=0;assign recv_mac_valid=0;assign recv_ack_retire_ready=0;
assign guarded_native_tdata=native_tx_tdata;assign guarded_native_tkeep=native_tx_tkeep;assign guarded_native_tvalid=native_tx_tvalid;
assign native_tx_tready=guarded_native_tready;assign guarded_native_tlast=native_tx_tlast;assign guarded_native_tuser=native_tx_tuser;
assign native_cpl_tag=guarded_cpl_tag;assign native_cpl_ts=guarded_cpl_ts;assign native_cpl_valid=guarded_cpl_valid;assign guarded_cpl_ready=native_cpl_ready;
end endgenerate
rocev2_wqe_memory_executor #(.MAX_QPS(MAX_QPS)) executor (
    .clk(clk),
    .rst(rst),
    .enable(1'b1),
    .halt(pipeline_fault || parent_fault),
    .s_owner_context(sq_m_executor_context),
    .s_owner_valid(owner_take),
    .s_owner_ready(ex_s_owner_ready),
    .s_read_response_context(rx_m_read_response_context),
    .s_read_response_valid(read_token_take),
    .s_read_response_ready(ex_s_read_response_ready),
    .s_hls_read_command(h_m_local_read_command),
    .s_hls_read_command_valid(h_m_local_read_command_valid),
    .s_hls_read_command_ready(ex_s_hls_read_command_ready),
    .s_hls_write_command(up_m_command),
    .s_hls_write_command_valid(up_m_command_valid),
    .s_hls_write_command_ready(up_m_command_ready),
    .s_axis_hls_write_tdata(up_m_axis_tdata),
    .s_axis_hls_write_tkeep(up_m_axis_tkeep),
    .s_axis_hls_write_tlast(up_m_axis_tlast),
    .s_axis_hls_write_tvalid(up_m_axis_tvalid),
    .s_axis_hls_write_tready(up_m_axis_tready),
    .m_axis_hls_read_tdata(ex_m_axis_hls_read_tdata),
    .m_axis_hls_read_tkeep(ex_m_axis_hls_read_tkeep),
    .m_axis_hls_read_tlast(ex_m_axis_hls_read_tlast),
    .m_axis_hls_read_tvalid(ex_m_axis_hls_read_tvalid),
    .m_axis_hls_read_tready(ex_m_axis_hls_read_tready),
    .m_memory_command_write(ex_m_memory_command_write),
    .m_memory_command_offset(ex_m_memory_command_offset),
    .m_memory_command_length(ex_m_memory_command_length),
    .m_memory_command_key(ex_m_memory_command_key),
    .m_memory_command_tag(ex_m_memory_command_tag),
    .m_memory_command_valid(ex_m_memory_command_valid),
    .m_memory_command_ready(ex_m_memory_command_ready),
    .m_axis_memory_write_tdata(ex_m_axis_memory_write_tdata),
    .m_axis_memory_write_tkeep(ex_m_axis_memory_write_tkeep),
    .m_axis_memory_write_tlast(ex_m_axis_memory_write_tlast),
    .m_axis_memory_write_tvalid(ex_m_axis_memory_write_tvalid),
    .m_axis_memory_write_tready(ex_m_axis_memory_write_tready),
    .s_axis_memory_read_tdata(ex_s_axis_memory_read_tdata),
    .s_axis_memory_read_tkeep(ex_s_axis_memory_read_tkeep),
    .s_axis_memory_read_tlast(ex_s_axis_memory_read_tlast),
    .s_axis_memory_read_tvalid(ex_s_axis_memory_read_tvalid),
    .s_axis_memory_read_tready(ex_s_axis_memory_read_tready),
    .s_memory_status_tag(ex_s_memory_status_tag),
    .s_memory_status_error(ex_s_memory_status_error),
    .s_memory_status_valid(ex_s_memory_status_valid),
    .s_memory_status_ready(ex_s_memory_status_ready),
    .m_memory_event_context(ex_m_memory_event_context),
    .m_memory_event_error(ex_m_memory_event_error),
    .m_memory_event_valid(ex_m_memory_event_valid),
    .m_memory_event_ready(tx_s_memory_ready),
    .downstream_queue_guard(tx_queue_guard | h_local_hls_queue_guard),
    .queue_guard(ex_queue_guard),
    .busy(ex_busy),
    .fault(ex_fault),
    .fault_code(ex_fault_code),
    .owner_count(ex_owner_count),
    .command_count(ex_command_count),
    .memory_status_count(ex_memory_status_count)
);
rocev2_wqe_tx_lifetime #(.MAX_QPS(MAX_QPS),.TX_TAG_WIDTH(TX_TAG_WIDTH),.TS_WIDTH(TS_WIDTH),.RETRY_ENABLE(RETRY_ENABLE),.NATIVE_RECV_CPL_ENABLE(RECV_CQ_ENABLE),.REQUEST_CQ_ENABLE(REQUEST_CQ_ENABLE),.CLOCK_PERIOD_PS(CLOCK_PERIOD_PS)) wire_lifetime (
    .s_request_done_data(h_request_done_data),.s_request_done_valid(h_request_done_valid),.s_request_done_ready(h_request_done_ready),
    .cfg_qpn(rrp_cfg_qpn),
    .cfg_pd(rrp_cfg_pd),
    .cfg_cookie(rrp_cfg_cookie),
    .cfg_epoch(rrp_cfg_epoch),
    .cfg_timeout(rrp_cfg_timeout),
    .cfg_retry(rrp_cfg_retry),
    .cfg_rnr_retry(rrp_cfg_rnr_retry),
    .cfg_valid(rrp_cfg_valid),
    .cfg_ready(rrp_cfg_ready),
    .rsp_qpn(rrp_rsp_qpn),
    .rsp_pd(rrp_rsp_pd),
    .rsp_cookie(rrp_rsp_cookie),
    .rsp_epoch(rrp_rsp_epoch),
    .rsp_timeout(rrp_rsp_timeout),
    .rsp_retry(rrp_rsp_retry),
    .rsp_rnr_retry(rrp_rsp_rnr_retry),
    .rsp_error(rrp_rsp_error),
    .rsp_valid(rrp_rsp_valid),
    .rsp_ready(rrp_rsp_ready),
    .s_control_context(rx_control_context),.s_control_psn(rx_control_psn),.s_control_syndrome(rx_control_syndrome),
    .s_control_valid(rx_control_valid),.s_control_ready(rx_control_ready),.retry_count(native_retry_count),.rnr_count(native_rnr_count),
    .clk(clk),
    .rst(rst),
    .enable(1'b1),
    .parent_fault(parent_fault || ex_fault || rx_fault || up_fault || h_shared_hls_fault),
    .s_owner_context(sq_m_executor_context),
    .s_owner_local_ip(local_hls_local_ip),
    .s_owner_peer_ip(local_hls_peer_ip),
    .s_owner_peer_qpn(local_hls_peer_qpn),
    .s_owner_local_mac(active_local_mac),
    .s_owner_peer_mac(active_peer_mac),
    .s_owner_valid(owner_take),
    .s_owner_ready(tx_s_owner_ready),
    .s_axis_ip_tdata(h_m_local_tx_tdata),
    .s_axis_ip_tkeep(h_m_local_tx_tkeep),
    .s_axis_ip_tvalid(h_m_local_tx_tvalid),
    .s_axis_ip_tready(tx_s_axis_ip_tready),
    .s_axis_ip_tlast(h_m_local_tx_tlast),
    .s_axis_ip_tuser(1'b0),
    .s_axis_native_tdata(guarded_native_tdata),
    .s_axis_native_tkeep(guarded_native_tkeep),
    .s_axis_native_tvalid(guarded_native_tvalid),
    .s_axis_native_tready(guarded_native_tready),
    .s_axis_native_tlast(guarded_native_tlast),
    .s_axis_native_tuser(guarded_native_tuser),
    .m_axis_mac_tdata(m_axis_mac_tx_tdata),
    .m_axis_mac_tkeep(m_axis_mac_tx_tkeep),
    .m_axis_mac_tvalid(m_axis_mac_tx_tvalid),
    .m_axis_mac_tready(m_axis_mac_tx_tready),
    .m_axis_mac_tlast(m_axis_mac_tx_tlast),
    .m_axis_mac_tuser(m_axis_mac_tx_tuser),
    .s_mac_cpl_tag(s_axis_mac_cpl_tag),
    .s_mac_cpl_ts(s_axis_mac_cpl_ts),
    .s_mac_cpl_valid(s_axis_mac_cpl_valid),
    .s_mac_cpl_ready(s_axis_mac_cpl_ready),
    .m_native_cpl_tag(guarded_cpl_tag),
    .m_native_cpl_ts(guarded_cpl_ts),
    .m_native_cpl_valid(guarded_cpl_valid),
    .m_native_cpl_ready(guarded_cpl_ready),
    .m_expect_context(tx_m_expect_context),
    .m_expect_local_ip(tx_m_expect_local_ip),
    .m_expect_peer_ip(tx_m_expect_peer_ip),
    .m_expect_psn(tx_m_expect_psn),
    .m_expect_valid(tx_m_expect_valid),
    .m_expect_ready(tx_m_expect_ready),
    .response_admission_ready(tx_response_admission_ready),
    .s_memory_context(ex_m_memory_event_context),
    .s_memory_error(ex_m_memory_event_error),
    .s_memory_valid(ex_m_memory_event_valid),
    .s_memory_ready(tx_s_memory_ready),
    .s_response_context(rx_m_response_event_context),
    .s_response_psn(rx_m_response_event_psn),
    .s_response_opcode(rx_m_response_event_opcode),
    .s_response_syndrome(rx_m_response_event_syndrome),
    .s_response_valid(rx_m_response_event_valid),
    .s_response_ready(rx_m_response_event_ready),
    .s_hls_ack(h_m_local_ack_tdata),
    .s_hls_ack_valid(h_m_local_ack_tvalid),
    .s_hls_ack_ready(tx_s_hls_ack_ready),
    .memory_drained(completion_memory_drained),
    .hls_transport_drained(1'b0),
    .m_cq_context(local_cq_context),
    .m_cq_valid(local_cq_valid),
    .m_cq_ready(local_cq_ready),
    .s_cq_commit_context(cq_commit_context),
    .s_cq_commit_error(cq_commit_error),
    .s_cq_commit_valid(cq_commit_valid && !receive_commit),
    .s_cq_commit_ready(local_commit_ready),
    .queue_guard(tx_queue_guard),
    .busy(tx_busy),
    .fault(tx_fault),
    .fault_code(tx_fault_code),
    .failed_status(tx_failed_status),
    .proof_flags(local_proof_flags),
    .committed_count(local_committed_count),
    .local_tx_drained(tx_local_tx_drained),
    .tags_exhausted(tx_tags_exhausted),
    .active_tag(tx_active_tag),
    .frame_count(tx_frame_count),
    .receipt_count(tx_receipt_count),
    .mac_proof_count(tx_mac_proof_count)
);
rocev2_wqe_response_guard #(.MAX_QPS(MAX_QPS),.CONTROL_ENABLE(RETRY_ENABLE)) protected_response (
    .m_control_context(rx_control_context),.m_control_psn(rx_control_psn),.m_control_syndrome(rx_control_syndrome),
    .m_control_valid(rx_control_valid),.m_control_ready(rx_control_ready),
    .clk(clk),
    .rst(rst),
    .enable(1'b1),
    .halt(pipeline_fault || parent_fault),
    .s_expect_context(tx_m_expect_context),
    .s_expect_local_ip(tx_m_expect_local_ip),
    .s_expect_peer_ip(tx_m_expect_peer_ip),
    .s_expect_psn(tx_m_expect_psn),
    .s_expect_valid(tx_m_expect_valid),
    .s_expect_ready(tx_m_expect_ready),
    .s_axis_rx_tdata(response_tdata),
    .s_axis_rx_tkeep(response_tkeep),
    .s_axis_rx_tvalid(response_tvalid && tx_response_admission_ready),
    .s_axis_rx_tready(response_guard_ready),
    .s_axis_rx_tlast(response_tlast),
    .s_axis_rx_tuser(response_tuser),
    .m_read_response_context(rx_m_read_response_context),
    .m_read_response_valid(rx_m_read_response_valid),
    .m_read_response_ready(read_token_ready),
    .m_axis_hls_rx_tdata(rx_m_axis_hls_rx_tdata),
    .m_axis_hls_rx_tkeep(rx_m_axis_hls_rx_tkeep),
    .m_axis_hls_rx_tlast(rx_m_axis_hls_rx_tlast),
    .m_axis_hls_rx_tvalid(rx_m_axis_hls_rx_tvalid),
    .m_axis_hls_rx_tready(rx_m_axis_hls_rx_tready),
    .m_response_event_context(rx_m_response_event_context),
    .m_response_event_psn(rx_m_response_event_psn),
    .m_response_event_opcode(rx_m_response_event_opcode),
    .m_response_event_syndrome(rx_m_response_event_syndrome),
    .m_response_event_valid(rx_m_response_event_valid),
    .m_response_event_ready(rx_m_response_event_ready),
    .downstream_queue_guard(tx_queue_guard | ex_queue_guard | up_queue_guard | h_local_hls_queue_guard),
    .queue_guard(rx_queue_guard),
    .busy(rx_busy),
    .m_reject_error(rx_m_reject_error),
    .m_reject_valid(rx_m_reject_valid),
    .m_reject_ready(1'b1),
    .fault(rx_fault),
    .fault_code(rx_fault_code),
    .accepted_count(rx_accepted_count),
    .rejected_count(rx_rejected_count),
    .integrity_drop_count(response_integrity_drop_count),
    .unowned_drop_count(rx_unowned_drop_count)
);
rocev2_wqe_read_unpad #(.MAX_QPS(MAX_QPS)) read_unpad (
    .clk(clk),
    .rst(rst),
    .enable(1'b1),
    .s_context(rx_m_read_response_context),
    .s_context_valid(read_token_take),
    .s_context_ready(up_s_context_ready),
    .downstream_queue_guard(ex_queue_guard | tx_queue_guard | h_local_hls_queue_guard),
    .s_command(h_m_local_write_command),
    .s_command_valid(h_m_local_write_command_valid),
    .s_command_ready(up_s_command_ready),
    .m_command(up_m_command),
    .m_command_valid(up_m_command_valid),
    .m_command_ready(up_m_command_ready),
    .s_axis_tdata(h_m_local_write_tdata),
    .s_axis_tkeep(h_m_local_write_tkeep),
    .s_axis_tlast(h_m_local_write_tlast),
    .s_axis_tvalid(h_m_local_write_tvalid),
    .s_axis_tready(up_s_axis_tready),
    .m_axis_tdata(up_m_axis_tdata),
    .m_axis_tkeep(up_m_axis_tkeep),
    .m_axis_tlast(up_m_axis_tlast),
    .m_axis_tvalid(up_m_axis_tvalid),
    .m_axis_tready(up_m_axis_tready),
    .queue_guard(up_queue_guard),
    .busy(up_busy),
    .fault(up_fault),
    .fault_code(up_fault_code),
    .context_count(up_context_count),
    .command_count(up_command_count),
    .discarded_padding_bytes(up_discarded_padding_bytes)
);

// The host sees a committed event only after these two REAL owner handoffs.
generate if(RETRY_ENABLE)begin : replay_control
rocev2_retry_mmio #(.CLOCK_PERIOD_PS(CLOCK_PERIOD_PS)) retry_registers(
    .clk(clk),.rst(rst),.parent_fault(parent_fault || native_fault || ex_fault || tx_fault || rx_fault || up_fault || h_shared_hls_fault || cq_fault),
    .owner_query_qpn(rrp_query_qpn),.owner_query_cookie(rrp_query_cookie),.owner_query_epoch(rrp_query_epoch),
    .owner_query_pd(rrp_query_pd),.owner_query_valid(rrp_query_valid),
    .cfg_qpn(rrp_cfg_qpn),
    .cfg_pd(rrp_cfg_pd),
    .cfg_cookie(rrp_cfg_cookie),
    .cfg_epoch(rrp_cfg_epoch),
    .cfg_timeout(rrp_cfg_timeout),
    .cfg_retry(rrp_cfg_retry),
    .cfg_rnr_retry(rrp_cfg_rnr_retry),
    .cfg_valid(rrp_cfg_valid),
    .cfg_ready(rrp_cfg_ready),
    .rsp_qpn(rrp_rsp_qpn),
    .rsp_pd(rrp_rsp_pd),
    .rsp_cookie(rrp_rsp_cookie),
    .rsp_epoch(rrp_rsp_epoch),
    .rsp_timeout(rrp_rsp_timeout),
    .rsp_retry(rrp_rsp_retry),
    .rsp_rnr_retry(rrp_rsp_rnr_retry),
    .rsp_error(rrp_rsp_error),
    .rsp_valid(rrp_rsp_valid),
    .rsp_ready(rrp_rsp_ready),
    .queue_guard(rrp_queue_guard),.busy(rrp_busy),.fault(rrp_fault),
    .s_axil_awaddr(rrp_awaddr),
    .s_axil_awprot(rrp_awprot),
    .s_axil_awvalid(rrp_awvalid),
    .s_axil_awready(rrp_awready),
    .s_axil_wdata(rrp_wdata),
    .s_axil_wstrb(rrp_wstrb),
    .s_axil_wvalid(rrp_wvalid),
    .s_axil_wready(rrp_wready),
    .s_axil_bresp(rrp_bresp),
    .s_axil_bvalid(rrp_bvalid),
    .s_axil_bready(rrp_bready),
    .s_axil_araddr(rrp_araddr),
    .s_axil_arprot(rrp_arprot),
    .s_axil_arvalid(rrp_arvalid),
    .s_axil_arready(rrp_arready),
    .s_axil_rdata(rrp_rdata),
    .s_axil_rresp(rrp_rresp),
    .s_axil_rvalid(rrp_rvalid),
    .s_axil_rready(rrp_rready));
end else begin : no_replay_control
assign rrp_cfg_qpn=0;
assign rrp_cfg_pd=0;
assign rrp_cfg_cookie=0;
assign rrp_cfg_epoch=0;
assign rrp_cfg_timeout=0;
assign rrp_cfg_retry=0;
assign rrp_cfg_rnr_retry=0;
assign rrp_cfg_valid=0;
assign rrp_rsp_ready=0;
assign rrp_awready=0;
assign rrp_wready=0;
assign rrp_bresp=0;
assign rrp_bvalid=0;
assign rrp_arready=0;
assign rrp_rdata=0;
assign rrp_rresp=0;
assign rrp_rvalid=0;
assign rrp_query_qpn=0;
assign rrp_queue_guard=0;assign rrp_busy=0;assign rrp_fault=0;
end endgenerate

rocev2_cq_mmio #(.MESSAGE_ENABLE(RECV_CQ_ENABLE)) completion_publisher (
    .clk(clk),.rst(rst),
    .parent_fault(parent_fault || ex_fault || tx_fault || rx_fault || up_fault || h_shared_hls_fault),
    .s_ticket_context(m_cq_context),.s_ticket_valid(m_cq_valid),.s_ticket_ready(cq_ticket_ready),
    .s_ticket_received_bytes(rq_ticket_valid ? rq_ticket_received_bytes : 32'd0),
    .s_owner_cookie(cq_owner_cookie),.s_owner_epoch(cq_owner_epoch),.s_owner_pd(cq_owner_pd),.s_owner_valid(cq_owner_valid),
    .m_commit_context(cq_commit_context),.m_commit_error(cq_commit_error),
    .m_commit_valid(cq_commit_valid),.m_commit_ready(s_cq_commit_ready),
    .m_retire_context(cq_retire_context),.m_retire_valid(cq_retire_valid),.m_retire_ready(cq_retire_ready),
    .queue_guard(cq_queue_guard),.busy(cq_busy),.fault(cq_fault),.fault_code(cq_fault_code),
    .published_count(),.acknowledged_count(),
    .s_axil_awaddr(cq_awaddr),
    .s_axil_awprot(cq_awprot),
    .s_axil_awvalid(cq_awvalid),
    .s_axil_awready(cq_awready),
    .s_axil_wdata(cq_wdata),
    .s_axil_wstrb(cq_wstrb),
    .s_axil_wvalid(cq_wvalid),
    .s_axil_wready(cq_wready),
    .s_axil_bresp(cq_bresp),
    .s_axil_bvalid(cq_bvalid),
    .s_axil_bready(cq_bready),
    .s_axil_araddr(cq_araddr),
    .s_axil_arprot(cq_arprot),
    .s_axil_arvalid(cq_arvalid),
    .s_axil_arready(cq_arready),
    .s_axil_rdata(cq_rdata),
    .s_axil_rresp(cq_rresp),
    .s_axil_rvalid(cq_rvalid),
    .s_axil_rready(cq_rready)
);
endmodule
`resetall
