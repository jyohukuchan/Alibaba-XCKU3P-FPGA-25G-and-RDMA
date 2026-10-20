// SPDX-License-Identifier: BSD-2-Clause-Views
// Copyright (c) 2026 jyohukuchan
// Authorized contiguous command -> real Corundum application DMA interfaces.
// OFFLINE candidate, not wired to the deployed board. RAM is DMA staging, NOT
// a host-copy replacement. Pin/map lifetime and SG page translation are external.
// Integration MUST prove ordered same-function/TC, attr=0 PCIe requests and
// write status after the last TX request (generic TX_SEQ_NUM_ENABLE=1;
// older standalone US engines call it RQ_SEQ_NUM_ENABLE). A subsequent
// one-byte readback fence is REQUIRED before successful WRITE completion.
// enable only stops NEW commands. Reset MUST NOT cancel live DMA or revoke MR.
`resetall
`timescale 1ns / 1ps
`default_nettype none

module rocev2_corundum_dma_backend #(
    parameter RAM_SIZE=8192,
    parameter RAM_ADDR_WIDTH=16,
    parameter SEG_COUNT=2,
    parameter SEG_DATA_WIDTH=256,
    parameter SEG_BE_WIDTH=SEG_DATA_WIDTH/8,
    parameter SEG_ADDR_WIDTH=RAM_ADDR_WIDTH-$clog2(SEG_COUNT*SEG_BE_WIDTH),
    parameter RAM_SEL_WIDTH=4,
    parameter DMA_LEN_WIDTH=16,
    parameter TAG_WIDTH=16,
    // Default preserves fail-stop protected-payload behavior. A dedicated SQ
    // READ client may report a known terminal DMA error and wait for REAL
    // parent+local drain before reusing staging. Never recover WRITE/fence,
    // bad tag, malformed RAM/stream or any uncertain protocol ownership.
    parameter RECOVER_READ_DMA_ERROR=0
)(
    input wire clk,
    input wire rst,
    input wire enable,
    input wire parent_dma_drained,
    input wire s_command_write,
    input wire [63:0] s_command_address,
    input wire [31:0] s_command_length,
    input wire [TAG_WIDTH-1:0] s_command_tag,
    input wire s_command_valid,
    output wire s_command_ready,
    input wire [511:0] s_axis_write_tdata,
    input wire [63:0] s_axis_write_tkeep,
    input wire s_axis_write_tvalid,
    output wire s_axis_write_tready,
    input wire s_axis_write_tlast,
    output wire [511:0] m_axis_read_tdata,
    output wire [63:0] m_axis_read_tkeep,
    output wire m_axis_read_tvalid,
    input wire m_axis_read_tready,
    output wire m_axis_read_tlast,
    output reg [TAG_WIDTH-1:0] m_status_tag=0,
    output reg [7:0] m_status_error=0,
    output reg m_status_valid=0,
    input wire m_status_ready,
    output wire [63:0] m_dma_read_address,
    output wire [RAM_SEL_WIDTH-1:0] m_dma_read_ram_sel,
    output reg [RAM_ADDR_WIDTH-1:0] m_dma_read_ram_address=0,
    output reg [DMA_LEN_WIDTH-1:0] m_dma_read_length=0,
    output wire [TAG_WIDTH-1:0] m_dma_read_tag,
    output reg m_dma_read_valid=0,
    input wire m_dma_read_ready,
    input wire [TAG_WIDTH-1:0] s_dma_read_status_tag,
    input wire [3:0] s_dma_read_status_error,
    input wire s_dma_read_status_valid,
    output wire [63:0] m_dma_write_address,
    output wire [RAM_SEL_WIDTH-1:0] m_dma_write_ram_sel,
    output wire [RAM_ADDR_WIDTH-1:0] m_dma_write_ram_address,
    output wire [31:0] m_dma_write_imm,
    output wire m_dma_write_imm_en,
    output wire [DMA_LEN_WIDTH-1:0] m_dma_write_length,
    output wire [TAG_WIDTH-1:0] m_dma_write_tag,
    output reg m_dma_write_valid=0,
    input wire m_dma_write_ready,
    input wire [TAG_WIDTH-1:0] s_dma_write_status_tag,
    input wire [3:0] s_dma_write_status_error,
    input wire s_dma_write_status_valid,
    input wire [SEG_COUNT*RAM_SEL_WIDTH-1:0] dma_ram_wr_cmd_sel,
    input wire [SEG_COUNT*SEG_BE_WIDTH-1:0] dma_ram_wr_cmd_be,
    input wire [SEG_COUNT*SEG_ADDR_WIDTH-1:0] dma_ram_wr_cmd_addr,
    input wire [SEG_COUNT*SEG_DATA_WIDTH-1:0] dma_ram_wr_cmd_data,
    input wire [SEG_COUNT-1:0] dma_ram_wr_cmd_valid,
    output wire [SEG_COUNT-1:0] dma_ram_wr_cmd_ready,
    output wire [SEG_COUNT-1:0] dma_ram_wr_done,
    input wire [SEG_COUNT*RAM_SEL_WIDTH-1:0] dma_ram_rd_cmd_sel,
    input wire [SEG_COUNT*SEG_ADDR_WIDTH-1:0] dma_ram_rd_cmd_addr,
    input wire [SEG_COUNT-1:0] dma_ram_rd_cmd_valid,
    output wire [SEG_COUNT-1:0] dma_ram_rd_cmd_ready,
    output wire [SEG_COUNT*SEG_DATA_WIDTH-1:0] dma_ram_rd_resp_data,
    output wire [SEG_COUNT-1:0] dma_ram_rd_resp_valid,
    input wire [SEG_COUNT-1:0] dma_ram_rd_resp_ready,
    output wire idle,
    output wire dma_drained,
    output reg fault=0,
    output reg [7:0] fault_code=0,
    output reg [31:0] command_count=0,
    output reg [31:0] fence_count=0,
    output reg [31:0] completion_count=0
);
localparam IDLE=0,W_SINK=1,W_STREAM=2,W_DMA=3,W_WAIT=4,FENCE=5,FENCE_WAIT=6,
    R_DMA=7,R_WAIT=8,R_SOURCE=9,R_STREAM=10,ZERO_STREAM=11,STATUS=12,FAULT=13,READ_DRAIN=14;
localparam FENCE_ADDRESS=RAM_SIZE-64;
localparam [7:0] ERR_COMMAND=1,ERR_STREAM=2,ERR_CLIENT=3,ERR_STATUS=4,ERR_RAM=5,ERR_DMA=6;
reg [3:0] state=IDLE;
reg [63:0] address=0;
reg [31:0] length=0,remaining=0;
reg [TAG_WIDTH-1:0] tag=0;
reg [7:0] operation_error=0;
reg dma_read_inflight=0,dma_write_inflight=0;
reg read_operation=0;
reg sink_desc_valid=0,source_desc_valid=0;
reg read_last_seen=0,source_status_seen=0;
wire sink_desc_ready,source_desc_ready;
wire [DMA_LEN_WIDTH-1:0] sink_status_length;
wire [TAG_WIDTH-1:0] sink_status_tag,source_status_tag;
wire [3:0] sink_status_error,source_status_error;
wire sink_status_valid,source_status_valid;
wire sink_ready;
wire sink_input_ready;
wire [511:0] staged_write_data;
wire [63:0] staged_write_keep;
wire staged_write_valid,staged_write_last;
wire [511:0] source_data;
wire [63:0] source_keep;
wire source_valid,source_last;
wire [64:0] command_end={1'b0,s_command_address}+{33'd0,s_command_length};
wire command_ok=s_command_length!=0 && s_command_length<=FENCE_ADDRESS &&
    s_command_length<=(64'h1<<DMA_LEN_WIDTH)-1 && s_command_tag!=0 &&
    (!command_end[64] || command_end[63:0]==0);
wire [63:0] expected_keep;
genvar n;
generate for(n=0;n<64;n=n+1) begin : keep_bits
    assign expected_keep[n]=remaining>n;
end endgenerate
wire write_shape_ok=s_axis_write_tkeep==expected_keep && s_axis_write_tlast==(remaining<=64);
wire zero_transfer=state==ZERO_STREAM && m_axis_read_tready;
wire read_last_transfer=source_valid && m_axis_read_tready && source_last && state!=ZERO_STREAM;
wire read_status_ok=source_status_tag==tag && source_status_error==0;
assign s_command_ready=state==IDLE && enable && !fault && !rst;
assign idle=state==IDLE && !fault && !rst;
assign m_dma_read_address=address;
assign m_dma_read_ram_sel=0;
assign m_dma_read_tag=tag;
assign m_dma_write_address=address;
assign m_dma_write_ram_sel=0;
assign m_dma_write_ram_address=0;
assign m_dma_write_imm=0;
assign m_dma_write_imm_en=0;
assign m_dma_write_length=length;
assign m_dma_write_tag=tag;
assign s_axis_write_tready=sink_input_ready && write_shape_ok && (state==W_STREAM || state==FAULT) && !rst;
assign m_axis_read_tdata=state==ZERO_STREAM ? 512'd0 : source_data;
assign m_axis_read_tkeep=state==ZERO_STREAM ? expected_keep : source_keep;
assign m_axis_read_tlast=state==ZERO_STREAM ? remaining<=64 : source_last;
assign m_axis_read_tvalid=(state==ZERO_STREAM || source_valid) && !rst;

wire [SEG_COUNT*SEG_BE_WIDTH-1:0] sink_wr_be;
wire [SEG_COUNT*SEG_ADDR_WIDTH-1:0] sink_wr_addr,source_rd_addr;
wire [SEG_COUNT*SEG_DATA_WIDTH-1:0] sink_wr_data,ram_rd_data;
wire [SEG_COUNT-1:0] sink_wr_valid,sink_wr_ready,sink_wr_done;
wire [SEG_COUNT-1:0] source_rd_valid,source_rd_ready,source_resp_valid,source_resp_ready;
wire [SEG_COUNT-1:0] ram_wr_ready,ram_wr_done,ram_rd_ready,ram_rd_valid;
wire [SEG_COUNT-1:0] allowed_dma_wr,allowed_dma_rd;
wire [SEG_COUNT*SEG_BE_WIDTH-1:0] ram_wr_be=dma_read_inflight ? dma_ram_wr_cmd_be : sink_wr_be;
wire [SEG_COUNT*SEG_ADDR_WIDTH-1:0] ram_wr_addr=dma_read_inflight ? dma_ram_wr_cmd_addr : sink_wr_addr;
wire [SEG_COUNT*SEG_DATA_WIDTH-1:0] ram_wr_data=dma_read_inflight ? dma_ram_wr_cmd_data : sink_wr_data;
wire [SEG_COUNT-1:0] ram_wr_valid=dma_read_inflight ? dma_ram_wr_cmd_valid & allowed_dma_wr : sink_wr_valid;
wire [SEG_COUNT*SEG_ADDR_WIDTH-1:0] ram_rd_addr=dma_write_inflight ? dma_ram_rd_cmd_addr : source_rd_addr;
wire [SEG_COUNT-1:0] ram_rd_cmd_valid=dma_write_inflight ? dma_ram_rd_cmd_valid & allowed_dma_rd : source_rd_valid;
wire [SEG_COUNT-1:0] ram_rd_resp_ready=dma_write_inflight ? dma_ram_rd_resp_ready : source_resp_ready;
assign sink_wr_ready=ram_wr_ready & {SEG_COUNT{!dma_read_inflight}};
assign sink_wr_done=ram_wr_done & {SEG_COUNT{!dma_read_inflight}};
assign dma_ram_wr_cmd_ready=ram_wr_ready & allowed_dma_wr & {SEG_COUNT{dma_read_inflight}};
assign dma_ram_wr_done=ram_wr_done & {SEG_COUNT{dma_read_inflight}};
assign source_rd_ready=ram_rd_ready & {SEG_COUNT{!dma_write_inflight}};
assign source_resp_valid=ram_rd_valid & {SEG_COUNT{!dma_write_inflight}};
assign dma_ram_rd_cmd_ready=ram_rd_ready & allowed_dma_rd & {SEG_COUNT{dma_write_inflight}};
assign dma_ram_rd_resp_data=ram_rd_data;
assign dma_ram_rd_resp_valid=ram_rd_valid & {SEG_COUNT{dma_write_inflight}};

// Guard the FULL external RAM addresses before the smaller staging RAM can
// alias them. A DMA read may write only the exact issued payload/fence span.
// Stable descriptor extents, prepared BEFORE descriptor valid/acceptance.
// Avoid serial add -> byte guard -> RAM-pending/drain -> FSM on one cycle.
// These are the SAME full enabled-byte/word bounds, not a timing exception.
reg [RAM_ADDR_WIDTH:0] dma_read_ram_end=0;
reg [32:0] rounded_length=0;
reg [7:0] wr_pending[0:SEG_COUNT-1];
reg [7:0] rd_pending[0:SEG_COUNT-1];
wire [SEG_COUNT-1:0] ram_pending_empty;
wire [SEG_COUNT-1:0] ram_pending_registered_empty;
generate for(n=0;n<SEG_COUNT;n=n+1) begin : ram_guards
    wire [RAM_ADDR_WIDTH:0] write_base={1'b0,dma_ram_wr_cmd_addr[n*SEG_ADDR_WIDTH+:SEG_ADDR_WIDTH],6'd0}+n*SEG_BE_WIDTH;
    wire [RAM_ADDR_WIDTH:0] read_base={1'b0,dma_ram_rd_cmd_addr[n*SEG_ADDR_WIDTH+:SEG_ADDR_WIDTH],6'd0}+n*SEG_BE_WIDTH;
    wire [SEG_BE_WIDTH-1:0] byte_allowed;
    genvar j;
    for(j=0;j<SEG_BE_WIDTH;j=j+1) begin : byte_guards
        assign byte_allowed[j]=!dma_ram_wr_cmd_be[n*SEG_BE_WIDTH+j] ||
            (write_base+j>={1'b0,m_dma_read_ram_address} && write_base+j<dma_read_ram_end);
    end
    assign allowed_dma_wr[n]=dma_ram_wr_cmd_sel[n*RAM_SEL_WIDTH+:RAM_SEL_WIDTH]==0 && (&byte_allowed) && write_base<RAM_SIZE;
    assign allowed_dma_rd[n]=dma_ram_rd_cmd_sel[n*RAM_SEL_WIDTH+:RAM_SEL_WIDTH]==0 && read_base<rounded_length && read_base<RAM_SIZE;
    wire wr_push=dma_ram_wr_cmd_valid[n] && dma_ram_wr_cmd_ready[n];
    wire wr_pop=dma_ram_wr_done[n];
    wire rd_push=dma_ram_rd_cmd_valid[n] && dma_ram_rd_cmd_ready[n];
    wire rd_pop=dma_ram_rd_resp_valid[n] && dma_ram_rd_resp_ready[n];
    wire wr_empty_after=wr_pending[n]+wr_push-wr_pop==0;
    wire rd_empty_after=rd_pending[n]+rd_push-rd_pop==0;
    assign ram_pending_empty[n]=wr_empty_after && rd_empty_after;
    assign ram_pending_registered_empty[n]=wr_pending[n]==0 && rd_pending[n]==0;
    always @(posedge clk) begin
        if(rst) begin wr_pending[n]<=0;rd_pending[n]<=0;end
        else begin
            case({wr_push,wr_pop}) 2'b10:wr_pending[n]<=wr_pending[n]+1'b1;2'b01:wr_pending[n]<=wr_pending[n]-1'b1;default:begin end endcase
            case({rd_push,rd_pop}) 2'b10:rd_pending[n]<=rd_pending[n]+1'b1;2'b01:rd_pending[n]<=rd_pending[n]-1'b1;default:begin end endcase
        end
    end
end endgenerate
// PUBLIC drain proof must not depend on a current address/byte-guard decision.
// Keep the predicted pending-after proof ABOVE for actual status retirement;
// here require registered-zero counters AND no current external RAM/status
// offer. This is conservative: it implies the old pending-after-zero proof,
// and blocks unsolicited work immediately, before its sticky fault is clocked.
// No status/tag/byte/range/fence permission or physical ownership is relaxed.
assign dma_drained=!dma_read_inflight && !dma_write_inflight &&
    !m_dma_read_valid && !m_dma_write_valid && (&ram_pending_registered_empty) &&
    !(|dma_ram_wr_cmd_valid) && !(|dma_ram_rd_cmd_valid) &&
    !(|dma_ram_wr_done) && !(|dma_ram_rd_resp_valid) &&
    !s_dma_read_status_valid && !s_dma_write_status_valid;

dma_psdpram #(.SIZE(RAM_SIZE),.SEG_COUNT(SEG_COUNT),.SEG_DATA_WIDTH(SEG_DATA_WIDTH),
    .SEG_BE_WIDTH(SEG_BE_WIDTH),.SEG_ADDR_WIDTH(SEG_ADDR_WIDTH),.PIPELINE(2)) staging_ram (
    .clk(clk),.rst(rst),.wr_cmd_be(ram_wr_be),.wr_cmd_addr(ram_wr_addr),.wr_cmd_data(ram_wr_data),
    .wr_cmd_valid(ram_wr_valid),.wr_cmd_ready(ram_wr_ready),.wr_done(ram_wr_done),
    .rd_cmd_addr(ram_rd_addr),.rd_cmd_valid(ram_rd_cmd_valid),.rd_cmd_ready(ram_rd_ready),
    .rd_resp_data(ram_rd_data),.rd_resp_valid(ram_rd_valid),.rd_resp_ready(ram_rd_resp_ready));
// Isolate the external keep-validation path from the sink's byte-count/status
// FIFO logic. Already accepted authorized beats remain valid through a fault.
axis_register #(.DATA_WIDTH(512),.KEEP_ENABLE(1),.KEEP_WIDTH(64),.LAST_ENABLE(1),
    .ID_ENABLE(0),.ID_WIDTH(1),.DEST_ENABLE(0),.DEST_WIDTH(1),.USER_ENABLE(0),.USER_WIDTH(1),.REG_TYPE(2)) write_ingress (
    .clk(clk),.rst(rst),.s_axis_tdata(s_axis_write_tdata),.s_axis_tkeep(s_axis_write_tkeep),
    .s_axis_tvalid(s_axis_write_tvalid && write_shape_ok && (state==W_STREAM || state==FAULT)),
    .s_axis_tready(sink_input_ready),.s_axis_tlast(s_axis_write_tlast),.s_axis_tid(1'b0),.s_axis_tdest(1'b0),.s_axis_tuser(1'b0),
    .m_axis_tdata(staged_write_data),.m_axis_tkeep(staged_write_keep),.m_axis_tvalid(staged_write_valid),
    .m_axis_tready(sink_ready),.m_axis_tlast(staged_write_last),.m_axis_tid(),.m_axis_tdest(),.m_axis_tuser());
dma_client_axis_sink #(.RAM_ADDR_WIDTH(RAM_ADDR_WIDTH),.SEG_COUNT(SEG_COUNT),.SEG_DATA_WIDTH(SEG_DATA_WIDTH),
    .SEG_BE_WIDTH(SEG_BE_WIDTH),.SEG_ADDR_WIDTH(SEG_ADDR_WIDTH),.AXIS_DATA_WIDTH(512),.AXIS_KEEP_WIDTH(64),
    .AXIS_USER_ENABLE(0),.LEN_WIDTH(DMA_LEN_WIDTH),.TAG_WIDTH(TAG_WIDTH)) sink (
    .clk(clk),.rst(rst),.s_axis_write_desc_ram_addr({RAM_ADDR_WIDTH{1'b0}}),.s_axis_write_desc_len(length[DMA_LEN_WIDTH-1:0]),
    .s_axis_write_desc_tag(tag),.s_axis_write_desc_valid(sink_desc_valid),.s_axis_write_desc_ready(sink_desc_ready),
    .m_axis_write_desc_status_len(sink_status_length),.m_axis_write_desc_status_tag(sink_status_tag),
    .m_axis_write_desc_status_id(),.m_axis_write_desc_status_dest(),.m_axis_write_desc_status_user(),
    .m_axis_write_desc_status_error(sink_status_error),.m_axis_write_desc_status_valid(sink_status_valid),
    .s_axis_write_data_tdata(staged_write_data),.s_axis_write_data_tkeep(staged_write_keep),
    .s_axis_write_data_tvalid(staged_write_valid),
    .s_axis_write_data_tready(sink_ready),.s_axis_write_data_tlast(staged_write_last),
    .s_axis_write_data_tid(8'd0),.s_axis_write_data_tdest(8'd0),.s_axis_write_data_tuser(1'b0),
    .ram_wr_cmd_be(sink_wr_be),.ram_wr_cmd_addr(sink_wr_addr),.ram_wr_cmd_data(sink_wr_data),
    .ram_wr_cmd_valid(sink_wr_valid),.ram_wr_cmd_ready(sink_wr_ready),.ram_wr_done(sink_wr_done),.enable(1'b1),.abort(1'b0));
dma_client_axis_source #(.RAM_ADDR_WIDTH(RAM_ADDR_WIDTH),.SEG_COUNT(SEG_COUNT),.SEG_DATA_WIDTH(SEG_DATA_WIDTH),
    .SEG_BE_WIDTH(SEG_BE_WIDTH),.SEG_ADDR_WIDTH(SEG_ADDR_WIDTH),.AXIS_DATA_WIDTH(512),.AXIS_KEEP_WIDTH(64),
    .AXIS_USER_ENABLE(0),.LEN_WIDTH(DMA_LEN_WIDTH),.TAG_WIDTH(TAG_WIDTH)) source (
    .clk(clk),.rst(rst),.s_axis_read_desc_ram_addr({RAM_ADDR_WIDTH{1'b0}}),.s_axis_read_desc_len(length[DMA_LEN_WIDTH-1:0]),
    .s_axis_read_desc_tag(tag),.s_axis_read_desc_id(8'd0),.s_axis_read_desc_dest(8'd0),.s_axis_read_desc_user(1'b0),
    .s_axis_read_desc_valid(source_desc_valid),.s_axis_read_desc_ready(source_desc_ready),
    .m_axis_read_desc_status_tag(source_status_tag),.m_axis_read_desc_status_error(source_status_error),.m_axis_read_desc_status_valid(source_status_valid),
    .m_axis_read_data_tdata(source_data),.m_axis_read_data_tkeep(source_keep),.m_axis_read_data_tvalid(source_valid),
    .m_axis_read_data_tready(m_axis_read_tready && state!=ZERO_STREAM),.m_axis_read_data_tlast(source_last),
    .m_axis_read_data_tid(),.m_axis_read_data_tdest(),.m_axis_read_data_tuser(),
    .ram_rd_cmd_addr(source_rd_addr),.ram_rd_cmd_valid(source_rd_valid),.ram_rd_cmd_ready(source_rd_ready),
    .ram_rd_resp_data(ram_rd_data),.ram_rd_resp_valid(source_resp_valid),.ram_rd_resp_ready(source_resp_ready),.enable(1'b1));

initial begin
    if(SEG_COUNT!=2 || SEG_DATA_WIDTH!=256 || SEG_BE_WIDTH!=32 ||
        RAM_ADDR_WIDTH!=SEG_ADDR_WIDTH+6 || RAM_SIZE<8192 || (RAM_SIZE&(RAM_SIZE-1))!=0 ||
        RAM_SIZE>(64'h1<<RAM_ADDR_WIDTH) || DMA_LEN_WIDTH<13 || DMA_LEN_WIDTH>32) begin
        $error("Unsupported Corundum DMA backend parameters");$finish;
    end
end

integer segment;
always @(posedge clk) begin
    if(rst) begin
        state<=IDLE;address<=0;length<=0;remaining<=0;tag<=0;operation_error<=0;
        dma_read_inflight<=0;dma_write_inflight<=0;sink_desc_valid<=0;source_desc_valid<=0;
        read_operation<=0;
        read_last_seen<=0;source_status_seen<=0;m_status_tag<=0;m_status_error<=0;m_status_valid<=0;
        m_dma_read_ram_address<=0;m_dma_read_length<=0;m_dma_read_valid<=0;m_dma_write_valid<=0;
        dma_read_ram_end<=0;rounded_length<=0;
        fault<=0;fault_code<=0;command_count<=0;fence_count<=0;completion_count<=0;
    end else begin
        // Once valid is asserted, even a sticky fault/enable change must not
        // withdraw a stalled descriptor. Its already-authorized lease persists.
        if(sink_desc_valid && sink_desc_ready) sink_desc_valid<=0;
        if(source_desc_valid && source_desc_ready) source_desc_valid<=0;
        if(m_dma_read_valid && m_dma_read_ready) begin m_dma_read_valid<=0;dma_read_inflight<=1;end
        if(m_dma_write_valid && m_dma_write_ready) begin m_dma_write_valid<=0;dma_write_inflight<=1;end
        if(m_status_valid && m_status_ready) begin
            m_status_valid<=0;completion_count<=completion_count+1'b1;
            if(!fault && RECOVER_READ_DMA_ERROR && read_operation &&
                m_status_error!=0 && m_status_error<=15)begin
                // The matching DMA status already retired local pending RAM;
                // ZERO_STREAM drained without exposing stale staged contents.
                // Reporting this fetch error is NOT permission to reuse RAM.
                state<=READ_DRAIN;
            end else if(m_status_error!=0 || fault) begin
                state<=FAULT;fault<=1;
                if(m_status_error!=0 && !fault) fault_code<=ERR_DMA;
            end else state<=IDLE;
        end
        if(s_dma_read_status_valid && dma_read_inflight && s_dma_read_status_tag==tag && (&ram_pending_empty)) dma_read_inflight<=0;
        if(s_dma_write_status_valid && dma_write_inflight && s_dma_write_status_tag==tag && (&ram_pending_empty)) dma_write_inflight<=0;
        if(!fault) begin
            for(segment=0;segment<SEG_COUNT;segment=segment+1) begin
                if((dma_ram_wr_cmd_valid[segment] && (!dma_read_inflight || !allowed_dma_wr[segment])) ||
                    (dma_ram_rd_cmd_valid[segment] && (!dma_write_inflight || !allowed_dma_rd[segment]))) begin
                    fault<=1;fault_code<=ERR_RAM;state<=FAULT;
                end
            end
            if((s_dma_read_status_valid && (!dma_read_inflight || s_dma_read_status_tag!=tag || !( &ram_pending_empty))) ||
                (s_dma_write_status_valid && (!dma_write_inflight || s_dma_write_status_tag!=tag || !( &ram_pending_empty)))) begin
                fault<=1;fault_code<=ERR_STATUS;state<=FAULT;
            end
            case(state)
                IDLE: if(s_command_valid && s_command_ready) begin
                    if(!command_ok) begin fault<=1;fault_code<=ERR_COMMAND;state<=FAULT;end
                    else begin
                        address<=s_command_address;length<=s_command_length;remaining<=s_command_length;tag<=s_command_tag;
                        rounded_length<=({1'b0,s_command_length}+33'd63)&~33'd63;
                        operation_error<=0;read_last_seen<=0;source_status_seen<=0;command_count<=command_count+1'b1;
                        read_operation<=!s_command_write;
                        if(s_command_write) begin sink_desc_valid<=1;state<=W_SINK;end
                        else state<=R_DMA;
                    end
                end
                W_SINK: if(sink_desc_valid && sink_desc_ready) state<=W_STREAM;
                W_STREAM: begin
                    if(s_axis_write_tvalid && !write_shape_ok) begin fault<=1;fault_code<=ERR_STREAM;state<=FAULT;end
                    if(s_axis_write_tvalid && s_axis_write_tready) remaining<=remaining>64 ? remaining-64 : 0;
                    if(sink_status_valid) begin
                        if(sink_status_tag!=tag || sink_status_length!=length || sink_status_error!=0 || remaining!=0) begin
                            fault<=1;fault_code<=ERR_CLIENT;state<=FAULT;
                        end else begin m_dma_write_valid<=1;state<=W_DMA;end
                    end
                end
                W_DMA: if(m_dma_write_valid && m_dma_write_ready) state<=W_WAIT;
                W_WAIT: if(s_dma_write_status_valid && s_dma_write_status_tag==tag && (&ram_pending_empty)) begin
                    if(s_dma_write_status_error!=0) begin operation_error<={4'd0,s_dma_write_status_error};state<=STATUS;end
                    else state<=FENCE;
                end
                FENCE: begin
                    m_dma_read_ram_address<=FENCE_ADDRESS;m_dma_read_length<=1;dma_read_ram_end<=FENCE_ADDRESS+1;
                    m_dma_read_valid<=1;fence_count<=fence_count+1'b1;state<=FENCE_WAIT;
                end
                FENCE_WAIT: if(s_dma_read_status_valid && s_dma_read_status_tag==tag && (&ram_pending_empty)) begin
                    operation_error<={4'd0,s_dma_read_status_error};state<=STATUS;
                end
                R_DMA: begin
                    m_dma_read_ram_address<=0;m_dma_read_length<=length;dma_read_ram_end<=length;
                    m_dma_read_valid<=1;state<=R_WAIT;
                end
                R_WAIT: if(s_dma_read_status_valid && s_dma_read_status_tag==tag && (&ram_pending_empty)) begin
                    if(s_dma_read_status_error!=0) begin operation_error<={4'd0,s_dma_read_status_error};state<=ZERO_STREAM;end
                    else begin source_desc_valid<=1;state<=R_SOURCE;end
                end
                R_SOURCE: if(source_desc_valid && source_desc_ready) state<=R_STREAM;
                R_STREAM: begin
                    if(read_last_transfer) read_last_seen<=1;
                    if(source_status_valid) begin
                        if(!read_status_ok) begin fault<=1;fault_code<=ERR_CLIENT;state<=FAULT;end
                        else source_status_seen<=1;
                    end
                    if((read_last_seen || read_last_transfer) && (source_status_seen || (source_status_valid && read_status_ok))) state<=STATUS;
                end
                ZERO_STREAM: if(zero_transfer) begin
                    if(remaining<=64) begin remaining<=0;state<=STATUS;end else remaining<=remaining-64;
                end
                STATUS: if(!m_status_valid) begin m_status_tag<=tag;m_status_error<=operation_error;m_status_valid<=1;end
                READ_DRAIN: if(parent_dma_drained && dma_drained)state<=IDLE;
                default: begin end
            endcase
        end
    end
end
endmodule
`resetall
