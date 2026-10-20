# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual FPGA page table vs the shared kernel C page-resolution contract.

No native DMA/page pin or responder integration claim. The full-VA/PD/access
guard must authorize a key/offset lease BEFORE this translation component.
"""
import ctypes as C
import errno
import hashlib
import json
import os
from pathlib import Path
import random
import re
import subprocess
import tempfile
import unittest

import test_mr_contract as contract

ROOT=contract.ROOT
RTL=ROOT/'rdma/rnic/rtl/rocev2_mr_page_table.v'

TB=r'''
`timescale 1ns/1ps
module tb;
reg clk=0;always #2 clk=~clk;
reg rst=1,quiet=1,cv=0,car=0,qv=0,mr=0;
reg [2:0] cc=0,cs=0,qs=0;
reg [31:0] ck=0,cl=0,qk=0,ql=0;
reg [11:0] cf=0;reg [7:0] ci=0;reg [63:0] cd=0,qo=0;reg [15:0] qt=0;
wire cr,cav,qr,mv;wire [7:0] ce,me;wire [31:0] cak;
wire [15:0] mt;wire [63:0] md;wire [12:0] ml;
rocev2_mr_page_table dut(
 .clk(clk),.rst(rst),.cfg_quiescent(quiet),.cfg_command(cc),.cfg_slot(cs),.cfg_key(ck),
 .cfg_length(cl),.cfg_first_offset(cf),.cfg_page_index(ci),.cfg_dma_page(cd),
 .cfg_valid(cv),.cfg_ready(cr),.cfg_response_error(ce),.cfg_response_key(cak),.cfg_response_valid(cav),.cfg_response_ready(car),
 .s_query_slot(qs),.s_query_key(qk),.s_query_offset(qo),.s_query_length(ql),.s_query_tag(qt),.s_query_valid(qv),.s_query_ready(qr),
 .m_segment_tag(mt),.m_segment_error(me),.m_segment_dma_address(md),.m_segment_length(ml),.m_segment_valid(mv),.m_segment_ready(mr));
integer cycles=0,management_count=0,query_count=0;
always @(posedge clk) begin cycles=cycles+1;if(cycles>200000) $fatal(1,"deadline");end
task management;
 input [2:0] command,slot;input [31:0] key,length;input [11:0] first;
 input [7:0] index;input [63:0] dma;input [7:0] error;input [31:0] response_key;
 begin
  @(negedge clk);cc=command;cs=slot;ck=key;cl=length;cf=first;ci=index;cd=dma;cv=1;car=0;
  @(posedge clk);while(!cr) @(posedge clk);
  @(negedge clk);cv=0;
  while(!cav) @(negedge clk);
  if(ce!==error || cak!==response_key) $fatal(1,"cfg cmd=%d slot=%d got=%d/%h expected=%d/%h",command,slot,ce,cak,error,response_key);
  repeat(3) begin @(negedge clk);if(!cav || ce!==error || cak!==response_key || cr || qr) $fatal(1,"cfg response ownership");end
  car=1;@(negedge clk);car=0;management_count=management_count+1;
 end
endtask
task query;
 input [2:0] slot;input [31:0] key;input [63:0] offset;input [31:0] length;
 input [15:0] tag;input [7:0] error;input [63:0] dma;input [12:0] piece;
 begin
  @(negedge clk);qs=slot;qk=key;qo=offset;ql=length;qt=tag;qv=1;mr=0;
  @(posedge clk);while(!qr) @(posedge clk);
  @(negedge clk);qv=0;
  while(!mv) @(negedge clk);
  if(mt!==tag || me!==error || md!==dma || ml!==piece) $fatal(1,"query %d got=%d/%h/%d expected=%d/%h/%d",tag,me,md,ml,error,dma,piece);
  repeat(4) begin @(negedge clk);if(!mv || mt!==tag || me!==error || md!==dma || ml!==piece || cr || qr) $fatal(1,"segment stability/ownership");end
  mr=1;@(negedge clk);mr=0;query_count=query_count+1;
 end
endtask
initial begin
 repeat(4) @(negedge clk);rst=0;
 // BODY
 $display("RESULT {\"pass_test\":true,\"cycles\":%0d,\"management_commands\":%0d,\"queries\":%0d}",cycles,management_count,query_count);
 $finish;
end
endmodule
'''


class Model:
    def __init__(self,lib):
        self.lib=lib;self.entries=[None]*8;self.keys=[0]*8;self.body=[];self.queries=0;self.managements=0

    def manage(self,command,slot,key,length=65,first=0,index=0,dma=0):
        entry=self.entries[slot];error=0;result=0
        if command==1:
            if entry is not None:error=6
            elif key%8!=slot or key//8<=self.keys[slot]//8:error=1
            elif not length or length+first>256*4096:error=8
            else:
                layout=contract.Layout();assert self.lib.as02_mr_layout_init(C.byref(layout),0x100000+first,0,length,17,7,slot,1+slot)==0
                self.entries[slot]=dict(layout=layout,pages={},active=False,key=key)
                self.keys[slot]=key;result=key
        elif command==2:
            if key!=self.keys[slot]:error=1
            elif entry is None or entry['active']:error=10
            elif index>=entry['layout'].page_count or dma%4096:error=8
            elif index in entry['pages']:error=9
            else:
                assert self.lib.as02_mr_set_page(C.byref(entry['layout']),index,dma)==0
                entry['pages'][index]=dma;result=key
        elif command==3:
            if key!=self.keys[slot]:error=1
            elif entry is None or entry['active'] or len(entry['pages'])!=entry['layout'].page_count:error=10
            else:
                layout=entry['layout'];assert self.lib.as02_mr_seal(C.byref(layout))==0
                e=contract.Epoch();floor=key//8-1
                assert self.lib.as02_mr_epoch_init(C.byref(e),floor)==0
                assert self.lib.as02_mr_epoch_confirm(C.byref(e),99,floor,C.byref(contract.EpochProof(99,floor,1,1,1)))==0
                assert self.lib.as02_mr_begin_publish(C.byref(layout),C.byref(e))==0
                assert self.lib.as02_mr_confirm_publish(C.byref(layout),C.byref(e),C.byref(contract.Publish(1+slot,slot,key)))==0
                entry['active']=True;result=key
        elif command==4:
            if key!=self.keys[slot]:error=1
            else:self.entries[slot]=None;result=key
        else:error=5
        self.body.append(f"management(3'd{command},3'd{slot},32'h{key:x},32'd{length},12'd{first},8'd{index},64'h{dma:x},8'd{error},32'h{result:x});")
        self.managements+=1
        return error

    def populate(self,slot=0,generation=1,length=8193,first=4095):
        key=generation*8+slot;assert self.manage(1,slot,key,length,first)==0
        for index in range(self.entries[slot]['layout'].page_count):
            dma=0 if index==0 else 0xfffffffffffff000 if index==1 else 0x8123450000000000+index*0x1b000
            assert self.manage(2,slot,key,index=index,dma=dma)==0
        assert self.manage(3,slot,key)==0
        return key

    def query(self,slot,key,offset,length):
        entry=self.entries[slot];dma=piece=0;error=1
        if entry and entry['active'] and key==entry['key'] and key%8==slot:
            out=contract.Segment();code=self.lib.as02_mr_resolve(C.byref(entry['layout']),17,key,offset,length,2,C.byref(out))
            if code==0:error=0;dma=out.dma_address;piece=out.length
            elif code==-errno.EFAULT:error=4
            else:raise AssertionError(f'unexpected C translation result{code}')
        tag=(self.queries*977+65535)&65535
        self.body.append(f"query(3'd{slot},32'h{key:x},64'h{offset:x},32'h{length:x},16'd{tag},8'd{error},64'h{dma:x},13'd{piece});")
        self.queries+=1
        return error,piece


class MRPageTableRTLTests(unittest.TestCase):
    reports={}

    @classmethod
    def setUpClass(cls):
        cls.directory=tempfile.TemporaryDirectory(prefix='as02-page-oracle-');cls.path=Path(cls.directory.name)
        result=subprocess.run(['cc','-std=c11','-O2','-Wall','-Wextra','-Werror','-shared','-fPIC',
            str(contract.KERNEL/'mr_contract.c'),'-o',str(cls.path/'oracle.so')],capture_output=True,text=True,timeout=30)
        if result.returncode:raise RuntimeError(result.stderr)
        cls.lib=C.CDLL(str(cls.path/'oracle.so'))
        p=C.POINTER;u32=C.c_uint32;u64=C.c_uint64
        for name,args in {
            'layout_init':[p(contract.Layout),u64,u64,u64,u32,u32,u32,u64], 'set_page':[p(contract.Layout),u32,u64],
            'seal':[p(contract.Layout)],'epoch_init':[p(contract.Epoch),u32],
            'epoch_confirm':[p(contract.Epoch),u64,u32,p(contract.EpochProof)],
            'begin_publish':[p(contract.Layout),p(contract.Epoch)],'confirm_publish':[p(contract.Layout),p(contract.Epoch),p(contract.Publish)],
            'resolve':[p(contract.Layout),u32,u32,u64,u32,u32,p(contract.Segment)]}.items():
            fn=getattr(cls.lib,'as02_mr_'+name);fn.argtypes=args;fn.restype=C.c_int
        cls.sources=[RTL,Path(__file__),contract.KERNEL/'mr_contract.c',contract.KERNEL/'mr_contract.h']
        cls.before={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in cls.sources}

    def simulate(self,model):
        with tempfile.TemporaryDirectory(prefix='as02-page-table-') as directory:
            path=Path(directory);(path/'tb.v').write_text(TB.replace('// BODY','\n'.join(model.body)))
            compiled=subprocess.run(['iverilog','-g2012','-s','tb','-o',str(path/'test.vvp'),str(path/'tb.v'),str(RTL)],capture_output=True,text=True,timeout=20)
            self.assertEqual(compiled.returncode,0,compiled.stderr)
            ran=subprocess.run(['vvp',str(path/'test.vvp')],capture_output=True,text=True,timeout=15)
            self.assertEqual(ran.returncode,0,ran.stdout+ran.stderr)
            rows=[json.loads(l[7:]) for l in ran.stdout.splitlines() if l.startswith('RESULT ')]
            self.assertEqual(len(rows),1,ran.stdout);self.assertEqual(rows[0]['queries'],model.queries)
            self.assertEqual(rows[0]['management_commands'],model.managements)
            self.reports[self._testMethodName]=rows[0]

    def test_all_slots_scattered_dma64_and_independent_first_offset(self):
        o=Model(self.lib)
        for slot in range(8):
            key=o.populate(slot,first=(slot*631)%4096)
            for offset in (0,1,4095,4096,8192):o.query(slot,key,offset,8193-offset)
            o.query(slot,key^0x80000000,0,1);o.query(slot,key,8192,2)
        self.simulate(o)

    def test_maximum256_pages_and_full_operation_before_first_segment(self):
        o=Model(self.lib);key=o.populate(length=256*4096,first=0)
        for page in range(256):o.query(0,key,page*4096,256*4096-page*4096)
        o.query(0,key,0,256*4096+1);o.query(0,key,256*4096-1,1)
        self.simulate(o)

    def test_partial_population_duplicate_and_active_immutability(self):
        o=Model(self.lib);o.manage(1,0,8,length=65,first=4095)
        o.manage(2,0,8,index=0,dma=0);o.manage(3,0,8);o.query(0,8,0,65)
        o.manage(2,0,8,index=0,dma=0x1000);o.manage(2,0,8,index=1,dma=1)
        o.manage(2,0,8,index=2,dma=0x1000);o.manage(2,0,8,index=1,dma=0x8123456789abc000)
        o.manage(3,0,8);o.manage(2,0,8,index=1,dma=0)
        o.manage(1,0,16);o.query(0,8,0,65);o.query(0,8,1,64)
        self.simulate(o)

    def test_reset_unpopulated_ram_and_stale_generation(self):
        o=Model(self.lib);old=o.populate(length=65,first=4095)
        o.query(0,old,0,65)
        o.body.append('@(negedge clk);rst=1;repeat(4) @(negedge clk);rst=0;')
        o.entries=[None]*8;o.keys=[0]*8
        o.query(0,old,0,65);new=o.populate(generation=9,length=65,first=0)
        o.query(0,old,0,65);o.query(0,new,0,65)
        o.manage(4,0,new);o.manage(1,0,new);o.query(0,new,0,65)
        self.simulate(o)

    def test_range_offset_length_key_and_config_boundaries(self):
        o=Model(self.lib)
        for key,length,first in ((0,65,0),(9,65,0),(8,0,0),(8,0xffffffff,0),(8,256*4096,1)):
            o.manage(1,0,key,length,first)
        key=o.populate(length=65,first=4095)
        for offset,length in ((0,0),(0,66),(64,2),(65,1),(1<<63,1),((1<<64)-1,1)):
            o.query(0,key,offset,length)
        o.query(1,key,0,1);o.manage(4,0,key+8);o.query(0,key,0,65)
        self.simulate(o)

    def test_external_dma_lease_blocks_reconfiguration(self):
        o=Model(self.lib);key=o.populate(length=65,first=4095)
        o.body.append('quiet=0;cv=1;cc=4;cs=0;ck=8;repeat(7) begin @(negedge clk);if(cr || cav) $fatal(1,"external lease not retained");end cv=0;')
        o.query(0,key,0,65)
        o.body.append('quiet=1;')
        o.manage(4,0,key);o.query(0,key,0,65)
        self.simulate(o)

    def test_captured_cfg_payload_and_lost_quiescence(self):
        o=Model(self.lib);o.manage(1,0,8,length=1,first=0)
        o.body.append(r'''
@(negedge clk);cv=1;cc=2;cs=0;ck=8;ci=0;cd=64'h8123456789abc000;
@(posedge clk);while(!cr) @(posedge clk);
@(negedge clk);cv=0;ci=255;cd=0;
while(!cav) @(negedge clk);if(ce!=0 || cak!=8) $fatal(1,"cfg inputs not captured");
car=1;@(negedge clk);car=0;management_count=management_count+1;
''')
        entry=o.entries[0];self.assertEqual(self.lib.as02_mr_set_page(C.byref(entry['layout']),0,0x8123456789abc000),0)
        entry['pages'][0]=0x8123456789abc000;o.managements+=1
        o.manage(3,0,8)
        o.body.append(r'''
@(negedge clk);cv=1;cc=4;cs=0;ck=8;
@(posedge clk);while(!cr) @(posedge clk);
@(negedge clk);cv=0;quiet=0;
while(!cav) @(negedge clk);if(ce!=6 || cak!=0) $fatal(1,"lost quiescence did not abort");
quiet=1;car=1;@(negedge clk);car=0;management_count=management_count+1;
''')
        o.managements+=1;o.query(0,8,0,1);self.simulate(o)

    def test_deterministic_query_oracle_with_mutation_and_stale_keys(self):
        o=Model(self.lib);rng=random.Random(0x455a5047)
        for slot in range(8):o.populate(slot,length=65+slot*917,first=rng.randrange(4096))
        for _ in range(300):
            slot=rng.randrange(8);entry=o.entries[slot];length=entry['layout'].length
            o.query(slot,entry['key'] if rng.randrange(4) else entry['key']^0x80000000,
                    rng.choice((0,1,length-1,length,1<<48,rng.randrange(length))),rng.choice((0,1,65,4096,0xffffffff)))
        self.simulate(o)

    @classmethod
    def tearDownClass(cls):
        after={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in cls.sources}
        cls.directory.cleanup()
        if after!=cls.before:raise RuntimeError('page table/oracle inputs changed')
        if name:=os.environ.get('AS02_RNIC_PAGE_TABLE_REPORT'):
            target=Path(name)
            if not target.is_absolute():target=ROOT/target
            report=dict(scope='Actual FPGA page table vs shared kernel C contract, not responder/SG-DMA/native integration',
                hardware_verified=False,kernel_runtime_pin_verified=False,integrated_with_dma_backend=False,completion_claim=False,
                pass_test=len(cls.reports)==8,tests=cls.reports,source_sha256=after)
            with target.open('x') as out:out.write(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':unittest.main()
