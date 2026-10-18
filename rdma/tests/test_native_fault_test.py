# SPDX-License-Identifier: BSD-2-Clause-Views
"""Fault-runner verdict tests against modeled records, never hardware."""
import copy
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'host'))
import fpga_write_client as client
import mac_rx_fault as fault
import native_fault_test as runner
from test_native_test import observations


def fixture(mode='retry'):
    pre, result, peer = observations(size=65, count=1, psn=0x234567)
    sample = dict(status=5 << 8 | client.BUSY, error_code=0, issued=1, acknowledged=0,
                  read_commands=2, read_bytes=130, elapsed_cycles=260000,
                  diagnostics={'0xc0': 102, '0xc4': 102, '0xac': 0, '0xb0': 0, '0xcc': 0})
    f = dict(mode=mode, original_rx_writable=1, restored_rx_writable=1,
             rx_restored=True, deadline_expired=False, hls_rto_modified=False,
             rx_off_seconds=0.003, retry_observed_before_restore=True,
             baseline_tx=100, baseline_cpl=100, before_restore=sample,
             layout=dict(interface=1, port=0, port_control=0x840010, rx_control_address=0x840024))
    result.update(fault=f, transport_success=True)
    if mode == 'watchdog':
        sample.update(status=8 << 8 | client.FAILED | client.CORE_RESET | client.HALT | client.QUIET,
                      error_code=2, elapsed_cycles=fault.WATCHDOG_CYCLES + 500)
        result.update(copy.deepcopy(sample), transport_success=False, expected_timeout_verified=True)
    return pre, result, peer


class NativeFaultTests(unittest.TestCase):
    def test_valid_faults_keep_timeout_separate_from_write_completion(self):
        for mode in ['retry', 'watchdog']:
            with self.subTest(mode=mode):
                verdict = runner.verify_results(*fixture(mode), mode, 0x234567, 0x987654)
                self.assertTrue(verdict['fault_verification_passed'])
                self.assertTrue(verdict['receiver_memory_verified'])
                self.assertEqual(verdict['native_write_completed'], mode == 'retry')
                self.assertEqual(verdict['native_transfer_verified'], mode == 'retry')
                self.assertNotIn('hardware_fault_injection_verified', verdict)

    def test_lack_of_actual_retry_or_restore_is_rejected(self):
        for key, value in [('rx_restored', False), ('deadline_expired', True), ('hls_rto_modified', True),
                           ('original_rx_writable', 0), ('restored_rx_writable', 0x101),
                           ('rx_off_seconds', 0.2), ('rx_off_seconds', 0.0001),
                           ('retry_observed_before_restore', False), ('mode', 'other')]:
            with self.subTest(key=key, value=value):
                pre, result, peer = fixture(); result['fault'][key] = value
                with self.assertRaises(RuntimeError):
                    runner.verify_results(pre, result, peer, 'retry', 0x234567, 0x987654)
        for key, value in [('read_commands', 1), ('read_bytes', 65), ('issued', 2), ('acknowledged', 1),
                           ('elapsed_cycles', 999)]:
            with self.subTest(key=key):
                pre, result, peer = fixture(); result['fault']['before_restore'][key] = value
                with self.assertRaises(RuntimeError):
                    runner.verify_results(pre, result, peer, 'retry', 0x234567, 0x987654)
        for key in ['0xc0', '0xc4']:
            pre, result, peer = fixture(); result['fault']['before_restore']['diagnostics'][key] = 101
            with self.assertRaises(RuntimeError):
                runner.verify_results(pre, result, peer, 'retry', 0x234567, 0x987654)

    def test_wrong_target_and_watchdog_failure_semantics_rejected(self):
        for key, value in [('interface', 0), ('port', 1), ('rx_control_address', 0x840014)]:
            pre, result, peer = fixture(); result['fault']['layout'][key] = value
            with self.assertRaises(RuntimeError):
                runner.verify_results(pre, result, peer, 'retry', 0x234567, 0x987654)
        for key, value in [('transport_success', True), ('expected_timeout_verified', False),
                           ('error_code', 5), ('status', 8 << 8 | client.FAILED), ('acknowledged', 1),
                           ('elapsed_cycles', 100), ('receiver_verified', False), ('hardware_access', False),
                           ('control_only_tcp', False), ('software_roce_in_this_client', True)]:
            with self.subTest(key=key):
                pre, result, peer = fixture('watchdog'); result[key] = value
                with self.assertRaises(RuntimeError):
                    runner.verify_results(pre, result, peer, 'watchdog', 0x234567, 0x987654)

    def test_receiver_identity_memory_and_psn_rejections(self):
        for index, key, value in [(1, 'device', 'rxe0'), (1, 'path_mtu', 1024), (1, 'psn', 9),
                                   (1, 'gid', '::ffff:198.18.10.2'), (2, 'qpn', 8), (2, 'psn', 1),
                                   (3, 'mismatches', 1), (3, 'bytes', 64), (3, 'pass', False)]:
            with self.subTest(key=key):
                pre, result, peer = fixture('watchdog'); peer[index][key] = value
                with self.assertRaises(RuntimeError):
                    runner.verify_results(pre, result, peer, 'watchdog', 0x234567, 0x987654)

    def test_final_hardware_claim_requires_guard_and_clean_children(self):
        for mode in ['retry', 'watchdog']:
            verdict = runner.verify_results(*fixture(mode), mode, 0x234567, 0x987654)
            worker = dict(verdict, success=True, owned_children_stopped_without_force=True)
            result = runner.final_result(0, worker)
            self.assertTrue(result['hardware_fault_injection_verified'])
            self.assertEqual(result['hardware_rdma_verified'], mode == 'retry')
            for key in ['success', 'fault_verification_passed', 'receiver_memory_verified',
                        'owned_children_stopped_without_force']:
                broken = dict(worker); broken[key] = False
                with self.assertRaises(RuntimeError):
                    runner.final_result(0, broken)
            with self.assertRaises(RuntimeError):
                runner.final_result(1, worker)

    def test_commands_retain_native_bdf_namespace_and_new_explicit_fault_opt_in(self):
        pre, _, _ = fixture()
        peer, controller = runner.commands(pre, 'retry', 0x234567, 0x987654, pathlib.Path('/fixture'))
        self.assertIn('mlx5_0', peer)
        self.assertIn('AS02_ALLOW_MAC_RX_FAULT=YES', controller)
        self.assertIn(str(runner.PROJECT / 'rdma/host/mac_rx_fault.py'), controller)
        self.assertEqual(controller[-2:], ['--fault-mode', 'retry'])
        self.assertEqual(controller[controller.index('--bdf') + 1], client.AUDITED_BDF)
        for text in ['rxe', 'enp7s0', '192.168.0.148', 'openFPGALoader', 'mlxconfig']:
            self.assertNotIn(text, ' '.join(peer + controller))


if __name__ == '__main__':
    unittest.main()
