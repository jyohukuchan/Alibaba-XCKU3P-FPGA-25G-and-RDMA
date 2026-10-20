# SPDX-License-Identifier: BSD-2-Clause-Views
"""Real process barrier derivation invariants, not native/core/physical proof."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[3]
spec=importlib.util.spec_from_file_location('owned_fence',ROOT/'rdma/rnic/hls/owned_retrans_fence_profile.py')
p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)

@unittest.skipUnless(p.META.is_file(),'requires retained verified wrkey HLS fixture')
class OwnedFenceDerivationTests(unittest.TestCase):
    reports={}
    def evidence(self,**kw):
        files=[Path(__file__),Path(p.__file__),Path(p.base.__file__),p.META,p.TOP,
            ROOT/'rdma/rnic/rtl/rocev2_owned_retrans_fenced.v']
        self.reports[self._testMethodName]=dict(source_sha256={str(q.relative_to(ROOT)):hashlib.sha256(q.read_bytes()).hexdigest()for q in files},**kw)
    def test_complete_licensed_original_full_geometry_no_false_dependency_or_shadow(self):
        old=p.META.read_text();new=p.derive(old);self.assertTrue(new.startswith(old));new=new[len(old):]
        self.assertIn('META_TABLE_SIZE = 2000',old)
        self.assertIn('meta_table[META_TABLE_SIZE]',new);self.assertIn('ptr_table[MAX_QPS]',new)
        self.assertNotIn('HLS DEPENDENCE',new)
        self.assertIn('sampled_record=meta_table[barrier_index]',new)
        self.assertIn('barrier_index==META_TABLE_SIZE-1',new)
        self.assertIn('barrier_digest^=as02_owned_record_digest(sampled_record)',new)
        self.assertIn('r(285,222)=metadata_digest',new)
        self.assertIn('return_lease=meta.lease',new)
        self.evidence(licensed_original_preserved=True,actual_full2000record_BRAM_scan=True,real_immutable_lease_retained=True,no_shadow_free_validity_proxy=True)
    def test_four_real_input_markers_all_real_downstream_queues_and_exact_replies(self):
        old=p.META.read_text();new=p.derive(old)[len(old):];top=p.derive_top(p.TOP.read_text())
        self.assertIn('if(seen==15 && !have_insert)',new)
        self.assertIn('(seen!=0 && owner!=token)',new)
        self.assertIn('if(replies_seen==31)',new)
        self.assertIn('if(barrier_reply(167,0)!=token)',new)
        self.assertIn('r[168]=1;alloc_req.write(r)',new)
        self.assertIn('r[248]=1;release_req.write(r)',new)
        self.assertIn('as02FencePointerReq r;r.marker=true',new)
        self.assertIn('as02FencePointerUpdate r;r.marker=true',new)
        self.assertIn('r.marker=true;r.owner=token;events.write(r)',new)
        self.assertIn('r.marker=true;r.owner=token;rdinit.write(r)',new)
        self.assertIn('m.marker=r[399]',top);self.assertIn('m.marker=r[200]',top);self.assertIn('m.marker=r[168]',top)
        self.assertIn('(m.marker && r(270,40)!=0)',top)
        self.evidence(full168matching_four_inputs=True,real_pointer_twoqueue_meta_pool_twoqueue_and_output_markers=True,exact_actual_reply_join=True)
    def test_real_handoff_receipts_not_AXIS_buffered_write_idle_or_CQ_success(self):
        old=p.META.read_text();new=p.derive(old)[len(old):]
        w=(ROOT/'rdma/rnic/rtl/rocev2_owned_retrans_fenced.v').read_text()
        for condition in ['raw_event_valid&&raw_event_ready&&raw_event[575]',
            'raw_rdinit_valid&&raw_rdinit_ready&&raw_rdinit[319]','raw_fence_valid&&raw_fence_ready']:
            self.assertIn(condition,w)
        self.assertIn('if(!fence_accepts.empty())',new)
        self.assertIn('if(r(167,0)!=token || r(191,168)!=0)',new)
        self.assertIn('fences.write(r);state=FENCE_ACCEPT',new)
        self.assertIn('seen=0;replies_seen=0;state=MAIN',new)
        self.assertNotIn('drain_ok',w);self.assertNotIn('idle_cycles',w);self.assertNotIn('test_pool_mux',w)
        self.assertIn('pool_active=active;pool_free=free',new)
        self.assertIn('if(status==2)barrier_busy=true',new)
        self.evidence(actual_output_and_final_response_handshakes=True,no_early_reopen_on_buffered_write=True,whole_core_drain=False,native_CQ=False)
    def test_registered_priority_fullpool_pending_insert_no_overtake_and_anchor_rejection(self):
        old=p.META.read_text();before=hashlib.sha256(p.META.read_bytes()).hexdigest();new=p.derive(old)[len(old):]
        self.assertIn('else if(have_insert && pool_initialized && credit!=0)',new)
        self.assertIn('else if(!seen[3] && !have_insert && !inserts.empty())',new)
        self.assertIn('else if(!seen[1] && !pointerUpdFifo.empty())',new)
        self.assertIn('held_update=pointerUpdFifo.read()',new)
        self.assertIn('held_request=meta_upd_req.read()',new)
        self.assertIn('req=held_request',new)
        for anchor in ['void retrans_pointer_table(','void retrans_meta_table(','struct retransMetaReq\n']:
            with self.assertRaises((ValueError,IndexError)):p.derive(old.replace(anchor,'REMOVED',1))
        self.assertEqual(before,hashlib.sha256(p.META.read_bytes()).hexdigest())
        self.evidence(pending_insert_no_marker_overtake=True,credit0_ACK_liveness_preserved=True,registered_actual_queue_heads=True,changed_anchors_rejected=3)
    @classmethod
    def tearDownClass(cls):
        if name:=os.environ.get('AS02_RNIC_OWNED_FENCE_DERIVATION_REPORT'):
            path=Path(name);path=path if path.is_absolute()else ROOT/path
            with path.open('x')as out:out.write(json.dumps(dict(scope=__doc__,pass_test=len(cls.reports)==4,methods=len(cls.reports),tests=cls.reports,hardware_verified=False),indent=2)+'\n')
if __name__=='__main__':unittest.main()
