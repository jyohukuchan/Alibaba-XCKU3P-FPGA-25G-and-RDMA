# SPDX-License-Identifier: BSD-2-Clause-Views
"""Pure register/socket models; never opens hardware or changes a network."""
import dataclasses
import pathlib
import sys
import time
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'host'))
import fpga_write_client as client
import mac_rx_fault as fault
from test_fpga_write_client import Registers, PeerSocket, PEER_LINE, CFG, ACTIVE, IDLE, COMPLETE, FAILURE


def layout():
    values = {0: 0xFFFFFFFF, 4: 0x100, 8: 0x100,
              0x100: 0xC000, 0x104: 0x100, 0x108: 0,
              0x10C: 0x1000, 0x110: 2, 0x114: 0x1000, 0x118: 0x80,
              0x2080: 0xC001, 0x2084: 0x400, 0x2088: 0x200, 0x2090: 1,
              0x2200: 0xC002, 0x2204: 0x200, 0x2208: 0, 0x220C: 0x300,
              0x2300: 0xC003, 0x2304: 0x300, 0x2308: 0}
    return values


class Rx:
    layout = dict(interface=1, port=0, rx_control_address=0x2314)
    def __init__(self, value=0x101):
        self.value, self.writes = value, []
    def read(self):
        return self.value | (1 << 16)
    def write(self, value):
        if value & ~fault.RX_WRITABLE:
            raise AssertionError('status/other bits must never be written')
        self.writes.append(value)
        self.value = value


class SingleWriteRegisters(Registers):
    def read32(self, address):
        if address == client.STATUS and self.values[address] == ACTIVE:
            self.values.update({client.ISSUED: 1, client.ACKED: 0,
                                client.READ_COMMANDS: 2, client.READ_BYTES: 130, 0xC0: 13, 0xC4: 13})
        return super().read32(address)
    def finish(self):
        super().finish()
        self.values.update({client.ISSUED: 1, client.ACKED: 1, client.TOTAL: 65,
                            client.READ_COMMANDS: 3, client.READ_BYTES: 195, 0xC0: 14, 0xC4: 14})
        if self.mode == 'watchdog':
            self.values.update({client.STATUS: FAILURE, client.ERROR: 2, client.ACKED: 0,
                                client.ELAPSED: fault.WATCHDOG_CYCLES + 100})


class RestoreCheckingPeer(PeerSocket):
    def __init__(self, registers, rx):
        super().__init__(registers, packet=PEER_LINE.replace(b'65 3', b'65 1').ljust(256, b'\0'))
        self.rx = rx
    def sendall(self, data):
        if data == b'D':
            if self.rx.value != 0x101:
                raise AssertionError('RX not restored before control verification')
        super().sendall(data)


class MacRxFaultTests(unittest.TestCase):
    def test_discovers_child_relative_not_guessed_port_header_offset(self):
        values = layout()
        result = fault.discover_rx_control(lambda a: values.get(a, 0), 0x4000)
        self.assertEqual(result['interface'], 1)
        self.assertEqual(result['rx_control_address'], 0x2314)
        self.assertNotEqual(result['rx_control_address'], 0x2200 + 0x14)

    def test_bad_layouts_refused_without_writes(self):
        for address, value in [(8, 0x4000), (8, 3), (0x108, 0x100), (0x110, 1),
                               (0x114, 0), (0x114, 0x3000), (0x118, 0x1000),
                               (0x2090, 2), (0x2084, 0x300), (0x2204, 0x100),
                               (0x220C, 0x1000), (0x2304, 0x200), (0x2308, 0x300)]:
            with self.subTest(address=address, value=value):
                values = layout(); values[address] = value
                with self.assertRaises(client.ClientError):
                    fault.discover_rx_control(lambda a: values.get(a, 0), 0x4000)

    def test_restore_requires_actual_reread_and_completed_retransmit(self):
        registers, rx = Registers('timeout'), Rx()
        gate = fault.FaultRegisters(registers, rx, 'retry', 65)
        try:
            gate.write32(client.COMMAND, 1)
            self.assertEqual(rx.value, 0x100)
            registers.values.update({client.ISSUED: 1, client.ACKED: 0, client.READ_COMMANDS: 2,
                                     client.READ_BYTES: 130, 0xC0: 13, 0xC4: 12})
            gate.read32(client.STATUS)
            self.assertTrue(gate.dropping)  # Missing completion cannot pass.
            registers.values[0xC4] = 13
            gate.read32(client.STATUS)
            self.assertFalse(gate.dropping)
            self.assertEqual(rx.writes, [0x100, 0x101])
            self.assertTrue(gate.evidence['retry_observed_before_restore'])
        finally:
            gate.close()

    def test_good_retry_and_expected_watchdog_keep_transport_semantics_distinct(self):
        for mode in ['retry', 'watchdog']:
            with self.subTest(mode=mode):
                registers, rx = SingleWriteRegisters(mode), Rx()
                config = dataclasses.replace(CFG, count=1, device_timeout_cycles=fault.WATCHDOG_CYCLES,
                                             host_timeout_seconds=1)
                peer = RestoreCheckingPeer(registers, rx)
                result = fault.run_fault_transfer(registers, rx, config, peer, mode)
                self.assertTrue(result['success'] and result['receiver_verified'])
                self.assertEqual(result['transport_success'], mode == 'retry')
                self.assertEqual(result['acknowledged'], 1 if mode == 'retry' else 0)
                self.assertEqual(rx.writes, [0x100, 0x101])
                self.assertEqual(peer.sent[-1], b'D')
                if mode == 'watchdog':
                    self.assertEqual(result['error_code'], 2)
                    self.assertTrue(result['expected_timeout_verified'])

    def test_unrelated_failure_is_not_expected_watchdog(self):
        registers, rx = Registers('failed'), Rx()
        config = dataclasses.replace(CFG, count=1, device_timeout_cycles=fault.WATCHDOG_CYCLES,
                                     host_timeout_seconds=1)
        peer = RestoreCheckingPeer(registers, rx)
        with self.assertRaises(client.ClientError):
            fault.run_fault_transfer(registers, rx, config, peer, 'watchdog')
        self.assertEqual(rx.value, 0x101)
        self.assertNotIn(b'D', peer.sent)

    def test_interruption_restores_rx_before_owned_abort_and_peer_teardown(self):
        registers, rx = SingleWriteRegisters('interrupt'), Rx()
        config = dataclasses.replace(CFG, count=1, device_timeout_cycles=fault.WATCHDOG_CYCLES,
                                     host_timeout_seconds=1)
        peer = RestoreCheckingPeer(registers, rx)
        original = registers.write32
        def ordered_abort(address, value):
            if address == client.COMMAND and value == 4:
                self.assertEqual(rx.value, 0x101)
            original(address, value)
        registers.write32 = ordered_abort
        with self.assertRaises(client.ClientError):
            fault.run_fault_transfer(registers, rx, config, peer, 'retry')
        self.assertEqual(rx.value, 0x101)
        self.assertIn((client.COMMAND, 4), registers.writes)
        self.assertNotIn(b'D', peer.sent)

    def test_disable_readback_failure_restores_without_start(self):
        registers, rx = Registers(), Rx()
        gate = fault.FaultRegisters(registers, rx, 'retry', 65)
        write = rx.write
        def failed_disable(value):
            write(value)
            if value == 0x100:
                raise client.ClientError('injected readback failure')
        rx.write = failed_disable
        try:
            with self.assertRaises(client.ClientError):
                gate.write32(client.COMMAND, 1)
        finally:
            gate.close()
        self.assertNotIn((client.COMMAND, 1), registers.writes)
        self.assertEqual(rx.value, 0x101)

    def test_abort_restores_even_if_abort_write_fails(self):
        registers, rx = Registers('timeout'), Rx()
        gate = fault.FaultRegisters(registers, rx, 'watchdog', 65)
        try:
            gate.write32(client.COMMAND, 1)
            original = registers.write32
            def abort_failed(address, value):
                self.assertEqual(rx.value, 0x101)
                raise client.ClientError('abort readback failure')
            registers.write32 = abort_failed
            with self.assertRaises(client.ClientError):
                gate.write32(client.COMMAND, 4)
            registers.write32 = original
        finally:
            gate.close()
        self.assertEqual(rx.value, 0x101)

    def test_independent_restoration_watchdog_marks_case_failed(self):
        registers, rx = Registers('timeout'), Rx()
        gate = fault.FaultRegisters(registers, rx, 'watchdog', 65)
        try:
            with mock.patch.object(fault, 'MAX_RX_OFF_SECONDS', 0.005):
                gate.write32(client.COMMAND, 1)
            deadline = time.monotonic() + 1
            while gate.dropping and time.monotonic() < deadline:
                time.sleep(0.001)
            self.assertFalse(gate.dropping)
            self.assertEqual(rx.value, 0x101)
            self.assertTrue(gate.evidence['deadline_expired'])
            with self.assertRaises(client.ClientError):
                gate.read32(client.STATUS)
        finally:
            gate.close()

    def test_disabled_receiver_and_wrong_live_opt_in_refused(self):
        with self.assertRaises(client.ClientError):
            fault.FaultRegisters(Registers(), Rx(0), 'retry', 65)
        with mock.patch.dict('os.environ', {}, clear=True):
            with self.assertRaises(client.ClientError):
                fault.PciRxControl(client.AUDITED_BDF, Registers())


if __name__ == '__main__':
    unittest.main()
