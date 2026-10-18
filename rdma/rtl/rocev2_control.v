// SPDX-License-Identifier: BSD-2-Clause-Views
// AXI-Lite control/status and bounded local pattern memory for the native25
// experimental WRITE endpoint. No arbitrary PCIe DMA is exposed. This block
// does not replace the Ethernet frame admission/quiescence gate or MR lifetime
// protocol: wire tx_quiescent to the validated physical-drain indication.
`resetall
`timescale 1ns / 1ps
`default_nettype none

module rocev2_control #(
    parameter ADDR_WIDTH=24,
    parameter WINDOW=32,
    parameter RESET_CYCLES=16,
    parameter INIT_CYCLES=4096,
    parameter SETTLE_CYCLES=64
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
    output reg [1:0] s_axil_bresp=0,
    output reg s_axil_bvalid=0,
    input wire s_axil_bready,
    input wire [ADDR_WIDTH-1:0] s_axil_araddr,
    input wire [2:0] s_axil_arprot,
    input wire s_axil_arvalid,
    output wire s_axil_arready,
    output reg [31:0] s_axil_rdata=0,
    output reg [1:0] s_axil_rresp=0,
    output reg s_axil_rvalid=0,
    input wire s_axil_rready,
    input wire tx_quiescent,
    input wire unexpected_memory_write,
    input wire [511:0] diagnostics,
    output wire [47:0] local_mac,
    output wire [47:0] peer_mac,
    output wire [31:0] local_ip,
    output wire [31:0] peer_ip,
    output wire [23:0] local_qpn,
    output wire core_reset,
    output wire halt_tx,
    output wire rx_enable,
    output wire busy,
    output wire done,
    output wire failed,
    output wire [183:0] m_axis_qp_tdata,
    output wire m_axis_qp_tvalid,
    input wire m_axis_qp_tready,
    output wire [183:0] m_axis_conn_tdata,
    output wire m_axis_conn_tvalid,
    input wire m_axis_conn_tready,
    output wire [239:0] m_axis_sq_tdata,
    output wire m_axis_sq_tvalid,
    input wire m_axis_sq_tready,
    input wire [39:0] s_axis_ack_tdata,
    input wire s_axis_ack_tvalid,
    output wire s_axis_ack_tready,
    input wire [95:0] s_axis_mem_cmd_tdata,
    input wire s_axis_mem_cmd_tvalid,
    output wire s_axis_mem_cmd_tready,
    output wire [511:0] m_axis_mem_tdata,
    output wire [63:0] m_axis_mem_tkeep,
    output wire m_axis_mem_tvalid,
    input wire m_axis_mem_tready,
    output wire m_axis_mem_tlast
);

initial begin
    if (ADDR_WIDTH<8) begin $error("AXI-Lite address width must cover registers"); $finish; end
end
reg [31:0] config_regs[0:17];
assign local_mac={config_regs[1][15:0],config_regs[0]};
assign peer_mac={config_regs[3][15:0],config_regs[2]};
assign local_ip=config_regs[4];
assign peer_ip=config_regs[5];
assign local_qpn=config_regs[6][23:0];
wire ethernet_config_valid=local_mac!=0 && peer_mac!=0 && !local_mac[40] && !peer_mac[40] &&
    local_ip!=0 && peer_ip!=0 && local_ip!=peer_ip;
reg start=0,clear=0,abort_run=0;
wire start_ready;
wire [3:0] state;
wire [31:0] error,issued,acked,duplicates,total,read_commands;
wire [63:0] elapsed,read_bytes;
wire pattern_fault;
rocev2_write_engine #(.WINDOW(WINDOW),.RESET_CYCLES(RESET_CYCLES),.INIT_CYCLES(INIT_CYCLES),.SETTLE_CYCLES(SETTLE_CYCLES)) engine (
    .clk(clk),.rst(rst),.start(start),.clear(clear),.abort_run(abort_run),.start_ready(start_ready),
    .cfg_local_qpn(local_qpn),.cfg_peer_qpn(config_regs[7][23:0]),
    .cfg_tx_psn(config_regs[8][23:0]),.cfg_peer_psn(config_regs[9][23:0]),.cfg_peer_ip(peer_ip),
    .cfg_rkey(config_regs[10]),.cfg_remote_address({config_regs[13],config_regs[12]}),
    .cfg_remote_bytes({config_regs[15],config_regs[14]}),.cfg_message_bytes(config_regs[11]),
    .cfg_message_count(config_regs[16]),.cfg_timeout_cycles(config_regs[17]),
    .tx_quiescent(tx_quiescent),.memory_fault(pattern_fault || unexpected_memory_write),
    .core_reset(core_reset),.halt_tx(halt_tx),.rx_enable(rx_enable),.busy(busy),.done(done),.failed(failed),.state(state),
    .error_code(error),.issued_count(issued),.acked_count(acked),.duplicate_ack_count(duplicates),.total_bytes(total),.elapsed_cycles(elapsed),
    .m_axis_qp_tdata(m_axis_qp_tdata),.m_axis_qp_tvalid(m_axis_qp_tvalid),.m_axis_qp_tready(m_axis_qp_tready),
    .m_axis_conn_tdata(m_axis_conn_tdata),.m_axis_conn_tvalid(m_axis_conn_tvalid),.m_axis_conn_tready(m_axis_conn_tready),
    .m_axis_sq_tdata(m_axis_sq_tdata),.m_axis_sq_tvalid(m_axis_sq_tvalid),.m_axis_sq_tready(m_axis_sq_tready),
    .s_axis_ack_tdata(s_axis_ack_tdata),.s_axis_ack_tvalid(s_axis_ack_tvalid),.s_axis_ack_tready(s_axis_ack_tready)
);
rocev2_pattern_source memory_source (
    .clk(clk),.rst(core_reset),.enable(!core_reset),.total_bytes(total),
    .s_axis_cmd_tdata(s_axis_mem_cmd_tdata),.s_axis_cmd_tvalid(s_axis_mem_cmd_tvalid),.s_axis_cmd_tready(s_axis_mem_cmd_tready),
    .m_axis_tdata(m_axis_mem_tdata),.m_axis_tkeep(m_axis_mem_tkeep),.m_axis_tvalid(m_axis_mem_tvalid),
    .m_axis_tready(m_axis_mem_tready),.m_axis_tlast(m_axis_mem_tlast),.fault(pattern_fault),
    .command_count(read_commands),.supplied_bytes(read_bytes)
);

reg aw_pending=0,w_pending=0;
reg [ADDR_WIDTH-1:0] awaddr=0;
reg [31:0] wdata=0;
reg [3:0] wstrb=0;
reg [31:0] rejected_writes=0,last_rejection=0;
assign s_axil_awready=!aw_pending && !s_axil_bvalid;
assign s_axil_wready=!w_pending && !s_axil_bvalid;
assign s_axil_arready=!s_axil_rvalid;
wire write_commit=aw_pending && w_pending && !s_axil_bvalid;
wire config_address=awaddr>=64 && awaddr<=132 && awaddr[1:0]==0;
wire read_config_address=s_axil_araddr>=64 && s_axil_araddr<=132 && s_axil_araddr[1:0]==0;
wire read_diagnostic_address=s_axil_araddr>=144 && s_axil_araddr<=204 && s_axil_araddr[1:0]==0;
// Modulo-width subtraction; range checks above ensure the selected word
// lies in the configuration/diagnostic bank. No SystemVerilog-sized casts.
wire [4:0] config_index=awaddr[6:2]-5'd16;
wire [4:0] read_config_index=s_axil_araddr[6:2]-5'd16;
wire [3:0] diagnostic_index=s_axil_araddr[5:2]-4'd4;
wire [31:0] byte_mask={{8{wstrb[3]}},{8{wstrb[2]}},{8{wstrb[1]}},{8{wstrb[0]}}};
wire [31:0] write_mask=(config_index==1 || config_index==3) ? 32'h0000ffff :
    (config_index>=6 && config_index<=9) ? 32'h00ffffff : 32'hffffffff;
reg [31:0] write_error;
always @* begin
    write_error=0;
    if (awaddr[1:0]!=0) write_error=1;
    else if (config_address) begin if (wstrb!=0 && (state!=0 || start)) write_error=2; end
    else if (awaddr==8) begin
        if (!wstrb[0] || wdata[7:0]==0) write_error=0;
        else if (wdata[7:0]==1) begin
            if (!start_ready) write_error=2;
            else if (!ethernet_config_valid) write_error=4;
        end else if (wdata[7:0]==2) begin if (busy) write_error=2; end
        else if (wdata[7:0]==4) begin if (!busy) write_error=2; end
        else write_error=3;
    end else write_error=1;
end

integer i;
reg [31:0] saved_read_commands=0;
reg [63:0] saved_read_bytes=0;
reg [511:0] saved_diagnostics=0;
always @(posedge clk) begin
    if (rst) begin
        for (i=0;i<18;i=i+1) config_regs[i]<=0;
        config_regs[6]<=2; config_regs[8]<=32'h00123456; config_regs[9]<=32'h00654321;
        config_regs[11]<=64; config_regs[16]<=1; config_regs[17]<=250000000;
        start<=0; clear<=0; abort_run<=0;
        aw_pending<=0; w_pending<=0; awaddr<=0; wdata<=0; wstrb<=0;
        rejected_writes<=0; last_rejection<=0;
        saved_read_commands<=0; saved_read_bytes<=0;
        saved_diagnostics<=0;
        s_axil_bvalid<=0; s_axil_bresp<=0; s_axil_rvalid<=0; s_axil_rdata<=0; s_axil_rresp<=0;
    end else begin
        start<=0; clear<=0; abort_run<=0;
        // Preserve evidence when the quiesced transport/memory is reset.
        if (!core_reset) begin
            saved_read_commands<=read_commands; saved_read_bytes<=read_bytes; saved_diagnostics<=diagnostics;
        end
        if (s_axil_bvalid && s_axil_bready) s_axil_bvalid<=0;
        if (s_axil_rvalid && s_axil_rready) s_axil_rvalid<=0;
        if (s_axil_awvalid && s_axil_awready) begin awaddr<=s_axil_awaddr; aw_pending<=1; end
        if (s_axil_wvalid && s_axil_wready) begin wdata<=s_axil_wdata; wstrb<=s_axil_wstrb; w_pending<=1; end
        if (write_commit) begin
            aw_pending<=0; w_pending<=0; s_axil_bvalid<=1; s_axil_bresp<=write_error==0 ? 2'b00 : 2'b10;
            if (write_error!=0) begin rejected_writes<=rejected_writes+1'b1; last_rejection<=write_error; end
            else if (config_address) config_regs[config_index]<=
                ((config_regs[config_index] & ~byte_mask) | (wdata & byte_mask)) & write_mask;
            else if (awaddr==8 && wstrb[0]) begin
                if (wdata[7:0]==1) begin
                    start<=1; saved_read_commands<=0; saved_read_bytes<=0; saved_diagnostics<=0;
                end
                if (wdata[7:0]==2) begin clear<=1; last_rejection<=0; end
                if (wdata[7:0]==4) abort_run<=1;
            end
        end
        if (s_axil_arvalid && s_axil_arready) begin
            s_axil_rvalid<=1; s_axil_rresp<=0; s_axil_rdata<=0;
            if (s_axil_araddr[1:0]!=0) s_axil_rresp<=2'b10;
            else if (read_config_address) s_axil_rdata<=config_regs[read_config_index];
            else if (read_diagnostic_address) s_axil_rdata<=(done || failed) ?
                saved_diagnostics[diagnostic_index*32+:32] : diagnostics[diagnostic_index*32+:32];
            else case (s_axil_araddr)
                0: s_axil_rdata<=32'h524f4332;
                4: s_axil_rdata<=32'h00010000;
                8: s_axil_rdata<=0;
                12: s_axil_rdata<={20'd0,state,1'b0,rx_enable,halt_tx,tx_quiescent,core_reset,failed,done,busy};
                16: s_axil_rdata<=error;
                20: s_axil_rdata<=issued;
                24: s_axil_rdata<=acked;
                28: s_axil_rdata<=total;
                32: s_axil_rdata<=elapsed[31:0];
                36: s_axil_rdata<=elapsed[63:32];
                40: s_axil_rdata<=duplicates;
                44: s_axil_rdata<=saved_read_commands;
                48: s_axil_rdata<=saved_read_bytes[31:0];
                52: s_axil_rdata<=saved_read_bytes[63:32];
                56: s_axil_rdata<=rejected_writes;
                60: s_axil_rdata<=last_rejection;
                default: s_axil_rresp<=2'b10;
            endcase
        end
    end
end
endmodule
`resetall
