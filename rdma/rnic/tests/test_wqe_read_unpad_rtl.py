# SPDX-License-Identifier: BSD-2-Clause-Views
"""Production full-WQE READ wire-pad adapter; token/HLS/executor are MODELS.

Checks original96-bit padded ABI, normalized payload-only command/data and
continuous owner guards. Not actual HLS, native DMA, protected RX or CQ proof.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

from test_wqe_hls_sq_rtl import context,DEFAULT
from test_wqe_memory_executor_rtl import raw_command

ROOT=Path(__file__).resolve().parents[3]
RTL=ROOT/'rdma/rnic/rtl/rocev2_wqe_read_unpad.v'


TB=r'''
`timescale 1ns/1ps
module tb;
localparam MAX_QPS=8;
// DECLARATIONS
rocev2_wqe_read_unpad dut(.*);
always #2 clk=~clk;
integer cycle=0,deadline,pos,n,wire_n,lane;
reg cs=0,ds=0;reg [95:0] held_command;reg [576:0] held_data;
always @(posedge clk)if(!rst)begin
 cycle=cycle+1;if(cycle>5000)$fatal(1,"unpad finite deadline");
 if(cs && (!m_command_valid || m_command!==held_command))$fatal(1,"normalized command changed/retracted");
 if(ds && (!m_axis_tvalid || {m_axis_tlast,m_axis_tkeep,m_axis_tdata}!==held_data))$fatal(1,"unpadded data changed/retracted");
 cs=m_command_valid&&!m_command_ready;held_command=m_command;
 ds=m_axis_tvalid&&!m_axis_tready;held_data={m_axis_tlast,m_axis_tkeep,m_axis_tdata};
end
task capture;
 input [587:0] value;
 begin
  downstream_queue_guard=8'h80;@(negedge clk);s_context=value;s_context_valid=1;
  @(posedge clk);if(!s_context_ready || queue_guard!==8'h80)$fatal(1,"pad-adapter guarded context");
  @(negedge clk);s_context_valid=0;s_context=0;
 end
endtask
task command;
 input [95:0] raw_value,normal_value;
 begin
  s_command=raw_value;s_command_valid=1;@(posedge clk);if(!s_command_ready)$fatal(1,"raw padded command capture");
  @(negedge clk);s_command_valid=0;
  if(!m_command_valid || m_command!==normal_value || !busy || queue_guard!==8'h80 || fault)$fatal(1,"saved length normalization");
  enable=0;repeat(13)@(negedge clk);
  m_command_ready=1;@(posedge clk);@(negedge clk);m_command_ready=0;
 end
endtask
task payload;
 input integer length;
 begin
  for(pos=0;pos<length;pos=pos+64)begin
   n=length-pos;if(n>64)n=64;wire_n=((length+3)&~3)-pos;if(wire_n>64)wire_n=64;
   s_axis_tdata={512{1'bx}};s_axis_tkeep=0;
   for(lane=0;lane<wire_n;lane=lane+1)begin
    s_axis_tkeep[lane]=1;s_axis_tdata[lane*8+:8]=lane<n ? ((pos+lane)^8'h5a) : 8'hab;
   end
   s_axis_tlast=pos+64>=length;s_axis_tvalid=1;
   @(posedge clk);if(!s_axis_tready)$fatal(1,"padded data capture");
   @(negedge clk);s_axis_tvalid=0;
   for(lane=0;lane<64;lane=lane+1)
    if(m_axis_tkeep[lane]!==(lane<n) || m_axis_tdata[lane*8+:8]!==
     (lane<n ? (((pos+lane)^8'h5a)&8'hff) : 8'd0))$fatal(1,"pad reached payload or payload changed");
   if(!m_axis_tvalid || m_axis_tlast!==(pos+64>=length))$fatal(1,"unpadded output framing");
   repeat(7)begin @(negedge clk);if(!busy || queue_guard!==8'h80 || fault)$fatal(1,"pad staging owner vanished");end
   m_axis_tready=1;@(posedge clk);@(negedge clk);m_axis_tready=0;
  end
  if(busy || queue_guard || fault || discarded_padding_bytes!==((-length)&3) || context_count!=1 || command_count!=1 || downstream_queue_guard!==8'h80)
   $fatal(1,"pad staging incorrectly ended downstream WR owner");
 end
endtask
initial begin
 rst=1;repeat(4)@(negedge clk);rst=0;enable=1;
 // BODY
 $display("READ_UNPAD_RESULT {\"pass_test\":true,\"contexts\":%0d,\"commands\":%0d,\"padding_bytes\":%0d,\"fault\":%0d,\"cycles\":%0d}",context_count,command_count,discarded_padding_bytes,fault,cycle);
 $finish;
end
endmodule
'''


def bench(body):
    h=RTL.read_text().split(')(\n',1)[1].split('\n);',1)[0]
    ports=re.findall(r'^\s*(input|output)\s+(?:wire|reg)\s+(\[[^]]+\]\s+)?(\w+)(?:=0)?\s*,?$',h,re.M)
    if len(ports)!=30:raise ValueError(('unpad interface changed',len(ports)))
    d='\n'.join(('reg 'if direction=='input'else'wire ')+(w or'')+n+('=0;'if direction=='input'else';')for direction,w,n in ports)
    return TB.replace('// DECLARATIONS',d).replace('// BODY',body)


class ReadUnpadTests(unittest.TestCase):
    reports={}

    def simulate(self,body):
        tb=bench(body);paths=[RTL,Path(__file__).resolve(),ROOT/'rdma/rnic/tests/test_wqe_hls_sq_rtl.py',ROOT/'rdma/rnic/tests/test_wqe_memory_executor_rtl.py']
        before={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in paths}
        with tempfile.TemporaryDirectory(prefix='as02-read-unpad-')as directory:
            p=Path(directory);(p/'tb.v').write_text(tb)
            c=subprocess.run(['iverilog','-g2012','-s','tb','-o',str(p/'test.vvp'),str(p/'tb.v'),str(RTL)],capture_output=True,text=True,timeout=20)
            self.assertEqual(c.returncode,0,c.stdout+c.stderr)
            r=subprocess.run(['vvp',str(p/'test.vvp')],capture_output=True,text=True,timeout=10)
            self.assertEqual(r.returncode,0,r.stdout+r.stderr)
            rows=[json.loads(l[18:])for l in r.stdout.splitlines()if l.startswith('READ_UNPAD_RESULT ')]
            self.assertEqual(len(rows),1,r.stdout);self.assertTrue(rows[0]['pass_test'])
        self.assertEqual(before,{n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest()for n in before})
        self.reports.setdefault(self._testMethodName,[]).append(dict(summary=rows[0],source_sha256=before,bench_sha256=hashlib.sha256(tb.encode()).hexdigest()))

    def test_all_pad_lengths_and_64byte_PMTU_boundaries_do_not_store_pad(self):
        for length in [1,2,3,4,63,64,65,4095,4096]:
            self.simulate(f'capture({context(opcode=2,length=length)});command({raw_command(length=(length+3)&~3)},{raw_command(length=length)});payload({length});')

    def test_all96_raw_bits_including_padded_length_route_and_high_padding_are_checked(self):
        cmd=int(raw_command(length=68).split("'h")[1],16)
        for bit in [0,47,48,75,76,77,78,79,80,83,84,93,94,95]:
            self.simulate(f'capture({context(opcode=2)});s_command=96\'h{cmd^(1<<bit):024x};s_command_valid=1;'+r'''
repeat(7)@(negedge clk);if(!fault || fault_code!=8'ha2 || s_command_ready || m_command_valid || command_count || queue_guard!==8'hff)$fatal(1,"bad HLS ABI repaired into executable command");
''')

    def test_missing_guard_invalid_or_unknown_context_cannot_authorize_unpadding(self):
        for c in [context(opcode=1),context(opcode=2,qpn=0x800007),context(opcode=2,authorized=0),context(opcode=2,tag=0),context(opcode=2,epoch=0),context(opcode=2,sequence=0),context(opcode=2,length=0),context(opcode=2,length=4097),context(opcode=2,address=(1<<64)-1,length=2),"{4'hx,584'd0}"]:
            self.simulate(f'downstream_queue_guard=8\'h80;s_context={c};s_context_valid=1;'+r'''
repeat(7)@(negedge clk);if(!fault || fault_code!=8'ha1 || s_context_ready || m_command_valid || queue_guard!==8'hff)$fatal(1,"invalid context acquired pad authority");
''')
        self.simulate(f's_context={context(opcode=2)};s_context_valid=1;'+r'''
repeat(7)@(negedge clk);if(!fault || s_context_ready || queue_guard!==8'hff)$fatal(1,"missing executor guard accepted context");
''')

    def test_malformed_keep_last_or_unknown_wire_pad_never_reaches_executor(self):
        for inject in ["s_axis_tkeep=1;s_axis_tlast=1;", "s_axis_tkeep=64'hffffffffffffffff;s_axis_tlast=1;", "s_axis_tkeep=64'hffffffffffffffff;s_axis_tdata={512{1'bx}};"]:
            self.simulate(f'capture({context(opcode=2)});command({raw_command(length=68)},{raw_command()});'+inject+r'''
s_axis_tvalid=1;repeat(7)@(negedge clk);if(!fault || fault_code!=8'ha3 || m_axis_tvalid || queue_guard!==8'hff)$fatal(1,"malformed padded data reached executor");
''')

    def test_lost_guard_retains_already_offered_command_and_data(self):
        self.simulate(f'capture({context(opcode=2)});s_command={raw_command(length=68)};s_command_valid=1;'+r'''
@(posedge clk);@(negedge clk);s_command_valid=0;downstream_queue_guard=0;enable=0;repeat(7)@(negedge clk);
if(!fault || fault_code!=8'ha4 || !m_command_valid || queue_guard!==8'hff)$fatal(1,"fault retracted normalized command");
m_command_ready=1;@(posedge clk);@(negedge clk);m_command_ready=0;
if(!busy || command_count!=1 || queue_guard!==8'hff)$fatal(1,"fault fabricated staging drain");
''')
        self.simulate(f'capture({context(opcode=2)});command({raw_command(length=68)},{raw_command()});'+r'''
s_axis_tkeep=64'hffffffffffffffff;s_axis_tdata=512'd3;s_axis_tvalid=1;
@(posedge clk);@(negedge clk);s_axis_tvalid=0;downstream_queue_guard=0;repeat(7)@(negedge clk);
if(!fault || !m_axis_tvalid || queue_guard!==8'hff)$fatal(1,"fault retracted normalized payload");
''')

    @classmethod
    def tearDownClass(cls):
        if name:=os.environ.get('AS02_RNIC_READ_UNPAD_UNIT_REPORT'):
            p=Path(name);p=p if p.is_absolute()else ROOT/p
            d=dict(scope=__doc__,pass_test=len(cls.reports)==5,methods=len(cls.reports),simulations=sum(map(len,cls.reports.values())),tests=cls.reports,
                real_HLS_RX_token_executor_or_DMA=False,actual_WR_completion=False,hardware_verified=False)
            with p.open('x')as out:out.write(json.dumps(d,indent=2)+'\n')


if __name__=='__main__':unittest.main()
