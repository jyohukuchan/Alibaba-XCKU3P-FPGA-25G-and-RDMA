#!/usr/bin/env python3
"""Small offline IPv4 RoCEv2 decoder/ICRC oracle; never transmits packets.

Invariant field masking is checked against Linux v6.17 rxe_icrc.c:
https://github.com/torvalds/linux/blob/v6.17/drivers/infiniband/sw/rxe/rxe_icrc.c
Implementation below is independent Python, not copied kernel source.
"""
import argparse
import collections
import ipaddress
import json
import struct
import zlib

OPCODES = {
    0x06: "WRITE_FIRST", 0x07: "WRITE_MIDDLE", 0x08: "WRITE_LAST",
    0x0A: "WRITE_ONLY", 0x0C: "READ_REQUEST", 0x11: "ACK",
}


def internet_checksum(data):
    padded = data + b"\0" * (len(data) % 2)
    total = sum(struct.unpack(f"!{len(padded) // 2}H", padded))
    while total >> 16:
        total = (total & 0xFFFF) + (total >> 16)
    return (~total) & 0xFFFF


def write_only_frame(*, source_mac, destination_mac, source_ip, destination_ip,
                     udp_source_port, destination_qpn, psn, remote_address, rkey,
                     payload, identification=0, tos=0, bth_flags=0,
                     ack_requested=True):
    """Offline golden model for one RC WRITE_ONLY (no Ethernet FCS).

    This is test stimulus, not a transport engine: it has no QP lifecycle,
    retry window, memory protection or DMA. Never use packet generation alone
    as evidence that the FPGA implements RDMA.
    """
    if not 0 <= destination_qpn <= 0xFFFFFF or not 0 <= psn <= 0xFFFFFF:
        raise ValueError("QPN/PSN must be 24 bits")
    if not 0 <= rkey <= 0xFFFFFFFF or not 0 <= remote_address <= 0xFFFFFFFFFFFFFFFF:
        raise ValueError("rkey/address outside wire width")
    if not 1 <= len(payload) <= 4096:
        raise ValueError("WRITE_ONLY payload must be 1..4096 bytes")
    padding = (-len(payload)) & 3
    bth = (bytes([0x0A, (bth_flags & 0xCF) | (padding << 4)]) + b"\xff\xff\0" +
           destination_qpn.to_bytes(3, "big") + bytes([0x80 if ack_requested else 0]) + psn.to_bytes(3, "big"))
    reth = struct.pack("!QII", remote_address, rkey, len(payload))
    udp_length = 8 + len(bth) + len(reth) + len(payload) + padding + 4
    ip = bytearray(struct.pack("!BBHHHBBH4s4s", 0x45, tos, 20 + udp_length,
                               identification, 0x4000, 64, 17, 0,
                               ipaddress.IPv4Address(source_ip).packed,
                               ipaddress.IPv4Address(destination_ip).packed))
    ip[10:12] = struct.pack("!H", internet_checksum(ip))
    packet = (bytes(ip) + struct.pack("!HHHH", udp_source_port, 4791, udp_length, 0) +
              bth + reth + payload + b"\0" * padding + b"\0" * 4)
    ethernet = bytes.fromhex(destination_mac.replace(":", "") + source_mac.replace(":", "")) + b"\x08\x00"
    if len(ethernet) != 14:
        raise ValueError("invalid Ethernet addresses")
    return ethernet + packet[:-4] + icrc_ipv4(packet)


def icrc_ipv4(packet):
    """Compute wire-order ICRC over IPv4..pad, excluding the final ICRC.

    Covers the masked 8-byte LRH, IP TOS/TTL/checksum, UDP checksum, and BTH
    reserved byte before destination QPN. CRC uses reflected IEEE CRC-32.
    Only plain IPv4 (no options/fragmentation) is supported by this oracle.
    """
    if len(packet) < 44 or packet[0] != 0x45 or packet[9] != 17:
        raise ValueError("requires plain IPv4/UDP/BTH/ICRC")
    total = int.from_bytes(packet[2:4], "big")
    if total != len(packet) or int.from_bytes(packet[6:8], "big") & 0x3FFF:
        raise ValueError("incomplete or fragmented IPv4 packet")
    masked = bytearray(packet[:-4])
    masked[1] = masked[8] = 0xFF
    masked[10:12] = b"\xff\xff"
    masked[26:28] = b"\xff\xff"
    masked[32] = 0xFF
    return struct.pack("<I", zlib.crc32(b"\xff" * 8 + masked))


def decode_ethernet(frame):
    frame = bytes(frame)
    if len(frame) < 14:
        raise ValueError("short Ethernet frame")
    offset = 14
    ethertype = int.from_bytes(frame[12:14], "big")
    while ethertype in (0x8100, 0x88A8):
        if len(frame) < offset + 4:
            raise ValueError("short VLAN header")
        ethertype = int.from_bytes(frame[offset + 2:offset + 4], "big")
        offset += 4
    if ethertype != 0x0800:
        return None
    ip = frame[offset:]
    if len(ip) < 20:
        raise ValueError("short IPv4 header")
    if ip[9] != 17:
        return None
    if ip[0] != 0x45:
        raise ValueError("IPv4 options/version unsupported")
    total = int.from_bytes(ip[2:4], "big")
    ip = ip[:total]
    if len(ip) < 28:
        raise ValueError("short UDP")
    sport, dport, udp_length = struct.unpack_from("!HHH", ip, 20)
    if dport != 4791:
        return None
    if udp_length != len(ip) - 20 or udp_length < 24:
        raise ValueError("invalid RoCEv2 UDP length")
    expected_icrc = icrc_ipv4(ip)
    bth = ip[28:-4]
    opcode, flags = bth[0:2]
    pad = (flags >> 4) & 3
    extension_length = 16 if opcode in (0x06, 0x0A, 0x0C) else 4 if opcode == 0x11 else 0
    if len(bth) < 12 + extension_length + pad:
        raise ValueError("short extended transport header")
    result = {
        "source_ip": str(ipaddress.IPv4Address(ip[12:16])),
        "destination_ip": str(ipaddress.IPv4Address(ip[16:20])),
        "udp_source_port": sport,
        "opcode": opcode, "operation": OPCODES.get(opcode, f"OP_{opcode:02x}"),
        "destination_qpn": int.from_bytes(bth[5:8], "big"),
        "psn": int.from_bytes(bth[9:12], "big"),
        "ack_requested": bool(bth[8] & 0x80),
        "pkey": int.from_bytes(bth[2:4], "big"),
        "pad_bytes": pad,
        "payload_bytes": len(bth) - 12 - extension_length - pad,
        "icrc_valid": ip[-4:] == expected_icrc,
        "wire_icrc": ip[-4:].hex(), "expected_icrc": expected_icrc.hex(),
    }
    if extension_length == 16:
        result.update(remote_address=f"0x{int.from_bytes(bth[12:20], 'big'):016x}",
                      rkey=f"0x{int.from_bytes(bth[20:24], 'big'):08x}",
                      dma_length=int.from_bytes(bth[24:28], "big"))
    elif opcode == 0x11:
        result.update(aeth_syndrome=bth[12], msn=int.from_bytes(bth[13:16], "big"))
    return result


def read_pcap(path):
    with open(path, "rb") as stream:
        header = stream.read(24)
        byte_orders = {b"\xd4\xc3\xb2\xa1": "<", b"\xa1\xb2\xc3\xd4": ">",
                       b"\x4d\x3c\xb2\xa1": "<", b"\xa1\xb2\x3c\x4d": ">"}
        if len(header) != 24 or header[:4] not in byte_orders:
            raise ValueError("requires classic PCAP, not pcapng")
        order = byte_orders[header[:4]]
        if struct.unpack_from(order + "I", header, 20)[0] != 1:
            raise ValueError("requires Ethernet link type")
        while record := stream.read(16):
            if len(record) != 16:
                raise ValueError("truncated PCAP record")
            _, _, captured, original = struct.unpack(order + "IIII", record)
            if captured != original or captured > 65536:
                raise ValueError("truncated/oversized packet")
            frame = stream.read(captured)
            if len(frame) != captured:
                raise ValueError("truncated PCAP data")
            decoded = decode_ethernet(frame)
            if decoded is not None:
                yield decoded


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture")
    parser.add_argument("--packets", action="store_true")
    args = parser.parse_args()
    packets = list(read_pcap(args.capture))
    summary = {
        "reference_only": True,
        "rocev2_packets": len(packets),
        "invalid_icrc": sum(not p["icrc_valid"] for p in packets),
        "operations": dict(collections.Counter(p["operation"] for p in packets)),
        "directions": dict(collections.Counter(p["source_ip"] + "->" + p["destination_ip"] for p in packets)),
        "ack_syndromes": dict(collections.Counter(f"0x{p['aeth_syndrome']:02x}" for p in packets if p["opcode"] == 0x11)),
    }
    print(json.dumps(summary, indent=2))
    if args.packets:
        for packet in packets:
            print(json.dumps(packet))
    return 0 if packets and not summary["invalid_icrc"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
