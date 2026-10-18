// SPDX-License-Identifier: BSD-2-Clause-Views
// Complete 128-bit/250MHz initiator boundary for the Corundum synchronous app.
// rst is whole-NIC reset. Per-run core_reset resets ONLY the HLS/integrity/
// pattern state, after the independent injected-frame guard has drained.
// No arbitrary PCIe DMA or inbound WRITE memory is exposed by this endpoint.
`resetall
`timescale 1ns / 1ps
`default_nettype none

module rocev2_endpoint #(
    parameter ADDR_WIDTH=24,
    parameter TAG_WIDTH=16,
    parameter TS_WIDTH=96,
    parameter RX_USER_WIDTH=97,
    parameter WINDOW=32
)(
    input wire clk,
    input wire rst,
    input wire [ADDR_WIDTH-1:0] s_axil_awaddr,
    input wire [2:0] s_axil_awprot,
    input wire s_axil_awvalid,
    output wire s_axil_awready,
    input wire [31:0] s_axil_wdata,
    input wire [3:0] s_axil_wstrb,
    input wire s_axil_wvalid,
    output wire s_axil_wready,
    output wire [1:0] s_axil_bresp,
    output wire s_axil_bvalid,
    input wire s_axil_bready,
    input wire [ADDR_WIDTH-1:0] s_axil_araddr,
    input wire [2:0] s_axil_arprot,
    input wire s_axil_arvalid,
    output wire s_axil_arready,
    output wire [31:0] s_axil_rdata,
    output wire [1:0] s_axil_rresp,
    output wire s_axil_rvalid,
    input wire s_axil_rready,
    input wire [127:0] s_axis_host_tx_tdata,
    input wire [15:0] s_axis_host_tx_tkeep,
    input wire s_axis_host_tx_tvalid,
    output wire s_axis_host_tx_tready,
    input wire s_axis_host_tx_tlast,
    input wire [TAG_WIDTH:0] s_axis_host_tx_tuser,
    output wire [127:0] m_axis_mac_tx_tdata,
    output wire [15:0] m_axis_mac_tx_tkeep,
    output wire m_axis_mac_tx_tvalid,
    input wire m_axis_mac_tx_tready,
    output wire m_axis_mac_tx_tlast,
    output wire [TAG_WIDTH:0] m_axis_mac_tx_tuser,
    input wire [TAG_WIDTH-1:0] s_axis_mac_cpl_tag,
    input wire [TS_WIDTH-1:0] s_axis_mac_cpl_ts,
    input wire s_axis_mac_cpl_valid,
    output wire s_axis_mac_cpl_ready,
    output wire [TAG_WIDTH-1:0] m_axis_host_cpl_tag,
    output wire [TS_WIDTH-1:0] m_axis_host_cpl_ts,
    output wire m_axis_host_cpl_valid,
    input wire m_axis_host_cpl_ready,
    input wire [127:0] s_axis_mac_rx_tdata,
    input wire [15:0] s_axis_mac_rx_tkeep,
    input wire s_axis_mac_rx_tvalid,
    output wire s_axis_mac_rx_tready,
    input wire s_axis_mac_rx_tlast,
    input wire [RX_USER_WIDTH-1:0] s_axis_mac_rx_tuser,
    output wire [127:0] m_axis_host_rx_tdata,
    output wire [15:0] m_axis_host_rx_tkeep,
    output wire m_axis_host_rx_tvalid,
    input wire m_axis_host_rx_tready,
    output wire m_axis_host_rx_tlast,
    output wire [RX_USER_WIDTH-1:0] m_axis_host_rx_tuser
);

wire [47:0] local_mac,peer_mac;
wire [31:0] local_ip,peer_ip;
wire [23:0] local_qpn;
wire core_reset,halt_tx,rx_enable,tx_quiescent,guard_fault;
// Give the generated HLS reset inverter a real startup transition even
// when the idle controller holds core_reset high from time zero. Global
// reset dominates immediately; subsequent resets remain the real controller's.
reg reset_armed=0;
always @(posedge clk) reset_armed<=1'b1;
wire transport_reset=rst || (reset_armed && core_reset);
wire [183:0] qp,conn;
wire qv,qr,cv,cr;
wire [239:0] sq;
wire sv,sr;
wire [39:0] ack;
wire av,ar;
wire [95:0] mem_cmd;
wire mv,mr;
wire [511:0] mem_data;
wire [63:0] mem_keep;
wire mdv,mdr,ml;
wire bad_wcmd,bad_wdata;
wire [31:0] psn_drop,retrans,rx_words,tx_words,rx_good,rx_bad,tx_good,tx_bad,overflow;
wire [31:0] eth_drop,eth_rx,eth_host,eth_tx,eth_cpl,rx_overflow;
wire [15:0] guard_pending;
wire [31:0] guard_admitted,guard_completed;
reg [31:0] flushed_ack_frames=0;
wire [511:0] diagnostics={15'd0,guard_fault,guard_pending,flushed_ack_frames,
    eth_cpl,eth_tx,eth_host,eth_rx,eth_drop,overflow+rx_overflow,
    tx_bad,tx_good,rx_bad,rx_good,tx_words,rx_words,retrans,psn_drop};
rocev2_control #(.ADDR_WIDTH(ADDR_WIDTH),.WINDOW(WINDOW)) control (
    .clk(clk),.rst(rst),
    .s_axil_awaddr(s_axil_awaddr),.s_axil_awprot(s_axil_awprot),.s_axil_awvalid(s_axil_awvalid),.s_axil_awready(s_axil_awready),
    .s_axil_wdata(s_axil_wdata),.s_axil_wstrb(s_axil_wstrb),.s_axil_wvalid(s_axil_wvalid),.s_axil_wready(s_axil_wready),
    .s_axil_bresp(s_axil_bresp),.s_axil_bvalid(s_axil_bvalid),.s_axil_bready(s_axil_bready),
    .s_axil_araddr(s_axil_araddr),.s_axil_arprot(s_axil_arprot),.s_axil_arvalid(s_axil_arvalid),.s_axil_arready(s_axil_arready),
    .s_axil_rdata(s_axil_rdata),.s_axil_rresp(s_axil_rresp),.s_axil_rvalid(s_axil_rvalid),.s_axil_rready(s_axil_rready),
    .tx_quiescent(tx_quiescent),.unexpected_memory_write(bad_wcmd || bad_wdata || guard_fault),.diagnostics(diagnostics),
    .local_mac(local_mac),.peer_mac(peer_mac),.local_ip(local_ip),.peer_ip(peer_ip),.local_qpn(local_qpn),
    .core_reset(core_reset),.halt_tx(halt_tx),.rx_enable(rx_enable),.busy(),.done(),.failed(),
    .m_axis_qp_tdata(qp),.m_axis_qp_tvalid(qv),.m_axis_qp_tready(qr),
    .m_axis_conn_tdata(conn),.m_axis_conn_tvalid(cv),.m_axis_conn_tready(cr),
    .m_axis_sq_tdata(sq),.m_axis_sq_tvalid(sv),.m_axis_sq_tready(sr),
    .s_axis_ack_tdata(ack),.s_axis_ack_tvalid(av),.s_axis_ack_tready(ar),
    .s_axis_mem_cmd_tdata(mem_cmd),.s_axis_mem_cmd_tvalid(mv),.s_axis_mem_cmd_tready(mr),
    .m_axis_mem_tdata(mem_data),.m_axis_mem_tkeep(mem_keep),.m_axis_mem_tvalid(mdv),.m_axis_mem_tready(mdr),.m_axis_mem_tlast(ml));

wire [127:0] ip_rx_data,ip_tx_data;
wire [15:0] ip_rx_keep,ip_tx_keep;
wire ip_rx_valid,ip_rx_ready,ip_rx_last,ip_rx_user,ip_tx_valid,ip_tx_ready,ip_tx_last;
// Flush queued old-run ACKs while the endpoint is disabled/initializing.
// Ordinary host traffic still passes through the global-reset-only router.
wire consume_ack=rx_enable && !core_reset;
wire router_ready=!consume_ack || ip_rx_ready;
always @(posedge clk) begin
    if (rst) flushed_ack_frames<=0;
    else if (!consume_ack && ip_rx_valid && router_ready && ip_rx_last)
        flushed_ack_frames<=flushed_ack_frames+1'b1;
end
wire [31:0] local_ip_axis={local_ip[7:0],local_ip[15:8],local_ip[23:16],local_ip[31:24]};
rocev2_integrity_transport transport (
    .clk(clk),.rst(transport_reset),
    .s_axis_rx_tdata(ip_rx_data),.s_axis_rx_tkeep(ip_rx_keep),.s_axis_rx_tvalid(ip_rx_valid && consume_ack),
    .s_axis_rx_tready(ip_rx_ready),.s_axis_rx_tlast(ip_rx_last),.s_axis_rx_tuser(ip_rx_user),
    .m_axis_tx_tdata(ip_tx_data),.m_axis_tx_tkeep(ip_tx_keep),.m_axis_tx_tvalid(ip_tx_valid),.m_axis_tx_tready(ip_tx_ready),.m_axis_tx_tlast(ip_tx_last),
    .s_axis_qp_tdata(qp),.s_axis_qp_tvalid(qv),.s_axis_qp_tready(qr),.s_axis_conn_tdata(conn),.s_axis_conn_tvalid(cv),.s_axis_conn_tready(cr),
    .s_axis_sq_tdata(sq),.s_axis_sq_tvalid(sv),.s_axis_sq_tready(sr),
    .m_axis_ack_tdata(ack),.m_axis_ack_tvalid(av),.m_axis_ack_tready(ar),
    .m_axis_mem_write_cmd_tdata(),.m_axis_mem_write_cmd_tvalid(bad_wcmd),.m_axis_mem_write_cmd_tready(1'b1),
    .m_axis_mem_read_cmd_tdata(mem_cmd),.m_axis_mem_read_cmd_tvalid(mv),.m_axis_mem_read_cmd_tready(mr),
    .m_axis_mem_write_tdata(),.m_axis_mem_write_tkeep(),.m_axis_mem_write_tvalid(bad_wdata),.m_axis_mem_write_tready(1'b1),.m_axis_mem_write_tlast(),
    .s_axis_mem_read_tdata(mem_data),.s_axis_mem_read_tkeep(mem_keep),.s_axis_mem_read_tvalid(mdv),.s_axis_mem_read_tready(mdr),.s_axis_mem_read_tlast(ml),
    .local_ip_address({4{local_ip_axis}}),.m_axis_debug_tdata(),.m_axis_debug_tvalid(),.m_axis_debug_tready(1'b1),
    .core_psn_drop_count(psn_drop),.core_retransmit_count(retrans),.core_rx_word_count(rx_words),.core_tx_word_count(tx_words),
    .rx_integrity_good_count(rx_good),.rx_integrity_drop_count(rx_bad),.tx_integrity_good_count(tx_good),.tx_integrity_drop_count(tx_bad),.integrity_overflow_count(overflow));

rocev2_ethernet_rx #(.USER_WIDTH(RX_USER_WIDTH)) ingress (
    .clk(clk),.rst(rst),.enable(rx_enable),.local_mac(local_mac),.peer_mac(peer_mac),.local_ip(local_ip),.peer_ip(peer_ip),.local_qpn(local_qpn),
    .s_axis_tdata(s_axis_mac_rx_tdata),.s_axis_tkeep(s_axis_mac_rx_tkeep),.s_axis_tvalid(s_axis_mac_rx_tvalid),.s_axis_tready(s_axis_mac_rx_tready),.s_axis_tlast(s_axis_mac_rx_tlast),.s_axis_tuser(s_axis_mac_rx_tuser),
    .m_axis_host_tdata(m_axis_host_rx_tdata),.m_axis_host_tkeep(m_axis_host_rx_tkeep),.m_axis_host_tvalid(m_axis_host_rx_tvalid),.m_axis_host_tready(m_axis_host_rx_tready),.m_axis_host_tlast(m_axis_host_rx_tlast),.m_axis_host_tuser(m_axis_host_rx_tuser),
    .m_axis_roce_tdata(ip_rx_data),.m_axis_roce_tkeep(ip_rx_keep),.m_axis_roce_tvalid(ip_rx_valid),.m_axis_roce_tready(router_ready),.m_axis_roce_tlast(ip_rx_last),.m_axis_roce_tuser(ip_rx_user),
    .host_frame_count(eth_host),.roce_frame_count(eth_rx),.drop_frame_count(eth_drop),.overflow_count(rx_overflow));

wire [127:0] guarded_data;
wire [15:0] guarded_keep;
wire guarded_valid,guarded_ready,guarded_last;
rocev2_tx_guard guard (
    .clk(clk),.rst(rst),.halt(halt_tx),
    .completion(s_axis_mac_cpl_valid && s_axis_mac_cpl_ready && !s_axis_mac_cpl_tag[TAG_WIDTH-1]),
    .s_axis_tdata(ip_tx_data),.s_axis_tkeep(ip_tx_keep),.s_axis_tvalid(ip_tx_valid),.s_axis_tready(ip_tx_ready),.s_axis_tlast(ip_tx_last),
    .m_axis_tdata(guarded_data),.m_axis_tkeep(guarded_keep),.m_axis_tvalid(guarded_valid),.m_axis_tready(guarded_ready),.m_axis_tlast(guarded_last),
    .quiescent(tx_quiescent),.fault(guard_fault),.pending_frames(guard_pending),.admitted_frames(guard_admitted),.completed_frames(guard_completed));
rocev2_ethernet_tx #(.TAG_WIDTH(TAG_WIDTH),.TS_WIDTH(TS_WIDTH)) egress (
    .clk(clk),.rst(rst),.local_mac(local_mac),.peer_mac(peer_mac),
    .s_axis_roce_tdata(guarded_data),.s_axis_roce_tkeep(guarded_keep),.s_axis_roce_tvalid(guarded_valid),.s_axis_roce_tready(guarded_ready),.s_axis_roce_tlast(guarded_last),
    .s_axis_host_tdata(s_axis_host_tx_tdata),.s_axis_host_tkeep(s_axis_host_tx_tkeep),.s_axis_host_tvalid(s_axis_host_tx_tvalid),.s_axis_host_tready(s_axis_host_tx_tready),.s_axis_host_tlast(s_axis_host_tx_tlast),.s_axis_host_tuser(s_axis_host_tx_tuser),
    .m_axis_tdata(m_axis_mac_tx_tdata),.m_axis_tkeep(m_axis_mac_tx_tkeep),.m_axis_tvalid(m_axis_mac_tx_tvalid),.m_axis_tready(m_axis_mac_tx_tready),.m_axis_tlast(m_axis_mac_tx_tlast),.m_axis_tuser(m_axis_mac_tx_tuser),
    .s_axis_cpl_tag(s_axis_mac_cpl_tag),.s_axis_cpl_ts(s_axis_mac_cpl_ts),.s_axis_cpl_valid(s_axis_mac_cpl_valid),.s_axis_cpl_ready(s_axis_mac_cpl_ready),
    .m_axis_host_cpl_tag(m_axis_host_cpl_tag),.m_axis_host_cpl_ts(m_axis_host_cpl_ts),.m_axis_host_cpl_valid(m_axis_host_cpl_valid),.m_axis_host_cpl_ready(m_axis_host_cpl_ready),
    .roce_frame_count(eth_tx),.roce_completion_count(eth_cpl));
endmodule
`resetall
