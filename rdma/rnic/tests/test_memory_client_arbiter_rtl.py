# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual memory arbiter RTL; authorized clients/backend are EXPLICIT MODELS.

Not MR authorization, page translation, PCIe DMA, a local transport executor,
CQ publication, drain/reset safety or native runtime evidence.
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
RTL=ROOT/'rdma/rnic/rtl/rocev2_memory_client_arbiter.v'
TB=r'''
`timescale 1ns/1ps
module tb;
// DECLARATIONS
rocev2_memory_client_arbiter dut(.*);
always #2 clk=~clk;
integer cycle=0,commands=0,statuses=0,deadline,packet_index;
reg cmd_stalled=0,write_stalled=0;reg [1:0] read_stalled=0,status_stalled=0;
reg [144:0] held_command;reg [576:0] held_write,held_read[0:1];reg [23:0] held_status[0:1];integer lane;
always @(posedge clk)if(!rst)begin
 cycle=cycle+1;if(cycle>3000)$fatal(1,"arbiter cycle deadline");
 if(cmd_stalled && (!m_command_valid || {m_command_write,m_command_offset,m_command_length,m_command_key,m_command_tag}!==held_command))$fatal(1,"backend command changed/withdrawn");
 if(write_stalled && (!m_axis_write_tvalid || {m_axis_write_tdata,m_axis_write_tkeep,m_axis_write_tlast}!==held_write))$fatal(1,"backend write beat changed/withdrawn");
 cmd_stalled=m_command_valid&&!m_command_ready;held_command={m_command_write,m_command_offset,m_command_length,m_command_key,m_command_tag};
 write_stalled=m_axis_write_tvalid&&!m_axis_write_tready;held_write={m_axis_write_tdata,m_axis_write_tkeep,m_axis_write_tlast};
 for(lane=0;lane<2;lane=lane+1)begin
  if(read_stalled[lane] && (!m_axis_read_tvalid[lane] || {m_axis_read_tdata[lane*512+:512],m_axis_read_tkeep[lane*64+:64],m_axis_read_tlast[lane]}!==held_read[lane]))$fatal(1,"client read beat changed/withdrawn");
  if(status_stalled[lane] && (!m_status_valid[lane] || {m_status_tag[lane*16+:16],m_status_error[lane*8+:8]}!==held_status[lane]))$fatal(1,"client status changed/withdrawn");
  read_stalled[lane]=m_axis_read_tvalid[lane]&&!m_axis_read_tready[lane];held_read[lane]={m_axis_read_tdata[lane*512+:512],m_axis_read_tkeep[lane*64+:64],m_axis_read_tlast[lane]};
  status_stalled[lane]=m_status_valid[lane]&&!m_status_ready[lane];held_status[lane]={m_status_tag[lane*16+:16],m_status_error[lane*8+:8]};
  if(m_status_valid[lane]&&m_status_ready[lane])statuses=statuses+1;
 end
 if(m_command_valid&&m_command_ready)commands=commands+1;
end
task offer;
 input integer client;input wr;input [31:0] key;input [63:0] offset;input [31:0] len;input [15:0] tag;
 begin
  @(negedge clk);s_command_write[client]=wr;s_command_offset[client*64+:64]=offset;
  s_command_length[client*32+:32]=len;s_command_key[client*32+:32]=key;s_command_tag[client*16+:16]=tag;
  s_command_valid[client]=1;
 end
endtask
task accept;
 input integer client;input wr;input [31:0] key;input [63:0] offset;input [31:0] len;input [15:0] tag;
 begin
  deadline=cycle+50;@(posedge clk);while(!s_command_ready[client])begin if(cycle>deadline)$fatal(1,"input command deadline");@(posedge clk);end
  @(negedge clk);s_command_valid[client]=0;
  if(!m_command_valid || {m_command_write,m_command_offset,m_command_length,m_command_key,m_command_tag}!=={wr,offset,len,key,tag} || client_guard!==(2'b01<<client))$fatal(1,"full command/owner corrupted");
  repeat(4)@(negedge clk);enable=0;m_command_ready=1;
  @(posedge clk);@(negedge clk);m_command_ready=0;
 end
endtask
task read_beat;
 input integer client;input [511:0] bytes;input [63:0] keep;input last;input [511:0] expected;
 begin
  @(negedge clk);s_axis_read_tdata=bytes;s_axis_read_tkeep=keep;s_axis_read_tlast=last;s_axis_read_tvalid=1;
  @(posedge clk);while(!s_axis_read_tready)@(posedge clk);
  @(negedge clk);s_axis_read_tvalid=0;
  if(m_axis_read_tvalid!==(2'b01<<client) || m_axis_read_tdata[client*512+:512]!==expected ||
   m_axis_read_tkeep[client*64+:64]!==keep || m_axis_read_tlast[client]!==last ||
   m_axis_read_tdata[(!client)*512+:512]!==0 || m_axis_read_tkeep[(!client)*64+:64]!==0)$fatal(1,"read ownership/bytes/padding");
  repeat(5)@(negedge clk);m_axis_read_tready[client]=1;
  @(posedge clk);@(negedge clk);m_axis_read_tready=0;
 end
endtask
task write_beat;
 input integer client;input [511:0] bytes;input [63:0] keep;input last;input [511:0] expected;
 begin
  @(negedge clk);s_axis_write_tdata[client*512+:512]=bytes;s_axis_write_tkeep[client*64+:64]=keep;
  s_axis_write_tlast[client]=last;s_axis_write_tvalid[client]=1;
  @(posedge clk);while(!s_axis_write_tready[client])@(posedge clk);
  @(negedge clk);s_axis_write_tvalid=0;
  if(!m_axis_write_tvalid || m_axis_write_tdata!==expected || m_axis_write_tkeep!==keep || m_axis_write_tlast!==last || s_axis_write_tready[!client])$fatal(1,"write ownership/bytes/padding");
  repeat(5)@(negedge clk);m_axis_write_tready=1;
  @(posedge clk);@(negedge clk);m_axis_write_tready=0;
 end
endtask
task status;
 input integer client;input [15:0] tag;input [7:0] error;
 begin
  @(negedge clk);s_status_tag=tag;s_status_error=error;s_status_valid=1;
  @(posedge clk);while(!s_status_ready)@(posedge clk);
  @(negedge clk);s_status_valid=0;
  if(m_status_valid!==(2'b01<<client) || m_status_tag[client*16+:16]!==tag || m_status_error[client*8+:8]!==error || !busy)$fatal(1,"status owner/context/error");
  repeat(7)@(negedge clk);m_status_ready[client]=1;
  @(posedge clk);@(negedge clk);m_status_ready=0;
 end
endtask
initial begin
 rst=1;repeat(4)@(negedge clk);rst=0;enable=1;
 // BODY
 $display("MEMORY_ARBITER_RESULT {\"pass_test\":true,\"commands\":%0d,\"statuses\":%0d,\"cycles\":%0d,\"fault\":%0d}",commands,statuses,cycle,fault);
 $finish;
end
endmodule
'''


def declarations():
    header=RTL.read_text().split('module rocev2_memory_client_arbiter (',1)[1].split('\n);',1)[0]
    ports=re.findall(r'^\s*(input|output)\s+(?:wire|reg)\s+(\[[^]]+\]\s+)?(\w+)(?:=0)?\s*,?$',header,re.M)
    if len(ports)!=50:raise ValueError(('arbiter port declaration changed',len(ports)))
    return '\n'.join(('reg 'if d=='input'else'wire ')+(w or '')+n+('=0;'if d=='input'else';')for d,w,n in ports)


class MemoryClientArbiterTests(unittest.TestCase):
    reports={}

    def simulate(self,body):
        tb=TB.replace('// DECLARATIONS',declarations()).replace('// BODY',body)
        paths=[RTL,Path(__file__).resolve()];before={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in paths}
        with tempfile.TemporaryDirectory(prefix='as02-memory-arbiter-')as directory:
            p=Path(directory);(p/'tb.v').write_text(tb)
            c=subprocess.run(['iverilog','-g2012','-s','tb','-o',str(p/'test.vvp'),str(p/'tb.v'),str(RTL)],capture_output=True,text=True,timeout=20)
            self.assertEqual(c.returncode,0,c.stdout+c.stderr)
            r=subprocess.run(['vvp',str(p/'test.vvp')],capture_output=True,text=True,timeout=10)
            self.assertEqual(r.returncode,0,r.stdout+r.stderr)
            rows=[json.loads(l[22:])for l in r.stdout.splitlines()if l.startswith('MEMORY_ARBITER_RESULT ')]
            self.assertEqual(len(rows),1,r.stdout);self.assertTrue(rows[0]['pass_test'])
        self.assertEqual(before,{n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest()for n in before})
        self.reports.setdefault(self._testMethodName,[]).append(dict(summary=rows[0],source_sha256=before,bench_sha256=hashlib.sha256(tb.encode()).hexdigest()))

    def test_both_clients_full_key_offset_tag_and_registered_data_status_ownership(self):
        self.simulate(r'''
offer(0,0,32'hfedcba98,64'hf123456789abc001,65,16'hffff);
accept(0,0,32'hfedcba98,64'hf123456789abc001,65,16'hffff);
read_beat(0,{64{8'ha5}},64'hffffffffffffffff,0,{64{8'ha5}});
read_beat(0,{504'hx,8'hc7},1,1,512'hc7);status(0,16'hffff,0);
if(busy || configuration_guard || fault)$fatal(1,"successful owner not retired");enable=1;
offer(1,1,32'h80000000,64'hffffffffffffffbf,65,16'hffff);
accept(1,1,32'h80000000,64'hffffffffffffffbf,65,16'hffff);
write_beat(1,{64{8'h5a}},64'hffffffffffffffff,0,{64{8'h5a}});
write_beat(1,{504'hx,8'h31},1,1,512'h31);status(1,16'hffff,0);
if(busy || client_guard || commands!=2 || statuses!=2 || fault)$fatal(1,"same tags aliased/false idle");
''')

    def test_continuously_offered_competitor_keeps_full_tuple_and_round_robin(self):
        self.simulate(r'''
enable=0;offer(0,0,0,64'h8000000000000000,1,0);
offer(1,0,32'hffffffff,64'h9000000000000000,1,0);
enable=1;
accept(0,0,0,64'h8000000000000000,1,0);
read_beat(0,512'h11,1,1,512'h11);status(0,0,0);enable=1;
accept(1,0,32'hffffffff,64'h9000000000000000,1,0);
read_beat(1,512'h22,1,1,512'h22);status(1,0,0);
if(fault || busy || statuses!=2)$fatal(1,"fair/full context result");
''')

    def test_invalid_full_width_and_unknown_command_never_reaches_backend(self):
        for command in ["s_command_offset[63:0]=64'hffffffffffffffff;s_command_length[31:0]=2;",
                        's_command_length[31:0]=0;','s_command_length[31:0]=4097;',
                        "s_command_key[31:28]=4'hx;","s_command_offset[63:60]=4'hx;", "s_command_valid=2'bx1;"]:
            with self.subTest(command=command):self.simulate('enable=0;offer(0,0,8,0,1,1);'+command+r'''
enable=1;repeat(10)@(negedge clk);
if(!fault || fault_code!=8'h61 || !busy || client_guard!=3 || m_command_valid || s_command_ready || m_status_valid)$fatal(1,"invalid command gained authority/released ownership");
''')

    def test_wrong_or_unknown_status_retains_already_offered_read_beat(self):
        for bad in ["s_status_tag=16'hfffe;", "s_status_error=8'hxx;"]:
            with self.subTest(status=bad):self.simulate(r'''
offer(1,0,32'hffffffff,0,1,16'hffff);accept(1,0,32'hffffffff,0,1,16'hffff);
@(negedge clk);s_axis_read_tdata=512'h1234;s_axis_read_tkeep=1;s_axis_read_tlast=1;s_axis_read_tvalid=1;
@(posedge clk);while(!s_axis_read_tready)@(posedge clk);
@(negedge clk);s_axis_read_tvalid=0;s_status_tag=16'hffff;s_status_error=0;
'''+bad+r'''
s_status_valid=1;repeat(8)@(negedge clk);
if(!fault || fault_code!=8'h62 || !busy || client_guard!=3 || s_status_ready || m_status_valid || m_axis_read_tvalid!=2 || m_axis_read_tdata[512+:512]!==512'h34)$fatal(1,"corrupt status erased offered ownership");
m_axis_read_tready=2;@(posedge clk);@(negedge clk);m_axis_read_tready=0;s_status_valid=0;
if(!fault || !busy || m_status_valid)$fatal(1,"fault fabricated completion");
''')

    def test_all_known_backend_errors_return_exact_error_without_safe_release(self):
        for error in range(1,16):
            with self.subTest(error=error):self.simulate(r'''
offer(1,0,32'h80000000,0,65,16'hffff);accept(1,0,32'h80000000,0,65,16'hffff);
'''+f'status(1,16\'hffff,8\'d{error});'+r'''
enable=1;repeat(5)@(negedge clk);
if(!fault || fault_code!=8'h65 || !busy || client_guard!=3 || m_command_valid || s_command_ready || m_status_valid || commands!=1 || statuses!=1)$fatal(1,"DMA error was mistaken for safe release");
''')

    def test_malformed_owned_data_does_not_reach_other_client_or_backend(self):
        for wr in [False,True]:
            for mutation in ["KEEP=64'h2;LAST=1;DATA=1;", "KEEP=1;LAST=0;DATA=1;",
                             "KEEP=1;LAST=1;DATA=512'hx;", "KEEP=64'hx;LAST=1;DATA=1;"]:
                with self.subTest(write=wr,mutation=mutation):
                    prefix='s_axis_write_'if wr else's_axis_read_'
                    fields={"KEEP":prefix+'tkeep'+('[64+:64]'if wr else''),
                        "LAST":prefix+'tlast'+('[1]'if wr else''),"DATA":prefix+'tdata'+('[512+:512]'if wr else'')}
                    for old,new in fields.items():mutation=mutation.replace(old,new)
                    self.simulate(f"offer(1,{int(wr)},32'hffffffff,0,1,16'hffff);accept(1,{int(wr)},32'hffffffff,0,1,16'hffff);\n"+
                        '@(negedge clk);'+mutation+("s_axis_write_tvalid=2;"if wr else"s_axis_read_tvalid=1;")+r'''
repeat(8)@(negedge clk);
if(!fault || fault_code!=8'h63 || !busy || client_guard!=3 || m_axis_write_tvalid || m_axis_read_tvalid || m_status_valid)$fatal(1,"malformed data gained authority or released ownership");
''')

    def test_fault_and_disable_do_not_retract_already_offered_backend_command(self):
        self.simulate(r'''
offer(1,0,32'hfedcba98,64'h8123456789abcdef,65,16'hffff);
@(posedge clk);while(!s_command_ready[1])@(posedge clk);
@(negedge clk);s_command_valid=0;enable=0;s_status_valid=1'bx;
repeat(8)@(negedge clk);
if(!fault || fault_code!=8'h62 || !busy || client_guard!=3 || !m_command_valid ||
 {m_command_offset,m_command_length,m_command_key,m_command_tag}!=={64'h8123456789abcdef,32'd65,32'hfedcba98,16'hffff})$fatal(1,"fault withdrew accepted command");
s_status_valid=0;m_command_ready=1;@(posedge clk);@(negedge clk);m_command_ready=0;
repeat(5)@(negedge clk);if(m_command_valid || !busy || !fault || m_status_valid || s_command_ready)$fatal(1,"fault invented safe completion");
''')

    def test_backend_success_waits_for_actual_last_data_handoff(self):
        self.simulate(r'''
offer(1,0,8,0,1,16'hffff);accept(1,0,8,0,1,16'hffff);
@(negedge clk);s_axis_read_tdata=512'h5a;s_axis_read_tkeep=1;s_axis_read_tlast=1;s_axis_read_tvalid=1;
@(posedge clk);while(!s_axis_read_tready)@(posedge clk);
@(negedge clk);s_axis_read_tvalid=0;s_status_tag=16'hffff;s_status_error=0;s_status_valid=1;
repeat(8)begin @(negedge clk);if(s_status_ready || m_status_valid || fault || m_axis_read_tvalid!=2 || !busy)$fatal(1,"status bypassed stalled last data");end
m_axis_read_tready=2;@(posedge clk);@(negedge clk);m_axis_read_tready=0;
@(posedge clk);while(!s_status_ready)@(posedge clk);
@(negedge clk);s_status_valid=0;
if(m_status_valid!=2 || m_status_tag[31:16]!==16'hffff || m_status_error || fault)$fatal(1,"last-data status context");
m_status_ready=2;@(posedge clk);@(negedge clk);m_status_ready=0;
if(busy || client_guard || fault || commands!=1 || statuses!=1)$fatal(1,"last-data owner release");
''')

    def test_extra_data_while_final_read_beat_stalls_retains_that_accepted_beat(self):
        self.simulate(r'''
offer(1,0,8,0,1,16'hffff);accept(1,0,8,0,1,16'hffff);
@(negedge clk);s_axis_read_tdata=512'h5a;s_axis_read_tkeep=1;s_axis_read_tlast=1;s_axis_read_tvalid=1;
@(posedge clk);while(!s_axis_read_tready)@(posedge clk);
@(negedge clk);s_axis_read_tdata=512'hff;
repeat(8)@(negedge clk);
if(!fault || fault_code!=8'h64 || !busy || client_guard!=3 || s_axis_read_tready || m_status_valid ||
 m_axis_read_tvalid!=2 || m_axis_read_tdata[512+:512]!==512'h5a)$fatal(1,"extra data replaced held authorized last beat");
s_axis_read_tvalid=0;m_axis_read_tready=2;@(posedge clk);@(negedge clk);m_axis_read_tready=0;
if(!busy || !fault || m_status_valid)$fatal(1,"extra-data fault released owner");
''')

    def test_full4096_capacity_and_exclusive_offset_end_two_to64(self):
        self.simulate(r'''
offer(1,0,32'hffffffff,64'hfffffffffffff000,4096,16'hffff);
accept(1,0,32'hffffffff,64'hfffffffffffff000,4096,16'hffff);
for(packet_index=0;packet_index<64;packet_index=packet_index+1)
 read_beat(1,{64{packet_index[7:0]}},64'hffffffffffffffff,packet_index==63,{64{packet_index[7:0]}});
status(1,16'hffff,0);
if(fault || busy || client_guard || commands!=1 || statuses!=1)$fatal(1,"full capacity or DMA64end reduced");
''')

    @classmethod
    def tearDownClass(cls):
        if name:=os.environ.get('AS02_RNIC_MEMORY_ARBITER_UNIT_REPORT'):
            p=Path(name);p=p if p.is_absolute()else ROOT/p
            d=dict(scope=__doc__,pass_test=len(cls.reports)==10,methods=len(cls.reports),simulations=sum(map(len,cls.reports.values())),tests=cls.reports,
                actual_MR_PTE_PCIe=False,actual_local_executor_CQ=False,hardware_verified=False,completion_claim=False)
            with p.open('x')as out:out.write(json.dumps(d,indent=2)+'\n')


if __name__=='__main__':unittest.main()
