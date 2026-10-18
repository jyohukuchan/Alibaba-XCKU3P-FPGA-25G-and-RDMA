#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Finite ACK-loss experiment on audited FPGA interface1/port0 only.

Keeps the accepted bitstream and its real 1ms HLS retransmission timer intact.
Only RX_CTRL writable bits are touched, after TCP peer readiness, with
readback-verified restoration before peer verification or owned abort.
"""
import argparse
import json
import mmap
import os
import pathlib
import signal
import socket
import struct
import sys
import threading
import time

import fpga_write_client as client

RX_WRITABLE = 0x101
MAX_RX_OFF_SECONDS = 0.1
WATCHDOG_CYCLES = client.CLOCK_HZ // 100  # 10ms; HLS RTO stays 1ms.


def blocks(read, base, offset, size):
    """Corundum NEXT pointers are relative to the containing region base."""
    seen, result = set(), []
    while True:
        client.require(offset % 4 == 0 and 0 <= offset <= size - 12 and
                       offset not in seen and len(seen) < 64, "invalid/looping register-block list")
        seen.add(offset)
        address = base + offset
        result.append((read(address), read(address + 4), address))
        offset = read(address + 8)
        if offset == 0:
            return result


def unique(entries, kind, version):
    matches = [address for typ, ver, address in entries if typ == kind and ver == version]
    client.require(len(matches) == 1 and sum(typ == kind for typ, _, _ in entries) == 1,
                   f"missing/ambiguous register block {kind:x}/{version:x}")
    return matches[0]


def discover_rx_control(read, size):
    root = unique(blocks(read, 0, 0, size), 0xC000, 0x100)
    client.require(root <= size - 28, "truncated interface-list header")
    offset, count, stride, csr = [read(root + n) for n in (12, 16, 20, 24)]
    client.require(count == 2 and stride >= 4096 and stride % 4096 == 0 and
                   offset % 4096 == 0 and offset + count * stride <= size and
                   0 <= csr <= stride - 12, "unexpected audited two-interface layout")
    base = offset + stride  # Interface1, never a caller-selected port.
    entries = blocks(read, base, csr, stride)
    interface = unique(entries, 0xC001, 0x400)
    client.require(interface <= base + stride - 20, "truncated interface control header")
    client.require(read(interface + 16) == 1, "expected exactly one port on interface1")
    port = unique(entries, 0xC002, 0x200)
    client.require(port <= base + stride - 16, "truncated port header")
    child = read(port + 12)
    control = unique(blocks(read, base, child, stride), 0xC003, 0x300)
    address = control + 0x14  # Child-relative, NOT port-header-relative.
    client.require(base <= address <= base + stride - 4, "RX control outside interface1")
    return dict(interface=1, port=0, interface_base=base, interface_stride=stride,
                port_header=port, port_control=control, rx_control_address=address)


class PciRxControl:
    """Requires the already locked/identity-checked ROC2 BAR2 owner."""
    def __init__(self, bdf, registers):
        client.require(os.environ.get("AS02_ALLOW_MAC_RX_FAULT") == "YES", "explicit MAC RX fault opt-in required")
        client.require(bdf == client.AUDITED_BDF, "only the audited dedicated FPGA is allowed")
        registers.check_identity()
        client.require(client.safe_terminal(registers.read32(client.STATUS)), "require initial FPGA TX quiescence")
        self.fd = self.mapping = None
        self.lock = threading.RLock()
        path = pathlib.Path('/sys/bus/pci/devices') / bdf / 'resource0'
        try:
            fd = os.open(path, os.O_RDONLY | os.O_SYNC | os.O_CLOEXEC)
            try:
                size = os.fstat(fd).st_size
                client.require(4096 <= size <= 64 * 1024 * 1024, "unexpected BAR0 extent")
                with mmap.mmap(fd, size, flags=mmap.MAP_SHARED, prot=mmap.PROT_READ) as view:
                    def read(address):
                        client.require(0 <= address <= size - 4 and address % 4 == 0, "invalid discovery read")
                        return struct.unpack_from('<I', view, address)[0]
                    self.layout = discover_rx_control(read, size)
            finally:
                os.close(fd)
            address = self.layout['rx_control_address']
            self.fd = os.open(path, os.O_RDWR | os.O_SYNC | os.O_CLOEXEC)
            self.mapping = mmap.mmap(self.fd, 4096, flags=mmap.MAP_SHARED,
                                     prot=mmap.PROT_READ | mmap.PROT_WRITE, offset=address & ~4095)
            self.word_offset = address & 4095
            self.initial_raw = self.read()
            client.require(self.initial_raw & 1 and not self.initial_raw & (1 << 17),
                           "dedicated MAC RX must initially be enabled and out of reset")
        except BaseException:
            self.close()
            raise

    def read(self):
        with self.lock:
            return struct.unpack_from('<I', self.mapping, self.word_offset)[0]

    def write(self, writable):
        client.require(writable & ~RX_WRITABLE == 0, "only RX enable/pause are writable")
        with self.lock:
            struct.pack_into('<I', self.mapping, self.word_offset, writable)
            # UC non-posted read flush; status bits are read-only, not echoed.
            client.require(self.read() & RX_WRITABLE == writable, "MAC RX control readback differs")

    def close(self):
        with self.lock:
            if self.mapping is not None:
                self.mapping.close(); self.mapping = None
            if self.fd is not None:
                os.close(self.fd); self.fd = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


class FaultRegisters:
    def __init__(self, registers, rx, mode, size, clock=time.monotonic):
        client.require(mode in ('retry', 'watchdog'), "unsupported fault mode")
        self.registers, self.rx, self.mode, self.size, self.clock = registers, rx, mode, size, clock
        self.original = rx.read() & RX_WRITABLE
        client.require(self.original & 1, "cannot borrow an already disabled receiver")
        self.dropping = self.started = False
        self.timer = None
        self.lock = threading.RLock()
        self.evidence = dict(mode=mode, original_rx_writable=self.original, rx_restored=False,
                             retry_observed_before_restore=False, deadline_expired=False,
                             hls_rto_modified=False, max_rx_off_seconds=MAX_RX_OFF_SECONDS)

    def check_identity(self):
        return self.registers.check_identity()

    def restore(self):
        with self.lock:
            if self.dropping:
                self.rx.write(self.original)
                self.evidence.update(rx_restored=True, rx_off_seconds=self.clock() - self.off_start,
                                     restored_rx_writable=self.rx.read() & RX_WRITABLE)
                self.dropping = False
            if self.timer:
                self.timer.cancel()

    def emergency_restore(self):
        # Independent of the completion-poll path; not a hard real-time promise
        # under OS suspension, process SIGKILL, host failure or device removal.
        with self.lock:
            if self.dropping:
                self.evidence['deadline_expired'] = True
                try:
                    self.restore()
                except BaseException as error:
                    self.evidence['restoration_error'] = str(error)

    def activity(self):
        return client.snapshot(self.registers)

    def read32(self, address):
        value = self.registers.read32(address)
        if address == client.STATUS:
            with self.lock:
                client.require(not self.evidence['deadline_expired'], "MAC RX fault deadline exceeded")
                if self.dropping:
                    sample = self.activity()
                    diag = sample['diagnostics']
                    retry = (sample['issued'] == 1 and sample['acknowledged'] == 0 and
                             sample['read_commands'] >= 2 and sample['read_bytes'] >= 2 * self.size and
                             (diag['0xc0'] - self.baseline_tx) & 0xFFFFFFFF >= 2 and
                             (diag['0xc4'] - self.baseline_cpl) & 0xFFFFFFFF >= 2)
                    if value & (client.DONE | client.FAILED) or self.mode == 'retry' and retry:
                        self.evidence.update(before_restore=sample, retry_observed_before_restore=retry)
                        self.restore()
                    elif self.clock() - self.off_start >= MAX_RX_OFF_SECONDS:
                        self.emergency_restore()
                        raise client.ClientError("MAC RX fault deadline exceeded")
        return value

    def write32(self, address, value):
        if address == client.COMMAND and value == 1:
            with self.lock:
                client.require(not self.started, "fault owner only permits one START")
                self.started = True
                self.baseline_tx = self.registers.read32(0xC0)
                self.baseline_cpl = self.registers.read32(0xC4)
                self.evidence.update(baseline_tx=self.baseline_tx, baseline_cpl=self.baseline_cpl)
                self.off_start = self.clock()
                self.dropping = True  # Restore even if disable's readback raises.
                self.timer = threading.Timer(MAX_RX_OFF_SECONDS, self.emergency_restore)
                self.timer.daemon = True
                self.timer.start()
                self.rx.write(self.original & ~1)
                if self.clock() - self.off_start >= MAX_RX_OFF_SECONDS:
                    self.emergency_restore()
                    raise client.ClientError("MAC RX disable exceeded deadline before START")
        if address == client.COMMAND and value == 4:
            try:
                self.restore()
            finally:
                self.registers.write32(address, value)
            return
        self.registers.write32(address, value)

    def close(self):
        try:
            self.restore()
        finally:
            if self.timer:
                self.timer.cancel()
                self.timer.join(timeout=1)
                client.require(not self.timer.is_alive(), "MAC restoration thread did not stop")


class ObservedControl:
    def __init__(self, sock, gate):
        self.sock, self.gate, self.prefix = sock, gate, bytearray()

    def recv(self, count):
        value = self.sock.recv(count)
        self.prefix.extend(value[:max(0, client.CONTROL_BYTES - len(self.prefix))])
        return value

    def sendall(self, value):
        if value == b'D':
            client.require(not self.gate.dropping and self.gate.evidence['rx_restored'] and
                           client.safe_terminal(self.gate.registers.read32(client.STATUS)),
                           "cannot request MR verification/release before RX restoration and quiescence")
        self.sock.sendall(value)


def run_fault_transfer(registers, rx, config, sock, mode):
    client.require(config.count == 1 and config.size == 65, "fault cases are exactly one 65-byte WRITE")
    client.require(mode != 'watchdog' or config.device_timeout_cycles == WATCHDOG_CYCLES,
                   "watchdog case must use the finite 10ms controller deadline")
    gate = FaultRegisters(registers, rx, mode, config.size)
    control = ObservedControl(sock, gate)
    result = None
    try:
        try:
            result = client.run_transfer(gate, config, control)
            client.require(mode == 'retry', "ACK completed despite intended watchdog fault")
            result['transport_success'] = True
        except client.ClientError as error:
            if mode != 'watchdog':
                raise
            result = dict(error.evidence)
            status = result.get('status', 0)
            client.require(result.get('start_attempted') is True and result.get('tx_quiescence_verified') is True and
                           client.safe_terminal(status) and client.state(status) == 8 and status & client.FAILED and
                           result.get('error_code') == 2 and result.get('issued') == 1 and
                           result.get('acknowledged') == 0 and result.get('elapsed_cycles', 0) >= WATCHDOG_CYCLES,
                           "failure is not the expected quiescent controller timeout")
            gate.restore()
            control.sendall(b'D')
            client.require(client.receive(control, 1) == b'P', "receiver payload differs after expected timeout")
            peer = client.decode_endpoint(bytes(control.prefix), config.size, 1, config.peer_ip)
            result.update(success=True, receiver_verified=True, transport_success=False,
                          expected_timeout_verified=True, local_qpn=config.local_qpn, local_psn=config.local_psn,
                          peer_qpn=peer.qpn, peer_psn=peer.psn, software_roce_in_this_client=False,
                          fpga_payload_source='bounded_local_pattern')
        client.require(gate.evidence['retry_observed_before_restore'] and gate.evidence['rx_restored'] and
                       not gate.evidence['deadline_expired'] and
                       gate.evidence['restored_rx_writable'] == gate.original and
                       gate.evidence['rx_off_seconds'] <= MAX_RX_OFF_SECONDS,
                       "fault/retry/restoration evidence is incomplete")
        result.update(fault=dict(gate.evidence, layout=rx.layout))
        return result
    except BaseException as error:
        evidence = dict(getattr(error, 'evidence', {}), fault=gate.evidence)
        raise client.ClientError(str(error) or type(error).__name__, evidence) from error
    finally:
        gate.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name, convert in [('bdf', str), ('local-ip', client.ipv4), ('peer-ip', client.ipv4),
                          ('local-mac', client.mac_number), ('peer-mac', client.mac_number)]:
        parser.add_argument('--' + name, type=convert, required=True)
    parser.add_argument('--fault-mode', choices=('retry', 'watchdog'), required=True)
    parser.add_argument('--message-bytes', type=int, choices=(65,), default=65)
    parser.add_argument('--count', type=int, choices=(1,), default=1)
    parser.add_argument('--port', type=int, choices=(18516,), default=18516)
    parser.add_argument('--qpn', type=int, choices=(2,), default=2)
    parser.add_argument('--psn', type=lambda s: int(s, 0), required=True)
    parser.add_argument('--report', type=pathlib.Path, required=True)
    args = parser.parse_args()
    config = client.Config(args.local_ip, args.peer_ip, args.local_mac, args.peer_mac, 65, 1, 2, args.psn,
                           WATCHDOG_CYCLES if args.fault_mode == 'watchdog' else client.CLOCK_HZ)
    config.validate()
    def interrupted(signum, _frame):
        raise KeyboardInterrupt(f'signal {signum}')
    signal.signal(signal.SIGTERM, interrupted); signal.signal(signal.SIGINT, interrupted)
    try:
        with client.PciBar2(args.bdf) as registers:
            with PciRxControl(args.bdf, registers) as rx:
                with socket.create_connection((config.peer_ip, args.port), timeout=5,
                                              source_address=(config.local_ip, 0)) as sock:
                    sock.settimeout(5)
                    result = run_fault_transfer(registers, rx, config, sock, args.fault_mode)
        result.update(hardware_access=True, bdf=args.bdf)
        status = 0
    except (client.ClientError, OSError, ValueError) as error:
        result = dict(getattr(error, 'evidence', {}), success=False, error=str(error), bdf=args.bdf)
        status = 1
    with args.report.open('x') as output:
        output.write(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
    return status


if __name__ == '__main__':
    sys.exit(main())
