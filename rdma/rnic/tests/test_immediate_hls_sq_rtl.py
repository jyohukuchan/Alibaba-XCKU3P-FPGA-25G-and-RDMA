# SPDX-License-Identifier: BSD-2-Clause-Views
"""Four-state typed620-bit owner/280-bit SQ; executor/HLS are explicit models."""
import unittest
import test_wqe_hls_sq_rtl as base

def context(imm=0,**fields):
    n=int(base.context(**fields).split("'h")[1],16)|(imm<<588)
    return f"620'h{n:0155x}"

def expected(op,imm,remote,key):
    n=(imm<<241)|(1<<240)|(key<<208)|(65<<176)|(remote<<112)|\
        (0xfedcba9876543210<<48)|(1<<43)|(1<<42)|(7<<32)|(5 if op==5 else 11)
    return f"280'h{n:070x}"

class ImmediateHLSSQTests(unittest.TestCase):
    reports={}
    def test_both_opcodes_notifications_keys_and_owner_before_SQ(self):
        body=''
        for op in [5,6]:
            for imm in [0,0x01234567,0x80000000,0xffffffff]:
                remote=0 if op==5 else 0xe23456789abcdef0;key=0 if op==5 else imm^0x81234567
                c=context(imm,opcode=op,remote=remote,rkey=key)
                body+=f'submit({c});owner({c},7);sq({expected(op,imm,remote,key)});\n'
        base.WQEHlsSQTests.simulate(self,body,immediate=True)

    def test_unknown_or_wrong_notification_never_becomes_HLS_authority(self):
        bad=[context(1,opcode=1),context(1,opcode=5,remote=1,rkey=0),"{32'hxxxxxxxx,"+base.context()+"}"]
        for value in bad:
            with self.subTest(value=value):
                body=f's_work_context={value};s_work_valid=1;repeat(9)@(negedge clk);'+r'''
if(!fault || s_work_ready || m_owner_valid || m_axis_sq_tvalid || owner_handoff_count || HLS_SQ_handoff_count)
 $fatal(1,"invalid Immediate context became authority");
'''
                base.WQEHlsSQTests.simulate(self,body,immediate=True)

if __name__=='__main__':unittest.main()
