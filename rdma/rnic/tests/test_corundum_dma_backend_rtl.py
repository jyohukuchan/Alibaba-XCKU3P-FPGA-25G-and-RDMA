# SPDX-License-Identifier: BSD-2-Clause-Views
"""Real backend + Corundum AXIS DMA clients/RAM, descriptor-engine MODEL.

No actual PCIe TLP engine, hardware, pinned pages, or native DMA is claimed.
Posted writes remain invisible in the model until the readback fence executes.
All staging data traverses real segmented RAM ports; no DUT memory forcing.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[3]
RTL=ROOT/'rdma/rnic/rtl/rocev2_corundum_dma_backend.v'
PCIE=ROOT/'external/corundum/fpga/lib/pcie/rtl'
SOURCES=[RTL]+[PCIE/name for name in ('dma_client_axis_sink.v','dma_client_axis_source.v','dma_psdpram.v')]
SOURCES.append(ROOT/'external/corundum/fpga/lib/axis/rtl/axis_register.v')

TB=r'''
`timescale 1ns/1ps
module tb;
localparam RAM_ADDR_WIDTH=16,SEG_COUNT=2,SEG_DATA_WIDTH=256,SEG_BE_WIDTH=32,
 SEG_ADDR_WIDTH=RAM_ADDR_WIDTH-6,RAM_SEL_WIDTH=4,DMA_LEN_WIDTH=16,TAG_WIDTH=16;
// PORT_DECLARATIONS
rocev2_corundum_dma_backend #(.RAM_ADDR_WIDTH(RAM_ADDR_WIDTH),.SEG_ADDR_WIDTH(SEG_ADDR_WIDTH)) dut(.*);
always #2 clk=~clk;
reg [7:0] host[0:16383],posted[0:8191];
reg [63:0] pending_address=0;
integer pending_length=0;
reg posted_pending=0;
integer scenario=0,dummy,cycle=0,seed=17,read_position=0,writes=0,reads=0,statuses=0;
integer expected_read_length=0,expected_read_zero=0,streamed_read_bytes=0;
integer m,j,k,start,amount,word,seg,byte_index,base_index,issued_tag,issued_length,ram_address,deadline;
integer current_tag=1,current_length=0,current_offset=0,old_completions;
reg [1:0] mask,done_mask;
reg [63:0] issued_address;
reg [31:0] rng=32'h455a444d;
reg rstalled=0,wstalled=0,ostalled=0,sstalled=0;
reg [127:0] saved_rdesc,saved_wdesc;
reg [576:0] saved_output;
reg [23:0] saved_status;
function [7:0] pattern;
 input integer i;
 begin pattern=(i*179)^(i>>7)^seed^8'hd3;end
endfunction
function [63:0] keep;
 input integer i;
 begin keep=i>=64 ? 64'hffffffffffffffff : (64'h1<<i)-1;end
endfunction
always @(negedge clk) if(!rst) begin
 rng={rng[30:0],rng[31]^rng[21]^rng[1]^rng[0]};m_axis_read_tready=rng[2:0]!=0;
end
always @(posedge clk) if(!rst) begin
 cycle=cycle+1;if(cycle>30000) $fatal(1,"deadline scenario=%d fault=%b/%d",scenario,fault,fault_code);
 if(dma_drained && (dma_ram_wr_cmd_valid || dma_ram_rd_cmd_valid || s_dma_read_status_valid || s_dma_write_status_valid ||
    dut.wr_pending[0] || dut.wr_pending[1] || dut.rd_pending[0] || dut.rd_pending[1] || !(&dut.ram_pending_empty)))
  $fatal(1,"public drain advanced past registered/old pending proof or current external offer");
 if(rstalled && (!m_dma_read_valid || {m_dma_read_address,m_dma_read_length,m_dma_read_tag,m_dma_read_ram_address,m_dma_read_ram_sel}!==saved_rdesc)) $fatal(1,"read descriptor unstable");
 if(wstalled && (!m_dma_write_valid || {m_dma_write_address,m_dma_write_length,m_dma_write_tag,m_dma_write_ram_address,m_dma_write_ram_sel}!==saved_wdesc)) $fatal(1,"write descriptor unstable");
 if(ostalled && (!m_axis_read_tvalid || {m_axis_read_tlast,m_axis_read_tkeep,m_axis_read_tdata}!==saved_output)) $fatal(1,"read output unstable");
 if(sstalled && (!m_status_valid || {m_status_error,m_status_tag}!==saved_status)) $fatal(1,"status unstable");
 rstalled=m_dma_read_valid&&!m_dma_read_ready;wstalled=m_dma_write_valid&&!m_dma_write_ready;
 ostalled=m_axis_read_tvalid&&!m_axis_read_tready;sstalled=m_status_valid&&!m_status_ready;
 saved_rdesc={m_dma_read_address,m_dma_read_length,m_dma_read_tag,m_dma_read_ram_address,m_dma_read_ram_sel};
 saved_wdesc={m_dma_write_address,m_dma_write_length,m_dma_write_tag,m_dma_write_ram_address,m_dma_write_ram_sel};
 saved_output={m_axis_read_tlast,m_axis_read_tkeep,m_axis_read_tdata};saved_status={m_status_error,m_status_tag};
 if(m_axis_read_tvalid && m_axis_read_tready) begin
  if(m_axis_read_tkeep!==keep(expected_read_length-read_position) || m_axis_read_tlast!==(read_position+64>=expected_read_length)) $fatal(1,"bad READ shape");
  for(m=0;m<64;m=m+1) if(m_axis_read_tkeep[m]) begin
   if(m_axis_read_tdata[m*8+:8] !== (expected_read_zero ? 8'd0 : pattern(read_position+m))) $fatal(1,"READ payload mismatch pos=%d",read_position+m);
   streamed_read_bytes=streamed_read_bytes+1;
  end
  read_position=read_position+64;
 end
 if(m_status_valid && m_status_ready) statuses=statuses+1;
end
task command;
 input integer write_op,length,offset,tag;
 begin
  @(negedge clk);s_command_write=write_op;s_command_address=64'h8123456789abc000+offset;
  s_command_length=length;s_command_tag=tag;s_command_valid=1;
  @(posedge clk);while(!s_command_ready) @(posedge clk);
  @(negedge clk);s_command_valid=0;
 end
endtask
task send_payload;
 input integer length;
 integer pos,lane;
 begin
  for(pos=0;pos<length;pos=pos+64) begin
   @(negedge clk);s_axis_write_tdata=0;s_axis_write_tkeep=keep(length-pos);s_axis_write_tlast=pos+64>=length;
   for(lane=0;lane<64;lane=lane+1) if(pos+lane<length) s_axis_write_tdata[lane*8+:8]=pattern(pos+lane);
   s_axis_write_tvalid=1;
   @(posedge clk);while(!s_axis_write_tready) @(posedge clk);
  end
  @(negedge clk);s_axis_write_tvalid=0;
 end
endtask
task dma_read_accept;
 input integer expected_length,expected_ram,expected_tag,offset;
 begin
  deadline=cycle+1000;while(!m_dma_read_valid && cycle<deadline) @(negedge clk);
  if(!m_dma_read_valid || m_dma_read_address!==64'h8123456789abc000+offset ||
     m_dma_read_length!==expected_length || m_dma_read_ram_address!==expected_ram || m_dma_read_ram_sel!==0 || m_dma_read_tag!==expected_tag)
   $fatal(1,"wrong full-width DMA read/fence descriptor %h/%d/%d",m_dma_read_address,m_dma_read_length,m_dma_read_ram_address);
  repeat(7) @(negedge clk);
  if(m_status_valid) $fatal(1,"status before DMA read/fence accepted");
  issued_length=m_dma_read_length;issued_tag=m_dma_read_tag;issued_address=m_dma_read_address;ram_address=m_dma_read_ram_address;
  m_dma_read_ready=1;@(posedge clk);@(negedge clk);m_dma_read_ready=0;reads=reads+1;
 end
endtask
task dma_fill_ram;
 // Model Corundum host-read completion placement through REAL RAM ports.
 begin
  base_index=issued_address-64'h8123456789abc000;
  for(start=0;start<issued_length;start=start+64) begin
   @(negedge clk);dma_ram_wr_cmd_data=0;dma_ram_wr_cmd_be=0;dma_ram_wr_cmd_addr=0;mask=0;
   for(seg=0;seg<2;seg=seg+1) begin
    dma_ram_wr_cmd_addr[seg*SEG_ADDR_WIDTH+:SEG_ADDR_WIDTH]=(ram_address+start)/64;
    for(byte_index=0;byte_index<32;byte_index=byte_index+1) begin
     j=seg*32+byte_index;
     if(start+j<issued_length) begin
      mask[seg]=1;dma_ram_wr_cmd_be[j]=1;dma_ram_wr_cmd_data[j*8+:8]=host[base_index+start+j];
     end
    end
   end
   dma_ram_wr_cmd_valid=mask;
   @(posedge clk);while((dma_ram_wr_cmd_ready&mask)!=mask) @(posedge clk);
   @(negedge clk);dma_ram_wr_cmd_valid=0;
   if((dma_ram_wr_done&mask)!=mask) $fatal(1,"RAM write did not commit");
  end
  repeat(4) @(negedge clk);
 end
endtask
task read_status;
 input integer error,tag;
 begin
  @(negedge clk);s_dma_read_status_error=error;s_dma_read_status_tag=tag;s_dma_read_status_valid=1;
  @(negedge clk);s_dma_read_status_valid=0;
 end
endtask
task dma_write_post;
 input integer length,offset,tag,error;
 begin
  deadline=cycle+1000;while(!m_dma_write_valid && cycle<deadline) @(negedge clk);
  if(!m_dma_write_valid || m_dma_write_address!==64'h8123456789abc000+offset || m_dma_write_length!==length ||
     m_dma_write_tag!==tag || m_dma_write_ram_address!==0 || m_dma_write_ram_sel!==0 || m_dma_write_imm_en || m_dma_write_imm!=0)
   $fatal(1,"wrong full-width DMA write descriptor");
  repeat(7) @(negedge clk);
  if(m_status_valid) $fatal(1,"status before write DMA");
  m_dma_write_ready=1;@(posedge clk);@(negedge clk);m_dma_write_ready=0;writes=writes+1;
  for(start=0;start<length;start=start+64) begin
   @(negedge clk);mask=0;dma_ram_rd_cmd_addr=0;
   for(seg=0;seg<2;seg=seg+1) begin
    if(start+seg*32<length) mask[seg]=1;
    dma_ram_rd_cmd_addr[seg*SEG_ADDR_WIDTH+:SEG_ADDR_WIDTH]=start/64;
   end
   dma_ram_rd_cmd_valid=mask;@(posedge clk);while((dma_ram_rd_cmd_ready&mask)!=mask) @(posedge clk);
   @(negedge clk);dma_ram_rd_cmd_valid=0;
   while((dma_ram_rd_resp_valid&mask)!=mask) @(negedge clk);
   repeat(3) begin @(negedge clk);if((dma_ram_rd_resp_valid&mask)!=mask) $fatal(1,"RAM response lost under backpressure");end
   for(j=0;j<64;j=j+1) if(start+j<length) begin
    posted[start+j]=dma_ram_rd_resp_data[j*8+:8];
    if(posted[start+j]!==pattern(start+j)) $fatal(1,"WRITE payload not in actual staging RAM pos=%d",start+j);
   end
   dma_ram_rd_resp_ready=mask;@(negedge clk);dma_ram_rd_resp_ready=0;
  end
  pending_address=64'h8123456789abc000+offset;pending_length=length;posted_pending=error==0;
  repeat(4) @(negedge clk);
  s_dma_write_status_tag=tag;s_dma_write_status_error=error;s_dma_write_status_valid=1;
  @(negedge clk);s_dma_write_status_valid=0;
 end
endtask
task fence;
 input integer offset,tag,error;
 begin
  dma_read_accept(1,8128,tag,offset);
  if(!posted_pending) $fatal(1,"fence before posted write");
  repeat(25) begin @(negedge clk);if(m_status_valid) $fatal(1,"WRITE completed before read fence returned");end
  // Explicit model assumption: ordered same-function/TC attr0 read cannot
  // bypass earlier posted writes. Real PCIe engine/link proof is still needed.
  base_index=pending_address-64'h8123456789abc000;
  for(k=0;k<pending_length;k=k+1) host[base_index+k]=posted[k];
  posted_pending=0;
  if(error==0) dma_fill_ram;
  read_status(error,tag);
 end
endtask
task completion;
 input integer tag,error;
 begin
  deadline=cycle+1000;while(!m_status_valid && cycle<deadline) @(negedge clk);
  if(!m_status_valid || m_status_tag!==tag || m_status_error!==error || !dma_drained) $fatal(1,"wrong completion %d/%d drained=%b",m_status_tag,m_status_error,dma_drained);
  repeat(7) @(negedge clk);m_status_ready=1;@(negedge clk);m_status_ready=0;
  repeat(3) @(negedge clk);
  if(error==0 && (!idle || fault)) $fatal(1,"success failed recovery");
  if(error!=0 && (!fault || idle || s_command_ready)) $fatal(1,"DMA failure did not hold fault");
 end
endtask
task pair;
 input integer length,offset;
 begin
  for(k=0;k<16384;k=k+1) host[k]=(k*37)^8'h5a;
  seed=length^offset^current_tag;old_completions=completion_count;
  command(1,length,offset,current_tag);send_payload(length);
  dma_write_post(length,offset,current_tag,0);fence(offset,current_tag,0);completion(current_tag,0);
  for(k=0;k<16384;k=k+1)
   if(host[k] !== ((k>=offset && k<offset+length) ? pattern(k-offset) : (((k*37)^8'h5a)&255))) $fatal(1,"host bytes/guard mismatch at%d",k);
  current_tag=current_tag+1;expected_read_length=length;expected_read_zero=0;read_position=0;
  command(0,length,offset,current_tag);dma_read_accept(length,0,current_tag,offset);
  dma_fill_ram;read_status(0,current_tag);completion(current_tag,0);
  if(read_position<length || completion_count!=old_completions+2) $fatal(1,"missing stream/completion");
  current_tag=current_tag+1;
 end
endtask
initial begin
 #1 rst=1;dummy=$value$plusargs("case=%d",scenario);
 repeat(5) @(negedge clk);rst=0;enable=1;
 case(scenario)
  0: begin pair(1,1);pair(31,7);pair(32,31);pair(63,63);pair(64,4095);pair(65,4096);pair(4095,4097);pair(4096,8191);end
  1: begin
   // Real staging RAM still contains prior data; failed read MUST drain zero,
   // not disclose that stale data, and produce only an ERROR status.
   pair(65,63);expected_read_length=65;expected_read_zero=1;read_position=0;
   command(0,65,63,current_tag);dma_read_accept(65,0,current_tag,63);read_status(4,current_tag);completion(current_tag,4);
  end
  2: begin command(1,65,7,1);send_payload(65);dma_write_post(65,7,1,2);completion(1,2);if(reads!=0 || fence_count!=0) $fatal(1,"fence after failed write");end
  3: begin command(1,65,7,1);send_payload(65);dma_write_post(65,7,1,0);fence(7,1,4);completion(1,4);end
  4: begin
   command(0,65,7,1);dma_read_accept(65,0,1,7);read_status(0,2);
   repeat(5) @(negedge clk);if(!fault || fault_code!=4 || dma_drained || m_status_valid) $fatal(1,"wrong tag released live DMA");
   for(k=0;k<16384;k=k+1) host[k]=0;dma_fill_ram;read_status(0,1);
   repeat(5) @(negedge clk);if(!fault || !dma_drained || idle || m_status_valid) $fatal(1,"failed to drain retained DMA/fault");
  end
  5: begin
   command(0,1,7,1);dma_read_accept(1,0,1,7);
   dma_ram_wr_cmd_addr=20'h00100;dma_ram_wr_cmd_be=1;dma_ram_wr_cmd_valid=1;
   @(negedge clk);if(dma_ram_wr_cmd_ready&dma_ram_wr_cmd_valid) $fatal(1,"high RAM address aliased");
   @(negedge clk);dma_ram_wr_cmd_valid=0;
   repeat(3) @(negedge clk);if(!fault || fault_code!=5 || dma_drained) $fatal(1,"unbounded RAM write not held");
  end
  6: begin
   command(0,1,7,1);dma_read_accept(1,0,1,7);
   dma_ram_wr_cmd_be=2;dma_ram_wr_cmd_valid=1;
   @(negedge clk);if(dma_ram_wr_cmd_ready&dma_ram_wr_cmd_valid) $fatal(1,"RAM byte beyond descriptor accepted");
   @(negedge clk);dma_ram_wr_cmd_valid=0;
   repeat(3) @(negedge clk);if(!fault || fault_code!=5 || dma_drained) $fatal(1,"RAM overflow not held");
  end
  7: begin command(1,0,7,1);repeat(5) @(negedge clk);if(!fault || fault_code!=1 || m_dma_write_valid || m_dma_read_valid) $fatal(1,"bad length allowed");end
  8: begin
   command(1,65,7,1);repeat(5) @(negedge clk);
   s_axis_write_tkeep=1;s_axis_write_tlast=1;s_axis_write_tvalid=1;
   repeat(3) @(negedge clk);s_axis_write_tvalid=0;
   if(!fault || fault_code!=2 || m_dma_write_valid) $fatal(1,"bad data issued host write");
  end
  9: begin
   command(1,65,7,1);send_payload(65);
   while(!m_dma_write_valid) @(negedge clk);enable=0;
   repeat(9) @(negedge clk);dma_write_post(65,7,1,0);fence(7,1,0);completion(1,0);
   if(s_command_ready) $fatal(1,"disabled endpoint admits new command");
  end
  10: begin command(1,65,7,0);repeat(5) @(negedge clk);if(!fault || fault_code!=1 || m_dma_write_valid || m_dma_read_valid) $fatal(1,"zero tag allowed");end
  11: begin command(1,8129,7,1);repeat(5) @(negedge clk);if(!fault || fault_code!=1 || m_dma_write_valid || m_dma_read_valid) $fatal(1,"RAM-overflowing command allowed");end
  12: begin
   @(negedge clk);s_command_write=1;s_command_address=64'hfffffffffffffff0;s_command_length=65;s_command_tag=1;s_command_valid=1;
   @(posedge clk);while(!s_command_ready) @(posedge clk);
   @(negedge clk);s_command_valid=0;
   repeat(5) @(negedge clk);if(!fault || fault_code!=1 || m_dma_write_valid || m_dma_read_valid) $fatal(1,"DMA address overflow allowed");
  end
  13,14,15,16: begin
   repeat(3)@(negedge clk);if(!dma_drained || fault)$fatal(1,"idle initial drain proof");
   // No descriptor is outstanding. An unsolicited offer must immediately
   // withdraw the PUBLIC drain proof, before the sequential fault is set.
   case(scenario)
    13:dma_ram_wr_cmd_valid=1;
    14:dma_ram_rd_cmd_valid=1;
    15:s_dma_read_status_valid=1;
    16:s_dma_write_status_valid=1;
   endcase
   #0.1;if(dma_drained || fault)$fatal(1,"unsolicited offer bypassed combinational drain guard");
   repeat(3)@(negedge clk);
   if(!fault || dma_drained || m_status_valid || fault_code!=(scenario<15 ? 5 : 4))$fatal(1,"unsolicited offer did not retain fault/proof");
   dma_ram_wr_cmd_valid=0;dma_ram_rd_cmd_valid=0;s_dma_read_status_valid=0;s_dma_write_status_valid=0;
   repeat(3)@(negedge clk);
   if(!fault || idle || m_status_valid || s_command_ready)$fatal(1,"physical drain falsely cleared sticky ownership fault");
  end
  default:$fatal(1,"unknown scenario");
 endcase
 $display("RESULT {\"pass_test\":true,\"scenario\":%0d,\"cycles\":%0d,\"commands\":%0d,\"fences\":%0d,\"completions\":%0d,\"dma_reads\":%0d,\"dma_writes\":%0d,\"read_bytes\":%0d,\"fault\":%0d,\"fault_code\":%0d}",scenario,cycle,command_count,fence_count,completion_count,reads,writes,streamed_read_bytes,fault,fault_code);
 $finish;
end
endmodule
'''


class CorundumDMABackendTests(unittest.TestCase):
    reports={}

    @classmethod
    def setUpClass(cls):
        cls.before={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in SOURCES+[Path(__file__)]}
        declarations=[]
        ports=RTL.read_text().split(')(\n',1)[1].split('\n);',1)[0]
        for line in ports.splitlines():
            match=re.match(r'\s*(input|output) (?:wire|reg) (.*?)(?:=0)?[,]?$',line)
            if match:
                value=match[2].rstrip(',');declarations.append(('reg ' if match[1]=='input' else 'wire ')+value+('=0;' if match[1]=='input' else ';'))
        cls.directory=tempfile.TemporaryDirectory(prefix='as02-corundum-backend-');cls.path=Path(cls.directory.name)
        for address_width in (16,15):
            tb=TB.replace('// PORT_DECLARATIONS','\n'.join(declarations)).replace('RAM_ADDR_WIDTH=16',f'RAM_ADDR_WIDTH={address_width}')
            source=cls.path/f'tb{address_width}.v';source.write_text(tb)
            built=subprocess.run(['iverilog','-g2012','-s','tb','-o',str(cls.path/f'test{address_width}.vvp'),str(source),*map(str,SOURCES)],capture_output=True,text=True,timeout=30)
            if built.returncode:raise RuntimeError(built.stdout+built.stderr)

    def run_case(self,scenario,address_width=16):
        ran=subprocess.run(['vvp',str(self.path/f'test{address_width}.vvp'),f'+case={scenario}'],capture_output=True,text=True,timeout=15)
        self.assertEqual(ran.returncode,0,ran.stdout+ran.stderr)
        rows=[json.loads(line[7:]) for line in ran.stdout.splitlines() if line.startswith('RESULT ')]
        self.assertEqual(len(rows),1,ran.stdout);self.reports[self._testMethodName]=rows[0]

    def test_exact_data_boundaries_guards_unaligned_addresses_and_fences(self):self.run_case(0)
    def test_failed_read_drains_zero_not_stale_ram(self):self.run_case(1)
    def test_failed_write_has_error_without_fence_or_success(self):self.run_case(2)
    def test_failed_fence_never_successfully_completes(self):self.run_case(3)
    def test_wrong_status_tag_retains_and_later_drains_dma(self):self.run_case(4)
    def test_ram_high_address_cannot_alias_staging(self):self.run_case(5)
    def test_ram_byte_outside_issued_extent_rejected(self):self.run_case(6)
    def test_invalid_command_never_issues_dma(self):self.run_case(7)
    def test_bad_write_shape_never_issues_host_dma(self):self.run_case(8)
    def test_disable_only_stops_new_work_not_stalled_descriptor(self):self.run_case(9)
    def test_zero_tag_never_issues_dma(self):self.run_case(10)
    def test_command_exceeding_staging_never_issues_dma(self):self.run_case(11)
    def test_full64_dma_address_overflow_never_issues_dma(self):self.run_case(12)
    def test_actual_board_15bit_ram_geometry_all_payload_boundaries(self):self.run_case(0,15)
    def test_unsolicited_RAM_write_blocks_drain_before_fault_clock(self):self.run_case(13)
    def test_unsolicited_RAM_read_blocks_drain_before_fault_clock(self):self.run_case(14)
    def test_unsolicited_DMA_read_status_blocks_drain_before_fault_clock(self):self.run_case(15)
    def test_unsolicited_DMA_write_status_blocks_drain_before_fault_clock(self):self.run_case(16)

    @classmethod
    def tearDownClass(cls):
        after={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in SOURCES+[Path(__file__)]}
        cls.directory.cleanup()
        if after!=cls.before:raise RuntimeError('backend simulation inputs changed')
        if name:=os.environ.get('AS02_RNIC_DMA_BACKEND_REPORT'):
            target=Path(name)
            if not target.is_absolute():target=ROOT/target
            report=dict(scope='Actual Corundum RAM/source/sink/backend RTL with DESCRIPTOR ENGINE MODEL, not PCIe/native DMA',
                hardware_verified=False,board_integrated=False,actual_pcie_tlp_engine=False,completion_claim=False,
                pass_test=len(cls.reports)==18,tests=cls.reports,source_sha256=after)
            with target.open('x') as out:out.write(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':unittest.main()
