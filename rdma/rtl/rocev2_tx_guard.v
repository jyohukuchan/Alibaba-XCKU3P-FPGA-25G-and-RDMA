// SPDX-License-Identifier: BSD-2-Clause-Views
// Place before the RDMA Ethernet framer, not on the merged host/MAC stream.
// halt closes admission of new IP frames; already admitted frames drain.
// Reset this block only with the whole NIC, never with transport core_reset.
// completion must be a one-cycle pulse for an accepted injected MAC SFD
// completion (tag MSB=0); host completions must NOT enter this input.
// Quiescence concerns injected frames only: host Ethernet can keep running.
// Target contract: 250MHz core, >=25Gb/s MAC, IP frames <=MAX_IPV4_BYTES.
// SFD completion is not EOF: retain a full conservative wire-tail interval.
`resetall
`timescale 1ns / 1ps
`default_nettype none

module rocev2_tx_guard #(
    parameter MAX_IPV4_BYTES=8192,
    parameter TAIL_CYCLES=1024,
    parameter PENDING_WIDTH=16
)(
    input wire clk,
    input wire rst,
    input wire halt,
    input wire completion,
    input wire [127:0] s_axis_tdata,
    input wire [15:0] s_axis_tkeep,
    input wire s_axis_tvalid,
    output wire s_axis_tready,
    input wire s_axis_tlast,
    output wire [127:0] m_axis_tdata,
    output wire [15:0] m_axis_tkeep,
    output wire m_axis_tvalid,
    input wire m_axis_tready,
    output wire m_axis_tlast,
    output wire quiescent,
    output reg fault=0,
    output reg [PENDING_WIDTH-1:0] pending_frames=0,
    output reg [31:0] admitted_frames=0,
    output reg [31:0] completed_frames=0
);

// Maximum IP + Ethernet header/FCS/preamble/IFG, rounded up at 25G/250MHz.
localparam MIN_TAIL_CYCLES=((MAX_IPV4_BYTES+14+4+8+12)*2+24)/25;
localparam TAIL_WIDTH=$clog2(TAIL_CYCLES+1);
localparam [TAIL_WIDTH-1:0] TAIL_RELOAD=TAIL_CYCLES[TAIL_WIDTH-1:0];
localparam [16:0] MAX_BYTES=MAX_IPV4_BYTES[16:0];
initial begin
    if (MAX_IPV4_BYTES<1 || MAX_IPV4_BYTES>65535 || TAIL_CYCLES<MIN_TAIL_CYCLES ||
            TAIL_CYCLES<1 || PENDING_WIDTH<2 || PENDING_WIDTH>24) begin
        $error("Invalid 25G transmit guard bounds"); $finish;
    end
end

reg in_frame=0;
reg [15:0] frame_bytes=0;
reg [TAIL_WIDTH-1:0] tail_left=0;
reg [127:0] data_reg=0;
reg [15:0] keep_reg=0;
reg valid_reg=0,last_reg=0;
reg [4:0] beat_bytes;
integer lane;
always @* begin
    beat_bytes=0;
    for (lane=0;lane<16;lane=lane+1) beat_bytes=beat_bytes+{4'd0,s_axis_tkeep[lane]};
end
wire [16:0] next_bytes=(in_frame ? {1'b0,frame_bytes} : 17'd0)+{12'd0,beat_bytes};
wire has_capacity=!(&pending_frames);
assign s_axis_tready=!rst && (in_frame || (!halt && !fault && has_capacity)) &&
    (!valid_reg || m_axis_tready);
assign m_axis_tdata=data_reg;
assign m_axis_tkeep=keep_reg;
assign m_axis_tvalid=valid_reg;
assign m_axis_tlast=last_reg;
wire take=s_axis_tvalid && s_axis_tready;
wire start=take && !in_frame;
assign quiescent=!rst && halt && !fault && !in_frame && !valid_reg &&
    pending_frames==0 && tail_left==0;

always @(posedge clk) begin
    if (rst) begin
        in_frame<=0; frame_bytes<=0; tail_left<=0;
        data_reg<=0; keep_reg<=0; valid_reg<=0; last_reg<=0;
        fault<=0; pending_frames<=0; admitted_frames<=0; completed_frames<=0;
    end else begin
        if (m_axis_tready) valid_reg<=0;
        if (take) begin
            data_reg<=s_axis_tdata; keep_reg<=s_axis_tkeep;
            valid_reg<=1; last_reg<=s_axis_tlast;
            in_frame<=!s_axis_tlast; frame_bytes<=next_bytes[15:0];
            if (next_bytes>MAX_BYTES || s_axis_tkeep==0 ||
                    (!s_axis_tlast && s_axis_tkeep!=16'hffff) ||
                    (({1'b0,s_axis_tkeep}+17'd1)&{1'b0,s_axis_tkeep})!=0)
                fault<=1;
        end
        if (tail_left!=0) tail_left<=tail_left-1'b1;
        if (completion) begin
            tail_left<=TAIL_RELOAD;
            if (pending_frames==0) fault<=1;
            else completed_frames<=completed_frames+1'b1;
        end
        if (start) admitted_frames<=admitted_frames+1'b1;
        case ({start,completion})
            2'b10: pending_frames<=pending_frames+1'b1;
            2'b01: if (pending_frames!=0) pending_frames<=pending_frames-1'b1;
            default: ;
        endcase
    end
end
endmodule
`resetall
