# SPDX-License-Identifier: BSD-2-Clause-Views
"""Offline RC READ wire oracle. Never opens a socket or accesses hardware."""
import ipaddress
import pathlib
import struct
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / 'host'))
from rocev2_wire import icrc_ipv4, internet_checksum

REQUEST, FIRST, MIDDLE, LAST, ONLY = 0x0C, 0x0D, 0x0E, 0x0F, 0x10
AETH_OPS = (FIRST, LAST, ONLY)
PMTU = 4096


def require(condition, message):
    if not condition:
        raise ValueError(message)


def encode(*, opcode, source_ip, destination_ip, destination_qpn, psn,
           payload=b'', remote_address=0, rkey=0, read_bytes=0,
           msn=1, syndrome=0x1F, source_mac='b8:83:03:67:c5:d0',
           destination_mac='8a:f3:fb:b9:75:31', udp_source_port=49152):
    require(opcode in (REQUEST, FIRST, MIDDLE, LAST, ONLY), 'unsupported READ opcode')
    require(0 <= destination_qpn <= 0xFFFFFF and 0 <= psn <= 0xFFFFFF, 'QPN/PSN width')
    require(0 <= remote_address < 1 << 64 and 0 <= rkey < 1 << 32, 'RETH width')
    require(0 <= msn <= 0xFFFFFF and 0 <= syndrome <= 255, 'AETH width')
    require(1 <= udp_source_port <= 65535, 'UDP source port')
    payload = bytes(payload)
    if opcode == REQUEST:
        require(not payload and 1 <= read_bytes <= 0xFFFFFFFF, 'READ request length/payload')
        extension = struct.pack('!QII', remote_address, rkey, read_bytes)
    else:
        require(1 <= len(payload) <= PMTU, 'response payload must fit PMTU')
        require(opcode not in (FIRST, MIDDLE) or len(payload) == PMTU, 'nonfinal response must fill PMTU')
        extension = bytes([syndrome]) + msn.to_bytes(3, 'big') if opcode in AETH_OPS else b''
    pad = -len(payload) & 3
    bth = (bytes([opcode, pad << 4]) + b'\xff\xff\0' + destination_qpn.to_bytes(3, 'big') +
           bytes([0x80 if opcode == REQUEST else 0]) + psn.to_bytes(3, 'big'))
    udp_length = 8 + len(bth) + len(extension) + len(payload) + pad + 4
    ip = bytearray(struct.pack('!BBHHHBBH4s4s', 0x45, 0, 20 + udp_length, 0, 0x4000, 64, 17, 0,
                              ipaddress.IPv4Address(source_ip).packed,
                              ipaddress.IPv4Address(destination_ip).packed))
    ip[10:12] = internet_checksum(ip).to_bytes(2, 'big')
    packet = (bytes(ip) + struct.pack('!HHHH', udp_source_port, 4791, udp_length, 0) +
              bth + extension + payload + b'\0' * pad + b'\0' * 4)
    ethernet = bytes.fromhex(destination_mac.replace(':', '') + source_mac.replace(':', '') + '0800')
    require(len(ethernet) == 14, 'Ethernet header size')
    return ethernet + packet[:-4] + icrc_ipv4(packet)


def responses(payload, *, initial_psn, **endpoint):
    payload = bytes(payload)
    require(payload and 0 <= initial_psn <= 0xFFFFFF, 'response extent/PSN')
    result = []
    for index, start in enumerate(range(0, len(payload), PMTU)):
        end = min(start + PMTU, len(payload))
        opcode = ONLY if len(payload) <= PMTU else FIRST if start == 0 else LAST if end == len(payload) else MIDDLE
        result.append(encode(opcode=opcode, payload=payload[start:end],
                             psn=(initial_psn + index) & 0xFFFFFF, **endpoint))
    return result


def decode(frame):
    frame = bytes(frame)
    require(len(frame) >= 58 and frame[12:14] == b'\x08\x00', 'short/non-IPv4 Ethernet frame')
    ip = frame[14:]
    require(ip[0] == 0x45 and ip[9] == 17 and int.from_bytes(ip[2:4], 'big') == len(ip), 'IPv4 framing')
    require(not int.from_bytes(ip[6:8], 'big') & 0x3FFF and internet_checksum(ip[:20]) == 0, 'IPv4 checksum/fragment')
    require(int.from_bytes(ip[22:24], 'big') == 4791 and int.from_bytes(ip[24:26], 'big') == len(ip) - 20,
            'RoCE UDP framing')
    require(ip[-4:] == icrc_ipv4(ip), 'invalid ICRC')
    bth = ip[28:-4]
    require(len(bth) >= 12 and bth[0] in (REQUEST, FIRST, MIDDLE, LAST, ONLY), 'not an RC READ packet')
    opcode, pad = bth[0], bth[1] >> 4 & 3
    require(bth[1] & 0x0F == 0 and bth[2:4] == b'\xff\xff', 'transport version/PKey')
    extension = 16 if opcode == REQUEST else 4 if opcode in AETH_OPS else 0
    require(len(bth) >= 12 + extension + pad, 'short extension/padding')
    payload = bth[12 + extension:len(bth) - pad if pad else len(bth)]
    result = dict(opcode=opcode, destination_qpn=int.from_bytes(bth[5:8], 'big'),
                  psn=int.from_bytes(bth[9:12], 'big'), pad_bytes=pad, payload=payload,
                  source_ip=str(ipaddress.IPv4Address(ip[12:16])),
                  destination_ip=str(ipaddress.IPv4Address(ip[16:20])))
    if opcode == REQUEST:
        address, key, length = struct.unpack('!QII', bth[12:28])
        require(not payload and pad == 0 and length > 0, 'request data/zero length')
        result.update(remote_address=address, rkey=key, read_bytes=length)
    else:
        require(1 <= len(payload) <= PMTU and pad == -len(payload) & 3, 'response payload/padding length')
        require(opcode not in (FIRST, MIDDLE) or len(payload) == PMTU, 'nonfinal short response')
        if opcode in AETH_OPS:
            result.update(syndrome=bth[12], msn=int.from_bytes(bth[13:16], 'big'))
    return result
