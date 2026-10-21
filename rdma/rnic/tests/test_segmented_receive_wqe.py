#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual full-range RECV C128 codec/UBSan and ALL26 old codec methods.

Check complete independent bytes, full64 inclusive ranges, canonical zero
and null/alias failure clearing. No MR/DMA or installed API/capability claim.
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
import test_segmented_immediate_wqe as old

ROOT=old.ROOT;KERNEL=old.KERNEL;AtomicWQE=old.AtomicWQE;digest=old.digest
SOURCES=[*old.SOURCES,'wqe_segmented_receive.c']


class SegmentedReceiveWQE(old.SegmentedImmediateWQE):
    @classmethod
    def setUpClass(cls):
        cls.directory=tempfile.TemporaryDirectory(prefix='as02-segmented-receive-wqe-');cls.path=Path(cls.directory.name)
        c=subprocess.run(['cc','-std=c11','-O2','-g','-Wall','-Wextra','-Werror','-shared','-fPIC',
            '-fsanitize=undefined','-fno-sanitize-recover=undefined','-I',str(KERNEL),
            *[str(KERNEL/n)for n in SOURCES],'-o',str(cls.path/'receive.so')],capture_output=True,text=True,timeout=30)
        if c.returncode:raise ValueError(c.stdout+c.stderr)
        cls.lib=C.CDLL(str(cls.path/'receive.so'))
        for prefix in ['as02_atomic_wqe','as02_zero_wqe','as02_segmented_wqe','as02_segmented_read_wqe',
                       'as02_segmented_immediate_wqe','as02_segmented_receive_wqe']:
            getattr(cls.lib,prefix+'_encode').argtypes=[C.POINTER(C.c_uint8),C.POINTER(AtomicWQE)]
            getattr(cls.lib,prefix+'_decode').argtypes=[C.POINTER(AtomicWQE),C.POINTER(C.c_uint8)]

    @staticmethod
    def receive(length=8193,**kwargs):
        w=old.old.old.SegmentedWQETests.large(3,length,**kwargs);w.base.opcode=4
        if not length:w.base.local_address=0;w.base.local_key=0
        return w

    def encode(self,w,error=0):
        raw=(C.c_uint8*128)(*([0xa5]*128));self.assertEqual(self.lib.as02_segmented_receive_wqe_encode(raw,C.byref(w)),error)
        self.assertEqual(bytes(raw),old.old.old.old.old.oracle(w)if not error else bytes(128));return bytes(raw)

    def decode(self,b,error=0):
        out=AtomicWQE();C.memset(C.byref(out),0xa5,C.sizeof(out));raw=(C.c_uint8*128).from_buffer_copy(b)
        self.assertEqual(self.lib.as02_segmented_receive_wqe_decode(C.byref(out),raw),error)
        if error:self.assertEqual(bytes(out),bytes(C.sizeof(out)))
        return out

    def test_receive_all_sizes_full_keys_whole_bytes_and_all_old_refusals(self):
        for length in [0,1,65,4096,4097,8192,8193,65537,1048576]:
            for key in [0,0x81234567,0xffffffff]:
                w=self.receive(length);w.base.local_key=key if length else 0
                raw=self.encode(w);self.assertEqual(bytes(self.decode(raw)),bytes(w))
                if length>4096:
                    for prefix in ['as02_atomic_wqe','as02_zero_wqe','as02_segmented_wqe','as02_segmented_read_wqe','as02_segmented_immediate_wqe']:
                        out=(C.c_uint8*128)(*([0xa5]*128));self.assertEqual(getattr(self.lib,prefix+'_encode')(out,C.byref(w)),-errno.EMSGSIZE)
                        self.assertEqual(bytes(out),bytes(128))

    def test_receive_full64_inclusive_end_and_oversize(self):
        for length in [4097,8193,1048576]:
            w=self.receive(length,local_address=(1<<64)-length);self.assertEqual(bytes(self.decode(self.encode(w))),bytes(w))
            w.base.local_address+=1;self.encode(w,-errno.EFAULT);self.decode(old.old.old.old.old.oracle(w),-errno.EFAULT)
        w=self.receive(1048577);self.encode(w,-errno.EMSGSIZE);self.decode(old.old.old.old.old.oracle(w),-errno.EMSGSIZE)

    def test_receive_no_remote_immediate_Atomic_or_wrong_signal_policy(self):
        for field in ['remote_address','remote_key','immediate']:
            w=self.receive();setattr(w.base,field,1);self.encode(w,-errno.EINVAL)
        for field in ['compare','swap_add']:
            w=self.receive();setattr(w,field,1);self.encode(w,-errno.EINVAL)
        for flags in [0,2,3,0xffff]:
            w=self.receive(flags=flags);self.encode(w,-errno.EINVAL)
        for field in ['sequence','epoch']:
            w=self.receive();setattr(w.base,field,0);self.encode(w,-errno.EINVAL)

    def test_receive_noncanonical_reserved_bytes_and_zero_preserved(self):
        raw=self.encode(self.receive())
        for offset in [*range(52,56),*range(64,128)]:
            b=bytearray(raw);b[offset]=0x80;self.decode(b,-errno.EINVAL)
        w=self.receive(0);self.assertEqual(bytes(self.decode(self.encode(w))),bytes(w))
        for field in ['local_address','local_key']:
            w=self.receive(0);setattr(w.base,field,1);self.encode(w,-errno.EINVAL)

    def test_receive_alias_and_null_clear_every_output_byte(self):
        w=self.receive();expected=self.encode(w);raw=(C.c_uint8*256)();C.memmove(raw,C.byref(w),C.sizeof(w));alias=C.cast(raw,C.POINTER(AtomicWQE))
        self.assertEqual(self.lib.as02_segmented_receive_wqe_encode(raw,alias),0);self.assertEqual(bytes(raw[:128]),expected)
        self.assertEqual(self.lib.as02_segmented_receive_wqe_decode(alias,raw),0);self.assertEqual(bytes(alias.contents),bytes(w))
        C.memset(raw,0xa5,128);self.assertEqual(self.lib.as02_segmented_receive_wqe_encode(raw,None),-errno.EINVAL);self.assertEqual(bytes(raw[:128]),bytes(128))
        C.memset(C.byref(w),0xa5,C.sizeof(w));self.assertEqual(self.lib.as02_segmented_receive_wqe_decode(C.byref(w),None),-errno.EINVAL);self.assertEqual(bytes(w),bytes(C.sizeof(w)))
        self.assertEqual(self.lib.as02_segmented_receive_wqe_encode(None,C.byref(w)),-errno.EINVAL)
        self.assertEqual(self.lib.as02_segmented_receive_wqe_decode(None,raw),-errno.EINVAL)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve earlier evidence')
    files=[KERNEL/n for n in SOURCES]+list(KERNEL.glob('wqe*.h'))+[Path(m.__file__).resolve()for m in
        [old,old.old,old.old.old,old.old.old.old,old.old.old.old.old]]+[Path(__file__).resolve()]
    before={str(q.relative_to(ROOT)):digest(q)for q in files}
    classes=[old.old.old.SegmentedWQETests,old.old.SegmentedReadWQE,old.SegmentedImmediateWQE,SegmentedReceiveWQE]
    suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromTestCase(c)for c in classes)
    start=time.monotonic();r=unittest.TextTestRunner(verbosity=2).run(suite);same=all(digest(ROOT/n)==h for n,h in before.items())
    report=dict(scope=__doc__,pass_test=r.wasSuccessful()and same,methods=r.testsRun,seconds=time.monotonic()-start,
        source_sha256=before,source_unchanged=same,C_UBSan=True,all26_old_methods_retained=True,
        old6_Immediate_methods_rerun_via_new_codec=True,receive_source_limit=1048576,descriptor_bytes=128,
        actual_MR_or_native_or_installed_profile=False,hardware_verified=False,
        failures=[dict(test=str(t),trace=s)for t,s in r.failures+r.errors])
    with a.report.open('x')as f:f.write(json.dumps(report,indent=2)+'\n')
    raise SystemExit(not report['pass_test'])


if __name__=='__main__':main()
