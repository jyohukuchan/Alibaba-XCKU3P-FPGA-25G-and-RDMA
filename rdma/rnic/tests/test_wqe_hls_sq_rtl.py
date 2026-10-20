# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual owner-before-HLS-SQ RTL; work authorization/executor/HLS are MODELS.

No actual MR/SQ fetch/HLS memory/wire/CQ/runtime completion is claimed here.
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
RTL=ROOT/'rdma/rnic/rtl/rocev2_wqe_hls_sq.v'
WIDTHS=[64,64,64,24,16,16,16,16,32,32,64,64,64,32,8,2,8,1,1]
DEFAULT=[0xf123456789abc001,0xf123456700000001,0x9123456700000001,7,0xffff,0xffff,1,1,65,
    0x80000008,0xfedcba9876543210,0x210,0xe23456789abcdef0,0,0,0,0,1,1]


def context(**changes):
    names=['id','sequence','epoch','qpn','pd','tag','opcode','flags','length','lkey','address','offset',
        'remote','rkey','error','source','fetch','available','authorized']
    values=DEFAULT.copy()
    for n,v in changes.items():values[names.index(n)]=v
    value=0
    for bits,v in zip(WIDTHS,values):value=(value<<bits)|v
    assert sum(WIDTHS)==588
    return f"588'h{value:0147x}"


def expected_sq(**changes):
    # Independent explicit ABI offsets, not the production concatenation.
    v=dict(opcode=1,qpn=7,length=65,address=0xfedcba9876543210,remote=0xe23456789abcdef0,rkey=0)
    v.update(changes)
    value=(1<<240)|(v['rkey']<<208)|(v['length']<<176)|(v['remote']<<112)|\
        (v['address']<<48)|(1<<43)|(1<<42)|(v['qpn']<<32)|(10 if v['opcode']==1 else 12)
    return f"248'h{value:062x}"


TB=r'''
`timescale 1ns/1ps
module tb;
localparam MAX_QPS=8,IMMEDIATE_ENABLE=0;
// DECLARATIONS
rocev2_wqe_hls_sq dut(.*);
always #2 clk=~clk;
integer cycle=0,deadline;reg cs=0,ss=0;reg [587:0] held_context;reg [247:0] held_sq;
always @(posedge clk)if(!rst)begin
 cycle=cycle+1;if(cycle>3000)$fatal(1,"WQE->HLS cycle deadline");
 if(cs && (!m_owner_valid || m_owner_context!==held_context))$fatal(1,"owner context changed/retracted");
 if(ss && (!m_axis_sq_tvalid || m_axis_sq_tdata!==held_sq))$fatal(1,"HLS SQ changed/retracted");
 cs=m_owner_valid&&!m_owner_ready;held_context=m_owner_context;
 ss=m_axis_sq_tvalid&&!m_axis_sq_tready;held_sq=m_axis_sq_tdata;
end
task submit;
 input [587:0] value;
 begin
  @(negedge clk);s_work_context=value;s_work_valid=1;
  @(posedge clk);deadline=cycle+100;
  while(!s_work_ready)begin if(cycle>deadline)$fatal(1,"work capture deadline");@(posedge clk);end
  @(negedge clk);s_work_valid=0;s_work_context=0;
 end
endtask
task owner;
 input [587:0] expected;input integer q;
 begin
  if(!m_owner_valid || m_owner_context!==expected || m_axis_sq_tvalid || !configuration_guard || queue_guard!==(8'b1<<q))$fatal(1,"owner context/guard/early SQ");
  repeat(7)@(negedge clk);downstream_queue_guard=(8'b1<<q);m_owner_ready=1;
  @(posedge clk);@(negedge clk);m_owner_ready=0;
 end
endtask
task sq;
 input [247:0] expected;
 begin
  deadline=cycle+100;while(!m_axis_sq_tvalid)begin if(cycle>deadline)$fatal(1,"HLS SQ deadline");@(negedge clk);end
  if(m_axis_sq_tdata!==expected || fault || !busy)$fatal(1,"per-WR ABI/full key/address/host changed %h expected%h",m_axis_sq_tdata,expected);
  enable=0;halt=1;repeat(13)@(negedge clk);
  if(!m_axis_sq_tvalid || m_axis_sq_tdata!==expected)$fatal(1,"accepted metadata canceled by halt");
  m_axis_sq_tready=1;@(posedge clk);@(negedge clk);m_axis_sq_tready=0;
  if(busy || queue_guard || fault || HLS_SQ_handoff_count!=owner_handoff_count)$fatal(1,"staging handoff did not finish");
  // Explicit model-only downstream WR retirement, NOT actual completion.
  downstream_queue_guard=0;enable=1;halt=0;
 end
endtask
initial begin
 rst=1;repeat(4)@(negedge clk);rst=0;enable=1;
 // BODY
 $display("WQE_HLS_SQ_RESULT {\"pass_test\":true,\"owners\":%0d,\"SQ\":%0d,\"fault\":%0d,\"cycles\":%0d}",owner_handoff_count,HLS_SQ_handoff_count,fault,cycle);
 $finish;
end
endmodule
'''


class WQEHlsSQTests(unittest.TestCase):
    reports={}

    def simulate(self,body,immediate=False):
        header=RTL.read_text().split(')(\n',1)[1].split('\n);',1)[0]
        ports=re.findall(r'^\s*(input|output)\s+(?:wire|reg)\s+(\[[^]]+\]\s+)?(\w+)(?:=0)?\s*,?$',header,re.M)
        if len(ports)!=21:raise ValueError(('SQ owner interface changed',len(ports)))
        declarations='\n'.join(('reg 'if d=='input'else'wire ')+(w or '')+n+('=0;'if d=='input'else';')for d,w,n in ports)
        tb=TB.replace('// DECLARATIONS',declarations).replace('// BODY',body)
        if immediate:
            tb=tb.replace('IMMEDIATE_ENABLE=0','IMMEDIATE_ENABLE=1').replace('[587:0]','[619:0]').replace('[247:0]','[279:0]')
            tb=tb.replace('rocev2_wqe_hls_sq dut','rocev2_wqe_hls_sq #(.IMMEDIATE_ENABLE(1)) dut')
        paths=[RTL,Path(__file__).resolve()];before={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in paths}
        with tempfile.TemporaryDirectory(prefix='as02-wqe-hls-sq-')as directory:
            p=Path(directory);(p/'tb.v').write_text(tb)
            c=subprocess.run(['iverilog','-g2012','-s','tb','-o',str(p/'test.vvp'),str(p/'tb.v'),str(RTL)],capture_output=True,text=True,timeout=20)
            self.assertEqual(c.returncode,0,c.stdout+c.stderr)
            r=subprocess.run(['vvp',str(p/'test.vvp')],capture_output=True,text=True,timeout=10)
            self.assertEqual(r.returncode,0,r.stdout+r.stderr)
            rows=[json.loads(l[18:])for l in r.stdout.splitlines()if l.startswith('WQE_HLS_SQ_RESULT ')]
            self.assertEqual(len(rows),1,r.stdout);self.assertTrue(rows[0]['pass_test'])
        self.assertEqual(before,{n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest()for n in before})
        self.reports.setdefault(self._testMethodName,[]).append(dict(summary=rows[0],source_sha256=before,bench_sha256=hashlib.sha256(tb.encode()).hexdigest()))

    def test_complete_WRITE_READ_ABI_full_zero_high_keys_and_QP0_PD0(self):
        body=''
        for op in [1,2]:
            for q,pd in [(7,0xffff),(0,0)]:
                for key in [0,0x80000000,0xffffffff,0x12345678]:
                    ctx=context(opcode=op,qpn=q,pd=pd,rkey=key)
                    body+=f'submit({ctx});owner({ctx},{q});sq({expected_sq(opcode=op,qpn=q,rkey=key)});\n'
        self.simulate(body)

    def test_all_failed_fetches_handoff_identity_but_never_offer_HLS_SQ(self):
        body=''
        for error in range(1,16):
            ctx=context(id=0,opcode=0,flags=0,length=0,lkey=0,address=0,offset=0,remote=0,rkey=0,
                error=error,source=1,fetch=error,available=0,authorized=0)
            body+=f'submit({ctx});owner({ctx},7);'+r'''
repeat(8)@(negedge clk);if(m_axis_sq_tvalid || busy || fault || HLS_SQ_handoff_count)$fatal(1,"failed fetch became HLS operation");
downstream_queue_guard=0;
'''
        self.simulate(body)

    def test_denied_MR_record_handoff_does_not_become_a_transport_operation(self):
        for available in [0,1]:
            ctx=context(id=DEFAULT[0]if available else 0,opcode=0,flags=0,length=0,lkey=0,address=0,
                offset=0,remote=0,rkey=0,error=32,source=2,available=available,authorized=0)
            with self.subTest(available=available):self.simulate(f'submit({ctx});owner({ctx},7);'+r'''
repeat(8)@(negedge clk);if(m_axis_sq_tvalid || busy || fault || HLS_SQ_handoff_count || owner_handoff_count!=1)$fatal(1,"denial transport/owner mismatch");
''')

    def test_invalid_or_unknown_full_context_never_gets_owner_or_HLS_authority(self):
        cases=[context(qpn=0x800007),context(tag=0),context(sequence=0),context(epoch=0),context(flags=2),
            context(length=0),context(length=4097),context(address=(1<<64)-1,length=2),
            context(offset=(1<<64)-1,length=2),context(remote=(1<<64)-1,length=2),context(authorized=0)]
        for value in cases+["{4'hx,584'd0}"]:
            with self.subTest(context=value):self.simulate(f'@(negedge clk);s_work_context={value};s_work_valid=1;'+r'''
repeat(8)@(negedge clk);
if(!fault || fault_code!=8'h71 || queue_guard!=8'hff || s_work_ready || m_owner_valid || m_axis_sq_tvalid || !busy)$fatal(1,"invalid full context gained authority or released refs");
''')

    def test_owner_cannot_handoff_without_existing_downstream_lifetime_guard(self):
        self.simulate(f'submit({context()});'+r'''
m_owner_ready=1;repeat(8)@(negedge clk);
if(!fault || fault_code!=8'h72 || !m_owner_valid || queue_guard!=8'hff || m_axis_sq_tvalid || !busy)$fatal(1,"owner handoff gap");
''')

    def test_lost_downstream_guard_does_not_retract_already_offered_SQ(self):
        self.simulate(f'submit({context()});owner({context()},7);'+r'''
while(!m_axis_sq_tvalid)@(negedge clk);
downstream_queue_guard=0;repeat(8)@(negedge clk);
if(!fault || fault_code!=8'h73 || !m_axis_sq_tvalid || queue_guard!=8'hff || !busy)$fatal(1,"lost downstream owner erased SQ");
m_axis_sq_tready=1;@(posedge clk);@(negedge clk);m_axis_sq_tready=0;
if(!fault || !busy || queue_guard!=8'hff || HLS_SQ_handoff_count!=1)$fatal(1,"fault fabricated completion");
''')

    def test_halt_prevents_NEW_SQ_but_not_accepted_context_progress(self):
        self.simulate('halt=1;'+f'submit({context()});owner({context()},7);'+r'''
enable=0;repeat(13)@(negedge clk);
if(m_axis_sq_tvalid || !busy || queue_guard!=8'h80 || fault)$fatal(1,"halt allowed new SQ or lost owner");
halt=0;
'''+f'sq({expected_sq()});')

    @classmethod
    def tearDownClass(cls):
        if name:=os.environ.get('AS02_RNIC_WQE_HLS_SQ_UNIT_REPORT'):
            p=Path(name);p=p if p.is_absolute()else ROOT/p
            cases=sum(map(len,cls.reports.values()))
            d=dict(scope=__doc__,pass_test=len(cls.reports)==7 and cases==19,methods=len(cls.reports),simulations=cases,tests=cls.reports,
                actual_MR_SQ_fetch_HLS=False,actual_executor_CQ=False,hardware_verified=False,completion_claim=False)
            with p.open('x')as out:out.write(json.dumps(d,indent=2)+'\n')


if __name__=='__main__':unittest.main()
