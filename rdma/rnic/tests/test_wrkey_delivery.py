# SPDX-License-Identifier: BSD-2-Clause-Views
"""Synthetic delivery/provenance refusal tests, NOT HLS/wire/native proof."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import wrkey_delivery_sim as simulation

ROOT = Path(__file__).resolve().parents[3]
GENERATOR = ROOT/'rdma/rnic/fpga/prepare_wrkey_transport.py'
spec = importlib.util.spec_from_file_location('test_wrkey_delivery_generator', GENERATOR)
generator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generator)


def fixture(base):
    """Small fake text files for verifier refusal ONLY, not compilable HLS."""
    original = base/'original/solution1/syn/verilog'
    delivered = base/'delivery/solution1/syn/verilog'
    original.mkdir(parents=True);delivered.mkdir(parents=True)
    names = ['rocev2_top.v']+[f'synthetic_{i:03d}.v' for i in range(137)]
    for name in names:
        p = original/name;p.write_text('// synthetic nonfunctional fixture '+name+'\n')
        shutil.copy2(p,delivered/name)
    raw_hash,_ = generator.aggregate(original)
    hls = base/'fake-hls.json'
    hls.write_text(json.dumps(dict(pass_test=True,terminal_exit_status=0,generated_files=138,
        generated_hls_sha256=raw_hash,hls_build=str(base/'original'))))
    (delivered/'rocev2_integrity_transport_wrkey.v').write_text(generator.derive_bridge(generator.BRIDGE.read_text()))
    shutil.copy2(generator.ADAPTER,delivered/generator.ADAPTER.name)
    full_hash,files = generator.aggregate(delivered)
    record = dict(profile='per-wr-key-context-v1',prepared=True,
        output_directory=str(base/'delivery'),legacy_default_mode=1,explicit_key_mode=0,
        original_generated_files=138,delivery_files=140,hls_record=str(hls),
        original_generated_HLS_sha256=raw_hash,delivery_sha256=full_hash,
        copied_raw_sha256={n:generator.digest(original/n) for n in names},
        generated_sha256={p.name:generator.digest(p) for p in files},
        source_sha256={str(p):generator.digest(p) for p in
            [GENERATOR,generator.BRIDGE,generator.ADAPTER,hls]})
    save_record(base,record)
    return base/'delivery',record


def save_record(base,record):
    (base/'delivery/wrkey-delivery.json').write_text(json.dumps(record))


def rewrite_generated_manifest(base,record):
    folder=base/'delivery/solution1/syn/verilog'
    value,files=generator.aggregate(folder)
    record['delivery_sha256']=value
    record['generated_sha256']={p.name:generator.digest(p) for p in files}
    save_record(base,record)


class WRKeyDeliveryTests(unittest.TestCase):
    def test_exact_interface_derivation_keeps_original_and_refuses_reapplication(self):
        original=generator.BRIDGE.read_text()
        before=generator.digest(generator.BRIDGE)
        derived=generator.derive_bridge(original)
        self.assertIn('parameter LEGACY_QP_KEY = 1',derived)
        self.assertIn('input wire [31:0] s_axis_sq_rkey,',derived)
        self.assertIn('.s_axis_sq_meta_TDATA(keyed_sq_data)',derived)
        self.assertEqual(derived.count('rocev2_top transport ('),1)
        for preserved in ['rocev2_ipv4_icrc #(.TX_MODE(0)) rx_integrity',
                          '.ap_clk(clk), .ap_rst_n(!rst), .local_ip_address(local_ip_address)']:
            self.assertIn(preserved,derived)
        self.assertEqual(before,generator.digest(generator.BRIDGE))
        with self.assertRaises(ValueError):generator.derive_bridge(derived)

    def test_unreviewed_original_interface_refused(self):
        text=generator.BRIDGE.read_text()
        for changed in [text.replace('[239:0] s_axis_sq_tdata','[238:0] s_axis_sq_tdata'),
                        text+'\nrocev2_top transport (\n']:
            with self.subTest(changed=changed[-40:]),self.assertRaises(ValueError):
                generator.derive_bridge(changed)

    def test_wrong_reset_scope_or_mixed_candidate_refused(self):
        # Synthetic shape fixture, not source preparation/function evidence.
        source=dict(source_freeze_prepared=True,upstream_commit='75c32bae73f5c336b5c46c9de35ae0cb9cb7cc1c',
            source_sha256={n:'old' for n in generator.TARGETS},
            patched_source_sha256={n:'new' for n in generator.TARGETS},
            metadata_entries=2000,metadata_fields=13,hls_build='synthetic')
        hls=dict(pass_test=True,terminal_exit_status=0,SQ_AXIS_width_248_verified=True,
                 source_and_frozen_inputs_unchanged=True,hls_build='synthetic',generated_hls_sha256='same')
        table=dict(pass_test=True,four_state_simulation=True,inputs_unchanged=True,
            metadata_fields=13,metadata_entries=2000,sequential_initialization_required=True,
            original_testbench_assertions_and_deadlines_preserved=True,
            checks=8024,zero_checks=4023,data_checks=2000,append_checks=2001,reset_checks=16,
            generated_hls_sha256='same')
        ctor=dict(characterization_pass=True,release_reset_gate_pass=True,total_observations=88,
                  invalid_observations=0,observations=[{'valid':True}]*88,generated_hls_sha256='same')
        valid=[source,hls,table,ctor];generator.validate(valid)
        for idx,key,value in [(0,'metadata_entries',8),(1,'SQ_AXIS_width_248_verified',False),
                (2,'four_state_simulation',False),(2,'checks',8023),(2,'metadata_fields',10),
                (3,'generated_hls_sha256','other'),(3,'invalid_observations',1)]:
            with self.subTest(key=key):
                bad=copy.deepcopy(valid);bad[idx][key]=value
                with self.assertRaises(ValueError):generator.validate(bad)

    def test_self_consistent_output_manifest_cannot_hide_raw_or_adapter_edits(self):
        for target in ['rocev2_top.v','rocev2_wrkey_sq_adapter.v','rocev2_integrity_transport_wrkey.v']:
            with self.subTest(target=target),tempfile.TemporaryDirectory(prefix='as02-wrkey-delivery-') as directory:
                base=Path(directory);project,record=fixture(base)
                simulation.verify_delivery(project)
                p=project/'solution1/syn/verilog'/target
                p.write_text(p.read_text()+'\n// synthetic unexpected edit\n')
                rewrite_generated_manifest(base,record)
                with self.assertRaises(ValueError):simulation.verify_delivery(project)

    def test_extra_or_missing_HDL_refused_even_if_manifest_rewritten(self):
        for extra in [False,True]:
            with self.subTest(extra=extra),tempfile.TemporaryDirectory(prefix='as02-wrkey-files-') as directory:
                base=Path(directory);project,record=fixture(base)
                folder=project/'solution1/syn/verilog'
                if extra:(folder/'unexpected.v').write_text('// synthetic extra')
                else:(folder/'synthetic_000.v').unlink()
                rewrite_generated_manifest(base,record)
                with self.assertRaises(ValueError):simulation.verify_delivery(project)

    def test_existing_output_refused_before_input_access(self):
        with tempfile.TemporaryDirectory(prefix='as02-wrkey-existing-') as directory:
            base=Path(directory);(base/'sentinel').write_text('retain')
            result=subprocess.run(['python3',str(GENERATOR),'--source-record','missing-source',
                '--hls-record','missing-hls','--table-record','missing-table',
                '--constructor-record','missing-ctor','--output',str(base)],
                capture_output=True,text=True,timeout=10)
            self.assertNotEqual(result.returncode,0)
            self.assertIn('never overwrite an existing delivery',result.stderr)
            self.assertEqual((base/'sentinel').read_text(),'retain')

    def test_identity_extension_does_not_collide_with_original_report_fields(self):
        with tempfile.TemporaryDirectory(prefix='as02-wrkey-identity-',dir=ROOT/'rdma/rnic') as directory:
            project,_=fixture(Path(directory))
            # Simulate only the existing runner's metadata return, NOT RTL.
            with patch.object(simulation,'ORIGINAL_SIMULATE',return_value=('synthetic',{'source_sha256':{}})):
                output,identity=simulation.simulate('',{},project)
            self.assertEqual(output,'synthetic')
            self.assertNotIn('hardware_verified',identity)
            self.assertNotIn('standard_verbs_implemented',identity)
            report=dict(hardware_verified=False,standard_verbs_implemented=False,**identity)
            self.assertFalse(report['hardware_verified'])
            self.assertFalse(report['delivery_hardware_verified'])
            self.assertIs(simulation.bounded.rw_sim.modules,simulation.ORIGINAL_MODULES)


if __name__=='__main__':unittest.main()
