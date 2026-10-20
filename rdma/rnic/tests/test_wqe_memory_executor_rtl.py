# SPDX-License-Identifier: BSD-2-Clause-Views
"""Production WQE/HLS memory executor; MR/HLS/backend/receive/CQ are MODELS.

Checks full saved authority, READ response-context requirement, registered
data/commands, exact status and owner transfer. No real wire/DMA/CQ claimed.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

from test_wqe_hls_sq_rtl import context, DEFAULT

ROOT=Path(__file__).resolve().parents[3]
RTL=ROOT/'rdma/rnic/rtl/rocev2_wqe_memory_executor.v'


def raw_command(address=DEFAULT[10],length=65,qpn=7):
    # Independent memCmd ABI bit offsets, not production concatenation.
    n=(qpn<<84)|(((address>>48)&15)<<80)|(1<<79)|(((address>>52)&1)<<77)|(1<<76)|(length<<48)|(address&((1<<48)-1))
    return f"96'h{n:024x}"


def declarations():
    header=RTL.read_text().split(')(\n',1)[1].split('\n);',1)[0]
    ports=re.findall(r'^\s*(input|output)\s+(?:wire|reg)\s+(\[[^]]+\]\s+)?(\w+)(?:=0)?\s*,?$',header,re.M)
    if len(ports)!=59:raise ValueError(('executor interface changed',len(ports)))
    return '\n'.join(('reg 'if d=='input'else'wire ')+(w or '')+n+('=0;'if d=='input'else';')for d,w,n in ports)


TB=r'''
`timescale 1ns/1ps
module tb;
localparam MAX_QPS=8;
// DECLARATIONS
rocev2_wqe_memory_executor dut(.*);
always #2 clk=~clk;
integer cycle=0,deadline,lane,pos,n;
reg stalled_cmd=0,stalled_data=0,stalled_event=0;
reg [144:0] held_cmd;reg [576:0] held_data;reg [595:0] held_event;
wire [576:0] out_data=m_memory_command_write ?
 {m_axis_memory_write_tdata,m_axis_memory_write_tkeep,m_axis_memory_write_tlast} :
 {m_axis_hls_read_tdata,m_axis_hls_read_tkeep,m_axis_hls_read_tlast};
wire out_valid=m_memory_command_write ? m_axis_memory_write_tvalid : m_axis_hls_read_tvalid;
wire out_ready=m_memory_command_write ? m_axis_memory_write_tready : m_axis_hls_read_tready;
always @(posedge clk)if(!rst)begin
 cycle=cycle+1;if(cycle>5000)$fatal(1,"executor cycle deadline");
 if(stalled_cmd && (!m_memory_command_valid || {m_memory_command_write,m_memory_command_offset,
  m_memory_command_length,m_memory_command_key,m_memory_command_tag}!==held_cmd))$fatal(1,"command retracted/changed");
 if(stalled_data && (!out_valid || out_data!==held_data))$fatal(1,"data retracted/changed");
 if(stalled_event && (!m_memory_event_valid || {m_memory_event_context,m_memory_event_error}!==held_event))$fatal(1,"memory event changed");
 stalled_cmd=m_memory_command_valid&&!m_memory_command_ready;
 held_cmd={m_memory_command_write,m_memory_command_offset,m_memory_command_length,m_memory_command_key,m_memory_command_tag};
 stalled_data=out_valid&&!out_ready;held_data=out_data;
 stalled_event=m_memory_event_valid&&!m_memory_event_ready;held_event={m_memory_event_context,m_memory_event_error};
end
task owner;
 input [587:0] value;
 begin
  @(negedge clk);s_owner_context=value;s_owner_valid=1;
  #0.1;if(queue_guard!==8'h80)$fatal(1,"owner guard gap before ready");
  @(posedge clk);deadline=cycle+100;
  while(!s_owner_ready)begin if(cycle>deadline)$fatal(1,"executor owner deadline");@(posedge clk);end
  @(negedge clk);s_owner_valid=0;s_owner_context=0;
  if(!busy || queue_guard!==8'h80 || m_memory_event_context!==value)$fatal(1,"saved full owner/guard");
 end
endtask
task response;
 begin
  s_read_response_context=m_memory_event_context;s_read_response_valid=1;
  @(posedge clk);if(!s_read_response_ready)$fatal(1,"matching trusted response not accepted");
  @(negedge clk);s_read_response_valid=0;
 end
endtask
task raw;
 input placement;input [95:0] command;
 begin
  if(placement)begin s_hls_write_command=command;s_hls_write_command_valid=1;end
  else begin s_hls_read_command=command;s_hls_read_command_valid=1;end
  @(posedge clk);if(!(placement ? s_hls_write_command_ready : s_hls_read_command_ready))$fatal(1,"raw command not accepted");
  @(negedge clk);s_hls_read_command_valid=0;s_hls_write_command_valid=0;
  if(!m_memory_command_valid || m_memory_command_offset!==64'h210 || m_memory_command_length!=65 ||
   m_memory_command_tag!=16'hffff || m_memory_command_key!==32'h80000008 || m_memory_command_write!==placement)
   $fatal(1,"raw metadata substituted for saved full memory authority");
  enable=0;halt=1;repeat(11)@(negedge clk);
  m_memory_command_ready=1;@(posedge clk);@(negedge clk);m_memory_command_ready=0;
 end
endtask
task data;
 input placement;
 begin
  for(pos=0;pos<65;pos=pos+64)begin
   n=65-pos;if(n>64)n=64;
   if(placement)begin
    s_axis_hls_write_tdata={512{1'bx}};s_axis_hls_write_tkeep=0;
    for(lane=0;lane<n;lane=lane+1)begin s_axis_hls_write_tdata[lane*8+:8]=(pos+lane)^8'h5a;s_axis_hls_write_tkeep[lane]=1;end
    s_axis_hls_write_tlast=pos+64>=65;s_axis_hls_write_tvalid=1;
   end else begin
    s_axis_memory_read_tdata={512{1'bx}};s_axis_memory_read_tkeep=0;
    for(lane=0;lane<n;lane=lane+1)begin s_axis_memory_read_tdata[lane*8+:8]=(pos+lane)^8'h5a;s_axis_memory_read_tkeep[lane]=1;end
    s_axis_memory_read_tlast=pos+64>=65;s_axis_memory_read_tvalid=1;
   end
   @(posedge clk);if(!(placement ? s_axis_hls_write_tready : s_axis_memory_read_tready))$fatal(1,"payload capture");
   @(negedge clk);s_axis_hls_write_tvalid=0;s_axis_memory_read_tvalid=0;
   for(lane=0;lane<64;lane=lane+1)begin
    if(out_data[1+lane] !== (lane<n))$fatal(1,"payload keep");
    if(out_data[65+lane*8+:8] !== (lane<n ? ((pos+lane)^8'h5a) : 8'd0))$fatal(1,"payload bytes/padding");
   end
   if(!out_valid || out_data[0]!==(pos+64>=65))$fatal(1,"payload last/valid");
   repeat(13)begin @(negedge clk);if(m_memory_event_valid || queue_guard!==8'h80 || !busy)$fatal(1,"stalled payload completed WR");end
   if(placement)m_axis_memory_write_tready=1;else m_axis_hls_read_tready=1;
   @(posedge clk);@(negedge clk);m_axis_memory_write_tready=0;m_axis_hls_read_tready=0;
  end
 end
endtask
task status;
 input [7:0] err;
 begin
  s_memory_status_tag=16'hffff;s_memory_status_error=err;s_memory_status_valid=1;
  @(posedge clk);if(!s_memory_status_ready)$fatal(1,"status not accepted");
  @(negedge clk);s_memory_status_valid=0;
  if(!m_memory_event_valid || m_memory_event_error!==err || !busy || queue_guard!==(err!=0 ? 8'hff : 8'h80))$fatal(1,"memory status released WR");
 end
endtask
task handoff;
 begin
  repeat(17)@(negedge clk);downstream_queue_guard=8'h80;m_memory_event_ready=1;
  @(posedge clk);@(negedge clk);m_memory_event_ready=0;
  if(m_memory_event_valid || busy || queue_guard || !downstream_queue_guard)$fatal(1,"guarded event transfer");
  // This is only an EXPLICIT test-model owner release, NOT a real CQ event.
  downstream_queue_guard=0;enable=1;halt=0;
 end
endtask
initial begin
 rst=1;repeat(4)@(negedge clk);rst=0;enable=1;
 // BODY
 $display("WQE_MEMORY_RESULT {\"pass_test\":true,\"owners\":%0d,\"memory_commands\":%0d,\"memory_status\":%0d,\"fault\":%0d,\"cycles\":%0d}",owner_count,command_count,memory_status_count,fault,cycle);
 $finish;
end
endmodule
'''


class WQEMemoryExecutorTests(unittest.TestCase):
    reports={}

    def simulate(self,body):
        tb=TB.replace('// DECLARATIONS',declarations()).replace('// BODY',body)
        paths=[RTL,Path(__file__).resolve(),ROOT/'rdma/rnic/tests/test_wqe_hls_sq_rtl.py']
        before={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in paths}
        with tempfile.TemporaryDirectory(prefix='as02-wqe-memory-')as directory:
            p=Path(directory);(p/'tb.v').write_text(tb)
            c=subprocess.run(['iverilog','-g2012','-s','tb','-o',str(p/'test.vvp'),str(p/'tb.v'),str(RTL)],capture_output=True,text=True,timeout=20)
            self.assertEqual(c.returncode,0,c.stdout+c.stderr)
            r=subprocess.run(['vvp',str(p/'test.vvp')],capture_output=True,text=True,timeout=10)
            self.assertEqual(r.returncode,0,r.stdout+r.stderr)
            rows=[json.loads(l[18:])for l in r.stdout.splitlines()if l.startswith('WQE_MEMORY_RESULT ')]
            self.assertEqual(len(rows),1,r.stdout);self.assertTrue(rows[0]['pass_test'])
        self.assertEqual(before,{n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest()for n in before})
        self.reports.setdefault(self._testMethodName,[]).append(dict(summary=rows[0],source_sha256=before,bench_sha256=hashlib.sha256(tb.encode()).hexdigest()))

    def test_WRITE_source_and_READ_placement_have_full_authority_and_continuous_owner(self):
        for op in [1,2]:
            self.simulate(f'owner({context(opcode=op)});'+('response();'if op==2 else'')+
                f'raw({op==2:d},{raw_command()});data({op==2:d});status(0);handoff();')

    def test_READ_raw_command_cannot_place_bytes_without_trusted_response_context(self):
        self.simulate(f'owner({context(opcode=2)});s_hls_write_command={raw_command()};s_hls_write_command_valid=1;'+r'''
repeat(19)begin @(negedge clk);if(s_hls_write_command_ready || m_memory_command_valid || fault || !busy || queue_guard!==8'h80)$fatal(1,"raw HLS READ response authorized placement");end
response();@(posedge clk);if(!s_hls_write_command_ready)$fatal(1,"trusted placement permit");
@(negedge clk);s_hls_write_command_valid=0;
if(!m_memory_command_valid || fault)$fatal(1,"placement authority not retained");
''')

    def test_all96_raw_command_bits_are_checked_before_backend_offer(self):
        original=int(raw_command().split("'h")[1],16)
        for bit in [0,47,48,75,76,77,78,79,80,83,84,93,94,95]:
            self.simulate(f'owner({context()});s_hls_read_command=96\'h{original^(1<<bit):024x};s_hls_read_command_valid=1;'+r'''
repeat(7)@(negedge clk);if(!fault || fault_code!=8'h82 || m_memory_command_valid || s_hls_read_command_ready || command_count || queue_guard!==8'hff)$fatal(1,"malformed HLS command became DMA");
''')

    def test_trusted_READ_response_context_must_match_every_identity_and_authority_field(self):
        for field,value in [('id',1),('sequence',1),('epoch',1),('qpn',0),('pd',0),('tag',1),('lkey',8),('address',0),('offset',0),('length',64),('remote',0),('rkey',1)]:
            self.simulate(f'owner({context(opcode=2)});s_read_response_context={context(opcode=2,**{field:value})};s_read_response_valid=1;'+r'''
repeat(7)@(negedge clk);if(!fault || fault_code!=8'h83 || s_read_response_ready || m_memory_command_valid || queue_guard!==8'hff)$fatal(1,"wrong READ response identity accepted");
''')

    def test_denials_and_all_failed_fetch_errors_handoff_but_never_DMA(self):
        for err in range(1,16):
            c=context(id=0,opcode=0,flags=0,length=0,lkey=0,address=0,offset=0,remote=0,rkey=0,error=err,source=1,fetch=err,available=0,authorized=0)
            self.simulate(f'owner({c});'+f'if(!m_memory_event_valid || m_memory_event_error!={err} || m_memory_command_valid || command_count)$fatal(1,"failed fetch DMA");handoff();')
        c=context(opcode=0,flags=0,length=0,lkey=0,address=0,offset=0,remote=0,rkey=0,error=32,source=2,authorized=0)
        self.simulate(f'owner({c});if(m_memory_event_error!=32 || m_memory_command_valid)$fatal(1,"MR denial DMA");handoff();')

    def test_invalid_full_context_faults_without_owner_or_DMA(self):
        for c in [context(qpn=0x800007),context(tag=0),context(epoch=0),context(sequence=0),context(length=0),context(length=4097),context(address=(1<<64)-1,length=2),context(offset=(1<<64)-1,length=2),context(remote=(1<<64)-1,length=2),"{4'hx,584'd0}"]:
            self.simulate(f's_owner_context={c};s_owner_valid=1;'+r'''
repeat(7)@(negedge clk);if(!fault || fault_code!=8'h81 || s_owner_ready || owner_count || m_memory_command_valid || queue_guard!==8'hff)$fatal(1,"invalid owner acquired DMA");
''')

    def test_backend_error_exact_status_is_delivered_but_owner_is_quarantined(self):
        self.simulate(f'owner({context()});raw(0,{raw_command()});status(8\'ha5);'+r'''
downstream_queue_guard=8'h80;m_memory_event_ready=1;@(posedge clk);@(negedge clk);m_memory_event_ready=0;
if(!fault || fault_code!=8'h89 || !busy || queue_guard!==8'hff || m_memory_event_valid || memory_status_count!=1)$fatal(1,"DMA error released owner");
''')

    def test_event_ready_without_already_held_downstream_guard_is_not_completion(self):
        self.simulate(f'owner({context()});raw(0,{raw_command()});data(0);status(0);'+r'''
m_memory_event_ready=1;repeat(7)@(negedge clk);
if(!fault || fault_code!=8'h87 || !m_memory_event_valid || !busy || queue_guard!==8'hff)$fatal(1,"event ready caused owner gap");
''')

    def test_bad_tag_and_payload_shape_never_create_success_event(self):
        for mutation in ['s_memory_status_tag=1;s_memory_status_valid=1;',
                         "s_axis_memory_read_tkeep=64'h7;s_axis_memory_read_tvalid=1;",
                         "s_axis_memory_read_tdata={512{1'bx}};s_axis_memory_read_tkeep=64'hffffffffffffffff;s_axis_memory_read_tvalid=1;"]:
            self.simulate(f'owner({context()});raw(0,{raw_command()});'+mutation+r'''
repeat(7)@(negedge clk);if(!fault || m_memory_event_valid || m_axis_hls_read_tvalid || queue_guard!==8'hff)$fatal(1,"bad data/status reached HLS/completion");
''')

    def test_already_offered_command_and_data_survive_fault_disable_and_halt(self):
        self.simulate(f'owner({context()});s_hls_read_command={raw_command()};s_hls_read_command_valid=1;'+r'''
@(posedge clk);@(negedge clk);s_hls_read_command_valid=0;enable=0;halt=1;
s_read_response_valid=1;repeat(7)@(negedge clk);
if(!fault || !m_memory_command_valid || queue_guard!==8'hff)$fatal(1,"fault retracted accepted memory command");
m_memory_command_ready=1;@(posedge clk);@(negedge clk);m_memory_command_ready=0;
if(m_memory_command_valid || command_count!=1 || !busy)$fatal(1,"fault fabricated drain");
''')
        self.simulate(f'owner({context()});raw(0,{raw_command()});'+r'''
s_axis_memory_read_tkeep=64'hffffffffffffffff;s_axis_memory_read_tdata=512'd3;s_axis_memory_read_tvalid=1;
@(posedge clk);@(negedge clk);s_axis_memory_read_tvalid=0;s_read_response_valid=1;
repeat(7)@(negedge clk);if(!fault || !m_axis_hls_read_tvalid || queue_guard!==8'hff)$fatal(1,"fault retracted already offered payload");
m_axis_hls_read_tready=1;@(posedge clk);@(negedge clk);m_axis_hls_read_tready=0;
if(m_axis_hls_read_tvalid || !busy || m_memory_event_valid)$fatal(1,"payload acceptance falsely released owner");
''')

    def test_QP0_PD0_key0_and_exact_exclusive_2pow64_ends_are_not_truncated(self):
        for op in [1,2]:
            address=(1<<64)-65
            c=context(opcode=op,qpn=0,pd=0,lkey=0,address=address,offset=address,remote=address)
            self.simulate(f's_owner_context={c};s_owner_valid=1;'+r'''
@(posedge clk);if(!s_owner_ready || queue_guard!==1)$fatal(1,"valid boundary context rejected");
@(negedge clk);s_owner_valid=0;
'''+('response();'if op==2 else'')+f'''
s_hls_{'write'if op==2 else'read'}_command={raw_command(address=address,qpn=0)};
s_hls_{'write'if op==2 else'read'}_command_valid=1;
@(posedge clk);@(negedge clk);s_hls_read_command_valid=0;s_hls_write_command_valid=0;
if(fault || !m_memory_command_valid || m_memory_command_key!==0 || m_memory_command_offset!==64'h{address:016x} ||
 m_memory_command_length!==65 || queue_guard!==1 || m_memory_event_context!=={c})$fatal(1,"full zero/high authority or legal end2^64 changed");
''')

    def test_opposite_duplicate_and_unknown_raw_commands_never_start_a_second_DMA(self):
        for offer in [f's_hls_write_command={raw_command()};s_hls_write_command_valid=1;',
                      f's_hls_read_command={raw_command()};s_hls_read_command_valid=1;s_hls_write_command_valid=1;',
                      "s_hls_read_command_valid=1'bx;"]:
            self.simulate(f'owner({context()});'+offer+r'''
repeat(7)@(negedge clk);if(!fault || m_memory_command_valid || command_count || queue_guard!==8'hff)$fatal(1,"opposite/unknown command issued DMA");
''')
        self.simulate(f'owner({context()});raw(0,{raw_command()});'+f's_hls_read_command={raw_command()};s_hls_read_command_valid=1;'+r'''
repeat(7)@(negedge clk);if(!fault || m_memory_command_valid || command_count!=1 || queue_guard!==8'hff)$fatal(1,"duplicate issued second DMA");
''')

    def test_early_success_status_waits_for_final_data_and_held_output(self):
        self.simulate(f'owner({context()});raw(0,{raw_command()});'+r'''
s_memory_status_tag=16'hffff;s_memory_status_error=0;s_memory_status_valid=1;
repeat(13)begin @(negedge clk);if(s_memory_status_ready || m_memory_event_valid || fault)$fatal(1,"early status bypassed remaining data");end
s_memory_status_valid=0;
'''+r'''data(0);status(0);handoff();''')

    def test_halt_pauses_new_owner_without_losing_offered_guard(self):
        self.simulate(f'halt=1;s_owner_context={context()};s_owner_valid=1;'+r'''
repeat(13)begin @(negedge clk);if(s_owner_ready || owner_count || m_memory_command_valid || fault || queue_guard!==8'h80)$fatal(1,"halt granted owner or lost its offered guard");end
halt=0;@(posedge clk);if(!s_owner_ready)$fatal(1,"owner did not resume");
@(negedge clk);s_owner_valid=0;enable=0;halt=1;
'''+f'raw(0,{raw_command()});data(0);status(0);handoff();')

    @classmethod
    def tearDownClass(cls):
        if name:=os.environ.get('AS02_RNIC_WQE_MEMORY_EXECUTOR_UNIT_REPORT'):
            p=Path(name);p=p if p.is_absolute()else ROOT/p
            d=dict(scope=__doc__,pass_test=len(cls.reports)==14,methods=len(cls.reports),simulations=sum(map(len,cls.reports.values())),tests=cls.reports,
                real_MR_HLS_backend_receive_CQ=False,actual_WR_completion=False,hardware_verified=False)
            with p.open('x')as out:out.write(json.dumps(d,indent=2)+'\n')


if __name__=='__main__':unittest.main()
