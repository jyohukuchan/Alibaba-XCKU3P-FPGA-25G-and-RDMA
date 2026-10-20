#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual SQ + paged payload + tag/RAM router + muxes + PCIe DMA/parent guard.

Only trusted config/authorized-command/payload source/root complex/host/link
are MODELS. No descriptor/status/RAM agent, internal force or parent-drain
constant. NOT protected network admission, local-WQE execution, kernel pins,
actual native parent/board, standard verbs/CQ or PCIe ordering signoff.
"""
import argparse
import ctypes as C
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import time

import probe_controlled_pcie as pcie
import test_wqe_codec as codec

ROOT=pcie.ROOT
RTL=ROOT/'rdma/rnic/rtl'
TOP=RTL/'rocev2_sq_paged_dma.v'
SOURCES=[TOP,*[RTL/(n+'.v')for n in ['rocev2_dma_client_router','rocev2_sq_dma_fetch','rocev2_sq_fetch',
    'rocev2_paged_memory_backend','rocev2_page_dma_engine','rocev2_mr_page_table','rocev2_corundum_dma_backend',
    'rocev2_pcie_parent_guard']],*pcie.PCIE_SOURCES]
SOURCES += [pcie.PCIE/(n+'.v')for n in ['dma_client_axis_sink','dma_client_axis_source','dma_psdpram']]
SOURCES += [ROOT/'external/corundum/fpga/lib/axis/rtl'/(n+'.v')for n in ['axis_register','arbiter','priority_encoder']]

HOST=r'''
reg [7:0] host[0:16511],posted[0:16511];reg posted_valid[0:16511];
reg [511:0] records[0:1];
integer cycle=0,descriptors=0,read_tlps=0,write_tlps=0,read_completions=0,fences=0;
integer restored_statuses=0,write_bytes=0,read_bytes=0,sq_results=0,peak_active=0,wr_seq_hold_cycles=0;
integer posted_count=0,i,lane,last_physical_tag=0;
integer engine_descriptors=0,engine_index;
reg descriptor_write[1:7],descriptor_bank[1:7],engine_seen[1:7];
reg [63:0] descriptor_address[1:7];
reg [14:0] descriptor_ram[1:7];reg [15:0] descriptor_length[1:7];
reg [15:0] client_tag[0:1];reg [1:0] saw_logical_one=0;
reg [31:0] rng=32'h455a1234;
reg rd_stalled=0,wr_stalled=0;reg [134:0] held_rd;reg [399:0] held_wr;
wire parent_guard_fault;wire [3:0] parent_guard_code;
assign parent_fault=parent_guard_fault;
rocev2_pcie_parent_guard parent_guard(
 .clk(clk),.rst(rst),.rd_busy(tlp_status_rd_busy),.wr_busy(tlp_status_wr_busy),
 .rd_desc_valid(eng_m_dma_read_valid),.rd_desc_ready(eng_m_dma_read_ready),
 .wr_desc_valid(eng_m_dma_write_valid),.wr_desc_ready(eng_m_dma_write_ready),
 .rd_status_valid(eng_s_dma_read_status_valid),.rd_status_error(eng_s_dma_read_status_error),
 .wr_status_valid(eng_s_dma_write_status_valid),.wr_status_error(eng_s_dma_write_status_error),
 .ram_wr_cmd_valid(eng_dma_ram_wr_cmd_valid),.ram_wr_cmd_ready(eng_dma_ram_wr_cmd_ready),.ram_wr_done(eng_dma_ram_wr_done),
 .ram_rd_cmd_valid(eng_dma_ram_rd_cmd_valid),.ram_rd_cmd_ready(eng_dma_ram_rd_cmd_ready),
 .ram_rd_resp_valid(eng_dma_ram_rd_resp_valid),.ram_rd_resp_ready(eng_dma_ram_rd_resp_ready),
 .tlp_activity(tlp_tx_rd_req_tlp_valid || tlp_tx_wr_req_tlp_valid || tlp_rx_cpl_tlp_valid ||
  tlp_s_axis_rd_req_tx_seq_num_valid || tlp_s_axis_wr_req_tx_seq_num_valid),
 .error_event(tlp_status_error_cor || tlp_status_error_uncor),.drained(parent_dma_drained),
 .fault(parent_guard_fault),.fault_code(parent_guard_code));
function [63:0] page;
 input integer n;
 begin case(n)0:page=64'h8123456789abc000;1:page=64'hfffffffffffff000;2:page=64'h12345000;default:page=0;endcase end
endfunction
function integer host_index;
 input [63:0] address;integer p;
 begin
  host_index=-1;
  for(p=0;p<3;p=p+1)if(address[63:12]==(page(p)>>12))host_index=p*4096+address[11:0];
  if(address>=64'hfedcba9876543000 && address<64'hfedcba9876543080)host_index=16384+address-64'hfedcba9876543000;
  if(host_index<0)$fatal(1,"DMA outside exact mapped pages/ring: %h",address);
 end
endfunction
function [7:0] payload;
 input integer n;
 begin payload=(n*179)^(n>>7)^8'h93;end
endfunction
task check_request;
 input [127:0] h;input write_op;
 begin
  if(h[127:125]!==(write_op ? 3'b011:3'b001) || h[124:120]!=0 || h[119:106]!=0 || h[95:80]!==16'h8200 || h[1:0]!=0)
   $fatal(1,"DMA64/requester/TC0/attr0 changed");
 end
endtask
always @(negedge clk)if(!rst)begin
 rng={rng[30:0],rng[31]^rng[21]^rng[1]^rng[0]};data_m_axis_read_tready=rng[2:0]!=0;
end
always @(posedge clk)if(!rst)begin
 cycle=cycle+1;if(cycle>30000)$fatal(1,"shared DMA deadline desc=%d SQ=%d data=%d",descriptors,sq_results,read_bytes);
 if(fault || parent_fault)$fatal(1,"shared/parent fault %h parent=%h router=%h",fault_code,parent_guard_code,router_fault_code);
 if(router_client_busy==3)peak_active=2;else if(router_client_busy!=0 && peak_active<1)peak_active=1;
 if(dut.data_m_dma_read_valid && dut.data_m_dma_read_ready)begin client_tag[0]=dut.data_m_dma_read_tag;if(client_tag[0]==1)saw_logical_one[0]=1;end
 if(dut.data_m_dma_write_valid && dut.data_m_dma_write_ready)begin client_tag[0]=dut.data_m_dma_write_tag;if(client_tag[0]==1)saw_logical_one[0]=1;end
 if(dut.sq_m_dma_read_valid && dut.sq_m_dma_read_ready)begin client_tag[1]=dut.sq_m_dma_read_tag;if(client_tag[1]==1)saw_logical_one[1]=1;end
 if(dut.sq_m_dma_write_valid)$fatal(1,"SQ issued host WRITE");
 if((m_dma_read_valid&&m_dma_read_ready)||(m_dma_write_valid&&m_dma_write_ready))begin
  if(m_dma_read_valid&&m_dma_read_ready && m_dma_write_valid&&m_dma_write_ready)$fatal(1,"two shared physical descriptor slots");
  if((m_dma_write_valid ? m_dma_write_tag:m_dma_read_tag)!==last_physical_tag+1)$fatal(1,"physical tag reuse/truncation");
  last_physical_tag=last_physical_tag+1;descriptors=descriptors+1;
  if(last_physical_tag>7)$fatal(1,"extra physical descriptor");
  descriptor_write[last_physical_tag]=m_dma_write_valid;
  descriptor_bank[last_physical_tag]=m_dma_write_valid ? m_dma_write_ram_sel:m_dma_read_ram_sel;
  descriptor_address[last_physical_tag]=m_dma_write_valid ? m_dma_write_address:m_dma_read_address;
  descriptor_ram[last_physical_tag]=m_dma_write_valid ? m_dma_write_ram_address:m_dma_read_ram_address;
  descriptor_length[last_physical_tag]=m_dma_write_valid ? m_dma_write_length:m_dma_read_length;
  $display("SHARED_DESCRIPTOR %0d %0d %0d %h %0d",m_dma_write_valid,
   m_dma_write_valid ? m_dma_write_ram_sel:m_dma_read_ram_sel,last_physical_tag,
   m_dma_write_valid ? m_dma_write_address:m_dma_read_address,m_dma_write_valid ? m_dma_write_length:m_dma_read_length);
 end
 if(dut.data_s_dma_read_status_valid)begin if(dut.data_s_dma_read_status_tag!==client_tag[0] || dut.data_s_dma_read_status_error)$fatal(1,"data read logical status corrupted");restored_statuses=restored_statuses+1;end
 if(dut.data_s_dma_write_status_valid)begin if(dut.data_s_dma_write_status_tag!==client_tag[0] || dut.data_s_dma_write_status_error)$fatal(1,"data write logical status corrupted");restored_statuses=restored_statuses+1;end
 if(dut.sq_s_dma_read_status_valid)begin if(dut.sq_s_dma_read_status_tag!==client_tag[1] || dut.sq_s_dma_read_status_error)$fatal(1,"SQ logical status corrupted");restored_statuses=restored_statuses+1;end
 if(eng_m_dma_read_valid&&eng_m_dma_read_ready)begin
  engine_index=eng_m_dma_read_tag[15:0];
  if((^eng_m_dma_read_tag)===1'bx || eng_m_dma_read_tag[18:16]!==3'b110 ||
    engine_index<1 || engine_index>last_physical_tag || engine_index>7)$fatal(1,"unissued native read19-bit tag");
  if(engine_seen[engine_index]!==0 || descriptor_write[engine_index]!==0 ||
    eng_m_dma_read_ram_sel!=={3'b110,descriptor_bank[engine_index]} ||
    eng_m_dma_read_address!==descriptor_address[engine_index] ||
    eng_m_dma_read_ram_address!==descriptor_ram[engine_index] ||
    eng_m_dma_read_length!==descriptor_length[engine_index])$fatal(1,"native read19-bit mux/RAM descriptor changed");
  engine_seen[engine_index]=1;engine_descriptors=engine_descriptors+1;
 end
 if(eng_m_dma_write_valid&&eng_m_dma_write_ready)begin
  engine_index=eng_m_dma_write_tag[15:0];
  if((^eng_m_dma_write_tag)===1'bx || eng_m_dma_write_tag[18:16]!==3'b110 ||
    engine_index<1 || engine_index>last_physical_tag || engine_index>7)$fatal(1,"unissued native write19-bit tag");
  if(engine_seen[engine_index]!==0 || descriptor_write[engine_index]!==1 ||
    eng_m_dma_write_ram_sel!=={3'b110,descriptor_bank[engine_index]} ||
    eng_m_dma_write_address!==descriptor_address[engine_index] ||
    eng_m_dma_write_ram_address!==descriptor_ram[engine_index] ||
    eng_m_dma_write_length!==descriptor_length[engine_index] || eng_m_dma_write_imm_en!==0)$fatal(1,"native write19-bit mux/RAM descriptor changed");
  engine_seen[engine_index]=1;engine_descriptors=engine_descriptors+1;
 end
 if(rd_stalled && (!tlp_tx_rd_req_tlp_valid || {tlp_tx_rd_req_tlp_hdr,tlp_tx_rd_req_tlp_seq,tlp_tx_rd_req_tlp_sop,tlp_tx_rd_req_tlp_eop}!==held_rd))$fatal(1,"read TLP stall ownership");
 if(wr_stalled && (!tlp_tx_wr_req_tlp_valid || {tlp_tx_wr_req_tlp_data,tlp_tx_wr_req_tlp_strb,tlp_tx_wr_req_tlp_hdr,tlp_tx_wr_req_tlp_seq,tlp_tx_wr_req_tlp_sop,tlp_tx_wr_req_tlp_eop}!==held_wr))$fatal(1,"write TLP stall ownership");
 rd_stalled=tlp_tx_rd_req_tlp_valid&&!tlp_tx_rd_req_tlp_ready;wr_stalled=tlp_tx_wr_req_tlp_valid&&!tlp_tx_wr_req_tlp_ready;
 held_rd={tlp_tx_rd_req_tlp_hdr,tlp_tx_rd_req_tlp_seq,tlp_tx_rd_req_tlp_sop,tlp_tx_rd_req_tlp_eop};
 held_wr={tlp_tx_wr_req_tlp_data,tlp_tx_wr_req_tlp_strb,tlp_tx_wr_req_tlp_hdr,tlp_tx_wr_req_tlp_seq,tlp_tx_wr_req_tlp_sop,tlp_tx_wr_req_tlp_eop};
 if(data_m_axis_read_tvalid&&data_m_axis_read_tready)begin
  if(data_m_axis_read_tkeep!==(read_bytes==0 ? 64'hffffffffffffffff:64'd1) || data_m_axis_read_tlast!==(read_bytes!=0))$fatal(1,"shared READ keep/last");
  for(lane=0;lane<64;lane=lane+1)if(data_m_axis_read_tkeep[lane])begin
   if(data_m_axis_read_tdata[lane*8+:8]!==payload(read_bytes))$fatal(1,"shared READ byte mismatch %d",read_bytes);
   read_bytes=read_bytes+1;
  end
 end
end
initial begin: root_complex_write_model
 reg [127:0] h;reg [63:0] base;reg [4:0] seq;reg [3:0] be;
 integer words,offset,dw,b,idx;reg active;
 active=0;offset=0;repeat(20)@(negedge clk);
 forever begin
  @(negedge clk);tlp_tx_wr_req_tlp_ready=rng[8:6]!=0;
  @(posedge clk);
  if(tlp_tx_wr_req_tlp_valid&&tlp_tx_wr_req_tlp_ready)begin
   if(tlp_tx_wr_req_tlp_sop)begin
    if(active)$fatal(1,"overlapping posted TLP");h=tlp_tx_wr_req_tlp_hdr;check_request(h,1);
    base={h[63:2],2'b0};words=h[105:96];if(!words)words=1024;seq=tlp_tx_wr_req_tlp_seq;offset=0;active=1;write_tlps=write_tlps+1;
   end
   if(!active || tlp_tx_wr_req_tlp_seq!==seq)$fatal(1,"posted ownership");
   for(dw=0;dw<8;dw=dw+1)begin
    if(tlp_tx_wr_req_tlp_strb[dw]!==(offset+dw<words))$fatal(1,"posted dword strobe");
    if(offset+dw<words)begin
     be=offset+dw==0 ? h[67:64] : (offset+dw==words-1 ? h[71:68]:4'hf);
     for(b=0;b<4;b=b+1)if(be[b])begin
      idx=host_index(base+(offset+dw)*4+b);
      if(idx<4093 || idx>=4158 || tlp_tx_wr_req_tlp_data[(dw*4+b)*8+:8]!==payload(idx-4093))$fatal(1,"posted payload/range idx=%d",idx);
      posted[idx]=tlp_tx_wr_req_tlp_data[(dw*4+b)*8+:8];posted_valid[idx]=1;posted_count=posted_count+1;write_bytes=write_bytes+1;
     end
    end
   end
   offset=offset+8;if(tlp_tx_wr_req_tlp_eop!==(offset>=words))$fatal(1,"posted EOP");
   if(tlp_tx_wr_req_tlp_eop)begin
    active=0;@(negedge clk);tlp_tx_wr_req_tlp_ready=0;
    repeat(64)begin @(negedge clk);wr_seq_hold_cycles=wr_seq_hold_cycles+1;end
    tlp_s_axis_wr_req_tx_seq_num=seq;tlp_s_axis_wr_req_tx_seq_num_valid=1;
    @(negedge clk);tlp_s_axis_wr_req_tx_seq_num_valid=0;
   end
  end
 end
end
initial begin: root_complex_read_model
 reg [127:0] h,cpl;reg [63:0] base,first_address;reg [4:0] seq;
 integer words,position,b,dw,first_lane,bytes_count,idx,n;
 repeat(20)@(negedge clk);
 forever begin
  while(!tlp_tx_rd_req_tlp_valid)@(negedge clk);
  h=tlp_tx_rd_req_tlp_hdr;seq=tlp_tx_rd_req_tlp_seq;check_request(h,0);
  repeat(9)begin @(negedge clk);if(!tlp_tx_rd_req_tlp_valid || tlp_tx_rd_req_tlp_hdr!==h)$fatal(1,"held read TLP changed");end
  tlp_tx_rd_req_tlp_ready=1;@(posedge clk);if(!tlp_tx_rd_req_tlp_sop || !tlp_tx_rd_req_tlp_eop)$fatal(1,"read TLP framing");
  @(negedge clk);tlp_tx_rd_req_tlp_ready=0;read_tlps=read_tlps+1;
  words=h[105:96];if(!words)words=1024;base={h[63:2],2'b0};first_lane=0;
  while(first_lane<4 && !h[64+first_lane])first_lane=first_lane+1;if(first_lane==4)$fatal(1,"zero-length read");
  first_address=base+first_lane;bytes_count=0;
  for(dw=0;dw<words;dw=dw+1)for(b=0;b<4;b=b+1)if(dw==0 ? h[64+b]:(dw==words-1 ? h[68+b]:1'b1))bytes_count=bytes_count+1;
  if(first_address>=64'hfedcba9876543000 && first_address<64'hfedcba9876543080)begin
   repeat(250)begin @(negedge clk);if(parent_dma_drained)$fatal(1,"real parent drain while SQ read pending");end
  end else repeat(17)@(negedge clk);
  tlp_s_axis_rd_req_tx_seq_num=seq;tlp_s_axis_rd_req_tx_seq_num_valid=1;
  @(negedge clk);tlp_s_axis_rd_req_tx_seq_num_valid=0;
  // Explicit ordinary same-requester/TC attr0 MODEL ordering. Any later
  // ordered read makes previous posted writes visible before completion.
  for(n=0;n<16512;n=n+1)if(posted_valid[n])begin host[n]=posted[n];posted_valid[n]=0;end
  posted_count=0;
  if(bytes_count==1 && first_address==64'h8123456789abcffd)fences=fences+1;
  cpl=0;cpl[127:125]=3'b010;cpl[124:120]=5'b01010;cpl[105:96]=words;
  cpl[95:80]=16'h0100;cpl[75:64]=bytes_count;cpl[63:48]=h[95:80];cpl[47:40]=h[79:72];cpl[38:32]=first_address[6:0];
  for(position=0;position<words*4;position=position+32)begin
   repeat(3)@(negedge clk);tlp_rx_cpl_tlp_data=0;tlp_rx_cpl_tlp_hdr=cpl;
   for(b=0;b<32;b=b+1)if(position+b<words*4)tlp_rx_cpl_tlp_data[b*8+:8]=host[host_index(base+position+b)];
   tlp_rx_cpl_tlp_sop=position==0;tlp_rx_cpl_tlp_eop=position+32>=words*4;tlp_rx_cpl_tlp_valid=1;
   @(posedge clk);while(!tlp_rx_cpl_tlp_ready)@(posedge clk);
   @(negedge clk);tlp_rx_cpl_tlp_valid=0;
  end
  read_completions=read_completions+1;
 end
end
'''

DRIVERS=r'''
task page_config;
 input integer op,index;
 begin
  @(negedge clk);data_cfg_command=op;data_cfg_slot=3;data_cfg_key=11;data_cfg_length=8192;data_cfg_first_offset=4093;
  data_cfg_page_index=index;data_cfg_dma_page=page(index);data_cfg_valid=1;
  @(posedge clk);while(!data_cfg_ready)@(posedge clk);
  @(negedge clk);data_cfg_valid=0;while(!data_cfg_response_valid)@(negedge clk);
  if(data_cfg_response_error || data_cfg_response_key!==11)$fatal(1,"PTE configuration");
  data_cfg_response_ready=1;@(posedge clk);@(negedge clk);data_cfg_response_ready=0;
 end
endtask
task queue_config;
 input [1:0] op;input [63:0] producer;
 begin
  @(negedge clk);sq_cfg_command=op;sq_cfg_qpn=0;sq_cfg_pd=17;sq_cfg_epoch=64'h9123456700000001;
  sq_cfg_dma_base=64'hfedcba9876543000;sq_cfg_log_depth=1;sq_cfg_producer=producer;sq_cfg_valid=1;
  @(posedge clk);while(!sq_cfg_ready)@(posedge clk);
  @(negedge clk);sq_cfg_valid=0;while(!sq_cfg_response_valid)@(negedge clk);
  if(sq_cfg_response_error)$fatal(1,"SQ configuration %d",sq_cfg_response_error);
  sq_cfg_response_ready=1;@(posedge clk);@(negedge clk);sq_cfg_response_ready=0;
 end
endtask
task data_command;
 input write_op;input [15:0] tag;
 begin
  @(negedge clk);data_cfg_quiescent=0;data_s_command_key=11;data_s_command_write=write_op;
  data_s_command_offset=0;data_s_command_length=65;data_s_command_tag=tag;data_s_command_valid=1;
  @(posedge clk);while(!data_s_command_ready)@(posedge clk);
  @(negedge clk);data_s_command_valid=0;
 end
endtask
task send_payload;
 integer pos,b;
 begin
  for(pos=0;pos<65;pos=pos+64)begin
   @(negedge clk);data_s_axis_write_tdata=0;data_s_axis_write_tkeep=pos==0 ? 64'hffffffffffffffff:64'd1;
   data_s_axis_write_tlast=pos!=0;
   for(b=0;b<64;b=b+1)if(pos+b<65)data_s_axis_write_tdata[b*8+:8]=payload(pos+b);
   data_s_axis_write_tvalid=1;@(posedge clk);while(!data_s_axis_write_tready)@(posedge clk);
  end
  @(negedge clk);data_s_axis_write_tvalid=0;
 end
endtask
task data_status;
 input [15:0] tag;
 begin
  while(!data_m_status_valid)@(negedge clk);
  if(data_m_status_error || data_m_status_tag!==tag)$fatal(1,"data operation status");
  data_m_status_ready=1;@(posedge clk);@(negedge clk);data_m_status_ready=0;
 end
endtask
task take_SQ;
 input integer index;
 begin
  while(!sq_m_result_valid)@(negedge clk);
  if(sq_m_result_error || sq_m_result_data!==records[index] || sq_m_result_qpn!==0 || sq_m_result_pd!==17 ||
    sq_m_result_epoch!==64'h9123456700000001 || sq_m_result_sequence!==index+1 || !sq_queue_guard[0])$fatal(1,"shared SQ bytes/context");
  repeat(13)begin @(negedge clk);if(!sq_m_result_valid || sq_m_result_data!==records[index] || !sq_busy)$fatal(1,"SQ held result owner");end
  sq_m_result_ready=1;@(posedge clk);@(negedge clk);sq_m_result_ready=0;sq_results=sq_results+1;
 end
endtask
initial begin
 rst=0;repeat(2)@(negedge clk);rst=1;$readmemh("records.hex",records);
 for(i=1;i<=7;i=i+1)engine_seen[i]=0;
 for(i=0;i<16512;i=i+1)begin host[i]=(i*37)^8'h5a;posted_valid[i]=0;end
 for(i=0;i<128;i=i+1)host[16384+i]=records[i/64][(i%64)*8+:8];
 repeat(8)@(negedge clk);rst=0;enable=1;data_cfg_quiescent=1;repeat(40)@(negedge clk);
 page_config(1,0);page_config(2,0);page_config(2,1);page_config(2,2);page_config(3,0);
 queue_config(1,0);
 fork
  begin data_command(1,16'h8001);send_payload();end
  begin queue_config(2,2);end
 join
 data_status(16'h8001);if(write_bytes!=65 || fences!=1)$fatal(1,"WRITE status before full split/fence");
 take_SQ(0);
 fork
  begin data_command(0,16'hffff);data_status(16'hffff);end
  begin take_SQ(1);end
 join
 repeat(50)@(negedge clk);
 if(!dma_drained || !parent_dma_drained || fault || parent_fault || peak_active!=2 || saw_logical_one!==3 ||
   descriptors!=7 || engine_descriptors!=7 || restored_statuses!=7 || router_descriptor_count!=7 || router_completion_count!=7 ||
   read_tlps!=5 || write_tlps!=2 || read_completions!=5 || read_bytes!=65 || write_bytes!=65 || sq_results!=2 ||
   sq_fetch_count!=2 || sq_result_count!=2 || data_command_count!=2 || data_fence_count!=1 || wr_seq_hold_cycles!=128 || posted_count)
  $fatal(1,"shared actual-path coverage/drain desc=%d statuses=%d rd/wr=%d/%d bytes=%d/%d overlap=%d",descriptors,restored_statuses,read_tlps,write_tlps,read_bytes,write_bytes,peak_active);
 for(i=0;i<16384;i=i+1)if(posted_valid[i] || host[i]!==((i>=4093 && i<4158) ? payload(i-4093):(((i*37)^8'h5a)&255)))$fatal(1,"host payload/sentinel%0d",i);
 for(i=0;i<128;i=i+1)if(host[16384+i]!==records[i/64][(i%64)*8+:8])$fatal(1,"SQ ring unexpectedly modified");
 $display("SHARED_PCIE_RESULT {\"pass_test\":true,\"descriptors\":%0d,\"restored_statuses\":%0d,\"read_tlps\":%0d,\"write_tlps\":%0d,\"write_bytes\":%0d,\"read_bytes\":%0d,\"SQ_records\":%0d,\"peak_active_clients\":%0d,\"write_tx_seq_hold_cycles\":%0d,\"cycles\":%0d}",descriptors,restored_statuses,read_tlps,write_tlps,write_bytes,read_bytes,sq_results,peak_active,wr_seq_hold_cycles,cycle);
 $finish;
end
'''


def bench():
    params=dict(MAX_QPS=8,RAM_SIZE=8192,RAM_ADDR_WIDTH=15,SEG_COUNT=2,SEG_DATA_WIDTH=256,
                SEG_BE_WIDTH=32,SEG_ADDR_WIDTH=9,DMA_LEN_WIDTH=16,TAG_WIDTH=16)
    driven={'parent_dma_drained','parent_fault','m_dma_read_ready','m_dma_write_ready'}
    driven.update('s_dma_'+d+'_status_'+f for d in ['read','write']for f in ['tag','error','valid'])
    driven.update('dma_ram_'+f for f in ['wr_cmd_sel','wr_cmd_be','wr_cmd_addr','wr_cmd_data','wr_cmd_valid',
                                      'rd_cmd_sel','rd_cmd_addr','rd_cmd_valid','rd_resp_ready'])
    declarations=[pcie.declaration(n,pcie.width(e,params),'reg'if d=='input'and n not in driven else'wire')for d,e,n in pcie.ports(TOP)]
    graph=pcie.bundle('mid_',18,3)+'\n'+pcie.bundle('eng_',19,4)+'\n'
    graph+=pcie.mux('interface_mux','','mid_',3,2,16,18,1,3)
    graph+=pcie.mux('control_data_mux','mid_','eng_',2,1,18,19,3,4)+pcie.engine()
    return '`timescale 1ns/1ps\nmodule tb;\n'+'\n'.join(declarations)+'\nrocev2_sq_paged_dma dut(.*);\nalways #2 clk=~clk;\n'+graph+HOST+DRIVERS+'\nendmodule\n'


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--report',type=Path,required=True);args=parser.parse_args()
    if args.report.exists():parser.error('preserve prior evidence')
    own=[Path(__file__).resolve(),Path(pcie.__file__).resolve(),Path(codec.__file__).resolve(),codec.KERNEL/'wqe.c',codec.KERNEL/'wqe.h']
    before={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in SOURCES+own}
    build=ROOT/'rdma/rnic/build';build.mkdir(exist_ok=True,parents=True)
    run=Path(tempfile.mkdtemp(prefix='sq-paged-pcie-',dir=build))
    c=subprocess.run(['cc','-std=c11','-O2','-Wall','-Wextra','-Werror','-shared','-fPIC','-fsanitize=undefined',
        '-fno-sanitize-recover=undefined','-I',str(codec.KERNEL),str(codec.KERNEL/'wqe.c'),'-o',str(run/'wqe.so')],capture_output=True,text=True,timeout=30)
    if c.returncode:raise RuntimeError(c.stdout+c.stderr)
    lib=C.CDLL(str(run/'wqe.so'));lib.as02_wqe_encode.argtypes=[C.POINTER(C.c_uint8),C.POINTER(codec.WQE)]
    records=[]
    for i in range(2):
        w=codec.candidate(wr_id=0xf123456789abc000+i,sequence=i+1,epoch=0x9123456700000001,
                          local_address=0xfedcba9876543000+i*64,remote_key=0xffffffff if i else 0,opcode=i+1)
        out=(C.c_uint8*64)();assert lib.as02_wqe_encode(out,C.byref(w))==0 and bytes(out)==codec.oracle(w);records.append(bytes(out))
    (run/'records.hex').write_text(''.join(f'{int.from_bytes(r,"little"):0128x}\n'for r in records));(run/'tb.v').write_text(bench())
    command=['iverilog','-g2012','-s','tb','-o',str(run/'test.vvp'),str(run/'tb.v'),*map(str,SOURCES)]
    report=dict(scope=__doc__,pass_test=False,terminal_exit_status=None,directory=str(run.relative_to(ROOT)),source_sha256=before,
        compiler_command=command,bench_sha256=hashlib.sha256((run/'tb.v').read_bytes()).hexdigest(),
        records_sha256=hashlib.sha256((run/'records.hex').read_bytes()).hexdigest(),compile_timeout_seconds=60,simulation_timeout_seconds=60,
        hardware_verified=False,actual_native_parent_or_board=False,actual_router_paged_SQ_RAM_mux_PCIe_and_parent_guard=True,
        constant_parent_drained_used=False,descriptor_status_RAM_agents_used=False,protected_network_admission_verified=False,
        local_WQE_execution_or_CQ_or_standard_verbs_verified=False,real_kernel_pins_or_coherent_allocation=False)
    started=time.monotonic()
    try:
        c=subprocess.run(command,capture_output=True,text=True,timeout=60);(run/'compile.log').write_text(c.stdout+c.stderr)
        if c.returncode:raise RuntimeError(c.stdout+c.stderr)
        s=subprocess.run(['vvp',str(run/'test.vvp')],cwd=run,capture_output=True,text=True,timeout=60)
        (run/'simulation.log').write_text(s.stdout+s.stderr);print(s.stdout+s.stderr,flush=True)
        if s.returncode or 'ERROR:'in s.stdout+s.stderr:raise RuntimeError('actual shared DMA PCIe simulation failed')
        rows=[json.loads(l[19:])for l in s.stdout.splitlines()if l.startswith('SHARED_PCIE_RESULT ')]
        if len(rows)!=1 or not rows[0]['pass_test']:raise ValueError('missing shared DMA summary')
        if before!={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest()for n in before}:raise ValueError('sources changed during execution')
        report.update(pass_test=True,terminal_exit_status=0,summary=rows[0],source_sha256_before_after_equal=True,
            SQ_descriptor_bytes_verified=128,payload_WRITE_bytes_verified=65,payload_READ_bytes_verified=65,
            host_sentinel_bytes_verified=16384-65,coherent_ring_unchanged_bytes_verified=128)
    except Exception as e:report.update(terminal_exit_status=1,error_type=type(e).__name__,error=str(e));raise
    finally:
        report['elapsed_seconds']=time.monotonic()-started
        with args.report.open('x')as f:json.dump(report,f,indent=2);f.write('\n')


if __name__=='__main__':main()
