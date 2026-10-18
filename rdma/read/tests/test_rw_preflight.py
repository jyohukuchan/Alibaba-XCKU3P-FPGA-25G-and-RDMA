# SPDX-License-Identifier: BSD-2-Clause-Views
"""Pure network/BAR observation fixtures, no sysfs/MMIO/QPs/packets."""
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
sys.path.insert(0,str(ROOT / 'rdma/tests'))
import native_rw_preflight as preflight
import test_native_preflight as legacy_tests


def fixture():
    value=legacy_tests.fixture()
    value['application']=dict(bar2_present=True,registers_read=True,id=0x524F4332,version=0x20000,
        aperture_bytes=16*1024*1024,capacity=262144,ram_base=0x10000,status=0x38,mode=0,run_id=12,capture_state=6)
    return value


class RWPreflightTests(unittest.TestCase):
    reports={}

    @classmethod
    def tearDownClass(cls):
        if target:=os.environ.get('AS02_RW_PREFLIGHT_REPORT'):
            paths=[Path(__file__),Path(preflight.__file__),Path(preflight.legacy.__file__),Path(legacy_tests.__file__)]
            result=dict(scope='Version2 preflight observation models only, not hardware',hardware_verified=False,
                complete=len(cls.reports)==6,tests=cls.reports,
                source_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths})
            with Path(target).open('x') as out:out.write(json.dumps(result,indent=2)+'\n')

    def test_v2_idle_done_and_error_quiescence(self):
        for status,mode,capture in ((0x38,0,6),(0xB8,1,6),(0x7BA,1,6),(0x8BC,1,5),(0x73A,0,6)):
            snapshot=fixture();snapshot['application'].update(status=status,mode=mode,capture_state=capture)
            result=preflight.audit(snapshot,True)
            self.assertTrue(result['application']['supported'] and result['application']['quiescent'])
            self.assertEqual(result['native_receiver']['gid_index'],37)
        self.reports[self._testMethodName]=dict(pass_test=True,states=5)

    def test_v1_unknown_busy_bad_layout_and_exhausted_generation_refused(self):
        changes=[dict(version=0x10000),dict(id=0),dict(capacity=65536),dict(ram_base=0x20000),
            dict(aperture_bytes=4096),dict(status=0x5C1,mode=1),dict(status=0xB8,mode=0),
            dict(capture_state=2),dict(status=0x738),dict(run_id=0xFFFFFFFF)]
        for change in changes:
            snapshot=fixture();snapshot['application'].update(change)
            with self.subTest(change=change),self.assertRaises(preflight.legacy.PreflightError):preflight.audit(snapshot,True)
        self.reports[self._testMethodName]=dict(pass_test=True,rejections=len(changes))

    def test_native_role_gid_and_physical_link_guards_retained(self):
        mutations=[('bdf','0000:07:00.0'),('driver','rdma_rxe')]
        for field,value in mutations:
            snapshot=fixture();snapshot['devices']['peer'][field]=value
            with self.assertRaises(preflight.legacy.PreflightError):preflight.audit(snapshot,True)
        snapshot=fixture();snapshot['rdma']['gids'][0]['type']='IB/RoCE v1'
        with self.assertRaises(preflight.legacy.PreflightError):preflight.audit(snapshot,True)
        snapshot=fixture();snapshot['devices']['peer']['link']='Speed: 10000Mb/s\nDuplex: Full\nLink detected: yes\n'
        with self.assertRaises(preflight.legacy.PreflightError):preflight.audit(snapshot,True)
        self.reports[self._testMethodName]=dict(pass_test=True,rejections=4)

    def test_version1_identity_only_still_allows_readonly_network_audit(self):
        snapshot=fixture()
        snapshot['application']=dict(bar2_present=True,registers_read=True,id=0x524F4332,version=0x10000,
                                     aperture_bytes=16*1024*1024)
        result=preflight.audit(snapshot,False)
        self.assertTrue(result['success']);self.assertFalse(result['application']['supported'])
        self.assertFalse(result['application']['quiescent']);self.assertNotIn('status',result['application'])
        with self.assertRaises(preflight.legacy.PreflightError):preflight.audit(snapshot,True)
        self.reports[self._testMethodName]=dict(pass_test=True)

    def test_read_only_mapping_stops_at_unknown_version(self):
        for version,reads in ((0x10000,2),(0x20000,8)):
            values=[(0x524F4332,),(version,)]+[(v,) for v in (0x38,0,262144,0x10000,12,6)]
            with mock.patch.object(preflight.os,'open',return_value=5) as opened, \
                mock.patch.object(preflight.os,'fstat',return_value=mock.Mock(st_size=16*1024*1024)), \
                mock.patch.object(preflight.os,'close') as closed, \
                mock.patch.object(preflight.mmap,'mmap') as mapped, \
                mock.patch.object(preflight.struct,'unpack_from',side_effect=values) as unpacked:
                result=preflight.read_application(Path('/test-only-device'))
                self.assertEqual(unpacked.call_count,reads)
                self.assertEqual(mapped.call_args.kwargs['prot'],preflight.mmap.PROT_READ)
                self.assertFalse(opened.call_args.args[1]&preflight.os.O_RDWR)
                if version==0x10000:self.assertNotIn('status',result)
                closed.assert_called_once_with(5)
        self.reports[self._testMethodName]=dict(pass_test=True)

    def test_collector_never_uses_legacy_v1_bar_reader(self):
        snapshot=fixture();snapshot['application']=dict(bar2_present=True,registers_read=False)
        with mock.patch.object(preflight.legacy,'collect',return_value=copy.deepcopy(snapshot)) as collected, \
            mock.patch.object(preflight,'read_application',return_value=fixture()['application']) as reader:
            result=preflight.collect(sysfs=Path('/mock-sysfs'),read_app=True)
            self.assertTrue(result['application']['registers_read'])
            self.assertFalse(collected.call_args.kwargs['read_app'])
            reader.assert_called_once_with(Path('/mock-sysfs/bus/pci/devices/0000:82:00.0'))
        self.reports[self._testMethodName]=dict(pass_test=True)


if __name__=='__main__':unittest.main()
