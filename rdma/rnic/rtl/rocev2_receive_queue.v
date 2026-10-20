// SPDX-License-Identifier: BSD-2-Clause-Views
// Genuine posted receive-owner queue, fed ONLY by coherent WQE fetch + SAME
// MR authorization. No raw packet address/key becomes placement authority.
// Placement/ACK submission is NOT CQ/core-drain/MAC completion or unpin.
// Opt-in CQ joins actual per-operation HLS and fresh-tag MAC receipts before
// exact commit/retire. No reset/quiet/constant1 substitute is accepted here.
`resetall
`timescale 1ns/1ps
`default_nettype none
module rocev2_receive_queue #(
    parameter MAX_QPS=8,
    parameter DEPTH=8,
    parameter RECV_RETIRE_ENABLE=0,
    parameter RECV_CQ_ENABLE=0,
    parameter RECV_CANCEL_ENABLE=0,
    parameter IMMEDIATE_ENABLE=0
)(
    input wire clk,input wire rst,input wire parent_fault,
    input wire cancel_block,input wire cancel_valid,input wire cancel_safe,
    input wire [23:0] cancel_qpn,input wire [15:0] cancel_pd,input wire [63:0] cancel_epoch,
    output wire cancel_ready,output reg [31:0] cancelled_count=0,
    input wire [587+32*IMMEDIATE_ENABLE:0] s_post_context,input wire s_post_valid,output wire s_post_ready,
    input wire [23:0] query_qpn,output wire [587+32*IMMEDIATE_ENABLE:0] m_head_context,output wire m_head_valid,input wire m_head_ready,
    input wire [587+32*IMMEDIATE_ENABLE:0] s_placement_context,input wire [31:0] s_placement_length,
    // From the protected wire admission, not from the posted RQ descriptor.
    // WRITE_WITH_IMM data still needs independent remote-MR authorization.
    input wire [31:0] s_placement_notification,input wire [7:0] s_placement_notification_flags,
    input wire s_placement_valid,output wire s_placement_ready,
    input wire [23:0] s_placement_psn,
    input wire [679+72*IMMEDIATE_ENABLE:0] s_core_data,input wire s_core_valid,output wire s_core_ready,
    output reg core_proved=0,output reg [31:0] core_proof_count=0,
    output reg [23:0] core_msn=0,
    output wire [587+32*IMMEDIATE_ENABLE:0] held_context,
    output reg [679+72*IMMEDIATE_ENABLE:0] held_core_data=0,
    input wire [695+72*IMMEDIATE_ENABLE:0] s_mac_data,input wire s_mac_valid,output wire s_mac_ready,
    input wire memory_drained,
    output wire [587+32*IMMEDIATE_ENABLE:0] m_ticket_context,output wire [31:0] m_ticket_received_bytes,
    output wire [31:0] m_ticket_notification,output wire [7:0] m_ticket_notification_flags,
    output wire m_ticket_valid,input wire m_ticket_ready,
    input wire [587+32*IMMEDIATE_ENABLE:0] s_commit_context,input wire s_commit_valid,output wire s_commit_ready,
    input wire [587+32*IMMEDIATE_ENABLE:0] s_retire_context,input wire s_retire_valid,output wire s_retire_ready,
    output wire [MAX_QPS-1:0] queue_guard,output wire active,
    output reg fault=0,output reg [7:0] fault_code=0,
    output reg [31:0] posted_count=0,output reg [31:0] taken_count=0,
    output reg [31:0] placement_count=0,output reg [31:0] received_bytes=0
);
initial if(MAX_QPS!=8 || DEPTH!=8)$fatal(1,"receive queue requires full8QP/8entry profile");
initial if(RECV_CQ_ENABLE && !RECV_RETIRE_ENABLE)$fatal(1,"receive CQ needs actual operation receipt");
initial if(RECV_CANCEL_ENABLE && !RECV_CQ_ENABLE)$fatal(1,"receive cancellation requires complete receive lifetime");
initial if((IMMEDIATE_ENABLE!=0 && IMMEDIATE_ENABLE!=1) || (IMMEDIATE_ENABLE && !RECV_CQ_ENABLE))$fatal(1,"Immediate RQ requires full receive CQ profile");
localparam OWNER_WIDTH=588+32*IMMEDIATE_ENABLE,CORE_WIDTH=680+72*IMMEDIATE_ENABLE;
reg [OWNER_WIDTH-1:0] owners[0:MAX_QPS*DEPTH-1];
reg [3:0] count[0:MAX_QPS-1];
reg [2:0] head[0:MAX_QPS-1],tail[0:MAX_QPS-1];
reg held=0,placed=0;reg [OWNER_WIDTH-1:0] owner=0;
reg [31:0] notification=0;reg [7:0] notification_flags=0;
reg [23:0] placement_psn=0;
reg mac_proved=0,ticket_prepared=0,ticket_sent=0,committed=0;
assign held_context=owner;
wire [23:0] qpn=s_post_context[395:372];
wire [31:0] length=s_post_context[307:276];
wire post_known=(^s_post_context)!==1'bx;
wire post_ok=post_known && qpn<MAX_QPS && s_post_context[459:396]!=0 &&
    s_post_context[523:460]!=0 && s_post_context[355:340]!=0 &&
    s_post_context[339:324]==4 && s_post_context[323:308]==1 &&
    length!=0 && length<=4096 && s_post_context[115:20]==0 && s_post_context[19:0]==20'd3 &&
    (s_post_context>>588)==0;
wire query_ok=(^query_qpn)!==1'bx && query_qpn<MAX_QPS;
assign m_head_context=query_ok ? owners[{query_qpn[2:0],head[query_qpn[2:0]]}] : 0;
wire cancel_target=RECV_CANCEL_ENABLE && cancel_block!==1'b0 &&
    ((^cancel_qpn)===1'bx || cancel_qpn==query_qpn);
assign m_head_valid=query_ok && count[query_qpn[2:0]]!=0 && !held && !fault && !parent_fault && !rst && !cancel_target;
assign s_post_ready=post_ok && count[qpn[2:0]]<DEPTH && !fault && !parent_fault && !rst;
assign active=held;
wire placement_notification_ok=!IMMEDIATE_ENABLE ||
    ((^{s_placement_notification,s_placement_notification_flags})!==1'bx &&
     (s_placement_notification_flags==0 || s_placement_notification_flags==1 || s_placement_notification_flags==3) &&
     (s_placement_notification_flags!=0 || s_placement_notification==0));
wire placement_write=IMMEDIATE_ENABLE && s_placement_notification_flags==3;
wire placement_match=held && !placed && (^s_placement_context)!==1'bx && s_placement_context==owner &&
    (^s_placement_length)!==1'bx && s_placement_length!=0 && s_placement_length<=4096 &&
    (placement_write || s_placement_length<=owner[307:276]) && placement_notification_ok &&
    (!RECV_RETIRE_ENABLE || (^s_placement_psn)!==1'bx);
assign s_placement_ready=placement_match && !fault && !parent_fault && !rst;
// SAME full owner + actual byte count + packet PSN; proof comes ONLY from
// the selected actual HLS consumers, never an empty/idle/pool-count input.
wire [31:0] core_notification=s_core_data>>(OWNER_WIDTH+84);
wire [7:0] core_notification_flags=s_core_data>>(OWNER_WIDTH+116);
wire core_notification_ok=!IMMEDIATE_ENABLE ||
    ((core_notification_flags==0 || core_notification_flags==1 || core_notification_flags==3) &&
     (core_notification_flags!=0 || core_notification==0));
wire core_write=IMMEDIATE_ENABLE && core_notification_flags==3;
wire core_shape=held && (^s_core_data)!==1'bx && s_core_data[OWNER_WIDTH-1:0]==owner &&
    s_core_data[OWNER_WIDTH+59:OWNER_WIDTH+56]==0 && s_core_data[CORE_WIDTH-1:CORE_WIDTH-8]==0 && core_notification_ok &&
    s_core_data[OWNER_WIDTH+31:OWNER_WIDTH]!=0 && s_core_data[OWNER_WIDTH+31:OWNER_WIDTH]<=4096 &&
    (core_write || s_core_data[OWNER_WIDTH+31:OWNER_WIDTH]<=owner[307:276]);
wire placement_core_match=s_core_data[OWNER_WIDTH+31:OWNER_WIDTH]==received_bytes &&
    s_core_data[OWNER_WIDTH+55:OWNER_WIDTH+32]==placement_psn &&
    (!IMMEDIATE_ENABLE || (core_notification==notification && core_notification_flags==notification_flags));
wire core_match=core_shape && placed && !core_proved && placement_core_match;
assign s_core_ready=RECV_RETIRE_ENABLE && core_match && !fault && !parent_fault && !rst;
wire mac_shape=held && (^s_mac_data)!==1'bx && s_mac_data[CORE_WIDTH-1:0]===held_core_data &&
    s_mac_data[CORE_WIDTH+15:CORE_WIDTH+13]==3'b011 && s_mac_data[CORE_WIDTH+12:CORE_WIDTH]!=0;
assign s_mac_ready=RECV_CQ_ENABLE && core_proved && !mac_proved && mac_shape && !fault && !parent_fault && !rst;
assign m_ticket_context=owner;
assign m_ticket_received_bytes=received_bytes;
assign m_ticket_notification=notification;assign m_ticket_notification_flags=notification_flags;
assign m_ticket_valid=RECV_CQ_ENABLE && ticket_prepared && !ticket_sent && !rst;
assign s_commit_ready=RECV_CQ_ENABLE && held && ticket_sent && !committed &&
    s_commit_context===owner && !fault && !parent_fault && !rst;
assign s_retire_ready=RECV_CQ_ENABLE && held && committed && s_retire_context===owner &&
    !fault && !parent_fault && !rst;
wire release_owner=s_retire_valid && s_retire_ready;
reg cancel_match;
integer ci;
always @*begin
    cancel_match=(^{cancel_qpn,cancel_pd,cancel_epoch})!==1'bx &&
        cancel_qpn<MAX_QPS && cancel_pd!=0 && cancel_epoch!=0;
    for(integer n=0;n<DEPTH;n=n+1)begin
        ci=(head[cancel_qpn[2:0]]+n)%DEPTH;
        if(cancel_qpn<MAX_QPS && n<count[cancel_qpn[2:0]] &&
          (owners[{cancel_qpn[2:0],ci[2:0]}][395:372]!==cancel_qpn ||
           owners[{cancel_qpn[2:0],ci[2:0]}][371:356]!==cancel_pd ||
           owners[{cancel_qpn[2:0],ci[2:0]}][459:396]!==cancel_epoch))cancel_match=0;
    end
end
// Only never-taken posted owners are cancellable here. A held/placed/HLS/MAC
// owner must finish its existing real lifetime; no synthetic CQ/core receipt.
assign cancel_ready=RECV_CANCEL_ENABLE && cancel_block===1'b1 && cancel_valid===1'b1 &&
    cancel_safe===1'b1 && memory_drained===1'b1 && cancel_match && !held &&
    !(s_post_valid && qpn==cancel_qpn) && !fault && !parent_fault && !rst;
reg [7:0] guards;
integer j;
always @*begin
    guards=0;
    for(integer k=0;k<MAX_QPS;k=k+1)if(count[k]!=0)guards[k]=1;
    if(s_post_valid && post_ok)guards[qpn[2:0]]=1;
    if(fault || parent_fault!==1'b0)guards=8'hff;
end
assign queue_guard=guards;
always @(posedge clk)begin
    if(rst)begin
        held<=0;placed<=0;owner<=0;notification<=0;notification_flags<=0;fault<=0;fault_code<=0;
        posted_count<=0;taken_count<=0;placement_count<=0;received_bytes<=0;cancelled_count<=0;
        core_proved<=0;core_proof_count<=0;core_msn<=0;placement_psn<=0;
        held_core_data<=0;mac_proved<=0;ticket_prepared<=0;ticket_sent<=0;committed<=0;
        for(j=0;j<MAX_QPS;j=j+1)begin count[j]<=0;head[j]<=0;tail[j]<=0;end
    end else begin
        if(parent_fault!==1'b0 || s_post_valid && !post_ok || s_placement_valid && !placement_match)begin
            fault<=1;fault_code<=8'he8;
        end
        if(RECV_RETIRE_ENABLE && s_core_valid && (!core_shape || core_proved ||
            (placed && !placement_core_match)))begin
            fault<=1;fault_code<=8'hea;
        end
        if(RECV_CQ_ENABLE && s_mac_valid && (!mac_shape || mac_proved))begin fault<=1;fault_code<=8'heb;end
        for(j=0;j<MAX_QPS;j=j+1)begin
            case({s_post_valid && s_post_ready && qpn==j,release_owner && owner[395:372]==j})
                2'b10:count[j]<=count[j]+1'b1;
                2'b01:count[j]<=count[j]-1'b1;
                default:begin end
            endcase
        end
        if(s_post_valid && s_post_ready)begin
            owners[{qpn[2:0],tail[qpn[2:0]]}]<=s_post_context;
            tail[qpn[2:0]]<=tail[qpn[2:0]]+1'b1;
            posted_count<=posted_count+1'b1;
        end
        if(m_head_valid && m_head_ready)begin
            // Do NOT pop at take: the full owner remains until exact CQ
            // retirement, including actual HLS and per-frame MAC receipts.
            held<=1;owner<=m_head_context;placed<=0;core_proved<=0;taken_count<=taken_count+1'b1;
            notification<=0;notification_flags<=0;
            held_core_data<=0;mac_proved<=0;ticket_prepared<=0;ticket_sent<=0;committed<=0;
        end
        if(s_placement_valid && s_placement_ready)begin
            placed<=1;placement_count<=placement_count+1'b1;received_bytes<=s_placement_length;placement_psn<=s_placement_psn;
            notification<=IMMEDIATE_ENABLE ? s_placement_notification:0;
            notification_flags<=IMMEDIATE_ENABLE ? s_placement_notification_flags:0;
        end
        if(s_core_valid && s_core_ready)begin
            // Genuine per-operation HLS receipt, NOT MAC/CQ retirement or
            // permission to pop/unpin. All original owners/guards stay held.
            core_proved<=1;core_proof_count<=core_proof_count+1'b1;core_msn<=s_core_data[OWNER_WIDTH+83:OWNER_WIDTH+60];
            held_core_data<=s_core_data;
        end
        if(s_mac_valid && s_mac_ready)mac_proved<=1;
        if(RECV_CQ_ENABLE && held && placed && core_proved && mac_proved && memory_drained===1'b1 &&
           !fault && !parent_fault)ticket_prepared<=1;
        if(m_ticket_valid && m_ticket_ready)ticket_sent<=1;
        if(s_commit_valid && s_commit_ready)committed<=1;
        if(release_owner)begin
            head[owner[374:372]]<=head[owner[374:372]]+1'b1;
            held<=0;placed<=0;owner<=0;core_proved<=0;notification<=0;notification_flags<=0;
            mac_proved<=0;ticket_prepared<=0;ticket_sent<=0;committed<=0;
        end
        if(cancel_valid && cancel_ready)begin
            cancelled_count<=cancelled_count+count[cancel_qpn[2:0]];
            count[cancel_qpn[2:0]]<=0;head[cancel_qpn[2:0]]<=tail[cancel_qpn[2:0]];
        end
    end
end
endmodule
`resetall
