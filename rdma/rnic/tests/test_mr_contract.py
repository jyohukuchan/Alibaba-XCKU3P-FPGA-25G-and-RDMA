# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual shared kernel/user C MR contract; independent Python range oracle.

Does NOT pin real user pages, load a module, provide an FPGA SG translator or
claim native DMA/verbs. Kernel ib_umem API linkage is a separate compile gate.
"""
import ctypes as C
import errno
import hashlib
import json
import os
from pathlib import Path
import random
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[3]
KERNEL=ROOT/'rdma/rnic/kernel'
U64=(1<<64)-1
MAX_GEN=(1<<29)-1


class Epoch(C.Structure):
    _fields_=[('floor',C.c_uint32),('highest',C.c_uint32),('last',C.c_uint32*8),('configured',C.c_uint32)]
class EpochProof(C.Structure):
    _fields_=[('cookie',C.c_uint64),('floor',C.c_uint32),('qps_closed',C.c_uint32),('mr_table_invalid',C.c_uint32),('dma_drained',C.c_uint32)]
class Layout(C.Structure):
    _fields_=[('user_address',C.c_uint64),('iova',C.c_uint64),('length',C.c_uint64),('cookie',C.c_uint64),
              ('pages',C.c_uint64*256),('present',C.c_uint64*4)]+[(name,C.c_uint32) for name in
              ('pd','access','slot','page_count','first_offset','pages_written','state','key','required_generation')]
class Publish(C.Structure):
    _fields_=[('cookie',C.c_uint64),('slot',C.c_uint32),('key',C.c_uint32)]
class Revoke(C.Structure):
    _fields_=[('cookie',C.c_uint64),('slot',C.c_uint32),('generation',C.c_uint32),('invalidated',C.c_uint32),('dma_drained',C.c_uint32)]
class Segment(C.Structure):
    _fields_=[('dma_address',C.c_uint64),('memory_offset',C.c_uint64),('page_index',C.c_uint32),('length',C.c_uint32)]


class MRContractTests(unittest.TestCase):
    queries=0
    test_names=[]

    @classmethod
    def setUpClass(cls):
        cls.files=[KERNEL/'mr_contract.c',KERNEL/'mr_contract.h',Path(__file__)]
        cls.before={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in cls.files}
        cls.directory=tempfile.TemporaryDirectory(prefix='as02-mr-contract-');cls.path=Path(cls.directory.name)
        (cls.path/'abi.c').write_text('#include <stddef.h>\n#include "mr_contract.h"\nsize_t layout_size(void){return sizeof(struct as02_mr_layout);}\n')
        built=subprocess.run(['cc','-std=c11','-O2','-g','-Wall','-Wextra','-Werror','-shared','-fPIC',
            '-fsanitize=undefined','-fno-sanitize-recover=undefined','-I',str(KERNEL),str(KERNEL/'mr_contract.c'),
            str(cls.path/'abi.c'),'-o',str(cls.path/'contract.so')],capture_output=True,text=True,timeout=30)
        if built.returncode:raise RuntimeError(built.stdout+built.stderr)
        cls.lib=C.CDLL(str(cls.path/'contract.so'))
        ptr=C.POINTER;u32=C.c_uint32;u64=C.c_uint64
        signatures={
            'epoch_init':[ptr(Epoch),u32], 'epoch_confirm':[ptr(Epoch),u64,u32,ptr(EpochProof)],
            'layout_init':[ptr(Layout),u64,u64,u64,u32,u32,u32,u64],
            'set_page':[ptr(Layout),u32,u64], 'seal':[ptr(Layout)],
            'begin_publish':[ptr(Layout),ptr(Epoch)], 'confirm_publish':[ptr(Layout),ptr(Epoch),ptr(Publish)],
            'begin_revoke':[ptr(Layout)], 'confirm_revoke':[ptr(Layout),ptr(Epoch),ptr(Revoke)],
            'can_unpin':[ptr(Layout)], 'resolve':[ptr(Layout),u32,u32,u64,u32,u32,ptr(Segment)]}
        for name,args in signatures.items():
            fn=getattr(cls.lib,'as02_mr_'+name);fn.argtypes=args;fn.restype=C.c_int
        cls.lib.layout_size.restype=C.c_size_t
        if cls.lib.layout_size()!=C.sizeof(Layout):raise RuntimeError('C/ctypes layout mismatch')

    def setUp(self):self.test_names.append(self._testMethodName)

    def call(self,name,*args):return getattr(self.lib,'as02_mr_'+name)(*args)

    def epoch(self,floor=7):
        e=Epoch();self.assertEqual(self.call('epoch_init',C.byref(e),floor),0)
        self.assertEqual(self.call('epoch_confirm',C.byref(e),99,floor,C.byref(EpochProof(99,floor,1,1,1))),0)
        return e

    def layout(self,offset=0,length=8193,iova=0xfedcba9876500000,flags=7,slot=2,epoch=None,pages=None):
        e=epoch if epoch is not None else self.epoch()
        m=Layout();self.assertEqual(self.call('layout_init',C.byref(m),0x123450000+offset,iova,length,17,flags,slot,0x123456789),0)
        for index in range(m.page_count):
            dma=pages[index] if pages is not None else (0 if index==0 else (U64-4095 if index==1 else 0x8123450000000000+index*0x19000))
            self.assertEqual(self.call('set_page',C.byref(m),index,dma),0)
        self.assertEqual(self.call('seal',C.byref(m)),0)
        self.assertEqual(self.call('begin_publish',C.byref(m),C.byref(e)),0)
        key=((int(e.last[slot])+1)<<3)|slot
        self.assertEqual(self.call('confirm_publish',C.byref(m),C.byref(e),C.byref(Publish(m.cookie,slot,key))),0)
        return m,e

    def resolve(self,m,pd,key,address,length,operation):
        out=Segment(U64,U64,0xffffffff,0xffffffff)
        result=self.call('resolve',C.byref(m),pd,key,address,length,operation,C.byref(out))
        if m.state!=4 or pd!=m.pd or key!=m.key:expected=-errno.EACCES
        elif operation>4:expected=-errno.EOPNOTSUPP
        elif operation and not m.access & {1:1,2:4,3:2,4:8}[operation]:expected=-errno.EACCES
        elif not length or address<m.iova or address+length>int(m.iova)+m.length:expected=-errno.EFAULT
        elif operation==4 and (length!=8 or address%8 or (int(m.pages[(m.first_offset+address-m.iova)//4096])+(m.first_offset+address-m.iova)%4096)%8):expected=-errno.EINVAL
        else:expected=0
        self.assertEqual(result,expected,(pd,key,address,length,operation))
        if expected:self.assertEqual(bytes(out),b'\0'*C.sizeof(out))
        else:
            linear=m.first_offset+address-m.iova;page=linear//4096;page_offset=linear%4096
            self.assertEqual((out.dma_address,out.memory_offset,out.page_index,out.length),
                             (int(m.pages[page])+page_offset,address-m.iova,page,min(length,4096-page_offset)))
        type(self).queries+=1
        return out

    def close(self,m,e):
        generation=m.key>>3 if m.key else m.required_generation
        self.assertEqual(self.call('begin_revoke',C.byref(m)),0)
        self.assertEqual(self.call('confirm_revoke',C.byref(m),C.byref(e),C.byref(Revoke(m.cookie,m.slot,generation,1,1))),0)
        self.assertEqual(self.call('can_unpin',C.byref(m)),1)

    def test_scattered_page_boundaries_and_independent_iova_offset(self):
        for offset in (0,1,63,4095):
            for length in (1,64,65,4095,4096,8193,256*4096-offset):
                m,e=self.layout(offset,length,iova=0xfedcba9876543210)
                position=0
                while position<length:
                    segment=self.resolve(m,17,m.key,m.iova+position,length-position,2)
                    position+=segment.length
                self.assertEqual(position,length);self.close(m,e)

    def test_permissions_pd_full_key_and_range_matrix(self):
        for flags in range(16):
            if flags&10 and not flags&1:continue
            m,_=self.layout(0,8193,flags=flags)
            for operation in range(7):
                for pd,key in ((17,m.key),(18,m.key),(17,m.key^0x80000000)):
                    self.resolve(m,pd,key,m.iova,8,operation)
            for delta,length in ((-1,1),(0,0),(8192,1),(8192,2),(8193,1)):
                self.resolve(m,17,m.key,m.iova+delta,length,0)

    def test_failed_publish_and_bad_revoke_proof_cannot_unpin(self):
        e=self.epoch();m=Layout()
        self.assertEqual(self.call('layout_init',C.byref(m),0x100003,m.iova or 0x8000000000,65,17,7,0,42),0)
        self.assertEqual(self.call('set_page',C.byref(m),0,0x12345000),0)
        self.assertEqual(self.call('seal',C.byref(m)),0)
        self.assertEqual(self.call('can_unpin',C.byref(m)),1)
        self.assertEqual(self.call('begin_publish',C.byref(m),C.byref(e)),0)
        self.assertEqual(self.call('can_unpin',C.byref(m)),0)
        self.assertEqual(self.call('confirm_publish',C.byref(m),C.byref(e),C.byref(Publish(43,0,64))),-errno.ESTALE)
        self.assertEqual(self.call('can_unpin',C.byref(m)),0)
        self.assertEqual(self.call('begin_revoke',C.byref(m)),0)
        for proof in (Revoke(43,0,8,1,1),Revoke(42,1,8,1,1),Revoke(42,0,6,1,1),Revoke(42,0,8,0,1),Revoke(42,0,8,1,0)):
            self.assertNotEqual(self.call('confirm_revoke',C.byref(m),C.byref(e),C.byref(proof)),0)
            self.assertEqual(self.call('can_unpin',C.byref(m)),0)
        self.assertEqual(self.call('confirm_revoke',C.byref(m),C.byref(e),C.byref(Revoke(42,0,8,1,1))),0)
        self.assertEqual(e.highest,8);self.assertEqual(self.call('can_unpin',C.byref(m)),1)

    def test_fresh_epoch_floor_covers_all_prior_generations(self):
        e=self.epoch(7);old,e=self.layout(epoch=e,slot=0);old_key=old.key;self.close(old,e)
        for floor,proof in ((7,EpochProof(100,7,1,1,1)),(8,EpochProof(101,8,1,1,1)),(8,EpochProof(100,8,0,1,1)),(8,EpochProof(100,8,1,0,1)),(8,EpochProof(100,8,1,1,0))):
            self.assertNotEqual(self.call('epoch_confirm',C.byref(e),100,floor,C.byref(proof)),0)
            self.assertEqual(e.floor,7)
        self.assertEqual(self.call('epoch_confirm',C.byref(e),100,8,C.byref(EpochProof(100,8,1,1,1))),0)
        new,_=self.layout(epoch=e,slot=0);self.assertNotEqual(old_key,new.key)
        self.resolve(new,17,old_key,new.iova,1,2)
        self.resolve(new,17,new.key,new.iova,1,2)

    def test_generation_exhaustion_does_not_wrap(self):
        e=self.epoch(MAX_GEN-1);m,e=self.layout(epoch=e,slot=0);self.assertEqual(m.key,MAX_GEN<<3)
        self.close(m,e)
        n=Layout();self.assertEqual(self.call('layout_init',C.byref(n),0,0,1,17,7,0,88),0)
        self.assertEqual(self.call('set_page',C.byref(n),0,0),0);self.assertEqual(self.call('seal',C.byref(n)),0)
        self.assertEqual(self.call('begin_publish',C.byref(n),C.byref(e)),-errno.ENOSPC)
        self.assertEqual(self.call('can_unpin',C.byref(n)),1)
        self.assertEqual(self.call('epoch_confirm',C.byref(e),101,MAX_GEN,C.byref(EpochProof(101,MAX_GEN,1,1,1))),-errno.ENOSPC)

    def test_page_population_zero_alias_alignment_and_immutability(self):
        e=self.epoch();m=Layout()
        self.assertEqual(self.call('layout_init',C.byref(m),4095,7,65,17,7,0,123),0)
        self.assertEqual(m.page_count,2)
        self.assertEqual(self.call('set_page',C.byref(m),0,0),0)
        self.assertEqual(self.call('set_page',C.byref(m),0,0),-errno.EEXIST)
        self.assertEqual(self.call('set_page',C.byref(m),1,1),-errno.EINVAL)
        self.assertEqual(self.call('set_page',C.byref(m),2,0),-errno.EINVAL)
        self.assertEqual(self.call('seal',C.byref(m)),-errno.EINVAL)
        self.assertEqual(self.call('set_page',C.byref(m),1,0),0) # legitimate aliased user pages
        self.assertEqual(self.call('seal',C.byref(m)),0)
        self.assertEqual(self.call('set_page',C.byref(m),1,4096),-errno.EBUSY)
        self.assertEqual(self.call('begin_publish',C.byref(m),C.byref(e)),0)
        self.assertEqual(self.call('confirm_publish',C.byref(m),C.byref(e),C.byref(Publish(123,0,64))),0)
        self.resolve(m,17,m.key,7,65,2)

    def test_64bit_exclusive_end_and_zeroized_denials(self):
        m,_=self.layout(0,65,iova=U64-64)
        self.resolve(m,17,m.key,U64,1,2);self.resolve(m,17,m.key,U64,2,2)
        self.resolve(m,17,m.key,U64-65,1,2)
        for user,iova,length in ((0,U64,2),(U64,0,2),(0,0,0),(4095,0,256*4096)):
            n=Layout();self.assertNotEqual(self.call('layout_init',C.byref(n),user,iova,length,17,7,0,1),0)

    def test_reinitialization_and_revoke_cannot_disclose_addresses(self):
        m,e=self.layout()
        self.assertEqual(self.call('layout_init',C.byref(m),0,0,1,17,7,0,88),-errno.EBUSY)
        self.assertEqual(self.call('can_unpin',C.byref(m)),0)
        key=m.key;self.close(m,e)
        self.resolve(m,17,key,m.iova,1,2)

    def test_deterministic_randomized_independent_range_oracle(self):
        rng=random.Random(0x455a2026)
        for _ in range(20):
            length=rng.randrange(1,20000);offset=rng.randrange(4096)
            m,_=self.layout(offset,length,flags=rng.choice((0,1,3,4,5,7,9,11,13,15)))
            for _ in range(100):
                delta=rng.choice((-1,0,length-1,length,rng.randrange(length)))
                self.resolve(m,rng.choice((17,17,18)),m.key if rng.randrange(4) else m.key^0x80000000,
                             m.iova+delta,rng.choice((0,1,8,65,4096,0xffffffff)),rng.randrange(7))

    @classmethod
    def tearDownClass(cls):
        after={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in cls.files}
        cls.directory.cleanup()
        if after!=cls.before:raise RuntimeError('C contract sources changed during tests')
        if name:=os.environ.get('AS02_RNIC_MR_CONTRACT_REPORT'):
            target=Path(name)
            if not target.is_absolute():target=ROOT/target
            report=dict(scope='Actual shared C SG/lifecycle contract, Python integer oracle; no runtime page pin or FPGA translation',
                hardware_verified=False,kernel_runtime_pin_verified=False,fpga_sg_translation_implemented=False,completion_claim=False,
                method_count=len(cls.test_names),resolve_queries=cls.queries,tests=cls.test_names,source_sha256=after)
            with target.open('x') as out:out.write(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':unittest.main()
