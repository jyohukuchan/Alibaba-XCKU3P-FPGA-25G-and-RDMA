# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual native decoder/Ethernet CSR; datapath and old/new CSR slaves MODELS."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

import probe_native_control as native
import test_control_regs_rtl as control

ROOT=control.ROOT
SOURCES=[native.RTL,native.CONFIG,*native.XBAR,*control.SOURCES[1:],
         ROOT/'external/corundum/fpga/lib/axis/rtl/arbiter.v',
         ROOT/'external/corundum/fpga/lib/axis/rtl/priority_encoder.v']


def datapath_model():
    header=native.dual.TOP.read_text().split('\n);',1)[0]+'\n);\n'
    body=[]
    for direction,expr,name in native.pcie.ports(native.dual.TOP):
        if direction=='output' and not name.startswith(('s_axil_rw_','s_axil_responder_')):
            body.append('assign '+name+'='+('1' if name=='config_safe' else '0')+';')
    for prefix,ident,version,width in [('s_axil_rw_',0x524f4332,0x20000,24),('s_axil_responder_',0x524e4331,0x10000,12)]:
        tag='rw' if width==24 else 'control'
        body += [f'wire [{width-1}:0] {tag}_ra;',f'wire {tag}_re;']
        fields='awaddr awprot awvalid awready wdata wstrb wvalid wready bresp bvalid bready araddr arprot arvalid arready rdata rresp rvalid rready'.split()
        connections=[f'.s_axil_{f}({prefix+f})' for f in fields]
        connections += [f'.reg_rd_addr({tag}_ra)',f'.reg_rd_en({tag}_re)',
            f".reg_rd_data({tag}_ra==0 ? 32'h{ident:x} : ({tag}_ra==4 ? 32'h{version:x} : 32'd0))",
            '.reg_rd_wait(1\'b0)',f'.reg_rd_ack({tag}_re)',
            '.reg_wr_addr()','.reg_wr_data()','.reg_wr_strb()','.reg_wr_en()',
            '.reg_wr_wait(1\'b0)','.reg_wr_ack(1\'b1)']
        body.append(f'axil_reg_if #(.DATA_WIDTH(32),.ADDR_WIDTH({width}),.STRB_WIDTH(4)) {tag}_model(.clk(clk),.rst(rst),'+','.join(connections)+');')
    return header+'\n'.join(body)+'\nendmodule\n`resetall\n'


TB=r'''
`timescale 1ns/1ps
module tb;
localparam TX_TAG_WIDTH=16,TS_WIDTH=96,RX_USER_WIDTH=97,RAM_SIZE=8192,RAM_ADDR_WIDTH=15,
 SEG_COUNT=2,SEG_DATA_WIDTH=256,SEG_BE_WIDTH=32,SEG_ADDR_WIDTH=9,RAM_SEL_WIDTH=1,DMA_LEN_WIDTH=16,DMA_TAG_WIDTH=16;
// PORTS
rocev2_native_endpoint dut(.*);
always #2 clk=~clk;
integer scenario=0,dummy,cycles=0,writes=0,reads=0;reg [31:0] value;
always @(posedge clk) if(!rst) begin
 cycles=cycles+1;
 if(cycles>2000)$fatal(1,"decode deadline arready%b rvalid%b bus_ar%b/%b bus_r%b",s_axil_arready,s_axil_rvalid,dut.bus_arvalid,dut.bus_arready,dut.bus_rvalid);
end
// TASKS
initial begin
 #1 rst=1;dummy=$value$plusargs("case=%d",scenario);
 repeat(8)@(negedge clk);rst=0;
 case(scenario)
 0:begin
  read_reg(0,value);if(value!==32'h524f4332)$fatal(1,"RW model ID %h",value);
  read_reg(4,value);if(value!==32'h20000)$fatal(1,"RW model ABI");
  read_reg(24'h400000,value);if(value!==32'h524e4331)$fatal(1,"control model ID");
  read_reg(24'h401000,value);if(value!==32'h524e4531)$fatal(1,"actual Ethernet CSR ID");
 end
 1:begin
  expect_decerr(24'h300010);expect_decerr(24'h402000);expect_decerr(24'h100000);
  read_reg(0,value);if(value!==32'h524f4332)$fatal(1,"error aliased RW");
  read_reg(24'h40100c,value);if(value!=0 || ethernet_config_error)$fatal(1,"error aliased actual CSR");
 end
 2:begin
  write_reg(24'h401020,32'hfbb97531,15,0,3);write_reg(24'h401024,32'h8af3,15,3,0);
  write_reg(24'h401028,32'h0367c5d0,15,0,0);write_reg(24'h40102c,32'hb883,15,0,0);
  write_reg(24'h401030,32'hc6120b02,15,0,0);write_reg(24'h401034,1,15,0,0);write_reg(24'h401010,1,15,0,0);
  read_reg(24'h40100c,value);if(value!=1 || ethernet_config_error || !ethernet_enabled)$fatal(1,"actual config through decoder");
  read_reg(24'h401040,value);if(value!==32'hfbb97531)$fatal(1,"actual active readback");
  read_reg(0,value);if(value!==32'h524f4332)$fatal(1,"CSR write hit RW");
 end
 default:$fatal(1,"scenario");
 endcase
 $display("RESULT {\"pass_test\":true,\"scenario\":%0d,\"cycles\":%0d}",scenario,cycles);$finish;
end
endmodule
'''


class NativeDecodeRTLTests(unittest.TestCase):
    reports={}

    @classmethod
    def setUpClass(cls):
        cls.paths=[*SOURCES,native.dual.TOP,native.HEADER,Path(__file__),Path(native.__file__),Path(control.__file__)]
        cls.before={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in cls.paths}
        decl=[];initialize=[]
        for direction,expr,name in native.pcie.ports(native.RTL):
            decl.append(('reg ' if direction=='input' else 'wire ')+(f'[{expr}] ' if expr else '')+name+('=0;' if name=='clk' else ';'))
            if direction=='input' and name not in ('clk','rst'):initialize.append(name+'=0;')
        tasks=control.TB.split('task write_reg;',1)[1].split('task stage;',1)[0]
        tasks=('task write_reg;'+tasks).replace('input [11:0] address;','input [23:0] address;')
        tasks+='\ntask expect_decerr;'+native.DECERR.split('task expect_decerr;',1)[1]
        for signal in ['awready','wready','bvalid','arready','rvalid']:
            tasks=tasks.replace(f'while(!s_axil_{signal})',f"while(s_axil_{signal}!==1'b1)")
        cls.directory=tempfile.TemporaryDirectory(prefix='as02-native-decode-');cls.path=Path(cls.directory.name)
        bench=TB.replace('// PORTS','\n'.join(decl)).replace('// TASKS',tasks)
        # Match the pinned Corundum benches: clock an initial unreset phase,
        # assert a real synchronous reset, then release. This wakes initial
        # combinational-next logic before its zero-initialized flops reset.
        # No hierarchical forcing or altered IP/safety checks are involved.
        bench=bench.replace('#1 rst=1;','#1 rst=0;'+''.join(initialize)+'repeat(2)@(negedge clk);rst=1;')
        src=cls.path/'tb.v';src.write_text(datapath_model()+bench)
        r=subprocess.run(['iverilog','-g2012','-s','tb','-o',str(cls.path/'test.vvp'),str(src),*map(str,SOURCES)],capture_output=True,text=True,timeout=20)
        if r.returncode:raise RuntimeError(r.stdout+r.stderr)

    def case(self,n):
        r=subprocess.run(['vvp',str(self.path/'test.vvp'),f'+case={n}'],capture_output=True,text=True,timeout=10)
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        rows=[json.loads(l[7:]) for l in r.stdout.splitlines() if l.startswith('RESULT ')]
        self.assertEqual(len(rows),1,r.stdout);self.reports[self._testMethodName]=rows[0]

    def test_actual_decode_preserves_three_region_identities(self):self.case(0)
    def test_real_unmapped_DECERR_no_truncation_alias(self):self.case(1)
    def test_actual_ethernet_CSR_writes_through_decoder(self):self.case(2)

    @classmethod
    def tearDownClass(cls):
        after={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in cls.paths};cls.directory.cleanup()
        if after!=cls.before:raise RuntimeError('native decode sources changed')
        if name:=os.environ.get('AS02_RNIC_NATIVE_DECODE_REPORT'):
            p=Path(name)
            if not p.is_absolute():p=ROOT/p
            report=dict(scope='Actual native AXI crossbar/Ethernet CSR, old/new control and datapath MODELS',
                pass_test=len(cls.reports)==3,hardware_verified=False,board_integrated=False,completion_claim=False,
                tests=cls.reports,source_sha256=after)
            with p.open('x') as out:out.write(json.dumps(report,indent=2)+'\n')
