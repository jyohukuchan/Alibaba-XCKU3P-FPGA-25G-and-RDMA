# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual shared SQ/payload PCIe graph; host/root complex/link are models."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[3]


class SharedSQPayloadDMA(unittest.TestCase):
    def test_actual_clients_tag_translation_segmented_RAM_muxes_and_parent_guard(self):
        with tempfile.TemporaryDirectory(prefix='as02-sq-paged-report-')as directory:
            report=Path(directory)/'result.json'
            result=subprocess.run([sys.executable,str(ROOT/'rdma/rnic/tests/probe_sq_paged_dma.py'),
                '--report',str(report)],cwd=ROOT,capture_output=True,text=True,timeout=20)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            data=json.loads(report.read_text())
            self.assertTrue(data['pass_test']);self.assertEqual(data['terminal_exit_status'],0)
            self.assertTrue(data['source_sha256_before_after_equal'])
            self.assertTrue(data['actual_router_paged_SQ_RAM_mux_PCIe_and_parent_guard'])
            for key in ['hardware_verified','actual_native_parent_or_board','constant_parent_drained_used',
                        'descriptor_status_RAM_agents_used','protected_network_admission_verified',
                        'local_WQE_execution_or_CQ_or_standard_verbs_verified','real_kernel_pins_or_coherent_allocation']:
                self.assertFalse(data[key],key)
            expected=dict(descriptors=7,restored_statuses=7,read_tlps=5,write_tlps=2,
                          write_bytes=65,read_bytes=65,SQ_records=2,peak_active_clients=2,
                          write_tx_seq_hold_cycles=128)
            for key,value in expected.items():self.assertEqual(data['summary'][key],value,key)
            self.assertEqual(data['SQ_descriptor_bytes_verified'],128)
            self.assertEqual(data['payload_WRITE_bytes_verified'],65)
            self.assertEqual(data['payload_READ_bytes_verified'],65)
            self.assertEqual(data['host_sentinel_bytes_verified'],16319)
            self.assertEqual(data['coherent_ring_unchanged_bytes_verified'],128)


if __name__=='__main__':unittest.main()
