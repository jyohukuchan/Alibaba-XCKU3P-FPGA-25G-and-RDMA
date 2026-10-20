// SPDX-License-Identifier: BSD-2-Clause-Views
// Full-frame request steering BEFORE the preserved initiator Ethernet ingress.
// Matching configured IPv4/UDP4791 RC requests reach ONLY the protected
// responder's integrity gate; ACK/READ responses and ordinary Ethernet retain
// ALL sidebands and flow to the unchanged initiator/host path. Not an ICRC or
// authorization checker. Configuration is privileged and may change only when
// the surrounding endpoint's config_safe is true. No reset-as-cancellation.
// Derived from the pinned original RW ingress without modifying that source.
`resetall
`timescale 1ns / 1ps
`default_nettype none

module rocev2_responder_ethernet_rx #(
    parameter USER_WIDTH = 97,
    // Opt-in native requester response steering; original request mode stays 0.
    parameter RESPONSE_MODE = 0,
    parameter MAX_FRAME_BYTES = 9214,
    parameter FIFO_BYTES = 16384
)(
    input wire clk,
    input wire rst,
    input wire enable,
    input wire [31:0] run_id,
    // Conventional numeric/network order (e.g. 48'h020000000001,
    // 32'hc6120a02), NOT AXIS byte-lane order. Sampled at frame start.
    input wire [47:0] local_mac,
    input wire [47:0] peer_mac,
    input wire [31:0] local_ip,
    input wire [127:0] s_axis_tdata,
    input wire [15:0] s_axis_tkeep,
    input wire s_axis_tvalid,
    output wire s_axis_tready,
    input wire s_axis_tlast,
    input wire [USER_WIDTH-1:0] s_axis_tuser,
    output wire [127:0] m_axis_host_tdata,
    output wire [15:0] m_axis_host_tkeep,
    output wire m_axis_host_tvalid,
    input wire m_axis_host_tready,
    output wire m_axis_host_tlast,
    output wire [USER_WIDTH-1:0] m_axis_host_tuser,
    output wire [127:0] m_axis_roce_tdata,
    output wire [15:0] m_axis_roce_tkeep,
    output wire m_axis_roce_tvalid,
    input wire m_axis_roce_tready,
    output wire m_axis_roce_tlast,
    output wire m_axis_roce_tuser,
    output reg [31:0] host_frame_count = 0,
    output reg [31:0] roce_frame_count = 0,
    output reg [31:0] drop_frame_count = 0,
    output reg [31:0] overflow_count = 0,
    output reg [31:0] stale_frame_count = 0,
    output wire quiescent
);

initial begin
    if (USER_WIDTH < 1 || MAX_FRAME_BYTES < 62 ||
        FIFO_BYTES < MAX_FRAME_BYTES || FIFO_BYTES > 65536 ||
        (FIFO_BYTES & (FIFO_BYTES-1)) != 0) begin
        $error("Unsupported Ethernet ingress configuration");
        $finish;
    end
end

function [15:0] be16;
    input [127:0] data;
    input integer offset;
    begin be16={data[offset*8+:8],data[(offset+1)*8+:8]}; end
endfunction
function [31:0] be32;
    input [31:0] data;
    begin be32={data[7:0],data[15:8],data[23:16],data[31:24]}; end
endfunction
function [47:0] be48;
    input [47:0] data;
    begin be48={data[7:0],data[15:8],data[23:16],data[31:24],data[39:32],data[47:40]}; end
endfunction

localparam ROUTE_HOST=2'd0, ROUTE_ROCE=2'd1, ROUTE_DROP=2'd2;
localparam META_DEPTH=32;
reg [1:0] routes[0:META_DEPTH-1];
reg [31:0] route_run_id[0:META_DEPTH-1];
reg [31:0] saved_run_id=0;
reg [4:0] wr_ptr=0, rd_ptr=0;
reg [5:0] route_count=0;
reg output_route_latched=0,output_stale=0;
wire route_valid=route_count!=0 && output_route_latched;
wire [1:0] stored_route=routes[rd_ptr];
wire stale_now=output_stale;
wire [1:0] route=stored_route==ROUTE_ROCE && stale_now ? ROUTE_DROP : stored_route;
reg first=1;
reg [16:0] offset=0;
reg [1:0] classified_route=ROUTE_HOST;
reg enabled=0, ipv4=0, udp=0, mac_match=0, bad=0;
reg [31:0] saved_local_ip=0;
reg [15:0] dst_ip_head=0;
reg [4:0] valid_bytes;
integer lane;
always @* begin
    valid_bytes=0;
    for (lane=0;lane<16;lane=lane+1) valid_bytes=valid_bytes+{4'd0,s_axis_tkeep[lane]};
end
wire [16:0] frame_bytes=offset+{12'd0,valid_bytes};
wire [16:0] dense_keep=(17'd1<<valid_bytes)-17'd1;
wire bad_now=bad || s_axis_tuser[0] || valid_bytes==0 ||
    s_axis_tkeep!=dense_keep[15:0] || (!s_axis_tlast && s_axis_tkeep!=16'hffff);
wire [31:0] destination_ip={dst_ip_head,s_axis_tdata[7:0],s_axis_tdata[15:8]};
reg [1:0] route_now;
always @* begin
    route_now=first ? ROUTE_HOST : classified_route;
    // Requests and responses share UDP4791. Never consume ACK/READ/Atomic
    // responses needed by the existing initiator; the protected responder is
    // the sole authority for QP/PD/full-key/PSN/range/operation checks.
    if (offset==32 && enabled && ipv4 && udp && mac_match &&
            destination_ip==saved_local_ip && be16(s_axis_tdata,4)==16'd4791 &&
            (RESPONSE_MODE ?
             (s_axis_tdata[87:80]>=8'h0d && s_axis_tdata[87:80]<=8'h12) :
             (s_axis_tdata[87:80]<=8'h0c ||
              (s_axis_tdata[87:80]>=8'h13 && s_axis_tdata[87:80]<=8'h17))))
        route_now=ROUTE_ROCE;
    if (s_axis_tlast && ((route_now!=ROUTE_HOST && (bad_now || frame_bytes<17'd62)) ||
        frame_bytes>MAX_FRAME_BYTES)) route_now=ROUTE_DROP;
end

wire [127:0] fifo_data;
wire [15:0] fifo_keep;
wire fifo_valid, fifo_ready, fifo_last, fifo_input_ready, fifo_overflow;
wire [USER_WIDTH-1:0] fifo_user;
// Reserve metadata capacity at SOP; never stop an already-started frame for
// metadata space. With one producer, the reservation cannot be stolen.
wire input_allowed=!first || route_count<META_DEPTH;
assign s_axis_tready=fifo_input_ready && input_allowed;
wire input_transfer=s_axis_tvalid && s_axis_tready;
// DROP_OVERSIZE_FRAME drops a frame using more than FIFO_BYTES/16 beats.
// Do NOT queue an orphan route for such a frame, even for sparse invalid keep.
wire route_push=input_transfer && s_axis_tlast && offset<FIFO_BYTES;
wire route_pop=fifo_valid && fifo_ready && fifo_last;

axis_fifo #(
    .DEPTH(FIFO_BYTES),.DATA_WIDTH(128),.KEEP_ENABLE(1),.KEEP_WIDTH(16),
    .LAST_ENABLE(1),.ID_ENABLE(0),.ID_WIDTH(1),.DEST_ENABLE(0),.DEST_WIDTH(1),
    .USER_ENABLE(1),.USER_WIDTH(USER_WIDTH),.RAM_PIPELINE(2),.OUTPUT_FIFO_ENABLE(1),
    .FRAME_FIFO(1),.DROP_OVERSIZE_FRAME(1),.DROP_BAD_FRAME(0),.DROP_WHEN_FULL(0)
) frame_fifo (
    .clk(clk),.rst(rst),.s_axis_tdata(s_axis_tdata),.s_axis_tkeep(s_axis_tkeep),
    .s_axis_tvalid(s_axis_tvalid && input_allowed),.s_axis_tready(fifo_input_ready),
    .s_axis_tlast(s_axis_tlast),.s_axis_tid(1'b0),.s_axis_tdest(1'b0),.s_axis_tuser(s_axis_tuser),
    .m_axis_tdata(fifo_data),.m_axis_tkeep(fifo_keep),.m_axis_tvalid(fifo_valid),
    .m_axis_tready(fifo_ready),.m_axis_tlast(fifo_last),.m_axis_tid(),.m_axis_tdest(),.m_axis_tuser(fifo_user),
    .pause_req(1'b0),.pause_ack(),.status_depth(),.status_depth_commit(),
    .status_overflow(fifo_overflow),.status_bad_frame(),.status_good_frame()
);
wire strip_ready,strip_busy;
assign quiescent=!rst && first && !s_axis_tvalid && route_count==0 &&
    !fifo_valid && !strip_busy && !m_axis_roce_tvalid;
assign fifo_ready=route_valid && (route==ROUTE_HOST ? m_axis_host_tready :
    route==ROUTE_ROCE ? strip_ready : 1'b1);
assign m_axis_host_tdata=fifo_data;
assign m_axis_host_tkeep=fifo_keep;
assign m_axis_host_tvalid=fifo_valid && route_valid && route==ROUTE_HOST;
assign m_axis_host_tlast=fifo_last;
assign m_axis_host_tuser=fifo_user;

// The pinned generic Ethernet framer supports 128-bit lanes. No 64-bit/250MHz
// bottleneck is inserted. Header metadata is already checked above.
eth_axis_rx #(.DATA_WIDTH(128),.KEEP_ENABLE(1),.KEEP_WIDTH(16)) strip_header (
    .clk(clk),.rst(rst),.s_axis_tdata(fifo_data),.s_axis_tkeep(fifo_keep),
    .s_axis_tvalid(fifo_valid && route_valid && route==ROUTE_ROCE),.s_axis_tready(strip_ready),
    .s_axis_tlast(fifo_last),.s_axis_tuser(fifo_user[0]),
    .m_eth_hdr_valid(),.m_eth_hdr_ready(1'b1),.m_eth_dest_mac(),.m_eth_src_mac(),.m_eth_type(),
    .m_eth_payload_axis_tdata(m_axis_roce_tdata),.m_eth_payload_axis_tkeep(m_axis_roce_tkeep),
    .m_eth_payload_axis_tvalid(m_axis_roce_tvalid),.m_eth_payload_axis_tready(m_axis_roce_tready),
    .m_eth_payload_axis_tlast(m_axis_roce_tlast),.m_eth_payload_axis_tuser(m_axis_roce_tuser),
    .busy(strip_busy),.error_header_early_termination()
);

always @(posedge clk) begin
    if (rst) begin
        first<=1; offset<=0; classified_route<=ROUTE_HOST;
        enabled<=0; ipv4<=0; udp<=0; mac_match<=0; bad<=0;
        saved_local_ip<=0; dst_ip_head<=0;
        wr_ptr<=0; rd_ptr<=0; route_count<=0;
        host_frame_count<=0; roce_frame_count<=0; drop_frame_count<=0; overflow_count<=0;
        saved_run_id<=0;output_route_latched<=0;output_stale<=0;stale_frame_count<=0;
    end else begin
        if (route_push) begin
            routes[wr_ptr]<=route_now;route_run_id[wr_ptr]<=saved_run_id;wr_ptr<=wr_ptr+1'b1;
        end
        // Freeze the output route at frame start: changing an epoch during
        // a stalled/mid-frame transfer must never withdraw TVALID or truncate
        // the Ethernet framer. Endpoint INIT drains an already-started old
        // frame before enabling HLS RX; queued stale frames are discarded here.
        if (!output_route_latched && route_count!=0) begin
            output_stale<=route_run_id[rd_ptr]!=run_id;output_route_latched<=1;
        end
        if (fifo_valid && fifo_ready) begin
            if (fifo_last) output_route_latched<=0;
            if (fifo_last && stored_route==ROUTE_ROCE && stale_now)
                stale_frame_count<=stale_frame_count+1'b1;
        end
        if (route_pop) rd_ptr<=rd_ptr+1'b1;
        case ({route_push,route_pop})
            2'b10: route_count<=route_count+1'b1;
            2'b01: route_count<=route_count-1'b1;
            default: begin end
        endcase
        if (fifo_overflow) overflow_count<=overflow_count+1'b1;
        if (input_transfer) begin
            classified_route<=route_now;
            bad<=bad_now;
            if (first) begin
                enabled<=enable;saved_run_id<=run_id;
                saved_local_ip<=local_ip;
                ipv4<=be16(s_axis_tdata,12)==16'h0800 && s_axis_tdata[119:112]==8'h45;
                mac_match<=be48(s_axis_tdata[47:0])==local_mac && be48(s_axis_tdata[95:48])==peer_mac;
                udp<=0;
            end
            if (offset==16) begin
                udp<=s_axis_tdata[63:56]==8'd17;
                dst_ip_head<={s_axis_tdata[119:112],s_axis_tdata[127:120]};
                // Trusted QP/peer-IP authority belongs to the protected guard,
                // not to this Ethernet steering layer.
            end
            if (s_axis_tlast) begin
                first<=1; offset<=0; classified_route<=ROUTE_HOST; bad<=0;
                if (route_now==ROUTE_HOST) host_frame_count<=host_frame_count+1'b1;
                else if (route_now==ROUTE_ROCE) roce_frame_count<=roce_frame_count+1'b1;
                else drop_frame_count<=drop_frame_count+1'b1;
            end else begin
                first<=0;
                if (offset<17'd65536) offset<=offset+17'd16;
            end
        end
    end
end
endmodule
`resetall
