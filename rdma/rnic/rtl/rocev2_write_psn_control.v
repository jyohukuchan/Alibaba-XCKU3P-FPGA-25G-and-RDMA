// SPDX-License-Identifier: BSD-2-Clause-Views
// Certified checked WRITE PSN reject -> SAME HLS and actual ACK/MAC proof.
// Never executes/replays data, takes RQ, commits PSN or publishes CQ.
// Suppression tracks genuine native expected-PSN/epoch/cookie progress only;
// it is NOT a drain/unpin/lifetime certificate. Fatal QP recovery is separate.
`resetall
`timescale 1ns/1ps
`default_nettype none
module rocev2_write_psn_control #(
 parameter [63:0] INITIAL_SERIAL=0
)(
 input wire clk,rst,enable,parent_fault,
 input wire trusted_valid,input wire [355:0] trusted_context,input wire [23:0] trusted_expected_psn,
 input wire [7:0] s_error,input wire [23:0] s_qpn,s_psn,s_msn,input wire s_keep_message,s_valid,
 input wire s_cert_valid,input wire [355:0] s_cert_context,input wire [23:0] s_cert_received_psn,s_cert_expected_psn,
 output wire s_ready,output wire m_error_valid,input wire m_error_ready,
 output wire [479:0] m_ack_owner,output wire m_ack_owner_valid,input wire m_ack_owner_ready,
 input wire [527:0] s_ack_done,input wire s_ack_done_valid,output wire s_ack_done_ready,
 output wire [479:0] m_ack_retire_owner,output wire m_ack_retire_valid,input wire m_ack_retire_ready,
 output wire [479:0] m_hls_owner,output wire m_hls_owner_valid,input wire m_hls_owner_ready,
 output wire tx_release,configuration_guard,output wire [7:0] queue_guard,
 output reg fault=0,output reg [7:0] fault_code=0,
 output reg [31:0] requests=0,wire_proofs=0,retirements=0,reports=0,suppressed=0
);
localparam IDLE=0,OWNER=1,EVENT=2,PROOF=3,RETIRE=4,REPORT=5;
reg [2:0] state=IDLE;
reg [479:0] owner=0;
reg [80:0] reject_snapshot=0;
reg [63:0] last_serial=INITIAL_SERIAL;
reg [7:0] nak_sent=0;
reg [23:0] nak_expected[0:7];
reg [127:0] nak_identity[0:7];
integer k;
wire halted=fault || parent_fault!==1'b0;
wire error_known=(^{s_error,s_qpn,s_psn,s_msn,s_keep_message})!==1'bx;
wire current_known=(^{trusted_context,trusted_expected_psn})!==1'bx;
wire current_ok=trusted_valid===1'b1 && current_known && trusted_context[23:0]<8 &&
 trusted_context[39:24]!=0 && trusted_context[103:40]!=0 && trusted_context[167:104]!=0;
wire request=enable===1'b1 && s_valid===1'b1 && s_error===8'd18 && s_cert_valid===1'b1;
wire context_ok=current_ok && error_known &&
 (^{s_cert_context,s_cert_received_psn,s_cert_expected_psn})!==1'bx &&
 s_cert_context===trusted_context && s_cert_context[353]===1'b1 &&
 s_qpn===s_cert_context[23:0] && s_psn===s_cert_received_psn && s_cert_expected_psn===trusted_expected_psn;
wire [23:0] delta=s_cert_received_psn-s_cert_expected_psn;
wire [23:0] behind=s_cert_expected_psn-s_cert_received_psn;
wire future=delta!=0 && !delta[23];
wire duplicate=behind!=0 && !behind[23];
wire repeat_nak=context_ok && future && nak_sent[s_qpn] &&
 nak_expected[s_qpn]===s_cert_expected_psn && nak_identity[s_qpn]===s_cert_context[167:40];
wire wire_request=request && (future || duplicate) && !repeat_nak;
wire input_ok=error_known && (s_cert_valid===1'b0 || s_cert_valid===1'b1) && (!request || context_ok);
wire retained=state!=IDLE;
wire stable_reject=s_valid===1'b1 && s_cert_valid===1'b1 && context_ok &&
 {s_error,s_qpn,s_psn,s_msn,s_keep_message}===reject_snapshot && s_cert_context===owner[355:0] &&
 s_cert_received_psn===owner[467:444] &&
 (owner[475:468]==8'h60 ? s_cert_expected_psn===owner[443:420]:s_cert_expected_psn===owner[443:420]+24'd1);
wire done_match=(^s_ack_done)!==1'bx && s_ack_done[479:0]===owner && s_ack_done[511:504]==0 &&
 s_ack_done[527:525]==3'b011 && s_ack_done[524:512]!=0;
assign m_ack_owner=owner;assign m_hls_owner=owner;assign m_ack_retire_owner=owner;
assign m_ack_owner_valid=state==OWNER && !halted && !rst;
assign m_hls_owner_valid=state==EVENT && !halted && !rst;
assign tx_release=(state==PROOF || state==RETIRE || state==REPORT) && !halted && !rst;
assign s_ack_done_ready=state==PROOF && done_match && !halted && !rst;
assign m_ack_retire_valid=state==RETIRE && !halted && !rst;
// A suppressed or ambiguous-half-window PSN is only a local reject/drop,
// never a fabricated wire response, positive receipt or resource retirement.
assign m_error_valid=!halted && !rst && input_ok && s_valid===1'b1 &&
 ((state==IDLE && !wire_request) || state==REPORT);
assign s_ready=!halted && !rst && input_ok &&
 ((state==IDLE && !wire_request) || state==REPORT) && m_error_ready;
assign configuration_guard=retained || request || halted;
assign queue_guard=halted ? 8'hff:retained ? 8'h01<<owner[23:0]:request && context_ok ? 8'h01<<s_qpn:8'd0;
always @(posedge clk)begin
 if(rst)begin
  state<=IDLE;owner<=0;reject_snapshot<=0;last_serial<=INITIAL_SERIAL;nak_sent<=0;
  for(k=0;k<8;k=k+1)begin nak_expected[k]<=0;nak_identity[k]<=0;end
  fault<=0;fault_code<=0;requests<=0;wire_proofs<=0;retirements<=0;reports<=0;suppressed<=0;
 end else begin
  if(parent_fault!==1'b0 || s_valid!==1'b0 && s_valid!==1'b1 ||
     s_valid===1'b1 && (!error_known || s_cert_valid!==1'b0 && s_cert_valid!==1'b1) ||
     request && !context_ok || retained && !stable_reject)begin fault<=1;fault_code<=8'ha1;end
  if(s_ack_done_valid!==1'b0 && s_ack_done_valid!==1'b1 ||
     s_ack_done_valid===1'b1 && (state!=PROOF || !done_match))begin fault<=1;fault_code<=8'ha2;end
  // Only authoritative native context/frontier observation clears suppression.
  if(current_ok && nak_sent[trusted_context[23:0]] &&
     (nak_expected[trusted_context[23:0]]!==trusted_expected_psn || nak_identity[trusted_context[23:0]]!==trusted_context[167:40]))
   nak_sent[trusted_context[23:0]]<=0;
  if(!halted)case(state)
   IDLE:if(wire_request)begin
    if(!context_ok || last_serial==64'hffffffffffffffff)begin fault<=1;fault_code<=8'ha3;end
    else begin
     owner<={4'd0,future ? 8'h60:8'h1f,s_cert_received_psn,
      future ? s_cert_expected_psn:s_cert_expected_psn-24'd1,last_serial+64'd1,s_cert_context};
     reject_snapshot<={s_error,s_qpn,s_psn,s_msn,s_keep_message};
     last_serial<=last_serial+64'd1;requests<=requests+1'b1;state<=OWNER;
    end
   end else if(request && repeat_nak && s_valid && s_ready)suppressed<=suppressed+1'b1;
   OWNER:if(m_ack_owner_valid && m_ack_owner_ready)state<=EVENT;
   EVENT:if(m_hls_owner_valid && m_hls_owner_ready)state<=PROOF;
   PROOF:if(s_ack_done_valid && s_ack_done_ready)begin
    wire_proofs<=wire_proofs+1'b1;state<=RETIRE;
    if(owner[475:468]==8'h60)begin
     nak_sent[owner[23:0]]<=1;nak_expected[owner[23:0]]<=owner[443:420];nak_identity[owner[23:0]]<=owner[167:40];
    end
   end
   RETIRE:if(m_ack_retire_valid && m_ack_retire_ready)begin retirements<=retirements+1'b1;state<=REPORT;end
   REPORT:if(s_valid && s_ready)begin reports<=reports+1'b1;state<=IDLE;owner<=0;reject_snapshot<=0;end
   default:begin fault<=1;fault_code<=8'ha4;end
  endcase
 end
end
endmodule
`resetall
