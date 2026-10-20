# SPDX-License-Identifier: BSD-2-Clause-Views
"""Owned FNS derivation invariants, not functional/physical/native proof."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[3]
spec=importlib.util.spec_from_file_location('owned_profile',ROOT/'rdma/rnic/hls/owned_retrans_profile.py')
profile=importlib.util.module_from_spec(spec);spec.loader.exec_module(profile)

@unittest.skipUnless(profile.META.is_file(),'requires retained verified wrkey HLS fixture')
class OwnedDerivationTests(unittest.TestCase):
    reports={}
    def evidence(self,**kw):
        files=[profile.META,Path(profile.__file__),Path(__file__),ROOT/'rdma/rnic/hls/owned_retrans_top.cpp']
        self.reports[self._testMethodName]=dict(source_sha256={str(q.relative_to(ROOT)):hashlib.sha256(q.read_bytes()).hexdigest()for q in files},**kw)
    def test_complete_original_prefix_original_capacities_and_table_actions_retained(self):
        old=profile.META.read_text();new=profile.derive(old);self.assertTrue(new.startswith(old));new=new[len(old):]
        self.assertIn('const uint32_t META_TABLE_SIZE = 2000;',old)
        self.assertIn('static as02OwnedMetaEntry meta_table[META_TABLE_SIZE];',new)
        self.assertIn('static retransPointerEntry ptr_table[MAX_QPS];',new)
        self.assertNotIn('HLS DEPENDENCE',new)
        a,_,e=profile.block(old,'if (!clear_complete)')
        self.assertIn(old[a:e].replace('retransMetaEntry','as02OwnedMetaEntry'),new)
        for action in ['meta_table[req.idx] = req.entry;','meta_table[req.idx].next = req.entry.next;',
            'meta_table[req.idx].isTail = false;','meta_rsp.write(meta_table[req.idx]);',
            'ptr_table[upd.qpn] = upd.entry;','pt_wait = true;']:
            self.assertIn(action,new)
        self.evidence(licensed_original_unchanged=True,actual2000metadata_and8pointer_geometry=True,real_dependencies_not_waived=True)
    def test_real_pool_full_immutable_lease_not_bare_indices_or_mutable_PSN(self):
        old=profile.META.read_text();new=profile.derive(old)[len(old):]
        self.assertIn('ap_uint<248> lease = 0;',new)
        self.assertIn('lease(token), valid(true)',new)
        self.assertIn('r(247,80)!=as02_owner(insert.normal.qpn,insert.normal.psn,insert.epoch,insert.sequence)',new)
        self.assertIn('return_lease=meta.lease;',new)
        self.assertIn('r(247,0)!=return_lease',new)
        self.assertIn('meta.psn+=1;',new)
        self.assertIn('as02OwnedMetaEntry(meta)',new)
        self.assertNotIn('freeListFifo',new);self.assertNotIn('releaseFifo',new)
        self.assertNotIn('freelist_handler',new)
        self.evidence(full248immutable_lease_on_metadata_event_RDinit=True,actual_external_offer_and_exact_return_ack=True,mutable_protocol_PSN_not_used_for_return=True)
    def test_full_pool_ACK_liveness_and_full_context_before_side_effects(self):
        old=profile.META.read_text();new=profile.derive(old)[len(old):]
        self.assertIn('pool_initialized && credit!=0 && !inserts.empty()',new)
        self.assertLess(new.index('if(!updates.empty())'),new.index('credit!=0'))
        self.assertIn('meta.lease(15,0)!=curr',new)
        self.assertIn('!as02_wr_matches(meta.lease,update.normal.qpn,update.epoch,update.sequence)',new)
        self.assertIn('!as02_wr_matches(meta.lease,retry.normal.qpn,retry.epoch,retry.sequence)',new)
        self.assertIn('meta.psn!=update.normal.latest_acked_req',new)
        self.assertIn('req.idx>=META_TABLE_SIZE',new)
        self.assertIn('pt_req.qpn>=MAX_QPS',new)
        self.assertIn('upd.qpn>=MAX_QPS',new)
        self.assertNotIn('drained=true',new);self.assertNotIn('CQE',new.replace('never fabricate retirement/CQ/unpin',''))
        self.evidence(fullQPN_and_WR_context_guards=True,credit0_does_not_hide_ACK=True,whole_core_drain=False)
    def test_changed_unique_anchors_rejected_and_original_file_unchanged(self):
        old=profile.META.read_text();before=hashlib.sha256(profile.META.read_bytes()).hexdigest()
        for anchor in ['struct retransMetaEntry\n','void retrans_pointer_table(',
            'void retrans_meta_table(','\t#pragma HLS DEPENDENCE variable=meta_table inter false']:
            with self.assertRaises((ValueError,IndexError)):profile.derive(old.replace(anchor,'REMOVED',1))
        profile.derive(old);self.assertEqual(before,hashlib.sha256(profile.META.read_bytes()).hexdigest())
        self.evidence(changed_anchors_rejected=4,original_unchanged=True)
    @classmethod
    def tearDownClass(cls):
        if name:=os.environ.get('AS02_RNIC_OWNED_DERIVATION_REPORT'):
            p=Path(name);p=p if p.is_absolute()else ROOT/p
            with p.open('x')as out:out.write(json.dumps(dict(scope=__doc__,pass_test=len(cls.reports)==4,methods=len(cls.reports),tests=cls.reports,hardware_verified=False),indent=2)+'\n')
if __name__=='__main__':unittest.main()
