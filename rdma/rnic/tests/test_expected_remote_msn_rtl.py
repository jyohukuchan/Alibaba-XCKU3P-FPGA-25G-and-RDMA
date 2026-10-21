#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Real SQC/mailbox/fetch owner allocation -> actual expected-MSN predictor.

Route configuration acceptance, authorized WRs, TX expectations and CQ are
models. SQC cookie/epoch/PD replies are REAL, never forced table contents.
No RX-learned/local-MSN source, native runtime/remote peer/physical proof.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import unittest
import test_sq_control_regs_rtl as legacy
import probe_atomic_responder as helper

ROOT=legacy.ROOT;digest=helper.digest
sys.path.insert(0,str(ROOT/'rdma/rnic/fpga'))
import derive_expected_remote_msn_native as source

TASKS=r'''
reg [747:0] expected=0;reg [63:0] wanted_epoch=64'h9123456700000001;reg [23:0] wanted_qpn=7;
task route;
 begin
  @(negedge clk);p_route_qpn=wanted_qpn;p_route_peer_qpn=189+wanted_qpn;p_route_local_ip=32'hc6120b02;p_route_peer_ip=32'hc6120b01;p_route_valid=1;
  repeat(5)@(negedge clk);
 end
endtask
task make_owner;input integer op;input [63:0] seq;
 begin
  expected=0;expected[587:524]=64'hfedcba9876543210+seq;expected[523:460]=seq;expected[459:396]=wanted_epoch;
  expected[395:372]=wanted_qpn;expected[371:356]=17;expected[355:340]=9;expected[339:324]=op;expected[323:308]=1;
  expected[307:276]=(op==7 || op==8) ? 8:8193;expected[275:244]=8;expected[243:180]=64'hfedcba9876543210;
  expected[179:116]=64'h1234567800000210;expected[19:0]=3;
  if(op!=3 && op!=5)begin expected[115:52]=64'he23456789abcdef0;expected[51:20]=32'h81234567;end
  if(op==5 || op==6)expected[619:588]=32'h89abcdef;
 end
endtask
task capture;input integer op;input [63:0] seq;input [23:0] msn;
 begin
  make_owner(op,seq);@(negedge clk);p_s_owner_context=expected;repeat(5)@(negedge clk);#1;
  if(p_owner_eligible!==1'b1 || msn_query_cookie!==64'hfedcba9889abcdef && wanted_epoch==64'h9123456700000001 ||
   msn_query_epoch!==wanted_epoch || msn_query_pd!==17)$fatal(1,"real SQC owner not bound to eligible logical request");
  p_s_owner_fire=1;@(posedge clk);@(negedge clk);p_s_owner_fire=0;#1;
  if(p_expected_msn!==msn || !p_busy || !p_configuration_guard || wire_queue_guard!==(8'd1<<wanted_qpn) || p_fault)$fatal(1,"expected logical MSN/lease not captured");
 end
endtask
task expectation;input [23:0] msn;
 integer n;
 begin
  p_s_expect_context=expected;p_s_expect_valid=1;
  for(n=0;n<20;n=n+1)begin @(negedge clk);if(p_expect_eligible!==1'b1 || p_expected_msn!==msn || p_fault)$fatal(1,"packet/replay expectation changed logical MSN");end
  p_s_expect_valid=0;
 end
endtask
task retire;
 begin
  p_s_retire_context=expected;p_s_retire_offer_valid=1;
  repeat(10)begin @(negedge clk);if(!p_busy || !p_configuration_guard || wire_queue_guard!==(8'd1<<wanted_qpn))$fatal(1,"uncommitted CQ released expected MSN lease");end
  p_s_retire_fire=1;@(posedge clk);if(p_retire_eligible!==1'b1)$fatal(1,"exact accepted CQ identity missing");
  @(negedge clk);p_s_retire_fire=0;p_s_retire_offer_valid=0;#1;
  if(p_busy || p_configuration_guard || wire_queue_guard || p_fault)$fatal(1,"exact CQ failed to release expected MSN owner");
 end
endtask
task quarantine;
 begin repeat(10)@(negedge clk);if(p_fault!==1'b1 || p_busy!==1'b1 || wire_queue_guard!==255 || p_owner_eligible!==1'b0 || p_retire_eligible!==1'b0)$fatal(1,"MSN failure released authority");end
endtask
'''

END=r'''
initial begin
 scenario=0;subcase=0;rst=0;repeat(2)@(negedge clk);rst=1;parent_dma_drained=1;
 repeat(8)@(negedge clk);rst=0;
 // BODY
 if(fatal || mmio_error || fetch_fault || fetches || results)$fatal(1,"unexpected real SQC mutation/fetch/fault");
 $display("EXPECTED_REMOTE_MSN {\"pass_test\":true,\"messages\":%0d,\"retired\":%0d,\"fault\":%0d,\"actual_SQC_configs\":%0d}",p_message_count,p_retired_count,p_fault,configs);$finish;
end
endmodule
'''


class ExpectedMSN(unittest.TestCase):
    reports={}

    def simulate(self,body):
        run=Path(tempfile.mkdtemp(prefix='expected-msn-',dir=ROOT/'rdma/rnic/build'));ram=Path(tempfile.mkdtemp(prefix='as02-expected-msn-',dir='/dev/shm'))
        derived=source.derive()
        sq=run/'rocev2_sq_control_regs.v';sq.write_text(derived[source.RTL/sq.name])
        fetch=run/'rocev2_sq_fetch.v';fetch.write_text(derived[source.RTL/fetch.name])
        io=re.findall(r'\b(input|output)\s+(?:wire|reg)\s+(?:\[([^]]+)\]\s+)?(\w+)',sq.read_text().split('\n);',1)[0])
        driven={'cfg_ready','cfg_response_error','cfg_response_qpn','cfg_response_epoch','cfg_response_consumer','cfg_response_valid','fetch_queue_guard','wire_queue_guard','msn_query_qpn'}
        decl='\n'.join(legacy.pcie.declaration(n,legacy.pcie.width(w,dict(ADDR_WIDTH=12,MAX_QPS=8)),'reg'if d=='input'and n not in driven else'wire')for d,w,n in io)
        macros='\n'.join('localparam '+n+'='+re.sub(r'([0-9a-fA-F]+)U$',r'\1',v).replace('0x',"32'h")+';'for n,v in re.findall(r'^#define (AS02_SQC_\w+) (\w+)',legacy.HEADER.read_text(),re.M))
        pred=helper.instance(source.PRED,'predictor','p_',dict(clk='clk',rst='rst',m_query_qpn='msn_query_qpn',s_query_cookie='msn_query_cookie',s_query_epoch='msn_query_epoch',s_query_pd='msn_query_pd',s_query_valid='msn_query_valid',queue_guard='wire_queue_guard'))
        # These are direct wires from the genuine new SQC lookup, not a model.
        prefix=legacy.TB[:legacy.TB.index('initial begin\n scenario=0;')]
        prefix=source.once(prefix,'#(.INITIAL_SEQUENCE(INITIAL_SEQUENCE_VALUE)) dut',
            '#(.IMMEDIATE_ENABLE(1),.INITIAL_SEQUENCE(INITIAL_SEQUENCE_VALUE)) dut')
        prefix=source.once(prefix,'wire [511:0] result_data;','wire [1023:0] result_data;')
        prefix=source.once(prefix,"result_data!==512'hdeadbeef","result_data!==1024'hdeadbeef")
        prefix=source.once(prefix,'.clk(clk),.rst(rst),.enable(fetch_enable),',
            ".clk(clk),.rst(rst),.enable(fetch_enable),\n .cfg_receive(1'b0),.admission_available(2'b01),.receive_downstream_guard(8'd0),")
        # Configuration/ownership only: no producer is published. Do not keep
        # the old64-byte DMA backend model in a matched128-byte fixture.
        start=prefix.index('initial begin: backend_model')
        end=prefix.index('task write_reg;',start)
        prefix=prefix[:start]+prefix[end:]
        prefix=source.once(prefix,'if(fetch_fault)$fatal',
            'if(command_valid)$fatal(1,"unexpected DMA in configuration-only MSN fixture");\n if(fetch_fault)$fatal')
        tb=prefix.replace('// ABI',macros).replace('// DECLARATIONS',decl+'\n'+pred).replace('INITIAL_SEQUENCE_VALUE','0')+TASKS+END.replace('// BODY',body)
        if 'force 'in tb:raise ValueError('no internal state/lookup override')
        (run/'tb.v').write_text(tb);item=dict(directory=str(run.relative_to(ROOT)),pass_test=False,runtime_limit_seconds=10)
        self.reports.setdefault(self._testMethodName,[]).append(item)
        try:
            cmd=['iverilog','-g2012','-s','tb','-o',str(ram/'test'),str(run/'tb.v'),str(sq),str(fetch),str(source.PRED),*map(str,legacy.SOURCES[2:])]
            c=subprocess.run(cmd,capture_output=True,text=True,timeout=30);(run/'compile.log').write_text(c.stdout+c.stderr)
            self.assertEqual(c.returncode,0,c.stdout+c.stderr);self.assertFalse(any('expects'in l and 'bits'in l for l in c.stderr.splitlines()),c.stderr)
            start=time.monotonic();r=subprocess.run(['vvp',str(ram/'test')],capture_output=True,text=True,timeout=10)
            item.update(seconds=time.monotonic()-start,exit=r.returncode);(run/'simulation.log').write_text(r.stdout+r.stderr)
            self.assertEqual(r.returncode,0,r.stdout+r.stderr)
            rows=[json.loads(l.split(' ',1)[1])for l in r.stdout.splitlines()if l.startswith('EXPECTED_REMOTE_MSN ')]
            self.assertEqual(len(rows),1);item.update(pass_test=True,summary=rows[0])
        finally:
            item['artifact_sha256']={str(p.relative_to(ROOT)):digest(p)for p in run.iterdir()if p.is_file()}
            item['RAM_artifact_sha256']={str(p):digest(p)for p in ram.iterdir()if p.is_file()}

    def test_real_SQC_epoch_cookie_and_all_logical_operations_no_packet_recount(self):
        self.simulate(r'''
allocate();route();
capture(1,1,1);expectation(1);retire();capture(2,4,2);expectation(2);retire();
capture(3,5,3);expectation(3);retire();capture(5,6,4);expectation(4);retire();
capture(6,7,5);expectation(5);retire();capture(7,8,6);expectation(6);retire();capture(8,9,7);expectation(7);retire();
if(p_message_count!=7 || p_retired_count!=7 || configs!=1)$fatal(1,"logical message vs sequence/packet/Atomic count");
''')

    def test_route_before_real_SQC_allocation_waits_without_invented_binding(self):
        self.simulate(r'''
route();make_owner(2,1);p_s_owner_context=expected;repeat(10)@(negedge clk);
if(p_owner_eligible || p_message_count || p_fault || msn_query_valid)$fatal(1,"route manufactured actual SQC owner");
allocate();capture(2,1,1);expectation(1);retire();
''')

    def test_genuine_SQC_lease_blocks_retirement_and_query_has_no_mailbox_gap(self):
        self.simulate(r'''
allocate();route();capture(2,1,1);p_s_expect_context=expected;p_s_expect_valid=1;
defaults(3,0,64'h8123456789abcdef);stage_words();bell();reply(35,0);ack();
if(owner_active!==128 || fetch_active!==128 || p_fault || p_expect_eligible!==1 || p_message_count!=1)$fatal(1,"held MSN lease/query did not protect real SQC");
p_s_expect_valid=0;retire();
''')

    def test_two_actual_SQCs_interleave_without_route_reconfiguration(self):
        self.simulate(r'''
allocate();route();capture(2,1,1);expectation(1);retire();
defaults(1,0,0);words[2]=6;stage_words();bell();reply(0,7);ack();
wanted_qpn=6;route();capture(1,1,1);expectation(1);retire();
// The latest accepted route stays QP6. Neither QP may need reconfiguration
// to select its existing trusted identity or lose its logical MSN history.
wanted_qpn=7;capture(2,2,2);expectation(2);retire();
wanted_qpn=6;capture(3,2,2);expectation(2);retire();
if(owner_active!==192 || fetch_active!==192 || configs!=2 || p_message_count!=4 || p_retired_count!=4)
 $fatal(1,"two genuine SQ owners/history did not survive interleaving");
''')

    def test_new_actual_SQC_epoch_reinitializes_not_same_route_reapply(self):
        self.simulate(r'''
allocate();route();capture(2,1,1);expectation(1);retire();route();capture(2,2,2);retire();
defaults(3,0,64'h8123456789abcdef);stage_words();bell();reply(0,31);ack();
defaults(1,0,0);words[4]=2;words[6]=32'h89abcdf0;stage_words();bell();reply(0,7);ack();
wanted_epoch=64'h9123456700000002;repeat(5)@(negedge clk);capture(2,1,1);expectation(1);retire();
if(p_message_count!=3 || p_retired_count!=3 || configs!=3)$fatal(1,"real epoch reset/history accounting");
''')

    def test_foreign_expectation_retire_or_old_sequence_quarantines(self):
        for mutation in ['p_s_expect_context=expected^1;p_s_expect_valid=1;',
                         'p_s_retire_context=expected^1;p_s_retire_offer_valid=1;',
                         'p_route_peer_qpn=197;']:
            self.simulate('allocate();route();capture(2,1,1);'+mutation+'quarantine();if(p_message_count!=1 || p_retired_count)$fatal(1,"bad proof altered logical state");')
        self.simulate(r'''
allocate();route();capture(2,1,1);retire();make_owner(2,1);p_s_owner_context=expected;p_s_owner_fire=1;quarantine();
if(p_message_count!=1 || p_retired_count!=1)$fatal(1,"duplicate logical owner counted as replay/new message");
''')

    def test_unknown_owner_route_or_parent_fault_does_not_release(self):
        for change in ["p_route_peer_ip[8]=1'bx;",'p_parent_fault=1;']:
            self.simulate('allocate();route();capture(2,1,1);'+change+'quarantine();if(p_message_count!=1 || p_retired_count)$fatal(1,"fault freed logical owner");')
        self.simulate(r'''
allocate();route();make_owner(2,1);p_s_owner_context=expected;p_s_owner_context[400]=1'bx;p_s_owner_fire=1;quarantine();
if(p_message_count || p_retired_count)$fatal(1,"unknown actual authority counted");
''')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve previous evidence')
    inputs=[*list((ROOT/'rdma/rnic/fpga').glob('*.py')),source.PRED,*legacy.SOURCES,legacy.HEADER,Path(legacy.__file__).resolve(),Path(helper.__file__).resolve(),Path(__file__).resolve()]
    before={str(p.relative_to(ROOT)):digest(p)for p in inputs};start=time.monotonic()
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(ExpectedMSN);methods=suite.countTestCases();r=unittest.TextTestRunner(verbosity=2).run(suite)
    same=all(digest(ROOT/n)==h for n,h in before.items())
    result=dict(scope=__doc__,pass_test=r.wasSuccessful()and same,methods=methods,cases=sum(map(len,ExpectedMSN.reports.values())),source_unchanged=same,
        seconds=time.monotonic()-start,source_sha256=before,tests=ExpectedMSN.reports,
        failures=[dict(test=str(t),trace=s)for t,s in r.failures+r.errors],actual_SQC_mailbox_and_owner_lookup=True,
        route_WR_TX_CQ_modeled=True,fresh_remote_peer_required=True,native_runtime=False,hardware_verified=False,READ_admission_limit=4096)
    with a.report.open('x')as f:f.write(json.dumps(result,indent=2)+'\n')
    raise SystemExit(0 if result['pass_test']else 1)
