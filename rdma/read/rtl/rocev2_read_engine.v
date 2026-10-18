// SPDX-License-Identifier: BSD-2-Clause-Views
// Finite RC READ initiator. Transport completions and RAM commits are
// separate: DONE requires both, then the unchanged physical-TX drain.
// Connect each accepted SQ to the protected buffer's descriptor input;
// SQ ready MUST include both transport and descriptor capacity.
`resetall
`timescale 1ns / 1ps
`default_nettype none

module rocev2_read_engine #(
    parameter QP_ENTRIES=8,
    parameter MAX_WINDOW=32,
    parameter RESET_CYCLES=16,
    parameter INIT_CYCLES=4096,
    parameter SETTLE_CYCLES=64,
    parameter CAPACITY_BYTES=262144
)(
    input wire clk,
    input wire rst,
    input wire start,
    input wire clear,
    input wire abort_run,
    output wire start_ready,
    input wire [23:0] cfg_local_qpn,
    input wire [23:0] cfg_peer_qpn,
    input wire [23:0] cfg_tx_psn,
    input wire [23:0] cfg_peer_psn,
    input wire [31:0] cfg_peer_ip,
    input wire [31:0] cfg_rkey,
    input wire [63:0] cfg_remote_address,
    input wire [63:0] cfg_remote_bytes,
    input wire [31:0] cfg_message_bytes,
    input wire [31:0] cfg_message_count,
    input wire [31:0] cfg_read_window,
    input wire [31:0] cfg_timeout_cycles,
    input wire tx_quiescent,
    input wire memory_fault,
    input wire capture_idle,
    input wire capture_host_idle,
    input wire [31:0] captured_count,
    input wire [31:0] captured_bytes,
    output wire capture_clear,
    output wire capture_enable,
    output reg [31:0] lease_bytes=0,
    output wire core_reset,
    output wire halt_tx,
    output wire rx_enable,
    output wire busy,
    output wire done,
    output wire failed,
    output wire [3:0] state,
    output reg [31:0] error_code=0,
    output reg [31:0] issued_count=0,
    output reg [31:0] acked_count=0,
    output reg [31:0] duplicate_ack_count=0,
    output reg [31:0] total_bytes=0,
    output reg [63:0] elapsed_cycles=0,
    output reg [183:0] m_axis_qp_tdata=0,
    output reg m_axis_qp_tvalid=0,
    input wire m_axis_qp_tready,
    output reg [183:0] m_axis_conn_tdata=0,
    output reg m_axis_conn_tvalid=0,
    input wire m_axis_conn_tready,
    output reg [239:0] m_axis_sq_tdata=0,
    output reg m_axis_sq_tvalid=0,
    input wire m_axis_sq_tready,
    input wire [39:0] s_axis_ack_tdata,
    input wire s_axis_ack_tvalid,
    output wire s_axis_ack_tready
);
localparam IDLE=4'd0,RESET_CORE=4'd1,INIT_CORE=4'd2,SETUP_QP=4'd3,
    SETTLE=4'd4,RUN=4'd5,QUIESCE=4'd6,DONE=4'd7,ERROR=4'd8,VALIDATE=4'd9;
localparam ERR_CONFIG=32'd1,ERR_TIMEOUT=32'd2,ERR_ACK=32'd3,ERR_MEMORY=32'd4,ERR_ABORT=32'd5;
reg [3:0] state_reg=IDLE;
reg core_released=0,scalar_ok=0,remote_overflow=0;
reg [31:0] phase_cycles=0,message_bytes=0,message_count=0,read_window=0,timeout_cycles=0,stride=0;
reg [31:0] local_offset=0;
reg [63:0] remote_address=0,remote_bytes=0;
reg [23:0] local_qpn=0,next_completion_psn=0,last_completion_psn=0;
reg [4:0] response_packets=0;
wire [31:0] configured_stride=(cfg_message_bytes+32'd63)&~32'd63;
wire [29:0] configured_allocation=configured_stride[16:0]*cfg_message_count[12:0];
wire [29:0] configured_payload=cfg_message_bytes[16:0]*cfg_message_count[12:0];
wire [4:0] configured_packets=(cfg_message_bytes+32'd4095)>>12;
wire [64:0] remote_limit={1'b0,cfg_remote_address}+{1'b0,cfg_remote_bytes};
wire scalar_valid=cfg_local_qpn>=2 && cfg_local_qpn<QP_ENTRIES && cfg_peer_qpn>=2 &&
    cfg_message_bytes>=1 && cfg_message_bytes<=65536 &&
    cfg_message_count>=1 && cfg_message_count<=4096 &&
    cfg_read_window>=1 && cfg_read_window<=MAX_WINDOW &&
    cfg_timeout_cycles>RESET_CYCLES+INIT_CYCLES+SETTLE_CYCLES;
wire range_valid=scalar_ok && !remote_overflow && lease_bytes<=CAPACITY_BYTES &&
    {32'd0,total_bytes}<=remote_bytes;
wire sq_transfer=m_axis_sq_tvalid && m_axis_sq_tready;
wire [31:0] issued_now=issued_count+{31'd0,sq_transfer};
wire completion_shape=!s_axis_ack_tdata[0] && s_axis_ack_tdata[10:1]==local_qpn[9:0] &&
    s_axis_ack_tdata[39:35]==0;
wire completion_next=s_axis_ack_tdata[34:11]==next_completion_psn && acked_count<issued_now;
wire completion_duplicate=acked_count!=0 && s_axis_ack_tdata[34:11]==last_completion_psn;

function [31:0] axis_ip;
    input [31:0] ip;
    begin axis_ip={ip[7:0],ip[15:8],ip[23:16],ip[31:24]};end
endfunction
initial begin
    if (QP_ENTRIES<3 || QP_ENTRIES>1024 || MAX_WINDOW<1 || MAX_WINDOW>32 ||
        RESET_CYCLES<1 || INIT_CYCLES<1 || SETTLE_CYCLES<1 ||
        CAPACITY_BYTES<64 || CAPACITY_BYTES>262144) begin
        $error("Invalid finite READ engine parameters");$finish;
    end
end
assign state=state_reg;
assign core_reset=rst || !core_released || state_reg==IDLE || state_reg==DONE || state_reg==ERROR;
assign halt_tx=state_reg!=RUN;
assign rx_enable=state_reg==RUN || state_reg==QUIESCE;
assign capture_enable=rx_enable;
assign capture_clear=start && start_ready;
assign start_ready=state_reg==IDLE && tx_quiescent && capture_host_idle;
assign done=state_reg==DONE;
assign failed=state_reg==ERROR;
assign busy=state_reg!=IDLE && state_reg!=DONE && state_reg!=ERROR;
assign s_axis_ack_tready=1'b1;

always @(posedge clk) begin
    if (rst) begin
        state_reg<=IDLE;core_released<=0;scalar_ok<=0;remote_overflow<=0;
        phase_cycles<=0;message_bytes<=0;message_count<=0;read_window<=0;timeout_cycles<=0;stride<=0;
        local_offset<=0;remote_address<=0;remote_bytes<=0;local_qpn<=0;
        next_completion_psn<=0;last_completion_psn<=0;response_packets<=0;
        lease_bytes<=0;error_code<=0;issued_count<=0;acked_count<=0;duplicate_ack_count<=0;
        total_bytes<=0;elapsed_cycles<=0;
        m_axis_qp_tdata<=0;m_axis_qp_tvalid<=0;m_axis_conn_tdata<=0;m_axis_conn_tvalid<=0;
        m_axis_sq_tdata<=0;m_axis_sq_tvalid<=0;
    end else begin
        if (state_reg==IDLE || state_reg==DONE || state_reg==ERROR) core_released<=0;
        if (busy) elapsed_cycles<=elapsed_cycles+1'b1;
        if (m_axis_qp_tvalid && m_axis_qp_tready) m_axis_qp_tvalid<=0;
        if (m_axis_conn_tvalid && m_axis_conn_tready) m_axis_conn_tvalid<=0;
        if (sq_transfer) begin
            m_axis_sq_tvalid<=0;
            if (!core_reset) begin
                issued_count<=issued_count+1'b1;local_offset<=local_offset+stride;
                remote_address<=remote_address+{32'd0,message_bytes};
            end
        end
        if (core_reset) begin
            m_axis_qp_tvalid<=0;m_axis_conn_tvalid<=0;m_axis_sq_tvalid<=0;
        end
        case (state_reg)
            IDLE: if (start && start_ready) begin
                error_code<=0;issued_count<=0;acked_count<=0;duplicate_ack_count<=0;elapsed_cycles<=0;
                phase_cycles<=0;local_offset<=0;total_bytes<={2'd0,configured_payload};
                lease_bytes<={2'd0,configured_allocation};scalar_ok<=scalar_valid;
                remote_overflow<=remote_limit[64];remote_bytes<=cfg_remote_bytes;
                message_bytes<=cfg_message_bytes;message_count<=cfg_message_count;read_window<=cfg_read_window;
                timeout_cycles<=cfg_timeout_cycles;stride<=configured_stride;
                remote_address<=cfg_remote_address;local_qpn<=cfg_local_qpn;
                response_packets<=configured_packets;
                next_completion_psn<=cfg_tx_psn+{19'd0,configured_packets}-24'd1;
                last_completion_psn<=0;
                m_axis_qp_tdata<={cfg_rkey,48'd0,cfg_peer_psn,cfg_tx_psn,cfg_local_qpn,32'd3};
                m_axis_conn_tdata<={16'd4791,{4{axis_ip(cfg_peer_ip)}},cfg_peer_qpn,cfg_local_qpn[15:0]};
                state_reg<=VALIDATE;
            end
            VALIDATE: begin
                if (range_valid) state_reg<=RESET_CORE;
                else begin state_reg<=ERROR;error_code<=ERR_CONFIG;end
            end
            RESET_CORE: begin
                if (phase_cycles==RESET_CYCLES-1) begin phase_cycles<=0;state_reg<=INIT_CORE;core_released<=1;end
                else phase_cycles<=phase_cycles+1'b1;
            end
            INIT_CORE: begin
                if (phase_cycles==INIT_CYCLES-1) begin
                    phase_cycles<=0;state_reg<=SETUP_QP;m_axis_qp_tvalid<=1;m_axis_conn_tvalid<=1;
                end else phase_cycles<=phase_cycles+1'b1;
            end
            SETUP_QP: if ((!m_axis_qp_tvalid || m_axis_qp_tready) &&
                          (!m_axis_conn_tvalid || m_axis_conn_tready)) begin
                phase_cycles<=0;state_reg<=SETTLE;
            end
            SETTLE: begin
                if (phase_cycles==SETTLE_CYCLES-1) begin phase_cycles<=0;state_reg<=RUN;end
                else phase_cycles<=phase_cycles+1'b1;
            end
            RUN: begin
                if (!m_axis_sq_tvalid && issued_count<message_count && issued_count-acked_count<read_window) begin
                    m_axis_sq_tdata<={32'd0,message_bytes,remote_address,32'd0,local_offset,
                                     4'd0,1'b1,1'b1,local_qpn[9:0],32'd12};
                    m_axis_sq_tvalid<=1;
                end
                if (s_axis_ack_tvalid) begin
                    if (!completion_shape || (!completion_next && !completion_duplicate)) begin
                        error_code<=ERR_ACK;state_reg<=QUIESCE;
                    end else if (completion_next) begin
                        acked_count<=acked_count+1'b1;last_completion_psn<=next_completion_psn;
                        next_completion_psn<=next_completion_psn+{19'd0,response_packets};
                    end else duplicate_ack_count<=duplicate_ack_count+1'b1;
                end
                if (issued_count==message_count && acked_count==message_count &&
                    captured_count==message_count && captured_bytes==total_bytes && capture_idle)
                    state_reg<=QUIESCE;
            end
            QUIESCE: if (tx_quiescent) state_reg<=error_code==0 ? DONE : ERROR;
            DONE,ERROR: if (clear) state_reg<=IDLE;
            default: begin state_reg<=ERROR;error_code<=ERR_CONFIG;end
        endcase
        if (busy && state_reg!=QUIESCE) begin
            if (state_reg!=VALIDATE && elapsed_cycles>={32'd0,timeout_cycles}) begin
                error_code<=ERR_TIMEOUT;state_reg<=QUIESCE;
            end
            if (memory_fault || captured_count>issued_now || captured_bytes>total_bytes) begin
                error_code<=ERR_MEMORY;state_reg<=QUIESCE;
            end
            if (abort_run) begin error_code<=ERR_ABORT;state_reg<=QUIESCE;end
        end
    end
end
endmodule
`resetall
