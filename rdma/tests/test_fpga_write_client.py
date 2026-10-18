# SPDX-License-Identifier: BSD-2-Clause-Views
"""Pure control-protocol/register-model tests; no FPGA, RNIC or MMIO access."""
import dataclasses
import hashlib
import json
import os
import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "host"))
import fpga_write_client as client

PEER_LINE = b"AS02RC1 abcdef 987654 fedcba98 fedcba9876543210 65 3 00000000000000000000ffffc6120a01\n"
PEER = PEER_LINE.ljust(256, b"\0")
CFG = client.Config("198.18.10.2", "198.18.10.1", 0x8AF3FBB97531, 0xB8830367C5D0,
                    size=65, count=3, local_psn=0xFFFFFE, device_timeout_cycles=10000, host_timeout_seconds=0.02)
IDLE = client.CORE_RESET | client.QUIET | client.HALT
COMPLETE = 7 << 8 | IDLE | client.DONE
FAILURE = 8 << 8 | IDLE | client.FAILED
ACTIVE = 5 << 8 | client.BUSY


class Registers:
    def __init__(self, mode="good"):
        self.mode = mode
        self.values = {client.ID: 0x524F4332, client.VERSION: 0x00010000, client.STATUS: IDLE,
                       0xC0: 11, 0xC4: 11}
        self.writes = []
        self.remaining = 3
        self.interrupted = False

    def check_identity(self):
        client.require(self.read32(client.ID) == 0x524F4332 and self.read32(client.VERSION) == 0x00010000,
                       "wrong identity")

    def read32(self, address):
        if address == client.STATUS and self.values[address] == ACTIVE:
            if self.mode == "interrupt" and not self.interrupted:
                self.interrupted = True
                raise KeyboardInterrupt()
            if self.mode not in ("timeout", "interrupt"):
                self.remaining -= 1
                if self.remaining == 0:
                    self.finish()
        if address == 0x68 and self.mode == "readback":
            return self.values.get(address, 0) ^ 1
        return self.values.get(address, 0)

    def write32(self, address, value):
        self.writes.append((address, value))
        if address == client.COMMAND:
            if value == 1:
                self.values[client.STATUS] = ACTIVE
            elif value == 4:
                self.values[client.STATUS] = FAILURE
                self.values[client.ERROR] = 5
            elif value == 2:
                self.values[client.STATUS] = IDLE
        else:
            self.values[address] = value

    def finish(self):
        self.values.update({client.STATUS: COMPLETE, client.ERROR: 0, client.ISSUED: 3,
                            client.ACKED: 3, client.TOTAL: 195, client.ELAPSED: 40000,
                            client.READ_COMMANDS: 3, client.READ_BYTES: 195,
                            0xC0: 14, 0xC4: 14, 0xA8: 3})
        if self.mode == "bad_count":
            self.values[client.ACKED] = 2
        if self.mode == "guard_fault":
            self.values[0xCC] = 1 << 16
        if self.mode == "tx_fault":
            self.values[0xAC] = 1
        if self.mode == "no_completions":
            self.values[0xC4] = 11
        if self.mode == "failed":
            self.values[client.STATUS] = FAILURE
            self.values[client.ERROR] = 3


class PeerSocket:
    def __init__(self, registers, packet=PEER, ready=b"R", verdict=b"P"):
        self.incoming = bytearray(packet + ready + verdict)
        self.sent = []
        self.registers = registers

    def recv(self, count):
        # Exercise every fixed-length read across short TCP receives.
        result = bytes(self.incoming[:min(count, 7)])
        del self.incoming[:len(result)]
        return result

    def sendall(self, data):
        if data == b"D":
            if not client.safe_terminal(self.registers.values[client.STATUS]):
                raise AssertionError("MR release/verify requested before real quiescence")
        self.sent.append(bytes(data))


class FpgaWriteClientTests(unittest.TestCase):
    def test_full_width_configuration_and_peer_verification(self):
        registers = Registers()
        peer = PeerSocket(registers)
        result = client.run_transfer(registers, CFG, peer)
        self.assertTrue(result["success"] and result["receiver_verified"])
        self.assertTrue(result["control_only_tcp"] and not result["software_roce_in_this_client"])
        self.assertFalse(result["remote_provider_identity_verified"])
        self.assertEqual(result["fpga_payload_source"], "bounded_local_pattern")
        self.assertEqual(result["total_bytes"], 195)
        self.assertEqual(peer.sent[1:], [b"R", b"D"])
        self.assertEqual(peer.sent[0], b"AS02RC1 2 fffffe 0 0 65 3 00000000000000000000ffffc6120a02\n".ljust(256, b"\0"))
        expected = (0xFBB97531, 0x8AF3, 0x0367C5D0, 0xB883, 0xC6120A02, 0xC6120A01,
                    2, 0xABCDEF, 0xFFFFFE, 0x987654, 0xFEDCBA98, 65,
                    0x76543210, 0xFEDCBA98, 195, 0, 3, 10000)
        self.assertEqual(registers.writes[:-1], [(0x40 + 4 * i, word) for i, word in enumerate(expected)])
        self.assertEqual(registers.writes[-1], (client.COMMAND, 1))

    def test_peer_record_rejections_before_any_mmio_write(self):
        replacements = [(b"abcdef", b"1000000"), (b"987654", b"1000000"),
                        (b"fedcba98 ", b"1fedcba98 "),
                        (b"fedcba9876543210", b"1fedcba9876543210"),
                        (b"fedcba9876543210", b"ffffffffffffff80"),
                        (b"65 3", b"64 3"), (b"65 3", b"65 2"),
                        (b"c6120a01", b"c6120a03"), (b"AS02RC1", b"AS02RC2"),
                        (b"abcdef", b"-1"), (b"65 3", b"65 +3")]
        for old, new in replacements:
            with self.subTest(new=new):
                packet = PEER_LINE.replace(old, new).ljust(256, b"\0")
                registers = Registers(); peer = PeerSocket(registers, packet)
                with self.assertRaises(client.ClientError):
                    client.run_transfer(registers, CFG, peer)
                self.assertEqual(registers.writes, [])
                self.assertEqual(peer.sent, [])
        for packet in (PEER[:-1], PEER[:-1] + b"X", b"X" * 256, PEER_LINE.rstrip(b"\n").ljust(256, b"\0")):
            with self.subTest(packet=packet[:16]):
                with self.assertRaises(client.ClientError):
                    client.decode_endpoint(packet, 65, 3, CFG.peer_ip)

    def test_busy_or_unknown_device_is_not_taken_over(self):
        for status, identity in ((ACTIVE, 0x524F4332), (IDLE, 0xDEADBEEF), (7 << 8 | client.DONE, 0x524F4332)):
            with self.subTest(status=status, identity=identity):
                registers = Registers(); registers.values[client.STATUS] = status; registers.values[client.ID] = identity
                with self.assertRaises(client.ClientError):
                    client.run_transfer(registers, CFG, PeerSocket(registers))
                self.assertEqual(registers.writes, [])

    def test_safe_terminal_is_cleared_without_resetting_nic(self):
        registers = Registers(); registers.values[client.STATUS] = COMPLETE
        result = client.run_transfer(registers, CFG, PeerSocket(registers))
        self.assertTrue(result["success"])
        self.assertEqual(registers.writes[0], (client.COMMAND, 2))

    def test_failures_never_signal_receiver_success(self):
        for mode in ("bad_count", "guard_fault", "tx_fault", "no_completions", "failed", "readback", "timeout", "interrupt"):
            with self.subTest(mode=mode):
                registers = Registers(mode); peer = PeerSocket(registers)
                with self.assertRaises(client.ClientError) as caught:
                    client.run_transfer(registers, CFG, peer)
                self.assertNotIn(b"D", peer.sent)
                self.assertFalse(caught.exception.evidence["success"])
                if mode in ("timeout", "interrupt"):
                    self.assertIn((client.COMMAND, 4), registers.writes)
                    self.assertTrue(caught.exception.evidence["tx_quiescence_verified"])
                if mode == "readback":
                    self.assertNotIn((client.COMMAND, 1), registers.writes)

    def test_failed_peer_memory_verification_is_not_success(self):
        registers = Registers(); peer = PeerSocket(registers, verdict=b"F")
        with self.assertRaises(client.ClientError) as caught:
            client.run_transfer(registers, CFG, peer)
        self.assertFalse(caught.exception.evidence["receiver_verified"])
        self.assertTrue(caught.exception.evidence["tx_quiescence_verified"])
        self.assertEqual(peer.sent[-1], b"D")

    def test_peer_not_ready_prevents_start(self):
        registers = Registers(); peer = PeerSocket(registers, ready=b"F")
        with self.assertRaises(client.ClientError):
            client.run_transfer(registers, CFG, peer)
        self.assertEqual(registers.writes, [])

    def test_config_bounds(self):
        for changes in (dict(size=0), dict(size=4097), dict(count=0), dict(count=65537),
                        dict(size=4096, count=65536), dict(local_qpn=1), dict(local_qpn=8),
                        dict(local_psn=0x1000000), dict(local_mac=0x010000000001),
                        dict(local_ip=CFG.peer_ip), dict(device_timeout_cycles=0)):
            with self.subTest(changes=changes), self.assertRaises(client.ClientError):
                dataclasses.replace(CFG, **changes).validate()
        dataclasses.replace(CFG, size=4096, count=16384).validate()

    def test_mmio_requires_opt_in_and_exact_bdf_before_filesystem_access(self):
        with mock.patch.dict("os.environ", {}, clear=True), mock.patch.object(pathlib.Path, "read_text") as read:
            with self.assertRaises(client.ClientError):
                client.PciBar2(client.AUDITED_BDF)
            read.assert_not_called()
        with mock.patch.dict("os.environ", {"AS02_ALLOW_FPGA_RDMA": "YES"}), mock.patch.object(pathlib.Path, "read_text") as read:
            with self.assertRaises(client.ClientError):
                client.PciBar2("0000:07:00.0")
            read.assert_not_called()

    def test_high_low_counter_rollover(self):
        values = iter((0, 0xFFFFFFFF, 1, 1, 4, 1))
        registers = mock.Mock()
        registers.read32.side_effect = lambda _address: next(values)
        self.assertEqual(client.read64(registers, client.ELAPSED), (1 << 32) | 4)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(FpgaWriteClientTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if result.wasSuccessful() and result.testsRun == 10 and not result.skipped:
        record = dict(evidence_type="host control protocol/register-model unit tests, not RTL or hardware",
                      pass_test=True, tests_run=result.testsRun, failures=len(result.failures), errors=len(result.errors),
                      hardware_verified=False, hardware_accessed=False, registered_memory_tested=False,
                      source_sha256={"fpga_write_client.py": hashlib.sha256(pathlib.Path(client.__file__).read_bytes()).hexdigest()},
                      test_sha256=hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest())
        print(json.dumps(record, indent=2))
        if os.environ.get("AS02_FPGA_CLIENT_REPORT"):
            pathlib.Path(os.environ["AS02_FPGA_CLIENT_REPORT"]).write_text(json.dumps(record, indent=2) + "\n")
    sys.exit(not result.wasSuccessful())
