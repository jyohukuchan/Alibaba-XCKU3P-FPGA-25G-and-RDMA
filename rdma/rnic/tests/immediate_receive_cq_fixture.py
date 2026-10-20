# SPDX-License-Identifier: BSD-2-Clause-Views
"""Real Immediate RQ/MAC receipt/CQC leaf; admitted wire/core/DMA are MODELS."""
import re
import test_receive_ack_rtl as ack
import test_cq_path_rtl as cq

ROOT=ack.ROOT
SOURCES=[ack.RTL,ROOT/'rdma/rnic/rtl/rocev2_receive_queue.v',cq.RTL]+[
    cq.AXI/(n+'.v')for n in ['axil_reg_if','axil_reg_if_rd','axil_reg_if_wr']]
VALUES=[0,0x01234567,0x80000000,0xffffffff]

def context(seq,write=False):
    value=int(ack.context(qpn=7,sequence=seq).split("'h")[1],16)
    value=(value&~(((1<<32)-1)<<276))|((1 if write else 128)<<276)
    return f"620'h{value:0155x}"

def once(t,a,b):
    if t.count(a)!=1:raise ValueError('Immediate CQ fixture anchor changed: '+a)
    return t.replace(a,b,1)

def bench():
    header=ack.RTL.read_text().split(')(\n',1)[1].split('\n);',1)[0]
    ports=re.findall(r'\b(input|output)\s+(?:wire|reg)\s+(\[[^]]+\]\s+)?(\w+)',header)
    driven={'s_owner_context','s_owner_valid','s_retire_context','s_retire_valid','m_done_ready'}
    declarations='\n'.join(('reg 'if d=='input'and n not in driven else'wire ')+(w or'')+n+
        ('=0;'if d=='input'and n not in driven else';')for d,w,n in ports)
    mapping={'s_core_data':'rq_core_data','s_core_valid':'rq_core_proved'}
    instance='rocev2_receive_ack_tx #(.IMMEDIATE_ENABLE(1)) mac_owner('+','.join(
        '.'+n+'('+mapping.get(n,n)+')'for _,_,n in ports)+');'
    host=cq.HOST[:cq.HOST.index('task cq_snapshot;')].replace('[587:0]','[619:0]')
    host=once(host,'rocev2_cq_mmio publisher(', 'rocev2_cq_mmio #(.MESSAGE_ENABLE(1),.IMMEDIATE_ENABLE(1)) publisher(')
    host=once(host,".s_ticket_received_bytes(32'd0),",'.s_ticket_received_bytes(ticket_bytes),\n'
        ' .s_ticket_notification(ticket_notification),.s_ticket_notification_flags(ticket_flags),')
    host=once(host,'.m_retire_ready(retire_allowed)', '.m_retire_ready(retire_allowed && rq_retire_ready && s_retire_ready)')
    body=''
    for seq in range(1,9):
        body+=f'operation({context(seq,seq>4)},32\'h{VALUES[(seq-1)%4]:08x},8\'d{3 if seq>4 else 1},{seq});\n'
    return r'''
`timescale 1ns/1ps
module tb;
localparam IMMEDIATE_ENABLE=1;
'''+declarations+r'''
reg [619:0] post_context=0,placement_context=0;
reg post_valid=0,placement_valid=0;wire post_ready,placement_ready;
reg [23:0] placement_psn=0;reg [31:0] placement_notification=0;
reg [7:0] placement_flags=0;
wire rq_core_ready,rq_core_proved,rq_mac_ready,rq_active,rq_fault;
wire [7:0] rq_guard,rq_fault_code;wire [751:0] rq_core_data;
reg physical_memory_drained=0,commit_allowed=0;
wire [619:0] m_cq_context,s_cq_commit_context;wire [7:0] s_cq_commit_error;
wire m_cq_valid,m_cq_ready,s_cq_commit_valid,s_cq_commit_ready;
wire rq_commit_ready,rq_retire_ready;
wire [31:0] ticket_bytes,ticket_notification;wire [7:0] ticket_flags;
wire rq_commit_valid=s_cq_commit_valid && commit_allowed;
wire rq_retire_valid=pub_retire_valid && retire_allowed && s_retire_ready;
assign s_cq_commit_ready=rq_commit_ready && commit_allowed;
assign s_retire_context=pub_retire_context;
assign s_retire_valid=pub_retire_valid && retire_allowed && rq_retire_ready;
assign m_done_ready=rq_mac_ready;
integer cycle=0,deadline,i,seqno=0;reg [127:0] words[0:3];reg [160:0] held_frame;
always #2 clk=~clk;
always @(posedge clk)if(!rst)begin
 cycle=cycle+1;if(cycle>80000)$fatal(1,"Immediate receive/CQ bounded deadline");
 if(fault || rq_fault || pub_fault)$fatal(1,"Immediate receive/CQ fault ACK%h RQ%h CQ%h",fault_code,rq_fault_code,pub_fault_code);
end
rocev2_receive_queue #(.RECV_RETIRE_ENABLE(1),.RECV_CQ_ENABLE(1),.IMMEDIATE_ENABLE(1)) rq(
 .clk(clk),.rst(rst),.parent_fault(parent_fault),
 .cancel_block(1'b0),.cancel_valid(1'b0),.cancel_safe(1'b0),.cancel_qpn(24'd0),.cancel_pd(16'd0),.cancel_epoch(64'd0),.cancel_ready(),.cancelled_count(),
 .s_post_context(post_context),.s_post_valid(post_valid),.s_post_ready(post_ready),
 .query_qpn(24'd7),.m_head_context(s_owner_context),.m_head_valid(s_owner_valid),.m_head_ready(s_owner_ready),
 .s_placement_context(placement_context),.s_placement_length(32'd65),.s_placement_valid(placement_valid),.s_placement_ready(placement_ready),
 .s_placement_psn(placement_psn),.s_placement_notification(placement_notification),.s_placement_notification_flags(placement_flags),
 .s_core_data(s_core_data),.s_core_valid(s_core_valid),.s_core_ready(rq_core_ready),.core_proved(rq_core_proved),.core_proof_count(),.core_msn(),
 .held_context(),.held_core_data(rq_core_data),.s_mac_data(m_done_data),.s_mac_valid(m_done_valid),.s_mac_ready(rq_mac_ready),
 .memory_drained(physical_memory_drained),.m_ticket_context(m_cq_context),.m_ticket_received_bytes(ticket_bytes),
 .m_ticket_notification(ticket_notification),.m_ticket_notification_flags(ticket_flags),.m_ticket_valid(m_cq_valid),.m_ticket_ready(m_cq_ready),
 .s_commit_context(s_cq_commit_context),.s_commit_valid(rq_commit_valid),.s_commit_ready(rq_commit_ready),
 .s_retire_context(pub_retire_context),.s_retire_valid(rq_retire_valid),.s_retire_ready(rq_retire_ready),
 .queue_guard(rq_guard),.active(rq_active),.fault(rq_fault),.fault_code(rq_fault_code),
 .posted_count(),.taken_count(),.placement_count(),.received_bytes());
'''+instance+'\n'+host+r'''
task operation;
 input [619:0] ctx;input [31:0] notification;input [7:0] flags;input integer seq;
 reg [751:0] expected_core;reg [31:0] expected_word;
 begin
  seqno=seq;physical_memory_drained=0;commit_allowed=0;
  case(seq)
   1:$readmemh("ack1.hex",words);2:$readmemh("ack2.hex",words);3:$readmemh("ack3.hex",words);4:$readmemh("ack4.hex",words);
   5:$readmemh("ack5.hex",words);6:$readmemh("ack6.hex",words);7:$readmemh("ack7.hex",words);8:$readmemh("ack8.hex",words);
  endcase
  @(negedge clk);post_context=ctx;post_valid=1;
  @(posedge clk);if(!post_ready)$fatal(1,"RQ post notification owner");@(negedge clk);post_valid=0;
  deadline=cycle+50;while(!rq_active || !busy)begin if(cycle>deadline)$fatal(1,"RQ/ACK owner handoff");@(negedge clk);end
  placement_context=ctx;placement_psn=24'h987653+seq;placement_notification=notification;placement_flags=flags;placement_valid=1;
  @(posedge clk);if(!placement_ready)$fatal(1,"Immediate placement-notification bind");@(negedge clk);placement_valid=0;
  for(i=0;i<4;i=i+1)begin
   s_axis_tdata=words[i];s_axis_tkeep=i==3 ? 16'h3fff:16'hffff;s_axis_tlast=i==3;s_axis_tuser={16'h4000,1'b0};s_axis_tvalid=1;
   @(posedge clk);if(!s_axis_tready)$fatal(1,"Immediate ACK capture");@(negedge clk);s_axis_tvalid=0;
  end
  repeat(17)begin @(negedge clk);if(m_axis_tvalid || m_cq_valid || pub_busy)$fatal(1,"missing actual core receipt bypassed");end
  expected_core={8'd0,flags,notification,24'(seq),4'd0,24'(24'h987653+seq),32'd65,ctx};
  s_core_data=expected_core;s_core_valid=1;
  @(posedge clk);while(!rq_core_ready)@(posedge clk);@(negedge clk);s_core_valid=0;
  deadline=cycle+100;while(!m_axis_tvalid)begin if(cycle>deadline)$fatal(1,"Immediate ACK proof bind");@(negedge clk);end
  held_frame={m_axis_tdata,m_axis_tkeep,m_axis_tlast,m_axis_tuser};
  repeat(17)begin @(negedge clk);if(!m_axis_tvalid || {m_axis_tdata,m_axis_tkeep,m_axis_tlast,m_axis_tuser}!==held_frame)$fatal(1,"Immediate ACK backpressure");end
  for(i=0;i<4;i=i+1)begin
   m_axis_tready=1;@(posedge clk);
   if(!m_axis_tvalid || m_axis_tdata!==words[i] || m_axis_tuser!=={16'(16'h6000+seq),1'b0})$fatal(1,"Immediate ACK/fresh tag");
   @(negedge clk);m_axis_tready=0;
  end
  repeat(1100)begin @(negedge clk);if(m_done_valid || m_cq_valid || pub_busy || !rq_active || !busy)$fatal(1,"no MAC receipt yet");end
  s_cpl_tag=16'h6000+seq;s_cpl_ts=seq;s_cpl_valid=1;m_cpl_ready=0;
  repeat(17)begin @(negedge clk);if(!m_cpl_valid || s_cpl_ready || m_cpl_tag!==16'h4000)$fatal(1,"Immediate real receipt backpressure");end
  m_cpl_ready=1;@(posedge clk);@(negedge clk);s_cpl_valid=0;
  deadline=cycle+1150;while(!rq.mac_proved)begin if(cycle>deadline)$fatal(1,"Immediate MAC tail proof");@(negedge clk);end
  repeat(17)begin @(negedge clk);if(m_cq_valid || pub_busy || !rq_active || !busy)$fatal(1,"missing physical memory visibility bypassed");end
  physical_memory_drained=1;deadline=cycle+100;
  while(!s_cq_commit_valid)begin if(cycle>deadline)$fatal(1,"Immediate CQ ticket");@(negedge clk);end
  repeat(17)begin @(negedge clk);if(s_cq_commit_context!==ctx || pub_guard!==8'h80 || !rq_active || !busy)$fatal(1,"Immediate immutable commit hold");end
  cq_read(12'h00c,host_value);if(host_value!==2)$fatal(1,"CQ visible before commit");
  cq_read(12'h090,host_value);if(host_value)$fatal(1,"early notification visibility");
  commit_allowed=1;@(posedge clk);@(negedge clk);commit_allowed=0;
  repeat(17)begin @(negedge clk);if(!pub_retire_valid || pub_retire_context!==ctx || !rq_active || !busy)$fatal(1,"actual RQ/ACK retirement hold");end
  retire_allowed=1;@(posedge clk);if(!rq_retire_ready || !s_retire_ready)$fatal(1,"atomic RQ/ACK retirement");
  @(negedge clk);retire_allowed=0;
  if(rq_active || busy || rq_guard || queue_guard || pub_guard!==8'h80)$fatal(1,"CQ did not retain final owner guard");
  host_fd=$fopen($sformatf("event%0d.hex",seq),"w");
  cq_read(12'h018,host_value);if(host_value!=seq)$fatal(1,"event sequence");$fdisplay(host_fd,"%08h",host_value);
  cq_read(12'h01c,host_value);if(host_value!=15)$fatal(1,"real ownership handoffs");$fdisplay(host_fd,"%08h",host_value);
  cq_read(12'h028,host_value);$fdisplay(host_fd,"%08h",host_value);
  cq_read(12'h020,host_value);$fdisplay(host_fd,"%08h",host_value);cq_read(12'h024,host_value);$fdisplay(host_fd,"%08h",host_value);
  for(host_i=0;host_i<20;host_i=host_i+1)begin
   cq_read(12'h040+host_i*4,host_value);expected_word=({20'd0,ctx}>>(host_i*32));
   if(host_value!==expected_word)$fatal(1,"notification changed posted context/capacity");$fdisplay(host_fd,"%08h",host_value);
  end
  cq_read(12'h038,host_value);if(host_value!=65)$fatal(1,"actual received bytes");$fdisplay(host_fd,"%08h",host_value);
  cq_read(12'h03c,host_value);if(host_value!=flags)$fatal(1,"notification flags");$fdisplay(host_fd,"%08h",host_value);
  cq_read(12'h090,host_value);if(host_value!==notification)$fatal(1,"wire notification");$fdisplay(host_fd,"%08h",host_value);
  cq_read(12'h008,host_value);if(host_value!=7)$fatal(1,"matched CQ profile");$fdisplay(host_fd,"%08h",host_value);$fclose(host_fd);
  if(seq>1)begin cq_ack(seq-1);cq_read(12'h00c,host_value);if(host_value!==3)$fatal(1,"old ACK cleared next notification");end
  cq_ack(seq);if(pub_busy || pub_guard)$fatal(1,"host notification consumption did not release CQ");
 end
endtask
initial begin
 rst=1;repeat(5)@(negedge clk);rst=0;prior_response_drained=1;
 local_mac=48'h8af3fbb97531;peer_mac=48'hb8830367c5d0;local_ip=32'hc6120b02;peer_ip=32'hc6120b01;peer_qpn=196;
'''+body+r'''
 if(frame_count!=8 || receipt_count!=8 || pub_published!=8 || pub_acked!=8)$fatal(1,"Immediate receive notification coverage");
 $display("IMMEDIATE_RECEIVE_CQ {\"pass_test\":true,\"events\":8,\"actual_RQ_MAC_CQC\":true,\"wire_core_memory_source_models\":true,\"hardware_verified\":false}");$finish;
end
endmodule
'''
