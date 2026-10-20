# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual CSR-controlled shared PCIe graph; privileged software/host are models."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[3]


class SQControlledPCIe(unittest.TestCase):
    def test_actual_AXI_SQ_owner_publication_fetch_and_retire_through_real_shared_DMA(self):
        with tempfile.TemporaryDirectory(prefix='as02-controlled-sq-report-')as directory:
            report=Path(directory)/'report.json'
            r=subprocess.run([sys.executable,str(ROOT/'rdma/rnic/tests/probe_sq_controlled_pcie.py'),
                '--report',str(report)],cwd=ROOT,capture_output=True,text=True,timeout=20)
            self.assertEqual(r.returncode,0,r.stdout+r.stderr)
            data=json.loads(report.read_text());self.assertTrue(data['pass_test'])
            self.assertEqual(data['terminal_exit_status'],0)
            self.assertTrue(data['source_sha256_before_after_equal'])
            self.assertTrue(data['actual_SQ_CSR_AW_W_adapter_and_real_backend_composition'])
            self.assertTrue(data['actual_shared_router_RAM_mux_PCIe_parent_guard'])
            for k in ['raw_SQ_configuration_bypass','constant_parent_proof_or_host_counter_substitution',
                      'descriptor_status_RAM_agents_used','hardware_verified','native_parent_mapping_or_kernel_driver',
                      'local_MR_WQE_executor_CQ_or_verbs','actual_kernel_pins_or_coherent_allocation']:
                self.assertFalse(data[k],k)
            self.assertEqual(data['control_summary'],dict(commands=4,last_sequence=4,
                             raw_SQ_configuration_bypass=False,owner_active=0))
            for k,v in dict(descriptors=7,restored_statuses=7,read_tlps=5,write_tlps=2,
                write_bytes=65,read_bytes=65,SQ_records=2,peak_active_clients=2,write_tx_seq_hold_cycles=128).items():
                self.assertEqual(data['summary'][k],v,k)
            self.assertEqual(data['SQ_descriptor_bytes_verified'],128)
            self.assertEqual(data['host_sentinel_bytes_verified'],16319)
            self.assertEqual(data['coherent_ring_unchanged_bytes_verified'],128)


if __name__=='__main__':unittest.main()
