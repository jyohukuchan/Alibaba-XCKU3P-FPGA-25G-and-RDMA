# SPDX-License-Identifier: BSD-2-Clause-Views
"""Short actual generic-PCIe SQ path tests; physical host/link remain models."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[3]


class SQDMAFetchRTLTests(unittest.TestCase):
    def run_probe(self,error):
        with tempfile.TemporaryDirectory(prefix='as02-sq-dma-report-')as directory:
            report=Path(directory)/'result.json'
            command=[sys.executable,str(ROOT/'rdma/rnic/tests/probe_sq_dma_fetch.py'),'--report',str(report)]
            if error:command.append('--error')
            result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,timeout=20)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            data=json.loads(report.read_text())
            self.assertTrue(data['pass_test']);self.assertEqual(data['terminal_exit_status'],0)
            self.assertTrue(data['actual_PCIe_engine']);self.assertTrue(data['actual_backend_segmented_RAM_and_clients'])
            self.assertTrue(data['actual_native_shape_muxes']);self.assertTrue(data['no_host_write_or_fence'])
            self.assertFalse(data['hardware_verified']);self.assertFalse(data['RDMA_completion_claim'])
            self.assertEqual(data['summary']['results'],4 if error else 6)
            self.assertEqual(data['summary']['read_tlps'],data['summary']['results'])
            self.assertEqual(data['summary']['generic_correctable_events'],int(error))
            self.assertEqual(data['summary']['parent_proof_hold_cycles'],40 if error else 0)
            self.assertEqual(data['zeroed_error_record_bytes_verified'],64 if error else 0)

    def test_actual_DMA64_ring_records_mux_tags_RAM_and_reuse(self):self.run_probe(False)
    def test_actual_PCIe_UR_zero_record_queue_stop_real_drain_and_fresh_epoch_recovery(self):self.run_probe(True)


if __name__=='__main__':unittest.main()
