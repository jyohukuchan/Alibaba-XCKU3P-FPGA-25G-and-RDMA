// SPDX-License-Identifier: BSD-2-Clause-Views
// Copyright (c) 2026 jyohukuchan
// Actual SQ-fetch result/context -> existing local WQE/shared-MR frontend.
// Ring ownership and payload-MR ownership are DIFFERENT: a raw fetched result
// waiting behind management is not yet an MR lease. Its SQ queue guard must
// remain held upstream, while this module's guard begins at real admission.
// Work handoff is NOT DMA/wire/CQ completion. Downstream must retain its own
// per-QP guard without a handoff gap until true completion/recovery.
// Reset is not cancellation/unpin; requires coordinated real parent drain,
// closed work owners and fresh host epochs outside this module.
`resetall
`timescale 1ns/1ps
`default_nettype none
module rocev2_sq_wqe_admission #(
    parameter MAX_QPS=8,
    parameter SEND_ENABLE=0,
    parameter IMMEDIATE_ENABLE=0,
    parameter RECV_ENABLE=0,
    parameter RECV_ONLY=0
)(
    input wire clk,
    input wire rst,
    input wire enable,
    input wire configuration_idle,
    input wire [511:0] s_fetch_data,
    input wire [7:0] s_fetch_error,
    input wire [23:0] s_fetch_qpn,
    input wire [15:0] s_fetch_pd,
    input wire [63:0] s_fetch_epoch,
    input wire [63:0] s_fetch_sequence,
    input wire [15:0] s_fetch_tag,
    input wire s_fetch_valid,
    output wire s_fetch_ready,
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
    // 0=success,1=original fetch DMA error,2=WQE/MR admission error.
    // Fetch errors retain their exact8bits, not a fabricated parse error.
    output wire [1:0] m_work_error_source,
    output wire [7:0] m_work_fetch_error,
    // On failed/uninitialized fetch bytes WR_ID is unavailable, not ID0.
    // A real CQ publisher must use the trusted queue/sequence shadow record.
    output wire m_work_descriptor_available,
    output wire m_work_authorized,
    output wire m_work_valid,
    input wire m_work_ready,
    output wire [MAX_QPS-1:0] queue_guard,
    output wire configuration_guard,
    output wire busy,
    output wire fault,
    output wire [7:0] fault_code
);
reg owned=0,fetch_failed=0,descriptor_known=0;
reg [7:0] fetch_error=0;
reg [23:0] qpn=0;
reg [15:0] pd=0,tag=0;
reg [63:0] epoch=0,expected_sequence_reg=0;
reg protocol_fault=0;
reg [7:0] protocol_fault_code=0;
reg context_known,error_known,data_known;
always @* begin
    context_known=0;error_known=0;data_known=0;
    case(^{s_fetch_qpn,s_fetch_pd,s_fetch_epoch,s_fetch_sequence,s_fetch_tag})
    1'b0,1'b1:case(s_fetch_qpn<MAX_QPS && s_fetch_epoch!=0 && s_fetch_sequence!=0 && s_fetch_tag!=0)
        1'b1:context_known=1;
        default:context_known=0;
    endcase
    default:context_known=0;
    endcase
    case(s_fetch_error)
    0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15:error_known=1;
    default:error_known=0;
    endcase
    case(^s_fetch_data)
    1'b0,1'b1:data_known=1;
    default:data_known=0;
    endcase
end
wire dma_error=error_known && s_fetch_error!=0;
wire frontend_ready,frontend_valid,frontend_guard,frontend_busy,frontend_fault;
wire [7:0] frontend_fault_code,frontend_error;
wire [63:0] frontend_wr_id,frontend_sequence,frontend_epoch;
wire [23:0] frontend_qpn;
wire [15:0] frontend_pd,frontend_tag;
wire [15:0] frontend_opcode,frontend_flags;
wire [31:0] frontend_length,frontend_local_key,frontend_remote_key;
wire [31:0] frontend_immediate;
wire [63:0] frontend_local_address,frontend_local_offset,frontend_remote_address;
wire input_allowed=!owned && context_known && error_known && !fault && !rst;
// A known failed DMA has NO MR authority to acquire. It can be handed to the
// error owner even while new work is disabled/management waits for drain.
assign s_fetch_ready=input_allowed && (dma_error || frontend_ready);
wire take=s_fetch_valid && s_fetch_ready;
wire frontend_input=s_fetch_valid && input_allowed && !dma_error;
assign busy=owned || frontend_busy || fault;
assign fault=protocol_fault || frontend_fault;
assign fault_code=protocol_fault ? protocol_fault_code : frontend_fault_code;
assign configuration_guard=frontend_guard || owned ||
    (s_fetch_valid && input_allowed && dma_error) || fault;
genvar n;
generate for(n=0;n<MAX_QPS;n=n+1)begin: ownership
    assign queue_guard[n]=fault || (owned && qpn==n) ||
        (s_fetch_valid && input_allowed && (dma_error || frontend_ready) && s_fetch_qpn==n);
end endgenerate
assign m_work_valid=owned && (fetch_failed || frontend_valid) && !rst;
assign m_work_wr_id=descriptor_known && !fetch_failed ? frontend_wr_id : 64'd0;
assign m_work_sequence=expected_sequence_reg;
assign m_work_epoch=epoch;
assign m_work_qpn=qpn;
assign m_work_pd=pd;
assign m_work_tag=tag;
assign m_work_fetch_error=owned && fetch_failed ? fetch_error : 8'd0;
assign m_work_error=owned ? (fetch_failed ? fetch_error : frontend_error) : 8'd0;
assign m_work_error_source=owned ? (fetch_failed ? 2'd1 : frontend_error!=0 ? 2'd2 : 2'd0) : 2'd0;
assign m_work_descriptor_available=owned && descriptor_known && !fetch_failed;
assign m_work_authorized=m_work_valid && !fetch_failed && frontend_error==0;
assign m_work_opcode=m_work_authorized ? frontend_opcode : 16'd0;
assign m_work_flags=m_work_authorized ? frontend_flags : 16'd0;
assign m_work_length=m_work_authorized ? frontend_length : 32'd0;
assign m_work_local_key=m_work_authorized ? frontend_local_key : 32'd0;
assign m_work_local_address=m_work_authorized ? frontend_local_address : 64'd0;
assign m_work_local_offset=m_work_authorized ? frontend_local_offset : 64'd0;
assign m_work_remote_address=m_work_authorized ? frontend_remote_address : 64'd0;
assign m_work_remote_key=m_work_authorized ? frontend_remote_key : 32'd0;
assign m_work_immediate=m_work_authorized ? frontend_immediate : 32'd0;
rocev2_wqe_admission #(.MAX_QPS(MAX_QPS),.SEND_ENABLE(SEND_ENABLE),.IMMEDIATE_ENABLE(IMMEDIATE_ENABLE),.RECV_ENABLE(RECV_ENABLE),.RECV_ONLY(RECV_ONLY)) frontend(
    .clk(clk),.rst(rst),.enable(enable),.configuration_idle(configuration_idle),
    .s_wqe_data(s_fetch_data),
    // Unknown descriptor bits, including otherwise-unused remote-key/WR_ID,
    // are a denied record. They never reach an MR query or become authority.
    .s_wqe_keep(data_known ? 64'hffffffffffffffff : 64'd0),.s_wqe_last(1'b1),
    .s_wqe_valid(frontend_input),.s_wqe_ready(frontend_ready),
    .s_context_valid(context_known),.s_context_qpn(s_fetch_qpn),.s_context_pd(s_fetch_pd),
    .s_context_tag(s_fetch_tag),.s_context_sequence(s_fetch_sequence),.s_context_epoch(s_fetch_epoch),
    .m_mr_request_pd(m_mr_request_pd),.m_mr_request_key(m_mr_request_key),
    .m_mr_request_address(m_mr_request_address),.m_mr_request_length(m_mr_request_length),
    .m_mr_request_operation(m_mr_request_operation),.m_mr_request_tag(m_mr_request_tag),
    .m_mr_request_valid(m_mr_request_valid),.m_mr_request_ready(m_mr_request_ready),
    .s_mr_response_tag(s_mr_response_tag),.s_mr_response_error(s_mr_response_error),
    .s_mr_response_offset(s_mr_response_offset),.s_mr_response_length(s_mr_response_length),
    .s_mr_response_valid(s_mr_response_valid),.s_mr_response_ready(s_mr_response_ready),
    .m_work_wr_id(frontend_wr_id),.m_work_sequence(frontend_sequence),.m_work_epoch(frontend_epoch),
    .m_work_qpn(frontend_qpn),.m_work_pd(frontend_pd),.m_work_tag(frontend_tag),
    .m_work_opcode(frontend_opcode),.m_work_flags(frontend_flags),.m_work_length(frontend_length),
    .m_work_local_key(frontend_local_key),.m_work_local_address(frontend_local_address),
    .m_work_local_offset(frontend_local_offset),.m_work_remote_address(frontend_remote_address),
    .m_work_remote_key(frontend_remote_key),.m_work_immediate(frontend_immediate),.m_work_error(frontend_error),.m_work_authorized(),
    .m_work_valid(frontend_valid),.m_work_ready(owned && !fetch_failed && m_work_ready),
    .busy(frontend_busy),.configuration_guard(frontend_guard),.fault(frontend_fault),
    .fault_code(frontend_fault_code));
// Never leak a previous successful frontend's payload authority for a failed
// fetch. The frontend returns to IDLE at each handoff, with its old fields
// retained internally; the muxes below therefore cannot be implicit.
initial begin
    if(MAX_QPS<1 || MAX_QPS>8)$fatal(1,"unreviewed SQ admission capacity");
end
always @(posedge clk)begin
    if(rst)begin
        owned<=0;fetch_failed<=0;descriptor_known<=0;fetch_error<=0;
        qpn<=0;pd<=0;tag<=0;epoch<=0;expected_sequence_reg<=0;
        protocol_fault<=0;protocol_fault_code<=0;
    end else begin
        if(s_fetch_valid && (!context_known || !error_known))begin
            protocol_fault<=1;protocol_fault_code<=8'h51;
        end
        if(frontend_valid && (!owned || fetch_failed || frontend_qpn!=qpn || frontend_pd!=pd ||
            frontend_tag!=tag || frontend_epoch!=epoch || frontend_sequence!=expected_sequence_reg))begin
            protocol_fault<=1;protocol_fault_code<=8'h52;
        end
        if(take)begin
            owned<=1;fetch_failed<=dma_error;fetch_error<=s_fetch_error;descriptor_known<=data_known && !dma_error;
            qpn<=s_fetch_qpn;pd<=s_fetch_pd;tag<=s_fetch_tag;epoch<=s_fetch_epoch;expected_sequence_reg<=s_fetch_sequence;
        end
        if(m_work_valid && m_work_ready)owned<=0;
    end
end
endmodule
`resetall
