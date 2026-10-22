// SPDX-License-Identifier: BSD-2-Clause-Views
// Retain the actual selected1000 certificate for privileged software.
// Notification ACK NEVER clears native quarantine, cancels work, produces a
// WC, retires references or certifies STOP/global drain/unpin. The producer
// must be the actual authenticated native abort/cancel join, not host data.
`resetall
`timescale 1ns/1ps
`default_nettype none
module rocev2_fatal_event_mmio #(
    parameter ADDR_WIDTH=12,parameter MAX_QPS=8
)(
    input wire clk,input wire rst,input wire parent_fault,
    input wire [999:0] s_selected,input wire s_selected_valid,output wire s_selected_ready,
    output wire configuration_guard,output wire [MAX_QPS-1:0] queue_guard,
    output reg fault=0,output reg [7:0] fault_code=0,
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
reg visible=0;
reg [999:0] saved=0;
reg [31:0] event_sequence=0,last_ack=0;
reg [63:0] last_serial=0;
wire [23:0] qpn=s_selected[447:424];
wire [63:0] serial=s_selected[843:780];
wire [7:0] syndrome=s_selected[899:892];
wire known=(^s_selected)!==1'bx;
// The producer already proved native/HLS/MAC/cancel ownership. Check the
// retained envelope here; software independently validates every inner bit.
wire envelope_ok=known && s_selected[999:992]==7 && s_selected[991:984]==0 &&
    s_selected[983:960]==s_selected[927:904] && s_selected[959:952]==0 &&
    s_selected[903:900]==0 && syndrome>=8'h61 && syndrome<=8'h63 &&
    s_selected[891:868]==s_selected[867:844] && serial!=0 && qpn<MAX_QPS &&
    s_selected[463:448]!=0 && s_selected[527:464]!=0 && s_selected[591:528]!=0;
wire halted=fault || parent_fault!==1'b0;
assign s_selected_ready=!rst && !halted && !visible && event_sequence!=32'hffffffff &&
    envelope_ok && serial>last_serial;
assign configuration_guard=halted || visible || s_selected_valid!==1'b0;
assign queue_guard=halted ? {MAX_QPS{1'b1}} : visible ?
    ({{(MAX_QPS-1){1'b0}},1'b1}<<saved[447:424]) : s_selected_valid!==1'b0 ?
    (envelope_ok ? ({{(MAX_QPS-1){1'b0}},1'b1}<<qpn):{MAX_QPS{1'b1}}):0;
wire [ADDR_WIDTH-1:0] wa,ra;wire [31:0] wd;wire [3:0] ws;
wire we,re;reg [31:0] rd;
wire record_read=ra>=12'h040 && ra<=12'h0bc;
wire read_known=record_read || ra==0 || ra==4 || ra==8 || ra==12 ||
    ra==12'h014 || ra==12'h018 || ra==12'h01c;
wire write_ack=we && wa==12'h010;
wire read_ack=re && ra[1:0]==0 && read_known;
always @*begin
    rd=0;
    if(record_read && ra[1:0]==0 && visible)rd=({24'd0,saved}>>(((ra-12'h040)>>2)*32));
    else case(ra)
    0:rd=32'h46454331;
    4:rd=32'h00010000;
    8:rd=32'h0000000f;
    12:rd={29'd0,event_sequence==32'hffffffff,halted,visible};
    12'h014:rd=last_ack;
    12'h018:rd=event_sequence;
    12'h01c:rd={24'd0,fault_code};
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
initial if(ADDR_WIDTH!=12 || MAX_QPS!=8)$fatal(1,"unreviewed fatal-event geometry");
always @(posedge clk)begin
    if(rst)begin
        visible<=0;saved<=0;event_sequence<=0;last_ack<=0;last_serial<=0;fault<=0;fault_code<=0;
    end else begin
        if(parent_fault!==1'b0)begin fault<=1;fault_code<=8'he1;end
        if(!visible && (s_selected_valid!==1'b0 && s_selected_valid!==1'b1 ||
            s_selected_valid && (!envelope_ok || serial<=last_serial || event_sequence==32'hffffffff)))begin
            fault<=1;fault_code<=8'he2;
        end
        if(s_selected_valid && s_selected_ready)begin
            saved<=s_selected;visible<=1;event_sequence<=event_sequence+1'b1;last_serial<=serial;
        end
        if(we)begin
            if(!write_ack || ws!==4'hf || (^wd)===1'bx || wd==0 || halted)begin fault<=1;fault_code<=8'he3;end
            else if(visible && wd==event_sequence)begin last_ack<=event_sequence;visible<=0;end
            else if(wd!=last_ack)begin fault<=1;fault_code<=8'he4;end
        end
        if(re && !read_ack)begin fault<=1;fault_code<=8'he5;end
    end
end
endmodule
`resetall
