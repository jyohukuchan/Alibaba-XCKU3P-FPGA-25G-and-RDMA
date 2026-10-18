#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Audit finite RXE reference logs AND corresponding captured wire packets."""
import collections
import hashlib
import ipaddress
import json
import pathlib
import sys

from rocev2_wire import read_pcap


def one_event(events, name):
    found = [event for event in events if event["event"] == name]
    if len(found) != 1:
        raise ValueError(f"expected exactly one {name} event")
    return found[0]


def summarize(directory):
    capture = directory / "reference.pcap"
    packets = list(read_pcap(capture))
    if not packets or any(not p["icrc_valid"] for p in packets):
        raise ValueError("missing packets or invalid ICRC")
    tests = []
    for size in (1, 63, 64, 65, 4095, 4096, 4097, 8192):
        for direction in ("cx-to-rxe", "rxe-to-cx"):
            prefix = f"{direction}-{size}"
            receiver = [json.loads(line) for line in (directory / f"{prefix}-receiver.jsonl").read_text().splitlines()]
            sender = [json.loads(line) for line in (directory / f"{prefix}-sender.jsonl").read_text().splitlines()]
            r = one_event(receiver, "local_endpoint")
            s = one_event(sender, "local_endpoint")
            verification = one_event(receiver, "memory_verification")
            completion = one_event(sender, "write_completions")
            confirmed = one_event(sender, "receiver_verified")
            if (not verification["pass"] or verification["mismatches"] or
                    verification["bytes"] != size * 16 or completion["messages"] != 16 or
                    completion["bytes"] != size * 16 or not confirmed["pass"]):
                raise ValueError(f"failed memory/completion check: {prefix}")
            source_ip = str(ipaddress.IPv6Address(s["gid"]).ipv4_mapped)
            destination_ip = str(ipaddress.IPv6Address(r["gid"]).ipv4_mapped)
            writes = [p for p in packets if p["source_ip"] == source_ip and
                      p["destination_ip"] == destination_ip and p["destination_qpn"] == r["qpn"] and
                      p["opcode"] in (6, 7, 8, 10)]
            by_psn = {p["psn"]: p for p in writes}
            expected_packets = 16 * ((size + 4095) // 4096)
            expected_psns = {(s["psn"] + i) & 0xFFFFFF for i in range(expected_packets)}
            if set(by_psn) != expected_psns:
                raise ValueError(f"missing/unexpected captured WRITE PSNs: {prefix}")
            payload_bytes = sum(p["payload_bytes"] for p in by_psn.values())
            if payload_bytes != size * 16:
                raise ValueError(f"captured payload byte count mismatch: {prefix}")
            for p in writes:
                if p["opcode"] in (6, 10) and (p["rkey"] != r["rkey"] or p["dma_length"] != size):
                    raise ValueError(f"RETH full-width key/length mismatch: {prefix}")
            acks = [p for p in packets if p["source_ip"] == destination_ip and
                    p["destination_ip"] == source_ip and p["destination_qpn"] == s["qpn"] and p["opcode"] == 17]
            if not acks or any(p["aeth_syndrome"] & 0xE0 for p in acks):
                raise ValueError(f"missing ACK or non-success AETH: {prefix}")
            tests.append(dict(direction=direction, message_bytes=size, messages=16,
                              receiver_verified_bytes=verification["bytes"], mismatches=0,
                              unique_write_packets=len(by_psn), captured_repeated_writes=len(writes)-len(by_psn),
                              captured_acks=len(acks), pass_test=True))
    return dict(reference_only=True, fpga_rdma_implemented=False, data_plane="host RXE <-> CX455A RNIC",
                link_speed_mbit_s=25000, throughput_claim=False,
                pcap_sha256=hashlib.sha256(capture.read_bytes()).hexdigest(),
                rocev2_packets=len(packets), invalid_icrc=0,
                operations=dict(collections.Counter(p["operation"] for p in packets)),
                tests=tests, total_receiver_verified_bytes=sum(t["receiver_verified_bytes"] for t in tests))


if __name__ == "__main__":
    print(json.dumps(summarize(pathlib.Path(sys.argv[1])), indent=2))
