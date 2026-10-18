#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Run real integrity RTL tests against an explicit, unselected staged RTL.

Never edits board sources/selected evidence, runs Vivado or accesses hardware.
Only substitutes the exact ICRC file in each Icarus compiler invocation and
adds the pinned vendor AXIS register source. Testbench/oracles remain intact.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "rdma/tests"))
import test_icrc_rtl as integrity
import test_metadata_backpressure_rtl as metadata


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    candidate = args.candidate.resolve(strict=True)
    original = ROOT / "rdma/rtl/rocev2_ipv4_icrc.v"
    register = ROOT / "external/corundum/fpga/lib/eth/lib/axis/rtl/axis_register.v"
    if candidate == original.resolve() or args.report.exists():
        parser.error("need an unselected candidate and a new report path")
    observed = {str(path.relative_to(ROOT)): sha(path) for path in
                (original, register, Path(integrity.__file__), Path(metadata.__file__), Path(__file__))}
    candidate_before = sha(candidate)
    original_run = subprocess.run
    replacements = 0

    def run_candidate(command, *positional, **keywords):
        nonlocal replacements
        if isinstance(command, (list, tuple)) and Path(command[0]).name == "iverilog":
            command = list(command)
            if command.count(str(original)) != 1:
                raise RuntimeError("each compiler invocation must replace exactly the selected ICRC source")
            command = [str(candidate) if part == str(original) else part for part in command]
            if str(register) not in command:
                command.append(str(register))
            replacements += 1
        return original_run(command, *positional, **keywords)

    integrity.IntegrityRTLTests.reports = {}
    metadata.MetadataBackpressureRTLTests.reports = {}
    suite = unittest.TestSuite()
    suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(integrity.IntegrityRTLTests))
    suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(metadata.MetadataBackpressureRTLTests))
    # Suppress existing selected-result exporters for this isolated candidate.
    with mock.patch.dict(os.environ, AS02_RTL_REPORT="", AS02_METADATA_RTL_REPORT=""), \
            mock.patch.object(integrity.subprocess, "run", side_effect=run_candidate):
        result = unittest.TextTestRunner(verbosity=2).run(suite)
    unchanged = all(sha(ROOT / name) == value for name, value in observed.items())
    unchanged = unchanged and sha(candidate) == candidate_before
    success = result.wasSuccessful() and result.testsRun == replacements == 4 and unchanged
    report = dict(
        evidence_type="isolated staged-RTL integrity and real metadata-capacity tests, not a selected board source or hardware result",
        success=success, tests_run=result.testsRun, compiler_source_replacements=replacements,
        candidate=str(candidate), candidate_sha256=candidate_before,
        source_sha256=observed, inputs_unchanged=unchanged,
        integrity_tests=integrity.IntegrityRTLTests.reports,
        metadata_tests=metadata.MetadataBackpressureRTLTests.reports,
        selected_into_board_build=False, whole_hls_app_tests_run=False,
        physical_gate_passed=False, hardware_verified=False,
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as output:
        output.write(json.dumps(report, indent=2) + "\n")
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
