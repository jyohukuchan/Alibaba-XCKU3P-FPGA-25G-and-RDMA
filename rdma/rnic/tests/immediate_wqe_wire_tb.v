// SPDX-License-Identifier: BSD-2-Clause-Views
// Real codec bytes/SQ-result admission/MR/typed staging/generated HLS/integrity.
// SQ DMA, host payload, executor lifetime and peer ACK source are MODELS.
`timescale 1ns/1ps
module tb;
reg clk=0;always #2 clk=~clk;
reg rst=1;integer cycle=0,case_id=0;
reg [511:0] records[0:7];reg [144:0] acknowledgments[0:23];
reg fetch_valid=0;wire fetch_ready;
wire [63:0] wid,wseq,wepoch,wla,woff,wra;
wire [23:0] wq;wire [15:0] wpd,wtag,wop,wflags;
wire [31:0] wlen,wlk,wrk,wimm;wire [7:0] werr,wfetch;
wire [1:0] wsource;wire wavail,wauth,wvalid,wready,front_busy,front_guard,front_fault;
wire [7:0] front_qguard,front_code;
wire [619:0] work={wimm,wid,wseq,wepoch,wq,wpd,wtag,wop,wflags,wlen,wlk,wla,woff,wra,wrk,werr,wsource,wfetch,wavail,wauth};
wire [15:0] qpd,qt,rt;wire [31:0] qkey,qlen,rlen;
wire [63:0] qa,roff;wire [2:0] qop;wire qv,qr,rv,rr;wire [7:0] rerr;
reg cfg_valid=0,cfg_result_ready=0;reg [1:0] cfg_command=0;
reg [31:0] cfg_key=0;wire cfg_ready,cfg_result_valid,configured;
wire [7:0] cfg_error;wire [31:0] cfg_result_key;
wire [619:0] owner;wire owner_valid,owner_ready;
wire [279:0] sq;wire sq_valid,sq_ready,stage_busy,stage_fault;
wire [7:0] stage_guard,stage_code;reg [7:0] executor_model_guard=0;
wire [31:0] owner_count,sq_count;
wire core_owner_ready;wire core_owner_valid=owner_valid && executor_model_guard[2];
assign owner_ready=core_owner_ready && executor_model_guard[2];
reg [619:0] saved_owner=0;
wire [687:0] request_done;wire request_done_valid;reg request_done_ready=0;
wire rnr_fault,recv_fault,request_fault;
reg qp_valid=0,conn_valid=0;wire qp_ready,conn_ready;
wire [79:0] qp_applied;wire qp_applied_valid;
wire [127:0] tx_data;wire [15:0] tx_keep;wire tx_valid,tx_last;
reg tx_ready=0;
reg [127:0] rx_data=0;reg [15:0] rx_keep=0;reg rx_valid=0,rx_last=0;wire rx_ready;
wire [95:0] source_command;wire source_command_valid,source_ready;
reg [511:0] source_data=0;reg [63:0] source_keep=0;
reg source_valid=0,source_last=0,source_active=0;integer source_offset=0;
wire [31:0] rx_good,rx_bad,tx_good,tx_bad,overflow,psn_drop,retrans;
wire write_command_valid,write_data_valid,ack_valid;
wire [751:0] receive_done;wire receive_done_valid;
integer owner_transfers=0,sq_transfers=0,commands=0,source_frames=0,frames=0,done_count=0,queries=0;
integer network_stalls=0,lane,deadline,j;
reg [687:0] saved_done=0;
reg owner_stall=0,sq_stall=0,network_stall=0;
reg [619:0] held_owner;reg [279:0] held_sq;reg [144:0] held_network;

rocev2_sq_wqe_admission #(.SEND_ENABLE(1),.IMMEDIATE_ENABLE(1)) admission(
 .clk(clk),.rst(rst),.enable(configured),.configuration_idle(!cfg_valid && configured),
 .s_fetch_data(records[case_id]),.s_fetch_error(8'd0),.s_fetch_qpn(24'd2),.s_fetch_pd(16'd17),
 .s_fetch_epoch(64'h9123456700000001),.s_fetch_sequence(case_id+64'd1),.s_fetch_tag(16'hf123),
 .s_fetch_valid(fetch_valid),.s_fetch_ready(fetch_ready),
 .m_mr_request_pd(qpd),.m_mr_request_key(qkey),.m_mr_request_address(qa),.m_mr_request_length(qlen),
 .m_mr_request_operation(qop),.m_mr_request_tag(qt),.m_mr_request_valid(qv),.m_mr_request_ready(qr),
 .s_mr_response_tag(rt),.s_mr_response_error(rerr),.s_mr_response_offset(roff),.s_mr_response_length(rlen),
 .s_mr_response_valid(rv),.s_mr_response_ready(rr),
 .m_work_wr_id(wid),.m_work_sequence(wseq),.m_work_epoch(wepoch),.m_work_qpn(wq),.m_work_pd(wpd),.m_work_tag(wtag),
 .m_work_opcode(wop),.m_work_flags(wflags),.m_work_length(wlen),.m_work_local_key(wlk),
 .m_work_local_address(wla),.m_work_local_offset(woff),.m_work_remote_address(wra),.m_work_remote_key(wrk),
 .m_work_immediate(wimm),.m_work_error(werr),.m_work_error_source(wsource),.m_work_fetch_error(wfetch),
 .m_work_descriptor_available(wavail),.m_work_authorized(wauth),.m_work_valid(wvalid),.m_work_ready(wready),
 .queue_guard(front_qguard),.configuration_guard(front_guard),.busy(front_busy),.fault(front_fault),.fault_code(front_code));
rocev2_mr_table #(.REQUIRE_EPOCH(1)) mr(
 .clk(clk),.rst(rst),.cfg_quiescent(!front_guard && !stage_guard && !executor_model_guard),
 .cfg_command(cfg_command),.cfg_index(3'd0),.cfg_pd(16'd17),.cfg_key(cfg_key),
 .cfg_virtual_address(64'hfedcba9876543000),.cfg_dma_address(64'd0),.cfg_length(64'd8192),.cfg_access(4'd0),
 .cfg_valid(cfg_valid),.cfg_ready(cfg_ready),.cfg_response_error(cfg_error),.cfg_response_key(cfg_result_key),
 .cfg_response_valid(cfg_result_valid),.cfg_response_ready(cfg_result_ready),.epoch_configured(configured),
 .s_request_pd(qpd),.s_request_key(qkey),.s_request_address(qa),.s_request_length(qlen),
 .s_request_operation(qop),.s_request_tag(qt),.s_request_valid(qv),.s_request_ready(qr),
 .m_response_tag(rt),.m_response_error(rerr),.m_response_offset(roff),.m_response_dma_address(),.m_response_length(rlen),
 .m_response_valid(rv),.m_response_ready(rr));
rocev2_wqe_hls_sq #(.IMMEDIATE_ENABLE(1)) staging(
 .clk(clk),.rst(rst),.enable(1'b1),.halt(1'b0),.s_work_context(work),.s_work_valid(wvalid),.s_work_ready(wready),
 .m_owner_context(owner),.m_owner_valid(owner_valid),.m_owner_ready(owner_ready),.downstream_queue_guard(executor_model_guard),
 .m_axis_sq_tdata(sq),.m_axis_sq_tvalid(sq_valid),.m_axis_sq_tready(sq_ready),
 .queue_guard(stage_guard),.configuration_guard(),.busy(stage_busy),.fault(stage_fault),.fault_code(stage_code),
 .owner_handoff_count(owner_count),.HLS_SQ_handoff_count(sq_count));
rocev2_immediate_integrity_transport #(.LEGACY_QP_KEY(0),.REQUEST_CQ_ENABLE(1)) transport(
 .clk(clk),.rst(rst),.s_rnr_event_tdata(56'd0),.s_rnr_event_tvalid(1'b0),.s_rnr_event_tready(),.rnr_fault(rnr_fault),
 .s_recv_owner_tdata(680'd0),.s_recv_owner_tvalid(1'b0),.s_recv_owner_tready(),
 .m_recv_done_tdata(receive_done),.m_recv_done_tvalid(receive_done_valid),.m_recv_done_tready(1'b1),.recv_fault(recv_fault),
 .s_request_owner_tdata(owner),.s_request_owner_tvalid(core_owner_valid),.s_request_owner_tready(core_owner_ready),
 .m_request_done_tdata(request_done),.m_request_done_tvalid(request_done_valid),.m_request_done_tready(request_done_ready),.request_fault(request_fault),
 .m_axis_qp_apply_tdata(qp_applied),.m_axis_qp_apply_tvalid(qp_applied_valid),.m_axis_qp_apply_tready(1'b1),
 .s_axis_rx_tdata(rx_data),.s_axis_rx_tkeep(rx_keep),.s_axis_rx_tvalid(rx_valid),.s_axis_rx_tready(rx_ready),.s_axis_rx_tlast(rx_last),.s_axis_rx_tuser(1'b0),
 .m_axis_tx_tdata(tx_data),.m_axis_tx_tkeep(tx_keep),.m_axis_tx_tvalid(tx_valid),.m_axis_tx_tready(tx_ready),.m_axis_tx_tlast(tx_last),
 .s_axis_qp_tdata({32'hfedcba98,48'd0,24'h123456,24'hfffffe,24'd2,32'd3}),.s_axis_qp_tvalid(qp_valid),.s_axis_qp_tready(qp_ready),
 .s_axis_conn_tdata({16'd4791,{4{32'h010b12c6}},24'd196,16'd2}),.s_axis_conn_tvalid(conn_valid),.s_axis_conn_tready(conn_ready),
 .s_axis_sq_tdata(sq),.s_axis_sq_tvalid(sq_valid),.s_axis_sq_tready(sq_ready),
 .m_axis_ack_tdata(),.m_axis_ack_tvalid(ack_valid),.m_axis_ack_tready(1'b1),
 .m_axis_mem_write_cmd_tdata(),.m_axis_mem_write_cmd_tvalid(write_command_valid),.m_axis_mem_write_cmd_tready(1'b1),
 .m_axis_mem_write_tdata(),.m_axis_mem_write_tkeep(),.m_axis_mem_write_tvalid(write_data_valid),.m_axis_mem_write_tready(1'b1),.m_axis_mem_write_tlast(),
 .m_axis_mem_read_cmd_tdata(source_command),.m_axis_mem_read_cmd_tvalid(source_command_valid),.m_axis_mem_read_cmd_tready(!source_active),
 .s_axis_mem_read_tdata(source_data),.s_axis_mem_read_tkeep(source_keep),.s_axis_mem_read_tvalid(source_valid),.s_axis_mem_read_tready(source_ready),.s_axis_mem_read_tlast(source_last),
 .local_ip_address({4{32'h020b12c6}}),.m_axis_debug_tdata(),.m_axis_debug_tvalid(),.m_axis_debug_tready(1'b1),
 .core_psn_drop_count(psn_drop),.core_retransmit_count(retrans),.core_rx_word_count(),.core_tx_word_count(),
 .rx_integrity_good_count(rx_good),.rx_integrity_drop_count(rx_bad),.tx_integrity_good_count(tx_good),.tx_integrity_drop_count(tx_bad),.integrity_overflow_count(overflow));

always @(negedge clk)if(!rst)begin
 tx_ready=cycle>2400 && cycle%11>2;
 if(owner_valid)executor_model_guard=8'h04;
 source_valid=source_active;source_data=0;source_keep=0;source_last=0;
 if(source_active)begin
  for(lane=0;lane<64;lane=lane+1)if(source_offset+lane<65)begin
   source_data[lane*8+:8]=((source_offset+lane)*131)^8'h5a;source_keep[lane]=1;
  end
  source_last=source_offset+64>=65;
 end
end
always @(posedge clk)if(!rst)begin
 cycle=cycle+1;if(cycle>12000)$fatal(1,"Immediate pipeline deadline frames%0d done%0d request_fault%0d",frames,done_count,request_fault);
 if(front_fault || stage_fault || request_fault || recv_fault || rnr_fault || rx_bad || tx_bad || overflow || psn_drop || retrans)
  $fatal(1,"Immediate actual pipeline fault front%h stage%h request%0d",front_code,stage_code,request_fault);
 if(owner_stall && (!owner_valid || owner!==held_owner))$fatal(1,"owner changed under backpressure");
 if(sq_stall && (!sq_valid || sq!==held_sq))$fatal(1,"Immediate SQ changed under backpressure");
 if(network_stall && (!tx_valid || {tx_last,tx_keep,tx_data}!==held_network))$fatal(1,"wire changed under backpressure");
 owner_stall=owner_valid&&!owner_ready;held_owner=owner;sq_stall=sq_valid&&!sq_ready;held_sq=sq;
 network_stall=tx_valid&&!tx_ready;held_network={tx_last,tx_keep,tx_data};if(network_stall)network_stalls=network_stalls+1;
 if(qv&&qr)begin
  queries=queries+1;
  if(qpd!==17 || qkey!==32'h80000008 || qa!==64'hfedcba9876543210 || qlen!==65 || qop!==0)$fatal(1,"full actual MR query changed");
 end
 if(wvalid && (werr || !wauth || wimm!==records[case_id][415:384] || woff!==64'h210))$fatal(1,"authorized work lost Immediate/offset");
 if(owner_valid&&owner_ready)begin owner_transfers=owner_transfers+1;saved_owner=owner;end
 if(sq_valid&&sq_ready)begin
  if(owner_transfers!=1 || sq[272:241]!==saved_owner[619:588] || sq[279:273]!=0 || !sq[240] ||
     sq[239:208]!==records[case_id][351:320] || executor_model_guard!==8'h04)$fatal(1,"SQ Immediate/key/owner alias");
  sq_transfers=sq_transfers+1;
 end
 if(source_command_valid && !source_active)begin
  if(commands || source_command[95:94]!==2 || source_command[47:0]!==48'hba9876543210 ||
     source_command[75:48]!==65 || source_command[93:84]!==2 || !source_command[79])$fatal(1,"actual local memory origin/command");
  commands=commands+1;source_offset=0;source_active<=1;
 end
 if(source_valid&&source_ready)begin
  source_offset=source_offset+64;
  if(source_last)begin source_active<=0;source_frames=source_frames+1;end
 end
 if(tx_valid&&tx_ready)begin
  $display("IMMEDIATE_IP %032h %04h %0d",tx_data,tx_keep,tx_last);
  if(tx_last)frames=frames+1;
 end
 if(write_command_valid || write_data_valid || receive_done_valid)$fatal(1,"TX request invented RX placement");
 if(request_done_valid && (request_done[619:0]!==saved_owner || request_done[643:620]!==24'hfffffe ||
    request_done[667:644]!==24'hffffff || request_done[675:668]!==(case_id<4 ? 8'h05:8'h0b) || request_done[687:676]!=0))
  $fatal(1,"actual Immediate retire receipt lost full immutable owner");
 if(request_done_valid&&request_done_ready)done_count=done_count+1;
 if((front_guard || stage_guard || executor_model_guard) && cfg_ready)$fatal(1,"MR mutation ready across owner handoff");
end
task manage;
 input [1:0] command;input [31:0] key,expected;
 begin
  @(negedge clk);cfg_command=command;cfg_key=key;cfg_valid=1;
  @(posedge clk);while(!cfg_ready)@(posedge clk);
  @(negedge clk);cfg_valid=0;
  while(!cfg_result_valid)@(negedge clk);
  if(cfg_error || cfg_result_key!==expected)$fatal(1,"actual MR setup failed");
  cfg_result_ready=1;@(posedge clk);@(negedge clk);cfg_result_ready=0;
 end
endtask
initial begin
 if(!$value$plusargs("CASE=%d",case_id))case_id=0;
 if(case_id<0 || case_id>7)$fatal(1,"bad test case");
 $readmemh("records.hex",records);$readmemh("acks.hex",acknowledgments);
 repeat(8)@(negedge clk);rst=0;
 manage(3,32'h10000000,32'h10000000);manage(1,0,32'h80000008);
 qp_valid=1;@(posedge clk);while(!qp_ready)@(posedge clk);@(negedge clk);qp_valid=0;
 conn_valid=1;@(posedge clk);while(!conn_ready)@(posedge clk);@(negedge clk);conn_valid=0;
 while(cycle<2200)@(negedge clk);
 fetch_valid=1;@(posedge clk);while(!fetch_ready)@(posedge clk);@(negedge clk);fetch_valid=0;
 while(frames!=1 || source_active)@(negedge clk);
 if(request_done_valid)$fatal(1,"Immediate request completed without peer ACK");
 repeat(17)@(negedge clk);
 for(j=0;j<3;j=j+1)begin
  {rx_last,rx_keep,rx_data}=acknowledgments[case_id*3+j];rx_valid=1;
  @(posedge clk);while(!rx_ready)@(posedge clk);@(negedge clk);rx_valid=0;
 end
 while(!request_done_valid)@(negedge clk);
 saved_done=request_done;
 repeat(17)begin
  @(negedge clk);
  if(!request_done_valid || request_done!==saved_done || executor_model_guard!==8'h04 || cfg_ready)$fatal(1,"held actual receipt lost owner");
 end
 request_done_ready=1;@(posedge clk);@(negedge clk);request_done_ready=0;
 if(done_count!=1 || queries!=1 || commands!=1 || source_frames!=1 || owner_count!=1 || sq_count!=1 ||
    front_busy || stage_busy || rx_good!=1 || tx_good!=1 || !network_stalls)$fatal(1,"pipeline coverage incomplete");
 executor_model_guard=0;repeat(8)@(negedge clk);
 if(front_guard || stage_guard || request_done_valid || !cfg_ready)$fatal(1,"candidate model handoff did not finish");
 $display("IMMEDIATE_WQE_WIRE {\"pass_test\":true,\"case\":%0d,\"actual_MR_query\":true,\"typed_owner_and_SQ\":true,\"actual_generated_HLS\":true,\"actual_request_retire\":true,\"native_DMA_MAC_CQ_or_physical\":false}",case_id);
 $finish;
end
endmodule
