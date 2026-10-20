# SPDX-License-Identifier: BSD-2-Clause-Views
"""Candidate actual C128-byte codec with UBSan; no posting/MR/DMA/API claim."""
import argparse
import ctypes as C
import errno
import hashlib
import json
from pathlib import Path
import random
import struct
import subprocess
import tempfile
import time
import unittest
import test_wqe_codec as base

ROOT=base.ROOT;KERNEL=base.KERNEL


class AtomicWQE(C.Structure):
    _fields_=[('base',base.WQE),('compare',C.c_uint64),('swap_add',C.c_uint64)]


def candidate(opcode=7,compare=0xfedcba9876543210,swap_add=0x8123456789abcdef,**values):
    values=dict(length=8,remote_address=0xe23456789abcd008,**values)
    return AtomicWQE(base.candidate(opcode=opcode,**values),compare,swap_add)


def oracle(w):
    return base.oracle(w.base)+struct.pack('<QQ',w.compare,w.swap_add)+bytes(48)


class AtomicWQETests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory=tempfile.TemporaryDirectory(prefix='as02-atomic-wqe-');cls.path=Path(cls.directory.name)
        c=subprocess.run(['cc','-std=c11','-O2','-g','-Wall','-Wextra','-Werror','-shared','-fPIC',
            '-fsanitize=undefined','-fno-sanitize-recover=undefined','-I',str(KERNEL),
            str(KERNEL/'wqe.c'),str(KERNEL/'wqe_atomic.c'),'-o',str(cls.path/'atomic.so')],capture_output=True,text=True,timeout=30)
        if c.returncode:raise RuntimeError(c.stdout+c.stderr)
        cls.lib=C.CDLL(str(cls.path/'atomic.so'))
        for name,args in [('as02_atomic_wqe_encode',[C.POINTER(C.c_uint8),C.POINTER(AtomicWQE)]),
            ('as02_atomic_wqe_decode',[C.POINTER(AtomicWQE),C.POINTER(C.c_uint8)]),
            ('as02_wqe_encode',[C.POINTER(C.c_uint8),C.POINTER(base.WQE)]),
            ('as02_wqe_encode_profile',[C.POINTER(C.c_uint8),C.POINTER(base.WQE),C.c_uint32])]:
            f=getattr(cls.lib,name);f.argtypes=args;f.restype=C.c_int
    @classmethod
    def tearDownClass(cls):cls.directory.cleanup()

    def encode(self,w,error=0):
        out=(C.c_uint8*128)(*([0xa5]*128))
        self.assertEqual(self.lib.as02_atomic_wqe_encode(out,C.byref(w)),error)
        self.assertEqual(bytes(out),oracle(w)if not error else bytes(128));return bytes(out)

    def decode(self,data,error=0):
        out=AtomicWQE();C.memset(C.byref(out),0xa5,C.sizeof(out))
        raw=(C.c_uint8*128).from_buffer_copy(data)
        self.assertEqual(self.lib.as02_atomic_wqe_decode(C.byref(out),raw),error)
        if error:self.assertEqual(bytes(out),bytes(C.sizeof(out)))
        return out

    def test_exact_CAS_FADD_full_width_independent_operands_and_roundtrip(self):
        self.assertEqual(C.sizeof(AtomicWQE),80)
        rng=random.Random(455)
        for op in [7,8]:
            for i in range(32):
                w=candidate(op,compare=rng.getrandbits(64)if op==7 else 0,swap_add=rng.getrandbits(64),
                    remote_key=rng.getrandbits(32),local_key=rng.getrandbits(32),flags=i%2)
                encoded=self.encode(w);decoded=self.decode(encoded)
                self.assertEqual(bytes(decoded),bytes(w))
                self.assertEqual(encoded[64:80],struct.pack('<QQ',w.compare,w.swap_add))

    def test_normal_Immediate_RECV_share_header_but_have_zero_extension(self):
        for op in [1,2,3,4,5,6]:
            b=base.candidate(opcode=op,remote_address=0 if op in [3,4,5]else 0xe23456789abcd002,
                remote_key=0 if op in [3,4,5]else 0x81234567,immediate=0x89abcdef if op in [5,6]else 0)
            w=AtomicWQE(b,0,0);self.assertEqual(bytes(self.decode(self.encode(w))),bytes(w))

    def test_alignment_length_ranges_flags_epochs_and_noncanonical_fields(self):
        cases=[(dict(base=dict(length=0)),-errno.EMSGSIZE),(dict(base=dict(length=7)),-errno.EMSGSIZE),
            (dict(base=dict(length=9)),-errno.EMSGSIZE),(dict(base=dict(remote_address=1)),-errno.EINVAL),
            (dict(base=dict(local_address=base.U64)),-errno.EFAULT),(dict(base=dict(flags=2)),-errno.EOPNOTSUPP),
            (dict(base=dict(sequence=0)),-errno.EINVAL),(dict(base=dict(epoch=0)),-errno.EINVAL),
            (dict(base=dict(immediate=1)),-errno.EINVAL),(dict(base=dict(opcode=0x10007)),-errno.EINVAL)]
        for change,error in cases:
            w=candidate()
            for n,v in change['base'].items():setattr(w.base,n,v)
            with self.subTest(change=change):self.encode(w,error)
        self.encode(candidate(8,compare=1),-errno.EINVAL)
        w=candidate();w.base.local_address=base.U64-7;w.base.remote_address=base.U64-7
        self.assertEqual(bytes(self.decode(self.encode(w))),bytes(w))

    def test_reserved_and_unused_extension_bytes_are_rejected_and_zeroed(self):
        for op in [7,8]:
            w=candidate(op,compare=0 if op==8 else 1)
            for off in [*range(52,56),*range(80,128),*(range(64,72)if op==8 else [])]:
                data=bytearray(oracle(w));data[off]=0x80
                with self.subTest(opcode=op,offset=off):self.decode(data,-errno.EINVAL)
        w=AtomicWQE(base.candidate(),0,0)
        for off in range(64,80):
            data=bytearray(oracle(w));data[off]=1;self.decode(data,-errno.EINVAL)

    def test_legacy64_APIs_still_refuse_atomic_operations(self):
        for op in [7,8]:
            w=candidate(op,compare=0 if op==8 else 1)
            for profile in [0,1]:
                out=(C.c_uint8*64)(*([0xa5]*64))
                self.assertEqual(self.lib.as02_wqe_encode_profile(out,C.byref(w.base),profile),-errno.EOPNOTSUPP)
                self.assertEqual(bytes(out),bytes(64))

    def test_overlapping_input_output_is_supported(self):
        store=(C.c_uint8*256)();w=candidate();wanted=oracle(w)
        C.memmove(C.byref(store),C.byref(w),C.sizeof(w));alias=C.cast(store,C.POINTER(AtomicWQE))
        self.assertEqual(self.lib.as02_atomic_wqe_encode(store,alias),0);self.assertEqual(bytes(store[:128]),wanted)
        self.assertEqual(self.lib.as02_atomic_wqe_decode(alias,store),0);self.assertEqual(bytes(alias.contents),bytes(w))

    def test_null_inputs_zero_the_complete_outputs(self):
        out=(C.c_uint8*128)(*([0xa5]*128));w=AtomicWQE();C.memset(C.byref(w),0xa5,C.sizeof(w))
        self.assertEqual(self.lib.as02_atomic_wqe_encode(out,None),-errno.EINVAL);self.assertEqual(bytes(out),bytes(128))
        self.assertEqual(self.lib.as02_atomic_wqe_decode(C.byref(w),None),-errno.EINVAL);self.assertEqual(bytes(w),bytes(C.sizeof(w)))
        self.assertEqual(self.lib.as02_atomic_wqe_encode(None,None),-errno.EINVAL)
        self.assertEqual(self.lib.as02_atomic_wqe_decode(None,None),-errno.EINVAL)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve prior evidence')
    files=[KERNEL/n for n in ['wqe.c','wqe.h','wqe_atomic.c','wqe_atomic.h']]+[Path(__file__).resolve(),Path(base.__file__).resolve()]
    def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
    before={str(path.relative_to(ROOT)):digest(path)for path in files};start=time.monotonic()
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(AtomicWQETests))
    if before!={str(path.relative_to(ROOT)):digest(path)for path in files}:raise ValueError('source changed')
    report=dict(scope=__doc__,pass_test=result.wasSuccessful(),methods=result.testsRun,seconds=time.monotonic()-start,
        source_sha256=before,C_UBSan=True,descriptor_bytes=128,legacy64_unchanged=True,
        native_requester_integrated=False,hardware_verified=False,standard_API_runtime=False)
    with a.report.open('x')as f:f.write(json.dumps(report,indent=2)+'\n')
    raise SystemExit(not result.wasSuccessful())
