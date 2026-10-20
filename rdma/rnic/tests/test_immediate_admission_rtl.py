# SPDX-License-Identifier: BSD-2-Clause-Views
"""Four-state actual C descriptor/SQ-result/shared-MR Immediate candidate."""
import ctypes as C
import subprocess
import tempfile
from pathlib import Path
import unittest
import test_wqe_admission_rtl as base
import test_sq_wqe_admission_rtl as sq

class ImmediateAdmissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base.WQEAdmissionRTLTests.setUpClass.__func__(cls)
        cls.lib.as02_wqe_encode_profile.argtypes=[C.POINTER(C.c_uint8),C.POINTER(base.codec.WQE),C.c_uint32]
        cls.lib.as02_wqe_encode_profile.restype=C.c_int
    @classmethod
    def tearDownClass(cls):cls.directory.cleanup()

    def entry(self,op=6,imm=0x81234567,*,error=0,queries=1,mutate=None,pd=7):
        w=base.codec.candidate(opcode=op,immediate=imm,local_address=base.BASE+1,
            remote_address=0 if op==5 else 0xe23456789abcdef0,remote_key=0 if op==5 else imm^0x81234567)
        data=(C.c_uint8*64)();self.assertEqual(self.lib.as02_wqe_encode_profile(data,C.byref(w),1),0)
        record=bytearray(data)
        if mutate:mutate(record)
        vals=[(64,w.wr_id),(64,base.SEQ),(64,base.EPOCH),(24,1),(16,pd),(16,0xf123),
            (16,op if not error else 0),(16,1 if not error else 0),(32,65 if not error else 0),
            (32,w.local_key if not error else 0),(64,w.local_address if not error else 0),(64,1 if not error else 0),
            (64,w.remote_address if not error else 0),(32,w.remote_key if not error else 0),(8,error)]
        return f'''expected_imm=32'h{imm:08x};
issue(512'h{int.from_bytes(record,'little'):0128x},64'hffffffffffffffff,1'b1,1'b1,
24'd1,16'd{pd},16'hf123,64'h{base.SEQ:x},64'h{base.EPOCH:x},576'h{base.packed(vals):0144x},
{queries},7,7,11,1'b1,8'd0);
'''

    def simulate(self,body,mode=1):
        tb=sq.bench(body)
        tb=tb.replace('rocev2_sq_wqe_admission dut(',f'rocev2_sq_wqe_admission #(.SEND_ENABLE(1),.IMMEDIATE_ENABLE({mode})) dut(')
        tb=tb.replace('.m_work_remote_key(ork),','.m_work_remote_key(ork),.m_work_immediate(oimm),')
        tb=tb.replace('reg clk=0;',"reg [31:0] expected_imm=0;wire [31:0] oimm;reg imm_stall=0;reg [31:0] held_imm;\nreg clk=0;")
        tb=tb.replace('initial begin\n repeat(4)',r'''
always @(posedge clk)if(!rst)begin
 if(ov && oimm!==(oe ? 32'd0:expected_imm))$fatal(1,"Immediate lost or leaked through denial/fetch error");
 if(imm_stall && (!ov || oimm!==held_imm))$fatal(1,"Immediate changed under actual MR/result stall");
 imm_stall=ov&&!ready;held_imm=oimm;
end
initial begin
 repeat(4)''',1)
        with tempfile.TemporaryDirectory(prefix='as02-imm-admission-')as directory:
            run=Path(directory);(run/'tb.v').write_text(tb)
            c=subprocess.run(['iverilog','-g2012','-s','tb','-o',str(run/'test.vvp'),str(run/'tb.v'),str(sq.RTL),
                str(base.RTL/'rocev2_wqe_admission.v'),str(base.RTL/'rocev2_mr_table.v')],capture_output=True,text=True,timeout=20)
            self.assertEqual(c.returncode,0,c.stdout+c.stderr)
            r=subprocess.run(['vvp',str(run/'test.vvp')],capture_output=True,text=True,timeout=15)
            self.assertEqual(r.returncode,0,r.stdout+r.stderr);self.assertIn('WQE_ADMISSION_PASS',r.stdout)

    def test_both_operations_full_immediate_keys_MR_and_backpressure(self):
        self.simulate(''.join(self.entry(op,imm)for op in [5,6]for imm in [0,0x01234567,0x80000000,0xffffffff]))

    def test_reserved_or_wrong_PD_denials_and_failed_fetch_erase_notification(self):
        body=self.entry(6,0xffffffff)
        body+=self.entry(error=0x20,queries=0,mutate=lambda b:b.__setitem__(52,0x80))
        body+=self.entry(error=2,pd=8)
        body+=self.entry(5,1,error=0x20,queries=0,mutate=lambda b:b.__setitem__(24,1))
        body+='failed_fetch(8\'d5);'
        self.simulate(body)

    def test_default_profile_still_refuses_zero_and_nonzero_notification(self):
        self.simulate(self.entry(5,0,error=0x24,queries=0)+self.entry(6,1,error=0x20,queries=0),mode=0)

if __name__=='__main__':unittest.main()
