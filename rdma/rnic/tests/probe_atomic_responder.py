#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Candidate wire Atomic -> real MR -> exclusive arbiter -> paged RAM/DMA.

Physical descriptor engine, host storage and visibility ordering are MODELS.
Integrity/peer admission is an explicit upstream contract, NOT exercised here.
This is not native/shared-HLS QP integration, requester, standard verbs, timing
or physical atomicity evidence. All simulations <=30s; no device is opened.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
import tempfile
import time

import test_paged_memory_backend_rtl as paged

ROOT=paged.ROOT
RTL=ROOT/'rdma/rnic/rtl'
ATOMIC=RTL/'rocev2_atomic_responder.v'
BRIDGE=RTL/'rocev2_atomic_memory_bridge.v'
SOURCES=[ATOMIC,BRIDGE,RTL/'rocev2_memory_client_arbiter.v',RTL/'rocev2_mr_table.v',*paged.SOURCES]


def ports(path):
    # Supports grouped scalar declarations, preserving checked numeric widths.
    header=path.read_text().split('\n);',1)[0].split(')(\n',1)[-1]
    if ')(\n' not in path.read_text().split('\n);',1)[0]:
        header=header.split('module '+path.stem+' (',1)[1]
    return re.findall(r'\b(input|output)\s+(?:wire|reg)\s+(\[[^]]+\]\s+)?(\w+)(?:=0)?',header)


def instance(path,name,prefix,mapping):
    decl=[];conn=[]
    for direction,width,port in ports(path):
        signal=mapping.get(port,prefix+port)
        conn.append(f'.{port}({signal})')
        if port not in mapping:
            decl.append(('reg 'if direction=='input'else'wire ')+(width or '')+signal+
                        ('=0;'if direction=='input'else';'))
    return '\n'.join(decl)+'\n'+path.stem+' '+name+'('+','.join(conn)+');\n'


def bench():
    a=instance(ATOMIC,'atomic','a_',dict(clk='clk',rst='rst',enable='enable',
        cfg_quiescent='quiet',memory_lock_granted='lock_granted'))
    mrmap=dict(clk='clk',rst='rst',cfg_quiescent='quiet',
        s_request_pd='a_m_mr_pd',s_request_key='a_m_mr_key',s_request_address='a_m_mr_address',
        s_request_length='a_m_mr_length',s_request_operation='a_m_mr_operation',
        s_request_tag='a_m_mr_tag',s_request_valid='a_m_mr_valid',s_request_ready='a_m_mr_ready',
        m_response_tag='a_s_mr_tag',m_response_error='a_s_mr_error',
        m_response_offset='a_s_mr_offset',m_response_length='a_s_mr_length',
        m_response_valid='a_s_mr_valid',m_response_ready='a_s_mr_ready')
    # These connections are wires driven by the actual connected modules,
    # not the default stimulus regs emitted by the generic declaration helper.
    for n in ['memory_lock_granted','m_mr_ready','s_mr_tag','s_mr_error','s_mr_offset',
              's_mr_length','s_mr_valid','m_memory_ready','m_axis_write_tready',
              's_axis_read_tdata','s_axis_read_tkeep','s_axis_read_tlast','s_axis_read_tvalid',
              's_memory_status_tag','s_memory_status_error','s_memory_status_valid']:
        a=re.sub(r'reg (\[[^]]+\]\s+)?a_'+n+r'=0;',lambda m:'wire '+(m[1]or'')+'a_'+n+';',a)
    bmap=dict(clk='clk',rst='rst',enable="1'b1",atomic_lock_request='a_memory_lock_request',
        atomic_lock_granted='lock_granted')
    bridge=instance(BRIDGE,'bridge','b_',bmap)
    # Drive both client vectors by explicit concatenations; client0 is a
    # continuously offerable competing normal memory client, client1 atomic.
    for port,expression in dict(
        s_command_write="{a_m_memory_write,1'b0}",
        s_command_offset="{a_m_memory_offset,64'd0}",
        s_command_length="{a_m_memory_length,32'd8}",
        s_command_key="{a_m_memory_key,32'd8}",
        s_command_tag="{a_m_memory_tag,16'hf123}",
        s_command_valid='{a_m_memory_valid,competitor}',
        s_axis_write_tdata="{a_m_axis_write_tdata,512'd0}",
        s_axis_write_tkeep="{a_m_axis_write_tkeep,64'd0}",
        s_axis_write_tlast="{a_m_axis_write_tlast,1'b0}",
        s_axis_write_tvalid="{a_m_axis_write_tvalid,1'b0}",
        m_axis_read_tready="{a_s_axis_read_tready,1'b1}",
        m_status_ready="{a_s_memory_status_ready,1'b1}").items():
        bridge=re.sub(r'reg (\[[^]]+\]\s+)?b_'+port+r'=0;',
            lambda m:'wire '+(m[1]or'')+'b_'+port+'='+expression+';',bridge)
    backmap=dict(clk='clk',rst='rst',enable="1'b1",cfg_quiescent='quiet')
    for n in ['command_write','command_offset','command_length','command_key','command_tag','command_valid']:
        backmap['s_'+n]='b_m_'+n
    backmap['s_command_ready']='b_m_command_ready'
    for n in ['tdata','tkeep','tlast','tvalid']:backmap['s_axis_write_'+n]='b_m_axis_write_'+n
    backmap['s_axis_write_tready']='b_m_axis_write_tready'
    for n in ['tdata','tkeep','tlast','tvalid']:backmap['m_axis_read_'+n]='b_s_axis_read_'+n
    backmap['m_axis_read_tready']='b_s_axis_read_tready'
    for n in ['tag','error','valid']:backmap['m_status_'+n]='b_s_status_'+n
    backmap['m_status_ready']='b_s_status_ready'
    for n in ['m_command_ready','m_axis_write_tready','s_axis_read_tdata','s_axis_read_tkeep',
              's_axis_read_tlast','s_axis_read_tvalid','s_status_tag','s_status_error','s_status_valid']:
        bridge=re.sub(r'reg (\[[^]]+\]\s+)?b_'+n+r'=0;',lambda m:'wire '+(m[1]or'')+'b_'+n+';',bridge)
    backend=instance(paged.RTL,'backend','',backmap)
    # Reuse existing physical/RAM model tasks, not the existing operation or
    # expected result oracle. Compare all old/new values independently below.
    tasks='task fill_ram;'+paged.TB.split('task fill_ram;',1)[1].split('task physical_status;',1)[0]
    tasks=tasks.replace('if(dma_ram_rd_resp_data[b*8+:8]!==pattern(q)) $fatal(1,"WRITE staging payload pos=%d",q);','')
    functions='function [63:0] dma_page;'+paged.TB.split('function [63:0] dma_page;',1)[1].split('function [63:0] expected_dma;',1)[0]
    return HEADER+a+instance(RTL/'rocev2_mr_table.v','mr','mr_',mrmap)+bridge+backend+ALIASES+functions+tasks+BODY


HEADER=r'''
`timescale 1ns/1ps
module tb;
localparam MAX_QPS=8,ENTRY_COUNT=8,INDEX_WIDTH=3;
localparam RAM_SIZE=8192,RAM_ADDR_WIDTH=15,SEG_COUNT=2,SEG_DATA_WIDTH=256,SEG_BE_WIDTH=32,
 SEG_ADDR_WIDTH=9,RAM_SEL_WIDTH=4,DMA_LEN_WIDTH=16,TAG_WIDTH=16;
reg clk=0,rst=0,enable=0,competitor=0;
wire lock_granted,quiet;
always #2 clk=~clk;
reg [7:0] host[0:16383],posted[0:16383];reg posted_valid[0:16383];
integer cycles=0,scenario=0,dummy,k,seg,base_index,ram_start,issued_len,issued_tag;
integer physical_reads=0,physical_writes=0,write_bytes=0,commands=0,fences=0;
integer fail_read=0,fail_write=0,fail_fence=0,wrong_read_tag=0;
integer normal_accepted=0,atomic_read_done=0;
reg [63:0] issued_address=0;reg [1:0] mask=0;
reg service_enabled=1,request_ackbit=1;
'''

ALIASES=r'''
assign quiet=!a_configuration_guard && !b_configuration_guard && idle && !fault;
assign a_m_memory_ready=b_s_command_ready[1];
assign a_m_axis_write_tready=b_s_axis_write_tready[1];
assign a_s_axis_read_tdata=b_m_axis_read_tdata[1023:512];
assign a_s_axis_read_tkeep=b_m_axis_read_tkeep[127:64];
assign a_s_axis_read_tlast=b_m_axis_read_tlast[1];
assign a_s_axis_read_tvalid=b_m_axis_read_tvalid[1];
assign a_s_memory_status_tag=b_m_status_tag[31:16];
assign a_s_memory_status_error=b_m_status_error[15:8];
assign a_s_memory_status_valid=b_m_status_valid[1];
reg stalled=0;reg [285:0] saved_response;
always @(posedge clk)if(!rst)begin
 cycles=cycles+1;if(cycles>30000)$fatal(1,"bounded cycle deadline state=%d fault=%h/%h",atomic.state,a_fault_code,fault_code);
 if(stalled && (!a_m_response_valid || {a_m_response_header,a_m_response_bytes,a_m_response_qpn,a_m_response_epoch}!==saved_response))$fatal(1,"ACK lost under backpressure");
 stalled=a_m_response_valid&&!a_m_response_ready;
 saved_response={a_m_response_header,a_m_response_bytes,a_m_response_qpn,a_m_response_epoch};
 if(a_configuration_guard && (mr_cfg_ready || cfg_ready))$fatal(1,"MR/PTE mutation escaped lifetime");
 if(b_s_command_valid[0] && b_s_command_ready[0])normal_accepted=normal_accepted+1;
 if(a_memory_lock_request && b_s_command_ready[0])$fatal(1,"normal DMA entered atomic reservation");
 if(b_m_command_valid && b_m_command_ready)commands=commands+1;
 if(b_m_status_valid[1] && b_m_status_ready[1] && !b_m_command_write)atomic_read_done=atomic_read_done+1;
end
'''

BODY=r'''
function [63:0] load64;input integer n;integer i;begin for(i=0;i<8;i=i+1)load64[i*8+:8]=host[n+i];end endfunction
task store64;input integer n;input [63:0] value;integer i;begin for(i=0;i<8;i=i+1)host[n+i]=value[i*8+:8];end endtask
function [23:0] be24;input [23:0] v;begin be24={v[7:0],v[15:8],v[23:16]};end endfunction
function [31:0] be32;input [31:0] v;begin be32={v[7:0],v[15:8],v[23:16],v[31:24]};end endfunction
function [63:0] be64;input [63:0] v;integer i;begin for(i=0;i<8;i=i+1)be64[i*8+:8]=v[(7-i)*8+:8];end endfunction
task configure_qp;
 input integer q;input [63:0] epoch;input [15:0] pd;input [23:0] psn;
 begin
  @(negedge clk);a_cfg_qpn=q;a_cfg_peer_qpn=24'hf12345+q;a_cfg_pd=pd;
  a_cfg_epoch=epoch;a_cfg_psn=psn;a_cfg_msn=24'hfffffe;a_cfg_valid=1;
  @(posedge clk);while(!a_cfg_ready)@(posedge clk);
  @(negedge clk);a_cfg_valid=0;
  while(!a_cfg_response_valid)@(negedge clk);
  if(a_cfg_error)$fatal(1,"QP config error %d",a_cfg_error);
  a_cfg_response_ready=1;@(negedge clk);a_cfg_response_ready=0;
 end
endtask
task configure_mr;
 input integer index;input [3:0] access;input [63:0] length;
 begin
  @(negedge clk);mr_cfg_command=1;mr_cfg_index=index;mr_cfg_pd=17;
  mr_cfg_virtual_address=64'hfedcba9876543005;mr_cfg_dma_address=dma_page(0)+5;
  mr_cfg_length=length;mr_cfg_access=access;mr_cfg_valid=1;
  @(posedge clk);while(!mr_cfg_ready)@(posedge clk);
  @(negedge clk);mr_cfg_valid=0;while(!mr_cfg_response_valid)@(negedge clk);
  if(mr_cfg_response_error || mr_cfg_response_key!==(8+index))$fatal(1,"MR config result");
  mr_cfg_response_ready=1;@(negedge clk);mr_cfg_response_ready=0;
 end
endtask
task configure_pages;
 input integer op,page;
 begin
  @(negedge clk);cfg_command=op;cfg_slot=0;cfg_key=8;cfg_length=8192;
  cfg_first_offset=5;cfg_page_index=page;cfg_dma_page=dma_page(page);cfg_valid=1;
  @(posedge clk);while(!cfg_ready)@(posedge clk);
  @(negedge clk);cfg_valid=0;while(!cfg_response_valid)@(negedge clk);
  if(cfg_response_error)$fatal(1,"PTE config result");
  cfg_response_ready=1;@(negedge clk);cfg_response_ready=0;
 end
endtask
task offer;
 input [7:0] op;input integer q;input [23:0] psn;input [63:0] epoch,address;
 input [31:0] key;input [63:0] operand,compare;
 begin
  @(negedge clk);a_s_request_header=0;
  a_s_request_header[7:0]=op;a_s_request_header[31:16]=16'hffff;
  a_s_request_header[63:40]=be24(q);a_s_request_header[71]=request_ackbit;
  a_s_request_header[95:72]=be24(psn);a_s_request_header[159:96]=be64(address);
  a_s_request_header[191:160]=be32(key);a_s_request_header[255:192]=be64(operand);
  a_s_request_header[319:256]=be64(compare);a_s_request_bytes=40;
  a_s_request_epoch=epoch;a_s_request_valid=1;
  @(posedge clk);while(!a_s_request_ready)@(posedge clk);
  @(negedge clk);a_s_request_valid=0;
 end
endtask
task ack;
 input integer q;input [23:0] psn,message;input [63:0] original;
 input [7:0] syndrome;
 reg [191:0] expected;
 begin
  while(!a_m_response_valid && !a_fault)@(negedge clk);
  if(a_fault)$fatal(1,"unexpected atomic fault %h",a_fault_code);
  expected=0;expected[7:0]=syndrome==8'h1f ? 8'h12:8'h11;
  expected[31:16]=16'hffff;expected[63:40]=be24(24'hf12345+q);
  expected[95:72]=be24(psn);expected[103:96]=syndrome;
  expected[127:104]=be24(message);expected[191:128]=syndrome==8'h1f ? be64(original):64'd0;
  if(a_m_response_header!==expected || a_m_response_bytes!==(syndrome==8'h1f ? 24:16) ||
    a_m_response_qpn!==q || a_m_response_epoch!==a_s_request_epoch)
    $fatal(1,"wire reply mismatch got=%h expected=%h",a_m_response_header,expected);
  $display("ATOMIC_REPLY %048h %0d %0d %06h %06h %016h %02h",a_m_response_header,a_m_response_bytes,q,psn,message,original,syndrome);
  repeat(13)@(negedge clk);
  a_m_response_ready=1;@(negedge clk);a_m_response_ready=0;
  repeat(4)@(negedge clk);
 end
endtask
task one;
 input [7:0] op;input integer q;input [23:0] psn,message;
 input [63:0] operand,compare,original,result;
 begin
  offer(op,q,psn,64'h9123456780000001,64'hfedcba9876544000,8,operand,compare);
  ack(q,psn,message,original,8'h1f);
  if(load64(4096)!==result)$fatal(1,"memory RMW result got=%h want=%h",load64(4096),result);
 end
endtask
// Physical descriptor/host MODEL; all bytes pass real public RAM ports.
initial begin
 wait(!rst && enable);
 forever begin
  @(negedge clk);
  if(service_enabled && (m_dma_read_valid || m_dma_write_valid))begin : serve
   reg wr,fence_op;integer error;
   wr=m_dma_write_valid;issued_address=wr ? m_dma_write_address:m_dma_read_address;
   issued_len=wr ? m_dma_write_length:m_dma_read_length;
   ram_start=wr ? m_dma_write_ram_address:m_dma_read_ram_address;
   issued_tag=wr ? m_dma_write_tag:m_dma_read_tag;fence_op=!wr && issued_len==1;
   if(host_index(issued_address)<0 || (issued_len!=8 && !fence_op) ||
      (wr ? m_dma_write_ram_sel:m_dma_read_ram_sel)!=0 || m_dma_write_imm_en)
    $fatal(1,"unbound physical descriptor");
   if(a_memory_lock_request && issued_len==8 && issued_address!==dma_page(1))
    $fatal(1,"full scattered-page DMA64 not retained %h",issued_address);
   repeat(7)begin @(negedge clk);if(a_m_response_valid)$fatal(1,"early AtomicACK");end
   if(wr)begin m_dma_write_ready=1;physical_writes=physical_writes+1;end
   else begin m_dma_read_ready=1;physical_reads=physical_reads+1;end
   @(negedge clk);m_dma_write_ready=0;m_dma_read_ready=0;
   error=wr ? fail_write:(fence_op ? fail_fence:fail_read);
   if(fence_op)begin
    fences=fences+1;
    repeat(29)begin @(negedge clk);if(a_m_response_valid)$fatal(1,"ACK before visibility fence");end
    if(!error)for(k=0;k<16384;k=k+1)if(posted_valid[k])begin host[k]=posted[k];posted_valid[k]=0;end
   end
   if(!error)begin if(wr)post_ram;else fill_ram;end
   repeat(7)@(negedge clk);
   if(wr)begin s_dma_write_status_tag=issued_tag;s_dma_write_status_error=error;s_dma_write_status_valid=1;end
   else begin s_dma_read_status_tag=issued_tag+wrong_read_tag;s_dma_read_status_error=error;s_dma_read_status_valid=1;end
   @(negedge clk);s_dma_read_status_valid=0;s_dma_write_status_valid=0;
  end
 end
end
integer before_cmd,before_exec,before_read,before_write;
initial begin
 #1 rst=1;dummy=$value$plusargs("case=%d",scenario);
 for(k=0;k<16384;k=k+1)begin host[k]=(k*37)^8'h5a;posted_valid[k]=0;end
 repeat(5)@(negedge clk);rst=0;
 configure_qp(0,64'h9123456780000001,17,24'hfffffe);
 configure_qp(1,64'h9123456780000001,17,24'h123456);
 configure_qp(2,64'h9123456780000001,18,24'h345678);
 configure_mr(0,9,8192);configure_mr(1,1,8192);configure_mr(2,9,4091);
 configure_pages(1,0);configure_pages(2,0);configure_pages(2,1);configure_pages(2,2);configure_pages(3,0);
 enable=1;store64(4096,64'hf123456789abcdef);
 case(scenario)
  0:begin
   one(8'h13,0,24'hfffffe,24'hffffff,64'h8123456789abcdef,64'hf123456789abcdef,64'hf123456789abcdef,64'h8123456789abcdef);
   before_cmd=commands;
   request_ackbit=0;
   one(8'h13,0,24'hfffffe,24'hffffff,64'h8123456789abcdef,64'hf123456789abcdef,64'hf123456789abcdef,64'h8123456789abcdef);
   request_ackbit=1;
   if(commands!=before_cmd || a_replay_count!=1)$fatal(1,"duplicate CAS re-executed");
   one(8'h13,0,24'hffffff,0,64'hffffffffffffffff,64'h0123456789abcdef,64'h8123456789abcdef,64'h8123456789abcdef);
   if(physical_writes!=1 || fences!=1)$fatal(1,"failed compare wrote memory");
   one(8'h14,0,0,1,64'h7edcba9876543211,0,64'h8123456789abcdef,0);
   one(8'h14,1,24'h123456,24'hffffff,64'hfedcba9876543210,0,0,64'hfedcba9876543210);
   before_cmd=commands;
   one(8'h14,1,24'h123456,24'hffffff,64'hfedcba9876543210,0,0,64'hfedcba9876543210);
   if(commands!=before_cmd || a_replay_count!=2 || a_executed_count!=4)$fatal(1,"FADD duplicate applied twice");
  end
  1:begin
   // Keep a normal client offered specifically between Atomic READ and WRITE.
   offer(8'h14,0,24'hfffffe,64'h9123456780000001,64'hfedcba9876544000,8,1,0);
   wait(atomic_read_done==1);@(negedge clk);competitor=1;
   ack(0,24'hfffffe,24'hffffff,64'hf123456789abcdef,8'h1f);
   // Reservation releases after ACK acceptance; normal client then proceeds.
   while(!normal_accepted)@(negedge clk);competitor=0;
   while(b_busy)@(negedge clk);
   if(load64(4096)!==64'hf123456789abcdf0 || normal_accepted!=1)$fatal(1,"atomic isolation/fair handoff");
  end
  2,3,4,5:begin
   before_cmd=commands;
   offer(8'h14,scenario==3 ? 2:0,scenario==3 ? 24'h345678:24'hfffffe,
    64'h9123456780000001,64'hfedcba9876544000,scenario==2 ? 9:scenario==4 ? 10:16,1,0);
   ack(scenario==3 ? 2:0,scenario==3 ? 24'h345678:24'hfffffe,24'hfffffe,0,8'h62);
   if(commands!=before_cmd || a_executed_count || load64(4096)!==64'hf123456789abcdef)$fatal(1,"permission/PD/range/key denial issued DMA");
  end
  6:begin
   offer(8'h14,0,24'hfffffe,64'h9123456780000001,64'hfedcba9876544001,8,1,0);
   ack(0,24'hfffffe,24'hfffffe,0,8'h61);
   if(commands || a_executed_count)$fatal(1,"unaligned atomic gained DMA");
  end
  7:begin
   offer(8'h14,0,24'hffffff,64'h9123456780000001,64'hfedcba9876544000,8,1,0);
   ack(0,24'hfffffe,24'hfffffe,0,8'h60);
   if(commands)$fatal(1,"future PSN executed");
   one(8'h14,0,24'hfffffe,24'hffffff,1,0,64'hf123456789abcdef,64'hf123456789abcdf0);
   before_cmd=commands;
   offer(8'h14,0,24'hfffffe,64'h9123456780000001,64'hfedcba9876544000,8,2,0);
   ack(0,24'hfffffe,24'hffffff,0,8'h61);
   if(commands!=before_cmd)$fatal(1,"mutated duplicate re-executed");
  end
  8:begin
   offer(8'h14,0,24'hfffffe,64'h9123456780000000,64'hfedcba9876544000,8,1,0);
   repeat(12)@(negedge clk);
   if(a_m_response_valid || commands || a_dropped_count!=1)$fatal(1,"stale epoch accepted");
   one(8'h14,0,24'hfffffe,24'hffffff,0,0,64'hf123456789abcdef,64'hf123456789abcdef);
   configure_qp(0,64'h9123456780000002,17,24'hfffffe);
   offer(8'h14,0,24'hfffffe,64'h9123456780000001,64'hfedcba9876544000,8,0,0);
   repeat(12)@(negedge clk);
   if(a_m_response_valid || a_dropped_count!=2)$fatal(1,"old-QP replay survived fresh epoch");
  end
  9,10,11,12:begin
   fail_read=scenario==9 ? 4:0;fail_write=scenario==10 ? 4:0;
   fail_fence=scenario==11 ? 5:0;wrong_read_tag=scenario==12;
   offer(8'h14,0,24'hfffffe,64'h9123456780000001,64'hfedcba9876544000,8,1,0);
   repeat(700)@(negedge clk);
   if(!(a_fault || b_fault || fault) || a_m_response_valid || a_executed_count ||
      quiet || mr_cfg_ready || cfg_ready || !a_memory_lock_request || b_s_command_ready[0])
    $fatal(1,"DMA failure manufactured completion or unpin permission");
  end
  13:begin
   one(8'h14,0,24'hfffffe,24'hffffff,1,0,64'hf123456789abcdef,64'hf123456789abcdf0);
   one(8'h14,0,24'hffffff,0,1,0,64'hf123456789abcdf0,64'hf123456789abcdf1);
   before_cmd=commands;
   offer(8'h14,0,24'hfffffe,64'h9123456780000001,64'hfedcba9876544000,8,1,0);
   repeat(12)@(negedge clk);
   if(commands!=before_cmd || a_dropped_count!=1 || a_m_response_valid)$fatal(1,"evicted duplicate re-executed");
  end
  default:$fatal(1,"unknown case");
 endcase
 // Every byte outside the exact8-byte target stays unchanged.
 for(k=0;k<16384;k=k+1)if(k<4096 || k>=4104)
  if(host[k]!==(((k*37)^8'h5a)&255))$fatal(1,"neighbor clobbered byte=%d",k);
 $display("ATOMIC_RESULT {\"pass_test\":true,\"case\":%0d,\"cycles\":%0d,\"executed\":%0d,\"replayed\":%0d,\"dropped\":%0d,\"commands\":%0d,\"physical_reads\":%0d,\"physical_writes\":%0d,\"fences\":%0d}",scenario,cycles,a_executed_count,a_replay_count,a_dropped_count,commands,physical_reads,physical_writes,fences);
 $finish;
end
endmodule
'''


def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve previous evidence')
    inputs=[*SOURCES,Path(__file__).resolve(),Path(paged.__file__).resolve()]
    before={str(x.relative_to(ROOT)):digest(x)for x in inputs}
    run=Path(tempfile.mkdtemp(prefix='atomic-responder-',dir=ROOT/'rdma/rnic/build'))
    report=dict(scope=__doc__,pass_test=False,run=str(run),source_sha256=before,
        simulation_limit_seconds=30,hardware_verified=False,native_integrated=False,
        standard_verbs=False,shared_HLS_QP_table=False,integrity_peer_admission_model=True,
        physical_descriptor_host_visibility_model=True,atomic_capability_advertised=False)
    try:
        tb=bench();(run/'tb.v').write_text(tb)
        report['bench_sha256']=hashlib.sha256(tb.encode()).hexdigest()
        cmd=['iverilog','-g2012','-s','tb','-o',str(run/'test.vvp'),str(run/'tb.v'),*map(str,SOURCES)]
        start=time.monotonic();c=subprocess.run(cmd,capture_output=True,text=True,timeout=30)
        (run/'compile.log').write_text(c.stdout+c.stderr);report['compile_seconds']=time.monotonic()-start
        if c.returncode:raise RuntimeError(c.stdout+c.stderr)
        elaborated=(run/'test.vvp').read_text()
        counts={n:len(re.findall(r'\.scope module, "[^\"]+" "'+n+r'"',elaborated))for n in
            ['rocev2_atomic_responder','rocev2_atomic_memory_bridge','rocev2_memory_client_arbiter',
             'rocev2_mr_table','rocev2_mr_page_table','rocev2_paged_memory_backend',
             'rocev2_corundum_dma_backend','dma_psdpram']}
        if not all(v==1 for v in counts.values()):raise ValueError(('module multiplicity',counts))
        report['actual_elaborated_module_counts']=counts
        report['tests']={}
        for n in range(14):
            start=time.monotonic();r=subprocess.run(['vvp',str(run/'test.vvp'),f'+case={n}'],
                capture_output=True,text=True,timeout=30)
            (run/f'case-{n}.log').write_text(r.stdout+r.stderr)
            report['tests'][n]=dict(seconds=time.monotonic()-start,exit_code=r.returncode)
            if r.returncode:raise RuntimeError(r.stdout+r.stderr)
            rows=[json.loads(l.split(' ',1)[1])for l in r.stdout.splitlines()if l.startswith('ATOMIC_RESULT ')]
            if len(rows)!=1 or not rows[0]['pass_test']:raise ValueError('missing actual assertions')
            report['tests'][n]['summary']=rows[0]
            replies=[]
            for line in r.stdout.splitlines():
                if not line.startswith('ATOMIC_REPLY '):continue
                _,raw,size,q,psn,msn,old,syn=line.split()
                size,q=int(size),int(q);psn,msn,old,syn=(int(x,16)for x in [psn,msn,old,syn])
                actual=int(raw,16).to_bytes(24,'little')
                # Independent Python network-layout oracle: no Verilog
                # byte-reversal helper or implementation response() is used.
                bth=bytes([0x12 if syn==0x1f else 0x11,0])+struct.pack('!H',0xffff)
                bth+=struct.pack('!I',0xf12345+q)+struct.pack('!I',psn)
                expected=bth+bytes([syn])+msn.to_bytes(3,'big')
                expected+=struct.pack('!Q',old)if syn==0x1f else bytes(8)
                if actual!=expected or size!=(24 if syn==0x1f else 16):
                    raise ValueError(('independent AtomicACK oracle',actual.hex(),expected.hex()))
                replies.append(dict(wire_hex=actual[:size].hex(),bytes=size,wire_oracle_pass=True))
            report['tests'][n]['independent_wire_replies']=replies
        if before!={n:digest(ROOT/n)for n in before}:raise ValueError('source changed during test')
        report.update(pass_test=True,source_unchanged=True,
            artifact_sha256={str(x.relative_to(ROOT)):digest(x)for x in [run/'tb.v',run/'test.vvp']})
    except Exception as e:report['error']=str(e);raise
    finally:
        with a.report.open('x')as f:f.write(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(pass_test=True,run=str(run),cases=len(report['tests']),
        compile_seconds=report['compile_seconds'],max_runtime_seconds=max(x['seconds']for x in report['tests'].values()))))


if __name__=='__main__':main()
