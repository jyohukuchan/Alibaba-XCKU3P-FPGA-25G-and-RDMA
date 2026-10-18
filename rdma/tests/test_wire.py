#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Hardware-independent protocol checks, including observed RNIC/RXE frames."""
import pathlib
import re
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "host"))
from rocev2_wire import decode_ethernet, internet_checksum, write_only_frame

# Finite reference experiment, 2026-10-17 UTC. Data is our deterministic
# pattern; transient registered addresses/keys are not valid after test exit.
CX_WRITE = bytes.fromhex(
    "8af3fbb97531b8830367c5d008004502007c0f704000401188d7c6120b01c6120b02"
    "cd0412b7006800000a40ffff00000011801234560000615eb7c6b0000000021400000040"
    "5ad95cd356d548cf42c144fb7efd70f76ae96ce366e5189f1291148b0e8d00873a"
    "b93cb336b528af22a1245bde5dd057ca49cc43c645f87ff271f46bee6de067ef63811a")
RXE_ACK = bytes.fromhex(
    "b8830367c5d08af3fbb975310800450000308eaa4000401109ebc6120b02c6120b01"
    "cd0412b7001c00001100ffff000000c4001234561f00000155ca8b46")
RXE_WRITE = bytes.fromhex(
    "b8830367c5d08af3fbb9753108004500007c8ee9400040110960c6120b02c6120b01"
    "cdda12b7006800000a00ffff000000c5801234560000652eec1010000017a49300000040"
    "5ad95cd356d548cf42c144fb7efd70f76ae96ce366e5189f1291148b0e8d00873a"
    "b93cb336b528af22a1245bde5dd057ca49cc43c645f87ff271f46bee6de0673c4d0588")
CX_ACK = bytes.fromhex(
    "8af3fbb97531b8830367c5d00800450200300f8740004011890cc6120b01c6120b02"
    "cdda12b7001c00001140ffff00000012001234580000000338ee4174")


class WireTests(unittest.TestCase):
    def parameters(self, payload=b"test"):
        return dict(source_mac="b8:83:03:67:c5:d0", destination_mac="8a:f3:fb:b9:75:31",
                    source_ip="198.18.11.1", destination_ip="198.18.11.2",
                    udp_source_port=52484, destination_qpn=17, psn=0x123456,
                    remote_address=0x615EB7C6B000, rkey=0x214, payload=payload,
                    identification=0x0F70, tos=2, bth_flags=0x40)

    def test_independent_observed_frames(self):
        for frame, operation in ((CX_WRITE, "WRITE_ONLY"), (RXE_WRITE, "WRITE_ONLY"),
                                 (CX_ACK, "ACK"), (RXE_ACK, "ACK")):
            with self.subTest(operation=operation, frame=frame[:6]):
                p = decode_ethernet(frame)
                self.assertEqual(p["operation"], operation)
                self.assertTrue(p["icrc_valid"])
                self.assertEqual(internet_checksum(frame[14:34]), 0)
        self.assertEqual(decode_ethernet(RXE_WRITE)["rkey"], "0x0017a493")

    def test_exact_rnic_write_reproduction(self):
        payload = bytes(((i * 131) ^ (i >> 8) ^ 0x5A) & 255 for i in range(64))
        self.assertEqual(write_only_frame(**self.parameters(payload)), CX_WRITE)

    def test_hls_probe_input_vector(self):
        source = (pathlib.Path(__file__).resolve().parents[1] / "hls/probe/test_rx_write.cpp").read_text()
        literal = source.split("auto packet = unhex(", 1)[1].split(");", 1)[0]
        packet = bytes.fromhex("".join(re.findall(r'"([0-9a-f]+)"', literal)))
        decoded = decode_ethernet(CX_WRITE[:14] + packet)
        self.assertTrue(decoded["icrc_valid"])
        self.assertEqual(decoded["destination_qpn"], 2)
        self.assertEqual(decoded["payload_bytes"], 64)

    def test_lengths_padding_and_widths(self):
        for size in (1, 2, 3, 4, 63, 64, 65, 4095, 4096):
            with self.subTest(size=size):
                params = self.parameters(bytes(i & 255 for i in range(size)))
                params.update(rkey=0xFEDCBA98, remote_address=0xFEDCBA9876543210,
                              psn=0xFFFFFF, destination_qpn=0xABCDEF)
                p = decode_ethernet(write_only_frame(**params))
                self.assertTrue(p["icrc_valid"])
                self.assertEqual(p["payload_bytes"], size)
                self.assertEqual(p["pad_bytes"], (-size) & 3)
                self.assertEqual(p["dma_length"], size)
                self.assertEqual(p["rkey"], "0xfedcba98")
                self.assertEqual(p["remote_address"], "0xfedcba9876543210")
                self.assertEqual(p["psn"], 0xFFFFFF)

    def test_invariant_masks(self):
        # IP TOS/TTL/checksum, UDP checksum, BTH resv8a must not affect ICRC.
        for index in (15, 22, 24, 25, 40, 41, 46):
            changed = bytearray(CX_WRITE)
            changed[index] ^= 0x5A
            self.assertTrue(decode_ethernet(changed)["icrc_valid"], index)

    def test_corruption_detected(self):
        for index in (26, 47, 53, 60, 66, 74, len(CX_WRITE) - 1):
            changed = bytearray(CX_WRITE)
            changed[index] ^= 1
            self.assertFalse(decode_ethernet(changed)["icrc_valid"], index)

    def test_truncation_rejected(self):
        for length in (0, 13, 30, 50, len(CX_WRITE) - 1):
            with self.subTest(length=length), self.assertRaises(ValueError):
                decode_ethernet(CX_WRITE[:length])

    def test_fragment_rejected(self):
        changed = bytearray(CX_WRITE)
        changed[20] |= 0x20
        with self.assertRaises(ValueError):
            decode_ethernet(changed)

    def test_generator_rejects_invalid_widths(self):
        for field, value in (("psn", 0x1000000), ("destination_qpn", -1),
                             ("rkey", 0x100000000), ("payload", b""),
                             ("remote_address", 1 << 64), ("payload", b"x" * 4097)):
            params = self.parameters()
            params[field] = value
            with self.subTest(field=field, value=str(value)[:30]), self.assertRaises(ValueError):
                write_only_frame(**params)


if __name__ == "__main__":
    unittest.main()
