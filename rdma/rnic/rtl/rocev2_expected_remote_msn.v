// SPDX-License-Identifier: BSD-2-Clause-Views
// Trusted logical-message predictor for a freshly established RC peer QP.
// Route comes from actual privileged accepted QP configuration (TX-only too),
// identity from the genuine SQC owner lookup, never an RX/AETH/local RX MSN.
// One authorized WR increments once before wire issue; packet/retry activity
// never increments. Failed/no-wire work must quarantine until a NEW epoch.
// This predicts normal fresh-peer semantics, not takeover of an existing peer
// QP. Full RX/protocol/runtime/interop/timing proof remains required.
`resetall
`timescale 1ns/1ps
`default_nettype none
module rocev2_expected_remote_msn #(
 parameter MAX_QPS=8
)(
 input wire clk,input wire rst,input wire parent_fault,
 input wire route_valid,input wire [23:0] route_qpn,input wire [23:0] route_peer_qpn,
 input wire [31:0] route_local_ip,input wire [31:0] route_peer_ip,
 output wire [23:0] m_query_qpn,input wire s_query_valid,
 input wire [63:0] s_query_cookie,input wire [63:0] s_query_epoch,input wire [15:0] s_query_pd,
 input wire [747:0] s_owner_context,input wire s_owner_fire,output wire owner_eligible,
 input wire [747:0] s_expect_context,input wire s_expect_valid,output wire expect_eligible,
 output wire [23:0] expected_msn,
 input wire [747:0] s_retire_context,input wire s_retire_offer_valid,input wire s_retire_fire,
 output wire retire_eligible,
 output wire configuration_guard,output wire [MAX_QPS-1:0] queue_guard,output wire busy,
 output reg fault=0,output reg [7:0] fault_code=0,
 output reg [31:0] message_count=0,output reg [31:0] retired_count=0
);
reg [MAX_QPS-1:0] initialized=0;
reg [63:0] cookies[0:MAX_QPS-1],epochs[0:MAX_QPS-1],last_sequences[0:MAX_QPS-1];
reg [15:0] pds[0:MAX_QPS-1];reg [23:0] msns[0:MAX_QPS-1],peers[0:MAX_QPS-1];
reg [31:0] local_ips[0:MAX_QPS-1],peer_ips[0:MAX_QPS-1];
// The configuration observer exposes the last accepted snapshot, NOT the
// currently issued QP. Preserve every QP's accepted route independently.
reg [MAX_QPS-1:0] configured=0;
reg [23:0] configured_peers[0:MAX_QPS-1];
reg [31:0] configured_local_ips[0:MAX_QPS-1],configured_peer_ips[0:MAX_QPS-1];
reg active=0;reg [747:0] owner=0;reg [63:0] held_cookie=0;reg [23:0] held_msn=0;
wire [23:0] owner_qpn=owner[395:372];
wire owner_known=(^s_owner_context)!==1'bx;
wire [15:0] op=s_owner_context[339:324];
wire message_shape=owner_known && s_owner_context[19:0]==3 && s_owner_context[355:340]!=0 &&
 s_owner_context[523:460]!=0 && s_owner_context[459:396]!=0 &&
 (op==1 || op==2 || op==3 || op==5 || op==6 || op==7 || op==8);
assign m_query_qpn=active ? owner_qpn:message_shape ? s_owner_context[395:372]:
 route_valid===1'b1 ? route_qpn:24'd0;
wire [2:0] index=m_query_qpn[2:0];
wire route_known=(^{route_qpn,route_peer_qpn,route_local_ip,route_peer_ip})!==1'bx;
wire route_slot_known=(^route_qpn)!==1'bx && route_qpn<MAX_QPS;
wire [2:0] route_index=route_qpn[2:0];
wire route_shape=route_known && route_slot_known && route_local_ip!=0 && route_peer_ip!=0;
wire route_changed=route_slot_known && (route_valid!==configured[route_index] ||
 (route_valid===1'b1 && (route_peer_qpn!==configured_peers[route_index] ||
  route_local_ip!==configured_local_ips[route_index] || route_peer_ip!==configured_peer_ips[route_index])));
wire query_known=(^{s_query_valid,s_query_cookie,s_query_epoch,s_query_pd})!==1'bx;
wire binding_live=(^m_query_qpn)!==1'bx && m_query_qpn<MAX_QPS && configured[index] &&
 query_known && s_query_valid &&
 s_query_cookie!=0 && s_query_epoch!=0 && s_query_pd!=0;
wire same_identity=initialized[index] && s_query_cookie==cookies[index] &&
 s_query_epoch==epochs[index] && s_query_pd==pds[index];
wire same_route=configured_peers[index]==peers[index] && configured_local_ips[index]==local_ips[index] &&
 configured_peer_ips[index]==peer_ips[index];
wire newer=binding_live && (!initialized[index] || s_query_epoch>epochs[index]);
wire bad_idle_binding=!active && binding_live && initialized[index] &&
 (s_query_epoch<epochs[index] || (s_query_epoch==epochs[index] &&
  (!same_identity || (!same_route && last_sequences[index]!=0))));
wire active_binding_ok=binding_live && same_identity && same_route &&
 s_query_cookie==held_cookie && s_query_epoch==owner[459:396] && s_query_pd==owner[371:356];
wire owner_candidate=!active && !fault && parent_fault===1'b0 && binding_live && same_identity && same_route &&
 message_shape && s_owner_context[395:372]==m_query_qpn && s_owner_context[371:356]==s_query_pd &&
 s_owner_context[459:396]==s_query_epoch && s_owner_context[523:460]>last_sequences[index];
wire expect_match=(^s_expect_context)!==1'bx && active && s_expect_context==owner;
wire retire_match=(^s_retire_context)!==1'bx && active && s_retire_context==owner;
wire bad_event=(route_valid!==1'b0 && route_valid!==1'b1) ||
 (route_valid===1'b1 && !route_shape) || (active && route_changed) ||
 (s_owner_fire!==1'b0 && s_owner_fire!==1'b1) ||
 (s_expect_valid!==1'b0 && s_expect_valid!==1'b1) ||
 (s_retire_offer_valid!==1'b0 && s_retire_offer_valid!==1'b1) ||
 (s_retire_fire!==1'b0 && s_retire_fire!==1'b1) ||
 bad_idle_binding || (active && !active_binding_ok) ||
 (s_owner_fire && !owner_candidate) || (s_expect_valid && !expect_match) ||
 (s_retire_offer_valid && !retire_match) || (s_retire_fire && (!s_retire_offer_valid || !retire_match));
wire stopped=fault || parent_fault!==1'b0 || bad_event;
assign owner_eligible=owner_candidate && !stopped;
assign expect_eligible=expect_match && !stopped;
assign retire_eligible=retire_match && !stopped;
assign expected_msn=held_msn;
assign configuration_guard=active || stopped;
assign queue_guard=stopped ? {MAX_QPS{1'b1}}:active ?
 ({{(MAX_QPS-1){1'b0}},1'b1}<<owner_qpn):{MAX_QPS{1'b0}};
assign busy=active || stopped;
integer i;
initial if(MAX_QPS<1 || MAX_QPS>8)$fatal(1,"unreviewed expected-MSN QP geometry");
always @(posedge clk)begin
 if(rst)begin
  initialized<=0;configured<=0;active<=0;owner<=0;held_cookie<=0;held_msn<=0;
  fault<=0;fault_code<=0;message_count<=0;retired_count<=0;
  for(i=0;i<MAX_QPS;i=i+1)begin cookies[i]<=0;epochs[i]<=0;last_sequences[i]<=0;pds[i]<=0;
   msns[i]<=0;peers[i]<=0;local_ips[i]<=0;peer_ips[i]<=0;
   configured_peers[i]<=0;configured_local_ips[i]<=0;configured_peer_ips[i]<=0;end
 end else begin
  if(!stopped && !active && route_slot_known)begin
   configured[route_index]<=route_valid;
   if(route_valid)begin configured_peers[route_index]<=route_peer_qpn;
    configured_local_ips[route_index]<=route_local_ip;configured_peer_ips[route_index]<=route_peer_ip;end
  end
  if(!stopped && !active && binding_live)begin
   if(newer)begin
    initialized[index]<=1;cookies[index]<=s_query_cookie;epochs[index]<=s_query_epoch;pds[index]<=s_query_pd;
    msns[index]<=0;last_sequences[index]<=0;peers[index]<=configured_peers[index];
    local_ips[index]<=configured_local_ips[index];peer_ips[index]<=configured_peer_ips[index];
   end else if(same_identity && !same_route && last_sequences[index]==0)begin
    peers[index]<=configured_peers[index];local_ips[index]<=configured_local_ips[index];peer_ips[index]<=configured_peer_ips[index];
   end
  end
  if(s_owner_fire && owner_eligible)begin
   active<=1;owner<=s_owner_context;held_cookie<=s_query_cookie;held_msn<=msns[index]+24'd1;
   msns[index]<=msns[index]+24'd1;last_sequences[index]<=s_owner_context[523:460];message_count<=message_count+1'b1;
  end
  if(s_retire_fire && retire_eligible)begin active<=0;retired_count<=retired_count+1'b1;end
  if(!fault && (parent_fault!==1'b0 || bad_event))begin fault<=1;fault_code<=parent_fault!==1'b0 ? 8'ha1:8'ha2;end
 end
end
endmodule
`resetall
