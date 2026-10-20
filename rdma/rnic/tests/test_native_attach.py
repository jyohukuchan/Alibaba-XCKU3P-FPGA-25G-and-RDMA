# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual shared-C parent validation/UBSan plus static probe scope checks.

Parent metadata is a MODEL. Kernel auxiliary callbacks/MMIO are NOT executed.
No module loaded, BAR touched, RDMA device registered or user page pinned.
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

ROOT=Path(__file__).resolve().parents[3]
KERNEL=ROOT/'rdma/rnic/kernel'


class Parent(C.Structure):
    _fields_=[(name,C.c_uint32) for name in ['vendor','device','subvendor','subdevice','app_id','mapped']]+[('bar_bytes',C.c_uint64)]


class NativeAttachTests(unittest.TestCase):
    test_names=[]
    passed_names=[]

    @classmethod
    def setUpClass(cls):
        cls.files=[KERNEL/name for name in ['native_attach.c','native_attach.h','native_regs.h','mr_contract.h','aux_control.c','Makefile']]+[Path(__file__)]
        cls.before={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in cls.files}
        cls.directory=tempfile.TemporaryDirectory(prefix='as02-native-attach-')
        path=Path(cls.directory.name)
        abi=path/'abi.c'
        abi.write_text('#include <stddef.h>\n#include "native_attach.h"\nsize_t native_size(void){return sizeof(struct as02_native_parent);}\n')
        compiled=subprocess.run(['cc','-std=c11','-O2','-Wall','-Wextra','-Werror','-shared','-fPIC',
            '-fsanitize=undefined','-fno-sanitize-recover=undefined','-I',str(KERNEL),
            str(KERNEL/'native_attach.c'),str(abi),'-o',str(path/'test.so')],capture_output=True,text=True,timeout=30)
        if compiled.returncode:raise RuntimeError(compiled.stdout+compiled.stderr)
        cls.lib=C.CDLL(str(path/'test.so'))
        cls.lib.as02_native_parent_validate.argtypes=[C.POINTER(Parent)]
        cls.lib.native_size.restype=C.c_size_t

    def setUp(self):self.test_names.append(self._testMethodName)
    def tearDown(self):
        result=self._outcome.result
        if not any(test is self for test,_ in result.failures+result.errors+result.skipped):
            self.passed_names.append(self._testMethodName)

    def parent(self):return Parent(0x1234,0x1001,0x1ce4,0x0009,0x41534e31,1,0x1000000)
    def validate(self,parent):return self.lib.as02_native_parent_validate(C.byref(parent))

    def test_exact_parent_and_actual_C_ABI(self):
        self.assertEqual(self.lib.native_size(),C.sizeof(Parent))
        self.assertEqual(self.validate(self.parent()),0)

    def test_wrong_identity_old_application_and_full_high_bits_refused(self):
        for field in ['vendor','device','subvendor','subdevice','app_id']:
            for mode in ['different','high']:
                p=self.parent();value=getattr(p,field)
                setattr(p,field,value^1 if mode=='different' else value|(1<<31))
                self.assertEqual(self.validate(p),-errno.ENODEV,(field,mode))
        for app in [0,0x524f4332,0x41535232,0xffffffff]:
            p=self.parent();p.app_id=app;self.assertEqual(self.validate(p),-errno.ENODEV)
        p=self.parent();p.vendor=0x15b3;self.assertEqual(self.validate(p),-errno.ENODEV)

    def test_unmapped_or_unreviewed_BAR_geometry_refused(self):
        for mapped in [0,2,0xffffffff]:
            p=self.parent();p.mapped=mapped;self.assertEqual(self.validate(p),-errno.ENXIO)
        for size in [0,0x400fff,0x401000,0xffffff,0x1000001,0xffffffffffffffff]:
            p=self.parent();p.bar_bytes=size;self.assertEqual(self.validate(p),-errno.ENXIO)

    def test_null_identity_refused(self):
        self.assertEqual(self.lib.as02_native_parent_validate(None),-errno.EINVAL)

    def test_exact_alias_control_only_and_identification_precedes_MMIO(self):
        header=(KERNEL/'native_attach.h').read_text()
        self.assertIn('"mqnic.app_41534e31"',header)
        text=(KERNEL/'aux_control.c').read_text()
        self.assertIn('static bool enable_probe;',text)
        self.assertIn('module_param(enable_probe, bool, 0400)',text)
        self.assertLess(text.index('if (!enable_probe)'),text.index('parent = app->mdev'))
        self.assertLess(text.index('as02_native_parent_validate(&identity)'),text.index('as02_rnic_hw_init(&control->hw'))
        for name in ['ib_register_device','as02_ctl_execute','as02_mr_pool_start_epoch','ib_umem_get','pci_iomap','pci_set_master','writel']:
            self.assertNotRegex(text,r'\b'+name+r'\s*\(')
        self.assertIn('.name = AS02_NATIVE_AUX_NAME',text)
        remove=text.split('static void as02_control_remove',1)[1]
        self.assertLess(remove.index('as02_rnic_hw_detach'),remove.index('kfree(control)'))

    @classmethod
    def tearDownClass(cls):
        after={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in cls.files}
        cls.directory.cleanup()
        if after!=cls.before:raise RuntimeError('native attach test source changed')
        if report:=os.environ.get('AS02_NATIVE_ATTACH_REPORT'):
            path=Path(report)
            if not path.is_absolute():path=ROOT/path
            value=dict(scope=__doc__,pass_test=len(cls.passed_names)==len(cls.test_names)==5,
                hardware_verified=False,kernel_probe_or_remove_executed=False,MMIO_executed=False,
                module_loaded=False,ib_device_registered=False,user_pages_pinned=False,
                test_names=cls.test_names,passed_names=cls.passed_names,source_sha256=after)
            with path.open('x') as out:out.write(json.dumps(value,indent=2)+'\n')


if __name__=='__main__':unittest.main()
