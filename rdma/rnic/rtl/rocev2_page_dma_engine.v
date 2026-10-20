// SPDX-License-Identifier: BSD-2-Clause-Views
// Copyright (c) 2026 jyohukuchan
// Serialize one authorized MR lease into page-bounded Corundum descriptors.
// Offsets are NOT physical addresses. Only the trusted page table supplies DMA64.
// Every physical descriptor gets a non-reused tag until reset (no silent wrap).
// A fault retains the lease; matching already-issued status may only drain it.
// Reset is legal ONLY after the parent PCIe engine is drained and QPs closed.
`resetall
`timescale 1ns/1ps
`default_nettype none
module rocev2_page_dma_engine #(
    parameter RAM_ADDR_WIDTH=15,
    parameter DMA_LEN_WIDTH=16,
    parameter FENCE_ADDRESS=8128
)(
    input wire clk,
    input wire rst,
    input wire halt,
    input wire s_lease_write,
    input wire [31:0] s_lease_key,
    input wire [63:0] s_lease_offset,
    input wire [31:0] s_lease_length,
    input wire [15:0] s_lease_tag,
    input wire s_lease_valid,
    output wire s_lease_ready,
    input wire release_lease,
    input wire s_descriptor_write,
    input wire [63:0] s_descriptor_offset,
    input wire [RAM_ADDR_WIDTH-1:0] s_descriptor_ram_address,
    input wire [DMA_LEN_WIDTH-1:0] s_descriptor_length,
    input wire [15:0] s_descriptor_tag,
    input wire s_descriptor_valid,
    output wire s_descriptor_ready,
    output reg m_status_write=0,
    output reg [15:0] m_status_tag=0,
    output reg [3:0] m_status_error=0,
    output reg m_status_valid=0,
    output wire [2:0] m_query_slot,
    output wire [31:0] m_query_key,
    output wire [63:0] m_query_offset,
    output wire [31:0] m_query_length,
    output wire [15:0] m_query_tag,
    output wire m_query_valid,
    input wire m_query_ready,
    input wire [15:0] s_segment_tag,
    input wire [7:0] s_segment_error,
    input wire [63:0] s_segment_dma_address,
    input wire [12:0] s_segment_length,
    input wire s_segment_valid,
    output wire s_segment_ready,
    output reg m_descriptor_write=0,
    output reg [63:0] m_descriptor_address=0,
    output reg [RAM_ADDR_WIDTH-1:0] m_descriptor_ram_address=0,
    output reg [DMA_LEN_WIDTH-1:0] m_descriptor_length=0,
    output reg [15:0] m_descriptor_tag=0,
    output wire m_descriptor_valid,
    input wire m_descriptor_ready,
    input wire s_status_write,
    input wire [15:0] s_status_tag,
    input wire [3:0] s_status_error,
    input wire s_status_valid,
    output wire idle,
    output wire descriptor_drained,
    output reg fault=0,
    output reg [7:0] fault_code=0,
    output reg [31:0] descriptor_count=0
);
localparam IDLE=0,QUERY=1,TABLE_WAIT=2,ISSUE=3,DMA_WAIT=4,FAILED=5;
localparam ERR_LEASE=1,ERR_DESCRIPTOR=2,ERR_TABLE=3,ERR_STATUS=4,ERR_RELEASE=5,ERR_TAGS=6,ERR_HALT=7;
reg [2:0] state=IDLE;
reg lease=0,lease_write=0,payload_done=0,fence_done=0;
reg [31:0] lease_key=0,lease_length=0;
reg [63:0] lease_offset=0,offset=0;
reg [15:0] lease_tag=0,next_tag=1;
reg exhausted=0,logical_write=0,logical_fence=0,outstanding=0;
reg [31:0] remaining=0;
reg [RAM_ADDR_WIDTH-1:0] ram_offset=0;
wire [64:0] lease_end={1'b0,s_lease_offset}+{33'd0,s_lease_length};
wire lease_shape=s_lease_tag!=0 && s_lease_key[31:3]!=0 && s_lease_length!=0 &&
    s_lease_length<=4096 && lease_end<=65'd1048576;
wire payload_shape=!payload_done && s_descriptor_write==lease_write &&
    s_descriptor_offset==lease_offset && s_descriptor_length==lease_length && s_descriptor_ram_address==0;
wire fence_shape=payload_done && lease_write && !fence_done && !s_descriptor_write &&
    s_descriptor_offset==lease_offset && s_descriptor_length==1 && s_descriptor_ram_address==FENCE_ADDRESS;
wire descriptor_shape=s_descriptor_tag==lease_tag && (payload_shape || fence_shape);
wire matching_status=state==DMA_WAIT && outstanding && s_status_tag==m_descriptor_tag && s_status_write==logical_write;
wire unexpected_status=s_status_valid && !matching_status;
wire release_ok=lease && state==IDLE && payload_done && (!lease_write || fence_done);
wire bad_release=release_lease && !release_ok;
assign s_lease_ready=!lease && state==IDLE && !m_status_valid && !fault && !halt && !rst;
assign s_descriptor_ready=lease && state==IDLE && !m_status_valid && !fault && !halt && !rst;
assign m_query_slot=lease_key[2:0];
assign m_query_key=lease_key;
assign m_query_offset=offset;
assign m_query_length=remaining;
assign m_query_tag=lease_tag;
// Issued requests are never withdrawn under backpressure, even after fault.
assign m_query_valid=state==QUERY && !rst;
assign s_segment_ready=state==TABLE_WAIT && !rst;
assign m_descriptor_valid=state==ISSUE && !rst;
assign idle=!lease && state==IDLE && !m_status_valid && !fault && !rst;
assign descriptor_drained=!outstanding && state!=ISSUE && state!=QUERY && state!=TABLE_WAIT && !rst;

always @(posedge clk) begin
    if(rst) begin
        state<=IDLE;lease<=0;lease_write<=0;payload_done<=0;fence_done<=0;
        lease_key<=0;lease_length<=0;lease_offset<=0;lease_tag<=0;next_tag<=1;exhausted<=0;
        logical_write<=0;logical_fence<=0;outstanding<=0;remaining<=0;offset<=0;ram_offset<=0;
        m_status_write<=0;m_status_tag<=0;m_status_error<=0;m_status_valid<=0;
        m_descriptor_write<=0;m_descriptor_address<=0;m_descriptor_ram_address<=0;
        m_descriptor_length<=0;m_descriptor_tag<=0;fault<=0;fault_code<=0;descriptor_count<=0;
    end else begin
        m_status_valid<=0;
        if(unexpected_status) begin fault<=1;if(!fault) fault_code<=ERR_STATUS;end
        if(halt) begin fault<=1;if(!fault) fault_code<=ERR_HALT;end
        if(release_lease) begin
            if(release_ok && !fault && !unexpected_status && !halt)
                lease<=0;
            else begin fault<=1;if(!fault) fault_code<=ERR_RELEASE;end
        end
        if(fault || halt || unexpected_status || bad_release) begin
            // Preserve the outstanding descriptor/RAM lease. No success or
            // memory-release proof is manufactured by a wrong/late status.
            case(state)
                QUERY: if(m_query_ready) state<=TABLE_WAIT;
                TABLE_WAIT: if(s_segment_valid) state<=FAILED;
                ISSUE: if(m_descriptor_ready) begin outstanding<=1;state<=DMA_WAIT;end
                DMA_WAIT: if(s_status_valid && matching_status) begin outstanding<=0;state<=FAILED;end
                default: state<=FAILED;
            endcase
        end else case(state)
            IDLE: begin
                if(s_lease_valid && s_lease_ready) begin
                    lease<=1;lease_write<=s_lease_write;lease_key<=s_lease_key;
                    lease_offset<=s_lease_offset;lease_length<=s_lease_length;lease_tag<=s_lease_tag;
                    payload_done<=0;fence_done<=0;
                    if(!lease_shape) begin fault<=1;fault_code<=ERR_LEASE;state<=FAILED;end
                end
                if(s_descriptor_valid && s_descriptor_ready) begin
                    logical_write<=s_descriptor_write;logical_fence<=fence_shape;
                    offset<=s_descriptor_offset;remaining<=s_descriptor_length;ram_offset<=s_descriptor_ram_address;
                    if(!descriptor_shape) begin
                        fault<=1;fault_code<=ERR_DESCRIPTOR;state<=FAILED;
                        m_status_write<=s_descriptor_write;m_status_tag<=s_descriptor_tag;m_status_error<=15;m_status_valid<=1;
                    end else state<=QUERY;
                end
            end
            QUERY: if(m_query_ready) state<=TABLE_WAIT;
            TABLE_WAIT: if(s_segment_valid) begin
                if(s_segment_error!=0 || s_segment_tag!=lease_tag || s_segment_length==0 ||
                    s_segment_length>remaining || s_segment_length>4096 ||
                    s_segment_length>13'd4096-{1'b0,s_segment_dma_address[11:0]}) begin
                    fault<=1;fault_code<=ERR_TABLE;state<=FAILED;
                    m_status_write<=logical_write;m_status_tag<=lease_tag;m_status_error<=15;m_status_valid<=1;
                end else if(exhausted) begin
                    fault<=1;fault_code<=ERR_TAGS;state<=FAILED;
                    m_status_write<=logical_write;m_status_tag<=lease_tag;m_status_error<=15;m_status_valid<=1;
                end else begin
                    m_descriptor_write<=logical_write;m_descriptor_address<=s_segment_dma_address;
                    m_descriptor_ram_address<=ram_offset;m_descriptor_length<=s_segment_length;
                    m_descriptor_tag<=next_tag;
                    if(next_tag==16'hffff) exhausted<=1;else next_tag<=next_tag+1'b1;
                    state<=ISSUE;
                end
            end
            ISSUE: if(m_descriptor_ready) begin outstanding<=1;descriptor_count<=descriptor_count+1'b1;state<=DMA_WAIT;end
            DMA_WAIT: if(s_status_valid && matching_status) begin
                outstanding<=0;
                if(s_status_error!=0) begin
                    fault<=1;fault_code<=ERR_STATUS;state<=FAILED;
                    m_status_write<=logical_write;m_status_tag<=lease_tag;m_status_error<=s_status_error;m_status_valid<=1;
                end else if(remaining==m_descriptor_length) begin
                    if(logical_fence) fence_done<=1;else payload_done<=1;
                    m_status_write<=logical_write;m_status_tag<=lease_tag;m_status_error<=0;m_status_valid<=1;state<=IDLE;
                end else begin
                    remaining<=remaining-m_descriptor_length;offset<=offset+m_descriptor_length;
                    ram_offset<=ram_offset+m_descriptor_length;state<=QUERY;
                end
            end
            default: begin end
        endcase
    end
end
endmodule
`resetall
