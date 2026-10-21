// SPDX-License-Identifier: BSD-2-Clause-Views
// Protected segmented WRITE packet -> SAME shared MR-relative backend.
// s_packet_* MUST connect directly to the actual message MR guard. The
// guard retains the WHOLE message lease; this packet leaf never unpins it.
// HLS96 is an assertion, NOT address/key/offset/physical DMA authority.
// Backend status MUST be from the real shared nonce/paged/fenced backend.
// Actual HLS456 -> SAME ACK allocator -> actual MAC472 joins that status
// and real unpadded data EOF. No idle/drain/reset/CQ certificate is invented.
`resetall
`timescale 1ns/1ps
`default_nettype none
module rocev2_remote_write_memory #(
    parameter MAX_QPS=8
)(
    input wire clk,input wire rst,input wire enable,input wire parent_fault,
    input wire [423:0] s_packet_token,input wire [63:0] s_packet_mr_offset,s_packet_mr_address,
    input wire s_packet_notify,input wire [619:0] s_packet_rq_context,
    input wire s_packet_valid,output wire s_packet_ready,
    output wire [423:0] m_hls_owner,output wire m_hls_owner_valid,input wire m_hls_owner_ready,
    output wire [423:0] m_ack_owner,output wire m_ack_owner_notify,output wire [619:0] m_ack_owner_rq_context,
    output wire m_ack_owner_valid,input wire m_ack_owner_ready,
    // After the actual origin router has selected remote and stripped2bits.
    input wire [95:0] s_hls_command,input wire s_hls_command_valid,output wire s_hls_command_ready,
    input wire [511:0] s_hls_data,input wire [63:0] s_hls_keep,input wire s_hls_last,
    input wire s_hls_valid,output wire s_hls_ready,
    output wire m_command_write,output wire [63:0] m_command_offset,
    output wire [31:0] m_command_length,m_command_key,output wire [15:0] m_command_tag,
    output reg m_command_valid=0,input wire m_command_ready,
    output reg [511:0] m_data=0,output reg [63:0] m_keep=0,output reg m_last=0,
    output reg m_valid=0,input wire m_ready,
    input wire [15:0] s_status_tag,input wire [7:0] s_status_error,input wire s_status_valid,output wire s_status_ready,
    input wire [455:0] s_hls_done,input wire s_hls_done_valid,output wire s_hls_done_ready,
    output wire [455:0] m_ack_core,output wire m_ack_core_valid,input wire m_ack_core_ready,
    input wire [471:0] s_ack_done,input wire s_ack_done_valid,output wire s_ack_done_ready,
    output wire [423:0] m_done_token,output wire [23:0] m_done_msn,output wire [7:0] m_done_proofs,
    output wire m_done_valid,input wire m_done_ready,
    output wire [423:0] m_ack_retire_token,output wire m_ack_retire_valid,input wire m_ack_retire_ready,
    output wire [MAX_QPS-1:0] queue_guard,output wire configuration_guard,output wire busy,
    output reg fault=0,output reg [7:0] fault_code=0,
    output reg [31:0] packet_count=0,command_count=0,status_count=0,done_count=0,retired_count=0
);
initial if(MAX_QPS!=8)$fatal(1,"original8QP remote WRITE geometry required");
reg active=0,hls_owner_sent=0,ack_owner_sent=0,raw_seen=0,issued=0;
reg data_done=0,status_seen=0,hls_seen=0,ack_core_sent=0,ack_seen=0,done_sent=0;
reg [423:0] owner=0;
reg [63:0] mr_offset=0;
reg notify=0;reg [619:0] rq_context=0;
reg [31:0] remaining=0,wire_remaining=0;
reg [455:0] hls_proof=0;
reg [15:0] ack_tag=0;
wire stopped=fault || parent_fault!==1'b0;
wire [32:0] in_end={1'b0,s_packet_token[103:72]}+{1'b0,s_packet_token[71:40]};
wire [64:0] in_va_end={1'b0,s_packet_token[223:160]}+{33'd0,s_packet_token[159:128]};
wire [64:0] in_offset_end={1'b0,s_packet_mr_offset}+{33'd0,s_packet_token[71:40]};
wire [64:0] in_mr_end={1'b0,s_packet_mr_address}+{33'd0,s_packet_token[71:40]};
wire [23:0] in_psn_delta=s_packet_token[103:84];
wire owner_known=(^{s_packet_token,s_packet_mr_offset,s_packet_mr_address,s_packet_notify,s_packet_rq_context})!==1'bx;
wire owner_shape=owner_known && s_packet_token[423:400]<MAX_QPS && s_packet_token[399:384]!=0 &&
    s_packet_token[383:320]!=0 && s_packet_token[319:256]!=0 && s_packet_token[255:224]!=0 && s_packet_token[15:0]!=0 &&
    s_packet_token[159:128]>4096 && s_packet_token[159:128]<=1048576 && s_packet_token[83:72]==0 &&
    s_packet_token[71:40]!=0 && s_packet_token[71:40]<=4096 &&
    in_end<={1'b0,s_packet_token[159:128]} &&
    (in_end=={1'b0,s_packet_token[159:128]} || s_packet_token[71:40]==4096) &&
    s_packet_token[39:16]==((s_packet_token[127:104]+in_psn_delta)&24'hffffff) &&
    in_va_end<=65'h10000000000000000 && in_offset_end<=65'h10000000000000000 && in_mr_end<=65'h10000000000000000 &&
    (s_packet_notify ? in_end=={1'b0,s_packet_token[159:128]} &&
        s_packet_rq_context[395:372]===s_packet_token[423:400] &&
        s_packet_rq_context[371:356]===s_packet_token[399:384] &&
        s_packet_rq_context[459:396]===s_packet_token[383:320]:s_packet_rq_context===620'd0);
assign s_packet_ready=!active && enable===1'b1 && owner_shape && !stopped && !rst;
assign m_hls_owner=owner;assign m_hls_owner_valid=active && !hls_owner_sent && !stopped && !rst;
assign m_ack_owner=owner;assign m_ack_owner_notify=notify;assign m_ack_owner_rq_context=rq_context;
assign m_ack_owner_valid=active && !ack_owner_sent && !stopped && !rst;
wire [64:0] packet_va={1'b0,owner[223:160]}+{33'd0,owner[103:72]};
wire [31:0] wire_length=(owner[71:40]+3)&32'hfffffffc;
wire [32:0] packet_end={1'b0,owner[103:72]}+{1'b0,owner[71:40]};
wire terminal_packet=packet_end=={1'b0,owner[159:128]};
wire [95:0] expected_command={2'd0,owner[409:400],packet_va[51:48],1'b1,1'b0,
    packet_va[52],terminal_packet,wire_length[27:0],packet_va[47:0]};
wire command_match=(^s_hls_command)!==1'bx && s_hls_command===expected_command;
assign s_hls_command_ready=active && hls_owner_sent && ack_owner_sent && !raw_seen && command_match && !stopped && !rst;
assign m_command_write=1'b1;assign m_command_offset=mr_offset;assign m_command_length=owner[71:40];
assign m_command_key=owner[255:224];assign m_command_tag=owner[15:0];
function [63:0] mask64;
    input [31:0] n;integer lane;
    begin for(lane=0;lane<64;lane=lane+1)mask64[lane]=n>lane;end
endfunction
reg bytes_known,pad_zero;
integer lane;
always @*begin
    bytes_known=1;pad_zero=1;
    for(lane=0;lane<64;lane=lane+1)begin
        if(s_hls_keep[lane] && (^s_hls_data[lane*8+:8])===1'bx)bytes_known=0;
        if(lane>=remaining && lane<wire_remaining && s_hls_data[lane*8+:8]!==8'd0)pad_zero=0;
    end
end
wire input_shape=(^{s_hls_keep,s_hls_last})!==1'bx && bytes_known && pad_zero &&
    s_hls_keep==mask64(wire_remaining) && s_hls_last==(wire_remaining<=64);
assign s_hls_ready=active && issued && !data_done && remaining!=0 && !m_valid && input_shape && !stopped && !rst;
wire output_fire=m_valid && m_ready;
wire status_match=(^{s_status_tag,s_status_error})!==1'bx && s_status_tag===owner[15:0];
assign s_status_ready=active && issued && !status_seen && status_match &&
    (data_done || s_status_error!=0) && !stopped && !rst;
wire hls_match=(^s_hls_done)!==1'bx && s_hls_done[423:0]===owner && s_hls_done[455:448]==0;
assign s_hls_done_ready=active && hls_owner_sent && !hls_seen && hls_match && !stopped && !rst;
assign m_ack_core=hls_proof;
assign m_ack_core_valid=active && hls_seen && ack_owner_sent && !ack_core_sent && !stopped && !rst;
wire ack_match=(^s_ack_done)!==1'bx && s_ack_done[455:0]===hls_proof &&
    s_ack_done[471:469]==3'b011 && s_ack_done[468:456]!=0;
assign s_ack_done_ready=active && hls_seen && ack_core_sent && !ack_seen && ack_match && !stopped && !rst;
assign m_done_token=owner;assign m_done_msn=hls_proof[447:424];
assign m_done_proofs={4'd0,ack_seen,hls_seen,status_seen,data_done};
assign m_done_valid=active && raw_seen && issued && hls_owner_sent && ack_owner_sent && ack_core_sent &&
    m_done_proofs==8'h0f && !done_sent && !stopped && !rst;
assign m_ack_retire_token=owner;
assign m_ack_retire_valid=active && done_sent && !stopped && !rst;
assign busy=active || stopped;
assign configuration_guard=busy || s_packet_valid!==1'b0;
assign queue_guard=stopped ? 8'hff:active ? (8'h01<<owner[423:400]):
    s_packet_valid && owner_shape ? (8'h01<<s_packet_token[423:400]):8'd0;
always @(posedge clk)begin
    if(rst)begin
        active<=0;hls_owner_sent<=0;ack_owner_sent<=0;raw_seen<=0;issued<=0;
        data_done<=0;status_seen<=0;hls_seen<=0;ack_core_sent<=0;ack_seen<=0;done_sent<=0;
        owner<=0;mr_offset<=0;notify<=0;rq_context<=0;remaining<=0;wire_remaining<=0;hls_proof<=0;ack_tag<=0;
        m_command_valid<=0;m_data<=0;m_keep<=0;m_last<=0;m_valid<=0;
        fault<=0;fault_code<=0;packet_count<=0;command_count<=0;status_count<=0;done_count<=0;retired_count<=0;
    end else begin
        if(s_packet_valid && s_packet_ready)begin
            active<=1;owner<=s_packet_token;mr_offset<=s_packet_mr_offset;notify<=s_packet_notify;rq_context<=s_packet_rq_context;
            hls_owner_sent<=0;ack_owner_sent<=0;raw_seen<=0;issued<=0;data_done<=0;status_seen<=0;
            hls_seen<=0;ack_core_sent<=0;ack_seen<=0;done_sent<=0;hls_proof<=0;ack_tag<=0;
            remaining<=s_packet_token[71:40];wire_remaining<=(s_packet_token[71:40]+3)&32'hfffffffc;
            packet_count<=packet_count+1'b1;
        end
        if(m_hls_owner_valid && m_hls_owner_ready)hls_owner_sent<=1;
        if(m_ack_owner_valid && m_ack_owner_ready)ack_owner_sent<=1;
        if(s_hls_command_valid && s_hls_command_ready)begin raw_seen<=1;m_command_valid<=1;end
        // Already offered backend command/data stay stable on disable/fault.
        if(m_command_valid && m_command_ready)begin m_command_valid<=0;issued<=1;command_count<=command_count+1'b1;end
        if(s_hls_valid && s_hls_ready)begin
            for(integer b=0;b<64;b=b+1)m_data[b*8+:8]<=b<remaining ? s_hls_data[b*8+:8]:8'd0;
            m_keep<=mask64(remaining);m_last<=remaining<=64;m_valid<=1;
            remaining<=remaining<=64 ? 0:remaining-64;
            wire_remaining<=wire_remaining<=64 ? 0:wire_remaining-64;
        end
        if(output_fire)begin m_valid<=0;if(m_last)data_done<=1;end
        if(s_status_valid && s_status_ready)begin
            status_seen<=1;status_count<=status_count+1'b1;
            if(s_status_error!=0)begin fault<=1;fault_code<=8'hb5;end
        end
        if(s_hls_done_valid && s_hls_done_ready)begin hls_seen<=1;hls_proof<=s_hls_done;end
        if(m_ack_core_valid && m_ack_core_ready)ack_core_sent<=1;
        if(s_ack_done_valid && s_ack_done_ready)begin ack_seen<=1;ack_tag<=s_ack_done[471:456];end
        if(m_done_valid && m_done_ready)begin done_sent<=1;done_count<=done_count+1'b1;end
        if(m_ack_retire_valid && m_ack_retire_ready)begin
            active<=0;owner<=0;rq_context<=0;notify<=0;retired_count<=retired_count+1'b1;
        end
        if(!fault)begin
            if(parent_fault!==1'b0)begin fault<=1;fault_code<=8'hb0;end
            if(s_packet_valid!==1'b0 && s_packet_valid!==1'b1 ||
               !active && enable===1'b1 && s_packet_valid && !owner_shape)begin fault<=1;fault_code<=8'hb1;end
            if(s_hls_command_valid!==1'b0 && s_hls_command_valid!==1'b1 ||
               s_hls_command_valid && (!active || raw_seen || !command_match))begin fault<=1;fault_code<=8'hb2;end
            if(s_hls_valid!==1'b0 && s_hls_valid!==1'b1 || s_hls_valid &&
               (!active || data_done || remaining==0 && !m_valid || !input_shape))begin fault<=1;fault_code<=8'hb3;end
            if(s_status_valid!==1'b0 && s_status_valid!==1'b1 || s_status_valid &&
               (!active || !issued || status_seen || !status_match || !data_done && s_status_error==0))begin fault<=1;fault_code<=8'hb4;end
            if(s_hls_done_valid!==1'b0 && s_hls_done_valid!==1'b1 || s_hls_done_valid &&
               (!active || !hls_owner_sent || hls_seen || !hls_match))begin fault<=1;fault_code<=8'hb6;end
            if(s_ack_done_valid!==1'b0 && s_ack_done_valid!==1'b1 || s_ack_done_valid &&
               (!active || !hls_seen || !ack_core_sent || ack_seen || !ack_match))begin fault<=1;fault_code<=8'hb7;end
        end
    end
end
endmodule
`resetall
