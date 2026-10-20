// SPDX-License-Identifier: BSD-2-Clause-Views
// Two independent owned SQ/RQ control mailboxes -> one real DMA fetch engine.
// Immutable request/response owner is retained across stalls. Accepting this
// arbiter's input is NOT a successful hardware configuration/drain proof.
`resetall
`timescale 1ns/1ps
`default_nettype none
module rocev2_queue_cfg_arbiter (
    input wire clk,
    input wire rst,
    input wire [475:0] s_command,
    input wire [1:0] s_valid,
    output wire [1:0] s_ready,
    output wire [319:0] s_response,
    output wire [1:0] s_response_valid,
    input wire [1:0] s_response_ready,
    output wire [237:0] m_command,
    output wire m_receive,
    output wire m_valid,
    input wire m_ready,
    input wire [159:0] m_response,
    input wire m_response_valid,
    output wire m_response_ready,
    output wire busy,
    output reg fault=0
);
localparam IDLE=0,OFFER=1,WAIT=2;
reg [1:0] state=IDLE;
reg owner=0,preferred=0;
reg [237:0] held=0;
wire chosen=s_valid[preferred] ? preferred : !preferred;
wire valid_known=(^s_valid)!==1'bx;
wire command_known=(^s_command[chosen*238+:238])!==1'bx;
wire bad_response=m_response_valid && state!=WAIT;
assign s_ready=state==IDLE && !fault && valid_known && command_known && !m_response_valid && !rst ?
    (chosen ? 2'b10 : 2'b01) : 2'b00;
assign m_command=held;
assign m_receive=owner;
assign m_valid=state==OFFER && !rst;
assign m_response_ready=state==WAIT && s_response_ready[owner] && !fault && !rst;
assign s_response_valid=state==WAIT && m_response_valid && !fault && !rst ? (owner ? 2'b10 : 2'b01):0;
assign s_response={owner ? m_response : 160'd0,owner ? 160'd0 : m_response};
assign busy=state!=IDLE || fault;
always @(posedge clk)begin
    if(rst)begin state<=IDLE;owner<=0;preferred<=0;held<=0;fault<=0;end
    else begin
        if(!valid_known || bad_response || (state==IDLE && s_valid[chosen] && !command_known))fault<=1;
        case(state)
        IDLE:if(s_valid[chosen] && s_ready[chosen])begin owner<=chosen;held<=s_command[chosen*238+:238];state<=OFFER;end
        OFFER:if(m_valid && m_ready)state<=WAIT;
        WAIT:if(m_response_valid && m_response_ready)begin preferred<=!owner;state<=IDLE;end
        default:fault<=1;
        endcase
    end
end
endmodule
`resetall
