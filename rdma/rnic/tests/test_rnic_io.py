# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual shared C mailbox client/UBSan, MMIO/controller-reply MODEL only.

Kernel readl/writel wrapper linkage is separate; no real pins/native MMIO/DMA.
"""
import ctypes as C
import errno
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[3];KERNEL=ROOT/'rdma/rnic/kernel'
READ=C.CFUNCTYPE(C.c_int,C.c_void_p,C.c_uint32,C.POINTER(C.c_uint32))
WRITE=C.CFUNCTYPE(C.c_int,C.c_void_p,C.c_uint32,C.c_uint32)
TIME=C.CFUNCTYPE(C.c_uint64,C.c_void_p);WAIT=C.CFUNCTYPE(None,C.c_void_p)
class Transport(C.Structure):_fields_=[('read32',READ),('write32',WRITE),('time_us',TIME),('wait',WAIT)]
class Control(C.Structure):
    _fields_=[('io',C.POINTER(Transport)),('context',C.c_void_p),('timeout_us',C.c_uint32),('sequence',C.c_uint32),
        ('initialized',C.c_int),('pending',C.c_int),('uncertain',C.c_int),('detached',C.c_int),('expected',C.c_uint32*21)]
class Reply(C.Structure):
    _fields_=[('sequence',C.c_uint32),('command',C.c_uint32),('cookie',C.c_uint64),
        ('slot',C.c_uint32),('key',C.c_uint32),('error',C.c_uint32),('flags',C.c_uint32)]

DEFINES={n:int(v,0) for n,v in re.findall(r'^#define (AS02_\w+) (0x[0-9a-fA-F]+|\d+)U$',(KERNEL/'rnic_regs.h').read_text(),re.M)}
ENUM=re.search(r'enum as02_ctl_word \{([^}]+)\}',(KERNEL/'rnic_regs.h').read_text(),re.S)[1]
WORD={n.strip():i for i,n in enumerate(ENUM.split(','))}


class MMIO:
    def __init__(self):
        self.words=[0]*21;self.captured=[];self.reply=None;self.busy=False;self.time=0;self.acks=0;self.writes=[]
        self.reads=[];self.time_calls=0;self.wait_calls=0
        self.id=DEFINES['AS02_CTL_ID_VALUE'];self.abi=DEFINES['AS02_CTL_ABI_VALUE'];self.live=False;self.fatal=False
        self.drop=False;self.corrupt=None;self.stage_fail=None;self.stage_corrupt=None;self.doorbell_fail=False;self.ack_fail=None
        self.reply_error=0;self.reply_error_flags=0;self.fatal_on_reply_read=False;self.floor=0;self.generation=[0]*8
        self.callbacks=(READ(self.read),WRITE(self.write),TIME(self.now),WAIT(self.wait))
        self.transport=Transport(*self.callbacks)

    def status(self):return (8|512|1024|(16 if self.fatal else 0)|(32 if self.live else 0)|((2|4) if self.reply is not None else (2 if self.busy else 1)))
    def read(self,ctx,address,value):
        self.reads.append(address)
        if address==0:result=self.id
        elif address==4:result=self.abi
        elif address==8:result=1
        elif address==12:result=self.status()
        elif address in (28,160,164,168):result=0
        elif 32<=address<=112 and address%4==0:
            index=(address-32)//4;result=self.words[index]^(1 if self.stage_corrupt==index else 0)
        elif 128<=address<=156 and address%4==0:
            result=self.reply[(address-128)//4] if self.reply is not None else 0
            if self.fatal_on_reply_read:self.fatal=True
        else:result=0
        value[0]=result;return 0

    def make_reply(self):
        w=self.captured[-1];seq,op,lo,hi,slot,key=w[:6]
        if op==1:self.floor=key;self.generation=[key]*8
        if op==2:self.generation[slot]+=1;key=(self.generation[slot]<<3)|slot
        elif op==5:key=key or ((self.generation[slot]<<3)|slot)
        elif op in (6,7,8):key=0
        flags={1:14,2:0,3:0,4:16,5:3,6:0,7:0,8:2}[op]
        r=[seq,op,lo,hi,slot,key,self.reply_error,self.reply_error_flags if self.reply_error else flags]
        if self.corrupt:self.corrupt(r)
        self.reply=r

    def write(self,ctx,address,value):
        self.writes.append((address,value))
        if 32<=address<=112 and address%4==0:
            index=(address-32)//4;self.words[index]=value
            if self.stage_fail==index:return -errno.EIO
        elif address==16:
            self.captured.append(self.words.copy());self.busy=True
            if not self.drop:self.make_reply()
            if self.doorbell_fail:return -errno.EIO
        elif address==20:
            if self.ack_fail=='keep':return -errno.EIO
            if self.reply is None or value!=self.reply[0]:return -errno.EPROTO
            self.reply=None;self.busy=False;self.acks+=1
            if self.ack_fail=='lost':return -errno.EIO
        return 0

    def now(self,ctx):self.time_calls+=1;return self.time
    def wait(self,ctx):self.wait_calls+=1;self.time+=10


class RNICIOTests(unittest.TestCase):
    test_names=[]
    passed_names=[]
    @classmethod
    def setUpClass(cls):
        cls.files=[KERNEL/n for n in ['rnic_io.c','rnic_io.h','rnic_regs.h','mr_contract.h']]+[Path(__file__)]
        cls.before={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in cls.files}
        cls.directory=tempfile.TemporaryDirectory(prefix='as02-rnic-io-');cls.path=Path(cls.directory.name)
        p=cls.path/'abi.c';p.write_text('#include <stddef.h>\n#include "rnic_io.h"\nsize_t ctl_size(void){return sizeof(struct as02_ctl);}\nsize_t reply_size(void){return sizeof(struct as02_ctl_reply);}\n')
        r=subprocess.run(['cc','-std=c11','-O2','-Wall','-Wextra','-Werror','-shared','-fPIC','-fsanitize=undefined',
            '-fno-sanitize-recover=undefined','-I',str(KERNEL),str(KERNEL/'rnic_io.c'),str(p),'-o',str(cls.path/'test.so')],capture_output=True,text=True,timeout=30)
        if r.returncode:raise RuntimeError(r.stdout+r.stderr)
        cls.lib=C.CDLL(str(cls.path/'test.so'))
        cls.lib.as02_ctl_init.argtypes=[C.POINTER(Control),C.POINTER(Transport),C.c_void_p,C.c_uint32]
        cls.lib.as02_ctl_execute.argtypes=[C.POINTER(Control),C.POINTER(C.c_uint32),C.POINTER(Reply)]
        cls.lib.as02_ctl_reconcile.argtypes=[C.POINTER(Control),C.POINTER(Reply)]
        cls.lib.as02_ctl_detach.argtypes=[C.POINTER(Control)]
        cls.lib.ctl_size.restype=cls.lib.reply_size.restype=C.c_size_t
        if cls.lib.ctl_size()!=C.sizeof(Control) or cls.lib.reply_size()!=C.sizeof(Reply):raise RuntimeError('C ABI mismatch')

    def setUp(self):self.test_names.append(self._testMethodName)
    def tearDown(self):
        result=self._outcome.result
        if not any(test is self for test,_ in result.failures+result.errors+result.skipped):
            self.passed_names.append(self._testMethodName)
    def init(self,model=None):
        m=model or MMIO();c=Control();self.assertEqual(self.lib.as02_ctl_init(C.byref(c),C.byref(m.transport),None,40),0);return c,m
    def words(self,op=2,key=0):
        w=(C.c_uint32*21)();values=dict(AS02_W_OP=op,AS02_W_COOKIE_LO=0x89abcdef,AS02_W_COOKIE_HI=0x12345678,
            AS02_W_SLOT=2,AS02_W_KEY=key,AS02_W_PD=17,AS02_W_ACCESS=7,AS02_W_VA_LO=0x76543210,AS02_W_VA_HI=0xfedcba98,
            AS02_W_LENGTH=8193,AS02_W_FIRST=4093,AS02_W_PAGE_INDEX=255,AS02_W_DMA_LO=0xfffff000,AS02_W_DMA_HI=0xffffffff,
            AS02_W_QP=2,AS02_W_PEER_QP=196,AS02_W_LOCAL_IP=0xc6120b02,AS02_W_PEER_IP=0xc6120b01,AS02_W_RX_PSN=0x987654,AS02_W_TX_PSN=0xfffffe)
        for n,v in values.items():w[WORD[n]]=v
        return w
    def execute(self,c,w):
        r=Reply();C.memset(C.byref(r),0xa5,C.sizeof(r));ret=self.lib.as02_ctl_execute(C.byref(c),w,C.byref(r))
        if ret:self.assertEqual(bytes(r),b'\0'*C.sizeof(r))
        return ret,r

    def test_all_commands_actual_full64_metadata_snapshot_and_flags(self):
        c,m=self.init();key=0
        for op in [1,6,2,3,4,7,5,8]:
            value=7 if op==1 else (key if op in (3,4,5) else 0)
            w=self.words(op,value);ret,r=self.execute(c,w);self.assertEqual(ret,0);self.assertEqual(r.cookie,0x1234567889abcdef)
            self.assertEqual(r.slot,2);self.assertEqual(r.error,0)
            self.assertEqual(r.flags,{1:14,6:0,2:0,3:0,4:16,7:0,5:3,8:2}[op])
            if op==2:key=r.key;self.assertEqual(key,66)
            expected=list(w);expected[0]=c.sequence;self.assertEqual(m.captured[-1],expected)
            self.assertFalse(c.pending or c.uncertain)
        self.assertEqual(m.acks,8);self.assertEqual([w[0] for w in m.captured],list(range(1,9)))

    def test_old_device_abi_live_state_and_missing_transport_rejected_without_writes(self):
        for name,value,expected in [('id',0x524f4332,-errno.ENODEV),('abi',0,-errno.EOPNOTSUPP),('live',True,-errno.EBUSY),('fatal',True,-errno.EIO)]:
            m=MMIO();setattr(m,name,value);c=Control();self.assertEqual(self.lib.as02_ctl_init(C.byref(c),C.byref(m.transport),None,40),expected);self.assertFalse(m.writes)
        c=Control();missing=Transport()
        self.assertEqual(self.lib.as02_ctl_init(C.byref(c),C.byref(missing),None,40),-errno.EINVAL)
        m=MMIO();self.assertEqual(self.lib.as02_ctl_init(C.byref(c),C.byref(m.transport),None,0),-errno.EINVAL);self.assertFalse(m.writes)

    def test_bad_response_identity_key_and_proof_never_ack_or_publish(self):
        corruptions=[(2,0,lambda r:r.__setitem__(0,r[0]+1)),(2,0,lambda r:r.__setitem__(1,3)),
            (2,0,lambda r:r.__setitem__(2,r[2]^1)),(2,0,lambda r:r.__setitem__(3,r[3]^1)),
            (2,0,lambda r:r.__setitem__(4,3)),(2,0,lambda r:r.__setitem__(5,8)),
            (2,0,lambda r:r.__setitem__(7,16)),(4,10,lambda r:r.__setitem__(7,0)),
            (5,10,lambda r:r.__setitem__(7,1)),(5,10,lambda r:r.__setitem__(5,18)),
            (1,7,lambda r:r.__setitem__(7,3))]
        for op,key,corrupt in corruptions:
            c,m=self.init();m.corrupt=corrupt;ret,_=self.execute(c,self.words(op,key))
            self.assertEqual(ret,-errno.EPROTO);self.assertTrue(c.pending and c.uncertain);self.assertEqual(m.acks,0)

    def test_timeout_keeps_expected_owner_and_late_reply_can_only_resynchronize(self):
        c,m=self.init();m.drop=True;w=self.words();ret,_=self.execute(c,w);self.assertEqual(ret,-errno.ETIMEDOUT)
        self.assertTrue(c.pending and c.uncertain);self.assertEqual(c.expected[2],0x89abcdef)
        self.assertEqual(self.execute(c,w)[0],-errno.EBUSY);m.drop=False;m.make_reply();r=Reply()
        self.assertEqual(self.lib.as02_ctl_reconcile(C.byref(c),C.byref(r)),0);self.assertFalse(c.pending or c.uncertain);self.assertEqual(m.acks,1)

    def test_ambiguous_doorbell_failure_retains_then_matches_real_reply(self):
        c,m=self.init();m.doorbell_fail=True;ret,_=self.execute(c,self.words());self.assertEqual(ret,-errno.EIO)
        self.assertTrue(c.pending and c.uncertain);m.doorbell_fail=False;r=Reply()
        self.assertEqual(self.lib.as02_ctl_reconcile(C.byref(c),C.byref(r)),0);self.assertEqual(r.command,2)

    def test_staging_failure_or_readback_mismatch_never_rings_doorbell(self):
        for attribute in ['stage_fail','stage_corrupt']:
            c,m=self.init();setattr(m,attribute,14);self.assertEqual(self.execute(c,self.words())[0],-errno.EIO)
            self.assertFalse(c.pending or c.uncertain);self.assertFalse(m.captured);self.assertEqual(m.acks,0)

    def test_fatal_after_reply_read_forbids_ack_and_release(self):
        c,m=self.init();m.fatal_on_reply_read=True;self.assertEqual(self.execute(c,self.words())[0],-errno.EIO)
        self.assertTrue(c.pending and c.uncertain);self.assertEqual(m.acks,0)

    def test_ack_error_never_becomes_success_and_lost_ack_is_not_guessed(self):
        for kind in ['keep','lost']:
            c,m=self.init();m.ack_fail=kind;self.assertEqual(self.execute(c,self.words())[0],-errno.EIO)
            self.assertTrue(c.pending and c.uncertain);m.ack_fail=None;r=Reply()
            result=self.lib.as02_ctl_reconcile(C.byref(c),C.byref(r))
            self.assertEqual(result,0 if kind=='keep' else -errno.ETIMEDOUT)
            if kind=='lost':self.assertTrue(c.pending and c.uncertain)

    def test_error_response_is_transport_completion_not_memory_proof(self):
        c,m=self.init();m.reply_error=0xe3;ret,r=self.execute(c,self.words())
        self.assertEqual(ret,0);self.assertEqual((r.error,r.flags),(0xe3,0));self.assertEqual(m.acks,1)
        c,m=self.init();m.reply_error=0xe3;m.reply_error_flags=3
        self.assertEqual(self.execute(c,self.words())[0],-errno.EPROTO);self.assertEqual(m.acks,0)

    def test_validation_and_sequence_exhaustion_prevent_truncation_and_reuse(self):
        for index,value in [('AS02_W_SLOT',8),('AS02_W_PD',65536),('AS02_W_FIRST',4096),('AS02_W_QP',8),
                            ('AS02_W_PEER_QP',1<<24),('AS02_W_RX_PSN',1<<24),('AS02_W_ACCESS',2),('AS02_W_LENGTH',0)]:
            c,m=self.init();w=self.words();w[WORD[index]]=value;self.assertEqual(self.execute(c,w)[0],-errno.EINVAL);self.assertFalse(m.writes)
        c,m=self.init();c.sequence=0xffffffff;self.assertEqual(self.execute(c,self.words())[0],-errno.ENOSPC);self.assertFalse(m.writes)

    def assert_detached_no_access(self,c,m):
        before=(len(m.reads),len(m.writes),m.time_calls,m.wait_calls,m.acks)
        owner=(c.pending,c.uncertain,c.sequence,list(c.expected))
        for _ in range(3):
            self.assertEqual(self.execute(c,self.words())[0],-errno.ENODEV)
            r=Reply();C.memset(C.byref(r),0xa5,C.sizeof(r))
            self.assertEqual(self.lib.as02_ctl_reconcile(C.byref(c),C.byref(r)),-errno.ENODEV)
            self.assertEqual(bytes(r),b'\0'*C.sizeof(r))
            self.assertEqual(self.lib.as02_ctl_detach(C.byref(c)),0)
        self.assertEqual(before,(len(m.reads),len(m.writes),m.time_calls,m.wait_calls,m.acks))
        self.assertEqual(owner,(c.pending,c.uncertain,c.sequence,list(c.expected)))
        self.assertEqual(self.lib.as02_ctl_init(C.byref(c),C.byref(m.transport),None,40),-errno.ENODEV)
        self.assertEqual(before,(len(m.reads),len(m.writes),m.time_calls,m.wait_calls,m.acks))

    def test_detach_idle_is_terminal_without_transport_access_or_reinitialization(self):
        c,m=self.init();self.assertEqual(self.lib.as02_ctl_detach(C.byref(c)),0)
        self.assertTrue(c.initialized and c.detached);self.assertFalse(c.pending or c.uncertain)
        self.assert_detached_no_access(c,m)

    def test_detach_ambiguous_command_preserves_full_owner_and_pin_uncertainty(self):
        c,m=self.init();m.doorbell_fail=True;self.assertEqual(self.execute(c,self.words())[0],-errno.EIO)
        owner=(c.pending,c.uncertain,c.sequence,list(c.expected))
        self.assertEqual(self.lib.as02_ctl_detach(C.byref(c)),0)
        self.assertTrue(c.pending and c.uncertain)
        self.assertEqual(owner,(c.pending,c.uncertain,c.sequence,list(c.expected)))
        self.assert_detached_no_access(c,m)

    def test_detach_forbids_even_a_valid_late_drain_reply_from_becoming_proof(self):
        c,m=self.init();m.drop=True;self.assertEqual(self.execute(c,self.words(5,10))[0],-errno.ETIMEDOUT)
        self.assertEqual(self.lib.as02_ctl_detach(C.byref(c)),0)
        m.drop=False;m.make_reply();self.assertEqual(m.reply[-1],3)
        self.assert_detached_no_access(c,m);self.assertTrue(c.pending and c.uncertain)

    def test_detach_completed_history_keeps_sequence_and_invalid_objects_rejected(self):
        self.assertEqual(self.lib.as02_ctl_detach(None),-errno.EINVAL)
        empty=Control();self.assertEqual(self.lib.as02_ctl_detach(C.byref(empty)),-errno.EINVAL)
        c,m=self.init();self.assertEqual(self.execute(c,self.words())[0],0);self.assertEqual(c.sequence,1)
        self.assertEqual(self.lib.as02_ctl_detach(C.byref(c)),0);self.assertEqual(c.sequence,1)
        self.assert_detached_no_access(c,m)

    @classmethod
    def tearDownClass(cls):
        after={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in cls.files};cls.directory.cleanup()
        if after!=cls.before:raise RuntimeError('C I/O test sources changed')
        if name:=os.environ.get('AS02_RNIC_IO_REPORT'):
            p=Path(name)
            if not p.is_absolute():p=ROOT/p
            d=dict(scope='Actual shared C MMIO client/UBSan and logical detach, MMIO/controller-reply MODEL only',pass_test=len(cls.passed_names)==len(cls.test_names)==14,
                kernel_readl_writel_executed=False,hardware_verified=False,board_integrated=False,completion_claim=False,
                test_names=cls.test_names,passed_names=cls.passed_names,source_sha256=after)
            with p.open('x') as out:out.write(json.dumps(d,indent=2)+'\n')


if __name__=='__main__':unittest.main()
