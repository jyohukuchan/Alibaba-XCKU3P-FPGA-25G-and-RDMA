# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual Ethernet CSR/Corundum AXI; whole-path config_safe is a MODEL."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

import test_control_regs_rtl as control

ROOT=control.ROOT
RTL=ROOT/'rdma/rnic/rtl/rocev2_ethernet_config_regs.v'
HEADER=ROOT/'rdma/rnic/kernel/native_regs.h'
SOURCES=[RTL,*control.SOURCES[1:]]
TASKS=control.TB.split('task write_reg;',1)[1].split('task stage;',1)[0]
TASKS='task write_reg;'+TASKS
TB=r'''
`timescale 1ns/1ps
module tb;
localparam ADDR_WIDTH=12;
// PORTS
// ABI
rocev2_ethernet_config_regs #(.EPOCH_MAX(3)) dut(.*);
always #2 clk=~clk;
integer scenario=0,dummy,cycles=0,writes=0,reads=0;
reg [31:0] value;
reg [160:0] saved_active;
always @(posedge clk) if(!rst) begin
 cycles=cycles+1;if(cycles>10000)$fatal(1,"deadline");
end
// TASKS
task stage;
 begin
  write_reg(AS02_ETH_STAGE,32'hfbb97531,15,0,3);
  write_reg(AS02_ETH_STAGE+4,32'h8af3,15,3,0);
  write_reg(AS02_ETH_STAGE+8,32'h0367c5d0,15,0,0);
  write_reg(AS02_ETH_STAGE+12,32'hb883,15,0,0);
  write_reg(AS02_ETH_STAGE+16,32'hc6120b02,15,0,0);
  write_reg(AS02_ETH_STAGE+20,1,15,0,0);
 end
endtask
task commit;
 begin write_reg(AS02_ETH_COMMIT,1,15,0,0);end
endtask
task clear;
 begin
  write_reg(AS02_ETH_CLEAR_ERROR,1,15,0,0);
  if(mmio_error || last_error)$fatal(1,"safe clear failed");
 end
endtask
task check_active;
 begin
  if(!cfg_enable || !committed || cfg_epoch!=1 || cfg_local_mac!==48'h8af3fbb97531 ||
    cfg_peer_mac!==48'hb8830367c5d0 || cfg_local_ip!==32'hc6120b02)
   $fatal(1,"partial/wrong active commit");
 end
endtask
initial begin
 #1 rst=1;dummy=$value$plusargs("case=%d",scenario);config_safe=1;
 repeat(5)@(negedge clk);rst=0;
 case(scenario)
 0: begin
  read_reg(AS02_ETH_ID,value);if(value!==AS02_ETH_ID_VALUE)$fatal(1,"ID ABI");
  read_reg(AS02_ETH_ABI,value);if(value!==AS02_ETH_ABI_VALUE)$fatal(1,"version ABI");
  stage;if(cfg_epoch || cfg_enable || committed)$fatal(1,"staging published");
  commit;check_active;
  read_reg(AS02_ETH_ACTIVE,value);if(value!==32'hfbb97531)$fatal(1,"active low");
  read_reg(AS02_ETH_ACTIVE+4,value);if(value!==32'h8af3)$fatal(1,"active high");
  read_reg(AS02_ETH_ACTIVE+8,value);if(value!==32'h0367c5d0)$fatal(1,"peer low");
  read_reg(AS02_ETH_ACTIVE+12,value);if(value!==32'hb883)$fatal(1,"peer high");
  read_reg(AS02_ETH_ACTIVE+16,value);if(value!==32'hc6120b02)$fatal(1,"IP order");
  read_reg(AS02_ETH_STATUS,value);if(value!=11)$fatal(1,"status ABI %h",value);
  write_reg(AS02_ETH_STAGE,32'h55112266,4'b0101,0,0);
  read_reg(AS02_ETH_STAGE,value);if(value!==32'hfb117566)$fatal(1,"byte strobes %h",value);
  check_active;
 end
 1: begin
  stage;config_safe=0;commit;
  if(!mmio_error || last_error!=3 || cfg_epoch || cfg_enable)$fatal(1,"unsafe commit");
  write_reg(AS02_ETH_CLEAR_ERROR,1,15,0,0);if(!mmio_error)$fatal(1,"unsafe clear");
  config_safe=1;commit;if(cfg_epoch || !mmio_error)$fatal(1,"sticky error bypass");
  clear;commit;check_active;
  saved_active={cfg_enable,cfg_epoch,cfg_local_mac,cfg_peer_mac,cfg_local_ip};
  config_safe=0;write_reg(AS02_ETH_STAGE+20,0,15,0,0);commit;
  if(!mmio_error || {cfg_enable,cfg_epoch,cfg_local_mac,cfg_peer_mac,cfg_local_ip}!==saved_active)$fatal(1,"live config changed");
 end
 2: begin
  stage;write_reg(AS02_ETH_STAGE+4,32'h10008af3,15,0,0);commit;
  if(!mmio_error || last_error!=4 || cfg_epoch)$fatal(1,"high MAC bits truncated");
  clear;write_reg(AS02_ETH_STAGE+4,32'h8bf3,15,0,0);commit;
  if(!mmio_error || cfg_epoch)$fatal(1,"multicast local MAC");
  clear;stage;write_reg(AS02_ETH_STAGE+12,32'hb983,15,0,0);commit;
  if(!mmio_error || cfg_epoch)$fatal(1,"multicast peer MAC");
  clear;stage;write_reg(AS02_ETH_STAGE+16,32'he0000001,15,0,0);commit;
  if(!mmio_error || cfg_epoch)$fatal(1,"multicast IP");
  clear;stage;write_reg(AS02_ETH_STAGE+20,32'h80000001,15,0,0);commit;
  if(!mmio_error || cfg_epoch)$fatal(1,"reserved enable bits");
 end
 3: begin
  stage;write_reg(AS02_ETH_COMMIT,1,4'b0011,0,0);
  if(!mmio_error || cfg_epoch)$fatal(1,"partial commit");
  clear;write_reg(AS02_ETH_COMMIT,0,15,0,0);
  if(!mmio_error || cfg_epoch)$fatal(1,"invalid command");
  clear;write_reg(12'h110,1,15,0,0);if(!mmio_error || cfg_epoch)$fatal(1,"high write alias");
  clear;read_reg(12'h025,value);if(!mmio_error || value!=0)$fatal(1,"unaligned read alias");
  clear;read_reg(12'h140,value);if(!mmio_error || value!=0)$fatal(1,"high read alias");
  clear;write_reg(AS02_ETH_ID,1,15,0,0);if(!mmio_error || cfg_epoch)$fatal(1,"read-only write");
 end
 4: begin
  stage;commit;check_active;commit;commit;
  if(cfg_epoch!=3 || mmio_error)$fatal(1,"epoch progression");
  write_reg(AS02_ETH_STAGE+20,0,15,0,0);commit;
  if(cfg_epoch!=3 || !cfg_enable || !mmio_error || last_error!=5)$fatal(1,"epoch wrapped/changed config");
  clear;commit;if(cfg_epoch!=3 || !cfg_enable || !mmio_error)$fatal(1,"clear reset epoch");
 end
 5: begin
  // Disabled configuration is allowed at a safe boundary without inventing
  // valid peers. It still increments epoch and never resets any other block.
  commit;if(cfg_epoch!=1 || cfg_enable || !committed || mmio_error)$fatal(1,"disabled atomic commit");
  stage;commit;if(cfg_epoch!=2 || !cfg_enable || mmio_error)$fatal(1,"safe enable");
  config_safe=0;write_reg(AS02_ETH_STAGE+20,0,15,0,0);
  if(cfg_epoch!=2 || !cfg_enable || mmio_error)$fatal(1,"staging during live work affected active config");
  config_safe=1;commit;if(cfg_epoch!=3 || cfg_enable || mmio_error)$fatal(1,"safe disable");
 end
 default:$fatal(1,"unknown scenario");
 endcase
 $display("RESULT {\"pass_test\":true,\"scenario\":%0d,\"cycles\":%0d,\"axi_writes\":%0d,\"axi_reads\":%0d}",scenario,cycles,writes,reads);
 $finish;
end
endmodule
'''


class EthernetConfigRTLTests(unittest.TestCase):
    reports={}

    @classmethod
    def setUpClass(cls):
        cls.paths=[*SOURCES,HEADER,Path(__file__),Path(control.__file__)]
        cls.before={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in cls.paths}
        declarations=[]
        ports=RTL.read_text().split(')(\n',1)[1].split('\n);',1)[0]
        for line in ports.splitlines():
            m=re.match(r'\s*(input|output) (?:wire|reg) (.*?)(?:=0)?[,]?$',line)
            if m:
                d=m[2].rstrip(',');declarations.append(('reg ' if m[1]=='input' else 'wire ')+d+('=0;' if m[1]=='input' else ';'))
        abi=[f"localparam {n}=32'h{int(v,0):x};" for n,v in re.findall(r'^#define (AS02_ETH_\w+) (0x[0-9a-fA-F]+|\d+)U$',HEADER.read_text(),re.M)]
        cls.directory=tempfile.TemporaryDirectory(prefix='as02-ethernet-csr-');cls.path=Path(cls.directory.name)
        source=cls.path/'tb.v';source.write_text(TB.replace('// PORTS','\n'.join(declarations)).replace('// ABI','\n'.join(abi)).replace('// TASKS',TASKS))
        r=subprocess.run(['iverilog','-g2012','-s','tb','-o',str(cls.path/'test.vvp'),str(source),*map(str,SOURCES)],capture_output=True,text=True,timeout=20)
        if r.returncode:raise RuntimeError(r.stdout+r.stderr)

    def case(self,n):
        r=subprocess.run(['vvp',str(self.path/'test.vvp'),f'+case={n}'],capture_output=True,text=True,timeout=10)
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        rows=[json.loads(l[7:]) for l in r.stdout.splitlines() if l.startswith('RESULT ')]
        self.assertEqual(len(rows),1,r.stdout);self.reports[self._testMethodName]=rows[0]

    def test_actual_axi_and_kernel_abi_atomic_snapshot_byte_strobes(self):self.case(0)
    def test_unsafe_and_sticky_error_cannot_mutate_active_config(self):self.case(1)
    def test_full_width_mac_ip_enable_validation_before_narrowing(self):self.case(2)
    def test_partial_unknown_unaligned_and_readonly_accesses_do_not_alias(self):self.case(3)
    def test_epoch_exhaustion_and_clear_never_reuse_or_reset(self):self.case(4)
    def test_staging_during_live_work_and_atomic_enable_disable(self):self.case(5)

    @classmethod
    def tearDownClass(cls):
        after={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in cls.paths};cls.directory.cleanup()
        if after!=cls.before:raise RuntimeError('Ethernet CSR sources changed')
        if name:=os.environ.get('AS02_RNIC_ETH_CONFIG_REPORT'):
            p=Path(name)
            if not p.is_absolute():p=ROOT/p
            report=dict(scope='Actual Ethernet CSR/Corundum AXI and kernel ABI; whole-path safe input MODEL, reduced epoch limit3 for finite exhaustion proof',
                pass_test=len(cls.reports)==6,hardware_verified=False,board_integrated=False,completion_claim=False,
                tests=cls.reports,source_sha256=after)
            with p.open('x') as out:out.write(json.dumps(report,indent=2)+'\n')
