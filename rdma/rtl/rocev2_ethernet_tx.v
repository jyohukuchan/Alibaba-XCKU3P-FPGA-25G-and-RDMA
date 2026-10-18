// SPDX-License-Identifier: BSD-2-Clause-Views
// Ethernet encapsulation + frame-locked arbitration at 128 bits. Inputs from
// the transport MUST already include IPv4 checksum/ICRC. Ethernet FCS/padding
// are the downstream MAC's responsibility. MAC addresses use numeric order.
// Corundum tx_engine sets tag MSB=1 for real NIC descriptors (tx_engine.v
// lines 719-720 in pinned 1ca0151); injected frames use tag=0. Filter only
// injected completions, without consuming/altering any host completion.
`resetall
`timescale 1ns / 1ps
`default_nettype none

module rocev2_ethernet_tx #(
    parameter TAG_WIDTH=16,
    parameter TS_WIDTH=96
)(
    input wire clk,
    input wire rst,
    input wire [47:0] local_mac,
    input wire [47:0] peer_mac,
    input wire [127:0] s_axis_roce_tdata,
    input wire [15:0] s_axis_roce_tkeep,
    input wire s_axis_roce_tvalid,
    output wire s_axis_roce_tready,
    input wire s_axis_roce_tlast,
    input wire [127:0] s_axis_host_tdata,
    input wire [15:0] s_axis_host_tkeep,
    input wire s_axis_host_tvalid,
    output wire s_axis_host_tready,
    input wire s_axis_host_tlast,
    input wire [TAG_WIDTH:0] s_axis_host_tuser,
    output wire [127:0] m_axis_tdata,
    output wire [15:0] m_axis_tkeep,
    output wire m_axis_tvalid,
    input wire m_axis_tready,
    output wire m_axis_tlast,
    output wire [TAG_WIDTH:0] m_axis_tuser,
    input wire [TAG_WIDTH-1:0] s_axis_cpl_tag,
    input wire [TS_WIDTH-1:0] s_axis_cpl_ts,
    input wire s_axis_cpl_valid,
    output wire s_axis_cpl_ready,
    output wire [TAG_WIDTH-1:0] m_axis_host_cpl_tag,
    output wire [TS_WIDTH-1:0] m_axis_host_cpl_ts,
    output wire m_axis_host_cpl_valid,
    input wire m_axis_host_cpl_ready,
    output reg [31:0] roce_frame_count=0,
    output reg [31:0] roce_completion_count=0
);

initial begin
    if (TAG_WIDTH<2 || TS_WIDTH<1) begin $error("Invalid tag/timestamp width"); $finish; end
end
reg header_sent=0;
wire header_ready;
wire header_valid=s_axis_roce_tvalid && !header_sent;
always @(posedge clk) begin
    if (rst) header_sent<=0;
    else begin
        if (header_valid && header_ready) header_sent<=1;
        if (s_axis_roce_tvalid && s_axis_roce_tready && s_axis_roce_tlast) header_sent<=0;
    end
end
wire [127:0] framed_data;
wire [15:0] framed_keep;
wire framed_valid,framed_ready,framed_last,framed_user;
eth_axis_tx #(.DATA_WIDTH(128),.KEEP_ENABLE(1),.KEEP_WIDTH(16)) add_header (
    .clk(clk),.rst(rst),.s_eth_hdr_valid(header_valid),.s_eth_hdr_ready(header_ready),
    .s_eth_dest_mac(peer_mac),.s_eth_src_mac(local_mac),.s_eth_type(16'h0800),
    .s_eth_payload_axis_tdata(s_axis_roce_tdata),.s_eth_payload_axis_tkeep(s_axis_roce_tkeep),
    .s_eth_payload_axis_tvalid(s_axis_roce_tvalid),.s_eth_payload_axis_tready(s_axis_roce_tready),
    .s_eth_payload_axis_tlast(s_axis_roce_tlast),.s_eth_payload_axis_tuser(1'b0),
    .m_axis_tdata(framed_data),.m_axis_tkeep(framed_keep),.m_axis_tvalid(framed_valid),
    .m_axis_tready(framed_ready),.m_axis_tlast(framed_last),.m_axis_tuser(framed_user),.busy()
);
axis_arb_mux #(
    .S_COUNT(2),.DATA_WIDTH(128),.KEEP_ENABLE(1),.KEEP_WIDTH(16),
    .ID_ENABLE(0),.S_ID_WIDTH(1),.M_ID_WIDTH(2),.DEST_ENABLE(0),.DEST_WIDTH(1),
    .USER_ENABLE(1),.USER_WIDTH(TAG_WIDTH+1),.LAST_ENABLE(1),.UPDATE_TID(0),
    .ARB_TYPE_ROUND_ROBIN(1),.ARB_LSB_HIGH_PRIORITY(1)
) merge_frames (
    .clk(clk),.rst(rst),.s_axis_tdata({framed_data,s_axis_host_tdata}),
    .s_axis_tkeep({framed_keep,s_axis_host_tkeep}),.s_axis_tvalid({framed_valid,s_axis_host_tvalid}),
    .s_axis_tready({framed_ready,s_axis_host_tready}),.s_axis_tlast({framed_last,s_axis_host_tlast}),
    .s_axis_tid(2'b0),.s_axis_tdest(2'b0),
    .s_axis_tuser({{TAG_WIDTH{1'b0}},framed_user,s_axis_host_tuser}),
    .m_axis_tdata(m_axis_tdata),.m_axis_tkeep(m_axis_tkeep),.m_axis_tvalid(m_axis_tvalid),
    .m_axis_tready(m_axis_tready),.m_axis_tlast(m_axis_tlast),.m_axis_tid(),.m_axis_tdest(),.m_axis_tuser(m_axis_tuser)
);

assign m_axis_host_cpl_tag=s_axis_cpl_tag;
assign m_axis_host_cpl_ts=s_axis_cpl_ts;
assign m_axis_host_cpl_valid=s_axis_cpl_valid && s_axis_cpl_tag[TAG_WIDTH-1];
assign s_axis_cpl_ready=!s_axis_cpl_tag[TAG_WIDTH-1] || m_axis_host_cpl_ready;
always @(posedge clk) begin
    if (rst) begin roce_frame_count<=0; roce_completion_count<=0; end
    else begin
        if (framed_valid && framed_ready && framed_last) roce_frame_count<=roce_frame_count+1'b1;
        if (s_axis_cpl_valid && s_axis_cpl_ready && !s_axis_cpl_tag[TAG_WIDTH-1])
            roce_completion_count<=roce_completion_count+1'b1;
    end
end
endmodule
`resetall
