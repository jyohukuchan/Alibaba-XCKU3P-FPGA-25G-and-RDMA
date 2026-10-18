#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Exercise the real TX checksum FIFO at capacity, bad-frame drop and recovery.

Reuse the byte-exact RTL oracle/driver without changing its selected results.
No forced DUT state, shortened FIFO, hardware, network or Vivado operation.
"""
import hashlib
import json
import os
from pathlib import Path
import unittest
from unittest import mock

import test_icrc_rtl as integrity


class MetadataBackpressureRTLTests(unittest.TestCase):
    reports = {}

    @classmethod
    def tearDownClass(cls):
        if target := os.environ.get("AS02_METADATA_RTL_REPORT"):
            report = dict(
                evidence_type="real TX checksum FIFO capacity/drop/recovery RTL simulation, not hardware",
                complete=len(cls.reports) == 1,
                hardware_verified=False,
                tests=cls.reports,
                rtl_sha256=hashlib.sha256((integrity.ROOT / "rdma/rtl/rocev2_ipv4_icrc.v").read_bytes()).hexdigest(),
                test_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                base_test_sha256=hashlib.sha256(Path(integrity.__file__).read_bytes()).hexdigest(),
            )
            path = Path(target)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(report, indent=2) + "\n")

    def test_bad_final_beat_at_full_metadata_fifo_recovers(self):
        # 32 actual RAM slots plus the FIFO's two output pipeline registers.
        # Output remains blocked until cycle 6000 in the unchanged driver.
        # Complete good frames fill the checksum FIFO, not the 16KiB packet
        # FIFO. Then a malformed frame's final beat meets metadata backpressure.
        prefix = [integrity.packet(1, sequence=i) for i in range(34)]
        suffix = [integrity.packet(size, sequence=100 + i)
                  for i, size in enumerate((63, 64, 65, 4096))]
        invalid = bytearray(integrity.packet(1, sequence=99)[:-4])
        invalid[23] ^= 1  # UDP destination != 4791: discard the entire frame.
        inputs = [(packet[:-4], None, None) for packet in prefix]
        inputs.append((bytes(invalid), None, None))
        inputs.extend((packet[:-4], None, None) for packet in suffix)
        expected = prefix + suffix

        bench = integrity.TESTBENCH
        bench = bench.replace(
            "integer first_output=-1, last_output=-1;",
            "integer first_output=-1, last_output=-1;\n"
            "integer meta_full_cycles=0, bad_full_cycles=0, meta_pushes=0;",
        )
        bench = bench.replace(
            "if (good) good_count=good_count+1;",
            "if (!dut.meta_ready) meta_full_cycles=meta_full_cycles+1;\n"
            "  if (sv && sl && dut.staged_bad && !dut.meta_ready) bad_full_cycles=bad_full_cycles+1;\n"
            "  if (dut.meta_push) meta_pushes=meta_pushes+1;\n"
            "  if (good) good_count=good_count+1;",
        )
        bench = bench.replace(
            "if(quiet==50) begin",
            "if(quiet==50) begin\n"
            '   if(meta_full_cycles==0 || bad_full_cycles==0) $fatal(1,"metadata capacity/bad-final coverage missing");\n'
            '   if(meta_pushes!=GOOD_COUNT) $fatal(1,"orphan/absent checksum metadata entry");',
        )
        bench = bench.replace(
            r',\"last_output\":%0d}',
            r',\"last_output\":%0d,\"metadata_full_cycles\":%0d,\"bad_final_while_metadata_full_cycles\":%0d,\"checksum_entries_pushed\":%0d}',
        )
        bench = bench.replace(
            "first_output,last_output);",
            "first_output,last_output,meta_full_cycles,bad_full_cycles,meta_pushes);",
        )
        self.assertIn("metadata_full_cycles", bench)
        with mock.patch.object(integrity, "TESTBENCH", bench):
            result = integrity.IntegrityRTLTests.simulate(self, True, inputs, expected, 1)
        self.assertGreater(result["metadata_full_cycles"], 0)
        self.assertGreater(result["bad_final_while_metadata_full_cycles"], 0)
        self.assertEqual(result["checksum_entries_pushed"], len(expected))
        self.assertEqual(result["good_frames"], 38)
        self.assertEqual(result["bad_frames"], 1)
        self.reports[self._testMethodName] = dict(
            **result, pass_test=True, expected_good_packets=38, rejected_packets=1,
            checksum_fifo_ram_depth=32, checksum_fifo_depth_reduced=False,
            dut_state_forced=False, keep_masks_checked=65536,
        )


if __name__ == "__main__":
    unittest.main()
