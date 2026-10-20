// SPDX-License-Identifier: BSD-2-Clause-Views
// One immutable admitted owner, MAC reservation FIRST, HLS ownership SECOND.
// Input is already admitted: a later new-admission disable must not retract
// either offered AXIS word. Faults retain the configuration/queue lease.
// This is NOT execution/core/MAC retirement, cancellation or safe unpin proof.
`resetall
`timescale 1ns/1ps
`default_nettype none
module rocev2_atomic_owner_reservation (
    input wire clk,input wire rst,input wire parent_fault,
    input wire [327:0] s_owner,input wire s_valid,output wire s_ready,
    output wire [327:0] m_mac_owner,output wire m_mac_valid,input wire m_mac_ready,
    output wire [143:0] m_hls_owner,output wire m_hls_valid,input wire m_hls_ready,
    output wire configuration_guard,output wire [7:0] queue_guard,
    output reg fault=0,output reg [31:0] reserved_count=0,
    output reg [31:0] delivered_count=0
);
localparam IDLE=0,MAC=1,HLS=2;
reg [1:0] state=IDLE;
reg [327:0] owner=0;
wire halted=fault || parent_fault!==1'b0;
wire valid_known=s_valid===1'b0 || s_valid===1'b1;
wire owner_known=(^s_owner)!==1'bx;
wire owner_ok=owner_known && s_owner[23:0]<8 && s_owner[87:24]!=0 && s_owner[143:112]!=0 &&
    s_owner[327:280]!=0 && !s_owner[320] && s_owner[279:232]!=0 && !s_owner[272];
wire bad_offer=!valid_known || (state==IDLE && s_valid && !owner_ok);
assign s_ready=state==IDLE && !halted && !rst && owner_ok;
assign m_mac_owner=owner;assign m_hls_owner=owner[143:0];
// Once offered, valid/payload remain until the real consumer handshake even
// under a late fault. The actual MAC refuses reservation when it is faulted;
// this module never infers a reservation from ready/quiet alone.
assign m_mac_valid=state==MAC && !rst;
assign m_hls_valid=state==HLS && !rst;
assign configuration_guard=state!=IDLE || halted || s_valid!==1'b0;
assign queue_guard=(halted || bad_offer) ? 8'hff : state!=IDLE ? (8'h01<<owner[23:0]) :
    (s_valid && owner_ok) ? (8'h01<<s_owner[23:0]):8'd0;
always @(posedge clk)begin
    if(rst)begin state<=IDLE;owner<=0;fault<=0;reserved_count<=0;delivered_count<=0;end
    else begin
        if(s_valid && s_ready)begin owner<=s_owner;state<=MAC;end
        if(m_mac_valid && m_mac_ready)begin
            state<=HLS;reserved_count<=reserved_count+1'b1;
        end
        if(m_hls_valid && m_hls_ready)begin
            delivered_count<=delivered_count+1'b1;
            if(!halted && !bad_offer)begin state<=IDLE;owner<=0;end
            // Offered HLS transfer can finish under late fault, but must not
            // be offered a second time. Retain a faulted idle guard instead.
            else begin state<=IDLE;fault<=1;end
        end
        if(parent_fault!==1'b0 || bad_offer)fault<=1;
    end
end
endmodule
`resetall
