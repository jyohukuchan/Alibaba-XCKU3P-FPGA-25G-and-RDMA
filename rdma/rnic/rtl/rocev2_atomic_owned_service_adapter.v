// SPDX-License-Identifier: BSD-2-Clause-Views
// Owned512/392 HLS ABI. The packet guard's immutable QPN/epoch/PSN/nonce
// travels THROUGH HLS, not a current-head or CSR lookup at service time.
// Registered execution offers survive disable/backpressure. This reply is
// NOT the HLS consumed/table-readback receipt or MAC/native retirement.
`resetall
`timescale 1ns/1ps
`default_nettype none
module rocev2_atomic_owned_service_adapter (
    input wire clk, input wire rst, input wire enable,
    input wire [511:0] s_hls_request, input wire s_hls_request_valid,
    output wire s_hls_request_ready,
    output wire [319:0] m_execute_header, output wire [5:0] m_execute_bytes,
    output wire [23:0] m_execute_expected_psn, output wire [23:0] m_execute_msn,
    output wire [63:0] m_execute_epoch, output wire m_execute_valid,
    input wire m_execute_ready,
    input wire [191:0] s_execute_response_header, input wire [5:0] s_execute_response_bytes,
    input wire [23:0] s_execute_response_qpn, input wire [63:0] s_execute_response_epoch,
    input wire s_execute_response_advance, input wire s_execute_response_drop,
    input wire s_execute_response_valid, output wire s_execute_response_ready,
    output reg [391:0] m_hls_reply=0, output reg m_hls_reply_valid=0,
    input wire m_hls_reply_ready,
    output wire busy, output wire configuration_guard,
    output reg fault=0, output reg [7:0] fault_code=0
);
reg active=0,execute_valid=0;
reg [511:0] request=0;
wire [143:0] owner=request[511:368];
wire [23:0] qpn=owner[23:0],request_psn=owner[111:88];
wire [63:0] epoch=owner[87:24];
wire [143:0] incoming_owner=s_hls_request[511:368];
wire [23:0] wire_qpn={s_hls_request[47:40],s_hls_request[55:48],s_hls_request[63:56]};
wire [23:0] wire_psn={s_hls_request[79:72],s_hls_request[87:80],s_hls_request[95:88]};
wire request_known=(^s_hls_request)!==1'bx;
wire request_match=request_known && wire_qpn==incoming_owner[23:0] &&
    wire_psn==incoming_owner[111:88] && incoming_owner[23:0]<8 &&
    incoming_owner[87:24]!=0 && incoming_owner[143:112]!=0;
wire offer=enable && !active && !fault && !rst && s_hls_request_valid;
assign s_hls_request_ready=enable && !active && !fault && !rst && request_match;
assign m_execute_header=request[319:0];assign m_execute_bytes=40;
assign m_execute_expected_psn=request[343:320];assign m_execute_msn=request[367:344];
assign m_execute_epoch=epoch;assign m_execute_valid=execute_valid && !rst;
wire response_known=(^{s_execute_response_header,s_execute_response_bytes,
    s_execute_response_qpn,s_execute_response_epoch,s_execute_response_advance,s_execute_response_drop})!==1'bx;
wire response_match=response_known && s_execute_response_qpn==qpn && s_execute_response_epoch==epoch;
assign s_execute_response_ready=active && !execute_valid && !m_hls_reply_valid && !fault && !rst && response_match;
assign busy=active || m_hls_reply_valid || fault;
assign configuration_guard=busy || (enable && s_hls_request_valid!==1'b0);
always @(posedge clk)begin
    if(rst)begin active<=0;execute_valid<=0;request<=0;m_hls_reply<=0;m_hls_reply_valid<=0;fault<=0;fault_code<=0;end
    else begin
        if(s_hls_request_valid && s_hls_request_ready)begin active<=1;execute_valid<=1;request<=s_hls_request;end
        if(m_execute_valid && m_execute_ready)execute_valid<=0;
        if(s_execute_response_valid && s_execute_response_ready)begin
            m_hls_reply<={owner,s_execute_response_drop,s_execute_response_advance,
                s_execute_response_bytes,request_psn,qpn,s_execute_response_header};
            m_hls_reply_valid<=1;
        end
        if(m_hls_reply_valid && m_hls_reply_ready)begin m_hls_reply_valid<=0;if(!fault)active<=0;end
        if(!fault)begin
            if((s_hls_request_valid!==1'b0 && s_hls_request_valid!==1'b1) ||
               (offer && !request_match))begin fault<=1;fault_code<=8'h83;end
            if((s_execute_response_valid!==1'b0 && s_execute_response_valid!==1'b1) ||
               (s_execute_response_valid && (!active || execute_valid || m_hls_reply_valid || !response_match)))begin fault<=1;fault_code<=8'h84;end
        end
    end
end
endmodule
`resetall
