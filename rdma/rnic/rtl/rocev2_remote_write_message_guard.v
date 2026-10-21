// SPDX-License-Identifier: BSD-2-Clause-Views
// Segmented incoming WRITE ownership. Integrity-checked packet metadata and
// privileged QP context enter here; raw RETH alone is never authorization.
// A REAL remote-write MR lookup covers the WHOLE message and every packet.
// The final WRITE Immediate binds a separate genuine posted RQ. Execution
// certificates MUST come from the real backend/HLS/MAC join, not this block.
// This leaf is not yet connected to the qualified native endpoint.
`resetall
`timescale 1ns/1ps
`default_nettype none
module rocev2_remote_write_message_guard #(
    parameter MAX_QPS=8,parameter [63:0] INITIAL_MESSAGE_COOKIE=0
)(
    input wire clk,input wire rst,input wire enable,input wire parent_fault,
    input wire trusted_valid,input wire [23:0] trusted_qpn,
    input wire [15:0] trusted_pd,input wire [63:0] trusted_epoch,
    input wire [23:0] trusted_expected_psn,
    input wire [7:0] s_packet_opcode,input wire [23:0] s_packet_qpn,s_packet_psn,
    input wire [31:0] s_packet_length,s_packet_wire_length,input wire [1:0] s_packet_pad,
    input wire s_packet_reth_valid,input wire [63:0] s_packet_reth_va,
    input wire [31:0] s_packet_reth_key,s_packet_reth_length,
    input wire [15:0] s_packet_tag,input wire s_packet_valid,output wire s_packet_ready,
    output wire [15:0] m_mr_pd,output wire [31:0] m_mr_key,
    output wire [63:0] m_mr_address,output wire [31:0] m_mr_length,
    output wire [2:0] m_mr_operation,output wire [15:0] m_mr_tag,
    output wire m_mr_valid,input wire m_mr_ready,
    input wire [15:0] s_mr_tag,input wire [7:0] s_mr_error,
    input wire [63:0] s_mr_offset,s_mr_address,input wire [31:0] s_mr_length,
    input wire s_mr_valid,output wire s_mr_ready,
    input wire [619:0] s_rq_context,input wire s_rq_valid,
    output wire [319:0] m_notice_context,output wire [23:0] m_notice_last_psn,
    output wire m_notice_valid,input wire m_notice_ready,
    // {message320,byte_offset32,payload_length32,PSN24,transaction_tag16}.
    output wire [423:0] m_packet_token,output wire [63:0] m_packet_address,
    output wire [63:0] m_packet_mr_offset,m_packet_mr_address,
    output wire [31:0] m_packet_key,m_packet_wire_length,
    output wire m_packet_last,m_packet_notify,output wire [619:0] m_packet_rq_context,
    output wire m_packet_valid,input wire m_packet_ready,
    input wire [423:0] s_done_token,input wire [23:0] s_done_msn,
    // Bits0..3: real data EOF, ordered backend visibility fence, HLS/ACK
    // state readback, actual ACK-MAC/tail. This block invents NONE of them.
    input wire [7:0] s_done_proofs,input wire s_done_valid,output wire s_done_ready,
    input wire [319:0] s_notice_retire_context,input wire s_notice_retire_valid,
    output wire s_notice_retire_ready,
    // Privileged STOP may abandon a partially written message only between
    // fully certified packets and with real parent RX/backend/HLS/MAC drain.
    input wire [319:0] s_cancel_context,input wire s_cancel_valid,
    input wire cancel_drained,output wire s_cancel_ready,
    output reg [7:0] m_reject_error=0,output reg [23:0] m_reject_qpn=0,m_reject_psn=0,
    output reg [23:0] m_reject_msn=0,output reg m_reject_keep_message=0,
    output wire m_reject_valid,input wire m_reject_ready,
    output wire [319:0] message_context,output wire configuration_guard,
    output wire [7:0] queue_guard,output reg message_active=0,
    output reg [31:0] accepted_packets=0,completed_packets=0,completed_messages=0,cancelled_messages=0,
    output reg fault=0,output reg [7:0] fault_code=0
);
initial if(MAX_QPS!=8)$fatal(1,"original8QP geometry required");
localparam IDLE=0,WHOLE_Q=1,WHOLE_R=2,PACKET_Q=3,PACKET_R=4,
    NOTICE=5,OFFER=6,WAIT_DONE=7,WAIT_PACKET=8,WAIT_RETIRE=9,REJECT=10;
reg [3:0] state=IDLE;
reg [63:0] cookie=INITIAL_MESSAGE_COOKIE;
reg [319:0] remote_context=0;
reg [31:0] offset=0,packet_offset=0,packet_length=0,packet_wire_length=0;
reg [23:0] packet_psn=0,next_psn=0,base_msn=0;
reg [15:0] packet_tag=0,last_granted_tag=0;
reg packet_last=0,packet_notify=0,base_msn_valid=0;
reg [63:0] whole_mr_offset=0,whole_mr_address=0,packet_mr_offset=0,packet_mr_address=0;
reg [619:0] rq_context=0;
wire halted=fault || parent_fault!==1'b0;
wire accepting=state==IDLE || state==WAIT_PACKET;
wire trusted_known=(^{trusted_qpn,trusted_pd,trusted_epoch,trusted_expected_psn})!==1'bx;
wire trusted_ok=trusted_valid===1'b1 && trusted_known && trusted_qpn<8 && trusted_pd!=0 && trusted_epoch!=0;
wire owns_context=message_active || state==WHOLE_Q || state==WHOLE_R;
wire context_stable=!owns_context || trusted_valid===1'b1 && trusted_known &&
    trusted_qpn===remote_context[319:296] && trusted_pd===remote_context[295:280] && trusted_epoch===remote_context[279:216];
wire offered=accepting && enable===1'b1 && trusted_valid===1'b1 && s_packet_valid===1'b1;
assign s_packet_ready=accepting && enable===1'b1 && trusted_ok && context_stable && !halted && !rst;
wire first=s_packet_opcode==8'h06;
wire last=s_packet_opcode==8'h08 || s_packet_opcode==8'h09;
wire notify=s_packet_opcode==8'h09;
wire packet_known=(^{s_packet_opcode,s_packet_qpn,s_packet_psn,s_packet_length,s_packet_wire_length,
    s_packet_pad,s_packet_reth_valid,s_packet_tag})!==1'bx;
wire reth_known=(^{s_packet_reth_va,s_packet_reth_key,s_packet_reth_length})!==1'bx;
wire [64:0] input_reth_end={1'b0,s_packet_reth_va}+{33'd0,s_packet_reth_length};
wire [32:0] input_end={1'b0,offset}+{1'b0,s_packet_length};
wire [31:0] padded=(s_packet_length+3)&32'hfffffffc;
wire opcode_ok=first || s_packet_opcode==8'h07 || last;
wire shape_ok=packet_known && opcode_ok && s_packet_reth_valid==first &&
    s_packet_length!=0 && s_packet_length<=4096 && s_packet_wire_length==padded &&
    s_packet_pad==((32'd0-s_packet_length)&3) &&
    (last || s_packet_length==4096 && s_packet_pad==0);
wire sequence_ok=first ? !message_active && reth_known && s_packet_reth_key!=0 &&
    s_packet_reth_length>4096 && s_packet_reth_length<=1048576 &&
    input_reth_end<=65'h10000000000000000 :
    message_active && context_stable && s_packet_psn==next_psn &&
    input_end<={1'b0,remote_context[55:24]} && (last ? input_end=={1'b0,remote_context[55:24]}:input_end<{1'b0,remote_context[55:24]});
assign message_context=remote_context;
assign configuration_guard=message_active || state!=IDLE || offered || halted;
assign queue_guard=halted ? 8'hff:configuration_guard ?
    (8'h01<<(message_active || state!=IDLE ? remote_context[319:296]:trusted_qpn)):8'd0;
// Two serial authorization checks share this packet's tag. There is only
// ONE outstanding lookup and only ONE eventual physical command per packet;
// phase/length/tag/offset bind each response. No MR response is reused as a
// backend status or as authorization for a different physical nonce.
assign m_mr_pd=remote_context[295:280];assign m_mr_key=remote_context[151:120];
assign m_mr_address=remote_context[119:56]+(state==WHOLE_Q ? 64'd0:{32'd0,packet_offset});
assign m_mr_length=state==WHOLE_Q ? remote_context[55:24]:packet_length;
assign m_mr_operation=3;assign m_mr_tag=packet_tag;
assign m_mr_valid=(state==WHOLE_Q || state==PACKET_Q) && !halted && !rst;
assign s_mr_ready=(state==WHOLE_R || state==PACKET_R) && !halted && !rst;
wire mr_known=(^{s_mr_tag,s_mr_error,s_mr_offset,s_mr_address,s_mr_length})!==1'bx;
wire [64:0] expected_offset={1'b0,whole_mr_offset}+{33'd0,packet_offset};
wire [64:0] expected_address={1'b0,whole_mr_address}+{33'd0,packet_offset};
wire rq_known=(^s_rq_context)!==1'bx;
wire [31:0] rq_capacity=s_rq_context[307:276];
wire [64:0] rq_va_end={1'b0,s_rq_context[243:180]}+{33'd0,rq_capacity};
wire [64:0] rq_offset_end={1'b0,s_rq_context[179:116]}+{33'd0,rq_capacity};
wire rq_match=rq_known && s_rq_context[395:372]===remote_context[319:296] &&
    s_rq_context[371:356]===remote_context[295:280] && s_rq_context[459:396]===remote_context[279:216] &&
    s_rq_context[523:460]!=0 && s_rq_context[355:340]!=0 && s_rq_context[339:324]==4 &&
    s_rq_context[323:308]==1 && s_rq_context[19:0]==20'd3 && s_rq_context[619:588]==0 &&
    s_rq_context[115:20]==0 && rq_capacity<=1048576 &&
    (rq_capacity==0 ? s_rq_context[275:116]==0:s_rq_context[275:244]!=0 &&
     rq_va_end<=65'h10000000000000000 && rq_offset_end<=65'h10000000000000000);
assign m_notice_context=remote_context;assign m_notice_last_psn=packet_psn;
assign m_notice_valid=state==NOTICE && s_rq_valid===1'b1 && rq_match && !halted && !rst;
assign m_packet_token={remote_context,packet_offset,packet_length,packet_psn,packet_tag};
assign m_packet_address=remote_context[119:56]+{32'd0,packet_offset};
assign m_packet_mr_offset=packet_mr_offset;assign m_packet_mr_address=packet_mr_address;
assign m_packet_key=remote_context[151:120];assign m_packet_wire_length=packet_wire_length;
assign m_packet_last=packet_last;assign m_packet_notify=packet_notify;
assign m_packet_rq_context=packet_notify ? rq_context:620'd0;
assign m_packet_valid=state==OFFER && !halted && !rst;
wire done_match=(^{s_done_token,s_done_msn,s_done_proofs})!==1'bx &&
    s_done_token===m_packet_token && s_done_proofs==8'h0f &&
    (!base_msn_valid || s_done_msn==(base_msn+(packet_last ? 24'd1:24'd0)));
assign s_done_ready=state==WAIT_DONE && done_match && !halted && !rst;
assign s_notice_retire_ready=state==WAIT_RETIRE && s_notice_retire_context===remote_context && !halted && !rst;
assign s_cancel_ready=state==WAIT_PACKET && message_active && s_cancel_context===remote_context &&
    cancel_drained===1'b1 && s_packet_valid===1'b0 && !halted && !rst;
assign m_reject_valid=state==REJECT && !halted && !rst;
always @(posedge clk)begin
    if(rst)begin
        state<=IDLE;cookie<=INITIAL_MESSAGE_COOKIE;remote_context<=0;offset<=0;packet_offset<=0;
        packet_length<=0;packet_wire_length<=0;packet_psn<=0;next_psn<=0;base_msn<=0;
        packet_tag<=0;last_granted_tag<=0;packet_last<=0;packet_notify<=0;base_msn_valid<=0;
        whole_mr_offset<=0;whole_mr_address<=0;packet_mr_offset<=0;packet_mr_address<=0;rq_context<=0;
        message_active<=0;fault<=0;fault_code<=0;m_reject_error<=0;m_reject_qpn<=0;m_reject_psn<=0;
        m_reject_msn<=0;m_reject_keep_message<=0;
        accepted_packets<=0;completed_packets<=0;completed_messages<=0;cancelled_messages<=0;
    end else begin
        if(parent_fault!==1'b0 || !context_stable || offered && !trusted_ok ||
           accepting && enable===1'b1 && s_packet_valid!==1'b0 && s_packet_valid!==1'b1)begin
            fault<=1;fault_code<=8'he1;
        end
        if(s_done_valid && (state!=WAIT_DONE || !done_match))begin fault<=1;fault_code<=8'he2;end
        if(s_mr_valid && (state!=WHOLE_R && state!=PACKET_R))begin fault<=1;fault_code<=8'he3;end
        if(s_notice_retire_valid && (!message_active || !packet_notify || s_notice_retire_context!==remote_context))begin fault<=1;fault_code<=8'he4;end
        if(s_cancel_valid && (!message_active || s_cancel_context!==remote_context))begin fault<=1;fault_code<=8'he5;end
        if(!halted)case(state)
            IDLE,WAIT_PACKET:begin
                if(s_cancel_valid && s_cancel_ready)begin
                    message_active<=0;state<=IDLE;cancelled_messages<=cancelled_messages+1'b1;
                end else if(s_packet_valid && s_packet_ready)begin
                    m_reject_qpn<=trusted_qpn;m_reject_psn<=s_packet_psn;
                    m_reject_msn<=base_msn;m_reject_keep_message<=message_active;
                    if(!shape_ok || !sequence_ok)begin m_reject_error<=16;state<=REJECT;end
                    else if(s_packet_qpn!=trusted_qpn)begin m_reject_error<=17;state<=REJECT;end
                    else if(s_packet_psn!=trusted_expected_psn)begin m_reject_error<=18;state<=REJECT;end
                    else if(s_packet_tag==0 || s_packet_tag<=last_granted_tag || first && cookie==64'hffffffffffffffff)begin m_reject_error<=36;state<=REJECT;end
                    else begin
                        packet_tag<=s_packet_tag;packet_psn<=s_packet_psn;packet_length<=s_packet_length;
                        packet_wire_length<=s_packet_wire_length;packet_last<=last;packet_notify<=notify;rq_context<=0;
                        packet_offset<=first ? 0:offset;
                        if(first)begin
                            cookie<=cookie+1'b1;remote_context<={trusted_qpn,trusted_pd,trusted_epoch,cookie+1'b1,
                                s_packet_reth_key,s_packet_reth_va,s_packet_reth_length,s_packet_psn};
                            base_msn_valid<=0;offset<=0;state<=WHOLE_Q;
                        end else state<=PACKET_Q;
                    end
                end
            end
            WHOLE_Q:if(m_mr_valid && m_mr_ready)state<=WHOLE_R;
            WHOLE_R:if(s_mr_valid && s_mr_ready)begin
                if(!mr_known || s_mr_tag!=packet_tag || s_mr_error>10 ||
                   s_mr_error!=0 && (s_mr_offset!=0 || s_mr_address!=0 || s_mr_length!=0) ||
                   s_mr_error==0 && s_mr_length!=remote_context[55:24])begin fault<=1;fault_code<=8'he6;end
                else if(s_mr_error!=0)begin
                    m_reject_error<=s_mr_error;m_reject_keep_message<=0;state<=REJECT;
                end else begin
                    whole_mr_offset<=s_mr_offset;whole_mr_address<=s_mr_address;message_active<=1;state<=PACKET_Q;
                end
            end
            PACKET_Q:if(m_mr_valid && m_mr_ready)state<=PACKET_R;
            PACKET_R:if(s_mr_valid && s_mr_ready)begin
                if(!mr_known || s_mr_tag!=packet_tag || s_mr_error!=0 || s_mr_length!=packet_length ||
                   expected_offset[64] || expected_address[64] || s_mr_offset!=expected_offset[63:0] ||
                   s_mr_address!=expected_address[63:0])begin fault<=1;fault_code<=8'he7;end
                else begin
                    packet_mr_offset<=s_mr_offset;packet_mr_address<=s_mr_address;
                    state<=packet_notify ? NOTICE:OFFER;
                end
            end
            NOTICE:begin
                if(s_rq_valid===1'b0)begin
                    m_reject_error<=38;m_reject_keep_message<=1;m_reject_msn<=base_msn;state<=REJECT;
                end else if(s_rq_valid!==1'b1 || !rq_match)begin fault<=1;fault_code<=8'he8;end
                else if(m_notice_valid && m_notice_ready)begin rq_context<=s_rq_context;state<=OFFER;end
            end
            OFFER:if(m_packet_valid && m_packet_ready)begin
                last_granted_tag<=packet_tag;accepted_packets<=accepted_packets+1'b1;state<=WAIT_DONE;
            end
            WAIT_DONE:if(s_done_valid && s_done_ready)begin
                completed_packets<=completed_packets+1'b1;offset<=packet_offset+packet_length;next_psn<=packet_psn+1'b1;
                if(!base_msn_valid)begin base_msn<=s_done_msn;base_msn_valid<=1;end
                if(packet_last)begin
                    if(packet_notify)state<=WAIT_RETIRE;
                    else begin message_active<=0;completed_messages<=completed_messages+1'b1;state<=IDLE;end
                end else state<=WAIT_PACKET;
            end
            WAIT_RETIRE:if(s_notice_retire_valid && s_notice_retire_ready)begin
                message_active<=0;completed_messages<=completed_messages+1'b1;state<=IDLE;
            end
            REJECT:if(m_reject_valid && m_reject_ready)state<=message_active ? WAIT_PACKET:IDLE;
            default:begin fault<=1;fault_code<=8'he9;end
        endcase
    end
end
endmodule
`resetall
