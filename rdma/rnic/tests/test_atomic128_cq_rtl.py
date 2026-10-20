# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual748-bit CQ ABI; ticket/commit/retire and host are explicit models.

Atomic operands occupy0xa0..0xac, NEVER the legacy notification at0x90 or
the old context's zero padding. Runtime publisher test, not native DMA proof.
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
import test_message_cq_rtl as old
from test_atomic128_response_rtl import owner

ROOT=old.ROOT;sys.path.insert(0,str(ROOT/'rdma/rnic/fpga'))
import derive_atomic128_native as source


def bench():
    t=old.bench().replace('[587:0]','[747:0]')
    t=source.once(t,'.MESSAGE_ENABLE(1)', '.MESSAGE_ENABLE(1),.IMMEDIATE_ENABLE(1)')
    t=source.once(t,'reg [31:0] actual_bytes=0;',
        'reg [31:0] actual_bytes=0,notification=0;reg [7:0] notification_flags=0;')
    t=source.once(t,'.s_ticket_received_bytes(actual_bytes),',
        '.s_ticket_received_bytes(actual_bytes),.s_ticket_notification(notification),.s_ticket_notification_flags(notification_flags),')
    t=source.once(t,'host_i<19','host_i<20')
    t=source.once(t,"({20'd0,expected}>>","({20'd0,expected[619:0]}>>")
    t=source.once(t,'host_value!=3)$fatal(1,"message feature ABI")',
        'host_value!=15)$fatal(1,"message feature ABI")')
    t=source.once(t,'  cq_read(12\'h038,host_value);if(host_value!=bytes)$fatal(1,"actual received byte count");',
        '  cq_read(12\'h038,host_value);if(host_value!=bytes)$fatal(1,"actual received byte count");\n'+VISIBLE)
    t=source.once(t,'  cq_read(12\'h038,host_value);if(host_value)$fatal(1,"early received bytes");',
        '  cq_read(12\'h038,host_value);if(host_value)$fatal(1,"early received bytes");\n'
        '  for(host_i=0;host_i<4;host_i=host_i+1)begin cq_read(12\'h0a0+host_i*4,host_value);\n'
        '   if(host_value)$fatal(1,"Atomic operands visible before commit/retire");end')
    a=t.index("publish(588'h");b=t.index('\n $display("MESSAGE_CQ_RESULT',a)
    body=''
    for seq,op in enumerate([7,8,2,4],1):
        changes=dict(pd=17,sequence=seq,tag=seq)
        if op==4:changes.update(length=128,remote=0,rkey=0)
        body+=("notification=32'h89abcdef;notification_flags=3;\n"if op==4 else'notification=0;notification_flags=0;\n')
        body+=f'publish({owner(op,**changes)},{65 if op==4 else 0},{seq},0);\n'
    t=t[:a]+body+t[b:]
    t=source.once(t,' $display("MESSAGE_CQ_RESULT',
        ' if(pub_published!=4 || pub_acked!=4)$fatal(1,"four full-owner events");\n $display("MESSAGE_CQ_RESULT')
    return t


VISIBLE=r'''
  cq_read(12'h03c,host_value);if(host_value!==notification_flags)$fatal(1,"CQ flags collided with operand");
  cq_read(12'h090,host_value);if(host_value!==notification)$fatal(1,"CQ notification collided with operand");
  cq_read(12'h094,host_value);if(host_value!==748)$fatal(1,"CQ full owner bits");
  cq_read(12'h098,host_value);if(host_value!==32'ha0)$fatal(1,"CQ operand aperture");
  for(host_i=0;host_i<4;host_i=host_i+1)begin
   cq_read(12'h0a0+host_i*4,host_value);
   if(host_value!==((expected[747:620]>>(host_i*32))&32'hffffffff))$fatal(1,"full immutable Atomic operands");
  end
'''


class Atomic128CQTests(unittest.TestCase):
    reports={}

    def simulate(self,t):
        generated=source.cq()
        inputs=[source.CQ,Path(source.__file__).resolve(),Path(__file__).resolve(),
            Path(old.__file__).resolve(),Path(old.original.__file__).resolve(),
            ROOT/'rdma/rnic/tests/test_atomic128_response_rtl.py',*old.SOURCES[1:]]
        def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
        before={str(p.relative_to(ROOT)):digest(p)for p in inputs}
        with tempfile.TemporaryDirectory(prefix='as02-atomic128-cq-')as directory:
            run=Path(directory);(run/'tb.v').write_text(t);(run/'cq.v').write_text(generated)
            cmd=['iverilog','-g2012','-s','tb','-o',str(run/'test.vvp'),str(run/'tb.v'),str(run/'cq.v'),*map(str,old.SOURCES[1:])]
            c=subprocess.run(cmd,capture_output=True,text=True,timeout=20)
            self.assertEqual(c.returncode,0,c.stdout+c.stderr)
            r=subprocess.run(['vvp',str(run/'test.vvp')],cwd=run,capture_output=True,text=True,timeout=10)
            if r.returncode:
                saved=Path(tempfile.mkdtemp(prefix='atomic128-cq-failure-',dir=ROOT/'rdma/rnic/build'))
                for p in run.iterdir():shutil.copy2(p,saved/p.name)
                (saved/'simulation.log').write_text(r.stdout+r.stderr)
            self.assertEqual(r.returncode,0,r.stdout+r.stderr);self.assertNotIn('ERROR:',r.stdout+r.stderr)
        self.assertEqual(before,{n:digest(ROOT/n)for n in before})
        self.reports.setdefault(self._testMethodName,[]).append(dict(source_sha256=before,
            bench_sha256=hashlib.sha256(t.encode()).hexdigest(),generated_CQ_sha256=hashlib.sha256(generated.encode()).hexdigest()))

    def test_CAS_FADD_READ_RECV_preserve_operands_notification_padding_and_owned_ACK(self):
        self.simulate(bench())

    def test_noncanonical_Atomic_and_normal_extensions_never_publish(self):
        for value in [owner(8,pd=17,compare=1),owner(2,pd=17,argument=1),
                owner(7,pd=17,length=9),owner(7,pd=17,immediate=1),owner(8,pd=17,remote=1)]:
            t=bench();a=t.index('initial begin\n repeat(5)');t=t[:a]+r'''
initial begin
 repeat(5)@(posedge clk);@(negedge clk);rst=0;
 m_cq_context=BAD_OWNER;m_cq_valid=1;
 repeat(7)@(negedge clk);
 if(!pub_fault || pub_fault_code!==8'hc2 || m_cq_ready || s_cq_commit_valid || pub_retire_valid ||
   pub_published || pub_acked || pub_guard!==8'hff)$fatal(1,"noncanonical owner acquired CQ authority");
 $finish;
end
endmodule
'''
            t=t.replace(' if(pub_fault)$fatal(1,"message CQ fault %h",pub_fault_code);','')
            self.simulate(t.replace('BAD_OWNER',value))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve previous evidence')
    start=time.monotonic();r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Atomic128CQTests))
    report=dict(scope=__doc__,pass_test=r.wasSuccessful(),methods=r.testsRun,simulations=sum(map(len,Atomic128CQTests.reports.values())),
        seconds=time.monotonic()-start,tests=Atomic128CQTests.reports,upstream_lifetime_models=True,hardware_verified=False)
    with a.report.open('x')as f:f.write(json.dumps(report,indent=2)+'\n')
    raise SystemExit(not r.wasSuccessful())

