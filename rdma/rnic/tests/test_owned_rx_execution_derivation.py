#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Exact actual RX FSM derivation/ownership source invariants, NOT RTL proof."""
import argparse
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import shutil
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[3]
spec=importlib.util.spec_from_file_location('owned_rx_execution',ROOT/'rdma/rnic/hls/owned_rx_execution_profile.py')
p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)

class OwnedRxExecutionDerivation(unittest.TestCase):
    def setUp(self):self.original=p.CPP.read_text()
    def test_exact_actual_functions_and_original_license(self):
        h=p.derive(self.original)
        self.assertTrue(h.startswith(self.original.split('#include',1)[0]))
        for fn in ['rx_ibh_fsm','rx_exh_fsm']:
            original=p.source.function(self.original,fn)
            derived=p.derive_ibh(self.original)if fn=='rx_ibh_fsm'else p.derive_exh(self.original)
            self.assertIn('as02_owned_'+fn,derived)
            self.assertEqual(re.findall(r'case\s+RC_\w+\s*:',original),re.findall(r'case\s+RC_\w+\s*:',derived))
            self.assertIn('#pragma HLS pipeline II=1',derived)
        self.assertNotIn('void rx_ibh_fsm(',h)
        self.assertNotIn('void rx_exh_fsm(',h)
    def test_all_effect_streams_carry_same_full_owner(self):
        ibh=p.derive_ibh(self.original);exh=p.derive_exh(self.original)
        for t in ['rxStateReq','rxStateRsp','ackEvent','bool','fwdPolicy','ackMeta','rxTimerUpdate','retransUpdate','psnPkg']:
            self.assertIn('stream<as02RxOwned<'+t+'>>&',ibh)
        for t in ['dmaState','retransmission','retransRdInit','readRequest','rxMsnReq','ackEvent','pkgSplit','pkgShift']:
            self.assertIn('stream<as02RxOwned<'+t+'>>&',exh)
        self.assertIn('a.packet==b.packet && a.native==b.native',p.TYPES)
        self.assertIn('ap_uint<1024> packet=0;ap_uint<588> native=0;',p.TYPES)
        for name in ['stateTable_upd_req','rx2retrans_upd','rxClearTimer_req']:
            self.assertRegex(ibh+exh,name+r'\.write\(as02_rx_tag\(')
        self.assertRegex(exh,r'rxExh2msnTable_upd_req\.write\(as02_rx_msn_effect\(')
    def test_admission_and_exact_response_validation_before_effects(self):
        i=p.derive_ibh(self.original);e=p.derive_exh(self.original)
        self.assertLess(i.index('!as02_rx_execution_valid(owner)'),i.index('stateTable_upd_req.write'))
        self.assertLess(i.index('!as02_rx_same_owner(owner,rsp.owner)'),i.index('qpState=rsp.normal'))
        self.assertLess(e.index('!as02_rx_execution_valid(owner)'),e.index('rxExh2msnTable_upd_req.write'))
        self.assertIn('!as02_rx_same_owner(owner,dm.owner)',e)
        self.assertIn('!as02_rx_same_owner(owner,ri.owner)',e)
        self.assertIn('ri.normal.laddr!=as02_rx_va(owner)',e)
        self.assertIn('dmaMeta.vaddr!=as02_rx_address(owner)',e)
        for f in [i,e]:self.assertIn('fault=error;if(error)return;',f)
    def test_same_packet_headers_and_udp_length_not_independent_queues(self):
        e=p.derive_exh(self.original)
        for forbidden in ['headerInput.read(','udpLengthFifo.read(','stream<ExHeader<WIDTH> >& headerInput','stream<ap_uint<16> >& udpLengthFifo']:
            self.assertNotIn(forbidden,e)
        for required in ['exHeader.setRawHeader(owner.packet(671,544))','udpLength=ap_uint<17>(owner.packet(799,784))+12']:
            self.assertIn(required,e)
        self.assertIn('ap_uint<17>(d(103,88))+12>65535',p.TYPES)
    def test_full64_address_retained_before_lossy_legacy_memCmd_constructor(self):
        old=p.source.function(self.original,'rx_exh_fsm');new=p.derive_exh(self.original)
        self.assertEqual(old.count('memoryWriteCmd.write('),10)
        self.assertEqual(new.count('memoryWriteCmd.write(effect)'),10)
        self.assertNotIn('memoryWriteCmd.write(memCmd(',new)
        self.assertNotIn('stream<memCmd>&',new)
        self.assertIn('ap_uint<64> address=0;ap_uint<32> length=0;ap_uint<24> qpn=0;',p.TYPES)
        self.assertIn('e.address==as02_rx_address(o)',p.TYPES)
        self.assertIn('if(!as02_rx_memory_valid(effect)) {error=67;return;}',new)
    def test_full_syndrome_controls_do_not_clear_timer_or_publish_positive_effects(self):
        i=p.derive_ibh(self.original)
        self.assertIn('as02_rx_syndrome(o)(7,5)!=0',p.TYPES)
        self.assertLess(i.index('if(as02_rx_control(owner))'),i.index('stateTable_upd_req.write'))
        self.assertIn('controls.write(as02_rx_tag(as02_rx_syndrome(owner),owner));return;',i)
        self.assertIn('isResponse && !emeta.isNak && meta.op_code != RC_RDMA_READ_RESP_MIDDLE',i)
        self.assertIn('as02_rx_control(owner)) {error=63;return;}',p.derive_exh(self.original))
    def test_no_head_guess_geometry_or_length_cap_reduction(self):
        for required in ['ap_uint<248> lease','lease(183,120)!=epoch','lease(247,184)!=sequence',
            'qpn>=MAX_QPS','lease(15,0)>=META_TABLE_SIZE','ap_uint<33>(length)+PMTU-1','span>=8388608']:
            self.assertIn(required,p.TYPES)
        for forbidden in ['length<=4096','length>4096','b[421]!=1','key==0','epoch(31,0)','sequence(31,0)']:
            self.assertNotIn(forbidden,p.TYPES)
        self.assertIn('native_op==1 && d(103,88)==16',p.TYPES)
        self.assertIn('if(native_op!=2 || length==0)return false;',p.TYPES)
        self.assertIn('ap_uint<25> psn_distance',p.TYPES)
        self.assertIn('ap_uint<3>(4)-ap_uint<3>(bytes(1,0))',p.TYPES)
    def test_anchor_and_unknown_effect_changes_fail_closed(self):
        for before in ['stateTable_rsp.read(qpState);','exhMetaFifo.read(emeta);']:
            with self.assertRaises(ValueError):p.derive_ibh(self.original.replace(before,'CHANGED;'))
        for before in ['headerInput.read(exHeader);','msnTable2rxExh_rsp.read(dmaMeta);']:
            with self.assertRaises(ValueError):p.derive_exh(self.original.replace(before,'CHANGED;'))
        with self.assertRaises(ValueError):p.tag_writes('memoryWriteCmd.write(unknown());',['memoryWriteCmd'])
    def test_no_native_CQ_drain_release_or_hardware_substitute(self):
        h=p.derive(self.original)
        for forbidden in ['ib_register_device(','memcpy(','local_core_drained=1','release_req.write(','cq_commit.write(']:
            self.assertNotIn(forbidden,h)
        self.assertIn('caller must already hold all real refs',h)
        self.assertIn('No output below is CQ publication',h)
    def test_probe_failure_cannot_leave_eligible_pass_or_relative_report_failure(self):
        driver=(ROOT/'rdma/rnic/tests/probe_owned_rx_execution.py').read_text()
        self.assertIn('args.report=args.report.resolve()',driver)
        self.assertIn('result.update(pass_test=False,terminal_exit_status=1',driver)
        self.assertIn("'-fsanitize=undefined','-fno-sanitize-recover=all'",driver)
        self.assertNotIn('-DNDEBUG',driver)
    def test_raw_transport_padding_not_native_DMA_length(self):
        self.assertIn('ap_uint<32> payload_length=0;ap_uint<2> pad_bytes=0;',p.TYPES)
        self.assertIn('e.payload_length==bytes && e.pad_bytes==pad',p.TYPES)
        self.assertIn('NOT native DMA authority',p.TYPES)
    def test_native_MSN_progress_uses_payload_and_closes_LAST(self):
        self.assertIn('normal.vaddr=as02_rx_address(owner)+bytes;normal.dma_length=bytes;',p.TYPES)
        self.assertIn('Close the real MSN packet transaction for LAST as well.',p.derive_exh(self.original))

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--report',type=Path,required=True);a=ap.parse_args()
    if a.report.exists():ap.error('preserve earlier evidence')
    if not a.report.resolve().is_relative_to(ROOT/'results'):ap.error('report must be in repository results/')
    files=[Path(__file__).resolve(),Path(p.__file__).resolve(),Path(p.source.__file__).resolve(),p.CPP,p.HPP,
        ROOT/'rdma/rnic/hls/test_owned_rx_execution.cpp',ROOT/'rdma/rnic/tests/probe_owned_rx_execution.py']
    hashes={str(q.relative_to(ROOT)):hashlib.sha256(q.read_bytes()).hexdigest()for q in files}
    run=Path(tempfile.mkdtemp(prefix='owned-rx-execution-unit-',dir=ROOT/'rdma/rnic/build'));inputs=run/'inputs'
    for q in files:
        target=inputs/q.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(q,target)
    output=io.StringIO();suite=unittest.defaultTestLoader.loadTestsFromTestCase(OwnedRxExecutionDerivation)
    result=unittest.TextTestRunner(stream=output,verbosity=2).run(suite)
    assert all(hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h for n,h in hashes.items())
    log=run/'unittest.log';log.write_text(output.getvalue())
    record=dict(scope=__doc__,pass_test=result.wasSuccessful(),methods=result.testsRun,terminal_exit_status=0 if result.wasSuccessful()else 1,
        retained_directory=str(run.relative_to(ROOT)),source_sha256=hashes,
        frozen_source_sha256={str(q.relative_to(inputs)):hashlib.sha256(q.read_bytes()).hexdigest()for q in inputs.rglob('*')if q.is_file()},
        artifact_sha256={str(log.relative_to(ROOT)):hashlib.sha256(log.read_bytes()).hexdigest()},RTL_tested=False,hardware_verified=False,native_DMA_CQ=False)
    with a.report.open('x')as out:out.write(json.dumps(record,indent=2)+'\n')
    print(output.getvalue());print(json.dumps(dict(record=str(a.report),pass_test=record['pass_test'],methods=record['methods'])))
    if not result.wasSuccessful():raise SystemExit(1)

if __name__=='__main__':main()
