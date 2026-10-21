#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual WRITE MR/lateRQ -> data/unpad/nonce/pagedRAM/fence -> ACK/MAC/DONE.

Metadata/trusted QP/post admission, HLS96/456/data/ACK and whole-RQ HLS
certificate boundaries are models/checked actual C++ traces, NOT live
generated HLS. Actual MR, guard, late-RQ, packet memory leaf, backend/page
splitter/RAM/fence and MAC/FCS/SFD/CDC execute real RTL. Descriptor engine/
host PCIe ordering/clock/PTP/PHY and CQ commit/retire consumers are models.
This is NOT the full native PCIe/TLP/HLS/Linux/board or1MiB qualification.
"""
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import probe_remote_write_mr_notice as authorization
import probe_receive_write_ack as ack_test
import test_paged_memory_backend_rtl as backend
from probe_segmented_write_receive_hls import verify_write_receive

ROOT=authorization.ROOT;digest=authorization.digest;ports=authorization.ports
MEMORY=ROOT/'rdma/rnic/rtl/rocev2_remote_write_memory.v'
NONCE=ROOT/'rdma/rnic/rtl/rocev2_memory_command_nonce.v'
MODES=list(range(14))


def instance(text,module,name,prefix,mapping,params=''):
    decl=[];connections=[]
    for d,w,n in ports(text):
        target=mapping.get(n,prefix+n);connections.append('.'+n+'('+target+')')
        if n not in mapping:decl.append(('reg 'if d=='input'else'wire ')+(w+' 'if w else'')+target+('=0;'if d=='input'else';'))
    return '\n'.join(decl)+'\n'+module+(' #('+params+')'if params else'')+' '+name+'('+','.join(connections)+');\n'


def bench(ack,queue):
    common=dict(clk='clk',rst='rst')
    # Original paged backend interface, RAM and descriptor-model task names.
    b=instance(backend.RTL.read_text(),'rocev2_paged_memory_backend','actual_backend','',
        dict(common,enable='enable',s_command_write='n_m_command_write',s_command_offset='n_m_command_offset',
        s_command_length='n_m_command_length',s_command_key='n_m_command_key',s_command_tag='n_m_command_tag',
        s_command_valid='n_m_command_valid',s_command_ready='n_m_command_ready',s_axis_write_tdata='e_m_data',
        s_axis_write_tkeep='e_m_keep',s_axis_write_tlast='e_m_last',s_axis_write_tvalid='e_m_valid',s_axis_write_tready='e_m_ready',
        cfg_quiescent='configuration_idle',m_status_ready='m_status_ready'))
    nonce=instance(NONCE.read_text(),'rocev2_memory_command_nonce','physical_nonce','n_',dict(common,
        enable='enable',parent_fault='fault || g_fault || e_fault || a_fault || q_fault',
        **{'s_command_'+n:'e_m_command_'+n for n in ['write','offset','length','key','tag','valid','ready']},
        **{'s_status_'+n:'m_status_'+n for n in ['tag','error','valid','ready']},m_status_ready='n_m_status_ready',m_command_ready='n_m_command_ready'))
    g=instance(authorization.GUARD.read_text(),'rocev2_remote_write_message_guard','message_guard','g_',dict(common,
        enable='enable',parent_fault='fault || e_fault || a_fault || q_fault || n_fault',
        **{'s_done_'+n:'e_m_done_'+n for n in ['token','msn','proofs']},s_done_valid='e_m_done_valid && done_allow',s_done_ready='done_ready',
        s_rq_context='q_m_notice_head_context',s_rq_valid='q_m_notice_head_valid',
        m_notice_ready='q_s_write_notice_ready',s_notice_retire_context='q_m_write_retire_context',
        s_notice_retire_valid='q_m_write_retire_valid',s_notice_retire_ready='q_m_write_retire_ready',
        m_packet_ready='g_m_packet_ready',m_mr_ready='g_m_mr_ready',
        **{'s_mr_'+n:'g_s_mr_'+n for n in ['tag','error','offset','address','length','valid']}),
        ".INITIAL_MESSAGE_COOKIE(64'hfedcba9876543212)")
    e=instance(MEMORY.read_text(),'rocev2_remote_write_memory','packet_memory','e_',dict(common,
        enable='enable',parent_fault='fault || g_fault || a_fault || q_fault || n_fault',
        **{'s_packet_'+n:'g_m_packet_'+n for n in ['token','mr_offset','mr_address','notify','rq_context','valid','ready']},
        **{'m_ack_owner'+n:'a_s_write_owner'+n for n in ['','_notify','_rq_context','_valid','_ready']},
        **{'s_status_'+n:'n_m_status_'+n for n in ['tag','error','valid','ready']},
        m_ack_core='a_s_write_core_data',m_ack_core_valid='a_s_write_core_valid',m_ack_core_ready='a_s_write_core_ready',
        s_ack_done='a_m_write_done_data',s_ack_done_valid='a_m_write_done_valid',s_ack_done_ready='a_m_write_done_ready',
        m_done_ready='done_ready && done_allow',m_ack_retire_token='retire_token',
        m_ack_retire_valid='retire_valid',m_ack_retire_ready='a_s_write_retire_ready && retire_allow',
        m_command_ready='e_m_command_ready',m_ready='e_m_ready'))
    a=instance(ack,ack_test.candidate.NAME,'shared_ack','a_',dict(common,parent_fault='fault || g_fault || e_fault || q_fault || n_fault',
        s_write_retire_token='retire_token',s_write_retire_valid='retire_valid && retire_allow',
        s_retire_context='q_m_packet_retire_context',s_retire_valid='q_m_packet_retire_valid',s_retire_ready='q_m_packet_retire_ready',
        m_done_data='q_s_mac_data',m_done_valid='q_s_mac_valid',m_done_ready='q_s_mac_ready',
        s_core_data='q_held_core_data',s_core_valid='q_core_proved',
        m_axis_tready='link_s_ready',s_cpl_tag='link_m_cpl_tag',s_cpl_ts='link_m_cpl_ts',
        s_cpl_valid='link_m_cpl_valid && receipt_allow',s_cpl_ready='actual_cpl_ready',
        **{'s_write_owner'+n:'a_s_write_owner'+n for n in ['','_notify','_rq_context','_valid']},
        s_write_core_data='a_s_write_core_data',s_write_core_valid='a_s_write_core_valid',
        m_write_done_ready='a_m_write_done_ready'),'.IMMEDIATE_ENABLE(1)')
    # The queue's real held core owner/proof drives the ACK leaf. Its whole
    # message HLS producer remains a boundary model, not an invented RQ.
    q=instance(queue,authorization.queue.NAME,'late_rq','q_',dict(common,parent_fault='fault || g_fault || e_fault || a_fault || n_fault',
        query_qpn='g_trusted_qpn',s_write_notice_context='g_m_notice_context',
        s_write_notice_last_psn='g_m_notice_last_psn',s_write_notice_valid='g_m_notice_valid',
        m_head_ready='g_m_notice_valid',memory_drained='dma_drained && !n_busy',
        m_write_retire_ready='q_m_write_retire_ready',m_packet_retire_ready='q_m_packet_retire_ready',
        s_mac_data='q_s_mac_data',s_mac_valid='q_s_mac_valid'))
    mr=instance(authorization.MR.read_text(),'rocev2_mr_table','actual_mr','mr_',dict(common,
        cfg_quiescent='configuration_idle',cfg_index="3'd7",cfg_pd="16'd17",cfg_virtual_address="64'he23456789abcdce0",
        cfg_dma_address="64'h9123456780000000",cfg_length="64'd8721",
        **{'s_request_'+n:'g_m_mr_'+n for n in ['pd','key','address','length','operation','tag','valid','ready']},
        **{'m_response_'+n:'g_s_mr_'+n for n in ['tag','error','offset','length','valid','ready']},m_response_dma_address='g_s_mr_address'),'.REQUIRE_EPOCH(1)')
    # Interconnects are declared exactly once, regardless of producer order.
    blocks=[b,nonce,g,e,a,q,mr];text='\n'.join(blocks)
    declared=set(re.findall(r'\b(?:reg|wire)\s+(?:\[[^]]+\]\s+)?(\w+)(?:=0)?;',text))
    missing={}
    # A mapped port can be shared by any number of instances; infer its width
    # from each endpoint and require identical static expressions there.
    for block,src in zip(blocks,[backend.RTL.read_text(),NONCE.read_text(),authorization.GUARD.read_text(),MEMORY.read_text(),ack,queue,authorization.MR.read_text()]):
        ws={n:w for _,w,n in ports(src)}
        for n,target in re.findall(r'\.(\w+)\((\w+)\)',block):
            if target in declared or target in ['clk','rst','enable','configuration_idle','done_allow','done_ready','retire_allow','retire_valid','receipt_allow','actual_cpl_ready','link_s_ready','link_m_cpl_tag','link_m_cpl_ts']:continue
            if target in ['link_m_cpl_valid','retire_token']:continue
            w=ws.get(n)
            if w is not None:missing.setdefault(target,w)
    text='\n'.join('wire '+(w+' 'if w else'')+n+';'for n,w in missing.items())+'\n'+text
    head=backend.TB[backend.TB.index('reg [7:0] host'):backend.TB.index('always @(negedge clk)')]
    head=head.replace('for(p=0;p<3;p=p+1)','for(p=0;p<4;p=p+1)')
    head=head.replace('2:dma_page=64\'h12345000;default:',"2:dma_page=64'h12345000;3:dma_page=64'ha123456789abc000;default:")
    head=head.replace('pattern=(pos*179)^(pos>>7)^seed^8\'hd3;',
        "pattern=((current_offset-528+pos)*113)^((current_offset-528+pos)>>8)^8'hb7;")
    tasks=backend.TB[backend.TB.index('task accept_descriptor;'):backend.TB.index('task completion;')]
    return r'''
`timescale 1ns/1ps
module tb;
localparam RAM_SIZE=8192,RAM_ADDR_WIDTH=15,SEG_COUNT=2,SEG_DATA_WIDTH=256,SEG_BE_WIDTH=32,
 SEG_ADDR_WIDTH=9,RAM_SEL_WIDTH=4,DMA_LEN_WIDTH=16,TAG_WIDTH=16,MAX_QPS=8,IMMEDIATE_ENABLE=1;
reg clk=0,rst=0,enable=0;always #2 clk=~clk;
reg done_allow=0,retire_allow=0,receipt_allow=0;
wire done_ready,retire_valid,actual_cpl_ready;wire [423:0] retire_token;
wire configuration_idle=!g_configuration_guard && !e_configuration_guard && !a_busy && q_queue_guard==0 && !n_busy;
'''+text+'\n'+head+'\n'+ack_test.physical.LINK+r'''
assign link_s_data=a_m_axis_tdata;assign link_s_keep=a_m_axis_tkeep;assign link_s_valid=a_m_axis_tvalid;
assign link_s_last=a_m_axis_tlast;assign link_s_user=a_m_axis_tuser;
assign link_m_cpl_ready=actual_cpl_ready && receipt_allow;
reg [455:0] records[0:2];reg [127:0] ack_words[0:3];reg [511:0] payload[0:63];
integer mode=0,packet_index,offset_value,payload_index,lane_value,limit,done_before,owner_beats=0,actual_done=0;
reg [423:0] token;reg [455:0] proof_value;reg [95:0] raw_command;reg [619:0] rq;
reg [775:0] whole;reg expect_fault=0;
wire any_fault=fault || e_fault || g_fault || a_fault || n_fault || q_fault;
always @(posedge clk)if(!rst)begin
 cycles=cycles+1;if(cycles>100000)$fatal(1,"original100000cycle4ns bound");
 if(any_fault && !expect_fault)$fatal(1,"connected WRITE fault mode%0d backend%h exec%h guard%h ack%h nonce%h rq%h",mode,fault_code,e_fault_code,g_fault_code,a_fault_code,n_fault_code,q_fault_code);
 if(e_m_hls_owner_valid && e_m_hls_owner_ready)begin
  if(e_m_hls_owner!==token)$fatal(1,"exact guarded424 -> HLS owner fanout");owner_beats=owner_beats+1;end
 if(e_m_done_valid && done_ready && done_allow)begin
  if(e_m_done_token!==token || e_m_done_msn!==proof_value[447:424] || e_m_done_proofs!==15 ||
     !packet_memory.data_done || !packet_memory.status_seen || !packet_memory.hls_seen || !packet_memory.ack_seen)
   $fatal(1,"actual four-consumer whole424/MSN completion join");actual_done=actual_done+1;
 end
end
task tick;begin @(posedge clk);@(negedge clk);end endtask
task mr_manage;
 input [1:0] op;input [31:0] key;
 begin mr_cfg_command=op;mr_cfg_key=key;mr_cfg_valid=1;
 @(posedge clk);while(!mr_cfg_ready)@(posedge clk);@(negedge clk);mr_cfg_valid=0;
 while(!mr_cfg_response_valid)tick;
 if(mr_cfg_response_error || mr_cfg_response_key!==(op==3 ? key:32'h81234567))$fatal(1,"real MR registration/epoch failed");
 mr_cfg_response_ready=1;tick;mr_cfg_response_ready=0;end
endtask
task page_config;
 input integer op,index;
 begin cfg_command=op;cfg_slot=7;cfg_key=32'h81234567;cfg_length=8721;cfg_first_offset=4093;
 cfg_page_index=index;cfg_dma_page=dma_page(index);cfg_valid=1;
 @(posedge clk);while(!cfg_ready)@(posedge clk);@(negedge clk);cfg_valid=0;
 while(!cfg_response_valid)tick;if(cfg_response_error || cfg_response_key!==32'h81234567)$fatal(1,"real PTE registration failed");
 cfg_response_ready=1;tick;cfg_response_ready=0;end
endtask
task no_revoke;
 begin mr_cfg_command=2;mr_cfg_key=32'h81234567;mr_cfg_valid=1;cfg_command=4;cfg_valid=1;
 repeat(11)begin tick;if(mr_cfg_ready || cfg_ready || configuration_idle || !g_message_active)
  $fatal(1,"real message owner must block MR/PTE invalidation");end
 mr_cfg_valid=0;cfg_valid=0;end
endtask
task metadata;
 begin
  g_s_packet_opcode=packet_index==0 ? 6:packet_index==2 ? (mode==1 ? 9:8):7;
  g_s_packet_qpn=2;g_s_packet_psn=token[39:16];g_trusted_expected_psn=token[39:16];
  g_s_packet_length=token[71:40];g_s_packet_wire_length=(token[71:40]+3)&32'hfffffffc;
  g_s_packet_pad=(-token[71:40])&3;g_s_packet_reth_valid=packet_index==0;
  g_s_packet_reth_va=64'he23456789abcdef0;g_s_packet_reth_key=32'h81234567;g_s_packet_reth_length=8193;
  g_s_packet_tag=token[15:0];g_s_packet_valid=1;
  @(posedge clk);if(!g_s_packet_ready)$fatal(1,"guard metadata admission");@(negedge clk);g_s_packet_valid=0;
  limit=cycles+300;while(!e_busy)begin if(cycles>limit)$fatal(1,"actual MR guard -> backend owner missing");tick;end
  if(packet_memory.owner!==token || packet_memory.mr_offset!==528+offset_value ||
     e_m_command_valid || e_m_done_valid)$fatal(1,"actual MR offset/full token never narrowed");
  no_revoke;
 end
endtask
task hls_command;
 reg [63:0] va;reg last_packet;reg [27:0] padded_count;
 begin va=64'he23456789abcdef0+offset_value;last_packet=packet_index==2;
  padded_count=(current_length+3)&28'hffffffc;
  raw_command={2'd0,10'd2,va[51:48],1'b1,1'b0,va[52],last_packet,padded_count,va[47:0]};
  if(mode==3)raw_command[0]=~raw_command[0];
  if(mode==4)raw_command[94]=1;
  e_s_hls_command=raw_command;e_s_hls_command_valid=1;
  if(mode==5)begin
   e_s_hls_data=payload[0];e_s_hls_keep=keep((current_length+3)&~3);e_s_hls_last=current_length<=64;e_s_hls_valid=1;
   repeat(11)begin tick;if(e_s_hls_ready || e_m_command_valid || !e_busy)$fatal(1,"early data bypassed accepted command");end
  end
  e_m_hls_owner_ready=1;
  @(posedge clk);while(!e_s_hls_command_ready && !any_fault)@(posedge clk);
  @(negedge clk);e_s_hls_command_valid=0;e_s_hls_valid=0;e_m_hls_owner_ready=0;
 end
endtask
task hls_payload;
 integer pos,count,b;
 begin
  for(pos=0;pos<current_length && !any_fault;pos=pos+64)begin
   count=current_length-pos;if(count>64)count=64;
   e_s_hls_data=payload[pos/64];e_s_hls_keep=keep((current_length+3 & ~3)-pos);
   e_s_hls_last=pos+64>=current_length;e_s_hls_valid=1;
   if(mode==6 && packet_index==2)e_s_hls_data[8]=1;
   if(mode==7)e_s_hls_keep=64'h7fffffffffffffff;
   if(mode==8)e_s_hls_last=1;
   @(posedge clk);while(!e_s_hls_ready && !any_fault)@(posedge clk);
   @(negedge clk);e_s_hls_valid=0;
  end
 end
endtask
task core_receipt;
 begin e_s_hls_done=proof_value;if(mode==9)e_s_hls_done[320]=~e_s_hls_done[320];
 if(mode==13)e_s_hls_done[424]=~e_s_hls_done[424];
 e_s_hls_done_valid=1;@(posedge clk);while(!e_s_hls_done_ready && !any_fault)@(posedge clk);
 @(negedge clk);e_s_hls_done_valid=0;end
endtask
task ack_frame;
 begin
  for(payload_index=0;payload_index<4 && !any_fault;payload_index=payload_index+1)begin
   a_s_axis_tdata=ack_words[payload_index];a_s_axis_tkeep=payload_index==3 ? 16'h3fff:16'hffff;
   a_s_axis_tlast=payload_index==3;a_s_axis_tuser={16'h4000,1'b0};a_s_axis_tvalid=1;
   @(posedge clk);while(!a_s_axis_tready && !any_fault)@(posedge clk);
   @(negedge clk);a_s_axis_tvalid=0;
  end
 end
endtask
'''+tasks+r'''
task finish_packet;
 begin
  limit=cycles+2000;while(!e_m_done_valid)begin if(cycles>limit)$fatal(1,"actual backend/HLS/MAC joined DONE missing");tick;end
  repeat(17)begin tick;if(!e_m_done_valid || e_m_done_token!==token || !e_busy || g_completed_packets!=packet_index)
   $fatal(1,"actual DONE backpressure retains packet/message owners");end
  done_allow=1;tick;done_allow=0;
  repeat(17)begin tick;if(!e_busy || !a_busy || !retire_valid)$fatal(1,"frontend DONE is not ACK retirement");end
  retire_allow=1;limit=cycles+100;
  while(e_busy)begin if(cycles>limit)$fatal(1,"paired actual ACK retirement missing");tick;end
  retire_allow=0;
  if(a_busy || g_completed_packets!=packet_index+1 || e_retired_count!=packet_index+1)$fatal(1,"packet release cardinality");
  for(lane_value=0;lane_value<16384;lane_value=lane_value+1)begin
   if(posted_valid[lane_value])$fatal(1,"unfenced host bytes remain");
   if(lane_value>=4093+528 && lane_value<4093+528+offset_value+current_length)begin
    if(host[lane_value]!==((((lane_value-4093-528)*113)^((lane_value-4093-528)>>8)^8'hb7)&8'hff))
     $fatal(1,"every actual host payload byte mismatch%0d",lane_value);
   end else if(host[lane_value]!==(((lane_value*37)^8'h5a)&8'hff))$fatal(1,"actual host sentinel changed%0d",lane_value);
  end
 end
endtask
initial begin
 dummy=$value$plusargs("MODE=%d",mode);expect_fault=mode>=3 && mode!=5;
 rst=1;repeat(5)@(negedge clk);rst=0;enable=1;mr_cfg_access=7;a_prior_response_drained=1;a_m_cpl_ready=1;
 a_local_mac=48'h8af3fbb97531;a_peer_mac=48'hb8830367c5d0;a_local_ip=32'hc6120b02;a_peer_ip=32'hc6120b01;a_peer_qpn=196;
 g_trusted_valid=1;g_trusted_qpn=2;g_trusted_pd=17;g_trusted_epoch=64'h9123456700000001;
 for(k=0;k<16384;k=k+1)begin host[k]=((k*37)^8'h5a)&255;posted_valid[k]=0;end
 mr_manage(3,32'h102468ab);mr_manage(1,0);
 page_config(1,0);for(k=0;k<4;k=k+1)page_config(2,k);page_config(3,0);
 $readmemh("write-proofs.hex",records);
 rq=0;rq[587:524]=64'hf123456789abc001;rq[523:460]=1;rq[459:396]=64'h9123456700000001;
 rq[395:372]=2;rq[371:356]=17;rq[355:340]=1;rq[339:324]=4;rq[323:308]=1;rq[19:0]=3;
 if(mode==1)begin q_s_post_context=rq;q_s_post_valid=1;
 @(posedge clk);if(!q_s_post_ready)$fatal(1,"real posted zero-cap notification");@(negedge clk);q_s_post_valid=0;end
 for(packet_index=0;packet_index<3 && !any_fault;packet_index=packet_index+1)begin
  proof_value=records[packet_index];token=proof_value[423:0];offset_value=token[103:72];
  current_length=token[71:40];current_offset=528+offset_value;receipt_allow=0;done_allow=0;retire_allow=0;
  $readmemh($sformatf("write%0d.hex",packet_index),ack_words);
  $readmemh($sformatf("payload%0d.hex",packet_index),payload,0,((current_length+3&~3)+63)/64-1);
  metadata;hls_command;
  if(mode==2)begin enable=0;repeat(17)begin tick;if(!e_busy || e_m_done_valid)$fatal(1,"admission disable lost live owner");end enable=1;end
  if(!any_fault)begin
   hls_payload;
   if(!any_fault)begin
    core_receipt;
    if(!any_fault)begin
     if(mode==1 && packet_index==2)begin
      q_s_placement_context=rq;q_s_placement_length=1;q_s_placement_psn=token[39:16];
      q_s_placement_notification=32'h89abcdf1;q_s_placement_notification_flags=3;q_s_placement_valid=1;
      @(posedge clk);if(!q_s_placement_ready)$fatal(1,"real notice placement");@(negedge clk);q_s_placement_valid=0;
      q_s_core_data={8'd0,8'd3,32'h89abcdf1,proof_value[447:424],4'd0,token[39:16],32'd1,rq};q_s_core_valid=1;
      @(posedge clk);if(!q_s_core_ready)$fatal(1,"modeled actual-RQ HLS producer");@(negedge clk);q_s_core_valid=0;
      whole={4'd0,8'd0,8'd3,32'h89abcdf1,24'd3,24'd4,24'd2,32'd8193,rq};
      q_s_message_data=whole;q_s_message_valid=1;
      @(posedge clk);if(!q_s_message_ready)$fatal(1,"modeled whole-RQ HLS producer");@(negedge clk);q_s_message_valid=0;
     end
     ack_frame;tick;
     if(!any_fault)begin
     repeat(1100)begin tick;if(e_m_done_valid || packet_memory.status_seen || g_completed_packets!=packet_index)
      $fatal(1,"HLS/SFD/quiet without actual data DMA/fence advanced packet");end
     if(mode==10)begin accept_descriptor(1,0,0);physical_status(1,0,issued_tag+1);end
     else begin service_payload(1,mode==11 ? 0:-1);
      if(mode!=11)service_fence(mode==12 ? 5:0);
     end
     if(!any_fault)begin
      limit=cycles+2000;while(!packet_memory.status_seen)begin if(cycles>limit)$fatal(1,"actual fence/nonce/status missing");tick;end
      repeat(1100)begin tick;if(e_m_done_valid || packet_memory.ack_seen || g_completed_packets!=packet_index)
       $fatal(1,"real fence/EOF plus quiet without accepted SFD receipt advanced packet");end
      receipt_allow=1;
      finish_packet;
     end
     end
    end
   end
  end
 end
 if(expect_fault)begin
  repeat(31)tick;
  if(!any_fault || !g_configuration_guard || !e_configuration_guard || g_completed_packets>=3 || e_m_done_valid || mr_cfg_ready || cfg_ready)
   $fatal(1,"bad transfer/status/proof lost remote MR/PTE lifetime");
 end else begin
  if(mode==1)begin
   limit=cycles+100;while(!q_m_ticket_valid)begin if(cycles>limit)$fatal(1,"actual whole-WRITE CQ ticket absent");tick;end
   if(q_m_ticket_received_bytes!=8193 || q_m_ticket_context!==rq || q_m_ticket_notification_flags!=3 || q_m_ticket_notification!==32'h89abcdf1)
    $fatal(1,"whole CQ does not equal last fragment or notification capacity");
   q_m_ticket_ready=1;tick;q_m_ticket_ready=0;q_s_commit_context=rq;q_s_commit_valid=1;tick;q_s_commit_valid=0;
   q_s_retire_context=rq;q_s_retire_valid=1;@(posedge clk);if(!q_s_retire_ready || !q_m_write_retire_valid || !q_m_write_retire_ready)
    $fatal(1,"actual joint whole RQ/remote MR retirement");@(negedge clk);q_s_retire_valid=0;
  end
  if(any_fault || g_message_active || e_busy || a_busy || q_active || g_completed_packets!=3 || g_completed_messages!=1 ||
     e_done_count!=3 || e_retired_count!=3 || packet_memory.status_count!=3 || actual_SFD_count!=3)
   $fatal(1,"actual connected WRITE completion counts");
 end
 $display("WRITE_MEMORY_RESULT {\"pass_test\":true,\"mode\":%0d,\"fault\":%0d,\"packets\":%0d,\"completed\":%0d,\"host_bytes\":%0d,\"physical_writes\":%0d,\"fences\":%0d,\"nonce_commands\":%0d,\"ACK_SFDs\":%0d,\"cycles\":%0d}",
 mode,any_fault,g_accepted_packets,g_completed_packets,write_bytes,physical_writes,fence_count,n_command_count,actual_SFD_count,cycles);
 $finish;
end
endmodule
'''


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve all prior evidence')
    run=Path(tempfile.mkdtemp(prefix='remote-write-memory-',dir=ROOT/'rdma/rnic/build'))
    ram=Path(tempfile.mkdtemp(prefix='as02-remote-write-memory-',dir='/dev/shm'))
    sources=[MEMORY,NONCE,authorization.GUARD,authorization.MR,*backend.SOURCES,*ack_test.physical.SOURCES]
    inputs=list(dict.fromkeys([*sources,Path(__file__).resolve(),Path(authorization.__file__).resolve(),authorization.BENCH,
        Path(ack_test.__file__).resolve(),Path(backend.__file__).resolve(),*sorted((ROOT/'rdma/rnic/fpga').glob('derive_*.py'))]))
    before={str(n.relative_to(ROOT)):digest(n)for n in inputs}
    result=dict(scope=__doc__,pass_test=False,directory=str(run.relative_to(ROOT)),source_sha256=before,tests={},
        planned_modes=MODES,compile_limit_seconds=10,runtime_limit_seconds=10,clock_ns=4,cycle_limit=100000,
        actual_MR_guard_RQ=True,actual_paged_backend_RAM_nonce_fence=True,actual_MAC_FCS_SFD_CDC=True,
        generated_HLS_live=False,full_native_PCIe_TLP=False,full_native_1MiB=False,live_Linux=False,hardware_verified=False)
    try:
        trace,paths=ack_test.traces();result['HLS_trace_sha256']={str(n.relative_to(ROOT)):digest(n)for n in paths}
        ack=ack_test.candidate.derive();q=authorization.queue.derive()
        (run/'ack.v').write_text(ack);(run/'rq.v').write_text(q);(run/'tb.v').write_text(bench(ack,q))
        (run/'lfsr_constant_masks.v').write_text(ack_test.crc.compiletime_lfsr())
        (run/'write-proofs.hex').write_text(''.join(f'{v["receipt"]:0114x}\n'for v in trace['write-rx']))
        r=json.loads((ROOT/'results/2026-10-18/rocev2-rnic-segmented-write-owned-hls-001.json').read_text())
        text=(ROOT/r['directory']/'write-rx.log').read_text();verify_write_receive(text,False)
        data={int(v[3]):bytes.fromhex(v[4])for s in text.splitlines()if s.startswith('WRITE_RECEIVE_DATA 0 8193 ')for v in [s.split()]}
        _,_,_,packet=ack_test.old_message.native.case(True,True)
        expected=[]
        for i,v in enumerate(trace['write-rx']):
            b=bytearray(packet);b[28:-4]=bytes.fromhex(v['ACK_body']);b=ack_test.old_message.native.qp.main.response.repair(b)
            f=bytes.fromhex('b8830367c5d08af3fbb975310800')+b;expected.append(f)
            (run/f'write{i}.hex').write_text(''.join(f'{int.from_bytes(f[n:n+16].ljust(16,bytes(1)),"little"):032x}\n'for n in range(0,len(f),16)))
            payload=data[v['offset']];(run/f'payload{i}.hex').write_text(''.join(f'{int.from_bytes(payload[n:n+64].ljust(64,bytes(1)),"little"):0128x}\n'for n in range(0,len(payload),64)))
        actual_sources=[run/'tb.v',run/'ack.v',run/'rq.v',*dict.fromkeys(run/'lfsr_constant_masks.v'if n.name=='lfsr.v'else n for n in sources)]
        cmd=['iverilog','-g2012','-s','tb','-o',str(ram/'test'),*map(str,actual_sources)]
        result['compile_command']=cmd;start=time.monotonic();c=subprocess.run(cmd,capture_output=True,text=True,timeout=10)
        (run/'compile.log').write_text(c.stdout+c.stderr);result['compile_seconds']=time.monotonic()-start
        if c.returncode:raise ValueError('connected WRITE compile failed')
        for mode in MODES:
            start=time.monotonic();c=subprocess.run(['vvp',str(ram/'test'),f'+MODE={mode}'],cwd=run,capture_output=True,text=True,timeout=10)
            (run/(str(mode)+'.log')).write_text(c.stdout+c.stderr);item=dict(exit=c.returncode,seconds=time.monotonic()-start);result['tests'][str(mode)]=item
            if c.returncode:raise ValueError('connected WRITE mode failed:'+str(mode))
            rows=[json.loads(s.split(' ',1)[1])for s in c.stdout.splitlines()if s.startswith('WRITE_MEMORY_RESULT ')]
            if len(rows)!=1 or not rows[0]['pass_test']:raise ValueError('missing complete actual assertions')
            item['summary']=rows[0]
            if mode in [0,1,2,5]:
                if ack_test.physical.frames(c.stdout)!=[(0x6001+i,f)for i,f in enumerate(expected)]:raise ValueError('every actual XGMII/FCS/SFD tag/ACK byte must match')
        if any(digest(ROOT/n)!=h for n,h in before.items()):raise ValueError('source changed during execution')
        result.update(pass_test=True,source_unchanged=True)
    except Exception as e:result.update(error_type=type(e).__name__,error=str(e));raise
    finally:
        result['artifact_sha256']={str(n.relative_to(ROOT)):digest(n)for n in run.iterdir()if n.is_file()}
        result['RAM_artifact_sha256']={str(n):digest(n)for n in ram.iterdir()if n.is_file()}
        with a.report.open('x')as f:f.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(pass_test=True,modes=len(result['tests']),maximum_seconds=max(v['seconds']for v in result['tests'].values()),actual_bytes=8193)),flush=True)


if __name__=='__main__':main()
