// SPDX-License-Identifier: BSD-2-Clause-Views
// Copyright (c) 2026 jyohukuchan
// Prototype AXI-Lite32 mailbox for rocev2_mr_control. Not old ROC2 BAR ABI.
// A doorbell snapshots ALL staging words; staging edits cannot mutate a queued
// command. Reply fields stay owned until an exact-sequence ACK. No reset CSR.
// Corundum AXI adapter handles independent AW/W and read/write backpressure.
`resetall
`timescale 1ns/1ps
`default_nettype none
module rocev2_control_regs #(
    parameter ADDR_WIDTH=12,
    parameter QP_TX_ENABLE=0,
    parameter SEND_ENABLE=0,
    parameter RECV_ENABLE=0,
    parameter RNR_ENABLE=0,
    parameter RECV_RETIRE_ENABLE=0,
    parameter RECV_CQ_ENABLE=0,
    parameter REQUEST_CQ_ENABLE=0,
    parameter SEPARATE_RQ_ENABLE=0,
    parameter IMMEDIATE_ENABLE=0
)(
    input wire clk,
    input wire rst,
    input wire [ADDR_WIDTH-1:0] s_axil_awaddr,
    input wire [2:0] s_axil_awprot,
    input wire s_axil_awvalid,
    output wire s_axil_awready,
    input wire [31:0] s_axil_wdata,
    input wire [3:0] s_axil_wstrb,
    input wire s_axil_wvalid,
    output wire s_axil_wready,
    output wire [1:0] s_axil_bresp,
    output wire s_axil_bvalid,
    input wire s_axil_bready,
    input wire [ADDR_WIDTH-1:0] s_axil_araddr,
    input wire [2:0] s_axil_arprot,
    input wire s_axil_arvalid,
    output wire s_axil_arready,
    output wire [31:0] s_axil_rdata,
    output wire [1:0] s_axil_rresp,
    output wire s_axil_rvalid,
    input wire s_axil_rready,
    output wire [7:0] command,
    output wire [31:0] command_sequence,
    output wire [63:0] cookie,
    output wire [2:0] slot,
    output wire [31:0] key,
    output wire [15:0] pd,
    output wire [63:0] virtual_address,
    output wire [31:0] length,
    output wire [3:0] access,
    output wire [11:0] first_offset,
    output wire [7:0] page_index,
    output wire [63:0] dma_page,
    output wire [2:0] qp_number,
    output wire [23:0] peer_qp_number,
    output wire [31:0] local_ip,
    output wire [31:0] peer_ip,
    output wire [23:0] rx_psn,
    output wire [23:0] tx_psn,
    output reg command_valid=0,
    input wire command_ready,
    input wire [7:0] response_command,
    input wire [31:0] response_sequence,
    input wire [63:0] response_cookie,
    input wire [2:0] response_slot,
    input wire [31:0] response_key,
    input wire [7:0] response_error,
    input wire [7:0] response_flags,
    input wire response_valid,
    output reg response_ready=0,
    input wire control_busy,
    input wire admission_pause,
    input wire fatal,
    input wire [7:0] fatal_code,
    input wire epoch_ready,
    input wire qp_configured,
    input wire run_requested,
    input wire parent_dma_drained,
    input wire endpoint_quiescent,
    input wire endpoint_fault,
    input wire [7:0] building,
    input wire [7:0] active,
    input wire [7:0] tainted,
    input wire [31:0] last_sequence,
    output reg mmio_error=0,
    output reg [31:0] last_queued_sequence=0
);
wire [ADDR_WIDTH-1:0] wr_addr,rd_addr;
wire [31:0] wr_data;
wire [3:0] wr_strb;
wire wr_en,rd_en,wr_ack,rd_ack;
reg [31:0] rd_data;
reg [31:0] staging[0:20],snapshot[0:20];
wire write_stage=wr_addr>=32'h20 && wr_addr<=32'h70;
wire read_stage=rd_addr>=32'h20 && rd_addr<=32'h70;
wire write_known=write_stage || wr_addr==32'h10 || wr_addr==32'h14 || wr_addr==32'h18;
wire read_known=read_stage || rd_addr==0 || rd_addr==4 || rd_addr==8 || rd_addr==12 || rd_addr==28 ||
    (rd_addr>=32'h80 && rd_addr<=32'ha8);
assign wr_ack=wr_en && wr_addr[1:0]==0 && write_known;
assign rd_ack=rd_en && rd_addr[1:0]==0 && read_known;
wire available=command_ready && !command_valid && !response_valid && !control_busy && !fatal && !endpoint_fault && !mmio_error;
wire staged_shape=staging[0]!=0 && staging[1]>=1 && staging[1]<=(QP_TX_ENABLE ? 9 : 8) &&
    {staging[3],staging[2]}!=0 && staging[4][31:3]==0 && staging[6][31:16]==0 &&
    staging[7][31:4]==0 && staging[11][31:12]==0 && staging[12][31:8]==0 &&
    staging[15][31:3]==0 && staging[16][31:24]==0 && staging[19][31:24]==0 && staging[20][31:24]==0;
wire [31:0] status={20'd0,endpoint_fault,endpoint_quiescent,parent_dma_drained,mmio_error,
    run_requested,qp_configured,epoch_ready,fatal,admission_pause,response_valid,
    (control_busy || command_valid),available};
assign command_sequence=snapshot[0];
assign command=snapshot[1][7:0];
assign cookie={snapshot[3],snapshot[2]};
assign slot=snapshot[4][2:0];
assign key=snapshot[5];
assign pd=snapshot[6][15:0];
assign access=snapshot[7][3:0];
assign virtual_address={snapshot[9],snapshot[8]};
assign length=snapshot[10];
assign first_offset=snapshot[11][11:0];
assign page_index=snapshot[12][7:0];
assign dma_page={snapshot[14],snapshot[13]};
assign qp_number=snapshot[15][2:0];
assign peer_qp_number=snapshot[16][23:0];
assign local_ip=snapshot[17];
assign peer_ip=snapshot[18];
assign rx_psn=snapshot[19][23:0];
assign tx_psn=snapshot[20][23:0];
initial if(IMMEDIATE_ENABLE && (!QP_TX_ENABLE || !SEND_ENABLE || !RECV_ENABLE ||
    !RNR_ENABLE || !RECV_RETIRE_ENABLE || !RECV_CQ_ENABLE || !REQUEST_CQ_ENABLE || !SEPARATE_RQ_ENABLE))
    $fatal(1,"Immediate capability requires the complete matched native profile");

axil_reg_if #(.DATA_WIDTH(32),.ADDR_WIDTH(ADDR_WIDTH),.STRB_WIDTH(4),.TIMEOUT(8)) bus (
    .clk(clk),.rst(rst),
    .s_axil_awaddr(s_axil_awaddr),.s_axil_awprot(s_axil_awprot),.s_axil_awvalid(s_axil_awvalid),.s_axil_awready(s_axil_awready),
    .s_axil_wdata(s_axil_wdata),.s_axil_wstrb(s_axil_wstrb),.s_axil_wvalid(s_axil_wvalid),.s_axil_wready(s_axil_wready),
    .s_axil_bresp(s_axil_bresp),.s_axil_bvalid(s_axil_bvalid),.s_axil_bready(s_axil_bready),
    .s_axil_araddr(s_axil_araddr),.s_axil_arprot(s_axil_arprot),.s_axil_arvalid(s_axil_arvalid),.s_axil_arready(s_axil_arready),
    .s_axil_rdata(s_axil_rdata),.s_axil_rresp(s_axil_rresp),.s_axil_rvalid(s_axil_rvalid),.s_axil_rready(s_axil_rready),
    .reg_wr_addr(wr_addr),.reg_wr_data(wr_data),.reg_wr_strb(wr_strb),.reg_wr_en(wr_en),.reg_wr_wait(1'b0),.reg_wr_ack(wr_ack),
    .reg_rd_addr(rd_addr),.reg_rd_en(rd_en),.reg_rd_data(rd_data),.reg_rd_wait(1'b0),.reg_rd_ack(rd_ack));

always @* begin
    rd_data=0;
    if(read_stage && rd_addr[1:0]==0) rd_data=staging[(rd_addr-32'h20)>>2];
    else case(rd_addr)
        0: rd_data=32'h524e4331;
        4: rd_data=32'h00010000;
        8: rd_data=(QP_TX_ENABLE ? 3 : 1) | (SEND_ENABLE ? 4 : 0) | (RECV_ENABLE ? 8 : 0) | (RNR_ENABLE ? 16 : 0) | (RECV_RETIRE_ENABLE ? 32 : 0) | (RECV_CQ_ENABLE ? 64 : 0) | (REQUEST_CQ_ENABLE ? 128 : 0) | (SEPARATE_RQ_ENABLE ? 256 : 0) | (IMMEDIATE_ENABLE ? 512 : 0);
        12: rd_data=status;
        28: rd_data=last_queued_sequence;
        'h80: rd_data=response_sequence;
        'h84: rd_data={24'd0,response_command};
        'h88: rd_data=response_cookie[31:0];
        'h8c: rd_data=response_cookie[63:32];
        'h90: rd_data={29'd0,response_slot};
        'h94: rd_data=response_key;
        'h98: rd_data={24'd0,response_error};
        'h9c: rd_data={24'd0,response_flags};
        'ha0: rd_data={8'd0,tainted,active,building};
        'ha4: rd_data=last_sequence;
        'ha8: rd_data={24'd0,fatal_code};
        default: rd_data=0;
    endcase
end
integer i,b;
always @(posedge clk) begin
    if(rst) begin
        command_valid<=0;response_ready<=0;mmio_error<=0;last_queued_sequence<=0;
        for(i=0;i<21;i=i+1) begin staging[i]<=0;snapshot[i]<=0;end
    end else begin
        response_ready<=0;
        if(command_valid && command_ready) command_valid<=0;
        // This pinned Corundum adapter returns AXI OKAY even on its timeout.
        // Software MUST check sticky MMIO_ERROR, never infer command success
        // from bus completion. Unknown/unaligned reads return0 and set it too.
        if((wr_en && !wr_ack) || (rd_en && !rd_ack)) mmio_error<=1;
        if(wr_ack) begin
            if(write_stage) begin
                for(b=0;b<4;b=b+1) if(wr_strb[b]) staging[(wr_addr-32'h20)>>2][b*8+:8]<=wr_data[b*8+:8];
            end else case(wr_addr)
                'h10: begin
                    if(wr_strb!=15 || wr_data!=1 || !available || !staged_shape) mmio_error<=1;
                    else begin
                        for(i=0;i<21;i=i+1) snapshot[i]<=staging[i];
                        command_valid<=1;last_queued_sequence<=staging[0];
                    end
                end
                'h14: begin
                    if(wr_strb==15 && response_valid && wr_data==response_sequence) response_ready<=1;
                    else mmio_error<=1;
                end
                'h18: begin
                    // Parser-error recovery ONLY. Does not reset/cancel DMA,
                    // clear a controller fault or manufacture memory proof.
                    if(wr_strb==15 && wr_data==1 && command_ready && !command_valid && !response_valid &&
                        !control_busy && !fatal && !endpoint_fault && parent_dma_drained && endpoint_quiescent) mmio_error<=0;
                    else mmio_error<=1;
                end
                default: mmio_error<=1;
            endcase
        end
    end
end
initial begin if(ADDR_WIDTH<8) begin $error("Control register region needs at least256bytes");$finish;end end
endmodule
`resetall
