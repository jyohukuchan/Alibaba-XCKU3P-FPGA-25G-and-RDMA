# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual kernel SQ/MMIO-IO/WR/MR C under explicit MMIO/time/CQ/primitive models.

NOT Linux readl/DMA/pins, actual RTL/native parent, registered CQ/verbs evidence.
Negative in-flight cases intentionally retain refs, never fake successful free.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

import test_kernel_queue_lifecycle as old

ROOT=old.ROOT
KERNEL=old.KERNEL
TESTS=old.TESTS
COMPILED=[KERNEL/n for n in ['mr.c','mr_contract.c','wqe.c','verbs_wqe.c','sq.c','sq_io.c','sq_hw.c']]
COMPILED += [TESTS/'kernel_queue_model.c',TESTS/'kernel_sq_hw_cases.c']
INPUTS=COMPILED+[KERNEL/n for n in ['mr.h','mr_contract.h','wqe.h','sq.h','sq_io.h','sq_hw.h','sq_regs.h']]
INPUTS += [TESTS/'kernel_queue_model.h',TESTS/'kernel_sq_hw_model.h',Path(old.__file__).resolve(),Path(__file__).resolve()]


class KernelSQHWTests(unittest.TestCase):
    reports={}

    @classmethod
    def setUpClass(cls):
        cls.before={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in INPUTS}
        cls.directory=tempfile.TemporaryDirectory(prefix='as02-kernel-sq-hw-');cls.path=Path(cls.directory.name)
        headers=old.HEADERS+['linux/io.h','linux/ktime.h','linux/lockdep.h','asm/processor.h']
        for name in headers:
            p=cls.path/'include'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('#include "kernel_sq_hw_model.h"\n')
        cls.command=['cc','-std=c11','-D_GNU_SOURCE','-D__KERNEL__','-O1','-g','-Wall','-Wextra','-Werror','-pthread',
            '-fsanitize=address,undefined','-fno-sanitize-recover=undefined','-I',str(cls.path/'include'),
            '-I',str(TESTS),'-I',str(KERNEL),'-include',str(TESTS/'kernel_sq_hw_model.h'),
            *map(str,COMPILED),'-o',str(cls.path/'cases')]
        r=subprocess.run(cls.command,capture_output=True,text=True,timeout=30)
        if r.returncode:raise RuntimeError(r.stdout+r.stderr)

    def run_case(self,case,subcase=0,retained=False):
        env=os.environ.copy();env['ASAN_OPTIONS']='detect_leaks=1:halt_on_error=1'
        r=subprocess.run([str(self.path/'cases'),str(case),str(subcase)],capture_output=True,text=True,env=env,timeout=10)
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        rows=[json.loads(l[14:])for l in r.stdout.splitlines()if l.startswith('SQC_HW_RESULT ')]
        self.assertEqual(len(rows),1,r.stdout);self.assertTrue(rows[0]['pass_test'])
        if retained:
            self.assertGreater(rows[0]['heap_live'],0);self.assertEqual(rows[0]['umem_live'],1)
            self.assertEqual(rows[0]['dma_allocs'],1);self.assertEqual(rows[0]['dma_frees'],0)
        else:
            self.assertEqual(rows[0]['heap_live'],0);self.assertEqual(rows[0]['umem_live'],0)
            self.assertEqual(rows[0]['dma_allocs'],rows[0]['dma_frees'])
        self.assertEqual(self.before,{n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest()for n in self.before})
        self.reports.setdefault(self._testMethodName,[]).append(rows[0])

    def test_identity_ABI_dirty_sequence_and_required_real_CQ_publisher(self):
        for n in range(4):
            with self.subTest(n=n):self.run_case(0,n)
    def test_actual_kernel_coherent_post_MR_refs_CQ_full_commit_and_retire(self):self.run_case(1)
    def test_all_fifteen_reply_words_wrong_owner_never_ACK_or_free_then_explicit_reconcile(self):
        for n in range(15):
            with self.subTest(n=n):self.run_case(2,n)
    def test_unknown_error_and_missing_or_error_release_flags_refuse_before_ACK(self):
        for n in range(5):
            with self.subTest(n=n):self.run_case(3,n)
    def test_posted_timeout_and_late_transport_resync_do_NOT_release_WR_or_MR(self):self.run_case(4,retained=True)
    def test_lost_ACK_and_detach_never_prove_completion_or_unpin(self):self.run_case(5,retained=True)
    def test_prebell_staging_failures_do_NOT_consume_strict_hardware_sequence(self):
        for n in range(3):
            with self.subTest(n=n):self.run_case(6,n)
    def test_known_retire_rejection_keeps_ring_until_fresh_actual_matched_proof(self):self.run_case(7)
    def test_foreign_sequence_and_terminal_detach_do_not_adopt_or_reinitialize(self):self.run_case(8)
    def test_final_sequence_ACK_and_nonwrapping_exhaustion(self):self.run_case(9)
    def test_full_command_shapes_and_DMA64_exclusive_end(self):
        for n in range(13):
            with self.subTest(n=n):self.run_case(10,n)
    def test_two_threads_post_sixteen_WRs_through_actual_kernel_MMIO_C_and_CQ_retire(self):self.run_case(11)
    def test_stopped_clock_still_obeys_atomic_poll_count_bound(self):self.run_case(12)

    @classmethod
    def tearDownClass(cls):
        if name:=os.environ.get('AS02_RNIC_SQ_HW_UNIT_REPORT'):
            report=dict(scope=__doc__,pass_test=len(cls.reports)==13 and sum(map(len,cls.reports.values()))==48,
                methods=len(cls.reports),cases=sum(map(len,cls.reports.values())),tests=cls.reports,source_sha256=cls.before,
                compiler_command=cls.command,actual_kernel_SQ_IO_HW_MR_WR_bodies_executed=True,
                explicit_userspace_MMIO_time_CQ_primitive_DMA_models=True,sanitizers='address,undefined',
                hardware_verified=False,actual_Linux_MMIO_pins_DMA_or_registered_CQ=False,actual_RTL_executed=False,
                negative_inflight_cases_intentionally_retain_owners=True)
            with (ROOT/name).open('x')as out:json.dump(report,out,indent=2);out.write('\n')
        cls.directory.cleanup()


if __name__=='__main__':unittest.main()
