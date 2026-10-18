#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""READ control RTL tests; completion/capture inputs are explicit test models."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
RTL = ROOT / 'rdma/read/rtl/rocev2_read_engine.v'

TB = r'''
`timescale 1ns/1ps
module tb;
reg clk=0;always #2 clk=~clk;
reg rst=1,start=0,clear=0,abort_run=0,quiet=1,memory_fault=0;
reg capture_idle=1,host_idle=1;
reg [31:0] captured_count=0,captured_bytes=0;
reg [23:0] lqp=2,pqp=24'habcdef;
reg [31:0] size=4097,count=3,window=2,timeout=600,key=32'hfedcba98;
reg [63:0] remote=64'hfedcba9876543210,extent=12291;
wire ready,buffer_clear,capture_enable,core_rst,halt,rx,busy,done,failed;
wire [3:0] state;
wire [31:0] lease,error,issued,acked,dups,total;
wire [63:0] elapsed;
wire [183:0] qp,conn;
wire qv,cv;reg qr=0,cr=0;
wire [239:0] sq;wire sv;reg sr=1;
reg [39:0] ack=0;reg av=0;wire ar;
rocev2_read_engine #(.RESET_CYCLES(4),.INIT_CYCLES(16),.SETTLE_CYCLES(4)) dut(
 .clk(clk),.rst(rst),.start(start),.clear(clear),.abort_run(abort_run),.start_ready(ready),
 .cfg_local_qpn(lqp),.cfg_peer_qpn(pqp),.cfg_tx_psn(24'hfffffe),.cfg_peer_psn(24'h123456),
 .cfg_peer_ip(32'hc6120a01),.cfg_rkey(key),.cfg_remote_address(remote),.cfg_remote_bytes(extent),
 .cfg_message_bytes(size),.cfg_message_count(count),.cfg_read_window(window),.cfg_timeout_cycles(timeout),
 .tx_quiescent(quiet),.memory_fault(memory_fault),.capture_idle(capture_idle),.capture_host_idle(host_idle),
 .captured_count(captured_count),.captured_bytes(captured_bytes),.capture_clear(buffer_clear),
 .capture_enable(capture_enable),.lease_bytes(lease),.core_reset(core_rst),.halt_tx(halt),.rx_enable(rx),
 .busy(busy),.done(done),.failed(failed),.state(state),.error_code(error),.issued_count(issued),
 .acked_count(acked),.duplicate_ack_count(dups),.total_bytes(total),.elapsed_cycles(elapsed),
 .m_axis_qp_tdata(qp),.m_axis_qp_tvalid(qv),.m_axis_qp_tready(qr),
 .m_axis_conn_tdata(conn),.m_axis_conn_tvalid(cv),.m_axis_conn_tready(cr),
 .m_axis_sq_tdata(sq),.m_axis_sq_tvalid(sv),.m_axis_sq_tready(sr),
 .s_axis_ack_tdata(ack),.s_axis_ack_tvalid(av),.s_axis_ack_tready(ar));
integer cycle=0,commands=0,qps=0,conns=0,early_wait=0;
integer expected_size,expected_stride,expected_count;
reg [63:0] expected_remote;
reg [183:0] held_qp,held_conn;
reg [239:0] held_sq;
reg q_stall=0,c_stall=0,s_stall=0;
always @(posedge clk) if(!rst) begin
 cycle=cycle+1;
 if(cycle>3000) $fatal(1,"test deadline state=%0d issued=%0d acked=%0d error=%0d",state,issued,acked,error);
 if(q_stall && !core_rst && (!qv || qp!==held_qp)) $fatal(1,"QP changed under stall");
 if(c_stall && !core_rst && (!cv || conn!==held_conn)) $fatal(1,"connection changed under stall");
 if(s_stall && !core_rst && (!sv || sq!==held_sq)) $fatal(1,"SQ changed under stall before reset");
 q_stall=qv && !qr;c_stall=cv && !cr;s_stall=sv && !sr;
 held_qp=qp;held_conn=conn;held_sq=sq;
 if(qv && qr && !core_rst) begin
  if(qp!=={32'hfedcba98,48'd0,24'h123456,24'hfffffe,24'd2,32'd3}) $fatal(1,"QP snapshot wrong");
  qps=qps+1;
 end
 if(cv && cr && !core_rst) begin
  if(conn!=={16'd4791,{4{32'h010a12c6}},24'habcdef,16'd2}) $fatal(1,"connection snapshot wrong");
  conns=conns+1;
 end
 if(sv && sr && !core_rst) begin
  if(sq[31:0]!==32'd12 || sq[41:32]!==10'd2 || sq[47:42]!==6'b000011 ||
     sq[111:48]!==64'(commands*expected_stride) ||
     sq[175:112]!==expected_remote+64'(commands*expected_size) ||
     sq[207:176]!==32'(expected_size) || sq[239:208]!==0)
   $fatal(1,"READ SQ mismatch index=%0d value=%h",commands,sq);
  commands=commands+1;capture_idle=0;
 end
 if(done && (!quiet || captured_count!=expected_count || captured_bytes!=total || !capture_idle))
  $fatal(1,"DONE before data commit or physical TX drain");
 if(state==6 && (core_rst || !halt)) $fatal(1,"transport reset before drain");
 if((done || failed) && !quiet) $fatal(1,"terminal before drain");
end
task arm;
 begin
  expected_size=size;expected_stride=(size+63)&~63;expected_count=count;expected_remote=remote;
  @(negedge clk);start=1;
  #0.001;if(!ready || !buffer_clear) $fatal(1,"arm did not clear capture transaction state");
  @(negedge clk);start=0;
  if(state!=9 || buffer_clear) $fatal(1,"arm failed");
  quiet=0;
  // Host changes after START must not alter the captured configuration.
  size=1;count=1;window=1;key=0;remote=0;extent=0;lqp=7;pqp=1;timeout=0;
 end
endtask
task release_setup;
 begin
  wait(qv && cv);repeat(8) @(negedge clk);qr=1;
  repeat(8) @(negedge clk);cr=1;
 end
endtask
task await_issued;
 input integer n;
 begin while(issued<n) @(negedge clk);end
endtask
task completion;
 input [23:0] psn;
 input [9:0] qpn;
 input rd;
 begin
  @(negedge clk);ack={5'd0,psn,qpn,rd};av=1;
  @(posedge clk);if(!ar) $fatal(1,"completion unexpectedly blocked");
  @(negedge clk);av=0;
 end
endtask
task finish_error;
 input integer code;
 begin
  wait(state==6);repeat(10) @(negedge clk);
  if(error!=code || core_rst || failed) $fatal(1,"bad pre-drain error=%0d expected=%0d",error,code);
  quiet=1;wait(failed);@(negedge clk);
  if(error!=code || !core_rst) $fatal(1,"bad terminal error");
 end
endtask
initial begin
 repeat(4) @(negedge clk);rst=0;
 // BODY
 $display("RESULT {\"pass_test\":true,\"cycles\":%0d,\"issued\":%0d,\"transport_completed\":%0d,\"captured\":%0d,\"payload_bytes\":%0d,\"lease_bytes\":%0d,\"error_code\":%0d}",cycle,issued,acked,captured_count,total,lease,error);
 $finish;
end
endmodule
'''


class ReadEngineRTLTests(unittest.TestCase):
    reports = {}

    def simulate(self, body):
        with tempfile.TemporaryDirectory(prefix='as02-read-engine-') as directory:
            path = Path(directory)
            (path / 'tb.v').write_text(TB.replace('// BODY', body))
            compiled = subprocess.run(['iverilog', '-g2012', '-s', 'tb', '-o', str(path / 'test.vvp'),
                                       str(path / 'tb.v'), str(RTL)], capture_output=True, text=True, timeout=20)
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            sim = subprocess.run(['vvp', str(path / 'test.vvp')], capture_output=True, text=True, timeout=20)
            self.assertEqual(sim.returncode, 0, sim.stdout + sim.stderr)
            rows = [json.loads(line[7:]) for line in sim.stdout.splitlines() if line.startswith('RESULT ')]
            self.assertEqual(len(rows), 1, sim.stdout)
            return rows[0]

    @classmethod
    def tearDownClass(cls):
        if target := os.environ.get('AS02_READ_ENGINE_REPORT'):
            report = dict(scope='READ controller RTL, modeled completion/capture inputs; not HLS/app/hardware',
                          hardware_verified=False, complete=len(cls.reports)==8, tests=cls.reports,
                          source_sha256={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest()
                                         for f in [RTL, Path(__file__)]})
            with Path(target).open('x') as out:
                out.write(json.dumps(report, indent=2) + '\n')

    def test_segmented_psn_wrap_window_snapshot_and_late_commit(self):
        body = r'''
arm;release_setup;await_issued(2);
repeat(20) begin @(negedge clk);if(issued!=2 || sv) $fatal(1,"read window overflow");end
completion(24'hffffff,2,0);completion(24'hffffff,2,0);
await_issued(3);completion(24'h000001,2,0);completion(24'h000003,2,0);
repeat(20) begin @(negedge clk);if(done || !busy || core_rst || acked!=3) $fatal(1,"early completion became DONE");end
captured_count=3;captured_bytes=12290;
repeat(10) begin @(negedge clk);if(done || state!=5) $fatal(1,"short capture completed");end
captured_bytes=12291;
repeat(10) begin @(negedge clk);if(done || state!=5) $fatal(1,"non-idle capture completed");end
capture_idle=1;wait(state==6);repeat(20) @(negedge clk);
if(core_rst || done || dups!=1 || total!=12291 || lease!=12480 || commands!=3 || qps!=1 || conns!=1) $fatal(1,"bad success metadata");
quiet=1;wait(done);@(negedge clk);clear=1;@(negedge clk);clear=0;
if(!ready || state!=0 || !core_rst) $fatal(1,"clear did not restore idle");
'''
        self.reports[self._testMethodName] = self.simulate(body)

    def test_invalid_configurations_emit_nothing(self):
        setups = ['size=0;', 'size=65537;', 'count=0;', 'count=4097;',
                  'lqp=1;', 'lqp=8;', 'pqp=1;', 'window=0;', 'window=33;',
                  'extent=12290;', 'remote=64\'hfffffffffffffff0;', 'timeout=24;',
                  'size=65536;count=5;extent=327680;']
        rows = []
        for setup in setups:
            with self.subTest(config=setup):
                rows.append(self.simulate(setup + r'''
arm;quiet=1;wait(failed);@(negedge clk);
if(error!=1 || commands || qps || conns || issued) $fatal(1,"invalid config reached transport");
'''))
        self.reports[self._testMethodName] = dict(pass_test=True, scenarios=rows)

    def test_wrong_completion_qp_type_psn_and_future(self):
        rows = []
        for psn, qpn, rd in [(0xFFFFFF,3,0),(0xFFFFFF,2,1),(0xFFFFFE,2,0),(1,2,0)]:
            body = f'arm;release_setup;await_issued(2);completion(24\'h{psn:06x},{qpn},{rd});finish_error(3);'
            rows.append(self.simulate(body))
        self.reports[self._testMethodName] = dict(pass_test=True, scenarios=rows)

    def test_ack_without_payload_times_out(self):
        self.reports[self._testMethodName] = self.simulate(r'''
size=65;count=1;extent=65;timeout=300;
arm;release_setup;await_issued(1);completion(24'hfffffe,2,0);finish_error(2);
if(acked!=1 || captured_count!=0 || done) $fatal(1,"ACK substituted for data");
''')

    def test_pending_sq_abort_holds_until_transport_reset(self):
        self.reports[self._testMethodName] = self.simulate(r'''
sr=0;arm;release_setup;wait(sv);repeat(12) @(negedge clk);
abort_run=1;finish_error(5);
if(commands || issued) $fatal(1,"blocked SQ was accepted");
''')

    def test_memory_fault_and_impossible_commit_progress(self):
        rows = []
        for fault in ['memory_fault=1;', 'captured_count=3;', 'captured_bytes=12292;']:
            rows.append(self.simulate('arm;release_setup;await_issued(2);' + fault + 'finish_error(4);'))
        self.reports[self._testMethodName] = dict(pass_test=True, scenarios=rows)

    def test_host_busy_blocks_arm_and_setup_stall_times_out(self):
        self.reports[self._testMethodName] = self.simulate(r'''
host_idle=0;@(negedge clk);start=1;@(negedge clk);start=0;
if(ready || state!=0 || buffer_clear) $fatal(1,"armed during pending host access");
host_idle=1;timeout=150;arm;qr=1;finish_error(2);
if(commands || conns) $fatal(1,"issued before connection setup");
''')

    def test_full_capture_capacity_and_sixteen_packet_psn_reservations(self):
        self.reports[self._testMethodName] = self.simulate(r'''
size=65536;count=4;extent=262144;
arm;release_setup;await_issued(2);
completion(24'h00000d,2,0);await_issued(3);
completion(24'h00001d,2,0);await_issued(4);
completion(24'h00002d,2,0);completion(24'h00003d,2,0);
captured_count=4;captured_bytes=262144;capture_idle=1;
wait(state==6);quiet=1;wait(done);@(negedge clk);
if(error || total!=262144 || lease!=262144 || issued!=4 || acked!=4) $fatal(1,"maximum capture failed");
''')


if __name__ == '__main__':
    unittest.main()
