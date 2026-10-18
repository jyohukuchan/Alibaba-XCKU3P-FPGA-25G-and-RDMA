#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Finite command/window control and bounded replayable-memory RTL tests."""
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]

ENGINE_TB = r'''
`timescale 1ns / 1ps
module tb;
localparam MODE=MODE_VALUE;
reg clk=0; always #2 clk=~clk;
reg rst=0,start=0,clear=0,abort_run=0,quiet=1,memory_fault=0;
reg [23:0] lqp=MODE==9 ? 8 : MODE==17 ? 1 : 2;
reg [31:0] size=MODE==14 ? 0 : MODE==7 ? 4097 : MODE==11 ? 8192 : (MODE==13 || MODE==18) ? 4096 : 65;
reg [31:0] count=MODE==8 ? 0 : MODE==12 ? 131072 : MODE==13 ? 65536 : MODE==18 ? 16384 : 9;
reg [31:0] key=32'hfedcba98;
reg [63:0] address=MODE==6 ? 64'hfffffffffffffffe : 64'hfedcba9876543210;
wire [63:0] extent=MODE==5 ? 64'd584 : MODE==13 ? 64'd268435456 : MODE==18 ? 64'd67108864 : 64'd585;
wire ready,core_rst,halt,rx,busy,done,failed;
wire [3:0] state;
wire [31:0] error,issued,acked,dups,total;
wire [63:0] elapsed;
wire [183:0] qp,conn;
wire qv,cv;
wire [239:0] sq;
wire sv;
reg qr=0,cr=0,sr=0;
reg [39:0] ack=0;
reg av=0;
wire ar;
rocev2_write_engine #(.WINDOW(4),.RESET_CYCLES(4),.INIT_CYCLES(16),.SETTLE_CYCLES(4)) dut (
 .clk(clk),.rst(rst),.start(start),.clear(clear),.abort_run(abort_run),.start_ready(ready),
 .cfg_local_qpn(lqp),.cfg_peer_qpn(MODE==16 ? 24'd1 : 24'habcdef),.cfg_tx_psn(24'hfffffc),.cfg_peer_psn(24'h123456),
 .cfg_peer_ip(32'hc6120a01),.cfg_rkey(key),.cfg_remote_address(address),.cfg_remote_bytes(extent),
 .cfg_message_bytes(size),.cfg_message_count(count),.cfg_timeout_cycles(MODE==15 ? 32'd0 : 32'd600),
 .tx_quiescent(quiet),.memory_fault(memory_fault),.core_reset(core_rst),.halt_tx(halt),.rx_enable(rx),
 .busy(busy),.done(done),.failed(failed),.state(state),.error_code(error),.issued_count(issued),.acked_count(acked),
 .duplicate_ack_count(dups),.total_bytes(total),.elapsed_cycles(elapsed),
 .m_axis_qp_tdata(qp),.m_axis_qp_tvalid(qv),.m_axis_qp_tready(qr),
 .m_axis_conn_tdata(conn),.m_axis_conn_tvalid(cv),.m_axis_conn_tready(cr),
 .m_axis_sq_tdata(sq),.m_axis_sq_tvalid(sv),.m_axis_sq_tready(sr),
 .s_axis_ack_tdata(ack),.s_axis_ack_tvalid(av),.s_axis_ack_tready(ar));
integer cycle=0,commands=0,qps=0,conns=0,phase=0,quiet_cycles=0,terminal_cycles=0;
integer q_stalls=0,c_stalls=0,s_stalls=0,max_outstanding=0,window_wait=0;
reg qp_stalled=0,conn_stalled=0,sq_stalled=0;
reg [183:0] qp_held,conn_held;
reg [239:0] sq_held;
reg ack_taken=0;
reg [31:0] rng=32'hd4169e1b;
reg [31:0] expected_error;
initial begin
 #1 rst=1; repeat(6) @(negedge clk); rst=0;
 @(negedge clk); start=1;
 @(negedge clk); start=0;
 // Deliberately mutate configuration after arm. All emitted data must use
 // the captured snapshot, including full key, address, sizes and QP fields.
 key=0; address=0; size=1; count=1; lqp=7;
end
always @(negedge clk) if(!rst) begin
 rng={rng[30:0],rng[31]^rng[21]^rng[1]^rng[0]};
 qr=cycle>35 && rng[2:0]!=0;
 cr=MODE!=4 && cycle>45 && rng[5:3]!=0;
 sr=MODE!=3 && MODE!=18 && cycle>60 && rng[8:6]!=0;
 if(busy && state!=6 && state!=9) quiet=0;
 if(state==6) begin quiet_cycles=quiet_cycles+1; quiet=quiet_cycles>25; end
 if(ack_taken) begin av=0; phase=phase+1; end
 if(MODE==0 && !av) begin
  if(phase==0 && issued==4 && cycle>200) begin ack={5'd0,24'hffffff,10'd2,1'b1}; av=1; end
  else if(phase==1 && acked==4) begin ack={5'd0,24'hfffffd,10'd2,1'b1}; av=1; end
  else if(phase==2 && issued==8) begin ack={5'd0,24'h000003,10'd2,1'b1}; av=1; end
  else if(phase==3 && issued==9) begin ack={5'd0,24'h000004,10'd2,1'b1}; av=1; end
 end
 if((MODE==1 || MODE==2) && issued==4 && phase==0 && !av) begin
  ack=MODE==1 ? {5'd0,24'hffffff,10'd3,1'b1} : {5'd0,24'h000000,10'd2,1'b1}; av=1;
 end
 if((MODE==3 || MODE==18) && sv && cycle>100) abort_run=1;
 if(MODE==10 && issued>=2) memory_fault=1;
 if(done || failed) begin terminal_cycles=terminal_cycles+1; if(terminal_cycles==5) clear=1; end
end
always @(posedge clk) if(!rst) begin
 cycle=cycle+1; ack_taken=av && ar;
 if(qp_stalled && !core_rst && (!qv || qp!==qp_held)) $fatal(1,"QP changed under backpressure");
 if(conn_stalled && !core_rst && (!cv || conn!==conn_held)) $fatal(1,"connection changed under backpressure");
 if(sq_stalled && !core_rst && (!sv || sq!==sq_held)) $fatal(1,"SQ withdrawn/changed before reset");
 qp_stalled=qv && !qr; conn_stalled=cv && !cr; sq_stalled=sv && !sr;
 qp_held=qp; conn_held=conn; sq_held=sq;
 if(qp_stalled) q_stalls=q_stalls+1; if(conn_stalled) c_stalls=c_stalls+1; if(sq_stalled) s_stalls=s_stalls+1;
 if(qv && qr && !core_rst) begin
  if(qp!=={32'hfedcba98,48'd0,24'h123456,24'hfffffc,24'd2,32'd3}) $fatal(1,"wrong QP/PSN ordering %h",qp);
  qps=qps+1;
 end
 if(cv && cr && !core_rst) begin
  if(conn!=={16'd4791,{4{32'h010a12c6}},24'habcdef,16'd2}) $fatal(1,"wrong connection %h",conn);
  conns=conns+1;
 end
 if(sv && sr && !core_rst) begin
  if(sq[31:0]!==32'd10 || sq[41:32]!==10'd2 || sq[47:42]!==6'b000010 ||
     sq[111:48]!==64'(commands*65) || sq[175:112]!==64'hfedcba9876543210+64'(commands*65) ||
     sq[207:176]!==32'd65 || sq[239:208]!==0) $fatal(1,"wrong SQ command %0d: %h",commands,sq);
  commands=commands+1;
 end
 if(issued-acked>4) $fatal(1,"window overflow");
 if(issued-acked>max_outstanding) max_outstanding=issued-acked;
 if(issued==4 && acked==0 && !sv && state==5) window_wait=window_wait+1;
 if(state==6 && (core_rst || !halt)) $fatal(1,"reset before physical quiescence");
 if((done || failed) && !quiet) $fatal(1,"terminal status before transmit drain");
 if(done || failed) begin
  if(MODE==0) begin
   if(!done || error!==0 || issued!==9 || acked!==9 || dups!==1 || commands!=9 || qps!=1 || conns!=1 || total!==585)
    $fatal(1,"bad successful result issued=%0d acked=%0d duplicate=%0d",issued,acked,dups);
   if(max_outstanding!=4 || window_wait<50 || !q_stalls || !c_stalls) $fatal(1,"missing window/backpressure coverage");
  end else begin
   case(MODE)
    1,2: expected_error=3;
    3,18: expected_error=5;
    4: expected_error=2;
    5,6,7,8,9,11,12,13,14,15,16,17: expected_error=1;
    10: expected_error=4;
   endcase
   if(!failed || error!==expected_error) $fatal(1,"wrong failure mode=%0d code=%0d",MODE,error);
   if((MODE>=5 && MODE<=9 || MODE>=11 && MODE<=17) && (qps || conns || commands)) $fatal(1,"invalid config emitted a command");
   if(MODE==18 && total!==67108864) $fatal(1,"valid maximum-sized run was not accepted");
  end
 end
 if(terminal_cycles>=5 && state==0) begin
  if(!core_rst || !ready) $fatal(1,"clear did not return to reset idle");
  $display("RESULT {\"scenario\":%0d,\"cycles\":%0d,\"issued\":%0d,\"acked\":%0d,\"configured_total_bytes\":%0d,\"duplicate_acks\":%0d,\"max_outstanding\":%0d,\"window_wait_cycles\":%0d,\"qp_stalls\":%0d,\"connection_stalls\":%0d,\"sq_stalls\":%0d,\"quiesce_wait_cycles\":%0d,\"error_code\":%0d}",MODE,cycle,issued,acked,total,dups,max_outstanding,window_wait,q_stalls,c_stalls,s_stalls,quiet_cycles,error);
  $finish;
 end
 if(cycle>1100) $fatal(1,"deadline mode=%0d state=%0d issued=%0d acked=%0d error=%0d",MODE,state,issued,acked,error);
end
endmodule
'''

PATTERN_TB = r'''
`timescale 1ns / 1ps
module tb;
reg clk=0; always #2 clk=~clk;
reg rst=0,enable=0;
reg [95:0] cmd=0;
reg cv=0;
wire cr;
wire [511:0] md;
wire [63:0] mk;
wire mv,ml,fault;
reg mr=0;
wire [31:0] count;
wire [63:0] bytes_sent;
rocev2_pattern_source dut (
 .clk(clk),.rst(rst),.enable(enable),.total_bytes(32'd67108864),.s_axis_cmd_tdata(cmd),.s_axis_cmd_tvalid(cv),.s_axis_cmd_tready(cr),
 .m_axis_tdata(md),.m_axis_tkeep(mk),.m_axis_tvalid(mv),.m_axis_tready(mr),.m_axis_tlast(ml),
 .fault(fault),.command_count(count),.supplied_bytes(bytes_sent));
reg [95:0] commands[0:N_CMD-1];
reg [576:0] expected[0:N_OUT-1];
integer cycle=0,ci=0,accepted=0,received=0,quiet=0,lane,in_stalls=0,out_stalls=0;
reg took_cmd=0,stalled=0;
reg [576:0] held;
reg [31:0] rng=32'h472daf19;
initial begin
 $readmemh("commands.hex",commands); $readmemh("expected.hex",expected);
 #1 rst=1; repeat(6) @(negedge clk); rst=0;
end
always @(negedge clk) if(!rst) begin
 rng={rng[30:0],rng[31]^rng[21]^rng[1]^rng[0]};
 enable=cycle>20;
 mr=cycle>500 && rng[2:0]!=0;
 if(!cv || took_cmd) begin
  cv=0;
  if(ci<N_CMD && rng[5:3]!=0) begin cmd=commands[ci]; cv=1; ci=ci+1; end
 end
end
always @(posedge clk) if(!rst) begin
 cycle=cycle+1; took_cmd=cv && cr;
 if(took_cmd) accepted=accepted+1;
 if(!enable && cr) $fatal(1,"accepted command while disabled");
 if(cv && !cr) in_stalls=in_stalls+1;
 if(mv && !mr) out_stalls=out_stalls+1;
 if(stalled && (!mv || {ml,mk,md}!==held)) $fatal(1,"payload changed under backpressure");
 stalled=mv && !mr; held={ml,mk,md};
 if(mv && mr) begin
  if(BAD_CMD || received>=N_OUT || {ml,mk}!==expected[received][576:512]) $fatal(1,"unexpected payload shape");
  for(lane=0;lane<64;lane=lane+1) if(mk[lane] && md[lane*8+:8]!==expected[received][lane*8+:8])
   $fatal(1,"payload byte mismatch word=%0d lane=%0d",received,lane);
  received=received+1;
 end
 if(BAD_CMD) begin
  if(fault && count==0 && received==0 && !cr) quiet=quiet+1;
  if(quiet==50) begin
   $display("RESULT {\"invalid_command_rejected\":true,\"payload_beats\":0}"); $finish;
  end
 end else begin
  if(fault) $fatal(1,"valid range incorrectly rejected");
  if(accepted==N_CMD && received==N_OUT && count==N_CMD && bytes_sent==TOTAL_BYTES) quiet=quiet+1;
  else quiet=0;
  if(quiet==50) begin
   if(!in_stalls || !out_stalls) $fatal(1,"missing backpressure coverage");
   $display("RESULT {\"commands\":%0d,\"payload_beats\":%0d,\"verified_bytes\":%0d,\"input_stalls\":%0d,\"output_stalls\":%0d}",count,received,bytes_sent,in_stalls,out_stalls);
   $finish;
  end
 end
 if(cycle>10000) $fatal(1,"deadline commands=%0d received=%0d fault=%b",accepted,received,fault);
end
endmodule
'''


class WriteEngineRTLTests(unittest.TestCase):
    reports = {}

    @classmethod
    def tearDownClass(cls):
        if target := os.environ.get("AS02_ENGINE_RTL_REPORT"):
            paths = [ROOT / "rdma/rtl/rocev2_write_engine.v", ROOT / "rdma/rtl/rocev2_pattern_source.v"]
            record = dict(evidence_type="finite WRITE engine/pattern source RTL simulation, not hardware",
                          hardware_verified=False, complete=len(cls.reports) == 3, tests=cls.reports,
                          source_sha256={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
                          test_sha256=hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest())
            destination = pathlib.Path(target)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(json.dumps(record, indent=2) + "\n")

    def simulate(self, tb, constants, files, module):
        self.assertIsNotNone(shutil.which("iverilog"))
        for name, value in sorted(constants.items(), key=lambda item: -len(item[0])):
            tb = tb.replace(name, str(value))
        with tempfile.TemporaryDirectory(prefix="as02-write-engine-") as directory:
            path = pathlib.Path(directory)
            (path / "tb.v").write_text(tb)
            for name, values in files.items():
                (path / name).write_text("".join(f"{v:x}\n" for v in values))
            compile_result = subprocess.run(["iverilog", "-g2012", "-s", "tb", "-o", str(path / "test.vvp"),
                                             str(path / "tb.v"), str(ROOT / f"rdma/rtl/{module}.v")],
                                            capture_output=True, text=True, timeout=20)
            self.assertEqual(compile_result.returncode, 0, compile_result.stderr)
            result = subprocess.run(["vvp", str(path / "test.vvp")], cwd=path,
                                    capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertNotIn("ERROR:", result.stdout + result.stderr)
            records = [json.loads(line[7:]) for line in result.stdout.splitlines() if line.startswith("RESULT ")]
            self.assertEqual(len(records), 1, result.stdout)
            return records[0]

    def test_window_psn_wrap_and_faults(self):
        scenarios = []
        for scenario in range(19):
            with self.subTest(scenario=scenario):
                scenarios.append(self.simulate(ENGINE_TB, {"MODE_VALUE": scenario}, {}, "rocev2_write_engine"))
        self.assertEqual(len(scenarios), 19)
        self.reports[self._testMethodName] = dict(pass_test=True, scenarios=scenarios)

    def test_pattern_alignment_tails_and_replay(self):
        commands = [(0, 1), (1, 63), (63, 64), (65, 65), (65503, 4095), (65536, 4096),
                    (67108864 - 4096, 4096), (65, 65)]
        packed_cmds, expected = [], []
        for address, length in commands:
            packed_cmds.append(address | (length << 48))
            payload = bytes(((i * 131) ^ (i >> 8) ^ 0x5A) & 255 for i in range(address, address + length))
            for offset in range(0, length, 64):
                chunk = payload[offset:offset + 64]
                expected.append(int.from_bytes(chunk.ljust(64, b"\0"), "little") |
                                (((1 << len(chunk)) - 1) << 512) | (int(offset + 64 >= length) << 576))
        result = self.simulate(PATTERN_TB, dict(N_CMD=len(commands), N_OUT=len(expected), BAD_CMD=0,
                                              TOTAL_BYTES=sum(length for _, length in commands)),
                               {"commands.hex": packed_cmds, "expected.hex": expected}, "rocev2_pattern_source")
        self.reports[self._testMethodName] = dict(**result, pass_test=True)

    def test_pattern_bounds_fail_closed(self):
        results = []
        for address, length, host in ((0, 0, False), (0, 4097, False), (67108832, 64, False),
                                      ((1 << 48) - 16, 32, False), (0, 64, True)):
            with self.subTest(address=address, length=length, host=host):
                result = self.simulate(PATTERN_TB, dict(N_CMD=1, N_OUT=1, BAD_CMD=1, TOTAL_BYTES=0),
                                       {"commands.hex": [address | (length << 48) | (int(host) << 79)],
                                        "expected.hex": [0]}, "rocev2_pattern_source")
                results.append(result)
        self.assertEqual(len(results), 5)
        self.reports[self._testMethodName] = dict(pass_test=True, invalid_commands=results)


if __name__ == "__main__":
    unittest.main(verbosity=2)
