# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual protected Atomic result memory executor; MR/HLS/backend/CQ models.

Check exact full748-bit owner and result token, post-origin-router96-bit
command,8-byte write, actual data handshakes and tagged status/owner transfer.
This component is NOT actual paged PCIe DMA, memory visibility or native CQ.
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
import test_wqe_memory_executor_rtl as old
from test_atomic128_response_rtl import owner

ROOT=old.ROOT;sys.path.insert(0,str(ROOT/'rdma/rnic/fpga'))
import derive_atomic128_executor as source


def raw(length=8):
    return old.raw_command(length=length)


class Atomic128ExecutorTests(unittest.TestCase):
    reports={}

    def simulate(self,body,length=8):
        tb=old.TB.replace('// DECLARATIONS',old.declarations()).replace('// BODY',body)
        tb=source.once(tb,'localparam MAX_QPS=8;',f'localparam MAX_QPS=8,TEST_LENGTH={length};')
        tb=source.once(tb,'rocev2_wqe_memory_executor dut(.*);','rocev2_atomic128_wqe_memory_executor dut(.*);')
        tb=tb.replace('[587:0]','[747:0]').replace('[595:0]','[755:0]')
        for a,b in [('m_memory_command_length!=65','m_memory_command_length!=TEST_LENGTH'),('pos<65','pos<TEST_LENGTH'),
                    ('n=65-pos','n=TEST_LENGTH-pos'),('pos+64>=65','pos+64>=TEST_LENGTH')]:
            if a not in tb:raise ValueError('old data fixture changed '+a)
            tb=tb.replace(a,b)
        rtl=source.derive()
        files=[source.SOURCE,Path(source.__file__).resolve(),Path(source.geometry.__file__).resolve(),
            Path(source.geometry.base.__file__).resolve(),Path(__file__).resolve(),Path(old.__file__).resolve(),
            ROOT/'rdma/rnic/tests/test_atomic128_response_rtl.py',ROOT/'rdma/rnic/tests/test_wqe_hls_sq_rtl.py']
        def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
        before={str(p.relative_to(ROOT)):digest(p)for p in files}
        with tempfile.TemporaryDirectory(prefix='as02-atomic128-executor-')as temp:
            p=Path(temp);(p/'tb.v').write_text(tb);(p/'rocev2_atomic128_wqe_memory_executor.v').write_text(rtl)
            c=subprocess.run(['iverilog','-g2012','-s','tb','-o',str(p/'test.vvp'),str(p/'tb.v'),
                str(p/'rocev2_atomic128_wqe_memory_executor.v')],capture_output=True,text=True,timeout=20)
            if c.returncode:
                diag=Path(tempfile.mkdtemp(prefix='atomic128-executor-compile-failure-',dir=ROOT/'rdma/rnic/build'))
                for f in p.iterdir():shutil.copy2(f,diag/f.name)
                (diag/'compile.log').write_text(c.stdout+c.stderr)
            self.assertEqual(c.returncode,0,c.stdout+c.stderr)
            r=subprocess.run(['vvp',str(p/'test.vvp')],capture_output=True,text=True,timeout=10)
            if r.returncode:
                diag=Path(tempfile.mkdtemp(prefix='atomic128-executor-runtime-failure-',dir=ROOT/'rdma/rnic/build'))
                for f in p.iterdir():shutil.copy2(f,diag/f.name)
                (diag/'simulation.log').write_text(r.stdout+r.stderr)
            self.assertEqual(r.returncode,0,r.stdout+r.stderr)
            rows=[json.loads(l.split(' ',1)[1])for l in r.stdout.splitlines()if l.startswith('WQE_MEMORY_RESULT ')]
            self.assertEqual(len(rows),1,r.stdout);self.assertTrue(rows[0]['pass_test'])
        self.assertEqual(before,{n:digest(ROOT/n)for n in before})
        self.reports.setdefault(self._testMethodName,[]).append(dict(summary=rows[0],source_sha256=before,
            bench_sha256=hashlib.sha256(tb.encode()).hexdigest(),generated_RTL_sha256=hashlib.sha256(rtl.encode()).hexdigest()))

    def test_CAS_FADD_real8byte_result_write_exact_saved_key_offset_and_status(self):
        for op in [7,8]:
            self.simulate(f'owner({owner(op)});response();raw(1,{raw()});data(1);status(0);handoff();')

    def test_normal_WRITE_READ_SEND_Immediate_same_executor(self):
        for op in [1,2,3,5,6]:
            n=owner(op,immediate=0x89abcdef if op in [5,6]else 0)
            self.simulate(f'owner({n});'+('response();'if op==2 else'')+
                f'raw({int(op==2)},{raw(65)});data({int(op==2)});status(0);handoff();',length=65)

    def test_atomic_raw_command_waits_for_protected_matching_result_token(self):
        self.simulate(f'owner({owner()});s_hls_write_command={raw()};s_hls_write_command_valid=1;'+r'''
repeat(19)begin @(negedge clk);if(s_hls_write_command_ready || m_memory_command_valid || fault || !busy || queue_guard!==8'h80)$fatal(1,"raw HLS AtomicACK authorized memory");
end
response();@(posedge clk);if(!s_hls_write_command_ready)$fatal(1,"trusted Atomic result permit not consumed");
@(negedge clk);s_hls_write_command_valid=0;if(!m_memory_command_valid || fault)$fatal(1,"result authority not retained");
''')

    def test_exact96bit_command_and_full748bit_response_context_required(self):
        original=int(raw().split("'h",1)[1],16)
        for bit in [0,47,48,75,76,77,78,79,80,83,84,93,94,95]:
            self.simulate(f'owner({owner()});response();s_hls_write_command=96\'h{original^(1<<bit):024x};s_hls_write_command_valid=1;'+r'''
repeat(7)@(negedge clk);if(!fault || fault_code!=8'h82 || m_memory_command_valid || s_hls_write_command_ready || queue_guard!==8'hff)$fatal(1,"bad raw result command acquired backend");
''')
        original=int(owner().split("'h",1)[1],16)
        for bit in [20,52,116,180,244,276,324,340,356,372,396,460,524,588,620,683,684,747]:
            self.simulate(f'owner({owner()});s_read_response_context=748\'h{original^(1<<bit):0187x};s_read_response_valid=1;'+r'''
repeat(7)@(negedge clk);if(!fault || fault_code!=8'h83 || s_read_response_ready || m_memory_command_valid || queue_guard!==8'hff)$fatal(1,"changed Atomic context acquired backend");
''')

    def test_denied_DMA_and_MR_records_never_create_memory_authority(self):
        for error,source_kind,fetch,available in [(1,1,1,0),(15,1,15,0),(32,2,0,1)]:
            n=owner(0,flags=0,length=0,lkey=0,address=0,offset=0,remote=0,rkey=0,error=error,source=source_kind,
                fetch=fetch,available=available,authorized=0)
            self.simulate(f'owner({n});if(!m_memory_event_valid || m_memory_event_error!={error} || m_memory_command_valid || command_count)$fatal(1,"denied Atomic fetch gained memory");handoff();')

    def test_noncanonical_atomic_owners_refused_before_any_memory_offer(self):
        for n in [owner(8,compare=1),owner(1,argument=1),owner(immediate=1),owner(length=9),
                  owner(remote=0xe23456789abcd009),owner(address=(1<<64)-7),owner(epoch=0),"{64'hx,684'd0}"]:
            self.simulate(f's_owner_context={n};s_owner_valid=1;'+r'''
repeat(7)@(negedge clk);if(!fault || fault_code!=8'h81 || s_owner_ready || m_memory_command_valid || owner_count || queue_guard!==8'hff)$fatal(1,"invalid Atomic owner acquired memory");
''')

    def test_backend_error_and_missing_downstream_lease_never_release_owner(self):
        self.simulate(f'owner({owner()});response();raw(1,{raw()});status(8\'ha5);'+r'''
downstream_queue_guard=8'h80;m_memory_event_ready=1;@(posedge clk);@(negedge clk);m_memory_event_ready=0;
if(!fault || fault_code!=8'h89 || !busy || queue_guard!==8'hff || m_memory_event_valid)$fatal(1,"Atomic backend failure released lifetime");
''')
        self.simulate(f'owner({owner()});response();raw(1,{raw()});data(1);status(0);'+r'''
m_memory_event_ready=1;repeat(7)@(negedge clk);
if(!fault || fault_code!=8'h87 || !m_memory_event_valid || !busy || queue_guard!==8'hff)$fatal(1,"ready alone released Atomic owner");
''')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve prior evidence')
    start=time.monotonic();result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Atomic128ExecutorTests))
    report=dict(scope=__doc__,pass_test=result.wasSuccessful(),methods=result.testsRun,simulations=sum(map(len,Atomic128ExecutorTests.reports.values())),
        seconds=time.monotonic()-start,tests=Atomic128ExecutorTests.reports,actual_native_result_DMA_WR_CQ=False,hardware_verified=False)
    with a.report.open('x')as f:f.write(json.dumps(report,indent=2)+'\n')
    raise SystemExit(not result.wasSuccessful())
