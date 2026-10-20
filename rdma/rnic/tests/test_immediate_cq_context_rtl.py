# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual CQC620-bit snapshot ABI; upstream commit/retire producers are MODELS."""
from pathlib import Path
import subprocess
import tempfile
import unittest
import test_message_cq_rtl as base
from test_wqe_hls_sq_rtl import context

class ImmediateCQContextTests(unittest.TestCase):
    def test_full_immutable_transmit_immediate_and_separate_zero_notification(self):
        tb=base.bench().replace('[587:0]','[619:0]').replace('.MESSAGE_ENABLE(1)', '.MESSAGE_ENABLE(1),.IMMEDIATE_ENABLE(1)')
        tb=tb.replace('.s_ticket_received_bytes(actual_bytes),',
            ".s_ticket_received_bytes(actual_bytes),.s_ticket_notification(32'd0),.s_ticket_notification_flags(8'd0),")
        tb=tb.replace('host_i<19','host_i<20').replace('host_value!=3)$fatal(1,"message feature ABI")',
            'host_value!=7)$fatal(1,"message feature ABI")')
        # Replace only the original three operation calls, retaining ALL
        # immutable owner/commit/retire/AXI/backpressure/old-ACK checks.
        start=tb.index('publish(588\'h');end=tb.index('\n $display("MESSAGE_CQ_RESULT',start)
        body='';seq=0
        for op in [5,6]:
            for imm in [0,0x01234567,0x80000000,0xffffffff]:
                seq+=1
                c=int(context(id=0xf123456789abc000+seq,sequence=seq,qpn=7,pd=17,tag=seq,lkey=8,
                    opcode=op,remote=0 if op==5 else 0xe23456789abcdef0,rkey=0 if op==5 else imm^0x81234567).split("'h")[1],16)|(imm<<588)
                body+=f"publish(620'h{c:0155x},0,{seq},0);\n"
        tb=tb[:start]+body+tb[end:]
        tb=tb.replace('  cq_read(12\'h038,host_value);if(host_value!=bytes)$fatal(1,"actual received byte count");',
            '  cq_read(12\'h038,host_value);if(host_value!=bytes)$fatal(1,"actual received byte count");\n'
            '  cq_read(12\'h03c,host_value);if(host_value)$fatal(1,"visible TX synthesized receive flags");\n'
            '  cq_read(12\'h090,host_value);if(host_value)$fatal(1,"visible TX synthesized receive notification");')
        tb=tb.replace(' $display("MESSAGE_CQ_RESULT',
            ' cq_read(12\'h03c,host_value);if(host_value)$fatal(1,"TX synthesized receive notification flags");\n'
            ' cq_read(12\'h090,host_value);if(host_value)$fatal(1,"TX synthesized receive notification");\n'
            ' $display("MESSAGE_CQ_RESULT')
        start=tb.index(' $display("MESSAGE_CQ_RESULT');end=tb.index(';',start)+1
        tb=tb[:start]+''' if(pub_published!=8 || pub_acked!=8)$fatal(1,"eight TX context events required");
 $display("IMMEDIATE_CQ_CONTEXT {\\"pass_test\\":true,\\"TX_context_events\\":8}");'''+tb[end:]
        with tempfile.TemporaryDirectory(prefix='as02-immediate-cqc-context-')as directory:
            run=Path(directory);(run/'tb.v').write_text(tb)
            c=subprocess.run(['iverilog','-g2012','-s','tb','-o',str(run/'test'),str(run/'tb.v'),*map(str,base.SOURCES)],capture_output=True,text=True,timeout=20)
            self.assertEqual(c.returncode,0,c.stdout+c.stderr)
            r=subprocess.run(['vvp',str(run/'test')],capture_output=True,text=True,timeout=10)
            self.assertEqual(r.returncode,0,r.stdout+r.stderr)

if __name__=='__main__':unittest.main()
