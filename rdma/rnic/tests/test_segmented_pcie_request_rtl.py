#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Exact private root-model 3DW/4DW guards and full64 descriptor byte joins.

Four-state component only; actual generated native DMA is a separate gate.
Each bad request must genuinely fatal, never suppress an assertion.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
import segmented_pcie_request_fixture as fixture

ROOT=fixture.ROOT


def header(address, count, fmt):
    first=(15<<(address&3))&15
    last=15>>(3-((address+count-1)&3))
    words=((address&3)+count+3)//4
    if words==1:first&=last;last=0
    return fmt<<125 | (words&1023)<<96 | 0x8200<<80 | 5<<72 | last<<68 | first<<64 | \
        ((address&~3)<<32 if fmt==0 else address&~3)


class PCIeRequest(unittest.TestCase):
    reports={}

    def simulate(self, name, address, length, headers, runtime=True, expected=None, finish=True):
        text=fixture.apply(fixture.old.bench())
        start=text.index('function [63:0] segmented_read_address;')
        end=text.index('// Root-complex MODEL: transmit sequence',start)
        declarations=text[start:end]
        start=text.index('  if(runtime_segmented)begin\n   if(!read_outstanding')
        end=text.index('\n  repeat(17)',start)
        guard=text[start:end]
        steps='\n'.join("consume(128'h%032x);"%h for h in headers)
        t=TESTBENCH.replace('CHECKER',declarations).replace('RANGE_GUARD',guard).replace('STEPS',steps)
        for token,value in [('RUNTIME',int(runtime)),('ADDRESS',f"64'h{address:016x}"),('LENGTH',length),('FINISH',int(finish))]:
            t=t.replace(token,str(value))
        run=Path(tempfile.mkdtemp(prefix='segmented-pcie-request-',dir=ROOT/'rdma/rnic/build'))
        (run/'tb.v').write_text(t)
        c=subprocess.run(['iverilog','-g2012','-s','tb','-o',str(run/'test'),str(run/'tb.v')],capture_output=True,text=True,timeout=30)
        (run/'compile.log').write_text(c.stdout+c.stderr)
        self.assertEqual(c.returncode,0,c.stdout+c.stderr)
        start=time.monotonic();c=subprocess.run(['vvp',str(run/'test')],capture_output=True,text=True,timeout=10)
        seconds=time.monotonic()-start;output=c.stdout+c.stderr
        (run/'simulation.log').write_text(output)
        if expected:
            self.assertNotEqual(c.returncode,0,output);self.assertIn(expected,output);self.assertNotIn('RESULT PASS',output)
        else:self.assertEqual(c.returncode,0,output);self.assertIn('RESULT PASS',output)
        self.reports[name]=dict(pass_test=True,expected_fatal=expected,process_exit=c.returncode,seconds=seconds,
            directory=str(run.relative_to(ROOT)),artifact_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in run.iterdir()if p.is_file()})

    def test_low_3DW_and_high_4DW_decode_exact_range_and_top64_last_byte(self):
        for name,address,length in [('low',0x12345000,256),('high',0x8123456789abc000,256),('top',0xfffffffffffffffd,3)]:
            fmt=0 if name=='low'else 1
            hs=[header(address,128,fmt),header(address+128,128,fmt)]if length==256 else[header(address,length,fmt)]
            self.simulate(name,address,length,hs)

    def test_3DW_wrong_requester_type_attributes_unused_PH_or_page_still_fatal(self):
        h=header(0x12345000,128,0)
        for name,bad in [('requester',h^(1<<80)),('type',h^(1<<120)),('attributes',h^(1<<109)),
                         ('unused_DW3',h|1),('PH',h|(1<<32)),('page',header(0x12346000,128,0))]:
            self.simulate(name,0x12345000,128,[bad],expected='not exact sealed low-page 3DW')

    def test_old_profile_still_refuses_3DW(self):
        self.simulate('old_profile',0x12345000,128,[header(0x12345000,128,0)],False,'not ordinary DMA64')

    def test_full64_descriptor_prevents_truncation_reorder_excess_and_missing_bytes(self):
        h=header(0x12345000,128,0)
        for name,address,length,hs,error in [
            ('high_truncation',0x112345000,128,[h],'full64 descriptor/TLP byte range'),
            ('reorder',0x12345000,128,[header(0x12345004,124,0)],'full64 descriptor/TLP byte range'),
            ('excess',0x12345000,3,[h],'full64 descriptor/TLP byte range'),
            ('missing',0x12345000,256,[h],'physical descriptor completed before exact TLP bytes')]:
            self.simulate(name,address,length,hs,expected=error)


TESTBENCH=r'''
`timescale 1ns/1ps
module tb;
reg clk=0;always #2 clk=~clk;
reg rst=1,runtime_segmented=RUNTIME,read_outstanding=1;
reg m_dma_read_valid=0,m_dma_read_ready=1,s_dma_read_status_valid=0;
reg [63:0] m_dma_read_address=ADDRESS;
reg [31:0] m_dma_read_length=LENGTH;
function [63:0] pcie_dma_page;
 input integer index;
 begin case(index)0:pcie_dma_page=64'h8123456789abc000;1:pcie_dma_page=64'hfffffffffffff000;
 2:pcie_dma_page=64'h12345000;default:pcie_dma_page=0;endcase end
endfunction
CHECKER
task consume;
 input [127:0] h;
 reg [63:0] base,first_address;
 integer total_dwords,first_lane,bytes_count,dw,b;
 begin
  check_request(h,0);
  total_dwords=h[105:96];if(!total_dwords)total_dwords=1024;
  first_lane=0;while(first_lane<4 && !h[64+first_lane])first_lane=first_lane+1;
  if(first_lane==4)$fatal(1,"zero-byte request");
  bytes_count=0;
  for(dw=0;dw<total_dwords;dw=dw+1)for(b=0;b<4;b=b+1)
   if(dw==0 ? h[64+b]:(dw==total_dwords-1 ? h[68+b]:1'b1))bytes_count=bytes_count+1;
  base=segmented_read_address(h);first_address=base+first_lane;
RANGE_GUARD
 end
endtask
initial begin
 repeat(4)@(negedge clk);rst=0;m_dma_read_valid=1;
 @(negedge clk);m_dma_read_valid=0;
 STEPS
 if(FINISH)begin s_dma_read_status_valid=1;@(negedge clk);s_dma_read_status_valid=0;end
 $display("RESULT PASS");$finish;
end
initial begin #5000;$fatal(1,"component deadline");end
endmodule
'''


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve earlier evidence')
    files=[Path(__file__).resolve(),Path(fixture.__file__).resolve(),Path(fixture.old.__file__).resolve(),*fixture.INPUTS]
    before={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in files}
    start=time.monotonic();r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(PCIeRequest))
    if any(hashlib.sha256((ROOT/n).read_bytes()).hexdigest()!=h for n,h in before.items()):raise ValueError('source changed')
    report=dict(scope=__doc__,pass_test=r.wasSuccessful(),methods=r.testsRun,cases=len(PCIeRequest.reports),
                seconds=time.monotonic()-start,source_sha256=before,tests=PCIeRequest.reports,
                four_state=True,native_RTL_runtime=False,hardware_verified=False)
    a.report.write_text(json.dumps(report,indent=2)+'\n');raise SystemExit(not r.wasSuccessful())


if __name__=='__main__':main()
