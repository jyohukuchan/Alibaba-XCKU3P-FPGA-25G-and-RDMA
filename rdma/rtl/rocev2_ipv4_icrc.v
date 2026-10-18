// SPDX-License-Identifier: BSD-2-Clause-Views
// IPv4 RoCEv2 framing integrity stage, 128-bit byte-lane order.
// TX input omits ICRC but IP/UDP length fields include its four bytes.
// RX input/output retain ICRC for the upstream HLS extract_icrc stage.
// Complete frames are buffered: rejected RX frames cannot reach memory logic.
// This is not a QP/MR protection engine or an Ethernet-header parser.
`resetall
`timescale 1ns / 1ps
`default_nettype none

module rocev2_ipv4_icrc #(
    parameter TX_MODE = 0,
    parameter MAX_PACKET_BYTES = 8192,
    parameter FIFO_BYTES = 16384
)(
    input  wire         clk,
    input  wire         rst,
    input  wire [127:0] s_axis_tdata,
    input  wire [15:0]  s_axis_tkeep,
    input  wire         s_axis_tvalid,
    output wire         s_axis_tready,
    input  wire         s_axis_tlast,
    input  wire         s_axis_tuser,
    output wire [127:0] m_axis_tdata,
    output wire [15:0]  m_axis_tkeep,
    output wire         m_axis_tvalid,
    input  wire         m_axis_tready,
    output wire         m_axis_tlast,
    output wire         status_good_frame,
    output wire         status_bad_frame,
    output wire         status_overflow
);

initial begin
    if (MAX_PACKET_BYTES > 65520 || FIFO_BYTES < 2*MAX_PACKET_BYTES ||
        (FIFO_BYTES & (FIFO_BYTES-1)) != 0) begin
        $error("ICRC FIFO must be power-of-two and >= two maximum packets");
        $finish;
    end
end

function [15:0] be16;
    input [127:0] data;
    input integer byte_offset;
    begin
        be16 = {data[byte_offset*8 +: 8], data[(byte_offset+1)*8 +: 8]};
    end
endfunction

function [15:0] checksum;
    input [20:0] sum;
    reg [16:0] fold1;
    reg [16:0] fold2;
    begin
        fold1 = {1'b0,sum[15:0]} + {12'b0,sum[20:16]};
        fold2 = {1'b0,fold1[15:0]} + {16'b0,fold1[16]};
        checksum = ~fold2[15:0];
    end
endfunction

// Verification needs only the zero/nonzero checksum result, not the complete
// folded checksum. For a 21-bit nonnegative sum, the first end-around fold
// is at most 0x1001e, so the ONLY value that folds to 0xffff is 0x0ffff.
// Compare low16 against the complement of high5: avoid two carry-propagating
// fold adders plus zero detection on the RX bad-frame critical path.
function valid_ipv4_sum;
    input [20:0] sum;
    begin valid_ipv4_sum = sum[15:0] == ~{11'd0,sum[20:16]}; end
endfunction

// A dense LSB-prefix mask has no 1 immediately above a 0. This is exactly
// equivalent to keep == (1 << popcount(keep))-1 for all 65536 binary masks,
// without a popcount/variable-shift/subtract chain on AXIS ready feedback.
function valid_keep_prefix;
    input [15:0] keep;
    begin valid_keep_prefix = keep != 0 && !(|(keep[15:1] & ~keep[14:0])); end
endfunction

reg [15:0] offset_reg = 0;
reg [15:0] ip_length_reg = 0;
reg [20:0] header_sum_reg = 0;
reg [15:0] checksum_reg = 0;
reg [31:0] crc_reg = 32'hdebb20e3;
reg bad_reg = 0;
reg first_reg = 1;
reg extra_reg = 0;
reg [31:0] extra_crc_reg = 0;
reg extra_bad_reg = 0;

reg [4:0] byte_count;
reg [4:0] crc_bytes;
reg [127:0] masked_data;
reg [31:0] crc_next;
reg [31:0] received_crc;
reg bad_current;
integer i;
wire [15:0] packet_length = first_reg ? be16(s_axis_tdata,2) : ip_length_reg;
wire [20:0] first_header_sum =
    {5'b0,be16(s_axis_tdata,0)} + {5'b0,be16(s_axis_tdata,2)} +
    {5'b0,be16(s_axis_tdata,4)} + {5'b0,be16(s_axis_tdata,6)} +
    {5'b0,be16(s_axis_tdata,8)} + (TX_MODE ? 21'd0 : {5'b0,be16(s_axis_tdata,10)}) +
    {5'b0,be16(s_axis_tdata,12)} + {5'b0,be16(s_axis_tdata,14)};
wire [20:0] full_header_sum = header_sum_reg +
    {5'b0,be16(s_axis_tdata,0)} + {5'b0,be16(s_axis_tdata,2)};
wire [15:0] computed_checksum = checksum(full_header_sum);

wire [31:0] crc_words [4:0];
assign crc_words[0] = crc_reg;
genvar n;
generate
    for (n=1; n<=4; n=n+1) begin : crc_parallel
        lfsr #(
            .LFSR_WIDTH(32), .LFSR_POLY(32'h04c11db7),
            .LFSR_CONFIG("GALOIS"), .LFSR_FEED_FORWARD(0),
            .REVERSE(1), .DATA_WIDTH(n*32), .STYLE("REDUCTION")
        ) crc_inst (
            .data_in(masked_data[n*32-1:0]), .state_in(crc_reg),
            .data_out(), .state_out(crc_words[n])
        );
    end
endgenerate

always @* begin
    byte_count = 0;
    for (i=0; i<16; i=i+1) byte_count = byte_count + {4'd0,s_axis_tkeep[i]};
    masked_data = s_axis_tdata;
    // IP TOS, TTL, checksum; UDP checksum; BTH resv8a before destination QPN.
    if (first_reg) begin
        masked_data[8 +: 8] = 8'hff;
        masked_data[64 +: 8] = 8'hff;
        masked_data[80 +: 16] = 16'hffff;
    end else if (offset_reg == 16) begin
        masked_data[80 +: 16] = 16'hffff;
    end else if (offset_reg == 32) begin
        masked_data[0 +: 8] = 8'hff;
    end
    crc_bytes = s_axis_tlast ? (TX_MODE ? byte_count : (byte_count >= 4 ? byte_count-4 : 0)) : 16;
    case (crc_bytes)
        0: crc_next = crc_words[0];
        4: crc_next = crc_words[1];
        8: crc_next = crc_words[2];
        12: crc_next = crc_words[3];
        16: crc_next = crc_words[4];
        default: crc_next = crc_words[0];
    endcase
    case (byte_count)
        4: received_crc = s_axis_tdata[31:0];
        8: received_crc = s_axis_tdata[63:32];
        12: received_crc = s_axis_tdata[95:64];
        default: received_crc = s_axis_tdata[127:96];
    endcase
    bad_current = bad_reg || s_axis_tuser;
    // Require a dense byte mask, full non-final words and 4-byte packet alignment.
    if (!valid_keep_prefix(s_axis_tkeep) ||
        (!s_axis_tlast && s_axis_tkeep != 16'hffff) || (s_axis_tlast && byte_count[1:0] != 0)) bad_current = 1;
    if (offset_reg >= MAX_PACKET_BYTES) bad_current = 1;
    if (first_reg && (s_axis_tdata[7:0] != 8'h45 || s_axis_tdata[79:72] != 8'd17 ||
        (be16(s_axis_tdata,6) & 16'hbfff) != 0 || packet_length < 48 ||
        packet_length > MAX_PACKET_BYTES || packet_length[1:0] != 0)) bad_current = 1;
    if (!first_reg && offset_reg == 16) begin
        if (be16(s_axis_tdata,6) != 4791 || be16(s_axis_tdata,8) != ip_length_reg-20) bad_current = 1;
        if (!TX_MODE && !valid_ipv4_sum(full_header_sum)) bad_current = 1;
    end
    if (s_axis_tlast) begin
        if ({1'b0,offset_reg}+{12'd0,byte_count} != {1'b0,packet_length}-(TX_MODE ? 17'd4 : 17'd0)) bad_current = 1;
        if (!TX_MODE && (byte_count < 4 || received_crc != ~crc_next)) bad_current = 1;
    end
end

wire fifo_ready;
wire meta_ready;
wire [15:0] meta_checksum;
wire meta_valid;
reg [127:0] staged_data;
reg [15:0] staged_keep;
reg staged_last;
wire staged_bad = extra_reg ? extra_bad_reg : bad_current;
wire staged_valid = extra_reg || s_axis_tvalid;
// Reserve metadata capacity at every TX final beat, including a bad frame.
// Admission must not depend combinationally on CRC/length validity. A bad
// frame may wait for metadata capacity, but never consumes a metadata entry.
wire final_gate = !staged_last || !TX_MODE || meta_ready;
wire fifo_valid = staged_valid && final_gate;
wire fifo_transfer = fifo_valid && fifo_ready;
wire meta_push = TX_MODE && fifo_transfer && staged_last && !staged_bad;
assign s_axis_tready = !extra_reg && fifo_ready && final_gate;

always @* begin
    staged_data = s_axis_tdata;
    staged_keep = s_axis_tkeep;
    staged_last = s_axis_tlast;
    if (extra_reg) begin
        staged_data = {96'b0,extra_crc_reg};
        staged_keep = 16'h000f;
        staged_last = 1;
    end else if (TX_MODE && s_axis_tlast) begin
        case (byte_count)
            4: begin staged_data[63:32] = ~crc_next; staged_keep = 16'h00ff; end
            8: begin staged_data[95:64] = ~crc_next; staged_keep = 16'h0fff; end
            12: begin staged_data[127:96] = ~crc_next; staged_keep = 16'hffff; end
            16: staged_last = 0;
            default: begin end
        endcase
    end
end

always @(posedge clk) begin
    if (rst) begin
        offset_reg <= 0; ip_length_reg <= 0; header_sum_reg <= 0;
        checksum_reg <= 0; crc_reg <= 32'hdebb20e3; bad_reg <= 0;
        first_reg <= 1; extra_reg <= 0; extra_crc_reg <= 0; extra_bad_reg <= 0;
    end else begin
        if (extra_reg && fifo_transfer) extra_reg <= 0;
        if (s_axis_tvalid && s_axis_tready) begin
            if (first_reg) begin
                ip_length_reg <= packet_length;
                header_sum_reg <= first_header_sum;
                checksum_reg <= 0;
            end else if (offset_reg == 16) checksum_reg <= computed_checksum;
            if (s_axis_tlast) begin
                offset_reg <= 0; first_reg <= 1;
                crc_reg <= 32'hdebb20e3; bad_reg <= 0;
                if (TX_MODE && byte_count == 16) begin
                    extra_reg <= 1;
                    extra_crc_reg <= ~crc_next;
                    extra_bad_reg <= bad_current;
                end
            end else begin
                if (offset_reg < 65520) offset_reg <= offset_reg+16;
                first_reg <= 0; crc_reg <= crc_next; bad_reg <= bad_current;
            end
        end
    end
end

// Register the complete FIFO input beat and its bad-frame sideband together.
// The two-entry skid stage retains one beat/cycle and decouples CRC/length
// validation from the BRAM's input setup. Checksum metadata is reserved on
// this stage's admission; its frame follows in order into the frame FIFO.
wire [127:0] buffered_data;
wire [15:0] buffered_keep;
wire buffered_valid, buffered_ready, buffered_last, buffered_bad;
axis_register #(
    .DATA_WIDTH(128), .KEEP_ENABLE(1), .KEEP_WIDTH(16), .LAST_ENABLE(1),
    .ID_ENABLE(0), .ID_WIDTH(1), .DEST_ENABLE(0), .DEST_WIDTH(1),
    .USER_ENABLE(1), .USER_WIDTH(1), .REG_TYPE(2)
) fifo_input_register (
    .clk(clk), .rst(rst),
    .s_axis_tdata(staged_data), .s_axis_tkeep(staged_keep), .s_axis_tvalid(fifo_valid),
    .s_axis_tready(fifo_ready), .s_axis_tlast(staged_last), .s_axis_tid(1'b0),
    .s_axis_tdest(1'b0), .s_axis_tuser(staged_bad),
    .m_axis_tdata(buffered_data), .m_axis_tkeep(buffered_keep), .m_axis_tvalid(buffered_valid),
    .m_axis_tready(buffered_ready), .m_axis_tlast(buffered_last), .m_axis_tid(),
    .m_axis_tdest(), .m_axis_tuser(buffered_bad)
);

wire [127:0] fifo_data;
wire [15:0] fifo_keep;
wire fifo_out_valid;
wire fifo_last;
wire fifo_out_ready = m_axis_tready && (!TX_MODE || meta_valid);
axis_fifo #(
    .DEPTH(FIFO_BYTES), .DATA_WIDTH(128), .KEEP_ENABLE(1), .KEEP_WIDTH(16),
    .LAST_ENABLE(1), .ID_ENABLE(0), .ID_WIDTH(1), .DEST_ENABLE(0), .DEST_WIDTH(1),
    .USER_ENABLE(1), .USER_WIDTH(1), .RAM_PIPELINE(2), .OUTPUT_FIFO_ENABLE(1),
    .FRAME_FIFO(1), .DROP_OVERSIZE_FRAME(1), .DROP_BAD_FRAME(1), .DROP_WHEN_FULL(0)
) packet_fifo (
    .clk(clk), .rst(rst), .s_axis_tdata(buffered_data), .s_axis_tkeep(buffered_keep),
    .s_axis_tvalid(buffered_valid), .s_axis_tready(buffered_ready), .s_axis_tlast(buffered_last),
    .s_axis_tid(1'b0), .s_axis_tdest(1'b0), .s_axis_tuser(buffered_bad),
    .m_axis_tdata(fifo_data), .m_axis_tkeep(fifo_keep), .m_axis_tvalid(fifo_out_valid),
    .m_axis_tready(fifo_out_ready), .m_axis_tlast(fifo_last),
    .m_axis_tid(), .m_axis_tdest(), .m_axis_tuser(), .pause_req(1'b0), .pause_ack(),
    .status_depth(), .status_depth_commit(), .status_overflow(status_overflow),
    .status_bad_frame(status_bad_frame), .status_good_frame(status_good_frame)
);

generate
    if (TX_MODE) begin : tx_metadata
        axis_fifo #(
            .DEPTH(32), .DATA_WIDTH(16), .KEEP_ENABLE(0), .KEEP_WIDTH(1),
            .LAST_ENABLE(0), .ID_ENABLE(0), .ID_WIDTH(1), .DEST_ENABLE(0), .DEST_WIDTH(1),
            .USER_ENABLE(0), .USER_WIDTH(1), .RAM_PIPELINE(1), .FRAME_FIFO(0)
        ) checksum_fifo (
            .clk(clk), .rst(rst), .s_axis_tdata(checksum_reg), .s_axis_tkeep(1'b1),
            .s_axis_tvalid(meta_push), .s_axis_tready(meta_ready), .s_axis_tlast(1'b0),
            .s_axis_tid(1'b0), .s_axis_tdest(1'b0), .s_axis_tuser(1'b0),
            .m_axis_tdata(meta_checksum), .m_axis_tkeep(), .m_axis_tvalid(meta_valid),
            .m_axis_tready(m_axis_tvalid && m_axis_tready && m_axis_tlast), .m_axis_tlast(),
            .m_axis_tid(), .m_axis_tdest(), .m_axis_tuser(), .pause_req(1'b0), .pause_ack(),
            .status_depth(), .status_depth_commit(), .status_overflow(), .status_bad_frame(), .status_good_frame()
        );
    end else begin : rx_metadata
        assign meta_ready = 1;
        assign meta_valid = 1;
        assign meta_checksum = 0;
    end
endgenerate

reg output_first_reg = 1;
always @(posedge clk) begin
    if (rst) output_first_reg <= 1;
    else if (m_axis_tvalid && m_axis_tready) output_first_reg <= m_axis_tlast;
end
reg [127:0] corrected_data;
always @* begin
    corrected_data = fifo_data;
    if (TX_MODE && output_first_reg) begin
        corrected_data[80 +: 8] = meta_checksum[15:8];
        corrected_data[88 +: 8] = meta_checksum[7:0];
    end
end
assign m_axis_tdata = corrected_data;
assign m_axis_tkeep = fifo_keep;
assign m_axis_tvalid = fifo_out_valid && (!TX_MODE || meta_valid);
assign m_axis_tlast = fifo_last;

endmodule
`resetall
