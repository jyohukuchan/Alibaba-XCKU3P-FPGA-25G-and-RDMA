// SPDX-License-Identifier: BSD-2-Clause-Views
// Dedicated positive-WQE IP TX -> actual Ethernet framer/shared native MAC.
// Own completion class001 is disjoint from native host(MSB1), legacy0 and
// responder0x4000. A fresh non-reused tag maps a real accepted MAC SFD receipt
// back to the saved FULL owner; no test/CPU context copy is completion proof.
// SFD is NOT EOF: require actual final MAC beat, framer idle and a conservative
// tail AFTER BOTH receipt and final beat. Existing native traffic stays live.
// Tail contract: 250MHz core, >=25Gb/s MAC, bounded MAX_IP_BYTES, genuine
// downstream SFD completions (never Corundum's TX_CPL_ENABLE=0 EOF fallback).
// Whole parent/NIC reset ONLY. A local reset is not cancellation: downstream
// queues/timestamps must be drained before resetting/reusing this tag space.
// Finite non-reused tags fail closed on exhaustion; no wrap/recovery claim.
// Positive 1-frame READ/WRITE prototype, NOT remote success/CQ/provider/verbs.
`resetall
`timescale 1ns/1ps
`default_nettype none
module rocev2_wqe_mac_tx #(
    parameter MAX_QPS=8,
    parameter TX_TAG_WIDTH=16,
    parameter TS_WIDTH=96,
    parameter TAG_SEQUENCE_WIDTH=13,
    parameter MAX_IP_BYTES=4156,
    parameter TAIL_CYCLES=1024,
    parameter REAL_MAC_COMPLETION_ENABLE=1,
    parameter NATIVE_RECV_CPL_ENABLE=0
)(
    input wire clk,
    input wire rst,
    input wire enable,
    input wire [587:0] s_owner_context,
    input wire [47:0] s_owner_local_mac,
    input wire [47:0] s_owner_peer_mac,
    input wire s_owner_valid,
    output wire s_owner_ready,
    // Already integrity-checked/generated IP; this is not arbitrary host TX.
    input wire [127:0] s_axis_ip_tdata,
    input wire [15:0] s_axis_ip_tkeep,
    input wire s_axis_ip_tvalid,
    output wire s_axis_ip_tready,
    input wire s_axis_ip_tlast,
    input wire s_axis_ip_tuser,
    // Existing native host/legacy/protected-responder mux, unchanged tags.
    input wire [127:0] s_axis_native_tdata,
    input wire [15:0] s_axis_native_tkeep,
    input wire s_axis_native_tvalid,
    output wire s_axis_native_tready,
    input wire s_axis_native_tlast,
    input wire [TX_TAG_WIDTH:0] s_axis_native_tuser,
    output wire [127:0] m_axis_mac_tdata,
    output wire [15:0] m_axis_mac_tkeep,
    output wire m_axis_mac_tvalid,
    input wire m_axis_mac_tready,
    output wire m_axis_mac_tlast,
    output wire [TX_TAG_WIDTH:0] m_axis_mac_tuser,
    input wire [TX_TAG_WIDTH-1:0] s_mac_cpl_tag,
    input wire [TS_WIDTH-1:0] s_mac_cpl_ts,
    input wire s_mac_cpl_valid,
    output wire s_mac_cpl_ready,
    output wire [TX_TAG_WIDTH-1:0] m_native_cpl_tag,
    output wire [TS_WIDTH-1:0] m_native_cpl_ts,
    output wire m_native_cpl_valid,
    input wire m_native_cpl_ready,
    output wire [587:0] m_mac_context,
    output wire [7:0] m_mac_error,
    output wire [TS_WIDTH-1:0] m_mac_timestamp,
    output reg m_mac_valid=0,
    input wire m_mac_ready,
    output wire local_tx_drained,
    output wire [MAX_QPS-1:0] queue_guard,
    output wire busy,
    output wire fault_pending,
    output reg fault=0,
    output reg [7:0] fault_code=0,
    output reg tags_exhausted=0,
    output wire [TX_TAG_WIDTH-1:0] active_tag,
    output reg [31:0] frame_count=0,
    output reg [31:0] receipt_count=0,
    output reg [31:0] proof_count=0
);
localparam [TX_TAG_WIDTH-1:0] LOCAL_CLASS=16'h2000;
localparam [TX_TAG_WIDTH-1:0] CLASS_MASK=16'he000;
localparam TAIL_WIDTH=$clog2(TAIL_CYCLES+1);
localparam MIN_TAIL_CYCLES=((MAX_IP_BYTES+14+4+8+12)*2+24)/25;
initial begin
    if(MAX_QPS<1 || MAX_QPS>8 || TX_TAG_WIDTH!=16 || TS_WIDTH<1 ||
       TAG_SEQUENCE_WIDTH<1 || TAG_SEQUENCE_WIDTH>13 || MAX_IP_BYTES<60 ||
       MAX_IP_BYTES>8192 || TAIL_CYCLES<MIN_TAIL_CYCLES || TAIL_CYCLES<1 ||
       REAL_MAC_COMPLETION_ENABLE!=1)
        $fatal(1,"unreviewed native MAC shape/tail or synthetic EOF completion");
end
reg [587:0] owner=0;
reg [47:0] local_mac=0,peer_mac=0;
reg [TAG_SEQUENCE_WIDTH-1:0] next_tag=1;
reg [TX_TAG_WIDTH-1:0] tag=0;
reg active=0,header_sent=0,ip_done=0,mac_started=0,mac_done=0,receipt_seen=0;
reg [15:0] ip_bytes=0;
reg [TAIL_WIDTH-1:0] tail_left=0;
reg [TS_WIDTH-1:0] timestamp=0;
wire [63:0] in_id,in_seq,in_epoch,in_va,in_offset,in_remote;
wire [23:0] in_qpn;
wire [15:0] in_pd,in_tag,in_op,in_flags;
wire [31:0] in_length,in_key,in_rkey;
wire [7:0] in_error,in_fetch;
wire [1:0] in_source;
wire in_available,in_authorized;
assign {in_id,in_seq,in_epoch,in_qpn,in_pd,in_tag,in_op,in_flags,in_length,in_key,in_va,in_offset,
    in_remote,in_rkey,in_error,in_source,in_fetch,in_available,in_authorized}=s_owner_context;
// Unpack the complete original owner instead of shortening its authority.
wire [63:0] saved_id,saved_seq,saved_epoch,saved_va,saved_offset,saved_remote;
wire [23:0] saved_qpn;
wire [15:0] saved_pd,saved_tag,saved_op,saved_flags;
wire [31:0] saved_length,saved_key,saved_rkey;
wire [7:0] saved_error,saved_fetch;
wire [1:0] saved_source;
wire saved_available,saved_authorized;
assign {saved_id,saved_seq,saved_epoch,saved_qpn,saved_pd,saved_tag,saved_op,saved_flags,
    saved_length,saved_key,saved_va,saved_offset,saved_remote,saved_rkey,saved_error,
    saved_source,saved_fetch,saved_available,saved_authorized}=owner;
wire known_owner=(^{s_owner_context,s_owner_local_mac,s_owner_peer_mac})!==1'bx;
wire [64:0] va_end={1'b0,in_va}+{33'd0,in_length};
wire [64:0] off_end={1'b0,in_offset}+{33'd0,in_length};
wire [64:0] remote_end={1'b0,in_remote}+{33'd0,in_length};
wire owner_ok=known_owner && in_qpn<MAX_QPS && in_seq!=0 && in_epoch!=0 && in_tag!=0 &&
    in_authorized && in_available && in_error==0 && in_source==0 && in_fetch==0 &&
    (in_op==1 || in_op==2 || (in_op==3 && in_remote==0 && in_rkey==0)) && (in_flags&16'hfffe)==0 && in_length!=0 && in_length<=4096 &&
    (!va_end[64] || va_end==65'h10000000000000000) &&
    (!off_end[64] || off_end==65'h10000000000000000) &&
    (!remote_end[64] || remote_end==65'h10000000000000000) &&
    s_owner_local_mac!=0 && !s_owner_local_mac[40] && s_owner_peer_mac!=0 && !s_owner_peer_mac[40];
wire bad_owner=enable && !active && ((s_owner_valid!==1'b0 && s_owner_valid!==1'b1) ||
    (s_owner_valid && !owner_ok));
wire own_cpl_class=(s_mac_cpl_tag&CLASS_MASK)==LOCAL_CLASS;
wire native_cpl_class=s_mac_cpl_tag[TX_TAG_WIDTH-1] || s_mac_cpl_tag==0 || s_mac_cpl_tag==16'h4000 ||
    (NATIVE_RECV_CPL_ENABLE && (s_mac_cpl_tag&16'he000)==16'h6000);
wire cpl_known=(^{s_mac_cpl_tag,s_mac_cpl_ts})!==1'bx;
assign m_native_cpl_tag=s_mac_cpl_tag;
assign m_native_cpl_ts=s_mac_cpl_ts;
assign m_native_cpl_valid=s_mac_cpl_valid && cpl_known && native_cpl_class;
// Invalid/duplicate/unknown local receipts are consumed into quarantine, NOT
// forwarded into the legacy tag0 completion guard or acknowledged as success.
assign s_mac_cpl_ready=!rst && (cpl_known && native_cpl_class ? m_native_cpl_ready : 1'b1);
wire cpl_take=s_mac_cpl_valid && s_mac_cpl_ready;
wire [127:0] framed_data;
wire [15:0] framed_keep;
wire framed_valid,framed_ready,framed_last,framed_user,framer_busy,header_ready;
wire [TX_TAG_WIDTH-1:0] native_tag=s_axis_native_tuser[TX_TAG_WIDTH:1];
wire native_tag_known=(^s_axis_native_tuser)!==1'bx;
wire native_tag_ok=native_tag_known && (native_tag[TX_TAG_WIDTH-1] || native_tag==0 || native_tag==16'h4000 ||
    (NATIVE_RECV_CPL_ENABLE && (native_tag&16'he000)==16'h6000));
wire native_ready;
assign s_axis_native_tready=native_ready && native_tag_ok;
wire mac_local=(m_axis_mac_tuser[TX_TAG_WIDTH:1]&CLASS_MASK)==LOCAL_CLASS;
wire mac_take=m_axis_mac_tvalid && m_axis_mac_tready && mac_local;
wire good_receipt=cpl_known && own_cpl_class && active && s_mac_cpl_tag==tag && !receipt_seen &&
    (mac_started || mac_take);
wire bad_cpl=(s_mac_cpl_valid!==1'b0 && s_mac_cpl_valid!==1'b1) ||
    (cpl_take && (!cpl_known || (!native_cpl_class && !good_receipt)));
wire bad_native=(s_axis_native_tvalid!==1'b0 && s_axis_native_tvalid!==1'b1) ||
    (s_axis_native_tvalid && !native_tag_ok);
wire bad_ip_valid=(s_axis_ip_tvalid!==1'b0 && s_axis_ip_tvalid!==1'b1) ||
    (s_axis_ip_tvalid && (!active || ip_done));
reg [4:0] beat_bytes;
reg ip_known;
integer lane;
always @*begin
    beat_bytes=0;ip_known=1;
    for(lane=0;lane<16;lane=lane+1)begin
        beat_bytes=beat_bytes+{4'd0,s_axis_ip_tkeep[lane]};
        if(s_axis_ip_tkeep[lane] && (^s_axis_ip_tdata[lane*8+:8])===1'bx)ip_known=0;
    end
end
wire [16:0] ip_next={1'b0,ip_bytes}+{12'd0,beat_bytes};
wire ip_shape=(^{s_axis_ip_tkeep,s_axis_ip_tlast,s_axis_ip_tuser})!==1'bx && ip_known &&
    s_axis_ip_tkeep!=0 && !(|(s_axis_ip_tkeep[15:1]&~s_axis_ip_tkeep[14:0])) &&
    (s_axis_ip_tlast || s_axis_ip_tkeep==16'hffff) && !s_axis_ip_tuser && ip_next<=MAX_IP_BYTES;
wire framer_ip_ready;
// Once an owner is accepted its presented frame drains even after disable or
// quarantine. Never gate an already offered AXI valid with a later fault.
wire ip_offer=s_axis_ip_tvalid && active && !ip_done;
assign s_axis_ip_tready=framer_ip_ready && active && !ip_done && !rst;
wire ip_take=s_axis_ip_tvalid && s_axis_ip_tready;
wire bad_frame=(ip_take && !ip_shape) || (mac_take && (m_axis_mac_tuser[0] || !active || mac_done));
wire incoming_fault=bad_owner || bad_cpl || bad_native || bad_ip_valid || bad_frame;
assign fault_pending=fault || incoming_fault;
// bad_owner is already excluded by owner_ok; keeping it out of this READY
// cone also permits an acyclic atomic multi-owner broadcast at the caller.
assign s_owner_ready=enable && !active && !fault && !bad_cpl && !bad_native &&
    !bad_ip_valid && !bad_frame && !tags_exhausted && owner_ok && !rst;
assign queue_guard=(fault || incoming_fault) ? {MAX_QPS{1'b1}} : active ?
    ({{(MAX_QPS-1){1'b0}},1'b1}<<saved_qpn) : (s_owner_valid && owner_ok) ?
    ({{(MAX_QPS-1){1'b0}},1'b1}<<in_qpn) : {MAX_QPS{1'b0}};
assign busy=active || fault;
assign active_tag=tag;
assign m_mac_context=owner;
assign m_mac_error=0;
assign m_mac_timestamp=timestamp;
assign local_tx_drained=!rst && !fault && !incoming_fault && !active && !framer_busy && tail_left==0;
eth_axis_tx #(.DATA_WIDTH(128),.KEEP_ENABLE(1),.KEEP_WIDTH(16)) framer(
    .clk(clk),.rst(rst),.s_eth_hdr_valid(ip_offer && !header_sent),.s_eth_hdr_ready(header_ready),
    .s_eth_dest_mac(peer_mac),.s_eth_src_mac(local_mac),.s_eth_type(16'h0800),
    .s_eth_payload_axis_tdata(s_axis_ip_tdata),.s_eth_payload_axis_tkeep(s_axis_ip_tkeep),
    .s_eth_payload_axis_tvalid(ip_offer),.s_eth_payload_axis_tready(framer_ip_ready),
    .s_eth_payload_axis_tlast(s_axis_ip_tlast),.s_eth_payload_axis_tuser(s_axis_ip_tuser),
    .m_axis_tdata(framed_data),.m_axis_tkeep(framed_keep),.m_axis_tvalid(framed_valid),
    .m_axis_tready(framed_ready),.m_axis_tlast(framed_last),.m_axis_tuser(framed_user),.busy(framer_busy));
axis_arb_mux #(.S_COUNT(2),.DATA_WIDTH(128),.KEEP_ENABLE(1),.KEEP_WIDTH(16),
    .ID_ENABLE(0),.S_ID_WIDTH(1),.M_ID_WIDTH(2),.DEST_ENABLE(0),.DEST_WIDTH(1),
    .USER_ENABLE(1),.USER_WIDTH(TX_TAG_WIDTH+1),.LAST_ENABLE(1),.UPDATE_TID(0),
    .ARB_TYPE_ROUND_ROBIN(1),.ARB_LSB_HIGH_PRIORITY(1)) merge(
    .clk(clk),.rst(rst),.s_axis_tdata({framed_data,s_axis_native_tdata}),
    .s_axis_tkeep({framed_keep,s_axis_native_tkeep}),
    .s_axis_tvalid({framed_valid,s_axis_native_tvalid && native_tag_ok}),
    .s_axis_tready({framed_ready,native_ready}),.s_axis_tlast({framed_last,s_axis_native_tlast}),
    .s_axis_tid(2'b0),.s_axis_tdest(2'b0),.s_axis_tuser({tag,framed_user,s_axis_native_tuser}),
    .m_axis_tdata(m_axis_mac_tdata),.m_axis_tkeep(m_axis_mac_tkeep),.m_axis_tvalid(m_axis_mac_tvalid),
    .m_axis_tready(m_axis_mac_tready),.m_axis_tlast(m_axis_mac_tlast),
    .m_axis_tid(),.m_axis_tdest(),.m_axis_tuser(m_axis_mac_tuser));
always @(posedge clk)begin
    if(rst)begin
        owner<=0;local_mac<=0;peer_mac<=0;next_tag<=1;tag<=0;active<=0;header_sent<=0;
        ip_done<=0;mac_started<=0;mac_done<=0;receipt_seen<=0;ip_bytes<=0;tail_left<=0;
        timestamp<=0;m_mac_valid<=0;fault<=0;fault_code<=0;tags_exhausted<=0;
        frame_count<=0;receipt_count<=0;proof_count<=0;
    end else begin
        if(tail_left!=0)tail_left<=tail_left-1'b1;
        if(s_owner_valid && s_owner_ready)begin
            owner<=s_owner_context;local_mac<=s_owner_local_mac;peer_mac<=s_owner_peer_mac;
            tag<=LOCAL_CLASS | {{(TX_TAG_WIDTH-TAG_SEQUENCE_WIDTH){1'b0}},next_tag};
            if(&next_tag)tags_exhausted<=1;else next_tag<=next_tag+1'b1;
            active<=1;header_sent<=0;ip_done<=0;mac_started<=0;mac_done<=0;receipt_seen<=0;
            ip_bytes<=0;timestamp<=0;
        end
        if(ip_offer && !header_sent && header_ready)header_sent<=1;
        if(ip_take)begin
            ip_bytes<=ip_next[15:0];
            if(s_axis_ip_tlast)ip_done<=1;
        end
        if(mac_take)begin
            mac_started<=1;
            if(m_axis_mac_tlast)begin
                mac_done<=1;frame_count<=frame_count+1'b1;tail_left<=TAIL_CYCLES;
            end
        end
        if(cpl_take && good_receipt)begin
            receipt_seen<=1;timestamp<=s_mac_cpl_ts;receipt_count<=receipt_count+1'b1;
            tail_left<=TAIL_CYCLES;
        end
        if(active && ip_done && mac_done && receipt_seen && tail_left==0 && !framer_busy &&
           !fault && !incoming_fault && !m_mac_valid)m_mac_valid<=1;
        // An already offered proof stays stable through faults. The separate
        // sticky fault/all-QP guard MUST participate in the final CQ gate.
        if(m_mac_valid && m_mac_ready && !fault && !incoming_fault)begin
            m_mac_valid<=0;active<=0;proof_count<=proof_count+1'b1;
        end
        if(incoming_fault && !fault)begin
            fault<=1;
            fault_code<=bad_owner ? 8'he1 : bad_cpl ? 8'he2 : bad_native ? 8'he3 : bad_ip_valid ? 8'he4 : 8'he5;
        end
    end
end
endmodule
`resetall
