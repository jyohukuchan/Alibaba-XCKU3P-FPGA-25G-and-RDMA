// SPDX-License-Identifier: BSD-2-Clause-Views
// Actual post-integrity IPv4/UDP/BTH output: requests go to local WR/MAC
// lifetime, ACK/READ responses to protected responder/MAC lifetime. Hold both
// header beats before selecting, preserving exact wire bytes and packet lock.
// Direction is routing, NOT QP/MR/DMA authority or a completion certificate.
`resetall
`timescale 1ns/1ps
`default_nettype none
module rocev2_duplex_tx_router(
    input wire clk,input wire rst,input wire local_owned,input wire remote_owned,
    input wire [127:0] s_data,input wire [15:0] s_keep,input wire s_valid,
    output wire s_ready,input wire s_last,
    output wire [127:0] m_local_data,output wire [15:0] m_local_keep,
    output wire m_local_valid,input wire m_local_ready,output wire m_local_last,
    output wire [127:0] m_remote_data,output wire [15:0] m_remote_keep,
    output wire m_remote_valid,input wire m_remote_ready,output wire m_remote_last,
    output wire local_busy,output wire remote_busy,
    output reg fault=0
);
localparam FIRST=0,SECOND=1,HEADER0=2,HEADER1=3,BODY=4;
reg [2:0] state=FIRST;
reg [127:0] header0=0,header1=0;
reg local_packet=0;
wire [7:0] opcode=s_data[103:96];
wire request=opcode<=8'h0c;
wire response=opcode>=8'h0d && opcode<=8'h12;
wire bad_header=s_valid && (state==FIRST || state==SECOND) &&
    ((^{s_keep,s_last})===1'bx || s_keep!=16'hffff || s_last ||
     (state==FIRST && s_data[7:0]!==8'h45) ||
     (state==SECOND && ((^opcode)===1'bx || !(request || response) ||
       (request ? local_owned!==1'b1:remote_owned!==1'b1))));
wire bad_owner=state>=HEADER0 && (local_packet ? local_owned!==1'b1:remote_owned!==1'b1);
wire stopped=rst || fault || bad_header || bad_owner;
wire [127:0] data=state==HEADER0 ? header0:state==HEADER1 ? header1:s_data;
wire [15:0] keep=state==BODY ? s_keep:16'hffff;
wire last=state==BODY && s_last;
wire valid=state>=HEADER0 && (state!=BODY || s_valid) && !stopped;
wire ready=local_packet ? m_local_ready:m_remote_ready;
assign m_local_data=data;assign m_remote_data=data;
assign m_local_keep=keep;assign m_remote_keep=keep;
assign m_local_last=last;assign m_remote_last=last;
assign m_local_valid=valid && local_packet;assign m_remote_valid=valid && !local_packet;
assign s_ready=!stopped && (state<=SECOND || (state==BODY && ready));
assign local_busy=(state>=HEADER0 && local_packet) || fault;
assign remote_busy=(state>=HEADER0 && !local_packet) || fault;
always @(posedge clk)begin
    if(rst)begin state<=FIRST;local_packet<=0;header0<=0;header1<=0;fault<=0;end
    else begin
        if(bad_header || bad_owner)fault<=1;
        if(s_valid && s_ready && state==FIRST)begin header0<=s_data;state<=SECOND;end
        if(s_valid && s_ready && state==SECOND)begin header1<=s_data;local_packet<=request;state<=HEADER0;end
        if(valid && ready)begin
            if(state==HEADER0)state<=HEADER1;
            else if(state==HEADER1)state<=BODY;
            else if(last)state<=FIRST;
        end
    end
end
endmodule
`resetall
