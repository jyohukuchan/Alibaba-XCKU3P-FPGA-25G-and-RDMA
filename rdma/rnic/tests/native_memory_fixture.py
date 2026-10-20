# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual native coherent SQ/SAME-MR -> SAME paged payload backend/PCIe.

The trusted local transport/executor and final wire/CQ lifetime are EXPLICIT
MODELS. Commands copy ONLY the actual authorized WQE tuple, never arbitrary
DMA addresses. Host/link/MAC remain models; no real RDMA completion or pins.
"""
import re

import native_sq_fixture as sq

ROOT=sq.ROOT
ARBITER=ROOT/'rdma/rnic/rtl/rocev2_memory_client_arbiter.v'

TASKS=r'''
integer local_memory_bytes=0,local_memory_operations=0,local_memory_position,local_memory_lane,local_memory_amount,local_memory_deadline;
always @(posedge clk)if(!rst && s_local_memory_command_valid && s_local_memory_command_ready)begin
 if(executor_queue_guard!==8'h04 || s_local_memory_command_offset!==64'h210 ||
  s_local_memory_command_length!==65 || s_local_memory_command_key!==expected_work_key || s_local_memory_command_tag!==1)
  $fatal(1,"modeled executor changed full authorized memory tuple");
 // The original monitor sampled ONLY incoming responder commands. The new
 // real local client must supply its actual accepted MR-relative context to
 // the SAME exact physical address/page/length/tag checks, not bypass them.
 pcie_current_length=s_local_memory_command_length;pcie_current_offset=s_local_memory_command_offset;
end
task snapshot_local_memory;
 input placement;
 begin
  if(!m_work_valid || !m_work_authorized || m_work_error || !m_work_descriptor_available ||
   m_work_opcode!==(placement ? 16'd2 : 16'd1) || m_work_qpn!=2 || m_work_pd!=17 || m_work_length!=65 ||
   m_work_local_offset!==64'h210 || m_work_local_key!==expected_work_key)$fatal(1,"model executor did not receive actual SAME-MR authority");
  // This MODELED executor binds its command to the actual full authorized
  // tuple. No physical DMA address or separate MR/PTE namespace is supplied.
  s_local_memory_command_write=placement;
  s_local_memory_command_offset=m_work_local_offset;s_local_memory_command_length=m_work_length;
  s_local_memory_command_key=m_work_local_key;s_local_memory_command_tag=m_work_tag;
 end
endtask
task transfer_local_memory;
 input placement;
 begin
  if(executor_queue_guard!==8'h04 || !control_busy || !admission_pause)$fatal(1,"local memory lost authorized owner/STOP exclusion");
  @(negedge clk);s_local_memory_command_valid=1;local_memory_deadline=cycle+3000;
  @(posedge clk);while(!s_local_memory_command_ready)begin if(cycle>local_memory_deadline)$fatal(1,"shared local memory command deadline");@(posedge clk);end
  @(negedge clk);s_local_memory_command_valid=0;local_memory_position=0;
  while(local_memory_position<65)begin
   local_memory_amount=65-local_memory_position;if(local_memory_amount>64)local_memory_amount=64;
   if(placement)begin
    s_axis_local_memory_write_tdata={512{1'bx}};s_axis_local_memory_write_tkeep=0;
    for(local_memory_lane=0;local_memory_lane<local_memory_amount;local_memory_lane=local_memory_lane+1)begin
     s_axis_local_memory_write_tdata[local_memory_lane*8+:8]=pcie_pattern(local_memory_position+local_memory_lane);
     s_axis_local_memory_write_tkeep[local_memory_lane]=1;
    end
    s_axis_local_memory_write_tlast=local_memory_position+local_memory_amount==65;s_axis_local_memory_write_tvalid=1;
    @(posedge clk);while(!s_axis_local_memory_write_tready)begin if(cycle>local_memory_deadline)$fatal(1,"local placement data deadline");@(posedge clk);end
    @(negedge clk);s_axis_local_memory_write_tvalid=0;
   end else begin
    while(!m_axis_local_memory_read_tvalid)begin if(cycle>local_memory_deadline)$fatal(1,"local source DMA data deadline");@(negedge clk);end
    if(m_axis_local_memory_read_tlast!==(local_memory_position+local_memory_amount==65))$fatal(1,"local source last");
    for(local_memory_lane=0;local_memory_lane<64;local_memory_lane=local_memory_lane+1)begin
     if(m_axis_local_memory_read_tkeep[local_memory_lane]!==(local_memory_lane<local_memory_amount))$fatal(1,"local source keep");
     if(m_axis_local_memory_read_tdata[local_memory_lane*8+:8]!==
      (local_memory_lane<local_memory_amount ? pcie_host[4093+local_memory_position+local_memory_lane] : 8'd0))$fatal(1,"local source host byte/padding");
    end
    repeat(11)begin @(negedge clk);if(m_local_memory_status_valid || !local_memory_busy || dut.memory_drained || quiet || config_safe || !control_busy)$fatal(1,"local stalled data falsely complete/drained");end
    m_axis_local_memory_read_tready=1;@(posedge clk);@(negedge clk);m_axis_local_memory_read_tready=0;
   end
   local_memory_position=local_memory_position+local_memory_amount;
  end
  while(!m_local_memory_status_valid)begin if(cycle>local_memory_deadline)$fatal(1,"local memory actual backend status deadline");@(negedge clk);end
  repeat(17)begin @(negedge clk);
   if(m_local_memory_status_tag!==s_local_memory_command_tag || m_local_memory_status_error!==0 ||
    !m_local_memory_status_valid || !local_memory_busy || dut.memory_drained || quiet || config_safe || !control_busy)
    $fatal(1,"local memory status lost owner or falsely completed WR");
  end
  m_local_memory_status_ready=1;@(posedge clk);@(negedge clk);m_local_memory_status_ready=0;
  repeat(13)@(negedge clk);
  if(local_memory_busy || !native_sq_dma_drained || executor_queue_guard!==8'h04 || quiet || config_safe || !control_busy)
   $fatal(1,"memory status was mistaken for actual RDMA/CQ completion");
  if(placement)for(local_memory_lane=0;local_memory_lane<65;local_memory_lane=local_memory_lane+1)
   if(pcie_host[4093+local_memory_lane]!==pcie_pattern(local_memory_lane) || pcie_posted_valid[4093+local_memory_lane])$fatal(1,"local placement did not become visible through actual fence");
  for(local_memory_lane=0;local_memory_lane<16384;local_memory_lane=local_memory_lane+1)begin
   if(pcie_posted_valid[local_memory_lane])$fatal(1,"unfenced host byte remains");
   if(local_memory_lane>=4093 && local_memory_lane<4158 && (placement || commands!=0))begin
    if(pcie_host[local_memory_lane]!==pcie_pattern(local_memory_lane-4093))$fatal(1,"local/remote payload host byte");
   end else if(pcie_host[local_memory_lane]!==(((local_memory_lane*37)^8'h5a)&8'hff))$fatal(1,"local DMA changed host sentinel byte%0d",local_memory_lane);
  end
  local_memory_bytes=local_memory_bytes+65;local_memory_operations=local_memory_operations+1;
 end
endtask
'''


def body(placement=False):
    text=sq.forward_body()
    text=sq.once(text,'retain_work=1;accept_work();retain_work=0;',
        f'snapshot_local_memory({int(placement)});retain_work=1;accept_work();retain_work=0;transfer_local_memory({int(placement)});')
    text=sq.once(text,'$finish;',r'''
$display("NATIVE_MEMORY_RESULT {\"pass_test\":true,\"local_memory_operations\":%0d,\"payload_bytes_checked\":%0d,\"physical_descriptors\":%0d,\"read_tlps\":%0d,\"write_tlps\":%0d,\"fences\":%0d,\"native_RDMA_completion\":false}",local_memory_operations,local_memory_bytes,router_descriptor_count,read_tlps,write_tlps,fences);
$finish;''')
    return text


def enable_memory(tb,placement=False):
    declarations=[]
    for direction,expr,name in sq.native.pcie.ports(sq.TOP):
        if 'local_memory'not in name:continue
        # Existing default fixtures explicitly tie this optional client OFF.
        # Enabled fixtures replace each tie-off and declare its actual port.
        if re.search(r'\b(?:reg|wire)\s+(?:\[[^]]+\]\s+)?'+name+r'\b',tb):
            raise ValueError('optional memory port unexpectedly declared: '+name)
        declarations.append(('reg 'if direction=='input'else'wire ')+('['+expr+'] 'if expr else'')+name+('=0;'if direction=='input'else';'))
        pattern=r'\.'+name+r'\([^()]*\)'
        if len(re.findall(pattern,tb))!=1:raise ValueError('native memory port changed: '+name)
        tb=re.sub(pattern,lambda _:f'.{name}({name})',tb)
    if len(declarations)!=22:raise ValueError('complete native memory interface changed')
    tb=sq.once(tb,'rocev2_native_sq_endpoint dut(',
        '\n'.join(declarations)+'\n'+TASKS+'\nrocev2_native_sq_endpoint #(.LOCAL_MEMORY_ENABLE(1)) dut(')
    if placement:tb=sq.once(tb,'m_work_opcode!==1','m_work_opcode!==2')
    return f'`include "{ARBITER}"\n'+tb


def make_tb(words,placement=False):return enable_memory(sq.make_tb(words,body(placement)),placement)
