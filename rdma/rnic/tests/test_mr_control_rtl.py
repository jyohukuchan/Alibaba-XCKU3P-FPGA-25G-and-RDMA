# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual sequencer/MR/PTE RTL; QP/dataplane/parent-drain MODEL only.

No live MMIO, actual PCIe DMA/user pins or full controlled-responder claim.
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
RTL=ROOT/'rdma/rnic/rtl/rocev2_mr_control.v'
SOURCES=[RTL,ROOT/'rdma/rnic/rtl/rocev2_mr_table.v',ROOT/'rdma/rnic/rtl/rocev2_mr_page_table.v']
TB=r'''
`timescale 1ns/1ps
module tb;
// PORTS
rocev2_mr_control ctrl(.*);
reg quiet=1,allow_config=1;
wire table_mr_ready,table_page_ready,table_mr_valid,table_page_valid;
wire [7:0] table_mr_error,table_page_error;
wire [31:0] table_mr_key,table_page_key;
reg inject_key=0;
assign cfg_mr_ready=table_mr_ready && allow_config;
assign cfg_page_ready=table_page_ready && allow_config;
assign cfg_mr_response_valid=table_mr_valid;
assign cfg_mr_response_error=table_mr_error;
assign cfg_mr_response_key=inject_key ? table_mr_key^32'd1 : table_mr_key;
assign cfg_page_response_valid=table_page_valid;
assign cfg_page_response_error=table_page_error;
assign cfg_page_response_key=table_page_key;
assign endpoint_quiescent=quiet && table_mr_ready && table_page_ready && !qp_pending;
assign cfg_qp_ready=quiet && !qp_pending;
reg [3:0] qp_pending=0;
always @(posedge clk) begin
 if(rst) begin qp_pending<=0;endpoint_qp_ready<=0;end
 else if(cfg_qp_valid && cfg_qp_ready) begin qp_pending<=4;endpoint_qp_ready<=0;end
 else if(qp_pending!=0) begin qp_pending<=qp_pending-1'b1;if(qp_pending==1) endpoint_qp_ready<=1;end
end
reg qv=0,pr=0;wire qr,pv;wire [15:0] pt;wire [7:0] pe;wire [63:0] po,pdma;wire [31:0] plen;
reg pqv=0,pmr=0;wire pqr,pmv;wire [15:0] pmt;wire [7:0] pme;wire [63:0] pma;wire [12:0] pml;
reg [31:0] query_key=8;
rocev2_mr_table #(.REQUIRE_EPOCH(1)) mr(
 .clk(clk),.rst(rst),.cfg_quiescent(quiet),.cfg_command(cfg_mr_command),.cfg_index(cfg_mr_index),
 .cfg_pd(cfg_mr_pd),.cfg_key(cfg_mr_key),.cfg_virtual_address(cfg_mr_virtual_address),.cfg_dma_address(64'd0),
 .cfg_length(cfg_mr_length),.cfg_access(cfg_mr_access),.cfg_valid(cfg_mr_valid && allow_config),.cfg_ready(table_mr_ready),
 .cfg_response_error(table_mr_error),.cfg_response_key(table_mr_key),.cfg_response_valid(table_mr_valid),.cfg_response_ready(cfg_mr_response_ready),
 .epoch_configured(),.s_request_pd(16'd17),.s_request_key(query_key),.s_request_address(64'hfedcba9876543000),
 .s_request_length(32'd65),.s_request_operation(3'd3),.s_request_tag(16'd77),.s_request_valid(qv),.s_request_ready(qr),
 .m_response_tag(pt),.m_response_error(pe),.m_response_offset(po),.m_response_dma_address(pdma),
 .m_response_length(plen),.m_response_valid(pv),.m_response_ready(pr));
rocev2_mr_page_table pages(
 .clk(clk),.rst(rst),.cfg_quiescent(quiet),.cfg_command(cfg_page_command),.cfg_slot(cfg_page_slot),.cfg_key(cfg_page_key),
 .cfg_length(cfg_page_length),.cfg_first_offset(cfg_page_first_offset),.cfg_page_index(cfg_page_page_index),.cfg_dma_page(cfg_page_dma_page),
 .cfg_valid(cfg_page_valid && allow_config),.cfg_ready(table_page_ready),.cfg_response_error(table_page_error),
 .cfg_response_key(table_page_key),.cfg_response_valid(table_page_valid),.cfg_response_ready(cfg_page_response_ready),
 .s_query_slot(3'd0),.s_query_key(query_key),.s_query_offset(64'd0),.s_query_length(32'd65),.s_query_tag(16'd77),
 .s_query_valid(pqv),.s_query_ready(pqr),.m_segment_tag(pmt),.m_segment_error(pme),.m_segment_dma_address(pma),
 .m_segment_length(pml),.m_segment_valid(pmv),.m_segment_ready(pmr));
always #2 clk=~clk;
integer cycles=0,scenario=0,dummy,commands=0,mr_commands=0,page_commands=0,qp_commands=0,next_sequence=1;
reg [31:0] last_key=0;
reg rs=0,ms=0,ps=0,qs=0;
reg [186:0] saved_reply;
reg [205:0] saved_mr;
reg [153:0] saved_page;
reg [154:0] saved_qp;
always @(posedge clk) if(!rst) begin
 cycles=cycles+1;if(cycles>10000) $fatal(1,"deadline state=%d fault=%d",ctrl.state,fatal_code);
 if(rs && (!m_valid || {m_command,m_sequence,m_cookie,m_slot,m_key,m_error,m_flags}!==saved_reply)) $fatal(1,"reply ownership");
 if(ms && (!cfg_mr_valid || {cfg_mr_command,cfg_mr_index,cfg_mr_pd,cfg_mr_key,cfg_mr_virtual_address,cfg_mr_length,cfg_mr_access}!==saved_mr)) $fatal(1,"MR valid ownership");
 if(ps && (!cfg_page_valid || {cfg_page_command,cfg_page_slot,cfg_page_key,cfg_page_length,cfg_page_first_offset,cfg_page_page_index,cfg_page_dma_page}!==saved_page)) $fatal(1,"PTE valid ownership");
 if(qs && (!cfg_qp_valid || {cfg_qp_number,cfg_peer_qp_number,cfg_qp_pd,cfg_local_ip,cfg_peer_ip,cfg_rx_psn,cfg_tx_psn}!==saved_qp)) $fatal(1,"QP valid ownership");
 rs=m_valid&&!m_ready;ms=cfg_mr_valid&&!cfg_mr_ready;ps=cfg_page_valid&&!cfg_page_ready;qs=cfg_qp_valid&&!cfg_qp_ready;
 saved_reply={m_command,m_sequence,m_cookie,m_slot,m_key,m_error,m_flags};
 saved_mr={cfg_mr_command,cfg_mr_index,cfg_mr_pd,cfg_mr_key,cfg_mr_virtual_address,cfg_mr_length,cfg_mr_access};
 saved_page={cfg_page_command,cfg_page_slot,cfg_page_key,cfg_page_length,cfg_page_first_offset,cfg_page_page_index,cfg_page_dma_page};
 saved_qp={cfg_qp_number,cfg_peer_qp_number,cfg_qp_pd,cfg_local_ip,cfg_peer_ip,cfg_rx_psn,cfg_tx_psn};
 if(cfg_mr_valid && cfg_mr_ready) mr_commands=mr_commands+1;
 if(cfg_page_valid && cfg_page_ready) page_commands=page_commands+1;
 if(cfg_qp_valid && cfg_qp_ready) qp_commands=qp_commands+1;
 if((cfg_mr_valid || cfg_page_valid || cfg_qp_valid || m_valid || building || tainted || fatal) && !admission_pause) $fatal(1,"publication gate escaped");
end
task submit;
 input integer op;input [63:0] cookie;input [31:0] key;input [7:0] index;input [63:0] dma;
 begin
  @(negedge clk);s_command=op;s_sequence=next_sequence;next_sequence=next_sequence+1;
  s_cookie=cookie;s_slot=0;s_key=key;s_pd=17;s_virtual_address=64'hfedcba9876543000;
  s_length=65;s_access=7;s_first_offset=4093;s_page_index=index;s_dma_page=dma;
  s_qp_number=2;s_peer_qp_number=196;s_local_ip=32'hc6120b02;s_peer_ip=32'hc6120b01;
  s_rx_psn=24'h987654;s_tx_psn=24'hfffffe;s_valid=1;
  @(posedge clk);while(!s_ready) @(posedge clk);
  @(negedge clk);s_valid=0;commands=commands+1;
  // Every caller field may change immediately after the accepted snapshot.
  s_command=0;s_cookie=0;s_key=0;s_pd=0;s_length=0;s_virtual_address=0;s_dma_page=0;
 end
endtask
task response;
 input integer op;input [63:0] cookie;input [31:0] key;input [7:0] error,flags;
 begin
  while(!m_valid) @(negedge clk);
  if(m_command!==op || m_sequence!==next_sequence-1 || m_cookie!==cookie || m_slot!==0 || m_key!==key || m_error!==error || m_flags!==flags)
   $fatal(1,"response op=%d got=%d/%h/%h/%d/%h expected=%d/%h/%h/%d/%h",op,m_command,m_cookie,m_key,m_error,m_flags,op,cookie,key,error,flags);
  last_key=m_key;
  repeat(7) begin @(negedge clk);if(!admission_pause || s_ready) $fatal(1,"response reopened gate");end
  m_ready=1;@(negedge clk);m_ready=0;repeat(2) @(negedge clk);
 end
endtask
task seed;
 input [31:0] floor;
 begin submit(1,99,floor,0,0);response(1,99,floor,0,14);end
endtask
task initialize;
 begin seed(0);submit(6,100,0,0,0);response(6,100,0,0,0);end
endtask
task begin_mr;
 input [63:0] owner;input [31:0] key;
 begin submit(2,owner,0,0,0);response(2,owner,key,0,0);if(building!=1 || !admission_pause) $fatal(1,"BEGIN published early");end
endtask
task load_pages;
 input [63:0] owner;input [31:0] key;
 begin
  submit(3,owner,key,0,64'h8123456789abc000);response(3,owner,key,0,0);
  repeat(19) begin @(negedge clk);if(!admission_pause) $fatal(1,"page-command gap reopened gate");end
  submit(3,owner,key,1,64'hfffffffffffff000);response(3,owner,key,0,0);
 end
endtask
task seal_mr;
 input [63:0] owner;input [31:0] key;
 begin submit(4,owner,key,0,0);response(4,owner,key,0,16);end
endtask
task invalidate;
 input [63:0] owner;input [31:0] key,result;
 begin submit(5,owner,key,0,0);response(5,owner,result,0,3);end
endtask
task query;
 input integer error;
 begin
  @(negedge clk);qv=1;@(posedge clk);while(!qr) @(posedge clk);@(negedge clk);qv=0;
  while(!pv) @(negedge clk);
  if(pe!==error || pt!=77 || (!error && (po!=0 || pdma!=0 || plen!=65))) $fatal(1,"MR authorization not bound");
  pr=1;@(negedge clk);pr=0;
  if(!error) begin
   pqv=1;@(posedge clk);while(!pqr) @(posedge clk);@(negedge clk);pqv=0;
   while(!pmv) @(negedge clk);
   if(pme || pmt!=77 || pma!==64'h8123456789abcffd || pml!=3) $fatal(1,"wrong actual PTE translation");
   pmr=1;@(negedge clk);pmr=0;
  end
 end
endtask
initial begin
 #1 rst=1;dummy=$value$plusargs("case=%d",scenario);parent_dma_drained=1;
 repeat(5) @(negedge clk);rst=0;
 case(scenario)
  0: begin
   initialize;submit(7,101,0,0,0);response(7,101,0,0,0);if(admission_pause) $fatal(1,"RUN did not open");
   begin_mr(42,8);load_pages(42,8);if(!admission_pause) $fatal(1,"last PAGE implicitly published");
   seal_mr(42,8);if(admission_pause || active!=1 || building) $fatal(1,"SEAL did not restore requested RUN");
   query(0);invalidate(42,8,8);query(1);
   begin_mr(43,16);load_pages(43,16);seal_mr(43,16);query_key=8;query(1);query_key=16;query(0);
   invalidate(43,16,16);submit(8,102,0,0,0);response(8,102,0,0,2);if(!admission_pause) $fatal(1,"STOP reopened gate");
  end
  1: begin
   initialize;begin_mr(42,8);
   submit(4,42,8,0,0);response(4,42,8,8'h8a,0);if(!admission_pause || !building) $fatal(1,"incomplete seal released owner");
   submit(3,42,8,0,64'h8123456789abc000);response(3,42,8,0,0);
   submit(3,42,8,0,64'h8123456789abc000);response(3,42,8,8'h89,0);
   invalidate(42,0,8);
  end
  2: begin
   initialize;begin_mr(42,8);load_pages(42,8);seal_mr(42,8);
   submit(5,41,8,0,0);response(5,41,0,8'he2,0);
   submit(5,42,16,0,0);response(5,42,0,8'he2,0);query(0);
   invalidate(42,0,8);
  end
  3: begin
   initialize;quiet=0;parent_dma_drained=0;submit(2,42,0,0,0);
   repeat(30) begin @(negedge clk);if(cfg_mr_valid || cfg_page_valid || m_valid || !admission_pause) $fatal(1,"unproven live drain accepted");end
   quiet=1;repeat(20) begin @(negedge clk);if(cfg_mr_valid || m_valid) $fatal(1,"endpoint quiet substituted for parent drain");end
   parent_dma_drained=1;response(2,42,8,0,0);invalidate(42,0,8);
  end
  4: begin
   initialize;begin_mr(42,8);load_pages(42,8);seal_mr(42,8);submit(5,42,8,0,0);
   while(!cfg_page_response_valid) @(negedge clk);parent_dma_drained=0;
   repeat(25) begin @(negedge clk);if(m_valid || !admission_pause || tainted!=1) $fatal(1,"invalidate synthesized drain proof");end
   parent_dma_drained=1;response(5,42,8,0,3);
  end
  5: begin
   submit(1,99,7,0,0);while(!cfg_mr_response_valid) @(negedge clk);parent_dma_drained=0;
   repeat(25) begin @(negedge clk);if(m_valid || !admission_pause) $fatal(1,"epoch synthesized drain proof");end
   parent_dma_drained=1;response(1,99,7,0,14);
  end
  6: begin
   seed(0);submit(1,100,0,0,0);response(1,100,0,8'he3,0);
   next_sequence=1;submit(8,111,0,0,0);response(8,111,0,8'he1,0);
   next_sequence=3;submit(8,0,0,0,0);response(8,0,0,8'he1,0);
   next_sequence=4;submit(7,112,0,0,0);response(7,112,0,8'he3,0);
  end
  7: begin
   initialize;allow_config=0;submit(2,42,0,0,0);
   // QUIET needs table readiness, not the modeled link's ready gate.
   while(!cfg_mr_valid) @(negedge clk);endpoint_fault=1;
   repeat(12) begin @(negedge clk);if(!cfg_mr_valid || !fatal || !building || m_valid) $fatal(1,"fault withdrew accepted config ownership");end
   allow_config=1;repeat(20) @(negedge clk);
   if(cfg_mr_valid || cfg_page_valid || m_valid || !fatal || !admission_pause || !building) $fatal(1,"faulted config manufactured release");
  end
  8: begin
   initialize;inject_key=1;submit(2,42,0,0,0);
   repeat(25) @(negedge clk);
   if(!fatal || fatal_code!=6 || !building || cfg_page_valid || m_valid || !admission_pause) $fatal(1,"bad allocated key accepted");
  end
  9: begin
   seed(32'h1ffffffe);begin_mr(42,32'hfffffff8);invalidate(42,0,32'hfffffff8);
   submit(2,43,0,0,0);response(2,43,32'hfffffff8,8'h47,0);
   invalidate(43,0,32'hfffffff8);
  end
  10: begin
   initialize;parent_dma_drained=0;submit(5,42,0,0,0);
   repeat(20) begin @(negedge clk);if(m_valid || !admission_pause) $fatal(1,"free slot cleanup skipped real drain");end
   parent_dma_drained=1;response(5,42,0,0,3);
   begin_mr(43,8);load_pages(43,8);seal_mr(43,8);
   submit(5,42,0,0,0);response(5,42,0,8'he2,0);
   invalidate(43,8,8);invalidate(43,8,8);
  end
  default:$fatal(1,"unknown case");
 endcase
 $display("RESULT {\"pass_test\":true,\"scenario\":%0d,\"cycles\":%0d,\"host_commands\":%0d,\"mr_commands\":%0d,\"page_commands\":%0d,\"qp_commands\":%0d,\"fatal\":%0d,\"building\":%0d,\"active\":%0d}",scenario,cycles,commands,mr_commands,page_commands,qp_commands,fatal,building,active);
 $finish;
end
endmodule
'''


class MRControlRTLTests(unittest.TestCase):
    reports={}

    @classmethod
    def setUpClass(cls):
        cls.paths=[*SOURCES,Path(__file__)];cls.before={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in cls.paths}
        ports=RTL.read_text().split('module rocev2_mr_control (',1)[1].split('\n);',1)[0]
        driven=set('cfg_mr_ready cfg_mr_response_error cfg_mr_response_key cfg_mr_response_valid cfg_page_ready cfg_page_response_error cfg_page_response_key cfg_page_response_valid endpoint_quiescent cfg_qp_ready'.split())
        declarations=[]
        for line in ports.splitlines():
            m=re.match(r'\s*(input|output) (?:wire|reg) (.*?)(?:=0)?[,]?$',line)
            if not m:continue
            decl=m[2].rstrip(',');name=decl.split()[-1];input_reg=m[1]=='input' and name not in driven
            declarations.append(('reg ' if input_reg else 'wire ')+decl+('=0;' if input_reg else ';'))
        cls.directory=tempfile.TemporaryDirectory(prefix='as02-mr-control-');cls.path=Path(cls.directory.name)
        p=cls.path/'tb.v';p.write_text(TB.replace('// PORTS','\n'.join(declarations)))
        r=subprocess.run(['iverilog','-g2012','-s','tb','-o',str(cls.path/'test.vvp'),str(p),*map(str,SOURCES)],capture_output=True,text=True,timeout=20)
        if r.returncode:raise RuntimeError(r.stdout+r.stderr)

    def case(self,n):
        r=subprocess.run(['vvp',str(self.path/'test.vvp'),f'+case={n}'],capture_output=True,text=True,timeout=10)
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        rows=[json.loads(l[7:]) for l in r.stdout.splitlines() if l.startswith('RESULT ')]
        self.assertEqual(len(rows),1,r.stdout);self.reports[self._testMethodName]=rows[0]

    def test_publish_translate_drain_reuse_fresh_key_and_stop(self):self.case(0)
    def test_partial_pages_duplicate_and_unsealed_failure_retain_mapping(self):self.case(1)
    def test_wrong_owner_and_key_cannot_revoke_current_mapping(self):self.case(2)
    def test_no_config_before_endpoint_and_real_parent_drain(self):self.case(3)
    def test_invalidation_rechecks_parent_drain_after_both_headers(self):self.case(4)
    def test_epoch_rechecks_parent_drain_after_seed(self):self.case(5)
    def test_epoch_duplicate_stale_sequence_zero_cookie_and_run_order(self):self.case(6)
    def test_fault_retains_stalled_config_then_drains_without_proof(self):self.case(7)
    def test_malformed_allocated_key_quarantines_before_pte_begin(self):self.case(8)
    def test_exhausted_registration_has_owned_cleanup_without_reusing_key(self):self.case(9)
    def test_never_queued_or_already_invalidated_cleanup_requires_real_drain_and_free_slot(self):self.case(10)

    @classmethod
    def tearDownClass(cls):
        after={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in cls.paths};cls.directory.cleanup()
        if after!=cls.before:raise RuntimeError('MR control test sources changed')
        if name:=os.environ.get('AS02_RNIC_MR_CONTROL_REPORT'):
            target=Path(name)
            if not target.is_absolute():target=ROOT/target
            d=dict(scope='Actual MR control/MR/PTE RTL, QP and parent-drain MODEL',pass_test=len(cls.reports)==11,
                hardware_verified=False,board_integrated=False,actual_pcie_tlp_engine=False,completion_claim=False,tests=cls.reports,source_sha256=after)
            with target.open('x') as out:out.write(json.dumps(d,indent=2)+'\n')


if __name__=='__main__':unittest.main()
