# SPDX-License-Identifier: BSD-2-Clause-Views
"""Wire RX derivation/ownership invariants, not native/physical proof."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[3]
spec=importlib.util.spec_from_file_location('wire_rx',ROOT/'rdma/rnic/hls/owned_wire_rx_profile.py')
p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)

@unittest.skipUnless(p.META.is_file(),'requires retained verified source fixture')
class OwnedWireRxDerivationTests(unittest.TestCase):
    reports={}
    def header(self):return p.wire_header(p.CPP.read_text(),p.HPP.read_text())
    def evidence(self,**kw):
        files=[Path(__file__),Path(p.__file__),Path(p.base.__file__),Path(p.base.base.__file__),
            Path(p.base.base.base.__file__),Path(p.base.base.base.base.__file__),Path(p.lex.__file__),
            p.CPP,p.HPP,p.META,p.TIMER,p.TOP,p.CPP.with_name('ib_utils.cpp'),
            ROOT/'rdma/rnic/rtl/rocev2_retrans_pool.v',ROOT/'rdma/rnic/rtl/rocev2_owned_timer_retrans.v',
            ROOT/'rdma/rnic/rtl/rocev2_owned_wire_rx.v',ROOT/'rdma/rnic/tests/probe_owned_wire_rx.py',
            ROOT/'rdma/rnic/tests/probe_owned_wire_rx_xsim.py',ROOT/'rdma/rnic/tests/owned_wire_rx_tb.v']
        files.extend([ROOT/'rdma/rnic/tests/probe_owned_wire_rx_control_xsim.py',ROOT/'rdma/rnic/tests/owned_wire_rx_control_tb.v'])
        self.reports[self._testMethodName]=dict(source_sha256={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest()for f in files},**kw)
    def test_actual_FNS_parsers_and_complete_AETH_not_synthetic_lookup(self):
        header=self.header();top=p.derive_top(p.TOP.read_text())
        self.assertTrue(header.startswith(p.CPP.read_text().split('#include',1)[0]))
        self.assertIn('bth.parseWord(currWord.data)',header)
        self.assertIn('ackHeader.parseWord(currWord.data)',header)
        self.assertIn('rdmaHeader.parseWord(currWord.data)',header)
        self.assertIn('as02_rx_aeth_meta(ackHeader.isNAK(),ackHeader.getSyndrome())',header)
        self.assertIn('as02_rx_wire_process_ibh<64,58>',top)
        self.assertIn('as02_rx_wire_process_exh<64,58>',top)
        self.assertNotIn('s_rx_query',top)
        self.evidence(actual_BTH_AETH_RETH_source=True,full8bit_syndrome=True,no_external_query_substitute=True)
    def test_whole_frame_retention_original_length_and_exact_last(self):
        for s in ['depth=8192','s_rx_descriptor','s_rx_packet']:
            self.assertIn(s,p.derive_top(p.TOP.read_text()))
        for s in ['(!w.last && keep!=255)','bytes==0','total>65535',
                  'total!=descriptor(103,88)','if(receipt!=descriptor)']:
            self.assertIn(s,p.INGRESS)
        self.assertLess(p.INGRESS.index('total!=descriptor(103,88)'),p.INGRESS.rindex('commands.write(descriptor)'))
        self.evidence(full_uint16_frame_length=True,canonical_keep_and_exact_TLAST_length=True,not_ICRC_or_native_auth=True)
    def test_full_QPN_epoch_PKey_header_echo_and_nonunique_fail_closed(self):
        for s in ['descriptor(23,0)>=MAX_QPS','descriptor(87,24)==0','!descriptor[104]']:
            self.assertIn(s,p.INGRESS)
        for s in ['ibh.normal.dest_qp!=descriptor(23,0)','ibh.normal.partition_key!=descriptor(289,274)',
            'binding(367,304)!=query(119,56)','lease(95,80)!=query(23,0)',
            'lease(183,120)!=query(119,56)','binding(419,412)!=query(127,120)',
            'status!=0 && (lease!=0','exh.syndrome(7,5)!=0']:
            self.assertIn(s,p.FRONT)
        self.evidence(full_identity_not_current_head_guess=True,trusted_admission_is_still_caller_input=True)
    def test_actual_meta_and_body_receipts_no_early_done(self):
        wrapper=(ROOT/'rdma/rnic/rtl/rocev2_owned_wire_rx.v').read_text()
        self.assertEqual(wrapper,p.derive_wrapper((ROOT/'rdma/rnic/rtl/rocev2_owned_timer_retrans.v').read_text()))
        for s in ['if(m_rx_meta_valid && m_rx_meta_ready)','meta_ack<=m_rx_meta_data',
            'm_rx_body_valid && m_rx_body_ready && m_rx_body_data[72]','body_ack<=body_owner']:
            self.assertIn(s,wrapper)
        self.assertNotIn('input wire [1023:0] s_meta_accept',wrapper)
        self.assertNotIn('input wire [1023:0] s_body_accept',wrapper)
        for s in ['receipt!=token','state=(no_body || discard)?DONE:BODY_ACCEPT',
            'lookup_accepts.write(binding)','case DONE:completed.write(descriptor)']:
            self.assertIn(s,p.FRONT)
        self.evidence(buffered_meta_not_actual_acceptance=True,actual_body_TLAST_receipt=True,not_lifetime_grant=True)
    def test_parser_end_is_actual_TLAST_not_empty_poll(self):
        header=self.header();a=header.index('void as02_rx_wire_process_exh(');b=header.index('// Descriptor320:')
        actual=header[a:b]
        self.assertEqual(actual.count('completed.write(1)'),3)
        self.assertIn('parser_ends.read()!=1',p.FRONT)
        self.assertNotIn('raw_body.empty())state=DONE',p.FRONT)
        self.evidence(real_three_original_TLAST_sites=True,no_empty_FIFO_drain_proof=True)
    def test_remote_raw_is_not_local_authorization_or_CQ(self):
        self.assertIn('local=checkIfResponse',p.FRONT)
        self.assertIn('binding(399,392)=255',p.FRONT)
        self.assertIn('token[695]=!local',p.FRONT)
        self.assertIn('if(exh.has_aeth || checkIfRethHeader',p.FRONT)
        for forbidden in ['release_req.write','mreq.write','rdinit.write','timer_controls.write','memcpy','CQE']:
            self.assertNotIn(forbidden,p.FRONT)
        self.evidence(remote_raw_separate_discriminator=True,no_memory_or_CQ_or_WR_release=True,raw_EXH_body_not_DMA_payload=True)
    def test_marker_waits_actual_external_fence_acceptance(self):
        wrapper=(ROOT/'rdma/rnic/rtl/rocev2_owned_wire_rx.v').read_text()
        for s in ['case MARKER_RESUME:','r(167,0)!=descriptor(273,106)','queries.write(query);state=MARKER_RESUME']:
            self.assertIn(s,p.FRONT)
        self.assertIn('rx_resume<={24\'d0,raw_fence[167:0]}',wrapper)
        self.assertIn('if(raw_fence_valid&&raw_fence_ready)',wrapper)
        self.assertIn('!fence_ack_valid&&!rx_resume_valid',wrapper)
        self.evidence(marker_after_actual_body_handoff=True,reopen_after_real_external_fence_handshake_only=True,whole_core_drain=False)
    def test_changed_parser_anchor_rejected_no_geometry_cut(self):
        with self.assertRaises(ValueError):p.wire_header(p.CPP.read_text().replace('metaOut.write(ibhMeta(','REMOVED('),p.HPP.read_text())
        with self.assertRaises(ValueError):p.derive_top(p.TOP.read_text().replace('owned_insert_decode(s_insert,inserts);','REMOVED;'))
        self.assertIn('AS02_TIMER_CLOCK_PS 4000',(p.BASE/'adapter/rocev2_config.hpp').read_text())
        self.assertIn('META_TABLE_SIZE',p.FRONT)
        self.evidence(fail_closed_derivation=True,original4ns_8QP_2000metadata_preserved=True,no_physical_waiver=True)
    def test_registered_checks_preserve_II1_and_all_protection(self):
        for s in ['case HEADER_CHECK:','case HEADER_CLASSIFY:','case QUERY_BUILD:',
                  'case REMOTE_BUILD:','case CHECK_RESULT:','if(binding_invalid!=0)',
                  'binding_invalid[0]=','binding_invalid[1]=','binding_invalid[2]=','binding_invalid[3]=']:
            self.assertIn(s,p.FRONT)
        self.assertIn('ap_uint<4> as02_rx_wire_keep_bytes',p.INGRESS)
        self.assertIn('ap_uint<17> total=count+ap_uint<17>(bytes)',p.INGRESS)
        self.assertIn('d(88,84)=checkIfAethHeader(op)?16:',p.INGRESS)
        self.assertEqual(p.INGRESS.count('#pragma HLS pipeline II=1'),5)
        self.assertIn('as02_rx_wire_decode(s_rx_packet,decoded_packets)',p.derive_top(p.TOP.read_text()))
        actual=p.derive(p.META.read_text())
        self.assertIn('case RX_EPOCH:',actual)
        self.assertIn('case RX_CHAIN:',actual)
        self.assertIn('meta.lease(79,16)<=lookup_generation',actual)
        self.assertIn('meta.lease(247,184)<lookup_sequence',actual)
        self.assertIn('#pragma HLS pipeline II=1',p.FRONT)
        self.assertNotIn('unsigned bytes=0',p.INGRESS)
        self.evidence(keep_decode_canonical_full256_domain=True,registered_header_and_lookup_validation=True,
                      body_beat_II1_not_multi_state_throttled=True,full_frame_length_and_protection_preserved=True)
    def test_actual_count_check_commit_no_early_frame_release(self):
        top=p.derive_top(p.TOP.read_text());wrapper=(ROOT/'rdma/rnic/rtl/rocev2_owned_wire_rx.v').read_text()
        for s in ['as02_rx_wire_ingress(s_rx_descriptor,decoded_packets,frame_begins,annotated_packets,completed,rx_ingress_fault)',
            'as02_rx_wire_frame_check(frame_begins,annotated_packets,checked_begins,checked_packets)',
            'as02_rx_wire_frame_commit(checked_begins,checked_packets,retained,commands,rx_frame_fault)']:
            self.assertIn(s,top)
        for s in ['a(112,96)=total','a[113]=count==0','a[114]=bad;saved=a;have=true',
            'if(a[114] || a(127,115)!=0)','if(w.last)state=EMIT',
            'else {commands.write(descriptor);state=LOAD;}']:
            self.assertIn(s,p.INGRESS)
        self.assertIn('rx_frame_fault!=0',wrapper)
        self.assertIn('if(receipt!=descriptor)',p.INGRESS)
        self.assertIn('if(have && !checked.full()) {checked.write(saved);have=false;}',p.INGRESS)
        self.assertIn('else if(!have && !annotated.empty())',p.INGRESS)
        self.assertIn('receipt=completed.read();state=RECEIPT_CHECK',p.INGRESS)
        self.assertNotIn('commands.write',p.INGRESS[p.INGRESS.index('void as02_rx_wire_ingress('):p.INGRESS.index('void as02_rx_wire_frame_check(')])
        self.evidence(actual_II1_count_check_commit_tasks=True,parser_command_only_after_real_validated_last_store=True,
                      private_bad_beat_quarantines_pool=True,not_native_admission_or_CQ=True)
    def test_full320_query_capture_preserves_every_original_field_guard(self):
        decoder=p.derive_query_decoder();top=p.derive_top(p.TOP.read_text())
        self.assertIn(decoder.strip(),top)
        for text in ['static ap_uint<320> held=0','if(have && !out.full())',
            'if(!have && !in.empty()) {held=in.read();have=true;}',
            'q.qpn=r(23,0);q.psn=r(47,24);q.opcode=r(55,48);q.epoch=r(119,56);',
            'q.syndrome=r(127,120);q.has_aeth=r[128];q.marker=r[129];q.owner=r(297,130);',
            'q.bad=r(319,298)!=0;out.write(q);have=false;']:
            self.assertIn(text,decoder)
        self.evidence(actual_elastic_full320_capture=True,full24_QPN_64epoch_168owner_and_reserved22_preserved=True,
                      query_field_validation_not_removed=True,not_native_lifetime_or_completion=True)
    def test_long_bad_frame_quarantine_stall_oracles_are_not_DUT_force(self):
        bench=(ROOT/'rdma/rnic/tests/owned_wire_rx_control_tb.v').read_text()
        for text in ['malformed_until_upstream_stall(which==12)','packet_data[71:64]=8\'hfd',
            'waited<32','blocked_beats>=32','dut.rx_frame_fault!==32\'d40',
            'packet_ready!==1\'b0 || meta_valid || body_valid || fence_valid || event_valid || rdinit_valid',
            'source packet changed under actual backpressure','WIRE_RX_QUARANTINE']:
            self.assertIn(text,bench)
        self.assertNotIn('force ',bench)
        self.evidence(two_long_bad_frame_actual_input_backpressure_cases=True,held_source_beat_not_withdrawn=True,
                      actual_frame_fault_and_no_owner_or_parser_effect_required=True,no_DUT_force=True)
    @classmethod
    def tearDownClass(cls):
        if name:=os.environ.get('AS02_RNIC_WIRE_RX_DERIVATION_REPORT'):
            path=Path(name);path=path if path.is_absolute()else ROOT/path
            run=Path(tempfile.mkdtemp(prefix='owned-wire-rx-unit-',dir=ROOT/'rdma/rnic/build'));inp=run/'inputs';inp.mkdir()
            identities={n:h for v in cls.reports.values()for n,h in v['source_sha256'].items()}
            for n,h in identities.items():
                f=ROOT/n;assert hashlib.sha256(f.read_bytes()).hexdigest()==h,n
                target=inp/n;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,target)
            frozen={str(f.relative_to(inp)):hashlib.sha256(f.read_bytes()).hexdigest()for f in inp.rglob('*')if f.is_file()}
            with path.open('x')as out:out.write(json.dumps(dict(scope=__doc__,pass_test=len(cls.reports)==12,methods=len(cls.reports),tests=cls.reports,
                retained_directory=str(run.relative_to(ROOT)),frozen_source_sha256=frozen,RTL_tested=False,native_CQ=False,hardware_verified=False),indent=2)+'\n')
if __name__=='__main__':unittest.main()
