// SPDX-License-Identifier: BSD-2-Clause-Views
// Copyright (c) 2026 jyohukuchan
// Experimental, OFFLINE-VERIFIED responder integration; not a board application.
// One trusted QP, one outstanding READ_REQUEST/WRITE_ONLY, 1..4096 bytes.
// The backend MUST retain the memory lease until status and MUST report status
// only after writes are visible (or reads have no outstanding accesses). Reset
// requires drained DMA/closed QPs and a fresh MR key epoch outside this module.
// No NAK/retry/SEND/host-page registration/PCIe DMA implementation is implied.
`resetall
`timescale 1ns / 1ps
`default_nettype none

module rocev2_protected_responder #(
    // Legacy contiguous probes have no external publication controller. A
    // paged/live integration MUST enable this and drive a real admission gate.
    parameter EXTERNAL_ADMISSION_CONTROL=0,
    // Optional native local-WQE query client. Default preserves the legacy
    // single-client path; no duplicate MR table or independent key namespace.
    parameter LOCAL_WQE_ENABLE=0
)(
    input wire clk,
    input wire rst,
    input wire cfg_admission_pause,
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
    // Trusted context: never derive PD, peer identity or expected PSN from RX.
    input wire [2:0] cfg_qp_number,
    input wire [23:0] cfg_peer_qp_number,
    input wire [15:0] cfg_qp_pd,
    input wire [31:0] cfg_local_ip,
    input wire [31:0] cfg_peer_ip,
    input wire [23:0] cfg_rx_psn,
    input wire [23:0] cfg_tx_psn,
    input wire cfg_qp_valid,
    output wire cfg_qp_ready,
    output wire qp_ready,
    input wire [1:0] cfg_mr_command,
    input wire [2:0] cfg_mr_index,
    input wire [15:0] cfg_mr_pd,
    input wire [31:0] cfg_mr_key,
    input wire [63:0] cfg_mr_virtual_address,
    input wire [63:0] cfg_mr_dma_address,
    input wire [63:0] cfg_mr_length,
    input wire [3:0] cfg_mr_access,
    input wire cfg_mr_valid,
    output wire cfg_mr_ready,
    output wire [7:0] cfg_mr_response_error,
    output wire [31:0] cfg_mr_response_key,
    output wire cfg_mr_response_valid,
    input wire cfg_mr_response_ready,
    // Trusted local-WQE lookup port. The caller MUST hold local_work_guard
    // from first accepted/offered WQE through the actual downstream lease;
    // a lookup response alone is NOT work completion or permission to unpin.
    // configuration_idle includes management offers/pause but deliberately
    // does not depend on the caller's guard (which would create a loop).
    input wire local_work_guard,
    output wire local_configuration_idle,
    input wire [15:0] s_local_mr_request_pd,
    input wire [31:0] s_local_mr_request_key,
    input wire [63:0] s_local_mr_request_address,
    input wire [31:0] s_local_mr_request_length,
    input wire [2:0] s_local_mr_request_operation,
    input wire [15:0] s_local_mr_request_tag,
    input wire s_local_mr_request_valid,
    output wire s_local_mr_request_ready,
    output wire [15:0] m_local_mr_response_tag,
    output wire [7:0] m_local_mr_response_error,
    output wire [63:0] m_local_mr_response_offset,
    output wire [31:0] m_local_mr_response_length,
    output wire m_local_mr_response_valid,
    input wire m_local_mr_response_ready,
    // Safe, full-width backend contract. Raw HLS addresses/routing NEVER escape.
    output wire m_memory_command_write,
    output wire [63:0] m_memory_command_address,
    output wire [31:0] m_memory_command_length,
    output wire [15:0] m_memory_command_tag,
    // Bound to the SAME successful MR lookup as address/length/tag. These
    // are not reconstructed from truncated HLS fields or a second RX parser.
    output wire [31:0] m_memory_command_key,
    output wire [63:0] m_memory_command_offset,
    output wire m_memory_command_valid,
    input wire m_memory_command_ready,
    output wire [511:0] m_axis_memory_write_tdata,
    output wire [63:0] m_axis_memory_write_tkeep,
    output wire m_axis_memory_write_tvalid,
    input wire m_axis_memory_write_tready,
    output wire m_axis_memory_write_tlast,
    input wire [511:0] s_axis_memory_read_tdata,
    input wire [63:0] s_axis_memory_read_tkeep,
    input wire s_axis_memory_read_tvalid,
    output wire s_axis_memory_read_tready,
    input wire s_axis_memory_read_tlast,
    input wire [15:0] s_memory_status_tag,
    input wire [7:0] s_memory_status_error,
    input wire s_memory_status_valid,
    output wire s_memory_status_ready,
    // Rejections are local events, NOT a wire-level remote-access NAK yet.
    output reg [7:0] m_reject_error=0,
    output reg [23:0] m_reject_qpn=0,
    output reg [23:0] m_reject_psn=0,
    output reg m_reject_valid=0,
    input wire m_reject_ready,
    output wire quiescent,
    output reg fault=0,
    output reg [7:0] fault_code=0,
    output reg [31:0] accepted_count=0,
    output reg [31:0] rejected_count=0,
    output reg [31:0] completed_count=0,
    output reg [31:0] tx_deferred_cycles=0,
    output reg [31:0] rx_integrity_good_count=0,
    output reg [31:0] rx_integrity_drop_count=0
);

localparam COLLECT=0, PARSE=1, LOOKUP=2, MR_WAIT=3, FORWARD=4,
    ACTIVE=5, REJECT=6;
localparam ERR_FORMAT=16, ERR_QP=17, ERR_PSN=18, ERR_OPCODE=19,
    ERR_COMMAND=32, ERR_DATA=33, ERR_STATUS=34, ERR_UNEXPECTED=35,
    ERR_TAG_EXHAUSTED=36, ERR_MR_PROTOCOL=37;
localparam FRAME_WORDS=260; // IPv4/UDP/BTH/RETH + 4096B + pad + ICRC.
reg [2:0] state=COLLECT;
reg [127:0] frame_data[0:FRAME_WORDS-1];
reg [15:0] frame_keep[0:FRAME_WORDS-1];
reg [8:0] word_count=0, forward_index=0;
reg [15:0] byte_count=0;
reg frame_bad=0;
reg [511:0] header=0;
reg [12:0] startup_count=0;
reg context_valid=0, qp_pending=0, conn_pending=0;
// Explicit management ownership, independent of cfg_ready/quiescence. In
// shared mode another client's memory lease may correctly suppress cfg_ready
// while independent RX/local queries must still be allowed to make progress.
reg mr_configuration_pending=0;
reg [23:0] local_qpn=0, peer_qpn=0, expected_psn=0, tx_psn=0;
reg [15:0] trusted_pd=0;
reg [31:0] local_ip=0, peer_ip=0;
reg lease=0, write_operation=0, command_done=0, data_done=0, committed=0;
reg [63:0] request_va=0, dma_address=0;
reg [31:0] request_key=0,lease_key=0;
reg [63:0] lease_offset=0;
reg [31:0] request_length=0, wire_length=0, data_remaining=0, wire_remaining=0;
reg [23:0] request_psn=0;
reg [15:0] lease_tag=0;

function [15:0] be16;
    input [511:0] data;
    input integer pos;
    begin be16={data[pos*8+:8],data[(pos+1)*8+:8]}; end
endfunction
function [31:0] be32;
    input [511:0] data;
    input integer pos;
    begin be32={be16(data,pos),be16(data,pos+2)}; end
endfunction
function [63:0] be64;
    input [511:0] data;
    input integer pos;
    begin be64={be32(data,pos),be32(data,pos+4)}; end
endfunction
function [31:0] swap32;
    input [31:0] value;
    begin swap32={value[7:0],value[15:8],value[23:16],value[31:24]}; end
endfunction
function [4:0] keep_bytes;
    input [15:0] keep;
    integer n;
    begin keep_bytes=0; for(n=0;n<16;n=n+1) keep_bytes=keep_bytes+keep[n]; end
endfunction
function [63:0] mask64;
    input [31:0] remaining;
    integer byte_lane;
    // Constant-lane comparisons avoid a variable shift +64-bit subtract on
    // HLS AXIS ready/CE feedback. Exact same prefix mask for ALL32-bit counts.
    begin for(byte_lane=0;byte_lane<64;byte_lane=byte_lane+1) mask64[byte_lane]=remaining>byte_lane; end
endfunction

wire startup_done=startup_count==4096;
wire admission_paused=EXTERNAL_ADMISSION_CONTROL && cfg_admission_pause;
wire config_busy=qp_pending || conn_pending;
wire mr_epoch_configured;
wire shared_mr_busy,shared_mr_fault;
wire mr_management_idle=!mr_configuration_pending && !cfg_mr_valid && !cfg_mr_response_valid;
wire local_guarded=LOCAL_WQE_ENABLE &&
    (local_work_guard || s_local_mr_request_valid || shared_mr_busy || shared_mr_fault);
assign qp_ready=context_valid && !config_busy && startup_done && mr_epoch_configured && !fault;
assign quiescent=state==COLLECT && word_count==0 && !lease && !config_busy &&
    !m_reject_valid && startup_done && !fault && !local_guarded && !rst;
assign cfg_qp_ready=quiescent && cfg_mr_ready && !cfg_mr_valid && !cfg_mr_response_valid;
assign local_configuration_idle=LOCAL_WQE_ENABLE && qp_ready && !shared_mr_fault &&
    !admission_paused && !cfg_qp_valid && mr_management_idle && !rst;

wire [127:0] checked_data;
wire [15:0] checked_keep;
wire checked_valid, checked_ready, checked_last, rx_good, rx_bad, rx_overflow;
// Full packet integrity is checked BEFORE QP/PD/MR admission. The unchanged
// baseline transport also validates it, deliberately retaining its own gate.
rocev2_ipv4_icrc #(.TX_MODE(0)) admission_integrity (
    .clk(clk),.rst(rst),.s_axis_tdata(s_axis_rx_tdata),.s_axis_tkeep(s_axis_rx_tkeep),
    .s_axis_tvalid(s_axis_rx_tvalid),.s_axis_tready(s_axis_rx_tready),
    .s_axis_tlast(s_axis_rx_tlast),.s_axis_tuser(s_axis_rx_tuser),
    .m_axis_tdata(checked_data),.m_axis_tkeep(checked_keep),.m_axis_tvalid(checked_valid),
    .m_axis_tready(checked_ready),.m_axis_tlast(checked_last),
    .status_good_frame(rx_good),.status_bad_frame(rx_bad),.status_overflow(rx_overflow));
assign checked_ready=state==COLLECT && qp_ready &&
    (word_count!=0 || (!admission_paused && (LOCAL_WQE_ENABLE ? mr_management_idle : cfg_mr_ready) &&
        !cfg_qp_valid && !cfg_mr_valid && !cfg_mr_response_valid)) && !fault && !rst;

wire [7:0] opcode=header[28*8+:8];
wire [1:0] pad=header[29*8+4+:2];
wire [31:0] parsed_length=be32(header,52);
wire [31:0] padded_length=(parsed_length+3)&32'hfffffffc;
wire [23:0] parsed_qpn={header[33*8+:8],header[34*8+:8],header[35*8+:8]};
wire [23:0] parsed_psn={header[37*8+:8],header[38*8+:8],header[39*8+:8]};
wire [7:0] mr_error;
wire [63:0] mr_dma;
wire [63:0] mr_offset;
wire [31:0] mr_length;
wire [15:0] mr_tag;
wire mr_request_ready, mr_response_valid;
wire [15:0] table_request_pd,table_request_tag,table_response_tag;
wire [31:0] table_request_key,table_request_length,table_response_length;
wire [63:0] table_request_address,table_response_offset,table_response_dma;
wire [2:0] table_request_operation;
wire [7:0] table_response_error;
wire table_request_valid,table_request_ready,table_response_valid,table_response_ready;
generate if(LOCAL_WQE_ENABLE) begin: shared_mr
    wire [31:0] response_tags;
    wire [15:0] response_errors;
    wire [127:0] response_offsets,response_dmas;
    wire [63:0] response_lengths;
    wire [1:0] request_ready,response_valid;
    rocev2_mr_query_arbiter arbiter (
        .clk(clk),.rst(rst),
        .s_request_pd({s_local_mr_request_pd,trusted_pd}),
        .s_request_key({s_local_mr_request_key,request_key}),
        .s_request_address({s_local_mr_request_address,request_va}),
        .s_request_length({s_local_mr_request_length,request_length}),
        .s_request_operation({s_local_mr_request_operation,write_operation ? 3'd3 : 3'd2}),
        .s_request_tag({s_local_mr_request_tag,lease_tag+16'd1}),
        .s_request_valid({s_local_mr_request_valid,state==LOOKUP && !fault}),
        .s_request_ready(request_ready),.m_response_tag(response_tags),.m_response_error(response_errors),
        .m_response_offset(response_offsets),.m_response_dma_address(response_dmas),
        .m_response_length(response_lengths),.m_response_valid(response_valid),
        .m_response_ready({m_local_mr_response_ready,state==MR_WAIT && !fault}),
        .m_request_pd(table_request_pd),.m_request_key(table_request_key),
        .m_request_address(table_request_address),.m_request_length(table_request_length),
        .m_request_operation(table_request_operation),.m_request_tag(table_request_tag),
        .m_request_valid(table_request_valid),.m_request_ready(table_request_ready),
        .s_response_tag(table_response_tag),.s_response_error(table_response_error),
        .s_response_offset(table_response_offset),.s_response_dma_address(table_response_dma),
        .s_response_length(table_response_length),.s_response_valid(table_response_valid),
        .s_response_ready(table_response_ready),.busy(shared_mr_busy),.fault(shared_mr_fault),.fault_code());
    assign mr_request_ready=request_ready[0];
    assign s_local_mr_request_ready=request_ready[1];
    assign mr_tag=response_tags[15:0];
    assign m_local_mr_response_tag=response_tags[31:16];
    assign mr_error=response_errors[7:0];
    assign m_local_mr_response_error=response_errors[15:8];
    assign mr_offset=response_offsets[63:0];
    assign m_local_mr_response_offset=response_offsets[127:64];
    assign mr_dma=response_dmas[63:0];
    assign mr_length=response_lengths[31:0];
    assign m_local_mr_response_length=response_lengths[63:32];
    assign mr_response_valid=response_valid[0];
    assign m_local_mr_response_valid=response_valid[1];
end else begin: dedicated_mr
    assign table_request_pd=trusted_pd;
    assign table_request_key=request_key;
    assign table_request_address=request_va;
    assign table_request_length=request_length;
    assign table_request_operation=write_operation ? 3'd3 : 3'd2;
    assign table_request_tag=lease_tag+16'd1;
    assign table_request_valid=state==LOOKUP && !fault;
    assign mr_request_ready=table_request_ready;
    assign mr_tag=table_response_tag;
    assign mr_error=table_response_error;
    assign mr_offset=table_response_offset;
    assign mr_dma=table_response_dma;
    assign mr_length=table_response_length;
    assign mr_response_valid=table_response_valid;
    assign table_response_ready=state==MR_WAIT && !fault;
    assign s_local_mr_request_ready=0;
    assign m_local_mr_response_tag=0;
    assign m_local_mr_response_error=0;
    assign m_local_mr_response_offset=0;
    assign m_local_mr_response_length=0;
    assign m_local_mr_response_valid=0;
    assign shared_mr_busy=0;
    assign shared_mr_fault=0;
end endgenerate
rocev2_mr_table #(.REQUIRE_EPOCH(1)) mr_table (
    .clk(clk),.rst(rst),.cfg_quiescent(quiescent),
    .cfg_command(cfg_mr_command),.cfg_index(cfg_mr_index),.cfg_pd(cfg_mr_pd),
    .cfg_key(cfg_mr_key),.cfg_virtual_address(cfg_mr_virtual_address),
    .cfg_dma_address(cfg_mr_dma_address),.cfg_length(cfg_mr_length),.cfg_access(cfg_mr_access),
    .cfg_valid(cfg_mr_valid),.cfg_ready(cfg_mr_ready),
    .cfg_response_error(cfg_mr_response_error),.cfg_response_key(cfg_mr_response_key),
    .cfg_response_valid(cfg_mr_response_valid),.cfg_response_ready(cfg_mr_response_ready),
    .epoch_configured(mr_epoch_configured),
    .s_request_pd(table_request_pd),.s_request_key(table_request_key),.s_request_address(table_request_address),
    .s_request_length(table_request_length),.s_request_operation(table_request_operation),
    .s_request_tag(table_request_tag),.s_request_valid(table_request_valid),
    .s_request_ready(table_request_ready),.m_response_tag(table_response_tag),.m_response_error(table_response_error),
    .m_response_offset(table_response_offset),.m_response_dma_address(table_response_dma),.m_response_length(table_response_length),
    .m_response_valid(table_response_valid),.m_response_ready(table_response_ready));

wire core_rx_ready, replay_ready;
wire [127:0] replay_data;
wire [15:0] replay_keep;
wire replay_valid,replay_last;
// Cut async frame RAM -> integrity checksum/length feedback. Accepted beats
// keep data/keep/last ownership under downstream stalls, including faults.
axis_register #(.DATA_WIDTH(128),.KEEP_ENABLE(1),.KEEP_WIDTH(16),.LAST_ENABLE(1),
    .ID_ENABLE(0),.ID_WIDTH(1),.DEST_ENABLE(0),.DEST_WIDTH(1),.USER_ENABLE(0),.USER_WIDTH(1),.REG_TYPE(2)) replay_register (
    .clk(clk),.rst(rst),.s_axis_tdata(frame_data[forward_index]),.s_axis_tkeep(frame_keep[forward_index]),
    .s_axis_tvalid(state==FORWARD && !fault),.s_axis_tready(replay_ready),
    .s_axis_tlast(forward_index+1==word_count),.s_axis_tid(1'b0),.s_axis_tdest(1'b0),.s_axis_tuser(1'b0),
    .m_axis_tdata(replay_data),.m_axis_tkeep(replay_keep),.m_axis_tvalid(replay_valid),.m_axis_tready(core_rx_ready),
    .m_axis_tlast(replay_last),.m_axis_tid(),.m_axis_tdest(),.m_axis_tuser());
wire [127:0] core_tx_data;
wire [15:0] core_tx_keep;
wire core_tx_valid, core_tx_ready, core_tx_last;
wire [95:0] core_write_command, core_read_command;
wire core_write_valid, core_write_ready, core_read_valid, core_read_ready;
wire [511:0] core_write_data;
wire [63:0] core_write_keep;
wire core_write_data_valid, core_write_data_ready, core_write_last, core_read_data_ready;
wire qp_if_ready, conn_if_ready;
wire [31:0] core_rx_bad, core_tx_bad, core_overflow;
rocev2_integrity_transport transport (
    .clk(clk),.rst(rst),
    .s_axis_rx_tdata(replay_data),.s_axis_rx_tkeep(replay_keep),
    .s_axis_rx_tvalid(replay_valid),.s_axis_rx_tready(core_rx_ready),
    .s_axis_rx_tlast(replay_last),.s_axis_rx_tuser(1'b0),
    .m_axis_tx_tdata(core_tx_data),.m_axis_tx_tkeep(core_tx_keep),
    .m_axis_tx_tvalid(core_tx_valid),.m_axis_tx_tready(core_tx_ready),.m_axis_tx_tlast(core_tx_last),
    .s_axis_qp_tdata({32'd0,48'd0,expected_psn,tx_psn,local_qpn,32'd3}),
    .s_axis_qp_tvalid(qp_pending),.s_axis_qp_tready(qp_if_ready),
    .s_axis_conn_tdata({16'd4791,{4{swap32(peer_ip)}},peer_qpn,local_qpn[15:0]}),
    .s_axis_conn_tvalid(conn_pending),.s_axis_conn_tready(conn_if_ready),
    .s_axis_sq_tdata(240'd0),.s_axis_sq_tvalid(1'b0),.s_axis_sq_tready(),
    .m_axis_ack_tdata(),.m_axis_ack_tvalid(),.m_axis_ack_tready(1'b1),
    .m_axis_mem_write_cmd_tdata(core_write_command),.m_axis_mem_write_cmd_tvalid(core_write_valid),
    .m_axis_mem_write_cmd_tready(core_write_ready),
    .m_axis_mem_read_cmd_tdata(core_read_command),.m_axis_mem_read_cmd_tvalid(core_read_valid),
    .m_axis_mem_read_cmd_tready(core_read_ready),
    .m_axis_mem_write_tdata(core_write_data),.m_axis_mem_write_tkeep(core_write_keep),
    .m_axis_mem_write_tvalid(core_write_data_valid),.m_axis_mem_write_tready(core_write_data_ready),
    .m_axis_mem_write_tlast(core_write_last),
    .s_axis_mem_read_tdata(s_axis_memory_read_tdata),.s_axis_mem_read_tkeep(s_axis_memory_read_tkeep),
    .s_axis_mem_read_tvalid(s_axis_memory_read_tvalid && lease && !write_operation && command_done && !data_done && read_shape_ok && !fault),
    .s_axis_mem_read_tready(core_read_data_ready),.s_axis_mem_read_tlast(s_axis_memory_read_tlast),
    .local_ip_address({4{swap32(local_ip)}}),
    .m_axis_debug_tdata(),.m_axis_debug_tvalid(),.m_axis_debug_tready(1'b1),
    .core_psn_drop_count(),.core_retransmit_count(),.core_rx_word_count(),.core_tx_word_count(),
    .rx_integrity_good_count(),.rx_integrity_drop_count(core_rx_bad),
    .tx_integrity_good_count(),.tx_integrity_drop_count(core_tx_bad),.integrity_overflow_count(core_overflow));

wire [95:0] selected_command=write_operation ? core_write_command : core_read_command;
wire selected_valid=write_operation ? core_write_valid : core_read_valid;
// Check ALL meaningful HLS fields, including VA-derived routing. Their values
// are assertions against saved authorized context, never DMA destinations.
wire [93:0] expected_command={local_qpn[9:0],request_va[51:48],1'b1,1'b0,
    request_va[52],1'b1,wire_length[27:0],request_va[47:0]};
wire command_match=selected_command[93:0]==expected_command;
assign m_memory_command_write=write_operation;
assign m_memory_command_address=dma_address;
assign m_memory_command_length=request_length;
assign m_memory_command_tag=lease_tag;
assign m_memory_command_valid=lease && !command_done && selected_valid && command_match && !fault && !rst;
assign core_write_ready=m_memory_command_ready && m_memory_command_valid && write_operation;
assign core_read_ready=m_memory_command_ready && m_memory_command_valid && !write_operation;
wire write_shape_ok=core_write_keep==mask64(wire_remaining) &&
    core_write_last==(wire_remaining<=64);
wire read_shape_ok=s_axis_memory_read_tkeep==mask64(data_remaining) &&
    s_axis_memory_read_tlast==(data_remaining<=64);
assign m_axis_memory_write_tkeep=mask64(data_remaining);
assign m_axis_memory_write_tlast=data_remaining<=64;
genvar lane;
generate for(lane=0;lane<64;lane=lane+1) begin : mask_padding
    assign m_axis_memory_write_tdata[lane*8+:8]=m_axis_memory_write_tkeep[lane] ? core_write_data[lane*8+:8] : 8'd0;
end endgenerate
assign m_memory_command_key=lease_key;
assign m_memory_command_offset=lease_offset;
assign m_axis_memory_write_tvalid=lease && write_operation && command_done && !data_done &&
    core_write_data_valid && write_shape_ok && !fault && !rst;
assign core_write_data_ready=m_axis_memory_write_tready && m_axis_memory_write_tvalid;
assign s_axis_memory_read_tready=lease && !write_operation && command_done && !data_done &&
    core_read_data_ready && read_shape_ok && !fault && !rst;
assign s_memory_status_ready=lease && command_done && data_done && !committed && !fault && !rst;
// HLS creates WRITE ACK before memory visibility. Never expose even its first
// beat until the backend's successful, tagged completion has been consumed.
assign m_axis_tx_tdata=core_tx_data;
assign m_axis_tx_tkeep=core_tx_keep;
assign m_axis_tx_tlast=core_tx_last;
assign m_axis_tx_tvalid=core_tx_valid && lease && committed && !fault && !rst;
assign core_tx_ready=m_axis_tx_tready && lease && committed && !fault && !rst;

always @(posedge clk) begin
    if(rst) begin
        state<=COLLECT;word_count<=0;forward_index<=0;byte_count<=0;frame_bad<=0;header<=0;
        startup_count<=0;context_valid<=0;qp_pending<=0;conn_pending<=0;
        mr_configuration_pending<=0;
        local_qpn<=0;peer_qpn<=0;expected_psn<=0;tx_psn<=0;trusted_pd<=0;local_ip<=0;peer_ip<=0;
        lease<=0;write_operation<=0;command_done<=0;data_done<=0;committed<=0;
        request_va<=0;dma_address<=0;request_length<=0;wire_length<=0;request_key<=0;lease_key<=0;lease_offset<=0;
        data_remaining<=0;wire_remaining<=0;request_psn<=0;lease_tag<=0;
        m_reject_error<=0;m_reject_qpn<=0;m_reject_psn<=0;m_reject_valid<=0;
        fault<=0;fault_code<=0;accepted_count<=0;rejected_count<=0;completed_count<=0;
        tx_deferred_cycles<=0;
        rx_integrity_good_count<=0;rx_integrity_drop_count<=0;
    end else begin
        if(cfg_mr_valid && cfg_mr_ready) mr_configuration_pending<=1;
        if(cfg_mr_response_valid && cfg_mr_response_ready) mr_configuration_pending<=0;
        if(!startup_done) startup_count<=startup_count+1'b1;
        if(rx_good) rx_integrity_good_count<=rx_integrity_good_count+1'b1;
        if(rx_bad || rx_overflow) rx_integrity_drop_count<=rx_integrity_drop_count+1'b1;
        if(core_tx_valid && lease && !committed) tx_deferred_cycles<=tx_deferred_cycles+1'b1;
        if(qp_pending && qp_if_ready) qp_pending<=0;
        if(conn_pending && conn_if_ready) conn_pending<=0;
        if(cfg_qp_valid && cfg_qp_ready) begin
            context_valid<=1;qp_pending<=1;conn_pending<=1;
            local_qpn<={21'd0,cfg_qp_number};peer_qpn<=cfg_peer_qp_number;trusted_pd<=cfg_qp_pd;
            local_ip<=cfg_local_ip;peer_ip<=cfg_peer_ip;expected_psn<=cfg_rx_psn;tx_psn<=cfg_tx_psn;
        end
        if(!fault) begin
            if(shared_mr_fault) begin fault<=1;fault_code<=ERR_MR_PROTOCOL;end
            if(core_rx_bad!=0 || core_tx_bad!=0 || core_overflow!=0 ||
                (core_write_valid && (!lease || !write_operation || command_done)) ||
                (core_read_valid && (!lease || write_operation || command_done)) ||
                (core_write_data_valid && (!lease || !write_operation || data_done))) begin
                fault<=1;fault_code<=ERR_UNEXPECTED;
            end
            if(lease && !command_done && selected_valid && !command_match) begin
                fault<=1;fault_code<=ERR_COMMAND;
            end
            if(m_memory_command_valid && m_memory_command_ready) command_done<=1;
            if(lease && command_done && !data_done) begin
                if((write_operation && core_write_data_valid && !write_shape_ok) ||
                    (!write_operation && s_axis_memory_read_tvalid && !read_shape_ok)) begin
                    fault<=1;fault_code<=ERR_DATA;
                end
                if((m_axis_memory_write_tvalid && m_axis_memory_write_tready) ||
                    (s_axis_memory_read_tvalid && s_axis_memory_read_tready)) begin
                    if(data_remaining<=64) begin data_done<=1;data_remaining<=0;wire_remaining<=0;end
                    else begin data_remaining<=data_remaining-64;wire_remaining<=wire_remaining-64;end
                end
            end
            if(s_memory_status_valid && s_memory_status_ready) begin
                if(s_memory_status_tag!=lease_tag || s_memory_status_error!=0) begin
                    fault<=1;fault_code<=ERR_STATUS;
                end else committed<=1;
            end
            case(state)
                COLLECT: if(checked_valid && checked_ready) begin
                    if(word_count<FRAME_WORDS) begin
                        frame_data[word_count]<=checked_data;frame_keep[word_count]<=checked_keep;
                        word_count<=word_count+1'b1;
                    end else frame_bad<=1;
                    // Saturate oversized input; drain rather than wrap/reuse RAM.
                    if(byte_count<16'hfff0) byte_count<=byte_count+keep_bytes(checked_keep);
                    else frame_bad<=1;
                    if(word_count<4) header[word_count*128+:128]<=checked_data;
                    if(checked_keep==0 || (checked_keep & (checked_keep+16'd1))!=0 ||
                        (!checked_last && checked_keep!=16'hffff)) frame_bad<=1;
                    if(checked_last) state<=PARSE;
                end
                PARSE: begin
                    m_reject_qpn<=parsed_qpn;m_reject_psn<=parsed_psn;
                    m_reject_error<=ERR_FORMAT;
                    state<=REJECT;
                    if(frame_bad || byte_count<60 || header[0+:8]!=8'h45 ||
                        header[9*8+:8]!=17 || be16(header,2)!=byte_count || be16(header,24)!=byte_count-20 ||
                        (be16(header,6)&16'h3fff)!=0 || be16(header,22)!=4791 || be16(header,26)!=0 ||
                        // MigReq(bit6)is a real BTH flag, not TVer/reserved.
                        // It cannot change trusted peer/QP/PD/PSN/MR context.
                        // Current op policy still requires SE0 and TVer0.
                        (header[29*8+:8]&8'h8f)!=0 || be16(header,30)!=16'hffff ||
                        (header[32*8+:8]&8'h3f)!=0 || (header[36*8+:8]&8'h7f)!=0 ||
                        parsed_length==0 || parsed_length>4096) begin
                        m_reject_error<=ERR_FORMAT;
                    end else if(opcode!=8'h0a && opcode!=8'h0c) m_reject_error<=ERR_OPCODE;
                    else if(parsed_qpn!=local_qpn || be32(header,12)!=peer_ip || be32(header,16)!=local_ip)
                        m_reject_error<=ERR_QP;
                    else if(parsed_psn!=expected_psn) m_reject_error<=ERR_PSN;
                    else if((opcode==8'h0a && (byte_count!=60+padded_length || pad!=((-parsed_length)&3))) ||
                        (opcode==8'h0c && (byte_count!=60 || pad!=0))) m_reject_error<=ERR_FORMAT;
                    else if(lease_tag==16'hffff) m_reject_error<=ERR_TAG_EXHAUSTED;
                    else begin
                        request_va<=be64(header,40);request_key<=be32(header,48);request_length<=parsed_length;request_psn<=parsed_psn;
                        write_operation<=opcode==8'h0a;wire_length<=opcode==8'h0a ? padded_length : parsed_length;
                        state<=LOOKUP;
                    end
                end
                LOOKUP: if(mr_request_ready) state<=MR_WAIT;
                MR_WAIT: if(mr_response_valid) begin
                    if(mr_error!=0) begin m_reject_error<=mr_error;state<=REJECT;end
                    else if(mr_tag!=lease_tag+16'd1 || mr_length!=request_length) begin
                        fault<=1;fault_code<=ERR_UNEXPECTED;
                    end else begin
                        lease<=1;lease_tag<=mr_tag;dma_address<=mr_dma;lease_key<=request_key;lease_offset<=mr_offset;
                        command_done<=0;data_done<=0;committed<=0;
                        data_remaining<=request_length;wire_remaining<=wire_length;
                        accepted_count<=accepted_count+1'b1;forward_index<=0;state<=FORWARD;
                    end
                end
                FORWARD: if(replay_ready) begin
                    if(forward_index+1==word_count) state<=ACTIVE;
                    else forward_index<=forward_index+1'b1;
                end
                ACTIVE: if(m_axis_tx_tvalid && m_axis_tx_tready && m_axis_tx_tlast) begin
                    lease<=0;completed_count<=completed_count+1'b1;expected_psn<=expected_psn+1'b1;
                    state<=COLLECT;word_count<=0;byte_count<=0;frame_bad<=0;header<=0;
                end
                REJECT: begin
                    if(!m_reject_valid) begin m_reject_valid<=1;rejected_count<=rejected_count+1'b1;end
                    else if(m_reject_ready) begin
                        m_reject_valid<=0;state<=COLLECT;word_count<=0;byte_count<=0;frame_bad<=0;header<=0;
                    end
                end
                default: begin fault<=1;fault_code<=ERR_UNEXPECTED;end
            endcase
        end
    end
end
endmodule
`resetall
