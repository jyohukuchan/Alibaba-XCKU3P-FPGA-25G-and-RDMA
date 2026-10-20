# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual C-encoded WQE -> actual admission RTL -> actual MR-table checks.

Queue fetch/host/PCIe/page execution/CQE/provider are NOT implemented here.
Only external response ports are corrupted for negative ownership tests;
no internal forcing, software authorization substitute or fake drain.
"""
import ctypes as C
from pathlib import Path
import subprocess
import tempfile
import unittest

import test_wqe_codec as codec

ROOT=Path(__file__).resolve().parents[3]
RTL=ROOT/'rdma/rnic/rtl'
KERNEL=ROOT/'rdma/rnic/kernel'
BASE=0xf123456789abc000
SEQ=0xf123456700000001
EPOCH=0x9123456700000001
KEY=0x80000008

TB=r'''
`timescale 1ns/1ps
module tb;
reg clk=0;always #2 clk=~clk;
reg rst=1,enable=0,cfg_idle=0;
reg [511:0] wd=0;reg [63:0] wk=0;reg wl=0,wv=0;wire wr;
reg cv=1;reg [23:0] cq=1;reg [15:0] cp=7,ct=16'hf123;
reg [63:0] cs=64'hf123456700000001,ce=64'h9123456700000001;
wire [15:0] qpd,qt;wire [31:0] qkey,qlen;wire [63:0] qa;
wire [2:0] qop;wire qv,qr;
wire [15:0] rt;wire [7:0] re;wire [63:0] ro;wire [31:0] rlen;wire rv,rr;
reg allow_q=1,allow_r=1;reg [1:0] corrupt=0;
wire [63:0] oid,oseq,oepoch,ola,ooff,ora;
wire [23:0] oq;wire [15:0] opd,ot,oop,oflags;
wire [31:0] olen,olk,ork;wire [7:0] oe;wire ov,authorized,busy,guard,fault;
wire [7:0] fault_code;reg ready=0;
wire [575:0] output_fields={oid,oseq,oepoch,oq,opd,ot,oop,oflags,olen,olk,ola,ooff,ora,ork,oe};
wire [162:0] query_fields={qpd,qkey,qa,qlen,qop,qt};
reg cfg_valid=0,cfg_response_ready=0;
reg [1:0] cfg_command=0;reg [2:0] cfg_index=0;reg [15:0] cfg_pd=7;
reg [31:0] cfg_key=0;reg [63:0] cfg_va=0,cfg_len=0;reg [3:0] cfg_access=0;
wire cfg_ready,cfg_response_valid,configured;wire [7:0] cfg_error;wire [31:0] cfg_result;
rocev2_wqe_admission dut(
 .clk(clk),.rst(rst),.enable(enable),.configuration_idle(cfg_idle),
 .s_wqe_data(wd),.s_wqe_keep(wk),.s_wqe_last(wl),.s_wqe_valid(wv),.s_wqe_ready(wr),
 .s_context_valid(cv),.s_context_qpn(cq),.s_context_pd(cp),.s_context_tag(ct),.s_context_sequence(cs),.s_context_epoch(ce),
 .m_mr_request_pd(qpd),.m_mr_request_key(qkey),.m_mr_request_address(qa),.m_mr_request_length(qlen),
 .m_mr_request_operation(qop),.m_mr_request_tag(qt),.m_mr_request_valid(qv),.m_mr_request_ready(qr&&allow_q),
 .s_mr_response_tag(corrupt==1 ? rt^16'h0001 : rt),.s_mr_response_error(corrupt==3 ? 8'hff : re),
 .s_mr_response_offset(ro),.s_mr_response_length(corrupt==2 ? rlen+32'd1 : rlen),
 .s_mr_response_valid(rv&&allow_r),.s_mr_response_ready(rr),
 .m_work_wr_id(oid),.m_work_sequence(oseq),.m_work_epoch(oepoch),.m_work_qpn(oq),.m_work_pd(opd),.m_work_tag(ot),
 .m_work_opcode(oop),.m_work_flags(oflags),.m_work_length(olen),.m_work_local_key(olk),.m_work_local_address(ola),
 .m_work_local_offset(ooff),.m_work_remote_address(ora),.m_work_remote_key(ork),.m_work_error(oe),
 .m_work_authorized(authorized),.m_work_valid(ov),.m_work_ready(ready),.busy(busy),.configuration_guard(guard),
 .fault(fault),.fault_code(fault_code));
rocev2_mr_table #(.REQUIRE_EPOCH(1)) mr(
 .clk(clk),.rst(rst),.cfg_quiescent(!guard),.cfg_command(cfg_command),.cfg_index(cfg_index),.cfg_pd(cfg_pd),
 .cfg_key(cfg_key),.cfg_virtual_address(cfg_va),.cfg_dma_address(64'd0),.cfg_length(cfg_len),.cfg_access(cfg_access),
 .cfg_valid(cfg_valid),.cfg_ready(cfg_ready),.cfg_response_error(cfg_error),.cfg_response_key(cfg_result),
 .cfg_response_valid(cfg_response_valid),.cfg_response_ready(cfg_response_ready),.epoch_configured(configured),
 .s_request_pd(qpd),.s_request_key(qkey),.s_request_address(qa),.s_request_length(qlen),.s_request_operation(qop),
 .s_request_tag(qt),.s_request_valid(qv&&allow_q),.s_request_ready(qr),
 .m_response_tag(rt),.m_response_error(re),.m_response_offset(ro),.m_response_dma_address(),.m_response_length(rlen),
 .m_response_valid(rv),.m_response_ready(rr&&allow_r));
integer cycle=0,queries=0,results=0,checked=0;
reg qstalled=0,ostalled=0;reg [162:0] saved_q;reg [575:0] saved_o;reg saved_auth;
always @(posedge clk)if(!rst)begin
 cycle=cycle+1;if(cycle>20000)$fatal(1,"WQE total cycle deadline");
 if(qstalled && (!qv || query_fields!==saved_q))$fatal(1,"MR query changed/withdrawn under stall");
 if(ostalled && (!ov || output_fields!==saved_o || authorized!==saved_auth))$fatal(1,"work changed under stall");
 qstalled=qv&&!(qr&&allow_q);ostalled=ov&&!ready;saved_q=query_fields;saved_o=output_fields;saved_auth=authorized;
 if(qv&&qr&&allow_q)queries=queries+1;
 if(ov&&ready)results=results+1;
 if(guard && cfg_ready)$fatal(1,"MR mutation ready while WQE ownership held");
end
task manage;
 input [1:0] command;input [2:0] index;input [31:0] key_value;
 input [63:0] address,extent;input [3:0] access_flags;input [31:0] expected_key;
 integer deadline;
 begin
  @(negedge clk);cfg_idle=0;cfg_command=command;cfg_index=index;cfg_key=key_value;
  cfg_va=address;cfg_len=extent;cfg_access=access_flags;cfg_valid=1;
  deadline=cycle+50;@(posedge clk);
  while(cfg_ready!==1)begin if(cycle>deadline)$fatal(1,"cfg request deadline");@(posedge clk);end
  @(negedge clk);cfg_valid=0;
  while(cfg_response_valid!==1)begin if(cycle>deadline)$fatal(1,"cfg response deadline");@(negedge clk);end
  if(cfg_error!==0 || cfg_result!==expected_key)$fatal(1,"MR setup failed %h %h",cfg_error,cfg_result);
  cfg_response_ready=1;@(posedge clk);@(negedge clk);cfg_response_ready=0;cfg_idle=1;
 end
endtask
task issue;
 input [511:0] data;input [63:0] keep;input last,context_valid;
 input [23:0] context_qpn;input [15:0] context_pd,context_tag;
 input [63:0] context_sequence,context_epoch;input [575:0] expected;
 input integer expected_queries,query_stall,response_stall,result_stall;
 input disable_after;input [7:0] expected_fault;
 integer start_queries,start_results,deadline;
 begin
  @(negedge clk);enable=1;cfg_idle=1;allow_q=query_stall==0;allow_r=response_stall==0;ready=0;
  wd=data;wk=keep;wl=last;cv=context_valid;cq=context_qpn;cp=context_pd;ct=context_tag;
  cs=context_sequence;ce=context_epoch;wv=1;start_queries=queries;start_results=results;deadline=cycle+200;
  #1;if(!guard)$fatal(1,"offered first WQE beat not guarded");
  @(posedge clk);while(wr!==1)begin if(cycle>deadline)$fatal(1,"WQE input deadline");@(posedge clk);end
  @(negedge clk);wv=0;wd={512{1'b1}};wk=0;wl=0;cv=0;cq=24'hffffff;cp=16'hffff;ct=0;cs=0;ce=0;
  if(disable_after)enable=0;
  repeat(query_stall)@(negedge clk);allow_q=1;
  repeat(response_stall)@(negedge clk);allow_r=1;
  if(expected_fault!=0)begin
   while(!fault)begin if(cycle>deadline)$fatal(1,"fault deadline");@(negedge clk);end
   if(fault_code!==expected_fault || ov || !busy || !guard || queries-start_queries!=expected_queries)
    $fatal(1,"wrong uncertain-owner fault behavior");
   ready=1;enable=1;repeat(12)@(negedge clk);
   if(!fault || !busy || !guard || ov || wr || results!=start_results)$fatal(1,"fault fabricated completion/drain");
  end else begin
   while(!ov)begin if(cycle>deadline)$fatal(1,"work deadline");@(negedge clk);end
   if(output_fields!==expected || authorized!==(expected[7:0]==0) || fault || !guard)
    $fatal(1,"work mismatch expected=%h actual=%h",expected,output_fields);
   repeat(result_stall)begin
    @(negedge clk);enable=0;cfg_idle=0;cfg_valid=1;
    if(cfg_ready || !guard || !ov || output_fields!==expected)$fatal(1,"pending result lost ownership");
   end
   @(negedge clk);cfg_valid=0;cfg_idle=1;ready=1;
   @(posedge clk);@(negedge clk);ready=0;enable=1;repeat(2)@(negedge clk);
   if(busy || guard || queries-start_queries!=expected_queries || results!=start_results+1)
    $fatal(1,"incorrect retirement/query count");
  end
  checked=checked+1;
 end
endtask
initial begin
 repeat(4)@(negedge clk);rst=0;
 manage(3,0,32'h10000000,0,0,0,32'h10000000);
 manage(1,0,0,64'hf123456789abc000,64'd8192,1,32'h80000008);
 manage(1,1,0,64'hf123456789abc000,64'd8192,0,32'h80000009);
 manage(1,2,0,64'hfffffffffffff000,64'd4096,1,32'h8000000a);
 if(!configured)$fatal(1,"missing MR epoch");
 // BODY
 $display("WQE_ADMISSION_PASS checked=%0d queries=%0d results=%0d fault=%0d cycles=%0d",checked,queries,results,fault,cycle);
 $finish;
end
endmodule
'''


def packed(values):
    out=0
    for width,value in values:out=(out<<width)|value
    return out


class WQEAdmissionRTLTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory=tempfile.TemporaryDirectory(prefix='as02-wqe-encoder-')
        p=Path(cls.directory.name)
        r=subprocess.run(['cc','-std=c11','-O2','-Wall','-Wextra','-Werror','-shared','-fPIC',
            '-fsanitize=undefined','-fno-sanitize-recover=undefined','-I',str(KERNEL),str(KERNEL/'wqe.c'),
            '-o',str(p/'wqe.so')],capture_output=True,text=True,timeout=30)
        if r.returncode:raise RuntimeError(r.stderr)
        cls.lib=C.CDLL(str(p/'wqe.so'))
        cls.lib.as02_wqe_encode.argtypes=[C.POINTER(C.c_uint8),C.POINTER(codec.WQE)]
        cls.lib.as02_wqe_encode.restype=C.c_int

    @classmethod
    def tearDownClass(cls):cls.directory.cleanup()

    def entry(self,w=None,*,mutate=None,context=None,error=0,queries=1,offset=None,
              keep=(1<<64)-1,last=1,context_valid=1,stalls=(0,0,4),disable=0,fault=0):
        w=w or codec.candidate(local_address=BASE+1)
        data=(C.c_uint8*64)();self.assertEqual(self.lib.as02_wqe_encode(data,C.byref(w)),0)
        record=bytearray(data)
        if mutate:mutate(record)
        qpn,pd,tag,sequence,epoch=(context or (1,7,0xf123,SEQ,EPOCH))
        successful=error==0
        offset=(w.local_address-BASE) if offset is None else offset
        values=[(64,w.wr_id),(64,sequence),(64,epoch),(24,qpn),(16,pd),(16,tag),
            (16,w.opcode if successful else 0),(16,w.flags if successful else 0),
            (32,w.length if successful else 0),(32,w.local_key if successful else 0),
            (64,w.local_address if successful else 0),(64,offset if successful else 0),
            (64,w.remote_address if successful else 0),(32,w.remote_key if successful else 0),(8,error)]
        return (f"issue(512'h{int.from_bytes(record,'little'):0128x},64'h{keep:016x},1'b{last},1'b{context_valid},"
                f"24'h{qpn:x},16'h{pd:x},16'h{tag:x},64'h{sequence:x},64'h{epoch:x},"
                f"576'h{packed(values):0144x},{queries},{stalls[0]},{stalls[1]},{stalls[2]},1'b{disable},8'h{fault:x});")

    def simulate(self,body):
        tb=TB.replace('// BODY','\n'.join(body))
        self.assertNotIn('force ',tb)
        with tempfile.TemporaryDirectory(prefix='as02-wqe-admission-')as directory:
            p=Path(directory);(p/'tb.v').write_text(tb)
            compiled=subprocess.run(['iverilog','-g2012','-s','tb','-o',str(p/'test.vvp'),str(p/'tb.v'),
                str(RTL/'rocev2_wqe_admission.v'),str(RTL/'rocev2_mr_table.v')],capture_output=True,text=True,timeout=20)
            self.assertEqual(compiled.returncode,0,compiled.stderr)
            result=subprocess.run(['vvp',str(p/'test.vvp')],capture_output=True,text=True,timeout=15)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertIn('WQE_ADMISSION_PASS',result.stdout)

    def test_actual_C_descriptors_full_keys_high_IOVA_cross_page_both_local_operations(self):
        body=[]
        for op in [1,2]:
            for offset,length in [(0,1),(1,65),(4095,4096)]:
                for key in [0,0xffffffff]:
                    body.append(self.entry(codec.candidate(opcode=op,local_address=BASE+offset,
                                                          length=length,remote_key=key)))
        self.simulate(body)

    def test_actual_MR_denies_wrong_key_PD_permissions_and_full_ranges(self):
        body=[self.entry(codec.candidate(local_address=BASE+1,local_key=KEY^0x80000000),error=1),
              self.entry(codec.candidate(local_address=BASE+1,local_key=0),error=1),
              self.entry(context=(1,8,0xf123,SEQ,EPOCH),error=2),
              self.entry(codec.candidate(local_address=BASE+1,local_key=KEY+1,opcode=2),error=3),
              self.entry(codec.candidate(local_address=BASE+1,local_key=KEY+1,opcode=1)),
              self.entry(codec.candidate(local_address=BASE-1),error=4),
              self.entry(codec.candidate(local_address=BASE+8192-64),error=4),
              self.entry(codec.candidate(local_address=(BASE+1)&((1<<48)-1)),error=4)]
        self.simulate(body)

    def test_untrusted_record_and_full_trusted_context_reject_before_any_MR_query(self):
        def replace(offset,data):return lambda b:b.__setitem__(slice(offset,offset+len(data)),data)
        body=[self.entry(keep=(1<<63)-1,error=0x20,queries=0),self.entry(last=0,error=0x20,queries=0),
              self.entry(mutate=replace(48,b'\x80'),error=0x20,queries=0),
              self.entry(context_valid=0,error=0x21,queries=0),
              self.entry(context=(8,7,0xf123,SEQ,EPOCH),error=0x21,queries=0),
              self.entry(context=(0x100001,7,0xf123,SEQ,EPOCH),error=0x21,queries=0),
              self.entry(context=(1,7,0xf123,SEQ,0),error=0x21,queries=0),
              self.entry(mutate=replace(56,(EPOCH^0x8000000000000000).to_bytes(8,'little')),error=0x22,queries=0),
              self.entry(mutate=replace(8,(SEQ^0x8000000000000000).to_bytes(8,'little')),error=0x23,queries=0),
              self.entry(mutate=replace(44,b'\x03\0'),error=0x24,queries=0),
              self.entry(mutate=replace(46,b'\x02\0'),error=0x25,queries=0),
              self.entry(mutate=replace(32,bytes(4)),error=0x26,queries=0),
              self.entry(mutate=replace(32,int(4097).to_bytes(4,'little')),error=0x26,queries=0),
              self.entry(mutate=replace(16,bytes([255])*8),error=0x27,queries=0),
              self.entry(mutate=replace(24,bytes([255])*8),error=0x27,queries=0)]
        self.simulate(body)

    def test_stalled_query_response_result_survive_disable_and_block_configuration(self):
        self.simulate([self.entry(stalls=(12,12,12),disable=1),
                       self.entry(codec.candidate(local_address=BASE+4095,opcode=2),stalls=(7,9,8))])

    def test_last_64bit_byte_remote_key_zero_and_maximum_valid_QP(self):
        w=codec.candidate(local_address=(1<<64)-1,remote_address=(1<<64)-1,
                          local_key=KEY+2,length=1,remote_key=0)
        self.simulate([self.entry(w,context=(7,7,0xffff,SEQ,EPOCH),offset=4095)])

    def test_wrong_tag_length_or_unknown_response_retains_uncertain_owner(self):
        for corrupt,code in [(1,0x31),(2,0x32),(3,0x33)]:
            with self.subTest(corrupt=corrupt):
                self.simulate([f'corrupt={corrupt};',self.entry(fault=code)])


if __name__=='__main__':unittest.main()
