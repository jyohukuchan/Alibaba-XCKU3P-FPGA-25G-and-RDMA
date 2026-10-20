# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual kernel CQ/SQ/MR/MMIO C consumes actual RTL-published event bytes.

The kernel primitives, umem/DMA, MMIO readl/writel and IRQ execution remain
explicit userspace models. RTL MAC/lifetime publication has modeled HLS/core
drain inputs; this is not real Linux/PCIe/board or registered verbs evidence.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

import test_cq_path_rtl as rtl
import test_message_cq_rtl as messages
import test_kernel_queue_lifecycle as original

ROOT=original.ROOT
KERNEL=original.KERNEL
TESTS=original.TESTS
SOURCES=[KERNEL/n for n in ['mr.c','mr_contract.c','wqe.c','verbs_wqe.c','sq.c','sq_io.c','sq_hw.c','cq_io.c','cq_hw.c','cq.c']]
SOURCES += [TESTS/'kernel_queue_model.c',TESTS/'kernel_cq_cases.c']


class KernelCQTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory=tempfile.TemporaryDirectory(prefix='as02-kernel-cq-');cls.path=Path(cls.directory.name)
        cls.rtl_summary=rtl.simulate(cls.path/'rtl')
        cls.message_summary=messages.simulate(cls.path/'messages')
        for n in original.HEADERS+['linux/io.h','linux/ktime.h','linux/lockdep.h','asm/processor.h','linux/irq_work.h',
            'linux/atomic.h','linux/workqueue.h','linux/jiffies.h']:
            h=cls.path/'include'/n;h.parent.mkdir(parents=True,exist_ok=True);h.write_text('#include "kernel_cq_model.h"\n')
        cls.inputs=SOURCES+[TESTS/'kernel_cq_model.h',TESTS/'kernel_sq_hw_model.h',TESTS/'kernel_queue_model.h',
            TESTS/'kernel_sq_hw_cases.c',Path(__file__).resolve(),Path(rtl.__file__).resolve(),*rtl.SOURCES]
        cls.inputs+=[Path(messages.__file__).resolve(),TESTS/'test_wqe_hls_sq_rtl.py']
        cls.inputs+=list(KERNEL.glob('*.h'))
        cls.before={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in cls.inputs}
        cls.command=['cc','-std=c11','-D_GNU_SOURCE','-D__KERNEL__','-O1','-g','-Wall','-Wextra','-Werror','-pthread',
            '-fsanitize=address,undefined','-fno-sanitize-recover=undefined','-I',str(cls.path/'include'),
            '-I',str(TESTS),'-I',str(KERNEL),'-include',str(TESTS/'kernel_cq_model.h'),*map(str,SOURCES),'-o',str(cls.path/'cases')]
        c=subprocess.run(cls.command,capture_output=True,text=True,timeout=30)
        if c.returncode:raise RuntimeError(c.stdout+c.stderr)
        cls.reports={}

    def run_case(self,n):
        env=os.environ.copy();env['ASAN_OPTIONS']='detect_leaks=1:halt_on_error=1'
        events=self.path/('messages' if n>=3 else 'rtl')
        r=subprocess.run([str(self.path/'cases'),str(n),str(events/'event1.hex'),str(events/'event2.hex')],
            capture_output=True,text=True,env=env,timeout=10)
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        rows=[json.loads(l.split(' ',1)[1])for l in r.stdout.splitlines()if l.startswith('KERNEL_CQ_RESULT ')]
        self.assertEqual(len(rows),1,r.stdout);self.assertTrue(rows[0]['pass_test'])
        self.reports[n]=rows[0]

    def test_actual_published_events_real_kernel_CQ_backpressure_and_MR_retirement(self):self.run_case(0)
    def test_lost_ACK_reconciles_without_duplicate_WC_or_work_ref_release(self):self.run_case(1)
    def test_wrong_full_WR_identity_never_publishes_or_releases_MR(self):self.run_case(2)
    def test_actual_RTL_RECV_events_route_to_distinct_receive_CQ_with_actual_length(self):self.run_case(3)
    def test_actual_RTL_RECV_events_shared_CQ_take_only_one_owner_reference(self):self.run_case(4)

    @classmethod
    def tearDownClass(cls):
        if name:=os.environ.get('AS02_RNIC_KERNEL_CQ_REPORT'):
            current={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest()for n in cls.before}
            d=dict(scope=__doc__,pass_test=len(cls.reports)==5 and current==cls.before,
                RTL_CQ_path=cls.rtl_summary,RTL_message_CQ_path=cls.message_summary,
                cases=cls.reports,source_sha256=cls.before,
                source_unchanged=current==cls.before,compiler_command=cls.command,
                actual_CQ_SQ_MR_IO_implementation_executed=True,event_bytes_from_actual_RTL=True,
                Linux_primitives_MMIO_pins_DMA_and_HLS_core_drain_models=True,
                hardware_verified=False,ib_device_registered=False,standard_verbs_runtime=False)
            with (ROOT/name).open('x')as out:out.write(json.dumps(d,indent=2)+'\n')
        cls.directory.cleanup()


if __name__=='__main__':unittest.main()
