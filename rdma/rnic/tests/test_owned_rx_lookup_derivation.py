# SPDX-License-Identifier: BSD-2-Clause-Views
"""Same-table lookup derivation invariants, not RTL/native/physical proof."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[3]
spec=importlib.util.spec_from_file_location('rx_lookup',ROOT/'rdma/rnic/hls/owned_rx_lookup_profile.py')
p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)

@unittest.skipUnless(p.META.is_file(),'requires retained verified source fixture')
class OwnedRxLookupDerivationTests(unittest.TestCase):
    reports={}
    def evidence(self,**kw):
        files=[Path(__file__),Path(p.__file__),Path(p.base.__file__),Path(p.base.base.__file__),Path(p.base.base.base.__file__),
            p.META,p.TIMER,p.TOP,ROOT/'rdma/rnic/rtl/rocev2_retrans_pool.v',ROOT/'rdma/rnic/rtl/rocev2_owned_timer_retrans.v',
            ROOT/'rdma/rnic/rtl/rocev2_owned_rx_lookup.v',ROOT/'rdma/rnic/tests/probe_owned_rx_lookup.py',
            ROOT/'rdma/rnic/tests/probe_owned_rx_lookup_xsim.py',ROOT/'rdma/rnic/tests/probe_owned_rx_lookup_compiled.py',ROOT/'rdma/rnic/tests/owned_rx_lookup_tb.v']
        self.reports[self._testMethodName]=dict(source_sha256={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest()for f in files},**kw)
    def derived(self):return p.derive(p.META.read_text())
    def test_same_real_pointer_and_metadata_not_shadow_owner_table(self):
        old=p.META.read_text();new=self.derived();self.assertTrue(new.startswith(old))
        selected=new[len(old):]
        self.assertEqual(selected.count('void as02_owned_pointer_table('),1)
        self.assertEqual(selected.count('void as02_owned_meta_table('),1)
        self.assertEqual(selected.count('meta_table[META_TABLE_SIZE]'),1)
        self.assertIn('preq.write(pointerReq(ap_uint<16>(rx_query.qpn),true))',p.STATES)
        self.assertIn('mreq.write(as02OwnedMetaReq(curr))',p.STATES)
        self.assertNotIn('shadow',p.STATES)
        self.evidence(actual_one_pointer_one_metadata_function=True,no_new_shadow_owner_RAM=True,original_licensed_prefix_unchanged=True)
    def test_full_lease_epoch_generation_sequence_and_full_QPN_guards(self):
        for guard in ['rx_query.qpn>=MAX_QPS','rx_query.epoch==0','meta.lease(15,0)!=curr',
            'meta.lease(79,16)==0','meta.lease(95,80)!=rx_query.qpn','meta.lease(183,120)!=lookup_epoch',
            'meta.lease(79,16)<=lookup_generation','meta.lease(247,184)<lookup_sequence',
            'lookup_found=meta.lease']:
            self.assertIn(guard,p.STATES)
        self.assertIn('q.qpn=r(23,0)',p.DECODE)
        self.assertIn('lookup_status=3',p.STATES)
        self.evidence(full24_QPN_checked_before16bit_table_request=True,actual_immutable248lease=True,trusted_epoch_not_generated_from_current_owner=True)
    def test_walk_full_list_and_reject_multiple_matches(self):
        for guard in ['lookup_matches++','lookup_matches==1?0:(lookup_matches==0?1:2)',
            'lookup_walked>=META_TABLE_SIZE','curr!=ptr.tail','meta.next>=META_TABLE_SIZE',
            'curr=meta.next;state=RX_READ']:
            self.assertIn(guard,p.STATES)
        self.assertIn('if(lookup_status==0) {lookup_result(247,0)=lookup_found',p.STATES)
        self.assertIn('lookup_result=0;',p.STATES)
        self.evidence(full2000bound_not_first_match=True,ambiguous_result_no_selected_lease=True,pointer_root_not_persistent_metadata_valid_only=True)
    def test_wide_length_rounding_modular_PSN_and_opaque_control_syndrome(self):
        self.assertIn('ap_uint<33> rounded=ap_uint<33>(meta.length)+ap_uint<33>(PMTU-1)',p.STATES)
        self.assertIn('lookup_span=rounded/PMTU',p.STATES)
        self.assertIn('lookup_candidate_delta=ap_uint<24>(rx_query.psn-meta.psn)',p.STATES)
        self.assertIn('rx_query.syndrome(7,5)!=0',p.STATES)
        self.assertIn('lookup_result(419,412)=rx_query.syndrome',p.STATES)
        self.evidence(full32bit_length_widened_before_rounding=True,PSN_wrap_delta_not_signed_current_owner_guess=True,RNR_NAK_not_completion=True)
    def test_lookup_has_no_metadata_write_free_timer_clear_or_CQ(self):
        self.assertNotIn('release_req.write',p.STATES)
        self.assertNotIn('timer_controls.write',p.STATES)
        self.assertNotIn('rdinit.write',p.STATES)
        self.assertNotIn('as02OwnedMetaReq(curr,',p.STATES)
        self.assertIn('pupd.write(pointerUpdate(ap_uint<16>(rx_query.qpn),ptr))',p.STATES)
        self.assertIn('lookup_receipt!=lookup_result',p.STATES)
        self.assertLess(p.STATES.index('lookup_receipt!=lookup_result'),p.STATES.index('case RX_UNLOCK:'))
        self.evidence(actual_lock_only_unlock_after_exact_receipt=True,no_lookup_retirement_or_native_CQ=True)
    def test_fifth_query_marker_required_and_private_real_output_receipt(self):
        new=self.derived();wrapper=(ROOT/'rdma/rnic/rtl/rocev2_owned_rx_lookup.v').read_text()
        self.assertEqual(wrapper,p.derive_wrapper((ROOT/'rdma/rnic/rtl/rocev2_owned_timer_retrans.v').read_text()))
        for anchor in ['static ap_uint<5> seen=0','if(seen==31 && !have_insert)',
            'seen[4] && !have_insert && !timer_closed','r[310]=seen[4]']:
            self.assertIn(anchor,new)
        self.assertIn('if(m_rx_binding_valid && m_rx_binding_ready)',wrapper)
        self.assertIn('lookup_ack<=m_rx_binding_data',wrapper)
        self.assertNotIn('input wire [447:0] s_rx_accept',wrapper)
        self.assertIn('raw_fence[310]!==1\'b1',wrapper)
        self.evidence(fifth_same_queue_query_marker_required=True,wrapper_receipt_not_externally_injectable=True,whole_wire_producer_closure=False)
    def test_source_changes_fail_closed_and_no_clock_geometry_cut(self):
        old=(ROOT/'rdma/rnic/rtl/rocev2_owned_timer_retrans.v').read_text()
        with self.assertRaises(ValueError):p.derive_wrapper(old.replace('as02_owned_timer_retrans_top process_and_tables(','REMOVED_ACTUAL_CORE'))
        self.assertIn('AS02_TIMER_CLOCK_PS 4000',(p.BASE/'adapter/rocev2_config.hpp').read_text())
        self.assertIn('lookup_walked>=META_TABLE_SIZE',p.STATES)
        self.assertIn("rx_query.qpn>=MAX_QPS",p.STATES)
        self.evidence(original4ns_8QP_2000metadata_not_reduced=True,changed_production_core_anchor_rejected=True,not_physical_signoff=True)
    @classmethod
    def tearDownClass(cls):
        if name:=os.environ.get('AS02_RNIC_RX_LOOKUP_DERIVATION_REPORT'):
            path=Path(name);path=path if path.is_absolute()else ROOT/path
            run=Path(tempfile.mkdtemp(prefix='owned-rx-lookup-unit-',dir=ROOT/'rdma/rnic/build'));inp=run/'inputs';inp.mkdir()
            identities={n:h for v in cls.reports.values()for n,h in v['source_sha256'].items()}
            for n,h in identities.items():
                f=ROOT/n;assert hashlib.sha256(f.read_bytes()).hexdigest()==h,n
                target=inp/n;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,target)
            frozen={str(f.relative_to(inp)):hashlib.sha256(f.read_bytes()).hexdigest()for f in inp.rglob('*')if f.is_file()}
            with path.open('x')as out:out.write(json.dumps(dict(scope=__doc__,pass_test=len(cls.reports)==7,methods=len(cls.reports),tests=cls.reports,
                retained_directory=str(run.relative_to(ROOT)),frozen_source_sha256=frozen,RTL_tested=False,native_CQ=False,hardware_verified=False),indent=2)+'\n')
if __name__=='__main__':unittest.main()
