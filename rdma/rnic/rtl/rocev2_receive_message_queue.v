// SPDX-License-Identifier: BSD-2-Clause-Views
// Separate segmented receive cohort. One genuine posted owner is retained
// across packets and through exact whole-message CQ commit/retire. Packet
// DMA/core/ACK-MAC retirement is NOT permission to pop or unpin the RQ.
// Producers must be the same protected MR/backend/HLS/MAC, never raw wire
// addresses or fabricated status. Old/default receive_queue is untouched.
`resetall
`timescale 1ns/1ps
`default_nettype none
module rocev2_receive_message_queue #(
    parameter MAX_QPS=8,parameter DEPTH=8,
    parameter RECV_RETIRE_ENABLE=1,parameter RECV_CQ_ENABLE=1,
    parameter RECV_CANCEL_ENABLE=1,parameter IMMEDIATE_ENABLE=1
)(
    input wire clk,input wire rst,input wire parent_fault,
    input wire cancel_block,input wire cancel_valid,input wire cancel_safe,
    input wire [23:0] cancel_qpn,input wire [15:0] cancel_pd,input wire [63:0] cancel_epoch,
    output wire cancel_ready,output reg [31:0] cancelled_count=0,
    input wire [619:0] s_post_context,input wire s_post_valid,output wire s_post_ready,
    input wire [23:0] query_qpn,output wire [619:0] m_head_context,
    output wire m_head_valid,input wire m_head_ready,
    input wire [619:0] s_placement_context,input wire [31:0] s_placement_length,
    input wire [31:0] s_placement_notification,input wire [7:0] s_placement_notification_flags,
    input wire s_placement_valid,output wire s_placement_ready,input wire [23:0] s_placement_psn,
    input wire [751:0] s_core_data,input wire s_core_valid,output wire s_core_ready,
    output reg core_proved=0,output reg [31:0] core_proof_count=0,output reg [23:0] core_msn=0,
    output wire [619:0] held_context,output reg [751:0] held_core_data=0,
    input wire [767:0] s_mac_data,input wire s_mac_valid,output wire s_mac_ready,
    input wire memory_drained,
    // Fresh actual ACK MAC/tail + actual backend visibility + real HLS
    // packet proof permit releasing ONLY packet ACK/bridge slots.
    output wire [619:0] m_packet_retire_context,
    output wire m_packet_retire_valid,input wire m_packet_retire_ready,
    // New HLS whole-message execution output, compact772 / AXIS776 bits.
    input wire [775:0] s_message_data,input wire s_message_valid,output wire s_message_ready,
    output wire [619:0] m_ticket_context,output wire [31:0] m_ticket_received_bytes,
    output wire [31:0] m_ticket_notification,output wire [7:0] m_ticket_notification_flags,
    output wire m_ticket_valid,input wire m_ticket_ready,
    input wire [619:0] s_commit_context,input wire s_commit_valid,output wire s_commit_ready,
    input wire [619:0] s_retire_context,input wire s_retire_valid,output wire s_retire_ready,
    output wire [MAX_QPS-1:0] queue_guard,output wire active,
    output reg fault=0,output reg [7:0] fault_code=0,
    output reg [31:0] posted_count=0,output reg [31:0] taken_count=0,
    output reg [31:0] placement_count=0,output reg [31:0] received_bytes=0,
    output reg [31:0] packet_retired_count=0
);
initial if(MAX_QPS!=8 || DEPTH!=8 || !RECV_RETIRE_ENABLE || !RECV_CQ_ENABLE ||
    !RECV_CANCEL_ENABLE || !IMMEDIATE_ENABLE)$fatal(1,"complete8QP/8entry message-RQ cohort required");
reg [619:0] owners[0:63];reg [3:0] count[0:7];reg [2:0] head[0:7],tail[0:7];
reg held=0,armed=0,placed=0,mac_proved=0,packet_done=0;
reg packet_prepared=0,ticket_prepared=0;
reg group_active=0,message_proved=0,ticket_sent=0,committed=0;
reg [619:0] owner=0;reg [31:0] packet_length=0,notification=0,message_notification=0;
reg [7:0] packet_flags=0,message_flags=0;reg [23:0] packet_psn=0,first_psn=0,next_psn=0,base_msn=0;
wire protocol_fault;
wire halted=fault || parent_fault!==1'b0 || protocol_fault;
wire [23:0] post_qpn=s_post_context[395:372];wire [31:0] post_length=s_post_context[307:276];
wire [64:0] post_va_end={1'b0,s_post_context[243:180]}+{33'd0,post_length};
wire [64:0] post_offset_end={1'b0,s_post_context[179:116]}+{33'd0,post_length};
wire post_ok=(^s_post_context)!==1'bx && post_qpn<8 && s_post_context[459:396]!=0 &&
    s_post_context[523:460]!=0 && s_post_context[371:356]!=0 && s_post_context[355:340]!=0 &&
    s_post_context[339:324]==4 && s_post_context[323:308]==1 && s_post_context[19:0]==20'd3 &&
    s_post_context[619:588]==0 && s_post_context[115:20]==0 && post_length<=1048576 &&
    (post_length==0 ? s_post_context[275:116]==0 : s_post_context[275:244]!=0 &&
     post_va_end<=65'h10000000000000000 && post_offset_end<=65'h10000000000000000);
assign s_post_ready=post_ok && count[post_qpn[2:0]]<8 && !halted && !rst;
wire query_ok=(^query_qpn)!==1'bx && query_qpn<8;
wire cancel_target=cancel_block!==1'b0 && ((^cancel_qpn)===1'bx || cancel_qpn==query_qpn);
wire continuation=held && group_active && !armed && !packet_done && !message_proved;
assign m_head_context=held ? owner : query_ok ? owners[{query_qpn[2:0],head[query_qpn[2:0]]}]:620'd0;
assign m_head_valid=query_ok && !cancel_target && !halted && !rst &&
    (held ? continuation && query_qpn==owner[395:372] : count[query_qpn[2:0]]!=0);
assign held_context=owner;assign active=held;

wire [7:0] pf=s_placement_notification_flags;
wire only=pf==0 || pf==1 || pf==3;wire first=pf==4,middle=pf==8,last=pf==16 || pf==17;
wire terminal=only || last;
wire [32:0] placement_total={1'b0,received_bytes}+{1'b0,s_placement_length};
wire placement_shape=(^{s_placement_context,s_placement_length,s_placement_notification,pf,s_placement_psn})!==1'bx &&
    held && armed && !placed && !packet_done && s_placement_context===owner &&
    (only || first || middle || last) && ((pf&1)!=0 || s_placement_notification==0) &&
    s_placement_length<=4096 && (pf==3 || s_placement_length<=owner[307:276]);
wire placement_sequence=only ? !group_active :
    first ? !group_active && s_placement_length==4096 && owner[307:276]>4096 :
    group_active && s_placement_psn==next_psn && placement_total<=1048576 &&
      placement_total<={1'b0,owner[307:276]} &&
      (middle ? s_placement_length==4096 && placement_total<{1'b0,owner[307:276]} : s_placement_length!=0);
wire placement_match=placement_shape && placement_sequence;
assign s_placement_ready=placement_match && !halted && !rst;
wire [31:0] core_length=s_core_data[651:620];wire [23:0] core_psn=s_core_data[675:652];
wire [23:0] incoming_msn=s_core_data[703:680];
wire [31:0] core_notification=s_core_data[735:704];wire [7:0] core_flags=s_core_data[743:736];
wire core_shape=(^s_core_data)!==1'bx && held && armed && !packet_done && s_core_data[619:0]===owner &&
    s_core_data[679:676]==0 && s_core_data[751:744]==0 && core_length<=4096 &&
    (core_flags==0 || core_flags==1 || core_flags==3 || core_flags==4 || core_flags==8 || core_flags==16 || core_flags==17) &&
    ((core_flags&1)!=0 || core_notification==0) && (core_flags==3 || core_length<=owner[307:276]);
wire core_match=core_shape && placed && !core_proved && core_length==packet_length &&
    core_psn==packet_psn && core_flags==packet_flags && core_notification==notification &&
    (!group_active || incoming_msn==(base_msn+((packet_flags==16 || packet_flags==17) ? 24'd1:24'd0)));
assign s_core_ready=core_match && !halted && !rst;
wire mac_shape=(^s_mac_data)!==1'bx && core_proved && !mac_proved && !packet_done &&
    s_mac_data[751:0]===held_core_data && s_mac_data[767:765]==3'b011 && s_mac_data[764:752]!=0;
assign s_mac_ready=mac_shape && !halted && !rst;
wire packet_terminal=packet_flags==0 || packet_flags==1 || packet_flags==3 || packet_flags==16 || packet_flags==17;
assign m_packet_retire_context=owner;
assign m_packet_retire_valid=packet_prepared && !packet_done && !halted && !rst;
wire packet_release=m_packet_retire_valid && m_packet_retire_ready;

wire [32:0] whole_bytes=packet_done ? {1'b0,received_bytes} : group_active ?
    {1'b0,received_bytes}+{1'b0,packet_length} : {1'b0,packet_length};
wire message_basic=(^s_message_data)!==1'bx && held && s_message_data[619:0]===owner &&
    s_message_data[775:764]==0;
wire message_match=message_basic && core_proved && placed && packet_terminal &&
    s_message_data[651:620]==whole_bytes && s_message_data[675:652]==first_psn &&
    s_message_data[699:676]==packet_psn && s_message_data[723:700]==core_msn &&
    s_message_data[755:724]==notification && s_message_data[763:756]==(packet_flags&8'h03);
assign s_message_ready=message_match && !message_proved && !halted && !rst;
assign m_ticket_context=owner;assign m_ticket_received_bytes=received_bytes;
assign m_ticket_notification=message_notification;assign m_ticket_notification_flags=message_flags;
assign m_ticket_valid=ticket_prepared && !ticket_sent && !halted && !rst;
assign s_commit_ready=held && packet_done && message_proved && ticket_sent && !committed &&
    s_commit_context===owner && !halted && !rst;
assign s_retire_ready=held && committed && s_retire_context===owner && !halted && !rst;
wire release_owner=s_retire_valid && s_retire_ready;
assign protocol_fault=s_post_valid && !post_ok || s_placement_valid && !placement_match ||
    s_core_valid && (!core_shape || core_proved || (placed && !core_match)) ||
    s_mac_valid && !mac_shape || s_message_valid &&
    (!message_basic || message_proved || (core_proved && !message_match)) ||
    s_commit_valid && s_commit_context!==owner || s_retire_valid && s_retire_context!==owner;

reg cancel_match;integer ci;
always @*begin
    cancel_match=(^{cancel_qpn,cancel_pd,cancel_epoch})!==1'bx && cancel_qpn<8 && cancel_pd!=0 && cancel_epoch!=0;
    for(integer n=0;n<8;n=n+1)begin
        ci=(head[cancel_qpn[2:0]]+n)%8;
        if(cancel_qpn<8 && n<count[cancel_qpn[2:0]] &&
           (owners[{cancel_qpn[2:0],ci[2:0]}][395:372]!==cancel_qpn ||
            owners[{cancel_qpn[2:0],ci[2:0]}][371:356]!==cancel_pd ||
            owners[{cancel_qpn[2:0],ci[2:0]}][459:396]!==cancel_epoch))cancel_match=0;
    end
end
assign cancel_ready=cancel_block===1'b1 && cancel_valid===1'b1 && cancel_safe===1'b1 &&
    memory_drained===1'b1 && cancel_match && !held &&
    !(s_post_valid && post_qpn==cancel_qpn) && !halted && !rst;
reg [7:0] guards;
always @*begin
    guards=0;
    for(integer k=0;k<8;k=k+1)if(count[k]!=0)guards[k]=1;
    if(held)guards[owner[374:372]]=1;
    if(s_post_valid && post_ok)guards[post_qpn[2:0]]=1;
    if(halted)guards=8'hff;
end
assign queue_guard=guards;
integer j;
always @(posedge clk)begin
    if(rst)begin
        held<=0;armed<=0;placed<=0;mac_proved<=0;packet_done<=0;group_active<=0;message_proved<=0;
        packet_prepared<=0;ticket_prepared<=0;
        ticket_sent<=0;committed<=0;owner<=0;packet_length<=0;notification<=0;packet_flags<=0;
        message_notification<=0;message_flags<=0;packet_psn<=0;first_psn<=0;next_psn<=0;base_msn<=0;
        core_proved<=0;held_core_data<=0;core_msn<=0;fault<=0;fault_code<=0;
        posted_count<=0;taken_count<=0;placement_count<=0;received_bytes<=0;core_proof_count<=0;
        packet_retired_count<=0;cancelled_count<=0;
        for(j=0;j<8;j=j+1)begin count[j]<=0;head[j]<=0;tail[j]<=0;end
    end else begin
        if(parent_fault!==1'b0 || s_post_valid && !post_ok || s_placement_valid && !placement_match)begin fault<=1;fault_code<=8'he8;end
        if(s_core_valid && (!core_shape || core_proved || (placed && !core_match)))begin fault<=1;fault_code<=8'hea;end
        if(s_mac_valid && !mac_shape)begin fault<=1;fault_code<=8'heb;end
        if(s_message_valid && (!message_basic || message_proved || (core_proved && !message_match)))begin fault<=1;fault_code<=8'hec;end
        if(s_commit_valid && s_commit_context!==owner)begin fault<=1;fault_code<=8'hed;end
        if(s_retire_valid && s_retire_context!==owner)begin fault<=1;fault_code<=8'hee;end
        for(j=0;j<8;j=j+1)begin
            case({s_post_valid && s_post_ready && post_qpn==j,release_owner && owner[395:372]==j})
                2'b10:count[j]<=count[j]+1'b1;
                2'b01:count[j]<=count[j]-1'b1;
                default:begin end
            endcase
        end
        if(s_post_valid && s_post_ready)begin owners[{post_qpn[2:0],tail[post_qpn[2:0]]}]<=s_post_context;tail[post_qpn[2:0]]<=tail[post_qpn[2:0]]+1'b1;posted_count<=posted_count+1'b1;end
        if(m_head_valid && m_head_ready)begin
            armed<=1;placed<=0;core_proved<=0;mac_proved<=0;held_core_data<=0;packet_prepared<=0;
            if(!held)begin
                held<=1;owner<=m_head_context;taken_count<=taken_count+1'b1;received_bytes<=0;group_active<=0;
                message_proved<=0;packet_done<=0;ticket_prepared<=0;ticket_sent<=0;committed<=0;
            end
        end
        if(s_placement_valid && s_placement_ready)begin
            placed<=1;packet_length<=s_placement_length;notification<=s_placement_notification;packet_flags<=pf;
            packet_psn<=s_placement_psn;if(!group_active)first_psn<=s_placement_psn;
            placement_count<=placement_count+1'b1;
        end
        if(s_core_valid && s_core_ready)begin
            core_proved<=1;held_core_data<=s_core_data;core_msn<=incoming_msn;
            core_proof_count<=core_proof_count+1'b1;
        end
        if(s_mac_valid && s_mac_ready)mac_proved<=1;
        if(s_message_valid && s_message_ready)begin
            message_proved<=1;message_notification<=s_message_data[755:724];message_flags<=s_message_data[763:756];
        end
        if(held && armed && placed && core_proved && mac_proved && !packet_done &&
            memory_drained===1'b1 && !halted)packet_prepared<=1;
        if(held && packet_done && message_proved && memory_drained===1'b1 && !halted)ticket_prepared<=1;
        if(packet_release)begin
            packet_retired_count<=packet_retired_count+1'b1;received_bytes<=whole_bytes;packet_prepared<=0;
            if(packet_terminal)packet_done<=1;
            else begin
                armed<=0;placed<=0;core_proved<=0;mac_proved<=0;held_core_data<=0;group_active<=1;
                next_psn<=packet_psn+1'b1;if(!group_active)base_msn<=core_msn;
            end
        end
        if(m_ticket_valid && m_ticket_ready)ticket_sent<=1;
        if(s_commit_valid && s_commit_ready)committed<=1;
        if(release_owner)begin
            head[owner[374:372]]<=head[owner[374:372]]+1'b1;
            held<=0;armed<=0;placed<=0;core_proved<=0;mac_proved<=0;packet_done<=0;group_active<=0;
            message_proved<=0;ticket_sent<=0;committed<=0;held_core_data<=0;owner<=0;
            packet_prepared<=0;ticket_prepared<=0;
        end
        if(cancel_valid && cancel_ready)begin
            cancelled_count<=cancelled_count+count[cancel_qpn[2:0]];
            head[cancel_qpn[2:0]]<=tail[cancel_qpn[2:0]];count[cancel_qpn[2:0]]<=0;
        end
    end
end
endmodule
`resetall
