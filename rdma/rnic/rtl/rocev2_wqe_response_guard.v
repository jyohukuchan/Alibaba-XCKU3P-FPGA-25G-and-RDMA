// SPDX-License-Identifier: BSD-2-Clause-Views
// Full retained authorized WQE + TRUSTED issued PSN/peer context -> protected
// positive WRITE ACK / READ RESPONSE ONLY ingress. Whole-packet integrity,
// peer/IP/QPN/PSN/opcode/AETH/length must pass before ANY HLS beat or READ
// placement token is offered. Tokens preserve all588bits of original authority.
// One WR/one <=4096B response is a prototype, not full RC/retry/CQ support.
// Trusted expected PSN MUST come from actual issued-WR/connection ownership,
// never RX. A validated/forwarded response is NOT memory visibility/CQ/unpin.
`resetall
`timescale 1ns/1ps
`default_nettype none
module rocev2_wqe_response_guard #(
    parameter MAX_QPS=8,
    parameter CONTROL_ENABLE=0
)(
    input wire clk,
    input wire rst,
    input wire enable,
    input wire halt,
    input wire [587:0] s_expect_context,
    input wire [31:0] s_expect_local_ip,
    input wire [31:0] s_expect_peer_ip,
    input wire [23:0] s_expect_psn,
    input wire s_expect_valid,
    output wire s_expect_ready,
    input wire [127:0] s_axis_rx_tdata,
    input wire [15:0] s_axis_rx_tkeep,
    input wire s_axis_rx_tvalid,
    output wire s_axis_rx_tready,
    input wire s_axis_rx_tlast,
    input wire s_axis_rx_tuser,
    output wire [587:0] m_read_response_context,
    output wire m_read_response_valid,
    input wire m_read_response_ready,
    output reg [127:0] m_axis_hls_rx_tdata=0,
    output reg [15:0] m_axis_hls_rx_tkeep=0,
    output reg m_axis_hls_rx_tlast=0,
    output reg m_axis_hls_rx_tvalid=0,
    input wire m_axis_hls_rx_tready,
    output reg [587:0] m_response_event_context=0,
    output wire [23:0] m_response_event_psn,
    output reg [7:0] m_response_event_opcode=0,
    output reg [7:0] m_response_event_syndrome=0,
    output reg m_response_event_valid=0,
    input wire m_response_event_ready,
    output wire [587:0] m_control_context,
    output wire [23:0] m_control_psn,
    output wire [7:0] m_control_syndrome,
    output wire m_control_valid,
    input wire m_control_ready,
    input wire [MAX_QPS-1:0] downstream_queue_guard,
    output wire [MAX_QPS-1:0] queue_guard,
    output wire busy,
    output reg [7:0] m_reject_error=0,
    output reg m_reject_valid=0,
    input wire m_reject_ready,
    output reg fault=0,
    output reg [7:0] fault_code=0,
    output reg [31:0] accepted_count=0,
    output reg [31:0] rejected_count=0,
    output reg [31:0] integrity_drop_count=0,
    output reg [31:0] unowned_drop_count=0
);
localparam COLLECT=0,PARSE=1,TOKEN=2,FORWARD=3,EVENT=4,REJECT=5,CONTROL=6;
localparam FRAME_WORDS=260;
reg active=0,raw_pending=0,raw_in_frame=0,discard_in_frame=0;
reg [2:0] state=COLLECT;
reg [127:0] frame_data[0:FRAME_WORDS-1];
reg [15:0] frame_keep[0:FRAME_WORDS-1];
reg [8:0] words=0,forward_index=0;
reg [15:0] bytes_received=0;
reg frame_bad=0;
reg [383:0] header=0;
reg [31:0] local_ip=0,peer_ip=0;
reg [23:0] expected_psn=0;
reg downstream_lease=0;
wire [63:0] in_id,in_seq,in_epoch,in_va,in_offset,in_remote;
wire [23:0] in_qpn;
wire [15:0] in_pd,in_tag,in_op,in_flags;
wire [31:0] in_length,in_key,in_rkey;
wire [7:0] in_error,in_fetch;
wire [1:0] in_source;
wire in_available,in_authorized;
assign {in_id,in_seq,in_epoch,in_qpn,in_pd,in_tag,in_op,in_flags,in_length,in_key,in_va,
    in_offset,in_remote,in_rkey,in_error,in_source,in_fetch,in_available,in_authorized}=s_expect_context;
wire [63:0] wr_id,sequence_value,epoch,va,offset,remote_address;
wire [23:0] qpn;
wire [15:0] pd,tag,opcode,flags;
wire [31:0] length,key,remote_key;
wire [7:0] error,fetch_error;
wire [1:0] error_source;
wire available,authorized;
assign {wr_id,sequence_value,epoch,qpn,pd,tag,opcode,flags,length,key,va,offset,
    remote_address,remote_key,error,error_source,fetch_error,available,authorized}=m_response_event_context;
wire known=(^{s_expect_context,s_expect_local_ip,s_expect_peer_ip,s_expect_psn})!==1'bx;
wire [64:0] va_end={1'b0,in_va}+{33'd0,in_length};
wire [64:0] off_end={1'b0,in_offset}+{33'd0,in_length};
wire [64:0] remote_end={1'b0,in_remote}+{33'd0,in_length};
wire expect_ok=known && in_qpn<MAX_QPS && in_seq!=0 && in_epoch!=0 && in_tag!=0 &&
    in_available && in_authorized && in_error==0 && in_source==0 && in_fetch==0 &&
    (in_op==1 || in_op==2 || (in_op==3 && in_remote==0 && in_rkey==0)) && (in_flags&16'hfffe)==0 && in_length!=0 && in_length<=4096 &&
    (!va_end[64] || va_end==65'h10000000000000000) &&
    (!off_end[64] || off_end==65'h10000000000000000) &&
    (!remote_end[64] || remote_end==65'h10000000000000000);
wire bad_expect=!active && enable && ((s_expect_valid!==1'b0 && s_expect_valid!==1'b1) ||
    (s_expect_valid && !expect_ok));
assign s_expect_ready=!active && !raw_pending && !raw_in_frame && !discard_in_frame && !fault &&
    enable && !halt && !rst && expect_ok;
assign busy=active || raw_pending || raw_in_frame || discard_in_frame || fault;
assign queue_guard=(fault || bad_expect) ? {MAX_QPS{1'b1}} :
    active ? ({{(MAX_QPS-1){1'b0}},1'b1}<<qpn) :
    (s_expect_valid && expect_ok) ? ({{(MAX_QPS-1){1'b0}},1'b1}<<in_qpn) : {MAX_QPS{1'b0}};
wire downstream_held=qpn<MAX_QPS && downstream_queue_guard[qpn]===1'b1 && (^downstream_queue_guard)!==1'bx;
wire checker_ready,checked_valid,checked_ready,checked_last,rx_good,rx_bad,rx_overflow;
wire [127:0] checked_data;
wire [15:0] checked_keep;
// An unowned SOP may coincide with expectation capture; its remaining bytes
// MUST stay on the discard path, never become the new owner's packet.
wire admit_raw=raw_in_frame || (!discard_in_frame && active && state==COLLECT && !raw_pending && !fault);
wire discard_raw=discard_in_frame || (!active && !raw_in_frame && !raw_pending);
reg raw_bytes_known;
always @*begin
    raw_bytes_known=1;
    for(integer b=0;b<16;b=b+1)
        if(s_axis_rx_tkeep[b] && (^s_axis_rx_tdata[b*8+:8])===1'bx)raw_bytes_known=0;
end
wire raw_known=(^{s_axis_rx_tkeep,s_axis_rx_tlast,s_axis_rx_tuser})!==1'bx && raw_bytes_known;
assign s_axis_rx_tready=!rst && (admit_raw ? checker_ready && raw_known : discard_raw);
rocev2_ipv4_icrc #(.TX_MODE(0)) integrity (
    .clk(clk),.rst(rst),.s_axis_tdata(s_axis_rx_tdata),.s_axis_tkeep(s_axis_rx_tkeep),
    .s_axis_tvalid(s_axis_rx_tvalid && admit_raw && raw_known && !rst),.s_axis_tready(checker_ready),
    .s_axis_tlast(s_axis_rx_tlast),.s_axis_tuser(s_axis_rx_tuser),
    .m_axis_tdata(checked_data),.m_axis_tkeep(checked_keep),.m_axis_tvalid(checked_valid),
    .m_axis_tready(checked_ready),.m_axis_tlast(checked_last),
    .status_good_frame(rx_good),.status_bad_frame(rx_bad),.status_overflow(rx_overflow));
assign checked_ready=active && state==COLLECT && !fault && !rst;
function [15:0] be16;
    input [383:0] data;input integer pos;
    begin be16={data[pos*8+:8],data[(pos+1)*8+:8]};end
endfunction
function [31:0] be32;
    input [383:0] data;input integer pos;
    begin be32={data[pos*8+:8],data[(pos+1)*8+:8],data[(pos+2)*8+:8],data[(pos+3)*8+:8]};end
endfunction
wire [23:0] parsed_qpn={header[33*8+:8],header[34*8+:8],header[35*8+:8]};
wire [23:0] parsed_psn={header[37*8+:8],header[38*8+:8],header[39*8+:8]};
wire [7:0] parsed_opcode=header[28*8+:8];
wire [1:0] pad=header[29*8+4+:2];
wire [31:0] padded_length=(length+3)&32'hfffffffc;
wire header_known=(^header)!==1'bx;
wire format_ok=header_known && !frame_bad && bytes_received>=48 && header[0+:8]==8'h45 &&
    header[9*8+:8]==17 && be16(header,2)==bytes_received && be16(header,24)==bytes_received-20 &&
    (be16(header,6)&16'h3fff)==0 && be16(header,22)==4791 && be16(header,26)==0 &&
    (header[29*8+:8]&8'h8f)==0 && be16(header,30)==16'hffff &&
    (header[32*8+:8]&8'h3f)==0 && (header[36*8+:8]&8'h7f)==0;
wire peer_ok=parsed_qpn==qpn && be32(header,12)==peer_ip && be32(header,16)==local_ip;
wire control_syndrome=header[40*8+5+:3]==1 ||
    (header[40*8+5+:3]==3 && header[40*8+:5]<=4);
wire control_packet=CONTROL_ENABLE && parsed_opcode==8'h11 && !syndrome_ok && control_syndrome;
wire op_ok=control_packet || parsed_opcode==(opcode==2 ? 8'h10 : 8'h11);
// AETH high3bits classify ACK vs RNR/NAK; low5bits are credits, not errors.
wire syndrome_ok=(header[40*8+:8]&8'he0)==0;
wire size_ok=(opcode!=2 || control_packet) ? (bytes_received==48 && pad==0) :
    (bytes_received==48+padded_length && pad==((-length)&3));
assign m_read_response_context=m_response_event_context;
// An already-offered token cannot be retracted by a later fault. Guards and
// the full saved owner remain quarantined even if that offer is consumed.
assign m_read_response_valid=state==TOKEN;
assign m_response_event_psn=expected_psn;
assign m_control_context=m_response_event_context;
assign m_control_psn=expected_psn;
assign m_control_syndrome=m_response_event_syndrome;
assign m_control_valid=state==CONTROL;
wire token_transfer=m_read_response_valid && m_read_response_ready && downstream_held;
wire frame_transfer=m_axis_hls_rx_tvalid && m_axis_hls_rx_tready;
integer lane;
reg [4:0] count;
always @*begin count=0;for(integer j=0;j<16;j=j+1)count=count+checked_keep[j];end
initial if(MAX_QPS<1 || MAX_QPS>8)$fatal(1,"unreviewed response QP capacity");
always @(posedge clk)begin
    if(rst)begin
        active<=0;state<=COLLECT;raw_pending<=0;raw_in_frame<=0;discard_in_frame<=0;
        words<=0;forward_index<=0;bytes_received<=0;frame_bad<=0;header<=0;
        local_ip<=0;peer_ip<=0;expected_psn<=0;downstream_lease<=0;
        m_axis_hls_rx_tdata<=0;m_axis_hls_rx_tkeep<=0;m_axis_hls_rx_tlast<=0;m_axis_hls_rx_tvalid<=0;
        m_response_event_context<=0;m_response_event_opcode<=0;m_response_event_syndrome<=0;m_response_event_valid<=0;
        m_reject_error<=0;m_reject_valid<=0;fault<=0;fault_code<=0;
        accepted_count<=0;rejected_count<=0;integrity_drop_count<=0;unowned_drop_count<=0;
    end else begin
        if(s_expect_valid && s_expect_ready)begin
            active<=1;m_response_event_context<=s_expect_context;local_ip<=s_expect_local_ip;
            peer_ip<=s_expect_peer_ip;expected_psn<=s_expect_psn;state<=COLLECT;
            words<=0;header<=0;bytes_received<=0;frame_bad<=0;downstream_lease<=0;
        end
        if(s_axis_rx_tvalid && s_axis_rx_tready)begin
            if(admit_raw)begin raw_pending<=1;raw_in_frame<=!s_axis_rx_tlast;end
            else begin
                discard_in_frame<=!s_axis_rx_tlast;
                if(s_axis_rx_tlast)unowned_drop_count<=unowned_drop_count+1'b1;
            end
        end
        if(rx_bad || rx_overflow)begin
            raw_pending<=0;integrity_drop_count<=integrity_drop_count+1'b1;
        end
        if(checked_valid && checked_ready)begin
            if(words<FRAME_WORDS)begin frame_data[words]<=checked_data;frame_keep[words]<=checked_keep;end
            else frame_bad<=1;
            if(words<3)header[words*128+:128]<=checked_data;
            if(words<FRAME_WORDS)words<=words+1'b1;
            bytes_received<=bytes_received+count;
            if((^{checked_keep,checked_last})===1'bx || count==0 ||
               (!checked_last && checked_keep!=16'hffff))frame_bad<=1;
            for(lane=0;lane<16;lane=lane+1)
                if(checked_keep[lane] && (^checked_data[lane*8+:8])===1'bx)frame_bad<=1;
            if(checked_last)begin raw_pending<=0;state<=PARSE;end
        end
        if(state==PARSE && !fault)begin
            m_reject_error<=8'h91;state<=REJECT;
            if(!format_ok || !size_ok)m_reject_error<=8'h91;
            else if(!peer_ok)m_reject_error<=8'h92;
            else if(parsed_psn!=expected_psn)m_reject_error<=8'h93;
            else if(!op_ok)m_reject_error<=8'h94;
            else if(!syndrome_ok && !control_packet)m_reject_error<=8'h95;
            else begin
                m_response_event_opcode<=parsed_opcode;m_response_event_syndrome<=header[40*8+:8];
                accepted_count<=accepted_count+1'b1;forward_index<=0;
                state<=control_packet ? CONTROL : opcode==2 ? TOKEN : FORWARD;
            end
        end
        if(token_transfer)begin downstream_lease<=1;state<=FORWARD;end
        if(m_control_valid && m_control_ready && downstream_held)begin
            // Keep the SAME expectation and full WR lease for its retry.
            // No HLS beat, READ-placement token or positive completion event.
            downstream_lease<=1;state<=COLLECT;words<=0;header<=0;bytes_received<=0;frame_bad<=0;
        end
        // Registered replay avoids frame-RAM -> ready/permission feedback.
        // No beat can be seen before a READ placement token was accepted.
        if(state==FORWARD && !m_axis_hls_rx_tvalid && !fault && downstream_held)begin
            downstream_lease<=1;m_axis_hls_rx_tdata<=frame_data[forward_index];
            m_axis_hls_rx_tkeep<=frame_keep[forward_index];m_axis_hls_rx_tlast<=forward_index+1==words;
            m_axis_hls_rx_tvalid<=1;
        end
        if(frame_transfer)begin
            m_axis_hls_rx_tvalid<=0;
            if(m_axis_hls_rx_tlast)begin state<=EVENT;m_response_event_valid<=1;end
            else forward_index<=forward_index+1'b1;
        end
        if(m_response_event_valid && m_response_event_ready && downstream_held)begin
            m_response_event_valid<=0;
            if(!fault)begin active<=0;downstream_lease<=0;state<=COLLECT;words<=0;header<=0;bytes_received<=0;frame_bad<=0;end
        end
        if(state==REJECT && !fault)begin
            if(!m_reject_valid)begin m_reject_valid<=1;rejected_count<=rejected_count+1'b1;end
            else if(m_reject_ready)begin
                m_reject_valid<=0;state<=COLLECT;words<=0;bytes_received<=0;header<=0;frame_bad<=0;
            end
        end
        if(!fault)begin
            if(bad_expect)begin fault<=1;fault_code<=8'h96;end
            if((m_read_response_valid && m_read_response_ready && !downstream_held) ||
               (m_control_valid && m_control_ready && !downstream_held) ||
               (m_response_event_valid && m_response_event_ready && !downstream_held) ||
               (downstream_lease && !downstream_held))begin fault<=1;fault_code<=8'h97;end
            if((s_axis_rx_tvalid!==1'b0 && s_axis_rx_tvalid!==1'b1) ||
               (active && !discard_in_frame && s_axis_rx_tvalid && !raw_known))begin fault<=1;fault_code<=8'h98;end
        end
    end
end
endmodule
`resetall
