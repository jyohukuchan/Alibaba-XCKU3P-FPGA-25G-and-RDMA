#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual private READ C128 codec plus unchanged full prior codec regression.

UBSan, independent bytes/full ranges, explicit old READ refusal. No post/MR/
DMA/driver/provider/device/hardware capability follows serialization success.
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
import test_segmented_wqe as old

ROOT=old.ROOT;KERNEL=old.KERNEL;AtomicWQE=old.AtomicWQE
digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
SOURCES=['wqe.c','wqe_atomic.c','wqe_zero.c','wqe_segmented.c','wqe_segmented_read.c']


class SegmentedReadWQE(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory=tempfile.TemporaryDirectory(prefix='as02-segmented-read-wqe-');cls.path=Path(cls.directory.name)
        r=subprocess.run(['cc','-std=c11','-O2','-g','-Wall','-Wextra','-Werror','-shared','-fPIC',
            '-fsanitize=undefined','-fno-sanitize-recover=undefined','-I',str(KERNEL),
            *[str(KERNEL/n)for n in SOURCES],'-o',str(cls.path/'read.so')],capture_output=True,text=True,timeout=30)
        if r.returncode:raise ValueError(r.stdout+r.stderr)
        cls.lib=C.CDLL(str(cls.path/'read.so'))
        for prefix in ['as02_atomic_wqe','as02_zero_wqe','as02_segmented_wqe','as02_segmented_read_wqe']:
            getattr(cls.lib,prefix+'_encode').argtypes=[C.POINTER(C.c_uint8),C.POINTER(AtomicWQE)]
            getattr(cls.lib,prefix+'_decode').argtypes=[C.POINTER(AtomicWQE),C.POINTER(C.c_uint8)]

    @classmethod
    def tearDownClass(cls):cls.directory.cleanup()

    @staticmethod
    def read(length=8193,**kwargs):return old.SegmentedWQETests.large(2,length,**kwargs)

    def encode(self,w,error=0):
        out=(C.c_uint8*128)(*([0xa5]*128));self.assertEqual(self.lib.as02_segmented_read_wqe_encode(out,C.byref(w)),error)
        self.assertEqual(bytes(out),old.old.old.oracle(w)if not error else bytes(128));return bytes(out)

    def decode(self,b,error=0):
        out=AtomicWQE();C.memset(C.byref(out),0xa5,C.sizeof(out));raw=(C.c_uint8*128).from_buffer_copy(b)
        self.assertEqual(self.lib.as02_segmented_read_wqe_decode(C.byref(out),raw),error)
        if error:self.assertEqual(bytes(out),bytes(C.sizeof(out)))
        return out

    def test_READ_all_lengths_independent_bytes_and_all_old_codecs_refuse_large_READ(self):
        for length in [1,65,4096,4097,8192,8193,65537,1048576]:
            for key in [0,0x81234567,0xffffffff]:
                w=self.read(length,remote_key=key);raw=self.encode(w);self.assertEqual(bytes(self.decode(raw)),bytes(w))
                if length>4096:
                    for prefix in ['as02_atomic_wqe','as02_zero_wqe','as02_segmented_wqe']:
                        out=(C.c_uint8*128)(*([0xa5]*128));self.assertEqual(getattr(self.lib,prefix+'_encode')(out,C.byref(w)),-errno.EMSGSIZE)
                        self.assertEqual(bytes(out),bytes(128))

    def test_READ_full64_ranges_top_byte_and_actual_overflow(self):
        for field in ['local_address','remote_address']:
            w=self.read();setattr(w.base,field,(1<<64)-8193)
            self.assertEqual(bytes(self.decode(self.encode(w))),bytes(w))
            setattr(w.base,field,(1<<64)-8192);self.encode(w,-errno.EFAULT);self.decode(old.old.old.oracle(w),-errno.EFAULT)
        self.encode(self.read(1048577),-errno.EMSGSIZE);self.decode(old.old.old.oracle(self.read(1048577)),-errno.EMSGSIZE)

    def test_READ_canonical_flags_epoch_operands_immediate_and_reserved_bytes(self):
        for field,value,error in [('sequence',0,-errno.EINVAL),('epoch',0,-errno.EINVAL),('flags',2,-errno.EOPNOTSUPP),('immediate',1,-errno.EINVAL)]:
            w=self.read();setattr(w.base,field,value);self.encode(w,error);self.decode(old.old.old.oracle(w),error)
        for field in ['compare','swap_add']:
            w=self.read();setattr(w,field,1);self.encode(w,-errno.EINVAL);self.decode(old.old.old.oracle(w),-errno.EINVAL)
        raw=self.encode(self.read())
        for offset in [*range(52,56),*range(80,128)]:
            b=bytearray(raw);b[offset]=0x80;self.decode(b,-errno.EINVAL)

    def test_old_operations_and_zero_READ_policies_are_unchanged(self):
        for op in [1,3]:
            w=old.SegmentedWQETests.large(op);self.assertEqual(bytes(self.decode(self.encode(w))),bytes(w))
        w=old.old.ZeroWQETests.zero(2);self.assertEqual(bytes(self.decode(self.encode(w))),bytes(w))
        for op in [4,5,6,7,8]:
            w=old.SegmentedWQETests.large(1);w.base.opcode=op
            if op in [4,5]:w.base.remote_address=0;w.base.remote_key=0
            self.encode(w,-errno.EMSGSIZE);self.decode(old.old.old.oracle(w),-errno.EMSGSIZE)

    def test_alias_null_outputs_fully_zeroed(self):
        w=self.read();want=self.encode(w);raw=(C.c_uint8*256)();C.memmove(raw,C.byref(w),C.sizeof(w));alias=C.cast(raw,C.POINTER(AtomicWQE))
        self.assertEqual(self.lib.as02_segmented_read_wqe_encode(raw,alias),0);self.assertEqual(bytes(raw[:128]),want)
        self.assertEqual(self.lib.as02_segmented_read_wqe_decode(alias,raw),0);self.assertEqual(bytes(alias.contents),bytes(w))
        C.memset(raw,0xa5,128);self.assertEqual(self.lib.as02_segmented_read_wqe_encode(raw,None),-errno.EINVAL);self.assertEqual(bytes(raw[:128]),bytes(128))
        C.memset(C.byref(w),0xa5,C.sizeof(w));self.assertEqual(self.lib.as02_segmented_read_wqe_decode(C.byref(w),None),-errno.EINVAL);self.assertEqual(bytes(w),bytes(C.sizeof(w)))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve earlier evidence')
    files=[KERNEL/n for n in [*SOURCES,'wqe.h','wqe_atomic.h','wqe_zero.h','wqe_segmented.h','wqe_segmented_read.h']]
    files += [Path(__file__).resolve(),Path(old.__file__).resolve(),Path(old.old.__file__).resolve(),Path(old.old.old.__file__).resolve()]
    before={str(q.relative_to(ROOT)):digest(q)for q in files}
    suite=unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(old.SegmentedWQETests),
        unittest.defaultTestLoader.loadTestsFromTestCase(SegmentedReadWQE)])
    start=time.monotonic();r=unittest.TextTestRunner(verbosity=2).run(suite);same=all(digest(ROOT/n)==h for n,h in before.items())
    record=dict(scope=__doc__,pass_test=r.wasSuccessful()and same,methods=r.testsRun,seconds=time.monotonic()-start,
        source_sha256=before,source_unchanged=same,C_UBSan=True,independent_bytes=True,
        all15_prior_segmented_methods_retained=True,old_codecs_unchanged=True,descriptor_bytes=128,
        large_READ_max_bytes=1048576,default_profile_changed=False,native_runtime=False,hardware_verified=False,
        failures=[dict(test=str(t),trace=s)for t,s in r.failures+r.errors])
    with a.report.open('x')as f:f.write(json.dumps(record,indent=2)+'\n')
    raise SystemExit(not record['pass_test'])


if __name__=='__main__':main()
