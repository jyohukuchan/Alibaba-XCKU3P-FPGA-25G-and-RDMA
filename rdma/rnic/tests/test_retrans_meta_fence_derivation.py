# SPDX-License-Identifier: BSD-2-Clause-Views
"""Full metadata consumer source invariants, not allocator/core/CQ proof."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[3]
spec=importlib.util.spec_from_file_location('meta_profile',ROOT/'rdma/rnic/hls/retrans_meta_fence_profile.py')
profile=importlib.util.module_from_spec(spec);spec.loader.exec_module(profile)

@unittest.skipUnless(profile.META.is_file(),'requires retained verified wrkey HLS source fixture')
class MetaDerivationTests(unittest.TestCase):
    reports={}
    def evidence(self,**extra):
        files=[profile.META,Path(profile.__file__),Path(__file__)]
        self.reports[self._testMethodName]=dict(source_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in files},**extra)
    def test_complete_original_header_and_normal_write_append_read_actions_exact(self):
        old=profile.META.read_text();new=profile.derive(old);self.assertTrue(new.startswith(old));new=new[len(old):]
        _,left,end=profile.block(old,'if (!meta_upd_req.empty())')
        normal=old[left+1:end-1].split('meta_upd_req.read(req);',1)[1]
        self.assertEqual(new.count(normal),1)
        self.evidence(original_complete_header_and_normal_actions_exact=True)
    def test_actual_full2000_BRAM_clear_preserved_false_dependency_removed_only_in_derivative(self):
        old=profile.META.read_text();new=profile.derive(old)[len(old):]
        self.assertIn('const uint32_t META_TABLE_SIZE = 2000;',old)
        self.assertIn('static retransMetaEntry meta_table[META_TABLE_SIZE];',new)
        self.assertIn('#pragma HLS bind_storage variable=meta_table type=RAM_T2P impl=BRAM',new)
        self.assertNotIn('HLS DEPENDENCE',new)
        a,_,end=profile.block(old,'if (!clear_complete)')
        self.assertEqual(new.count(old[a:end]),1)
        self.assertIn('meta_table[clear_index] = zero;',new)
        self.assertIn('clear_index == META_TABLE_SIZE - 1',new)
        self.evidence(all2000entries_actual_clear_unchanged=True,real_RAW_WAR_WAW_not_waived=True)
    def test_ordered_actual_snapshot_full_ranges_not_valid_bit_ownership_inference(self):
        new=profile.derive(profile.META.read_text())[len(profile.META.read_text()):]
        self.assertIn('m.normal.idx>=META_TABLE_SIZE',new)
        self.assertIn('m.normal.entry.next>=META_TABLE_SIZE',new)
        self.assertIn('token.normal.idx<META_TABLE_SIZE && token.qpn<MAX_QPS',new)
        self.assertIn('out.entry=meta_table[token.normal.idx]',new)
        self.assertIn('token.epoch==0 || token.sequence==0',new)
        self.assertIn('bool capture_allowed=!pending && (!executing || !work.marker)',new)
        self.assertIn('work=meta_upd_req.read();have_work=true;',new)
        self.assertNotIn('sampled.entry.valid',new)
        self.assertIn('else sampled.status=0; // committed DATA only, NEVER active/free',new)
        self.evidence(full16bit_index_QPN_range=True,actual_table_data=True,registered_ordered_request=True,valid_is_not_allocator_ownership=True,whole_core_drain=False)
    def test_changed_unique_anchors_rejected_original_untouched(self):
        old=profile.META.read_text();before=hashlib.sha256(profile.META.read_bytes()).hexdigest()
        for anchor in ['void retrans_meta_table(','\t#pragma HLS DEPENDENCE variable=meta_table inter false','\tretransMetaReq req;','meta_upd_req.read(req);']:
            with self.assertRaises((ValueError,IndexError)):profile.derive(old.replace(anchor,'REMOVED',1))
        profile.derive(old);self.assertEqual(before,hashlib.sha256(profile.META.read_bytes()).hexdigest())
        self.evidence(rejected_anchors=4,original_unchanged=True)
    @classmethod
    def tearDownClass(cls):
        if name:=os.environ.get('AS02_RNIC_META_DERIVATION_REPORT'):
            p=Path(name);p=p if p.is_absolute()else ROOT/p
            with p.open('x')as out:out.write(json.dumps(dict(scope=__doc__,pass_test=len(cls.reports)==4,methods=len(cls.reports),tests=cls.reports,hardware_verified=False),indent=2)+'\n')
if __name__=='__main__':unittest.main()
