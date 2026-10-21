// SPDX-License-Identifier: BSD-2-Clause-Views
// Bridge an ACTUAL retained-message empty-LAST-RQ reject to the SAME HLS
// RNR pipeline and shared fresh-tag ACK/MAC proof. No DMA/RQ/PSN/CQ grant.
// Producer reject stays held until negative wire proof, exact ACK retirement
// and the independent real host/local-error consumer handshake all finish.
`resetall
`timescale 1ns/1ps
`default_nettype none
module rocev2_segmented_write_rnr_control(
 input wire clk,rst,enable,parent_fault,
 input wire trusted_valid,input wire [103:0] trusted_identity,input wire [23:0] expected_psn,
 input wire [319:0] message_context,input wire message_active,mr_guard,input wire [7:0] message_queue_guard,
 input wire [7:0] s_error,input wire [23:0] s_qpn,s_psn,s_msn,input wire s_keep_message,s_valid,
 output wire s_ready,output wire m_error_valid,input wire m_error_ready,
 output wire [367:0] m_ack_owner,output wire m_ack_owner_valid,input wire m_ack_owner_ready,
 input wire [383:0] s_ack_done,input wire s_ack_done_valid,output wire s_ack_done_ready,
 output wire [367:0] m_ack_retire_owner,output wire m_ack_retire_valid,input wire m_ack_retire_ready,
 output wire [55:0] m_hls_event,output wire m_hls_event_valid,input wire m_hls_event_ready,
 output wire tx_release,configuration_guard,output wire [7:0] queue_guard,
 output reg fault=0,output reg [7:0] fault_code=0,
 output reg [31:0] requests=0,wire_proofs=0,retirements=0,reports=0
);
localparam IDLE=0,OWNER=1,EVENT=2,PROOF=3,RETIRE=4,REPORT=5;
reg [2:0] state=IDLE;
reg [367:0] owner=0;
reg [103:0] native_identity=0;
reg [383:0] wire_proof=0;
wire halted=fault || parent_fault!==1'b0;
wire error_known=(^{s_error,s_qpn,s_psn,s_msn,s_keep_message})!==1'bx;
wire rnr_request=enable===1'b1 && s_valid===1'b1 && s_error===8'd38;
wire context_known=(^{trusted_identity,expected_psn,message_context,message_queue_guard})!==1'bx;
wire [23:0] last_delta=(message_context[55:24]-32'd1)>>12;
wire [23:0] last_psn=message_context[23:0]+last_delta;
wire context_ok=trusted_valid===1'b1 && context_known && error_known &&
 message_active===1'b1 && mr_guard===1'b1 && s_keep_message===1'b1 &&
 trusted_identity[23:0]<8 && trusted_identity[39:24]!=0 && trusted_identity[103:40]!=0 &&
 message_context[319:296]===trusted_identity[23:0] && message_context[295:280]===trusted_identity[39:24] &&
 message_context[279:216]===trusted_identity[103:40] && message_context[215:152]!=0 && message_context[151:120]!=0 &&
 message_context[55:24]>4096 && message_context[55:24]<=1048576 &&
 message_queue_guard[trusted_identity[23:0]]===1'b1 && s_qpn===trusted_identity[23:0] && s_psn===expected_psn && s_psn===last_psn;
wire retained=state!=IDLE;
wire stable_reject=s_valid===1'b1 && s_error===8'd38 && s_keep_message===1'b1 &&
 {s_msn,s_psn,message_context}===owner && trusted_identity===native_identity && context_ok;
wire done_match=(^s_ack_done)!==1'bx && s_ack_done[367:0]===owner &&
 s_ack_done[383:381]==3'b011 && s_ack_done[380:368]!=0;
assign m_ack_owner=owner;
assign m_ack_owner_valid=state==OWNER && !halted && !rst;
assign m_hls_event={8'h20,owner[343:320],owner[319:296]};
assign m_hls_event_valid=state==EVENT && !halted && !rst;
assign tx_release=(state==PROOF || state==RETIRE || state==REPORT) && !halted && !rst;
assign s_ack_done_ready=state==PROOF && done_match && !halted && !rst;
assign m_ack_retire_owner=owner;
assign m_ack_retire_valid=state==RETIRE && !halted && !rst;
assign m_error_valid=!halted && !rst && error_known && s_valid===1'b1 &&
 ((state==IDLE && !rnr_request) || state==REPORT);
assign s_ready=!halted && !rst && error_known &&
 ((state==IDLE && !rnr_request) || state==REPORT) && m_error_ready;
assign configuration_guard=retained || rnr_request || halted;
assign queue_guard=halted ? 8'hff:retained ? 8'h01<<owner[319:296]:rnr_request && context_ok ? 8'h01<<s_qpn:8'd0;
always @(posedge clk)begin
 if(rst)begin
  state<=IDLE;owner<=0;native_identity<=0;wire_proof<=0;fault<=0;fault_code<=0;
  requests<=0;wire_proofs<=0;retirements<=0;reports<=0;
 end else begin
  if(parent_fault!==1'b0 || s_valid!==1'b0 && s_valid!==1'b1 ||
    s_valid===1'b1 && !error_known || retained && !stable_reject)begin fault<=1;fault_code<=8'he1;end
  if(s_ack_done_valid!==1'b0 && s_ack_done_valid!==1'b1 ||
    s_ack_done_valid && (state!=PROOF || !done_match))begin fault<=1;fault_code<=8'he2;end
  if(!halted)case(state)
   IDLE:if(rnr_request)begin
    if(!context_ok)begin fault<=1;fault_code<=8'he3;end
    else begin owner<={s_msn,s_psn,message_context};native_identity<=trusted_identity;requests<=requests+1'b1;state<=OWNER;end
   end
   OWNER:if(m_ack_owner_valid && m_ack_owner_ready)state<=EVENT;
   EVENT:if(m_hls_event_valid && m_hls_event_ready)state<=PROOF;
   PROOF:if(s_ack_done_valid && s_ack_done_ready)begin wire_proof<=s_ack_done;wire_proofs<=wire_proofs+1'b1;state<=RETIRE;end
   RETIRE:if(m_ack_retire_valid && m_ack_retire_ready)begin retirements<=retirements+1'b1;state<=REPORT;end
   REPORT:if(s_valid && s_ready)begin reports<=reports+1'b1;state<=IDLE;owner<=0;native_identity<=0;wire_proof<=0;end
   default:begin fault<=1;fault_code<=8'he4;end
  endcase
 end
end
endmodule
`resetall
