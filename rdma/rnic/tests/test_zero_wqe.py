# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual zero-aware C128 codec, independent byte oracle and UBSan.

Retain all seven prior Atomic codec methods; test new zero canonical forms,
ignored remote fields, malformed padding/local authority and alias/nulls.
No posting, MR, DMA, native or device-capability claim follows this codec.
"""
import argparse
import ctypes as C
import errno
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
import test_atomic_wqe as old

ROOT=old.ROOT;KERNEL=old.KERNEL


class ZeroWQETests(old.AtomicWQETests):
    @classmethod
    def setUpClass(cls):
        cls.directory=tempfile.TemporaryDirectory(prefix='as02-zero-wqe-');cls.path=Path(cls.directory.name)
        r=subprocess.run(['cc','-std=c11','-O2','-g','-Wall','-Wextra','-Werror','-shared','-fPIC',
            '-fsanitize=undefined','-fno-sanitize-recover=undefined','-I',str(KERNEL),
            *[str(KERNEL/n)for n in ['wqe.c','wqe_atomic.c','wqe_zero.c']],'-o',str(cls.path/'zero.so')],
            capture_output=True,text=True,timeout=30)
        if r.returncode:raise ValueError(r.stdout+r.stderr)
        cls.lib=C.CDLL(str(cls.path/'zero.so'))
        for prefix in ['as02_atomic_wqe','as02_zero_wqe']:
            getattr(cls.lib,prefix+'_encode').argtypes=[C.POINTER(C.c_uint8),C.POINTER(old.AtomicWQE)]
            getattr(cls.lib,prefix+'_decode').argtypes=[C.POINTER(old.AtomicWQE),C.POINTER(C.c_uint8)]
        cls.lib.as02_wqe_encode_profile.argtypes=[C.POINTER(C.c_uint8),C.POINTER(old.base.WQE),C.c_uint32]

    def encode(self,w,error=0):
        out=(C.c_uint8*128)(*([0xa5]*128))
        self.assertEqual(self.lib.as02_zero_wqe_encode(out,C.byref(w)),error)
        self.assertEqual(bytes(out),old.oracle(w)if not error else bytes(128));return bytes(out)

    def decode(self,data,error=0):
        out=old.AtomicWQE();C.memset(C.byref(out),0xa5,C.sizeof(out));raw=(C.c_uint8*128).from_buffer_copy(data)
        self.assertEqual(self.lib.as02_zero_wqe_decode(C.byref(out),raw),error)
        if error:self.assertEqual(bytes(out),bytes(C.sizeof(out)))
        return out

    @staticmethod
    def zero(op):
        b=old.base.candidate(opcode=op,length=0,local_address=0,local_key=0,
            remote_address=old.base.U64 if op in [1,2,6]else 0,
            remote_key=0xfedcba98 if op in [1,2,6]else 0,immediate=0x89abcdef if op in [5,6]else 0)
        return old.AtomicWQE(b,0,0)

    def test_all_zero_operations_exact_independent128_bytes_and_top_remote_VA(self):
        for op in range(1,7):
            for key in [0,0x80000001,0xffffffff]:
                w=self.zero(op)
                if op in [1,2,6]:w.base.remote_key=key
                with self.subTest(op=op,key=key):
                    self.assertEqual(bytes(self.decode(self.encode(w))),bytes(w))

    def test_zero_local_authority_reserved_and_operand_bytes_are_never_accepted(self):
        for op in range(1,7):
            w=self.zero(op)
            for off in [*range(16,24),*range(32,40),*range(52,56),*range(64,128)]:
                if off in range(32,36):continue # Nonzero lengths deliberately use the old format.
                bad=bytearray(old.oracle(w));bad[off]=0x80
                with self.subTest(op=op,offset=off):self.decode(bad,-errno.EINVAL)

    def test_zero_alias_and_null_error_outputs_remain_fully_zeroed(self):
        w=self.zero(2);wanted=old.oracle(w);data=(C.c_uint8*256)()
        C.memmove(data,C.byref(w),C.sizeof(w));alias=C.cast(data,C.POINTER(old.AtomicWQE))
        self.assertEqual(self.lib.as02_zero_wqe_encode(data,alias),0);self.assertEqual(bytes(data[:128]),wanted)
        self.assertEqual(self.lib.as02_zero_wqe_decode(alias,data),0);self.assertEqual(bytes(alias.contents),bytes(w))
        C.memset(data,0xa5,128);self.assertEqual(self.lib.as02_zero_wqe_encode(data,None),-errno.EINVAL)
        self.assertEqual(bytes(data[:128]),bytes(128))
        C.memset(C.byref(w),0xa5,C.sizeof(w));self.assertEqual(self.lib.as02_zero_wqe_decode(C.byref(w),None),-errno.EINVAL)
        self.assertEqual(bytes(w),bytes(C.sizeof(w)))

    def test_old_nonzero_codecs_still_refuse_zero_requests(self):
        for op in range(1,7):
            w=self.zero(op);out=(C.c_uint8*128)(*([0xa5]*128))
            self.assertEqual(self.lib.as02_atomic_wqe_encode(out,C.byref(w)),-errno.EMSGSIZE)
            self.assertEqual(bytes(out),bytes(128))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve previous evidence')
    files=[KERNEL/n for n in ['wqe.c','wqe.h','wqe_atomic.c','wqe_atomic.h','wqe_zero.c','wqe_zero.h']]+[Path(__file__).resolve(),Path(old.__file__).resolve(),Path(old.base.__file__).resolve()]
    digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    before={str(p.relative_to(ROOT)):digest(p)for p in files};start=time.monotonic()
    r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ZeroWQETests))
    if any(digest(ROOT/n)!=h for n,h in before.items()):raise ValueError('source changed')
    with a.report.open('x')as f:f.write(json.dumps(dict(scope=__doc__,pass_test=r.wasSuccessful(),methods=r.testsRun,
        seconds=time.monotonic()-start,source_sha256=before,C_UBSan=True,descriptor_bytes=128,
        independent_byte_oracle=True,default_codecs_unchanged=True,native_requester_integrated=False,hardware_verified=False),indent=2)+'\n')
    raise SystemExit(not r.wasSuccessful())
