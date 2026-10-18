# SPDX-License-Identifier: BSD-2-Clause-Views
"""Offline READ wire vectors, independent of FPGA/HCA execution."""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'host'))
import read_wire as wire

PEER = dict(source_ip='198.18.11.1', destination_ip='198.18.11.2', destination_qpn=2)


class ReadWireTests(unittest.TestCase):
    def test_request_full_address_key_length_and_psn(self):
        frame = wire.encode(opcode=wire.REQUEST, psn=0xFFFFFF,
                            remote_address=0xFEDCBA9876543210, rkey=0xFEDCBA98, read_bytes=8193, **PEER)
        decoded = wire.decode(frame)
        self.assertEqual(decoded['remote_address'], 0xFEDCBA9876543210)
        self.assertEqual(decoded['rkey'], 0xFEDCBA98)
        self.assertEqual(decoded['read_bytes'], 8193)
        self.assertEqual(decoded['psn'], 0xFFFFFF)
        self.assertEqual(decoded['payload'], b'')

    def test_all_tail_padding_sizes_and_segment_boundaries(self):
        for size in [1, 2, 3, 4, 63, 64, 65, 4095, 4096, 4097, 8192, 8193, 65536]:
            with self.subTest(size=size):
                payload = bytes((i * 179 ^ i >> 7 ^ 0xD3) & 255 for i in range(size))
                decoded = [wire.decode(f) for f in wire.responses(payload, initial_psn=0xFFFFFE, **PEER)]
                self.assertEqual(b''.join(d['payload'] for d in decoded), payload)
                self.assertEqual([d['psn'] for d in decoded], [(0xFFFFFE + i) & 0xFFFFFF for i in range(len(decoded))])
                self.assertEqual(decoded[-1]['opcode'], wire.ONLY if size <= 4096 else wire.LAST)
                self.assertEqual(decoded[0]['opcode'], wire.ONLY if size <= 4096 else wire.FIRST)
                self.assertEqual(decoded[-1]['pad_bytes'], -size & 3)
                for d in decoded[1:-1]:
                    self.assertEqual(d['opcode'], wire.MIDDLE)

    def test_corruption_and_truncation_are_not_valid_vectors(self):
        frame = wire.responses(bytes(range(65)), initial_psn=1, **PEER)[0]
        for index in range(14, len(frame)):
            with self.subTest(index=index):
                bad = bytearray(frame); bad[index] ^= 1
                # Some header bits are ICRC invariant; checksum/framing still
                # covers many, but TTL/UDP checksum are intentionally masked.
                if index in (14 + 8, 14 + 26, 14 + 27, 14 + 32):
                    continue
                with self.assertRaises(ValueError):
                    wire.decode(bad)
        for size in [0, 13, 30, len(frame) - 1]:
            with self.assertRaises(ValueError):
                wire.decode(frame[:size])

    def test_invalid_shapes_rejected(self):
        for arguments in [dict(opcode=wire.REQUEST, read_bytes=0),
                          dict(opcode=wire.REQUEST, read_bytes=1, payload=b'x'),
                          dict(opcode=wire.FIRST, payload=b'x'),
                          dict(opcode=wire.MIDDLE, payload=b'x'),
                          dict(opcode=wire.ONLY, payload=b''),
                          dict(opcode=wire.ONLY, payload=b'x' * 4097),
                          dict(opcode=0x11, payload=b'x')]:
            with self.subTest(arguments={k:len(v) if isinstance(v,bytes) else v for k,v in arguments.items()}):
                with self.assertRaises(ValueError):
                    wire.encode(psn=1, **arguments, **PEER)


if __name__ == '__main__':
    unittest.main()
