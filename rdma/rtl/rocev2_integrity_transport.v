// SPDX-License-Identifier: BSD-2-Clause-Views
// Integrity-protected IPv4 stream bridge around the probed FNS HLS transport.
// Normalize the candidate's missing TX RoCE padding before checksum/ICRC.
// IP-only network streams, no Ethernet header. Does not implement memory
// protection, PCIe DMA, QP control registers or the board-level application.
`resetall
`timescale 1ns / 1ps
`default_nettype none

module rocev2_integrity_transport (
    input wire clk,
    input wire rst,
    input wire [127:0] s_axis_rx_tdata,
    input wire [15:0] s_axis_rx_tkeep,
    input wire s_axis_rx_tvalid,
    output wire s_axis_rx_tready,
    input wire s_axis_rx_tlast,
    input wire s_axis_rx_tuser,
    output wire [127:0] m_axis_tx_tdata,
    output wire [15:0] m_axis_tx_tkeep,
    output wire m_axis_tx_tvalid,
    input wire m_axis_tx_tready,
    output wire m_axis_tx_tlast,
    input wire [183:0] s_axis_qp_tdata,
    input wire s_axis_qp_tvalid,
    output wire s_axis_qp_tready,
    input wire [183:0] s_axis_conn_tdata,
    input wire s_axis_conn_tvalid,
    output wire s_axis_conn_tready,
    input wire [239:0] s_axis_sq_tdata,
    input wire s_axis_sq_tvalid,
    output wire s_axis_sq_tready,
    output wire [39:0] m_axis_ack_tdata,
    output wire m_axis_ack_tvalid,
    input wire m_axis_ack_tready,
    output wire [95:0] m_axis_mem_write_cmd_tdata,
    output wire m_axis_mem_write_cmd_tvalid,
    input wire m_axis_mem_write_cmd_tready,
    output wire [95:0] m_axis_mem_read_cmd_tdata,
    output wire m_axis_mem_read_cmd_tvalid,
    input wire m_axis_mem_read_cmd_tready,
    output wire [511:0] m_axis_mem_write_tdata,
    output wire [63:0] m_axis_mem_write_tkeep,
    output wire m_axis_mem_write_tvalid,
    input wire m_axis_mem_write_tready,
    output wire m_axis_mem_write_tlast,
    input wire [511:0] s_axis_mem_read_tdata,
    input wire [63:0] s_axis_mem_read_tkeep,
    input wire s_axis_mem_read_tvalid,
    output wire s_axis_mem_read_tready,
    input wire s_axis_mem_read_tlast,
    input wire [127:0] local_ip_address,
    output wire [87:0] m_axis_debug_tdata,
    output wire m_axis_debug_tvalid,
    input wire m_axis_debug_tready,
    output reg [31:0] core_psn_drop_count=0,
    output reg [31:0] core_retransmit_count=0,
    output reg [31:0] core_rx_word_count=0,
    output reg [31:0] core_tx_word_count=0,
    output reg [31:0] rx_integrity_good_count=0,
    output reg [31:0] rx_integrity_drop_count=0,
    output reg [31:0] tx_integrity_good_count=0,
    output reg [31:0] tx_integrity_drop_count=0,
    output reg [31:0] integrity_overflow_count=0
);

wire [127:0] checked_data;
wire [15:0] checked_keep;
wire checked_valid, checked_ready, checked_last;
wire rx_good, rx_bad, rx_overflow, tx_good, tx_bad, tx_overflow;
rocev2_ipv4_icrc #(.TX_MODE(0)) rx_integrity (
    .clk(clk), .rst(rst), .s_axis_tdata(s_axis_rx_tdata), .s_axis_tkeep(s_axis_rx_tkeep),
    .s_axis_tvalid(s_axis_rx_tvalid), .s_axis_tready(s_axis_rx_tready),
    .s_axis_tlast(s_axis_rx_tlast), .s_axis_tuser(s_axis_rx_tuser),
    .m_axis_tdata(checked_data), .m_axis_tkeep(checked_keep), .m_axis_tvalid(checked_valid),
    .m_axis_tready(checked_ready), .m_axis_tlast(checked_last),
    .status_good_frame(rx_good), .status_bad_frame(rx_bad), .status_overflow(rx_overflow)
);
wire [511:0] core_rx_data, core_tx_data;
wire [63:0] core_rx_keep, core_tx_keep;
wire core_rx_valid, core_rx_ready, core_rx_last;
wire core_tx_valid, core_tx_ready, core_tx_last;
wire [31:0] psn_drop_data, retransmit_data, rx_word_data, tx_word_data;
wire psn_drop_valid, retransmit_valid, rx_word_valid, tx_word_valid;
axis_adapter #(
    .S_DATA_WIDTH(128), .S_KEEP_ENABLE(1), .S_KEEP_WIDTH(16),
    .M_DATA_WIDTH(512), .M_KEEP_ENABLE(1), .M_KEEP_WIDTH(64),
    .ID_ENABLE(0), .ID_WIDTH(1), .DEST_ENABLE(0), .DEST_WIDTH(1), .USER_ENABLE(0), .USER_WIDTH(1)
) rx_width_adapter (
    .clk(clk), .rst(rst), .s_axis_tdata(checked_data), .s_axis_tkeep(checked_keep),
    .s_axis_tvalid(checked_valid), .s_axis_tready(checked_ready), .s_axis_tlast(checked_last),
    .s_axis_tid(1'b0), .s_axis_tdest(1'b0), .s_axis_tuser(1'b0),
    .m_axis_tdata(core_rx_data), .m_axis_tkeep(core_rx_keep), .m_axis_tvalid(core_rx_valid),
    .m_axis_tready(core_rx_ready), .m_axis_tlast(core_rx_last), .m_axis_tid(), .m_axis_tdest(), .m_axis_tuser()
);

rocev2_top transport (
    .ap_clk(clk), .ap_rst_n(!rst), .local_ip_address(local_ip_address),
    .s_axis_rx_data_TDATA(core_rx_data), .s_axis_rx_data_TKEEP(core_rx_keep), .s_axis_rx_data_TSTRB(core_rx_keep),
    .s_axis_rx_data_TVALID(core_rx_valid), .s_axis_rx_data_TREADY(core_rx_ready), .s_axis_rx_data_TLAST(core_rx_last),
    .m_axis_tx_data_TDATA(core_tx_data), .m_axis_tx_data_TKEEP(core_tx_keep), .m_axis_tx_data_TSTRB(),
    .m_axis_tx_data_TVALID(core_tx_valid), .m_axis_tx_data_TREADY(core_tx_ready), .m_axis_tx_data_TLAST(core_tx_last),
    .s_axis_qp_interface_TDATA(s_axis_qp_tdata), .s_axis_qp_interface_TVALID(s_axis_qp_tvalid), .s_axis_qp_interface_TREADY(s_axis_qp_tready),
    .s_axis_qp_conn_interface_TDATA(s_axis_conn_tdata), .s_axis_qp_conn_interface_TVALID(s_axis_conn_tvalid), .s_axis_qp_conn_interface_TREADY(s_axis_conn_tready),
    .s_axis_sq_meta_TDATA(s_axis_sq_tdata), .s_axis_sq_meta_TVALID(s_axis_sq_tvalid), .s_axis_sq_meta_TREADY(s_axis_sq_tready),
    .m_axis_rx_ack_meta_TDATA(m_axis_ack_tdata), .m_axis_rx_ack_meta_TVALID(m_axis_ack_tvalid), .m_axis_rx_ack_meta_TREADY(m_axis_ack_tready),
    .m_axis_mem_write_cmd_TDATA(m_axis_mem_write_cmd_tdata), .m_axis_mem_write_cmd_TVALID(m_axis_mem_write_cmd_tvalid), .m_axis_mem_write_cmd_TREADY(m_axis_mem_write_cmd_tready),
    .m_axis_mem_read_cmd_TDATA(m_axis_mem_read_cmd_tdata), .m_axis_mem_read_cmd_TVALID(m_axis_mem_read_cmd_tvalid), .m_axis_mem_read_cmd_TREADY(m_axis_mem_read_cmd_tready),
    .m_axis_mem_write_data_TDATA(m_axis_mem_write_tdata), .m_axis_mem_write_data_TKEEP(m_axis_mem_write_tkeep), .m_axis_mem_write_data_TSTRB(),
    .m_axis_mem_write_data_TVALID(m_axis_mem_write_tvalid), .m_axis_mem_write_data_TREADY(m_axis_mem_write_tready), .m_axis_mem_write_data_TLAST(m_axis_mem_write_tlast),
    .s_axis_mem_read_data_TDATA(s_axis_mem_read_tdata), .s_axis_mem_read_data_TKEEP(s_axis_mem_read_tkeep), .s_axis_mem_read_data_TSTRB(s_axis_mem_read_tkeep),
    .s_axis_mem_read_data_TVALID(s_axis_mem_read_tvalid), .s_axis_mem_read_data_TREADY(s_axis_mem_read_tready), .s_axis_mem_read_data_TLAST(s_axis_mem_read_tlast),
    .m_axis_dbg_TDATA(m_axis_debug_tdata), .m_axis_dbg_TVALID(m_axis_debug_tvalid), .m_axis_dbg_TREADY(m_axis_debug_tready),
    .regCrcDropPkgCount(), .regCrcDropPkgCount_ap_vld(),
    .regInvalidPsnDropCount(psn_drop_data), .regInvalidPsnDropCount_ap_vld(psn_drop_valid),
    .regRetransCount(retransmit_data), .regRetransCount_ap_vld(retransmit_valid),
    .regIbvCountRx(rx_word_data), .regIbvCountRx_ap_vld(rx_word_valid),
    .regIbvCountTx(tx_word_data), .regIbvCountTx_ap_vld(tx_word_valid)
);

wire [127:0] bare_tx_data;
wire [15:0] bare_tx_keep;
wire bare_tx_valid, bare_tx_ready, bare_tx_last;
axis_adapter #(
    .S_DATA_WIDTH(512), .S_KEEP_ENABLE(1), .S_KEEP_WIDTH(64),
    .M_DATA_WIDTH(128), .M_KEEP_ENABLE(1), .M_KEEP_WIDTH(16),
    .ID_ENABLE(0), .ID_WIDTH(1), .DEST_ENABLE(0), .DEST_WIDTH(1), .USER_ENABLE(0), .USER_WIDTH(1)
) tx_width_adapter (
    .clk(clk), .rst(rst), .s_axis_tdata(core_tx_data), .s_axis_tkeep(core_tx_keep),
    .s_axis_tvalid(core_tx_valid), .s_axis_tready(core_tx_ready), .s_axis_tlast(core_tx_last),
    .s_axis_tid(1'b0), .s_axis_tdest(1'b0), .s_axis_tuser(1'b0),
    .m_axis_tdata(bare_tx_data), .m_axis_tkeep(bare_tx_keep), .m_axis_tvalid(bare_tx_valid),
    .m_axis_tready(bare_tx_ready), .m_axis_tlast(bare_tx_last), .m_axis_tid(), .m_axis_tdest(), .m_axis_tuser()
);
wire [127:0] padded_tx_data;
wire [15:0] padded_tx_keep;
wire padded_tx_valid,padded_tx_ready,padded_tx_last,padded_tx_user;
rocev2_tx_padding tx_padding (
    .clk(clk), .rst(rst), .s_axis_tdata(bare_tx_data), .s_axis_tkeep(bare_tx_keep),
    .s_axis_tvalid(bare_tx_valid), .s_axis_tready(bare_tx_ready), .s_axis_tlast(bare_tx_last), .s_axis_tuser(1'b0),
    .m_axis_tdata(padded_tx_data),.m_axis_tkeep(padded_tx_keep),.m_axis_tvalid(padded_tx_valid),
    .m_axis_tready(padded_tx_ready),.m_axis_tlast(padded_tx_last),.m_axis_tuser(padded_tx_user),
    .status_padded_frame(),.status_bad_frame()
);
rocev2_ipv4_icrc #(.TX_MODE(1)) tx_integrity (
    .clk(clk), .rst(rst), .s_axis_tdata(padded_tx_data), .s_axis_tkeep(padded_tx_keep),
    .s_axis_tvalid(padded_tx_valid), .s_axis_tready(padded_tx_ready), .s_axis_tlast(padded_tx_last), .s_axis_tuser(padded_tx_user),
    .m_axis_tdata(m_axis_tx_tdata), .m_axis_tkeep(m_axis_tx_tkeep), .m_axis_tvalid(m_axis_tx_tvalid),
    .m_axis_tready(m_axis_tx_tready), .m_axis_tlast(m_axis_tx_tlast),
    .status_good_frame(tx_good), .status_bad_frame(tx_bad), .status_overflow(tx_overflow)
);
always @(posedge clk) begin
    if (rst) begin
        core_psn_drop_count<=0; core_retransmit_count<=0; core_rx_word_count<=0; core_tx_word_count<=0;
        rx_integrity_good_count<=0; rx_integrity_drop_count<=0;
        tx_integrity_good_count<=0; tx_integrity_drop_count<=0; integrity_overflow_count<=0;
    end else begin
        if (psn_drop_valid) core_psn_drop_count<=psn_drop_data;
        if (retransmit_valid) core_retransmit_count<=retransmit_data;
        if (rx_word_valid) core_rx_word_count<=rx_word_data;
        if (tx_word_valid) core_tx_word_count<=tx_word_data;
        if (rx_good) rx_integrity_good_count<=rx_integrity_good_count+1;
        if (rx_bad) rx_integrity_drop_count<=rx_integrity_drop_count+1;
        if (tx_good) tx_integrity_good_count<=tx_integrity_good_count+1;
        if (tx_bad) tx_integrity_drop_count<=tx_integrity_drop_count+1;
        integrity_overflow_count<=integrity_overflow_count+{31'd0,rx_overflow}+{31'd0,tx_overflow};
    end
end

endmodule
`resetall
