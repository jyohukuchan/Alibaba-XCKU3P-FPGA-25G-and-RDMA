// SPDX-License-Identifier: BSD-2-Clause-Views
// Real remote MR table + message guard + actual late-notice RQ component.
// Integrity/QP metadata, posted RQ admission, backend/HLS/MAC certificates
// and the CQ consumer are MODELS here, not a qualified native endpoint.
`timescale 1ns/1ps
module tb;
parameter [63:0] COOKIE_INIT=64'hfedcba9876543210;
localparam MAX_QPS=8;
// GUARD_PORT_DECLARATIONS
// QUEUE_PORT_DECLARATIONS
rocev2_remote_write_message_guard #(.INITIAL_MESSAGE_COOKIE(COOKIE_INIT)) dut(.*);
// QUEUE_INSTANTIATION
always #2 clk=~clk;
integer mode=0,cycle=0,i,queries=0,grants=0,offset_index=0,cur_length=4096;
integer total=8193,capacity=0,cur_offset=0,cur_psn,cur_tag=1,imm=0,packets=0;
reg [63:0] mr_va=64'hfedcba9876543000,mr_dma=64'h8123456789abc000;
reg [31:0] remote_key=32'h80000008;
reg [319:0] expected_context;
reg [423:0] expected_token;
reg [619:0] rq_owner;
reg [751:0] core_proof;
reg [775:0] whole_proof;
reg mr_allow=1,mr_response_allow=1,retire_allow=1;
wire actual_mr_ready,actual_mr_valid;
wire [15:0] actual_mr_tag;
wire [7:0] actual_mr_error;
wire [63:0] actual_mr_offset,actual_mr_address;
wire [31:0] actual_mr_length;
reg [1:0] cfg_command=0;
reg [15:0] cfg_pd=17;
reg [31:0] cfg_key=0;
reg [63:0] cfg_span=0;
reg [3:0] cfg_access=7;
reg cfg_valid=0,cfg_response_ready=0;
wire cfg_ready,cfg_response_valid,epoch_configured;
wire [7:0] cfg_response_error;
wire [31:0] cfg_response_key;
wire [319:0] raw_notice_retire_context;
wire raw_notice_retire_valid;
assign m_mr_ready=actual_mr_ready && mr_allow;
assign s_mr_valid=actual_mr_valid && mr_response_allow;
// Only these labeled NEGATIVE transport corruptions alter a genuine reply.
assign s_mr_tag=actual_mr_tag ^ ((mode==31 && queries==1) ? 16'h8000:16'd0);
assign s_mr_error=actual_mr_error;
// Query1 authorizes the whole; query2 is FIRST, query3 is MIDDLE.
assign s_mr_offset=actual_mr_offset ^ ((mode==32 && queries==3) ? 64'd1:64'd0);
assign s_mr_address=actual_mr_address;
assign s_mr_length=(mode==45 && queries==1) ? 32'hxxxxxxxx:actual_mr_length;
assign s_notice_retire_context=raw_notice_retire_context ^
    (mode==36 ? (320'd1<<152):320'd0);
assign s_notice_retire_valid=raw_notice_retire_valid && retire_allow;
rocev2_mr_table #(.REQUIRE_EPOCH(1)) actual_mr(
 .clk(clk),.rst(rst),.cfg_quiescent(!configuration_guard && !q_active && q_queue_guard==0),
 .cfg_command(cfg_command),.cfg_index(3'd0),.cfg_pd(cfg_pd),.cfg_key(cfg_key),
 .cfg_virtual_address(mr_va),.cfg_dma_address(mr_dma),.cfg_length(cfg_span),
 .cfg_access(cfg_access),.cfg_valid(cfg_valid),.cfg_ready(cfg_ready),
 .cfg_response_error(cfg_response_error),.cfg_response_key(cfg_response_key),
 .cfg_response_valid(cfg_response_valid),.cfg_response_ready(cfg_response_ready),
 .epoch_configured(epoch_configured),.s_request_pd(m_mr_pd),.s_request_key(m_mr_key),
 .s_request_address(m_mr_address),.s_request_length(m_mr_length),
 .s_request_operation(m_mr_operation),.s_request_tag(m_mr_tag),
 .s_request_valid(m_mr_valid && mr_allow),.s_request_ready(actual_mr_ready),
 .m_response_tag(actual_mr_tag),.m_response_error(actual_mr_error),
 .m_response_offset(actual_mr_offset),.m_response_dma_address(actual_mr_address),
 .m_response_length(actual_mr_length),.m_response_valid(actual_mr_valid),
 .m_response_ready(s_mr_ready && mr_response_allow));
always @(posedge clk)if(!rst)begin
 cycle=cycle+1;if(cycle>100000)$fatal(1,"original bounded4ns/100000 cycle guard");
 if(m_mr_valid && m_mr_ready)begin
  if(m_mr_operation!==3 || m_mr_pd!==17 || m_mr_key!==remote_key ||
     m_mr_tag!==cur_tag[15:0] || m_mr_address!==(mr_va+64'h210+cur_offset) ||
     m_mr_length!==(queries==0 ? total[31:0]:cur_length[31:0]))
   $fatal(1,"independent actual remote-MR request oracle query%0d",queries);
  queries=queries+1;
 end
 if(m_packet_valid && m_packet_ready)grants=grants+1;
end
function [619:0] make_rq;
 input integer cap;input integer pd;
 reg [619:0] c;
 begin c=0;c[587:524]=64'hf123456789abc001;c[523:460]=64'h8000000000000042;
 c[459:396]=64'h9123456700000001;c[395:372]=7;c[371:356]=pd;c[355:340]=16'h42;
 c[339:324]=4;c[323:308]=1;c[307:276]=cap;c[19:0]=3;
 if(cap!=0)begin c[275:244]=32'hc7654321;c[243:180]=64'h123456789abc0000;c[179:116]=64'h890;end
 make_rq=c;end
endfunction
task tick;begin @(posedge clk);@(negedge clk);end endtask
task good;
 begin if(fault || q_fault)$fatal(1,"unexpected guard/RQ fault mode%0d code%h/%h",mode,fault_code,q_fault_code);end
endtask
task management;
 input [1:0] command;input [31:0] key;
 begin cfg_command=command;cfg_key=key;cfg_valid=1;
 // Sample the real transfer at a clock edge, not a stale READY just
 // after releasing reset. An accepted request must not be sent twice.
 @(posedge clk);while(cfg_ready!==1'b1)@(posedge clk);
 @(negedge clk);cfg_valid=0;while(!cfg_response_valid)tick;
 if(cfg_response_error || cfg_response_key!==(command==3 ? key:32'h80000008))
  $fatal(1,"real MR management failed %h key%h",cfg_response_error,cfg_response_key);
 cfg_response_ready=1;tick;cfg_response_ready=0;end
endtask
task no_revoke;
 begin cfg_command=2;cfg_key=32'h80000008;cfg_valid=1;
 repeat(5)begin tick;good;
  if(cfg_ready || cfg_response_valid || !configuration_guard || queue_guard!==8'h80)
   $fatal(1,"actual MR invalidation must not pass a live full-message owner");
 end
 cfg_valid=0;end
endtask
task post_rq;
 input integer cap;input integer pd;
 begin rq_owner=make_rq(cap,pd);q_s_post_context=rq_owner;q_s_post_valid=1;
 @(posedge clk);if(!q_s_post_ready)$fatal(1,"actual canonical posted RQ admission");
 @(negedge clk);q_s_post_valid=0;good;
 if(q_active || q_taken_count || q_posted_count!=1)$fatal(1,"posting is not taking a notification RQ");end
endtask
task emit_packet;
 input [7:0] opcode;input integer off;input integer n;input integer psn;input integer tag;
 begin cur_offset=off;cur_length=n;cur_psn=psn&24'hffffff;cur_tag=tag;
 s_packet_opcode=opcode;s_packet_qpn=7;s_packet_psn=cur_psn;s_packet_length=n;
 s_packet_wire_length=(n+3)&32'hfffffffc;s_packet_pad=(-n)&3;s_packet_reth_valid=opcode==6;
 s_packet_reth_va=mr_va+64'h210;s_packet_reth_key=remote_key;s_packet_reth_length=total;
 if(mode==38 && opcode!=6)begin
  s_packet_reth_va=64'hxxxxxxxxxxxxxxxx;s_packet_reth_key=32'hxxxxxxxx;s_packet_reth_length=32'hxxxxxxxx;
 end
 if(opcode==6)case(mode)
  14:s_packet_pad=1;15:s_packet_wire_length=n+4;16:s_packet_qpn=24'h800007;
  17:s_packet_psn=cur_psn+1;18:s_packet_tag=0;19:s_packet_reth_valid=0;
  20:s_packet_reth_key=0;21:s_packet_reth_va=64'hfffffffffffffff0;
 endcase
 if(mode!=18 || opcode!=6)s_packet_tag=tag;
 trusted_expected_psn=cur_psn;s_packet_valid=1;
 @(posedge clk);if(!s_packet_ready)$fatal(1,"metadata ready under trusted fixed QP");
 @(negedge clk);s_packet_valid=0;
 end
endtask
task wait_grant;
 begin i=0;while(!m_packet_valid && i<100)begin tick;good;i=i+1;end
 expected_token={expected_context,cur_offset[31:0],cur_length[31:0],cur_psn[23:0],cur_tag[15:0]};
 if(!m_packet_valid || m_packet_token!==expected_token || m_packet_address!==(mr_va+64'h210+cur_offset) ||
    m_packet_mr_offset!==(64'h210+cur_offset) || m_packet_mr_address!==(mr_dma+64'h210+cur_offset) ||
    m_packet_key!==remote_key || m_packet_wire_length!==((cur_length+3)&32'hfffffffc) ||
    m_packet_last!==(cur_offset+cur_length==total) ||
    m_packet_notify!==((cur_offset+cur_length==total) && imm!=0) ||
    m_packet_rq_context!==(m_packet_notify ? rq_owner:620'd0))
  $fatal(1,"independent full424 token/MR translation/late-RQ oracle");
 enable=0;repeat(3)begin tick;good;
  if(!m_packet_valid || m_packet_token!==expected_token || !configuration_guard)
   $fatal(1,"admitted grant cannot retract under pause/backpressure");end
 enable=1;no_revoke;m_packet_ready=1;
 @(posedge clk);if(!m_packet_valid)$fatal(1,"actual packet grant handshake");
 @(negedge clk);m_packet_ready=0;good;
 repeat(3)begin tick;if(!message_active || s_packet_ready || !configuration_guard)
  $fatal(1,"packet grant alone is not execution or next-packet permission");end
 end
endtask
task certify;
 begin s_done_token=expected_token;s_done_msn=(cur_offset+cur_length==total ? 8:7);
 s_done_proofs=15;s_done_valid=1;
 @(posedge clk);if(!s_done_ready)$fatal(1,"exact modeled backend/HLS/MAC certificate");
 @(negedge clk);s_done_valid=0;good;end
endtask
task reject_packet;
 input integer error;input integer keep;
 begin i=0;while(!m_reject_valid && i<100)begin tick;good;i=i+1;end
 if(!m_reject_valid || m_reject_error!==error[7:0] || m_reject_keep_message!==keep[0] ||
    m_reject_qpn!==7 || m_reject_psn!==s_packet_psn || message_active!==keep[0] ||
    m_packet_valid || q_taken_count || grants!==accepted_packets)
  $fatal(1,"exact reject/RNR without fabricated grant/owner mode%0d error%0d expected%0d",mode,m_reject_error,error);
 repeat(3)begin tick;good;if(!m_reject_valid)$fatal(1,"stable reject backpressure");end
 m_reject_ready=1;tick;m_reject_ready=0;good;
 end
endtask
task expect_fault;
 begin repeat(5)tick;
 if(!fault || !configuration_guard || queue_guard!==8'hff || m_packet_valid || s_done_ready || m_mr_valid)
  $fatal(1,"corrupt proof/context must fault and retain authority mode%0d",mode);
 end
endtask
task complete_notice;
 begin
 if(!message_active || !q_active || q_held_context!==rq_owner || q_taken_count!=1 || q_m_ticket_valid)
  $fatal(1,"two distinct full-message and notification owners held");
 q_s_placement_context=rq_owner;q_s_placement_length=cur_length;q_s_placement_psn=cur_psn;
 q_s_placement_notification=32'h89abcdef;q_s_placement_notification_flags=3;q_s_placement_valid=1;
 @(posedge clk);if(!q_s_placement_ready)$fatal(1,"actual final-WRITE placement join");
 @(negedge clk);q_s_placement_valid=0;good;
 core_proof={8'd0,8'd3,32'h89abcdef,24'd8,4'd0,cur_psn[23:0],cur_length[31:0],rq_owner};
 q_s_core_data=core_proof;q_s_core_valid=1;
 @(posedge clk);if(!q_s_core_ready)$fatal(1,"actual RQ core-certificate join");
 @(negedge clk);q_s_core_valid=0;good;
 repeat(4)begin tick;if(q_m_packet_retire_valid || q_m_ticket_valid)$fatal(1,"HLS alone not MAC/visibility");end
 whole_proof={4'd0,8'd0,8'd3,32'h89abcdef,24'd8,cur_psn[23:0],24'hfffffe,total[31:0],rq_owner};
 q_s_message_data=whole_proof;q_s_message_valid=1;
 @(posedge clk);if(!q_s_message_ready)$fatal(1,"actual whole-byte/firstPSN/lastPSN join");
 @(negedge clk);q_s_message_valid=0;good;
 q_s_mac_data={16'h6001,core_proof};q_s_mac_valid=1;
 @(posedge clk);if(!q_s_mac_ready)$fatal(1,"actual ACK-MAC certificate join");
 @(negedge clk);q_s_mac_valid=0;good;
 repeat(4)begin tick;if(q_m_packet_retire_valid || q_m_ticket_valid)$fatal(1,"missing backend visibility");end
 q_memory_drained=1;repeat(4)tick;q_memory_drained=0;
 repeat(4)begin tick;good;if(!q_m_packet_retire_valid || q_m_ticket_valid || !message_active || !q_active)
  $fatal(1,"certified packet backpressure retains both whole owners");end
 q_m_packet_retire_ready=1;tick;q_m_packet_retire_ready=0;good;
 if(q_received_bytes!=total || q_packet_retired_count!=1)$fatal(1,"whole WRITE count not RQ capacity/LAST bytes");
 q_memory_drained=1;repeat(4)tick;q_memory_drained=0;
 if(!q_m_ticket_valid || q_m_ticket_context!==rq_owner || q_m_ticket_received_bytes!=total ||
    q_m_ticket_notification!==32'h89abcdef || q_m_ticket_notification_flags!==3)
  $fatal(1,"one actual CQ ticket with whole-write bytes and separate RQ identity");
 q_s_commit_context=rq_owner;q_s_retire_context=rq_owner;q_s_commit_valid=1;q_s_retire_valid=1;
 repeat(5)begin tick;good;if(q_s_commit_ready || q_s_retire_ready || !q_m_ticket_valid || !message_active || !q_active)
  $fatal(1,"unconsumed CQ ticket cannot free either owner");end
 q_s_commit_valid=0;q_s_retire_valid=0;q_m_ticket_ready=1;tick;q_m_ticket_ready=0;
 q_s_commit_valid=1;@(posedge clk);if(!q_s_commit_ready)$fatal(1,"actual CQ commit");
 @(negedge clk);q_s_commit_valid=0;retire_allow=0;q_s_retire_valid=1;
 repeat(7)begin tick;good;
  if(q_s_retire_ready || !raw_notice_retire_valid || raw_notice_retire_context!==expected_context ||
     !message_active || !q_active || completed_messages || !configuration_guard)
   $fatal(1,"remote-MR retire backpressure retains both320/620 owners");end
 retire_allow=1;
 if(mode==36)begin expect_fault;
  if(!message_active || !q_active || completed_messages)$fatal(1,"wrong remote-retire cookie released owner");
 end else begin
  @(posedge clk);if(!q_s_retire_ready || !s_notice_retire_ready)$fatal(1,"actual two-owner retirement handshake");
  @(negedge clk);q_s_retire_valid=0;#1;good;
  if(message_active || q_active || configuration_guard || queue_guard || q_queue_guard || completed_messages!=1)
   $fatal(1,"exactly one whole message/RQ lifetime release");
 end
 end
endtask
initial begin
 if(!$value$plusargs("MODE=%d",mode))mode=0;
 imm=mode==1 || mode==2 || mode==3 || mode==4 || mode==5 || mode==33 || mode==36;
 total=mode==2 ? 1048576:mode==3 ? 8192:mode==5 ? 4097:8193;
 capacity=mode==2 ? 1:mode==3 ? 17:0;
 if(mode==5)mr_va=64'hffffffffffffedef;
 if(mode==6)cfg_access=5;if(mode==7)cfg_pd=18;
 if(mode==8)remote_key=8;if(mode==10)remote_key=32'h80000009;
 if(mode==11)total=4096;if(mode==12)total=1048577;
 cfg_span=total+528-(mode==9 ? 1:0);
 rst=1;repeat(5)@(negedge clk);rst=0;
 management(3,32'h10000000);management(1,0);
 trusted_valid=1;trusted_qpn=7;trusted_pd=17;trusted_epoch=64'h9123456700000001;enable=1;
 expected_context={24'd7,16'd17,64'h9123456700000001,COOKIE_INIT+64'd1,
     remote_key,(mr_va+64'h210),total[31:0],24'hfffffe};
 if(imm && mode!=4 && mode!=33 && mode!=36)post_rq(capacity,17);
 if(mode==33)post_rq(0,18);if(mode==36)post_rq(0,17);
 if(mode==39)begin
  trusted_pd=16'hxxxx;s_packet_valid=1;s_packet_opcode=6;
  repeat(2)tick;expect_fault;
 end else begin
 emit_packet(6,0,(mode==13 ? 4095:4096),24'hfffffe,1);
 if(mode>=6 && mode<=10)reject_packet(mode==6 ? 3:mode==7 ? 2:mode==9 ? 4:1,0);
 else if(mode>=11 && mode<=21 || mode==37)begin
  reject_packet(mode==16 ? 17:mode==17 ? 18:mode==18 || mode==37 ? 36:16,0);
  if(queries)$fatal(1,"malformed/exhausted metadata cannot query actual MR");
 end else if(mode==31 || mode==45)expect_fault;
 else begin
  wait_grant;
  if(mode==28 || mode==29 || mode>=41 && mode<=44)begin
   s_done_token=expected_token;s_done_msn=7;s_done_proofs=15;
   case(mode)
    28:s_done_token[423]=~s_done_token[423];29:s_done_proofs=7;
    41:s_done_proofs=14;42:s_done_proofs=11;43:s_done_proofs=13;44:s_done_proofs=8'hxx;
   endcase
   s_done_valid=1;expect_fault;
  end else if(mode==40)begin
   s_cancel_context=expected_context;s_cancel_valid=1;cancel_drained=1;
   repeat(5)begin tick;good;if(s_cancel_ready || !message_active)$fatal(1,"cancel cannot free in-flight packet");end
   certify;tick;s_cancel_valid=0;good;
   if(message_active || cancelled_messages!=1 || completed_messages || q_taken_count)$fatal(1,"drained cancellation without fake CQ");
  end else begin
   certify;
   if(mode==27)begin trusted_pd=18;expect_fault;end
   else if(mode==34 || mode==35)begin
    s_cancel_context=expected_context;s_cancel_valid=1;
    if(mode==35)begin s_cancel_context[152]=~s_cancel_context[152];expect_fault;end
    else begin
     repeat(5)begin tick;good;if(s_cancel_ready || !message_active)$fatal(1,"cancel missing real parent drain");end
     cancel_drained=1;tick;s_cancel_valid=0;good;
     if(message_active || cancelled_messages!=1 || completed_messages || q_taken_count)$fatal(1,"one drained cancel, no CQ");
    end
   end else if(mode>=22 && mode<=26)begin
    emit_packet(mode==23 ? 8:mode==24 ? 6:mode==25 ? 12:7,4096,mode==23 ? 1:4096,
      mode==22 ? 0:24'hffffff,mode==26 ? 1:2);
    reject_packet(mode==26 ? 36:16,1);no_revoke;
   end else begin
    offset_index=4096;
    while(offset_index<total)begin
     cur_length=(total-offset_index>4096 ? 4096:total-offset_index);
     emit_packet(offset_index+cur_length==total ? (imm ? 9:8):7,offset_index,cur_length,
        (24'hfffffe+offset_index/4096)&24'hffffff,offset_index/4096+1);
     if(mode==32)begin expect_fault;offset_index=total;end
     else if(mode==33 && offset_index+cur_length==total)begin expect_fault;
      if(q_taken_count || !message_active)$fatal(1,"wrong-PD RQ cannot be consumed");offset_index=total;end
     else begin
      if(mode==4 && offset_index+cur_length==total)begin
       reject_packet(38,1);
       if(grants!=2 || completed_packets!=2 || q_taken_count)$fatal(1,"RNR must not advance WRITE position/PSN");
       post_rq(0,17);emit_packet(9,offset_index,cur_length,cur_psn,cur_tag);
      end
      wait_grant;
      if(mode==30)begin s_done_token=expected_token;s_done_msn=8;s_done_proofs=15;s_done_valid=1;
       expect_fault;offset_index=total;
      end else begin certify;offset_index=offset_index+cur_length;end
     end
    end
    if(mode!=30 && mode!=32 && mode!=33)begin
     if(imm)complete_notice;
     else if(message_active || configuration_guard || completed_messages!=1 || q_taken_count || q_posted_count)
      $fatal(1,"ordinary WRITE must finish without notification RQ/CQ");
     packets=(total+4095)/4096;
     if(queries!=packets+1+(mode==4 ? 1:0) || grants!=packets || completed_packets!=packets)
      $fatal(1,"actual whole+per-packet MR queries and exactly one grant/completion per packet");
    end
   end
  end
 end
 end
 $display("REMOTE_WRITE_MR_RESULT {\"pass_test\":true,\"mode\":%0d,\"MR_queries\":%0d,\"grants\":%0d,\"completed_packets\":%0d,\"completed_messages\":%0d,\"cancelled_messages\":%0d,\"RQ_posted\":%0d,\"RQ_taken\":%0d,\"fault\":%0d,\"message_active\":%0d}",
  mode,queries,grants,completed_packets,completed_messages,cancelled_messages,q_posted_count,q_taken_count,fault,message_active);
 $finish;
end
endmodule
