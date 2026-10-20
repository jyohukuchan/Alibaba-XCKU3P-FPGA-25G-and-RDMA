// SPDX-License-Identifier: BSD-2-Clause-Views
// Bind privileged RX route configuration to the SAME actual SQC owner table.
// A read-only lookup is NOT a lease: all actual downstream guards must feed
// SQC deletion/configuration protection. No packet/CQ/current-head authority.
// Whole-parent reset is not epoch recovery, cancellation or safe unpin proof.
`resetall
`timescale 1ns/1ps
`default_nettype none
module rocev2_atomic_qp_binding (
    input wire clk,input wire rst,input wire parent_fault,
    input wire cfg_valid,input wire cfg_fire,input wire cfg_tx_only,
    input wire [23:0] cfg_qpn,input wire [15:0] cfg_pd,
    input wire [23:0] cfg_peer_qpn,input wire [31:0] cfg_local_ip,input wire [31:0] cfg_peer_ip,
    output wire cfg_binding_ready,
    output wire [23:0] m_query_qpn,
    input wire [63:0] s_query_cookie,input wire [63:0] s_query_epoch,
    input wire [15:0] s_query_pd,input wire s_query_valid,
    // Genuine operation/configuration/queue guards, never a software drain.
    input wire lease_guard,
    output wire admission_valid,output reg bound_valid=0,
    output reg [23:0] bound_qpn=0,output reg [15:0] bound_pd=0,
    output reg [63:0] bound_cookie=0,output reg [63:0] bound_epoch=0,
    output reg [23:0] bound_peer_qpn=0,
    output reg [31:0] bound_local_ip=0,output reg [31:0] bound_peer_ip=0,
    output wire configuration_guard,output wire [7:0] queue_guard,
    output reg fault=0
);
wire halted=fault || parent_fault!==1'b0;
// cfg_fire is an observer of the final ready/valid handshake. Readiness MUST
// NOT depend on it, including its knownness (which would form a ready loop).
wire cfg_known=(^{cfg_valid,cfg_tx_only,cfg_qpn,cfg_pd,cfg_peer_qpn,cfg_local_ip,cfg_peer_ip})!==1'bx;
wire lookup_known=(^{s_query_valid,s_query_cookie,s_query_epoch,s_query_pd})!==1'bx;
wire query_for_config=cfg_valid && !cfg_tx_only && cfg_pd!=0;
assign m_query_qpn=query_for_config ? cfg_qpn : bound_valid ? bound_qpn:24'd0;
wire config_owner_ok=lookup_known && s_query_valid && s_query_pd==cfg_pd && s_query_epoch!=0 && s_query_cookie!=0;
wire live_owner_ok=lookup_known && s_query_valid && s_query_pd==bound_pd &&
    s_query_epoch==bound_epoch && s_query_cookie==bound_cookie;
assign cfg_binding_ready=cfg_known && cfg_qpn<24'd8 && !halted && !rst && lease_guard===1'b0 &&
    (cfg_tx_only || cfg_pd==0 || (config_owner_ok && cfg_local_ip!=0 && cfg_peer_ip!=0));
assign admission_valid=bound_valid && live_owner_ok && cfg_valid===1'b0 && !halted && !rst;
// A temporarily busy query port pauses NEW admission, not already-owned work.
// SQC producer updates may run while an Atomic lease is held. Do not abort
// that owner just because the read-only lookup is temporarily unavailable.
assign configuration_guard=lease_guard!==1'b0 || halted;
wire lease_known=lease_guard===1'b0 || lease_guard===1'b1;
assign queue_guard=(halted || !lease_known || (lease_guard && !bound_valid)) ? 8'hff :
    lease_guard ? (8'h01<<bound_qpn):8'd0;
wire bad_event=(cfg_valid!==1'b0 && cfg_valid!==1'b1) ||
    (cfg_fire!==1'b0 && cfg_fire!==1'b1) || (lease_guard!==1'b0 && lease_guard!==1'b1) ||
    (cfg_fire && !(cfg_valid && cfg_binding_ready)) || (lease_guard && !bound_valid);
always @(posedge clk)begin
    if(rst)begin
        bound_valid<=0;bound_qpn<=0;bound_pd<=0;bound_cookie<=0;bound_epoch<=0;
        bound_peer_qpn<=0;bound_local_ip<=0;bound_peer_ip<=0;fault<=0;
    end else begin
        if(parent_fault!==1'b0 || bad_event)fault<=1;
        if(cfg_valid && cfg_fire && cfg_binding_ready && !cfg_tx_only)begin
            // PD0 is the existing drained inaccessible route tombstone.
            // It revokes this binding; it never manufactures an epoch.
            bound_valid<=cfg_pd!=0;
            bound_qpn<=cfg_pd!=0 ? cfg_qpn:24'd0;bound_pd<=cfg_pd;
            bound_cookie<=cfg_pd!=0 ? s_query_cookie:64'd0;
            bound_epoch<=cfg_pd!=0 ? s_query_epoch:64'd0;
            bound_peer_qpn<=cfg_pd!=0 ? cfg_peer_qpn:24'd0;
            bound_local_ip<=cfg_pd!=0 ? cfg_local_ip:32'd0;
            bound_peer_ip<=cfg_pd!=0 ? cfg_peer_ip:32'd0;
        end
    end
end
endmodule
`resetall
