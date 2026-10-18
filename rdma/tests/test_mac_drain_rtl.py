#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Guard/framer/real MAC + CDC simulation at 250/390.625MHz, not hardware.

Use a whole-frame test FIFO; this does not replace a full mqnic_port_tx test.
The physical XGMII terminator, not a modeled completion, is the drain oracle.
"""
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import tempfile
import unittest
import zlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
TB = r'''
`timescale 1ns / 1ps
module tb;
reg clk=0,mac_clk=0;
always #2 clk=~clk;
always #1.280 mac_clk=~mac_clk;
reg rst=1,halt=1,sv=0,sl=0,tx_enable=0;
reg [127:0] sd=0;
reg [15:0] sk=0;
wire sr,quiet,fault;
wire [127:0] gd,ed;
wire [15:0] gk,ek;
wire gv,gr,gl,ev,er,el;
wire [16:0] eu;
wire [63:0] mac_data,xd;
wire [7:0] mac_keep,xc;
wire mac_valid,mac_ready,mac_last,underflow;
wire [16:0] mac_user;
wire [95:0] ts_mac,ts_core;
wire [15:0] tag_mac,tag_core,pending;
wire cpl_mac,cpl_core,cpl_ready,cpl_fifo_ready;
wire [31:0] admitted,completed;
integer cycle=0,wire_frames=0,last_eof_cycle=0,last_cpl_cycle=0;
integer frame,index,ip_size,beats,j,tail;
reg in_wire=0;
wire tx_overflow,cpl_overflow;
rocev2_tx_guard guard (
 .clk(clk),.rst(rst),.halt(halt),.completion(cpl_core && cpl_ready && !tag_core[15]),
 .s_axis_tdata(sd),.s_axis_tkeep(sk),.s_axis_tvalid(sv),.s_axis_tready(sr),.s_axis_tlast(sl),
 .m_axis_tdata(gd),.m_axis_tkeep(gk),.m_axis_tvalid(gv),.m_axis_tready(gr),.m_axis_tlast(gl),
 .quiescent(quiet),.fault(fault),.pending_frames(pending),.admitted_frames(admitted),.completed_frames(completed));
rocev2_ethernet_tx egress (
 .clk(clk),.rst(rst),.local_mac(48'h8af3fbb97531),.peer_mac(48'hb8830367c5d0),
 .s_axis_roce_tdata(gd),.s_axis_roce_tkeep(gk),.s_axis_roce_tvalid(gv),.s_axis_roce_tready(gr),.s_axis_roce_tlast(gl),
 .s_axis_host_tdata(128'd0),.s_axis_host_tkeep(16'd0),.s_axis_host_tvalid(1'b0),.s_axis_host_tready(),.s_axis_host_tlast(1'b0),.s_axis_host_tuser(17'd0),
 .m_axis_tdata(ed),.m_axis_tkeep(ek),.m_axis_tvalid(ev),.m_axis_tready(er),.m_axis_tlast(el),.m_axis_tuser(eu),
 .s_axis_cpl_tag(tag_core),.s_axis_cpl_ts(ts_core),.s_axis_cpl_valid(cpl_core),.s_axis_cpl_ready(cpl_ready),
 .m_axis_host_cpl_tag(),.m_axis_host_cpl_ts(),.m_axis_host_cpl_valid(),.m_axis_host_cpl_ready(1'b1),
 .roce_frame_count(),.roce_completion_count());
axis_async_fifo_adapter #(
 .DEPTH(16384),.S_DATA_WIDTH(128),.S_KEEP_ENABLE(1),.S_KEEP_WIDTH(16),
 .M_DATA_WIDTH(64),.M_KEEP_ENABLE(1),.M_KEEP_WIDTH(8),.ID_ENABLE(0),.DEST_ENABLE(0),
 .USER_ENABLE(1),.USER_WIDTH(17),.RAM_PIPELINE(0),.FRAME_FIFO(1),
 .DROP_OVERSIZE_FRAME(0),.DROP_BAD_FRAME(0),.DROP_WHEN_FULL(0)
) transmit_cdc (
 .s_clk(clk),.s_rst(rst),.s_axis_tdata(ed),.s_axis_tkeep(ek),.s_axis_tvalid(ev),.s_axis_tready(er),.s_axis_tlast(el),.s_axis_tid(8'd0),.s_axis_tdest(8'd0),.s_axis_tuser(eu),
 .m_clk(mac_clk),.m_rst(rst),.m_axis_tdata(mac_data),.m_axis_tkeep(mac_keep),.m_axis_tvalid(mac_valid),.m_axis_tready(mac_ready),.m_axis_tlast(mac_last),.m_axis_tid(),.m_axis_tdest(),.m_axis_tuser(mac_user),
 .s_pause_req(1'b0),.s_pause_ack(),.m_pause_req(1'b0),.m_pause_ack(),
 .s_status_depth(),.s_status_depth_commit(),.s_status_overflow(tx_overflow),.s_status_bad_frame(),.s_status_good_frame(),
 .m_status_depth(),.m_status_depth_commit(),.m_status_overflow(),.m_status_bad_frame(),.m_status_good_frame());
axis_xgmii_tx_64 #(
 .PTP_PERIOD_NS(4'd2),.PTP_PERIOD_FNS(16'h8f5c),.PTP_TS_ENABLE(1),.PTP_TAG_ENABLE(1),.PTP_TAG_WIDTH(16),.USER_WIDTH(17)
) mac (
 .clk(mac_clk),.rst(rst),.s_axis_tdata(mac_data),.s_axis_tkeep(mac_keep),.s_axis_tvalid(mac_valid),.s_axis_tready(mac_ready),.s_axis_tlast(mac_last),.s_axis_tuser(mac_user),
 .xgmii_txd(xd),.xgmii_txc(xc),.ptp_ts(96'd0),.m_axis_ptp_ts(ts_mac),.m_axis_ptp_ts_tag(tag_mac),.m_axis_ptp_ts_valid(cpl_mac),
 .cfg_ifg(8'd12),.cfg_tx_enable(tx_enable),.start_packet(),.error_underflow(underflow));
axis_async_fifo #(
 .DEPTH(16),.DATA_WIDTH(112),.KEEP_ENABLE(0),.KEEP_WIDTH(1),.LAST_ENABLE(0),.ID_ENABLE(0),.DEST_ENABLE(0),.USER_ENABLE(0),.RAM_PIPELINE(1)
) completion_cdc (
 .s_clk(mac_clk),.s_rst(rst),.s_axis_tdata({tag_mac,ts_mac}),.s_axis_tkeep(1'b1),.s_axis_tvalid(cpl_mac),.s_axis_tready(cpl_fifo_ready),.s_axis_tlast(1'b1),.s_axis_tid(8'd0),.s_axis_tdest(8'd0),.s_axis_tuser(1'b0),
 .m_clk(clk),.m_rst(rst),.m_axis_tdata({tag_core,ts_core}),.m_axis_tkeep(),.m_axis_tvalid(cpl_core),.m_axis_tready(cpl_ready),.m_axis_tlast(),.m_axis_tid(),.m_axis_tdest(),.m_axis_tuser(),
 .s_pause_req(1'b0),.s_pause_ack(),.m_pause_req(1'b0),.m_pause_ack(),
 .s_status_depth(),.s_status_depth_commit(),.s_status_overflow(cpl_overflow),.s_status_bad_frame(),.s_status_good_frame(),
 .m_status_depth(),.m_status_depth_commit(),.m_status_overflow(),.m_status_bad_frame(),.m_status_good_frame());
always @(posedge clk) if(!rst) begin
 cycle=cycle+1;
 if(cycle==200) tx_enable<=1;
 if(cpl_core && cpl_ready) last_cpl_cycle=cycle;
 if(fault || tx_overflow) $fatal(1,"guard/data FIFO fault");
 if(quiet && admitted!=0 && (wire_frames!=admitted || in_wire || cycle-last_cpl_cycle<1024))
  $fatal(1,"guard reset permission preceded actual XGMII EOF/tail");
 if(cycle>10000) $fatal(1,"MAC drain deadline");
end
integer lane;
always @(posedge mac_clk) if(!rst) begin
 if(underflow || cpl_overflow || (cpl_mac && !cpl_fifo_ready)) $fatal(1,"MAC/FIFO loss");
 $display("XGMII %016h %02h",xd,xc);
 for(lane=0;lane<8;lane=lane+1) if(xc[lane]) begin
  if(xd[lane*8+:8]==8'hfb) in_wire=1;
  if(xd[lane*8+:8]==8'hfd && in_wire) begin
   in_wire=0; wire_frames=wire_frames+1; last_eof_cycle=cycle;
  end
 end
end
initial begin
 repeat(8) @(negedge clk); rst=0;
 for(frame=0;frame<3;frame=frame+1) begin
  ip_size=frame==0 ? 48 : frame==1 ? 124 : 8192;
  beats=(ip_size+15)/16; halt=0;
  for(index=0;index<beats;index=index+1) begin
   @(negedge clk);
   for(j=0;j<16;j=j+1) sd[j*8+:8]=(index*16+j)*131+frame*17;
   tail=ip_size-index*16; sk=tail>=16 ? 16'hffff : (17'h1<<tail)-1;
   sv=1; sl=index==beats-1;
   @(posedge clk); while(!sr) @(posedge clk);
   @(negedge clk); sv=0;
   if(index==1) halt=1;
  end
  halt=1;
  while(!quiet) @(negedge clk);
  if(admitted!=frame+1 || completed!=frame+1 || pending!=0 || wire_frames!=frame+1)
   $fatal(1,"missing physical/completion drain");
  if(frame==2 && last_eof_cycle<=last_cpl_cycle) $fatal(1,"long-frame SFD/EOF distinction not exercised");
  $display("DRAIN %0d %0d %0d %0d",frame,last_cpl_cycle,last_eof_cycle,cycle);
 end
 $display("RESULT {\"pass_test\":true,\"wire_frames\":%0d,\"admitted_frames\":%0d,\"completed_frames\":%0d,\"cycles\":%0d,\"mac_underflows\":0}",wire_frames,admitted,completed,cycle);
 $finish;
end
endmodule
'''


@unittest.skipUnless(shutil.which("iverilog") and shutil.which("vvp"), "Icarus Verilog required")
class MacDrainRTLTests(unittest.TestCase):
    def test_actual_mac_eof_after_early_completion(self):
        axis = ROOT / "external/corundum/fpga/lib/axis/rtl"
        eth = ROOT / "external/corundum/fpga/lib/eth/rtl"
        sources = [ROOT / "rdma/rtl/rocev2_tx_guard.v", ROOT / "rdma/rtl/rocev2_ethernet_tx.v"]
        sources += [axis / name for name in ("axis_adapter.v", "axis_arb_mux.v", "axis_async_fifo.v", "axis_async_fifo_adapter.v", "arbiter.v", "priority_encoder.v")]
        sources += [eth / name for name in ("eth_axis_tx.v", "axis_xgmii_tx_64.v", "lfsr.v")]
        with tempfile.TemporaryDirectory(prefix="as02-mac-drain-") as temporary:
            path = pathlib.Path(temporary)
            (path / "tb.v").write_text(TB)
            compiled = subprocess.run(["iverilog", "-g2012", "-s", "tb", "-o", str(path / "test.vvp"),
                                       str(path / "tb.v"), *map(str, sources)], timeout=30, text=True, capture_output=True)
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            result = subprocess.run(["vvp", str(path / "test.vvp")], timeout=30, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stdout[-4000:] + result.stderr)
            self.assertNotIn("ERROR:", result.stdout + result.stderr)
        frames, packet, active, preamble = [], bytearray(), False, False
        for line in result.stdout.splitlines():
            if not line.startswith("XGMII "):
                continue
            _, data, control = line.split()
            for lane, byte in enumerate(int(data, 16).to_bytes(8, "little")):
                if int(control, 16) & (1 << lane):
                    if byte == 0xFB:
                        self.assertFalse(active)
                        active, preamble = True, True
                    elif byte == 0xFD:
                        self.assertTrue(active)
                        frames.append(bytes(packet)); packet.clear(); active = False
                    else:
                        self.assertEqual(byte, 7)
                elif active:
                    if preamble:
                        if byte == 0xD5:
                            preamble = False
                        else:
                            self.assertEqual(byte, 0x55)
                    else:
                        packet.append(byte)
        self.assertFalse(active)
        self.assertEqual(len(frames), 3)
        for index, (frame, size) in enumerate(zip(frames, (48, 124, 8192))):
            expected = bytes.fromhex("b8830367c5d08af3fbb975310800") + bytes((i * 131 + index * 17) & 255 for i in range(size))
            self.assertEqual(frame[:-4], expected)
            self.assertEqual(frame[-4:], zlib.crc32(expected).to_bytes(4, "little"))
        metrics = [json.loads(line[7:]) for line in result.stdout.splitlines() if line.startswith("RESULT ")]
        self.assertEqual(len(metrics), 1)
        drains = [list(map(int, line.split()[1:])) for line in result.stdout.splitlines() if line.startswith("DRAIN ")]
        self.assertEqual(len(drains), 3)
        record = dict(evidence_type="real MAC/XGMII + representative whole-frame CDC simulation, not physical hardware",
                      hardware_verified=False, exact_mqnic_port_tx_verified=False, complete=True,
                      **metrics[0], core_clock_hz=250000000, mac_clock_hz=390625000,
                      wire_payload_bytes=48+124+8192, ethernet_fcs_checked=True, wire_bytes_checked=True,
                      drain_cycles=drains, source_sha256={source.name: hashlib.sha256(source.read_bytes()).hexdigest() for source in sources},
                      test_sha256=hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest())
        print(json.dumps(record, indent=2))
        if os.environ.get("AS02_MAC_DRAIN_REPORT"):
            pathlib.Path(os.environ["AS02_MAC_DRAIN_REPORT"]).write_text(json.dumps(record, indent=2) + "\n")


if __name__ == "__main__":
    unittest.main()
