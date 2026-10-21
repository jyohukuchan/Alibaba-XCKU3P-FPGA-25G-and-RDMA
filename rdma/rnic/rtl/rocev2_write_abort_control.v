// SPDX-License-Identifier: BSD-2-Clause-Views
// Actual RTL certificate consumer for the future native fatal-WRITE path.
// NOT YET CONNECTED to the native graph. Every *_taken input MUST be the
// genuine full handshake of the SAME native backend/HLS/ACK/MAC owner.
// Quarantine MUST precede fatal wire issue and stay asserted throughout.
// This certifies selected WRITE state/cancel only, never QP/global DMA drain,
// error CQ, STOP, safe unpin or permission to reset/reuse a quarantined QP.
`resetall
`timescale 1ns/1ps
`default_nettype none
module rocev2_write_abort_control(
 input wire clk,rst,enable,parent_fault,
 input wire trusted_valid,input wire [355:0] trusted_context,input wire [23:0] trusted_expected_psn,
 input wire [319:0] message_context,input wire message_active,
 input wire [355:0] quarantine_context,input wire quarantine_valid,
 input wire [471:0] positive_wire,input wire positive_wire_taken,
 input wire [423:0] positive_commit_token,input wire [23:0] positive_commit_msn,
 input wire [7:0] positive_commit_proofs,input wire positive_commit_taken,
 input wire [423:0] positive_retire_token,input wire positive_retire_taken,
 input wire [527:0] error_wire,input wire error_wire_valid,output wire error_wire_ready,
 input wire [479:0] error_retire_owner,input wire error_retire_taken,
 output wire [959:0] m_hls_owner,output wire m_hls_owner_valid,input wire m_hls_owner_ready,
 input wire [991:0] s_hls_done,input wire s_hls_done_valid,output wire s_hls_done_ready,
 output wire m_report_release,input wire [479:0] local_report_owner,input wire local_report_taken,
 output wire [319:0] m_cancel_context,output wire m_cancel_valid,m_cancel_certified,input wire m_cancel_ready,
 // {selected-only flags8, actual HLS abort992}; flags7 is NOT unpin/STOP.
 output wire [999:0] m_done,output wire m_done_valid,input wire m_done_ready,
 output wire configuration_guard,output wire [7:0] queue_guard,
 output reg [7:0] quarantined=0,output reg fault=0,output reg [7:0] fault_code=0,
 output reg [31:0] requests=0,hls_completions=0,cancels=0,completions=0
);
localparam IDLE=0,NAK_RETIRE=1,HLS_OWNER=2,HLS_REPLY=3,REPORT=4,CANCEL=5,VERIFY=6,DONE=7;
reg [2:0] state=IDLE;
reg [471:0] packet_wire[0:7];reg [355:0] packet_context[0:7];
reg [7:0] packet_valid=0,packet_committed=0,packet_retired=0;
reg [63:0] abort_serial[0:7];
reg [15:0] last_wire_tag=0;
reg [479:0] saved_error=0;reg [959:0] owner=0;
reg [991:0] receipt=0;reg saved_partial=0;
integer k;
wire halted=fault || parent_fault!==1'b0;
wire ctx_known=(^{trusted_context,trusted_expected_psn})!==1'bx;
wire ctx_ok=trusted_valid===1'b1 && ctx_known && trusted_context[23:0]<8 &&
 trusted_context[39:24]!=0 && trusted_context[103:40]!=0 && trusted_context[167:104]!=0;
wire retained=state!=IDLE;
wire [23:0] q=saved_error[23:0];
wire locked=ctx_ok && trusted_context===saved_error[355:0] &&
 trusted_expected_psn===saved_error[443:420] && quarantine_valid===1'b1 &&
 quarantine_context===saved_error[355:0];
function packet_shape;
 input [423:0] p;reg [32:0] end_bytes;reg [64:0] end_address;reg [31:0] left;
 begin
  end_bytes={1'b0,p[103:72]}+{1'b0,p[71:40]};end_address={1'b0,p[223:160]}+{33'd0,p[159:128]};
  left=p[159:128]-p[103:72];
  packet_shape=(^p)!==1'bx && p[423:400]<8 && p[399:384]!=0 && p[383:320]!=0 &&
   p[319:256]!=0 && p[255:224]!=0 && p[159:128]>4096 && p[159:128]<=1048576 &&
   p[103:72]<p[159:128] && p[83:72]==0 && p[71:40]==(left>4096 ? 32'd4096:left) &&
   end_bytes<={1'b0,p[159:128]} && end_address<=65'h10000000000000000 &&
   p[39:16]==(p[127:104]+p[103:84])%16777216 && p[15:0]!=0;
 end
endfunction
wire [23:0] pq=positive_wire[423:400],cq=positive_commit_token[423:400],rq=positive_retire_token[423:400];
wire [423:0] prior_packet=packet_wire[pq][423:0];
wire [32:0] prior_end={1'b0,prior_packet[103:72]}+{1'b0,prior_packet[71:40]};
wire continuation=prior_end<{1'b0,prior_packet[159:128]};
wire next_packet_ok=!packet_valid[pq] || packet_committed[pq] && packet_retired[pq] &&
 (continuation ? packet_context[pq]===trusted_context && positive_wire[423:104]===prior_packet[423:104] &&
 positive_wire[103:72]==prior_end && positive_wire[39:16]==prior_packet[39:16]+24'd1 &&
 positive_wire[447:424]==packet_wire[pq][447:424]+(positive_wire[103:72]+positive_wire[71:40]==positive_wire[159:128] ? 24'd1:24'd0):
 positive_wire[103:72]==0);
wire positive_ok=(^positive_wire)!==1'bx && ctx_ok && packet_shape(positive_wire[423:0]) && positive_wire[455:448]==0 &&
 positive_wire[471:469]==3 && positive_wire[468:456]!=0 && positive_wire[471:456]>last_wire_tag &&
 positive_wire[423:400]===trusted_context[23:0] && positive_wire[399:384]===trusted_context[39:24] &&
 positive_wire[383:320]===trusted_context[103:40] && positive_wire[39:16]===trusted_expected_psn &&
 !quarantined[pq] && next_packet_ok;
wire commit_ok=(^{positive_commit_token,positive_commit_msn,positive_commit_proofs})!==1'bx && cq<8 && ctx_ok &&
 packet_valid[cq] && !packet_committed[cq] && packet_context[cq]===trusted_context &&
 positive_commit_token===packet_wire[cq][423:0] && positive_commit_msn===packet_wire[cq][447:424] &&
 positive_commit_proofs==8'h0f && positive_commit_token[39:16]===trusted_expected_psn;
wire retire_ok=(^positive_retire_token)!==1'bx && rq<8 && ctx_ok && packet_valid[rq] &&
 packet_committed[rq] && !packet_retired[rq] && positive_retire_token===packet_wire[rq][423:0] &&
 packet_context[rq]===trusted_context && trusted_expected_psn===positive_retire_token[39:16]+24'd1;
wire [23:0] eq=error_wire[23:0];
wire [423:0] last_packet=packet_wire[eq][423:0];
wire [32:0] last_end={1'b0,last_packet[103:72]}+{1'b0,last_packet[71:40]};
wire partial_ok=packet_valid[eq] && packet_committed[eq] && packet_retired[eq] &&
 packet_context[eq]===trusted_context && last_packet[423:104]===message_context &&
 last_end<{1'b0,last_packet[159:128]} && last_packet[39:16]+24'd1===trusted_expected_psn &&
 packet_wire[eq][447:424]===error_wire[503:480];
wire empty_ok=!packet_valid[eq] || packet_committed[eq] && packet_retired[eq] &&
 last_end=={1'b0,last_packet[159:128]};
wire error_ok=(^error_wire)!==1'bx && ctx_ok && quarantine_valid===1'b1 &&
 quarantine_context===trusted_context && error_wire[355:0]===trusted_context &&
 error_wire[479:476]==0 && (error_wire[475:468]==8'h61 || error_wire[475:468]==8'h62 || error_wire[475:468]==8'h63) &&
 error_wire[467:444]===trusted_expected_psn && error_wire[443:420]===trusted_expected_psn &&
 error_wire[419:356]!=0 && error_wire[419:356]>abort_serial[eq] && error_wire[511:504]==0 &&
 error_wire[527:525]==3 && error_wire[524:512]!=0 && error_wire[527:512]>last_wire_tag &&
 !quarantined[eq] && (message_active===1'b1 ? partial_ok:message_active===1'b0 && empty_ok);
wire hls_match=(^s_hls_done)!==1'bx && s_hls_done==={8'd0,owner[927:904],owner};
assign error_wire_ready=state==IDLE && enable===1'b1 && error_ok===1'b1 && !halted && !rst;
assign m_hls_owner=owner;assign m_hls_owner_valid=state==HLS_OWNER && !halted && !rst;
assign s_hls_done_ready=state==HLS_REPLY && hls_match && !halted && !rst;
assign m_report_release=state==REPORT && !halted && !rst;
assign m_cancel_context=owner[423:104];
assign m_cancel_valid=state==CANCEL && !halted && !rst;
assign m_cancel_certified=m_cancel_valid;
assign m_done={8'h07,receipt};assign m_done_valid=state==DONE && !halted && !rst;
assign queue_guard=halted ? 8'hff:quarantined;
assign configuration_guard=halted || retained || quarantined!=0;
always @(posedge clk)begin
 if(rst)begin
  state<=IDLE;packet_valid<=0;packet_committed<=0;packet_retired<=0;last_wire_tag<=0;
  saved_error<=0;owner<=0;receipt<=0;saved_partial<=0;quarantined<=0;
  fault<=0;fault_code<=0;requests<=0;hls_completions<=0;cancels<=0;completions<=0;
  for(k=0;k<8;k=k+1)begin packet_wire[k]<=0;packet_context[k]<=0;abort_serial[k]<=0;end
 end else begin
  if(parent_fault!==1'b0 || retained && !locked ||
   (^{positive_wire_taken,positive_commit_taken,positive_retire_taken,error_wire_valid,error_retire_taken,s_hls_done_valid,local_report_taken})===1'bx)begin
   fault<=1;fault_code<=8'hb0;
  end
  if(positive_wire_taken && (state!=IDLE || !positive_ok || positive_commit_taken || positive_retire_taken || error_wire_valid))begin fault<=1;fault_code<=8'hb1;end
  if(positive_commit_taken && (state!=IDLE || !commit_ok || positive_retire_taken || error_wire_valid))begin fault<=1;fault_code<=8'hb2;end
  if(positive_retire_taken && (state!=IDLE || !retire_ok || error_wire_valid))begin fault<=1;fault_code<=8'hb3;end
  if(error_wire_valid && (state!=IDLE || enable!==1'b1 || error_ok!==1'b1))begin fault<=1;fault_code<=8'hb4;end
  if(error_retire_taken && (state!=NAK_RETIRE || error_retire_owner!==saved_error))begin fault<=1;fault_code<=8'hb5;end
  if(s_hls_done_valid && (state!=HLS_REPLY || !hls_match))begin fault<=1;fault_code<=8'hb6;end
  if(local_report_taken && (state!=REPORT || local_report_owner!==saved_error))begin fault<=1;fault_code<=8'hb7;end
  if(state==CANCEL && m_cancel_ready!==1'b0 && m_cancel_ready!==1'b1)begin fault<=1;fault_code<=8'hb8;end
  if(!halted)begin
   if(positive_wire_taken && positive_ok && state==IDLE)begin
    packet_wire[pq]<=positive_wire;packet_context[pq]<=trusted_context;packet_valid[pq]<=1;
    packet_committed[pq]<=0;packet_retired[pq]<=0;last_wire_tag<=positive_wire[471:456];
   end
   if(positive_commit_taken && commit_ok && state==IDLE)packet_committed[cq]<=1;
   if(positive_retire_taken && retire_ok && state==IDLE)packet_retired[rq]<=1;
   case(state)
    IDLE:if(error_wire_valid && error_wire_ready)begin
     saved_error<=error_wire[479:0];saved_partial<=message_active;
     owner<={8'd0,message_active ? 8'h0f:8'd0,message_active ? packet_wire[eq][471:456]:16'd0,
      error_wire[503:480],error_wire[479:0],message_active ? last_packet:424'd0};
     abort_serial[eq]<=error_wire[419:356];quarantined[eq]<=1;last_wire_tag<=error_wire[527:512];
     receipt<=0;requests<=requests+1'b1;state<=NAK_RETIRE;
    end
    NAK_RETIRE:if(error_retire_taken && error_retire_owner===saved_error)state<=HLS_OWNER;
    HLS_OWNER:if(m_hls_owner_valid && m_hls_owner_ready)state<=HLS_REPLY;
    HLS_REPLY:if(s_hls_done_valid && s_hls_done_ready)begin receipt<=s_hls_done;hls_completions<=hls_completions+1'b1;state<=REPORT;end
    REPORT:if(local_report_taken && local_report_owner===saved_error)state<=saved_partial ? CANCEL:VERIFY;
    CANCEL:if(m_cancel_valid && m_cancel_ready)begin cancels<=cancels+1'b1;state<=VERIFY;end
    VERIFY:begin
     if(message_active!==1'b0)begin fault<=1;fault_code<=8'hb9;end
     else state<=DONE;
    end
    DONE:if(m_done_valid && m_done_ready)begin
     completions<=completions+1'b1;packet_valid[q]<=0;packet_committed[q]<=0;packet_retired[q]<=0;
     owner<=0;saved_error<=0;receipt<=0;saved_partial<=0;state<=IDLE;
     // Quarantine and replay history deliberately survive selected completion.
    end
   endcase
  end
 end
end
endmodule
`resetall
