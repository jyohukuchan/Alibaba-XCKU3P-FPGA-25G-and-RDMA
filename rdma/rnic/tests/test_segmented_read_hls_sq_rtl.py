#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual private large READ748-owner to408-SQ staging, endpoints modeled.

Keep every original Atomic staging method. No actual MR grant/native fetch/
HLS execution/DMA/CQ/API or hardware proof follows the modeled owner handoff.
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
import test_atomic128_hls_sq_rtl as old

ROOT=old.ROOT;digest=lambda p:old.hashlib.sha256(p.read_bytes()).hexdigest()
sys.path.insert(0,str(ROOT/'rdma/rnic/fpga'))
import derive_segmented_read_profile as source


class ReadHLSSQ(old.Atomic128HLSSQTests):
    reports={}

    def simulate(self,body):
        run=Path(tempfile.mkdtemp(prefix='segmented-read-hls-sq-',dir=ROOT/'rdma/rnic/build'))
        text=source.derive()[source.RTL/'rocev2_wqe_hls_sq.v'];header=text.split(')(\n',1)[1].split('\n);',1)[0]
        ports=re.findall(r'^\s*(input|output)\s+(?:wire|reg)\s+(\[[^]]+\]\s+)?(\w+)(?:=0)?\s*,?$',header,re.M)
        self.assertEqual(len(ports),21)
        decl='\n'.join(('reg 'if d=='input'else'wire ')+(w or '')+n+('=0;'if d=='input'else';')for d,w,n in ports)
        tb=old.old.TB.replace('// DECLARATIONS',decl).replace('// BODY',body)
        tb=tb.replace('IMMEDIATE_ENABLE=0','IMMEDIATE_ENABLE=1').replace('[587:0]','[747:0]').replace('[247:0]','[407:0]')
        tb=source.once(tb,'rocev2_wqe_hls_sq dut','rocev2_wqe_hls_sq #(.IMMEDIATE_ENABLE(1)) dut')
        leaf=run/'rocev2_wqe_hls_sq.v';leaf.write_text(text);(run/'tb.v').write_text(tb)
        info=dict(directory=str(run.relative_to(ROOT)),pass_test=False,runtime_limit_seconds=10)
        self.reports.setdefault(self._testMethodName,[]).append(info)
        try:
            c=subprocess.run(['iverilog','-g2012','-s','tb','-o',str(run/'test.vvp'),str(run/'tb.v'),str(leaf)],capture_output=True,text=True,timeout=30)
            (run/'compile.log').write_text(c.stdout+c.stderr);self.assertEqual(c.returncode,0,c.stdout+c.stderr)
            self.assertFalse(any('expects'in l and 'bits'in l for l in c.stderr.splitlines()),c.stderr)
            start=time.monotonic();r=subprocess.run(['vvp',str(run/'test.vvp')],capture_output=True,text=True,timeout=10)
            info['seconds']=time.monotonic()-start;(run/'simulation.log').write_text(r.stdout+r.stderr)
            self.assertEqual(r.returncode,0,r.stdout+r.stderr)
            rows=[json.loads(l.split(' ',1)[1])for l in r.stdout.splitlines()if l.startswith('WQE_HLS_SQ_RESULT ')]
            self.assertEqual(len(rows),1);self.assertTrue(rows[0]['pass_test']);info.update(pass_test=True,summary=rows[0])
        finally:info['artifact_sha256']={str(q.relative_to(ROOT)):digest(q)for q in run.iterdir()if q.is_file()}

    def test_large_READ_full_length_keys_and_exact_owner_before_SQ(self):
        body=''
        for n in [4097,8193,65537,1048576]:
            for key in [0,0xffffffff]:
                ctx=old.context(2,compare=0,operand=0,length=n,rkey=key)
                body+=f'submit({ctx});owner({ctx},7);sq({old.expected(2,compare=0,operand=0,length=n,rkey=key)});\n'
        self.simulate(body)

    def test_large_READ_noncanonical_length_operands_Immediate_or_QPN_never_gets_SQ(self):
        bad=[old.context(2,compare=0,operand=0,length=1048577),old.context(2,compare=1,operand=0,length=8193),
            old.context(2,compare=0,operand=1,length=8193),old.context(2,compare=0,operand=0,immediate=1,length=8193),
            old.context(2,compare=0,operand=0,qpn=0x800007,length=8193)]
        for ctx in bad:self.simulate(f's_work_context={ctx};s_work_valid=1;'+r'''
repeat(8)@(negedge clk);
if(fault!==1'b1 || s_work_ready || m_owner_valid || m_axis_sq_tvalid || owner_handoff_count ||
 HLS_SQ_handoff_count || queue_guard!==255)$fatal(1,"invalid large READ became HLS authority");
''')

    def test_large_READ_exact_guard_required_and_late_loss_retains_offered_SQ(self):
        ctx=old.context(2,compare=0,operand=0,length=8193)
        self.simulate(f'submit({ctx});'+r'''
m_owner_ready=1;repeat(8)@(negedge clk);
if(fault!==1'b1 || !m_owner_valid || m_axis_sq_tvalid || !busy || queue_guard!==255)
 $fatal(1,"large READ owner handoff lost real downstream guard");
''')
        self.simulate(f'submit({ctx});owner({ctx},7);'+r'''
while(!m_axis_sq_tvalid)@(negedge clk);downstream_queue_guard=0;repeat(8)@(negedge clk);
if(fault!==1'b1 || !m_axis_sq_tvalid || !busy || queue_guard!==255)
 $fatal(1,"late guard loss retracted large READ SQ");
''')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve earlier evidence')
    helpers=[Path(m.__file__).resolve()for m in list(sys.modules.values())if getattr(m,'__file__',None)and
        Path(m.__file__).resolve().is_relative_to(ROOT/'rdma/rnic')]
    before={str(q.relative_to(ROOT)):digest(q)for q in dict.fromkeys([*helpers,*list((ROOT/'rdma/rnic/fpga').glob('*.py')),Path(__file__).resolve()])}
    start=time.monotonic();r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ReadHLSSQ))
    same=all(digest(ROOT/n)==h for n,h in before.items())
    report=dict(scope=__doc__,pass_test=r.wasSuccessful()and same,methods=r.testsRun,cases=sum(map(len,ReadHLSSQ.reports.values())),
        source_sha256=before,source_unchanged=same,seconds=time.monotonic()-start,
        all_five_original_Atomic_staging_methods_retained=True,owner_bits=748,SQ_bits=408,
        HLS_and_executor_endpoints_modeled=True,native_runtime=False,hardware_verified=False,
        failures=[dict(test=str(t),trace=s)for t,s in r.failures+r.errors],tests=ReadHLSSQ.reports)
    with a.report.open('x')as f:f.write(json.dumps(report,indent=2)+'\n')
    raise SystemExit(not report['pass_test'])


if __name__=='__main__':main()
