# SPDX-License-Identifier: BSD-2-Clause-Views
"""Execute actual PD/MR/QP/post_send/CQ callbacks and actual CSR transports.

Linux primitives, umem/DMA, wire/memory/internal-core completion, MMIO and
IRQ/workqueue execution are explicit user models. No ib_device registration,
native DMA/board or complete standard RC/userspace verbs claim is made.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import test_kernel_queue_lifecycle as original

ROOT,KERNEL,TESTS=original.ROOT,original.KERNEL,original.TESTS
SOURCES=[KERNEL/n for n in ['mr.c','mr_contract.c','wqe.c','verbs_wqe.c','sq.c','sq_io.c','sq_hw.c',
    'cq_io.c','cq_hw.c','cq.c','rnic_io.c','qp_hw.c','retry_io.c','verbs.c']]
SOURCES += [TESTS/'kernel_queue_model.c',TESTS/'kernel_verbs_cases.c']

class KernelVerbsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory=tempfile.TemporaryDirectory(prefix='as02-kernel-verbs-');cls.path=Path(cls.directory.name)
        headers=original.HEADERS+['linux/io.h','linux/ktime.h','linux/lockdep.h','asm/processor.h',
            'linux/irq_work.h','linux/atomic.h','linux/workqueue.h','linux/jiffies.h','rdma/uverbs_ioctl.h']
        for name in headers:
            h=cls.path/'include'/name;h.parent.mkdir(parents=True,exist_ok=True);h.write_text('#include "kernel_verbs_model.h"\n')
        cls.inputs=SOURCES+list(KERNEL.glob('*.h'))+[TESTS/n for n in ['kernel_verbs_model.h',
            'kernel_cq_model.h','kernel_sq_hw_model.h','kernel_queue_model.h','kernel_sq_hw_cases.c']]+[Path(__file__).resolve()]
        cls.before={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in cls.inputs}
        cls.command=['cc','-std=c11','-D_GNU_SOURCE','-D__KERNEL__','-O1','-g','-Wall','-Wextra','-Werror','-pthread',
            '-fsanitize=address,undefined','-fno-sanitize-recover=undefined','-I',str(cls.path/'include'),
            '-I',str(TESTS),'-I',str(KERNEL),'-include',str(TESTS/'kernel_verbs_model.h'),*map(str,SOURCES),'-o',str(cls.path/'cases')]
        r=subprocess.run(cls.command,capture_output=True,text=True,timeout=30)
        if r.returncode:raise RuntimeError(r.stdout+r.stderr)
        cls.reports={}
    def run_case(self,n):
        env=os.environ.copy();env['ASAN_OPTIONS']='detect_leaks=1:halt_on_error=1'
        r=subprocess.run([str(self.path/'cases'),str(n)],capture_output=True,text=True,env=env,timeout=10)
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        rows=[json.loads(l.split(' ',1)[1])for l in r.stdout.splitlines()if l.startswith('KERNEL_VERBS_RESULT ')]
        self.assertEqual(len(rows),1,r.stdout);self.assertTrue(rows[0]['pass_test']);self.reports[n]=rows[0]
    def test_PD_MR_CQ_QP_linked_READ_WRITE_notifications_and_real_drain_teardown(self):self.run_case(0)
    def test_bad_WR_preserves_prior_success_and_exact_bad_wr(self):self.run_case(1)
    def test_failed_MR_publication_retains_PD_until_actual_cleanup(self):self.run_case(2)
    def test_unknown_QP_close_never_frees_SQ_PD_or_CQ(self):self.run_case(3)
    def test_failed_QP_create_preserves_pool_owned_handle_and_PD_until_drain(self):self.run_case(4)
    def test_feature_gated_TX_PSN_reaches_real_CSR_without_resetting_RX(self):self.run_case(5)
    def test_standard_RTS_retry_attributes_reach_owned_actual_RRP_transport(self):self.run_case(6)
    def test_wrong_actual_retry_epoch_quarantines_full_QP_and_SQ_owner(self):self.run_case(7)
    def test_SEND_plain_WR_to_real_coherent_SQ_and_SEND_CQ_without_RDMA_cast(self):self.run_case(8)
    def test_RECV_posts_real_coherent_WQEs_preserves_bad_wr_quota_and_unproved_MR_refs(self):self.run_case(9)
    def test_RNR_capable_actual_feature_profile_preserves_real_RECV_posting_and_refs(self):self.run_case(10)
    def test_receive_internal_receipt_profile_still_retains_unproved_CQ_and_MR_refs(self):self.run_case(11)
    def test_RECV_actual_length_distinct_CQ_quota_reuse_teardown_and_SEND_routing(self):self.run_case(12)
    def test_requester_CQ_full_feature_profile_preserves_actual_verbs_and_CQ_routing(self):self.run_case(13)
    def test_independent_SQ_RQ_real_QP_callbacks_SEND_before_RECV_with_distinct_rings(self):self.run_case(14)
    @classmethod
    def tearDownClass(cls):
        if name:=os.environ.get('AS02_RNIC_KERNEL_VERBS_REPORT'):
            current={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest()for n in cls.before}
            report=dict(scope=__doc__,pass_test=len(cls.reports)==15 and current==cls.before,
                source_sha256=cls.before,source_unchanged=current==cls.before,cases=cls.reports,
                compiler_command=cls.command,actual_callbacks_and_CSR_transport_executed=True,
                Linux_Hardware_memory_wire_core_drain_models=True,ib_device_registered=False,
                complete_standard_RC_or_user_provider=False,hardware_verified=False)
            with (ROOT/name).open('x')as out:out.write(json.dumps(report,indent=2)+'\n')
        cls.directory.cleanup()

if __name__=='__main__':unittest.main()
