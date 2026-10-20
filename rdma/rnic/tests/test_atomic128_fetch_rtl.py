# SPDX-License-Identifier: BSD-2-Clause-Views
"""Four-state128-byte SQ controller, DMA/status/config endpoints modeled.

Real controller/guards/tables; no WQE authorization/native/API/unpin proof.
Actual PCIe/RAM tests are separate probe_atomic128_sq_dma evidence.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
import probe_atomic_responder as helper
import test_sq_fetch_rtl as prior

ROOT=prior.ROOT;sys.path.insert(0,str(ROOT/'rdma/rnic/fpga'))
import derive_atomic128_fetch as source

TB=r'''
`timescale 1ns/1ps
module tb;
localparam MAX_QPS=8;
// DECLARATIONS
always #2 clk=~clk;
integer cycle=0,deadline;
always @(posedge clk)if(!rst)begin cycle=cycle+1;if(cycle>3000)$fatal(1,"bounded deadline");end
// CONFIGURE
task command;
 input [63:0] address;input [15:0] tag;
 begin
  deadline=cycle+100;while(!m_command_valid)begin if(cycle>deadline)$fatal(1,"descriptor deadline");@(negedge clk);end
  repeat(5)begin @(negedge clk);
   if(m_command_address!==address || m_command_length!==128 || m_command_tag!==tag || !m_command_valid)
    $fatal(1,"full128-byte address/length/tag offer");
  end
  m_command_ready=1;@(negedge clk);m_command_ready=0;
 end
endtask
task beat;
 input [511:0] data;input [63:0] keep;input last;
 begin
  @(negedge clk);s_axis_read_tdata=data;s_axis_read_tkeep=keep;s_axis_read_tlast=last;s_axis_read_tvalid=1;
  @(posedge clk);while(!s_axis_read_tready)@(posedge clk);
  @(negedge clk);s_axis_read_tvalid=0;
 end
endtask
task status;
 input [15:0] tag;input [7:0] error;
 begin
  @(negedge clk);s_status_tag=tag;s_status_error=error;s_status_valid=1;
  @(posedge clk);while(!s_status_ready)@(posedge clk);@(negedge clk);s_status_valid=0;
 end
endtask
task result;
 input [1023:0] bytes;input [7:0] error;input [23:0] q;input [15:0] pd;
 input [63:0] epoch,sequence_value;input [15:0] tag;input receive_value;
 begin
  deadline=cycle+100;while(!m_result_valid)begin if(cycle>deadline)$fatal(1,"result deadline");@(negedge clk);end
  repeat(9)begin @(negedge clk);
   if(!m_result_valid || m_result_data!==(error ? 1024'd0:bytes) || m_result_error!==error ||
     m_result_qpn!==q || m_result_pd!==pd || m_result_epoch!==epoch || m_result_sequence!==sequence_value ||
     m_result_tag!==tag || m_result_receive!==receive_value || fault || !busy ||
     (receive_value ? !receive_queue_guard[q]:!queue_guard[q]))
    $fatal(1,"128-byte record or trusted held context changed");
  end
  m_result_ready=1;@(negedge clk);m_result_ready=0;
 end
endtask
task record;
 input [63:0] address;input [23:0] q;input [15:0] pd;input [63:0] epoch,sequence_value;
 input [15:0] tag;input receive_value;input [1023:0] bytes;
 begin
  command(address,tag);beat(bytes[511:0],64'hffffffffffffffff,0);
  repeat(5)begin @(negedge clk);if(m_result_valid)$fatal(1,"partial record became authorized output");end
  beat(bytes[1023:512],64'hffffffffffffffff,1);
  repeat(5)begin @(negedge clk);if(m_result_valid)$fatal(1,"record returned without actual status");end
  status(tag,0);result(bytes,0,q,pd,epoch,sequence_value,tag,receive_value);
 end
endtask
initial begin
 rst=1;parent_dma_drained=1;repeat(4)@(negedge clk);rst=0;
 // BODY
 $display("ATOMIC128_FETCH_UNIT {\"pass_test\":true,\"cycles\":%0d}",cycle);$finish;
end
endmodule
'''


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


class Atomic128FetchTests(unittest.TestCase):
    reports={}

    def simulate(self,body,initial_tag=0,separate=False):
        text=source.derive()[source.FETCH]
        with tempfile.TemporaryDirectory(prefix='as02-atomic128-fetch-')as temp:
            p=Path(temp);rtl=p/'rocev2_atomic128_sq_fetch.v';rtl.write_text(text)
            declaration=helper.instance(rtl,'dut','',{})
            declaration=source.once(declaration,'rocev2_atomic128_sq_fetch dut(',
                f'rocev2_atomic128_sq_fetch #(.INITIAL_TAG({initial_tag}),.SEPARATE_RQ_ENABLE({int(separate)}),.RECV_CANCEL_ENABLE({int(separate)})) dut(')
            configure=prior.TB[prior.TB.index('task configure;'):prior.TB.index('task wait_command;')]
            tb=TB.replace('// DECLARATIONS',declaration).replace('// CONFIGURE',configure).replace('// BODY',body)
            (p/'tb.v').write_text(tb)
            c=subprocess.run(['iverilog','-g2012','-s','tb','-o',str(p/'test.vvp'),str(p/'tb.v'),str(rtl)],capture_output=True,text=True,timeout=20)
            if c.returncode:
                diag=Path(tempfile.mkdtemp(prefix='atomic128-fetch-compile-failure-',dir=ROOT/'rdma/rnic/build'))
                for name in ['tb.v',rtl.name]:shutil.copy2(p/name,diag/name)
                (diag/'compile.log').write_text(c.stdout+c.stderr);print('Preserved '+str(diag),flush=True)
            self.assertEqual(c.returncode,0,c.stdout+c.stderr)
            r=subprocess.run(['vvp',str(p/'test.vvp')],capture_output=True,text=True,timeout=10)
            if r.returncode:
                diag=Path(tempfile.mkdtemp(prefix='atomic128-fetch-failure-',dir=ROOT/'rdma/rnic/build'))
                for name in ['tb.v','test.vvp',rtl.name]:shutil.copy2(p/name,diag/name)
                (diag/'simulation.log').write_text(r.stdout+r.stderr);print('Preserved '+str(diag),flush=True)
            self.assertEqual(r.returncode,0,r.stdout+r.stderr)
            rows=[json.loads(line.split(' ',1)[1])for line in r.stdout.splitlines()if line.startswith('ATOMIC128_FETCH_UNIT ')]
            self.assertEqual(len(rows),1);self.assertTrue(rows[0]['pass_test'])
            self.reports.setdefault(self._testMethodName,[]).append(dict(summary=rows[0],
                generated_RTL_sha256=hashlib.sha256(text.encode()).hexdigest(),bench_sha256=hashlib.sha256(tb.encode()).hexdigest()))

    def test_early_status_does_not_release_partial_record_or_trusted_owner(self):
        self.simulate(r'''
configure(1,2,17,64'h9123456700000001,64'h8123456789abc000,0,1,0);
configure(2,2,0,64'h9123456700000001,0,1,0,0);enable=1;
command(64'h8123456789abc000,1);enable=0;status(1,0);
beat(512'h1122,64'hffffffffffffffff,0);
repeat(10)begin @(negedge clk);if(m_result_valid || !queue_guard[2] || !busy)$fatal(1,"half record lost queue owner");end
configure(3,2,0,64'h9123456700000001,0,0,0,19);
beat(512'h99aa,64'hffffffffffffffff,1);result({512'h99aa,512'h1122},0,2,17,64'h9123456700000001,1,1,0);
configure(3,2,0,64'h9123456700000001,0,0,0,0);
if(queue_active || busy || fault)$fatal(1,"complete128-byte owner did not retire");
''')

    def test_bad_half_framing_keep_and_unknown_never_produce_result(self):
        for first,keep,last in [(True,"64'hffffffffffffffff",1),(True,"64'hfffffffffffffffe",0),
            (False,"64'hffffffffffffffff",0),(False,"64'hffffffffffffxFFF",1)]:
            body=r'''
configure(1,1,17,1,64'h1000,0,1,0);configure(2,1,0,1,0,1,0,0);enable=1;command(64'h1000,1);
'''
            if not first:body+="beat(512'h1234,64'hffffffffffffffff,0);\n"
            body+=f"beat(512'h5678,{keep},{last});"+r'''
repeat(7)@(negedge clk);
if(!fault || fault_code!==64 || m_result_valid || !queue_guard[1] || !busy || s_axis_read_tready)
 $fatal(1,"malformed128-byte record escaped quarantine");
'''
            with self.subTest(first=first,keep=keep,last=last):self.simulate(body)

    def test_full_record_DMA_error_zeroes_both_halves_and_halts_queue(self):
        self.simulate(r'''
configure(1,0,17,1,64'h1000,0,1,0);configure(2,0,0,1,0,2,0,0);enable=1;command(64'h1000,1);
beat({512{1'b1}},64'hffffffffffffffff,0);beat({512{1'b1}},64'hffffffffffffffff,1);
status(1,10);result(0,10,0,17,1,1,1,0);repeat(10)@(negedge clk);
if(m_command_valid || queue_halted!==1 || !queue_pending[0] || fault)$fatal(1,"bad DMA did not halt only owned queue");
configure(3,0,0,1,0,0,0,0);configure(1,0,17,1,64'h1000,0,1,17);
configure(1,0,17,2,64'h1000,0,1,0);
''')

    def test_full_DMA64_ring_range_128_alignment_and_highest_exact_end(self):
        self.simulate(r'''
configure(1,24'h100002,17,1,64'h1000,0,1,16);
configure(1,0,17,1,64'h1040,0,1,18);
configure(1,0,17,1,64'hffffffffffffff80,0,1,18);
configure(1,0,17,1,64'hffffffffffffff00,0,1,0);
configure(2,0,0,1,0,2,0,0);enable=1;
record(64'hffffffffffffff00,0,17,1,1,1,0,{512'hf123,512'h1234});
record(64'hffffffffffffff80,0,17,1,2,2,0,{512'hfedc,512'h5678});
enable=0;repeat(5)@(negedge clk);if(busy || fault || queue_pending)$fatal(1,"top DMA64 range");
''')

    def test_nonwrapping_finite_DMA_tags(self):
        self.simulate(r'''
configure(1,0,17,1,64'h1000,0,1,0);configure(2,0,0,1,0,2,0,0);enable=1;
record(64'h1000,0,17,1,1,16'hffff,0,{512'h1234,512'h5678});
repeat(20)@(negedge clk);if(!tag_exhausted || m_command_valid || !queue_pending[0] || fault)$fatal(1,"DMA tag wrapped/reused");
''',initial_tag=65534)

    def test_same_QPN_separate_SQ_RQ_context_banks(self):
        self.simulate(r'''
admission_available=3;cfg_receive=0;configure(1,2,17,1,64'h1000,0,1,0);
configure(2,2,0,1,0,1,0,0);cfg_receive=1;configure(1,2,31,2,64'h3000,0,1,0);
configure(2,2,0,2,0,1,0,0);enable=1;
record(64'h1000,2,17,1,1,1,0,{512'h1234,512'h5678});
record(64'h3000,2,31,2,1,2,1,{512'habcd,512'h9876});
enable=0;repeat(5)@(negedge clk);
if(queue_pending || receive_queue_pending || busy || fault)$fatal(1,"same QPN SQ/RQ owners aliased");
''',separate=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve previous evidence')
    files=[Path(__file__).resolve(),Path(source.__file__).resolve(),source.FETCH,source.DMA,
        Path(helper.__file__).resolve(),Path(prior.__file__).resolve()]
    before={str(path.relative_to(ROOT)):digest(path)for path in files};started=time.monotonic()
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Atomic128FetchTests))
    if before!={str(path.relative_to(ROOT)):digest(path)for path in files}:raise ValueError('source changed')
    report=dict(scope=__doc__,pass_test=result.wasSuccessful(),source_sha256=before,methods=result.testsRun,
        internal_simulations=sum(map(len,Atomic128FetchTests.reports.values())),seconds=time.monotonic()-started,
        tests=Atomic128FetchTests.reports,four_state=True,native_requester_integrated=False,hardware_verified=False)
    with a.report.open('x')as f:f.write(json.dumps(report,indent=2)+'\n')
    raise SystemExit(not result.wasSuccessful())
