// SPDX-License-Identifier: BSD-2-Clause-Views
// Copyright (c) 2026 jyohukuchan
// Real privileged CQ event publisher. A lifetime TICKET is not a host CQE:
// complete the exact lifetime commit AND shared-core retirement before making
// the immutable full-owner_context event visible. Retain a queue guard until the
// host ACKs this non-wrapping event sequence. No payload copy or DMA substitute.
// The caller supplies actual lifetime/core owners; this module invents no
// drain certificate. Whole-NIC reset is NOT DMA cancellation or safe unpin.
`resetall
`timescale 1ns/1ps
`default_nettype none
module rocev2_cq_mmio #(
    parameter MAX_QPS=8,
    parameter ADDR_WIDTH=12,
    // Opt-in ABI extension only, NOT an upstream completion certificate.
    // The main endpoint must keep this off until real receive lifetime joins.
    parameter MESSAGE_ENABLE=0,
    parameter IMMEDIATE_ENABLE=0
)(
    input wire clk,input wire rst,input wire parent_fault,
    input wire [587+32*IMMEDIATE_ENABLE:0] s_ticket_context,input wire s_ticket_valid,output wire s_ticket_ready,
    input wire [31:0] s_ticket_received_bytes,
    // Separate wire-derived notification; NEVER overwrite the posted owner.
    input wire [31:0] s_ticket_notification,input wire [7:0] s_ticket_notification_flags,
    input wire [63:0] s_owner_cookie,input wire [63:0] s_owner_epoch,
    input wire [15:0] s_owner_pd,input wire s_owner_valid,
    output wire [587+32*IMMEDIATE_ENABLE:0] m_commit_context,output wire [7:0] m_commit_error,
    output wire m_commit_valid,input wire m_commit_ready,
    output wire [587+32*IMMEDIATE_ENABLE:0] m_retire_context,output wire m_retire_valid,input wire m_retire_ready,
    output wire [MAX_QPS-1:0] queue_guard,output wire busy,
    output reg fault=0,output reg [7:0] fault_code=0,
    output reg [31:0] published_count=0,output reg [31:0] acknowledged_count=0,
    input wire [ADDR_WIDTH-1:0] s_axil_awaddr,input wire [2:0] s_axil_awprot,
    input wire s_axil_awvalid,output wire s_axil_awready,
    input wire [31:0] s_axil_wdata,input wire [3:0] s_axil_wstrb,
    input wire s_axil_wvalid,output wire s_axil_wready,
    output wire [1:0] s_axil_bresp,output wire s_axil_bvalid,input wire s_axil_bready,
    input wire [ADDR_WIDTH-1:0] s_axil_araddr,input wire [2:0] s_axil_arprot,
    input wire s_axil_arvalid,output wire s_axil_arready,
    output wire [31:0] s_axil_rdata,output wire [1:0] s_axil_rresp,
    output wire s_axil_rvalid,input wire s_axil_rready
);
localparam IDLE=0,COMMIT=1,RETIRE=2,VISIBLE=3;
reg [1:0] state=IDLE;
reg [587+32*IMMEDIATE_ENABLE:0] owner_context=0;
reg [63:0] cookie=0;
reg [31:0] received_bytes=0;
reg [31:0] notification=0;reg [7:0] notification_flags=0;
reg [31:0] event_sequence=0,last_ack=0;
wire [23:0] incoming_qpn=s_ticket_context[395:372];
wire [23:0] held_qpn=owner_context[395:372];
wire incoming_known=(^{s_ticket_context,s_owner_cookie,s_owner_epoch,s_owner_pd,s_owner_valid})!==1'bx;
wire owner_ok=incoming_known && s_owner_valid && s_owner_cookie!=0 &&
    s_owner_epoch==s_ticket_context[459:396] && s_owner_pd==s_ticket_context[371:356];
wire [15:0] incoming_opcode=s_ticket_context[339:324];
wire message_shape=s_ticket_context[115:20]==0 &&
    (incoming_opcode==3 || (IMMEDIATE_ENABLE && incoming_opcode==5) ||
     (incoming_opcode==4 && s_ticket_context[323:308]==1));
wire [31:0] posted_immediate=s_ticket_context>>588;
wire notification_known=(^{s_ticket_notification,s_ticket_notification_flags})!==1'bx;
wire notification_shape=!IMMEDIATE_ENABLE || (notification_known &&
    (incoming_opcode==5 || incoming_opcode==6 || posted_immediate==0) &&
    (s_ticket_notification_flags==0 || incoming_opcode==4 &&
     (s_ticket_notification_flags==1 || s_ticket_notification_flags==3)) &&
    (s_ticket_notification_flags!=0 || s_ticket_notification==0));
wire write_notification=IMMEDIATE_ENABLE && s_ticket_notification_flags==3;
wire receive_length_ok=(^s_ticket_received_bytes)!==1'bx &&
    (incoming_opcode==4 ? s_ticket_received_bytes!=0 &&
     s_ticket_received_bytes<=4096 && (write_notification || s_ticket_received_bytes<=s_ticket_context[307:276]) :
     s_ticket_received_bytes==0);
wire ticket_ok=owner_ok && incoming_qpn<MAX_QPS && s_ticket_context[523:460]!=0 &&
    s_ticket_context[459:396]!=0 && s_ticket_context[355:340]!=0 &&
    (incoming_opcode==1 || incoming_opcode==2 || (IMMEDIATE_ENABLE && incoming_opcode==6) || MESSAGE_ENABLE && message_shape) &&
    notification_shape &&
    (!MESSAGE_ENABLE || receive_length_ok) &&
    (s_ticket_context[323:308]&16'hfffe)==0 && s_ticket_context[307:276]!=0 &&
    s_ticket_context[307:276]<=4096 && s_ticket_context[19:2]==0 && s_ticket_context[1:0]==2'b11;
wire halted=fault || parent_fault!==1'b0;
assign s_ticket_ready=state==IDLE && !halted && !rst && event_sequence!=32'hffffffff && ticket_ok;
assign m_commit_context=owner_context;assign m_commit_error=0;
assign m_commit_valid=state==COMMIT && !rst;
assign m_retire_context=owner_context;
assign m_retire_valid=state==RETIRE && !rst;
assign busy=state!=IDLE || fault;
assign queue_guard=halted ? {MAX_QPS{1'b1}} : state!=IDLE ?
    ({{(MAX_QPS-1){1'b0}},1'b1}<<held_qpn) :
    (s_ticket_valid && ticket_ok) ? ({{(MAX_QPS-1){1'b0}},1'b1}<<incoming_qpn) : 0;
wire [ADDR_WIDTH-1:0] wa,ra;wire [31:0] wd;wire [3:0] ws;
wire we,re;reg [31:0] rd;
wire context_read=ra>=12'h040 && ra<=(IMMEDIATE_ENABLE ? 12'h08c:12'h088);
wire read_known=context_read || ra==0 || ra==4 || ra==8 || ra==12 ||
    ra==12'h014 || ra==12'h018 || ra==12'h01c || ra==12'h020 || ra==12'h024 ||
    ra==12'h028 || ra==12'h02c || ra==12'h030 || ra==12'h034 ||
    MESSAGE_ENABLE && ra==12'h038 || IMMEDIATE_ENABLE && (ra==12'h03c || ra==12'h090);
wire write_known=wa==12'h010;
wire write_ack=we && wa[1:0]==0 && write_known;
wire read_ack=re && ra[1:0]==0 && read_known;
always @*begin
    rd=0;
    if(context_read && ra[1:0]==0 && state==VISIBLE)
        rd=({20'd0,owner_context}>>(((ra-12'h040)>>2)*32));
    else case(ra)
    0:rd=32'h43514331; // CQC1, completion-event mailbox, NOT standard verbs ABI.
    4:rd=32'h00010000;
    8:rd=IMMEDIATE_ENABLE ? 7 : MESSAGE_ENABLE ? 3 : 1;
    12:rd={28'd0,event_sequence==32'hffffffff,halted,state!=IDLE,state==VISIBLE};
    12'h014:rd=last_ack;
    12'h018:rd=event_sequence;
    12'h01c:rd=state==VISIBLE ? 32'h0f : 0; // memory/transport/lifetime/core-retired
    12'h020:rd=state==VISIBLE ? cookie[31:0] : 0;
    12'h024:rd=state==VISIBLE ? cookie[63:32] : 0;
    12'h028:rd=0; // Positive publisher: actual upstream success only.
    12'h02c:rd={24'd0,fault_code};
    12'h030:rd=published_count;
    12'h034:rd=acknowledged_count;
    12'h038:rd=MESSAGE_ENABLE && state==VISIBLE ? received_bytes : 0;
    12'h03c:rd=IMMEDIATE_ENABLE && state==VISIBLE ? {24'd0,notification_flags} : 0;
    12'h090:rd=IMMEDIATE_ENABLE && state==VISIBLE ? notification : 0;
    default:rd=0;
    endcase
end
axil_reg_if #(.DATA_WIDTH(32),.ADDR_WIDTH(ADDR_WIDTH),.STRB_WIDTH(4),.TIMEOUT(8)) registers(
    .clk(clk),.rst(rst),
    .s_axil_awaddr(s_axil_awaddr),.s_axil_awprot(s_axil_awprot),.s_axil_awvalid(s_axil_awvalid),.s_axil_awready(s_axil_awready),
    .s_axil_wdata(s_axil_wdata),.s_axil_wstrb(s_axil_wstrb),.s_axil_wvalid(s_axil_wvalid),.s_axil_wready(s_axil_wready),
    .s_axil_bresp(s_axil_bresp),.s_axil_bvalid(s_axil_bvalid),.s_axil_bready(s_axil_bready),
    .s_axil_araddr(s_axil_araddr),.s_axil_arprot(s_axil_arprot),.s_axil_arvalid(s_axil_arvalid),.s_axil_arready(s_axil_arready),
    .s_axil_rdata(s_axil_rdata),.s_axil_rresp(s_axil_rresp),.s_axil_rvalid(s_axil_rvalid),.s_axil_rready(s_axil_rready),
    .reg_wr_addr(wa),.reg_wr_data(wd),.reg_wr_strb(ws),.reg_wr_en(we),.reg_wr_wait(1'b0),.reg_wr_ack(write_ack),
    .reg_rd_addr(ra),.reg_rd_en(re),.reg_rd_data(rd),.reg_rd_wait(1'b0),.reg_rd_ack(read_ack));
initial if(MAX_QPS!=8 || ADDR_WIDTH!=12 || (MESSAGE_ENABLE!=0 && MESSAGE_ENABLE!=1))$fatal(1,"unreviewed CQ geometry");
initial if((IMMEDIATE_ENABLE!=0 && IMMEDIATE_ENABLE!=1) || (IMMEDIATE_ENABLE && !MESSAGE_ENABLE))$fatal(1,"Immediate CQ needs complete message profile");
always @(posedge clk)begin
    if(rst)begin
        state<=IDLE;owner_context<=0;cookie<=0;received_bytes<=0;notification<=0;notification_flags<=0;event_sequence<=0;last_ack<=0;
        fault<=0;fault_code<=0;published_count<=0;acknowledged_count<=0;
    end else begin
        if(parent_fault!==1'b0)begin fault<=1;fault_code<=8'hc1;end
        if(state==IDLE && (s_ticket_valid!==1'b0 && s_ticket_valid!==1'b1 ||
           s_ticket_valid && (!ticket_ok || event_sequence==32'hffffffff)))begin
            fault<=1;fault_code<=8'hc2;
        end
        if(s_ticket_valid && s_ticket_ready)begin
            owner_context<=s_ticket_context;cookie<=s_owner_cookie;
            received_bytes<=MESSAGE_ENABLE ? s_ticket_received_bytes : 0;
            notification<=IMMEDIATE_ENABLE ? s_ticket_notification : 0;
            notification_flags<=IMMEDIATE_ENABLE ? s_ticket_notification_flags : 0;
            event_sequence<=event_sequence+1'b1;state<=COMMIT;
        end
        if(m_commit_valid && m_commit_ready)state<=RETIRE;
        if(m_retire_valid && m_retire_ready)begin state<=VISIBLE;published_count<=published_count+1'b1;end
        if(we)begin
            if(!write_ack || ws!==4'hf || (^wd)===1'bx || wd==0)begin fault<=1;fault_code<=8'hc3;end
            else if(state==VISIBLE && wd==event_sequence)begin
                // Same event only; a repeated ACK can never clear its successor.
                last_ack<=event_sequence;state<=IDLE;acknowledged_count<=acknowledged_count+1'b1;
            end else if(wd!=last_ack)begin fault<=1;fault_code<=8'hc4;end
        end
        if(re && !read_ack)begin fault<=1;fault_code<=8'hc5;end
    end
end
endmodule
`resetall
