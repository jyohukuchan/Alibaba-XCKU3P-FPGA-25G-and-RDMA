// SPDX-License-Identifier: BSD-2-Clause-Views
// Real raw-IP admission -> whole-frame integrity outcome reference tracking.
// Hold privileged context until ALL accepted RX frames leave the checker or
// are actually dropped. Downstream packet/core/MAC guards MUST outlive this.
// Neither these references nor an empty FIFO certify cancellation/unpin.
`resetall
`timescale 1ns/1ps
`default_nettype none
module rocev2_native_rx_refs (
    input wire clk,input wire rst,input wire enable,input wire parent_fault,
    input wire trusted_valid,input wire [351:0] trusted_context,
    input wire [127:0] s_data,input wire [15:0] s_keep,input wire s_valid,
    output wire s_ready,input wire s_last,input wire s_user,
    output wire [127:0] m_data,output wire [15:0] m_keep,output wire m_valid,
    input wire m_ready,output wire m_last,output wire m_user,
    input wire checked_eof,input wire checker_drop,
    output reg [351:0] held_context=0,
    output wire configuration_guard,output wire [7:0] queue_guard,
    output reg [15:0] references=0,output reg fault=0
);
reg granted=0,in_frame=0;
wire halted=fault || parent_fault!==1'b0;
wire context_known=(^trusted_context)!==1'bx;
wire context_ok=context_known && trusted_context[23:0]<24'd8 &&
    trusted_context[39:24]!=0 && trusted_context[103:40]!=0 && trusted_context[167:104]!=0;
wire context_stable=references==0 || trusted_context===held_context;
wire can_new=enable===1'b1 && trusted_valid===1'b1 && context_ok && context_stable && !halted && !rst;
wire first_offer=!granted && !in_frame && can_new && s_valid===1'b1;
// Once offered to the checker, no enable/fault/context transition retracts
// an AXIS beat. Even a quarantined owner can drain an already offered frame.
wire gate=granted || in_frame || can_new;
assign m_data=s_data;assign m_keep=s_keep;assign m_last=s_last;assign m_user=s_user;
assign m_valid=s_valid && gate && !rst;
assign s_ready=m_ready && gate && !rst;
wire fire=s_valid && s_ready;
wire acquire=fire && !in_frame;
wire [1:0] release_count={1'b0,checked_eof}+{1'b0,checker_drop};
wire [16:0] available={1'b0,references}+{16'd0,acquire};
wire accounting_known=(^{checked_eof,checker_drop,s_valid,m_ready})!==1'bx;
wire accounting_ok=accounting_known && available>={15'd0,release_count} &&
    available-{15'd0,release_count}<=17'd65535;
assign configuration_guard=references!=0 || granted || in_frame || first_offer || halted;
assign queue_guard=halted ? 8'hff : configuration_guard ?
    (8'h01<<(first_offer && references==0 ? trusted_context[23:0]:held_context[23:0])):8'd0;
always @(posedge clk)begin
    if(rst)begin granted<=0;in_frame<=0;held_context<=0;references<=0;fault<=0;end
    else begin
        if(first_offer)begin
            granted<=1;
            if(references==0)held_context<=trusted_context;
        end
        if(fire)begin granted<=0;in_frame<=!s_last;end
        if(accounting_ok)references<=available[15:0]-{14'd0,release_count};
        if(parent_fault!==1'b0 || !accounting_ok ||
            (enable===1'b1 && trusted_valid===1'b1 && !granted && !in_frame && s_valid &&
                (!context_ok || !context_stable)) ||
            (fire && (^{s_keep,s_last,s_user})===1'bx))fault<=1;
    end
end
endmodule
`resetall
