#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""128-bit RTL integrity-stage tests. No network, hardware or Vivado needed."""
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "rdma/host"))
from rocev2_wire import icrc_ipv4, internet_checksum, write_only_frame
import test_wire as observed


def packet(size, sequence=0):
    payload = bytes(((i * 131) ^ (i >> 8) ^ sequence ^ 0x5A) & 255 for i in range(size))
    return write_only_frame(source_mac="02:00:00:00:00:01", destination_mac="02:00:00:00:00:02",
                            source_ip="198.18.11.1", destination_ip="198.18.11.2",
                            udp_source_port=49152 + sequence % 1000, destination_qpn=2,
                            psn=sequence, remote_address=0x123456780000 + sequence * 4096,
                            rkey=0xFEDCBA98, payload=payload, identification=sequence,
                            tos=sequence & 255)[14:]


def update_ip_checksum(data):
    data = bytearray(data)
    data[10:12] = b"\0\0"
    data[10:12] = internet_checksum(bytes(data[:20])).to_bytes(2, "big")
    return bytes(data)


def words(data, error_beat=None, hole_beat=None):
    result = []
    for beat, offset in enumerate(range(0, len(data), 16)):
        chunk = data[offset:offset + 16]
        keep = (1 << len(chunk)) - 1
        if beat == hole_beat:
            keep ^= 1 << 6
        last = offset + 16 >= len(data)
        result.append(int.from_bytes(chunk.ljust(16, b"\0"), "little") |
                      (keep << 128) | (int(last) << 144) | (int(beat == error_beat) << 145))
    return result


TESTBENCH = r'''
`timescale 1ns / 1ps
module tb;
reg clk=0;
always #2 clk=~clk;
reg rst=1;
reg [127:0] sd=0;
reg [15:0] sk=0;
reg sv=0, sl=0, su=0;
wire sr;
wire [127:0] md;
wire [15:0] mk;
wire mv, ml;
reg mr=0;
wire good, bad, overflow;
rocev2_ipv4_icrc #(.TX_MODE(TX_VALUE)) dut (
 .clk(clk),.rst(rst),.s_axis_tdata(sd),.s_axis_tkeep(sk),.s_axis_tvalid(sv),
 .s_axis_tready(sr),.s_axis_tlast(sl),.s_axis_tuser(su),
 .m_axis_tdata(md),.m_axis_tkeep(mk),.m_axis_tvalid(mv),.m_axis_tready(mr),.m_axis_tlast(ml),
 .status_good_frame(good),.status_bad_frame(bad),.status_overflow(overflow));
reg [145:0] input_words[0:INPUT_COUNT-1];
reg [145:0] expected_words[0:OUTPUT_COUNT-1];
integer cycle=0, index=0, accepted=0, received=0, good_count=0, bad_count=0;
integer in_stalls=0, out_stalls=0, quiet=0, byte_lane;
integer first_output=-1, last_output=-1;
integer header_sum;
integer keep_mask, keep_count, keep_lane;
reg [31:0] rng=32'h74b12e09;
reg was_stalled=0;
reg input_accepted=0;
reg [144:0] stalled_word;
initial begin
 // Exhaustively compare the actual new RTL predicate, not a Python copy,
 // against the old popcount/shift rule. No DUT signals/state are forced.
 for(keep_mask=0;keep_mask<65536;keep_mask=keep_mask+1) begin
  keep_count=0;
  for(keep_lane=0;keep_lane<16;keep_lane=keep_lane+1)
   keep_count=keep_count+((keep_mask>>keep_lane)&1);
  if(dut.valid_keep_prefix(keep_mask[15:0]) !==
       (keep_mask!=0 && keep_mask==((32'd1<<keep_count)-1)))
   $fatal(1,"keep-prefix predicate mismatch at %h",keep_mask);
 end
 // Exhaustively check the actual RTL RX checksum predicate against integer
 // one's-complement arithmetic, including zero and every 21-bit carry case.
 if(!TX_VALUE) for(header_sum=0;header_sum<2097152;header_sum=header_sum+1)
  if(dut.valid_ipv4_sum(header_sum[20:0]) !== (header_sum!=0 && header_sum%65535==0))
   $fatal(1,"IPv4 sum predicate mismatch at %0d",header_sum);
 $readmemh("input.hex",input_words);
 $readmemh("expected.hex",expected_words);
 repeat(5) @(negedge clk);
 rst=0;
end
always @(negedge clk) begin
 if (!rst) begin
  rng={rng[30:0],rng[31]^rng[21]^rng[1]^rng[0]};
  mr=THROUGHPUT_MODE || (cycle>6000 && rng[2:0]!=0);
  if (!sv || input_accepted) begin
   sv=0;
   if (index<INPUT_COUNT && (THROUGHPUT_MODE || rng[7:5]!=0)) begin
    {su,sl,sk,sd}=input_words[index];
    sv=1;
    index=index+1;
   end
  end
 end
end
always @(posedge clk) begin
 if (!rst) begin
  cycle=cycle+1;
  input_accepted=sv && sr;
  if (sv && sr) accepted=accepted+1;
  if (sv && !sr) in_stalls=in_stalls+1;
  if (mv && !mr) out_stalls=out_stalls+1;
  if (was_stalled && (!mv || {ml,mk,md}!==stalled_word)) $fatal(1,"AXIS output changed while stalled");
  was_stalled=mv && !mr;
  stalled_word={ml,mk,md};
  if (good) good_count=good_count+1;
  if (bad) bad_count=bad_count+1;
  if (overflow) $fatal(1,"unexpected packet FIFO overflow");
  if (mv && mr) begin
   if (received>=OUTPUT_COUNT) $fatal(1,"unexpected output / rejected frame leaked");
   if ({ml,mk}!==expected_words[received][144:128])
    $fatal(1,"output shape mismatch word=%0d keep=%h expected=%h last=%b",received,mk,expected_words[received][143:128],ml);
   for(byte_lane=0;byte_lane<16;byte_lane=byte_lane+1)
    if(mk[byte_lane] && md[byte_lane*8+:8]!==expected_words[received][byte_lane*8+:8])
     $fatal(1,"output byte mismatch word=%0d lane=%0d actual=%h expected=%h",received,byte_lane,md,expected_words[received][127:0]);
   if(first_output<0) first_output=cycle;
   last_output=cycle;
   received=received+1;
  end
  if(accepted==INPUT_COUNT && received==OUTPUT_COUNT && good_count==GOOD_COUNT && bad_count==BAD_COUNT) quiet=quiet+1;
  else quiet=0;
  if(quiet==50) begin
   if(!THROUGHPUT_MODE && (in_stalls==0 || out_stalls==0)) $fatal(1,"test did not exercise backpressure");
   $display("RESULT {\"cycles\":%0d,\"input_beats\":%0d,\"output_beats\":%0d,\"good_frames\":%0d,\"bad_frames\":%0d,\"input_stall_cycles\":%0d,\"output_stall_cycles\":%0d,\"first_output\":%0d,\"last_output\":%0d}",cycle,accepted,received,good_count,bad_count,in_stalls,out_stalls,first_output,last_output);
   $finish;
  end
  if(cycle>150000) $fatal(1,"deadline accepted=%0d received=%0d good=%0d bad=%0d",accepted,received,good_count,bad_count);
 end
end
endmodule
'''


class IntegrityRTLTests(unittest.TestCase):
    reports = {}

    @classmethod
    def tearDownClass(cls):
        if target := os.environ.get("AS02_RTL_REPORT"):
            report = dict(evidence_type="integrity-stage RTL simulation, not hardware",
                          complete=len(cls.reports)==3, tests=cls.reports, hardware_verified=False,
                          rtl_sha256=hashlib.sha256((ROOT/"rdma/rtl/rocev2_ipv4_icrc.v").read_bytes()).hexdigest(),
                          test_sha256=hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest())
            path = pathlib.Path(target)
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text(json.dumps(report,indent=2)+"\n")

    def simulate(self, tx, inputs, expected, bad_count, throughput=False):
        self.assertIsNotNone(shutil.which("iverilog"), "install iverilog for RTL tests")
        input_words = [word for data, error, hole in inputs for word in words(data, error, hole)]
        expected_words = [word for data in expected for word in words(data)]
        substitutions = dict(TX_VALUE=int(tx), INPUT_COUNT=len(input_words), OUTPUT_COUNT=len(expected_words),
                             THROUGHPUT_MODE=int(throughput), GOOD_COUNT=len(expected), BAD_COUNT=bad_count)
        testbench = TESTBENCH
        # Replace longest names first, e.g. INPUT_COUNT before GOOD_COUNT.
        for name, value in substitutions.items():
            testbench = testbench.replace(name, str(value))
        with tempfile.TemporaryDirectory(prefix="as02-icrc-rtl-") as directory:
            path = pathlib.Path(directory)
            (path / "tb.v").write_text(testbench)
            (path / "input.hex").write_text("".join(f"{word:037x}\n" for word in input_words))
            (path / "expected.hex").write_text("".join(f"{word:037x}\n" for word in expected_words))
            sources = [ROOT / "rdma/rtl/rocev2_ipv4_icrc.v",
                       ROOT / "external/corundum/fpga/lib/eth/lib/axis/rtl/axis_fifo.v",
                       ROOT / "external/corundum/fpga/lib/eth/lib/axis/rtl/axis_register.v",
                       ROOT / "external/corundum/fpga/lib/eth/rtl/lfsr.v"]
            compiled = subprocess.run(["iverilog", "-g2012", "-s", "tb", "-o", str(path / "test.vvp"),
                                       str(path / "tb.v"), *(str(source) for source in sources)],
                                      capture_output=True, text=True, timeout=30)
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            result = subprocess.run(["vvp", str(path / "test.vvp")], cwd=path,
                                    capture_output=True, text=True, timeout=90)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            record = [line[7:] for line in result.stdout.splitlines() if line.startswith("RESULT ")]
            self.assertEqual(len(record), 1, result.stdout)
            return json.loads(record[0])

    def test_tx_golden_stalls_and_rejection(self):
        sizes = [4096] * 8 + [1, 2, 3, 4, 5, 6, 7, 8, 63, 64, 65, 255, 256, 257, 4095, 4096]
        valid = [packet(size, i) for i, size in enumerate(sizes)]
        inputs, expected = [], []
        for p in valid:
            bare = bytearray(p[:-4])
            bare[10:12] = b"\xdd\xcc"  # TX must repair, not trust, the checksum.
            inputs.append((bytes(bare), None, None))
            expected.append(p)
        invalid = []
        for position, value in ((0, 0x46), (9, 6), (6, 0x60), (23, 0xB8), (25, 0)):
            changed = bytearray(valid[9][:-4])
            changed[position] = value
            invalid.append((bytes(changed), None, None))
        invalid += [(valid[0][:-4], 3, None), (valid[0][:-4], None, 3)]
        for bad in invalid:
            inputs += [bad, (valid[8][:-4], None, None)]
            expected.append(valid[8])
        result = self.simulate(True, inputs, expected, len(invalid))
        self.assertEqual(result["bad_frames"], len(invalid))
        self.reports[self._testMethodName] = dict(**result, pass_test=True, keep_masks_checked=65536)

    def test_rx_whole_frame_integrity_and_stalls(self):
        valid = [packet(4096, i) for i in range(8)]
        valid += [observed.CX_WRITE[14:], observed.RXE_WRITE[14:], observed.CX_ACK[14:], observed.RXE_ACK[14:]]
        valid += [packet(size, 20 + i) for i, size in enumerate((1, 2, 3, 4, 5, 63, 64, 65, 4095))]
        # TTL/TOS are invariant fields, but the real IP header checksum must
        # remain valid. BTH congestion/reserved byte is masked for ICRC too.
        changed = bytearray(valid[8]); changed[8] = 33; changed[1] = 0xA2; changed[32] ^= 0x80
        valid.append(update_ip_checksum(changed))
        inputs = [(p, None, None) for p in valid]
        expected = list(valid)
        invalid = []
        for position in (60, 33, len(valid[0]) - 1, 10):
            changed = bytearray(valid[0]); changed[position] ^= 1
            invalid.append((bytes(changed), None, None))
        wrong_port = bytearray(valid[8]); wrong_port[23] ^= 1
        wrong_port[-4:] = icrc_ipv4(bytes(wrong_port))
        invalid += [(bytes(wrong_port), None, None), (valid[0][:-4], None, None),
                    (valid[0], 4, None), (valid[0], None, 4)]
        for bad in invalid:
            inputs += [bad, (valid[8], None, None)]
            expected.append(valid[8])
        result = self.simulate(False, inputs, expected, len(invalid))
        self.assertEqual(result["bad_frames"], len(invalid))
        self.reports[self._testMethodName] = dict(**result, pass_test=True,
                                                header_sum_values_checked=1 << 21, keep_masks_checked=65536)

    def test_cycle_capacity_above_25g(self):
        packets = [packet(4096, i) for i in range(32)]
        result = self.simulate(True, [(p[:-4], None, None) for p in packets], packets, 0, throughput=True)
        output_cycles = result["last_output"] - result["first_output"] + 1
        payload_gbit_s_at_250mhz = len(packets) * 4096 * 8 / (output_cycles * 4)
        # Units: bits per nanosecond = Gbit/s. This is simulated cycle
        # capacity, NOT achieved device timing or actual link performance.
        self.assertGreater(payload_gbit_s_at_250mhz, 25)
        self.reports[self._testMethodName] = dict(**result, pass_test=True,
            simulated_payload_gbit_s_at_250mhz=payload_gbit_s_at_250mhz, routed_clock_verified=False,
            keep_masks_checked=65536)
        print(f"ICRC RTL simulated payload capacity @250MHz: {payload_gbit_s_at_250mhz:.3f} Gbit/s (not hardware)")


if __name__ == "__main__":
    unittest.main()
