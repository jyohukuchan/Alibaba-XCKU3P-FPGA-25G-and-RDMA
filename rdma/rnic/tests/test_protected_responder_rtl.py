# SPDX-License-Identifier: BSD-2-Clause-Views
"""Fast admission/backend-contract RTL units with an EXPLICIT transport stub.

These do NOT verify HLS interoperability or actual response wire bytes. The
separate probe_protected_responder.py runs those checks with real generated HLS.
Here a deliberately faulty transport exercises fail-closed backend contracts.
The real admission IPv4/ICRC, MR table, parser and lease logic are not mocked.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

import probe_protected_responder as probe

ROOT=probe.ROOT

STUB=r'''
reg [511:0] header=0;
reg [8:0] index=0;
reg pending=0,command_sent=0,data_sent=0;
reg [31:0] position=0;
wire write_op=header[28*8+:8]==8'h0a;
wire [63:0] va={header[40*8+:8],header[41*8+:8],header[42*8+:8],header[43*8+:8],
 header[44*8+:8],header[45*8+:8],header[46*8+:8],header[47*8+:8]};
wire [31:0] length={header[52*8+:8],header[53*8+:8],header[54*8+:8],header[55*8+:8]};
wire [27:0] wire_length=write_op ? (length+3)&32'hfffffffc : length;
wire [23:0] qpn={header[33*8+:8],header[34*8+:8],header[35*8+:8]};
wire [93:0] command={qpn[9:0],va[51:48],1'b1,1'b0,va[52],1'b1,wire_length,va[47:0]};
// INJECTION 1..5: corrupt an address, length, host flag, route or QP field.
wire [95:0] emitted_command={2'd0,command} ^ COMMAND_XOR;
wire selected_write=write_op ^ REVERSE_DIRECTION;
wire [63:0] keep=(wire_length-position>=64) ? 64'hffffffffffffffff : (64'h1<<(wire_length-position))-1;
always @(posedge clk) begin
 if(rst) begin header<=0;index<=0;pending<=0;command_sent<=0;data_sent<=0;position<=0;end
 else begin
  if(s_axis_rx_tvalid && s_axis_rx_tready) begin
   if(index<4) header[index*128+:128]<=s_axis_rx_tdata;
   if(s_axis_rx_tlast) begin pending<=1;index<=0;command_sent<=0;data_sent<=0;position<=0;end
   else index<=index+1'b1;
  end
  if((m_axis_mem_write_cmd_tvalid && m_axis_mem_write_cmd_tready) ||
     (m_axis_mem_read_cmd_tvalid && m_axis_mem_read_cmd_tready)) command_sent<=1;
  if((m_axis_mem_write_tvalid && m_axis_mem_write_tready) ||
     (s_axis_mem_read_tvalid && s_axis_mem_read_tready)) begin
   if(position+64>=wire_length) data_sent<=1;
   else position<=position+64;
  end
  if(m_axis_tx_tvalid && m_axis_tx_tready) pending<=0;
 end
end
'''


def stub_source(xor=0,reverse=0,bad_keep=0,bad_last=0):
    baseline=(ROOT/'rdma/rtl/rocev2_integrity_transport.v').read_text()
    declaration='module rocev2_integrity_transport ('+baseline.split('module rocev2_integrity_transport (',1)[1].split(');',1)[0]+');\n'
    declaration=re.sub(r'output reg ', 'output wire ', declaration)
    declaration=re.sub(r'=0\b','',declaration)
    values=dict(s_axis_rx_tready='!pending',s_axis_qp_tready="1'b1",s_axis_conn_tready="1'b1",s_axis_sq_tready="1'b1",
        m_axis_tx_tdata="128'h1234",m_axis_tx_tkeep="16'hffff",m_axis_tx_tvalid='pending',m_axis_tx_tlast="1'b1",
        m_axis_mem_write_cmd_tdata='emitted_command',m_axis_mem_read_cmd_tdata='emitted_command',
        m_axis_mem_write_cmd_tvalid='pending && !command_sent && selected_write',
        m_axis_mem_read_cmd_tvalid='pending && !command_sent && !selected_write',
        m_axis_mem_write_tdata="512'd0",m_axis_mem_write_tkeep="64'd0" if bad_keep else 'keep',
        m_axis_mem_write_tvalid='pending && write_op && command_sent && !data_sent',
        m_axis_mem_write_tlast="1'b1" if bad_last else 'position+64>=wire_length',
        s_axis_mem_read_tready='pending && !write_op && command_sent && !data_sent')
    outputs=re.findall(r'output wire\s+(?:\[[^\]]+\]\s+)?(\w+)',declaration)
    assignments='\n'.join(f'assign {name}={values.get(name,"0")};' for name in outputs)
    body=STUB.replace('COMMAND_XOR',f"96'h{xor:x}").replace('REVERSE_DIRECTION',f"1'b{reverse}")
    return declaration+body+assignments+'\nendmodule\n'


class ProtectedResponderUnitTests(unittest.TestCase):
    reports={}

    def simulate(self,tb,fixtures,stub):
        axis=ROOT/'external/corundum/fpga/lib/axis/rtl'
        rtl=[ROOT/'rdma/rnic/rtl'/name for name in ('rocev2_mr_table.v','rocev2_protected_responder.v')]
        rtl += [ROOT/'rdma/rtl/rocev2_ipv4_icrc.v',ROOT/'external/corundum/fpga/lib/eth/rtl/lfsr.v']
        rtl += [axis/name for name in ('axis_register.v','axis_fifo.v')]
        with tempfile.TemporaryDirectory(prefix='as02-protected-unit-') as directory:
            path=Path(directory);(path/'tb.v').write_text(tb);(path/'stub.v').write_text(stub)
            (path/'input.hex').write_text(''.join(f'{word:x}\n' for word in fixtures))
            compiled=subprocess.run(['iverilog','-g2012','-s','tb','-o',str(path/'test.vvp'),
                str(path/'tb.v'),str(path/'stub.v'),*map(str,rtl)],capture_output=True,text=True,timeout=20)
            self.assertEqual(compiled.returncode,0,compiled.stderr)
            ran=subprocess.run(['vvp',str(path/'test.vvp')],cwd=path,capture_output=True,text=True,timeout=15)
            self.assertEqual(ran.returncode,0,ran.stdout+ran.stderr)
            rows=[json.loads(line[7:]) for line in ran.stdout.splitlines() if line.startswith('RESULT ')]
            self.assertEqual(len(rows),1,ran.stdout)
            self.reports.setdefault(self._testMethodName,[]).append(rows[0])

    def test_admission_rejections_lease_and_invalidation(self):
        fixtures,body,_=probe.stimulus()
        tb=probe.TB.replace('STIMULUS_LAST',str(len(fixtures)-1)).replace('// TEST_BODY','\n'.join(body))
        self.simulate(tb,fixtures,stub_source())

    def fault_case(self,expected,*,xor=0,reverse=0,bad_keep=0,bad_last=0,bad_status=0,bad_tag=False,read=False):
        endpoint=dict(source_mac='b8:83:03:67:c5:d0',destination_mac='8a:f3:fb:b9:75:31',
            source_ip='198.18.11.1',destination_ip='198.18.11.2',udp_source_port=49152,
            destination_qpn=2,psn=probe.PSN,remote_address=probe.VA+0x210,rkey=8)
        if read:frame=probe.read_wire.encode(**endpoint,opcode=probe.read_wire.REQUEST,read_bytes=65)
        else:frame=probe.rocev2_wire.write_only_frame(**endpoint,payload=probe.PAYLOAD)
        fixtures=probe.words(frame[14:])
        body=f'''
expect_fault=1;send_frame(0,{len(fixtures)});
expiry=cycle+1000;while(!fault && cycle<expiry) @(negedge clk);
if(!fault || fc!={expected} || completed!=0 || txframes!=0 || quiet || cr)
 $fatal(1,"not fail-closed fault=%b/%d",fault,fc);
repeat(100) @(negedge clk);
if(tv || mv || wdv || rr || sr || completed!=0 || quiet || cr) $fatal(1,"side effect after sticky fault");
$display("RESULT {{\\\"pass_test\\\":true,\\\"fault_code\\\":%0d,\\\"commands_before_fault\\\":%0d}}",fc,commands);
$finish;
'''
        # Verilog string escaping, not transport or DUT internals.
        body=body.replace('\\\\\\"','\\"')
        tb=probe.TB.replace('STIMULUS_LAST',str(len(fixtures)-1)).replace('// TEST_BODY',body)
        if bad_status:tb=tb.replace('st=backend_tag;se=0;',f'st=backend_tag;se={bad_status};')
        if bad_tag:tb=tb.replace('st=backend_tag;se=0;','st=backend_tag+1;se=0;')
        if read and (bad_keep or bad_last):
            injection='if(rdv) rk=0;' if bad_keep else 'if(rdv) rl=1;'
            tb=tb.replace('st=backend_tag;se=0;','st=backend_tag;se=0;'+injection)
        self.simulate(tb,fixtures,stub_source(xor,reverse,bad_keep,bad_last))

    def test_command_address_length_host_route_and_qp_corruption(self):
        for bit in (0,48,79,80,84):
            with self.subTest(bit=bit):self.fault_case(32,xor=1<<bit)

    def test_unexpected_command_direction(self):self.fault_case(35,reverse=1)
    def test_bad_write_keep(self):self.fault_case(33,bad_keep=1)
    def test_early_write_last(self):self.fault_case(33,bad_last=1)
    def test_backend_error_never_acknowledged(self):self.fault_case(34,bad_status=1)
    def test_wrong_completion_tag_never_acknowledged(self):self.fault_case(34,bad_tag=True)
    def test_bad_read_keep(self):self.fault_case(33,read=True,bad_keep=1)
    def test_early_read_last(self):self.fault_case(33,read=True,bad_last=1)

    def test_pending_invalidation_does_not_deadlock_partial_frame(self):
        frame=probe.rocev2_wire.write_only_frame(source_mac='b8:83:03:67:c5:d0',destination_mac='8a:f3:fb:b9:75:31',
            source_ip='198.18.11.1',destination_ip='198.18.11.2',udp_source_port=49152,
            destination_qpn=2,psn=probe.PSN,remote_address=probe.VA+0x210,rkey=8,payload=probe.PAYLOAD)
        fixtures=probe.words(frame[14:])
        body=f'''
send_frame(0,{len(fixtures)});
while(quiet) @(negedge clk);
ci=0;cp=17;cc=2;ck=8;cv=1;car=0;revoke_watch=1;
expiry=cycle+2000;while(completed==0 && cycle<expiry) @(negedge clk);
if(completed!=1) $fatal(1,"pending management blocked partial frame");
revoke_watch=0;
@(posedge clk);while(!cr) @(posedge clk);
@(negedge clk);cv=0;
while(!cav) @(negedge clk);
if(ce!==0) $fatal(1,"deferred invalidation failed");
car=1;@(negedge clk);car=0;
'''
        tb=probe.TB.replace('STIMULUS_LAST',str(len(fixtures)-1)).replace('// TEST_BODY',body)
        self.simulate(tb,fixtures,stub_source())

    @classmethod
    def tearDownClass(cls):
        if name:=os.environ.get('AS02_RNIC_RESPONDER_UNIT_REPORT'):
            paths=[Path(__file__),ROOT/'rdma/rnic/rtl/rocev2_protected_responder.v',
                   ROOT/'rdma/rnic/rtl/rocev2_mr_table.v',ROOT/'rdma/rnic/tests/probe_protected_responder.py',
                   ROOT/'rdma/rtl/rocev2_ipv4_icrc.v',ROOT/'rdma/rtl/rocev2_integrity_transport.v',
                   ROOT/'rdma/host/rocev2_wire.py',ROOT/'rdma/read/host/read_wire.py',
                   ROOT/'rdma/tests/test_icrc_rtl.py']
            paths += [ROOT/'external/corundum/fpga/lib/axis/rtl'/file for file in ('axis_fifo.v','axis_register.v')]
            paths.append(ROOT/'external/corundum/fpga/lib/eth/rtl/lfsr.v')
            runs=sum(map(len,cls.reports.values()))
            report=dict(scope='Actual admission/MR/lease/backend-contract RTL with EXPLICIT transport stub, not HLS wire evidence',
                        hardware_verified=False,board_integrated=False,transport_stub=True,
                        pass_test=len(cls.reports)==10 and runs==14,method_count=len(cls.reports),simulation_count=runs,
                        tests=cls.reports,source_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths})
            # make -C changes cwd; relative evidence paths are repository-root
            # relative, not relative to rdma/rnic. Preserve prior reports.
            output=Path(name)
            if not output.is_absolute():output=ROOT/output
            with output.open('x') as out:out.write(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':unittest.main()
