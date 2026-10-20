// SPDX-License-Identifier: BSD-2-Clause-Views
// Ordinary zero WRITE/READ response lifetime OUTSIDE existing Atomic/native
// MAC routing. Capture the genuine normal-tag4000 Ethernet/IP response,
// validate it against the immutable service owner/core receipt, then transmit
// with an OWN fresh4001..5fff tag. Translate ONLY its real SFD receipt back
// to4000 for the unchanged inner response drain guard. Exact EOF+SFD+tail
// still required before actual service retirement. No RQ/CQ/DMA surrogate.
// Upstream actual whole-IP checksum/ICRC validation remains mandatory.
`resetall
`timescale 1ns/1ps
`default_nettype none
module rocev2_zero_service_mac #(
 parameter TAG_SEQUENCE_WIDTH=13,parameter TAIL_CYCLES=1024,
 parameter REAL_MAC_COMPLETION_ENABLE=1
)(
 input wire clk,input wire rst,input wire enable,input wire parent_fault,
 input wire [527:0] s_owner,input wire s_owner_valid,output wire s_owner_ready,
 input wire [399:0] s_core_done,input wire s_core_valid,output wire s_core_ready,
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
 output wire [343:0] m_retire_owner,output wire [399:0] m_retire_core,
 output wire [15:0] m_retire_tag,output wire [95:0] m_retire_timestamp,
 output reg m_retire_valid=0,input wire m_retire_ready,
 output wire [7:0] queue_guard,output wire configuration_guard,output wire busy,
 output reg fault=0,output reg [7:0] fault_code=0,
 output wire [15:0] active_tag,output reg tags_exhausted=0,
 output reg [31:0] frame_count=0,output reg [31:0] receipt_count=0,output reg [31:0] retired_count=0
);
localparam COLLECT=0,CHECK=1,SEND=2,WAIT_MAC=3,READY=4;
localparam TAIL_WIDTH=$clog2(TAIL_CYCLES+1);
localparam MIN_TAIL_CYCLES=((62+4+8+12)*2+24)/25;
initial if(TAG_SEQUENCE_WIDTH<1 || TAG_SEQUENCE_WIDTH>13 || TAIL_CYCLES<MIN_TAIL_CYCLES ||
 TAIL_CYCLES<1 || REAL_MAC_COMPLETION_ENABLE!=1)$fatal(1,"unreviewed zero-service tag/tail or synthetic receipt");
reg [2:0] state=COLLECT;reg active=0,have_core=0,have_packet=0;
reg [527:0] owner=0;reg [399:0] core=0;reg [511:0] packet=0;
reg [2:0] capture_index=0,send_index=0;reg [6:0] packet_bytes=0;
reg [TAG_SEQUENCE_WIDTH-1:0] next_tag=1;reg [15:0] tag=0;reg [95:0] timestamp=0;
reg mac_started=0,mac_done=0,receipt_seen=0,tail_started=0;
reg [TAIL_WIDTH-1:0] tail_left=0;
wire halted=fault || parent_fault!==1'b0;
wire owner_ok=(^s_owner)!==1'bx && s_owner[23:0]<8 && s_owner[103:40]!=0 &&
 s_owner[167:104]!=0 && s_owner[183:168]!=0 && s_owner[343:312]==0 &&
 (s_owner[215:208]==8'h0a || s_owner[215:208]==8'h0c) &&
 s_owner[527:480]!=0 && !s_owner[520] && s_owner[479:432]!=0 && !s_owner[472];
assign s_owner_ready=enable && !active && !tags_exhausted && owner_ok && !halted && !rst;
assign s_core_ready=active && !have_core && !halted && !rst;
wire core_fire=s_core_valid && s_core_ready;
wire core_identity=(^s_core_done)!==1'bx && s_core_done[343:0]==owner[343:0] &&
 s_core_done[367:344]==owner[207:184]+24'd1 && s_core_done[399:392]==8'h0f;
wire input_known=(^{s_axis_native_tuser,s_axis_native_tkeep,s_axis_native_tlast})!==1'bx;
wire own_input=active && s_axis_native_tuser[16:1]==16'h4000;
wire input_reserved=s_axis_native_tuser[16:14]==3'b010 && s_axis_native_tuser[16:1]!=16'h4000;
wire capture_ready=active && state==COLLECT && !have_packet && capture_index<4 && !halted && !rst;
wire native_ready;
assign s_axis_native_tready=own_input ? capture_ready:native_ready && !input_reserved;
wire capture_fire=s_axis_native_tvalid && s_axis_native_tready && own_input;
reg [4:0] beat_bytes;reg data_known;integer lane;
always @*begin
 beat_bytes=0;data_known=1;
 for(lane=0;lane<16;lane=lane+1)begin
  beat_bytes=beat_bytes+{4'd0,s_axis_native_tkeep[lane]};
  if(s_axis_native_tkeep[lane] && (^s_axis_native_tdata[lane*8+:8])===1'bx)data_known=0;
 end
end
wire capture_shape=input_known && data_known && !s_axis_native_tuser[0] &&
 s_axis_native_tkeep!=0 && (s_axis_native_tkeep&(s_axis_native_tkeep+16'd1))==0 &&
 (s_axis_native_tlast || (s_axis_native_tkeep==16'hffff && capture_index<3));
function [7:0] octet;input [511:0] d;input integer p;begin octet=d[p*8+:8];end endfunction
function [15:0] be16;input [511:0] d;input integer p;begin be16={octet(d,p),octet(d,p+1)};end endfunction
function [23:0] be24;input [511:0] d;input integer p;begin be24={octet(d,p),octet(d,p+1),octet(d,p+2)};end endfunction
function [31:0] be32;input [511:0] d;input integer p;begin be32={be16(d,p),be16(d,p+2)};end endfunction
function [47:0] be48;input [511:0] d;input integer p;begin be48={be16(d,p),be16(d,p+2),be16(d,p+4)};end endfunction
wire packet_ok=packet_bytes==62 && be48(packet,0)==owner[479:432] && be48(packet,6)==owner[527:480] &&
 be16(packet,12)==16'h0800 && octet(packet,14)==8'h45 && be16(packet,16)==48 &&
 (be16(packet,20)&16'hbfff)==0 && octet(packet,23)==17 && be32(packet,26)==owner[431:400] &&
 be32(packet,30)==owner[399:368] && be16(packet,34)==4791 && be16(packet,36)==4791 &&
 be16(packet,38)==28 && be16(packet,40)==0 &&
 octet(packet,42)==(owner[215:208]==8'h0c ? 8'h10:8'h11) &&
 (octet(packet,43)&8'hbf)==0 && be16(packet,44)==16'hffff && octet(packet,46)==0 &&
 be24(packet,47)==owner[367:344] && octet(packet,50)==0 && be24(packet,51)==owner[207:184] &&
 octet(packet,54)==0 && be24(packet,55)==core[391:368];
wire send_valid=active && state==SEND;
wire [127:0] send_data=packet[send_index*128+:128];
wire send_last=send_index==3;wire [15:0] send_keep=send_last ? 16'h3fff:16'hffff;
wire send_ready;
axis_arb_mux #(.S_COUNT(2),.DATA_WIDTH(128),.KEEP_ENABLE(1),.KEEP_WIDTH(16),
 .ID_ENABLE(0),.S_ID_WIDTH(1),.M_ID_WIDTH(2),.DEST_ENABLE(0),.DEST_WIDTH(1),
 .USER_ENABLE(1),.USER_WIDTH(17),.LAST_ENABLE(1),.UPDATE_TID(0),
 .ARB_TYPE_ROUND_ROBIN(1),.ARB_LSB_HIGH_PRIORITY(1)) merge(
 .clk(clk),.rst(rst),.s_axis_tdata({send_data,s_axis_native_tdata}),.s_axis_tkeep({send_keep,s_axis_native_tkeep}),
 .s_axis_tvalid({send_valid,s_axis_native_tvalid && !own_input && !input_reserved}),
 .s_axis_tready({send_ready,native_ready}),.s_axis_tlast({send_last,s_axis_native_tlast}),
 .s_axis_tid(2'b0),.s_axis_tdest(2'b0),.s_axis_tuser({tag,1'b0,s_axis_native_tuser}),
 .m_axis_tdata(m_axis_mac_tdata),.m_axis_tkeep(m_axis_mac_tkeep),.m_axis_tvalid(m_axis_mac_tvalid),
 .m_axis_tready(m_axis_mac_tready),.m_axis_tlast(m_axis_mac_tlast),.m_axis_tid(),.m_axis_tdest(),.m_axis_tuser(m_axis_mac_tuser));
wire mac_fire=m_axis_mac_tvalid && m_axis_mac_tready && m_axis_mac_tuser[16:1]==tag && active;
wire cpl_known=(^{s_mac_cpl_tag,s_mac_cpl_ts})!==1'bx;
wire own_cpl=s_mac_cpl_tag[15:13]==3'b010 && s_mac_cpl_tag!=16'h4000;
wire good_receipt=cpl_known && own_cpl && active && s_mac_cpl_tag==tag && !receipt_seen &&
 state>=SEND && (mac_started || mac_fire);
wire ordinary_cpl=cpl_known && !own_cpl && !(active && s_mac_cpl_tag==16'h4000);
assign m_native_cpl_tag=own_cpl ? 16'h4000:s_mac_cpl_tag;assign m_native_cpl_ts=s_mac_cpl_ts;
assign m_native_cpl_valid=s_mac_cpl_valid && (good_receipt || ordinary_cpl) && !rst;
assign s_mac_cpl_ready=!rst && ((good_receipt || ordinary_cpl) ? m_native_cpl_ready:1'b1);
wire cpl_fire=s_mac_cpl_valid && s_mac_cpl_ready;
wire bad_valid=(s_owner_valid!==1'b0 && s_owner_valid!==1'b1) ||
 (s_core_valid!==1'b0 && s_core_valid!==1'b1) ||
 (s_axis_native_tvalid!==1'b0 && s_axis_native_tvalid!==1'b1) ||
 (s_mac_cpl_valid!==1'b0 && s_mac_cpl_valid!==1'b1);
wire bad_offer=bad_valid || (enable && !active && s_owner_valid && !owner_ok) ||
 (!active && s_core_valid) || (s_axis_native_tvalid && (!input_known || input_reserved)) ||
 (capture_fire && !capture_shape) || (core_fire && !core_identity) ||
 (cpl_fire && !good_receipt && !ordinary_cpl) || (mac_fire && (mac_done || m_axis_mac_tuser[0]));
wire bad_join=active && state==CHECK && !packet_ok;
assign queue_guard=(halted || bad_offer || bad_join) ? 8'hff : active ? 8'h01<<owner[23:0] :
 (s_owner_valid && owner_ok) ? 8'h01<<s_owner[23:0]:8'd0;
assign configuration_guard=active || halted || (enable && s_owner_valid!==1'b0);
assign busy=active || halted;assign active_tag=tag;
assign m_retire_owner=owner[343:0];assign m_retire_core=core;
assign m_retire_tag=tag;assign m_retire_timestamp=timestamp;
always @(posedge clk)begin
 if(rst)begin
  state<=COLLECT;active<=0;have_core<=0;have_packet<=0;owner<=0;core<=0;packet<=0;
  capture_index<=0;send_index<=0;packet_bytes<=0;next_tag<=1;tag<=0;timestamp<=0;
  mac_started<=0;mac_done<=0;receipt_seen<=0;tail_started<=0;tail_left<=0;
  m_retire_valid<=0;tags_exhausted<=0;fault<=0;fault_code<=0;frame_count<=0;receipt_count<=0;retired_count<=0;
 end else begin
  if(tail_left!=0)tail_left<=tail_left-1'b1;
  if(s_owner_valid && s_owner_ready)begin
   owner<=s_owner;active<=1;state<=COLLECT;have_core<=0;have_packet<=0;packet<=0;core<=0;
   capture_index<=0;send_index<=0;packet_bytes<=0;timestamp<=0;mac_started<=0;mac_done<=0;
   receipt_seen<=0;tail_started<=0;tail_left<=0;
   tag<=16'h4000|{{(16-TAG_SEQUENCE_WIDTH){1'b0}},next_tag};
   if(&next_tag)tags_exhausted<=1;else next_tag<=next_tag+1'b1;
  end
  if(core_fire)begin core<=s_core_done;have_core<=1;end
  if(capture_fire)begin
   packet[capture_index*128+:128]<=s_axis_native_tdata;capture_index<=capture_index+1'b1;
   packet_bytes<=packet_bytes+{2'd0,beat_bytes};if(s_axis_native_tlast)have_packet<=1;
  end
  if(active && state==COLLECT && have_core && have_packet)state<=CHECK;
  if(state==CHECK && !halted && !bad_offer && !bad_join)state<=SEND;
  if(send_valid && send_ready)begin send_index<=send_index+1'b1;if(send_last)state<=WAIT_MAC;end
  if(mac_fire)begin mac_started<=1;if(m_axis_mac_tlast)begin mac_done<=1;frame_count<=frame_count+1'b1;end end
  if(cpl_fire && good_receipt)begin receipt_seen<=1;timestamp<=s_mac_cpl_ts;receipt_count<=receipt_count+1'b1;end
  if(active && mac_done && receipt_seen && !tail_started && !halted)begin tail_started<=1;tail_left<=TAIL_CYCLES[TAIL_WIDTH-1:0];end
  if(state==WAIT_MAC && tail_started && tail_left==0 && !halted && !bad_offer)begin m_retire_valid<=1;state<=READY;end
  if(m_retire_valid && m_retire_ready)begin
   m_retire_valid<=0;retired_count<=retired_count+1'b1;
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
