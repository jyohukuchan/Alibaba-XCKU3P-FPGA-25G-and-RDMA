// SPDX-License-Identifier: BSD-2-Clause-Views
// Copyright (c) 2026 jyohukuchan
// Native64-byte WQE decode/local-MR authorization frontend, not queue DMA.
// Trusted queue context is separate from untrusted fetched descriptor bytes.
// Successful handoff transfers the MR/context lifetime obligation downstream;
// this module NEVER executes DMA, generates CQEs or proves global drain.
`resetall
`timescale 1ns/1ps
`default_nettype none
module rocev2_wqe_admission #(
    parameter MAX_QPS = 8,
    parameter SEND_ENABLE = 0,
    parameter IMMEDIATE_ENABLE = 0,
    parameter RECV_ENABLE = 0,
    parameter RECV_ONLY = 0
)(
    input wire clk,
    input wire rst,
    input wire enable,
    // Must include pending management transactions, not just cfg_valid.
    // Management offers take priority while idle; cannot change while busy.
    input wire configuration_idle,
    input wire [511:0] s_wqe_data,
    input wire [63:0] s_wqe_keep,
    input wire s_wqe_last,
    input wire s_wqe_valid,
    output wire s_wqe_ready,
    input wire s_context_valid,
    input wire [23:0] s_context_qpn,
    input wire [15:0] s_context_pd,
    input wire [15:0] s_context_tag,
    input wire [63:0] s_context_sequence,
    input wire [63:0] s_context_epoch,
    // Connect to actual shared MR validator. No CPU-address or lkey shortcut.
    output wire [15:0] m_mr_request_pd,
    output wire [31:0] m_mr_request_key,
    output wire [63:0] m_mr_request_address,
    output wire [31:0] m_mr_request_length,
    output wire [2:0] m_mr_request_operation,
    output wire [15:0] m_mr_request_tag,
    output wire m_mr_request_valid,
    input wire m_mr_request_ready,
    input wire [15:0] s_mr_response_tag,
    input wire [7:0] s_mr_response_error,
    input wire [63:0] s_mr_response_offset,
    input wire [31:0] s_mr_response_length,
    input wire s_mr_response_valid,
    output wire s_mr_response_ready,
    // Authenticated full context for the future page/DMA/work executor.
    // error!=0 zeros addresses/keys/length. It is NOT a completed RDMA WR.
    output wire [63:0] m_work_wr_id,
    output wire [63:0] m_work_sequence,
    output wire [63:0] m_work_epoch,
    output wire [23:0] m_work_qpn,
    output wire [15:0] m_work_pd,
    output wire [15:0] m_work_tag,
    output wire [15:0] m_work_opcode,
    output wire [15:0] m_work_flags,
    output wire [31:0] m_work_length,
    output wire [31:0] m_work_local_key,
    output wire [63:0] m_work_local_address,
    output wire [63:0] m_work_local_offset,
    output wire [63:0] m_work_remote_address,
    output wire [31:0] m_work_remote_key,
    output wire [31:0] m_work_immediate,
    output wire [7:0] m_work_error,
    output wire m_work_authorized,
    output wire m_work_valid,
    input wire m_work_ready,
    output wire busy,
    // Include this AND downstream ownership in external cfg quiescence.
    // Covers accepted work and the offered first beat, without deadlocking
    // management priority. configuration_idle must not derive from this.
    output wire configuration_guard,
    output reg fault=0,
    output reg [7:0] fault_code=0
);
localparam [2:0] IDLE=0, PARSE=1, RANGE=2, QUERY=3, WAIT=4, RESULT=5, FAULT=6;
localparam [7:0] ERR_RECORD=8'h20, ERR_CONTEXT=8'h21, ERR_EPOCH=8'h22,
    ERR_SEQUENCE=8'h23, ERR_OPCODE=8'h24, ERR_FLAGS=8'h25,
    ERR_LENGTH=8'h26, ERR_ADDRESS=8'h27;
reg [2:0] state=IDLE;
reg [511:0] record=0;
reg [63:0] record_keep=0;
reg record_last=0, context_valid=0;
reg [23:0] qpn=0;
reg [15:0] pd=0, tag=0;
reg [63:0] expected_sequence=0, epoch=0;
reg [64:0] local_last=0, remote_last=0;
reg [63:0] authorized_offset=0;
reg [7:0] error=0, parse_error;

wire [31:0] length=record[287:256];
wire [15:0] opcode=record[367:352];
wire [15:0] flags=record[383:368];
wire immediate_opcode=opcode==5 || opcode==6;
wire canonical_send=(SEND_ENABLE && (opcode==3 || (IMMEDIATE_ENABLE && opcode==5))) || (RECV_ENABLE && opcode==4);
wire shape_ok=record_keep==64'hffffffffffffffff && record_last && record[447:416]==0 &&
    ((IMMEDIATE_ENABLE && immediate_opcode) || record[415:384]==0) &&
    (!canonical_send || (record[255:192]==0 && record[351:320]==0));
wire context_ok=context_valid && qpn<MAX_QPS && expected_sequence!=0 && epoch!=0;
wire epoch_ok=record[511:448]==epoch;
wire sequence_ok=record[127:64]==expected_sequence;
wire opcode_ok=RECV_ONLY ? (RECV_ENABLE && opcode==4) :
    opcode==1 || opcode==2 || (SEND_ENABLE && opcode==3) || (RECV_ENABLE && opcode==4) ||
    (IMMEDIATE_ENABLE && (opcode==6 || (SEND_ENABLE && opcode==5)));
wire flags_ok=(flags & 16'hfffe)==0 && (!RECV_ENABLE || opcode!=4 || flags==1);
wire length_ok=length!=0 && length<=4096;
always @* begin
    parse_error=ERR_RECORD;
    // Explicit one-bit cases also refuse unknown/partly initialized context
    // in four-state simulation; no casex/force or simulation-only repair.
    case(shape_ok)
    1'b1: begin
        case(context_ok)
        1'b1: begin
            case(epoch_ok)
            1'b1: begin
                case(sequence_ok)
                1'b1: begin
                    case(opcode_ok)
                    1'b1: begin
                        case(flags_ok)
                        1'b1: begin
                            case(length_ok)
                            1'b1: parse_error=0;
                            default: parse_error=ERR_LENGTH;
                            endcase
                        end
                        default: parse_error=ERR_FLAGS;
                        endcase
                    end
                    default: parse_error=ERR_OPCODE;
                    endcase
                end
                default: parse_error=ERR_SEQUENCE;
                endcase
            end
            default: parse_error=ERR_EPOCH;
            endcase
        end
        default: parse_error=ERR_CONTEXT;
        endcase
    end
    default: parse_error=ERR_RECORD;
    endcase
end

assign s_wqe_ready=state==IDLE && enable && configuration_idle && !rst;
assign busy=state!=IDLE;
assign configuration_guard=busy || (s_wqe_valid && enable && configuration_idle && !rst);
assign m_mr_request_pd=pd;
assign m_mr_request_key=record[319:288];
assign m_mr_request_address=record[191:128];
assign m_mr_request_length=length;
assign m_mr_request_operation=(opcode==2 || opcode==4) ? 3'd1 : 3'd0;
assign m_mr_request_tag=tag;
// Once accepted, disabling new admissions NEVER withdraws an offered query.
assign m_mr_request_valid=state==QUERY && !rst;
assign s_mr_response_ready=state==WAIT && !rst;
assign m_work_valid=state==RESULT && !rst;
assign m_work_authorized=m_work_valid && error==0;
assign m_work_error=error;
assign m_work_wr_id=record[63:0];
assign m_work_sequence=expected_sequence;
assign m_work_epoch=epoch;
assign m_work_qpn=qpn;
assign m_work_pd=pd;
assign m_work_tag=tag;
assign m_work_opcode=error==0 ? opcode : 16'd0;
assign m_work_flags=error==0 ? flags : 16'd0;
assign m_work_length=error==0 ? length : 32'd0;
assign m_work_local_key=error==0 ? record[319:288] : 32'd0;
assign m_work_local_address=error==0 ? record[191:128] : 64'd0;
assign m_work_local_offset=error==0 ? authorized_offset : 64'd0;
assign m_work_remote_address=error==0 ? record[255:192] : 64'd0;
assign m_work_remote_key=error==0 ? record[351:320] : 32'd0;
assign m_work_immediate=error==0 && IMMEDIATE_ENABLE ? record[415:384] : 32'd0;

initial begin
    if(MAX_QPS<1 || MAX_QPS>8) $fatal(1,"unreviewed WQE QP capacity");
    if(IMMEDIATE_ENABLE!=0 && IMMEDIATE_ENABLE!=1)$fatal(1,"Immediate profile must be static0or1");
end
always @(posedge clk) begin
    if(rst) begin
        state<=IDLE;record<=0;record_keep<=0;record_last<=0;context_valid<=0;
        qpn<=0;pd<=0;tag<=0;expected_sequence<=0;epoch<=0;local_last<=0;remote_last<=0;
        authorized_offset<=0;error<=0;fault<=0;fault_code<=0;
    end else case(state)
    IDLE: if(s_wqe_valid && s_wqe_ready) begin
        record<=s_wqe_data;record_keep<=s_wqe_keep;record_last<=s_wqe_last;
        context_valid<=s_context_valid;qpn<=s_context_qpn;pd<=s_context_pd;
        tag<=s_context_tag;expected_sequence<=s_context_sequence;epoch<=s_context_epoch;
        error<=0;authorized_offset<=0;state<=PARSE;
    end
    PARSE: begin
        if(parse_error!=0) begin error<=parse_error;state<=RESULT;end
        else begin
            local_last<={1'b0,record[191:128]}+{33'd0,length-1'b1};
            remote_last<={1'b0,record[255:192]}+{33'd0,length-1'b1};
            state<=RANGE;
        end
    end
    RANGE: begin
        case({local_last[64],remote_last[64]})
        2'b00: state<=QUERY;
        default: begin error<=ERR_ADDRESS;state<=RESULT;end
        endcase
    end
    QUERY: if(m_mr_request_valid && m_mr_request_ready) state<=WAIT;
    WAIT: if(s_mr_response_valid && s_mr_response_ready) begin
        case(s_mr_response_tag==tag)
        1'b1: begin
            case(s_mr_response_error)
            0: begin
                case(s_mr_response_length==length)
                1'b1: begin authorized_offset<=s_mr_response_offset;error<=0;state<=RESULT;end
                default: begin fault<=1;fault_code<=8'h32;state<=FAULT;end
                endcase
            end
            1,2,3,4,5,6,7,8,9,10: begin error<=s_mr_response_error;state<=RESULT;end
            default: begin fault<=1;fault_code<=8'h33;state<=FAULT;end
            endcase
        end
        default: begin fault<=1;fault_code<=8'h31;state<=FAULT;end
        endcase
    end
    RESULT: if(m_work_valid && m_work_ready) state<=IDLE;
    FAULT: state<=FAULT;
    default: begin fault<=1;fault_code<=8'h34;state<=FAULT;end
    endcase
end
endmodule
`default_nettype wire
