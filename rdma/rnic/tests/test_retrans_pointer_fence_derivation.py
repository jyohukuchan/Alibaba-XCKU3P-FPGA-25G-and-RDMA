# SPDX-License-Identifier: BSD-2-Clause-Views
"""Real pointer consumer source invariants, not actual RTL/full-core proof."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[3]
spec=importlib.util.spec_from_file_location('pointer_profile',ROOT/'rdma/rnic/hls/retrans_pointer_fence_profile.py')
profile=importlib.util.module_from_spec(spec);spec.loader.exec_module(profile)

@unittest.skipUnless(profile.POINTER.is_file(),'requires retained verified wrkey HLS source fixture')
class PointerDerivationTests(unittest.TestCase):
    reports={}
    def evidence(self,**extra):
        files=[profile.POINTER,Path(profile.__file__),Path(__file__)]
        self.reports[self._testMethodName]=dict(source_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in files},**extra)
    def test_original_header_and_normal_update_request_wait_actions_exact(self):
        old=profile.POINTER.read_text();new=profile.derive(old)
        self.assertTrue(new.startswith(old));new=new[len(old):]
        for anchor,stream,req in [('if (!pointerUpdFifo.empty())','pointerUpdFifo','upd'),('else if (!pointerReqFifo.empty() && !pt_wait)','pointerReqFifo','pt_req')]:
            _,left,end=profile.block(old,anchor);normal=old[left+1:end-1].split(stream+'.read('+req+');',1)[1]
            self.assertEqual(new.count(normal),1)
        a,_,end=profile.block(old,'else if (pt_wait && !pt_isLocked)')
        self.assertEqual(new.count(old[a:end]),1)
        self.evidence(complete_original_header=True,normal_update_request_wait_actions_exact=True)
    def test_real_BRAM_all_eight_cleared_before_consuming_not_bitmap_fabrication(self):
        new=profile.derive(profile.POINTER.read_text())[len(profile.POINTER.read_text()):]
        self.assertIn('ptr_table[clear_index]=zero;',new)
        self.assertIn('if(clear_index==MAX_QPS-1)clear_complete=true;',new)
        self.assertIn('#pragma HLS reset variable=ptr_table off',new)
        self.assertIn('#pragma HLS bind_storage variable=ptr_table type=RAM_T2P impl=BRAM',new)
        self.assertLess(new.index('if(!clear_complete)'),new.index('pointerUpdFifo.read()'))
        self.assertNotIn('HLS DEPENDENCE',new)
        self.evidence(real_addressed_full_table_init=True,BRAM_and_RAW_preserved=True)
    def test_both_markers_full168bit_identity_actual_pointer_and_global_lock(self):
        new=profile.derive(profile.POINTER.read_text())[len(profile.POINTER.read_text()):]
        for source in range(2):
            self.assertIn('!seen['+str(source)+'] && !',new)
            self.assertIn('marker_source='+str(source)+';marker_pending=true;',new)
        for field in ['qpn','psn','epoch','sequence']:self.assertIn('m.'+field+'!=token.'+field,new)
        self.assertIn('else if(seen==3)',new)
        self.assertIn('out.entry=ptr_table[token.qpn]',new)
        self.assertIn('out.locked=pt_isLocked;out.waiting=pt_wait;',new)
        self.assertIn('sampled.entry.valid || sampled.locked || sampled.waiting',new)
        self.assertIn('m.head>=META_TABLE_SIZE || m.tail>=META_TABLE_SIZE',new)
        self.assertEqual(new.count('m.bad || m.qpn>=MAX_QPS'),2)
        self.evidence(actual_table_and_global_lock=True,full16bit_QPN_guard=True,metadata_capacity_2000_not_reduced=True,whole_core_drain=False)
    def test_changed_unique_anchors_rejected_original_untouched(self):
        old=profile.POINTER.read_text();before=hashlib.sha256(profile.POINTER.read_bytes()).hexdigest()
        for anchor in ['void retrans_pointer_table(','static retransPointerEntry ptr_table[MAX_QPS];','static ap_uint<16> pt_lockedQP;','pointerUpdFifo.read(upd);','pointerReqFifo.read(pt_req);']:
            with self.assertRaises((ValueError,IndexError)):profile.derive(old.replace(anchor,'REMOVED',1))
        profile.derive(old);self.assertEqual(before,hashlib.sha256(profile.POINTER.read_bytes()).hexdigest())
        self.evidence(rejected_anchors=5,original_unchanged=True)
    @classmethod
    def tearDownClass(cls):
        if name:=os.environ.get('AS02_RNIC_POINTER_DERIVATION_REPORT'):
            p=Path(name);p=p if p.is_absolute()else ROOT/p
            with p.open('x')as out:out.write(json.dumps(dict(scope=__doc__,pass_test=len(cls.reports)==4,methods=len(cls.reports),tests=cls.reports,hardware_verified=False),indent=2)+'\n')
if __name__=='__main__':unittest.main()
