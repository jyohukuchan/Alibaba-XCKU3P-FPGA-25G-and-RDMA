// SPDX-License-Identifier: BSD-2-Clause-Views
// Normalize the pinned FNS core's UNPADDED IPv4 RoCE output, before ICRC.
// Input IP/UDP lengths include the future four-byte ICRC, but omit padding;
// BTH pad count must be zero. Add zero padding and repair both lengths/BTH.
// IPv4 checksum is subsequently repaired by rocev2_ipv4_icrc TX. This block
// never makes malformed input trustworthy: mark it bad for that frame FIFO.
`resetall
`timescale 1ns / 1ps
`default_nettype none
module rocev2_tx_padding (
    input wire clk,
    input wire rst,
    input wire [127:0] s_axis_tdata,
    input wire [15:0] s_axis_tkeep,
    input wire s_axis_tvalid,
    output wire s_axis_tready,
    input wire s_axis_tlast,
    input wire s_axis_tuser,
    output reg [127:0] m_axis_tdata=0,
    output reg [15:0] m_axis_tkeep=0,
    output reg m_axis_tvalid=0,
    input wire m_axis_tready,
    output reg m_axis_tlast=0,
    output reg m_axis_tuser=0,
    output reg status_padded_frame=0,
    output reg status_bad_frame=0
);
reg first=1,bad=0;
reg [15:0] offset=0,length=0;
reg [1:0] padding=0;
function [15:0] be16;
    input [127:0] data;
    input integer index;
    begin be16={data[index*8+:8],data[(index+1)*8+:8]}; end
endfunction
wire [15:0] packet_length=first ? be16(s_axis_tdata,2) : length;
wire [1:0] pad=first ? 2'd0-packet_length[1:0] : padding;
wire [16:0] adjusted_ip={1'b0,packet_length}+{15'd0,pad};
wire [16:0] adjusted_udp={1'b0,be16(s_axis_tdata,8)}+{15'd0,pad};
reg [4:0] byte_count;
integer lane;
always @* begin
    byte_count=0;
    for (lane=0;lane<16;lane=lane+1) byte_count=byte_count+{4'd0,s_axis_tkeep[lane]};
end
wire [16:0] dense_keep=(17'd1<<byte_count)-17'd1;
wire [5:0] padded_bytes={1'b0,byte_count}+{4'd0,pad};
wire [16:0] padded_keep=(17'd1<<padded_bytes)-17'd1;
wire bad_now=bad || s_axis_tuser || byte_count==0 || s_axis_tkeep!=dense_keep[15:0] ||
    (!s_axis_tlast && byte_count!=16) || adjusted_ip[16] ||
    (first && (s_axis_tdata[7:0]!=8'h45 || packet_length<48)) ||
    (offset==16 && (adjusted_udp[16] || s_axis_tdata[109:108]!=0)) ||
    (s_axis_tlast && ({1'b0,offset}+{12'd0,byte_count}!={1'b0,packet_length}-17'd4 ||
        padded_bytes>16 || padded_bytes[1:0]!=0));
assign s_axis_tready=!m_axis_tvalid || m_axis_tready;
integer out_lane;
always @(posedge clk) begin
    if (rst) begin
        first<=1; bad<=0; offset<=0; length<=0; padding<=0;
        m_axis_tdata<=0; m_axis_tkeep<=0; m_axis_tvalid<=0; m_axis_tlast<=0; m_axis_tuser<=0;
        status_padded_frame<=0; status_bad_frame<=0;
    end else begin
        status_padded_frame<=0; status_bad_frame<=0;
        if (s_axis_tready) begin
            m_axis_tvalid<=s_axis_tvalid;
            if (s_axis_tvalid) begin
                m_axis_tdata<=s_axis_tdata; m_axis_tkeep<=s_axis_tkeep;
                m_axis_tlast<=s_axis_tlast; m_axis_tuser<=bad_now;
                if (first) begin
                    length<=packet_length; padding<=pad;
                    m_axis_tdata[23:16]<=adjusted_ip[15:8];
                    m_axis_tdata[31:24]<=adjusted_ip[7:0];
                end
                if (offset==16) begin
                    m_axis_tdata[71:64]<=adjusted_udp[15:8];
                    m_axis_tdata[79:72]<=adjusted_udp[7:0];
                    m_axis_tdata[109:108]<=pad;
                end
                if (s_axis_tlast) begin
                    // A well-formed unpadded packet always fits its padding
                    // into the same final 16-byte beat. Do not heal a hole.
                    if (!bad_now) begin
                        m_axis_tkeep<=padded_keep[15:0];
                        for (out_lane=0;out_lane<16;out_lane=out_lane+1)
                            if (out_lane>=byte_count) m_axis_tdata[out_lane*8+:8]<=0;
                    end
                    first<=1; offset<=0; bad<=0;
                    status_padded_frame<=!bad_now && pad!=0;
                    status_bad_frame<=bad_now;
                end else begin
                    first<=0; bad<=bad_now;
                    if (offset<65520) offset<=offset+16'd16;
                end
            end
        end
    end
end
endmodule
`resetall
