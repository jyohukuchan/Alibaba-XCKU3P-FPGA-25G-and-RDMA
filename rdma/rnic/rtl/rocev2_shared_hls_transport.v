// SPDX-License-Identifier: BSD-2-Clause-Views
// One ACTUAL HLS core shared between protected incoming requests and an
// authorized local WQE. Existing remote protection owns role0; complete588-bit
// WQE owns role1. Raw HLS addresses never become DMA authority in this mux.
// MR/executor/response/MAC/CQ protection stays outside and MUST remain real.
// LOCAL ownership is retained until exact retire AND independently proved
// actual core drain. Port idleness alone is NOT that proof; no constant1.
// Whole-NIC reset only. Positive READ/WRITE prototype, not recovery/full RNIC.
`resetall
`timescale 1ns/1ps
`default_nettype none
module rocev2_shared_hls_transport #(parameter QP_TX_ENABLE=0,parameter EXTERNAL_REPLAY_ENABLE=0,parameter RECV_ENABLE=0,parameter RNR_ENABLE=0,parameter RECV_RETIRE_ENABLE=0,parameter RECV_CQ_ENABLE=0,parameter REQUEST_CQ_ENABLE=0) (
    output wire [655:0] m_request_done_data,
    output wire m_request_done_valid,
    input wire m_request_done_ready,
    input wire [587:0] s_recv_retire_context,
    input wire s_recv_retire_valid,
    output wire s_recv_retire_ready,
    input wire [647:0] s_recv_owner_tdata,
    input wire s_recv_owner_tvalid,
    output wire s_recv_owner_tready,
    output wire [679:0] m_recv_done_tdata,
    output wire m_recv_done_tvalid,
    input wire m_recv_done_tready,
    input wire [55:0] s_rnr_event_tdata,
    input wire s_rnr_event_tvalid,
    output wire s_rnr_event_tready,
    input wire remote_receive_held,
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
    output wire [31:0] core_psn_drop_count,
    output wire [31:0] core_retransmit_count,
    output wire [31:0] core_rx_word_count,
    output wire [31:0] core_tx_word_count,
    output wire [31:0] rx_integrity_good_count,
    output wire [31:0] rx_integrity_drop_count,
    output wire [31:0] tx_integrity_good_count,
    output wire [31:0] tx_integrity_drop_count,
    output wire [31:0] integrity_overflow_count,
    input wire [587:0] s_local_owner_context,
    input wire s_local_owner_valid,
    output wire s_local_owner_ready,
    input wire [247:0] s_local_sq_tdata,
    input wire s_local_sq_tvalid,
    output wire s_local_sq_tready,
    input wire [127:0] s_local_rx_tdata,
    input wire [15:0] s_local_rx_tkeep,
    input wire s_local_rx_tvalid,
    output wire s_local_rx_tready,
    input wire s_local_rx_tlast,
    input wire s_local_rx_tuser,
    output wire [127:0] m_local_tx_tdata,
    output wire [15:0] m_local_tx_tkeep,
    output wire m_local_tx_tvalid,
    input wire m_local_tx_tready,
    output wire m_local_tx_tlast,
    output wire [39:0] m_local_ack_tdata,
    output wire m_local_ack_tvalid,
    input wire m_local_ack_tready,
    output wire [95:0] m_local_write_command,
    output wire m_local_write_command_valid,
    input wire m_local_write_command_ready,
    output wire [511:0] m_local_write_tdata,
    output wire [63:0] m_local_write_tkeep,
    output wire m_local_write_tvalid,
    input wire m_local_write_tready,
    output wire m_local_write_tlast,
    output wire [95:0] m_local_read_command,
    output wire m_local_read_command_valid,
    input wire m_local_read_command_ready,
    input wire [511:0] s_local_read_tdata,
    input wire [63:0] s_local_read_tkeep,
    input wire s_local_read_tvalid,
    output wire s_local_read_tready,
    input wire s_local_read_tlast,
    input wire [587:0] s_local_retire_context,
    input wire s_local_retire_valid,
    output wire s_local_retire_ready,
    input wire local_core_drained,
    output wire [7:0] local_hls_queue_guard,
    output wire local_hls_active,
    output wire shared_hls_fault,
    output wire [7:0] shared_hls_fault_code,
    input wire [23:0] trusted_local_qpn,
    input wire trusted_local_ready,
    input wire remote_operation_idle,
    output wire [79:0] m_axis_qp_apply_tdata,
    output wire m_axis_qp_apply_tvalid,
    input wire m_axis_qp_apply_tready
);

localparam NONE=0,REMOTE=1,LOCAL=2;
initial if(RNR_ENABLE && (!QP_TX_ENABLE || !EXTERNAL_REPLAY_ENABLE || !RECV_ENABLE))
    $fatal(1,"RNR requires the matched native receive/replay HLS");
initial if(RECV_RETIRE_ENABLE && !RNR_ENABLE)$fatal(1,"receive receipts require matched native RNR HLS");
initial if(RECV_CQ_ENABLE && !RECV_RETIRE_ENABLE)$fatal(1,"receive CQ needs matched operation receipt");
initial if(REQUEST_CQ_ENABLE && !RECV_CQ_ENABLE)$fatal(1,"request CQ needs complete matched native profile");
reg [1:0] role=NONE;
reg last_local=1,sq_seen=0;
reg [587:0] owner=0;
reg recv_held=0,recv_proved=0;
reg request_proved=0;
reg [647:0] recv_owner=0;
reg fault=0;
reg [7:0] fault_code=0;
wire local_role=role==LOCAL,remote_role=role==REMOTE;
wire core_rnr_ready,core_rnr_fault;
wire core_recv_owner_ready,core_recv_fault,core_recv_done_valid;
wire core_request_owner_ready,core_request_fault,core_request_done_valid;
assign m_request_done_valid=REQUEST_CQ_ENABLE && local_role && core_request_done_valid && !rst;
wire [7:0] request_opcode=owner[339:324]==1 ? 8'h0a : owner[339:324]==2 ? 8'h0c : 8'h04;
wire request_shape=(^m_request_done_data)!==1'bx && m_request_done_data[587:0]===owner &&
    m_request_done_data[655:644]==0 && m_request_done_data[643:636]==request_opcode &&
    m_request_done_data[635:612]==(m_request_done_data[611:588]+24'd1);
wire recv_owner_pending=RECV_RETIRE_ENABLE && s_recv_owner_tvalid;
assign s_recv_owner_tready=RECV_RETIRE_ENABLE && remote_role && core_recv_owner_ready &&
    (!RECV_CQ_ENABLE || !recv_held) && !fault && !rst;
assign m_recv_done_tvalid=RECV_RETIRE_ENABLE && remote_role && core_recv_done_valid && !rst;
wire rnr_pending=RNR_ENABLE && s_rnr_event_tvalid;
assign s_rnr_event_tready=RNR_ENABLE && remote_role && core_rnr_ready && !fault && !rst;
wire core_sq_ready;
wire [63:0] wr_id,sequence_value,epoch,va,offset,remote_address;
wire [23:0] qpn;
wire [15:0] pd,tag,opcode,flags;
wire [31:0] length,key,remote_key;
wire [7:0] error,fetch_error;
wire [1:0] error_source;
wire available,authorized;
assign {wr_id,sequence_value,epoch,qpn,pd,tag,opcode,flags,length,key,va,offset,
    remote_address,remote_key,error,error_source,fetch_error,available,authorized}=s_local_owner_context;
wire [64:0] va_end={1'b0,va}+{33'd0,length};
wire [64:0] off_end={1'b0,offset}+{33'd0,length};
wire [64:0] remote_end={1'b0,remote_address}+{33'd0,length};
wire owner_ok=(^{s_local_owner_context,trusted_local_qpn})!==1'bx &&
    qpn<8 && qpn==trusted_local_qpn && sequence_value!=0 && epoch!=0 && tag!=0 &&
    available && authorized && error==0 && error_source==0 && fetch_error==0 &&
    (opcode==1 || opcode==2 || (opcode==3 && remote_address==0 && remote_key==0)) && (flags&16'hfffe)==0 && length!=0 && length<=4096 &&
    (!va_end[64] || va_end==65'h10000000000000000) &&
    (!off_end[64] || off_end==65'h10000000000000000) &&
    (!remote_end[64] || remote_end==65'h10000000000000000);
wire [63:0] saved_id,saved_seq,saved_epoch,saved_va,saved_off,saved_remote;
wire [23:0] saved_qpn;
wire [15:0] saved_pd,saved_tag,saved_opcode,saved_flags;
wire [31:0] saved_length,saved_key,saved_rkey;
wire [7:0] saved_error,saved_fetch;
wire [1:0] saved_source;
wire saved_available,saved_authorized;
assign {saved_id,saved_seq,saved_epoch,saved_qpn,saved_pd,saved_tag,saved_opcode,saved_flags,
    saved_length,saved_key,saved_va,saved_off,saved_remote,saved_rkey,saved_error,saved_source,
    saved_fetch,saved_available,saved_authorized}=owner;
wire [247:0] expected_sq={7'd0,1'b1,saved_rkey,saved_length,saved_remote,saved_va,
    4'd0,1'b1,1'b1,saved_qpn[9:0],(saved_opcode==1 ? 32'd10 : saved_opcode==3 ? 32'd4 : 32'd12)};
wire sq_ok=(^s_local_sq_tdata)!==1'bx && s_local_sq_tdata==expected_sq;
assign s_local_sq_tready=local_role && !sq_seen && sq_ok && core_sq_ready && !rst;
assign local_hls_active=local_role;
assign shared_hls_fault=fault;
assign shared_hls_fault_code=fault_code;
wire [127:0] h_s_axis_rx_tdata;
wire [15:0] h_s_axis_rx_tkeep;
wire h_s_axis_rx_tvalid;
wire h_s_axis_rx_tready;
wire h_s_axis_rx_tlast;
wire h_s_axis_rx_tuser;
wire [127:0] h_m_axis_tx_tdata;
wire [15:0] h_m_axis_tx_tkeep;
wire h_m_axis_tx_tvalid;
wire h_m_axis_tx_tready;
wire h_m_axis_tx_tlast;
wire [39:0] h_m_axis_ack_tdata;
wire h_m_axis_ack_tvalid;
wire h_m_axis_ack_tready;
wire [95:0] h_m_axis_mem_write_cmd_tdata;
wire h_m_axis_mem_write_cmd_tvalid;
wire h_m_axis_mem_write_cmd_tready;
wire [95:0] h_m_axis_mem_read_cmd_tdata;
wire h_m_axis_mem_read_cmd_tvalid;
wire h_m_axis_mem_read_cmd_tready;
wire [511:0] h_m_axis_mem_write_tdata;
wire [63:0] h_m_axis_mem_write_tkeep;
wire h_m_axis_mem_write_tvalid;
wire h_m_axis_mem_write_tready;
wire h_m_axis_mem_write_tlast;
wire [511:0] h_s_axis_mem_read_tdata;
wire [63:0] h_s_axis_mem_read_tkeep;
wire h_s_axis_mem_read_tvalid;
wire h_s_axis_mem_read_tready;
wire h_s_axis_mem_read_tlast;
assign h_s_axis_rx_tdata=local_role ? s_local_rx_tdata : s_axis_rx_tdata;
assign h_s_axis_rx_tkeep=local_role ? s_local_rx_tkeep : s_axis_rx_tkeep;
assign h_s_axis_rx_tvalid=local_role ? s_local_rx_tvalid : remote_role ? s_axis_rx_tvalid : 1'b0;
assign s_axis_rx_tready=h_s_axis_rx_tready && remote_role;
assign s_local_rx_tready=h_s_axis_rx_tready && local_role;
assign h_s_axis_rx_tlast=local_role ? s_local_rx_tlast : s_axis_rx_tlast;
assign h_s_axis_rx_tuser=local_role ? s_local_rx_tuser : s_axis_rx_tuser;
assign m_axis_tx_tdata=h_m_axis_tx_tdata;
assign m_local_tx_tdata=h_m_axis_tx_tdata;
assign m_axis_tx_tkeep=h_m_axis_tx_tkeep;
assign m_local_tx_tkeep=h_m_axis_tx_tkeep;
assign m_axis_tx_tvalid=h_m_axis_tx_tvalid && remote_role;
assign m_local_tx_tvalid=h_m_axis_tx_tvalid && local_role;
assign h_m_axis_tx_tready=local_role ? m_local_tx_tready : remote_role ? m_axis_tx_tready : 1'b0;
assign m_axis_tx_tlast=h_m_axis_tx_tlast;
assign m_local_tx_tlast=h_m_axis_tx_tlast;
assign s_axis_sq_tready=1'b0;
assign m_axis_ack_tdata=h_m_axis_ack_tdata;
assign m_local_ack_tdata=h_m_axis_ack_tdata;
assign m_axis_ack_tvalid=h_m_axis_ack_tvalid && remote_role;
assign m_local_ack_tvalid=h_m_axis_ack_tvalid && local_role;
assign h_m_axis_ack_tready=local_role ? m_local_ack_tready : remote_role ? m_axis_ack_tready : 1'b0;
assign m_axis_mem_write_cmd_tdata=h_m_axis_mem_write_cmd_tdata;
assign m_local_write_command=h_m_axis_mem_write_cmd_tdata;
assign m_axis_mem_write_cmd_tvalid=h_m_axis_mem_write_cmd_tvalid && remote_role;
assign m_local_write_command_valid=h_m_axis_mem_write_cmd_tvalid && local_role;
assign h_m_axis_mem_write_cmd_tready=local_role ? m_local_write_command_ready : remote_role ? m_axis_mem_write_cmd_tready : 1'b0;
assign m_axis_mem_read_cmd_tdata=h_m_axis_mem_read_cmd_tdata;
assign m_local_read_command=h_m_axis_mem_read_cmd_tdata;
assign m_axis_mem_read_cmd_tvalid=h_m_axis_mem_read_cmd_tvalid && remote_role;
assign m_local_read_command_valid=h_m_axis_mem_read_cmd_tvalid && local_role;
assign h_m_axis_mem_read_cmd_tready=local_role ? m_local_read_command_ready : remote_role ? m_axis_mem_read_cmd_tready : 1'b0;
assign m_axis_mem_write_tdata=h_m_axis_mem_write_tdata;
assign m_local_write_tdata=h_m_axis_mem_write_tdata;
assign m_axis_mem_write_tkeep=h_m_axis_mem_write_tkeep;
assign m_local_write_tkeep=h_m_axis_mem_write_tkeep;
assign m_axis_mem_write_tvalid=h_m_axis_mem_write_tvalid && remote_role;
assign m_local_write_tvalid=h_m_axis_mem_write_tvalid && local_role;
assign h_m_axis_mem_write_tready=local_role ? m_local_write_tready : remote_role ? m_axis_mem_write_tready : 1'b0;
assign m_axis_mem_write_tlast=h_m_axis_mem_write_tlast;
assign m_local_write_tlast=h_m_axis_mem_write_tlast;
assign h_s_axis_mem_read_tdata=local_role ? s_local_read_tdata : s_axis_mem_read_tdata;
assign h_s_axis_mem_read_tkeep=local_role ? s_local_read_tkeep : s_axis_mem_read_tkeep;
assign h_s_axis_mem_read_tvalid=local_role ? s_local_read_tvalid : remote_role ? s_axis_mem_read_tvalid : 1'b0;
assign s_axis_mem_read_tready=h_s_axis_mem_read_tready && remote_role;
assign s_local_read_tready=h_s_axis_mem_read_tready && local_role;
assign h_s_axis_mem_read_tlast=local_role ? s_local_read_tlast : s_axis_mem_read_tlast;
wire core_offers=(h_m_axis_tx_tvalid!==1'b0) || (h_m_axis_ack_tvalid!==1'b0) ||
    (h_m_axis_mem_write_cmd_tvalid!==1'b0) || (h_m_axis_mem_read_cmd_tvalid!==1'b0) ||
    (h_m_axis_mem_write_tvalid!==1'b0);
wire bad_owner=role==NONE && (trusted_local_ready===1'b1) &&
    ((s_local_owner_valid!==1'b0 && s_local_owner_valid!==1'b1) || (s_local_owner_valid && !owner_ok));
wire bad_sq=(s_axis_sq_tvalid!==1'b0) ||
    (s_local_sq_tvalid!==1'b0 && s_local_sq_tvalid!==1'b1) || (s_local_sq_tvalid &&
    (!local_role || sq_seen || !sq_ok));
wire bad_retire=(s_local_retire_valid!==1'b0 && s_local_retire_valid!==1'b1) ||
    (s_local_retire_valid && (!local_role || (^s_local_retire_context)===1'bx || s_local_retire_context!=owner));
wire bad_config=local_role && (s_axis_qp_tvalid || s_axis_conn_tvalid);
wire unowned_core=role==NONE && core_offers;
wire bad_recv_retire=RECV_CQ_ENABLE && s_recv_retire_valid &&
    (!recv_held || s_recv_retire_context!==recv_owner[587:0]);
wire bad_request_done=REQUEST_CQ_ENABLE && core_request_done_valid && (!local_role || !request_shape || request_proved);
wire incoming_fault=bad_owner || bad_sq || bad_retire || bad_config || unowned_core || bad_recv_retire || bad_request_done || (REQUEST_CQ_ENABLE && core_request_fault!==1'b0) || (RNR_ENABLE && core_rnr_fault!==1'b0) || (RECV_RETIRE_ENABLE && core_recv_fault!==1'b0);
// Per-receive operation receipt, not a constant/global drain certificate.
// Admission is held until exact CQ/MAC/RQ retirement; no later RX may overtake.
assign s_recv_retire_ready=RECV_CQ_ENABLE && remote_role && recv_held && recv_proved &&
    s_recv_retire_context===recv_owner[587:0] && remote_operation_idle===1'b1 &&
    !core_offers && !s_axis_rx_tvalid && !rnr_pending && !recv_owner_pending && !core_recv_done_valid &&
    !fault && !incoming_fault && !rst;
assign s_local_owner_ready=!rst && !fault && !incoming_fault && role==NONE && owner_ok &&
    (!REQUEST_CQ_ENABLE || core_request_owner_ready) &&
    (trusted_local_ready===1'b1) && !rnr_pending && !recv_owner_pending && (!s_axis_rx_tvalid || !last_local);
// This readiness requires an EXTERNAL genuine same-core drain certificate.
// Complete interfaces being quiet is necessary but deliberately insufficient.
assign s_local_retire_ready=!rst && !fault && !incoming_fault && local_role && sq_seen &&
    ((local_core_drained===1'b1) || (REQUEST_CQ_ENABLE && request_proved && !core_request_done_valid)) && !core_offers && !s_local_rx_tvalid &&
    !s_local_sq_tvalid && !s_local_read_tvalid && (s_local_retire_context===owner);
assign local_hls_queue_guard=(fault || incoming_fault) ? 8'hff : local_role ?
    (8'h01<<saved_qpn) : (s_local_owner_valid && owner_ok) ? (8'h01<<qpn) : 8'd0;
generate if(QP_TX_ENABLE)begin : qptx_core
rocev2_qptx_integrity_transport #(.LEGACY_QP_KEY(0),.EXTERNAL_REPLAY_ENABLE(EXTERNAL_REPLAY_ENABLE),.RNR_ENABLE(RNR_ENABLE),.RECV_RETIRE_ENABLE(RECV_RETIRE_ENABLE),.REQUEST_CQ_ENABLE(REQUEST_CQ_ENABLE)) core(
.s_request_owner_tdata(s_local_owner_context),.s_request_owner_tvalid(REQUEST_CQ_ENABLE && s_local_owner_valid && s_local_owner_ready),.s_request_owner_tready(core_request_owner_ready),
.m_request_done_tdata(m_request_done_data),.m_request_done_tvalid(core_request_done_valid),.m_request_done_tready(m_request_done_ready && local_role && !fault && !incoming_fault && !rst),.request_fault(core_request_fault),
.s_recv_owner_tdata(s_recv_owner_tdata),.s_recv_owner_tvalid(recv_owner_pending && remote_role && (!RECV_CQ_ENABLE || !recv_held) && !fault && !rst),
.s_recv_owner_tready(core_recv_owner_ready),.m_recv_done_tdata(m_recv_done_tdata),
.m_recv_done_tvalid(core_recv_done_valid),.m_recv_done_tready(m_recv_done_tready && remote_role && !fault && !rst),.recv_fault(core_recv_fault),
.s_rnr_event_tdata(s_rnr_event_tdata),
.s_rnr_event_tvalid(RNR_ENABLE && s_rnr_event_tvalid && remote_role && !fault && !rst),
.s_rnr_event_tready(core_rnr_ready),.rnr_fault(core_rnr_fault),
.m_axis_qp_apply_tdata(m_axis_qp_apply_tdata),
.m_axis_qp_apply_tvalid(m_axis_qp_apply_tvalid),
.m_axis_qp_apply_tready(m_axis_qp_apply_tready),
.clk(clk),
.rst(rst),
.s_axis_rx_tdata(h_s_axis_rx_tdata),
.s_axis_rx_tkeep(h_s_axis_rx_tkeep),
.s_axis_rx_tvalid(h_s_axis_rx_tvalid),
.s_axis_rx_tready(h_s_axis_rx_tready),
.s_axis_rx_tlast(h_s_axis_rx_tlast),
.s_axis_rx_tuser(h_s_axis_rx_tuser),
.m_axis_tx_tdata(h_m_axis_tx_tdata),
.m_axis_tx_tkeep(h_m_axis_tx_tkeep),
.m_axis_tx_tvalid(h_m_axis_tx_tvalid),
.m_axis_tx_tready(h_m_axis_tx_tready),
.m_axis_tx_tlast(h_m_axis_tx_tlast),
.s_axis_qp_tdata(s_axis_qp_tdata),
.s_axis_qp_tvalid(s_axis_qp_tvalid),
.s_axis_qp_tready(s_axis_qp_tready),
.s_axis_conn_tdata(s_axis_conn_tdata),
.s_axis_conn_tvalid(s_axis_conn_tvalid),
.s_axis_conn_tready(s_axis_conn_tready),
.s_axis_sq_tdata(s_local_sq_tdata[239:0]),
.s_axis_sq_tvalid(s_local_sq_tvalid && local_role && !sq_seen && sq_ok),
.s_axis_sq_tready(core_sq_ready),
.m_axis_ack_tdata(h_m_axis_ack_tdata),
.m_axis_ack_tvalid(h_m_axis_ack_tvalid),
.m_axis_ack_tready(h_m_axis_ack_tready),
.m_axis_mem_write_cmd_tdata(h_m_axis_mem_write_cmd_tdata),
.m_axis_mem_write_cmd_tvalid(h_m_axis_mem_write_cmd_tvalid),
.m_axis_mem_write_cmd_tready(h_m_axis_mem_write_cmd_tready),
.m_axis_mem_read_cmd_tdata(h_m_axis_mem_read_cmd_tdata),
.m_axis_mem_read_cmd_tvalid(h_m_axis_mem_read_cmd_tvalid),
.m_axis_mem_read_cmd_tready(h_m_axis_mem_read_cmd_tready),
.m_axis_mem_write_tdata(h_m_axis_mem_write_tdata),
.m_axis_mem_write_tkeep(h_m_axis_mem_write_tkeep),
.m_axis_mem_write_tvalid(h_m_axis_mem_write_tvalid),
.m_axis_mem_write_tready(h_m_axis_mem_write_tready),
.m_axis_mem_write_tlast(h_m_axis_mem_write_tlast),
.s_axis_mem_read_tdata(h_s_axis_mem_read_tdata),
.s_axis_mem_read_tkeep(h_s_axis_mem_read_tkeep),
.s_axis_mem_read_tvalid(h_s_axis_mem_read_tvalid),
.s_axis_mem_read_tready(h_s_axis_mem_read_tready),
.s_axis_mem_read_tlast(h_s_axis_mem_read_tlast),
.local_ip_address(local_ip_address),
.m_axis_debug_tdata(m_axis_debug_tdata),
.m_axis_debug_tvalid(m_axis_debug_tvalid),
.m_axis_debug_tready(m_axis_debug_tready),
.core_psn_drop_count(core_psn_drop_count),
.core_retransmit_count(core_retransmit_count),
.core_rx_word_count(core_rx_word_count),
.core_tx_word_count(core_tx_word_count),
.rx_integrity_good_count(rx_integrity_good_count),
.rx_integrity_drop_count(rx_integrity_drop_count),
.tx_integrity_good_count(tx_integrity_good_count),
.tx_integrity_drop_count(tx_integrity_drop_count),
.integrity_overflow_count(integrity_overflow_count),
.s_axis_sq_rkey(s_local_sq_tdata[239:208]));
end else begin : legacy_core
assign core_request_owner_ready=0;assign core_request_fault=0;assign core_request_done_valid=0;assign m_request_done_data=0;
assign core_recv_owner_ready=0;assign core_recv_done_valid=0;assign m_recv_done_tdata=0;assign core_recv_fault=0;
assign core_rnr_ready=0;assign core_rnr_fault=0;
assign m_axis_qp_apply_tdata=0;
assign m_axis_qp_apply_tvalid=0;
rocev2_integrity_transport #(.LEGACY_QP_KEY(0)) core(
.clk(clk),
.rst(rst),
.s_axis_rx_tdata(h_s_axis_rx_tdata),
.s_axis_rx_tkeep(h_s_axis_rx_tkeep),
.s_axis_rx_tvalid(h_s_axis_rx_tvalid),
.s_axis_rx_tready(h_s_axis_rx_tready),
.s_axis_rx_tlast(h_s_axis_rx_tlast),
.s_axis_rx_tuser(h_s_axis_rx_tuser),
.m_axis_tx_tdata(h_m_axis_tx_tdata),
.m_axis_tx_tkeep(h_m_axis_tx_tkeep),
.m_axis_tx_tvalid(h_m_axis_tx_tvalid),
.m_axis_tx_tready(h_m_axis_tx_tready),
.m_axis_tx_tlast(h_m_axis_tx_tlast),
.s_axis_qp_tdata(s_axis_qp_tdata),
.s_axis_qp_tvalid(s_axis_qp_tvalid),
.s_axis_qp_tready(s_axis_qp_tready),
.s_axis_conn_tdata(s_axis_conn_tdata),
.s_axis_conn_tvalid(s_axis_conn_tvalid),
.s_axis_conn_tready(s_axis_conn_tready),
.s_axis_sq_tdata(s_local_sq_tdata[239:0]),
.s_axis_sq_tvalid(s_local_sq_tvalid && local_role && !sq_seen && sq_ok),
.s_axis_sq_tready(core_sq_ready),
.m_axis_ack_tdata(h_m_axis_ack_tdata),
.m_axis_ack_tvalid(h_m_axis_ack_tvalid),
.m_axis_ack_tready(h_m_axis_ack_tready),
.m_axis_mem_write_cmd_tdata(h_m_axis_mem_write_cmd_tdata),
.m_axis_mem_write_cmd_tvalid(h_m_axis_mem_write_cmd_tvalid),
.m_axis_mem_write_cmd_tready(h_m_axis_mem_write_cmd_tready),
.m_axis_mem_read_cmd_tdata(h_m_axis_mem_read_cmd_tdata),
.m_axis_mem_read_cmd_tvalid(h_m_axis_mem_read_cmd_tvalid),
.m_axis_mem_read_cmd_tready(h_m_axis_mem_read_cmd_tready),
.m_axis_mem_write_tdata(h_m_axis_mem_write_tdata),
.m_axis_mem_write_tkeep(h_m_axis_mem_write_tkeep),
.m_axis_mem_write_tvalid(h_m_axis_mem_write_tvalid),
.m_axis_mem_write_tready(h_m_axis_mem_write_tready),
.m_axis_mem_write_tlast(h_m_axis_mem_write_tlast),
.s_axis_mem_read_tdata(h_s_axis_mem_read_tdata),
.s_axis_mem_read_tkeep(h_s_axis_mem_read_tkeep),
.s_axis_mem_read_tvalid(h_s_axis_mem_read_tvalid),
.s_axis_mem_read_tready(h_s_axis_mem_read_tready),
.s_axis_mem_read_tlast(h_s_axis_mem_read_tlast),
.local_ip_address(local_ip_address),
.m_axis_debug_tdata(m_axis_debug_tdata),
.m_axis_debug_tvalid(m_axis_debug_tvalid),
.m_axis_debug_tready(m_axis_debug_tready),
.core_psn_drop_count(core_psn_drop_count),
.core_retransmit_count(core_retransmit_count),
.core_rx_word_count(core_rx_word_count),
.core_tx_word_count(core_tx_word_count),
.rx_integrity_good_count(rx_integrity_good_count),
.rx_integrity_drop_count(rx_integrity_drop_count),
.tx_integrity_good_count(tx_integrity_good_count),
.tx_integrity_drop_count(tx_integrity_drop_count),
.integrity_overflow_count(integrity_overflow_count),
.s_axis_sq_rkey(s_local_sq_tdata[239:208]));
end endgenerate
always @(posedge clk)begin
    if(rst)begin role<=NONE;last_local<=1;sq_seen<=0;owner<=0;recv_held<=0;recv_proved<=0;recv_owner<=0;request_proved<=0;fault<=0;fault_code<=0;end
    else begin
        if(!fault && !incoming_fault && role==NONE)begin
            if(s_local_owner_valid && s_local_owner_ready)begin
                role<=LOCAL;owner<=s_local_owner_context;sq_seen<=0;request_proved<=0;
            end else if(rnr_pending || recv_owner_pending || (s_axis_rx_tvalid && (!s_local_owner_valid || last_local)))role<=REMOTE;
        end
        if(local_role && s_local_sq_tvalid && s_local_sq_tready)sq_seen<=1;
        if(m_request_done_valid && m_request_done_ready)request_proved<=1;
        if(RECV_CQ_ENABLE && s_recv_owner_tvalid && s_recv_owner_tready)begin
            recv_held<=1;recv_proved<=0;recv_owner<=s_recv_owner_tdata;
        end
        if(RECV_CQ_ENABLE && m_recv_done_tvalid && m_recv_done_tready)begin
            if(!recv_held || m_recv_done_tdata[647:0]!==recv_owner || m_recv_done_tdata[679:672]!=0)begin
                fault<=1;fault_code<=8'hb6;
            end else recv_proved<=1;
        end
        // Existing protected responder's real lease/TX/visibility controller
        // certifies its finished remote operation, never a local WQE/CQ.
        if(remote_role && remote_operation_idle===1'b1 && !core_offers && !s_axis_rx_tvalid && !rnr_pending && !recv_owner_pending && !core_recv_done_valid &&
            (!RECV_ENABLE || remote_receive_held===1'b0) && (!RECV_CQ_ENABLE || !recv_held))begin
            role<=NONE;last_local<=0;
        end
        if(s_local_retire_valid && s_local_retire_ready)begin role<=NONE;last_local<=1;request_proved<=0;end
        if(s_recv_retire_valid && s_recv_retire_ready)begin
            recv_held<=0;recv_proved<=0;recv_owner<=0;role<=NONE;last_local<=0;
        end
        if(incoming_fault && !fault)begin
            fault<=1;fault_code<=bad_owner ? 8'hb1 : bad_sq ? 8'hb2 : bad_retire ? 8'hb3 : bad_config ? 8'hb4 : 8'hb5;
        end
    end
end
endmodule
`resetall
