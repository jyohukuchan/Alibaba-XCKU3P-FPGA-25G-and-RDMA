# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual SQ CSR/AW-W adapter plus actual SQ controller; backend/guards MODELS.

No actual kernel/MMIO/coherent DMA, native parent/CQ/verbs/page-release proof.
Only public ports are used, including deliberate response-corruption muxes.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

import probe_controlled_pcie as pcie

ROOT=pcie.ROOT
RTL=ROOT/'rdma/rnic/rtl/rocev2_sq_control_regs.v'
HEADER=ROOT/'rdma/rnic/kernel/sq_regs.h'
AXI=ROOT/'external/corundum/fpga/lib/axi/rtl'
SOURCES=[RTL,ROOT/'rdma/rnic/rtl/rocev2_sq_fetch.v',*[AXI/(n+'.v')for n in ['axil_reg_if','axil_reg_if_rd','axil_reg_if_wr']]]
TB=r'''
`timescale 1ns/1ps
module tb;
// ABI
// DECLARATIONS
rocev2_sq_control_regs #(.INITIAL_SEQUENCE(INITIAL_SEQUENCE_VALUE)) dut(.*);
always #2 clk=~clk;
integer cycle=0,configs=0,fetches=0,results=0,i,sequence_number=INITIAL_SEQUENCE_VALUE,scenario,subcase;
reg [31:0] words[0:14],value;
reg block_config=0,allow_backend=0,allow_result=0,inject_response=0,corrupt_qpn=0,corrupt_epoch=0,corrupt_error=0;
wire f_ready,f_response_valid;wire [7:0] f_error;wire [23:0] f_qpn;wire [63:0] f_epoch,f_consumer;
assign cfg_ready=f_ready&&!block_config;
assign cfg_response_valid=f_response_valid||inject_response;
assign cfg_response_error=corrupt_error ? 8'hxx:f_error;
assign cfg_response_qpn=corrupt_qpn ? 24'h800000:f_qpn;
assign cfg_response_epoch=corrupt_epoch ? f_epoch^64'h8000000000000000:f_epoch;
assign cfg_response_consumer=f_consumer;
wire [63:0] address;wire [31:0] length;wire [15:0] tag;wire command_valid;
reg command_ready=0,read_valid=0,status_valid=0;wire read_ready,status_ready;
reg [15:0] status_tag=0;
wire result_valid;wire [511:0] result_data;wire [63:0] result_sequence;
wire [7:0] result_error;wire [23:0] result_qpn;wire [63:0] result_epoch;
wire fetch_fault;wire [7:0] fetch_fault_code;wire [7:0] fetch_active;
reg fetch_enable=1;
rocev2_sq_fetch fetch(
 .clk(clk),.rst(rst),.enable(fetch_enable),
 .cfg_command(cfg_command),.cfg_qpn(cfg_qpn),.cfg_pd(cfg_pd),.cfg_epoch(cfg_epoch),
 .cfg_dma_base(cfg_dma_base),.cfg_log_depth(cfg_log_depth),.cfg_producer(cfg_producer),
 .cfg_valid(cfg_valid&&!block_config),.cfg_ready(f_ready),.cfg_response_error(f_error),
 .cfg_response_qpn(f_qpn),.cfg_response_epoch(f_epoch),.cfg_response_consumer(f_consumer),
 .cfg_response_valid(f_response_valid),.cfg_response_ready(cfg_response_ready),
 .parent_dma_drained(parent_dma_drained),
 .downstream_queue_guard(work_queue_guard|wire_queue_guard|completion_queue_guard),
 .queue_guard(fetch_queue_guard),.queue_active(fetch_active),.queue_halted(),
 .m_command_address(address),.m_command_length(length),.m_command_tag(tag),
 .m_command_valid(command_valid),.m_command_ready(command_ready),
 .s_axis_read_tdata(512'hdeadbeef),.s_axis_read_tkeep(64'hffffffffffffffff),
 .s_axis_read_tlast(1'b1),.s_axis_read_tvalid(read_valid),.s_axis_read_tready(read_ready),
 .s_status_tag(status_tag),.s_status_error(8'd0),.s_status_valid(status_valid),.s_status_ready(status_ready),
 .m_result_data(result_data),.m_result_error(result_error),.m_result_qpn(result_qpn),
 .m_result_pd(),.m_result_epoch(result_epoch),.m_result_sequence(result_sequence),.m_result_tag(),
 .m_result_valid(result_valid),.m_result_ready(allow_result),.busy(),.tag_exhausted(),
 .fault(fetch_fault),.fault_code(fetch_fault_code),.fetch_count(),.result_count());
always @(posedge clk)if(!rst)begin
 cycle=cycle+1;if(cycle>30000)$fatal(1,"CSR deadline scenario%d",scenario);
 if(cfg_valid&&cfg_ready)configs=configs+1;
 if(result_valid&&allow_result)begin
  if(result_data!==512'hdeadbeef || result_error || result_qpn!==7 || result_epoch!==64'h9123456700000001)$fatal(1,"owned fetch result");
  results=results+1;
 end
 if(fetch_fault)$fatal(1,"actual fetch controller fault %h",fetch_fault_code);
end
initial begin: backend_model
 repeat(10)@(negedge clk);
 forever begin
  @(negedge clk);
  if(command_valid&&allow_backend)begin
   if(address!==64'hfedcba9876543000+(fetches%2)*64 || length!==64)$fatal(1,"real fetched address/extent");
   command_ready=1;status_tag=tag;@(posedge clk);@(negedge clk);command_ready=0;fetches=fetches+1;
   repeat(7)@(negedge clk);read_valid=1;status_valid=1;
   @(posedge clk);if(!read_ready||!status_ready)$fatal(1,"actual READ readiness");
   @(negedge clk);read_valid=0;status_valid=0;
  end
 end
end
task write_reg;
 input [11:0] a;input [31:0] d;input [3:0] strobe;
 begin
  fork
   begin @(negedge clk);s_axil_awaddr=a;s_axil_awvalid=1;
    @(posedge clk);while(!s_axil_awready)@(posedge clk);@(negedge clk);s_axil_awvalid=0;end
   begin repeat(3)@(negedge clk);s_axil_wdata=d;s_axil_wstrb=strobe;s_axil_wvalid=1;
    @(posedge clk);while(!s_axil_wready)@(posedge clk);@(negedge clk);s_axil_wvalid=0;end
  join
  while(!s_axil_bvalid)@(negedge clk);
  // Actual axil_reg_if_wr ties BRESP to OKAY even on register timeout.
  // Sticky MMIO status/no mutation, NOT BRESP, diagnoses unknown accesses.
  if(s_axil_bresp!=0)$fatal(1,"unexpected AXI B status");
  repeat(3)begin @(negedge clk);if(!s_axil_bvalid)$fatal(1,"lost B response");end
  s_axil_bready=1;@(posedge clk);@(negedge clk);s_axil_bready=0;
 end
endtask
task read_reg;
 input [11:0] a;output [31:0] d;reg [31:0] held;
 begin
  @(negedge clk);s_axil_araddr=a;s_axil_arvalid=1;
  @(posedge clk);while(!s_axil_arready)@(posedge clk);@(negedge clk);s_axil_arvalid=0;
  while(!s_axil_rvalid)@(negedge clk);held=s_axil_rdata;
  if(s_axil_rresp!=0)$fatal(1,"known SQ CSR read failed");
  repeat(3)begin @(negedge clk);if(!s_axil_rvalid||s_axil_rdata!==held)$fatal(1,"unstable R response");end
  d=held;s_axil_rready=1;@(posedge clk);@(negedge clk);s_axil_rready=0;
 end
endtask
task defaults;
 input integer op;input [63:0] producer,nonce;
 begin
  for(i=0;i<15;i=i+1)words[i]=0;
  words[0]=sequence_number+1;words[1]=op;words[2]=7;words[3]=17;
  words[4]=1;words[5]=32'h91234567;words[6]=32'h89abcdef;words[7]=32'hfedcba98;
  words[8]=32'h76543000;words[9]=32'hfedcba98;words[10]=1;
  words[11]=producer;words[12]=producer>>32;words[13]=nonce;words[14]=nonce>>32;
 end
endtask
task stage_words;
 begin for(i=0;i<15;i=i+1)write_reg(AS02_SQC_STAGE+i*4,words[i],15);end
endtask
task bell;
 begin write_reg(AS02_SQC_DOORBELL,words[0],15);sequence_number=words[0];end
endtask
task reply;
 input [7:0] error_code;input [31:0] flags;
 begin
  while(!response_valid)@(negedge clk);
  read_reg(AS02_SQC_REPLY_ERROR,value);if(value!==error_code)$fatal(1,"reply error actual%d expected%d",value,error_code);
  read_reg(AS02_SQC_REPLY_FLAGS,value);if(value!==flags)$fatal(1,"manufactured/missing proof %h",value);
  for(i=0;i<15;i=i+1)begin read_reg(AS02_SQC_REPLY+i*4,value);if(value!==words[i])$fatal(1,"owned reply word%d",i);end
 end
endtask
task ack;
 begin write_reg(AS02_SQC_REPLY_ACK,sequence_number,15);if(response_valid)$fatal(1,"exact ACK did not retire reply");end
endtask
task allocate;
 begin defaults(1,0,0);stage_words();bell();reply(0,7);ack();if(owner_active!==8'h80||fetch_active!==8'h80)$fatal(1,"actual queue not allocated");end
endtask
task clear_error;
 begin write_reg(AS02_SQC_CLEAR_ERROR,1,15);if(mmio_error)$fatal(1,"idle MMIO error not cleared");end
endtask
initial begin
 scenario=0;subcase=0;i=$value$plusargs("case=%d",scenario);i=$value$plusargs("subcase=%d",subcase);
 rst=0;repeat(2)@(negedge clk);rst=1;parent_dma_drained=1;
 repeat(8)@(negedge clk);rst=0;
 case(scenario)
 0:begin
  read_reg(AS02_SQC_ID,value);if(value!==AS02_SQC_ID_VALUE)$fatal(1,"SQ identity");
  read_reg(AS02_SQC_ABI,value);if(value!==AS02_SQC_ABI_VALUE)$fatal(1,"SQ ABI");
  allocate();
  owner_query_qpn=7;#1;
  if(!owner_query_valid || owner_query_cookie!=={words[7],words[6]} ||
   owner_query_epoch!=={words[5],words[4]} || owner_query_pd!==words[3][15:0])
   $fatal(1,"CQ lookup did not return actual full SQ owner");
  owner_query_qpn=24'h800007;#1;
  if(owner_query_valid || owner_query_cookie || owner_query_epoch || owner_query_pd)
   $fatal(1,"wide CQ owner QPN aliased a real SQ");
  owner_query_qpn=7;
  defaults(2,1,0);stage_words();bell();reply(0,0);ack();
  repeat(8)@(negedge clk);if(fetches||fetch_queue_guard!==8'h80)$fatal(1,"offered fetch ownership");
  defaults(3,1,64'h8123456789abcdef);stage_words();bell();reply(35,0);ack();
  allow_backend=1;while(!result_valid)@(negedge clk);
  if(owner_active!==8'h80 || !fetch_queue_guard[7])$fatal(1,"fetch result released queue");
  repeat(13)@(negedge clk);allow_result=1;@(posedge clk);@(negedge clk);allow_result=0;
  repeat(5)@(negedge clk);defaults(3,1,64'h8123456789abcdef);stage_words();bell();reply(0,31);ack();
  if(owner_active||fetch_active||results!=1||fetches!=1 || owner_query_valid || owner_query_cookie)
   $fatal(1,"actual queue not retired or stale CQ cookie exposed");
 end
 1:begin
  block_config=1;defaults(1,0,0);stage_words();bell();
  if(!cfg_valid||configs||cfg_epoch!==64'h9123456700000001||cfg_dma_base!==64'hfedcba9876543000)$fatal(1,"snapshot offer");
  write_reg(AS02_SQC_STAGE+16,32'hffffffff,15);write_reg(AS02_SQC_STAGE+36,0,15);
  if(cfg_epoch!==64'h9123456700000001||cfg_dma_base!==64'hfedcba9876543000)$fatal(1,"staging changed snapshot");
  write_reg(AS02_SQC_DOORBELL,1,15);if(!mmio_error||!cfg_valid||configs)$fatal(1,"busy bell replaced command");
  block_config=0;reply(0,7);
  write_reg(AS02_SQC_REPLY_ACK,2,15);if(!response_valid)$fatal(1,"wrong ACK released owner");
  ack();clear_error();if(configs!=1)$fatal(1,"duplicate config");
 end
 2:begin
  allocate();defaults(2,1,0);
  case(subcase)
   0:words[2]=32'h80000007;1:words[3]=32'h10011;2:words[4]=2;
   3:words[7]=32'h7edcba98;4:words[9]=32'h7edcba98;5:words[10]=2;
   6:words[11]=2;7:words[13]=1;8:words[2]=32'hxxxxxxx7;
   9:words[8]=32'h76543x00;10:words[13]=32'h0000000x;
   11:words[4]=32'h0000000x;12:words[11]=32'h0000000x;
  endcase
  stage_words();bell();reply(subcase==0||subcase==1||subcase>=8 ? 36:(subcase==6 ? 34:32),0);ack();
  if(configs!=1||fetches||owner_active!==8'h80||fatal)$fatal(1,"bad owner caused config/DMA");
 end
 3:begin
  allocate();defaults(3,0,64'h8123456789abcdef);
  if(subcase>=4)begin
   block_config=1;stage_words();bell();
   case(subcase)4:parent_dma_drained=0;5:work_queue_guard=8'h80;6:wire_queue_guard=8'h80;7:completion_queue_guard=8'h80;endcase
   repeat(5)@(negedge clk);if(!cfg_valid)$fatal(1,"retire offer withdrawn");
   block_config=0;reply(19,0);ack();if(configs!=2||fatal)$fatal(1,"late guard did not reach actual fetcher");
  end else begin
   case(subcase)0:parent_dma_drained=0;1:work_queue_guard=8'h80;2:wire_queue_guard=8'h80;3:completion_queue_guard=8'h80;endcase
   stage_words();bell();reply(35,0);ack();if(configs!=1)$fatal(1,"early guard reached hardware");
  end
  if(owner_active!==8'h80||fetch_active!==8'h80)$fatal(1,"retire bypassed real guard");
 end
 4:begin
  if(subcase==3)begin inject_response=1;repeat(3)@(negedge clk);if(!fatal)$fatal(1,"unsolicited response ignored");end
  else begin
   block_config=1;defaults(1,0,0);stage_words();bell();
   case(subcase)0:corrupt_qpn=1;1:corrupt_epoch=1;2:corrupt_error=1;4:endpoint_fault=1;endcase
   repeat(3)@(negedge clk);if(!cfg_valid)$fatal(1,"accepted offer withdrawn by fault");
   block_config=0;reply(128,0);if(!fatal||owner_tainted!==8'h80)$fatal(1,"uncertain config exposed safe proof");
  end
 end
 5:begin
  defaults(1,0,0);stage_words();write_reg(AS02_SQC_DOORBELL,1,3);
  if(!mmio_error||cfg_valid||configs||last_sequence)$fatal(1,"partial bell executed");clear_error();
  write_reg(AS02_SQC_DOORBELL,2,15);if(!mmio_error||configs)$fatal(1,"wrong sequence executed");clear_error();
  bell();reply(0,7);ack();
  write_reg(AS02_SQC_REPLY_ACK,1,15);if(!mmio_error)$fatal(1,"empty ACK accepted");clear_error();
  write_reg(12'h840,32'hffffffff,15);if(!mmio_error||configs!=1)$fatal(1,"high address alias");clear_error();
  read_reg(AS02_SQC_STAGE,value);if(value!==1)$fatal(1,"unknown address changed staging");
 end
 6:begin
  defaults(1,0,0);
  case(subcase)0:words[8]=32'hffffffe0;1:begin words[8]=32'hffffffc0;words[9]=32'hffffffff;end
   2:words[10]=9;3:words[6]=0;4:begin words[8]=32'hffffff80;words[9]=32'hffffffff;end endcase
  if(subcase==3)words[7]=0;
  stage_words();bell();reply(subcase==4 ? 0:36,subcase==4 ? 7:0);ack();
  if(configs!=(subcase==4))$fatal(1,"full DMA64 ring bound");
 end
 7:begin
  allocate();fetch_enable=0;
  defaults(2,1,0);stage_words();bell();reply(0,0);ack();
  defaults(2,2,0);stage_words();bell();reply(0,0);ack();
  defaults(2,3,0);stage_words();bell();reply(21,0);ack();
  if(owner_active!==8'h80||fatal||fetches)$fatal(1,"ring full error lost ownership");
  defaults(3,2,64'h8123456789abcdef);stage_words();bell();reply(128,0);
  if(!fatal||owner_active!==8'h80||owner_tainted!==8'h80||fetch_active)$fatal(1,"cancelled unfetched tail manufactured retirement proof");
 end
 8:begin
  allocate();read_reg(AS02_SQC_STATUS,value);if(!value[5]||value[0])$fatal(1,"sequence exhaustion not visible");
  defaults(2,1,0);stage_words();write_reg(AS02_SQC_DOORBELL,0,15);
  if(!mmio_error||configs!=1||last_sequence!==32'hffffffff)$fatal(1,"sequence wrapped/reused");
 end
 default:$fatal(1,"bad scenario");
 endcase
 $display("SQC_RESULT {\"pass_test\":true,\"configs\":%0d,\"fetches\":%0d,\"results\":%0d,\"cycles\":%0d}",configs,fetches,results,cycle);$finish;
end
endmodule
'''


class SQControlRegsTests(unittest.TestCase):
    reports={}

    def simulate(self,scenario,subcase=0):
        inputs=[*SOURCES,HEADER,Path(__file__).resolve(),Path(pcie.__file__).resolve()]
        before={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in inputs}
        ports=re.findall(r'\b(input|output)\s+(?:wire|reg)\s+(?:\[([^]]+)\]\s+)?(\w+)',RTL.read_text().split('\n);',1)[0])
        driven={'cfg_ready','cfg_response_error','cfg_response_qpn','cfg_response_epoch','cfg_response_consumer','cfg_response_valid','fetch_queue_guard'}
        decl='\n'.join(pcie.declaration(n,pcie.width(e,dict(ADDR_WIDTH=12,MAX_QPS=8)),'reg'if d=='input'and n not in driven else'wire')for d,e,n in ports)
        macros='\n'.join('localparam '+n+'='+re.sub(r'([0-9a-fA-F]+)U$',r'\1',v).replace('0x',"32'h")+';'for n,v in re.findall(r'^#define (AS02_SQC_\w+) (\w+)',HEADER.read_text(),re.M))
        bench=TB.replace('// ABI',macros).replace('// DECLARATIONS',decl).replace('INITIAL_SEQUENCE_VALUE',"32'hfffffffe"if scenario==8 else'0')
        with tempfile.TemporaryDirectory(prefix='as02-sq-csr-')as directory:
            run=Path(directory);(run/'tb.v').write_text(bench)
            c=subprocess.run(['iverilog','-g2012','-s','tb','-o',str(run/'test.vvp'),str(run/'tb.v'),*map(str,SOURCES)],capture_output=True,text=True,timeout=20)
            self.assertEqual(c.returncode,0,c.stdout+c.stderr)
            s=subprocess.run(['vvp',str(run/'test.vvp'),f'+case={scenario}',f'+subcase={subcase}'],capture_output=True,text=True,timeout=10)
            self.assertEqual(s.returncode,0,s.stdout+s.stderr);self.assertNotIn('ERROR:',s.stdout+s.stderr)
            rows=[json.loads(l[11:])for l in s.stdout.splitlines()if l.startswith('SQC_RESULT ')]
            self.assertEqual(len(rows),1,s.stdout);self.assertTrue(rows[0]['pass_test'])
        self.assertEqual(before,{n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest()for n in before})
        self.reports.setdefault(self._testMethodName,[]).append(dict(summary=rows[0],source_sha256=before,bench_sha256=hashlib.sha256(bench.encode()).hexdigest()))

    def test_actual_fetch_allocation_post_result_and_owned_retirement(self):self.simulate(0)
    def test_immutable_stalled_snapshot_and_exact_owned_reply_ACK(self):self.simulate(1)
    def test_full_owner_reserved_fields_producer_and_unknown_values_before_mutation(self):
        for n in range(13):
            with self.subTest(n=n):self.simulate(2,n)
    def test_parent_work_wire_and_completion_guards_block_retirement(self):
        for n in range(8):
            with self.subTest(n=n):self.simulate(3,n)
    def test_bad_response_context_unknown_error_unsolicited_response_or_parent_fault(self):
        for n in range(5):
            with self.subTest(n=n):self.simulate(4,n)
    def test_AXI_strobes_sequence_unknown_addresses_and_ACK_errors_no_side_effects(self):self.simulate(5)
    def test_DMA64_ring_bounds_exclusive_end_and_full_shape(self):
        for n in range(5):
            with self.subTest(n=n):self.simulate(6,n)
    def test_actual_ring_full_and_cancelled_unfetched_tail_are_NOT_WR_completion(self):self.simulate(7)
    def test_control_sequence_exhaustion_never_wraps(self):self.simulate(8)

    @classmethod
    def tearDownClass(cls):
        destination=os.environ.get('AS02_SQC_UNIT_REPORT')
        if destination:
            report=dict(scope=__doc__,pass_test=len(cls.reports)==9 and sum(map(len,cls.reports.values()))==36,
                methods=len(cls.reports),simulations=sum(map(len,cls.reports.values())),tests=cls.reports,
                actual_SQ_control_AW_W_and_fetch=True,backend_and_guard_models=True,hardware_verified=False,
                registered_kernel_provider_or_verbs=False,native_parent_mapping=False,RDMA_completion_or_unpin_proof=False)
            with (ROOT/destination).open('x')as out:json.dump(report,out,indent=2);out.write('\n')


if __name__=='__main__':unittest.main()
