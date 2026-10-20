// SPDX-License-Identifier: BSD-2-Clause-Views
// After ACTUAL whole-packet integrity: hold two header beats, route only
// Atomic0x13/14 to its native guard. All other traffic retains normal parser.
// Classification is NOT QP/PD/epoch/MR/PSN authority. No payload rewriting.
`resetall
`timescale 1ns/1ps
`default_nettype none
module rocev2_native_atomic_rx_router (
    input wire clk,input wire rst,
    input wire [127:0] s_data,input wire [15:0] s_keep,input wire s_valid,
    output wire s_ready,input wire s_last,
    output wire [127:0] m_normal_data,output wire [15:0] m_normal_keep,
    output wire m_normal_valid,input wire m_normal_ready,output wire m_normal_last,
    output wire [127:0] m_atomic_data,output wire [15:0] m_atomic_keep,
    output wire m_atomic_valid,input wire m_atomic_ready,output wire m_atomic_last,
    output wire configuration_guard,output reg fault=0
);
localparam FIRST=0,SECOND=1,HEADER0=2,HEADER1=3,BODY=4;
reg [2:0] state=FIRST;
reg [127:0] header0=0,header1=0;
reg atomic_packet=0;
wire [7:0] opcode=s_data[103:96];
wire [127:0] data=state==HEADER0 ? header0:state==HEADER1 ? header1:s_data;
wire [15:0] keep=state==BODY ? s_keep:16'hffff;
wire last=state==BODY && s_last;
// Buffered/offered beats do not retract under late fault.
wire valid=state>=HEADER0 && (state!=BODY || s_valid) && !rst;
wire ready=atomic_packet ? m_atomic_ready:m_normal_ready;
assign m_normal_data=data;assign m_atomic_data=data;
assign m_normal_keep=keep;assign m_atomic_keep=keep;
assign m_normal_last=last;assign m_atomic_last=last;
assign m_normal_valid=valid && !atomic_packet;assign m_atomic_valid=valid && atomic_packet;
assign s_ready=!rst && (state<=SECOND ? !fault:(state==BODY && ready));
assign configuration_guard=state!=FIRST || fault || s_valid!==1'b0;
wire bad_header=s_valid && s_ready && state<=SECOND &&
    ((^{s_keep,s_last})===1'bx || s_keep!=16'hffff || s_last ||
     (state==FIRST && s_data[7:0]!==8'h45) || (state==SECOND && (^opcode)===1'bx));
always @(posedge clk)begin
    if(rst)begin state<=FIRST;header0<=0;header1<=0;atomic_packet<=0;fault<=0;end
    else begin
        if(bad_header || (s_valid!==1'b0 && s_valid!==1'b1))fault<=1;
        if(s_valid && s_ready && !bad_header && state==FIRST)begin header0<=s_data;state<=SECOND;end
        if(s_valid && s_ready && !bad_header && state==SECOND)begin
            header1<=s_data;atomic_packet<=opcode==8'h13 || opcode==8'h14;state<=HEADER0;
        end
        if(valid && ready)begin
            if(state==HEADER0)state<=HEADER1;
            else if(state==HEADER1)state<=BODY;
            else if(last)state<=FIRST;
        end
    end
end
endmodule
`resetall
