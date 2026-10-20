// SPDX-License-Identifier: BSD-2-Clause-Views
// Copyright (c) 2026 jyohukuchan
// Privileged SQ mailbox: immutable command snapshots and exact owner replies.
// NOT a CQ, standard verbs, unpin proof, reset controller or user doorbell BAR.
// Actual fetch downstream guard MUST include work|wire|completion guards below.
// Reset requires separately proven parent drain/closed QPs/persistent epochs.
`resetall
`timescale 1ns/1ps
`default_nettype none
module rocev2_sq_control_regs #(
    parameter ADDR_WIDTH=12,
    parameter MAX_QPS=8,
    parameter [31:0] CONTROL_ID=32'h53514331,
    parameter RECV_CANCEL_ENABLE=0,
    parameter IMMEDIATE_ENABLE=0,
    parameter [31:0] INITIAL_SEQUENCE=0
)(
    input wire clk,input wire rst,
    input wire [ADDR_WIDTH-1:0] s_axil_awaddr,input wire [2:0] s_axil_awprot,
    input wire s_axil_awvalid,output wire s_axil_awready,
    input wire [31:0] s_axil_wdata,input wire [3:0] s_axil_wstrb,
    input wire s_axil_wvalid,output wire s_axil_wready,
    output wire [1:0] s_axil_bresp,output wire s_axil_bvalid,input wire s_axil_bready,
    input wire [ADDR_WIDTH-1:0] s_axil_araddr,input wire [2:0] s_axil_arprot,
    input wire s_axil_arvalid,output wire s_axil_arready,
    output wire [31:0] s_axil_rdata,output wire [1:0] s_axil_rresp,
    output wire s_axil_rvalid,input wire s_axil_rready,
    output wire [1:0] cfg_command,output wire [23:0] cfg_qpn,
    output wire [15:0] cfg_pd,output wire [63:0] cfg_epoch,
    output wire [63:0] cfg_dma_base,output wire [3:0] cfg_log_depth,
    output wire [63:0] cfg_producer,output wire cfg_valid,input wire cfg_ready,
    input wire [7:0] cfg_response_error,input wire [23:0] cfg_response_qpn,
    input wire [63:0] cfg_response_epoch,input wire [63:0] cfg_response_consumer,
    input wire cfg_response_valid,output wire cfg_response_ready,
    input wire parent_dma_drained,input wire endpoint_fault,
    output wire cancel_block,output wire cancel_valid,
    output wire [23:0] cancel_qpn,output wire [15:0] cancel_pd,output wire [63:0] cancel_epoch,
    input wire cancel_ready,
    input wire [MAX_QPS-1:0] fetch_queue_guard,
    input wire [MAX_QPS-1:0] work_queue_guard,
    input wire [MAX_QPS-1:0] wire_queue_guard,
    input wire [MAX_QPS-1:0] completion_queue_guard,
    output wire busy,output wire response_valid,
    output reg fatal=0,output reg mmio_error=0,
    output reg [MAX_QPS-1:0] owner_active=0,
    output reg [MAX_QPS-1:0] owner_tainted=0,
    output reg [31:0] last_sequence=0,
    // Read-only trusted owner lookup for the actual CQ publisher. Never
    // recover a cookie from a user WR id, RX packet or narrowed QPN.
    input wire [23:0] owner_query_qpn,
    output wire [63:0] owner_query_cookie,
    output wire [63:0] owner_query_epoch,
    output wire [15:0] owner_query_pd,
    output wire owner_query_valid,
    input wire [23:0] retry_query_qpn,
    output wire [63:0] retry_query_cookie,
    output wire [63:0] retry_query_epoch,
    output wire [15:0] retry_query_pd,
    output wire retry_query_valid
);
localparam [2:0] IDLE=0,OFFER=1,WAIT=2,REPLY=3,CANCEL=4;
localparam [7:0] ERR_OWNER=32,ERR_SEQUENCE=33,ERR_PRODUCER=34,ERR_GUARD=35,
    ERR_SHAPE=36,ERR_UNCERTAIN=128;
reg [2:0] state=IDLE;
reg [31:0] stage[0:14],snapshot[0:14];
reg [63:0] owner_cookie[0:MAX_QPS-1],owner_epoch[0:MAX_QPS-1];
reg [63:0] owner_dma[0:MAX_QPS-1],owner_producer[0:MAX_QPS-1];
reg [15:0] owner_pd[0:MAX_QPS-1];reg [3:0] owner_depth[0:MAX_QPS-1];
wire query_known=(^owner_query_qpn)!==1'bx && owner_query_qpn<MAX_QPS;
wire [2:0] query_index=owner_query_qpn[2:0];
assign owner_query_valid=query_known && owner_active[query_index] &&
    !owner_tainted[query_index] && !fatal && !endpoint_fault;
assign owner_query_cookie=owner_query_valid ? owner_cookie[query_index] : 0;
assign owner_query_epoch=owner_query_valid ? owner_epoch[query_index] : 0;
assign owner_query_pd=owner_query_valid ? owner_pd[query_index] : 0;
wire retry_query_known=(^retry_query_qpn)!==1'bx && retry_query_qpn<MAX_QPS;
wire [2:0] retry_query_index=retry_query_qpn[2:0];
assign retry_query_valid=retry_query_known && state==IDLE && owner_active[retry_query_index] &&
    !owner_tainted[retry_query_index] && !fatal && !endpoint_fault;
assign retry_query_cookie=retry_query_valid ? owner_cookie[retry_query_index] : 0;
assign retry_query_epoch=retry_query_valid ? owner_epoch[retry_query_index] : 0;
assign retry_query_pd=retry_query_valid ? owner_pd[retry_query_index] : 0;
reg [7:0] reply_error=0;reg [31:0] reply_flags=0;
reg [63:0] reply_consumer=0;
reg transfer_safe=0;
wire [ADDR_WIDTH-1:0] wa,ra;wire [31:0] wd;wire [3:0] ws;
wire we,re,wack,rack;reg [31:0] rd;
wire write_stage=wa>=12'h040 && wa<=12'h078;
wire read_stage=ra>=12'h040 && ra<=12'h078;
wire read_reply=ra>=12'h100 && ra<=12'h138;
wire read_known=read_stage || read_reply || ra==0 || ra==4 || ra==8 || ra==12 || ra==28 ||
    (ra>=12'h13c && ra<=12'h148);
wire write_known=write_stage || wa==12'h010 || wa==12'h014 || wa==12'h018;
assign wack=we && wa[1:0]==0 && write_known;
assign rack=re && ra[1:0]==0 && read_known;
wire stage_shape=stage[0]!=0 && stage[1]>=1 && stage[1]<=(RECV_CANCEL_ENABLE ? 4:3) && stage[2]<MAX_QPS &&
    stage[3][31:16]==0 && {stage[5],stage[4]}!=0 && {stage[7],stage[6]}!=0 &&
    stage[10]>=1 && stage[10]<=8;
wire [2:0] si=stage[2][2:0],qi=snapshot[2][2:0];
wire [63:0] se={stage[5],stage[4]},sc={stage[7],stage[6]},sd={stage[9],stage[8]};
wire [63:0] sp={stage[12],stage[11]},sn={stage[14],stage[13]};
wire [64:0] ring_end={1'b0,sd}+((65'd1<<stage[10])<<6);
wire owner_match=stage[2]<MAX_QPS && owner_active[si] && !owner_tainted[si] &&
    se==owner_epoch[si] && sc==owner_cookie[si] && stage[3]==owner_pd[si] &&
    sd==owner_dma[si] && stage[10]==owner_depth[si];
wire stage_safe=parent_dma_drained && !fetch_queue_guard[si] && !work_queue_guard[si] &&
    !wire_queue_guard[si] && !completion_queue_guard[si];
wire command_safe=parent_dma_drained && !fetch_queue_guard[qi] && !work_queue_guard[qi] &&
    !wire_queue_guard[qi] && !completion_queue_guard[qi] && !endpoint_fault;
wire doorbell=we && wack && wa==12'h010;
wire available=state==IDLE && !fatal && !endpoint_fault && !mmio_error && last_sequence!=32'hffffffff;
wire sequence_ok=stage[0]==last_sequence+1'b1 && stage[0]!=0 && wd==stage[0];
reg stage_known;
always @* begin
    stage_known=0;
    case(^{stage[0],stage[1],stage[2],stage[3],stage[4],stage[5],stage[6],stage[7],
           stage[8],stage[9],stage[10],stage[11],stage[12],stage[13],stage[14]})
    1'b0,1'b1:stage_known=1;
    default:stage_known=0;
    endcase
end
// Full-width checks precede all narrowing and real queue mutation.
reg [7:0] stage_error;
always @* begin
    stage_error=0;
    if(!stage_known || stage_shape!==1'b1)stage_error=ERR_SHAPE;
    else case(stage[1])
    1:if(owner_active[si]!==0 || owner_tainted[si]!==0 || (se>owner_epoch[si])!==1'b1)stage_error=ERR_OWNER;
      else if(sd[5:0]!==0 || ((ring_end[64] && ring_end[63:0]!=0))!==0 || sp!==0 || sn!==0)stage_error=ERR_SHAPE;
      else if(stage_safe!==1'b1)stage_error=ERR_GUARD;
    2:if(owner_match!==1'b1 || sn!==0)stage_error=ERR_OWNER;
      else if(owner_producer[si]==64'hffffffffffffffff || sp!==owner_producer[si]+1'b1)stage_error=ERR_PRODUCER;
    3:if(owner_match!==1'b1 || sn==0 || sp!==owner_producer[si])stage_error=ERR_OWNER;
      else if(stage_safe!==1'b1)stage_error=ERR_GUARD;
    4:if(!RECV_CANCEL_ENABLE || owner_match!==1'b1 || sn==0 || sp!==owner_producer[si])stage_error=ERR_OWNER;
    default:stage_error=ERR_SHAPE;
    endcase
end
assign cfg_command=snapshot[1]==4 ? 2'd0:snapshot[1][1:0];assign cfg_qpn=snapshot[2][23:0];
assign cfg_pd=snapshot[3][15:0];assign cfg_epoch={snapshot[5],snapshot[4]};
assign cfg_dma_base={snapshot[9],snapshot[8]};assign cfg_log_depth=snapshot[10][3:0];
assign cfg_producer={snapshot[12],snapshot[11]};
// Once offered, the complete immutable command persists even under later fault.
// The real fetcher must recheck actual parent/downstream guards at acceptance.
assign cancel_block=RECV_CANCEL_ENABLE && snapshot[1]==4 && state!=IDLE && !rst;
assign cancel_valid=cancel_block && state==CANCEL && !fatal && !endpoint_fault;
assign cancel_qpn=cfg_qpn;assign cancel_pd=cfg_pd;assign cancel_epoch=cfg_epoch;
assign cfg_valid=state==OFFER && (snapshot[1]!=4 || command_safe===1'b1) && !rst;
assign cfg_response_ready=state==WAIT && !rst;
assign busy=state!=IDLE || fatal;
assign response_valid=state==REPLY;
reg error_known;
always @* begin
    error_known=0;
    case(cfg_response_error)
    0,16,17,18,19,20,21,22:error_known=1;
    default:error_known=0;
    endcase
end
wire response_context=cfg_response_qpn==cfg_qpn && cfg_response_epoch==cfg_epoch;
wire response_shape=cfg_command!=1 || cfg_response_consumer==0;
wire retire_shape=(cfg_command!=3 && snapshot[1]!=4) || cfg_response_consumer==cfg_producer;
wire success_safe=cfg_command==2 || transfer_safe;
wire uncertain_response=!error_known || response_context!==1'b1 ||
    (cfg_response_error==0 && (response_shape!==1'b1 || retire_shape!==1'b1 || !success_safe));
always @* begin
    rd=0;
    if(read_stage && ra[1:0]==0)rd=stage[(ra-12'h040)>>2];
    else if(read_reply && ra[1:0]==0)rd=snapshot[(ra-12'h100)>>2];
    else case(ra)
    0:rd=CONTROL_ID; // SQC1 default; RQC1 uses the same owned mailbox contract.
    4:rd=32'h00010000;
    8:rd=(RECV_CANCEL_ENABLE ? 32'h3:32'h1) | (IMMEDIATE_ENABLE ? 32'h4:0);
    12:rd={26'd0,last_sequence==32'hffffffff,endpoint_fault,mmio_error,fatal,response_valid,available};
    28:rd=last_sequence;
    12'h13c:rd={24'd0,reply_error};
    12'h140:rd=reply_flags;
    12'h144:rd=reply_consumer[31:0];
    12'h148:rd=reply_consumer[63:32];
    default:rd=0;
    endcase
end
axil_reg_if #(.DATA_WIDTH(32),.ADDR_WIDTH(ADDR_WIDTH),.STRB_WIDTH(4),.TIMEOUT(8)) bus(
 .clk(clk),.rst(rst),
 .s_axil_awaddr(s_axil_awaddr),.s_axil_awprot(s_axil_awprot),.s_axil_awvalid(s_axil_awvalid),.s_axil_awready(s_axil_awready),
 .s_axil_wdata(s_axil_wdata),.s_axil_wstrb(s_axil_wstrb),.s_axil_wvalid(s_axil_wvalid),.s_axil_wready(s_axil_wready),
 .s_axil_bresp(s_axil_bresp),.s_axil_bvalid(s_axil_bvalid),.s_axil_bready(s_axil_bready),
 .s_axil_araddr(s_axil_araddr),.s_axil_arprot(s_axil_arprot),.s_axil_arvalid(s_axil_arvalid),.s_axil_arready(s_axil_arready),
 .s_axil_rdata(s_axil_rdata),.s_axil_rresp(s_axil_rresp),.s_axil_rvalid(s_axil_rvalid),.s_axil_rready(s_axil_rready),
 .reg_wr_addr(wa),.reg_wr_data(wd),.reg_wr_strb(ws),.reg_wr_en(we),.reg_wr_wait(1'b0),.reg_wr_ack(wack),
 .reg_rd_addr(ra),.reg_rd_en(re),.reg_rd_data(rd),.reg_rd_wait(1'b0),.reg_rd_ack(rack));
integer i,b;
initial begin if(ADDR_WIDTH!=12 || MAX_QPS!=8)$fatal(1,"unreviewed SQ CSR geometry");end
initial if(RECV_CANCEL_ENABLE && CONTROL_ID!=32'h52514331)$fatal(1,"cancellation is RQC1-only");
always @(posedge clk)begin
    if(rst)begin
        state<=IDLE;fatal<=0;mmio_error<=0;last_sequence<=INITIAL_SEQUENCE;owner_active<=0;owner_tainted<=0;
        reply_error<=0;reply_flags<=0;reply_consumer<=0;transfer_safe<=0;
        for(i=0;i<15;i=i+1)begin stage[i]<=0;snapshot[i]<=0;end
        for(i=0;i<MAX_QPS;i=i+1)begin owner_cookie[i]<=0;owner_epoch[i]<=0;
            owner_dma[i]<=0;owner_producer[i]<=0;owner_pd[i]<=0;owner_depth[i]<=0;end
    end else begin
        if(endpoint_fault)begin fatal<=1;if(state==OFFER || state==WAIT)owner_tainted[qi]<=1;end
        if(cfg_response_valid && state!=WAIT)begin fatal<=1;if(state!=IDLE)owner_tainted[qi]<=1;end
        if(re && !rack)mmio_error<=1;
        if(we)begin
            if(!wack)mmio_error<=1;
            else if(write_stage)begin
                for(b=0;b<4;b=b+1)if(ws[b])stage[(wa-12'h040)>>2][b*8+:8]<=wd[b*8+:8];
            end else if(wa==12'h010)begin
                if(ws!==4'hf || available!==1'b1 || sequence_ok!==1'b1)mmio_error<=1;
                else begin
                    for(i=0;i<15;i=i+1)snapshot[i]<=stage[i];
                    last_sequence<=stage[0];reply_flags<=0;reply_consumer<=0;reply_error<=stage_error;
                    state<=stage_error!=0 ? REPLY:(stage[1]==4 ? CANCEL:OFFER);
                end
            end else if(wa==12'h014)begin
                if(ws!=4'hf || state!=REPLY || wd!=snapshot[0])mmio_error<=1;
                else state<=IDLE;
            end else if(wa==12'h018)begin
                if(ws==4'hf && wd==1 && state==IDLE && !fatal && !endpoint_fault)mmio_error<=0;
                else mmio_error<=1;
            end
        end
        if(cfg_valid && cfg_ready)begin state<=WAIT;transfer_safe<=command_safe===1'b1;end
        if(cancel_valid && cancel_ready===1'b1)state<=OFFER;
        if(cfg_response_valid && cfg_response_ready)begin
            state<=REPLY;reply_consumer<=cfg_response_consumer;reply_flags<=0;
            if(uncertain_response || fatal || endpoint_fault)begin
                reply_error<=ERR_UNCERTAIN;fatal<=1;owner_tainted[qi]<=1;
            end else begin
                reply_error<=cfg_response_error;
                if(cfg_response_error==0)case(cfg_command)
                1:begin
                    owner_active[qi]<=1;owner_cookie[qi]<={snapshot[7],snapshot[6]};
                    owner_epoch[qi]<=cfg_epoch;owner_pd[qi]<=cfg_pd;owner_dma[qi]<=cfg_dma_base;
                    owner_depth[qi]<=cfg_log_depth;owner_producer[qi]<=0;reply_flags<=7;
                end
                2:owner_producer[qi]<=cfg_producer;
                3,0:begin
                    owner_active[qi]<=0;owner_cookie[qi]<=0;owner_pd[qi]<=0;owner_dma[qi]<=0;
                    owner_depth[qi]<=0;owner_producer[qi]<=0;reply_flags<=snapshot[1]==4 ? 63:31;
                    // Epoch watermark remains; retire never authorizes reuse.
                end
                default:begin fatal<=1;owner_tainted[qi]<=1;reply_error<=ERR_UNCERTAIN;end
                endcase
            end
        end
    end
end
endmodule
`resetall
