// SPDX-License-Identifier: BSD-2-Clause-Views
// Bounded READ-response capture RAM. No PCIe DMA or public inbound MR.
// Every command must match an accepted READ SQ descriptor, in order. Slots
// start at zero, are 64-byte aligned, and cannot overlap. The HLS memory
// stream includes up to three wire pad bytes; those are never stored.
// clear resets transaction state, NOT RAM: the host can prefill sentinels
// before a run and read the actual captured bytes after the run.
`resetall
`timescale 1ns / 1ps
`default_nettype none

module rocev2_read_buffer #(
    parameter CAPACITY_BYTES=262144,
    parameter DESC_DEPTH=32
)(
    input wire clk,
    input wire rst,
    input wire clear,
    input wire capture_enable,
    input wire [9:0] local_qpn,
    input wire [31:0] lease_bytes,
    input wire [31:0] s_axis_desc_address,
    input wire [31:0] s_axis_desc_length,
    input wire s_axis_desc_valid,
    output wire s_axis_desc_ready,
    input wire [95:0] s_axis_cmd_tdata,
    input wire s_axis_cmd_tvalid,
    output wire s_axis_cmd_tready,
    input wire [511:0] s_axis_tdata,
    input wire [63:0] s_axis_tkeep,
    input wire s_axis_tvalid,
    output wire s_axis_tready,
    input wire s_axis_tlast,
    input wire [31:0] host_address,
    input wire host_write,
    input wire [31:0] host_wdata,
    input wire [3:0] host_wstrb,
    input wire host_valid,
    output wire host_ready,
    output reg [31:0] host_rdata=0,
    output reg host_error=0,
    output reg host_response_valid=0,
    input wire host_response_ready,
    output wire idle,
    output wire host_idle,
    output reg fault=0,
    output reg [7:0] error_code=0,
    output reg [31:0] authorized_count=0,
    output reg [31:0] committed_count=0,
    output reg [31:0] committed_bytes=0,
    output reg [31:0] padding_bytes=0,
    output reg [31:0] command_count=0
);
localparam ADDR_WIDTH=$clog2(CAPACITY_BYTES);
localparam PTR_WIDTH=$clog2(DESC_DEPTH);
localparam WORDS=CAPACITY_BYTES/64;
localparam ERR_DESCRIPTOR=8'd1, ERR_COMMAND=8'd2, ERR_STREAM=8'd3;

(* ram_style="block" *) reg [511:0] memory[0:WORDS-1];
reg [31:0] descriptor_address[0:DESC_DEPTH-1];
reg [31:0] descriptor_length[0:DESC_DEPTH-1];
reg [PTR_WIDTH-1:0] write_pointer=0,read_pointer=0;
reg [PTR_WIDTH:0] descriptor_count=0;
reg [31:0] next_descriptor_address=0,head_offset=0;
reg active=0,command_final_descriptor=0;
reg [31:0] write_address=0;
reg [12:0] wire_remaining=0,payload_remaining=0,chunk_bytes=0;

wire [32:0] descriptor_stride=({1'b0,s_axis_desc_length}+33'd63)&~33'd63;
wire [32:0] descriptor_end={1'b0,s_axis_desc_address}+descriptor_stride;
wire descriptor_ok=s_axis_desc_address==next_descriptor_address &&
    s_axis_desc_address[5:0]==0 && s_axis_desc_length>=1 && s_axis_desc_length<=65536 &&
    lease_bytes>=64 && lease_bytes<=CAPACITY_BYTES && descriptor_end<={1'b0,lease_bytes};
// Prefetch descriptor arithmetic before admitting a memory command. Avoid
// LUTRAM read -> subtract -> PMTU/pad selection -> compare in one 4ns cycle.
reg [1:0] head_phase=0;
reg [31:0] head_remaining=0,head_address=0;
reg [12:0] expected_payload=0,expected_wire=0;
reg [31:0] expected_address=0;
reg final_descriptor=0;
wire [12:0] next_payload=head_remaining>4096 ? 13'd4096 : head_remaining[12:0];
wire command_ok=descriptor_count!=0 && head_phase==2 &&
    s_axis_cmd_tdata[47:0]=={16'd0,expected_address} &&
    s_axis_cmd_tdata[75:48]=={15'd0,expected_wire} &&
    s_axis_cmd_tdata[76]==final_descriptor && s_axis_cmd_tdata[78:77]==0 &&
    s_axis_cmd_tdata[79] && s_axis_cmd_tdata[83:80]==0 && s_axis_cmd_tdata[93:84]==local_qpn;
wire [6:0] wire_beat_bytes=wire_remaining>=64 ? 7'd64 : wire_remaining[6:0];
wire [6:0] payload_beat_bytes=payload_remaining>=64 ? 7'd64 : payload_remaining[6:0];
// Parallel constant-lane comparisons avoid a 65-bit shift/subtract carry
// chain on the per-beat keep-validation path.
wire [63:0] expected_keep;
genvar keep_lane;
generate for (keep_lane=0;keep_lane<64;keep_lane=keep_lane+1) begin : keep_lanes
    assign expected_keep[keep_lane]=wire_beat_bytes>keep_lane;
end endgenerate
wire beat_ok=s_axis_tkeep==expected_keep && s_axis_tlast==(wire_remaining<=64);
wire descriptor_transfer=s_axis_desc_valid && s_axis_desc_ready;
wire push=descriptor_transfer && descriptor_ok;
wire command_transfer=s_axis_cmd_tvalid && s_axis_cmd_tready;
wire data_transfer=s_axis_tvalid && s_axis_tready;
wire pop=data_transfer && beat_ok && wire_remaining<=64 && command_final_descriptor;

// Host requests are single-outstanding and response data is held under
// backpressure. A request while capture is enabled receives an error, with
// no RAM access. Reads are registered at 512 bits, then lane-selected.
reg host_pending=0,host_pending_error=0,host_pending_write=0;
reg [3:0] host_lane=0;
reg [511:0] host_read_word=0;
wire host_transfer=host_valid && host_ready;
reg ram_write_valid=0,ram_write_capture=0,ram_write_final=0;
reg [ADDR_WIDTH-1:0] ram_write_address=0;
reg [511:0] ram_write_data=0;
reg [63:0] ram_write_mask=0;
reg [6:0] ram_payload_bytes=0,ram_padding_bytes=0;
wire host_access_ok=!capture_enable && !ram_write_valid && host_address<CAPACITY_BYTES && host_address[1:0]==0;
wire ram_stream_write=data_transfer && beat_ok;
wire ram_host_write=host_transfer && host_access_ok && host_write;
wire [ADDR_WIDTH-1:0] ram_read_address=host_address[ADDR_WIDTH-1:0]>>6;
assign host_ready=!host_pending && !host_response_valid;
assign host_idle=!host_pending && !host_response_valid;
assign idle=!active && descriptor_count==0 && !ram_write_valid;
assign s_axis_desc_ready=capture_enable && !clear && !rst && !fault && descriptor_count<DESC_DEPTH;
assign s_axis_cmd_tready=capture_enable && !clear && !rst && !fault && !active &&
    (descriptor_count==0 || head_phase==2);
assign s_axis_tready=capture_enable && !clear && !rst && !fault && active;

initial begin
    if (CAPACITY_BYTES<64 || CAPACITY_BYTES>262144 || (CAPACITY_BYTES&(CAPACITY_BYTES-1))!=0 ||
        DESC_DEPTH<2 || DESC_DEPTH>32 || (DESC_DEPTH&(DESC_DEPTH-1))!=0) begin
        $error("Invalid protected READ buffer parameters"); $finish;
    end
end

integer lane;
always @(posedge clk) begin
    if (rst || clear) begin
        write_pointer<=0;read_pointer<=0;descriptor_count<=0;
        next_descriptor_address<=0;head_offset<=0;
        active<=0;command_final_descriptor<=0;write_address<=0;
        wire_remaining<=0;payload_remaining<=0;chunk_bytes<=0;
        fault<=0;error_code<=0;authorized_count<=0;committed_count<=0;
        committed_bytes<=0;padding_bytes<=0;command_count<=0;
        host_pending<=0;host_pending_error<=0;host_pending_write<=0;
        host_lane<=0;host_read_word<=0;host_rdata<=0;host_error<=0;host_response_valid<=0;
        ram_write_valid<=0;ram_write_capture<=0;ram_write_final<=0;
        head_phase<=0;head_remaining<=0;head_address<=0;
        expected_payload<=0;expected_wire<=0;expected_address<=0;final_descriptor<=0;
    end else begin
        if (capture_enable && !fault && !active && descriptor_count!=0 && head_phase==0) begin
            head_remaining<=descriptor_length[read_pointer]-head_offset;
            head_address<=descriptor_address[read_pointer]+head_offset;
            head_phase<=1;
        end
        if (head_phase==1) begin
            expected_payload<=next_payload;expected_wire<=(next_payload+13'd3)&~13'd3;
            expected_address<=head_address;final_descriptor<=head_remaining<=4096;
            head_phase<=2;
        end
        // Register validated data/masks before driving the physically spread
        // BRAM banks. Counters describe actual RAM commits, not AXIS receipt.
        ram_write_valid<=ram_stream_write || ram_host_write;
        if (ram_stream_write || ram_host_write) begin
            ram_write_address<=(ram_stream_write ? write_address[ADDR_WIDTH-1:0] : host_address[ADDR_WIDTH-1:0])>>6;
            ram_write_data<=ram_stream_write ? s_axis_tdata : {16{host_wdata}};
            ram_write_capture<=ram_stream_write;
            ram_write_final<=ram_stream_write && pop;
            ram_payload_bytes<=payload_beat_bytes;
            ram_padding_bytes<=wire_beat_bytes-payload_beat_bytes;
            for (lane=0;lane<64;lane=lane+1)
                ram_write_mask[lane]<=ram_stream_write ? lane<payload_beat_bytes :
                    host_address[5:2]==lane/4 && host_wstrb[lane%4];
        end
        if (ram_write_valid && ram_write_capture) begin
            committed_bytes<=committed_bytes+{25'd0,ram_payload_bytes};
            padding_bytes<=padding_bytes+{25'd0,ram_padding_bytes};
            if (ram_write_final) committed_count<=committed_count+1'b1;
        end
        if (host_response_valid && host_response_ready) host_response_valid<=0;
        if (host_pending) begin
            host_pending<=0;host_response_valid<=1;host_error<=host_pending_error;
            host_rdata<=host_pending_error || host_pending_write ? 32'd0 : host_read_word[host_lane*32+:32];
        end
        if (host_transfer) begin
            host_pending<=1;host_pending_error<=!host_access_ok;host_pending_write<=host_write;
            host_lane<=host_address[5:2];
            if (host_access_ok && !host_write) host_read_word<=memory[ram_read_address];
        end

        if (descriptor_transfer && !descriptor_ok) begin fault<=1;error_code<=ERR_DESCRIPTOR;end
        if (push) begin
            descriptor_address[write_pointer]<=s_axis_desc_address;
            descriptor_length[write_pointer]<=s_axis_desc_length;
            write_pointer<=write_pointer+1'b1;
            next_descriptor_address<=descriptor_end[31:0];
            authorized_count<=authorized_count+1'b1;
        end
        case ({push,pop})
            2'b10: descriptor_count<=descriptor_count+1'b1;
            2'b01: descriptor_count<=descriptor_count-1'b1;
            default: begin end
        endcase
        if (command_transfer) begin
            if (!command_ok) begin fault<=1;error_code<=ERR_COMMAND;end
            else begin
                head_phase<=0;
                active<=1;write_address<=expected_address;chunk_bytes<=expected_payload;
                payload_remaining<=expected_payload;wire_remaining<=expected_wire;
                command_final_descriptor<=final_descriptor;command_count<=command_count+1'b1;
            end
        end
        if (data_transfer) begin
            if (!beat_ok) begin fault<=1;error_code<=ERR_STREAM;end
            else begin
                write_address<=write_address+32'd64;
                payload_remaining<=payload_remaining-{6'd0,payload_beat_bytes};
                wire_remaining<=wire_remaining-{6'd0,wire_beat_bytes};
                if (wire_remaining<=64) begin
                    active<=0;
                    if (command_final_descriptor) begin
                        read_pointer<=read_pointer+1'b1;head_offset<=0;
                    end else head_offset<=head_offset+{19'd0,chunk_bytes};
                end
            end
        end

    end
end
// Single registered write port with byte enables; RAM contents have no reset.
integer write_lane;
always @(posedge clk) begin
    for (write_lane=0;write_lane<64;write_lane=write_lane+1)
        if (!rst && !clear && ram_write_valid && ram_write_mask[write_lane])
            memory[ram_write_address][write_lane*8+:8]<=ram_write_data[write_lane*8+:8];
end
endmodule
`resetall
