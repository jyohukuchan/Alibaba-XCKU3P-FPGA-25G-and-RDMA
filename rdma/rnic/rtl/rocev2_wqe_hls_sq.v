// SPDX-License-Identifier: BSD-2-Clause-Views
// SAME-MR authorized native work -> complete owner context -> per-WR HLS SQ.
// The owner receiver MUST be the real executor/wire/CQ lifetime controller;
// its per-QP guard must cover handoff BEFORE HLS can accept the SQ. This is
// not a local memory executor, ACK/READ-response protection or CQ completion.
// Output is the actual248-bit per-WR HLS ABI, including key-valid bit240;
// never a legacy240-bit SQ or key0 inference/fallback. Reset is not recovery.
`resetall
`timescale 1ns/1ps
`default_nettype none
module rocev2_wqe_hls_sq #(
    parameter MAX_QPS=8,
    parameter IMMEDIATE_ENABLE=0
)(
    input wire clk,
    input wire rst,
    input wire enable,
    input wire halt,
    // Private RTL tuple, not a software wire ABI: same588-bit concatenation
    // as native SQ admission: id/seq/epoch/QPN/PD/tag/op/flags/len/lkey/VA/
    // offset/remoteVA/rkey/error/error_source/fetch_error/available/authorized.
    input wire [587+32*IMMEDIATE_ENABLE:0] s_work_context,
    input wire s_work_valid,
    output wire s_work_ready,
    output reg [587+32*IMMEDIATE_ENABLE:0] m_owner_context=0,
    output wire m_owner_valid,
    input wire m_owner_ready,
    input wire [MAX_QPS-1:0] downstream_queue_guard,
    output wire [247+32*IMMEDIATE_ENABLE:0] m_axis_sq_tdata,
    output reg m_axis_sq_tvalid=0,
    input wire m_axis_sq_tready,
    output wire [MAX_QPS-1:0] queue_guard,
    output wire configuration_guard,
    output wire busy,
    output reg fault=0,
    output reg [7:0] fault_code=0,
    output reg [31:0] owner_handoff_count=0,
    output reg [31:0] HLS_SQ_handoff_count=0
);
wire [63:0] in_id,in_sequence,in_epoch,in_local_address,in_local_offset,in_remote_address;
wire [23:0] in_qpn;
wire [15:0] in_pd,in_tag,in_opcode,in_flags;
wire [31:0] in_length,in_local_key,in_remote_key;
wire [7:0] in_error,in_fetch_error;
wire [1:0] in_error_source;
wire in_available,in_authorized;
assign {in_id,in_sequence,in_epoch,in_qpn,in_pd,in_tag,in_opcode,in_flags,in_length,
    in_local_key,in_local_address,in_local_offset,in_remote_address,in_remote_key,
    in_error,in_error_source,in_fetch_error,in_available,in_authorized}=s_work_context[587:0];
wire [31:0] in_immediate=s_work_context>>588;
wire [63:0] id,sequence_value,epoch,local_address,local_offset,remote_address;
wire [23:0] qpn;
wire [15:0] pd,tag,opcode,flags;
wire [31:0] length,local_key,remote_key;
wire [7:0] error,fetch_error;
wire [1:0] error_source;
wire available,authorized;
assign {id,sequence_value,epoch,qpn,pd,tag,opcode,flags,length,local_key,
    local_address,local_offset,remote_address,remote_key,error,error_source,
    fetch_error,available,authorized}=m_owner_context[587:0];
wire [31:0] immediate=m_owner_context>>588;
reg active=0,owner_sent=0;
wire known=(^s_work_context)!==1'bx;
wire downstream_known=(^downstream_queue_guard)!==1'bx;
wire [64:0] local_end={1'b0,in_local_address}+{33'd0,in_length};
wire [64:0] offset_end={1'b0,in_local_offset}+{33'd0,in_length};
wire [64:0] remote_end={1'b0,in_remote_address}+{33'd0,in_length};
wire identity_ok=known && in_qpn<MAX_QPS && in_tag!=0 && in_sequence!=0 && in_epoch!=0;
wire authorization_ok=in_error==0 && in_error_source==0 && in_fetch_error==0 && in_available &&
    in_authorized && (in_opcode==1 || in_opcode==2 ||
        ((in_opcode==3 || (IMMEDIATE_ENABLE && in_opcode==5)) && in_remote_address==0 && in_remote_key==0) ||
        (IMMEDIATE_ENABLE && in_opcode==6)) &&
    ((IMMEDIATE_ENABLE && (in_opcode==5 || in_opcode==6)) || in_immediate==0) && (in_flags & 16'hfffe)==0 &&
    in_length!=0 && in_length<=4096 &&
    (!local_end[64] || local_end==65'h10000000000000000) &&
    (!offset_end[64] || offset_end==65'h10000000000000000) &&
    (!remote_end[64] || remote_end==65'h10000000000000000);
wire denial_ok=in_error!=0 && !in_authorized &&
    ((in_error_source==1 && in_fetch_error==in_error && in_fetch_error<=15 && !in_available) ||
     (in_error_source==2 && in_fetch_error==0)) &&
    {in_opcode,in_flags,in_length,in_local_key,in_local_address,in_local_offset,in_remote_address,in_remote_key,in_immediate}==0;
wire offered=s_work_valid===1'b1;
wire bad_offer=enable && ((s_work_valid!==1'b0 && s_work_valid!==1'b1) ||
    (offered && (!identity_ok || (!authorization_ok && !denial_ok) || !downstream_known)));
wire target_guard=identity_ok ? downstream_queue_guard[in_qpn] : 1'b1;
assign s_work_ready=!active && !fault && enable && !rst && identity_ok &&
    (authorization_ok || denial_ok) && downstream_known && !target_guard;
assign m_owner_valid=active && !owner_sent;
// Header fields are opcode32/QPN10/host1/lst1/offs4, then full params192.
// Both WRITE source and READ destination refer to actual HOST memory.
// rkey0 remains exact; bit240is explicitly1, all7padding bits zero.
wire [31:0] wire_opcode=opcode==1 ? 32'd10 : opcode==2 ? 32'd12 : opcode==5 ? 32'd5 : opcode==6 ? 32'd11 : 32'd4;
wire [240:0] sq_payload={1'b1,remote_key,length,remote_address,local_address,4'd0,1'b1,1'b1,qpn[9:0],wire_opcode};
assign m_axis_sq_tdata=IMMEDIATE_ENABLE ? {7'd0,immediate,sq_payload} : {7'd0,sq_payload};
wire own_guard=active && qpn<MAX_QPS && downstream_queue_guard[qpn]===1'b1;
wire owner_transfer=m_owner_valid && m_owner_ready && own_guard;
wire sq_transfer=m_axis_sq_tvalid && m_axis_sq_tready;
assign queue_guard=(fault || bad_offer) ? {MAX_QPS{1'b1}} :
    active ? ({{(MAX_QPS-1){1'b0}},1'b1}<<qpn) :
    (enable && offered && identity_ok) ? ({{(MAX_QPS-1){1'b0}},1'b1}<<in_qpn) : {MAX_QPS{1'b0}};
assign configuration_guard=|queue_guard;
assign busy=active || fault;
initial begin
    if(MAX_QPS<1 || MAX_QPS>8)$fatal(1,"unreviewed HLS SQ QP capacity");
    if(IMMEDIATE_ENABLE!=0 && IMMEDIATE_ENABLE!=1)$fatal(1,"Immediate HLS profile must be static0or1");
end
always @(posedge clk)begin
    if(rst)begin
        m_owner_context<=0;active<=0;owner_sent<=0;m_axis_sq_tvalid<=0;
        fault<=0;fault_code<=0;owner_handoff_count<=0;HLS_SQ_handoff_count<=0;
    end else begin
        if(s_work_valid && s_work_ready)begin
            m_owner_context<=s_work_context;active<=1;owner_sent<=0;
        end
        if(owner_transfer)begin
            owner_sent<=1;owner_handoff_count<=owner_handoff_count+1'b1;
            if(!authorized)active<=0;
        end
        // Pause/fault prevents a NEW SQ offer, never withdraws an offer that
        // was already visible to HLS. Owner context still remains held.
        if(active && owner_sent && authorized && !m_axis_sq_tvalid && !halt && !fault && own_guard)
            m_axis_sq_tvalid<=1;
        if(sq_transfer)begin
            m_axis_sq_tvalid<=0;HLS_SQ_handoff_count<=HLS_SQ_handoff_count+1'b1;
            // Only the staging owner ends. The actual downstream WR guard
            // was required BEFORE SQ offer and must remain beyond this edge.
            if(!fault && own_guard)begin active<=0;owner_sent<=0;end
        end
        if(!fault)begin
            if(bad_offer)begin fault<=1;fault_code<=8'h71;end
            if(m_owner_valid && m_owner_ready && !own_guard)begin fault<=1;fault_code<=8'h72;end
            if(active && owner_sent && !own_guard)begin fault<=1;fault_code<=8'h73;end
        end
    end
end
endmodule
`resetall
