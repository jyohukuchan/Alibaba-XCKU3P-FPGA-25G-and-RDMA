// SPDX-License-Identifier: BSD-2-Clause-Views
// Copyright (c) 2026 jyohukuchan
// MR-relative authorized command -> real staging RAM -> paged PCIe descriptors.
// NOT board-integrated; descriptor/link behavior still requires native proof.
// Caller must authorize fullVA/key/PD/access and freeze admission across MR/PTE
// publication. A command key MUST match the allocated MR key in the page table.
// No unpin on error: fault makes dma_drained/quiescent unavailable. Parent DMA
// cleanup, retained page mappings and fresh key epochs are mandatory on reset.
`resetall
`timescale 1ns/1ps
`default_nettype none
module rocev2_paged_memory_backend #(
    parameter RAM_SIZE=8192,
    parameter RAM_ADDR_WIDTH=15,
    parameter SEG_COUNT=2,
    parameter SEG_DATA_WIDTH=256,
    parameter SEG_BE_WIDTH=SEG_DATA_WIDTH/8,
    parameter SEG_ADDR_WIDTH=RAM_ADDR_WIDTH-$clog2(SEG_COUNT*SEG_BE_WIDTH),
    parameter RAM_SEL_WIDTH=4,
    parameter DMA_LEN_WIDTH=16,
    parameter TAG_WIDTH=16
)(
    input wire clk,
    input wire rst,
    input wire enable,
    input wire s_command_write,
    input wire [63:0] s_command_offset,
    input wire [31:0] s_command_length,
    input wire [TAG_WIDTH-1:0] s_command_tag,
    input wire s_command_valid,
    output wire s_command_ready,
    input wire [511:0] s_axis_write_tdata,
    input wire [63:0] s_axis_write_tkeep,
    input wire s_axis_write_tvalid,
    output wire s_axis_write_tready,
    input wire s_axis_write_tlast,
    output wire [511:0] m_axis_read_tdata,
    output wire [63:0] m_axis_read_tkeep,
    output wire m_axis_read_tvalid,
    input wire m_axis_read_tready,
    output wire m_axis_read_tlast,
    output wire [TAG_WIDTH-1:0] m_status_tag,
    output wire [7:0] m_status_error,
    output wire m_status_valid,
    input wire m_status_ready,
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
    output wire idle,
    output wire dma_drained,
    output wire fault,
    output wire [7:0] fault_code,
    output wire [31:0] command_count,
    output wire [31:0] fence_count,
    output wire [31:0] completion_count,
    input wire [31:0] s_command_key,
    input wire cfg_quiescent,
    input wire [2:0] cfg_command,
    input wire [2:0] cfg_slot,
    input wire [31:0] cfg_key,
    input wire [31:0] cfg_length,
    input wire [11:0] cfg_first_offset,
    input wire [7:0] cfg_page_index,
    input wire [63:0] cfg_dma_page,
    input wire cfg_valid,
    output wire cfg_ready,
    output wire [7:0] cfg_response_error,
    output wire [31:0] cfg_response_key,
    output wire cfg_response_valid,
    input wire cfg_response_ready
);
wire [63:0] logical_m_dma_read_address;
wire [RAM_SEL_WIDTH-1:0] logical_m_dma_read_ram_sel;
wire [RAM_ADDR_WIDTH-1:0] logical_m_dma_read_ram_address;
wire [DMA_LEN_WIDTH-1:0] logical_m_dma_read_length;
wire [TAG_WIDTH-1:0] logical_m_dma_read_tag;
wire logical_m_dma_read_valid;
wire logical_m_dma_read_ready;
wire [TAG_WIDTH-1:0] logical_s_dma_read_status_tag;
wire [3:0] logical_s_dma_read_status_error;
wire logical_s_dma_read_status_valid;
wire [63:0] logical_m_dma_write_address;
wire [RAM_SEL_WIDTH-1:0] logical_m_dma_write_ram_sel;
wire [RAM_ADDR_WIDTH-1:0] logical_m_dma_write_ram_address;
wire [31:0] logical_m_dma_write_imm;
wire logical_m_dma_write_imm_en;
wire [DMA_LEN_WIDTH-1:0] logical_m_dma_write_length;
wire [TAG_WIDTH-1:0] logical_m_dma_write_tag;
wire logical_m_dma_write_valid;
wire logical_m_dma_write_ready;
wire [TAG_WIDTH-1:0] logical_s_dma_write_status_tag;
wire [3:0] logical_s_dma_write_status_error;
wire logical_s_dma_write_status_valid;
wire backend_ready,backend_idle,backend_drained,backend_fault;
wire [7:0] backend_fault_code;
wire engine_ready,engine_idle,engine_drained,engine_fault;
wire [7:0] engine_fault_code;
wire [31:0] leaf_descriptor_count;
wire command_transfer=s_command_valid && s_command_ready;
wire page_quiet=cfg_quiescent && backend_idle && engine_idle && !fault;
// The responder is NOT quiescent while presenting an authorized memory
// command. A held invalidate must wait for that lease, not deadlock it.
// The page-table query-ready excludes actual config capture/pending response.
assign s_command_ready=backend_ready && engine_ready && query_ready && !cfg_response_valid && !fault;
assign idle=backend_idle && engine_idle && !fault;
assign dma_drained=backend_drained && engine_drained && !fault;
assign fault=backend_fault || engine_fault;
assign fault_code=backend_fault ? backend_fault_code : (engine_fault ? engine_fault_code+8'd64 : 8'd0);

rocev2_corundum_dma_backend #(.RAM_SIZE(RAM_SIZE),.RAM_ADDR_WIDTH(RAM_ADDR_WIDTH),
    .SEG_COUNT(SEG_COUNT),.SEG_DATA_WIDTH(SEG_DATA_WIDTH),.SEG_BE_WIDTH(SEG_BE_WIDTH),
    .SEG_ADDR_WIDTH(SEG_ADDR_WIDTH),.RAM_SEL_WIDTH(RAM_SEL_WIDTH),
    .DMA_LEN_WIDTH(DMA_LEN_WIDTH),.TAG_WIDTH(TAG_WIDTH)) backend (
    .clk(clk),
    .rst(rst),
    .enable(enable && !engine_fault),
    .s_command_write(s_command_write),
    .s_command_address(s_command_offset),
    .s_command_length(s_command_length),
    .s_command_tag(s_command_tag),
    .s_command_valid(command_transfer),
    .s_command_ready(backend_ready),
    .s_axis_write_tdata(s_axis_write_tdata),
    .s_axis_write_tkeep(s_axis_write_tkeep),
    .s_axis_write_tvalid(s_axis_write_tvalid),
    .s_axis_write_tready(s_axis_write_tready),
    .s_axis_write_tlast(s_axis_write_tlast),
    .m_axis_read_tdata(m_axis_read_tdata),
    .m_axis_read_tkeep(m_axis_read_tkeep),
    .m_axis_read_tvalid(m_axis_read_tvalid),
    .m_axis_read_tready(m_axis_read_tready),
    .m_axis_read_tlast(m_axis_read_tlast),
    .m_status_tag(m_status_tag),
    .m_status_error(m_status_error),
    .m_status_valid(m_status_valid),
    .m_status_ready(m_status_ready),
    .m_dma_read_address(logical_m_dma_read_address),
    .m_dma_read_ram_sel(logical_m_dma_read_ram_sel),
    .m_dma_read_ram_address(logical_m_dma_read_ram_address),
    .m_dma_read_length(logical_m_dma_read_length),
    .m_dma_read_tag(logical_m_dma_read_tag),
    .m_dma_read_valid(logical_m_dma_read_valid),
    .m_dma_read_ready(logical_m_dma_read_ready),
    .s_dma_read_status_tag(logical_s_dma_read_status_tag),
    .s_dma_read_status_error(logical_s_dma_read_status_error),
    .s_dma_read_status_valid(logical_s_dma_read_status_valid),
    .m_dma_write_address(logical_m_dma_write_address),
    .m_dma_write_ram_sel(logical_m_dma_write_ram_sel),
    .m_dma_write_ram_address(logical_m_dma_write_ram_address),
    .m_dma_write_imm(logical_m_dma_write_imm),
    .m_dma_write_imm_en(logical_m_dma_write_imm_en),
    .m_dma_write_length(logical_m_dma_write_length),
    .m_dma_write_tag(logical_m_dma_write_tag),
    .m_dma_write_valid(logical_m_dma_write_valid),
    .m_dma_write_ready(logical_m_dma_write_ready),
    .s_dma_write_status_tag(logical_s_dma_write_status_tag),
    .s_dma_write_status_error(logical_s_dma_write_status_error),
    .s_dma_write_status_valid(logical_s_dma_write_status_valid),
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
    .command_count(command_count),
    .fence_count(fence_count),
    .completion_count(completion_count)
);

wire [2:0] query_slot;
wire [31:0] query_key,query_length;
wire [63:0] query_offset,segment_address;
wire [15:0] query_tag,segment_tag;
wire query_valid,query_ready,segment_valid,segment_ready;
wire [7:0] segment_error;
wire [12:0] segment_length;
rocev2_mr_page_table page_table (
    .clk(clk),.rst(rst),.cfg_quiescent(page_quiet),
    .cfg_command(cfg_command),.cfg_slot(cfg_slot),.cfg_key(cfg_key),
    .cfg_length(cfg_length),.cfg_first_offset(cfg_first_offset),
    .cfg_page_index(cfg_page_index),.cfg_dma_page(cfg_dma_page),
    .cfg_valid(cfg_valid),.cfg_ready(cfg_ready),.cfg_response_error(cfg_response_error),
    .cfg_response_key(cfg_response_key),.cfg_response_valid(cfg_response_valid),.cfg_response_ready(cfg_response_ready),
    .s_query_slot(query_slot),.s_query_key(query_key),.s_query_offset(query_offset),
    .s_query_length(query_length),.s_query_tag(query_tag),.s_query_valid(query_valid),.s_query_ready(query_ready),
    .m_segment_tag(segment_tag),.m_segment_error(segment_error),.m_segment_dma_address(segment_address),
    .m_segment_length(segment_length),.m_segment_valid(segment_valid),.m_segment_ready(segment_ready));

wire leaf_write,leaf_valid,leaf_ready,aggregate_write,aggregate_valid;
wire [63:0] leaf_address;
wire [RAM_ADDR_WIDTH-1:0] leaf_ram_address;
wire [DMA_LEN_WIDTH-1:0] leaf_length;
wire [15:0] leaf_tag,aggregate_tag;
wire [3:0] aggregate_error;
wire logical_write=logical_m_dma_write_valid;
assign logical_m_dma_write_ready=engine_descriptor_ready;
assign logical_m_dma_read_ready=engine_descriptor_ready && !logical_write;
wire engine_descriptor_ready;
wire physical_collision=s_dma_write_status_valid && s_dma_read_status_valid;
rocev2_page_dma_engine #(.RAM_ADDR_WIDTH(RAM_ADDR_WIDTH),.DMA_LEN_WIDTH(DMA_LEN_WIDTH),
    .FENCE_ADDRESS(RAM_SIZE-64)) pages (
    .clk(clk),.rst(rst),.halt(backend_fault),
    .s_lease_write(s_command_write),.s_lease_key(s_command_key),.s_lease_offset(s_command_offset),
    .s_lease_length(s_command_length),.s_lease_tag(s_command_tag),.s_lease_valid(command_transfer),.s_lease_ready(engine_ready),
    .release_lease(m_status_valid && m_status_ready && m_status_error==0 && !fault),
    .s_descriptor_write(logical_write),
    .s_descriptor_offset(logical_write ? logical_m_dma_write_address : logical_m_dma_read_address),
    .s_descriptor_ram_address(logical_write ? logical_m_dma_write_ram_address : logical_m_dma_read_ram_address),
    .s_descriptor_length(logical_write ? logical_m_dma_write_length : logical_m_dma_read_length),
    .s_descriptor_tag(logical_write ? logical_m_dma_write_tag : logical_m_dma_read_tag),
    .s_descriptor_valid(logical_m_dma_write_valid || logical_m_dma_read_valid),.s_descriptor_ready(engine_descriptor_ready),
    .m_status_write(aggregate_write),.m_status_tag(aggregate_tag),.m_status_error(aggregate_error),.m_status_valid(aggregate_valid),
    .m_query_slot(query_slot),.m_query_key(query_key),.m_query_offset(query_offset),
    .m_query_length(query_length),.m_query_tag(query_tag),.m_query_valid(query_valid),.m_query_ready(query_ready),
    .s_segment_tag(segment_tag),.s_segment_error(segment_error),.s_segment_dma_address(segment_address),
    .s_segment_length(segment_length),.s_segment_valid(segment_valid),.s_segment_ready(segment_ready),
    .m_descriptor_write(leaf_write),.m_descriptor_address(leaf_address),.m_descriptor_ram_address(leaf_ram_address),
    .m_descriptor_length(leaf_length),.m_descriptor_tag(leaf_tag),.m_descriptor_valid(leaf_valid),.m_descriptor_ready(leaf_ready),
    .s_status_write(s_dma_write_status_valid),
    .s_status_tag(physical_collision ? 16'd0 : (s_dma_write_status_valid ? s_dma_write_status_tag : s_dma_read_status_tag)),
    .s_status_error(s_dma_write_status_valid ? s_dma_write_status_error : s_dma_read_status_error),
    .s_status_valid(s_dma_write_status_valid || s_dma_read_status_valid),
    .idle(engine_idle),.descriptor_drained(engine_drained),.fault(engine_fault),.fault_code(engine_fault_code),
    .descriptor_count(leaf_descriptor_count));
assign logical_s_dma_write_status_tag=aggregate_tag;
assign logical_s_dma_write_status_error=aggregate_error;
assign logical_s_dma_write_status_valid=aggregate_valid && aggregate_write;
assign logical_s_dma_read_status_tag=aggregate_tag;
assign logical_s_dma_read_status_error=aggregate_error;
assign logical_s_dma_read_status_valid=aggregate_valid && !aggregate_write;

assign leaf_ready=leaf_write ? m_dma_write_ready : m_dma_read_ready;
assign m_dma_write_address=leaf_address;
assign m_dma_write_ram_sel=0;
assign m_dma_write_ram_address=leaf_ram_address;
assign m_dma_write_imm=0;
assign m_dma_write_imm_en=0;
assign m_dma_write_length=leaf_length;
assign m_dma_write_tag=leaf_tag;
assign m_dma_write_valid=leaf_valid && leaf_write;
assign m_dma_read_address=leaf_address;
assign m_dma_read_ram_sel=0;
assign m_dma_read_ram_address=leaf_ram_address;
assign m_dma_read_length=leaf_length;
assign m_dma_read_tag=leaf_tag;
assign m_dma_read_valid=leaf_valid && !leaf_write;
initial begin
    if(TAG_WIDTH!=16) begin $error("Paged backend requires16-bit unique physical tags");$finish;end
end
endmodule
`resetall

