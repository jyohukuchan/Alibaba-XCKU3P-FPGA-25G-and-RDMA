#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Private full-range C128 WRITE/SEND codec, real C/UBSan/independent bytes.

Retain all inherited zero/Atomic cases; no posting/MR/DMA/hardware authority.
Old codecs still refuse large work. Installed/default profiles are unchanged.
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
import test_zero_wqe as old

ROOT=old.ROOT;KERNEL=old.KERNEL;AtomicWQE=old.old.AtomicWQE


class SegmentedWQETests(old.ZeroWQETests):
    @classmethod
    def setUpClass(cls):
        cls.directory=tempfile.TemporaryDirectory(prefix='as02-segmented-wqe-');cls.path=Path(cls.directory.name)
        c=subprocess.run(['cc','-std=c11','-O2','-g','-Wall','-Wextra','-Werror','-shared','-fPIC',
            '-fsanitize=undefined','-fno-sanitize-recover=undefined','-I',str(KERNEL),
            *[str(KERNEL/n)for n in ['wqe.c','wqe_atomic.c','wqe_zero.c','wqe_segmented.c']],'-o',str(cls.path/'segmented.so')],
            capture_output=True,text=True,timeout=30)
        if c.returncode:raise ValueError(c.stdout+c.stderr)
        cls.lib=C.CDLL(str(cls.path/'segmented.so'))
        for prefix in ['as02_atomic_wqe','as02_zero_wqe','as02_segmented_wqe']:
            getattr(cls.lib,prefix+'_encode').argtypes=[C.POINTER(C.c_uint8),C.POINTER(AtomicWQE)]
            getattr(cls.lib,prefix+'_decode').argtypes=[C.POINTER(AtomicWQE),C.POINTER(C.c_uint8)]
        cls.lib.as02_wqe_encode_profile.argtypes=[C.POINTER(C.c_uint8),C.POINTER(old.old.base.WQE),C.c_uint32]

    def encode(self,w,error=0):
        out=(C.c_uint8*128)(*([0xa5]*128));self.assertEqual(self.lib.as02_segmented_wqe_encode(out,C.byref(w)),error)
        self.assertEqual(bytes(out),old.old.oracle(w)if not error else bytes(128));return bytes(out)

    def decode(self,data,error=0):
        out=AtomicWQE();C.memset(C.byref(out),0xa5,C.sizeof(out));raw=(C.c_uint8*128).from_buffer_copy(data)
        self.assertEqual(self.lib.as02_segmented_wqe_decode(C.byref(out),raw),error)
        if error:self.assertEqual(bytes(out),bytes(C.sizeof(out)))
        return out

    @staticmethod
    def large(op=1,length=8193,**values):
        fields=dict(opcode=op,length=length,remote_address=0 if op==3 else 0xe23456789abcdef0,
            remote_key=0 if op==3 else 0x81234567)
        fields.update(values)
        return AtomicWQE(old.old.base.candidate(**fields),0,0)

    def test_large_WRITE_SEND_full_range_and_independent128_bytes(self):
        for op in [1,3]:
            for length in [4097,8192,8193,65537,1048576]:
                w=self.large(op,length);self.assertEqual(bytes(self.decode(self.encode(w))),bytes(w))
                for prefix in ['as02_atomic_wqe','as02_zero_wqe']:
                    out=(C.c_uint8*128)(*([0xa5]*128))
                    self.assertEqual(getattr(self.lib,prefix+'_encode')(out,C.byref(w)),-errno.EMSGSIZE)
                    self.assertEqual(bytes(out),bytes(128))

    def test_large_real_range_wrap_top_byte_and_other_operations(self):
        for field in ['local_address','remote_address']:
            w=self.large();setattr(w.base,field,(1<<64)-8193)
            self.assertEqual(bytes(self.decode(self.encode(w))),bytes(w))
            setattr(w.base,field,(1<<64)-8192);self.encode(w,-errno.EFAULT);self.decode(old.old.oracle(w),-errno.EFAULT)
        self.encode(self.large(length=1048577),-errno.EMSGSIZE)
        for op in [2,4,5,6,7,8]:
            w=self.large();w.base.opcode=op
            if op in [4,5]:w.base.remote_address=0;w.base.remote_key=0
            self.encode(w,-errno.EMSGSIZE);self.decode(old.old.oracle(w),-errno.EMSGSIZE)

    def test_large_canonical_flags_operands_epoch_and_padding(self):
        for field,value,error in [('sequence',0,-errno.EINVAL),('epoch',0,-errno.EINVAL),('flags',2,-errno.EOPNOTSUPP),('immediate',1,-errno.EINVAL)]:
            w=self.large();setattr(w.base,field,value);self.encode(w,error);self.decode(old.old.oracle(w),error)
        for field in ['compare','swap_add']:
            w=self.large();setattr(w,field,1);self.encode(w,-errno.EINVAL);self.decode(old.old.oracle(w),-errno.EINVAL)
        for field in ['remote_address','remote_key']:
            w=self.large(3);setattr(w.base,field,1);self.encode(w,-errno.EINVAL);self.decode(old.old.oracle(w),-errno.EINVAL)
        data=old.old.oracle(self.large())
        for offset in [*range(52,56),*range(80,128)]:
            b=bytearray(data);b[offset]=0x80;self.decode(b,-errno.EINVAL)

    def test_large_alias_null_and_fully_zeroed_error_outputs(self):
        w=self.large();want=old.old.oracle(w);raw=(C.c_uint8*256)();C.memmove(raw,C.byref(w),C.sizeof(w));alias=C.cast(raw,C.POINTER(AtomicWQE))
        self.assertEqual(self.lib.as02_segmented_wqe_encode(raw,alias),0);self.assertEqual(bytes(raw[:128]),want)
        self.assertEqual(self.lib.as02_segmented_wqe_decode(alias,raw),0);self.assertEqual(bytes(alias.contents),bytes(w))
        C.memset(raw,0xa5,128);self.assertEqual(self.lib.as02_segmented_wqe_encode(raw,None),-errno.EINVAL);self.assertEqual(bytes(raw[:128]),bytes(128))
        C.memset(C.byref(w),0xa5,C.sizeof(w));self.assertEqual(self.lib.as02_segmented_wqe_decode(C.byref(w),None),-errno.EINVAL);self.assertEqual(bytes(w),bytes(C.sizeof(w)))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve prior evidence')
    files=[KERNEL/n for n in ['wqe.c','wqe.h','wqe_atomic.c','wqe_atomic.h','wqe_zero.c','wqe_zero.h','wqe_segmented.c','wqe_segmented.h']]+[Path(__file__).resolve(),Path(old.__file__).resolve(),Path(old.old.__file__).resolve()]
    before={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest()for f in files}
    start=time.monotonic();r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(SegmentedWQETests))
    if before!={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest()for n in before}:raise ValueError('codec source changed')
    with a.report.open('x')as f:f.write(json.dumps(dict(scope=__doc__,pass_test=r.wasSuccessful(),methods=r.testsRun,seconds=time.monotonic()-start,source_sha256=before,UBSan=True,native_or_hardware=False,old_codecs_unchanged=True),indent=2)+'\n')
    raise SystemExit(0 if r.wasSuccessful()else 1)


if __name__=='__main__':main()
