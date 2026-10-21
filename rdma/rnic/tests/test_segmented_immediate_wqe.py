#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual source-only Immediate C128 codec, UBSan and all20 old methods.

Independent full bytes/64-bit ranges and unchanged old codec refusals. No
posting/MR/DMA/driver/provider/capability follows serialization success.
"""
import argparse
import ctypes as C
import errno
import json
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
import test_segmented_read_wqe as old

ROOT=old.ROOT;KERNEL=old.KERNEL;AtomicWQE=old.AtomicWQE;digest=old.digest
SOURCES=[*old.SOURCES,'wqe_segmented_immediate.c']


class SegmentedImmediateWQE(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory=tempfile.TemporaryDirectory(prefix='as02-segmented-immediate-wqe-');cls.path=Path(cls.directory.name)
        r=subprocess.run(['cc','-std=c11','-O2','-g','-Wall','-Wextra','-Werror','-shared','-fPIC',
            '-fsanitize=undefined','-fno-sanitize-recover=undefined','-I',str(KERNEL),
            *[str(KERNEL/n)for n in SOURCES],'-o',str(cls.path/'immediate.so')],capture_output=True,text=True,timeout=30)
        if r.returncode:raise ValueError(r.stdout+r.stderr)
        cls.lib=C.CDLL(str(cls.path/'immediate.so'))
        for prefix in ['as02_atomic_wqe','as02_zero_wqe','as02_segmented_wqe','as02_segmented_read_wqe','as02_segmented_immediate_wqe']:
            getattr(cls.lib,prefix+'_encode').argtypes=[C.POINTER(C.c_uint8),C.POINTER(AtomicWQE)]
            getattr(cls.lib,prefix+'_decode').argtypes=[C.POINTER(AtomicWQE),C.POINTER(C.c_uint8)]

    @classmethod
    def tearDownClass(cls):cls.directory.cleanup()

    @staticmethod
    def immediate(op=5,length=8193,**kwargs):
        w=old.old.SegmentedWQETests.large(3 if op==5 else 1,length,**kwargs)
        w.base.opcode=op;w.base.immediate=0x89abcdef;return w

    def encode(self,w,error=0):
        out=(C.c_uint8*128)(*([0xa5]*128));self.assertEqual(self.lib.as02_segmented_immediate_wqe_encode(out,C.byref(w)),error)
        self.assertEqual(bytes(out),old.old.old.old.oracle(w)if not error else bytes(128));return bytes(out)

    def decode(self,b,error=0):
        out=AtomicWQE();C.memset(C.byref(out),0xa5,C.sizeof(out));raw=(C.c_uint8*128).from_buffer_copy(b)
        self.assertEqual(self.lib.as02_segmented_immediate_wqe_decode(C.byref(out),raw),error)
        if error:self.assertEqual(bytes(out),bytes(C.sizeof(out)))
        return out

    def test_all_sizes_Immediate_values_full_bytes_roundtrip_and_old_refusals(self):
        for op in [5,6]:
            for length in [1,65,4096,4097,8192,8193,65537,1048576]:
                for imm in [0,0x89abcdef,0xffffffff]:
                    w=self.immediate(op,length);w.base.immediate=imm
                    raw=self.encode(w);self.assertEqual(bytes(self.decode(raw)),bytes(w))
                    if length>4096:
                        for prefix in ['as02_atomic_wqe','as02_zero_wqe','as02_segmented_wqe','as02_segmented_read_wqe']:
                            out=(C.c_uint8*128)(*([0xa5]*128));self.assertEqual(getattr(self.lib,prefix+'_encode')(out,C.byref(w)),-errno.EMSGSIZE)
                            self.assertEqual(bytes(out),bytes(128))

    def test_full64_inclusive_end_and_oversize_fail_closed(self):
        for op in [5,6]:
            for field in ['local_address']+(['remote_address']if op==6 else []):
                w=self.immediate(op);setattr(w.base,field,(1<<64)-8193)
                self.assertEqual(bytes(self.decode(self.encode(w))),bytes(w))
                setattr(w.base,field,(1<<64)-8192);self.encode(w,-errno.EFAULT)
                self.decode(old.old.old.old.oracle(w),-errno.EFAULT)
            w=self.immediate(op,1048577);self.encode(w,-errno.EMSGSIZE);self.decode(old.old.old.old.oracle(w),-errno.EMSGSIZE)

    def test_full_keys_remote_SEND_policy_and_atomic_operands(self):
        for key in [0,0x81234567,0xffffffff]:
            w=self.immediate(6,remote_key=key);self.assertEqual(bytes(self.decode(self.encode(w))),bytes(w))
        for field in ['remote_address','remote_key']:
            w=self.immediate(5);setattr(w.base,field,1);self.encode(w,-errno.EINVAL)
        for field in ['compare','swap_add']:
            w=self.immediate(6);setattr(w,field,1);self.encode(w,-errno.EINVAL)

    def test_reserved_flags_epoch_and_noncanonical_bytes(self):
        for field,value,error in [('sequence',0,-errno.EINVAL),('epoch',0,-errno.EINVAL),('flags',2,-errno.EOPNOTSUPP)]:
            w=self.immediate();setattr(w.base,field,value);self.encode(w,error)
        raw=self.encode(self.immediate())
        for offset in [*range(52,56),*range(80,128)]:
            b=bytearray(raw);b[offset]=0x80;self.decode(b,-errno.EINVAL)

    def test_all_old_operation_and_zero_policies_unchanged(self):
        for op in [1,2,3]:
            w=old.old.SegmentedWQETests.large(op);self.assertEqual(bytes(self.decode(self.encode(w))),bytes(w))
        for op in [1,2,3,5,6]:
            w=old.old.old.ZeroWQETests.zero(op);self.assertEqual(bytes(self.decode(self.encode(w))),bytes(w))
        for op in [7,8]:
            w=old.old.old.old.candidate(opcode=op,compare=0xfedcba9876543210 if op==7 else 0)
            self.assertEqual(bytes(self.decode(self.encode(w))),bytes(w))

    def test_alias_and_null_outputs_fully_zeroed(self):
        w=self.immediate();want=self.encode(w);raw=(C.c_uint8*256)();C.memmove(raw,C.byref(w),C.sizeof(w));alias=C.cast(raw,C.POINTER(AtomicWQE))
        self.assertEqual(self.lib.as02_segmented_immediate_wqe_encode(raw,alias),0);self.assertEqual(bytes(raw[:128]),want)
        self.assertEqual(self.lib.as02_segmented_immediate_wqe_decode(alias,raw),0);self.assertEqual(bytes(alias.contents),bytes(w))
        C.memset(raw,0xa5,128);self.assertEqual(self.lib.as02_segmented_immediate_wqe_encode(raw,None),-errno.EINVAL);self.assertEqual(bytes(raw[:128]),bytes(128))
        C.memset(C.byref(w),0xa5,C.sizeof(w));self.assertEqual(self.lib.as02_segmented_immediate_wqe_decode(C.byref(w),None),-errno.EINVAL);self.assertEqual(bytes(w),bytes(C.sizeof(w)))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve earlier evidence')
    files=[KERNEL/n for n in [*SOURCES,'wqe.h','wqe_atomic.h','wqe_zero.h','wqe_segmented.h','wqe_segmented_read.h','wqe_segmented_immediate.h']]
    files += [Path(m.__file__).resolve()for m in [old,old.old,old.old.old,old.old.old.old]]+[Path(__file__).resolve()]
    before={str(q.relative_to(ROOT)):digest(q)for q in files}
    suite=unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(old.old.SegmentedWQETests),
        unittest.defaultTestLoader.loadTestsFromTestCase(old.SegmentedReadWQE),unittest.defaultTestLoader.loadTestsFromTestCase(SegmentedImmediateWQE)])
    start=time.monotonic();r=unittest.TextTestRunner(verbosity=2).run(suite);same=all(digest(ROOT/n)==h for n,h in before.items())
    record=dict(scope=__doc__,pass_test=r.wasSuccessful()and same,methods=r.testsRun,seconds=time.monotonic()-start,
        source_sha256=before,source_unchanged=same,C_UBSan=True,independent_bytes=True,all20_prior_methods_retained=True,
        old_codecs_unchanged=True,descriptor_bytes=128,large_Immediate_max_bytes=1048576,default_profile_changed=False,
        native_runtime=False,hardware_verified=False,failures=[dict(test=str(t),trace=s)for t,s in r.failures+r.errors])
    with a.report.open('x')as f:f.write(json.dumps(record,indent=2)+'\n')
    raise SystemExit(not record['pass_test'])


if __name__=='__main__':main()
