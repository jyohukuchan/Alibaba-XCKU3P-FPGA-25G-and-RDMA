# SPDX-License-Identifier: BSD-2-Clause-Views
"""Four-state ordinary zero-service owner reservation, actual RTL, endpoints modeled."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
import test_zero_service_mac_rtl as mac

ROOT=mac.ROOT
RTL=ROOT/'rdma/rnic/rtl/rocev2_zero_service_owner.v'
CONTEXT=mac.values()[0]
TB=r'''
`timescale 1ns/1ps
module tb;
// DECLARATIONS
always #2 clk=~clk;
integer cycles=0,mac_transfers=0,hls_transfers=0;
reg [527:0] expected=528'hCONTEXT;
reg mac_stalled=0,hls_stalled=0;
reg [527:0] held_mac;reg [343:0] held_hls;
always @(posedge clk)if(!rst)begin
 cycles=cycles+1;if(cycles>300)$fatal(1,"bounded deadline");
 if(mac_stalled && (!m_mac_valid || m_mac_owner!==held_mac))$fatal(1,"MAC reservation retracted");
 if(hls_stalled && (!m_hls_valid || m_hls_owner!==held_hls))$fatal(1,"HLS owner retracted");
 mac_stalled=m_mac_valid&&!m_mac_ready;held_mac=m_mac_owner;
 hls_stalled=m_hls_valid&&!m_hls_ready;held_hls=m_hls_owner;
 if(m_mac_valid && m_mac_ready)begin
  if(m_mac_owner!==expected || hls_transfers>=mac_transfers+1)$fatal(1,"MAC owner identity/order");
  mac_transfers=mac_transfers+1;
 end
 if(m_hls_valid && m_hls_ready)begin
  if(m_hls_owner!==expected[343:0] || hls_transfers>=mac_transfers)$fatal(1,"HLS before actual MAC reservation");
  hls_transfers=hls_transfers+1;
 end
end
task admit;
 begin
  @(negedge clk);s_owner=expected;s_valid=1;
  @(posedge clk);if(!s_ready || queue_guard!==4 || !configuration_guard)$fatal(1,"missing admitted owner guard");
  @(negedge clk);s_valid=0;s_owner=0;
 end
endtask
initial begin
 rst=1;repeat(4)@(negedge clk);rst=0;
 // BODY
 $display("ZERO_SERVICE_OWNER_UNIT {\"pass_test\":true,\"mac\":%0d,\"hls\":%0d}",mac_transfers,hls_transfers);
 $finish;
end
endmodule
'''


class ZeroServiceOwnerTests(unittest.TestCase):
    def simulate(self,body):
        before=hashlib.sha256(RTL.read_bytes()).hexdigest()
        tb=TB.replace('// DECLARATIONS',mac.helper.instance(RTL,'dut','',{}))
        tb=tb.replace('CONTEXT',f'{CONTEXT:0132x}').replace('// BODY',body)
        with tempfile.TemporaryDirectory(prefix='as02-zero-service-owner-')as temporary:
            p=Path(temporary);(p/'tb.v').write_text(tb)
            c=subprocess.run(['iverilog','-g2012','-s','tb','-o',str(p/'tb.vvp'),str(p/'tb.v'),str(RTL)],
                capture_output=True,text=True,timeout=30)
            self.assertEqual(c.returncode,0,c.stdout+c.stderr)
            r=subprocess.run(['vvp',str(p/'tb.vvp')],capture_output=True,text=True,timeout=10)
            self.assertEqual(r.returncode,0,r.stdout+r.stderr)
            rows=[json.loads(l.split(' ',1)[1])for l in r.stdout.splitlines()if l.startswith('ZERO_SERVICE_OWNER_UNIT ')]
            self.assertEqual(len(rows),1,r.stdout);self.assertTrue(rows[0]['pass_test'])
        self.assertEqual(before,hashlib.sha256(RTL.read_bytes()).hexdigest())

    def test_MAC_backpressure_prevents_HLS_owner_and_preserves_snapshot(self):
        self.simulate(r'''
admit();m_hls_ready=1;repeat(25)@(negedge clk);
if(!m_mac_valid || m_hls_valid || mac_transfers || hls_transfers || !configuration_guard || queue_guard!==4)
 $fatal(1,"unreserved owner reached HLS");
m_mac_ready=1;repeat(5)@(negedge clk);
if(mac_transfers!=1 || hls_transfers!=1 || configuration_guard || fault || reserved_count!=1 || delivered_count!=1)
 $fatal(1,"ordered delivery incomplete");
''')

    def test_HLS_backpressure_keeps_owned_word_and_second_input_blocked(self):
        self.simulate(r'''
admit();m_mac_ready=1;repeat(5)@(negedge clk);
if(!m_hls_valid || mac_transfers!=1 || hls_transfers || s_ready)$fatal(1,"owner lost or duplicate input accepted");
s_owner=expected;s_valid=1;repeat(20)@(negedge clk);
if(s_ready || m_mac_valid || m_hls_owner!==expected[343:0] || fault)$fatal(1,"held HLS owner changed");
s_valid=0;m_hls_ready=1;repeat(5)@(negedge clk);
if(configuration_guard || hls_transfers!=1 || fault)$fatal(1,"held owner not delivered");
''')

    def test_late_parent_fault_does_not_retract_MAC_offer_or_release_guard(self):
        self.simulate(r'''
admit();repeat(5)@(negedge clk);parent_fault=1;repeat(15)@(negedge clk);
if(!fault || !m_mac_valid || m_hls_valid || !configuration_guard || queue_guard!==255 || s_ready)
 $fatal(1,"fault retracted reservation or granted unreserved HLS work");
''')

    def test_late_parent_fault_does_not_retract_HLS_offer_or_duplicate_transfer(self):
        self.simulate(r'''
admit();m_mac_ready=1;repeat(5)@(negedge clk);parent_fault=1;repeat(15)@(negedge clk);
if(!fault || !m_hls_valid || !configuration_guard || queue_guard!==255)$fatal(1,"HLS offer retracted");
m_hls_ready=1;repeat(10)@(negedge clk);
if(hls_transfers!=1 || m_hls_valid || !fault || !configuration_guard || queue_guard!==255 || s_ready)
 $fatal(1,"late fault duplicated delivery or released guard");
''')

    def test_invalid_or_unknown_owner_never_acquires_downstream_authority(self):
        for change in ["s_owner[23:0]=24'h800002;","s_owner[103:40]=0;","s_owner[167:104]=0;",
                       "s_owner[527:524]=4'hx;","s_owner[520]=1;","s_valid=1'bx;","s_owner[183:168]=0;","s_owner[343:312]=1;","s_owner[215:208]=8'h12;"]:
            with self.subTest(change=change):self.simulate(r'''
@(negedge clk);s_owner=expected;s_valid=1;m_mac_ready=1;m_hls_ready=1;
'''+change+r'''
repeat(10)@(negedge clk);
if(!fault || s_ready || m_mac_valid || m_hls_valid || mac_transfers || hls_transfers ||
 !configuration_guard || queue_guard!==255)$fatal(1,"unknown owner gained authority");
''')


if __name__=='__main__':
    import argparse,time
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve evidence')
    inputs=[RTL,Path(__file__).resolve(),Path(mac.__file__).resolve(),Path(mac.helper.__file__).resolve()]
    digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    before={str(p.relative_to(ROOT)):digest(p)for p in inputs};start=time.monotonic()
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ZeroServiceOwnerTests))
    assert all(digest(ROOT/n)==h for n,h in before.items())
    report=dict(scope=__doc__,pass_test=result.wasSuccessful(),methods=result.testsRun,
        seconds=time.monotonic()-start,source_sha256=before,four_state=True,adjacent_HLS_MAC_modeled=True,
        native_or_hardware_runtime=False)
    with a.report.open('x')as f:f.write(json.dumps(report,indent=2)+'\n')
    raise SystemExit(not result.wasSuccessful())
