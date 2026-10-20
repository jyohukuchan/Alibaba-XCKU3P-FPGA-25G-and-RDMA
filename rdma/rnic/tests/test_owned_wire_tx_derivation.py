# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual TX producer source/ABI invariants, not RTL/native/physical proof."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[3]
spec=importlib.util.spec_from_file_location('wire_tx',ROOT/'rdma/rnic/hls/owned_wire_tx_profile.py')
p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)

@unittest.skipUnless(p.CPP.is_file(),'requires retained verified FNS fixture')
class OwnedWireTxDerivationTests(unittest.TestCase):
    reports={}
    def evidence(self,**kw):
        files=[Path(__file__),Path(p.__file__),p.CPP,p.HPP,p.META,
            ROOT/'rdma/rnic/hls/test_owned_wire_tx.cpp',ROOT/'rdma/rnic/hls/owned_wire_tx_top.cpp',
            ROOT/'rdma/rnic/hls/owned_wire_tx_synth.tcl']
        self.reports[self._testMethodName]=dict(source_sha256={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest()for f in files},**kw)
    def derived(self):return p.derive(p.CPP.read_text(),p.HPP.read_text(),p.META.read_text())
    def test_actual_five_complete_licensed_producers_and_comment_braces(self):
        original=p.CPP.read_text();new=self.derived()
        self.assertTrue(new.startswith(original[:original.index('#include')]))
        for name in ['local_req_handler','meta_merger','generate_ibh','generate_exh','merge_retrans_request']:
            self.assertEqual(new.count('void as02_owned_wire_'+name+'('),1)
            self.assertTrue(p.function(original,name).rstrip().endswith('}'))
        synthetic='void trial() { // { not code\n const char* x="}"; /* } */ if(1){} } AFTER'
        start,left,end=p.source_block(synthetic,'void trial(')
        self.assertEqual(synthetic[end:],' AFTER')
        self.evidence(real_five_FNS_function_bodies=True,license_preserved=True,comments_not_Cpp_scopes=True)
    def test_original_struct_fields_constructors_retained_with_owner(self):
        for source,name,new in [(p.HPP.read_text(),'txMeta','as02WireTxMeta'),(p.HPP.read_text(),'event','as02WireEvent'),
            (p.HPP.read_text(),'ibhMeta','as02WireIBHMeta'),(p.META.read_text(),'retransMeta','as02WireRetransMeta'),
            (p.META.read_text(),'retransAddrLen','as02WireAddrLen')]:
            at,_,end=p.source_block(source,'struct '+name+'\n')
            derived=p.struct(source,name,new).replace('\n    as02WireContext owner;','').replace(new,name)
            self.assertEqual(derived,source[at:end+1])
        self.evidence(original_fields_and_constructors_exact=True,full_context_not_late_QP_lookup=True)
    def test_actual_local_READ_WRITE_and_retry_keep_full_context(self):
        s=self.derived()
        self.assertEqual(s.count('ev.owner=meta.owner;'),2)
        for guard in ['owned_event.lease(79,16)==0','owned_event.lease(15,0)>=META_TABLE_SIZE',
            'owned_event.marker','retry_owner.lease=owned_event.lease','ev.owner=retry_owner',
            'meta.owner.retry || meta.owner.lease!=0','c(191,144)!=0','r(247,241)!=0']:
            self.assertIn(guard,s)
        self.evidence(actual_two_local_branches_and_immutable_retry_lease=True,invalid_context_refused=True,producer_fence_not_fabricated=True)
    def test_real_PSN_addrlen_owner_join_checks_before_insertion(self):
        s=self.derived();at=s.index('void as02_owned_wire_merge_retrans_request(');join=s[at:]
        self.assertIn('!as02_wire_same(meta.owner,addrlen.owner)',join)
        self.assertLess(join.index('error=6;return;'),join.index('tx2retrans_insertRequest.write(out)'))
        self.assertIn('out.epoch=meta.owner.epoch;out.sequence=meta.owner.sequence',join)
        self.assertIn('a.epoch==b.epoch && a.sequence==b.sequence && a.lease==b.lease',s)
        self.assertIn('qpState.req_next_psn, meta.op_code),meta.owner)',s)
        self.evidence(actual_generated_PSN_joined_to_same_WR_address=True,full_epoch_sequence_checked=True,no_registration_on_mismatch=True)
    def test_actual_EXH_timer_position_and_original_key_policy_retained(self):
        s=self.derived()
        self.assertIn('txSetTimer_req.write(meta.owner)',s)
        self.assertEqual(s.count('rdmaHeader.setRemoteKey(meta.rkey_valid ? meta.rkey : msnMeta.r_key)'),2)
        self.assertIn('as02_wire_tag(as02WireIBHMeta(ev.op_code, key, ev.qpn, ev.psn, ev.validPsn),ev.owner)',s)
        self.assertIn('create_clock -period 4.0',(ROOT/'rdma/rnic/hls/owned_wire_tx_synth.tcl').read_text())
        self.assertIn('AS02_TIMER_CLOCK_PS 4000',(p.BASE/'adapter/rocev2_config.hpp').read_text())
        self.evidence(actual_EXH_start_has_full_owner=True,original_clock_and_explicit_key_zero_preserved=True,MAC_SFD_and_native_join=False)
    def test_missing_critical_anchors_cannot_silently_generate(self):
        original=p.CPP.read_text()
        anchor='tx2retrans_insertMeta.write(retransMeta(meta.dest_qp, qpState.req_next_psn, meta.op_code));'
        self.assertEqual(original.count(anchor),1)
        with self.assertRaises((ValueError,IndexError)):
            p.derive(original.replace(anchor,'REMOVED_CRITICAL_REAL_PRODUCER'),p.HPP.read_text(),p.META.read_text())
        self.evidence(real_producer_source_change_fails_closed=True,not_regex_only_function_stub=True)
    def test_header_words_keep_full_index_partial_lanes_and_all_real_sites(self):
        helper=p.HEADER_WORD;s=self.derived()
        self.assertIn('const uint16_t index=h.idx',helper)
        self.assertIn('if(index==i)',helper)
        self.assertIn('word(BITS-i*WIDTH-1,0)=h.header(BITS-1,i*WIDTH)',helper)
        self.assertIn('h.idx=i+1',helper)
        self.assertNotIn('h.idx=',helper[helper.index('return remaining;'):])
        self.assertEqual(s.count('as02_owned_wire_consume_word<WIDTH,RETH_SIZE>(rdmaHeader,sendWord.data)'),2)
        self.assertEqual(s.count('as02_owned_wire_consume_word<WIDTH,AETH_SIZE>(ackHeader,sendWord.data)'),2)
        self.assertNotIn('rdmaHeader.consumeWord(sendWord.data)',s)
        original=p.CPP.read_text()
        with self.assertRaises(ValueError):
            p.derive(original.replace('rdmaHeader.consumeWord(sendWord.data)','REMOVED_CONSUMER',1),p.HPP.read_text(),p.META.read_text())
        self.evidence(all_actual_RETH_and_AETH_consumer_sites=True,original_full16bit_index_preserved=True,
            constant_cases_not_index_truncation=True,partial_unused_lanes_preserved=True,source_invariant_not_equivalence_test=True)
    @classmethod
    def tearDownClass(cls):
        if name:=os.environ.get('AS02_RNIC_OWNED_WIRE_TX_DERIVATION_REPORT'):
            path=Path(name);path=path if path.is_absolute()else ROOT/path
            run=Path(tempfile.mkdtemp(prefix='owned-wire-tx-unit-',dir=ROOT/'rdma/rnic/build'));inp=run/'inputs';inp.mkdir()
            identities={n:h for v in cls.reports.values()for n,h in v['source_sha256'].items()}
            for n,h in identities.items():
                f=ROOT/n;assert hashlib.sha256(f.read_bytes()).hexdigest()==h,n
                target=inp/n;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,target)
            frozen={str(f.relative_to(inp)):hashlib.sha256(f.read_bytes()).hexdigest()for f in inp.rglob('*')if f.is_file()}
            with path.open('x')as out:out.write(json.dumps(dict(scope=__doc__,pass_test=len(cls.reports)==7,methods=len(cls.reports),tests=cls.reports,
                retained_directory=str(run.relative_to(ROOT)),frozen_source_sha256=frozen,RTL_tested=False,hardware_verified=False),indent=2)+'\n')
if __name__=='__main__':unittest.main()
