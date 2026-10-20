// SPDX-License-Identifier: BSD-2-Clause-Views
// Copyright (c) 2026 jyohukuchan
// Staged8x256-page DMA translation table,4096B pages/full64-bit DMA bases.
// A query is a TRUSTED MR-authorized slot/key/offset/remaining-length lease.
// This does NOT replace the QP/PD/access/full-VA authorization engine.
// Caller MUST block new MR admission during configuration and retain mapped
// pages until MR invalidation + all memory leases drain. cfg_quiescent covers
// those leases, not just this FSM. No PCIe DMA is performed by this module.
`resetall
`timescale 1ns / 1ps
`default_nettype none
module rocev2_mr_page_table (
    input wire clk,
    input wire rst,
    input wire cfg_quiescent,
    // BEGIN1, PAGE2, SEAL3, INVALIDATE4. BEGIN uses an ALLOCATED MR key.
    input wire [2:0] cfg_command,
    input wire [2:0] cfg_slot,
    input wire [31:0] cfg_key,
    input wire [31:0] cfg_length,
    input wire [11:0] cfg_first_offset,
    input wire [7:0] cfg_page_index,
    input wire [63:0] cfg_dma_page,
    input wire cfg_valid,
    output wire cfg_ready,
    output reg [7:0] cfg_response_error=0,
    output reg [31:0] cfg_response_key=0,
    output reg cfg_response_valid=0,
    input wire cfg_response_ready,
    input wire [2:0] s_query_slot,
    input wire [31:0] s_query_key,
    input wire [63:0] s_query_offset,
    input wire [31:0] s_query_length,
    input wire [15:0] s_query_tag,
    input wire s_query_valid,
    output wire s_query_ready,
    output reg [15:0] m_segment_tag=0,
    output reg [7:0] m_segment_error=0,
    output reg [63:0] m_segment_dma_address=0,
    output reg [12:0] m_segment_length=0,
    output wire m_segment_valid,
    input wire m_segment_ready
);
localparam IDLE=0,CFG_APPLY=1,Q_RANGE=2,Q_CHECK=3,Q_MEMORY=4,Q_TRANSLATE=5,RESPONSE=6;
localparam OK=0,ERR_KEY=1,ERR_RANGE=4,ERR_OPERATION=5,ERR_BUSY=6,
    ERR_CONFIG=8,ERR_DUPLICATE=9,ERR_STATE=10;
reg [2:0] state=IDLE;
reg active_table[0:7],building_table[0:7];
reg [31:0] key_table[0:7];
reg [20:0] length_table[0:7];
reg [11:0] first_table[0:7];
reg [8:0] count_table[0:7],loaded_table[0:7];
reg [255:0] present_table[0:7];
(* ram_style="block" *) reg [63:0] page_memory[0:2047];
reg [2:0] management_command=0,management_slot=0;
reg [31:0] management_key=0,management_length=0;
reg [11:0] management_first=0;
reg [7:0] management_index=0;
reg [63:0] management_dma=0;
wire [21:0] management_span={1'b0,management_length[20:0]}+{10'd0,management_first};
wire [9:0] expected_pages=management_span[21:12]+(|management_span[11:0]);
reg query_active=0;
reg [31:0] query_key=0,query_saved_key=0,query_length=0;
reg [2:0] query_slot=0;
reg [63:0] query_offset=0;
reg [20:0] query_saved_length=0;
reg [11:0] query_first=0,query_page_offset=0;
reg [15:0] query_tag=0;
reg query_offset_ok=0;
reg [21:0] query_remaining=0,query_linear=0;
reg [7:0] query_page=0;
reg [12:0] query_piece=0;
reg [63:0] query_dma_page=0;
reg query_present=0;
wire [12:0] bytes_in_page=13'd4096-{1'b0,query_linear[11:0]};

assign cfg_ready=state==IDLE && !cfg_response_valid && cfg_quiescent && !rst;
wire cfg_transfer=cfg_valid && cfg_ready;
assign s_query_ready=state==IDLE && !cfg_response_valid && !cfg_transfer && !rst;
assign m_segment_valid=state==RESPONSE && !rst;
integer i;
always @(posedge clk) begin
    if(rst) begin
        state<=IDLE;cfg_response_error<=0;cfg_response_key<=0;cfg_response_valid<=0;
        m_segment_tag<=0;m_segment_error<=0;m_segment_dma_address<=0;m_segment_length<=0;
        management_command<=0;management_slot<=0;management_key<=0;management_length<=0;
        management_first<=0;management_index<=0;management_dma<=0;
        query_active<=0;query_key<=0;query_saved_key<=0;query_length<=0;query_slot<=0;
        query_offset<=0;query_saved_length<=0;query_first<=0;query_page_offset<=0;query_tag<=0;
        query_offset_ok<=0;query_remaining<=0;query_linear<=0;query_page<=0;query_piece<=0;
        query_dma_page<=0;query_present<=0;
        for(i=0;i<8;i=i+1) begin
            active_table[i]<=0;building_table[i]<=0;key_table[i]<=0;length_table[i]<=0;
            first_table[i]<=0;count_table[i]<=0;loaded_table[i]<=0;present_table[i]<=0;
        end
    end else begin
        if(cfg_response_valid && cfg_response_ready) cfg_response_valid<=0;
        case(state)
            IDLE: if(cfg_transfer) begin
                management_command<=cfg_command;management_slot<=cfg_slot;management_key<=cfg_key;
                management_length<=cfg_length;management_first<=cfg_first_offset;
                management_index<=cfg_page_index;management_dma<=cfg_dma_page;state<=CFG_APPLY;
            end else if(s_query_valid && s_query_ready) begin
                query_active<=active_table[s_query_slot];query_saved_key<=key_table[s_query_slot];
                query_saved_length<=length_table[s_query_slot];query_first<=first_table[s_query_slot];
                query_key<=s_query_key;query_slot<=s_query_slot;query_offset<=s_query_offset;
                query_length<=s_query_length;query_tag<=s_query_tag;state<=Q_RANGE;
            end
            CFG_APPLY: begin
                cfg_response_valid<=1;cfg_response_error<=OK;cfg_response_key<=0;state<=IDLE;
                if(!cfg_quiescent) cfg_response_error<=ERR_BUSY;
                else case(management_command)
                    1: begin
                        if(active_table[management_slot] || building_table[management_slot]) cfg_response_error<=ERR_BUSY;
                        else if(management_key[2:0]!=management_slot || management_key[31:3]<=key_table[management_slot][31:3])
                            cfg_response_error<=ERR_KEY;
                        else if(management_length==0 || management_length[31:21]!=0 || management_span>22'd1048576)
                            cfg_response_error<=ERR_CONFIG;
                        else begin
                            key_table[management_slot]<=management_key;length_table[management_slot]<=management_length[20:0];
                            first_table[management_slot]<=management_first;count_table[management_slot]<=expected_pages[8:0];
                            loaded_table[management_slot]<=0;present_table[management_slot]<=0;
                            building_table[management_slot]<=1;cfg_response_key<=management_key;
                        end
                    end
                    2: begin
                        if(management_key!=key_table[management_slot]) cfg_response_error<=ERR_KEY;
                        else if(!building_table[management_slot]) cfg_response_error<=ERR_STATE;
                        else if({1'b0,management_index}>=count_table[management_slot] || management_dma[11:0]!=0)
                            cfg_response_error<=ERR_CONFIG;
                        else if(present_table[management_slot][management_index]) cfg_response_error<=ERR_DUPLICATE;
                        else begin
                            page_memory[{management_slot,management_index}]<=management_dma;
                            present_table[management_slot][management_index]<=1;
                            loaded_table[management_slot]<=loaded_table[management_slot]+1'b1;
                            cfg_response_key<=management_key;
                        end
                    end
                    3: begin
                        if(management_key!=key_table[management_slot]) cfg_response_error<=ERR_KEY;
                        else if(!building_table[management_slot] || loaded_table[management_slot]!=count_table[management_slot])
                            cfg_response_error<=ERR_STATE;
                        else begin
                            building_table[management_slot]<=0;active_table[management_slot]<=1;cfg_response_key<=management_key;
                        end
                    end
                    4: begin
                        if(management_key!=key_table[management_slot]) cfg_response_error<=ERR_KEY;
                        else begin
                            active_table[management_slot]<=0;building_table[management_slot]<=0;
                            length_table[management_slot]<=0;first_table[management_slot]<=0;
                            count_table[management_slot]<=0;loaded_table[management_slot]<=0;present_table[management_slot]<=0;
                            // Retain key generation. A later BEGIN must be newer.
                            cfg_response_key<=management_key;
                        end
                    end
                    default: cfg_response_error<=ERR_OPERATION;
                endcase
            end
            Q_RANGE: begin
                query_offset_ok<=query_offset[63:21]==0 && query_offset[20:0]<query_saved_length;
                query_remaining<={1'b0,query_saved_length}-{1'b0,query_offset[20:0]};
                query_linear<={1'b0,query_offset[20:0]}+{10'd0,query_first};
                state<=Q_CHECK;
            end
            Q_CHECK: begin
                m_segment_tag<=query_tag;m_segment_error<=OK;m_segment_dma_address<=0;m_segment_length<=0;
                if(!query_active || query_key!=query_saved_key || query_key[2:0]!=query_slot) begin
                    m_segment_error<=ERR_KEY;state<=RESPONSE;
                end else if(!query_offset_ok || query_length==0 || {1'b0,query_length}>{11'd0,query_remaining} || query_linear[21:20]!=0) begin
                    m_segment_error<=ERR_RANGE;state<=RESPONSE;
                end else begin
                    query_page<=query_linear[19:12];query_page_offset<=query_linear[11:0];
                    query_piece<=query_length<bytes_in_page ? query_length[12:0] : bytes_in_page;state<=Q_MEMORY;
                end
            end
            Q_MEMORY: begin
                query_dma_page<=page_memory[{query_slot,query_page}];
                query_present<=present_table[query_slot][query_page];state<=Q_TRANSLATE;
            end
            Q_TRANSLATE: begin
                if(!query_present || query_dma_page[11:0]!=0) m_segment_error<=ERR_CONFIG;
                else begin
                    // Aligned page base + byte offset, with NO48-bit truncation.
                    m_segment_dma_address<={query_dma_page[63:12],query_page_offset};m_segment_length<=query_piece;
                end
                state<=RESPONSE;
            end
            RESPONSE: if(m_segment_ready) state<=IDLE;
            default: state<=IDLE;
        endcase
    end
end
endmodule
`resetall
