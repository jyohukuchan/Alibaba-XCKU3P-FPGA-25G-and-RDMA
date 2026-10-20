// SPDX-License-Identifier: BSD-2-Clause-Views
// Bind the SAME trusted receive operation receipt to its actual positive ACK
// frame, fresh MAC tag, real SFD receipt, actual EOF and conservative wire tail.
// The existing HLS/integrity/framer remains the packet producer. This is NOT
// a replacement CRC engine or a whole-core/requester drain certificate.
`resetall
`timescale 1ns/1ps
`default_nettype none
module rocev2_receive_ack_tx #(
    parameter TAG_SEQUENCE_WIDTH=13,
    parameter IMMEDIATE_ENABLE=0
)(
    input wire clk,input wire rst,input wire parent_fault,
    input wire prior_response_drained,
    input wire [587+32*IMMEDIATE_ENABLE:0] s_owner_context,input wire s_owner_valid,output wire s_owner_ready,
    input wire [47:0] local_mac,input wire [47:0] peer_mac,
    input wire [31:0] local_ip,input wire [31:0] peer_ip,input wire [23:0] peer_qpn,
    input wire [679+72*IMMEDIATE_ENABLE:0] s_core_data,input wire s_core_valid,
    input wire [127:0] s_axis_tdata,input wire [15:0] s_axis_tkeep,
    input wire s_axis_tvalid,output wire s_axis_tready,input wire s_axis_tlast,input wire [16:0] s_axis_tuser,
    output wire [127:0] m_axis_tdata,output wire [15:0] m_axis_tkeep,
    output wire m_axis_tvalid,input wire m_axis_tready,output wire m_axis_tlast,output wire [16:0] m_axis_tuser,
    input wire [15:0] s_cpl_tag,input wire [95:0] s_cpl_ts,input wire s_cpl_valid,output wire s_cpl_ready,
    output wire [15:0] m_cpl_tag,output wire [95:0] m_cpl_ts,output wire m_cpl_valid,input wire m_cpl_ready,
    output wire [695+72*IMMEDIATE_ENABLE:0] m_done_data,output wire m_done_valid,input wire m_done_ready,
    input wire [587+32*IMMEDIATE_ENABLE:0] s_retire_context,input wire s_retire_valid,output wire s_retire_ready,
    output wire [7:0] queue_guard,output wire busy,
    output reg fault=0,output reg [7:0] fault_code=0,
    output reg [15:0] active_tag=0,output wire tags_exhausted,
    output reg [31:0] frame_count=0,output reg [31:0] receipt_count=0
);
initial if(TAG_SEQUENCE_WIDTH<1 || TAG_SEQUENCE_WIDTH>13)$fatal(1,"unreviewed receive ACK tag geometry");
initial if(IMMEDIATE_ENABLE!=0 && IMMEDIATE_ENABLE!=1)$fatal(1,"Immediate receive ACK profile must be static0or1");
localparam OWNER_WIDTH=588+32*IMMEDIATE_ENABLE,CORE_WIDTH=680+72*IMMEDIATE_ENABLE;
localparam WAIT_ACK=0,CAPTURE=1,CHECK=2,SEND=3,WAIT_RECEIPT=4,DONE=5;
reg [2:0] state=WAIT_ACK;
reg held=0,pass_frame=0,first_sent=0,eof_sent=0,receipt_seen=0,proof_sent=0,tail_started=0;
reg [OWNER_WIDTH-1:0] owner=0;
reg [CORE_WIDTH-1:0] proof=0;
reg [511:0] packet=0;
reg [1:0] capture_index=0,send_index=0;
reg [9:0] tail_count=0;
reg [TAG_SEQUENCE_WIDTH:0] tag_sequence=0;
reg [47:0] saved_local_mac=0,saved_peer_mac=0;
reg [31:0] saved_local_ip=0,saved_peer_ip=0;
reg [23:0] saved_peer_qpn=0;
wire halted=fault || parent_fault!==1'b0;
wire owner_ok=(^{s_owner_context,local_mac,peer_mac,local_ip,peer_ip,peer_qpn})!==1'bx &&
    s_owner_context[395:372]<8 && s_owner_context[339:324]==4 && s_owner_context[323:308]==1 &&
    s_owner_context[459:396]!=0 && s_owner_context[523:460]!=0 && s_owner_context[355:340]!=0 &&
    s_owner_context[307:276]!=0 && s_owner_context[307:276]<=4096 &&
    s_owner_context[115:20]==0 && s_owner_context[19:0]==3 && (s_owner_context>>588)==0;
assign tags_exhausted=tag_sequence>={1'b0,{TAG_SEQUENCE_WIDTH{1'b1}}};
assign s_owner_ready=!held && !pass_frame && !s_axis_tvalid && prior_response_drained===1'b1 &&
    !tags_exhausted && !halted && !rst;
wire capture=!pass_frame && held && (state==CAPTURE || state==WAIT_ACK && s_axis_tuser[16:1]==16'h4000);
wire forward=!capture && state!=SEND && (!held || state==WAIT_ACK || pass_frame);
assign s_axis_tready=capture ? !halted && !rst : forward && m_axis_tready && !rst;
assign m_axis_tvalid=state==SEND ? !rst : forward && s_axis_tvalid && !rst;
assign m_axis_tdata=state==SEND ? packet[send_index*128+:128] : s_axis_tdata;
assign m_axis_tkeep=state==SEND ? (send_index==3 ? 16'h3fff:16'hffff) : s_axis_tkeep;
assign m_axis_tlast=state==SEND ? send_index==3 : s_axis_tlast;
assign m_axis_tuser=state==SEND ? {active_tag,1'b0} : s_axis_tuser;
wire send_fire=state==SEND && m_axis_tvalid && m_axis_tready;
wire private_cpl=s_cpl_tag[15:13]==3'b011;
wire cpl_match=held && state>=SEND && s_cpl_tag===active_tag && !receipt_seen &&
    (first_sent || send_fire) && !halted;
// Translate only the exact live fresh tag to the original response guard.
// Unknown/stale/duplicate private tags are quarantined, never forwarded.
assign m_cpl_tag=private_cpl ? 16'h4000:s_cpl_tag;
assign m_cpl_ts=s_cpl_ts;
assign m_cpl_valid=s_cpl_valid && (!private_cpl || cpl_match) && !rst;
assign s_cpl_ready=private_cpl && !cpl_match ? !rst : m_cpl_ready && !rst;
assign m_done_data={active_tag,proof};
assign m_done_valid=held && state==DONE && !proof_sent && !halted && !rst;
assign s_retire_ready=held && state==DONE && proof_sent && s_retire_context===owner && !halted && !rst;
assign busy=held || pass_frame || fault;
assign queue_guard=halted ? 8'hff : held ? (8'h01<<owner[395:372]) :
    s_owner_valid && owner_ok ? (8'h01<<s_owner_context[395:372]) : 0;
function [7:0] octet;
    input [511:0] data;
    input integer n;
    begin octet=data[n*8+:8];end
endfunction
function [23:0] be24;
    input [511:0] data;
    input integer n;
    begin be24={octet(data,n),octet(data,n+1),octet(data,n+2)};end
endfunction
function [31:0] be32;
    input [511:0] data;
    input integer n;
    begin be32={octet(data,n),octet(data,n+1),octet(data,n+2),octet(data,n+3)};end
endfunction
wire header_ok={octet(packet,0),octet(packet,1),octet(packet,2),octet(packet,3),octet(packet,4),octet(packet,5)}==saved_peer_mac &&
    {octet(packet,6),octet(packet,7),octet(packet,8),octet(packet,9),octet(packet,10),octet(packet,11)}==saved_local_mac &&
    {octet(packet,12),octet(packet,13),octet(packet,14),octet(packet,16),octet(packet,17),octet(packet,23)}==48'h080045003011 &&
    be32(packet,26)==saved_local_ip && be32(packet,30)==saved_peer_ip &&
    {octet(packet,34),octet(packet,35),octet(packet,36),octet(packet,37),octet(packet,38),octet(packet,39)}==48'h12b712b7001c &&
    {octet(packet,40),octet(packet,41),octet(packet,42),octet(packet,43),octet(packet,44),octet(packet,45),octet(packet,46)}==56'h00001140ffff00 &&
    be24(packet,47)==saved_peer_qpn && octet(packet,50)==0 && octet(packet,54)==0 &&
    be24(packet,51)==s_core_data[OWNER_WIDTH+55:OWNER_WIDTH+32] &&
    be24(packet,55)==s_core_data[OWNER_WIDTH+83:OWNER_WIDTH+60];
wire [31:0] core_notification=s_core_data>>(OWNER_WIDTH+84);
wire [7:0] core_notification_flags=s_core_data>>(OWNER_WIDTH+116);
wire notification_ok=!IMMEDIATE_ENABLE ||
    ((core_notification_flags==0 || core_notification_flags==1 || core_notification_flags==3) &&
     (core_notification_flags!=0 || core_notification==0));
wire write_notification=IMMEDIATE_ENABLE && core_notification_flags==3;
wire core_ok=(^s_core_data)!==1'bx && s_core_data[OWNER_WIDTH-1:0]==owner &&
    s_core_data[CORE_WIDTH-1:CORE_WIDTH-8]==0 && s_core_data[OWNER_WIDTH+59:OWNER_WIDTH+56]==0 && notification_ok &&
    s_core_data[OWNER_WIDTH+31:OWNER_WIDTH]!=0 && s_core_data[OWNER_WIDTH+31:OWNER_WIDTH]<=4096 &&
    (write_notification || s_core_data[OWNER_WIDTH+31:OWNER_WIDTH]<=owner[307:276]);
always @(posedge clk)begin
    if(rst)begin
        held<=0;pass_frame<=0;state<=WAIT_ACK;owner<=0;proof<=0;packet<=0;
        first_sent<=0;eof_sent<=0;receipt_seen<=0;proof_sent<=0;tail_started<=0;tail_count<=0;
        capture_index<=0;send_index<=0;tag_sequence<=0;active_tag<=0;
        saved_local_mac<=0;saved_peer_mac<=0;saved_local_ip<=0;saved_peer_ip<=0;saved_peer_qpn<=0;
        fault<=0;fault_code<=0;frame_count<=0;receipt_count<=0;
    end else begin
        if(parent_fault!==1'b0)begin fault<=1;fault_code<=8'hd1;end
        if(s_owner_valid && s_owner_ready)begin
            if(!owner_ok)begin fault<=1;fault_code<=8'hd2;end
            else begin
                held<=1;owner<=s_owner_context;state<=WAIT_ACK;packet<=0;
                active_tag<=16'h6000|({{(16-TAG_SEQUENCE_WIDTH){1'b0}},tag_sequence[TAG_SEQUENCE_WIDTH-1:0]}+16'd1);
                tag_sequence<=tag_sequence+1'b1;
                first_sent<=0;eof_sent<=0;receipt_seen<=0;proof_sent<=0;tail_started<=0;tail_count<=0;
                capture_index<=0;send_index<=0;
                saved_local_mac<=local_mac;saved_peer_mac<=peer_mac;saved_local_ip<=local_ip;saved_peer_ip<=peer_ip;saved_peer_qpn<=peer_qpn;
            end
        end
        if(forward && s_axis_tvalid && s_axis_tready)pass_frame<=!s_axis_tlast;
        if(capture && s_axis_tvalid && s_axis_tready)begin
            if((^{s_axis_tdata,s_axis_tkeep,s_axis_tlast,s_axis_tuser})===1'bx ||
               s_axis_tuser!=={16'h4000,1'b0} ||
               s_axis_tkeep!==(capture_index==3 ? 16'h3fff:16'hffff) ||
               s_axis_tlast!==(capture_index==3))begin fault<=1;fault_code<=8'hd3;end
            packet[capture_index*128+:128]<=s_axis_tdata;
            capture_index<=capture_index+1'b1;state<=capture_index==3 ? CHECK:CAPTURE;
        end
        if(state==CHECK && s_core_valid && !halted)begin
            if(!core_ok || !header_ok)begin fault<=1;fault_code<=8'hd4;end
            else begin proof<=s_core_data;state<=SEND;send_index<=0;end
        end
        if(send_fire)begin
            first_sent<=1;send_index<=send_index+1'b1;
            if(m_axis_tlast)begin eof_sent<=1;frame_count<=frame_count+1'b1;state<=WAIT_RECEIPT;end
        end
        if(s_cpl_valid && s_cpl_ready && private_cpl)begin
            if(!cpl_match)begin fault<=1;fault_code<=8'hd5;end
            else begin receipt_seen<=1;receipt_count<=receipt_count+1'b1;end
        end
        if(held && eof_sent && receipt_seen && !tail_started && !halted)begin
            tail_started<=1;tail_count<=1023;
        end else if(tail_started && tail_count!=0)begin
            tail_count<=tail_count-1'b1;if(tail_count==1)state<=DONE;
        end
        if(m_done_valid && m_done_ready)proof_sent<=1;
        if(s_retire_valid && s_retire_ready)begin held<=0;owner<=0;state<=WAIT_ACK;end
    end
end
endmodule
`resetall
