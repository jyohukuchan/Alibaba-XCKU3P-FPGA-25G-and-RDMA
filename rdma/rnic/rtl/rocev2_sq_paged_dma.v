// SPDX-License-Identifier: BSD-2-Clause-Views
// Copyright (c) 2026 jyohukuchan
// Actual paged payload and coherent-SQ DMA share original16-bit app tags/RAM.
// Trusted authorized data commands/config and SQ context are EXTERNAL; this is
// not the protected parser/local work executor/native CSR/provider/board top.
// Parent fault/drain must come from actual engine/mux/TLP/RAM evidence.
// No local idle/status/reset alone can release host mappings or WR refs.
`resetall
`timescale 1ns/1ps
`default_nettype none
module rocev2_sq_paged_dma #(
    parameter MAX_QPS=8,
    parameter RAM_SIZE=8192,
    parameter RAM_ADDR_WIDTH=15,
    parameter SEG_COUNT=2,
    parameter SEG_DATA_WIDTH=256,
    parameter SEG_BE_WIDTH=32,
    parameter SEG_ADDR_WIDTH=RAM_ADDR_WIDTH-6,
    parameter DMA_LEN_WIDTH=16,
    parameter TAG_WIDTH=16
)(
    input wire clk,
    input wire rst,
    input wire enable,
    input wire parent_dma_drained,
    input wire parent_fault,
    input wire data_s_command_write,
    input wire [63:0] data_s_command_offset,
    input wire [31:0] data_s_command_length,
    input wire [TAG_WIDTH-1:0] data_s_command_tag,
    input wire data_s_command_valid,
    output wire data_s_command_ready,
    input wire [511:0] data_s_axis_write_tdata,
    input wire [63:0] data_s_axis_write_tkeep,
    input wire data_s_axis_write_tvalid,
    output wire data_s_axis_write_tready,
    input wire data_s_axis_write_tlast,
    output wire [511:0] data_m_axis_read_tdata,
    output wire [63:0] data_m_axis_read_tkeep,
    output wire data_m_axis_read_tvalid,
    input wire data_m_axis_read_tready,
    output wire data_m_axis_read_tlast,
    output wire [TAG_WIDTH-1:0] data_m_status_tag,
    output wire [7:0] data_m_status_error,
    output wire data_m_status_valid,
    input wire data_m_status_ready,
    output wire data_idle,
    output wire data_dma_drained,
    output wire data_fault,
    output wire [7:0] data_fault_code,
    output wire [31:0] data_command_count,
    output wire [31:0] data_fence_count,
    output wire [31:0] data_completion_count,
    input wire [31:0] data_s_command_key,
    input wire data_cfg_quiescent,
    input wire [2:0] data_cfg_command,
    input wire [2:0] data_cfg_slot,
    input wire [31:0] data_cfg_key,
    input wire [31:0] data_cfg_length,
    input wire [11:0] data_cfg_first_offset,
    input wire [7:0] data_cfg_page_index,
    input wire [63:0] data_cfg_dma_page,
    input wire data_cfg_valid,
    output wire data_cfg_ready,
    output wire [7:0] data_cfg_response_error,
    output wire [31:0] data_cfg_response_key,
    output wire data_cfg_response_valid,
    input wire data_cfg_response_ready,
    input wire [1:0] sq_cfg_command,
    input wire [23:0] sq_cfg_qpn,
    input wire [15:0] sq_cfg_pd,
    input wire [63:0] sq_cfg_epoch,
    input wire [63:0] sq_cfg_dma_base,
    input wire [3:0] sq_cfg_log_depth,
    input wire [63:0] sq_cfg_producer,
    input wire sq_cfg_valid,
    output wire sq_cfg_ready,
    output wire [7:0] sq_cfg_response_error,
    output wire [23:0] sq_cfg_response_qpn,
    output wire [63:0] sq_cfg_response_epoch,
    output wire [63:0] sq_cfg_response_consumer,
    output wire sq_cfg_response_valid,
    input wire sq_cfg_response_ready,
    input wire [MAX_QPS-1:0] sq_downstream_queue_guard,
    output wire [MAX_QPS-1:0] sq_queue_guard,
    output wire [MAX_QPS-1:0] sq_queue_active,
    output wire [MAX_QPS-1:0] sq_queue_halted,
    output wire [511:0] sq_m_result_data,
    output wire [7:0] sq_m_result_error,
    output wire [23:0] sq_m_result_qpn,
    output wire [15:0] sq_m_result_pd,
    output wire [63:0] sq_m_result_epoch,
    output wire [63:0] sq_m_result_sequence,
    output wire [15:0] sq_m_result_tag,
    output wire sq_m_result_valid,
    input wire sq_m_result_ready,
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
    output wire [63:0] m_dma_read_address,
    output wire m_dma_read_ram_sel,
    output wire [RAM_ADDR_WIDTH-1:0] m_dma_read_ram_address,
    output wire [DMA_LEN_WIDTH-1:0] m_dma_read_length,
    output wire [TAG_WIDTH-1:0] m_dma_read_tag,
    output wire m_dma_read_valid,
    input wire m_dma_read_ready,
    input wire [TAG_WIDTH-1:0] s_dma_read_status_tag,
    input wire [3:0] s_dma_read_status_error,
    input wire s_dma_read_status_valid,
    output wire [63:0] m_dma_write_address,
    output wire m_dma_write_ram_sel,
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
    input wire [SEG_COUNT-1:0] dma_ram_wr_cmd_sel,
    input wire [SEG_COUNT*SEG_BE_WIDTH-1:0] dma_ram_wr_cmd_be,
    input wire [SEG_COUNT*SEG_ADDR_WIDTH-1:0] dma_ram_wr_cmd_addr,
    input wire [SEG_COUNT*SEG_DATA_WIDTH-1:0] dma_ram_wr_cmd_data,
    input wire [SEG_COUNT-1:0] dma_ram_wr_cmd_valid,
    output wire [SEG_COUNT-1:0] dma_ram_wr_cmd_ready,
    output wire [SEG_COUNT-1:0] dma_ram_wr_done,
    input wire [SEG_COUNT-1:0] dma_ram_rd_cmd_sel,
    input wire [SEG_COUNT*SEG_ADDR_WIDTH-1:0] dma_ram_rd_cmd_addr,
    input wire [SEG_COUNT-1:0] dma_ram_rd_cmd_valid,
    output wire [SEG_COUNT-1:0] dma_ram_rd_cmd_ready,
    output wire [SEG_COUNT*SEG_DATA_WIDTH-1:0] dma_ram_rd_resp_data,
    output wire [SEG_COUNT-1:0] dma_ram_rd_resp_valid,
    input wire [SEG_COUNT-1:0] dma_ram_rd_resp_ready,
    output wire fault,
    output wire [7:0] fault_code,
    output wire dma_drained,
    output wire [1:0] router_client_busy,
    output wire router_fault,
    output wire [7:0] router_fault_code,
    output wire router_tag_exhausted,
    output wire [31:0] router_descriptor_count,
    output wire [31:0] router_completion_count
);
localparam RAM_SEL_WIDTH=1;
wire router_drained;
wire [63:0] data_m_dma_read_address;
wire [RAM_SEL_WIDTH-1:0] data_m_dma_read_ram_sel;
wire [RAM_ADDR_WIDTH-1:0] data_m_dma_read_ram_address;
wire [DMA_LEN_WIDTH-1:0] data_m_dma_read_length;
wire [TAG_WIDTH-1:0] data_m_dma_read_tag;
wire data_m_dma_read_valid;
wire data_m_dma_read_ready;
wire [TAG_WIDTH-1:0] data_s_dma_read_status_tag;
wire [3:0] data_s_dma_read_status_error;
wire data_s_dma_read_status_valid;
wire [63:0] data_m_dma_write_address;
wire [RAM_SEL_WIDTH-1:0] data_m_dma_write_ram_sel;
wire [RAM_ADDR_WIDTH-1:0] data_m_dma_write_ram_address;
wire [31:0] data_m_dma_write_imm;
wire data_m_dma_write_imm_en;
wire [DMA_LEN_WIDTH-1:0] data_m_dma_write_length;
wire [TAG_WIDTH-1:0] data_m_dma_write_tag;
wire data_m_dma_write_valid;
wire data_m_dma_write_ready;
wire [TAG_WIDTH-1:0] data_s_dma_write_status_tag;
wire [3:0] data_s_dma_write_status_error;
wire data_s_dma_write_status_valid;
wire [SEG_COUNT*RAM_SEL_WIDTH-1:0] data_dma_ram_wr_cmd_sel;
wire [SEG_COUNT*SEG_BE_WIDTH-1:0] data_dma_ram_wr_cmd_be;
wire [SEG_COUNT*SEG_ADDR_WIDTH-1:0] data_dma_ram_wr_cmd_addr;
wire [SEG_COUNT*SEG_DATA_WIDTH-1:0] data_dma_ram_wr_cmd_data;
wire [SEG_COUNT-1:0] data_dma_ram_wr_cmd_valid;
wire [SEG_COUNT-1:0] data_dma_ram_wr_cmd_ready;
wire [SEG_COUNT-1:0] data_dma_ram_wr_done;
wire [SEG_COUNT*RAM_SEL_WIDTH-1:0] data_dma_ram_rd_cmd_sel;
wire [SEG_COUNT*SEG_ADDR_WIDTH-1:0] data_dma_ram_rd_cmd_addr;
wire [SEG_COUNT-1:0] data_dma_ram_rd_cmd_valid;
wire [SEG_COUNT-1:0] data_dma_ram_rd_cmd_ready;
wire [SEG_COUNT*SEG_DATA_WIDTH-1:0] data_dma_ram_rd_resp_data;
wire [SEG_COUNT-1:0] data_dma_ram_rd_resp_valid;
wire [SEG_COUNT-1:0] data_dma_ram_rd_resp_ready;
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
assign fault=parent_fault || router_fault || data_fault || sq_fault;
assign fault_code=parent_fault ? 8'hf0 : router_fault ? (router_fault_code|8'hc0) :
    data_fault ? data_fault_code : sq_fault ? (sq_fault_code|8'h80) : 8'd0;
// Boundary proof only, never full MR/QP/wire/CQ lifetime. SQ READ_DRAIN's
// parent input deliberately does NOT depend on its own idle/busy output.
assign dma_drained=parent_dma_drained && router_drained && data_dma_drained && sq_dma_drained && !fault;
rocev2_paged_memory_backend #(
    .RAM_SIZE(RAM_SIZE),.RAM_ADDR_WIDTH(RAM_ADDR_WIDTH),.SEG_COUNT(SEG_COUNT),
    .SEG_DATA_WIDTH(SEG_DATA_WIDTH),.SEG_BE_WIDTH(SEG_BE_WIDTH),.SEG_ADDR_WIDTH(SEG_ADDR_WIDTH),
    .RAM_SEL_WIDTH(1),.DMA_LEN_WIDTH(DMA_LEN_WIDTH),.TAG_WIDTH(TAG_WIDTH)
) payload (
    .clk(clk),
    .rst(rst),
    .enable(enable && !fault),
    .s_command_write(data_s_command_write),
    .s_command_offset(data_s_command_offset),
    .s_command_length(data_s_command_length),
    .s_command_tag(data_s_command_tag),
    .s_command_valid(data_s_command_valid),
    .s_command_ready(data_s_command_ready),
    .s_axis_write_tdata(data_s_axis_write_tdata),
    .s_axis_write_tkeep(data_s_axis_write_tkeep),
    .s_axis_write_tvalid(data_s_axis_write_tvalid),
    .s_axis_write_tready(data_s_axis_write_tready),
    .s_axis_write_tlast(data_s_axis_write_tlast),
    .m_axis_read_tdata(data_m_axis_read_tdata),
    .m_axis_read_tkeep(data_m_axis_read_tkeep),
    .m_axis_read_tvalid(data_m_axis_read_tvalid),
    .m_axis_read_tready(data_m_axis_read_tready),
    .m_axis_read_tlast(data_m_axis_read_tlast),
    .m_status_tag(data_m_status_tag),
    .m_status_error(data_m_status_error),
    .m_status_valid(data_m_status_valid),
    .m_status_ready(data_m_status_ready),
    .m_dma_read_address(data_m_dma_read_address),
    .m_dma_read_ram_sel(data_m_dma_read_ram_sel),
    .m_dma_read_ram_address(data_m_dma_read_ram_address),
    .m_dma_read_length(data_m_dma_read_length),
    .m_dma_read_tag(data_m_dma_read_tag),
    .m_dma_read_valid(data_m_dma_read_valid),
    .m_dma_read_ready(data_m_dma_read_ready),
    .s_dma_read_status_tag(data_s_dma_read_status_tag),
    .s_dma_read_status_error(data_s_dma_read_status_error),
    .s_dma_read_status_valid(data_s_dma_read_status_valid),
    .m_dma_write_address(data_m_dma_write_address),
    .m_dma_write_ram_sel(data_m_dma_write_ram_sel),
    .m_dma_write_ram_address(data_m_dma_write_ram_address),
    .m_dma_write_imm(data_m_dma_write_imm),
    .m_dma_write_imm_en(data_m_dma_write_imm_en),
    .m_dma_write_length(data_m_dma_write_length),
    .m_dma_write_tag(data_m_dma_write_tag),
    .m_dma_write_valid(data_m_dma_write_valid),
    .m_dma_write_ready(data_m_dma_write_ready),
    .s_dma_write_status_tag(data_s_dma_write_status_tag),
    .s_dma_write_status_error(data_s_dma_write_status_error),
    .s_dma_write_status_valid(data_s_dma_write_status_valid),
    .dma_ram_wr_cmd_sel(data_dma_ram_wr_cmd_sel),
    .dma_ram_wr_cmd_be(data_dma_ram_wr_cmd_be),
    .dma_ram_wr_cmd_addr(data_dma_ram_wr_cmd_addr),
    .dma_ram_wr_cmd_data(data_dma_ram_wr_cmd_data),
    .dma_ram_wr_cmd_valid(data_dma_ram_wr_cmd_valid),
    .dma_ram_wr_cmd_ready(data_dma_ram_wr_cmd_ready),
    .dma_ram_wr_done(data_dma_ram_wr_done),
    .dma_ram_rd_cmd_sel(data_dma_ram_rd_cmd_sel),
    .dma_ram_rd_cmd_addr(data_dma_ram_rd_cmd_addr),
    .dma_ram_rd_cmd_valid(data_dma_ram_rd_cmd_valid),
    .dma_ram_rd_cmd_ready(data_dma_ram_rd_cmd_ready),
    .dma_ram_rd_resp_data(data_dma_ram_rd_resp_data),
    .dma_ram_rd_resp_valid(data_dma_ram_rd_resp_valid),
    .dma_ram_rd_resp_ready(data_dma_ram_rd_resp_ready),
    .idle(data_idle),
    .dma_drained(data_dma_drained),
    .fault(data_fault),
    .fault_code(data_fault_code),
    .command_count(data_command_count),
    .fence_count(data_fence_count),
    .completion_count(data_completion_count),
    .s_command_key(data_s_command_key),
    .cfg_quiescent(data_cfg_quiescent),
    .cfg_command(data_cfg_command),
    .cfg_slot(data_cfg_slot),
    .cfg_key(data_cfg_key),
    .cfg_length(data_cfg_length),
    .cfg_first_offset(data_cfg_first_offset),
    .cfg_page_index(data_cfg_page_index),
    .cfg_dma_page(data_cfg_dma_page),
    .cfg_valid(data_cfg_valid),
    .cfg_ready(data_cfg_ready),
    .cfg_response_error(data_cfg_response_error),
    .cfg_response_key(data_cfg_response_key),
    .cfg_response_valid(data_cfg_response_valid),
    .cfg_response_ready(data_cfg_response_ready)
);
rocev2_sq_dma_fetch #(
    .MAX_QPS(MAX_QPS),.RAM_SIZE(RAM_SIZE),.RAM_ADDR_WIDTH(RAM_ADDR_WIDTH),.SEG_COUNT(SEG_COUNT),
    .SEG_DATA_WIDTH(SEG_DATA_WIDTH),.SEG_BE_WIDTH(SEG_BE_WIDTH),.SEG_ADDR_WIDTH(SEG_ADDR_WIDTH),
    .RAM_SEL_WIDTH(1),.DMA_LEN_WIDTH(DMA_LEN_WIDTH),.TAG_WIDTH(TAG_WIDTH)
) sq (
    .clk(clk),
    .rst(rst),
    .enable(enable && !fault),
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
    .parent_dma_drained(parent_dma_drained && router_drained && !fault),
    .downstream_queue_guard(sq_downstream_queue_guard),
    .queue_guard(sq_queue_guard),
    .queue_active(sq_queue_active),
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
    .enable(enable && !parent_fault && !data_fault && !sq_fault),
    .s_client_read_address({sq_m_dma_read_address,data_m_dma_read_address}),
    .s_client_read_ram_sel({sq_m_dma_read_ram_sel,data_m_dma_read_ram_sel}),
    .s_client_read_ram_address({sq_m_dma_read_ram_address,data_m_dma_read_ram_address}),
    .s_client_read_length({sq_m_dma_read_length,data_m_dma_read_length}),
    .s_client_read_tag({sq_m_dma_read_tag,data_m_dma_read_tag}),
    .s_client_read_valid({sq_m_dma_read_valid,data_m_dma_read_valid}),
    .s_client_read_ready({sq_m_dma_read_ready,data_m_dma_read_ready}),
    .m_client_read_status_tag({sq_s_dma_read_status_tag,data_s_dma_read_status_tag}),
    .m_client_read_status_error({sq_s_dma_read_status_error,data_s_dma_read_status_error}),
    .m_client_read_status_valid({sq_s_dma_read_status_valid,data_s_dma_read_status_valid}),
    .s_client_write_address({sq_m_dma_write_address,data_m_dma_write_address}),
    .s_client_write_ram_sel({sq_m_dma_write_ram_sel,data_m_dma_write_ram_sel}),
    .s_client_write_ram_address({sq_m_dma_write_ram_address,data_m_dma_write_ram_address}),
    .s_client_write_imm({sq_m_dma_write_imm,data_m_dma_write_imm}),
    .s_client_write_imm_en({sq_m_dma_write_imm_en,data_m_dma_write_imm_en}),
    .s_client_write_length({sq_m_dma_write_length,data_m_dma_write_length}),
    .s_client_write_tag({sq_m_dma_write_tag,data_m_dma_write_tag}),
    .s_client_write_valid({sq_m_dma_write_valid,data_m_dma_write_valid}),
    .s_client_write_ready({sq_m_dma_write_ready,data_m_dma_write_ready}),
    .m_client_write_status_tag({sq_s_dma_write_status_tag,data_s_dma_write_status_tag}),
    .m_client_write_status_error({sq_s_dma_write_status_error,data_s_dma_write_status_error}),
    .m_client_write_status_valid({sq_s_dma_write_status_valid,data_s_dma_write_status_valid}),
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
    .client_ram_wr_cmd_sel({sq_dma_ram_wr_cmd_sel,data_dma_ram_wr_cmd_sel}),
    .client_ram_wr_cmd_be({sq_dma_ram_wr_cmd_be,data_dma_ram_wr_cmd_be}),
    .client_ram_wr_cmd_addr({sq_dma_ram_wr_cmd_addr,data_dma_ram_wr_cmd_addr}),
    .client_ram_wr_cmd_data({sq_dma_ram_wr_cmd_data,data_dma_ram_wr_cmd_data}),
    .client_ram_wr_cmd_valid({sq_dma_ram_wr_cmd_valid,data_dma_ram_wr_cmd_valid}),
    .client_ram_wr_cmd_ready({sq_dma_ram_wr_cmd_ready,data_dma_ram_wr_cmd_ready}),
    .client_ram_wr_done({sq_dma_ram_wr_done,data_dma_ram_wr_done}),
    .client_ram_rd_cmd_sel({sq_dma_ram_rd_cmd_sel,data_dma_ram_rd_cmd_sel}),
    .client_ram_rd_cmd_addr({sq_dma_ram_rd_cmd_addr,data_dma_ram_rd_cmd_addr}),
    .client_ram_rd_cmd_valid({sq_dma_ram_rd_cmd_valid,data_dma_ram_rd_cmd_valid}),
    .client_ram_rd_cmd_ready({sq_dma_ram_rd_cmd_ready,data_dma_ram_rd_cmd_ready}),
    .client_ram_rd_resp_data({sq_dma_ram_rd_resp_data,data_dma_ram_rd_resp_data}),
    .client_ram_rd_resp_valid({sq_dma_ram_rd_resp_valid,data_dma_ram_rd_resp_valid}),
    .client_ram_rd_resp_ready({sq_dma_ram_rd_resp_ready,data_dma_ram_rd_resp_ready}),
    .client_busy(router_client_busy),
    .drained(router_drained),
    .tag_exhausted(router_tag_exhausted),
    .fault(router_fault),
    .fault_code(router_fault_code),
    .descriptor_count(router_descriptor_count),
    .completion_count(router_completion_count)
);
endmodule
`resetall
