// SPDX-License-Identifier: BSD-2-Clause-Views
// Matched real HLS368/248 ABI -> protected RTL Atomic executor. The native
// wire/QP guard must supply the TRUE owner QPN/epoch; do not source authority
// from a packet. PD/peer/key mapping remains the existing trusted controller.
// Registered completion holds ownership beyond executor handoff. Not a
// MAC/CQ/drain/unpin or reset-recovery proof; not default-native integrated.
`resetall
`timescale 1ns/1ps
`default_nettype none
module rocev2_atomic_service_adapter (
    input wire clk, input wire rst, input wire enable,
    input wire [367:0] s_hls_request, input wire s_hls_request_valid,
    output wire s_hls_request_ready,
    input wire [23:0] s_owner_qpn, input wire [63:0] s_owner_epoch,
    input wire s_owner_valid, output wire s_owner_ready,
    output wire [319:0] m_execute_header, output wire [5:0] m_execute_bytes,
    output wire [23:0] m_execute_expected_psn, output wire [23:0] m_execute_msn,
    output wire [63:0] m_execute_epoch, output wire m_execute_valid,
    input wire m_execute_ready,
    input wire [191:0] s_execute_response_header, input wire [5:0] s_execute_response_bytes,
    input wire [23:0] s_execute_response_qpn, input wire [63:0] s_execute_response_epoch,
    input wire s_execute_response_advance, input wire s_execute_response_drop,
    input wire s_execute_response_valid, output wire s_execute_response_ready,
    output reg [247:0] m_hls_reply=0, output reg m_hls_reply_valid=0,
    input wire m_hls_reply_ready,
    output wire busy, output wire configuration_guard,
    output reg fault=0, output reg [7:0] fault_code=0
);
reg active=0;
reg [23:0] qpn=0,request_psn=0;
reg [63:0] epoch=0;
wire [23:0] wire_qpn={s_hls_request[47:40],s_hls_request[55:48],s_hls_request[63:56]};
wire [23:0] wire_psn={s_hls_request[79:72],s_hls_request[87:80],s_hls_request[95:88]};
wire request_known=(^{s_hls_request,s_owner_qpn,s_owner_epoch})!==1'bx;
wire request_match=request_known && wire_qpn==s_owner_qpn && s_owner_qpn<8 && s_owner_epoch!=0;
wire offer=enable && !active && !fault && !rst && s_hls_request_valid && s_owner_valid;
assign m_execute_header=s_hls_request[319:0];assign m_execute_bytes=40;
assign m_execute_expected_psn=s_hls_request[343:320];assign m_execute_msn=s_hls_request[367:344];
assign m_execute_epoch=s_owner_epoch;assign m_execute_valid=offer && request_match;
assign s_hls_request_ready=m_execute_valid && m_execute_ready;
assign s_owner_ready=s_hls_request_ready;
wire response_known=(^{s_execute_response_header,s_execute_response_bytes,
    s_execute_response_qpn,s_execute_response_epoch,s_execute_response_advance,s_execute_response_drop})!==1'bx;
wire response_match=response_known && s_execute_response_qpn==qpn && s_execute_response_epoch==epoch;
assign s_execute_response_ready=active && !m_hls_reply_valid && !fault && !rst && response_match;
assign busy=active || m_hls_reply_valid || fault;
assign configuration_guard=busy || (enable && (s_hls_request_valid!==1'b0 || s_owner_valid!==1'b0));
always @(posedge clk)begin
    if(rst)begin active<=0;qpn<=0;request_psn<=0;epoch<=0;m_hls_reply<=0;m_hls_reply_valid<=0;fault<=0;fault_code<=0;end
    else begin
        if(m_execute_valid && m_execute_ready)begin
            active<=1;qpn<=s_owner_qpn;request_psn<=wire_psn;epoch<=s_owner_epoch;
        end
        if(s_execute_response_valid && s_execute_response_ready)begin
            m_hls_reply<={s_execute_response_drop,s_execute_response_advance,
                s_execute_response_bytes,request_psn,qpn,s_execute_response_header};
            m_hls_reply_valid<=1;
        end
        // Offered replies never retract on disable/fault; no later request or
        // configuration is admitted by a consumed reply while fault is set.
        if(m_hls_reply_valid && m_hls_reply_ready)begin
            m_hls_reply_valid<=0;if(!fault)active<=0;
        end
        if(!fault)begin
            if((s_hls_request_valid!==1'b0 && s_hls_request_valid!==1'b1) ||
               (s_owner_valid!==1'b0 && s_owner_valid!==1'b1) || (offer && !request_match))begin fault<=1;fault_code<=8'h81;end
            if((s_execute_response_valid!==1'b0 && s_execute_response_valid!==1'b1) ||
               (s_execute_response_valid && (!active || m_hls_reply_valid || !response_match)))begin fault<=1;fault_code<=8'h82;end
        end
    end
end
endmodule
`resetall
