# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual C codec candidate profile; normal posting retains profile0 refusal."""
import ctypes as C
import errno
import unittest
import test_wqe_codec as base

class ImmediateWQETests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base.WQECodecTests.setUpClass.__func__(cls)
        for name,args in [('as02_wqe_encode_profile',[C.POINTER(C.c_uint8),C.POINTER(base.WQE),C.c_uint32]),
                          ('as02_wqe_decode_profile',[C.POINTER(base.WQE),C.POINTER(C.c_uint8),C.c_uint32])]:
            f=getattr(cls.lib,name);f.argtypes=args;f.restype=C.c_int
    @classmethod
    def tearDownClass(cls):cls.directory.cleanup()

    def test_explicit_profile_has_exact_separate_32bit_immediate_and_reserved_tail(self):
        self.assertEqual(C.sizeof(base.WQE),64)
        for op in [5,6]:
            for imm in [0,0x01234567,0x80000000,0xffffffff]:
                w=base.candidate(opcode=op,immediate=imm,remote_address=0 if op==5 else 0xe23456789abcdef0,
                    remote_key=0 if op==5 else imm^0x81234567)
                out=(C.c_uint8*64)();decoded=base.WQE()
                self.assertEqual(self.lib.as02_wqe_encode_profile(out,C.byref(w),1),0)
                self.assertEqual(bytes(out),base.oracle(w))
                self.assertEqual(bytes(out)[48:52],imm.to_bytes(4,'little'))
                self.assertEqual(bytes(out)[52:56],bytes(4))
                self.assertEqual(self.lib.as02_wqe_decode_profile(C.byref(decoded),out,1),0)
                self.assertEqual(bytes(decoded),bytes(w))
                self.assertEqual(decoded.remote_key,w.remote_key)

    def test_default_profile_still_refuses_new_operations_and_zeroes_output(self):
        for op in [5,6]:
            w=base.candidate(opcode=op,remote_address=0 if op==5 else 123,remote_key=0,immediate=0)
            out=(C.c_uint8*64)(*([0xa5]*64))
            self.assertEqual(self.lib.as02_wqe_encode(out,C.byref(w)),-errno.EOPNOTSUPP)
            self.assertEqual(bytes(out),bytes(64))
            data=(C.c_uint8*64).from_buffer_copy(base.oracle(w));decoded=base.WQE()
            self.assertEqual(self.lib.as02_wqe_decode(C.byref(decoded),data),-errno.EOPNOTSUPP)
            self.assertEqual(bytes(decoded),bytes(64))

    def test_reserved_normal_operation_and_noncanonical_SEND_rejected(self):
        for w in [base.candidate(immediate=1),base.candidate(opcode=5,remote_address=1,remote_key=0),
                  base.candidate(opcode=5,remote_address=0,remote_key=0xffffffff)]:
            out=(C.c_uint8*64)(*([0xa5]*64))
            self.assertEqual(self.lib.as02_wqe_encode_profile(out,C.byref(w),1),-errno.EINVAL)
            self.assertEqual(bytes(out),bytes(64))
        w=base.candidate(opcode=6,immediate=0xffffffff)
        for offset in range(52,56):
            data=bytearray(base.oracle(w));data[offset]=0x80
            inp=(C.c_uint8*64).from_buffer_copy(data);decoded=base.WQE()
            self.assertEqual(self.lib.as02_wqe_decode_profile(C.byref(decoded),inp,1),-errno.EINVAL)
            self.assertEqual(bytes(decoded),bytes(64))

    def test_profile_alias_roundtrip_and_unknown_profile_refused(self):
        w=base.candidate(opcode=6,immediate=0x81234567);expected=base.oracle(w)
        alias=C.cast(C.byref(w),C.POINTER(C.c_uint8))
        self.assertEqual(self.lib.as02_wqe_encode_profile(alias,C.byref(w),1),0)
        self.assertEqual(bytes(w),expected)
        self.assertEqual(self.lib.as02_wqe_decode_profile(C.byref(w),alias,1),0)
        self.assertEqual(base.oracle(w),expected)
        out=(C.c_uint8*64)(*([0xa5]*64))
        self.assertEqual(self.lib.as02_wqe_encode_profile(out,C.byref(w),2),-errno.EOPNOTSUPP)
        self.assertEqual(bytes(out),bytes(64))

if __name__=='__main__':unittest.main()
