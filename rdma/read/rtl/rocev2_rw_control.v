// SPDX-License-Identifier: BSD-2-Clause-Views
// Exclusive version-2 WRITE/READ control and bounded local capture BAR window.
// Legacy version-1 clients must reject this API. No host PCIe DMA or inbound MR.
// Physical frame admission/drain and peer MR lifetime remain external contracts.
`resetall
`timescale 1ns / 1ps
`default_nettype none

module rocev2_rw_control #(
    parameter ADDR_WIDTH=24,
    parameter WINDOW=32,
    parameter RESET_CYCLES=16,
    parameter INIT_CYCLES=4096,
    parameter SETTLE_CYCLES=64,
    parameter CAPACITY_BYTES=262144,
    parameter RUN_ID_WIDTH=32
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
    output wire read_mode,
    output wire [31:0] run_id,
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
    input wire [95:0] s_axis_capture_cmd_tdata,
    input wire s_axis_capture_cmd_tvalid,
    output wire s_axis_capture_cmd_tready,
    input wire [511:0] s_axis_capture_tdata,
    input wire [63:0] s_axis_capture_tkeep,
    input wire s_axis_capture_tvalid,
    output wire s_axis_capture_tready,
    input wire s_axis_capture_tlast,
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
    if (ADDR_WIDTH<19 || CAPACITY_BYTES<64 || CAPACITY_BYTES>262144 || RUN_ID_WIDTH<1 || RUN_ID_WIDTH>32) begin
        $error("RW API requires capture-window address space"); $finish;
    end
end
localparam RAM_BASE=24'h010000;
reg [31:0] config_regs[0:17];
reg mode=0;
reg [31:0] run_counter=0;
localparam [31:0] RUN_ID_MAX=(64'd1<<RUN_ID_WIDTH)-64'd1;
assign run_id=run_counter;
reg [31:0] read_window=1;
reg start=0,clear=0,abort_run=0;
assign read_mode=mode;
assign local_mac={config_regs[1][15:0],config_regs[0]};
assign peer_mac={config_regs[3][15:0],config_regs[2]};
assign local_ip=config_regs[4];
assign peer_ip=config_regs[5];
assign local_qpn=config_regs[6][23:0];
wire ethernet_config_valid=local_mac!=0 && peer_mac!=0 && !local_mac[40] && !peer_mac[40] &&
    local_ip!=0 && peer_ip!=0 && local_ip!=peer_ip;

wire w_ready,w_reset,w_halt,w_rx,w_busy,w_done,w_failed;
wire r_ready,r_reset,r_halt,r_rx,r_busy,r_done,r_failed,r_capture_enable;
wire [3:0] w_state,r_state;
wire [31:0] w_error,w_issued,w_acked,w_dups,w_total;
wire [31:0] r_error,r_issued,r_acked,r_dups,r_total,lease_bytes;
wire [63:0] w_elapsed,r_elapsed;
wire [183:0] w_qp,w_conn,r_qp,r_conn;
wire w_qv,w_cv,w_sv,r_qv,r_cv,r_sv,r_sr;
wire [239:0] w_sq,r_sq;
wire [3:0] state=mode ? r_state : w_state;
wire [31:0] error=mode ? r_error : w_error;
wire [31:0] issued=mode ? r_issued : w_issued;
wire [31:0] acked=mode ? r_acked : w_acked;
wire [31:0] duplicates=mode ? r_dups : w_dups;
wire [31:0] total=mode ? r_total : w_total;
wire [63:0] elapsed=mode ? r_elapsed : w_elapsed;
wire all_idle=w_state==0 && r_state==0;
assign core_reset=mode ? r_reset : w_reset;
assign halt_tx=mode ? r_halt : w_halt;
assign rx_enable=mode ? r_rx : w_rx;
assign busy=w_busy || r_busy;
assign done=mode ? r_done : w_done;
assign failed=mode ? r_failed : w_failed;
assign m_axis_qp_tdata=mode ? r_qp : w_qp;
assign m_axis_qp_tvalid=mode ? r_qv : w_qv;
assign m_axis_conn_tdata=mode ? r_conn : w_conn;
assign m_axis_conn_tvalid=mode ? r_cv : w_cv;
assign s_axis_ack_tready=1'b1;

wire capture_fault,capture_idle,capture_host_idle,descriptor_ready;
wire [7:0] capture_error;
wire [31:0] capture_authorized,capture_committed,capture_bytes,capture_padding,capture_commands;
reg descriptor_fault=0,read_sq_reserved=0;
// Reserve one available descriptor slot before asserting HLS TVALID. With
// this single producer, no other command can consume that reserved capacity.
// Valid/data then stay stable even if a fault stops the sink during a stall.
// Authorization is committed on the ACTUAL HLS SQ handshake, never on START.
assign m_axis_sq_tdata=mode ? r_sq : w_sq;
assign m_axis_sq_tvalid=mode ? r_sv && read_sq_reserved : w_sv;
assign r_sr=m_axis_sq_tready && read_sq_reserved && mode;
wire read_sq_transfer=mode && m_axis_sq_tvalid && m_axis_sq_tready;
always @(posedge clk) begin
    if (rst || start) descriptor_fault<=0;
    else if (read_sq_transfer && !descriptor_ready) descriptor_fault<=1;
    if (rst || core_reset || !mode) read_sq_reserved<=0;
    else if (read_sq_transfer) read_sq_reserved<=0;
    else if (!read_sq_reserved && r_sv && descriptor_ready) read_sq_reserved<=1;
end

wire pattern_fault;
wire [31:0] read_commands;
wire [63:0] read_bytes;
wire unexpected_capture=!mode && (s_axis_capture_cmd_tvalid || s_axis_capture_tvalid);
wire unexpected_source=mode && s_axis_mem_cmd_tvalid;
wire pattern_cmd_ready;
rocev2_write_engine #(.WINDOW(WINDOW),.RESET_CYCLES(RESET_CYCLES),.INIT_CYCLES(INIT_CYCLES),.SETTLE_CYCLES(SETTLE_CYCLES)) write_engine (
    .clk(clk),.rst(rst),.start(start && !mode),.clear(clear),.abort_run(abort_run && !mode),.start_ready(w_ready),
    .cfg_local_qpn(local_qpn),.cfg_peer_qpn(config_regs[7][23:0]),
    .cfg_tx_psn(config_regs[8][23:0]),.cfg_peer_psn(config_regs[9][23:0]),.cfg_peer_ip(peer_ip),
    .cfg_rkey(config_regs[10]),.cfg_remote_address({config_regs[13],config_regs[12]}),
    .cfg_remote_bytes({config_regs[15],config_regs[14]}),.cfg_message_bytes(config_regs[11]),
    .cfg_message_count(config_regs[16]),.cfg_timeout_cycles(config_regs[17]),
    .tx_quiescent(tx_quiescent),.memory_fault(pattern_fault || unexpected_capture || unexpected_memory_write),
    .core_reset(w_reset),.halt_tx(w_halt),.rx_enable(w_rx),.busy(w_busy),.done(w_done),.failed(w_failed),.state(w_state),
    .error_code(w_error),.issued_count(w_issued),.acked_count(w_acked),.duplicate_ack_count(w_dups),.total_bytes(w_total),.elapsed_cycles(w_elapsed),
    .m_axis_qp_tdata(w_qp),.m_axis_qp_tvalid(w_qv),.m_axis_qp_tready(m_axis_qp_tready && !mode),
    .m_axis_conn_tdata(w_conn),.m_axis_conn_tvalid(w_cv),.m_axis_conn_tready(m_axis_conn_tready && !mode),
    .m_axis_sq_tdata(w_sq),.m_axis_sq_tvalid(w_sv),.m_axis_sq_tready(m_axis_sq_tready && !mode),
    .s_axis_ack_tdata(s_axis_ack_tdata),.s_axis_ack_tvalid(s_axis_ack_tvalid && !mode),.s_axis_ack_tready()
);
rocev2_read_engine #(.MAX_WINDOW(WINDOW),.RESET_CYCLES(RESET_CYCLES),.INIT_CYCLES(INIT_CYCLES),
    .SETTLE_CYCLES(SETTLE_CYCLES),.CAPACITY_BYTES(CAPACITY_BYTES)) read_engine (
    .clk(clk),.rst(rst),.start(start && mode),.clear(clear),.abort_run(abort_run && mode),.start_ready(r_ready),
    .cfg_local_qpn(local_qpn),.cfg_peer_qpn(config_regs[7][23:0]),
    .cfg_tx_psn(config_regs[8][23:0]),.cfg_peer_psn(config_regs[9][23:0]),.cfg_peer_ip(peer_ip),
    .cfg_rkey(config_regs[10]),.cfg_remote_address({config_regs[13],config_regs[12]}),
    .cfg_remote_bytes({config_regs[15],config_regs[14]}),.cfg_message_bytes(config_regs[11]),
    .cfg_message_count(config_regs[16]),.cfg_read_window(read_window),.cfg_timeout_cycles(config_regs[17]),
    .tx_quiescent(tx_quiescent),.memory_fault(capture_fault || descriptor_fault || unexpected_source || unexpected_memory_write),
    .capture_idle(capture_idle),.capture_host_idle(capture_host_idle),
    .captured_count(capture_committed),.captured_bytes(capture_bytes),.capture_clear(),.capture_enable(r_capture_enable),
    .lease_bytes(lease_bytes),.core_reset(r_reset),.halt_tx(r_halt),.rx_enable(r_rx),
    .busy(r_busy),.done(r_done),.failed(r_failed),.state(r_state),
    .error_code(r_error),.issued_count(r_issued),.acked_count(r_acked),.duplicate_ack_count(r_dups),
    .total_bytes(r_total),.elapsed_cycles(r_elapsed),
    .m_axis_qp_tdata(r_qp),.m_axis_qp_tvalid(r_qv),.m_axis_qp_tready(m_axis_qp_tready && mode),
    .m_axis_conn_tdata(r_conn),.m_axis_conn_tvalid(r_cv),.m_axis_conn_tready(m_axis_conn_tready && mode),
    .m_axis_sq_tdata(r_sq),.m_axis_sq_tvalid(r_sv),.m_axis_sq_tready(r_sr),
    .s_axis_ack_tdata(s_axis_ack_tdata),.s_axis_ack_tvalid(s_axis_ack_tvalid && mode),.s_axis_ack_tready()
);
rocev2_pattern_source memory_source (
    .clk(clk),.rst(core_reset || mode),.enable(!core_reset && !mode),.total_bytes(total),
    .s_axis_cmd_tdata(s_axis_mem_cmd_tdata),.s_axis_cmd_tvalid(s_axis_mem_cmd_tvalid && !mode),.s_axis_cmd_tready(pattern_cmd_ready),
    .m_axis_tdata(m_axis_mem_tdata),.m_axis_tkeep(m_axis_mem_tkeep),.m_axis_tvalid(m_axis_mem_tvalid),
    .m_axis_tready(m_axis_mem_tready),.m_axis_tlast(m_axis_mem_tlast),.fault(pattern_fault),
    .command_count(read_commands),.supplied_bytes(read_bytes)
);
assign s_axis_mem_cmd_tready=mode ? 1'b1 : pattern_cmd_ready;

reg ram_request_valid=0,ram_owner_write=0,ram_inflight=0;
reg [31:0] ram_address=0,ram_wdata=0;
reg [3:0] ram_wstrb=0;
wire ram_ready,ram_response_valid,ram_response_error;
wire [31:0] ram_rdata;
wire ram_response_ready=ram_inflight && (ram_owner_write ? !s_axil_bvalid : !s_axil_rvalid);
wire capture_cmd_ready,capture_data_ready;
rocev2_read_buffer #(.CAPACITY_BYTES(CAPACITY_BYTES)) capture (
    .clk(clk),.rst(rst),.clear(start),.capture_enable(mode && r_capture_enable && !core_reset),
    .local_qpn(local_qpn[9:0]),.lease_bytes(lease_bytes),
    .s_axis_desc_address(r_sq[79:48]),.s_axis_desc_length(r_sq[207:176]),
    .s_axis_desc_valid(read_sq_transfer && descriptor_ready),.s_axis_desc_ready(descriptor_ready),
    .s_axis_cmd_tdata(s_axis_capture_cmd_tdata),.s_axis_cmd_tvalid(s_axis_capture_cmd_tvalid && mode),
    .s_axis_cmd_tready(capture_cmd_ready),.s_axis_tdata(s_axis_capture_tdata),.s_axis_tkeep(s_axis_capture_tkeep),
    .s_axis_tvalid(s_axis_capture_tvalid && mode),.s_axis_tready(capture_data_ready),.s_axis_tlast(s_axis_capture_tlast),
    .host_address(ram_address),.host_write(ram_owner_write),.host_wdata(ram_wdata),.host_wstrb(ram_wstrb),
    .host_valid(ram_request_valid),.host_ready(ram_ready),.host_rdata(ram_rdata),.host_error(ram_response_error),
    .host_response_valid(ram_response_valid),.host_response_ready(ram_response_ready),
    .idle(capture_idle),.host_idle(capture_host_idle),.fault(capture_fault),.error_code(capture_error),
    .authorized_count(capture_authorized),.committed_count(capture_committed),
    .committed_bytes(capture_bytes),.padding_bytes(capture_padding),.command_count(capture_commands)
);
assign s_axis_capture_cmd_tready=mode ? capture_cmd_ready : 1'b1;
assign s_axis_capture_tready=mode ? capture_data_ready : 1'b1;

// One outstanding RAM request, with independently buffered AW/W and AR.
// A second owner cannot take over the host RAM port before its response.
reg aw_pending=0,w_pending=0,read_ram_pending=0;
reg [ADDR_WIDTH-1:0] awaddr=0,read_ram_address=0;
reg [31:0] wdata=0;
reg [3:0] wstrb=0;
reg [31:0] rejected_writes=0,last_rejection=0;
assign s_axil_awready=!aw_pending && !s_axil_bvalid && !(ram_owner_write && (ram_request_valid || ram_inflight));
assign s_axil_wready=!w_pending && !s_axil_bvalid && !(ram_owner_write && (ram_request_valid || ram_inflight));
assign s_axil_arready=!s_axil_rvalid && !read_ram_pending && !(!ram_owner_write && (ram_request_valid || ram_inflight));
wire write_commit=aw_pending && w_pending && !s_axil_bvalid && !ram_request_valid && !ram_inflight;
wire config_address=awaddr>=64 && awaddr<=132 && awaddr[1:0]==0;
wire read_config_address=s_axil_araddr>=64 && s_axil_araddr<=132 && s_axil_araddr[1:0]==0;
wire write_ram_address=awaddr>=RAM_BASE && awaddr<RAM_BASE+CAPACITY_BYTES;
wire read_ram_window=s_axil_araddr>=RAM_BASE && s_axil_araddr<RAM_BASE+CAPACITY_BYTES;
wire read_ram_accept=s_axil_arvalid && s_axil_arready && read_ram_window;
wire read_diagnostic_address=s_axil_araddr>=144 && s_axil_araddr<=204 && s_axil_araddr[1:0]==0;
wire [4:0] config_index=awaddr[6:2]-5'd16;
wire [4:0] read_config_index=s_axil_araddr[6:2]-5'd16;
wire [3:0] diagnostic_index=s_axil_araddr[5:2]-4'd4;
wire [31:0] byte_mask={{8{wstrb[3]}},{8{wstrb[2]}},{8{wstrb[1]}},{8{wstrb[0]}}};
wire [31:0] write_mask=(config_index==1 || config_index==3) ? 32'h0000ffff :
    (config_index>=6 && config_index<=9) ? 32'h00ffffff : 32'hffffffff;
wire [31:0] next_mode_data=({31'd0,mode} & ~byte_mask) | (wdata & byte_mask);
wire memory_access_locked=busy || start || clear || abort_run;
wire start_ready=(mode ? r_ready : w_ready) && all_idle && capture_host_idle &&
    !ram_request_valid && !ram_inflight && !read_ram_pending && !read_ram_accept && !s_axil_rvalid;
reg [31:0] write_error;
always @* begin
    write_error=0;
    if (awaddr[1:0]!=0) write_error=1;
    else if (config_address || awaddr==24'h100 || awaddr==24'h104) begin
        if (wstrb!=0 && (!all_idle || start)) write_error=2;
        else if (awaddr==24'h100 && next_mode_data>1) write_error=3;
    end else if (write_ram_address) begin
        if (memory_access_locked) write_error=2;
    end else if (awaddr==8) begin
        if (!wstrb[0] || wdata[7:0]==0) write_error=0;
        else if (wdata[7:0]==1) begin
            if (!start_ready) write_error=2;
            else if (!ethernet_config_valid) write_error=4;
            else if (run_counter==RUN_ID_MAX) write_error=5;
        end else if (wdata[7:0]==2) begin if (busy || ram_request_valid || ram_inflight) write_error=2; end
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
        config_regs[6]<=2;config_regs[8]<=32'h00123456;config_regs[9]<=32'h00654321;
        config_regs[11]<=64;config_regs[16]<=1;config_regs[17]<=250000000;
        mode<=0;run_counter<=0;read_window<=1;start<=0;clear<=0;abort_run<=0;
        aw_pending<=0;w_pending<=0;awaddr<=0;wdata<=0;wstrb<=0;
        ram_request_valid<=0;ram_owner_write<=0;ram_inflight<=0;read_ram_pending<=0;
        ram_address<=0;ram_wdata<=0;ram_wstrb<=0;read_ram_address<=0;
        rejected_writes<=0;last_rejection<=0;
        saved_read_commands<=0;saved_read_bytes<=0;saved_diagnostics<=0;
        s_axil_bvalid<=0;s_axil_bresp<=0;s_axil_rvalid<=0;s_axil_rdata<=0;s_axil_rresp<=0;
    end else begin
        start<=0;clear<=0;abort_run<=0;
        if (!core_reset) begin
            saved_read_commands<=read_commands;saved_read_bytes<=read_bytes;saved_diagnostics<=diagnostics;
        end
        if (s_axil_bvalid && s_axil_bready) s_axil_bvalid<=0;
        if (s_axil_rvalid && s_axil_rready) s_axil_rvalid<=0;
        if (s_axil_awvalid && s_axil_awready) begin awaddr<=s_axil_awaddr;aw_pending<=1;end
        if (s_axil_wvalid && s_axil_wready) begin wdata<=s_axil_wdata;wstrb<=s_axil_wstrb;w_pending<=1;end

        if (ram_request_valid && ram_ready) begin ram_request_valid<=0;ram_inflight<=1;end
        if (ram_response_valid && ram_response_ready) begin
            ram_inflight<=0;
            if (ram_owner_write) begin
                s_axil_bvalid<=1;s_axil_bresp<=ram_response_error ? 2'b10 : 2'b00;
                if (ram_response_error) begin rejected_writes<=rejected_writes+1'b1;last_rejection<=2;end
            end else begin
                s_axil_rvalid<=1;s_axil_rdata<=ram_rdata;s_axil_rresp<=ram_response_error ? 2'b10 : 2'b00;
            end
        end
        if (write_commit) begin
            aw_pending<=0;w_pending<=0;
            if (write_ram_address && write_error==0) begin
                ram_request_valid<=1;ram_owner_write<=1;
                ram_address<=awaddr-RAM_BASE;ram_wdata<=wdata;ram_wstrb<=wstrb;
            end else begin
                s_axil_bvalid<=1;s_axil_bresp<=write_error==0 ? 2'b00 : 2'b10;
                if (write_error!=0) begin rejected_writes<=rejected_writes+1'b1;last_rejection<=write_error;end
                else if (config_address) config_regs[config_index]<=
                    ((config_regs[config_index] & ~byte_mask) | (wdata & byte_mask)) & write_mask;
                else if (awaddr==24'h100) mode<=next_mode_data[0];
                else if (awaddr==24'h104) read_window<=(read_window & ~byte_mask) | (wdata & byte_mask);
                else if (awaddr==8 && wstrb[0]) begin
                    if (wdata[7:0]==1) begin
                        start<=1;run_counter<=run_counter+1'b1;
                        saved_read_commands<=0;saved_read_bytes<=0;saved_diagnostics<=0;
                    end
                    if (wdata[7:0]==2) begin clear<=1;last_rejection<=0;end
                    if (wdata[7:0]==4) abort_run<=1;
                end
            end
        end
        // Writes win arbitration, but only one request owns the RAM port.
        if (read_ram_pending && !ram_request_valid && !ram_inflight &&
            !(write_commit && write_ram_address && write_error==0)) begin
            read_ram_pending<=0;
            if (memory_access_locked) begin s_axil_rvalid<=1;s_axil_rdata<=0;s_axil_rresp<=2'b10;end
            else begin
                ram_request_valid<=1;ram_owner_write<=0;ram_address<=read_ram_address-RAM_BASE;
                ram_wdata<=0;ram_wstrb<=0;
            end
        end
        if (s_axil_arvalid && s_axil_arready) begin
            if (read_ram_window && s_axil_araddr[1:0]==0 && !memory_access_locked) begin
                read_ram_pending<=1;read_ram_address<=s_axil_araddr;
            end else begin
                s_axil_rvalid<=1;s_axil_rresp<=0;s_axil_rdata<=0;
                if (s_axil_araddr[1:0]!=0 || (read_ram_window && memory_access_locked)) s_axil_rresp<=2'b10;
                else if (read_config_address) s_axil_rdata<=config_regs[read_config_index];
                else if (read_diagnostic_address) s_axil_rdata<=(done || failed) ?
                    saved_diagnostics[diagnostic_index*32+:32] : diagnostics[diagnostic_index*32+:32];
                else case (s_axil_araddr)
                    0: s_axil_rdata<=32'h524f4332;
                    4: s_axil_rdata<=32'h00020000;
                    8: s_axil_rdata<=0;
                    12: s_axil_rdata<={20'd0,state,mode,rx_enable,halt_tx,tx_quiescent,core_reset,failed,done,busy};
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
                    24'h100: s_axil_rdata<={31'd0,mode};
                    24'h104: s_axil_rdata<=read_window;
                    24'h108: s_axil_rdata<=CAPACITY_BYTES;
                    24'h10c: s_axil_rdata<=RAM_BASE;
                    24'h110: s_axil_rdata<=capture_committed;
                    24'h114: s_axil_rdata<=capture_bytes;
                    24'h118: s_axil_rdata<=capture_padding;
                    24'h11c: s_axil_rdata<=capture_commands;
                    24'h120: s_axil_rdata<={23'd0,descriptor_fault,capture_error};
                    24'h124: s_axil_rdata<=capture_authorized;
                    24'h128: s_axil_rdata<=lease_bytes;
                    24'h12c: s_axil_rdata<={29'd0,capture_host_idle,capture_idle,capture_fault};
                    24'h130: s_axil_rdata<=run_counter;
                    default: s_axil_rresp<=2'b10;
                endcase
            end
        end
    end
end
endmodule
`resetall
