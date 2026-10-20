// SPDX-License-Identifier: BSD-2-Clause-Views
// RRP1: actual native replay-policy mailbox, not a shadow configuration bank.
// Full SQ cookie/PD/epoch comes from the SAME trusted SQC1 owner table. Its
// guard prevents owner retirement until real policy readback and host ACK.
`resetall
`timescale 1ns/1ps
`default_nettype none
module rocev2_retry_mmio #(parameter CLOCK_PERIOD_PS=4000)(
    input wire clk,input wire rst,input wire parent_fault,
    output wire [23:0] owner_query_qpn,input wire [63:0] owner_query_cookie,
    input wire [63:0] owner_query_epoch,input wire [15:0] owner_query_pd,input wire owner_query_valid,
    output wire [23:0] cfg_qpn,output wire [15:0] cfg_pd,
    output wire [63:0] cfg_cookie,output wire [63:0] cfg_epoch,
    output wire [4:0] cfg_timeout,output wire [2:0] cfg_retry,output wire [2:0] cfg_rnr_retry,
    output wire cfg_valid,input wire cfg_ready,
    input wire [23:0] rsp_qpn,input wire [15:0] rsp_pd,
    input wire [63:0] rsp_cookie,input wire [63:0] rsp_epoch,
    input wire [4:0] rsp_timeout,input wire [2:0] rsp_retry,input wire [2:0] rsp_rnr_retry,
    input wire [7:0] rsp_error,input wire rsp_valid,output wire rsp_ready,
    output wire [7:0] queue_guard,output wire busy,output reg fault=0,
    input wire [11:0] s_axil_awaddr,input wire [2:0] s_axil_awprot,
    input wire s_axil_awvalid,output wire s_axil_awready,
    input wire [31:0] s_axil_wdata,input wire [3:0] s_axil_wstrb,
    input wire s_axil_wvalid,output wire s_axil_wready,
    output wire [1:0] s_axil_bresp,output wire s_axil_bvalid,input wire s_axil_bready,
    input wire [11:0] s_axil_araddr,input wire [2:0] s_axil_arprot,
    input wire s_axil_arvalid,output wire s_axil_arready,
    output wire [31:0] s_axil_rdata,output wire [1:0] s_axil_rresp,
    output wire s_axil_rvalid,input wire s_axil_rready
);
localparam IDLE=0,OFFER=1,WAIT=2,REPLY=3;
reg [1:0] state=IDLE;
reg [31:0] stage[0:7],snapshot[0:7],reply_words[0:7];
reg [63:0] epoch=0;
reg [31:0] last_sequence=0;
reg [7:0] error=0;
wire [11:0] wa,ra;wire [31:0] wd;wire [3:0] ws;
wire we,re;reg [31:0] rd;
wire write_stage=wa>=12'h040 && wa<=12'h05c;
wire read_stage=ra>=12'h040 && ra<=12'h05c;
wire read_reply=ra>=12'h080 && ra<=12'h09c;
wire wack=we && wa[1:0]==0 && (write_stage || wa==12'h010 || wa==12'h014);
wire rack=re && ra[1:0]==0 && (read_stage || read_reply || ra==0 || ra==4 || ra==8 ||
    ra==12 || ra==24 || ra==28 || ra==12'h0a0 || ra==12'h0a4 || ra==12'h0a8);
assign owner_query_qpn=state==IDLE ? stage[1][23:0] : snapshot[1][23:0];
wire stage_known=(^{stage[0],stage[1],stage[2],stage[3],stage[4],stage[5],stage[6],stage[7],
    owner_query_cookie,owner_query_epoch,owner_query_pd,owner_query_valid})!==1'bx;
wire shape_ok=stage_known && stage[0]!=0 && stage[1]<8 && stage[2]!=0 && stage[2]<=65535 &&
    stage[3]<32 && stage[4]<8 && stage[5]<8 && {stage[7],stage[6]}!=0;
wire actual_owner=owner_query_valid && owner_query_cookie=={stage[7],stage[6]} &&
    owner_query_pd==stage[2] && owner_query_epoch!=0;
wire available=state==IDLE && !fault && parent_fault===1'b0 && last_sequence!=32'hffffffff;
wire offered_guard=we && wack && wa==12'h010 && ws==15 && available && shape_ok && actual_owner &&
    stage[0]==last_sequence+1 && wd==stage[0];
assign queue_guard=(fault || parent_fault!==1'b0) ? 8'hff :
    state!=IDLE ? (8'h01<<snapshot[1][2:0]) : offered_guard ? (8'h01<<stage[1][2:0]) : 0;
assign busy=state!=IDLE || fault;
assign cfg_qpn=snapshot[1][23:0];assign cfg_pd=snapshot[2][15:0];
assign cfg_timeout=snapshot[3][4:0];assign cfg_retry=snapshot[4][2:0];assign cfg_rnr_retry=snapshot[5][2:0];
assign cfg_cookie={snapshot[7],snapshot[6]};assign cfg_epoch=epoch;
assign cfg_valid=state==OFFER && !rst;
assign rsp_ready=state==WAIT && !rst;
wire response_match=(^{rsp_qpn,rsp_pd,rsp_cookie,rsp_epoch,rsp_timeout,rsp_retry,rsp_rnr_retry,rsp_error})!==1'bx &&
    rsp_qpn==cfg_qpn && rsp_pd==cfg_pd && rsp_cookie==cfg_cookie && rsp_epoch==cfg_epoch &&
    rsp_timeout==cfg_timeout && rsp_retry==cfg_retry && rsp_rnr_retry==cfg_rnr_retry;
always @*begin
    rd=0;
    if(read_stage && ra[1:0]==0)rd=stage[(ra-12'h040)>>2];
    else if(read_reply && ra[1:0]==0 && state==REPLY)rd=reply_words[(ra-12'h080)>>2];
    else case(ra)
    0:rd=32'h52525031;4:rd=32'h00010000;8:rd=1;
    12:rd={28'd0,fault,state==REPLY,state!=IDLE,available};
    24:rd=last_sequence;28:rd=CLOCK_PERIOD_PS;
    12'h0a0:rd=state==REPLY ? epoch[31:0] : 0;
    12'h0a4:rd=state==REPLY ? epoch[63:32] : 0;
    12'h0a8:rd={24'd0,error};
    default:rd=0;
    endcase
end
axil_reg_if #(.DATA_WIDTH(32),.ADDR_WIDTH(12),.STRB_WIDTH(4),.TIMEOUT(8)) registers(
    .clk(clk),.rst(rst),
    .s_axil_awaddr(s_axil_awaddr),.s_axil_awprot(s_axil_awprot),.s_axil_awvalid(s_axil_awvalid),.s_axil_awready(s_axil_awready),
    .s_axil_wdata(s_axil_wdata),.s_axil_wstrb(s_axil_wstrb),.s_axil_wvalid(s_axil_wvalid),.s_axil_wready(s_axil_wready),
    .s_axil_bresp(s_axil_bresp),.s_axil_bvalid(s_axil_bvalid),.s_axil_bready(s_axil_bready),
    .s_axil_araddr(s_axil_araddr),.s_axil_arprot(s_axil_arprot),.s_axil_arvalid(s_axil_arvalid),.s_axil_arready(s_axil_arready),
    .s_axil_rdata(s_axil_rdata),.s_axil_rresp(s_axil_rresp),.s_axil_rvalid(s_axil_rvalid),.s_axil_rready(s_axil_rready),
    .reg_wr_addr(wa),.reg_wr_data(wd),.reg_wr_strb(ws),.reg_wr_en(we),.reg_wr_wait(1'b0),.reg_wr_ack(wack),
    .reg_rd_addr(ra),.reg_rd_en(re),.reg_rd_data(rd),.reg_rd_wait(1'b0),.reg_rd_ack(rack));
integer i,b;
always @(posedge clk)begin
    if(rst)begin
        state<=IDLE;epoch<=0;last_sequence<=0;error<=0;fault<=0;
        for(i=0;i<8;i=i+1)begin stage[i]<=0;snapshot[i]<=0;reply_words[i]<=0;end
    end else begin
        if(parent_fault!==1'b0 || (re && !rack) || (we && !wack))fault<=1;
        if(we && wack)begin
            if(write_stage)begin
                for(b=0;b<4;b=b+1)if(ws[b])stage[(wa-12'h040)>>2][b*8+:8]<=wd[b*8+:8];
            end else if(wa==12'h010)begin
                if(ws!==4'hf || !available || !shape_ok || !actual_owner ||
                    stage[0]!=last_sequence+1 || wd!=stage[0])fault<=1;
                else begin
                    for(i=0;i<8;i=i+1)snapshot[i]<=stage[i];
                    epoch<=owner_query_epoch;last_sequence<=stage[0];error<=0;state<=OFFER;
                end
            end else if(wa==12'h014)begin
                if(ws!==4'hf || state!=REPLY || wd!=snapshot[0])fault<=1;
                else state<=IDLE;
            end
        end
        if(cfg_valid && cfg_ready)state<=WAIT;
        if(rsp_valid && rsp_ready)begin
            if(!response_match || rsp_error!=0)begin fault<=1;error<=8'h80;end
            else begin
                reply_words[0]<=snapshot[0];reply_words[1]<={8'd0,rsp_qpn};reply_words[2]<={16'd0,rsp_pd};
                reply_words[3]<={27'd0,rsp_timeout};reply_words[4]<={29'd0,rsp_retry};reply_words[5]<={29'd0,rsp_rnr_retry};
                reply_words[6]<=rsp_cookie[31:0];reply_words[7]<=rsp_cookie[63:32];
            end
            state<=REPLY;
        end else if(rsp_valid && state!=WAIT)fault<=1;
    end
end
endmodule
`resetall
