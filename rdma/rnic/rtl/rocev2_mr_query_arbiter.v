// SPDX-License-Identifier: BSD-2-Clause-Views
// Copyright (c) 2026 jyohukuchan
// Two trusted clients, ONE MR validator/namespace. A query response is not a
// released memory lease: client/downstream guards MUST outlive this arbiter.
// Reset is not a DMA-drain or host-unpin certificate.
`resetall
`timescale 1ns/1ps
`default_nettype none
module rocev2_mr_query_arbiter (
    input wire clk,
    input wire rst,
    input wire [31:0] s_request_pd,
    input wire [63:0] s_request_key,
    input wire [127:0] s_request_address,
    input wire [63:0] s_request_length,
    input wire [5:0] s_request_operation,
    input wire [31:0] s_request_tag,
    input wire [1:0] s_request_valid,
    output wire [1:0] s_request_ready,
    output wire [31:0] m_response_tag,
    output wire [15:0] m_response_error,
    output wire [127:0] m_response_offset,
    output wire [127:0] m_response_dma_address,
    output wire [63:0] m_response_length,
    output wire [1:0] m_response_valid,
    input wire [1:0] m_response_ready,
    output wire [15:0] m_request_pd,
    output wire [31:0] m_request_key,
    output wire [63:0] m_request_address,
    output wire [31:0] m_request_length,
    output wire [2:0] m_request_operation,
    output wire [15:0] m_request_tag,
    output wire m_request_valid,
    input wire m_request_ready,
    input wire [15:0] s_response_tag,
    input wire [7:0] s_response_error,
    input wire [63:0] s_response_offset,
    input wire [63:0] s_response_dma_address,
    input wire [31:0] s_response_length,
    input wire s_response_valid,
    output wire s_response_ready,
    output wire busy,
    output reg fault=0,
    output reg [7:0] fault_code=0
);
localparam [1:0] IDLE=0, SEND=1, WAIT=2, FAULT=3;
reg [1:0] state=IDLE;
reg preferred=0,owner=0;
reg [15:0] pd=0,tag=0;
reg [31:0] key=0,length=0;
reg [63:0] address=0;
reg [2:0] operation=0;
wire chosen=s_request_valid[preferred] ? preferred : !preferred;
wire accept=state==IDLE && !fault && !s_response_valid && !rst;
assign s_request_ready=accept ? (chosen ? 2'b10 : 2'b01) : 2'b00;
assign m_request_pd=pd;
assign m_request_key=key;
assign m_request_address=address;
assign m_request_length=length;
assign m_request_operation=operation;
assign m_request_tag=tag;
// Even a protocol fault cannot retract a query already offered under stall.
assign m_request_valid=state==SEND && !rst;
reg response_ok;
always @* begin
    response_ok=0;
    case(s_response_tag==tag)
    1'b1: case(s_response_error)
        0: case(s_response_length==length)
            1'b1: response_ok=1;
            default: response_ok=0;
        endcase
        1,2,3,4,5,6,7,8,9,10: response_ok=1;
        default: response_ok=0;
    endcase
    default: response_ok=0;
    endcase
end
wire response_valid=state==WAIT && !fault && response_ok && s_response_valid && !rst;
assign m_response_valid=response_valid ? (owner ? 2'b10 : 2'b01) : 2'b00;
assign s_response_ready=state==WAIT && !fault && response_ok && m_response_ready[owner] && !rst;
genvar c;
generate for(c=0;c<2;c=c+1) begin: client
    // Never expose another client's result or stale translated fields.
    assign m_response_tag[c*16+:16]=m_response_valid[c] ? s_response_tag : 16'd0;
    assign m_response_error[c*8+:8]=m_response_valid[c] ? s_response_error : 8'd0;
    assign m_response_offset[c*64+:64]=m_response_valid[c] && s_response_error==0 ? s_response_offset : 64'd0;
    assign m_response_dma_address[c*64+:64]=m_response_valid[c] && s_response_error==0 ? s_response_dma_address : 64'd0;
    assign m_response_length[c*32+:32]=m_response_valid[c] && s_response_error==0 ? s_response_length : 32'd0;
end endgenerate
assign busy=state!=IDLE || fault;
always @(posedge clk) begin
    if(rst) begin
        state<=IDLE;preferred<=0;owner<=0;pd<=0;tag<=0;key<=0;length<=0;
        address<=0;operation<=0;fault<=0;fault_code<=0;
    end else begin
        if(s_response_valid && (state!=WAIT || !response_ok)) begin
            fault<=1;fault_code<=8'h40;
        end
        case(state)
        IDLE: if(s_response_valid || fault) state<=FAULT;
        else if(s_request_valid[chosen] && s_request_ready[chosen]) begin
            owner<=chosen;pd<=s_request_pd[chosen*16+:16];tag<=s_request_tag[chosen*16+:16];
            key<=s_request_key[chosen*32+:32];length<=s_request_length[chosen*32+:32];
            address<=s_request_address[chosen*64+:64];operation<=s_request_operation[chosen*3+:3];state<=SEND;
        end
        SEND: if(m_request_valid && m_request_ready)
            state<=fault || s_response_valid ? FAULT : WAIT;
        WAIT: if(fault || (s_response_valid && !response_ok)) state<=FAULT;
        else if(response_valid && s_response_ready) begin preferred<=!owner;state<=IDLE;end
        FAULT: state<=FAULT;
        default: begin fault<=1;fault_code<=8'h41;state<=FAULT;end
        endcase
    end
end
endmodule
`resetall
