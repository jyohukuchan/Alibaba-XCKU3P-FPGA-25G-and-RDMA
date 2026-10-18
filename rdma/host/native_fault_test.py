#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""One finite native ACK-loss case, with read-only thermal supervision.

retry: restore dedicated MAC RX after an actual completed retransmission.
watchdog: keep ACK RX blocked until a quiescent 10ms controller timeout,
then restore RX and verify the receiver's payload. This is an expected
transport FAILURE, never reported as an acknowledged WRITE success.
"""
import argparse
import datetime
import hashlib
import ipaddress
import json
import os
import pathlib
import signal
import subprocess
import sys
import tempfile
import time

import fpga_write_client as client
import mac_rx_fault as fault
import native_test as native

PROJECT = native.PROJECT


def source_identity():
    result = native.source_identity()
    for name in ['rdma/host/mac_rx_fault.py', 'rdma/host/native_fault_test.py',
                 'rdma/tests/test_mac_rx_fault.py', 'rdma/tests/test_native_fault_test.py']:
        result[name] = hashlib.sha256((PROJECT / name).read_bytes()).hexdigest()
    return result


def commands(report, mode, psn, peer_psn, log_dir):
    server, controller = native.commands(report, 65, 1, psn, peer_psn, log_dir)
    controller[controller.index(str(PROJECT / 'rdma/host/fpga_write_client.py'))] = str(PROJECT / 'rdma/host/mac_rx_fault.py')
    controller.insert(controller.index('env') + 1, 'AS02_ALLOW_MAC_RX_FAULT=YES')
    controller.extend(['--fault-mode', mode])
    return server, controller


def verify_results(report, result, receiver, mode, psn, peer_psn):
    native.require(mode in ('retry', 'watchdog'), 'unknown fault mode')
    f = result.get('fault', {})
    native.require(result.get('success') is True and f.get('mode') == mode and
                   f.get('rx_restored') is True and f.get('deadline_expired') is False and
                   f.get('hls_rto_modified') is False and f.get('retry_observed_before_restore') is True,
                   'fault/restoration/retry proof is incomplete')
    original = f.get('original_rx_writable', 0)
    native.require(original & 1 and not original & ~fault.RX_WRITABLE and
                   f.get('restored_rx_writable') == original and
                   0.001 <= f.get('rx_off_seconds', 0) <= fault.MAX_RX_OFF_SECONDS,
                   'RX writable settings or bounded fault interval differ')
    layout = f.get('layout', {})
    native.require(layout.get('interface') == 1 and layout.get('port') == 0 and
                   layout.get('rx_control_address') == layout.get('port_control', -100) + 0x14,
                   'fault target was not the discovered dedicated interface1/port0 RX control')
    before = f['before_restore']; diag = before['diagnostics']
    native.require(before['issued'] == 1 and before['acknowledged'] == 0 and
                   before['read_commands'] >= 2 and before['read_bytes'] >= 130 and
                   before['elapsed_cycles'] >= client.CLOCK_HZ // 1000 and
                   (diag['0xc0'] - f['baseline_tx']) & 0xFFFFFFFF >= 2 and
                   (diag['0xc4'] - f['baseline_cpl']) & 0xFFFFFFFF >= 2,
                   'no completed retransmission/reread with zero received ACKs before restoring RX')
    if mode == 'retry':
        native.require(result.get('transport_success') is True, 'retry did not finish as an acknowledged WRITE')
        verified = native.verify_results(report, result, receiver, 65, 1, psn, peer_psn)
    else:
        rdma = report['native_receiver']
        native.require(report['success'] is True and report['application']['quiescent'] is True and
                       rdma['device'] == 'mlx5_0' and rdma['bdf'] == native.ROLES['peer']['bdf'] and
                       rdma['port'] == 1 and rdma['link_layer'] == 'Ethernet' and rdma['gid_type'] == 'RoCE v2',
                       'receiver is not the audited native CX455A')
        native.require(result.get('transport_success') is False and result.get('expected_timeout_verified') is True and
                       result.get('receiver_verified') is True and result.get('tx_quiescence_verified') is True and
                       result.get('hardware_access') is True and result['bdf'] == client.AUDITED_BDF and
                       result.get('control_only_tcp') is True and result.get('software_roce_in_this_client') is False and
                       result.get('fpga_payload_source') == 'bounded_local_pattern' and
                       result.get('message_bytes') == 65 and result.get('messages') == 1 and
                       result.get('issued') == 1 and result.get('acknowledged') == 0 and result.get('total_bytes') == 65,
                       'expected-timeout case has invalid control/transfer semantics')
        for sample in [before, result]:
            native.require(client.safe_terminal(sample['status']) and client.state(sample['status']) == 8 and
                           sample['status'] & client.FAILED and sample['error_code'] == 2 and
                           sample['elapsed_cycles'] >= fault.WATCHDOG_CYCLES and
                           sample['diagnostics']['0xac'] == 0 and sample['diagnostics']['0xb0'] == 0 and
                           sample['diagnostics']['0xcc'] == 0, 'not an otherwise clean, quiescent controller timeout')
        listening = native.one_event(receiver, 'listening')
        local = native.one_event(receiver, 'local_endpoint'); remote = native.one_event(receiver, 'remote_endpoint')
        memory = native.one_event(receiver, 'memory_verification')
        native.require(listening['ip'] == native.ROLES['peer']['ip'] and listening['port'] == native.CONTROL_PORT and
                       local['device'] == 'mlx5_0' and local['gid_index'] == rdma['gid_index'] and
                       ipaddress.IPv6Address(local['gid']) == ipaddress.IPv6Address(rdma['gid']) and
                       local['qpn'] == result['peer_qpn'] and local['psn'] == result['peer_psn'] == peer_psn and
                       local['message_bytes'] == 65 and local['messages'] == 1 and local['path_mtu'] == 4096 and
                       remote['qpn'] == result['local_qpn'] == 2 and remote['psn'] == result['local_psn'] == psn and
                       remote['message_bytes'] == 65 and remote['messages'] == 1 and
                       ipaddress.IPv6Address(remote['gid']) == ipaddress.IPv6Address('::ffff:' + native.ROLES['fpga']['ip']) and
                       memory.get('pass') is True and memory['bytes'] == 65 and memory['mismatches'] == 0,
                       'native QP/PSN/GID or all-byte receiver payload verification differs')
        verified = dict(receiver_memory_verified=True, verified_bytes=65, native_transfer_verified=False,
                        expected_timeout_verified=True, native_receiver=rdma)
    return dict(verified, fault= f, retry_observed=True, native_write_completed=mode == 'retry',
                fault_verification_passed=True)


def worker(args, log_dir):
    peer = controller = None
    result = dict(event='native_fault_worker', success=False, hardware_fault_injection_verified=False,
                  mode=args.mode, software_rxe_created=False, fpga_programmed=False, flash_modified=False,
                  fan_settings_changed=False, temporary_mac_rx_change=True)
    try:
        report = native.preflight()
        native.dump(log_dir / 'preflight.json', report)
        result['source_sha256'] = source_identity()
        listening = subprocess.run(['sudo', '-n', 'ip', 'netns', 'exec', native.ROLES['peer']['namespace'],
                                    'ss', '-H', '-ltn', 'sport = :' + str(native.CONTROL_PORT)],
                                   capture_output=True, text=True, check=True, timeout=5).stdout
        native.require(not listening.strip(), 'another process already owns the control port')
        server_cmd, client_cmd = commands(report, args.mode, args.psn, args.peer_psn, log_dir)
        native.dump(log_dir / 'commands.json', dict(receiver=server_cmd, client=client_cmd))
        with (log_dir / 'receiver.jsonl').open('x') as out, (log_dir / 'client.log').open('x') as err:
            peer = subprocess.Popen(server_cmd, stdout=out, stderr=subprocess.STDOUT)
            deadline = time.monotonic() + 5
            while not any(e.get('event') == 'listening' for e in native.events(log_dir / 'receiver.jsonl')):
                native.require(peer.poll() is None and time.monotonic() < deadline, 'receiver startup failed/timed out')
                time.sleep(0.02)
            controller = subprocess.Popen(client_cmd, stdout=err, stderr=subprocess.STDOUT)
            native.require(controller.wait(timeout=20) == 0, 'fault controller failed; inspect client.json/log')
            native.require(peer.wait(timeout=5) == 0, 'native peer failed; inspect receiver.jsonl')
        result.update(verify_results(report, json.loads((log_dir / 'client.json').read_text()),
                                     native.events(log_dir / 'receiver.jsonl'), args.mode, args.psn, args.peer_psn),
                      success=True)
    except BaseException as error:
        result.update(success=False, error=str(error) or type(error).__name__)
    finally:
        client_clean = native.stop_owned(controller)
        peer_clean = native.stop_owned(peer)
        result['owned_children_stopped_without_force'] = client_clean and peer_clean
        if not client_clean or not peer_clean:
            result.update(success=False, error='forced child cleanup; cannot prove safe fault recovery')
        native.dump(log_dir / 'worker.json', result)
    return 0 if result['success'] else 1


def final_result(guard_status, result):
    native.require(guard_status == 0 and result.get('success') is True and
                   result.get('fault_verification_passed') is True and result.get('receiver_memory_verified') is True and
                   result.get('owned_children_stopped_without_force') is True,
                   'fault worker or thermal supervision did not pass')
    return dict(result, event='native_fault_test', hardware_fault_injection_verified=True,
                hardware_rdma_verified=result['native_write_completed'], thermal_guard_exit_status=0,
                physical_review_operator_attested=True, physical_gate_automatically_checked=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('retry', 'watchdog'), required=True)
    parser.add_argument('--psn', type=lambda v: int(v, 0), required=True)
    parser.add_argument('--peer-psn', type=lambda v: int(v, 0), default=0x987654)
    parser.add_argument('--under-temperature-guard', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--log-dir', type=pathlib.Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    native.validate_request(65, 1, args.psn, args.peer_psn)
    guard = native.require_authorization(os.environ)
    native.require(os.environ.get('AS02_ALLOW_MAC_RX_FAULT') == 'YES', 'explicit MAC RX fault opt-in required')
    def interrupted(signum, _frame):
        raise KeyboardInterrupt(f'signal {signum}')
    signal.signal(signal.SIGTERM, interrupted); signal.signal(signal.SIGINT, interrupted)
    if args.under_temperature_guard:
        native.require(args.log_dir is not None and args.log_dir.is_dir() and
                       args.log_dir.resolve().parent == (PROJECT / 'rdma/logs').resolve(), 'invalid owned log directory')
        return worker(args, args.log_dir)
    native.require(args.log_dir is None, 'supervisor exclusively creates its log directory')
    native.preflight()
    log_dir = pathlib.Path(tempfile.mkdtemp(prefix='native-fault-', dir=PROJECT / 'rdma/logs'))
    result = dict(event='native_fault_test', success=False, hardware_fault_injection_verified=False,
                  mode=args.mode, observed_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  log_directory=str(log_dir), temperature_guard_sha256=hashlib.sha256(guard.read_bytes()).hexdigest())
    process = None
    try:
        command = ['bash', str(guard), sys.executable, str(pathlib.Path(__file__).resolve()),
                   '--under-temperature-guard', '--log-dir', str(log_dir), '--mode', args.mode,
                   '--psn', str(args.psn), '--peer-psn', str(args.peer_psn)]
        print('Finite native fault logs: ' + str(log_dir), flush=True)
        with (log_dir / 'temperature-guard.log').open('x') as out:
            process = subprocess.Popen(command, stdout=out, stderr=subprocess.STDOUT)
            guard_status = process.wait()
        result['thermal_guard_exit_status'] = guard_status
        result.update(final_result(guard_status, json.loads((log_dir / 'worker.json').read_text())))
    except BaseException as error:
        result.update(success=False, hardware_fault_injection_verified=False, error=str(error) or type(error).__name__)
    finally:
        if not native.stop_owned(process):
            result.update(success=False, hardware_fault_injection_verified=False, error='forced thermal supervisor cleanup')
        native.dump(log_dir / 'result.json', result)
    print(json.dumps(result, indent=2))
    return 0 if result['success'] else 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (RuntimeError, OSError, ValueError, subprocess.SubprocessError) as error:
        print('refused/failed: ' + str(error), file=sys.stderr)
        sys.exit(1)
