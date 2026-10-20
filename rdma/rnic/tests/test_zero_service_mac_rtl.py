# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual ordinary zero-service MAC/owner RTL, adjacent endpoints MODELED.

Exact genuine-owner/core/wire join, fresh SFD tag, accepted MAC EOF/tail,
backpressure, stale/unknown receipt and late fault. Not native/HW signoff.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import time
import unittest
import probe_atomic_responder as helper

ROOT=helper.ROOT;RTL=ROOT/'rdma/rnic/rtl/rocev2_zero_service_mac.v'
OWNER_RTL=RTL.with_name('rocev2_zero_service_owner.v')
AXIS=ROOT/'external/corundum/fpga/lib/axis/rtl'
SOURCES=[RTL,*[AXIS/n for n in ['axis_arb_mux.v','arbiter.v','priority_encoder.v']]]
sys.path.insert(0,str(ROOT/'rdma/host'));import rocev2_wire as wire
digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()


def values(read=False,psn=0xffffff,msn=0xabcdef):
    o=2|(17<<24)|(0x9123456700000001<<40)|(0xfedcba9889abcdef<<104)|(0x1234<<168)|\
      (psn<<184)|((0x0c if read else 0x0a)<<208)|(((1<<64)-1)<<216)|(0xfedcba98<<280)
    context=o|(0xf12347<<344)|(0xc6120b01<<368)|(0xc6120b02<<400)|(0x020000000001<<432)|(0x020000000002<<480)
    core=o|(((psn+1)&0xffffff)<<344)|(msn<<368)|(15<<392)
    bth=bytes([0x10 if read else 0x11,0x40])+struct.pack('!H',0xffff)+bytes(1)+(0xf12347).to_bytes(3,'big')+bytes(1)+psn.to_bytes(3,'big')
    body=bth+bytes(1)+msn.to_bytes(3,'big')
    ip=bytearray(struct.pack('!BBHHHBBHII',0x45,0,48,0,0x4000,64,17,0,0xc6120b02,0xc6120b01))
    ip[10:12]=wire.internet_checksum(ip).to_bytes(2,'big')
    p=bytes(ip)+struct.pack('!HHHH',4791,4791,28,0)+body+bytes(4);p=p[:-4]+wire.icrc_ipv4(p)
    frame=bytes.fromhex('0200000000010200000000020800')+p
    assert len(frame)==62
    return context,core,frame


TB=r'''
`timescale 1ns/1ps
module tb;
// DECLARATIONS
always #2 clk=~clk;
reg [527:0] expected_owner=528'hOWNER;
reg [399:0] expected_core=400'hCORE;
reg [127:0] words[0:3];
integer cycle=0,i,deadline,frames=0,translated=0;
reg stall=0,retire_stall=0;reg [161:0] held;reg [855:0] held_retire;
always @(posedge clk)if(!rst)begin
 cycle=cycle+1;if(cycle>15000)$fatal(1,"bounded zero service MAC deadline");
 if(stall && (!m_axis_mac_tvalid || {m_axis_mac_tdata,m_axis_mac_tkeep,m_axis_mac_tlast,m_axis_mac_tuser}!==held))$fatal(1,"MAC beat changed under stall");
 stall=m_axis_mac_tvalid&&!m_axis_mac_tready;held={m_axis_mac_tdata,m_axis_mac_tkeep,m_axis_mac_tlast,m_axis_mac_tuser};
 if(retire_stall && (!m_retire_valid || {m_retire_owner,m_retire_core,m_retire_tag,m_retire_timestamp}!==held_retire))$fatal(1,"retirement changed under stall");
 retire_stall=m_retire_valid&&!m_retire_ready;held_retire={m_retire_owner,m_retire_core,m_retire_tag,m_retire_timestamp};
 if(m_axis_mac_tvalid && m_axis_mac_tready)begin
  $display("ZERO_SERVICE_MAC_OUT %032h %04h %0d %04h",m_axis_mac_tdata,m_axis_mac_tkeep,m_axis_mac_tlast,m_axis_mac_tuser[16:1]);
  if(m_axis_mac_tlast)frames=frames+1;
 end
 if(m_native_cpl_valid && m_native_cpl_ready)begin
  $display("ZERO_SERVICE_CPL %04h %024h",m_native_cpl_tag,m_native_cpl_ts);
  if(m_native_cpl_tag==16'h4000)translated=translated+1;
 end
end
task bind_owner;
 begin
  @(negedge clk);s_owner=expected_owner;s_owner_valid=1;
  @(posedge clk);if(!s_owner_ready || queue_guard!==4)$fatal(1,"ordinary owner reservation");
  @(negedge clk);s_owner_valid=0;s_owner=0;
  if(!busy || !configuration_guard || m_retire_valid)$fatal(1,"lost genuine owner");
 end
endtask
task offer_core;
 begin
  @(negedge clk);s_core_done=expected_core;s_core_valid=1;
  @(posedge clk);while(!s_core_ready)@(posedge clk);
  @(negedge clk);s_core_valid=0;
 end
endtask
task send_packet;
 begin
  for(i=0;i<4;i=i+1)begin
   @(negedge clk);s_axis_native_tdata=words[i];s_axis_native_tkeep=i==3 ? 16'h3fff:16'hffff;
   s_axis_native_tlast=i==3;s_axis_native_tuser={16'h4000,1'b0};s_axis_native_tvalid=1;
   @(posedge clk);while(!s_axis_native_tready && !fault)@(posedge clk);
  end
  @(negedge clk);s_axis_native_tvalid=0;
 end
endtask
task receipt;input [15:0] nonce;
 begin
  @(negedge clk);s_mac_cpl_tag=nonce;s_mac_cpl_ts=96'h0123456789abcdef01234567;s_mac_cpl_valid=1;
  @(posedge clk);while(!s_mac_cpl_ready)@(posedge clk);
  @(negedge clk);s_mac_cpl_valid=0;
 end
endtask
task await_frame;
 begin
  deadline=cycle+300;
  while(!frames && !fault)begin @(negedge clk);if(cycle>deadline)$fatal(1,"zero response frame timeout");end
  if(fault)$fatal(1,"unexpected zero MAC fault%h",fault_code);
 end
endtask
task quarantined;
 begin
  repeat(1200)@(negedge clk);
  if(!fault || !busy || !configuration_guard || queue_guard!==255 || m_retire_valid)$fatal(1,"unsafe faulty owner release");
 end
endtask
initial begin
 rst=1;$readmemh("input.hex",words);repeat(5)@(negedge clk);rst=0;enable=1;m_native_cpl_ready=1;
 // BODY
 $display("ZERO_SERVICE_MAC_UNIT {\"pass_test\":true,\"frames\":%0d,\"translated\":%0d}",frames,translated);$finish;
end
endmodule
'''


class ZeroServiceMAC(unittest.TestCase):
    reports={}
    def simulate(self,body,read=False,expected_frames=None):
        context,core,frame=values(read)
        t=TB.replace('// DECLARATIONS',helper.instance(RTL,'dut','',{})).replace('528\'hOWNER',f"528'h{context:0132x}")
        t=t.replace('400\'hCORE',f"400'h{core:0100x}").replace('// BODY',body)
        run=Path(tempfile.mkdtemp(prefix='zero-service-mac-',dir=ROOT/'rdma/rnic/build'))
        ram=Path(tempfile.mkdtemp(prefix='as02-zero-service-mac-',dir='/dev/shm'))
        (run/'tb.v').write_text(t);(run/'input.hex').write_text(''.join(f'{int.from_bytes(frame[n:n+16].ljust(16,bytes(1)),"little"):032x}\n'for n in range(0,62,16)))
        c=subprocess.run(['iverilog','-g2012','-s','tb','-o',str(ram/'test'),str(run/'tb.v'),*map(str,SOURCES)],capture_output=True,text=True,timeout=30)
        (run/'compile.log').write_text(c.stdout+c.stderr);self.assertEqual(c.returncode,0,c.stdout+c.stderr)
        self.assertFalse(any('expects'in l and 'bits'in l for l in c.stderr.splitlines()),c.stderr)
        start=time.monotonic();r=subprocess.run(['vvp',str(ram/'test')],cwd=run,capture_output=True,text=True,timeout=10)
        (run/'simulation.log').write_text(r.stdout+r.stderr);self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        if expected_frames is not None:
            actual=[];data=bytearray();tag=None
            for line in r.stdout.splitlines():
                if line.startswith('ZERO_SERVICE_MAC_OUT '):
                    _,d,k,last,nonce=line.split();data+=int(d,16).to_bytes(16,'little')[:int(k,16).bit_count()]
                    if tag is None:tag=int(nonce,16)
                    self.assertEqual(tag,int(nonce,16))
                    if last=='1':actual.append((tag,bytes(data)));data.clear();tag=None
            self.assertFalse(data);self.assertEqual(actual,[(0x4001+i,frame)for i in range(expected_frames)])
        self.reports.setdefault(self._testMethodName,[]).append(dict(directory=str(run.relative_to(ROOT)),seconds=time.monotonic()-start,
            artifacts={str(p.relative_to(ROOT)):digest(p)for p in run.iterdir()if p.is_file()},RAM_binary_sha256=digest(ram/'test')))

    def test_WRITE_READ_need_exact_core_SFD_EOF_tail_and_stable_retirement(self):
        for read in [False,True]:
            self.simulate(r'''
bind_owner();send_packet();m_axis_mac_tready=1;repeat(1200)@(negedge clk);
if(frames || m_retire_valid || !busy)$fatal(1,"wire before actual core receipt");
offer_core();await_frame();repeat(1200)@(negedge clk);
if(m_retire_valid || receipt_count || !busy)$fatal(1,"EOF invented SFD completion");
receipt(active_tag);repeat(500)@(negedge clk);if(m_retire_valid)$fatal(1,"tail shortened");
repeat(600)@(negedge clk);
if(!m_retire_valid || retired_count || translated!=1 || m_retire_owner!==expected_owner[343:0] || m_retire_core!==expected_core ||
 m_retire_tag!==16'h4001 || m_retire_timestamp!==96'h0123456789abcdef01234567)$fatal(1,"exact ordinary retirement");
repeat(30)@(negedge clk);m_retire_ready=1;repeat(5)@(negedge clk);
if(busy || configuration_guard || fault || retired_count!=1)$fatal(1,"proved lifetime not released");
''',read,1)

    def test_MAC_backpressure_blocks_EOF_and_source_owner_changes_do_not_retarget(self):
        self.simulate(r'''
bind_owner();offer_core();send_packet();repeat(1200)@(negedge clk);
if(!m_axis_mac_tvalid || frames || m_retire_valid || active_tag!==16'h4001)$fatal(1,"stalled actual frame lost");
s_owner=~expected_owner;repeat(20)@(negedge clk);m_axis_mac_tready=1;await_frame();receipt(active_tag);
repeat(1100)@(negedge clk);if(!m_retire_valid || fault)$fatal(1,"stalled owner lost");
''',expected_frames=1)

    def test_bad_core_or_wire_is_quarantined_before_transmission(self):
        for mutation in ["expected_core[104]=~expected_core[104];","expected_core[392]=0;",
                         "expected_core[344]=1;","words[0][7:0]=8'hff;","words[2][87:80]=8'h12;",
                         "words[3][55:48]=8'hff;"]:
            self.simulate('bind_owner();'+mutation+'offer_core();send_packet();m_axis_mac_tready=1;quarantined();if(frames)$fatal(1,"bad frame transmitted");')

    def test_stale_unknown_duplicate_or_legacy_receipts_never_retire(self):
        for mutation in ["receipt(16'h4002);","receipt(16'h400x);","receipt(16'h4000);",
                         "receipt(active_tag);receipt(active_tag);"]:
            self.simulate('bind_owner();offer_core();send_packet();m_axis_mac_tready=1;await_frame();'+mutation+'quarantined();')
        self.simulate('bind_owner();receipt(active_tag);quarantined();')

    def test_late_parent_fault_retains_owner_and_does_not_retract_stalled_output(self):
        self.simulate(r'''
bind_owner();offer_core();send_packet();repeat(30)@(negedge clk);parent_fault=1;
repeat(30)@(negedge clk);if(!m_axis_mac_tvalid)$fatal(1,"late fault retracted offered packet");
m_axis_mac_tready=1;repeat(20)@(negedge clk);quarantined();
''')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve prior evidence')
    inputs=[*SOURCES,OWNER_RTL,Path(__file__).resolve(),Path(helper.__file__).resolve()]
    before={str(p.relative_to(ROOT)):digest(p)for p in inputs};start=time.monotonic()
    r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ZeroServiceMAC))
    assert all(digest(ROOT/n)==h for n,h in before.items())
    result=dict(scope=__doc__,pass_test=r.wasSuccessful(),methods=r.testsRun,seconds=time.monotonic()-start,
        source_sha256=before,tests=ZeroServiceMAC.reports,four_state=True,physical_MAC_receipts_modeled=True,
        native_or_hardware_runtime=False)
    with a.report.open('x')as f:f.write(json.dumps(result,indent=2)+'\n')
    raise SystemExit(not r.wasSuccessful())
