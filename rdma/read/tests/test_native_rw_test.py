# SPDX-License-Identifier: BSD-2-Clause-Views
"""Supervisor/provider/data-evidence rejection tests; no QPs, MMIO or traffic."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT / 'rdma/read/host'))
sys.path.insert(0,str(ROOT / 'rdma/read/tests'))
import native_rw_test as native
import test_rw_client as client_tests
import test_rw_preflight as preflight_tests


def fixture():
    observed=preflight_tests.fixture();observed['application']['run_id']=9
    report=native.preflight_module.audit(observed,True)
    registers=client_tests.Registers();peer=client_tests.PeerSocket(registers)
    result=native.client.run_read(registers,client_tests.CFG,peer)
    result.update(operation='read',application_version=0x20000,hardware_access=True,bdf=native.ROLES['fpga']['bdf'])
    source=dict(event='read_source',device='mlx5_0',bdf=native.ROLES['peer']['bdf'],gid_index=37,
        gid='::ffff:198.18.10.1',qpn=result['peer_qpn'],psn=result['peer_psn'],rkey=result['peer_rkey'],
        address=result['peer_address'],message_bytes=65,messages=3,path_mtu=4096,read_resources=1,
        remote_read_granted=True,remote_write_granted=False,nonce=result['nonce'],source_sha256=result['expected_payload_sha256'])
    events=[dict(event='listening',ip=native.ROLES['peer']['ip'],port=native.CONTROL_PORT),source,
        dict(event='read_remote',qpn=2,psn=0xFFFFFE,read_resources=1),
        dict(event='read_source_unchanged',bytes=195,mismatches=0,first_bad_offset=0,
             client_quiescent_control=True,client_aborted=False,pass_test=True)]
    events[-1]['pass']=True
    return report,result,events


def verify(report,result,events):return native.verify_results(report,result,events,'read',65,3,0xFFFFFE,0x987654,1)


class NativeRWTests(unittest.TestCase):
    reports={}

    @classmethod
    def tearDownClass(cls):
        if target:=os.environ.get('AS02_NATIVE_RW_TEST_REPORT'):
            paths=[Path(__file__),Path(native.__file__),Path(native.legacy.__file__),Path(native.client.__file__),
                Path(native.preflight_module.__file__),Path(client_tests.__file__),Path(preflight_tests.__file__)]
            result=dict(scope='Native supervisor/provider/evidence models; no hardware',hardware_verified=False,
                complete=len(cls.reports)==8,tests=cls.reports,
                source_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths})
            with Path(target).open('x') as out:out.write(json.dumps(result,indent=2)+'\n')

    def test_read_source_bar_metadata_and_scoped_commands(self):
        report,result,events=fixture();verified=verify(report,result,events)
        self.assertTrue(verified['native_transfer_verified'] and verified['host_bar_memory_verified'])
        self.assertEqual(verified['verified_bytes'],195)
        server,controller=native.commands(report,'read',65,3,0xFFFFFE,0x987654,1,Path('/test-owned-logs'))
        self.assertIn('fpga10g-cx4',server);self.assertIn('fpga10g-fpga',controller)
        self.assertIn('0000:82:00.0',controller);self.assertIn(str(ROOT / 'rdma/read/build/rc_read_peer'),server)
        self.assertIn('AS02_PHYSICAL_REVIEW_COMPLETE=YES',server);self.assertNotIn('enp7s0',server+controller)
        self.reports[self._testMethodName]=dict(pass_test=True)

    def test_incomplete_client_or_software_path_rejected(self):
        original,result,events=fixture()
        changes=dict(hardware_access=False,host_bar_verified=False,source_verified_unchanged=False,
            tx_quiescence_verified=False,bdf='0000:07:00.0',message_bytes=64,messages=2,issued=2,acknowledged=2,
            committed=2,capture_bytes=194,payload_bytes_compared=194,bar_bytes_compared=447,
            sentinel_bytes_compared=252,mismatches=1,read_window=2,source_payload_transferred_over_tcp=True,
            control_only_tcp=False,software_roce_in_this_client=True,expected_payload_complement_prefilled=False,
            status=0x5C1,run_id=9,operation_mode=0,capture_error=1,authorized=0,capture_state=4,
            capture_lease=64,padding_bytes=0,response_chunks=1,read_commands=1)
        for field,value in changes.items():
            altered=copy.deepcopy(result);altered[field]=value
            with self.subTest(field=field),self.assertRaises(RuntimeError):verify(original,altered,events)
        self.reports[self._testMethodName]=dict(pass_test=True,rejected=len(changes))

    def test_wrong_native_provider_nonce_mr_or_aborted_source_rejected(self):
        report,result,events=fixture();rejected=0
        changes={1:dict(device='rxe_ref',bdf='0000:07:00.0',gid_index=3,gid='::ffff:198.18.11.1',
            qpn=result['peer_qpn']+1,psn=0,rkey='0x00000000',address='0x0000000000000000',path_mtu=1024,
            read_resources=0,remote_read_granted=False,remote_write_granted=True,nonce='0'*64,source_sha256='0'*64),
            3:dict(bytes=194,mismatches=1,client_quiescent_control=False,client_aborted=True,**{'pass':False})}
        for index,fields in changes.items():
            for field,value in fields.items():
                altered=copy.deepcopy(events);altered[index][field]=value
                with self.subTest(field=field),self.assertRaises(RuntimeError):verify(report,result,altered)
                rejected+=1
        with self.assertRaises(RuntimeError):verify(report,result,events+[events[1]])
        altered=copy.deepcopy(report);altered['native_receiver']['device']='rxe_ref'
        with self.assertRaises(RuntimeError):verify(altered,result,events)
        self.reports[self._testMethodName]=dict(pass_test=True,rejected=rejected+2)

    def test_no_final_hardware_claim_before_thermal_and_owned_cleanup_proof(self):
        report,result,events=fixture();worker=verify(report,result,events)
        worker.update(success=True,owned_children_stopped_without_force=True)
        final=native.final_result(0,worker)
        self.assertTrue(final['hardware_rdma_verified']);self.assertFalse(final['physical_gate_automatically_checked'])
        with self.assertRaises(RuntimeError):native.final_result(90,worker)
        for field in ('success','native_transfer_verified','owned_children_stopped_without_force',
                      'native_read_completed','source_memory_verified','host_bar_memory_verified'):
            altered=dict(worker);altered[field]=False
            with self.subTest(field=field),self.assertRaises(RuntimeError):native.final_result(0,altered)
        self.reports[self._testMethodName]=dict(pass_test=True)

    def test_readonly_preflight_must_succeed_before_qp_creation(self):
        report,_,_=fixture()
        with mock.patch.object(native.subprocess,'run',return_value=mock.Mock(returncode=0,stdout=json.dumps(report),stderr='')) as run:
            self.assertTrue(native.preflight()['application']['quiescent'])
            self.assertIn('--require-application',run.call_args.args[0])
        for rc,change in ((1,{}),(0,dict(version=0x10000)),(0,dict(quiescent=False))):
            altered=copy.deepcopy(report);altered['application'].update(change)
            with mock.patch.object(native.subprocess,'run',return_value=mock.Mock(returncode=rc,stdout=json.dumps(altered),stderr='')):
                with self.assertRaises(RuntimeError):native.preflight()
        self.reports[self._testMethodName]=dict(pass_test=True)

    def test_failed_worker_stops_only_its_owned_children_client_first(self):
        report,_,_=fixture();server=mock.Mock();controller=mock.Mock()
        server.poll.return_value=None;controller.wait.return_value=1
        args=argparse.Namespace(operation='read',message_bytes=65,count=3,psn=0xFFFFFE,peer_psn=0x987654,
            read_window=1,probe_config_error=False)
        with tempfile.TemporaryDirectory(prefix='as02-native-rw-worker-') as directory:
            path=Path(directory)
            with mock.patch.object(native,'preflight',return_value=report), \
                mock.patch.object(native,'source_identity',return_value={}), \
                mock.patch.object(native.subprocess,'run',return_value=mock.Mock(stdout='')), \
                mock.patch.object(native.subprocess,'Popen',side_effect=[server,controller]), \
                mock.patch.object(native.legacy,'events',return_value=[dict(event='listening')]), \
                mock.patch.object(native.legacy,'stop_owned',return_value=True) as stopped:
                self.assertEqual(native.worker(args,path),1)
                self.assertEqual(stopped.call_args_list,[mock.call(controller),mock.call(server)])
            result=json.loads((path / 'worker.json').read_text())
            self.assertFalse(result['success'] or result['hardware_rdma_verified']);self.assertFalse(result['fpga_programmed'])
        self.reports[self._testMethodName]=dict(pass_test=True)

    def test_thermal_supervisor_and_sensor_fingerprints_required(self):
        with self.assertRaises(RuntimeError):native.require_authorization({})
        with tempfile.TemporaryDirectory(prefix='as02-native-thermal-fixture-') as directory:
            path=Path(directory);guard=path / 'guard.sh';sensor=path / 'read_temperature.cfg'
            guard.write_text('guard fixture\n');sensor.write_text('sensor fixture\n')
            with mock.patch.object(native.legacy,'require_authorization',return_value=guard), \
                mock.patch.object(native,'GUARD_SHA256',hashlib.sha256(guard.read_bytes()).hexdigest()), \
                mock.patch.object(native,'SENSOR_SHA256',hashlib.sha256(sensor.read_bytes()).hexdigest()):
                self.assertEqual(native.require_authorization({}),guard)
                sensor.write_text('changed\n')
                with self.assertRaises(RuntimeError):native.require_authorization({})
        self.reports[self._testMethodName]=dict(pass_test=True)

    def test_write_uses_original_all_byte_native_receiver_verifier(self):
        report,result,events=fixture();result.update(operation='write')
        verified=dict(native_transfer_verified=True,receiver_memory_verified=True,verified_bytes=195)
        with mock.patch.object(native.legacy,'verify_results',return_value=verified) as checked:
            output=native.verify_results(report,result,events,'write',65,3,0xFFFFFE,0x987654,1)
            checked.assert_called_once_with(report,result,events,65,3,0xFFFFFE,0x987654)
            self.assertTrue(output['native_write_completed']);self.assertFalse(output['native_read_completed'])
        self.reports[self._testMethodName]=dict(pass_test=True)


if __name__=='__main__':unittest.main()
