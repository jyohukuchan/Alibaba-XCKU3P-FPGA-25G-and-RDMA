#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Finite native FPGA WRITE controller. TCP carries metadata/verification only.

No programming, flash, NIC reset, fan change, or arbitrary host DMA. Live
access requires the audited BDF/identity, ROC2 BAR2 and explicit opt-in.
"""
import argparse
from dataclasses import dataclass
import fcntl
import ipaddress
import json
import mmap
import os
import pathlib
import re
import secrets
import signal
import socket
import stat
import struct
import sys
import time

CONTROL_BYTES = 256
MAX_TOTAL = 64 * 1024 * 1024
CLOCK_HZ = 250_000_000
AUDITED_BDF = "0000:82:00.0"
ID, VERSION, COMMAND, STATUS, ERROR = 0, 4, 8, 12, 16
ISSUED, ACKED, TOTAL, ELAPSED, DUPLICATES = 20, 24, 28, 32, 40
READ_COMMANDS, READ_BYTES, REJECTS = 44, 48, 56
BUSY, DONE, FAILED, CORE_RESET, QUIET, HALT = 1, 2, 4, 8, 16, 32


class ClientError(RuntimeError):
    def __init__(self, message, evidence=None):
        super().__init__(message)
        self.evidence = evidence or {}


def require(condition, message):
    if not condition:
        raise ClientError(message)


def ipv4(text):
    address = ipaddress.IPv4Address(text)
    require(not address.is_multicast and not address.is_unspecified and int(address) & 255 not in (0, 255),
            "an explicit unicast test IPv4 address is required")
    return str(address)


def mac_number(text):
    require(re.fullmatch(r"[0-9a-fA-F]{2}(?::[0-9a-fA-F]{2}){5}", text) is not None,
            "invalid MAC address")
    value = int(text.replace(":", ""), 16)
    require(value != 0 and not value & (1 << 40), "unicast nonzero MAC required")
    return value


def gid_for_ip(address):
    return b"\0" * 10 + b"\xff\xff" + ipaddress.IPv4Address(address).packed


@dataclass(frozen=True)
class Endpoint:
    qpn: int
    psn: int
    rkey: int
    address: int
    size: int
    count: int
    gid: bytes

    def encode(self):
        text = f"AS02RC1 {self.qpn:x} {self.psn:x} {self.rkey:x} {self.address:x} {self.size} {self.count} {self.gid.hex()}\n".encode("ascii")
        require(len(text) < CONTROL_BYTES, "endpoint control record too long")
        return text.ljust(CONTROL_BYTES, b"\0")


def decode_endpoint(packet, size, count, peer_ip):
    require(len(packet) == CONTROL_BYTES, "truncated endpoint record")
    prefix, nul, padding = packet.partition(b"\0")
    require(nul == b"\0" and not padding.strip(b"\0") and prefix.endswith(b"\n"), "invalid endpoint framing/padding")
    try:
        fields = prefix[:-1].decode("ascii").split(" ")
    except UnicodeDecodeError as error:
        raise ClientError("non-ASCII endpoint") from error
    require(len(fields) == 8 and fields[0] == "AS02RC1", "invalid endpoint fields")
    for field, width in zip(fields[1:5], (6, 6, 8, 16)):
        require(re.fullmatch(r"[0-9a-fA-F]{1," + str(width) + r"}", field) is not None, "invalid endpoint hex width")
    require(all(re.fullmatch(r"[0-9]{1,10}", field) for field in fields[5:7]) and
            re.fullmatch(r"[0-9a-fA-F]{32}", fields[7]) is not None, "invalid endpoint size/count/GID")
    endpoint = Endpoint(*(int(field, 16) for field in fields[1:5]),
                        int(fields[5]), int(fields[6]), bytes.fromhex(fields[7]))
    require(2 <= endpoint.qpn <= 0xFFFFFF and endpoint.size == size and endpoint.count == count,
            "peer QP/size/count does not match the finite run")
    require(endpoint.gid == gid_for_ip(peer_ip), "peer GID does not match explicit IPv4 peer")
    total = size * count
    require(endpoint.address != 0 and endpoint.address + total <= 0xFFFFFFFFFFFFFFFF,
            "peer MR extent overflows the supported 64-bit range")
    return endpoint


@dataclass(frozen=True)
class Config:
    local_ip: str
    peer_ip: str
    local_mac: int
    peer_mac: int
    size: int = 64
    count: int = 1
    local_qpn: int = 2
    local_psn: int = 0x123456
    device_timeout_cycles: int = CLOCK_HZ
    host_timeout_seconds: float = 2.0

    def validate(self):
        ipv4(self.local_ip); ipv4(self.peer_ip)
        require(self.local_ip != self.peer_ip, "local/peer IP must differ")
        require(1 <= self.size <= 4096 and 1 <= self.count <= 65536 and self.size * self.count <= MAX_TOTAL,
                "requires 1..4096 bytes, 1..65536 WRITEs, <=64MiB total")
        require(2 <= self.local_qpn < 8 and 0 <= self.local_psn <= 0xFFFFFF, "QP/PSN outside compiled table/width")
        require(all(0 < mac < 1 << 48 and not mac & (1 << 40) for mac in (self.local_mac, self.peer_mac)),
                "invalid unicast Ethernet addressing")
        require(10000 <= self.device_timeout_cycles <= 4 * CLOCK_HZ and
                self.device_timeout_cycles / CLOCK_HZ < self.host_timeout_seconds <= 8,
                "device/host deadlines must fit before peer control teardown")


class PciBar2:
    """UC sysfs MMIO mapping, restricted to the actual audited device."""
    def __init__(self, bdf):
        require(os.environ.get("AS02_ALLOW_FPGA_RDMA") == "YES", "set AS02_ALLOW_FPGA_RDMA=YES for live access")
        require(bdf == AUDITED_BDF, "this harness only authorizes the audited FPGA BDF")
        require(sys.byteorder == "little" and os.uname().machine == "x86_64", "MMIO access is audited for this x86_64 host only")
        self.lock_fd = self.fd = self.mapping = None
        device = pathlib.Path("/sys/bus/pci/devices") / bdf
        for name, value in (("vendor", 0x1234), ("device", 0x1001), ("subsystem_vendor", 0x1CE4),
                            ("subsystem_device", 0x0009), ("class", 0x020000)):
            require(int((device / name).read_text(), 16) == value, "unexpected PCI identity: " + name)
        require((device / "driver").resolve().name == "mqnic", "expected bound mqnic driver")
        try:
            lock_path = "/run/lock/as02-rocev2-0000_82_00_0.lock"
            self.lock_fd = os.open(lock_path, os.O_RDWR | os.O_CREAT | os.O_CLOEXEC | os.O_NOFOLLOW, 0o600)
            info = os.fstat(self.lock_fd)
            require(stat.S_ISREG(info.st_mode) and info.st_uid == os.geteuid(), "unsafe existing control lock")
            fcntl.flock(self.lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.fd = os.open(device / "resource2", os.O_RDWR | os.O_SYNC | os.O_CLOEXEC)
            require(os.fstat(self.fd).st_size >= 4096, "missing application BAR2 aperture")
            self.mapping = mmap.mmap(self.fd, 4096, flags=mmap.MAP_SHARED, prot=mmap.PROT_READ | mmap.PROT_WRITE)
            self.check_identity()
        except BaseException:
            self.close()
            raise

    def check_identity(self):
        require(self.read32(ID) == 0x524F4332 and self.read32(VERSION) == 0x00010000, "BAR2 is not the supported ROC2 app")

    def read32(self, address):
        require(0 <= address <= 4092 and address % 4 == 0, "invalid MMIO register")
        return struct.unpack_from("<I", self.mapping, address)[0]

    def write32(self, address, value):
        require(0 <= address <= 4092 and address % 4 == 0 and 0 <= value <= 0xFFFFFFFF, "invalid MMIO write")
        struct.pack_into("<I", self.mapping, address, value)
        # Non-posted readback flushes the preceding posted write on this
        # x86_64 UC PCI mapping; never use msync/flush on a PCI BAR.
        require(self.read32(ID) == 0x524F4332, "device disappeared during control write")

    def close(self):
        if self.mapping is not None:
            self.mapping.close(); self.mapping = None
        if self.fd is not None:
            os.close(self.fd); self.fd = None
        if self.lock_fd is not None:
            os.close(self.lock_fd); self.lock_fd = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def read64(registers, address):
    for _ in range(8):
        high = registers.read32(address + 4)
        low = registers.read32(address)
        if high == registers.read32(address + 4):
            return high << 32 | low
    raise ClientError("counter did not provide a coherent high/low snapshot")


def state(status):
    return status >> 8 & 15


def safe_terminal(status):
    return not status & BUSY and status & (CORE_RESET | QUIET | HALT) == CORE_RESET | QUIET | HALT and state(status) in (0, 7, 8)


def prepare(registers):
    registers.check_identity()
    status = registers.read32(STATUS)
    require(safe_terminal(status), "FPGA is busy or transmit quiescence is unproven; refusing to take over")
    if state(status) in (7, 8):
        registers.write32(COMMAND, 2)
        deadline = time.monotonic() + 0.25
        while state(registers.read32(STATUS)) != 0 and time.monotonic() < deadline:
            time.sleep(0.001)
    require(safe_terminal(registers.read32(STATUS)) and state(registers.read32(STATUS)) == 0,
            "FPGA did not enter quiescent idle")


def receive(sock, length):
    result = bytearray()
    while len(result) < length:
        part = sock.recv(length - len(result))
        require(bool(part), "peer closed the control connection")
        result.extend(part)
    return bytes(result)


def configure(registers, config, peer):
    total = config.size * config.count
    words = (config.local_mac & 0xFFFFFFFF, config.local_mac >> 32,
             config.peer_mac & 0xFFFFFFFF, config.peer_mac >> 32,
             int(ipaddress.IPv4Address(config.local_ip)), int(ipaddress.IPv4Address(config.peer_ip)),
             config.local_qpn, peer.qpn, config.local_psn, peer.psn, peer.rkey, config.size,
             peer.address & 0xFFFFFFFF, peer.address >> 32, total, 0, config.count, config.device_timeout_cycles)
    rejected = registers.read32(REJECTS)
    for index, value in enumerate(words):
        address = 0x40 + index * 4
        registers.write32(address, value)
        require(registers.read32(address) == value, f"configuration readback differs at {address:#x}")
    require(registers.read32(REJECTS) == rejected, "FPGA rejected a configuration write")


def abort_owned(registers, timeout=2.0):
    status = registers.read32(STATUS)
    if status & BUSY:
        registers.write32(COMMAND, 4)
    deadline = time.monotonic() + timeout
    while not safe_terminal(status) and time.monotonic() < deadline:
        time.sleep(0.001)
        status = registers.read32(STATUS)
    return bool(safe_terminal(status))


def snapshot(registers):
    return dict(status=registers.read32(STATUS), error_code=registers.read32(ERROR),
                issued=registers.read32(ISSUED), acknowledged=registers.read32(ACKED),
                total_bytes=registers.read32(TOTAL), elapsed_cycles=read64(registers, ELAPSED),
                duplicate_acks=registers.read32(DUPLICATES), read_commands=registers.read32(READ_COMMANDS),
                read_bytes=read64(registers, READ_BYTES),
                diagnostics={f"0x{address:02x}": registers.read32(address) for address in range(0x90, 0xD0, 4)})


def run_transfer(registers, config, sock):
    """The caller retains TCP/MR ownership until this function has stopped TX."""
    config.validate()
    prepare(registers)
    started = False
    evidence = dict(event="fpga_write_test", success=False, receiver_verified=False,
                    message_bytes=config.size, messages=config.count, control_only_tcp=True)
    wall_start = time.monotonic()
    try:
        peer = decode_endpoint(receive(sock, CONTROL_BYTES), config.size, config.count, config.peer_ip)
        local = Endpoint(config.local_qpn, config.local_psn, 0, 0, config.size, config.count, gid_for_ip(config.local_ip))
        sock.sendall(local.encode())
        require(receive(sock, 1) == b"R", "peer QP was not ready")
        configure(registers, config, peer)
        baseline_tx = registers.read32(0xC0)
        baseline_cpl = registers.read32(0xC4)
        sock.sendall(b"R")
        started = True  # Own the attempted START even if its flush/readback fails.
        registers.write32(COMMAND, 1)
        deadline = time.monotonic() + config.host_timeout_seconds
        while True:
            status = registers.read32(STATUS)
            if status & (DONE | FAILED):
                break
            require(time.monotonic() < deadline, "FPGA completion deadline exceeded")
            time.sleep(0.001)
        result = snapshot(registers)
        evidence.update(result)
        require(safe_terminal(result["status"]), "terminal status did not prove TX/core quiescence")
        require(state(result["status"]) == 7 and result["status"] & DONE and not result["status"] & FAILED and
                result["error_code"] == 0, "FPGA reported a failed run")
        require(result["issued"] == config.count and result["acknowledged"] == config.count and
                result["total_bytes"] == config.size * config.count and result["elapsed_cycles"] > 0,
                "incomplete FPGA completion counters")
        diag = result["diagnostics"]
        require(diag["0xcc"] == 0 and diag["0xac"] == 0 and diag["0xb0"] == 0,
                "guard/TX-integrity/FIFO fault at completion")
        require((diag["0xc0"] - baseline_tx) & 0xFFFFFFFF >= config.count and
                (diag["0xc4"] - baseline_cpl) & 0xFFFFFFFF >= config.count and
                result["read_commands"] >= config.count and result["read_bytes"] >= config.size * config.count,
                "missing actual injected/read/completion activity")
        # Only quiesced, acknowledged TX permits the peer to inspect/release MR.
        sock.sendall(b"D")
        require(receive(sock, 1) == b"P", "CX455A receiver did not verify every byte")
        seconds = result["elapsed_cycles"] / CLOCK_HZ
        evidence.update(success=True, receiver_verified=True, tx_quiescence_verified=True,
                        local_qpn=config.local_qpn, local_psn=config.local_psn, peer_qpn=peer.qpn, peer_psn=peer.psn,
                        seconds_from_hw_counter=seconds, includes_initialization_and_drain=True,
                        payload_gbit_per_second_from_hw_counter=config.size * config.count * 8 / seconds / 1e9,
                        total_control_wall_seconds=time.monotonic() - wall_start,
                        software_roce_in_this_client=False, fpga_payload_source="bounded_local_pattern",
                        remote_provider_identity_verified=False)
        return evidence
    except BaseException as error:
        message = str(error) or type(error).__name__
        evidence["error"] = message
        evidence["start_attempted"] = started
        if started:
            try:
                evidence["tx_quiescence_verified"] = abort_owned(registers)
                evidence["final_status"] = registers.read32(STATUS)
            except BaseException as abort_error:
                evidence["tx_quiescence_verified"] = False
                evidence["abort_error"] = str(abort_error)
        raise ClientError(message, evidence) from error


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bdf", required=True)
    parser.add_argument("--local-ip", required=True, type=ipv4)
    parser.add_argument("--peer-ip", required=True, type=ipv4)
    parser.add_argument("--local-mac", required=True, type=mac_number)
    parser.add_argument("--peer-mac", required=True, type=mac_number)
    parser.add_argument("--message-bytes", type=int, default=64)
    parser.add_argument("--count", type=int, default=1)
    parser.add_argument("--port", type=int, default=18516)
    parser.add_argument("--qpn", type=int, default=2)
    parser.add_argument("--psn", type=lambda value: int(value, 0))
    parser.add_argument("--report", type=pathlib.Path)
    args = parser.parse_args()
    require(os.environ.get("AS02_ALLOW_FPGA_RDMA") == "YES", "set AS02_ALLOW_FPGA_RDMA=YES for live access")
    require(1 <= args.port <= 65535, "invalid control port")
    config = Config(args.local_ip, args.peer_ip, args.local_mac, args.peer_mac,
                    args.message_bytes, args.count, args.qpn, args.psn if args.psn is not None else secrets.randbelow(1 << 24))
    config.validate()
    def interrupted(signum, _frame):
        raise KeyboardInterrupt(f"signal {signum}")
    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    try:
        with PciBar2(args.bdf) as registers:
            with socket.create_connection((config.peer_ip, args.port), timeout=5,
                                          source_address=(config.local_ip, 0)) as control:
                control.settimeout(5)
                result = run_transfer(registers, config, control)
        result.update(bdf=args.bdf, hardware_access=True)
        exit_code = 0
    except ClientError as error:
        result = dict(error.evidence, success=False, error=str(error), bdf=args.bdf)
        exit_code = 1
    print(json.dumps(result, indent=2))
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(result, indent=2) + "\n")
    return exit_code


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ClientError, OSError, ValueError) as error:
        print(f"refused/failed: {error}", file=sys.stderr)
        sys.exit(1)
