#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual owned state/MSN derivation invariants, not HLS/RTL/native proof."""
import argparse
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[3]
spec=importlib.util.spec_from_file_location('services',ROOT/'rdma/rnic/hls/owned_rx_services_profile.py')
p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)
class ServicesDerivation(unittest.TestCase):
    def setUp(self):self.state=p.STATE.read_text();self.msn=p.MSN.read_text()
    def test_original_licensed_real_tables_no_parallel_shadow(self):
        h=p.derive(self.state,self.msn)
        self.assertTrue(h.startswith(self.state.split('#include',1)[0]))
        self.assertEqual(h.count('static stateTableEntry state_table[MAX_QPS]'),1)
        self.assertEqual(h.count('static as02MsnOwnedEntry msn_table[MAX_QPS]'),1)
        self.assertIn('dmaState normal;as02RxExecutionOwner owner;',h)
        for forbidden in ['shadow_table','owner_ram[','state_table<','msn_table<']:
            self.assertNotIn(forbidden,h)
    def test_existing_real_state_actions_and_rendezvous_preserved(self):
        h=p.derive_state(self.state)
        for expected in ['if(seen==7)','committed_seen','pending_source','as02_state_marker(msg,0',
            'as02_state_marker(msg,1','as02_state_marker(msg,2','readbacks.write(sampled)',
            'state_table[rxRequest.qpn].req_old_unack = rxRequest.epsn;',
            'state_table[txRequest.qpn].req_next_psn = txRequest.psn;']:
            self.assertIn(expected,h)
        self.assertIn('ap_uint<24>(ap_uint<25>(entry.req_next_psn)+0xffffffU)',h)
        self.assertNotIn('entry.req_next_psn-1',h)
    def test_RX_state_full_owned_response_not_late_QP_owner(self):
        h=p.derive_state(self.state)
        self.assertIn('hls::stream<as02RxStateMessage>& rxIbh2stateTable_upd_req',h)
        self.assertIn('hls::stream<as02RxOwned<rxStateRsp>>& stateTable2rxIbh_rsp',h)
        self.assertEqual(h.count(',pending_owner));'),2)
        self.assertIn('!as02_rx_execution_valid(pending_owner)',h)
        self.assertIn('msg.sequence!=pending_owner.native(523,460)',h)
        self.assertIn('pending_owner.packet!=0 || pending_owner.native!=0',h)
    def test_connection_epoch_and_initialization_fail_closed(self):
        h=p.derive_state(self.state);m=p.derive_msn(self.msn)
        for text in [h,m]:
            self.assertIn('connection_epoch[MAX_QPS]',text)
            self.assertIn('initialized',text)
            self.assertIn('fault=error;if(error)return;',text)
        self.assertIn('msg.write && initialized[msg.qpn]',h)
        self.assertIn('initialized[request.qpn]) {error=86',m)
        self.assertIn('connection_epoch[qp]!=owner.native(459,396)',m)
    def test_actual_MSN_entry_remembers_native_lease_and_order(self):
        h=p.derive_msn(self.msn)
        for expected in ['entry.owner.native!=owner.native','entry.owner.packet(247,0)!=owner.packet(247,0)',
            'entry.next_psn!=owner.packet(295,272)','entry.normal.vaddr!=as02_rx_address(owner)',
            '!as02_rx_same_owner(entry.owner,owner)','entry.pending=true','entry.pending=false',
            'if(last)entry.read_active=false','owner.native(523,460)<=entry.owner.native(523,460)']:
            self.assertIn(expected,h)
        self.assertIn('NOT WR/MR/CQ retirement',h)
    def test_native_payload_not_raw_padding_progress(self):
        h=p.derive_msn(self.msn);e=p.rx.derive_exh(p.rx.CPP.read_text())
        self.assertIn('rxRequest.dma_length!=bytes',h)
        self.assertIn('rxRequest.vaddr!=ap_uint<64>(as02_rx_address(owner)+bytes)',h)
        self.assertIn('normal.vaddr=as02_rx_address(owner)+bytes;normal.dma_length=bytes;',p.rx.TYPES)
        self.assertIn('Close the real MSN packet transaction for LAST as well.',e)
    def test_TX_MSN_full_QPN_epoch_sequence_and_exact_zero_key(self):
        h=p.derive_msn(self.msn)
        self.assertIn('request.qpn>=MAX_QPS',h)
        self.assertIn('request.epoch==0 || request.sequence==0',h)
        self.assertIn('as02MsnTxRsp(txMsnRsp(',h)
        self.assertIn('ifRequest.r_key=request.rkey',h)
        self.assertNotIn('rkey==0',h)
    def test_actual_composition_has_no_modeled_RX_state_MSN_response(self):
        t=(ROOT/'rdma/rnic/hls/test_owned_rx_services.cpp').read_text()
        for s in ['as02_owned_rx_state_encode<ID>','as02_owned_rx_state_table<ID>',
            'as02_owned_rx_msn_table<ID>','h.ti();h.te();']:
            self.assertIn(s,t)
        for s in ['h.sr.write(','h.mr.write(','h.state(','h.msn(']:self.assertNotIn(s,t)
        self.assertIn('explicit read-init fixture, NOT pool proof',t)
        self.assertIn('rb.status==0 && rb.seen==7 && !g.h.update.empty()',t)
    def test_unknown_actual_anchors_rejected(self):
        with self.assertRaises(ValueError):p.derive_state(self.state.replace('state_table[txRequest.qpn].req_next_psn = txRequest.psn;','REMOVED;'))
        with self.assertRaises(ValueError):p.derive_msn(self.msn.replace('rxExh2msnTable_upd_req.read(rxRequest);','REMOVED;'))
        with self.assertRaises(ValueError):p.derive_msn(self.msn.replace('msn_table[ifRequest.qpn].lst = 0;','REMOVED;'))
    def test_no_core_drain_CQ_or_capacity_shortcut(self):
        h=p.derive(self.state,self.msn)
        for s in ['local_core_drained=1','cq_commit.write(','release_req.write(','memcpy(','MAX_QPS=1']:
            self.assertNotIn(s,h)
        self.assertIn('MAX_QPS',h)
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--report',type=Path,required=True);a=ap.parse_args();a.report=a.report.resolve()
    if a.report.exists():ap.error('preserve earlier evidence')
    if not a.report.is_relative_to(ROOT/'results'):ap.error('report must be under repository results/')
    files=[Path(__file__).resolve(),Path(p.__file__),Path(p.rx.__file__),Path(p.state.__file__),p.STATE,p.MSN,p.rx.CPP,
        ROOT/'rdma/rnic/hls/test_owned_rx_services.cpp',ROOT/'rdma/rnic/hls/test_owned_rx_execution.cpp',ROOT/'rdma/rnic/tests/probe_owned_rx_services.py']
    hashes={str(q.relative_to(ROOT)):hashlib.sha256(q.read_bytes()).hexdigest()for q in files}
    run=Path(tempfile.mkdtemp(prefix='owned-rx-services-unit-',dir=ROOT/'rdma/rnic/build'));inputs=run/'inputs'
    for q in files:
        target=inputs/q.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(q,target)
    out=io.StringIO();result=unittest.TextTestRunner(stream=out,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ServicesDerivation))
    assert all(hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h for n,h in hashes.items())
    log=run/'unittest.log';log.write_text(out.getvalue())
    record=dict(scope=__doc__,pass_test=result.wasSuccessful(),terminal_exit_status=0 if result.wasSuccessful()else 1,methods=result.testsRun,
        retained_directory=str(run.relative_to(ROOT)),source_sha256=hashes,
        frozen_source_sha256={str(q.relative_to(inputs)):hashlib.sha256(q.read_bytes()).hexdigest()for q in inputs.rglob('*')if q.is_file()},
        artifact_sha256={str(log.relative_to(ROOT)):hashlib.sha256(log.read_bytes()).hexdigest()},RTL_tested=False,hardware_verified=False,native_DMA_CQ=False)
    with a.report.open('x')as f:f.write(json.dumps(record,indent=2)+'\n')
    print(out.getvalue());print(json.dumps(dict(record=str(a.report.relative_to(ROOT)),pass_test=record['pass_test'],methods=record['methods'])))
    if not result.wasSuccessful():raise SystemExit(1)
if __name__=='__main__':main()
