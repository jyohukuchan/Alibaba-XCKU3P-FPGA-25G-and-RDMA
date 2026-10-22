// SPDX-License-Identifier: BSD-2-Clause-Views
// Selected fatal-WRITE join completion authorizes ONLY the RQC command4
// quarantine-guard distinction. NOT a cancellation receipt, CQ, QP STOP,
// global drain, reference release, reset/reuse or permission to clear guards.
// event_taken MUST be the real upstream join handshake AFTER BOTH existing
// observer and mailbox accept, never host ACK, VALID-only or a model pulse.
`resetall
`timescale 1ns/1ps
`default_nettype none
module rocev2_fatal_rq_cancel_authority(
 input wire clk,rst,parent_fault,
 input wire [999:0] event_data,input wire event_taken,
 input wire trusted_valid,input wire [355:0] trusted_context,input wire [23:0] trusted_psn,
 input wire [7:0] quarantined,input wire noncontrol_lease_guard,
 output wire [7:0] cancel_only_authorized,
 output reg fault=0,output reg [7:0] fault_code=0
);
reg [7:0] certified=0;
reg [355:0] contexts[0:7];reg [23:0] frontiers[0:7];
reg [63:0] last_serial=0;
wire [23:0] eq=event_data[447:424],tq=trusted_context[23:0];
wire [63:0] serial=event_data[843:780];
wire [7:0] syndrome=event_data[899:892];
wire trusted_known=(^{trusted_valid,trusted_context,trusted_psn,quarantined,noncontrol_lease_guard})!==1'bx;
wire trusted_ok=trusted_valid===1'b1 && trusted_known && tq<8 &&
 trusted_context[39:24]!=0 && trusted_context[103:40]!=0 && trusted_context[167:104]!=0;
wire event_known=(^event_data)!==1'bx;
wire [423:0] packet=event_data[423:0];
wire [32:0] packet_end={1'b0,packet[103:72]}+{1'b0,packet[71:40]};
wire [64:0] address_end={1'b0,packet[223:160]}+{33'd0,packet[159:128]};
wire [23:0] packet_psn=packet[127:104]+{4'd0,packet[103:84]};
wire [23:0] next_psn=packet[39:16]+24'd1;
wire empty_record=event_data[951:944]==0 && event_data[943:928]==0 && packet==0;
wire partial_record=event_data[951:944]==15 && event_data[943:941]==3 && event_data[940:928]!=0 &&
 packet[423:400]==eq && packet[399:384]==trusted_context[39:24] && packet[383:320]==trusted_context[103:40] &&
 packet[319:256]!=0 && packet[255:224]!=0 && packet[15:0]!=0 &&
 packet[159:128]>4096 && packet[159:128]<=1048576 && address_end<=65'h10000000000000000 &&
 packet[83:72]==0 && packet[71:40]==4096 && packet_end<{1'b0,packet[159:128]} &&
 packet[39:16]==packet_psn && next_psn==trusted_psn;
wire event_ok=event_known && trusted_ok && eq<8 && eq==tq &&
 event_data[999:992]==7 && event_data[991:984]==0 && event_data[983:960]==event_data[927:904] &&
 event_data[959:952]==0 && event_data[903:900]==0 && syndrome>=8'h61 && syndrome<=8'h63 &&
 event_data[779:424]===trusted_context && event_data[891:868]===trusted_psn &&
 event_data[867:844]===trusted_psn && quarantined[eq]===1'b1 && serial!=0 && serial>last_serial && !certified[eq] &&
 (empty_record || partial_record);
wire halted=fault || parent_fault!==1'b0;
// Zero authority while another actual Atomic/zero/control lease exists.
// The immutable native ingress/SQC/RQC configuration quarantine STAYS asserted.
assign cancel_only_authorized=!rst && !halted && trusted_ok && noncontrol_lease_guard===1'b0 &&
 certified[tq]===1'b1 && quarantined[tq]===1'b1 && contexts[tq]===trusted_context && frontiers[tq]===trusted_psn ?
 (8'h01<<tq):8'd0;
integer i;
always @(posedge clk)begin
 if(rst)begin
  certified<=0;last_serial<=0;fault<=0;fault_code<=0;
  for(i=0;i<8;i=i+1)begin contexts[i]<=0;frontiers[i]<=0;end
 end else begin
  if(parent_fault!==1'b0 || (event_taken!==1'b0 && event_taken!==1'b1))begin fault<=1;fault_code<=8'hc1;end
  if(event_taken && !event_ok)begin fault<=1;fault_code<=8'hc2;end
  if(event_taken && event_ok && !halted)begin
   certified[eq]<=1;contexts[eq]<=trusted_context;frontiers[eq]<=trusted_psn;last_serial<=serial;
  end
 end
end
endmodule
`resetall
