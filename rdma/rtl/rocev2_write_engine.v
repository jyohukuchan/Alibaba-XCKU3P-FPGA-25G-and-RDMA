// SPDX-License-Identifier: BSD-2-Clause-Views
// Finite, windowed RC WRITE initiator control. No host DMA and no inbound MR.
// Each <=4096-byte request is one WRITE_ONLY; addresses cover disjoint ranges
// in the peer's explicitly granted MR. The surrounding Ethernet application
// MUST stop admitting new engine frames when halt_tx is asserted and assert
// tx_quiescent only after admitted frames/physical transmit tail have drained.
// Only then does this engine reset the transport or expose a terminal status.
`resetall
`timescale 1ns / 1ps
`default_nettype none

module rocev2_write_engine #(
    parameter QP_ENTRIES=8,
    parameter WINDOW=32,
    parameter RESET_CYCLES=16,
    parameter INIT_CYCLES=4096,
    parameter SETTLE_CYCLES=64,
    parameter MAX_TOTAL_BYTES=67108864
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
    input wire [31:0] cfg_timeout_cycles,
    input wire tx_quiescent,
    input wire memory_fault,
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

localparam IDLE=4'd0, RESET_CORE=4'd1, INIT_CORE=4'd2, SETUP_QP=4'd3,
    SETTLE=4'd4, RUN=4'd5, QUIESCE=4'd6, DONE=4'd7, ERROR=4'd8, VALIDATE=4'd9;
localparam ERR_CONFIG=32'd1, ERR_TIMEOUT=32'd2, ERR_ACK=32'd3,
    ERR_MEMORY=32'd4, ERR_ABORT=32'd5;
reg [3:0] state_reg=IDLE;
reg [31:0] phase_cycles=0;
reg [23:0] local_qpn=0, tx_psn=0;
reg [31:0] message_bytes=0,message_count=0,timeout_cycles=0;
reg [63:0] remote_address=0;
reg [31:0] local_offset=0;
// Valid operands need only 13 x 17 bits. Register the product BEFORE MR/total
// comparisons; a 32x32 multiply + 64-bit range checks in one cycle failed
// the actual KU3P 4ns physical check. Invalid upper bits are rejected below.
wire [29:0] requested_bytes=cfg_message_bytes[12:0]*cfg_message_count[16:0];
wire [64:0] remote_limit={1'b0,cfg_remote_address}+{1'b0,cfg_remote_bytes};
wire scalar_config_valid=cfg_local_qpn>=2 && cfg_local_qpn<QP_ENTRIES && cfg_peer_qpn>=2 &&
    cfg_message_bytes>=1 && cfg_message_bytes<=4096 &&
    cfg_message_count>=1 && cfg_message_count<=65536 &&
    cfg_timeout_cycles>RESET_CYCLES+INIT_CYCLES+SETTLE_CYCLES;
reg scalar_ok=0,remote_overflow=0,core_released=0;
reg [63:0] remote_bytes=0;
wire range_config_valid=scalar_ok && !remote_overflow && total_bytes<=MAX_TOTAL_BYTES && {32'd0,total_bytes}<=remote_bytes;
wire sq_transfer=m_axis_sq_tvalid && m_axis_sq_tready;
wire [31:0] issued_now=issued_count+{31'd0,sq_transfer};
wire [23:0] ack_offset=s_axis_ack_tdata[34:11]-tx_psn;
wire [31:0] ack_count={8'd0,ack_offset}+32'd1;
wire ack_metadata_valid=s_axis_ack_tdata[0] && s_axis_ack_tdata[10:1]==local_qpn[9:0] &&
    s_axis_ack_tdata[39:35]==0 && ack_count<=issued_now;

initial begin
    if (QP_ENTRIES<3 || QP_ENTRIES>1024 || WINDOW<1 || WINDOW>1024 ||
        RESET_CYCLES<1 || INIT_CYCLES<1 || SETTLE_CYCLES<1 || MAX_TOTAL_BYTES>67108864) begin
        $error("Invalid finite WRITE engine parameters"); $finish;
    end
end
function [31:0] axis_ip;
    input [31:0] ip;
    begin axis_ip={ip[7:0],ip[15:8],ip[23:16],ip[31:24]}; end
endfunction

assign state=state_reg;
assign core_reset=rst || !core_released || state_reg==IDLE || state_reg==DONE || state_reg==ERROR;
assign halt_tx=state_reg!=RUN;
assign rx_enable=state_reg==RUN || state_reg==QUIESCE;
assign start_ready=state_reg==IDLE && tx_quiescent;
assign done=state_reg==DONE;
assign failed=state_reg==ERROR;
assign busy=state_reg!=IDLE && state_reg!=DONE && state_reg!=ERROR;
assign s_axis_ack_tready=1'b1;

always @(posedge clk) begin
    if (rst) begin
        state_reg<=IDLE; phase_cycles<=0; local_qpn<=0; tx_psn<=0;
        message_bytes<=0; message_count<=0; timeout_cycles<=0;
        remote_address<=0; local_offset<=0;
        scalar_ok<=0; remote_overflow<=0; remote_bytes<=0; core_released<=0;
        error_code<=0; issued_count<=0; acked_count<=0; duplicate_ack_count<=0;
        total_bytes<=0; elapsed_cycles<=0;
        m_axis_qp_tdata<=0; m_axis_qp_tvalid<=0;
        m_axis_conn_tdata<=0; m_axis_conn_tvalid<=0;
        m_axis_sq_tdata<=0; m_axis_sq_tvalid<=0;
    end else begin
        if (state_reg==IDLE || state_reg==DONE || state_reg==ERROR) core_released<=0;
        if (busy) elapsed_cycles<=elapsed_cycles+1'b1;
        if (m_axis_qp_tvalid && m_axis_qp_tready) m_axis_qp_tvalid<=0;
        if (m_axis_conn_tvalid && m_axis_conn_tready) m_axis_conn_tvalid<=0;
        if (sq_transfer) begin
            m_axis_sq_tvalid<=0;
            if (!core_reset) begin
                issued_count<=issued_count+1'b1;
                local_offset<=local_offset+message_bytes;
            end
        end
        // A pending command is retained under backpressure, including during
        // quiescing; resetting both ends is the only permitted cancellation.
        if (core_reset) begin
            m_axis_qp_tvalid<=0; m_axis_conn_tvalid<=0; m_axis_sq_tvalid<=0;
        end
        case (state_reg)
            IDLE: if (start && start_ready) begin
                error_code<=0; issued_count<=0; acked_count<=0;
                duplicate_ack_count<=0; elapsed_cycles<=0; local_offset<=0; phase_cycles<=0;
                total_bytes<={2'd0,requested_bytes};
                scalar_ok<=scalar_config_valid; remote_overflow<=remote_limit[64]; remote_bytes<=cfg_remote_bytes;
                local_qpn<=cfg_local_qpn; tx_psn<=cfg_tx_psn;
                message_bytes<=cfg_message_bytes; message_count<=cfg_message_count;
                timeout_cycles<=cfg_timeout_cycles; remote_address<=cfg_remote_address;
                // Upstream names are misleading: state_table assigns
                // req_next_psn=remote_psn, resp_epsn=local_psn. Therefore
                // outgoing PSN goes in bits 79:56, peer PSN in 103:80.
                m_axis_qp_tdata<={cfg_rkey,48'd0,cfg_peer_psn,cfg_tx_psn,cfg_local_qpn,32'd3};
                m_axis_conn_tdata<={16'd4791,{4{axis_ip(cfg_peer_ip)}},cfg_peer_qpn,cfg_local_qpn[15:0]};
                state_reg<=VALIDATE;
            end
            VALIDATE: begin
                if (range_config_valid) state_reg<=RESET_CORE;
                else begin state_reg<=ERROR; error_code<=ERR_CONFIG; end
            end
            RESET_CORE: begin
                if (phase_cycles==RESET_CYCLES-1) begin phase_cycles<=0; state_reg<=INIT_CORE; core_released<=1; end
                else phase_cycles<=phase_cycles+1'b1;
            end
            INIT_CORE: begin
                if (phase_cycles==INIT_CYCLES-1) begin
                    phase_cycles<=0; state_reg<=SETUP_QP;
                    m_axis_qp_tvalid<=1; m_axis_conn_tvalid<=1;
                end else phase_cycles<=phase_cycles+1'b1;
            end
            SETUP_QP: if ((!m_axis_qp_tvalid || m_axis_qp_tready) &&
                (!m_axis_conn_tvalid || m_axis_conn_tready)) begin
                phase_cycles<=0; state_reg<=SETTLE;
            end
            SETTLE: begin
                if (phase_cycles==SETTLE_CYCLES-1) begin phase_cycles<=0; state_reg<=RUN; end
                else phase_cycles<=phase_cycles+1'b1;
            end
            RUN: begin
                if (!m_axis_sq_tvalid && issued_count<message_count && issued_count-acked_count<WINDOW) begin
                    m_axis_sq_tdata<={32'd0,message_bytes,remote_address+{32'd0,local_offset},
                        32'd0,local_offset,4'd0,1'b1,1'b0,local_qpn[9:0],32'd10};
                    m_axis_sq_tvalid<=1;
                end
                if (s_axis_ack_tvalid) begin
                    if (!ack_metadata_valid) begin error_code<=ERR_ACK; state_reg<=QUIESCE; end
                    else if (ack_count>acked_count) acked_count<=ack_count;
                    else duplicate_ack_count<=duplicate_ack_count+1'b1;
                end
                if (issued_count==message_count && acked_count==message_count) state_reg<=QUIESCE;
            end
            QUIESCE: if (tx_quiescent) state_reg<=error_code==0 ? DONE : ERROR;
            DONE,ERROR: if (clear) state_reg<=IDLE;
            default: begin state_reg<=ERROR; error_code<=ERR_CONFIG; end
        endcase
        if (busy && state_reg!=QUIESCE) begin
            if (state_reg!=VALIDATE && elapsed_cycles>={32'd0,timeout_cycles}) begin error_code<=ERR_TIMEOUT; state_reg<=QUIESCE; end
            if (memory_fault) begin error_code<=ERR_MEMORY; state_reg<=QUIESCE; end
            if (abort_run) begin error_code<=ERR_ABORT; state_reg<=QUIESCE; end
        end
    end
end
endmodule
`resetall
