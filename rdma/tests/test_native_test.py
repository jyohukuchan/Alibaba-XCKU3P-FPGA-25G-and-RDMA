#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Native runner unit tests with modeled records/child processes only."""
import argparse
import copy
import hashlib
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "host"))
import native_test as runner
import native_preflight
from test_native_preflight import fixture as preflight_fixture


def observations(size=65, count=3, psn=0xFFFFFE, peer_psn=0x987654):
    snapshot = preflight_fixture()
    snapshot["application"] = dict(bar2_present=True, registers_read=True, id=0x524F4332,
                                    version=0x10000, status=0x38)
    report = native_preflight.audit(snapshot, require_application=True)
    client = dict(success=True, receiver_verified=True, tx_quiescence_verified=True, hardware_access=True,
                  bdf="0000:82:00.0", message_bytes=size, messages=count, issued=count, acknowledged=count,
                  total_bytes=size * count, elapsed_cycles=10000, software_roce_in_this_client=False,
                  control_only_tcp=True, fpga_payload_source="bounded_local_pattern", peer_qpn=0x74,
                  peer_psn=peer_psn, local_qpn=2, local_psn=psn, seconds_from_hw_counter=0.00004,
                  payload_gbit_per_second_from_hw_counter=size * count * 8 / 0.00004 / 1e9)
    receiver = [dict(event="listening", ip="198.18.10.1", port=18516),
                dict(event="local_endpoint", device="mlx5_0", gid_index=37, gid="::ffff:198.18.10.1",
                     qpn=0x74, psn=peer_psn, path_mtu=4096, message_bytes=size, messages=count),
                dict(event="remote_endpoint", device="peer", gid="::ffff:198.18.10.2", qpn=2, psn=psn,
                     path_mtu=4096, message_bytes=size, messages=count),
                dict(event="memory_verification", bytes=size * count, mismatches=0, first_bad_offset=0, pass_=True)]
    receiver[-1]["pass"] = receiver[-1].pop("pass_")
    return report, client, receiver


class RunnerTests(unittest.TestCase):
    def test_explicit_authorization_precedes_guard_filesystem_access(self):
        with mock.patch.object(pathlib.Path, "is_file", side_effect=AssertionError("unexpected file access")):
            for environment in ({}, {"AS02_ALLOW_NATIVE_FPGA_RDMA_TEST": "YES"}):
                with self.subTest(environment=environment), self.assertRaises(runner.TestError):
                    runner.require_authorization(environment)
        with tempfile.TemporaryDirectory() as directory:
            guard = pathlib.Path(directory) / "guard.sh"
            guard.touch()
            environment = dict(AS02_ALLOW_NATIVE_FPGA_RDMA_TEST="YES", AS02_PHYSICAL_REVIEW_COMPLETE="YES",
                               AS02_TEMPERATURE_GUARD=str(guard))
            self.assertEqual(runner.require_authorization(environment), guard.resolve())
            environment["AS02_TEMPERATURE_GUARD"] = "relative.sh"
            with self.assertRaises(runner.TestError):
                runner.require_authorization(environment)

    def test_finite_limits_and_full_width_psn(self):
        runner.validate_request(4096, 16384, 0xFFFFFF, 0xFFFFFF)
        for values in ((0, 1, 0, 0), (4097, 1, 0, 0), (65, 0, 0, 0), (4096, 16385, 0, 0),
                       (1, 65537, 0, 0), (1, 1, -1, 0), (1, 1, 0x1000000, 0), (1, 1, 0, 0x1000000)):
            with self.subTest(values=values), self.assertRaises(RuntimeError):
                runner.validate_request(*values)

    def test_commands_use_actual_macs_gid_and_native_device_only(self):
        report, _, _ = observations()
        server, client = runner.commands(report, 65, 3, 0xFFFFFE, 0x987654, pathlib.Path("/fixture/log"))
        self.assertIn("mlx5_0", server)
        self.assertEqual(server[server.index("mlx5_0") + 1], "37")
        self.assertEqual(client[client.index("--local-mac") + 1], "d6:b9:fb:83:a4:51")
        self.assertEqual(client[client.index("--peer-mac") + 1], "b8:83:03:67:c5:d0")
        self.assertEqual(client[client.index("--bdf") + 1], "0000:82:00.0")
        for forbidden in ("rxe", "modprobe", "openFPGALoader", "192.168.0.148", "enp7s0"):
            self.assertNotIn(forbidden, " ".join(server + client))
        self.assertIn("AS02_ALLOW_FPGA_RDMA=YES", client)

    def test_matching_native_records_are_verified_but_not_wire_benchmark(self):
        result = runner.verify_results(*observations(), 65, 3, 0xFFFFFE, 0x987654)
        self.assertTrue(result["native_transfer_verified"])
        self.assertEqual(result["verified_bytes"], 195)
        self.assertTrue(result["includes_initialization_and_drain"])
        self.assertNotIn("hardware_rdma_verified", result)  # External guard still must pass.

    def test_bad_client_counts_software_path_or_quiescence_never_pass(self):
        for key, value in (("success", False), ("receiver_verified", False), ("hardware_access", False),
                           ("tx_quiescence_verified", False), ("total_bytes", 194), ("acknowledged", 2),
                           ("software_roce_in_this_client", True), ("control_only_tcp", False),
                           ("fpga_payload_source", "software")):
            with self.subTest(key=key):
                report, client, receiver = observations(); client[key] = value
                with self.assertRaises(runner.TestError):
                    runner.verify_results(report, client, receiver, 65, 3, 0xFFFFFE, 0x987654)

    def test_peer_provider_gid_qp_psn_or_memory_failure_never_pass(self):
        for index, key, value in ((0, "ip", "192.168.0.148"), (0, "port", 1234),
                                  (1, "device", "rxe_as02_ref"), (1, "gid_index", 3), (1, "qpn", 0x75),
                                  (1, "psn", 0), (1, "gid", "::ffff:198.18.11.1"), (1, "path_mtu", 1024),
                                  (2, "qpn", 3), (2, "psn", 0), (3, "bytes", 194),
                                  (3, "mismatches", 1), (3, "pass", False)):
            with self.subTest(index=index, key=key):
                report, client, receiver = observations(); receiver[index][key] = value
                with self.assertRaises(runner.TestError):
                    runner.verify_results(report, client, receiver, 65, 3, 0xFFFFFE, 0x987654)
        report, client, receiver = observations(); receiver.append(copy.deepcopy(receiver[-1]))
        with self.assertRaises(runner.TestError):
            runner.verify_results(report, client, receiver, 65, 3, 0xFFFFFE, 0x987654)

    def test_mismatched_native_provider_in_preflight_is_not_verification(self):
        for key, value in (("bdf", "0000:07:00.0"), ("device", "rxe_as02_ref"), ("port", 2),
                           ("link_layer", "InfiniBand"), ("gid_type", "IB/RoCE v1")):
            with self.subTest(key=key):
                report, client, receiver = observations(); report["native_receiver"][key] = value
                with self.assertRaises(runner.TestError):
                    runner.verify_results(report, client, receiver, 65, 3, 0xFFFFFE, 0x987654)

    def test_cli_refuses_without_authority_before_any_subprocess_or_mmio(self):
        for environment in ({}, {"AS02_ALLOW_NATIVE_FPGA_RDMA_TEST": "YES"}):
            with self.subTest(environment=environment), \
                    mock.patch.dict(runner.os.environ, environment, clear=True), \
                    mock.patch.object(sys, "argv", ["native_test.py"]), \
                    mock.patch.object(runner, "preflight") as inspect, \
                    mock.patch.object(runner.subprocess, "Popen") as start:
                with self.assertRaises(runner.TestError):
                    runner.main()
                inspect.assert_not_called()
                start.assert_not_called()

    def test_guard_failure_cannot_promote_worker_success(self):
        worker = dict(success=True, native_transfer_verified=True, receiver_memory_verified=True,
                      owned_children_stopped_without_force=True, thermal_guard_result_pending=True)
        for status in (1, 85, 90, 91, -15):
            with self.subTest(status=status), self.assertRaises(runner.TestError):
                runner.final_result(status, worker)
        result = runner.final_result(0, worker)
        self.assertTrue(result["hardware_rdma_verified"])
        self.assertFalse(result["thermal_guard_result_pending"])
        self.assertFalse(result["physical_gate_automatically_checked"])
        for key in ("success", "native_transfer_verified", "receiver_memory_verified", "owned_children_stopped_without_force"):
            bad = dict(worker, **{key: False})
            with self.subTest(key=key), self.assertRaises(runner.TestError):
                runner.final_result(0, bad)

    def test_owned_cleanup_only_and_forced_kill_is_not_quiescence(self):
        process = mock.Mock(); process.poll.return_value = None
        process.wait.side_effect = [subprocess.TimeoutExpired("owned child", 5), 0]
        self.assertFalse(runner.stop_owned(process))
        process.terminate.assert_called_once_with()
        process.kill.assert_called_once_with()
        process = mock.Mock(); process.poll.return_value = 0
        self.assertTrue(runner.stop_owned(process))
        process.terminate.assert_not_called()
        self.assertTrue(runner.stop_owned(None))

    def test_model_worker_pipeline_and_client_abort_before_peer_cleanup(self):
        for timeout_client in (False, True):
            with self.subTest(timeout_client=timeout_client), tempfile.TemporaryDirectory() as directory:
                log_dir = pathlib.Path(directory)
                report, client, receiver = observations()
                cleanup_order = []

                class Child:
                    def __init__(self, role):
                        self.role, self.finished, self.waits = role, False, 0

                    def poll(self):
                        return 0 if self.finished else None

                    def wait(self, timeout=None):
                        self.waits += 1
                        if self.role == "client" and timeout_client and self.waits == 1:
                            raise subprocess.TimeoutExpired("modeled client", timeout)
                        self.finished = True
                        return 0

                    def terminate(self):
                        cleanup_order.append(self.role)

                    def kill(self):
                        raise AssertionError("model child should not need SIGKILL")

                def start(command, stdout, **_):
                    role = "receiver" if "mlx5_0" in command else "client"
                    if role == "receiver":
                        stdout.write("\n".join(json.dumps(item) for item in receiver) + "\n")
                        stdout.flush()
                    else:
                        (log_dir / "client.json").write_text(json.dumps(client))
                    return Child(role)

                args = argparse.Namespace(message_bytes=65, count=3, psn=0xFFFFFE, peer_psn=0x987654)
                with mock.patch.object(runner, "preflight", return_value=report), \
                        mock.patch.object(runner, "source_identity", return_value={"scope": "unit-model-only"}), \
                        mock.patch.object(runner.subprocess, "run", return_value=mock.Mock(stdout="")), \
                        mock.patch.object(runner.subprocess, "Popen", side_effect=start):
                    code = runner.worker(args, log_dir)
                result = json.loads((log_dir / "worker.json").read_text())
                self.assertFalse(result["hardware_rdma_verified"])
                if timeout_client:
                    self.assertEqual(code, 1)
                    self.assertFalse(result["success"])
                    self.assertEqual(cleanup_order, ["client", "receiver"])
                else:
                    self.assertEqual(code, 0)
                    self.assertTrue(result["success"])
                    self.assertTrue(result["native_transfer_verified"])
                    self.assertEqual(cleanup_order, [])

    def test_existing_listener_and_preflight_failure_never_start_children(self):
        args = argparse.Namespace(message_bytes=65, count=3, psn=0xFFFFFE, peer_psn=0x987654)
        for bad_preflight in (False, True):
            with self.subTest(bad_preflight=bad_preflight), tempfile.TemporaryDirectory() as directory:
                with mock.patch.object(runner, "preflight", side_effect=runner.TestError("model refusal") if bad_preflight else None,
                                       return_value=observations()[0]), \
                        mock.patch.object(runner, "source_identity", return_value={}), \
                        mock.patch.object(runner.subprocess, "run", return_value=mock.Mock(stdout="LISTEN owned-by-other\n")), \
                        mock.patch.object(runner.subprocess, "Popen") as start:
                    self.assertEqual(runner.worker(args, pathlib.Path(directory)), 1)
                    start.assert_not_called()


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(RunnerTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if result.wasSuccessful() and result.testsRun == 12 and not result.skipped:
        sources = ("native_test.py", "native_preflight.py", "fpga_write_client.py")
        host_dir = pathlib.Path(runner.__file__).parent
        record = dict(evidence_type="native runner record/child-process model tests, not actual RDMA or temperature monitoring",
                      pass_test=True, tests_run=result.testsRun, failures=len(result.failures), errors=len(result.errors),
                      hardware_verified=False, hardware_accessed=False, traffic_generated=False,
                      registered_memory_tested=False, thermal_guard_executed=False,
                      source_sha256={name: hashlib.sha256((host_dir / name).read_bytes()).hexdigest() for name in sources},
                      test_sha256=hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),
                      fixture_dependency_sha256=hashlib.sha256(pathlib.Path(preflight_fixture.__code__.co_filename).read_bytes()).hexdigest())
        print(json.dumps(record, indent=2))
        if os.environ.get("AS02_NATIVE_RUNNER_REPORT"):
            pathlib.Path(os.environ["AS02_NATIVE_RUNNER_REPORT"]).write_text(json.dumps(record, indent=2) + "\n")
    sys.exit(not result.wasSuccessful())
