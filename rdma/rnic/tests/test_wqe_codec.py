# SPDX-License-Identifier: BSD-2-Clause-Views
"""Execute shared WQE C/UBSan codec; kernel adapter is a separate compile gate.

No actual ib_send_wr callback, pinning, DMA, queue/provider/device or hardware.
Independent struct.pack oracle, boundary/invalid/overlap/round-trip cases.
"""
import ctypes as C
import errno
from pathlib import Path
import random
import struct
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[3]
KERNEL=ROOT/'rdma/rnic/kernel'
U64=(1<<64)-1


class WQE(C.Structure):
    _fields_=[(n,C.c_uint64)for n in ['wr_id','sequence','local_address','remote_address','epoch']]+[
        (n,C.c_uint32)for n in ['length','local_key','remote_key','opcode','flags','immediate']]


def candidate(**values):
    fields=dict(wr_id=0x8123456789abcdef,sequence=0xf123456700000001,
        local_address=0xf123456789abc001,remote_address=0xe23456789abcd002,
        epoch=0x9123456700000001,length=65,local_key=0x80000008,
        remote_key=0,opcode=1,flags=1)
    fields.update(values)
    return WQE(**fields)


def oracle(w):
    return struct.pack('<QQQQIIIHHQQ',w.wr_id,w.sequence,w.local_address,w.remote_address,
                       w.length,w.local_key,w.remote_key,w.opcode,w.flags,w.immediate,w.epoch)


class WQECodecTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory=tempfile.TemporaryDirectory(prefix='as02-wqe-codec-')
        cls.path=Path(cls.directory.name)
        result=subprocess.run(['cc','-std=c11','-O2','-g','-Wall','-Wextra','-Werror',
            '-shared','-fPIC','-fsanitize=undefined','-fno-sanitize-recover=undefined',
            '-I',str(KERNEL),str(KERNEL/'wqe.c'),'-o',str(cls.path/'wqe.so')],
            capture_output=True,text=True,timeout=30)
        if result.returncode:raise RuntimeError(result.stdout+result.stderr)
        cls.lib=C.CDLL(str(cls.path/'wqe.so'))
        cls.lib.as02_wqe_validate.argtypes=[C.POINTER(WQE)]
        cls.lib.as02_wqe_encode.argtypes=[C.POINTER(C.c_uint8),C.POINTER(WQE)]
        cls.lib.as02_wqe_decode.argtypes=[C.POINTER(WQE),C.POINTER(C.c_uint8)]
        for n in ['as02_wqe_validate','as02_wqe_encode','as02_wqe_decode']:
            getattr(cls.lib,n).restype=C.c_int

    @classmethod
    def tearDownClass(cls):cls.directory.cleanup()

    def encode(self,w,expected=0):
        output=(C.c_uint8*64)(*([0xa5]*64))
        result=self.lib.as02_wqe_encode(output,C.byref(w))
        self.assertEqual(result,expected)
        self.assertEqual(bytes(output),oracle(w) if expected==0 else bytes(64))
        return output

    def decode(self,data,expected=0):
        output=WQE();C.memset(C.byref(output),0xa5,C.sizeof(output))
        source=(C.c_uint8*64).from_buffer_copy(data)
        self.assertEqual(self.lib.as02_wqe_decode(C.byref(output),source),expected)
        if expected:self.assertEqual(bytes(output),bytes(C.sizeof(output)))
        return output

    def test_exact_little_endian_keys_full_widths_and_round_trip(self):
        self.assertEqual(C.sizeof(WQE),64)
        for opcode in [1,2]:
            for key in [0,0x80000000,0xffffffff,0x12345678]:
                for flags in [0,1]:
                    w=candidate(opcode=opcode,remote_key=key,flags=flags)
                    encoded=self.encode(w)
                    decoded=self.decode(encoded)
                    self.assertEqual([getattr(decoded,n)for n,_ in WQE._fields_],
                                     [getattr(w,n)for n,_ in WQE._fields_])

    def test_top_byte_nonwrapping_ranges_and_opaque_identifiers(self):
        for length in [1,2,65,4096]:
            w=candidate(local_address=U64-length+1,remote_address=U64-length+1,
                        length=length,wr_id=0,sequence=U64,epoch=U64)
            self.decode(self.encode(w))
        # Local key0 is not silently rewritten/authorized by the codec; the
        # actual MR validator must reject it when no matching registration.
        self.assertEqual(self.decode(self.encode(candidate(local_key=0))).local_key,0)

    def test_invalid_scalars_refuse_without_narrowing_and_zero_output(self):
        cases=[({'sequence':0},errno.EINVAL),({'epoch':0},errno.EINVAL),
            *[({'opcode':v},errno.EOPNOTSUPP)for v in [0,5,0x10001,0xffffffff]],
            *[({'flags':v},errno.EOPNOTSUPP)for v in [2,3,0x10001,0xffffffff]],
            *[({'length':v},errno.EMSGSIZE)for v in [0,4097,0xffffffff]],
            ({'local_address':U64,'length':2},errno.EFAULT),
            ({'remote_address':U64-63,'length':65},errno.EFAULT)]
        for fields,error in cases:
            with self.subTest(fields=fields):
                w=candidate(**fields)
                self.assertEqual(self.lib.as02_wqe_validate(C.byref(w)),-error)
                self.encode(w,-error)

    def test_untrusted_wire_reserved_opcode_flags_and_lengths_refused(self):
        initial=oracle(candidate())
        for offset in range(48,56):
            data=bytearray(initial);data[offset]=0x80
            self.decode(data,-errno.EINVAL)
        for offset,value,error in [(44,struct.pack('<H',5),errno.EOPNOTSUPP),
                (46,struct.pack('<H',2),errno.EOPNOTSUPP),
                (32,struct.pack('<I',0),errno.EMSGSIZE),(32,struct.pack('<I',4097),errno.EMSGSIZE),
                (8,bytes(8),errno.EINVAL),(56,bytes(8),errno.EINVAL),
                (16,struct.pack('<Q',U64),errno.EFAULT)]:
            data=bytearray(initial);data[offset:offset+len(value)]=value
            self.decode(data,-error)

    def test_SEND_has_canonical_zero_remote_fields_and_full_local_authority(self):
        w=candidate(opcode=3,remote_address=0,remote_key=0)
        self.encode(w);self.decode(oracle(w))
        for fields in [dict(remote_address=1),dict(remote_key=1),dict(remote_key=0xffffffff)]:
            bad=candidate(opcode=3,remote_address=0,remote_key=0)
            for name,value in fields.items():setattr(bad,name,value)
            self.encode(bad,-errno.EINVAL)
            self.decode(oracle(bad),-errno.EINVAL)

    def test_RECV_retains_full_buffer_capacity_and_requires_canonical_signaled_record(self):
        w=candidate(opcode=4,remote_address=0,remote_key=0,length=128,flags=1)
        self.encode(w);self.decode(oracle(w))
        for field,value in [('remote_address',1),('remote_key',1),('flags',0)]:
            bad=candidate(opcode=4,remote_address=0,remote_key=0,length=128,flags=1)
            setattr(bad,field,value);self.encode(bad,-errno.EINVAL);self.decode(oracle(bad),-errno.EINVAL)

    def test_null_and_exact_alias_buffers_are_safe_and_fail_closed(self):
        output=(C.c_uint8*64)(*([0xa5]*64))
        self.assertEqual(self.lib.as02_wqe_encode(output,None),-errno.EINVAL)
        self.assertEqual(bytes(output),bytes(64))
        w=candidate();expected=oracle(w)
        self.assertEqual(self.lib.as02_wqe_encode(None,C.byref(w)),-errno.EINVAL)
        self.assertEqual(self.lib.as02_wqe_validate(None),-errno.EINVAL)
        self.assertEqual(self.lib.as02_wqe_decode(None,output),-errno.EINVAL)
        self.assertEqual(self.lib.as02_wqe_decode(C.byref(w),None),-errno.EINVAL)
        self.assertEqual(bytes(w),bytes(C.sizeof(w)))
        w=candidate();alias=C.cast(C.byref(w),C.POINTER(C.c_uint8))
        self.assertEqual(self.lib.as02_wqe_encode(alias,C.byref(w)),0)
        self.assertEqual(bytes(w),expected)
        self.assertEqual(self.lib.as02_wqe_decode(C.byref(w),alias),0)
        self.assertEqual(oracle(w),expected)

    def test_seeded_random_actual_C_against_independent_oracle(self):
        rng=random.Random(0x455a5741)
        for _ in range(1000):
            length=rng.randint(1,4096)
            w=candidate(wr_id=rng.getrandbits(64),sequence=rng.randint(1,U64),
                epoch=rng.randint(1,U64),local_address=rng.randrange(U64-length+2),
                remote_address=rng.randrange(U64-length+2),length=length,
                local_key=rng.getrandbits(32),remote_key=rng.getrandbits(32),
                opcode=rng.choice([1,2]),flags=rng.randrange(2))
            self.assertEqual(oracle(self.decode(self.encode(w))),oracle(w))

    def test_kernel_adapter_is_truthfully_separate_and_refuses_extra_features(self):
        # Static routing/refusal check ONLY; actual Linux API compilation is
        # recorded separately and no kernel callback/module executes here.
        text=(KERNEL/'verbs_wqe.c').read_text()
        for token in ['#include <rdma/ib_verbs.h>','rdma_wr(wr)','wr->num_sge != 1',
                      'wr->send_flags & ~IB_SEND_SIGNALED','rdma->remote_addr',
                      'rdma->rkey','wr->sg_list[0].lkey','wr->sg_list[0].addr']:
            self.assertIn(token,text)
        self.assertNotIn('ib_register_device(',text)
        self.assertNotIn('ib_post_send(',text)
        self.assertIn('wqe.o verbs_wqe.o',(KERNEL/'Makefile').read_text())


if __name__=='__main__':unittest.main()
