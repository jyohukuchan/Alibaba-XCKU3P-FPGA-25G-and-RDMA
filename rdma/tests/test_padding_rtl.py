#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Candidate TX padding normalization followed by real integrity RTL."""
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import tempfile
import unittest

from test_icrc_rtl import TESTBENCH, packet, words

ROOT = pathlib.Path(__file__).resolve().parents[2]


def unpadded(ip):
    """Reproduce the pinned HLS core's absent pad/BTH pad-count behavior."""
    pad = (ip[29] >> 4) & 3
    bare = bytearray(ip[:len(ip) - 4 - pad])
    bare[2:4] = (int.from_bytes(ip[2:4], "big") - pad).to_bytes(2, "big")
    bare[24:26] = (int.from_bytes(ip[24:26], "big") - pad).to_bytes(2, "big")
    bare[29] &= 0xCF
    return bytes(bare)


class PaddingRTLTests(unittest.TestCase):
    reports = {}

    @classmethod
    def tearDownClass(cls):
        if target := os.environ.get("AS02_PADDING_RTL_REPORT"):
            record = dict(evidence_type="TX padding/integrity RTL simulation, not hardware", hardware_verified=False,
                          complete=len(cls.reports) == 3, tests=cls.reports,
                          source_sha256={name: hashlib.sha256((ROOT / "rdma/rtl" / name).read_bytes()).hexdigest()
                                         for name in ("rocev2_tx_padding.v", "rocev2_ipv4_icrc.v")},
                          test_sha256=hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),
                          integrity_test_dependency_sha256=hashlib.sha256((ROOT / "rdma/tests/test_icrc_rtl.py").read_bytes()).hexdigest())
            output = pathlib.Path(target)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(record, indent=2) + "\n")

    def simulate(self, inputs, expected, bad_count, throughput=False):
        self.assertIsNotNone(shutil.which("iverilog"))
        tb = TESTBENCH
        # Reuse the integrity test's strict byte/stall/full-frame scoreboard;
        # insert padding normalization in front of the actual integrity DUT.
        for old, new in (("tdata(sd)", "tdata(pd)"), ("tkeep(sk)", "tkeep(pk)"), ("tvalid(sv)", "tvalid(pv)"),
                         ("tready(sr)", "tready(pr)"), ("tlast(sl)", "tlast(pl)"), ("tuser(su)", "tuser(pu)")):
            self.assertIn(old, tb)
            tb = tb.replace(old, new)
        prefix = r'''
wire [127:0] pd;
wire [15:0] pk;
wire pv,pr,pl,pu;
rocev2_tx_padding padding (
 .clk(clk),.rst(rst),.s_axis_tdata(sd),.s_axis_tkeep(sk),.s_axis_tvalid(sv),.s_axis_tready(sr),.s_axis_tlast(sl),.s_axis_tuser(su),
 .m_axis_tdata(pd),.m_axis_tkeep(pk),.m_axis_tvalid(pv),.m_axis_tready(pr),.m_axis_tlast(pl),.m_axis_tuser(pu),
 .status_padded_frame(),.status_bad_frame());
'''
        tb = tb.replace("rocev2_ipv4_icrc #", prefix + "rocev2_ipv4_icrc #", 1)
        input_words = [w for frame, error, hole in inputs for w in words(frame, error, hole)]
        output_words = [w for frame in expected for w in words(frame)]
        constants = dict(TX_VALUE=1, INPUT_COUNT=len(input_words), OUTPUT_COUNT=len(output_words),
                         GOOD_COUNT=len(expected), BAD_COUNT=bad_count, THROUGHPUT_MODE=int(throughput))
        for name, value in constants.items():
            tb = tb.replace(name, str(value))
        with tempfile.TemporaryDirectory(prefix="as02-tx-padding-") as directory:
            path = pathlib.Path(directory)
            (path / "tb.v").write_text(tb)
            (path / "input.hex").write_text("".join(f"{w:x}\n" for w in input_words))
            (path / "expected.hex").write_text("".join(f"{w:x}\n" for w in output_words))
            sources = [ROOT / "rdma/rtl/rocev2_tx_padding.v", ROOT / "rdma/rtl/rocev2_ipv4_icrc.v",
                       ROOT / "external/corundum/fpga/lib/axis/rtl/axis_fifo.v",
                       ROOT / "external/corundum/fpga/lib/axis/rtl/axis_register.v",
                       ROOT / "external/corundum/fpga/lib/eth/rtl/lfsr.v"]
            compiled = subprocess.run(["iverilog", "-g2012", "-s", "tb", "-o", str(path / "test.vvp"),
                                       str(path / "tb.v"), *map(str, sources)], capture_output=True, text=True, timeout=30)
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            result = subprocess.run(["vvp", str(path / "test.vvp")], cwd=path, capture_output=True, text=True, timeout=100)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertNotIn("ERROR:", result.stdout + result.stderr)
            records = [json.loads(line[7:]) for line in result.stdout.splitlines() if line.startswith("RESULT ")]
            self.assertEqual(len(records), 1, result.stdout)
            return records[0]

    def test_all_padding_tail_positions(self):
        expected = [packet(n, n) for n in [*range(1, 34), 63, 64, 65, 4095, 4096]]
        result = self.simulate([(unpadded(p), None, None) for p in expected], expected, 0)
        self.reports[self._testMethodName] = dict(**result, pass_test=True)

    def test_bad_input_not_healed(self):
        valid = packet(65)
        bare = unpadded(valid)
        # Fill the complete-frame FIFO before the delayed sink is released;
        # malformed/recovery packets must also traverse real input stalls.
        prefix = [packet(4095, i) for i in range(8)]
        inputs = [(unpadded(p), None, None) for p in prefix]
        expected = list(prefix)
        bad_frames = [(bare, 0, None), (bare, 4, None), (bare, None, 2), (bare, None, 7)]
        for position in (2, 25, 29):
            changed = bytearray(bare); changed[position] ^= 0x10 if position == 29 else 1
            bad_frames.append((bytes(changed), None, None))
        for bad in bad_frames:
            inputs += [bad, (bare, None, None)]
            expected.append(valid)
        result = self.simulate(inputs, expected, len(bad_frames))
        self.reports[self._testMethodName] = dict(**result, pass_test=True)

    def test_padding_path_25g_cycle_capacity(self):
        frames = [packet(4095, i) for i in range(32)]
        result = self.simulate([(unpadded(p), None, None) for p in frames], frames, 0, throughput=True)
        cycles = result["last_output"] - result["first_output"] + 1
        rate = 32 * 4095 * 8 / (cycles * 4)
        self.assertGreater(rate, 25)
        self.reports[self._testMethodName] = dict(**result, pass_test=True,
                                                simulated_payload_gbit_s_at_250mhz=rate, routed_clock_verified=False)


if __name__ == "__main__":
    unittest.main(verbosity=2)
