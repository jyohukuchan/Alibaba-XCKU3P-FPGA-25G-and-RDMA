# SPDX-License-Identifier: BSD-2-Clause-Views
"""Offline release-package tests; /bin/false replaces Vivado, never hardware.

The checkpoint is deliberately NOT a DCP. These tests qualify provenance and
fail-closed preparation, not timing, CDC, bitstream generation or programming.
"""
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
FILES = (
    "rdma/scripts/release_routed_candidate.sh",
    "rdma/scripts/release_routed_candidate.tcl",
    "rdma/scripts/release_verify_mac_flow_control_cdc.tcl",
    "rdma/scripts/verify_lfc_equivalent.tcl",
    "fpga/write_verified_25g_eco.tcl",
    "fpga/verify_vio_status_cdc.tcl",
    "fpga/verify_mac_flow_control_cdc.tcl",
    "fpga/mac_flow_control_cdc.xdc",
    "external/corundum/fpga/mqnic/Nexus_K3P_S/fpga_25g/rtl/fpga_core.v",
    "external/corundum/fpga/lib/eth/rtl/eth_mac_10g.v",
    "external/corundum/fpga/common/rtl/mqnic_port.v",
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ReleaseProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="as02-release-provenance-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "checkout with spaces"
        for name in FILES:
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)
        self.build = self.root / "fpga/builds/as02mc04-25g-rocev2-negative-fixture"
        self.build.mkdir(parents=True)
        self.checkpoint = self.build / "as02mc04_25g_routed.dcp"
        self.checkpoint.write_bytes(b"NOT_A_DCP_OFFLINE_TEST_FIXTURE\n")
        self.frozen_source = self.root / "fixture-only.v"
        self.frozen_source.write_bytes(b"// test fixture, not an FPGA design\n")
        self.manifest = self.build / "rocev2-source-identity.txt"
        self.manifest.write_text(f"{sha(self.frozen_source)}  {self.frozen_source}\n")
        self.script = self.root / FILES[0]
        self.environment = dict(os.environ, VIVADO_BIN="/bin/false")
        self.environment.pop("AS02_BUILD_TERMINAL_CONFIRMED", None)

    def invoke(self, *arguments, terminal=False):
        env = self.environment.copy()
        if terminal:
            env["AS02_BUILD_TERMINAL_CONFIRMED"] = "YES"
        return subprocess.run(
            ["bash", str(self.script), *map(str, arguments)],
            env=env, capture_output=True, text=True, timeout=15,
        )

    def normal_arguments(self):
        return self.build, sha(self.manifest), sha(self.checkpoint)

    def packages(self):
        return sorted((self.root / "fpga/builds").glob("as02mc04-25g-rocev2-release-*"))

    def test_arguments_and_explicit_hashes_required(self):
        for arguments in ((), (self.build, "bad", "bad")):
            with self.subTest(arguments=arguments):
                self.assertEqual(self.invoke(*arguments).returncode, 2)
        self.assertEqual(self.packages(), [])

    def test_terminal_attestation_required_before_staging(self):
        result = self.invoke(*self.normal_arguments())
        self.assertEqual(result.returncode, 2)
        self.assertIn("confirm the original build process/session is terminal", result.stderr)
        self.assertEqual(self.packages(), [])

    def test_wrong_checkpoint_identity_rejected_before_vivado(self):
        result = self.invoke(self.build, sha(self.manifest), "0" * 64, terminal=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.packages(), [])

    def test_changed_original_source_rejected_before_vivado(self):
        arguments = self.normal_arguments()
        self.frozen_source.write_bytes(b"// intentionally changed test fixture\n")
        self.assertNotEqual(self.invoke(*arguments, terminal=True).returncode, 0)
        self.assertEqual(self.packages(), [])

    def test_existing_image_not_overwritten_or_alternately_released(self):
        image = self.build / "as02mc04_25g.bit"
        image.write_bytes(b"existing test fixture image")
        result = self.invoke(*self.normal_arguments(), terminal=True)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(image.read_bytes(), b"existing test fixture image")
        self.assertEqual(self.packages(), [])

    def test_unreviewed_gate_or_alias_assumption_rejected(self):
        for name in (FILES[4], FILES[5], FILES[6], FILES[3], *FILES[7:]):
            with self.subTest(source=name):
                path = self.root / name
                original = path.read_bytes()
                path.write_bytes(original + b"\n# deliberately altered test fixture\n")
                try:
                    self.assertNotEqual(self.invoke(*self.normal_arguments(), terminal=True).returncode, 0)
                    self.assertEqual(self.packages(), [])
                finally:
                    path.write_bytes(original)

    def test_preparation_preserves_original_and_binds_revision_separately(self):
        original_manifest = self.manifest.read_bytes()
        original_verifier = (self.root / FILES[6]).read_bytes()
        result = self.invoke(*self.normal_arguments(), terminal=True)
        # /bin/false deliberately stops here, without executing any Vivado.
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(len(self.packages()), 1)
        package = self.packages()[0]
        self.assertEqual(self.manifest.read_bytes(), original_manifest)
        self.assertEqual((self.root / FILES[6]).read_bytes(), original_verifier)
        self.assertEqual((package / "rocev2-source-identity.txt").read_bytes(), original_manifest)
        self.assertEqual((package / "verifiers/original_verify_mac_flow_control_cdc.tcl").read_bytes(), original_verifier)
        for name in (FILES[4], FILES[5]):
            self.assertEqual((package / "verifiers" / Path(name).name).read_bytes(), (self.root / name).read_bytes())
        revision = package / "verification-source-identity.txt"
        self.assertEqual(subprocess.run(["sha256sum", "--check", "--status", str(revision)]).returncode, 0)
        self.assertFalse((package / "as02mc04_25g.bit").exists())
        self.assertFalse((package / "as02mc04_25g.ltx").exists())
        copied_revision = package / "verifiers/verify_lfc_equivalent.tcl"
        copied_revision.write_bytes(copied_revision.read_bytes() + b"\n# deliberate staging corruption\n")
        result = subprocess.run(
            ["tclsh", str(package / "release_routed_candidate.tcl"), str(self.checkpoint),
             str(package), sha(revision), sha(self.manifest)],
            capture_output=True, text=True, timeout=15,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Release provenance is missing or changed", result.stderr)
        self.assertNotIn('invalid command name "open_checkpoint"', result.stderr)


if __name__ == "__main__":
    unittest.main()
