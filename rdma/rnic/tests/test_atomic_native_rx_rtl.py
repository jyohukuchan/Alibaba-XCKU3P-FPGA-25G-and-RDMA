# SPDX-License-Identifier: BSD-2-Clause-Views
"""Four-state native accepted-RX references/classifier; adjacent endpoints modeled.

These tests do NOT prove a complete native Atomic operation or host unpin.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest
import probe_atomic_responder as helper

ROOT=helper.ROOT;RTL=ROOT/'rdma/rnic/rtl'
CONTEXT=(0xb8830367c5d0<<304)|(0x8af3fbb97531<<256)|(0xc6120b01<<224)|(0xc6120b02<<192)|\
    (196<<168)|(0xfedcba9889abcdef<<104)|(0x9123456700000001<<40)|(17<<24)|2

COMMON=r'''
`timescale 1ns/1ps
module tb;
// DECLARATIONS
always #2 clk=~clk;
integer cycles=0;
always @(posedge clk)if(!rst)begin cycles=cycles+1;if(cycles>66000)$fatal(1,"bounded deadline");end
initial begin
 rst=1;repeat(4)@(negedge clk);rst=0;
 // BODY
 $display("NATIVE_RX_UNIT {\"pass_test\":true,\"cycles\":%0d}",cycles);$finish;
end
endmodule
'''


def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()


class NativeRXTests(unittest.TestCase):
    reports={}

    def simulate(self,module,body):
        rtl=RTL/(module+'.v');before=digest(rtl)
        tb=COMMON.replace('// DECLARATIONS',helper.instance(rtl,'dut','',{})).replace('// BODY',body)
        with tempfile.TemporaryDirectory(prefix='as02-atomic-native-rx-')as temp:
            p=Path(temp);(p/'tb.v').write_text(tb)
            c=subprocess.run(['iverilog','-g2012','-s','tb','-o',str(p/'test.vvp'),str(p/'tb.v'),str(rtl)],
                capture_output=True,text=True,timeout=20)
            self.assertEqual(c.returncode,0,c.stdout+c.stderr)
            started=time.monotonic()
            r=subprocess.run(['vvp',str(p/'test.vvp')],capture_output=True,text=True,timeout=10)
            if r.returncode:
                diag=Path(tempfile.mkdtemp(prefix='atomic-native-rx-failure-',dir=ROOT/'rdma/rnic/build'))
                for name in ['tb.v','test.vvp']:shutil.copy2(p/name,diag/name)
                (diag/'simulation.log').write_text(r.stdout+r.stderr)
                print('Preserved failed RX fixture/binary/log: '+str(diag),flush=True)
            self.assertEqual(r.returncode,0,r.stdout+r.stderr)
            rows=[json.loads(line.split(' ',1)[1])for line in r.stdout.splitlines()if line.startswith('NATIVE_RX_UNIT ')]
            self.assertEqual(len(rows),1,r.stdout);self.assertTrue(rows[0]['pass_test'])
            self.reports.setdefault(self._testMethodName,[]).append(dict(summary=rows[0],seconds=time.monotonic()-started,
                RTL=str(rtl.relative_to(ROOT)),RTL_sha256=before,bench_sha256=hashlib.sha256(tb.encode()).hexdigest()))
        self.assertEqual(before,digest(rtl))

    def refs(self,body):
        self.simulate('rocev2_native_rx_refs',
            f"enable=1;trusted_valid=1;trusted_context=352'h{CONTEXT:088x};s_keep=16'hffff;\n"+body)

    def test_offered_reference_drains_under_pause_and_context_query_unavailable(self):
        self.refs(r'''
s_data=128'h0123456789abcdef;s_valid=1;#1;
if(!m_valid || !configuration_guard || queue_guard!==4 || s_ready)$fatal(1,"first offer unguarded");
@(negedge clk);enable=0;trusted_valid=0;trusted_context=0;
repeat(7)begin @(negedge clk);if(!m_valid || held_context[23:0]!==2 || references || fault)$fatal(1,"offer retracted");end
m_ready=1;@(negedge clk);
if(references!==1 || !configuration_guard || m_data!==128'h0123456789abcdef)$fatal(1,"accepted first frame");
s_last=1;s_data=128'hfedcba9876543210;@(negedge clk);s_valid=0;s_last=0;
if(references!==1 || !configuration_guard || fault)$fatal(1,"EOF incorrectly freed checker reference");
checked_eof=1;@(negedge clk);checked_eof=0;#1;
if(references || configuration_guard || queue_guard || fault)$fatal(1,"actual checked EOF failed release");
''')

    def test_simultaneous_acquire_and_two_actual_checker_outcomes(self):
        self.refs(r'''
m_ready=1;s_valid=1;s_last=1;
repeat(2)@(negedge clk);
if(references!==2)$fatal(1,"two buffered frames not retained");
checked_eof=1;checker_drop=1;@(negedge clk);s_valid=0;checked_eof=0;checker_drop=0;
if(references!==1 || fault || !configuration_guard)$fatal(1,"acquire1 release2 accounting");
checked_eof=1;@(negedge clk);checked_eof=0;#1;
if(references || fault || configuration_guard)$fatal(1,"remaining real checker outcome");
''')

    def test_new_context_only_after_actual_last_reference_release(self):
        self.refs(r'''
m_ready=1;s_valid=1;s_last=1;@(negedge clk);s_valid=0;
trusted_valid=0;trusted_context[23:0]=3;repeat(4)@(negedge clk);
if(held_context[23:0]!==2 || references!==1 || fault || queue_guard!==4)$fatal(1,"held trusted route replaced");
checked_eof=1;@(negedge clk);checked_eof=0;trusted_valid=1;s_valid=1;#1;
if(!m_valid || queue_guard!==8)$fatal(1,"new route was not independently admitted");
@(negedge clk);s_valid=0;#1;
if(held_context[23:0]!==3 || references!==1 || queue_guard!==8 || fault)$fatal(1,"new trusted snapshot");
''')

    def test_invalid_unknown_alias_or_changed_context_fails_closed(self):
        for mutation in ["trusted_context[39:24]=0;","trusted_context[23:0]=24'h100002;",
            "trusted_context[103:40]=64'hx;","trusted_context[167:104]=0;"]:
            with self.subTest(mutation=mutation):self.refs(mutation+r'''
s_valid=1;m_ready=1;@(negedge clk);#1;
if(m_valid || s_ready || references || !fault || !configuration_guard || queue_guard!==255)$fatal(1,"bad route acquired authority");
''')
        self.refs(r'''
m_ready=1;s_last=1;s_valid=1;@(negedge clk);s_valid=0;
trusted_context[23:0]=3;s_valid=1;@(negedge clk);#1;
if(!fault || m_valid || s_ready || references!==1 || held_context[23:0]!==2 || queue_guard!==255)
 $fatal(1,"in-flight context was replaced");
''')

    def test_reference_underflow_unknown_outcomes_and_parent_fault_retain_guard(self):
        for event in ["checked_eof=1;","checker_drop=1;","checker_drop=1'bx;","parent_fault=1;"]:
            with self.subTest(event=event):self.refs(event+r'''
@(negedge clk);#1;
if(!fault || references || !configuration_guard || queue_guard!==255)$fatal(1,"invalid outcome released guard");
''')

    def test_reference_count_never_wraps_at_finite_capacity(self):
        self.refs(r'''
m_ready=1;s_last=1;s_valid=1;repeat(65535)@(negedge clk);
if(references!==65535 || fault)$fatal(1,"finite reference capacity");
@(negedge clk);s_valid=0;#1;
if(references!==65535 || !fault || !configuration_guard || queue_guard!==255)$fatal(1,"reference counter wrapped/released");
''')

    def router(self,body):self.simulate('rocev2_native_atomic_rx_router',body)

    @staticmethod
    def headers(op):
        return "s_data=128'h0123456789abcdef0123456789abcd45;s_keep=16'hffff;s_valid=1;@(negedge clk);\n"+\
            f"s_data=128'hfedcba{op:02x}76543210fedcba9876543210;@(negedge clk);\n"

    def test_complete_header_and_body_route_without_byte_changes_under_backpressure(self):
        for op in [0x13,0x14,0x0a,0x0c,0x0d,0x12,0x17]:
            atomic=op in (0x13,0x14);prefix='m_atomic_'if atomic else'm_normal_'
            other='m_normal_'if atomic else'm_atomic_'
            body=self.headers(op)+f'''
s_data=128'hffeeddccbbaa99887766554433221100;s_keep=16'h1fff;s_last=1;
repeat(5)begin @(negedge clk);
 if(!{prefix}valid || {other}valid || {prefix}data!==128'h0123456789abcdef0123456789abcd45 ||
   {prefix}keep!==16'hffff || {prefix}last || s_ready || !configuration_guard || fault)$fatal(1,"held first header");
end
{prefix}ready=1;@(negedge clk);
if(!{prefix}valid || {prefix}data!==128'hfedcba{op:02x}76543210fedcba9876543210 || {prefix}last)$fatal(1,"second header");
@(negedge clk);
if(!s_ready || !{prefix}valid || {prefix}data!==s_data || {prefix}keep!==16'h1fff || !{prefix}last)$fatal(1,"unchanged final body");
@(negedge clk);s_valid=0;#1;
if(fault || configuration_guard || m_normal_valid || m_atomic_valid)$fatal(1,"frame not fully routed");
'''
            with self.subTest(opcode=op):self.router(body)

    def test_short_unknown_or_malformed_header_does_not_offer_output(self):
        for first in [True,False]:
            for mutation in ["s_keep=16'hfffe;","s_keep=16'hxfff;","s_last=1;"]:
                prefix=""if first else "s_data=128'h45;s_keep=16'hffff;s_valid=1;@(negedge clk);\n"
                with self.subTest(first=first,mutation=mutation):self.router(prefix+"s_data=128'h45;s_keep=16'hffff;s_valid=1;"+mutation+r'''
@(negedge clk);#1;
if(!fault || !configuration_guard || m_atomic_valid || m_normal_valid || s_ready)$fatal(1,"malformed header exposed");
''')

    def test_late_fault_does_not_retract_already_offered_buffered_packet(self):
        self.router(self.headers(0x14)+r'''
s_data=128'h123456789abcdef;s_keep=16'h000f;s_last=1;s_valid=1'bx;@(negedge clk);s_valid=1;
repeat(5)begin @(negedge clk);
 if(!fault || !m_atomic_valid || m_atomic_data!==128'h0123456789abcdef0123456789abcd45 || !configuration_guard)
  $fatal(1,"late fault retracted first output");
end
m_atomic_ready=1;repeat(3)@(negedge clk);s_valid=0;#1;
if(!fault || !configuration_guard || m_atomic_valid || m_normal_valid || s_ready)$fatal(1,"faulted classifier released guard");
''')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--report',type=Path,required=True);args=parser.parse_args()
    if args.report.exists():parser.error('preserve prior evidence')
    sources=[Path(__file__).resolve(),Path(helper.__file__).resolve(),RTL/'rocev2_native_rx_refs.v',RTL/'rocev2_native_atomic_rx_router.v']
    before={str(p.relative_to(ROOT)):digest(p)for p in sources};started=time.monotonic()
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(NativeRXTests)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    report=dict(scope=__doc__,pass_test=result.wasSuccessful(),seconds=time.monotonic()-started,
        methods=result.testsRun,internal_simulations=sum(map(len,NativeRXTests.reports.values())),
        tests=NativeRXTests.reports,source_sha256=before,four_state_simulation=True,
        endpoint_models=True,full_native_runtime=False,hardware_verified=False)
    if before!={str(p.relative_to(ROOT)):digest(p)for p in sources}:raise ValueError('source changed')
    with args.report.open('x')as f:f.write(json.dumps(report,indent=2)+'\n')
    raise SystemExit(not result.wasSuccessful())
