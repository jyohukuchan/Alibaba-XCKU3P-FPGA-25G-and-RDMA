#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Version-2 BAR control/locking/RAM arbitration; modeled HLS metadata IO."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT / 'rdma/tests'))
import test_control_rtl as legacy

SOURCES=[ROOT / 'rdma/read/rtl' / name for name in
    ('rocev2_rw_control.v','rocev2_read_engine.v','rocev2_read_buffer.v')]
SOURCES += [ROOT / 'rdma/rtl' / name for name in ('rocev2_write_engine.v','rocev2_pattern_source.v')]
TASKS=legacy.TB[legacy.TB.index('task write_reg;'):legacy.TB.index('\ninitial begin')]

TB=r'''
`timescale 1ns/1ps
module tb;
reg clk=0;always #2 clk=~clk;
reg rst=0;
reg [23:0] aa=0,ra=0;
reg [31:0] wd=0;
reg [3:0] ws=0;
reg av=0,wv=0,br=0,rv=0,rr=0;
wire ar,wr,bv,arready,rvalid;
wire [1:0] bp,rp;
wire [31:0] rd;
wire mode,core_rst,halt,rx,busy,done,failed;
wire [31:0] run_id;
reg quiet=1,external_fault=0;
wire [183:0] qp,conn;
wire qv,cv;
wire [239:0] sq;wire sv;reg sr=0;
reg [39:0] ack=0;reg ack_valid=0;wire ack_ready;
reg [95:0] mem_cmd=0;reg mem_valid=0;wire mem_ready;
wire [511:0] md;wire [63:0] mk;wire mv,ml;
reg [95:0] cap_cmd=0;reg cap_cv=0;wire cap_cr;
reg [511:0] cap_data=0;reg [63:0] cap_keep=0;reg cap_valid=0,cap_last=0;wire cap_ready;
integer read_transactions=0,write_transactions=0,cycle=0,sqs=0,pattern_bytes=0,i,j;
reg bstalled=0,rstalled=0,sqstalled=0;
reg [1:0] held_b;
reg [33:0] held_r;
reg [239:0] held_sq;
reg [31:0] expected_word;
rocev2_rw_control #(.WINDOW(4),.RESET_CYCLES(4),.INIT_CYCLES(16),.SETTLE_CYCLES(4),
 .CAPACITY_BYTES(4096),.RUN_ID_WIDTH(2)) dut (
 .clk(clk),.rst(rst),.s_axil_awaddr(aa),.s_axil_awprot(3'd0),.s_axil_awvalid(av),.s_axil_awready(ar),
 .s_axil_wdata(wd),.s_axil_wstrb(ws),.s_axil_wvalid(wv),.s_axil_wready(wr),
 .s_axil_bresp(bp),.s_axil_bvalid(bv),.s_axil_bready(br),
 .s_axil_araddr(ra),.s_axil_arprot(3'd0),.s_axil_arvalid(rv),.s_axil_arready(arready),
 .s_axil_rdata(rd),.s_axil_rresp(rp),.s_axil_rvalid(rvalid),.s_axil_rready(rr),
 .tx_quiescent(quiet),.unexpected_memory_write(external_fault),.diagnostics(512'd0),
 .local_mac(),.peer_mac(),.local_ip(),.peer_ip(),.local_qpn(),.read_mode(mode),.run_id(run_id),
 .core_reset(core_rst),.halt_tx(halt),.rx_enable(rx),.busy(busy),.done(done),.failed(failed),
 .m_axis_qp_tdata(qp),.m_axis_qp_tvalid(qv),.m_axis_qp_tready(1'b1),
 .m_axis_conn_tdata(conn),.m_axis_conn_tvalid(cv),.m_axis_conn_tready(1'b1),
 .m_axis_sq_tdata(sq),.m_axis_sq_tvalid(sv),.m_axis_sq_tready(sr),
 .s_axis_ack_tdata(ack),.s_axis_ack_tvalid(ack_valid),.s_axis_ack_tready(ack_ready),
 .s_axis_mem_cmd_tdata(mem_cmd),.s_axis_mem_cmd_tvalid(mem_valid),.s_axis_mem_cmd_tready(mem_ready),
 .m_axis_mem_tdata(md),.m_axis_mem_tkeep(mk),.m_axis_mem_tvalid(mv),.m_axis_mem_tready(1'b1),.m_axis_mem_tlast(ml),
 .s_axis_capture_cmd_tdata(cap_cmd),.s_axis_capture_cmd_tvalid(cap_cv),.s_axis_capture_cmd_tready(cap_cr),
 .s_axis_capture_tdata(cap_data),.s_axis_capture_tkeep(cap_keep),.s_axis_capture_tvalid(cap_valid),
 .s_axis_capture_tready(cap_ready),.s_axis_capture_tlast(cap_last));
AXIL_TASKS
task configure;
 begin
  write_reg(24'h40,32'hfbb97531,15,0,0);write_reg(24'h44,32'h8af3,15,1,0);
  write_reg(24'h48,32'h0367c5d0,15,2,0);write_reg(24'h4c,32'hb883,15,0,0);
  write_reg(24'h50,32'hc6120b02,15,0,0);write_reg(24'h54,32'hc6120b01,15,0,0);
  write_reg(24'h5c,196,15,0,0);write_reg(24'h60,32'hfffffe,15,0,0);
  write_reg(24'h64,32'h987654,15,0,0);write_reg(24'h68,32'hfedcba98,15,0,0);
  write_reg(24'h6c,65,15,0,0);write_reg(24'h70,32'h76543210,15,0,0);
  write_reg(24'h74,32'hfedcba98,15,0,0);write_reg(24'h78,65,15,0,0);
  write_reg(24'h80,1,15,0,0);write_reg(24'h84,10000,15,0,0);
 end
endtask
task completion;
 input rd;
 begin
  @(negedge clk);ack={5'd0,24'hfffffe,10'd2,rd};ack_valid=1;
  @(posedge clk);if(!ack_ready) $fatal(1,"completion blocked");
  @(negedge clk);ack_valid=0;
 end
endtask
task send_capture_command;
 input [95:0] command;
 begin
  @(negedge clk);cap_cmd=command;cap_cv=1;
  @(posedge clk);while(!cap_cr) @(posedge clk);
  @(negedge clk);cap_cv=0;
 end
endtask
task capture_beat;
 input integer start,count,padded;
 input final_beat;
 begin
  @(negedge clk);cap_data=0;
  for(j=0;j<count;j=j+1) cap_data[j*8+:8]=((start+j)*179)^((start+j)>>7)^8'hd3;
  cap_keep=(65'd1<<padded)-1;cap_last=final_beat;cap_valid=1;
  @(posedge clk);while(!cap_ready) @(posedge clk);
  @(negedge clk);cap_valid=0;
 end
endtask
task accept_one_sq;
 begin
  wait(sv);@(negedge clk);sr=1;
  @(posedge clk);if(!sv) $fatal(1,"pending SQ withdrawn");
  @(negedge clk);sr=0;
 end
endtask
always @(posedge clk) if(!rst) begin
 cycle=cycle+1;
 if(cycle>20000) $fatal(1,"test deadline state=%0d",dut.state);
 if(bstalled && (!bv || bp!==held_b)) $fatal(1,"B response changed under stall");
 if(rstalled && (!rvalid || {rp,rd}!==held_r)) $fatal(1,"R response changed under stall");
 if(sqstalled && !core_rst && (!sv || sq!==held_sq)) $fatal(1,"SQ changed under stall");
 bstalled=bv && !br;held_b=bp;rstalled=rvalid && !rr;held_r={rp,rd};
 sqstalled=sv && !sr;held_sq=sq;
 if(sv && sr && !core_rst) sqs=sqs+1;
 if(mv) for(integer lane=0;lane<64;lane=lane+1) if(mk[lane]) pattern_bytes=pattern_bytes+1;
end
initial begin
 #1 rst=1;repeat(6) @(negedge clk);rst=0;
 BODY
 $display("RESULT {\"pass_test\":true,\"cycles\":%0d,\"axi_reads\":%0d,\"axi_writes\":%0d,\"sq_handshakes\":%0d,\"pattern_bytes\":%0d,\"run_id\":%0d}",cycle,read_transactions,write_transactions,sqs,pattern_bytes,run_id);
 $finish;
end
endmodule
'''.replace('AXIL_TASKS',TASKS)


class RWControlRTLTests(unittest.TestCase):
    reports={}

    def simulate(self,tb):
        with tempfile.TemporaryDirectory(prefix='as02-rw-control-') as directory:
            path=Path(directory)
            (path / 'tb.v').write_text(tb)
            compiled=subprocess.run(['iverilog','-g2012','-s','tb','-o',str(path / 'test.vvp'),
                                     str(path / 'tb.v'),*map(str,SOURCES)],capture_output=True,text=True,timeout=30)
            self.assertEqual(compiled.returncode,0,compiled.stderr)
            sim=subprocess.run(['vvp',str(path / 'test.vvp')],capture_output=True,text=True,timeout=45)
            self.assertEqual(sim.returncode,0,sim.stdout+sim.stderr)
            rows=[json.loads(line[7:]) for line in sim.stdout.splitlines() if line.startswith('RESULT ')]
            self.assertEqual(len(rows),1,sim.stdout)
            self.reports[self._testMethodName]=dict(rows[0],pass_test=True)
            return rows[0]

    @classmethod
    def tearDownClass(cls):
        if target:=os.environ.get('AS02_RW_CONTROL_REPORT'):
            deps=SOURCES+[Path(__file__),Path(legacy.__file__)]
            report=dict(scope='RW BAR/control RTL with modeled HLS metadata; not actual HLS or PCIe hardware',
                        complete=len(cls.reports)==5,hardware_verified=False,tests=cls.reports,
                        source_sha256={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in deps})
            with Path(target).open('x') as out:out.write(json.dumps(report,indent=2)+'\n')

    def test_existing_write_control_and_pattern_path(self):
        tb=legacy.TB.replace('rocev2_control #(','rocev2_rw_control #(')
        tb=tb.replace("read_reg(4,32'h00010000,0)","read_reg(4,32'h00020000,0)")
        tb=tb.replace('.s_axis_mem_cmd_tdata(mem_cmd)',
            ".s_axis_capture_cmd_tdata(96'd0),.s_axis_capture_cmd_tvalid(1'b0),.s_axis_capture_cmd_tready(),\n"
            ".s_axis_capture_tdata(512'd0),.s_axis_capture_tkeep(64'd0),.s_axis_capture_tvalid(1'b0),\n"
            ".s_axis_capture_tlast(1'b0),.s_axis_capture_tready(),.read_mode(),.run_id(),\n"
            '.s_axis_mem_cmd_tdata(mem_cmd)')
        self.simulate(tb)

    def test_ram_byte_enables_bounds_and_independent_owners(self):
        self.simulate(TB.replace('BODY',r'''
read_reg(4,32'h20000,0);read_reg(24'h108,4096,0);read_reg(24'h10c,32'h10000,0);
write_reg(24'h10000,32'ha5a5a5a5,15,1,0);write_reg(24'h10000,32'h12345678,5,2,0);
read_reg(24'h10000,32'ha534a578,0);
write_reg(24'h1003c,32'h11223344,15,0,0);write_reg(24'h10040,32'h55667788,15,1,0);
write_reg(24'h10ffc,32'hfeedface,15,2,0);
read_reg(24'h1003c,32'h11223344,0);read_reg(24'h10040,32'h55667788,0);read_reg(24'h10ffc,32'hfeedface,0);
write_reg(24'h10001,0,15,0,2);read_reg(24'h10001,0,2);write_reg(24'h11000,0,15,0,2);read_reg(24'h11000,0,2);
fork
 begin write_reg(24'h10040,32'hdeadbeef,15,1,0);end
 begin read_reg(24'h1003c,32'h11223344,0);end
join
read_reg(24'h10040,32'hdeadbeef,0);read_reg(24'h10000,32'ha534a578,0);
write_reg(24'h100,2,15,0,2);read_reg(24'h100,0,0);
'''))

    def test_read_commit_gating_bar_readback_and_warm_write(self):
        self.simulate(TB.replace('BODY',r'''
configure;write_reg(24'h100,1,15,0,0);write_reg(24'h104,2,15,1,0);
for(i=0;i<192;i=i+4) write_reg(24'h10000+i,32'ha5a5a5a5,15,0,0);
write_reg(8,1,1,0,0);quiet=0;wait(sv);
read_reg(24'h124,0,0);read_reg(24'h130,1,0);
write_reg(24'h100,0,15,0,2);write_reg(24'h104,1,15,0,2);
write_reg(24'h10000,32'hbad0bad0,15,0,2);read_reg(24'h10000,0,2);
accept_one_sq;read_reg(24'h124,1,0);completion(0);
repeat(20) @(negedge clk);if(done || !busy || core_rst) $fatal(1,"ACK substituted for READ data");
cap_cmd=0;cap_cmd[75:48]=68;cap_cmd[76]=1;cap_cmd[79]=1;cap_cmd[93:84]=2;
send_capture_command(cap_cmd);capture_beat(0,64,64,0);capture_beat(64,1,4,1);
wait(halt);read_reg(24'h10000,0,2);if(done || core_rst) $fatal(1,"terminal before physical drain");
quiet=1;wait(done);repeat(3) @(negedge clk);
read_reg(24'h110,1,0);read_reg(24'h114,65,0);read_reg(24'h118,3,0);read_reg(24'h11c,1,0);read_reg(24'h120,0,0);
for(i=0;i<192;i=i+4) begin
 expected_word=32'ha5a5a5a5;
 for(j=0;j<4;j=j+1) if(i+j<65) expected_word[j*8+:8]=((i+j)*179)^((i+j)>>7)^8'hd3;
 read_reg(24'h10000+i,expected_word,0);
end
write_reg(24'h100,0,15,0,2);write_reg(8,2,1,0,0);write_reg(24'h100,0,15,0,0);
write_reg(8,1,1,0,0);quiet=0;accept_one_sq;
@(negedge clk);mem_cmd=0;mem_cmd[75:48]=65;mem_valid=1;
@(posedge clk);while(!mem_ready) @(posedge clk);
@(negedge clk);mem_valid=0;wait(pattern_bytes==65);completion(1);wait(halt);quiet=1;wait(done);
read_reg(16,0,0);read_reg(20,1,0);read_reg(24,1,0);read_reg(24'h130,2,0);
expected_word=0;for(j=0;j<4;j=j+1) expected_word[j*8+:8]=(j*179)^8'hd3;
read_reg(24'h10000,expected_word,0);
'''))

    def test_unleased_capture_error_abort_recovery_and_epoch_exhaustion(self):
        self.simulate(TB.replace('BODY',r'''
configure;write_reg(24'h10000,32'h12345678,15,0,0);write_reg(24'h100,1,15,0,0);
write_reg(8,1,1,0,0);quiet=0;wait(sv);
cap_cmd=0;cap_cmd[75:48]=68;cap_cmd[76]=1;cap_cmd[79]=1;cap_cmd[93:84]=2;
send_capture_command(cap_cmd);wait(halt);if(core_rst) $fatal(1,"failed SQ canceled before drain");
quiet=1;wait(failed);read_reg(16,4,0);read_reg(24'h120,2,0);read_reg(24'h124,0,0);
read_reg(24'h10000,32'h12345678,0);write_reg(8,2,1,0,0);
for(i=0;i<2;i=i+1) begin
 write_reg(8,1,1,0,0);quiet=0;wait(sv);write_reg(8,4,1,0,0);wait(halt);
 quiet=1;wait(failed);read_reg(16,5,0);write_reg(8,2,1,0,0);
end
read_reg(24'h130,3,0);write_reg(8,1,1,0,2);read_reg(60,5,0);
if(busy || sqs!=0 || run_id!=3) $fatal(1,"generation wrapped or unaccepted SQ authorized");
read_reg(24'h10000,32'h12345678,0);
'''))

    def test_start_racing_ram_read_is_rejected_without_cancellation(self):
        self.simulate(TB.replace('BODY',r'''
configure;write_reg(24'h100,1,15,0,0);write_reg(24'h10000,32'h87654321,15,0,0);
@(negedge clk);aa=8;wd=1;ws=1;av=1;wv=1;
@(posedge clk);if(!ar || !wr) $fatal(1,"AW/W not accepted");
@(negedge clk);av=0;wv=0;ra=24'h10000;rv=1;
@(posedge clk);if(!arready) $fatal(1,"AR not accepted");
@(negedge clk);rv=0;
wait(bv && rvalid);repeat(5) @(negedge clk);
if(bp!=2 || rp!=0 || rd!=32'h87654321 || busy || run_id!=0) $fatal(1,"START stole/canceled RAM read");
br=1;rr=1;@(negedge clk);br=0;rr=0;
write_reg(8,1,1,0,0);quiet=0;wait(sv);write_reg(8,4,1,0,0);wait(halt);quiet=1;wait(failed);
read_reg(16,5,0);read_reg(24'h130,1,0);read_reg(24'h10000,32'h87654321,0);
'''))


if __name__=='__main__':unittest.main()
