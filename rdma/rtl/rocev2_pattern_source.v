// SPDX-License-Identifier: BSD-2-Clause-Views
// Replayable deterministic payload memory, not PCIe DMA. Every accepted read
// must be entirely within the configured finite local range. Supports byte
// alignment/partial tails and repeats on retransmission without storing data.
`resetall
`timescale 1ns / 1ps
`default_nettype none

module rocev2_pattern_source (
    input wire clk,
    input wire rst,
    input wire enable,
    input wire [31:0] total_bytes,
    input wire [95:0] s_axis_cmd_tdata,
    input wire s_axis_cmd_tvalid,
    output wire s_axis_cmd_tready,
    output reg [511:0] m_axis_tdata=0,
    output reg [63:0] m_axis_tkeep=0,
    output reg m_axis_tvalid=0,
    input wire m_axis_tready,
    output reg m_axis_tlast=0,
    output reg fault=0,
    output reg [31:0] command_count=0,
    output reg [63:0] supplied_bytes=0
);
reg active=0;
reg [31:0] address=0;
reg [27:0] remaining=0;
reg [6:0] output_bytes=0;
wire [48:0] command_end={1'b0,s_axis_cmd_tdata[47:0]}+{21'd0,s_axis_cmd_tdata[75:48]};
wire command_ok=s_axis_cmd_tdata[75:48]!=0 && s_axis_cmd_tdata[75:48]<=4096 &&
    command_end<={17'd0,total_bytes} && !s_axis_cmd_tdata[79];
wire [6:0] next_bytes=remaining>=64 ? 7'd64 : {1'b0,remaining[5:0]};
wire [64:0] next_keep=(65'd1<<next_bytes)-65'd1;
assign s_axis_cmd_tready=enable && !fault && !active && (!m_axis_tvalid || m_axis_tready);
integer lane;
reg [15:0] index;
reg [7:0] product;
always @(posedge clk) begin
    if (rst) begin
        active<=0; address<=0; remaining<=0; output_bytes<=0; fault<=0;
        command_count<=0; supplied_bytes<=0;
        m_axis_tdata<=0; m_axis_tkeep<=0; m_axis_tvalid<=0; m_axis_tlast<=0;
    end else begin
        if (m_axis_tvalid && m_axis_tready) begin
            m_axis_tvalid<=0;
            supplied_bytes<=supplied_bytes+{57'd0,output_bytes};
        end
        if (s_axis_cmd_tvalid && s_axis_cmd_tready) begin
            if (!command_ok) fault<=1;
            else begin
                active<=1; address<=s_axis_cmd_tdata[31:0]; remaining<=s_axis_cmd_tdata[75:48];
                command_count<=command_count+1'b1;
            end
        end
        if (active && (!m_axis_tvalid || m_axis_tready)) begin
            for (lane=0;lane<64;lane=lane+1) begin
                index=address[15:0]+lane[15:0];
                product=index[7:0]*8'd131;
                m_axis_tdata[lane*8+:8]<=product^index[15:8]^8'h5a;
            end
            m_axis_tkeep<=next_keep[63:0]; m_axis_tlast<=remaining<=64; m_axis_tvalid<=1;
            output_bytes<=next_bytes;
            address<=address+{25'd0,next_bytes}; remaining<=remaining-{21'd0,next_bytes};
            if (remaining<=64) active<=0;
        end
    end
end
endmodule
`resetall
