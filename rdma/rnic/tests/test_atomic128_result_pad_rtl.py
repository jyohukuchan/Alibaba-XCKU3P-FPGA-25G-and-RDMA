# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual748-bit Atomic/READ result-pad staging; adjacent endpoints modeled.

Check exact8-byte Atomic results and retained ordinary65-byte READ padding.
Not actual generated HLS, native result DMA, CQ or safe unpin proof.
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
import test_wqe_read_unpad_rtl as old
from test_atomic128_response_rtl import owner

ROOT=old.ROOT;sys.path.insert(0,str(ROOT/'rdma/rnic/fpga'))
import derive_atomic128_lifetime as source


class Atomic128ResultPadTests(unittest.TestCase):
    reports={}

    def simulate(self,body):
        rtl=source.leaf('rocev2_wqe_read_unpad')
        tb=old.bench(body).replace('[587:0]','[747:0]')
        tb=source.once(tb,'rocev2_wqe_read_unpad dut(.*);','rocev2_atomic128_wqe_read_unpad dut(.*);')
        inputs=[source.RTL/'rocev2_wqe_read_unpad.v',Path(source.__file__).resolve(),
            Path(source.geometry.__file__).resolve(),Path(source.geometry.base.__file__).resolve(),
            Path(__file__).resolve(),Path(old.__file__).resolve(),ROOT/'rdma/rnic/tests/test_atomic128_response_rtl.py',
            ROOT/'rdma/rnic/tests/test_wqe_hls_sq_rtl.py',ROOT/'rdma/rnic/tests/test_wqe_memory_executor_rtl.py']
        def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
        before={str(p.relative_to(ROOT)):digest(p)for p in inputs}
        with tempfile.TemporaryDirectory(prefix='as02-atomic128-result-pad-')as temp:
            p=Path(temp);(p/'tb.v').write_text(tb);(p/'rocev2_atomic128_wqe_read_unpad.v').write_text(rtl)
            c=subprocess.run(['iverilog','-g2012','-s','tb','-o',str(p/'test.vvp'),str(p/'tb.v'),
                str(p/'rocev2_atomic128_wqe_read_unpad.v')],capture_output=True,text=True,timeout=20)
            self.assertEqual(c.returncode,0,c.stdout+c.stderr)
            r=subprocess.run(['vvp',str(p/'test.vvp')],capture_output=True,text=True,timeout=10)
            if r.returncode:
                diag=Path(tempfile.mkdtemp(prefix='atomic128-result-pad-failure-',dir=ROOT/'rdma/rnic/build'))
                for f in p.iterdir():shutil.copy2(f,diag/f.name)
                (diag/'simulation.log').write_text(r.stdout+r.stderr)
            self.assertEqual(r.returncode,0,r.stdout+r.stderr)
            rows=[json.loads(l.split(' ',1)[1])for l in r.stdout.splitlines()if l.startswith('READ_UNPAD_RESULT ')]
            self.assertEqual(len(rows),1,r.stdout);self.assertTrue(rows[0]['pass_test'])
        self.assertEqual(before,{n:digest(ROOT/n)for n in before})
        self.reports.setdefault(self._testMethodName,[]).append(dict(summary=rows[0],source_sha256=before,
            bench_sha256=hashlib.sha256(tb.encode()).hexdigest(),generated_RTL_sha256=hashlib.sha256(rtl.encode()).hexdigest()))

    def test_CAS_FADD8_byte_result_and_ordinary_READ65_byte_padding(self):
        for op,length in [(7,8),(8,8),(2,65)]:
            self.simulate(f'capture({owner(op)});command({old.raw_command(length=(length+3)&~3)},{old.raw_command(length=length)});payload({length});')

    def test_noncanonical_result_context_never_acquires_staging_authority(self):
        for n in [owner(8,compare=1),owner(2,argument=1),owner(7,length=9),owner(7,immediate=1),owner(8,remote=1)]:
            self.simulate(f'downstream_queue_guard=8\'h80;s_context={n};s_context_valid=1;'+r'''
repeat(7)@(negedge clk);if(!fault || fault_code!=8'ha1 || s_context_ready || m_command_valid || queue_guard!==8'hff)$fatal(1,"invalid Atomic result acquired pad staging");
''')

    def test_fault_does_not_retract_already_offered8byte_command(self):
        self.simulate(f'capture({owner()});s_command={old.raw_command(length=8)};s_command_valid=1;'+r'''
@(posedge clk);@(negedge clk);s_command_valid=0;downstream_queue_guard=0;enable=0;repeat(7)@(negedge clk);
if(!fault || fault_code!=8'ha4 || !m_command_valid || queue_guard!==8'hff)$fatal(1,"late guard fault retracted result command");
m_command_ready=1;@(posedge clk);@(negedge clk);m_command_ready=0;
if(!busy || command_count!=1 || queue_guard!==8'hff)$fatal(1,"fault invented result staging drain");
''')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve prior evidence')
    start=time.monotonic();r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Atomic128ResultPadTests))
    report=dict(scope=__doc__,pass_test=r.wasSuccessful(),methods=r.testsRun,simulations=sum(map(len,Atomic128ResultPadTests.reports.values())),
        seconds=time.monotonic()-start,tests=Atomic128ResultPadTests.reports,actual_native_result_DMA_WR_CQ=False,hardware_verified=False)
    with a.report.open('x')as f:f.write(json.dumps(report,indent=2)+'\n')
    raise SystemExit(not r.wasSuccessful())
