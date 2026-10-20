# SPDX-License-Identifier: BSD-2-Clause-Views
"""Four-state shared-role ownership; HLS is an EXPLICIT controllable model.

core.STUB_* assignments change ONLY test-model outputs, never production
state. Actual-HLS one-core evidence is a separate bounded probe.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
import probe_shared_hls_roles as probe
from test_wqe_hls_sq_rtl import context,expected_sq

ROOT=probe.ROOT
RTL=ROOT/'rdma/rnic/rtl/rocev2_shared_hls_transport.v'


def stub():
    h=(ROOT/'rdma/rtl/rocev2_integrity_transport.v').read_text().split('module rocev2_integrity_transport (\n',1)[1].split('\n);',1)[0]
    h=h.replace('output reg','output wire').replace('=0','');decl=[];assign=[]
    for d,w,n in re.findall(r'^\s*(input|output) wire\s+(\[[^]]+\]\s+)?(\w+)\s*,?$',h,re.M):
        if d=='output':
            decl.append('reg '+(w or'')+'STUB_'+n+'=0;');assign.append('assign '+n+'=STUB_'+n+';')
    return 'module rocev2_integrity_transport #(parameter LEGACY_QP_KEY=1)(\n'+h+',\ninput wire [31:0] s_axis_sq_rkey);\n'+'\n'.join(decl+assign)+'\nendmodule\n'


TB=chr(96)+r'''timescale 1ns/1ps
module tb;
// DECLARATIONS
rocev2_shared_hls_transport dut(.*);
always #2 clk=~clk;
reg [587:0] expected_owner;
task owner;
 input [587:0] value;
 begin
  @(negedge clk);s_local_owner_context=value;expected_owner=value;s_local_owner_valid=1;
  #1;if(!s_local_owner_ready || local_hls_queue_guard!==8'h80)$fatal(1,"local offer guard/ready");
  @(posedge clk);@(negedge clk);s_local_owner_valid=0;
  if(!local_hls_active || local_hls_queue_guard!==8'h80 || dut.owner!==value)$fatal(1,"full shared owner capture");
 end
endtask
task SQ;
 input [247:0] value;
 begin
  @(negedge clk);s_local_sq_tdata=value;s_local_sq_tvalid=1;dut.core.STUB_s_axis_sq_tready=0;
  repeat(11)begin @(negedge clk);if(s_local_sq_tready || !dut.core.s_axis_sq_tvalid ||
   dut.core.s_axis_sq_tdata!==value[239:0] || dut.core.s_axis_sq_rkey!==value[239:208])$fatal(1,"full SQ/key-valid under stall");end
  dut.core.STUB_s_axis_sq_tready=1;@(posedge clk);if(!s_local_sq_tready)$fatal(1,"modeled HLS SQ acceptance");
  @(negedge clk);s_local_sq_tvalid=0;#1;
 end
endtask
task quarantined;
 begin repeat(17)begin @(negedge clk);if(!shared_hls_fault || local_hls_queue_guard!==8'hff || s_local_owner_ready || s_local_retire_ready)$fatal(1,"fault escaped quarantine");end end
endtask
initial begin
 rst=1;repeat(4)@(negedge clk);rst=0;trusted_local_ready=1;trusted_local_qpn=7;
 // BODY
 $display("SHARED_ROLE_UNIT {\"pass_test\":true,\"local_active\":%0d,\"fault\":%0d}",local_hls_active,shared_hls_fault);
 $finish;
end
endmodule
'''


class SharedRoleTests(unittest.TestCase):
    reports={}

    def simulate(self,body):
        decl='\n'.join(('reg 'if d=='input'else'wire ')+(w or'')+n+('=0;'if d=='input'else';')for d,w,n in probe.ports(RTL.read_text()))
        tb=TB.replace('// DECLARATIONS',decl).replace('// BODY',body)
        # Same old modeled core, now the statically selected legacy branch.
        tb=tb.replace('dut.core.','dut.legacy_core.core.')
        paths=[RTL,Path(__file__).resolve(),Path(probe.__file__).resolve(),Path(probe.derive.__file__).resolve(),
            ROOT/'rdma/rnic/tests/test_wqe_hls_sq_rtl.py',ROOT/'rdma/rtl/rocev2_integrity_transport.v']
        before={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in paths}
        with tempfile.TemporaryDirectory(prefix='as02-shared-role-')as directory:
            p=Path(directory);(p/'tb.v').write_text(tb);(p/'stub.v').write_text(stub())
            c=subprocess.run(['iverilog','-g2012','-s','tb','-o',str(p/'test.vvp'),str(p/'tb.v'),str(p/'stub.v'),str(RTL)],capture_output=True,text=True,timeout=20)
            self.assertEqual(c.returncode,0,c.stdout+c.stderr)
            r=subprocess.run(['vvp',str(p/'test.vvp')],capture_output=True,text=True,timeout=10)
            self.assertEqual(r.returncode,0,r.stdout+r.stderr)
            rows=[json.loads(l[len('SHARED_ROLE_UNIT '):])for l in r.stdout.splitlines()if l.startswith('SHARED_ROLE_UNIT ')]
            self.assertEqual(len(rows),1);self.assertTrue(rows[0]['pass_test'])
        self.assertEqual(before,{n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest()for n in before})
        self.reports.setdefault(self._testMethodName,[]).append(dict(summary=rows[0],source_sha256=before,bench_sha256=hashlib.sha256(tb.encode()).hexdigest()))

    def test_remote_then_local_route_the_SAME_core_ports(self):
        body=r'''
remote_operation_idle=0;s_axis_rx_tdata=128'h1234;s_axis_rx_tkeep=16'hffff;s_axis_rx_tlast=1;s_axis_rx_tvalid=1;
@(posedge clk);@(negedge clk);#1;
if(local_hls_active || dut.role!=1 || !dut.core.s_axis_rx_tvalid || dut.core.s_axis_rx_tdata!==128'h1234 || s_local_rx_tready)$fatal(1,"remote RX route");
dut.core.STUB_s_axis_rx_tready=1;@(posedge clk);@(negedge clk);s_axis_rx_tvalid=0;
dut.core.STUB_m_axis_tx_tdata=128'h54321;dut.core.STUB_m_axis_tx_tvalid=1;
repeat(11)begin @(negedge clk);if(!m_axis_tx_tvalid || m_axis_tx_tdata!==128'h54321 || m_local_tx_tvalid || dut.core.m_axis_tx_tready)$fatal(1,"remote TX cross-role");end
m_axis_tx_tready=1;@(posedge clk);@(negedge clk);dut.core.STUB_m_axis_tx_tvalid=0;remote_operation_idle=1;repeat(3)@(negedge clk);
'''
        body+=f'owner({context()});SQ({expected_sq()});'
        body+=r'''
s_local_rx_tdata=128'habcdef;s_local_rx_tkeep=16'h1234;s_local_rx_tvalid=1;s_local_rx_tlast=1;#1;
if(!dut.core.s_axis_rx_tvalid || dut.core.s_axis_rx_tdata!==128'habcdef || !s_local_rx_tready || s_axis_rx_tready)$fatal(1,"local RX");
@(posedge clk);@(negedge clk);s_local_rx_tvalid=0;
'''
        for data,valid,ready,ld,lv,lr,width in [
            ('m_axis_tx_tdata','m_axis_tx_tvalid','m_axis_tx_tready','m_local_tx_tdata','m_local_tx_tvalid','m_local_tx_tready',128),
            ('m_axis_mem_write_cmd_tdata','m_axis_mem_write_cmd_tvalid','m_axis_mem_write_cmd_tready','m_local_write_command','m_local_write_command_valid','m_local_write_command_ready',96),
            ('m_axis_mem_read_cmd_tdata','m_axis_mem_read_cmd_tvalid','m_axis_mem_read_cmd_tready','m_local_read_command','m_local_read_command_valid','m_local_read_command_ready',96),
            ('m_axis_mem_write_tdata','m_axis_mem_write_tvalid','m_axis_mem_write_tready','m_local_write_tdata','m_local_write_tvalid','m_local_write_tready',512),
            ('m_axis_ack_tdata','m_axis_ack_tvalid','m_axis_ack_tready','m_local_ack_tdata','m_local_ack_tvalid','m_local_ack_tready',40)]:
            body+=f"dut.core.STUB_{data}={width}'hfedcba;dut.core.STUB_{valid}=1;{lr}=1;#1;if(!{lv} || {ld}!=={width}'hfedcba || {valid} || !dut.core.{ready})$fatal(1,\"local output route {data}\");dut.core.STUB_{valid}=0;\n"
        body+=r'''
s_local_read_tdata=512'hf234567;s_local_read_tkeep=64'hff;s_local_read_tlast=1;s_local_read_tvalid=1;dut.core.STUB_s_axis_mem_read_tready=1;#1;
if(!dut.core.s_axis_mem_read_tvalid || dut.core.s_axis_mem_read_tdata!==512'hf234567 || !s_local_read_tready || s_axis_mem_read_tready)$fatal(1,"local source data");
s_local_read_tvalid=0;repeat(3)@(negedge clk);if(shared_hls_fault || !local_hls_active)$fatal(1,"positive routing fault");
'''
        self.simulate(body)

    def test_retire_needs_full_owner_and_real_core_drain_not_idle(self):
        for drain in ["1'b0","1'bx","1'bz"]:
            self.simulate(f'owner({context()});SQ({expected_sq()});s_local_retire_context=expected_owner;s_local_retire_valid=1;local_core_drained={drain};'+r'''
repeat(31)begin @(negedge clk);if(s_local_retire_ready || !local_hls_active || local_hls_queue_guard!==8'h80 || shared_hls_fault)$fatal(1,"idle became real core drain");end
''')
        self.simulate(f'owner({context()});SQ({expected_sq()});'+r'''
s_local_retire_context=expected_owner;s_local_retire_valid=1;local_core_drained=1;
@(posedge clk);if(!s_local_retire_ready)$fatal(1,"exact modeled certificate not accepted");
@(negedge clk);s_local_retire_valid=0;#1;if(local_hls_active || local_hls_queue_guard || shared_hls_fault)$fatal(1,"certified role retirement");
''')

    def test_invalid_full_owner_never_aliases_trusted_QPN_range(self):
        for ctx in [context(qpn=0x800007),context(qpn=6),context(tag=0),context(sequence=0),context(epoch=0),context(authorized=0),
            context(flags=2),context(length=0),context(length=4097),context(address=(1<<64)-1,length=2),"588'hx"]:
            self.simulate(f's_local_owner_context={ctx};s_local_owner_valid=1;'+r'''
#1;if(s_local_owner_ready)$fatal(1,"invalid owner accepted");@(posedge clk);@(negedge clk);s_local_owner_valid=0;quarantined();if(local_hls_active)$fatal(1,"bad owner captured");
''')

    def test_full_SQ_fields_and_explicit_zero_high_allone_keys(self):
        for key in [0,0x80000000,0xffffffff]:
            self.simulate(f'owner({context(rkey=key)});SQ({expected_sq(rkey=key)});if(shared_hls_fault)$fatal(1,"full key mode");')
        correct=int(expected_sq().split("'h")[1],16)
        for bit in [0,32,42,43,48,111,112,175,176,207,208,239,240,241,247]:
            self.simulate(f"owner({context()});s_local_sq_tdata=248'h{correct^(1<<bit):062x};s_local_sq_tvalid=1;"+r'''
#1;if(s_local_sq_tready || dut.core.s_axis_sq_tvalid)$fatal(1,"mutated SQ reached HLS");
@(posedge clk);@(negedge clk);s_local_sq_tvalid=0;quarantined();
''')

    def test_stale_retire_unowned_HLS_inflight_config_quarantine(self):
        for ctx in [context(sequence=2),context(epoch=2),context(pd=1),context(lkey=9),context(address=123),"588'hx"]:
            self.simulate(f'owner({context()});SQ({expected_sq()});s_local_retire_context={ctx};s_local_retire_valid=1;local_core_drained=1;'+r'''
#1;if(s_local_retire_ready)$fatal(1,"stale owner retired");@(posedge clk);@(negedge clk);s_local_retire_valid=0;quarantined();
''')
        for field in ['m_axis_tx_tvalid','m_axis_ack_tvalid','m_axis_mem_read_cmd_tvalid','m_axis_mem_write_cmd_tvalid','m_axis_mem_write_tvalid']:
            self.simulate(f'dut.core.STUB_{field}=1;@(posedge clk);@(negedge clk);quarantined();')
        self.simulate(f'owner({context()});s_axis_qp_tvalid=1;@(posedge clk);@(negedge clk);s_axis_qp_tvalid=0;quarantined();')

    @classmethod
    def tearDownClass(cls):
        if name:=os.environ.get('AS02_RNIC_SHARED_ROLE_UNIT_REPORT'):
            p=Path(name);p=p if p.is_absolute()else ROOT/p
            methods=len(cls.reports);simulations=sum(map(len,cls.reports.values()))
            r=dict(scope=__doc__,pass_test=methods==5 and simulations==46,methods=methods,simulations=simulations,
                tests=cls.reports,actual_HLS=False,actual_core_drain_certificate=False,hardware_verified=False)
            with p.open('x')as out:out.write(json.dumps(r,indent=2)+'\n')


if __name__=='__main__':unittest.main()
