# SPDX-License-Identifier: BSD-2-Clause-Views
"""Exact state-table derivative invariants; not actual RTL/physical proof."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[3]
spec=importlib.util.spec_from_file_location('state_profile',ROOT/'rdma/rnic/hls/state_table_fence_profile.py')
profile=importlib.util.module_from_spec(spec);spec.loader.exec_module(profile)

@unittest.skipUnless(profile.STATE.is_file(),'requires retained verified wrkey HLS source fixture')
class StateTableDerivationTests(unittest.TestCase):
    reports={}

    def evidence(self,**extra):
        files=[profile.STATE,Path(profile.__file__),Path(__file__)]
        self.reports[self._testMethodName]=dict(source_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in files},**extra)

    def test_all_original_ordinary_table_actions_and_types_are_exact(self):
        old=profile.STATE.read_text();new=profile.derive(old)
        for stream,request in [('rxIbh2stateTable_upd_req','rxRequest'),('txIbh2stateTable_upd_req','txRequest'),('qpi2stateTable_upd_req','ifRequest')]:
            _,left,end=profile.block(old,('if' if stream.startswith('rx')else 'else if')+' (!'+stream+'.empty())')
            normal=old[left+1:end-1].split(stream+'.read('+request+');',1)[1]
            self.assertEqual(new.count(normal),1)
        prefix=old[:old.index('template <int INSTID = 0>')]
        self.assertEqual(new[:len(prefix)],prefix)
        self.evidence(original_RX_TX_QPI_actions_copies=3,original_license_types_and_forward_declaration=True)

    def test_three_real_markers_not_idle_or_one_queue_success(self):
        new=profile.derive(profile.STATE.read_text())
        for source in range(3):
            self.assertIn('!seen['+str(source)+'] && !',new)
            self.assertIn('as02_state_marker(msg,'+str(source)+',token,seen',new)
            self.assertIn('pending_source='+str(source)+';have_pending=true;',new)
        self.assertIn('if(seen==7)',new)
        for comparison in ['msg.qpn!=token.qpn','msg.a!=token.a','msg.epoch!=token.epoch','msg.sequence!=token.sequence']:
            self.assertIn(comparison,new)
        self.assertIn('as02StateReq msg=pending;',new)
        self.assertIn('if(seen!=7 && !have_pending)',new)
        self.evidence(all_three_ordered_producers=True,registered_full168bit_identity=True,normal_requests_registered_without_action_changes=True,whole_core_drain=False)

    def test_real_BRAM_and_initialized_bitmap_not_zero_snapshot_fabrication(self):
        new=profile.derive(profile.STATE.read_text())
        self.assertIn('#pragma HLS bind_storage variable=state_table type=RAM_2P impl=BRAM',new)
        self.assertIn('#pragma HLS reset variable=state_table off',new)
        self.assertNotIn('HLS DEPENDENCE',new)
        self.assertIn('static ap_uint<MAX_QPS> initialized=0;',new)
        self.assertIn('if(msg.write)initialized[msg.qpn]=1;',new)
        self.assertIn('if(token.qpn<MAX_QPS && initialized[token.qpn])',new)
        self.assertIn('out.entry=state_table[token.qpn];',new)
        self.assertEqual(new.count('msg.bad || msg.qpn>=MAX_QPS'),3)
        self.assertIn('else if(!sampled.snapshot_valid)sampled.status=5;',new)
        self.evidence(original_BRAM_capacity_preserved=True,uninitialized_snapshot_denied=True,full16bit_range_checked_on_all_three=True)

    def test_changed_source_anchors_rejected_original_untouched(self):
        old=profile.STATE.read_text();before=hashlib.sha256(profile.STATE.read_bytes()).hexdigest()
        for anchor in ['void state_table(\t\t','template <int INSTID = 0>','\tstatic stateTableEntry state_table[MAX_QPS];','rxIbh2stateTable_upd_req.read(rxRequest);','txIbh2stateTable_upd_req.read(txRequest);','qpi2stateTable_upd_req.read(ifRequest);']:
            with self.assertRaises((ValueError,IndexError)):profile.derive(old.replace(anchor,'REMOVED_ANCHOR',1))
        profile.derive(old);self.assertEqual(before,hashlib.sha256(profile.STATE.read_bytes()).hexdigest())
        self.evidence(changed_anchors_rejected=6,original_unchanged=True)

    @classmethod
    def tearDownClass(cls):
        if name:=os.environ.get('AS02_RNIC_STATE_FENCE_DERIVATION_REPORT'):
            out=Path(name);out=out if out.is_absolute()else ROOT/out
            with out.open('x')as f:f.write(json.dumps(dict(scope=__doc__,pass_test=len(cls.reports)==4,methods=len(cls.reports),tests=cls.reports,hardware_verified=False),indent=2)+'\n')

if __name__=='__main__':unittest.main()
