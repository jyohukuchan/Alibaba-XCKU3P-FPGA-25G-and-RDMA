# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual128-byte SQC/fetch/AXI ownership; backend/guards remain models.

Preserve the complete prior control/error/retirement suite using the actual
matched128-byte SQC and two-beat fetch. Not native CQ/host DMA/API evidence.
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
import test_sq_control_regs_rtl as old

ROOT=old.ROOT;sys.path.insert(0,str(ROOT/'rdma/rnic/fpga'))
import derive_atomic128_native as source


class Atomic128SQControlTests(old.SQControlRegsTests):
    reports={}

    def simulate(self,scenario,subcase=0):
        derived=source.derive()
        selected={old.RTL:derived[old.RTL],source.admission.fetch.FETCH:derived[source.admission.fetch.FETCH]}
        inputs=[*old.SOURCES,old.HEADER,Path(__file__).resolve(),Path(old.__file__).resolve(),
            Path(source.__file__).resolve(),Path(source.base.rx.stage.authority.lookup.__file__).resolve(),
            Path(source.admission.fetch.__file__).resolve()]
        def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
        before={str(p.relative_to(ROOT)):digest(p)for p in inputs}
        ports=re.findall(r'\b(input|output)\s+(?:wire|reg)\s+(?:\[([^]]+)\]\s+)?(\w+)',selected[old.RTL].split('\n);',1)[0])
        driven={'cfg_ready','cfg_response_error','cfg_response_qpn','cfg_response_epoch','cfg_response_consumer','cfg_response_valid','fetch_queue_guard'}
        decl='\n'.join(old.pcie.declaration(n,old.pcie.width(e,dict(ADDR_WIDTH=12,MAX_QPS=8)),
            'reg'if d=='input'and n not in driven else'wire')for d,e,n in ports)
        macros='\n'.join('localparam '+n+'='+re.sub(r'([0-9a-fA-F]+)U$',r'\1',v).replace('0x',"32'h")+';'for n,v in
            re.findall(r'^#define (AS02_SQC_\w+) (\w+)',old.HEADER.read_text(),re.M))
        t=old.TB.replace('// ABI',macros).replace('// DECLARATIONS',decl).replace('INITIAL_SEQUENCE_VALUE',"32'hfffffffe"if scenario==8 else'0')
        t=source.once(t,'#(.INITIAL_SEQUENCE(', '#(.IMMEDIATE_ENABLE(1),.INITIAL_SEQUENCE(')
        t=source.once(t,'wire [511:0] result_data;','wire [1023:0] result_data;')
        t=source.once(t,'reg fetch_enable=1;','reg fetch_enable=1,second_beat=0;')
        t=source.once(t,".s_axis_read_tdata(512'hdeadbeef)",".s_axis_read_tdata(second_beat ? 512'd0:512'hdeadbeef)")
        t=source.once(t,".s_axis_read_tlast(1'b1)",'.s_axis_read_tlast(second_beat)')
        t=source.once(t,"result_data!==512'hdeadbeef","result_data!==1024'hdeadbeef")
        t=source.once(t,'+(fetches%2)*64 || length!==64','+(fetches%2)*128 || length!==128')
        t=source.once(t,'@(negedge clk);read_valid=0;status_valid=0;',
            '@(negedge clk);status_valid=0;second_beat=1;@(posedge clk);\n'
            '   if(!read_ready)$fatal(1,"real second128-byte fetch beat not owned");\n'
            '   @(negedge clk);read_valid=0;second_beat=0;')
        t=source.once(t,"4:begin words[8]=32'hffffff80;","4:begin words[8]=32'hffffff00;")
        t=source.once(t,' repeat(8)@(negedge clk);rst=0;',
            ' repeat(8)@(negedge clk);rst=0;\n'
            ' read_reg(8,value);if(value!==13)$fatal(1,"actual128 SQ feature");\n'
            ' read_reg(32,value);if(value!==128)$fatal(1,"actual128 SQ descriptor bytes");')
        with tempfile.TemporaryDirectory(prefix='as02-atomic128-sqc-')as directory:
            run=Path(directory);(run/'tb.v').write_text(t);src=[]
            for p in old.SOURCES:
                if p in selected:
                    q=run/p.name;q.write_text(selected[p]);src.append(q)
                else:src.append(p)
            c=subprocess.run(['iverilog','-g2012','-s','tb','-o',str(run/'test.vvp'),str(run/'tb.v'),*map(str,src)],
                capture_output=True,text=True,timeout=20)
            self.assertEqual(c.returncode,0,c.stdout+c.stderr)
            r=subprocess.run(['vvp',str(run/'test.vvp'),f'+case={scenario}',f'+subcase={subcase}'],
                capture_output=True,text=True,timeout=10)
            if r.returncode:
                saved=Path(tempfile.mkdtemp(prefix='atomic128-sqc-failure-',dir=ROOT/'rdma/rnic/build'))
                for p in run.iterdir():shutil.copy2(p,saved/p.name)
                (saved/'simulation.log').write_text(r.stdout+r.stderr)
            self.assertEqual(r.returncode,0,r.stdout+r.stderr);self.assertNotIn('ERROR:',r.stdout+r.stderr)
            rows=[json.loads(l[11:])for l in r.stdout.splitlines()if l.startswith('SQC_RESULT ')]
            self.assertEqual(len(rows),1);self.assertTrue(rows[0]['pass_test'])
        self.assertEqual(before,{n:digest(ROOT/n)for n in before})
        self.reports.setdefault(self._testMethodName,[]).append(dict(summary=rows[0],source_sha256=before,
            bench_sha256=hashlib.sha256(t.encode()).hexdigest(),
            generated_sha256={p.name:hashlib.sha256(text.encode()).hexdigest()for p,text in selected.items()}))

    @classmethod
    def tearDownClass(cls):pass


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve previous evidence')
    start=time.monotonic();r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Atomic128SQControlTests))
    report=dict(scope=__doc__,pass_test=r.wasSuccessful(),methods=r.testsRun,simulations=sum(map(len,Atomic128SQControlTests.reports.values())),
        seconds=time.monotonic()-start,tests=Atomic128SQControlTests.reports,backend_and_guards_modeled=True,
        actual_AXI_SQC_and_two_beat_fetch=True,hardware_verified=False,standard_API_runtime=False)
    with a.report.open('x')as f:f.write(json.dumps(report,indent=2)+'\n')
    raise SystemExit(not r.wasSuccessful())

