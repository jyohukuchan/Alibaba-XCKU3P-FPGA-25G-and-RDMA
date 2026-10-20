# SPDX-License-Identifier: BSD-2-Clause-Views
"""Four-state Immediate RQ provenance/retention units, all proof inputs MODELS."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import test_receive_queue_rtl as base
from immediate_receive_cq_fixture import context

class ImmediateReceiveLifetimeTests(unittest.TestCase):
    reports={}
    def simulate(self,body):
        tb=base.TB.replace('// BODY',body).replace('[587:0]','[619:0]').replace('[679:0]','[751:0]').replace('[695:0]','[767:0]')
        tb=tb.replace('.RECV_RETIRE_ENABLE(RETIRE_PROFILE)',
            '.RECV_RETIRE_ENABLE(1),.RECV_CQ_ENABLE(1),.IMMEDIATE_ENABLE(1)')
        inputs=[base.RTL,Path(base.__file__).resolve(),Path(__file__).resolve(),Path(context.__code__.co_filename).resolve()]
        before={str(x.relative_to(base.ROOT)):hashlib.sha256(x.read_bytes()).hexdigest()for x in inputs}
        with tempfile.TemporaryDirectory(prefix='as02-immediate-rq-unit-')as directory:
            run=Path(directory);(run/'tb.v').write_text(tb)
            c=subprocess.run(['iverilog','-g2012','-s','tb','-o',str(run/'test'),str(run/'tb.v'),str(base.RTL)],capture_output=True,text=True,timeout=10)
            self.assertEqual(c.returncode,0,c.stdout+c.stderr)
            r=subprocess.run(['vvp',str(run/'test')],capture_output=True,text=True,timeout=10)
            self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        self.assertEqual(before,{n:hashlib.sha256((base.ROOT/n).read_bytes()).hexdigest()for n in before})
        self.reports.setdefault(self._testMethodName,[]).append(dict(source_sha256=before,pass_test=True))

    def owner(self,write=False):
        ctx=context(1,write)
        return f'''
query_qpn=7;@(negedge clk);s_post_context={ctx};s_post_valid=1;
@(posedge clk);if(!s_post_ready)$fatal(1,"modeled RQ post");@(negedge clk);s_post_valid=0;m_head_ready=1;
@(posedge clk);if(!m_head_valid)$fatal(1,"modeled RQ take");@(negedge clk);m_head_ready=0;
s_placement_context={ctx};s_placement_length=65;s_placement_psn=24'h987654;
'''
    def placed(self,write=False):
        return self.owner(write)+f'''
s_placement_notification=32'h81234567;s_placement_notification_flags={3 if write else 1};s_placement_valid=1;
@(posedge clk);if(!s_placement_ready)$fatal(1,"modeled wire notification");@(negedge clk);s_placement_valid=0;
'''
    def proof(self,write=False,imm="32'h81234567",flags=None):
        flags=flags if flags is not None else (3 if write else 1)
        return f"{{8'd0,8'd{flags},{imm},24'd1,4'd0,24'h987654,32'd65,{context(1,write)}}}"
    @staticmethod
    def retained(code):
        return f'''
repeat(7)@(negedge clk);
if(!fault || fault_code!==8'h{code:02x} || !active || queue_guard!==8'hff || m_ticket_valid ||
 s_commit_ready || s_retire_ready)$fatal(1,"bad Immediate provenance released native RQ/CQ owner");
'''
    def test_wire_and_core_notification_value_mismatch_retains_owner(self):
        self.simulate(self.placed()+f"s_core_data={self.proof(imm='32\'h81234566')};s_core_valid=1;memory_drained=1;"+self.retained(0xea))

    def test_core_cannot_turn_SEND_notification_into_WRITE_capacity_bypass(self):
        self.simulate(self.placed()+f's_core_data={self.proof(flags=3)};s_core_valid=1;memory_drained=1;'+self.retained(0xea))

    def test_SEND_notification_cannot_exceed_posted_receive_capacity(self):
        self.simulate(self.owner(True)+"s_placement_notification_flags=1;s_placement_notification=1;s_placement_valid=1;"+self.retained(0xe8))

    def test_unknown_wire_notification_is_not_placement_authority(self):
        self.simulate(self.owner()+"s_placement_notification_flags=1;s_placement_notification=32'hxxxxxxxx;s_placement_valid=1;"+self.retained(0xe8))

    def test_MAC_receipt_cannot_change_the_bound_notification(self):
        good=self.proof(True);bad=self.proof(True,imm="32'h81234566")
        body=self.placed(True)+f'''
s_core_data={good};s_core_valid=1;@(posedge clk);if(!s_core_ready)$fatal(1,"same bound core proof");
@(negedge clk);s_core_valid=0;
s_mac_data={{16'h6001,{bad}}};s_mac_valid=1;memory_drained=1;
'''+self.retained(0xeb)
        self.simulate(body)

    @classmethod
    def tearDownClass(cls):
        if name:=os.environ.get('AS02_RNIC_IMMEDIATE_RQ_UNITS_REPORT'):
            p=Path(name);p=p if p.is_absolute()else base.ROOT/p
            report=dict(scope=__doc__,pass_test=len(cls.reports)==5,methods=len(cls.reports),tests=cls.reports,
                actual_RQ_RTL=True,four_state=True,proof_sources_modeled=True,hardware_verified=False)
            with p.open('x')as f:f.write(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':unittest.main()
