#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Negative controls for READ/WRITE preflight; no CAD or hardware access."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[3]
SCRIPT=ROOT / 'rdma/read/fpga/check_build.py'
spec=importlib.util.spec_from_file_location('rw_build_gate',SCRIPT)
gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate)
FIXTURES={kind:ROOT / 'results/2026-10-18' / name for kind,name in
    [('write','rocev2-rw-write-app-001.json'),(65,'rocev2-rw-read-app-003.json'),
     (4097,'rocev2-rw-read-app-002.json'),('warm','rocev2-rw-warm-app-001.json')]}


class RWBuildGateTests(unittest.TestCase):
    reports={}

    @classmethod
    def tearDownClass(cls):
        if target:=os.environ.get('AS02_RW_BUILD_GATE_REPORT'):
            deps=[SCRIPT,Path(__file__),*FIXTURES.values()]
            report=dict(scope='RW preflight predicate/hash negative controls; not CAD or hardware',
                hardware_verified=False,complete=len(cls.reports)==5,tests=cls.reports,
                source_sha256={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in deps})
            with Path(target).open('x') as out:out.write(json.dumps(report,indent=2)+'\n')

    def test_current_combined_app_reports_accepted(self):
        for kind,path in FIXTURES.items():gate.validate_app(json.loads(path.read_text()),kind)
        self.reports[self._testMethodName]=dict(pass_test=True,accepted=4)

    def test_read_missing_data_protection_or_checksums_rejected(self):
        rejected=0
        for kind in (65,4097):
            original=json.loads(FIXTURES[kind].read_text())
            fields=dict(host_bar_readback_bytes_verified=kind*3-1,prior_payload_complement_prefilled=False,
                protected_ram_used=False,version2_bar_used=False,done_after_ram_commit_checked=False,
                rtl_tx_guard_used=False,all_request_bytes_checked=False,wire_icrcs_valid=False,
                wire_ipv4_checksums_valid=False,initial_psn=0,message_count=2,hardware_verified=True)
            for field,value in fields.items():
                changed=copy.deepcopy(original);changed[field]=value
                with self.subTest(kind=kind,field=field),self.assertRaises(ValueError):gate.validate_app(changed,kind)
                rejected+=1
        self.reports[self._testMethodName]=dict(pass_test=True,rejected=rejected)

    def test_write_regression_scope_rejected_when_incomplete(self):
        original=json.loads(FIXTURES['write'].read_text())
        fields=dict(message_bytes=64,message_count=2,initial_psn=0,ack_every=1,wire_writes=2,
            wire_payload_bytes=194,all_wire_bytes_checked=False,wire_icrcs_valid=False,
            wire_ipv4_checksums_valid=False,physical_mac_completion_modeled=False)
        for field,value in fields.items():
            changed=copy.deepcopy(original);changed[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):gate.validate_app(changed,'write')
        self.reports[self._testMethodName]=dict(pass_test=True,rejected=len(fields))

    def test_warm_same_psn_stale_and_host_evidence_required(self):
        original=json.loads(FIXTURES['warm'].read_text())
        fields=dict(warm_runs=1,message_bytes=4096,same_qp_and_psn_reused=False,distinct_payloads=False,
            stale_read_first_discarded=0,host_frame_preserved_under_backpressure=False,
            host_bar_readback_bytes_verified=8193,payload_sha256=['same','same'])
        for field,value in fields.items():
            changed=copy.deepcopy(original);changed[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):gate.validate_app(changed,'warm')
        self.reports[self._testMethodName]=dict(pass_test=True,rejected=len(fields))

    def test_changed_source_and_relaxed_native_gate_fingerprints_rejected(self):
        with tempfile.TemporaryDirectory(prefix='as02-rw-hash-control-') as directory:
            fixture=Path(directory);path=fixture / 'input.v';path.write_text('original\n')
            expected={'input.v':hashlib.sha256(path.read_bytes()).hexdigest()}
            gate.check_hashes(expected,fixture)
            path.write_text('changed\n')
            with self.assertRaises(ValueError):gate.check_hashes(expected,fixture)
        gate.check_hashes(gate.PHYSICAL_INPUTS)
        changed=dict(gate.PHYSICAL_INPUTS);changed['fpga/write_verified_25g_eco.tcl']='0'*64
        with self.assertRaises(ValueError):gate.check_hashes(changed)
        self.reports[self._testMethodName]=dict(pass_test=True,changed_source_rejected=True,
            unchanged_native25_inputs_verified=True,wrong_native_gate_identity_rejected=True)


if __name__=='__main__':unittest.main()
