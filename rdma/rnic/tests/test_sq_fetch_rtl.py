# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual SQ-fetch RTL, explicit read-backend/parent-drain/host DATA MODELS.

No native pinned/coherent allocation, actual PCIe, WQE authorization, outgoing
RDMA or CQ completion is claimed by these controller-only units.
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
RTL=ROOT/'rdma/rnic/rtl/rocev2_sq_fetch.v'
TB=r'''
`timescale 1ns/1ps
module tb;
localparam MAX_QPS=8;
// DECLARATIONS
rocev2_sq_fetch #(.INITIAL_TAG(INITIAL_TAG_VALUE)) dut(.*);
always #2 clk=~clk;
integer cycle=0,commands=0,results=0,deadline;
reg cmd_stalled=0,result_stalled=0;
wire [111:0] cmd_fields={m_command_address,m_command_length,m_command_tag};
wire [703:0] result_fields={m_result_data,m_result_error,m_result_qpn,m_result_pd,m_result_epoch,m_result_sequence,m_result_tag};
reg [111:0] saved_cmd;reg [703:0] saved_result;
always @(posedge clk)if(!rst)begin
 cycle=cycle+1;if(cycle>5000)$fatal(1,"SQ fetch cycle deadline");
 if(cmd_stalled && (!m_command_valid || cmd_fields!==saved_cmd))$fatal(1,"fetch descriptor retracted/changed");
 if(result_stalled && (!m_result_valid || result_fields!==saved_result))$fatal(1,"fetched result retracted/changed");
 cmd_stalled=m_command_valid&&!m_command_ready;saved_cmd=cmd_fields;
 result_stalled=m_result_valid&&!m_result_ready;saved_result=result_fields;
 if(m_command_valid&&m_command_ready)commands=commands+1;
 if(m_result_valid&&m_result_ready)results=results+1;
end
task configure;
 input [1:0] op;input [23:0] q;input [15:0] pd_value;
 input [63:0] epoch_value,base,producer;input [3:0] log_depth;input [7:0] expected_error;
 reg [159:0] held;
 begin
  @(negedge clk);cfg_command=op;cfg_qpn=q;cfg_pd=pd_value;cfg_epoch=epoch_value;cfg_dma_base=base;
  cfg_producer=producer;cfg_log_depth=log_depth;cfg_valid=1;cfg_response_ready=0;
  @(posedge clk);while(!cfg_ready)@(posedge clk);
  @(negedge clk);cfg_valid=0;
  while(!cfg_response_valid)@(negedge clk);
  if(cfg_response_error!==expected_error || cfg_response_qpn!==q || cfg_response_epoch!==epoch_value)
   $fatal(1,"config error got=%d expected=%d q=%h",cfg_response_error,expected_error,q);
  held={cfg_response_error,cfg_response_qpn,cfg_response_epoch,cfg_response_consumer};
  repeat(4)begin @(negedge clk);
   if(!cfg_response_valid || cfg_ready || {cfg_response_error,cfg_response_qpn,cfg_response_epoch,cfg_response_consumer}!==held)
    $fatal(1,"config response not retained");
  end
  cfg_response_ready=1;@(posedge clk);@(negedge clk);cfg_response_ready=0;
 end
endtask
task wait_command;
 input [63:0] expected_address;input [15:0] expected_tag;
 begin
  deadline=cycle+100;while(!m_command_valid)begin if(cycle>deadline)$fatal(1,"fetch descriptor deadline");@(negedge clk);end
  if(m_command_address!==expected_address || m_command_length!==64 || m_command_tag!==expected_tag || !busy)
   $fatal(1,"wrong DMA64 ring descriptor %h/%d/%h",m_command_address,m_command_length,m_command_tag);
 end
endtask
task accept_command;
 begin
  repeat(5)@(negedge clk);m_command_ready=1;@(posedge clk);@(negedge clk);m_command_ready=0;
 end
endtask
task data_beat;
 input [511:0] bytes;input [63:0] keep;input last;
 begin
  @(negedge clk);s_axis_read_tdata=bytes;s_axis_read_tkeep=keep;s_axis_read_tlast=last;s_axis_read_tvalid=1;
  @(posedge clk);while(!s_axis_read_tready)@(posedge clk);
  @(negedge clk);s_axis_read_tvalid=0;s_axis_read_tdata=0;
 end
endtask
task status;
 input [15:0] tag;input [7:0] error_code;
 begin
  @(negedge clk);s_status_tag=tag;s_status_error=error_code;s_status_valid=1;
  @(posedge clk);while(!s_status_ready)@(posedge clk);
  @(negedge clk);s_status_valid=0;
 end
endtask
task finish_result;
 input [511:0] bytes;input [7:0] error_code;input [23:0] q;input [15:0] pd_value;
 input [63:0] epoch_value,sequence_value;input [15:0] tag;
 begin
  deadline=cycle+100;while(!m_result_valid)begin if(cycle>deadline)$fatal(1,"fetch result deadline");@(negedge clk);end
  if(m_result_data!==(error_code==0 ? bytes : 512'd0) || m_result_error!==error_code || m_result_qpn!==q ||
   m_result_pd!==pd_value || m_result_epoch!==epoch_value || m_result_sequence!==sequence_value || m_result_tag!==tag ||
   !queue_guard[q] || !busy || fault)$fatal(1,"fetched record/context/error corrupted");
  repeat(8)begin @(negedge clk);if(!queue_guard[q] || !busy || !m_result_valid)$fatal(1,"held fetched record lost owner");end
  m_result_ready=1;@(posedge clk);@(negedge clk);m_result_ready=0;
 end
endtask
task fetch;
 input [63:0] expected_address;input [23:0] q;input [15:0] pd_value;
 input [63:0] epoch_value,sequence_value;input [15:0] tag;input [7:0] error_code;
 input status_first;input [511:0] bytes;
 begin
  wait_command(expected_address,tag);accept_command();
  if(status_first)begin status(tag,error_code);repeat(5)@(negedge clk);
   if(m_result_valid)$fatal(1,"result before complete descriptor bytes");data_beat(bytes,64'hffffffffffffffff,1);end
  else begin data_beat(bytes,64'hffffffffffffffff,1);repeat(5)@(negedge clk);
   if(m_result_valid)$fatal(1,"result before actual DMA status");status(tag,error_code);end
  finish_result(bytes,error_code,q,pd_value,epoch_value,sequence_value,tag);
 end
endtask
initial begin
 rst=1;parent_dma_drained=1;repeat(4)@(negedge clk);rst=0;
 // BODY
 $display("SQ_FETCH_RESULT {\"pass_test\":true,\"commands\":%0d,\"results\":%0d,\"cycles\":%0d,\"fault\":%0d}",commands,results,cycle,fault);
 $finish;
end
endmodule
'''


def declarations():
    ports=re.findall(r'^\s*(input|output)\s+(?:wire|reg)\s+(\[[^]]+\]\s+)?(\w+)(?:=0)?\s*,?$',
                     RTL.read_text().split(')(\n',1)[1].split('\n);',1)[0],re.M)
    if len(ports)!=61:raise ValueError(('SQ port declaration changed',len(ports)))
    if [(d,w.strip())for d,w,n in ports if n=='queue_pending']!=[('output','[MAX_QPS-1:0]')]:
        raise ValueError('full per-QP pending ownership output changed')
    return '\n'.join(('reg 'if d=='input'else'wire ')+(width or '')+name+('=0;'if d=='input'else';')for d,width,name in ports)


class SQFetchRTLTests(unittest.TestCase):
    reports={}

    def simulate(self,body,initial_tag=0):
        tb=TB.replace('// DECLARATIONS',declarations()).replace('INITIAL_TAG_VALUE',str(initial_tag)).replace('// BODY',body)
        self.assertNotIn('force ',tb)
        own=[RTL,Path(__file__).resolve()];before={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in own}
        with tempfile.TemporaryDirectory(prefix='as02-sq-fetch-')as directory:
            p=Path(directory);(p/'tb.v').write_text(tb)
            c=subprocess.run(['iverilog','-g2012','-s','tb','-o',str(p/'test.vvp'),str(p/'tb.v'),str(RTL)],
                             capture_output=True,text=True,timeout=20)
            self.assertEqual(c.returncode,0,c.stdout+c.stderr)
            r=subprocess.run(['vvp',str(p/'test.vvp')],capture_output=True,text=True,timeout=10)
            self.assertEqual(r.returncode,0,r.stdout+r.stderr)
            rows=[json.loads(line[16:])for line in r.stdout.splitlines()if line.startswith('SQ_FETCH_RESULT ')]
            self.assertEqual(len(rows),1,r.stdout)
            self.assertTrue(rows[0]['pass_test'])
        self.assertEqual(before,{n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest()for n in before})
        self.reports.setdefault(self._testMethodName,[]).append(dict(summary=rows[0],source_sha256=before,
            bench_sha256=hashlib.sha256(tb.encode()).hexdigest()))

    def test_two_QP_full_DMA64_PD_epoch_sequence_and_fair_ring_wrap(self):
        self.simulate(r'''
configure(1,0,16'hf123,64'h8000000000000001,64'h8123456789abc000,0,1,0);
configure(1,7,16'habcd,64'h9000000000000001,64'hfedcba9876543000,0,1,0);
configure(2,0,0,64'h8000000000000001,0,2,0,0);configure(2,7,0,64'h9000000000000001,0,2,0,0);
if(queue_pending!==8'h81 || queue_guard || commands || results)$fatal(1,"posted, unfetched ownership not per-QP pending only");
enable=1;
fetch(64'h8123456789abc000,0,16'hf123,64'h8000000000000001,1,1,0,0,512'h1234);
fetch(64'hfedcba9876543000,7,16'habcd,64'h9000000000000001,1,2,0,1,512'habcd);
fetch(64'h8123456789abc040,0,16'hf123,64'h8000000000000001,2,3,0,1,512'h5678);
fetch(64'hfedcba9876543040,7,16'habcd,64'h9000000000000001,2,4,0,0,512'hdcba);
configure(2,0,0,64'h8000000000000001,0,4,0,0);
fetch(64'h8123456789abc000,0,16'hf123,64'h8000000000000001,3,5,0,0,512'h1122);
fetch(64'h8123456789abc040,0,16'hf123,64'h8000000000000001,4,6,0,1,512'h3344);
enable=0;repeat(5)@(negedge clk);if(busy || commands!=6 || results!=6 || queue_guard || queue_pending || queue_halted)$fatal(1,"ring/fairness coverage");
''')

    def test_configuration_full_QP_bounds_epoch_ring_range_and_producer_credits(self):
        self.simulate(r'''
configure(1,24'h100000,1,1,64'h1000,0,1,16);configure(1,8,1,1,64'h1000,0,1,16);
configure(1,0,1,0,64'h1000,0,1,17);configure(1,0,1,1,64'h1001,0,1,18);
configure(1,0,1,1,64'h1000,0,0,18);configure(1,0,1,1,64'h1000,0,9,18);
configure(1,0,1,1,64'hffffffffffffffc0,0,1,18);
configure(1,0,1,1,64'hffffffffffffff80,0,1,0);
configure(1,0,1,2,64'h1000,0,1,19);
configure(2,0,0,2,0,1,0,17);configure(2,0,0,1,0,3,0,21);
configure(2,0,0,1,0,2,0,0);configure(2,0,0,1,0,1,0,21);
enable=1;fetch(64'hffffffffffffff80,0,1,1,1,1,0,0,512'haaaa);
fetch(64'hffffffffffffffc0,0,1,1,2,2,0,1,512'hbbbb);
enable=0;configure(3,0,0,1,0,0,0,0);
configure(1,0,1,1,64'h1000,0,1,17);configure(1,0,1,2,64'h1000,0,1,0);
if(commands!=2 || results!=2 || queue_active!==1)$fatal(1,"config gate coverage");
''')

    def test_disable_does_not_cancel_offered_descriptor_or_held_result_or_downstream_guard(self):
        self.simulate(r'''
configure(1,1,17,64'h8000000000000001,64'h8123456789abc000,0,1,0);
configure(2,1,0,64'h8000000000000001,0,1,0,0);enable=1;
wait_command(64'h8123456789abc000,1);enable=0;
configure(3,1,0,64'h8000000000000001,0,0,0,19);accept_command();
data_beat(512'h9876,64'hffffffffffffffff,1);status(1,0);
downstream_queue_guard=2;finish_result(512'h9876,0,1,17,64'h8000000000000001,1,1);
configure(3,1,0,64'h8000000000000001,0,0,0,19);downstream_queue_guard=0;parent_dma_drained=0;
configure(3,1,0,64'h8000000000000001,0,0,0,19);parent_dma_drained=1;
configure(3,1,0,64'h8000000000000001,0,0,0,0);
if(queue_active || busy || commands!=1 || results!=1)$fatal(1,"retirement/drop owner coverage");
''')

    def test_known_DMA_error_zeroes_record_halts_only_its_queue_and_preserves_other_progress(self):
        self.simulate(r'''
configure(1,0,1,1,64'h1000,0,1,0);configure(1,1,2,2,64'h2000,0,1,0);
configure(2,0,0,1,0,2,0,0);configure(2,1,0,2,0,1,0,0);enable=1;
fetch(64'h1000,0,1,1,1,1,6,0,{512{1'b1}});
if(queue_halted!==1)$fatal(1,"bad queue not halted");
fetch(64'h2000,1,2,2,1,2,0,1,512'h7788);
repeat(10)@(negedge clk);if(m_command_valid || commands!=2 || results!=2 || fault)$fatal(1,"failed queue consumed unread tail");
configure(2,0,0,1,0,2,0,22);enable=0;configure(3,0,0,1,0,0,0,0);
configure(1,0,1,2,64'h3000,0,1,0);
''')

    def test_bad_data_shape_wrong_status_tag_and_unknown_status_fault_without_result(self):
        for body,code in [("data_beat(512'h1,64'hfffffffffffffffe,1);",64),
                          ("data_beat(512'h1,64'hffffffffffffffff,0);",64),
                          ('status(2,0);',65),("status(1,8'hff);",65)]:
            with self.subTest(body=body):self.simulate(r'''
configure(1,0,1,1,64'h1000,0,1,0);configure(2,0,0,1,0,1,0,0);enable=1;
wait_command(64'h1000,1);accept_command();
'''+body+f'''
repeat(5)@(negedge clk);if(!fault || fault_code!=={code} || !busy || !queue_guard[0] || m_result_valid || results!=0)
 $fatal(1,"uncertain fetch owner released");
configure(3,0,0,1,0,0,0,19);
''')

    def test_unexpected_status_never_accepts_or_retracts_offered_work(self):
        self.simulate(r'''
configure(1,0,1,1,64'h1000,0,1,0);configure(2,0,0,1,0,1,0,0);enable=1;
wait_command(64'h1000,1);s_status_valid=1;s_status_tag=1;
repeat(4)@(negedge clk);s_status_valid=0;
if(!fault || !m_command_valid || !queue_guard[0] || results!=0)$fatal(1,"unexpected status cancelled offered descriptor");
accept_command();repeat(4)@(negedge clk);
if(!fault || !busy || m_command_valid || m_result_valid || results!=0)$fatal(1,"unexpected status invented retirement");
''')

    def test_tag_exhaustion_refuses_wrap_and_does_not_fabricate_queued_work(self):
        self.simulate(r'''
configure(1,0,1,1,64'h1000,0,1,0);configure(2,0,0,1,0,2,0,0);enable=1;
fetch(64'h1000,0,1,1,1,16'hffff,0,0,512'h99);
repeat(10)@(negedge clk);if(!tag_exhausted || m_command_valid || busy || commands!=1 || results!=1)
 $fatal(1,"fetch tag wrapped or fake completion");
''',initial_tag=65534)

    @classmethod
    def tearDownClass(cls):
        if name:=os.environ.get('AS02_RNIC_SQ_FETCH_UNIT_REPORT'):
            p=Path(name);p=p if p.is_absolute()else ROOT/p
            with p.open('x')as out:json.dump(dict(scope=__doc__,pass_test=len(cls.reports)==7,
                methods=len(cls.reports),tests=cls.reports,hardware_verified=False,actual_PCIe_engine=False,
                real_host_queue_mapping=False,standard_verbs_implemented=False,RDMA_completion_claim=False),out,indent=2);out.write('\n')


if __name__=='__main__':unittest.main()
