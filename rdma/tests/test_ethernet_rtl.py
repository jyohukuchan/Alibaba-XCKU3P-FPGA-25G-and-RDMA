#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""128-bit board-boundary framing, peer/QP isolation and NIC coexistence.

No hardware access. This is deliberately not an ICRC or RDMA completion test.
The Ethernet RX's RoCE output must still pass the integrity/transport wrapper.
"""
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
from rocev2_wire import icrc_ipv4, write_only_frame
from test_wire import CX_ACK

LOCAL_MAC = "8a:f3:fb:b9:75:31"
PEER_MAC = "b8:83:03:67:c5:d0"


def ack(qpn=2):
    frame = bytearray(CX_ACK)
    frame[47:50] = qpn.to_bytes(3, "big")
    frame[-4:] = icrc_ipv4(frame[14:])
    return bytes(frame)


def write(size, sequence=0):
    return write_only_frame(source_mac=LOCAL_MAC, destination_mac=PEER_MAC,
                            source_ip="198.18.11.2", destination_ip="198.18.11.1",
                            udp_source_port=49152, destination_qpn=123,
                            psn=sequence, remote_address=0x123456780000 + sequence * 4096,
                            rkey=0xFEDCBA98, payload=bytes(i & 255 for i in range(size)))


def pack_words(data, user=0, error_beat=None, hole_beat=None):
    result = []
    for beat, offset in enumerate(range(0, len(data), 16)):
        chunk = data[offset:offset + 16]
        keep = (1 << len(chunk)) - 1
        if beat == hole_beat:
            keep ^= 1 << 4
        sideband = user | int(beat == error_beat)
        result.append(int.from_bytes(chunk.ljust(16, b"\0"), "little") |
                      (keep << 128) | (int(offset + 16 >= len(data)) << 144) |
                      (sideband << 145))
    return result


RX_TB = r'''
`timescale 1ns / 1ps
module tb;
reg clk=0; always #2 clk=~clk;
reg rst=0;
reg [127:0] sd=0;
reg [15:0] sk=0;
reg sv=0,sl=0;
reg [96:0] su=0;
reg enable=0;
reg [23:0] qpn=0;
wire sr;
wire [127:0] hd,rd;
wire [15:0] hk,rk;
wire hv,hl,rv,rl,ru;
wire [96:0] hu;
reg hr=0,rr=0;
wire [31:0] hosts,roces,drops,overflows;
rocev2_ethernet_rx dut (
 .clk(clk),.rst(rst),.enable(enable),.local_mac(48'h8af3fbb97531),.peer_mac(48'hb8830367c5d0),
 .local_ip(32'hc6120b02),.peer_ip(32'hc6120b01),.local_qpn(qpn),
 .s_axis_tdata(sd),.s_axis_tkeep(sk),.s_axis_tvalid(sv),.s_axis_tready(sr),.s_axis_tlast(sl),.s_axis_tuser(su),
 .m_axis_host_tdata(hd),.m_axis_host_tkeep(hk),.m_axis_host_tvalid(hv),.m_axis_host_tready(hr),.m_axis_host_tlast(hl),.m_axis_host_tuser(hu),
 .m_axis_roce_tdata(rd),.m_axis_roce_tkeep(rk),.m_axis_roce_tvalid(rv),.m_axis_roce_tready(rr),.m_axis_roce_tlast(rl),.m_axis_roce_tuser(ru),
 .host_frame_count(hosts),.roce_frame_count(roces),.drop_frame_count(drops),.overflow_count(overflows));
reg [266:0] inputs[0:N_INPUT-1];
reg [241:0] expected_host[0:N_HOST-1];
reg [145:0] expected_roce[0:N_ROCE-1];
integer cycle=0,index=0,accepted=0,host_index=0,roce_index=0,quiet=0,lane;
integer input_stalls=0,host_stalls=0,roce_stalls=0;
reg input_accepted=0,host_stalled=0,roce_stalled=0;
reg [241:0] host_held;
reg [145:0] roce_held;
reg [31:0] rng=32'h1e7a52f9;
initial begin
 $readmemh("inputs.hex",inputs); $readmemh("host.hex",expected_host); $readmemh("roce.hex",expected_roce);
 #1 rst=1; repeat(8) @(negedge clk); rst=0;
end
always @(negedge clk) if(!rst) begin
 rng={rng[30:0],rng[31]^rng[21]^rng[1]^rng[0]};
 hr=cycle>3000 && rng[2:0]!=0;
 rr=cycle>3500 && rng[5:3]!=0;
 if(!sv || input_accepted) begin
  sv=0;
  if(index<N_INPUT && rng[8:6]!=0) begin
   {qpn,enable,su,sl,sk,sd}=inputs[index]; sv=1; index=index+1;
  end
 end
end
always @(posedge clk) if(!rst) begin
 cycle=cycle+1; input_accepted=sv && sr;
 if(input_accepted) accepted=accepted+1;
 if(sv && !sr) input_stalls=input_stalls+1;
 if(hv && !hr) host_stalls=host_stalls+1;
 if(rv && !rr) roce_stalls=roce_stalls+1;
 if(host_stalled && (!hv || {hu,hl,hk,hd}!==host_held)) $fatal(1,"host output changed while stalled");
 if(roce_stalled && (!rv || {ru,rl,rk,rd}!==roce_held)) $fatal(1,"RoCE output changed while stalled");
 host_stalled=hv && !hr; host_held={hu,hl,hk,hd};
 roce_stalled=rv && !rr; roce_held={ru,rl,rk,rd};
 if(hv && hr) begin
  if(host_index>=N_HOST) $fatal(1,"unexpected host packet");
  if({hu,hl,hk}!==expected_host[host_index][241:128]) $fatal(1,"host metadata mismatch at %0d",host_index);
  for(lane=0;lane<16;lane=lane+1) if(hk[lane] && hd[lane*8+:8]!==expected_host[host_index][lane*8+:8])
   $fatal(1,"host byte mismatch at word=%0d lane=%0d",host_index,lane);
  host_index=host_index+1;
 end
 if(rv && rr) begin
  if(roce_index>=N_ROCE) $fatal(1,"untrusted frame leaked into transport");
  if({ru,rl,rk}!==expected_roce[roce_index][145:128]) $fatal(1,"RoCE metadata mismatch at %0d",roce_index);
  for(lane=0;lane<16;lane=lane+1) if(rk[lane] && rd[lane*8+:8]!==expected_roce[roce_index][lane*8+:8])
   $fatal(1,"RoCE byte mismatch at word=%0d lane=%0d",roce_index,lane);
  roce_index=roce_index+1;
 end
 if(accepted==N_INPUT && host_index==N_HOST && roce_index==N_ROCE &&
    hosts==HOST_FRAMES && roces==ROCE_FRAMES && drops==DROP_FRAMES && overflows==OVERFLOW_FRAMES) quiet=quiet+1;
 else quiet=0;
 if(quiet==50) begin
  if(!input_stalls || !host_stalls || !roce_stalls) $fatal(1,"missing backpressure coverage");
  $display("RESULT {\"cycles\":%0d,\"input_beats\":%0d,\"host_beats\":%0d,\"roce_beats\":%0d,\"host_frames\":%0d,\"roce_frames\":%0d,\"dropped_frames\":%0d,\"oversize_fifo_drops\":%0d,\"input_stalls\":%0d,\"host_stalls\":%0d,\"roce_stalls\":%0d}",cycle,accepted,host_index,roce_index,hosts,roces,drops,overflows,input_stalls,host_stalls,roce_stalls);
  $finish;
 end
 if(cycle>100000) $fatal(1,"deadline in=%0d host=%0d roce=%0d counts=%0d/%0d/%0d overflow=%0d",accepted,host_index,roce_index,hosts,roces,drops,overflows);
end
endmodule
'''

TX_TB = r'''
`timescale 1ns / 1ps
module tb;
reg clk=0; always #2 clk=~clk;
reg rst=0;
reg [127:0] hd=0,rd=0;
reg [15:0] hk=0,rk=0;
reg hv=0,hl=0,rv=0,rl=0;
reg [16:0] hu=0;
wire hr,rr;
wire [127:0] md;
wire [15:0] mk;
wire mv,ml;
wire [16:0] mu;
reg mr=0;
reg [15:0] ct=0;
reg [95:0] cs=0;
reg cv=0;
wire cr;
wire [15:0] hct;
wire [95:0] hcs;
wire hcv;
reg hcr=0;
wire [31:0] roces,cpls;
rocev2_ethernet_tx dut (
 .clk(clk),.rst(rst),.local_mac(48'h8af3fbb97531),.peer_mac(48'hb8830367c5d0),
 .s_axis_roce_tdata(rd),.s_axis_roce_tkeep(rk),.s_axis_roce_tvalid(rv),.s_axis_roce_tready(rr),.s_axis_roce_tlast(rl),
 .s_axis_host_tdata(hd),.s_axis_host_tkeep(hk),.s_axis_host_tvalid(hv),.s_axis_host_tready(hr),.s_axis_host_tlast(hl),.s_axis_host_tuser(hu),
 .m_axis_tdata(md),.m_axis_tkeep(mk),.m_axis_tvalid(mv),.m_axis_tready(mr),.m_axis_tlast(ml),.m_axis_tuser(mu),
 .s_axis_cpl_tag(ct),.s_axis_cpl_ts(cs),.s_axis_cpl_valid(cv),.s_axis_cpl_ready(cr),
 .m_axis_host_cpl_tag(hct),.m_axis_host_cpl_ts(hcs),.m_axis_host_cpl_valid(hcv),.m_axis_host_cpl_ready(hcr),
 .roce_frame_count(roces),.roce_completion_count(cpls));
reg [161:0] hosts[0:N_HOST-1];
reg [144:0] roces_in[0:N_ROCE_IN-1];
reg [144:0] roces_out[0:N_ROCE_OUT-1];
reg [111:0] cpl_in[0:N_CPL-1];
reg [111:0] cpl_out[0:N_HOST_CPL-1];
integer cycle=0,hi=0,ri=0,ci=0,ha=0,ra=0,ca=0,ho=0,ro=0,co=0,quiet=0,lane;
integer host_stalls=0,roce_stalls=0,output_stalls=0,cpl_stalls=0;
integer first_output=-1,last_output=-1;
reg host_accepted=0,roce_accepted=0,cpl_accepted=0,stalled=0,cpl_stalled=0;
reg [161:0] held;
reg [111:0] cpl_held;
reg [31:0] rng=32'h17a861f3;
reg frame_active=0,frame_host=0;
initial begin
 $readmemh("host.hex",hosts); $readmemh("roce_in.hex",roces_in); $readmemh("roce_out.hex",roces_out);
 $readmemh("cpl_in.hex",cpl_in); $readmemh("cpl_out.hex",cpl_out);
 #1 rst=1; repeat(8) @(negedge clk); rst=0;
end
always @(negedge clk) if(!rst) begin
 rng={rng[30:0],rng[31]^rng[21]^rng[1]^rng[0]};
 mr=THROUGHPUT || (cycle>3000 && rng[2:0]!=0);
 hcr=cycle>500 && rng[5:3]!=0;
 if(!hv || host_accepted) begin
  hv=0;
  if(hi<N_HOST && (THROUGHPUT || rng[8:6]!=0)) begin {hu,hl,hk,hd}=hosts[hi]; hv=1; hi=hi+1; end
 end
 if(!rv || roce_accepted) begin
  rv=0;
  if(ri<N_ROCE_IN && (THROUGHPUT || rng[11:9]!=0)) begin {rl,rk,rd}=roces_in[ri]; rv=1; ri=ri+1; end
 end
 if(!cv || cpl_accepted) begin
  cv=0;
  if(ci<N_CPL && rng[14:12]!=0) begin {ct,cs}=cpl_in[ci]; cv=1; ci=ci+1; end
 end
end
always @(posedge clk) if(!rst) begin
 cycle=cycle+1;
 host_accepted=hv && hr; roce_accepted=rv && rr; cpl_accepted=cv && cr;
 if(host_accepted) ha=ha+1; if(roce_accepted) ra=ra+1; if(cpl_accepted) ca=ca+1;
 if(hv && !hr) host_stalls=host_stalls+1;
 if(rv && !rr) roce_stalls=roce_stalls+1;
 if(mv && !mr) output_stalls=output_stalls+1;
 if(hcv && !hcr) cpl_stalls=cpl_stalls+1;
 if(stalled && (!mv || {mu,ml,mk,md}!==held)) $fatal(1,"TX output changed while stalled");
 stalled=mv && !mr; held={mu,ml,mk,md};
 if(cpl_stalled && (!hcv || {hct,hcs}!==cpl_held)) $fatal(1,"host completion changed while stalled");
 cpl_stalled=hcv && !hcr; cpl_held={hct,hcs};
 if(hcv && hcr) begin
  if(co>=N_HOST_CPL || {hct,hcs}!==cpl_out[co]) $fatal(1,"wrong host completion / injected completion leaked");
  co=co+1;
 end
 if(mv && mr) begin
  if(frame_active && mu[16]!==frame_host) $fatal(1,"frames interleaved");
  frame_host=mu[16]; frame_active=!ml;
  if(frame_host) begin
   if(ho>=N_HOST || {mu,ml,mk}!==hosts[ho][161:128]) $fatal(1,"host TX metadata mismatch word=%0d",ho);
   for(lane=0;lane<16;lane=lane+1) if(mk[lane] && md[lane*8+:8]!==hosts[ho][lane*8+:8])
    $fatal(1,"host TX data mismatch word=%0d lane=%0d",ho,lane);
   ho=ho+1;
  end else begin
   if(ro>=N_ROCE_OUT || mu!==0 || {ml,mk}!==roces_out[ro][144:128]) $fatal(1,"RoCE TX metadata mismatch word=%0d",ro);
   for(lane=0;lane<16;lane=lane+1) if(mk[lane] && md[lane*8+:8]!==roces_out[ro][lane*8+:8])
    $fatal(1,"RoCE TX data mismatch word=%0d lane=%0d actual=%h expected=%h",ro,lane,md,roces_out[ro][127:0]);
   ro=ro+1;
   if(first_output<0) first_output=cycle;
   last_output=cycle;
  end
 end
 if(ha==N_HOST && ra==N_ROCE_IN && ca==N_CPL && ho==N_HOST && ro==N_ROCE_OUT && co==N_HOST_CPL && roces==ROCE_FRAMES && cpls==FILTERED_CPLS) quiet=quiet+1;
 else quiet=0;
 if(quiet==50) begin
  if(!THROUGHPUT && (!host_stalls || !roce_stalls || !output_stalls || !cpl_stalls)) $fatal(1,"missing stall coverage");
  $display("RESULT {\"cycles\":%0d,\"host_beats\":%0d,\"roce_input_beats\":%0d,\"roce_output_beats\":%0d,\"roce_frames\":%0d,\"filtered_completions\":%0d,\"host_completions\":%0d,\"host_stalls\":%0d,\"roce_stalls\":%0d,\"output_stalls\":%0d,\"completion_stalls\":%0d,\"first_output\":%0d,\"last_output\":%0d}",cycle,ho,ra,ro,roces,cpls,co,host_stalls,roce_stalls,output_stalls,cpl_stalls,first_output,last_output);
  $finish;
 end
 if(cycle>100000) $fatal(1,"deadline host=%0d/%0d roce=%0d/%0d completions=%0d",ha,ho,ra,ro,co);
end
endmodule
'''


class EthernetRTLTests(unittest.TestCase):
    reports = {}

    @classmethod
    def tearDownClass(cls):
        if target := os.environ.get("AS02_ETH_RTL_REPORT"):
            sources = [ROOT / "rdma/rtl/rocev2_ethernet_rx.v", ROOT / "rdma/rtl/rocev2_ethernet_tx.v"]
            record = dict(evidence_type="Ethernet application boundary RTL simulation, not hardware",
                          hardware_verified=False, complete=len(cls.reports) == 3, tests=cls.reports,
                          source_sha256={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
                          test_sha256=hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest())
            destination = pathlib.Path(target)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(json.dumps(record, indent=2) + "\n")

    def simulate(self, tb, constants, files, rx):
        self.assertIsNotNone(shutil.which("iverilog"), "install iverilog")
        for name, value in sorted(constants.items(), key=lambda item: -len(item[0])):
            tb = tb.replace(name, str(value))
        with tempfile.TemporaryDirectory(prefix="as02-ethernet-rtl-") as directory:
            path = pathlib.Path(directory)
            (path / "tb.v").write_text(tb)
            for name, values in files.items():
                (path / name).write_text("".join(f"{v:x}\n" for v in values))
            axis = ROOT / "external/corundum/fpga/lib/axis/rtl"
            eth = ROOT / "external/corundum/fpga/lib/eth/rtl"
            sources = [ROOT / f"rdma/rtl/rocev2_ethernet_{'rx' if rx else 'tx'}.v"]
            sources += [eth / f"eth_axis_{'rx' if rx else 'tx'}.v"]
            sources += [axis / "axis_fifo.v"] if rx else [axis / name for name in ("axis_arb_mux.v", "arbiter.v", "priority_encoder.v")]
            compiled = subprocess.run(["iverilog", "-g2012", "-s", "tb", "-o", str(path / "test.vvp"),
                                       str(path / "tb.v"), *map(str, sources)], capture_output=True, text=True, timeout=30)
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            result = subprocess.run(["vvp", str(path / "test.vvp")], cwd=path,
                                    capture_output=True, text=True, timeout=45)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertNotIn("ERROR:", result.stdout + result.stderr)
            records = [line[7:] for line in result.stdout.splitlines() if line.startswith("RESULT ")]
            self.assertEqual(len(records), 1, result.stdout)
            return json.loads(records[0])

    def test_rx_peer_qp_guards_and_host_preservation(self):
        inputs, hosts, roces = [], [], []
        counts = dict(HOST_FRAMES=0, ROCE_FRAMES=0, DROP_FRAMES=0, OVERFLOW_FRAMES=0)

        def add(frame, route, user=0, enabled=True, qpn=2, error=None, hole=None, change_midframe=False):
            packed = pack_words(frame, user, error, hole)
            for index, value in enumerate(packed):
                # Deliberately change enable/QPN after SOP: route must use the
                # saved configuration, not a mixture of control snapshots.
                cfg_enable = enabled and not (change_midframe and index > 0)
                cfg_qpn = qpn if not change_midframe or index == 0 else 7
                inputs.append(value | (int(cfg_enable) << 242) | (cfg_qpn << 243))
            counts[f"{route}_FRAMES"] += 1
            if route == "HOST":
                hosts.extend(packed)
            elif route == "ROCE":
                roces.extend(pack_words(frame[14:]))
            if len(packed) > 1024:
                counts["OVERFLOW_FRAMES"] += 1

        # Fill the route queue before releasing host ready; preserve high PTP
        # sideband bits and error bit on ordinary traffic, not just its bytes.
        for i in range(50):
            ordinary = bytes(range(12)) + b"\x08\x06" + bytes([i]) * 46
            add(ordinary, "HOST", user=(0x123456780000000000000000 + i) << 1,
                error=1 if i % 4 == 0 else None)
        add(ack(), "ROCE", change_midframe=True)
        rejected = []
        for offset in (0, 6, 26, 30, 47, 48, 49):
            changed = bytearray(ack()); changed[offset] ^= 1
            rejected.append((bytes(changed), None, None, 2))
        changed = bytearray(ack()); changed[42] = 0x0A  # no unprotected inbound WRITE
        rejected.append((bytes(changed), None, None, 2))
        rejected += [(ack(), 0, None, 2), (ack(), 2, None, 2), (ack(), 3, None, 2),
                     (ack(), None, 1, 2), (ack(), None, 3, 2),
                     (ack(8), None, None, 8), (ack()[:48], None, None, 2)]
        for frame, error, hole, qpn in rejected:
            add(frame, "DROP", error=error, hole=hole, qpn=qpn)
            add(ack(), "ROCE")
        # Disabled engine must leave RoCE traffic available to the host.
        add(ack(), "HOST", enabled=False, user=0x123456789 << 1)
        add(ack(100), "HOST", enabled=False, error=0)
        # Non-RoCE UDP / TCP / IPv6 / VLAN remain host traffic, unmodified.
        for offset, value in ((37, 1), (23, 6), (12, 0x86)):
            changed = bytearray(ack()); changed[offset] = value
            add(bytes(changed), "HOST")
        vlan = ack()[:12] + b"\x81\x00\x00\x01" + ack()[12:]
        add(vlan, "HOST")
        for length in (9215, 16384, 16400, 65552):
            add(ack().ljust(length, b"\0"), "DROP")
            add(ack(), "ROCE")
        result = self.simulate(RX_TB, dict(N_INPUT=len(inputs), N_HOST=len(hosts), N_ROCE=len(roces), **counts),
                               {"inputs.hex": inputs, "host.hex": hosts, "roce.hex": roces}, True)
        self.reports[self._testMethodName] = dict(**result, pass_test=True,
                                                crc_validation="downstream integrity block, not this classifier")

    def run_tx(self, payloads, throughput=False):
        # Payloads include real RoCE frames and arbitrary lengths that exercise
        # every header-shift boundary. The latter are framing tests only.
        hosts = []
        if not throughput:
            for i in range(24):
                frame = bytes(range(12)) + b"\x08\x06" + bytes([i]) * (46 + i * 17)
                hosts += pack_words(frame, user=((0x8000 | i) << 1) | (i & 1))
        else:
            # One trailing host frame keeps fixture arrays nonempty without
            # changing the engine's long-packet cycle-capacity conclusion.
            hosts = pack_words(bytes(range(60)), user=0x10000)
        header = bytes.fromhex(PEER_MAC.replace(":", "") + LOCAL_MAC.replace(":", "") + "0800")
        r_in = [word for p in payloads for word in pack_words(p)]
        r_out = [word for p in payloads for word in pack_words(header + p)]
        tags = [0, 0x8000, 0x7FFF, 0x8001, 0xFFFF, 0]
        c_in = [(tag << 96) | (0x123456780000000000000000 + i) for i, tag in enumerate(tags)]
        c_out = [v for v in c_in if v >> 111]
        result = self.simulate(TX_TB, dict(N_HOST=len(hosts), N_ROCE_IN=len(r_in), N_ROCE_OUT=len(r_out),
                                         N_CPL=len(c_in), N_HOST_CPL=len(c_out), ROCE_FRAMES=len(payloads),
                                         FILTERED_CPLS=len(c_in) - len(c_out), THROUGHPUT=int(throughput)),
                               {"host.hex": hosts, "roce_in.hex": r_in, "roce_out.hex": r_out,
                                "cpl_in.hex": c_in, "cpl_out.hex": c_out}, False)
        return result

    def test_tx_framing_arbitration_and_completions(self):
        payloads = [bytes(range(n)) for n in range(1, 34)]
        payloads += [ack()[14:], write(1)[14:], write(64)[14:], write(4096)[14:]]
        result = self.run_tx(payloads)
        self.assertEqual(result["filtered_completions"], 3)
        self.assertEqual(result["host_completions"], 3)
        self.reports[self._testMethodName] = dict(**result, pass_test=True)

    def test_tx_25g_cycle_capacity(self):
        result = self.run_tx([write(4096, i)[14:] for i in range(32)], throughput=True)
        cycles = result["last_output"] - result["first_output"] + 1
        rate = 32 * 4096 * 8 * 250_000_000 / cycles / 1e9
        self.assertGreater(rate, 25)
        self.reports[self._testMethodName] = dict(**result, pass_test=True,
                                                simulated_payload_gbit_s_at_250mhz=rate,
                                                actual_timing_proven=False)


if __name__ == "__main__":
    unittest.main(verbosity=2)
