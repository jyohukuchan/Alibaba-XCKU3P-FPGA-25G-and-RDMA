# SPDX-License-Identifier: BSD-2-Clause-Views
"""Timer derivative source invariants, NOT generated-RTL/physical proof."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[3]
spec=importlib.util.spec_from_file_location('timer_profile',ROOT/'rdma/rnic/hls/timer_state_fence_profile.py')
profile=importlib.util.module_from_spec(spec);spec.loader.exec_module(profile)

class TimerDerivationTests(unittest.TestCase):
    reports={}

    def evidence(self,**extra):
        files=[profile.TIMER,Path(profile.__file__),Path(__file__)]
        self.reports[self._testMethodName]=dict(source_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in files},**extra)

    def test_actual_original_license_table_scan_and_retransmission_unchanged(self):
        old=profile.TIMER.read_text();new=profile.derive(old)
        self.assertEqual(old[:old.index('struct rxTimerUpdate')],new[:new.index(profile.TYPES)])
        scan=old[old.index('// perform round robin'):]
        self.assertEqual(scan,new[new.index('// perform round robin'):])
        self.assertIn('#pragma HLS array_partition variable=transportTimerTable complete dim=1',new)
        self.assertIn('#pragma HLS reset variable=transportTimerTable',new)
        self.assertIn('#error Ordered timer-state proof requires',new)
        self.evidence(original_scan_retry_and_resettable_register_table=True)

    def test_normal_stop_and_TX_backoff_algorithm_are_not_replaced(self):
        old=profile.TIMER.read_text();new=profile.derive(old)
        a,l,b=profile.block(old,'else if (!txSetTimer_req.empty())')
        old_tx=old[l+1:b-1].split('txSetTimer_req.read(setQP);',1)[1]
        self.assertEqual(new.count(old_tx),2)
        a,l,b=profile.block(old,'if (!rxClearTimer_req.empty())')
        old_rx=old[l+1:b-1].split('rxClearTimer_req.read(tt_update);',1)[1]
        self.assertEqual(new.count(old_rx),1)
        self.evidence(original_TX_backoff_copies=2,original_RX_stop_copies=1)

    def test_real_snapshot_boundaries_and_full_width_fail_closed_guards(self):
        new=profile.derive(profile.TIMER.read_text())
        self.assertEqual(new.count('if(setQP>=MAX_QPS)'),2)
        self.assertIn('if(fence_request.qpn<MAX_QPS)',new)
        self.assertIn('fence_request.epoch==0 || fence_request.sequence==0',new)
        self.assertIn('fence_observed=out;',new)
        self.assertIn('else if(fence_phase==1)',new)
        self.assertIn('fence_rsp.write(fence_observed);',new)
        self.assertIn('fence_phase=0; // a late real start invalidates any old snapshot',new)
        self.assertIn('out.time=observed.time;out.retries=observed.retries;',new)
        self.evidence(full24bit_TX_range=True,actual_table_data=True,registered_sample_classify_emit=True,whole_core_drain=False)

    def test_changed_unique_anchors_fail_and_original_input_stays_identical(self):
        old=profile.TIMER.read_text();before=hashlib.sha256(profile.TIMER.read_bytes()).hexdigest()
        for anchor in ['struct rxTimerUpdate','static rxTimerUpdate tt_update;','void transport_timer(','\tstatic bool tt_WaitForWrite = false;']:
            with self.assertRaises((ValueError,IndexError)):profile.derive(old.replace(anchor,'REMOVED_ANCHOR',1))
        profile.derive(old)
        self.assertEqual(before,hashlib.sha256(profile.TIMER.read_bytes()).hexdigest())
        self.evidence(rejected_changed_anchors=4,baseline_unchanged=True)

    @classmethod
    def tearDownClass(cls):
        if name:=os.environ.get('AS02_RNIC_TIMER_DERIVATION_REPORT'):
            out=Path(name);out=out if out.is_absolute()else ROOT/out
            with out.open('x')as f:f.write(json.dumps(dict(scope=__doc__,pass_test=len(cls.reports)==4,methods=len(cls.reports),tests=cls.reports,hardware_verified=False),indent=2)+'\n')

if __name__=='__main__':unittest.main()
