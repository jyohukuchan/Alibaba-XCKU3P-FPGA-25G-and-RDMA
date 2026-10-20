// SPDX-License-Identifier: BSD-2-Clause-Views
// Actual FNS READ output includes <=3wire pad bytes in command AND data.
// This adapter validates ALL96raw command bits against the full saved, already
// protected READ-response token. Only then normalize length/remove pad before
// the original full-WQE executor. No HLS/packet repair or physical authority.
// Token capture MUST be atomic with the actual executor's identical token
// acceptance (guarded two-consumer fanout), BEFORE replay can reach HLS.
// Final output ends staging only, not memory visibility/WR/CQ/unpin lifetime.
`resetall
`timescale 1ns/1ps
`default_nettype none
module rocev2_wqe_read_unpad #(
    parameter MAX_QPS=8
)(
    input wire clk,
    input wire rst,
    input wire enable,
    input wire [587:0] s_context,
    input wire s_context_valid,
    output wire s_context_ready,
    input wire [MAX_QPS-1:0] downstream_queue_guard,
    input wire [95:0] s_command,
    input wire s_command_valid,
    output wire s_command_ready,
    output wire [95:0] m_command,
    output reg m_command_valid=0,
    input wire m_command_ready,
    input wire [511:0] s_axis_tdata,
    input wire [63:0] s_axis_tkeep,
    input wire s_axis_tlast,
    input wire s_axis_tvalid,
    output wire s_axis_tready,
    output reg [511:0] m_axis_tdata=0,
    output reg [63:0] m_axis_tkeep=0,
    output reg m_axis_tlast=0,
    output reg m_axis_tvalid=0,
    input wire m_axis_tready,
    output wire [MAX_QPS-1:0] queue_guard,
    output wire busy,
    output reg fault=0,
    output reg [7:0] fault_code=0,
    output reg [31:0] context_count=0,
    output reg [31:0] command_count=0,
    output reg [31:0] discarded_padding_bytes=0
);
reg [587:0] owner=0;
reg active=0,command_seen=0,issued=0;
reg [31:0] payload_remaining=0,wire_remaining=0;
wire [63:0] in_id,in_seq,in_epoch,in_va,in_offset,in_remote;
wire [23:0] in_qpn;
wire [15:0] in_pd,in_tag,in_op,in_flags;
wire [31:0] in_length,in_key,in_rkey;
wire [7:0] in_error,in_fetch;
wire [1:0] in_source;
wire in_available,in_authorized;
assign {in_id,in_seq,in_epoch,in_qpn,in_pd,in_tag,in_op,in_flags,in_length,in_key,in_va,in_offset,
    in_remote,in_rkey,in_error,in_source,in_fetch,in_available,in_authorized}=s_context;
wire [63:0] wr_id,sequence_value,epoch,va,offset,remote_address;
wire [23:0] qpn;
wire [15:0] pd,tag,opcode,flags;
wire [31:0] length,key,remote_key;
wire [7:0] error,fetch_error;
wire [1:0] error_source;
wire available,authorized;
assign {wr_id,sequence_value,epoch,qpn,pd,tag,opcode,flags,length,key,va,offset,
    remote_address,remote_key,error,error_source,fetch_error,available,authorized}=owner;
wire known=(^s_context)!==1'bx;
wire guards_known=(^downstream_queue_guard)!==1'bx;
wire [64:0] va_end={1'b0,in_va}+{33'd0,in_length};
wire [64:0] off_end={1'b0,in_offset}+{33'd0,in_length};
wire [64:0] remote_end={1'b0,in_remote}+{33'd0,in_length};
wire context_ok=known && in_qpn<MAX_QPS && in_seq!=0 && in_epoch!=0 && in_tag!=0 &&
    in_op==2 && in_available && in_authorized && in_error==0 && in_source==0 && in_fetch==0 &&
    (in_flags&16'hfffe)==0 && in_length!=0 && in_length<=4096 &&
    (!va_end[64] || va_end==65'h10000000000000000) &&
    (!off_end[64] || off_end==65'h10000000000000000) &&
    (!remote_end[64] || remote_end==65'h10000000000000000);
wire incoming_guard=context_ok && guards_known && downstream_queue_guard[in_qpn]===1'b1;
wire held_guard=qpn<MAX_QPS && guards_known && downstream_queue_guard[qpn]===1'b1;
assign s_context_ready=!active && !fault && enable && !rst && context_ok && incoming_guard;
wire bad_context=enable && !active && ((s_context_valid!==1'b0 && s_context_valid!==1'b1) ||
    (s_context_valid && (!context_ok || !incoming_guard)));
assign queue_guard=(fault || bad_context) ? {MAX_QPS{1'b1}} :
    active ? ({{(MAX_QPS-1){1'b0}},1'b1}<<qpn) :
    (s_context_valid && context_ok) ? ({{(MAX_QPS-1){1'b0}},1'b1}<<in_qpn) : {MAX_QPS{1'b0}};
assign busy=active || fault;
wire [31:0] wire_length=(length+3)&32'hfffffffc;
wire [95:0] expected_raw={2'd0,qpn[9:0],va[51:48],1'b1,1'b0,va[52],1'b1,wire_length[27:0],va[47:0]};
wire command_known=(^s_command)!==1'bx;
wire command_match=command_known && s_command==expected_raw;
wire command_bad=(s_command_valid!==1'b0 && s_command_valid!==1'b1) ||
    (s_command_valid && (!active || command_seen || !command_match));
assign s_command_ready=active && !command_seen && command_match && !command_bad && held_guard && !fault && !rst;
assign m_command={2'd0,qpn[9:0],va[51:48],1'b1,1'b0,va[52],1'b1,length[27:0],va[47:0]};
function [63:0] mask64;
    input [31:0] n;integer b;
    begin for(b=0;b<64;b=b+1)mask64[b]=n>b;end
endfunction
reg data_known;
integer i;
always @*begin
    data_known=1;
    for(i=0;i<64;i=i+1)if(s_axis_tkeep[i] && (^s_axis_tdata[i*8+:8])===1'bx)data_known=0;
end
wire shape_ok=(^{s_axis_tkeep,s_axis_tlast})!==1'bx && data_known &&
    s_axis_tkeep==mask64(wire_remaining) && s_axis_tlast==(wire_remaining<=64);
assign s_axis_tready=active && issued && wire_remaining!=0 && payload_remaining!=0 &&
    !m_axis_tvalid && shape_ok && held_guard && !command_bad && !fault && !rst;
integer lane;
initial if(MAX_QPS<1 || MAX_QPS>8)$fatal(1,"unreviewed READ-pad QP capacity");
always @(posedge clk)begin
    if(rst)begin
        owner<=0;active<=0;command_seen<=0;issued<=0;payload_remaining<=0;wire_remaining<=0;
        m_command_valid<=0;m_axis_tdata<=0;m_axis_tkeep<=0;m_axis_tlast<=0;m_axis_tvalid<=0;
        fault<=0;fault_code<=0;context_count<=0;command_count<=0;discarded_padding_bytes<=0;
    end else begin
        if(s_context_valid && s_context_ready)begin
            owner<=s_context;active<=1;command_seen<=0;issued<=0;
            payload_remaining<=in_length;wire_remaining<=(in_length+3)&32'hfffffffc;
            context_count<=context_count+1'b1;
        end
        if(s_command_valid && s_command_ready)begin command_seen<=1;m_command_valid<=1;end
        // Already-offered command/data stay visible through disable/fault.
        if(m_command_valid && m_command_ready)begin
            m_command_valid<=0;issued<=1;command_count<=command_count+1'b1;
        end
        if(s_axis_tvalid && s_axis_tready)begin
            for(lane=0;lane<64;lane=lane+1)
                m_axis_tdata[lane*8+:8]<=payload_remaining>lane ? s_axis_tdata[lane*8+:8] : 8'd0;
            m_axis_tkeep<=mask64(payload_remaining);m_axis_tlast<=wire_remaining<=64;m_axis_tvalid<=1;
            payload_remaining<=payload_remaining<=64 ? 0 : payload_remaining-64;
            wire_remaining<=wire_remaining<=64 ? 0 : wire_remaining-64;
            if(wire_remaining<=64)discarded_padding_bytes<=discarded_padding_bytes+(wire_remaining-payload_remaining);
        end
        if(m_axis_tvalid && m_axis_tready)begin
            m_axis_tvalid<=0;
            // Only this pad-staging lease ends; executor/wire/CQ still owns WR.
            if(m_axis_tlast && !fault && held_guard)begin active<=0;issued<=0;end
        end
        if(!fault)begin
            if(bad_context)begin fault<=1;fault_code<=8'ha1;end
            if(command_bad)begin fault<=1;fault_code<=8'ha2;end
            if((s_axis_tvalid!==1'b0 && s_axis_tvalid!==1'b1) ||
               (s_axis_tvalid && (!active || (issued && (wire_remaining==0 || payload_remaining==0)) ||
                (issued && !m_axis_tvalid && !shape_ok))))begin fault<=1;fault_code<=8'ha3;end
            if(active && !held_guard)begin fault<=1;fault_code<=8'ha4;end
        end
    end
end
endmodule
`resetall
