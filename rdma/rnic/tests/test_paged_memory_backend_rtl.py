# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual page table/splitter/backend/Corundum RAM, modeled descriptor engine.

No native PCIe TLPs, actual pinned pages, board or verbs integration is claimed.
All data crosses real segmented RAM ports; no DUT state/memory is forced.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

import test_corundum_dma_backend_rtl as contiguous

ROOT=contiguous.ROOT
RTL=ROOT/'rdma/rnic/rtl/rocev2_paged_memory_backend.v'
SOURCES=[RTL,ROOT/'rdma/rnic/rtl/rocev2_page_dma_engine.v',ROOT/'rdma/rnic/rtl/rocev2_mr_page_table.v',*contiguous.SOURCES]

TB=r'''
`timescale 1ns/1ps
module tb;
localparam RAM_SIZE=8192,RAM_ADDR_WIDTH=15,SEG_COUNT=2,SEG_DATA_WIDTH=256,SEG_BE_WIDTH=32,
 SEG_ADDR_WIDTH=9,RAM_SEL_WIDTH=4,DMA_LEN_WIDTH=16,TAG_WIDTH=16;
// PORTS
rocev2_paged_memory_backend dut(.*);
always #2 clk=~clk;
reg [7:0] host[0:16383],posted[0:16383];
reg posted_valid[0:16383];
integer scenario=0,dummy,cycles=0,commands=0,physical_reads=0,physical_writes=0;
integer last_tag=0,current_length=0,current_offset=0,read_position=0,expect_zero=0;
integer seed=19,j,k,start,seg,lane,base_index,ram_start,amount,issued_tag,issued_len;
integer current_tag=1,piece,deadline,read_bytes=0,write_bytes=0,first=4093;
reg [63:0] issued_address;
reg [1:0] mask;
reg rstalled=0,wstalled=0,ostalled=0,sstalled=0;
reg [127:0] saved_rdesc,saved_wdesc;
reg [576:0] saved_output;
reg [23:0] saved_status;
reg [31:0] rng=32'h3ab455a1;
function [63:0] dma_page;
 input integer page;
 begin case(page) 0:dma_page=64'h8123456789abc000;1:dma_page=64'hfffffffffffff000;2:dma_page=64'h12345000;default:dma_page=0;endcase end
endfunction
function integer host_index;
 input [63:0] address;
 integer p;
 begin
  host_index=-1;
  for(p=0;p<3;p=p+1) if(address[63:12]==(dma_page(p)>>12)) host_index=p*4096+address[11:0];
 end
endfunction
function [63:0] expected_dma;
 input integer offset;
 begin expected_dma=dma_page((first+offset)/4096)+((first+offset)%4096);end
endfunction
function [7:0] pattern;
 input integer pos;
 begin pattern=(pos*179)^(pos>>7)^seed^8'hd3;end
endfunction
function [63:0] keep;
 input integer count;
 begin keep=count>=64 ? 64'hffffffffffffffff : (64'h1<<count)-1;end
endfunction
always @(negedge clk) if(!rst) begin
 rng={rng[30:0],rng[31]^rng[21]^rng[1]^rng[0]};m_axis_read_tready=rng[2:0]!=0;
end
always @(posedge clk) if(!rst) begin
 cycles=cycles+1;if(cycles>200000) $fatal(1,"deadline case=%d fault=%b/%d",scenario,fault,fault_code);
 if(rstalled && (!m_dma_read_valid || {m_dma_read_address,m_dma_read_length,m_dma_read_tag,m_dma_read_ram_address,m_dma_read_ram_sel}!==saved_rdesc)) $fatal(1,"read descriptor ownership");
 if(wstalled && (!m_dma_write_valid || {m_dma_write_address,m_dma_write_length,m_dma_write_tag,m_dma_write_ram_address,m_dma_write_ram_sel}!==saved_wdesc)) $fatal(1,"write descriptor ownership");
 if(ostalled && (!m_axis_read_tvalid || {m_axis_read_tlast,m_axis_read_tkeep,m_axis_read_tdata}!==saved_output)) $fatal(1,"read stream ownership");
 if(sstalled && (!m_status_valid || {m_status_error,m_status_tag}!==saved_status)) $fatal(1,"status ownership");
 rstalled=m_dma_read_valid&&!m_dma_read_ready;wstalled=m_dma_write_valid&&!m_dma_write_ready;
 ostalled=m_axis_read_tvalid&&!m_axis_read_tready;sstalled=m_status_valid&&!m_status_ready;
 saved_rdesc={m_dma_read_address,m_dma_read_length,m_dma_read_tag,m_dma_read_ram_address,m_dma_read_ram_sel};
 saved_wdesc={m_dma_write_address,m_dma_write_length,m_dma_write_tag,m_dma_write_ram_address,m_dma_write_ram_sel};
 saved_output={m_axis_read_tlast,m_axis_read_tkeep,m_axis_read_tdata};saved_status={m_status_error,m_status_tag};
 if(m_axis_read_tvalid && m_axis_read_tready) begin
  if(m_axis_read_tkeep!==keep(current_length-read_position) || m_axis_read_tlast!==(read_position+64>=current_length)) $fatal(1,"read stream shape");
  for(j=0;j<64;j=j+1) if(m_axis_read_tkeep[j]) begin
   if(m_axis_read_tdata[j*8+:8] !== (expect_zero ? 8'd0 : pattern(read_position+j))) $fatal(1,"READ data pos=%d got=%h",read_position+j,m_axis_read_tdata[j*8+:8]);
   read_bytes=read_bytes+1;
  end
  read_position=read_position+64;
 end
end
task configure;
 input integer op,index;
 begin
  @(negedge clk);cfg_command=op;cfg_slot=3;cfg_key=11;cfg_length=8192;
  cfg_first_offset=first;cfg_page_index=index;cfg_dma_page=dma_page(index);cfg_valid=1;
  @(posedge clk);while(!cfg_ready) @(posedge clk);
  @(negedge clk);cfg_valid=0;
  while(!cfg_response_valid) @(negedge clk);
  if(cfg_response_error!=0 || cfg_response_key!=11) $fatal(1,"PTE cfg error");
  repeat(3) begin @(negedge clk);if(!cfg_response_valid || s_command_ready) $fatal(1,"cfg response ownership");end
  cfg_response_ready=1;@(negedge clk);cfg_response_ready=0;
 end
endtask
task command;
 input integer write_op,length,offset,key;
 begin
  current_length=length;current_offset=offset;read_position=0;commands=commands+1;
  @(negedge clk);s_command_write=write_op;s_command_offset=offset;s_command_length=length;
  s_command_tag=current_tag;s_command_key=key;s_command_valid=1;
  @(posedge clk);while(!s_command_ready) @(posedge clk);
  @(negedge clk);s_command_valid=0;
 end
endtask
task send_payload;
 integer pos,b;
 begin
  for(pos=0;pos<current_length;pos=pos+64) begin
   @(negedge clk);s_axis_write_tdata=0;s_axis_write_tkeep=keep(current_length-pos);s_axis_write_tlast=pos+64>=current_length;
   for(b=0;b<64;b=b+1) if(pos+b<current_length) s_axis_write_tdata[b*8+:8]=pattern(pos+b);
   s_axis_write_tvalid=1;@(posedge clk);while(!s_axis_write_tready) @(posedge clk);
  end
  @(negedge clk);s_axis_write_tvalid=0;
 end
endtask
task accept_descriptor;
 input integer write_op,position,is_fence;
 reg [63:0] a;integer l,r,t;
 begin
  deadline=cycles+2000;
  while(!(write_op ? m_dma_write_valid : m_dma_read_valid) && cycles<deadline) @(negedge clk);
  if(!(write_op ? m_dma_write_valid : m_dma_read_valid)) $fatal(1,"missing leaf descriptor");
  a=write_op ? m_dma_write_address : m_dma_read_address;
  l=write_op ? m_dma_write_length : m_dma_read_length;
  r=write_op ? m_dma_write_ram_address : m_dma_read_ram_address;
  t=write_op ? m_dma_write_tag : m_dma_read_tag;
  amount=is_fence ? 1 : ((4096-((first+current_offset+position)%4096)<current_length-position) ? 4096-((first+current_offset+position)%4096) : current_length-position);
  if(a!==expected_dma(current_offset+(is_fence ? 0 : position)) || l!==amount || r!==(is_fence ? 8128 : position) || t<=last_tag)
   $fatal(1,"bad leaf w=%d pos=%d got=%h/%d/%d/tag%d expect=%h/%d/tag>%d",write_op,position,a,l,r,t,expected_dma(current_offset+(is_fence ? 0 : position)),amount,last_tag);
  if((write_op ? m_dma_write_ram_sel : m_dma_read_ram_sel)!=0 || m_dma_write_imm_en) $fatal(1,"bad select/immediate");
  repeat(9) begin @(negedge clk);if(m_status_valid || cfg_ready) $fatal(1,"lease/early completion");end
  issued_address=a;issued_len=l;ram_start=r;issued_tag=t;last_tag=t;
  if(write_op) begin m_dma_write_ready=1;physical_writes=physical_writes+1;end
  else begin m_dma_read_ready=1;physical_reads=physical_reads+1;end
  @(posedge clk);@(negedge clk);m_dma_write_ready=0;m_dma_read_ready=0;
 end
endtask
task fill_ram;
 integer word,b,q;
 begin
  base_index=host_index(issued_address);if(base_index<0) $fatal(1,"unknown DMA64");
  for(word=(ram_start/64)*64;word<ram_start+issued_len;word=word+64) begin
   @(negedge clk);mask=0;dma_ram_wr_cmd_addr=0;dma_ram_wr_cmd_be=0;dma_ram_wr_cmd_data=0;
   for(seg=0;seg<2;seg=seg+1) begin
    dma_ram_wr_cmd_addr[seg*SEG_ADDR_WIDTH+:SEG_ADDR_WIDTH]=word/64;
    for(b=0;b<32;b=b+1) begin
     q=word+seg*32+b;
     if(q>=ram_start && q<ram_start+issued_len) begin
      mask[seg]=1;dma_ram_wr_cmd_be[seg*32+b]=1;
      dma_ram_wr_cmd_data[(seg*32+b)*8+:8]=host[base_index+q-ram_start];
     end
    end
   end
   dma_ram_wr_cmd_valid=mask;@(posedge clk);while((dma_ram_wr_cmd_ready&mask)!=mask) @(posedge clk);
   @(negedge clk);dma_ram_wr_cmd_valid=0;
   if((dma_ram_wr_done&mask)!=mask) $fatal(1,"RAM placement incomplete");
  end
  repeat(4) @(negedge clk);
 end
endtask
task post_ram;
 integer word,b,q;
 begin
  base_index=host_index(issued_address);if(base_index<0) $fatal(1,"unknown DMA64");
  for(word=(ram_start/64)*64;word<ram_start+issued_len;word=word+64) begin
   @(negedge clk);mask=0;dma_ram_rd_cmd_addr=0;
   for(seg=0;seg<2;seg=seg+1) begin
    dma_ram_rd_cmd_addr[seg*SEG_ADDR_WIDTH+:SEG_ADDR_WIDTH]=word/64;
    if(word+seg*32<ram_start+issued_len && word+seg*32+32>ram_start) mask[seg]=1;
   end
   dma_ram_rd_cmd_valid=mask;@(posedge clk);while((dma_ram_rd_cmd_ready&mask)!=mask) @(posedge clk);
   @(negedge clk);dma_ram_rd_cmd_valid=0;
   while((dma_ram_rd_resp_valid&mask)!=mask) @(negedge clk);
   repeat(3) begin @(negedge clk);if((dma_ram_rd_resp_valid&mask)!=mask) $fatal(1,"RAM response ownership");end
   for(b=0;b<64;b=b+1) begin
    q=word+b;
    if(q>=ram_start && q<ram_start+issued_len) begin
     if(dma_ram_rd_resp_data[b*8+:8]!==pattern(q)) $fatal(1,"WRITE staging payload pos=%d",q);
     posted[base_index+q-ram_start]=dma_ram_rd_resp_data[b*8+:8];posted_valid[base_index+q-ram_start]=1;write_bytes=write_bytes+1;
    end
   end
   dma_ram_rd_resp_ready=mask;@(negedge clk);dma_ram_rd_resp_ready=0;
  end
  repeat(4) @(negedge clk);
 end
endtask
task physical_status;
 input integer write_op,error,tag;
 begin
  repeat(7) begin @(negedge clk);if(m_status_valid) $fatal(1,"premature completion");end
  if(write_op) begin s_dma_write_status_tag=tag;s_dma_write_status_error=error;s_dma_write_status_valid=1;end
  else begin s_dma_read_status_tag=tag;s_dma_read_status_error=error;s_dma_read_status_valid=1;end
  @(negedge clk);s_dma_read_status_valid=0;s_dma_write_status_valid=0;
 end
endtask
task service_payload;
 input integer write_op,fail_piece;
 integer pos,part;
 begin
  pos=0;part=0;
  while(pos<current_length) begin
   accept_descriptor(write_op,pos,0);
   if(write_op) post_ram;else if(part!=fail_piece) fill_ram;
   physical_status(write_op,part==fail_piece ? 4 : 0,issued_tag);
   if(part==fail_piece) pos=current_length;else pos=pos+issued_len;
   part=part+1;
  end
 end
endtask
task service_fence;
 input integer error;
 begin
  accept_descriptor(0,0,1);
  repeat(17) begin @(negedge clk);if(m_status_valid) $fatal(1,"WRITE visible before fence");end
  // Explicit model assumption, NOT real PCIe ordering evidence.
  for(k=0;k<16384;k=k+1) if(posted_valid[k]) begin host[k]=posted[k];posted_valid[k]=0;end
  if(!error) fill_ram;
  physical_status(0,error,issued_tag);
 end
endtask
task completion;
 input integer error;
 begin
  deadline=cycles+2000;while(!m_status_valid && cycles<deadline) @(negedge clk);
  if(!m_status_valid || m_status_tag!==current_tag || m_status_error!==error) $fatal(1,"bad completion got=%d/%d want=%d/%d fault=%d",m_status_tag,m_status_error,current_tag,error,fault_code);
  repeat(11) begin @(negedge clk);if(cfg_ready || s_command_ready) $fatal(1,"released lease before status acceptance");end
  m_status_ready=1;@(negedge clk);m_status_ready=0;repeat(4) @(negedge clk);
  if(error==0 && (!idle || !dma_drained || fault)) $fatal(1,"success failed cleanup");
  if(error!=0 && (!fault || dma_drained || cfg_ready || s_command_ready)) $fatal(1,"error manufactured page-release proof");
  current_tag=current_tag+1;
 end
endtask
task pair;
 input integer length,offset;
 begin
  for(k=0;k<16384;k=k+1) begin host[k]=(k*37)^8'h5a;posted_valid[k]=0;end
  seed=length^offset^current_tag;expect_zero=0;
  command(1,length,offset,11);send_payload;service_payload(1,-1);service_fence(0);completion(0);
  for(k=0;k<16384;k=k+1)
   if(host[k]!==((k>=first+offset && k<first+offset+length) ? pattern(k-first-offset) : (((k*37)^8'h5a)&255))) $fatal(1,"host guard/payload byte%d",k);
  command(0,length,offset,11);service_payload(0,-1);completion(0);
  if(read_position<length) $fatal(1,"missing read bytes");
 end
endtask
initial begin
 #1 rst=1;dummy=$value$plusargs("case=%d",scenario);
 repeat(5) @(negedge clk);rst=0;enable=1;cfg_quiescent=1;
 for(k=0;k<16384;k=k+1) begin host[k]=pattern(k-first);posted_valid[k]=0;end
 configure(1,0);configure(2,0);configure(2,1);configure(2,2);
 if(scenario!=9) configure(3,0);
 case(scenario)
  0: begin pair(1,0);pair(31,1);pair(32,2);pair(63,3);pair(64,31);pair(65,4090);pair(4095,4096);pair(4096,0);end
  1: begin expect_zero=1;command(0,4096,0,11);service_payload(0,1);completion(4);end
  2: begin command(1,4096,0,11);send_payload;service_payload(1,1);completion(4);if(physical_reads) $fatal(1,"failed write entered ordinary success fence");end
  3: begin command(1,65,0,11);send_payload;service_payload(1,-1);service_fence(5);completion(5);end
  4: begin expect_zero=1;command(0,65,0,19);completion(15);if(physical_reads || physical_writes) $fatal(1,"stale key caused DMA");end
  5: begin expect_zero=1;command(0,2,8191,11);completion(15);if(physical_reads || physical_writes) $fatal(1,"whole-range failure caused partial DMA");end
  6: begin
   command(0,65,0,11);accept_descriptor(0,0,0);
   physical_status(0,0,issued_tag+19);
   repeat(7) @(negedge clk);if(!fault || dma_drained || m_status_valid) $fatal(1,"wrong tag lost lease");
   fill_ram;physical_status(0,0,issued_tag);
   repeat(7) @(negedge clk);if(!fault || dma_drained || m_status_valid || cfg_ready || m_dma_read_valid) $fatal(1,"late drain manufactured success");
  end
  7: begin
   command(1,65,0,11);send_payload;
   while(!m_dma_write_valid) @(negedge clk);enable=0;
   repeat(17) @(negedge clk);service_payload(1,-1);service_fence(0);completion(0);
   if(s_command_ready) $fatal(1,"disable admitted next command");
  end
  8: begin
   command(0,65,0,11);accept_descriptor(0,0,0);
   @(negedge clk);s_dma_read_status_valid=1;s_dma_write_status_valid=1;
   s_dma_read_status_tag=issued_tag;s_dma_write_status_tag=issued_tag;
   @(negedge clk);s_dma_read_status_valid=0;s_dma_write_status_valid=0;
   repeat(7) @(negedge clk);if(!fault || dma_drained || m_status_valid) $fatal(1,"status collision manufactured success");
   fill_ram;physical_status(0,0,issued_tag);repeat(7) @(negedge clk);
   if(cfg_ready || m_status_valid || dma_drained) $fatal(1,"collision cleanup released pages");
  end
  9: begin expect_zero=1;command(0,65,0,11);completion(15);if(physical_reads || physical_writes) $fatal(1,"unsealed table caused DMA");end
  10: begin
   // A real responder owns an MR lease before issuing this command. Pending
   // invalidation cannot preempt or deadlock that already-authorized work.
   cfg_quiescent=0;cfg_command=4;cfg_slot=3;cfg_key=11;cfg_valid=1;
   pair(4096,0);
   if(cfg_ready || cfg_response_valid) $fatal(1,"invalidate preempted responder lease");
   cfg_valid=0;
  end
  11: begin
   command(0,4096,0,11);accept_descriptor(0,0,0);
   @(negedge clk);dma_ram_wr_cmd_addr=127;dma_ram_wr_cmd_be=1;dma_ram_wr_cmd_valid=1;
   repeat(3) @(negedge clk);dma_ram_wr_cmd_valid=0;
   repeat(4) @(negedge clk);if(!fault || dma_drained) $fatal(1,"bad RAM access lost lease");
   fill_ram;physical_status(0,0,issued_tag);
   repeat(9) @(negedge clk);
   if(m_dma_read_valid || m_status_valid || dma_drained || cfg_ready) $fatal(1,"backend fault did not halt later page descriptors");
  end
  default:$fatal(1,"unknown scenario");
 endcase
 $display("RESULT {\"pass_test\":true,\"scenario\":%0d,\"cycles\":%0d,\"commands\":%0d,\"physical_reads\":%0d,\"physical_writes\":%0d,\"read_bytes\":%0d,\"write_bytes\":%0d,\"last_physical_tag\":%0d,\"fault\":%0d,\"fault_code\":%0d}",scenario,cycles,commands,physical_reads,physical_writes,read_bytes,write_bytes,last_tag,fault,fault_code);
 $finish;
end
endmodule
'''


class PagedMemoryBackendTests(unittest.TestCase):
    reports={}

    @classmethod
    def setUpClass(cls):
        cls.paths=[*SOURCES,Path(__file__)]
        cls.before={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in cls.paths}
        declarations=[]
        ports=RTL.read_text().split(')(\n',1)[1].split('\n);',1)[0]
        for line in ports.splitlines():
            match=re.match(r'\s*(input|output) wire (.*?)[,]?$',line)
            if match:
                declarations.append(('reg ' if match[1]=='input' else 'wire ')+match[2].rstrip(',')+('=0;' if match[1]=='input' else ';'))
        cls.directory=tempfile.TemporaryDirectory(prefix='as02-paged-backend-');cls.path=Path(cls.directory.name)
        source=cls.path/'tb.v';source.write_text(TB.replace('// PORTS','\n'.join(declarations)))
        built=subprocess.run(['iverilog','-g2012','-s','tb','-o',str(cls.path/'test.vvp'),str(source),*map(str,SOURCES)],capture_output=True,text=True,timeout=30)
        if built.returncode:raise RuntimeError(built.stdout+built.stderr)

    def run_case(self,scenario):
        ran=subprocess.run(['vvp',str(self.path/'test.vvp'),f'+case={scenario}'],capture_output=True,text=True,timeout=15)
        self.assertEqual(ran.returncode,0,ran.stdout+ran.stderr)
        rows=[json.loads(line[7:]) for line in ran.stdout.splitlines() if line.startswith('RESULT ')]
        self.assertEqual(len(rows),1,ran.stdout);self.reports[self._testMethodName]=rows[0]

    def test_scattered_pages_full_dma64_exact_host_bytes_guards_and_fences(self):self.run_case(0)
    def test_partial_read_failure_zeroes_full_stream_and_retains_pages(self):self.run_case(1)
    def test_partial_write_failure_never_releases_posted_write_pages(self):self.run_case(2)
    def test_fence_failure_never_releases_pages(self):self.run_case(3)
    def test_stale_key_denied_before_any_descriptor(self):self.run_case(4)
    def test_whole_range_denied_before_first_partial_descriptor(self):self.run_case(5)
    def test_wrong_tag_then_matching_drain_keeps_lease_faulted(self):self.run_case(6)
    def test_disable_retains_stalled_descriptor_and_completes_existing_work(self):self.run_case(7)
    def test_simultaneous_read_write_status_is_not_accepted(self):self.run_case(8)
    def test_unsealed_translation_table_denied_before_dma(self):self.run_case(9)
    def test_nonquiescent_responder_lease_and_held_invalidation_do_not_deadlock(self):self.run_case(10)
    def test_backend_ram_fault_halts_later_page_descriptors_and_retains_pages(self):self.run_case(11)

    @classmethod
    def tearDownClass(cls):
        after={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in cls.paths}
        cls.directory.cleanup()
        if after!=cls.before:raise RuntimeError('paged backend simulation inputs changed')
        if name:=os.environ.get('AS02_RNIC_PAGED_BACKEND_REPORT'):
            target=Path(name)
            if not target.is_absolute():target=ROOT/target
            report=dict(scope='Actual page table/splitter/backend/Corundum RAM, DESCRIPTOR ENGINE MODEL only',
                hardware_verified=False,board_integrated=False,actual_pcie_tlp_engine=False,completion_claim=False,
                pass_test=len(cls.reports)==12,tests=cls.reports,source_sha256=after)
            with target.open('x') as out:out.write(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':unittest.main()
