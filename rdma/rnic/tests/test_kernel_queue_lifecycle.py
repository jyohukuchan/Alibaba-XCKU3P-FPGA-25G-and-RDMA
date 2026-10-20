# SPDX-License-Identifier: BSD-2-Clause-Views
"""Execute actual kernel MR/SQ/WR C with explicit userspace primitive models.

Model pthread locks/refcounts/umem/coherent DMA/HW/CQ are NOT native kernel
primitives, page pins, physical DMA, registered post_send/CQ or bus/provider.
The separate frozen running-kernel-header compile/link must also pass.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[3]
KERNEL=ROOT/'rdma/rnic/kernel'
TESTS=ROOT/'rdma/rnic/tests'
COMPILED=[KERNEL/n for n in ['mr.c','mr_contract.c','wqe.c','verbs_wqe.c','sq.c']]
COMPILED += [TESTS/'kernel_queue_model.c',TESTS/'kernel_queue_cases.c']
INPUTS=COMPILED+[KERNEL/n for n in ['mr.h','mr_contract.h','wqe.h','sq.h']]
INPUTS += [TESTS/'kernel_queue_model.h',Path(__file__).resolve()]
HEADERS=['linux/err.h','linux/mm.h','linux/module.h','linux/overflow.h','linux/sched/mm.h',
         'linux/slab.h','linux/list.h','linux/mutex.h','linux/refcount.h','linux/spinlock.h',
         'linux/types.h','linux/limits.h','linux/device.h','linux/dma-mapping.h','linux/export.h',
         'linux/string.h','rdma/ib_umem.h','rdma/ib_verbs.h']


class KernelQueueLifecycleTests(unittest.TestCase):
    reports={}

    @classmethod
    def setUpClass(cls):
        cls.before={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in INPUTS}
        cls.directory=tempfile.TemporaryDirectory(prefix='as02-kernel-queue-model-')
        cls.path=Path(cls.directory.name)
        for name in HEADERS:
            header=cls.path/'include'/name;header.parent.mkdir(parents=True,exist_ok=True)
            header.write_text('#include "kernel_queue_model.h"\n')
        cls.command=['cc','-std=c11','-D_GNU_SOURCE','-D__KERNEL__','-O1','-g','-Wall','-Wextra','-Werror','-pthread',
            '-fsanitize=address,undefined','-fno-sanitize-recover=undefined','-I',str(cls.path/'include'),
            '-I',str(TESTS),'-I',str(KERNEL),'-include',str(TESTS/'kernel_queue_model.h'),
            *map(str,COMPILED),'-o',str(cls.path/'cases')]
        r=subprocess.run(cls.command,capture_output=True,text=True,timeout=30)
        if r.returncode:raise RuntimeError(r.stdout+r.stderr)

    def run_case(self,case,retained=False):
        env=os.environ.copy();env['ASAN_OPTIONS']='detect_leaks=1:halt_on_error=1'
        r=subprocess.run([str(self.path/'cases'),str(case)],capture_output=True,text=True,env=env,timeout=10)
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        rows=[json.loads(line[20:])for line in r.stdout.splitlines()if line.startswith('KERNEL_QUEUE_RESULT ')]
        self.assertEqual(len(rows),1,r.stdout+r.stderr);data=rows[0]
        self.assertTrue(data['pass_test']);self.assertEqual(data['case'],case)
        if retained:
            self.assertGreater(data['heap_live'],0);self.assertEqual(data['umem_live'],1)
            self.assertEqual(data['dma_allocs'],1);self.assertEqual(data['dma_frees'],0)
        else:
            self.assertEqual(data['heap_live'],0);self.assertEqual(data['umem_live'],0)
            self.assertEqual(data['module_refs'],0);self.assertEqual(data['dma_allocs'],data['dma_frees'])
        self.assertEqual(self.before,{n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest()for n in self.before})
        self.reports[self._testMethodName]=dict(summary=data,ownership_intentionally_retained=retained)

    def test_MR_owned_fast_refs_full_authorization_stop_new_gets_and_block_close(self):self.run_case(0)
    def test_MR_unpublished_and_ambiguous_publication_never_release_without_revoke_proof(self):self.run_case(1)
    def test_MR_four_threads_hold_real_C_references_across_concurrent_close(self):self.run_case(2)
    def test_SQ_coherent_ring_post_barrier_CQ_backpressure_completion_and_ring_reuse(self):self.run_case(3)
    def test_SQ_local_READ_destination_WRITE_source_permissions_and_unsignaled_completion(self):self.run_case(4)
    def test_bad_or_fetch_only_completion_cannot_release_MR_or_queue_lifetime(self):self.run_case(5,True)
    def test_ambiguous_producer_doorbell_retains_ring_and_MR_refs_without_rollback(self):self.run_case(6,True)
    def test_ambiguous_allocation_retire_all_drain_flags_full_handle_and_epoch(self):self.run_case(7)
    def test_pool_device_module_teardown_keeps_owners_until_CQ_and_drain(self):self.run_case(8)
    def test_two_threads_post_sixteen_owned_WRs_then_source_matched_CQ_retirement(self):self.run_case(9)

    @classmethod
    def tearDownClass(cls):
        current={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest()for n in cls.before}
        if name:=os.environ.get('AS02_RNIC_KERNEL_QUEUE_UNIT_REPORT'):
            p=Path(name);p=p if p.is_absolute()else ROOT/p
            report=dict(scope=__doc__,pass_test=len(cls.reports)==10 and cls.before==current,
                methods=len(cls.reports),tests=cls.reports,source_sha256=cls.before,
                source_sha256_before_after_equal=cls.before==current,compiler_command=cls.command,
                actual_kernel_C_implementation_executed=True,userspace_primitive_and_DMA_HWCQ_models=True,
                sanitizer='address,undefined',hardware_verified=False,native_kernel_functions_executed=False,
                registered_provider_or_verbs_executed=False,real_coherent_DMA_or_page_pins=False,
                quarantine_tests_do_not_fake_cleanup=True)
            with p.open('x')as out:json.dump(report,out,indent=2);out.write('\n')
        cls.directory.cleanup()


if __name__=='__main__':unittest.main()
