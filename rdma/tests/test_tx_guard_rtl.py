#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Admission/SFD-tail guard RTL unit tests; not a MAC/hardware drain proof."""
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
TB = r'''
`timescale 1ns / 1ps
module tb;
reg clk=0; always #2 clk=~clk;
reg rst=1,halt=0,cpl=0,sv=0,sl=0,mr=0;
reg [127:0] sd=0;
wire sr,mv,ml,quiet,fault;
wire [127:0] md;
wire [15:0] mk;
wire [2:0] pending;
wire [31:0] admitted,completed;
integer cycle=0,input_words=0,output_words=0,out_frames=0,stalls=0,last_cpl=0;
integer first_out=0,last_out=0;
integer i;
reg held_valid=0;
reg [144:0] held;
rocev2_tx_guard #(.PENDING_WIDTH(3)) dut (
 .clk(clk),.rst(rst),.halt(halt),.completion(cpl),
 .s_axis_tdata(sd),.s_axis_tkeep(16'hffff),.s_axis_tvalid(sv),.s_axis_tready(sr),.s_axis_tlast(sl),
 .m_axis_tdata(md),.m_axis_tkeep(mk),.m_axis_tvalid(mv),.m_axis_tready(mr),.m_axis_tlast(ml),
 .quiescent(quiet),.fault(fault),.pending_frames(pending),.admitted_frames(admitted),.completed_frames(completed));
always @(posedge clk) if(!rst) begin
 cycle=cycle+1;
 if(sv && sr) input_words=input_words+1;
 if(held_valid && (!mv || {ml,mk,md}!==held)) $fatal(1,"output changed under stall/halt");
 held_valid=mv && !mr; held={ml,mk,md}; if(held_valid) stalls=stalls+1;
 if(mv && mr) begin
  if(md!=={4{output_words}} || mk!==16'hffff) $fatal(1,"data/order changed");
  output_words=output_words+1; if(ml) out_frames=out_frames+1;
  if(first_out==0) first_out=cycle; last_out=cycle;
 end
 if(cpl) last_cpl=cycle;
 if(quiet && (pending!=0 || mv || fault || (completed!=0 && cycle-last_cpl<1024))) $fatal(1,"premature quiescence");
 if(cycle>20000) $fatal(1,"deadline");
end
task word;
 input integer index;
 input last;
 begin
  @(negedge clk); sd={4{index}}; sl=last; sv=1;
  @(posedge clk); while(!sr) @(posedge clk);
  @(negedge clk); sv=0;
 end
endtask
task complete;
 begin @(negedge clk); cpl=1; @(negedge clk); cpl=0; end
endtask
task drained;
 begin
  while(!quiet) @(negedge clk);
  if(pending!=0 || admitted!=completed || fault) $fatal(1,"bad drain counters");
 end
endtask
initial begin
 repeat(8) @(negedge clk); rst=0;
 if(SCENARIO==0) begin
  word(0,0);
  fork
   begin for(i=1;i<8;i=i+1) word(i,i==7); end
   begin
    repeat(4) @(negedge clk); halt=1;
    repeat(12) @(negedge clk); if(!mv || sr) $fatal(1,"stalled admission");
    mr=1;
   end
  join
  repeat(50) @(negedge clk);
  if(quiet || pending!=1 || out_frames!=1) $fatal(1,"missing completion inferred");
  complete(); drained();
  // New frame stays blocked until explicitly resumed, including a valid
  // first beat waiting while the previous run becomes quiescent.
  sd={4{32'd8}}; sl=0; sv=1;
  repeat(16) @(negedge clk);
  if(sr || input_words!=8 || output_words!=8) $fatal(1,"new frame admitted under halt");
  halt=0; @(posedge clk); while(!sr) @(posedge clk);
  @(negedge clk); sv=0; halt=1;
  // Early SFD completion for an 8192-byte frame; its tail must still wait.
  fork
   begin for(i=9;i<520;i=i+1) word(i,i==519); end
   begin complete(); end
  join
  drained();
  if(admitted!=2 || completed!=2 || output_words!=520 || out_frames!=2 || !stalls)
   $fatal(1,"incomplete normal coverage");
 end else if(SCENARIO==1) begin
  halt=1; complete(); repeat(1100) @(negedge clk);
  if(!fault || quiet || pending!=0) $fatal(1,"unexpected completion not fail-closed");
 end else if(SCENARIO==2) begin
  mr=1;
  for(i=0;i<513;i=i+1) word(i,i==512);
  halt=1; complete(); repeat(1100) @(negedge clk);
  if(!fault || quiet || out_frames!=1 || output_words!=513) $fatal(1,"oversize not fail-closed");
 end else if(SCENARIO==3) begin
  mr=1;
  for(i=0;i<7;i=i+1) word(i,1);
  @(negedge clk); sd={4{32'd7}}; sl=1; sv=1;
  repeat(12) @(negedge clk);
  if(sr || pending!=7 || input_words!=7) $fatal(1,"pending overflow");
  complete();
  @(negedge clk); while(input_words!=8) @(negedge clk); sv=0; halt=1;
  for(i=0;i<7;i=i+1) complete();
  drained();
  if(admitted!=8 || completed!=8 || out_frames!=8) $fatal(1,"capacity recovery");
 end else if(SCENARIO==4) begin
  mr=1; word(0,1); halt=1; repeat(2200) @(negedge clk);
  if(quiet || pending!=1 || fault) $fatal(1,"lost completion falsely drained");
 end else begin
  mr=1;
  for(i=0;i<512;i=i+1) begin
   @(negedge clk); sd={4{i}}; sl=i==511; sv=1;
   @(posedge clk); while(!sr) @(posedge clk);
  end
  @(negedge clk); sv=0; halt=1;
  complete(); drained();
  if(output_words!=512 || last_out-first_out!=511 || stalls!=0)
   $fatal(1,"guard introduced steady-state bubbles");
 end
 $display("RESULT {\"pass_test\":true,\"scenario\":%0d,\"cycles\":%0d,\"admitted_frames\":%0d,\"completed_frames\":%0d,\"output_words\":%0d,\"output_frames\":%0d,\"output_stalls\":%0d,\"fault\":%0d}",SCENARIO,cycle,admitted,completed,output_words,out_frames,stalls,fault);
 $finish;
end
endmodule
'''


@unittest.skipUnless(shutil.which("iverilog") and shutil.which("vvp"), "Icarus Verilog required")
class TxGuardRTLTests(unittest.TestCase):
    def test_admission_tail_capacity_and_fail_closed(self):
        cases = []
        source = ROOT / "rdma/rtl/rocev2_tx_guard.v"
        for scenario in range(6):
            with self.subTest(scenario=scenario), tempfile.TemporaryDirectory(prefix="as02-tx-guard-") as tmp:
                path = pathlib.Path(tmp)
                (path / "tb.v").write_text(TB.replace("SCENARIO", str(scenario)))
                subprocess.run(["iverilog", "-g2012", "-s", "tb", "-o", str(path / "test.vvp"),
                                str(path / "tb.v"), str(source)], check=True, capture_output=True, text=True, timeout=30)
                result = subprocess.run(["vvp", str(path / "test.vvp")],
                                        capture_output=True, text=True, timeout=30)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertNotIn("ERROR:", result.stdout + result.stderr)
                records = [json.loads(line[7:]) for line in result.stdout.splitlines() if line.startswith("RESULT ")]
                self.assertEqual(len(records), 1)
                self.assertTrue(records[0]["pass_test"])
                cases.append(records[0])
        self.assertEqual(len(cases), 6, "never publish a partial subtest run as complete")
        record = dict(evidence_type="transmit admission/SFD-tail RTL unit simulation, not integrated MAC or hardware",
                      complete=True, hardware_verified=False, integrated_mac_drain_verified=False,
                      tail_cycles=1024, core_clock_hz=250000000, minimum_line_rate_gbit_s=25,
                      maximum_ipv4_bytes=8192, cases=cases,
                      source_sha256={source.name: hashlib.sha256(source.read_bytes()).hexdigest()},
                      test_sha256=hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest())
        print(json.dumps(record, indent=2))
        if os.environ.get("AS02_TX_GUARD_REPORT"):
            pathlib.Path(os.environ["AS02_TX_GUARD_REPORT"]).write_text(json.dumps(record, indent=2) + "\n")


if __name__ == "__main__":
    unittest.main()
