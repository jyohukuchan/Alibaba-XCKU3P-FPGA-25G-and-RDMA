// SPDX-License-Identifier: BSD-2-Clause-Views
// Copyright (c) 2026 jyohukuchan
// Exclusive MR/PTE/QP publication sequencer. No CPU payload copying.
// Own ALL raw config ports of the paged responder; no bypass/config alias.
// Parent drain is REAL app-descriptor/TLP/RAM drain evidence, never a timeout
// or a constant in a live profile. Reset is coordinated with drained parent
// DMA/closed QPs and fresh retained host key epoch; NOT cancellation/unpin.
`resetall
`timescale 1ns/1ps
`default_nettype none
module rocev2_mr_control #(parameter QP_TX_ENABLE=0) (
    input wire clk,
    input wire rst,
    // 1EPOCH,2BEGIN,3PAGE,4SEAL,5INVALIDATE,6QP,7RUN,8STOP.
    // cookie identifies the MR owner; sequence identifies EACH subcommand.
    input wire [7:0] s_command,
    input wire [31:0] s_sequence,
    input wire [63:0] s_cookie,
    input wire [2:0] s_slot,
    input wire [31:0] s_key,
    input wire [15:0] s_pd,
    input wire [63:0] s_virtual_address,
    input wire [31:0] s_length,
    input wire [3:0] s_access,
    input wire [11:0] s_first_offset,
    input wire [7:0] s_page_index,
    input wire [63:0] s_dma_page,
    input wire [2:0] s_qp_number,
    input wire [23:0] s_peer_qp_number,
    input wire [31:0] s_local_ip,
    input wire [31:0] s_peer_ip,
    input wire [23:0] s_rx_psn,
    input wire [23:0] s_tx_psn,
    input wire s_valid,
    output wire s_ready,
    output reg [7:0] m_command=0,
    output reg [31:0] m_sequence=0,
    output reg [63:0] m_cookie=0,
    output reg [2:0] m_slot=0,
    output reg [31:0] m_key=0,
    output reg [7:0] m_error=0,
    // bit0invalidated,1DMA-drained,2QPs-closed,3MR-table-invalid,4published.
    output reg [7:0] m_flags=0,
    output reg m_valid=0,
    input wire m_ready,
    input wire endpoint_quiescent,
    input wire endpoint_qp_ready,
    input wire endpoint_fault,
    input wire parent_dma_drained,
    output wire admission_pause,
    output wire busy,
    output reg epoch_ready=0,
    output reg qp_configured=0,
    output reg run_requested=0,
    output reg fatal=0,
    output reg [7:0] fatal_code=0,
    output reg [7:0] building=0,
    output reg [7:0] active=0,
    output reg [7:0] tainted=0,
    output reg [31:0] last_sequence=0,
    output reg [1:0] cfg_mr_command=0,
    output wire [2:0] cfg_mr_index,
    output wire [15:0] cfg_mr_pd,
    output wire [31:0] cfg_mr_key,
    output wire [63:0] cfg_mr_virtual_address,
    output wire [63:0] cfg_mr_length,
    output wire [3:0] cfg_mr_access,
    output wire cfg_mr_valid,
    input wire cfg_mr_ready,
    input wire [7:0] cfg_mr_response_error,
    input wire [31:0] cfg_mr_response_key,
    input wire cfg_mr_response_valid,
    output wire cfg_mr_response_ready,
    output reg [2:0] cfg_page_command=0,
    output wire [2:0] cfg_page_slot,
    output wire [31:0] cfg_page_key,
    output wire [31:0] cfg_page_length,
    output wire [11:0] cfg_page_first_offset,
    output wire [7:0] cfg_page_page_index,
    output wire [63:0] cfg_page_dma_page,
    output wire cfg_page_valid,
    input wire cfg_page_ready,
    input wire [7:0] cfg_page_response_error,
    input wire [31:0] cfg_page_response_key,
    input wire cfg_page_response_valid,
    output wire cfg_page_response_ready,
    output wire [2:0] cfg_qp_number,
    output wire [23:0] cfg_peer_qp_number,
    output wire [15:0] cfg_qp_pd,
    output wire [31:0] cfg_local_ip,
    output wire [31:0] cfg_peer_ip,
    output wire [23:0] cfg_rx_psn,
    output wire [23:0] cfg_tx_psn,
    output wire cfg_qp_tx_only,
    output wire cfg_qp_valid,
    input wire cfg_qp_ready
);
localparam IDLE=0,CHECK=1,QUIET=2,MR_SEND=3,MR_WAIT=4,PAGE_SEND=5,
    PAGE_WAIT=6,QP_SEND=7,QP_WAIT=8,DRAIN=9,FAILED=10,EPOCH_DRAIN=11;
localparam EPOCH=1,BEGIN=2,PAGE=3,SEAL=4,INVALIDATE=5,QP=6,RUN=7,STOP=8,QP_TX=9;
localparam ERR_COMMAND=8'he1,ERR_OWNER=8'he2,ERR_STATE=8'he3,ERR_SHAPE=8'he4;
reg [3:0] state=IDLE;
reg [7:0] command=0;
reg [2:0] slot=0,qp_number=0;
reg [31:0] key=0,length=0,floor=0;
reg [63:0] cookie=0,virtual_address=0,dma_page=0;
reg [15:0] pd=0;
reg [3:0] access=0;
reg [11:0] first_offset=0;
reg [7:0] page_index=0;
reg [23:0] peer_qp_number=0,rx_psn=0,tx_psn=0;
reg [31:0] local_ip=0,peer_ip=0;
reg sequence_bad=0;
reg [7:0] mr_created=0,page_created=0;
reg [63:0] owner[0:7];
reg [31:0] entry_key[0:7],last_generation[0:7];
reg [15:0] entry_pd[0:7];
reg [2:0] qp_owner_qpn=0;
reg [15:0] qp_owner_pd=0;
wire owner_ok=owner[slot]==cookie && (building[slot] || active[slot] || tainted[slot]) &&
    (key==entry_key[slot] || (command==INVALIDATE && key==0));
// Cleanup after a BEGIN that never reached hardware is still a REAL proof:
// exclusive hardware state says both headers are absent, then QUIET/DRAIN
// checks actual parent/endpoint ownership. No reset/timeout inference.
wire free_cleanup=command==INVALIDATE && owner[slot]==0 && !building[slot] && !active[slot] &&
    !tainted[slot] && !mr_created[slot] && !page_created[slot] && (key==0 || key==entry_key[slot]);
wire [64:0] va_end={1'b0,virtual_address}+{33'd0,length};
wire [32:0] page_span={1'b0,length}+{21'd0,first_offset};
wire begin_shape=length!=0 && page_span<=33'd1048576 &&
    (!va_end[64] || va_end[63:0]==0) && (!(access&4'ha) || access[0]);
wire unexpected=(cfg_mr_response_valid && state!=MR_WAIT) || (cfg_page_response_valid && state!=PAGE_WAIT);
assign s_ready=state==IDLE && !m_valid && !fatal && !endpoint_fault && !rst;
assign busy=state!=IDLE || m_valid;
assign admission_pause=!run_requested || !epoch_ready || !qp_configured ||
    (|building) || (|tainted) || busy || fatal || endpoint_fault || rst;
assign cfg_mr_index=slot;
assign cfg_mr_pd=command==INVALIDATE ? entry_pd[slot] : pd;
assign cfg_mr_key=command==EPOCH ? key : (command==INVALIDATE ? entry_key[slot] : 32'd0);
assign cfg_mr_virtual_address=virtual_address;
assign cfg_mr_length={32'd0,length};
assign cfg_mr_access=access;
assign cfg_mr_valid=state==MR_SEND && !rst;
assign cfg_mr_response_ready=state==MR_WAIT && !rst;
assign cfg_page_slot=slot;
assign cfg_page_key=entry_key[slot];
assign cfg_page_length=length;
assign cfg_page_first_offset=first_offset;
assign cfg_page_page_index=page_index;
assign cfg_page_dma_page=dma_page;
assign cfg_page_valid=state==PAGE_SEND && !rst;
assign cfg_page_response_ready=state==PAGE_WAIT && !rst;
assign cfg_qp_number=qp_number;
assign cfg_peer_qp_number=peer_qp_number;
assign cfg_qp_pd=pd;
assign cfg_local_ip=local_ip;
assign cfg_peer_ip=peer_ip;
assign cfg_rx_psn=rx_psn;
assign cfg_tx_psn=tx_psn;
assign cfg_qp_tx_only=command==QP_TX;
assign cfg_qp_valid=state==QP_SEND && !rst;

task reply_error;
    input [7:0] error;
    begin m_error<=error;m_flags<=0;m_valid<=1;state<=IDLE;end
endtask
task protocol_fault;
    input [7:0] code;
    begin fatal<=1;fatal_code<=code;run_requested<=0;state<=FAILED;end
endtask
integer i;
always @(posedge clk) begin
    if(rst) begin
        state<=IDLE;command<=0;slot<=0;key<=0;cookie<=0;pd<=0;virtual_address<=0;
        length<=0;access<=0;first_offset<=0;page_index<=0;dma_page<=0;
        qp_number<=0;peer_qp_number<=0;local_ip<=0;peer_ip<=0;rx_psn<=0;tx_psn<=0;
        qp_owner_qpn<=0;qp_owner_pd<=0;
        sequence_bad<=0;floor<=0;building<=0;active<=0;tainted<=0;mr_created<=0;page_created<=0;
        epoch_ready<=0;qp_configured<=0;run_requested<=0;fatal<=0;fatal_code<=0;last_sequence<=0;
        cfg_mr_command<=0;cfg_page_command<=0;m_command<=0;m_sequence<=0;m_cookie<=0;m_slot<=0;
        m_key<=0;m_error<=0;m_flags<=0;m_valid<=0;
        for(i=0;i<8;i=i+1) begin owner[i]<=0;entry_key[i]<=0;entry_pd[i]<=0;last_generation[i]<=0;end
    end else begin
        if(m_valid && m_ready) m_valid<=0;
        if(endpoint_fault || unexpected) begin
            fatal<=1;run_requested<=0;if(!fatal) fatal_code<=endpoint_fault ? 1 : 2;
        end
        if(fatal || endpoint_fault || unexpected) begin
            // Never withdraw an already-valid config request. Drain ONLY its
            // own accepted response; no reply/release proof follows a fault.
            case(state)
                MR_SEND: if(cfg_mr_ready) state<=MR_WAIT;
                MR_WAIT: if(cfg_mr_response_valid) state<=FAILED;
                PAGE_SEND: if(cfg_page_ready) state<=PAGE_WAIT;
                PAGE_WAIT: if(cfg_page_response_valid) state<=FAILED;
                QP_SEND: if(cfg_qp_ready) state<=QP_WAIT;
                QP_WAIT: if(endpoint_qp_ready) state<=FAILED;
                default: state<=FAILED;
            endcase
        end else case(state)
            IDLE: if(s_valid && s_ready) begin
                command<=s_command;slot<=s_slot;key<=s_key;cookie<=s_cookie;pd<=s_pd;
                virtual_address<=s_virtual_address;length<=s_length;access<=s_access;
                first_offset<=s_first_offset;page_index<=s_page_index;dma_page<=s_dma_page;
                qp_number<=s_qp_number;peer_qp_number<=s_peer_qp_number;local_ip<=s_local_ip;
                peer_ip<=s_peer_ip;rx_psn<=s_rx_psn;tx_psn<=s_tx_psn;
                m_command<=s_command;m_sequence<=s_sequence;m_cookie<=s_cookie;m_slot<=s_slot;
                m_key<=0;m_error<=0;m_flags<=0;
                sequence_bad<=s_sequence==0 || s_sequence<=last_sequence || s_cookie==0;
                if(s_sequence>last_sequence && s_cookie!=0) last_sequence<=s_sequence;
                state<=CHECK;
            end
            CHECK: begin
                if(sequence_bad || command<EPOCH || command>(QP_TX_ENABLE ? QP_TX : STOP)) reply_error(ERR_COMMAND);
                else if(command==EPOCH) begin
                    if(epoch_ready || qp_configured || (|building) || (|active) || (|tainted)) reply_error(ERR_STATE);
                    else if(key>=32'h1fffffff) reply_error(ERR_SHAPE);
                    else state<=QUIET;
                end else if(!epoch_ready) reply_error(ERR_STATE);
                else if(command==BEGIN) begin
                    if(building[slot] || active[slot] || tainted[slot]) reply_error(ERR_STATE);
                    else if(!begin_shape || key!=0) reply_error(ERR_SHAPE);
                    else state<=QUIET;
                end else if(command==PAGE || command==SEAL || command==INVALIDATE) begin
                    if(!owner_ok && !free_cleanup) reply_error(ERR_OWNER);
                    else if(command!=INVALIDATE && (!building[slot] || !mr_created[slot] || !page_created[slot])) reply_error(ERR_STATE);
                    else state<=QUIET;
                end else if(command==QP_TX && (!qp_configured || !pd || pd!=qp_owner_pd || qp_number!=qp_owner_qpn)) reply_error(ERR_OWNER);
                else if(command==QP_TX && (slot!=0 || key!=0 || virtual_address!=0 || length!=0 || access!=0 ||
                    first_offset!=0 || page_index!=0 || dma_page!=0 || peer_qp_number!=0 || local_ip!=0 || peer_ip!=0 || rx_psn!=0)) reply_error(ERR_SHAPE);
                else if((command==RUN || command==QP || command==QP_TX) && ((|building) || (|tainted))) reply_error(ERR_STATE);
                else if(command==RUN && !qp_configured) reply_error(ERR_STATE);
                else begin if(command==STOP) run_requested<=0;state<=QUIET;end
            end
            QUIET: if(endpoint_quiescent && parent_dma_drained) begin
                case(command)
                    EPOCH: begin cfg_mr_command<=3;state<=MR_SEND;end
                    BEGIN: begin
                        owner[slot]<=cookie;entry_pd[slot]<=pd;building[slot]<=1;
                        entry_key[slot]<={last_generation[slot][28:0],slot};
                        mr_created[slot]<=0;page_created[slot]<=0;cfg_mr_command<=1;state<=MR_SEND;
                    end
                    PAGE: begin cfg_page_command<=2;state<=PAGE_SEND;end
                    SEAL: begin cfg_page_command<=3;state<=PAGE_SEND;end
                    INVALIDATE: begin
                        tainted[slot]<=1;
                        if(mr_created[slot]) begin cfg_mr_command<=2;state<=MR_SEND;end
                        else if(page_created[slot]) begin cfg_page_command<=4;state<=PAGE_SEND;end
                        else state<=DRAIN;
                    end
                    QP,QP_TX: state<=QP_SEND;
                    RUN: begin run_requested<=1;m_valid<=1;state<=IDLE;end
                    STOP: begin m_flags<=2;m_valid<=1;state<=IDLE;end
                    default: protocol_fault(3);
                endcase
            end
            MR_SEND: if(cfg_mr_ready) state<=MR_WAIT;
            MR_WAIT: if(cfg_mr_response_valid) begin
                if(cfg_mr_response_error!=0) begin
                    if(cfg_mr_response_key!=0) protocol_fault(4);
                    else begin m_key<=entry_key[slot];reply_error(8'h40|cfg_mr_response_error);end
                end else if(command==EPOCH) begin
                    if(cfg_mr_response_key!=key) protocol_fault(5);
                    else begin
                        floor<=key;epoch_ready<=1;m_key<=key;state<=EPOCH_DRAIN;
                        for(i=0;i<8;i=i+1) begin last_generation[i]<=key;entry_key[i]<={key[28:0],i[2:0]};end
                    end
                end else if(command==BEGIN) begin
                    if(cfg_mr_response_key[2:0]!=slot || cfg_mr_response_key[31:3]<=last_generation[slot] ||
                        cfg_mr_response_key[31:3]<=floor) protocol_fault(6);
                    else begin
                        entry_key[slot]<=cfg_mr_response_key;last_generation[slot]<=cfg_mr_response_key>>3;
                        mr_created[slot]<=1;cfg_page_command<=1;state<=PAGE_SEND;
                    end
                end else if(command==INVALIDATE) begin
                    if(cfg_mr_response_key!=0) protocol_fault(7);
                    else begin
                        mr_created[slot]<=0;
                        if(page_created[slot]) begin cfg_page_command<=4;state<=PAGE_SEND;end
                        else state<=DRAIN;
                    end
                end else protocol_fault(8);
            end
            PAGE_SEND: if(cfg_page_ready) state<=PAGE_WAIT;
            PAGE_WAIT: if(cfg_page_response_valid) begin
                if(cfg_page_response_error!=0) begin
                    if(cfg_page_response_key!=0) protocol_fault(9);
                    else begin m_key<=entry_key[slot];reply_error(8'h80|cfg_page_response_error);end
                end else if(cfg_page_response_key!=entry_key[slot]) protocol_fault(10);
                else begin
                    m_key<=entry_key[slot];
                    case(command)
                        BEGIN: begin page_created[slot]<=1;m_valid<=1;state<=IDLE;end
                        PAGE: begin m_valid<=1;state<=IDLE;end
                        SEAL: begin building[slot]<=0;active[slot]<=1;m_flags<=16;m_valid<=1;state<=IDLE;end
                        INVALIDATE: begin page_created[slot]<=0;state<=DRAIN;end
                        default: protocol_fault(11);
                    endcase
                end
            end
            QP_SEND: if(cfg_qp_ready) state<=QP_WAIT;
            QP_WAIT: if(endpoint_qp_ready && endpoint_quiescent && parent_dma_drained) begin
                if(command==QP)begin qp_owner_qpn<=qp_number;qp_owner_pd<=pd;end
                qp_configured<=1;m_valid<=1;state<=IDLE;
            end
            EPOCH_DRAIN: if(endpoint_quiescent && parent_dma_drained) begin
                m_flags<=8'he;m_valid<=1;state<=IDLE;
            end
            DRAIN: if(endpoint_quiescent && parent_dma_drained) begin
                // Both headers invalidated and all real memory/wire leases
                // drained. Nothing reopens until this reply is consumed.
                building[slot]<=0;active[slot]<=0;tainted[slot]<=0;owner[slot]<=0;
                m_key<=entry_key[slot];m_flags<=3;m_valid<=1;state<=IDLE;
            end
            default: protocol_fault(12);
        endcase
    end
end
endmodule
`resetall
