#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Short real-RTL MR authorization tests; no hardware/network/kernel changes."""
import hashlib
import json
import os
from pathlib import Path
import random
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[3]
RTL=ROOT/'rdma/rnic/rtl/rocev2_mr_table.v'
LIMIT=1<<64
MAX_GENERATION=(1<<29)-1

TB=r'''
`timescale 1ns/1ps
module tb;
reg clk=0;always #2 clk=~clk;
reg rst=1,quiet=1,cv=0,car=0,qv=0,mr=0;
reg [1:0] cc=0;reg [2:0] ci=0,qo=0;
reg [15:0] cp=0,qp=0,qt=0;
reg [31:0] ck=0,qk=0,ql=0;
reg [63:0] ca=0,cd=0,cl=0,qa=0;
reg [3:0] cf=0;
wire cr,cav,qr,mv,ep;wire [7:0] ce,me;
wire [31:0] cak,ml;wire [15:0] mt;wire [63:0] mo,md;
rocev2_mr_table #(.INITIAL_GENERATION(INITIAL_GENERATION_VALUE),.REQUIRE_EPOCH(EPOCH_REQUIRED_VALUE)) dut(
 .clk(clk),.rst(rst),.cfg_quiescent(quiet),.cfg_command(cc),.cfg_index(ci),
 .cfg_pd(cp),.cfg_key(ck),.cfg_virtual_address(ca),.cfg_dma_address(cd),
 .cfg_length(cl),.cfg_access(cf),.cfg_valid(cv),.cfg_ready(cr),
 .cfg_response_error(ce),.cfg_response_key(cak),.cfg_response_valid(cav),.cfg_response_ready(car),
 .epoch_configured(ep),
 .s_request_pd(qp),.s_request_key(qk),.s_request_address(qa),.s_request_length(ql),
 .s_request_operation(qo),.s_request_tag(qt),.s_request_valid(qv),.s_request_ready(qr),
 .m_response_tag(mt),.m_response_error(me),.m_response_offset(mo),
 .m_response_dma_address(md),.m_response_length(ml),.m_response_valid(mv),.m_response_ready(mr));
integer cycles=0,management_count=0,query_count=0,stalled_cycles=0;
always @(posedge clk) begin cycles=cycles+1;if(cycles>100000) $fatal(1,"deadline");end
task management;
 input [2:0] index;input [1:0] command;input [15:0] pd;input [31:0] key;
 input [63:0] va,dma,length;input [3:0] flags;input [7:0] error;
 input [31:0] response_key;
 begin
  @(negedge clk);ci=index;cc=command;cp=pd;ck=key;ca=va;cd=dma;cl=length;cf=flags;cv=1;car=0;
  @(posedge clk);while(!cr) @(posedge clk);
  @(negedge clk);cv=0;
  while(!cav) @(negedge clk);
  if(ce!==error || cak!==response_key) $fatal(1,"config index=%d cmd=%d error=%d/%d key=%h/%h",index,command,ce,error,cak,response_key);
  repeat(3) begin
   @(negedge clk);stalled_cycles=stalled_cycles+1;
   if(!cav || ce!==error || cak!==response_key || cr || qr) $fatal(1,"config result unstable/ownership lost");
  end
  car=1;@(negedge clk);car=0;management_count=management_count+1;
 end
endtask
task request;
 input [15:0] pd;input [31:0] key;input [63:0] address;
 input [31:0] length;input [2:0] operation;input [15:0] tag;
 input [7:0] error;input [63:0] offset,dma;input [31:0] out_length;
 begin
  @(negedge clk);qp=pd;qk=key;qa=address;ql=length;qo=operation;qt=tag;qv=1;mr=0;
  @(posedge clk);while(!qr) @(posedge clk);
  @(negedge clk);qv=0;
  while(!mv) @(negedge clk);
  if(mt!==tag || me!==error || mo!==offset || md!==dma || ml!==out_length)
   $fatal(1,"query tag=%d got=%d/%h/%h/%d expected=%d/%h/%h/%d",tag,me,mo,md,ml,error,offset,dma,out_length);
  repeat(3) begin
   @(negedge clk);stalled_cycles=stalled_cycles+1;
   if(!mv || mt!==tag || me!==error || mo!==offset || md!==dma || ml!==out_length || qr || cr)
    $fatal(1,"query response unstable/reconfigured under stall");
  end
  mr=1;@(negedge clk);mr=0;query_count=query_count+1;
 end
endtask
initial begin
 repeat(4) @(negedge clk);rst=0;
 // BODY
 $display("RESULT {\"pass_test\":true,\"management_commands\":%0d,\"queries\":%0d,\"stalled_cycles\":%0d,\"cycles\":%0d}",management_count,query_count,stalled_cycles,cycles);
 $finish;
end
endmodule
'''


class Oracle:
    """Independent integer-range model; generates no DUT internal accesses."""
    def __init__(self,initial=0,require_epoch=False):
        self.generations=[initial]*8
        self.entries=[None]*8
        self.body=[]
        self.requests=0
        self.managements=0
        self.require_epoch=require_epoch
        self.seeded=not require_epoch

    def manage(self,index,command,pd=17,key=0,va=0x100000000,dma=0x800000000,
               length=4096,flags=7):
        entry=self.entries[index];error=0;result=0
        if self.require_epoch and not self.seeded and command!=3:error=10
        elif command==3:
            if not self.require_epoch:error=5
            elif self.seeded:error=6
            elif key>=MAX_GENERATION:error=8
            else:
                self.seeded=True;self.generations=[key]*8;result=key
        elif command==1:
            if entry is not None:error=6
            elif length==0 or va+length>LIMIT or dma+length>LIMIT or key!=0 or flags&10 and not flags&1:error=8
            elif self.generations[index]==MAX_GENERATION:error=7
            else:
                self.generations[index]+=1;result=self.generations[index]*8+index
                self.entries[index]=dict(key=result,pd=pd,va=va,dma=dma,length=length,flags=flags)
        elif command==2:
            if entry is None or key!=entry['key']:error=1
            elif pd!=entry['pd']:error=2
            else:self.entries[index]=None
        else:error=5
        self.body.append(f"management(3'd{index},2'd{command},16'd{pd},32'h{key:x},64'h{va:x},64'h{dma:x},64'h{length:x},4'h{flags:x},8'd{error},32'h{result:x});")
        self.managements+=1
        return result,error

    def query(self,pd,key,address,length,operation):
        entry=self.entries[key%8];error=0;offset=dma=out_length=0
        if entry is None or key!=entry['key']:error=1
        elif pd!=entry['pd']:error=2
        elif operation>4:error=5
        elif operation and not entry['flags']&{1:1,2:4,3:2,4:8}[operation]:error=3
        elif length==0 or address<entry['va'] or address+length>entry['va']+entry['length']:error=4
        elif operation==4 and (length!=8 or address%8 or (entry['dma']+address-entry['va'])%8):error=9
        else:
            offset=address-entry['va'];dma=entry['dma']+offset;out_length=length
        tag=(self.requests*977+65535)&0xffff
        self.body.append(f"request(16'd{pd},32'h{key:x},64'h{address:x},32'h{length:x},3'd{operation},16'd{tag},8'd{error},64'h{offset:x},64'h{dma:x},32'h{out_length:x});")
        self.requests+=1
        return error


class MRTableRTLTests(unittest.TestCase):
    reports={}

    def simulate(self,oracle,initial=0):
        bench=TB.replace('INITIAL_GENERATION_VALUE',str(initial)).replace('EPOCH_REQUIRED_VALUE',str(int(oracle.require_epoch))).replace('// BODY','\n'.join(oracle.body))
        self.assertNotIn('dut.',bench,'test must not force or inspect DUT internals')
        with tempfile.TemporaryDirectory(prefix='as02-mr-table-') as directory:
            path=Path(directory);(path/'tb.v').write_text(bench)
            built=subprocess.run(['iverilog','-g2012','-s','tb','-o',str(path/'test.vvp'),str(path/'tb.v'),str(RTL)],
                                 capture_output=True,text=True,timeout=20)
            self.assertEqual(built.returncode,0,built.stderr)
            ran=subprocess.run(['vvp',str(path/'test.vvp')],capture_output=True,text=True,timeout=15)
            self.assertEqual(ran.returncode,0,ran.stdout+ran.stderr)
            rows=[json.loads(line[7:]) for line in ran.stdout.splitlines() if line.startswith('RESULT ')]
            self.assertEqual(len(rows),1,ran.stdout)
            report=rows[0];self.assertEqual(report['queries'],oracle.requests)
            self.assertEqual(report['management_commands'],oracle.managements)
            self.reports[self._testMethodName]=report

    def test_all_slots_full_keys_domains_and_invalidation(self):
        o=Oracle()
        for index in range(8):
            key,error=o.manage(index,1,pd=100+index,va=0x100000000+index*8192)
            self.assertEqual(error,0)
            o.query(100+index,key,0x100000000+index*8192+19,65,2)
            o.query(101+index,key,0x100000000+index*8192,1,2)
            o.query(100+index,key^(1<<31),0x100000000+index*8192,1,2)
            o.manage(index,2,pd=100+index,key=key)
            o.query(100+index,key,0x100000000+index*8192,1,2)
            replacement,_=o.manage(index,1,pd=100+index,va=0x100000000+index*8192)
            self.assertNotEqual(key,replacement)
            o.query(100+index,key,0x100000000+index*8192,1,2)
            o.query(100+index,replacement,0x100000000+index*8192,1,2)
        self.simulate(o)

    def test_permission_matrix_and_unknown_operations(self):
        o=Oracle()
        for flags in range(16):
            key,error=o.manage(0,1,flags=flags)
            if error:continue
            for op in range(8):
                o.query(17,key,0x100000008,8,op)
                o.query(18,key,0x100000008,8,op)
                o.query(17,key+8,0x100000008,8,op)
            o.manage(0,2,key=key)
        self.simulate(o)

    def test_64bit_exclusive_end_and_overflow_boundaries(self):
        o=Oracle()
        o.manage(0,1,va=LIMIT-16,length=17)
        o.manage(0,1,dma=LIMIT-16,length=17)
        o.manage(0,1,length=0)
        key,_=o.manage(0,1,va=LIMIT-4096,dma=LIMIT-4096,length=4096)
        for address,length in [(LIMIT-4096,4096),(LIMIT-1,1),(LIMIT-4097,1),
                               (LIMIT-1,2),(LIMIT-10,0),(0,1),(LIMIT-4096,0xffffffff)]:
            o.query(17,key,address,length,2)
        o.manage(0,2,key=key)
        key,_=o.manage(0,1,va=0,dma=0,length=LIMIT-1)
        o.query(17,key,LIMIT-2,1,2);o.query(17,key,LIMIT-2,2,2)
        o.query(17,key,0,0xffffffff,2)
        self.simulate(o)

    def test_atomic_permissions_virtual_and_dma_alignment(self):
        o=Oracle();key,_=o.manage(0,1,flags=15)
        for delta,length in [(0,8),(1,8),(8,4),(16,16),(4088,8),(4096,8)]:
            o.query(17,key,0x100000000+delta,length,4)
        o.manage(0,2,key=key)
        key,_=o.manage(0,1,flags=15,dma=0x800000001)
        o.query(17,key,0x100000000,8,4)
        o.query(17,key,0x100000000,8,2)
        self.simulate(o)

    def test_failed_management_never_changes_active_region(self):
        o=Oracle();key,_=o.manage(4,1)
        for command,pd,wrong_key in [(1,99,0),(2,18,key),(2,17,key+8),(0,17,key),(3,17,key)]:
            o.manage(4,command,pd=pd,key=wrong_key,va=99,dma=15,length=128,flags=15)
            o.query(17,key,0x100000007,65,2)
        o.manage(4,2,key=key);o.query(17,key,0x100000007,65,2)
        self.simulate(o)

    def test_generation_exhaustion_refuses_reuse(self):
        initial=MAX_GENERATION-2;o=Oracle(initial)
        for _ in range(2):
            key,error=o.manage(7,1);self.assertEqual(error,0)
            o.query(17,key,0x100000000,8,2);o.manage(7,2,key=key)
            o.query(17,key,0x100000000,8,2)
        self.assertEqual(key,0xffffffff)
        _,error=o.manage(7,1);self.assertEqual(error,7)
        o.query(17,key,0x100000000,8,2)
        self.simulate(o,initial)

    def test_reconfiguration_waits_for_result_and_external_quiescence(self):
        o=Oracle();key,_=o.manage(0,1)
        o.body.append(r'''
@(negedge clk);qp=17;qk=8;qa=64'h100000010;ql=8;qo=2;qt=91;qv=1;mr=0;
@(posedge clk);while(!qr) @(posedge clk);
@(negedge clk);qv=0;quiet=0;cc=2;ci=0;cp=17;ck=8;cv=1;car=0;
while(!mv) begin @(negedge clk);if(cr || cav) $fatal(1,"mutated during lookup");end
repeat(5) begin
 @(negedge clk);
 if(cr || cav || !mv || mt!=91 || me!=0 || md!=64'h800000010 || ml!=8)
  $fatal(1,"mutation/result race");
end
mr=1;@(negedge clk);mr=0;
repeat(5) begin @(negedge clk);if(cr || cav) $fatal(1,"lookup idle substituted for drained leases");end
quiet=1;@(posedge clk);if(!cr || qr) $fatal(1,"management priority lost");
@(negedge clk);cv=0;
while(!cav) @(negedge clk);
if(!cav || ce!=0 || cak!=0) $fatal(1,"deferred invalidate failed");
car=1;@(negedge clk);car=0;query_count=query_count+1;management_count=management_count+1;
''')
        o.entries[0]=None;o.requests+=1;o.managements+=1
        o.query(17,key,0x100000010,8,2)
        self.simulate(o)

    def test_explicit_epoch_required_before_registration_or_lookup(self):
        o=Oracle(require_epoch=True)
        o.body.append(r'''
if(ep) $fatal(1,"implicit key epoch after reset");
@(negedge clk);qv=1;qp=17;qk=8;qa=64'h100000000;ql=1;qo=2;mr=1;
repeat(5) begin @(negedge clk);if(qr || mv || ep) $fatal(1,"lookup admitted before epoch");end
qv=0;mr=0;
''')
        o.manage(0,1)
        o.manage(0,3,key=0)
        key,_=o.manage(0,1)
        o.query(17,key,0x100000000,65,2)
        o.manage(0,3,key=1)
        o.query(17,key,0x100000000,65,2)
        self.simulate(o)

    def test_new_epoch_rejects_pre_reset_key(self):
        o=Oracle(require_epoch=True);o.manage(0,3,key=7)
        old,_=o.manage(0,1);o.query(17,old,0x100000000,65,2)
        o.body.append(r'''
@(negedge clk);rst=1;repeat(4) @(negedge clk);rst=0;
if(ep || qr || mv) $fatal(1,"reset reused prior epoch");
''')
        o.entries=[None]*8;o.generations=[0]*8;o.seeded=False
        o.manage(0,1)
        o.manage(0,3,key=8)
        new,_=o.manage(0,1);self.assertNotEqual(new,old)
        o.query(17,old,0x100000000,65,2)
        o.query(17,new,0x100000000,65,2)
        self.simulate(o)

    def test_epoch_invalid_seed_double_seed_and_generation_exhaustion(self):
        o=Oracle(require_epoch=True)
        o.manage(0,3,key=0x80000000)
        o.manage(0,3,key=MAX_GENERATION)
        o.manage(0,1)
        o.manage(0,3,key=MAX_GENERATION-1)
        key,_=o.manage(0,1)
        o.manage(0,3,key=0)
        o.query(17,key,0x100000000,1,2)
        o.manage(0,2,key=key)
        o.manage(0,1)
        self.simulate(o)

    def test_management_payload_is_captured_and_lost_quiescence_aborts(self):
        o=Oracle();key,_=o.manage(0,1)
        o.body.append(r'''
@(negedge clk);cc=1;ci=1;cp=99;ck=0;ca=64'h12340000;cd=64'h98760000;cl=65;cf=7;cv=1;car=0;
@(posedge clk);while(!cr) @(posedge clk);
@(negedge clk);cv=0;ci=7;cp=0;ck=32'hffffffff;ca=0;cd=0;cl=0;cf=0;
if(cr || qr) $fatal(1,"management pipeline ownership lost");
while(!cav) @(negedge clk);
if(ce!=0 || cak!=9) $fatal(1,"management reread changed inputs");
car=1;@(negedge clk);car=0;management_count=management_count+1;
''')
        o.generations[1]=1;o.entries[1]=dict(key=9,pd=99,va=0x12340000,dma=0x98760000,length=65,flags=7);o.managements+=1
        o.query(99,9,0x12340001,64,2)
        o.body.append(r'''
@(negedge clk);cc=2;ci=1;cp=99;ck=9;cv=1;car=0;
@(posedge clk);while(!cr) @(posedge clk);
@(negedge clk);cv=0;quiet=0;
while(!cav) @(negedge clk);
if(ce!=6 || cak!=0) $fatal(1,"nonquiescent apply mutated MR");
quiet=1;car=1;@(negedge clk);car=0;management_count=management_count+1;
''')
        o.managements+=1
        o.query(99,9,0x12340001,64,2)
        o.query(17,key,0x100000000,1,2)
        self.simulate(o)

    def test_deterministic_randomized_management_and_query_scoreboard(self):
        o=Oracle();rng=random.Random(0x455a2026)
        for _ in range(400):
            index=rng.randrange(8);entry=o.entries[index]
            if rng.randrange(5)==0:
                if entry and rng.randrange(2):o.manage(index,2,pd=entry['pd'],key=entry['key'])
                else:o.manage(index,rng.randrange(4),pd=rng.randrange(4),key=0,
                              va=rng.choice([0,0x100000000,LIMIT-1024]),dma=rng.choice([0,0x800000000,LIMIT-1024]),
                              length=rng.choice([0,1,1024,4096]),flags=rng.randrange(16))
            elif entry:
                key=entry['key'] if rng.randrange(4) else entry['key']^0x80000000
                address=(entry['va']+rng.choice([-1,0,1,8,entry['length']-1,entry['length']]))%LIMIT
                o.query(rng.choice([entry['pd'],99]),key,address,rng.choice([0,1,8,65,4096]),rng.randrange(8))
            else:o.query(0,rng.randrange(1<<29)*8+index,rng.randrange(LIMIT),rng.randrange(4097),rng.randrange(8))
        self.simulate(o)

    @classmethod
    def tearDownClass(cls):
        if name:=os.environ.get('AS02_RNIC_MR_REPORT'):
            report=dict(scope='Real standalone registered-memory authorization RTL, not integrated RNIC/native DMA',
                        hardware_verified=False,board_integrated=False,complete=len(cls.reports)==12,tests=cls.reports,
                        source_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (RTL,Path(__file__))})
            target=Path(name)
            if not target.is_absolute():target=ROOT/target
            with target.open('x') as out:out.write(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':unittest.main()
