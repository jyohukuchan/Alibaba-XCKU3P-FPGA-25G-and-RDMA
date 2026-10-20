// SPDX-License-Identifier: BSD-2-Clause-Views
// Copyright (c) 2026 jyohukuchan
// Conservative proof at the actual generic PCIe DMA engine boundary.
// Combine with leaf/backend and descriptor-mux quiescence, never use alone
// as MR revocation. Global reset is NOT a certificate to release old pages.
`resetall
`timescale 1ns/1ps
`default_nettype none
module rocev2_pcie_parent_guard #(
    parameter SEG_COUNT=2,
    parameter COUNT_WIDTH=16
)(
    input wire clk,
    input wire rst,
    input wire rd_busy,
    input wire wr_busy,
    input wire rd_desc_valid,
    input wire rd_desc_ready,
    input wire wr_desc_valid,
    input wire wr_desc_ready,
    input wire rd_status_valid,
    input wire [3:0] rd_status_error,
    input wire wr_status_valid,
    input wire [3:0] wr_status_error,
    input wire [SEG_COUNT-1:0] ram_wr_cmd_valid,
    input wire [SEG_COUNT-1:0] ram_wr_cmd_ready,
    input wire [SEG_COUNT-1:0] ram_wr_done,
    input wire [SEG_COUNT-1:0] ram_rd_cmd_valid,
    input wire [SEG_COUNT-1:0] ram_rd_cmd_ready,
    input wire [SEG_COUNT-1:0] ram_rd_resp_valid,
    input wire [SEG_COUNT-1:0] ram_rd_resp_ready,
    input wire tlp_activity,
    input wire error_event,
    output wire drained,
    output reg fault=0,
    output reg [3:0] fault_code=0
);
initial begin
    if(SEG_COUNT<1 || COUNT_WIDTH<2) begin
        $error("Invalid PCIe parent guard geometry");$finish;
    end
end
reg [COUNT_WIDTH-1:0] rd_pending=0,wr_pending=0;
reg [COUNT_WIDTH-1:0] ram_wr_pending[0:SEG_COUNT-1];
reg [COUNT_WIDTH-1:0] ram_rd_pending[0:SEG_COUNT-1];
wire rd_push=rd_desc_valid && rd_desc_ready;
wire wr_push=wr_desc_valid && wr_desc_ready;
wire [SEG_COUNT-1:0] ram_empty,ram_bad;
wire desc_bad=(rd_status_valid && rd_pending==0) ||
    (wr_status_valid && wr_pending==0) ||
    (rd_push && !rd_status_valid && (&rd_pending)) ||
    (wr_push && !wr_status_valid && (&wr_pending));
wire live_error=error_event || (rd_status_valid && rd_status_error!=0) ||
    (wr_status_valid && wr_status_error!=0);
genvar n;
generate for(n=0;n<SEG_COUNT;n=n+1) begin : segments
    wire wp=ram_wr_cmd_valid[n] && ram_wr_cmd_ready[n];
    wire wo=ram_wr_done[n];
    wire rp=ram_rd_cmd_valid[n] && ram_rd_cmd_ready[n];
    wire ro=ram_rd_resp_valid[n] && ram_rd_resp_ready[n];
    assign ram_empty[n]=ram_wr_pending[n]==0 && ram_rd_pending[n]==0;
    // Permit a real same-cycle RAM accept/completion, not a fabricated DMA
    // descriptor status. Retain counters on invalid overflow/underflow.
    assign ram_bad[n]=(wo && !wp && ram_wr_pending[n]==0) ||
        (ro && !rp && ram_rd_pending[n]==0) ||
        (wp && !wo && (&ram_wr_pending[n])) ||
        (rp && !ro && (&ram_rd_pending[n]));
    initial begin ram_wr_pending[n]=0;ram_rd_pending[n]=0;end
    always @(posedge clk) begin
        if(rst) begin ram_wr_pending[n]<=0;ram_rd_pending[n]<=0;end
        else if(!ram_bad[n]) begin
            case({wp,wo})
                2'b10:ram_wr_pending[n]<=ram_wr_pending[n]+1'b1;
                2'b01:ram_wr_pending[n]<=ram_wr_pending[n]-1'b1;
                default:begin end
            endcase
            case({rp,ro})
                2'b10:ram_rd_pending[n]<=ram_rd_pending[n]+1'b1;
                2'b01:ram_rd_pending[n]<=ram_rd_pending[n]-1'b1;
                default:begin end
            endcase
        end
    end
end endgenerate

// Busy outputs are registered in dma_if_pcie; raw offers additionally close
// the first-accept and last-status cycles. No current RAM/address decision
// or predicted subtraction participates in this public release boundary.
assign drained=!rst && !fault && !live_error && !desc_bad && !(|ram_bad) &&
    !rd_busy && !wr_busy && rd_pending==0 && wr_pending==0 && (&ram_empty) &&
    !rd_desc_valid && !wr_desc_valid && !rd_status_valid && !wr_status_valid &&
    !(|ram_wr_cmd_valid) && !(|ram_wr_done) && !(|ram_rd_cmd_valid) &&
    !(|ram_rd_resp_valid) && !tlp_activity;
always @(posedge clk) begin
    if(rst) begin
        rd_pending<=0;wr_pending<=0;fault<=0;fault_code<=0;
    end else begin
        if(!desc_bad) begin
            case({rd_push,rd_status_valid})
                2'b10:rd_pending<=rd_pending+1'b1;
                2'b01:rd_pending<=rd_pending-1'b1;
                default:begin end
            endcase
            case({wr_push,wr_status_valid})
                2'b10:wr_pending<=wr_pending+1'b1;
                2'b01:wr_pending<=wr_pending-1'b1;
                default:begin end
            endcase
        end
        if(!fault && (live_error || desc_bad || (|ram_bad))) begin
            fault<=1;
            fault_code<=live_error ? 4'd1 : desc_bad ? 4'd2 : 4'd3;
        end
    end
end
endmodule
`resetall
