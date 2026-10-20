# SPDX-License-Identifier: BSD-2-Clause-Views
"""Owned real timer/process derivation invariants, not runtime/physical proof."""
import hashlib
import importlib.util
import json
import os
import re
import shutil
import tempfile
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[3]
spec=importlib.util.spec_from_file_location('owned_timer',ROOT/'rdma/rnic/hls/owned_timer_profile.py')
p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)

@unittest.skipUnless(p.META.is_file()and p.TIMER.is_file(),'requires retained verified wrkey HLS fixture')
class OwnedTimerDerivationTests(unittest.TestCase):
    reports={}
    def evidence(self,**kw):
        files=[Path(__file__),Path(p.__file__),Path(p.base.__file__),Path(p.base.base.__file__),p.META,p.TIMER,p.TOP,
            ROOT/'rdma/rnic/rtl/rocev2_owned_timer_retrans.v',ROOT/'rdma/rnic/hls/test_owned_timer.cpp']
        self.reports[self._testMethodName]=dict(source_sha256={str(q.relative_to(ROOT)):hashlib.sha256(q.read_bytes()).hexdigest()for q in files},**kw)
    def test_actual_original_clock_backoff_scan_8entries_and_complete_license(self):
        old=p.META.read_text();new=p.derive(old);timer=p.derive_timer(p.TIMER.read_text())
        self.assertTrue(new.startswith(old));self.assertIn('Copyright (c) 2019, Systems Group, ETH Zurich.',timer)
        self.assertIn('AS02_TIMER_CLOCK_PS 4000',(p.BASE/'adapter/rocev2_config.hpp').read_text())
        for operation in ['entry.time--;','entry.retries++;','entry.active = false;',
            'entry.time = TIME_1ms;','entry.time = TIME_5ms;','entry.time = TIME_12ms;','entry.time = TIME_64ms;']:
            self.assertIn(operation,timer[timer.index('// Original countdown'):])
        self.assertIn('transportTimerTable[MAX_QPS]',timer)
        self.assertIn('array_partition variable=transportTimerTable complete dim=1',timer)
        self.assertIn('1ULL * AS02_TIMER_CLOCK_PS * MAX_QPS',timer)
        def scan_body(text,start=0):
            at=text.index('// perform round robin to check whether it has timed out',start)
            left=text.rfind('{',0,at);depth=1;end=left+1
            while depth:
                if text[end]=='{':depth+=1
                elif text[end]=='}':depth-=1
                end+=1
            return text[left+1:end-1]
        actual=scan_body(timer,timer.index('// Original countdown'))
        restored=re.sub(r'as02OwnedRetry r;.*?timer2retrans_req.write\(r\);',
            'timer2retrans_req.write(retransmission(checkQP));',actual,flags=re.S)
        self.assertEqual(''.join(restored.split()),''.join(scan_body(p.TIMER.read_text()).split()))
        self.evidence(original_4ns_1ms_8QP_calibration=True,real_idle_scan_actions_exact_except_saved_identity_output=True,real_counter_and_backoff_not_shortened=True,licensed_source_preserved=True)
    def test_actual_insert_ACK_head_and_replay_controls_not_external_timer_port(self):
        old=p.META.read_text();new=p.derive(old)[len(old):];top=p.derive_top(p.TOP.read_text())
        self.assertEqual(new.count('timer_starts.write(as02OwnedTimerTx(new_lease,false))'),2)
        self.assertIn('timer_starts.write(as02OwnedTimerTx(meta.lease,true))',new)
        self.assertIn('state=HEAD_WAIT',new);self.assertIn('next_head_lease=meta.lease',new)
        self.assertIn('meta.lease(79,16)<=return_lease(79,16)',new)
        self.assertIn('timer_controls.write(as02OwnedTimerCtrl(return_lease,next_head_lease,ptr.valid,true))',new)
        self.assertNotIn('port=s_timer',top);self.assertNotIn('s_timer,',top)
        w=(ROOT/'rdma/rnic/rtl/rocev2_owned_timer_retrans.v').read_text()
        self.assertNotIn('s_timer_data',w);self.assertIn('as02_owned_timer_retrans_top process_and_tables(',w)
        self.evidence(real_metadata_insert_ACK_head_replay_feedback=True,no_externally_injected_timer_request=True,whole_wire_producer_binding=False)
    def test_late_controls_and_TX_cannot_retag_or_clear_new_head(self):
        timer=p.derive_timer(p.TIMER.read_text())
        for guard in ['entry.head_lease!=ctrl.old_lease','seq<=entry.retired_sequence','epoch<entry.epoch',
            'if(!entry.bound) {entry.head_lease=tx.lease;entry.bound=true;}',
            'ctrl.next_lease(79,16)<=ctrl.old_lease(79,16)','r.epoch=entry.head_lease(183,120)',
            'r.sequence=entry.head_lease(247,184)']:
            self.assertIn(guard,timer)
        self.assertIn('if(ctrl.advance && (!ctrl.next_valid || nextseq!=seq) && seq>entry.retired_sequence)',timer)
        for stage in ['CTRL_CHECK','CTRL_EPOCH','CTRL_TIME','CTRL_RETIRE','CTRL_LATEST','CTRL_COMMIT',
            'TX_CHECK','TX_EPOCH','TX_BIND','TX_LATEST','TX_TIME','TX_COMMIT']:
            self.assertIn('case '+stage+':',timer)
        new=p.derive(p.META.read_text());self.assertIn('(!replay_started && !as02_wr_matches',new)
        self.assertIn('meta.lease(247,184)<replay_sequence',new)
        self.assertIn('timer_request && !replay_started && meta.valid',new)
        self.evidence(full_immutable_lease_on_head_and_full_WR_timeout=True,retired_WR_tombstone=True,older_timer_not_retagged_to_new_WR=True,multiWR_replay_keeps_each_record_lease=True,actual_compare_compute_commit_states=True)
    def test_real_two_phase_marker_cycle_break_resume_and_source_anchors(self):
        timer=p.derive_timer(p.TIMER.read_text());new=p.derive(p.META.read_text())
        for anchor in ['state=HALT_EMIT','case HALT_WAIT_TX:','case WAIT_RESUME:','timer2retrans_req.write(r)',
            'if(resume_token(167,0)!=token || resume_token(191,168)!=0)']:
            self.assertIn(anchor,timer)
        self.assertIn('resume_token=resumes.read();state=RESUME_CHECK',timer)
        self.assertIn('case RESUME_CHECK:',timer)
        self.assertIn('(seen & 11)==11',new);self.assertIn('if(replies_seen==63)',new)
        self.assertIn('r[302]=replies_seen[5]',new)
        self.assertIn('timer_resumes.write(r);seen=0',new)
        with self.assertRaises((ValueError,IndexError)):p.derive_timer(p.TIMER.read_text().replace('timer2retrans_req.write(retransmission(checkQP));','REMOVED'))
        self.evidence(actual_timer_scan_close_then_output_marker_then_TX_marker=True,actual_external_response_resume_only=True,joined_real_timer_certificate=True,whole_shared_core_MAC_DMA_CQ=False)
    @classmethod
    def tearDownClass(cls):
        if name:=os.environ.get('AS02_RNIC_OWNED_TIMER_DERIVATION_REPORT'):
            path=Path(name);path=path if path.is_absolute()else ROOT/path
            run=Path(tempfile.mkdtemp(prefix='owned-timer-unit-',dir=ROOT/'rdma/rnic/build'));inp=run/'inputs';inp.mkdir()
            identities={n:h for t in cls.reports.values()for n,h in t['source_sha256'].items()}
            for n,h in identities.items():
                source=ROOT/n;assert hashlib.sha256(source.read_bytes()).hexdigest()==h,n
                target=inp/source.name;assert not target.exists();shutil.copy2(source,target)
            frozen={q.name:hashlib.sha256(q.read_bytes()).hexdigest()for q in inp.iterdir()}
            with path.open('x')as out:out.write(json.dumps(dict(scope=__doc__,pass_test=len(cls.reports)==4,methods=len(cls.reports),tests=cls.reports,
                retained_directory=str(run.relative_to(ROOT)),frozen_source_sha256=frozen,hardware_verified=False),indent=2)+'\n')
if __name__=='__main__':unittest.main()
