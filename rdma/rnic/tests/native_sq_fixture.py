# SPDX-License-Identifier: BSD-2-Clause-Views
"""One actual native SQ/MR/router/mux/PCIe fixture; physical host/MAC MODELS.

No descriptor/RAM agent or constant parent proof. Local executor/CQ lifetime
is an EXPLICIT downstream guard model, not payload execution or completion.
"""
from pathlib import Path
import re

import probe_native_control as native
import probe_parent_guard_transport as parent
import probe_native_shared_mr as local
import test_native_shared_mr_rtl as portable

ROOT=native.ROOT
RTL=ROOT/'rdma/rnic/rtl'
TOP=RTL/'rocev2_native_sq_endpoint.v'
HEADER=ROOT/'rdma/rnic/kernel/sq_regs.h'
EXTRA=[TOP,*[RTL/(n+'.v')for n in ['rocev2_dma_client_router','rocev2_sq_dma_fetch',
    'rocev2_sq_fetch','rocev2_sq_control_regs','rocev2_queue_cfg_arbiter','rocev2_sq_wqe_admission',
    'rocev2_wqe_admission','rocev2_mr_query_arbiter']],parent.RTL]

TASKS=r'''
localparam SQ_BASE=24'h402000;
integer sq_sequence_number=0,sq_i,sq_deadline,sq_work_results=0;
reg [31:0] sq_words[0:14],sq_value;
reg [511:0] sq_records[0:1];
reg retain_work=0,release_work=0;
reg [31:0] expected_work_key=8;
reg [31:0] sq_hold_cycles=0;
reg work_stalled=0;reg [587:0] held_work;
wire [587:0] work_fields={m_work_wr_id,m_work_sequence,m_work_epoch,m_work_qpn,m_work_pd,m_work_tag,
 m_work_opcode,m_work_flags,m_work_length,m_work_local_key,m_work_local_address,m_work_local_offset,
 m_work_remote_address,m_work_remote_key,m_work_error,m_work_error_source,m_work_fetch_error,
 m_work_descriptor_available,m_work_authorized};
always @(posedge clk)if(!rst)begin
 if(work_stalled && (!m_work_valid || work_fields!==held_work))$fatal(1,"native SQ work changed under stall");
 work_stalled=m_work_valid&&!m_work_handoff;held_work=work_fields;
 if((|executor_queue_guard) && (quiet || config_safe))$fatal(1,"native SQ executor owner escaped management");
 if(m_work_handoff)begin
  sq_work_results=sq_work_results+1;
  if(retain_work)executor_queue_guard<=8'h04;
 end
 if(release_work)executor_queue_guard<=0;
end
task sq_write;
 input [11:0] address;input [31:0] value;
 begin write_reg(SQ_BASE+address,value,15,0,2);end
endtask
task sq_read;
 input [11:0] address;output [31:0] value;
 begin read_reg(SQ_BASE+address,value);end
endtask
task sq_stage;
 input [1:0] op;input [63:0] producer;
 begin
  sq_read(AS02_SQC_STATUS,sq_value);if(sq_value!==1)$fatal(1,"native SQC1 not clean/ready %h",sq_value);
  for(sq_i=0;sq_i<15;sq_i=sq_i+1)sq_words[sq_i]=0;
  sq_words[0]=sq_sequence_number+1;sq_words[1]=op;sq_words[2]=2;sq_words[3]=17;
  sq_words[4]=1;sq_words[5]=32'h91234567;sq_words[6]=32'h89abcdef;sq_words[7]=32'hfedcba98;
  sq_words[8]=32'h76543000;sq_words[9]=32'hfedcba98;sq_words[10]=1;
  sq_words[11]=producer;sq_words[12]=producer>>32;
  if(op==3)begin sq_words[13]=32'h76543210+sq_words[0];sq_words[14]=32'hf1234567;end
  for(sq_i=0;sq_i<15;sq_i=sq_i+1)sq_write(AS02_SQC_STAGE+sq_i*4,sq_words[sq_i]);
 end
endtask
task sq_bell;
 begin sq_write(AS02_SQC_DOORBELL,sq_words[0]);sq_sequence_number=sq_words[0];end
endtask
task sq_collect;
 input [7:0] error;input [31:0] flags;input [63:0] consumer;
 begin
  sq_deadline=cycle+5000;sq_value=0;
  while(!sq_value[1] && cycle<sq_deadline)sq_read(AS02_SQC_STATUS,sq_value);
  if(!sq_value[1] || sq_value[5:2])$fatal(1,"native SQC1 missing/uncertain reply %h",sq_value);
  for(sq_i=0;sq_i<15;sq_i=sq_i+1)begin
   sq_read(AS02_SQC_REPLY+sq_i*4,sq_value);
   if(sq_value!==sq_words[sq_i])$fatal(1,"native SQC1 full owner/layout/nonce word%d",sq_i);
  end
  sq_read(AS02_SQC_REPLY_ERROR,sq_value);if(sq_value!==error)$fatal(1,"native SQC1 error%d expected%d",sq_value,error);
  sq_read(AS02_SQC_REPLY_FLAGS,sq_value);if(sq_value!==flags)$fatal(1,"native SQC1 actual proof flags%h expected%h",sq_value,flags);
  if(error==0 && sq_words[1]!=2)begin
   sq_read(AS02_SQC_REPLY_CONSUMER_LO,sq_value);if(sq_value!==consumer[31:0])$fatal(1,"native SQC1 actual consumer low");
   sq_read(AS02_SQC_REPLY_CONSUMER_HI,sq_value);if(sq_value!==consumer[63:32])$fatal(1,"native SQC1 actual consumer high");
  end
  sq_write(AS02_SQC_REPLY_ACK,sq_sequence_number);
  sq_deadline=cycle+1000;
  while(sq_control_busy && cycle<sq_deadline)@(negedge clk);
  if(sq_control_busy || sq_control_response_valid || sq_control_fatal || sq_control_mmio_error || sq_control_owner_tainted)$fatal(1,"native SQC1 exact ACK/owner failed");
  $display("NATIVE_SQ_CSR seq%0d op%0d error%0d flags%0d consumer%0d",sq_sequence_number,sq_words[1],error,flags,consumer);
 end
endtask
task sq_command;
 input [1:0] op;input [63:0] producer;input [7:0] error;input [31:0] flags;input [63:0] consumer;
 begin sq_stage(op,producer);sq_bell();sq_collect(error,flags,consumer);end
endtask
task expect_work;
 input [7:0] error;input [1:0] error_source;
 begin
  sq_deadline=cycle+5000;while(!m_work_valid && cycle<sq_deadline)@(negedge clk);
  if(!m_work_valid || m_work_error!==error || m_work_error_source!==error_source || m_work_fetch_error ||
   !m_work_descriptor_available || m_work_qpn!==2 || m_work_pd!==17 || m_work_epoch!==64'h9123456700000001 ||
   m_work_sequence!==1 || m_work_tag!==1 || m_work_wr_id!==64'hf123456789abc001 ||
   m_work_authorized!==(error==0) || admission_queue_guard!==8'h04)$fatal(1,"actual fetched SQ record/trusted context/admission error");
  if(error==0)begin
   if(m_work_local_key!==expected_work_key || m_work_local_address!==64'hfedcba9876543210 || m_work_local_offset!==64'h210 ||
    m_work_remote_key!==0 || m_work_remote_address!==64'hf123456789abc001 || m_work_length!==65 || m_work_opcode!==1 || m_work_flags!==1)
    $fatal(1,"fetched SQ lost full local/remote authority tuple");
  end else if(m_work_local_key || m_work_local_address || m_work_local_offset || m_work_remote_key ||
   m_work_remote_address || m_work_length || m_work_opcode || m_work_flags)$fatal(1,"denied fetched WQE leaked payload authority");
  repeat(13)begin @(negedge clk);if(!m_work_valid || quiet || config_safe)$fatal(1,"held fetched work released MR/native lifetime");end
 end
endtask
task accept_work;
 begin
  @(negedge clk);m_work_ready=1;@(posedge clk);@(negedge clk);m_work_ready=0;#1;
 end
endtask
task release_execution;
 begin
  if(executor_queue_guard!==8'h04)$fatal(1,"missing modeled native executor handoff owner");
  repeat(17)begin @(negedge clk);if(quiet || config_safe)$fatal(1,"executor owner cleared too early");end
  release_work=1;@(posedge clk);@(negedge clk);release_work=0;
 end
endtask
task check_ring;
 begin
  for(sq_i=0;sq_i<128;sq_i=sq_i+1)
   if(pcie_host[16384+sq_i]!==sq_records[sq_i/64][(sq_i%64)*8+:8] || pcie_posted_valid[16384+sq_i])$fatal(1,"coherent ring bytes modified by DMA");
 end
endtask
'''


def once(text,old,new):
    if text.count(old)!=1:raise ValueError('native SQ fixture anchor changed: '+old)
    return text.replace(old,new)


def make_tb(fixtures,body):
    tb=native.bench()
    tb,count=re.subn(r'assign parent_dma_drained=.*?;',parent.GUARD,tb,count=1,flags=re.S)
    if count!=1:raise ValueError('actual native parent-proof layout changed')
    start=tb.index('rocev2_native_endpoint dut(');end=tb.index(');',start)+2
    mapping=dict(re.findall(r'\.(\w+)\(([^()]*)\)',tb[start:end]))
    tb=tb[:start]+'// NATIVE_SQ_INSTANCE\n'+tb[end:]
    # Read-only aliases now observe the original native child, never force it.
    tb=tb.replace('dut.','dut.network.')
    params=dict(TX_TAG_WIDTH=16,TS_WIDTH=96,RX_USER_WIDTH=97,RAM_SIZE=8192,RAM_ADDR_WIDTH=15,
        SEG_COUNT=2,SEG_DATA_WIDTH=256,SEG_BE_WIDTH=32,SEG_ADDR_WIDTH=9,RAM_SEL_WIDTH=1,
        DMA_LEN_WIDTH=16,DMA_TAG_WIDTH=16,MAX_QPS=8)
    declarations=['localparam MAX_QPS=8;'];connections=[]
    for direction,expr,name in native.pcie.ports(TOP):
        signal=mapping.get(name,name)
        if name=='parent_fault':signal='actual_parent_fault'
        elif name=='dma_drained':
            signal='native_sq_dma_drained';declarations.append('wire native_sq_dma_drained;')
        elif name not in mapping:
            declarations.append(native.pcie.declaration(name,native.pcie.width(expr,params),'reg'if direction=='input'else'wire'))
        connections.append(f'.{name}({signal})')
    tb=once(tb,'// NATIVE_SQ_INSTANCE','\n'.join(declarations)+'\nrocev2_native_sq_endpoint dut('+','.join(connections)+');')
    # Extend the explicit physical host MODEL with exactly one128B coherent
    # SQ ring. Every byte is actual C-encoded input, never a descriptor agent.
    tb=once(tb,'pcie_host[0:16383],pcie_posted[0:16383]','pcie_host[0:16511],pcie_posted[0:16511]')
    tb=once(tb,'pcie_posted_valid[0:16383]','pcie_posted_valid[0:16511]')
    marker='function integer pcie_host_index;'
    start=tb.index(marker);end=tb.index('endfunction',start)
    section=tb[start:end]
    # Insert the full-width ring mapping AFTER page lookup, before return.
    position=section.rfind(' end')
    if position<0:raise ValueError('host mapping return changed')
    section=section[:position]+" if(address>=64'hfedcba9876543000 && address<64'hfedcba9876543080)pcie_host_index=16384+address-64'hfedcba9876543000;\n"+section[position:]
    tb=tb[:start]+section+tb[end:]
    tb=once(tb,'for(init_byte=0;init_byte<16384;','for(init_byte=0;init_byte<16512;')
    tb=once(tb,"pcie_host[init_byte]=(init_byte*37)^8'h5a;pcie_posted_valid[init_byte]=0;\n end\nend",r'''
pcie_host[init_byte]=(init_byte*37)^8'h5a;pcie_posted_valid[init_byte]=0;
 end
 $readmemh("records.hex",sq_records);
 for(init_byte=0;init_byte<128;init_byte=init_byte+1)pcie_host[16384+init_byte]=sq_records[init_byte/64][(init_byte%64)*8+:8];
end''')
    # Preserve all original native-bank page/range checks, but distinguish the
    # real SQ bank and check its exact coherent READ address/size instead.
    begin=tb.index('  if(desc_tag!=pcie_last_tag+1');end=tb.index('  $display("PAGE_DMA',begin)
    old=tb[begin:end]
    new=r'''
  if((m_dma_write_valid ? m_dma_write_ram_sel:m_dma_read_ram_sel)==1)begin
   if(m_dma_write_valid || desc_tag!=pcie_last_tag+1 || desc_length!=64 || desc_ram!=0 ||
    desc_address!==64'hfedcba9876543000)$fatal(1,"actual coherent SQ descriptor/address/size/tag");
  end else begin
'''+old+'  end\n'
    tb=tb[:begin]+new+tb[end:]
    # Actual muxes must preserve BOTH physical RAM banks, not just old bank0.
    tb=once(tb,'eng_m_dma_write_ram_sel!=12',"eng_m_dma_write_ram_sel!={3'b110,m_dma_write_ram_sel}")
    tb=once(tb,'eng_m_dma_read_ram_sel!=12',"eng_m_dma_read_ram_sel!={3'b110,m_dma_read_ram_sel}")
    tb=once(tb,'  repeat(17) @(negedge clk);\n  tlp_s_axis_rd_req_tx_seq_num',r'''
  repeat(17) @(negedge clk);
  if(first_address>=64'hfedcba9876543000 && first_address<64'hfedcba9876543080)
   repeat(sq_hold_cycles)@(negedge clk);
  tlp_s_axis_rd_req_tx_seq_num''')
    # Reuse the original exact native reply/ACK checks for an already-rung
    # control command, with an explicit expected incoming-operation count.
    task=tb.split('task host_finish;',1)[1].split('task host_api;',1)[0]
    task=once(task,'  write_reg(AS02_CTL_DOORBELL,1,15,0,1);\n','')
    task=once(task,'if(op==5 && completed!=3)','if(op==5 && completed!=extra_invalidate_completed)')
    macros='\n'.join('localparam '+n+'='+re.sub(r'U$','',v).replace('0x',"32'h")+';'for n,v in
        re.findall(r'^#define (AS02_SQC_\w+) (0x[0-9a-fA-F]+U|\d+U)$',HEADER.read_text(),re.M))
    host=macros+'\n'+TASKS+'\ninteger extra_invalidate_completed=3;\ntask collect_native;'+task
    tb=once(tb,'reg [144:0] stimulus',host+'\nreg [144:0] stimulus')
    return '\n'.join(f'`include "{p}"'for p in EXTRA)+'\n'+tb.replace(
        'STIMULUS_LAST',str(len(fixtures)-1)).replace('// TEST_BODY',body)


def prefix():
    return r'''
read_reg(24'h402000,sq_value);if(sq_value!==AS02_SQC_ID_VALUE)$fatal(1,"actual native SQ ID decode");
read_reg(24'h402004,sq_value);if(sq_value!==AS02_SQC_ABI_VALUE)$fatal(1,"actual native SQ ABI decode");
read_reg(24'h402008,sq_value);if(sq_value!==1)$fatal(1,"native SQ must advertise control-only");
expect_decerr(24'h403000);
host_api(8,401,0,0,0,0,0,0,0,2);
if(!config_safe)$fatal(1,"native SQ initial empty STOP boundary");
write_reg(24'h401014,1,15,0,0);if(ethernet_config_error)$fatal(1,"clean pre-SQ route error");
host_api(7,402,0,0,0,0,0,0,0,0);
sq_command(1,0,0,7,0);
'''


def forward_body():
    return prefix()+r'''
// Even an unfetched posted ring entry owns route context, not an MR lease.
enable=0;sq_command(2,1,0,0,0);
if(sq_queue_pending!==8'h04 || sq_fetch_count || admission_queue_guard)$fatal(1,"posted/unadmitted ownership classification");
host_api(8,403,0,0,0,0,0,0,0,2);
if(config_safe || quiet)$fatal(1,"pending SQ falsely globally quiescent");
write_reg(24'h401010,1,15,0,0);read_reg(24'h40100c,sq_value);
if(sq_value!==1 || !ethernet_config_error)$fatal(1,"posted SQ allowed unsafe route COMMIT");
host_api(7,404,0,0,0,0,0,0,0,0);enable=1;
expect_work(0,0);
if(sq_fetch_count!=1 || sq_result_count!=1 || sq_queue_pending || sq_queue_guard)$fatal(1,"fetch handoff not real/complete");
host_stage(8,405,0,0,0,0,0,0);write_reg(AS02_CTL_DOORBELL,1,15,0,1);
repeat(20)begin @(negedge clk);if(!control_busy || !admission_pause || quiet || config_safe)$fatal(1,"STOP ignored fetched/MR work owner");end
retain_work=1;accept_work();retain_work=0;
if(executor_queue_guard!==8'h04 || admission_queue_guard)$fatal(1,"native work handoff gap");
sq_command(3,1,35,0,0);
if(sq_control_owner_active!==8'h04 || sq_queue_active!==8'h04 || quiet)$fatal(1,"retire mistaken fetch completion for WR completion");
release_execution();collect_native(8,405,0,0,2);
sq_command(3,1,0,31,1);
if(sq_control_owner_active || sq_queue_active || sq_queue_pending || !config_safe || !quiet || !native_sq_dma_drained ||
 sq_work_results!=1 || router_client_busy || router_descriptor_count!=router_completion_count)$fatal(1,"actual native SQ final owned drain");
check_ring();
$display("NATIVE_SQ_RESULT {\"pass_test\":true,\"work_results\":%0d,\"fetches\":%0d,\"physical_descriptors\":%0d,\"SQ_CSR_commands\":%0d,\"ring_bytes_checked\":128,\"local_payload_execution\":false}",sq_work_results,sq_fetch_count,router_descriptor_count,sq_sequence_number);
$finish;
'''


def priority_body():
    return prefix()+r'''
// Stage MR invalidation first, without its doorbell. It must not pause yet.
host_stage(5,OWNER0,0,8,0,0,0,0);extra_invalidate_completed=0;
sq_stage(2,1);enable=1;sq_hold_cycles=160;sq_bell();
sq_deadline=cycle+1000;while(!sq_queue_guard[2] && cycle<sq_deadline)@(negedge clk);
if(!sq_queue_guard[2])$fatal(1,"no actual SQ fetch reservation");
write_reg(AS02_CTL_DOORBELL,1,15,0,1);
sq_collect(0,0,0);
// Native MR management must finish even though raw SQ RESULT is waiting
// behind its pause. That raw result has no authorized payload lease yet.
collect_native(5,OWNER0,0,8,3);
expect_work(1,2);completion_queue_guard=8'h04;accept_work();
repeat(13)begin @(negedge clk);if(quiet || !native_sq_dma_drained)$fatal(1,"CQ owner or actual DMA boundary confused");end
sq_command(3,1,35,0,0);completion_queue_guard=0;
sq_command(3,1,0,31,1);
if(sq_work_results!=1 || sq_control_owner_active || sq_queue_pending || !quiet || !native_sq_dma_drained ||
 read_tlps!=1 || write_tlps || commands || completed || txframes)$fatal(1,"raw-result priority scope or false local execution");
check_ring();
$display("NATIVE_SQ_RESULT {\"pass_test\":true,\"work_results\":%0d,\"fetches\":%0d,\"physical_descriptors\":%0d,\"SQ_CSR_commands\":%0d,\"ring_bytes_checked\":128,\"stale_key_denied_after_actual_MR_invalidate\":true,\"local_payload_execution\":false}",sq_work_results,sq_fetch_count,router_descriptor_count,sq_sequence_number);
$finish;
'''
