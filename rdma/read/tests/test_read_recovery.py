# SPDX-License-Identifier: BSD-2-Clause-Views
"""Finite native-tool error/recovery models; no PCI writes, QPs or traffic."""
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT / 'rdma/read/host'))
import fpga_rw_client as client
import native_rw_test as native
import test_rw_client as model
import test_native_rw_test as supervisor_model

old=client.common


class Registers(model.Registers):
    def __init__(self,fault=None):
        super().__init__();self.fault=fault;self.probed=False;self.saved_diag={}

    def write32(self,address,value):
        if address==old.COMMAND and value==1 and self.values.get(0x78)==self.cfg.size*self.cfg.count-1:
            self.saved_diag={a:self.values.get(a,0) for a in range(0x90,0xD0,4)}
            super().write32(address,value);self.probed=True
            if self.fault=='timeout':self.mode='timeout';return
            if self.fault=='accepts':return
            self.values.update({old.STATUS:model.ERROR,old.ERROR:1,old.ISSUED:0,old.ACKED:0,
                old.TOTAL:self.cfg.size*self.cfg.count,old.ELAPSED:1,old.READ_COMMANDS:0,old.READ_BYTES:0,
                client.COMMITTED:0,client.CAPTURE_BYTES:0,client.AUTHORIZED:0,client.PADDING:0,
                client.CHUNKS:0,client.CAPTURE_ERROR:0,client.CAPTURE_STATE:6,client.LEASE:self.cfg.allocation})
            self.values.update({a:0 for a in self.saved_diag})
            changes={'wrong_error':(old.ERROR,2),'issued':(old.ISSUED,1),
                'captured':(client.CAPTURE_BYTES,1),'authorized':(client.AUTHORIZED,1),
                'capture_fault':(client.CAPTURE_ERROR,2),'core_released':(old.STATUS,model.ERROR&~old.CORE_RESET),
                'wrong_epoch':(client.RUN_ID,self.values[client.RUN_ID]+1),'guard':(0xCC,1)}
            if self.fault in changes:
                key,other=changes[self.fault];self.values[key]=other
            if self.fault=='interrupted_start':raise KeyboardInterrupt('posted probe START flush interrupted')
            return
        super().write32(address,value)
        if address==client.MODE and old.state(self.values[old.STATUS])==0:
            self.values[old.STATUS]=model.IDLE|(0x80 if value else 0)
        if address==old.COMMAND and value==2 and self.probed:
            self.values.update(self.saved_diag)
            if self.fault=='tx_leak':self.values[0xC0]+=1
            if self.fault=='cpl_leak':self.values[0xC4]+=1
            if self.fault=='clear_epoch':self.values[client.RUN_ID]+=1
            if self.fault=='clear_mode':self.values[client.MODE]=0


def recovery_fixture():
    registers=Registers();peer=model.PeerSocket(registers)
    result=client.run_read(registers,model.CFG,peer,probe_config_error=True)
    report,_,events=supervisor_model.fixture()
    result.update(operation='read',application_version=0x20000,hardware_access=True,bdf=native.ROLES['fpga']['bdf'])
    return registers,peer,report,result,events


def verify(report,result,events):
    return native.verify_results(report,result,events,'read',65,3,0xFFFFFE,0x987654,1,True)


class ReadRecoveryTests(unittest.TestCase):
    reports={}

    @classmethod
    def tearDownClass(cls):
        if target:=os.environ.get('AS02_READ_RECOVERY_REPORT'):
            paths=[Path(__file__),Path(client.__file__),Path(native.__file__),Path(model.__file__),
                Path(supervisor_model.__file__)]
            record=dict(scope='Native READ error/CLEAR/recovery models, not FPGA verification',hardware_verified=False,
                complete=len(cls.reports)==6,tests=cls.reports,
                source_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths})
            with Path(target).open('x') as out:out.write(json.dumps(record,indent=2)+'\n')

    def test_error_clear_then_native_read_keeps_source_lease_and_all_byte_checks(self):
        registers,peer,report,result,events=recovery_fixture()
        self.assertTrue(result['success'] and result['config_error_recovery_verified'])
        self.assertEqual([v for a,v in registers.writes if a==old.COMMAND],[1,2,1])
        self.assertEqual(peer.sent[1:],[b'R',b'D'])
        self.assertEqual(result['run_id'],11);self.assertEqual(result['payload_bytes_compared'],195)
        self.assertEqual(result['bar_bytes_compared'],448)
        proof=result['configuration_error_probe']
        self.assertEqual(proof['advertised_remote_bytes'],194)
        self.assertEqual(proof['error_terminal']['error_code'],1)
        self.assertEqual(proof['error_terminal']['issued'],0)
        self.assertEqual(proof['cleared_idle']['diagnostics']['0xc0'],11)
        worker=verify(report,result,events);worker.update(success=True,owned_children_stopped_without_force=True)
        final=native.final_result(0,worker)
        self.assertTrue(final['config_error_recovery_verified'] and final['hardware_rdma_verified'])
        self.reports[self._testMethodName]=dict(pass_test=True,model_only=True,payload_bytes_compared=195,
            bar_bytes_compared=448,commands=[1,2,1],source_lease_released_only_after_valid_read=True)

    def test_bad_rejection_or_clear_cannot_start_the_recovery(self):
        faults=['wrong_error','issued','captured','authorized','capture_fault','core_released','wrong_epoch',
            'guard','tx_leak','cpl_leak','clear_epoch','clear_mode','accepts']
        for fault in faults:
            registers=Registers(fault);peer=model.PeerSocket(registers)
            with self.subTest(fault=fault),self.assertRaises(client.ClientError) as caught:
                client.run_read(registers,model.CFG,peer,probe_config_error=True)
            self.assertFalse(caught.exception.evidence['success'])
            self.assertNotIn(b'D',peer.sent)
            self.assertEqual(sum(a==old.COMMAND and v==1 for a,v in registers.writes),1)
        self.reports[self._testMethodName]=dict(pass_test=True,rejected_faults=len(faults))

    def test_probe_timeout_and_interrupted_start_keep_owned_abort_path(self):
        for fault in ('timeout','interrupted_start'):
            registers=Registers(fault);peer=model.PeerSocket(registers)
            with self.subTest(fault=fault),self.assertRaises(client.ClientError) as caught:
                client.run_read(registers,model.CFG,peer,probe_config_error=True)
            self.assertTrue(caught.exception.evidence['tx_quiescence_verified'])
            self.assertEqual(peer.sent[-1],b'A');self.assertNotIn(b'D',peer.sent)
            if fault=='timeout':self.assertIn((old.COMMAND,4),registers.writes)
        self.reports[self._testMethodName]=dict(pass_test=True,aborts=2)

    def test_two_fresh_generations_required_before_any_start(self):
        for initial in (0xFFFFFFFE,0xFFFFFFFF):
            registers=Registers();registers.values[client.RUN_ID]=initial;peer=model.PeerSocket(registers)
            with self.subTest(generation=initial),self.assertRaises(client.ClientError):
                client.run_read(registers,model.CFG,peer,probe_config_error=True)
            self.assertNotIn((old.COMMAND,1),registers.writes);self.assertNotIn(b'R',peer.sent)
        self.reports[self._testMethodName]=dict(pass_test=True,no_wrap=True,rejected=2)

    def test_supervisor_requires_requested_scope_and_detailed_zero_activity_proof(self):
        _,_,report,result,events=recovery_fixture();rejected=0
        mutations=[('config_error_probe_requested',False),('config_error_recovery_verified',False)]
        for key,value in mutations:
            altered=copy.deepcopy(result);altered[key]=value
            with self.subTest(key=key),self.assertRaises(RuntimeError):verify(report,altered,events)
            rejected+=1
        proof_changes=dict(success=False,advertised_remote_bytes=195,application_commands=[1,4,2],
            global_reset_requested=True,clear_without_global_reset=False,peer_mr_lease_retained=False,
            no_read_sq_issued=False,no_roce_tx_or_completion=False)
        for key,value in proof_changes.items():
            altered=copy.deepcopy(result);altered['configuration_error_probe'][key]=value
            with self.subTest(key=key),self.assertRaises(RuntimeError):verify(report,altered,events)
            rejected+=1
        for key,value in ((old.ISSUED,1),(old.ERROR,2),(0xC0,12),(client.RUN_ID,99)):
            altered=copy.deepcopy(result);proof=altered['configuration_error_probe']
            if key==old.ISSUED:proof['error_terminal']['issued']=value
            if key==old.ERROR:proof['error_terminal']['error_code']=value
            if key==0xC0:proof['cleared_idle']['diagnostics']['0xc0']=value
            if key==client.RUN_ID:proof['cleared_idle']['run_id']=value
            with self.subTest(key=key),self.assertRaises(RuntimeError):verify(report,altered,events)
            rejected+=1
        with self.assertRaises(RuntimeError):native.verify_results(report,result,events,'read',65,3,0xFFFFFE,0x987654,1)
        self.reports[self._testMethodName]=dict(pass_test=True,rejections=rejected+1)

    def test_recovery_flag_is_scoped_to_read_and_thermal_success(self):
        _,_,report,result,events=recovery_fixture()
        _,command=native.commands(report,'read',65,3,0xFFFFFE,0x987654,1,Path('/owned'),True)
        self.assertIn('--probe-config-error',command)
        with self.assertRaises(RuntimeError):native.commands(report,'write',65,3,0xFFFFFE,0x987654,1,Path('/owned'),True)
        report['application']['run_id']=0xFFFFFFFE
        with self.assertRaises(RuntimeError):native.commands(report,'read',65,3,0xFFFFFE,0x987654,1,Path('/owned'),True)
        worker=dict(operation='read',success=True,native_transfer_verified=True,owned_children_stopped_without_force=True,
            native_read_completed=True,source_memory_verified=True,host_bar_memory_verified=True,
            config_error_probe_requested=True,config_error_recovery_verified=True,global_reset_between_error_and_read=False)
        with self.assertRaises(RuntimeError):native.final_result(90,worker)
        for key,value in (('config_error_recovery_verified',False),('global_reset_between_error_and_read',True)):
            altered=dict(worker);altered[key]=value
            with self.subTest(key=key),self.assertRaises(RuntimeError):native.final_result(0,altered)
        self.reports[self._testMethodName]=dict(pass_test=True)


if __name__=='__main__':unittest.main()
