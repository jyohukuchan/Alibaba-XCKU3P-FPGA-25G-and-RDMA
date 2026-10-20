// SPDX-License-Identifier: BSD-2-Clause-Views
// Unposted Atomic responder lifetime: immutable packet owner + actual owned
// service reply + consumed SAME-table core receipt + generated IP -> real
// Ethernet framer/shared native MAC. No invented receive WQE/CQ/global drain.
// Positive retirement requires OWN fresh SFD tag, accepted MAC EOF and tail.
// Drop requires genuine core/service no-packet proof and no offered IP frame.
// Integrate OUTSIDE existing WQE MAC routing: private tags1..8191 must never
// enter its inner native-tag policy. Other native traffic/completions pass.
// Tail contract:250MHz core,>=25Gb/s MAC, genuine SFD timestamps (NOT synthetic
// EOF fallback), bounded56B IP response. Whole-parent reset only; reset is NOT
// cancellation/unpin or safe tag reuse. All configuration must include this
// module's guard/fault even after a proven retirement is offered/accepted.
`resetall
`timescale 1ns/1ps
`default_nettype none
module rocev2_atomic_mac_tx #(
    parameter TAG_SEQUENCE_WIDTH=13,
    parameter TAIL_CYCLES=1024,
    parameter REAL_MAC_COMPLETION_ENABLE=1
)(
    input wire clk,input wire rst,input wire enable,input wire parent_fault,
    // ALL sideband authority must be snapshotted at actual packet admission,
    // not sampled later from a mutable current QP or service-head register.
    input wire [143:0] s_owner,input wire s_owner_valid,output wire s_owner_ready,
    input wire [47:0] s_owner_local_mac,input wire [47:0] s_owner_peer_mac,
    input wire [31:0] s_owner_local_ip,input wire [31:0] s_owner_peer_ip,
    input wire [23:0] s_owner_peer_qpn,
    input wire [391:0] s_service_reply,input wire s_service_valid,output wire s_service_ready,
    input wire [223:0] s_core_done,input wire s_core_valid,output wire s_core_ready,
    input wire [127:0] s_axis_ip_tdata,input wire [15:0] s_axis_ip_tkeep,
    input wire s_axis_ip_tvalid,output wire s_axis_ip_tready,input wire s_axis_ip_tlast,
    input wire [127:0] s_axis_native_tdata,input wire [15:0] s_axis_native_tkeep,
    input wire s_axis_native_tvalid,output wire s_axis_native_tready,
    input wire s_axis_native_tlast,input wire [16:0] s_axis_native_tuser,
    output wire [127:0] m_axis_mac_tdata,output wire [15:0] m_axis_mac_tkeep,
    output wire m_axis_mac_tvalid,input wire m_axis_mac_tready,
    output wire m_axis_mac_tlast,output wire [16:0] m_axis_mac_tuser,
    input wire [15:0] s_mac_cpl_tag,input wire [95:0] s_mac_cpl_ts,
    input wire s_mac_cpl_valid,output wire s_mac_cpl_ready,
    output wire [15:0] m_native_cpl_tag,output wire [95:0] m_native_cpl_ts,
    output wire m_native_cpl_valid,input wire m_native_cpl_ready,
    output wire [143:0] m_retire_owner,output wire [223:0] m_retire_core,
    output wire [15:0] m_retire_tag,output wire [95:0] m_retire_timestamp,
    output reg m_retire_valid=0,input wire m_retire_ready,
    output wire [7:0] queue_guard,output wire configuration_guard,output wire busy,
    output reg fault=0,output reg [7:0] fault_code=0,
    output wire [15:0] active_tag,output reg tags_exhausted=0,
    output reg [31:0] frame_count=0,output reg [31:0] receipt_count=0,
    output reg [31:0] retired_count=0,output reg [31:0] drop_retired_count=0
);
localparam [2:0] COLLECT=0,CHECK=1,SEND=2,WAIT_MAC=3,READY=4;
localparam TAIL_WIDTH=$clog2(TAIL_CYCLES+1);
localparam MIN_TAIL_CYCLES=((56+14+4+8+12)*2+24)/25;
initial if(TAG_SEQUENCE_WIDTH<1 || TAG_SEQUENCE_WIDTH>13 || TAIL_CYCLES<MIN_TAIL_CYCLES ||
    TAIL_CYCLES<1 || REAL_MAC_COMPLETION_ENABLE!=1)$fatal(1,"unreviewed Atomic MAC tag/tail or synthetic receipt");
reg [2:0] state=COLLECT;
reg active=0,have_service=0,have_core=0,have_packet=0;
reg [143:0] owner=0;reg [391:0] reply=0;reg [223:0] core=0;
reg [47:0] local_mac=0,peer_mac=0;reg [31:0] local_ip=0,peer_ip=0;reg [23:0] peer_qpn=0;
reg [511:0] packet=0;reg [6:0] packet_bytes=0;reg [2:0] capture_index=0,send_index=0;
reg [TAG_SEQUENCE_WIDTH-1:0] next_tag=1;reg [15:0] tag=0;reg [95:0] timestamp=0;
reg header_sent=0,ip_done=0,mac_started=0,mac_done=0,receipt_seen=0,tail_started=0;
reg [TAIL_WIDTH-1:0] tail_left=0;
wire halted=fault || parent_fault!==1'b0;
wire owner_known=(^{s_owner,s_owner_local_mac,s_owner_peer_mac,s_owner_local_ip,s_owner_peer_ip,s_owner_peer_qpn})!==1'bx;
wire owner_ok=owner_known && s_owner[23:0]<24'd8 && s_owner[87:24]!=0 && s_owner[143:112]!=0 &&
    s_owner_local_mac!=0 && !s_owner_local_mac[40] && s_owner_peer_mac!=0 && !s_owner_peer_mac[40];
assign s_owner_ready=enable && !active && !halted && !tags_exhausted && owner_ok && !rst;
assign s_service_ready=active && !have_service && !halted && !rst;
assign s_core_ready=active && !have_core && !halted && !rst;
assign s_axis_ip_tready=active && !have_packet && capture_index<4 && !halted && !rst;
wire service_fire=s_service_valid && s_service_ready,core_fire=s_core_valid && s_core_ready;
wire ip_fire=s_axis_ip_tvalid && s_axis_ip_tready;
wire service_identity=(^s_service_reply)!==1'bx && s_service_reply[391:248]==owner &&
    s_service_reply[215:192]==owner[23:0] && s_service_reply[239:216]==owner[111:88];
wire core_identity=(^s_core_done)!==1'bx && s_core_done[143:0]==owner && s_core_done[223:208]==0 &&
    s_core_done[202:200]==7 && s_core_done[207:206]==0 &&
    (s_core_done[151:144]==8'h13 || s_core_done[151:144]==8'h14);
reg [4:0] beat_bytes;reg ip_known;integer lane;
always @*begin
    beat_bytes=0;ip_known=1;
    for(lane=0;lane<16;lane=lane+1)begin
        beat_bytes=beat_bytes+{4'd0,s_axis_ip_tkeep[lane]};
        if(s_axis_ip_tkeep[lane] && (^s_axis_ip_tdata[lane*8+:8])===1'bx)ip_known=0;
    end
end
wire ip_shape=(^{s_axis_ip_tkeep,s_axis_ip_tlast})!==1'bx && ip_known && s_axis_ip_tkeep!=0 &&
    (s_axis_ip_tkeep&(s_axis_ip_tkeep+16'd1))==0 && (s_axis_ip_tlast || s_axis_ip_tkeep==16'hffff) &&
    (s_axis_ip_tlast || capture_index<3);
function [7:0] octet;input [511:0] d;input integer p;begin octet=d[p*8+:8];end endfunction
function [15:0] be16;input [511:0] d;input integer p;begin be16={octet(d,p),octet(d,p+1)};end endfunction
function [31:0] be32;input [511:0] d;input integer p;begin be32={be16(d,p),be16(d,p+2)};end endfunction
wire drop=reply[247],advance=reply[246];wire [5:0] response_bytes=reply[245:240];
wire [23:0] response_psn={reply[79:72],reply[87:80],reply[95:88]};
wire [23:0] response_msn={reply[111:104],reply[119:112],reply[127:120]};
wire response_success=reply[7:0]==8'h12 && response_bytes==24 && reply[103:96]==8'h1f;
wire response_nak=reply[7:0]==8'h11 && response_bytes==16 && !advance && reply[191:128]==0 &&
    (reply[103:96]==8'h60 || reply[103:96]==8'h61 || reply[103:96]==8'h62);
wire service_shape=drop ? (!advance && response_bytes==0 && reply[191:0]==0) :
    ((response_success || response_nak) && reply[15:8]==0 && reply[31:16]==16'hffff && reply[39:32]==0 &&
    {reply[47:40],reply[55:48],reply[63:56]}==peer_qpn && reply[71:64]==0 &&
    ((response_nak && reply[103:96]==8'h60) || response_psn==owner[111:88]));
wire joined_core=core[205]==drop && core[204]==advance && core[203]==!drop &&
    (!advance || (response_success && core[175:152]==owner[111:88]+24'd1 && core[199:176]==response_msn)) &&
    (!response_nak || (core[199:176]==response_msn && (reply[103:96]!=8'h60 || core[175:152]==response_psn)));
reg body_match;integer n;
always @*begin
    body_match=1;
    for(n=0;n<24;n=n+1)if(n<{26'd0,response_bytes})begin
        if(packet[(28+n)*8+:8]!=(n==1 ? reply[n*8+:8]|8'h40 : reply[n*8+:8]))body_match=0;
    end
end
wire packet_ok=have_packet && packet_bytes=={1'b0,response_bytes}+7'd32 &&
    octet(packet,0)==8'h45 && be16(packet,2)=={10'd0,response_bytes}+16'd32 && octet(packet,9)==17 &&
    (be16(packet,6)&16'hbfff)==0 && be32(packet,12)==local_ip && be32(packet,16)==peer_ip &&
    be16(packet,20)==4791 && be16(packet,22)==4791 && be16(packet,24)=={10'd0,response_bytes}+16'd12 &&
    be16(packet,26)==0 && body_match;
wire native_tag_ok=(^s_axis_native_tuser)!==1'bx &&
    (s_axis_native_tuser[16] || s_axis_native_tuser[16:1]==0 || s_axis_native_tuser[16:1]==16'h4000 ||
     s_axis_native_tuser[16:14]==3'b001 || s_axis_native_tuser[16:14]==3'b011);
wire native_ready;
assign s_axis_native_tready=native_ready && native_tag_ok;
wire cpl_known=(^{s_mac_cpl_tag,s_mac_cpl_ts})!==1'bx;
wire own_cpl=s_mac_cpl_tag[15:13]==0 && s_mac_cpl_tag!=0;
wire native_cpl=cpl_known && (s_mac_cpl_tag[15] || s_mac_cpl_tag==0 || s_mac_cpl_tag==16'h4000 ||
    s_mac_cpl_tag[15:13]==3'b001 || s_mac_cpl_tag[15:13]==3'b011);
assign m_native_cpl_tag=s_mac_cpl_tag;assign m_native_cpl_ts=s_mac_cpl_ts;
assign m_native_cpl_valid=s_mac_cpl_valid && native_cpl && !rst;
assign s_mac_cpl_ready=!rst && (native_cpl ? m_native_cpl_ready : 1'b1);
wire mac_atomic=m_axis_mac_tuser[16:14]==0 && m_axis_mac_tuser[16:1]!=0;
wire mac_fire=m_axis_mac_tvalid && m_axis_mac_tready && mac_atomic;
wire cpl_fire=s_mac_cpl_valid && s_mac_cpl_ready;
wire good_receipt=cpl_known && own_cpl && active && !drop && state>=SEND && s_mac_cpl_tag==tag &&
    !receipt_seen && (mac_started || mac_fire);
wire bad_valid=(s_owner_valid!==1'b0 && s_owner_valid!==1'b1) ||
    (s_service_valid!==1'b0 && s_service_valid!==1'b1) || (s_core_valid!==1'b0 && s_core_valid!==1'b1) ||
    (s_axis_ip_tvalid!==1'b0 && s_axis_ip_tvalid!==1'b1) ||
    (s_axis_native_tvalid!==1'b0 && s_axis_native_tvalid!==1'b1) || (s_mac_cpl_valid!==1'b0 && s_mac_cpl_valid!==1'b1);
wire bad_offer=bad_valid || (enable && !active && s_owner_valid && !owner_ok) ||
    (!active && (s_service_valid || s_core_valid || s_axis_ip_tvalid)) ||
    (have_service && drop && s_axis_ip_tvalid) || (s_axis_native_tvalid && !native_tag_ok) ||
    (ip_fire && !ip_shape) || (service_fire && !service_identity) || (core_fire && !core_identity) ||
    (cpl_fire && (!cpl_known || (!native_cpl && !good_receipt))) ||
    (mac_fire && (m_axis_mac_tuser[0] || !active || mac_done));
wire bad_join=active && state==CHECK && (!service_shape || !joined_core ||
    (drop ? (have_packet || s_axis_ip_tvalid):!packet_ok));
assign queue_guard=(halted || bad_offer || bad_join) ? 8'hff : active ? (8'h01<<owner[23:0]) :
    (s_owner_valid && owner_ok) ? (8'h01<<s_owner[23:0]):8'd0;
assign configuration_guard=active || fault || (enable && s_owner_valid!==1'b0);
assign busy=active || fault;assign active_tag=tag;
assign m_retire_owner=owner;assign m_retire_core=core;
assign m_retire_tag=drop ? 16'd0:tag;assign m_retire_timestamp=drop ? 96'd0:timestamp;
wire ip_offer=active && state==SEND && !ip_done;
wire ip_last=({4'd0,send_index}+7'd1)*7'd16>=packet_bytes;
wire [15:0] ip_keep=packet_bytes==56 && ip_last ? 16'h00ff:16'hffff;
wire framer_ready,framer_busy,framer_header_ready,framed_valid,framed_ready,framed_last,framed_user;
wire [127:0] framed_data;wire [15:0] framed_keep;
wire [1:0] unused_tid;wire unused_tdest;
eth_axis_tx #(.DATA_WIDTH(128),.KEEP_ENABLE(1),.KEEP_WIDTH(16)) framer(
    .clk(clk),.rst(rst),.s_eth_hdr_valid(ip_offer && !header_sent),.s_eth_hdr_ready(framer_header_ready),
    .s_eth_dest_mac(peer_mac),.s_eth_src_mac(local_mac),.s_eth_type(16'h0800),
    .s_eth_payload_axis_tdata(packet[send_index*128+:128]),.s_eth_payload_axis_tkeep(ip_keep),
    .s_eth_payload_axis_tvalid(ip_offer),.s_eth_payload_axis_tready(framer_ready),
    .s_eth_payload_axis_tlast(ip_last),.s_eth_payload_axis_tuser(1'b0),
    .m_axis_tdata(framed_data),.m_axis_tkeep(framed_keep),.m_axis_tvalid(framed_valid),
    .m_axis_tready(framed_ready),.m_axis_tlast(framed_last),.m_axis_tuser(framed_user),.busy(framer_busy));
axis_arb_mux #(.S_COUNT(2),.DATA_WIDTH(128),.KEEP_ENABLE(1),.KEEP_WIDTH(16),
    .ID_ENABLE(0),.S_ID_WIDTH(1),.M_ID_WIDTH(2),.DEST_ENABLE(0),.DEST_WIDTH(1),
    .USER_ENABLE(1),.USER_WIDTH(17),.LAST_ENABLE(1),.UPDATE_TID(0),
    .ARB_TYPE_ROUND_ROBIN(1),.ARB_LSB_HIGH_PRIORITY(1)) merge(
    .clk(clk),.rst(rst),.s_axis_tdata({framed_data,s_axis_native_tdata}),.s_axis_tkeep({framed_keep,s_axis_native_tkeep}),
    .s_axis_tvalid({framed_valid,s_axis_native_tvalid && native_tag_ok}),.s_axis_tready({framed_ready,native_ready}),
    .s_axis_tlast({framed_last,s_axis_native_tlast}),.s_axis_tid(2'b0),.s_axis_tdest(2'b0),.s_axis_tuser({tag,framed_user,s_axis_native_tuser}),
    .m_axis_tdata(m_axis_mac_tdata),.m_axis_tkeep(m_axis_mac_tkeep),.m_axis_tvalid(m_axis_mac_tvalid),
    .m_axis_tready(m_axis_mac_tready),.m_axis_tlast(m_axis_mac_tlast),.m_axis_tid(unused_tid),.m_axis_tdest(unused_tdest),.m_axis_tuser(m_axis_mac_tuser));
always @(posedge clk)begin
    if(rst)begin
        state<=COLLECT;active<=0;owner<=0;reply<=0;core<=0;local_mac<=0;peer_mac<=0;local_ip<=0;peer_ip<=0;peer_qpn<=0;
        have_service<=0;have_core<=0;have_packet<=0;packet<=0;packet_bytes<=0;capture_index<=0;send_index<=0;
        next_tag<=1;tag<=0;timestamp<=0;header_sent<=0;ip_done<=0;mac_started<=0;mac_done<=0;receipt_seen<=0;
        tail_started<=0;tail_left<=0;m_retire_valid<=0;tags_exhausted<=0;fault<=0;fault_code<=0;
        frame_count<=0;receipt_count<=0;retired_count<=0;drop_retired_count<=0;
    end else begin
        if(tail_left!=0)tail_left<=tail_left-1'b1;
        if(s_owner_valid && s_owner_ready)begin
            owner<=s_owner;local_mac<=s_owner_local_mac;peer_mac<=s_owner_peer_mac;
            local_ip<=s_owner_local_ip;peer_ip<=s_owner_peer_ip;peer_qpn<=s_owner_peer_qpn;
            active<=1;state<=COLLECT;have_service<=0;have_core<=0;have_packet<=0;reply<=0;core<=0;
            packet<=0;packet_bytes<=0;capture_index<=0;send_index<=0;header_sent<=0;ip_done<=0;
            mac_started<=0;mac_done<=0;receipt_seen<=0;tail_started<=0;tail_left<=0;timestamp<=0;
            tag<={{(16-TAG_SEQUENCE_WIDTH){1'b0}},next_tag};
            if(&next_tag)tags_exhausted<=1;else next_tag<=next_tag+1'b1;
        end
        if(service_fire)begin reply<=s_service_reply;have_service<=1;end
        if(core_fire)begin core<=s_core_done;have_core<=1;end
        if(ip_fire)begin
            packet[capture_index*128+:128]<=s_axis_ip_tdata;packet_bytes<=packet_bytes+{2'd0,beat_bytes};
            capture_index<=capture_index+1'b1;if(s_axis_ip_tlast)have_packet<=1;
        end
        if(active && state==COLLECT && have_service && have_core && (drop || have_packet))state<=CHECK;
        if(state==CHECK && !halted && !bad_offer && !bad_join)begin
            if(drop)begin m_retire_valid<=1;state<=READY;end
            else state<=SEND;
        end
        // Offered frame and retirement beats are never retracted by a later
        // disable/fault. A late fault still retains this owner's guard.
        if(ip_offer && !header_sent && framer_header_ready)header_sent<=1;
        if(ip_offer && framer_ready)begin send_index<=send_index+1'b1;if(ip_last)ip_done<=1;end
        if(mac_fire)begin
            mac_started<=1;
            if(m_axis_mac_tlast)begin mac_done<=1;frame_count<=frame_count+1'b1;state<=WAIT_MAC;end
        end
        if(cpl_fire && good_receipt)begin receipt_seen<=1;timestamp<=s_mac_cpl_ts;receipt_count<=receipt_count+1'b1;end
        if(active && mac_done && receipt_seen && !tail_started && !halted)begin
            tail_started<=1;tail_left<=TAIL_CYCLES[TAIL_WIDTH-1:0];
        end
        if(state==WAIT_MAC && tail_started && tail_left==0 && !framer_busy && !halted && !bad_offer)begin
            m_retire_valid<=1;state<=READY;
        end
        if(m_retire_valid && m_retire_ready)begin
            m_retire_valid<=0;retired_count<=retired_count+1'b1;if(drop)drop_retired_count<=drop_retired_count+1'b1;
            if(!halted && !bad_offer && !bad_join)begin active<=0;state<=COLLECT;end
        end
        if(!fault)begin
            if(parent_fault!==1'b0)begin fault<=1;fault_code<=8'ha0;end
            else if(bad_offer)begin fault<=1;fault_code<=8'ha1;end
            else if(bad_join)begin fault<=1;fault_code<=8'ha2;end
        end
    end
end
endmodule
`resetall
