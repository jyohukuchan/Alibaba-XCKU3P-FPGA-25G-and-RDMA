// SPDX-License-Identifier: BSD-2-Clause-Views
// Private zero-RQ ingress adapter, AFTER Ethernet header stripping and BEFORE
// unchanged whole-IP integrity. SEND_ONLY IP44 needs two Ethernet pad bytes
// to reach the60-byte Ethernet minimum (without FCS). They are not IP/ICRC.
// Only this exact complete shape loses those two bytes; every other input,
// error bit and malformed length/keep reaches the original integrity checks.
`resetall
`timescale 1ns/1ps
`default_nettype none
module rocev2_zero_rx_padding(
    input wire clk,input wire rst,
    input wire [127:0] s_axis_tdata,input wire [15:0] s_axis_tkeep,
    input wire s_axis_tvalid,output wire s_axis_tready,
    input wire s_axis_tlast,input wire s_axis_tuser,
    output wire [127:0] m_axis_tdata,output wire [15:0] m_axis_tkeep,
    output wire m_axis_tvalid,input wire m_axis_tready,
    output wire m_axis_tlast,output wire m_axis_tuser
);
reg first=1,ip44=0,send_only=0;
reg [15:0] offset=0;
wire padded=ip44===1'b1 && send_only===1'b1 && offset==32 &&
    s_axis_tlast===1'b1 && s_axis_tkeep===16'h3fff;
assign m_axis_tdata=s_axis_tdata;
assign m_axis_tkeep=padded ? 16'h0fff:s_axis_tkeep;
assign m_axis_tlast=s_axis_tlast;
assign m_axis_tuser=s_axis_tuser;
assign m_axis_tvalid=s_axis_tvalid && !rst;
assign s_axis_tready=m_axis_tready && !rst;
always @(posedge clk)begin
    if(rst)begin first<=1;ip44<=0;send_only<=0;offset<=0;end
    else if(s_axis_tvalid && s_axis_tready)begin
        if(first)ip44<=s_axis_tdata[7:0]===8'h45 &&
            {s_axis_tdata[23:16],s_axis_tdata[31:24]}===16'd44;
        if(!first && offset==16)send_only<=s_axis_tdata[103:96]===8'h04 &&
            s_axis_tdata[109:108]===2'd0;
        if(s_axis_tlast)begin first<=1;ip44<=0;send_only<=0;offset<=0;end
        else begin first<=0;if(offset<16'hfff0)offset<=offset+16'd16;end
    end
end
endmodule
`resetall
