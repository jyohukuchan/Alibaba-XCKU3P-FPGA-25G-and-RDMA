# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual748-bit owner/408-bit SQ staging; executor/HLS endpoints modeled.

No HLS Atomic operation, response placement, CQ or standard API claim.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
import test_wqe_hls_sq_rtl as old

ROOT=old.ROOT;sys.path.insert(0,str(ROOT/'rdma/rnic/fpga'))
import derive_atomic128_admission as source


def context(op=7,compare=0xfedcba9876543210,operand=0x8123456789abcdef,immediate=0,**fields):
    values=dict(opcode=op,length=8 if op in [7,8]else 65)
    values.update(fields)
    n=int(old.context(**values).split("'h")[1],16)|(immediate<<588)|(compare<<620)|(operand<<684)
    return f"748'h{n:0187x}"


def expected(op=7,compare=0xfedcba9876543210,operand=0x8123456789abcdef,immediate=0,**fields):
    v=dict(qpn=7,length=8 if op in [7,8]else 65,address=0xfedcba9876543210,remote=0xe23456789abcdef0,rkey=0)
    v.update(fields)
    n=(operand<<344)|(compare<<280)|(immediate<<241)|(1<<240)|(v['rkey']<<208)|(v['length']<<176)|\
        (v['remote']<<112)|(v['address']<<48)|(1<<43)|(1<<42)|(v['qpn']<<32)|{1:10,2:12,3:4,5:5,6:11,7:19,8:20}[op]
    return f"408'h{n:0102x}"


class Atomic128HLSSQTests(unittest.TestCase):
    reports={}

    def simulate(self,body):
        text=source.derive()[source.HLS];header=text.split(')(\n',1)[1].split('\n);',1)[0]
        ports=re.findall(r'^\s*(input|output)\s+(?:wire|reg)\s+(\[[^]]+\]\s+)?(\w+)(?:=0)?\s*,?$',header,re.M)
        self.assertEqual(len(ports),21)
        declarations='\n'.join(('reg 'if d=='input'else'wire ')+(w or '')+n+('=0;'if d=='input'else';')for d,w,n in ports)
        tb=old.TB.replace('// DECLARATIONS',declarations).replace('// BODY',body)
        tb=tb.replace('IMMEDIATE_ENABLE=0','IMMEDIATE_ENABLE=1').replace('[587:0]','[747:0]').replace('[247:0]','[407:0]')
        tb=source.once(tb,'rocev2_wqe_hls_sq dut','rocev2_atomic128_wqe_hls_sq #(.IMMEDIATE_ENABLE(1)) dut')
        with tempfile.TemporaryDirectory(prefix='as02-atomic128-hls-sq-')as temp:
            run=Path(temp);rtl=run/'rocev2_atomic128_wqe_hls_sq.v';rtl.write_text(text);(run/'tb.v').write_text(tb)
            c=subprocess.run(['iverilog','-g2012','-s','tb','-o',str(run/'test.vvp'),str(run/'tb.v'),str(rtl)],capture_output=True,text=True,timeout=20)
            r=None
            if not c.returncode:r=subprocess.run(['vvp',str(run/'test.vvp')],capture_output=True,text=True,timeout=10)
            if c.returncode or r.returncode:
                diag=Path(tempfile.mkdtemp(prefix='atomic128-hls-sq-failure-',dir=ROOT/'rdma/rnic/build'))
                for path in run.iterdir():shutil.copy2(path,diag/path.name)
                (diag/'compile.log').write_text(c.stdout+c.stderr)
                if r:(diag/'simulation.log').write_text(r.stdout+r.stderr)
                print('Preserved '+str(diag),flush=True)
            self.assertEqual(c.returncode,0,c.stdout+c.stderr);self.assertEqual(r.returncode,0,r.stdout+r.stderr)
            rows=[json.loads(line.split(' ',1)[1])for line in r.stdout.splitlines()if line.startswith('WQE_HLS_SQ_RESULT ')]
            self.assertEqual(len(rows),1,r.stdout);self.assertTrue(rows[0]['pass_test'])
            self.reports.setdefault(self._testMethodName,[]).append(dict(summary=rows[0],
                bench_sha256=hashlib.sha256(tb.encode()).hexdigest(),derived_RTL_sha256=hashlib.sha256(text.encode()).hexdigest()))

    def test_CAS_FADD_full_operands_keys_and_owner_before_SQ(self):
        body=''
        for op in [7,8]:
            for value in [0,0x0123456789abcdef,0x8000000000000000,0xffffffffffffffff]:
                for key in [0,0xffffffff]:
                    cmp=value^0x8123456789abcdef if op==7 else 0
                    c=context(op,compare=cmp,operand=value,rkey=key)
                    body+=f'submit({c});owner({c},7);sq({expected(op,compare=cmp,operand=value,rkey=key)});\n'
        self.simulate(body)

    def test_normal_Immediate_have_zero_extension_and_exact_lower_ABI(self):
        body=''
        for op in [1,2,3,5,6]:
            imm=0x89abcdef if op in [5,6]else 0;remote=0 if op in [3,5]else 0xe23456789abcdef0
            key=0 if op in [3,5]else 0xffffffff
            c=context(op,compare=0,operand=0,immediate=imm,remote=remote,rkey=key)
            body+=f'submit({c});owner({c},7);sq({expected(op,compare=0,operand=0,immediate=imm,remote=remote,rkey=key)});\n'
        self.simulate(body)

    def test_noncanonical_or_unknown_operands_never_become_HLS_authority(self):
        bad=[context(8,compare=1),context(7,length=9),context(7,remote=1),context(7,immediate=1),
            context(1,compare=1,operand=0),context(1,compare=0,operand=1),context(7,qpn=0x800007)]
        c=context();n=c.index("'h")+2;bad.append(c[:n]+'x'+c[n+1:])
        for value in bad:
            with self.subTest(value=value):self.simulate(f's_work_context={value};s_work_valid=1;'+r'''
repeat(8)@(negedge clk);
if(!fault || fault_code!==8'h71 || s_work_ready || m_owner_valid || m_axis_sq_tvalid ||
 owner_handoff_count || HLS_SQ_handoff_count || queue_guard!==255)$fatal(1,"bad Atomic operand gained authority");
''')

    def test_failed_DMA_and_denied_MR_keep_identity_but_no_HLS_SQ(self):
        body=''
        for error in [*range(1,16),32]:
            available=int(error==32);c=context(0,compare=0,operand=0,id=old.DEFAULT[0]if available else 0,
                flags=0,length=0,lkey=0,address=0,offset=0,remote=0,rkey=0,error=error,
                source=2 if available else 1,fetch=0 if available else error,available=available,authorized=0)
            body+=f'submit({c});owner({c},7);'+r'''
repeat(8)@(negedge clk);
if(m_axis_sq_tvalid || busy || fault || HLS_SQ_handoff_count)$fatal(1,"denial became an Atomic HLS operation");
downstream_queue_guard=0;
'''
        self.simulate(body)

    def test_real_downstream_guard_required_and_late_loss_does_not_retract_SQ(self):
        c=context()
        self.simulate(f'submit({c});'+r'''
m_owner_ready=1;repeat(8)@(negedge clk);
if(!fault || fault_code!==8'h72 || !m_owner_valid || m_axis_sq_tvalid || !busy || queue_guard!==255)
 $fatal(1,"Atomic owner handoff gap");
''')
        self.simulate(f'submit({c});owner({c},7);'+r'''
while(!m_axis_sq_tvalid)@(negedge clk);
downstream_queue_guard=0;repeat(8)@(negedge clk);
if(!fault || fault_code!==8'h73 || !m_axis_sq_tvalid || !busy || queue_guard!==255)$fatal(1,"late guard loss canceled SQ");
m_axis_sq_tready=1;@(posedge clk);@(negedge clk);m_axis_sq_tready=0;
if(!fault || !busy || queue_guard!==255 || HLS_SQ_handoff_count!=1)$fatal(1,"fault fabricated retirement");
''')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve prior evidence')
    files=[Path(__file__).resolve(),Path(source.__file__).resolve(),Path(source.fetch.__file__).resolve(),source.HLS,Path(old.__file__).resolve()]
    def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
    before={str(path.relative_to(ROOT)):digest(path)for path in files};started=time.monotonic()
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Atomic128HLSSQTests))
    if before!={str(path.relative_to(ROOT)):digest(path)for path in files}:raise ValueError('source changed')
    report=dict(scope=__doc__,pass_test=result.wasSuccessful(),source_sha256=before,methods=result.testsRun,
        simulations=sum(map(len,Atomic128HLSSQTests.reports.values())),tests=Atomic128HLSSQTests.reports,
        seconds=time.monotonic()-started,four_state=True,HLS_endpoint_model=True,executor_model=True,
        native_requester_integrated=False,hardware_verified=False)
    with a.report.open('x')as f:f.write(json.dumps(report,indent=2)+'\n')
    raise SystemExit(not result.wasSuccessful())
