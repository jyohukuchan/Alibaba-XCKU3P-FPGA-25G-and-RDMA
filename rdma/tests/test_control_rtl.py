#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""AXI-Lite host control, configuration locking and terminal memory evidence."""
import hashlib
import json
import os
import pathlib
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
TB = r'''
`timescale 1ns / 1ps
module tb;
reg clk=0; always #2 clk=~clk;
reg rst=0;
reg [23:0] aa=0,ra=0;
reg [31:0] wd=0;
reg [3:0] ws=0;
reg av=0,wv=0,br=0,rv=0,rr=0;
wire ar,wr,bv,arready,rvalid;
wire [1:0] bp,rp;
wire [31:0] rd;
reg [511:0] diagnostics=0;
wire [47:0] local_mac,peer_mac;
wire [31:0] local_ip,peer_ip;
wire [23:0] local_qpn;
wire core_rst,halt,rx,busy,done,failed;
wire [183:0] qp,conn;
wire qv,cv;
wire [239:0] sq;
wire sv;
reg [39:0] ack=0;
reg ack_valid=0;
wire ack_ready;
reg [95:0] mem_cmd=0;
reg mem_valid=0;
wire mem_ready;
wire [511:0] md;
wire [63:0] mk;
wire mv,ml;
reg allow_memory=0,allow_quiet=0;
wire quiet=!busy || allow_quiet;
reg mr=0;
rocev2_control #(.WINDOW(4),.RESET_CYCLES(4),.INIT_CYCLES(16),.SETTLE_CYCLES(4)) dut (
 .clk(clk),.rst(rst),.s_axil_awaddr(aa),.s_axil_awprot(3'd0),.s_axil_awvalid(av),.s_axil_awready(ar),
 .s_axil_wdata(wd),.s_axil_wstrb(ws),.s_axil_wvalid(wv),.s_axil_wready(wr),
 .s_axil_bresp(bp),.s_axil_bvalid(bv),.s_axil_bready(br),
 .s_axil_araddr(ra),.s_axil_arprot(3'd0),.s_axil_arvalid(rv),.s_axil_arready(arready),
 .s_axil_rdata(rd),.s_axil_rresp(rp),.s_axil_rvalid(rvalid),.s_axil_rready(rr),
 .tx_quiescent(quiet),.unexpected_memory_write(1'b0),.diagnostics(diagnostics),
 .local_mac(local_mac),.peer_mac(peer_mac),.local_ip(local_ip),.peer_ip(peer_ip),.local_qpn(local_qpn),
 .core_reset(core_rst),.halt_tx(halt),.rx_enable(rx),.busy(busy),.done(done),.failed(failed),
 .m_axis_qp_tdata(qp),.m_axis_qp_tvalid(qv),.m_axis_qp_tready(1'b1),
 .m_axis_conn_tdata(conn),.m_axis_conn_tvalid(cv),.m_axis_conn_tready(1'b1),
 .m_axis_sq_tdata(sq),.m_axis_sq_tvalid(sv),.m_axis_sq_tready(1'b1),
 .s_axis_ack_tdata(ack),.s_axis_ack_tvalid(ack_valid),.s_axis_ack_tready(ack_ready),
 .s_axis_mem_cmd_tdata(mem_cmd),.s_axis_mem_cmd_tvalid(mem_valid),.s_axis_mem_cmd_tready(mem_ready),
 .m_axis_mem_tdata(md),.m_axis_mem_tkeep(mk),.m_axis_mem_tvalid(mv),.m_axis_mem_tready(mr),.m_axis_mem_tlast(ml));
reg [95:0] command_queue[0:15];
integer cycle=0,commands=0,memory_index=0,data_frames=0,offset=0,verified=0,lane,i;
integer read_transactions=0,write_transactions=0,b_stalls=0,r_stalls=0,payload_stalls=0;
reg took_mem=0,took_ack=0,ack_sent=0;
reg bstalled=0,rstalled=0;
reg [1:0] b_held;
reg [33:0] r_held;
reg [31:0] rng=32'h761f9ad3;
reg [7:0] expected;

task write_reg;
 input [23:0] addr;
 input [31:0] data;
 input [3:0] strb;
 input integer order;
 input [1:0] response;
 begin
  fork
   begin
    if(order==1) repeat(3) @(negedge clk);
    @(negedge clk); aa=addr; av=1;
    @(posedge clk); while(!ar) @(posedge clk);
    @(negedge clk); av=0;
   end
   begin
    if(order==2) repeat(3) @(negedge clk);
    @(negedge clk); wd=data; ws=strb; wv=1;
    @(posedge clk); while(!wr) @(posedge clk);
    @(negedge clk); wv=0;
   end
  join
  while(!bv) @(negedge clk);
  if(bp!==response) $fatal(1,"wrong B response addr=%h got=%b expected=%b",addr,bp,response);
  repeat(3) @(negedge clk);
  br=1; @(negedge clk); br=0;
  write_transactions=write_transactions+1;
 end
endtask
task read_reg;
 input [23:0] addr;
 input [31:0] expected_value;
 input [1:0] response;
 begin
  @(negedge clk); ra=addr; rv=1;
  @(posedge clk); while(!arready) @(posedge clk);
  @(negedge clk); rv=0;
  while(!rvalid) @(negedge clk);
  if(rp!==response || rd!==expected_value) $fatal(1,"wrong R response addr=%h data=%h expected=%h resp=%b",addr,rd,expected_value,rp);
  repeat(3) @(negedge clk);
  rr=1; @(negedge clk); rr=0;
  read_transactions=read_transactions+1;
 end
endtask

initial begin
 for(i=0;i<16;i=i+1) diagnostics[i*32+:32]=32'ha0000000+i;
 #1 rst=1; repeat(6) @(negedge clk); rst=0;
 read_reg(0,32'h524f4332,0); read_reg(4,32'h00010000,0); read_reg(12,32'h38,0);
 read_reg(1,0,2); read_reg(24'hd0,0,2);
 write_reg(0,0,15,0,2); read_reg(56,1,0); read_reg(60,1,0);
 write_reg(8,1,1,1,2); read_reg(56,2,0); read_reg(60,4,0);
 write_reg(8,1,0,2,0); // unstroked command is a no-op
 write_reg(24'h40,32'hfbb97531,15,0,0); write_reg(24'h44,32'hffff8af3,15,1,0);
 write_reg(24'h48,32'h0367c5d0,15,2,0); write_reg(24'h4c,32'hffffb883,15,0,0);
 read_reg(24'h44,32'h8af3,0); read_reg(24'h4c,32'hb883,0);
 write_reg(24'h50,32'hc6120a02,15,1,0); write_reg(24'h54,32'hc6120a01,15,2,0);
 write_reg(24'h5c,32'h77,15,0,0); write_reg(24'h64,32'h987654,15,0,0);
 write_reg(24'h68,32'hfedcba98,15,1,0); write_reg(24'h68,32'h11223344,5,2,0);
 read_reg(24'h68,32'hfe22ba44,0);
 write_reg(24'h6c,65,15,0,0); write_reg(24'h70,32'h76543210,15,0,0);
 write_reg(24'h74,32'hfedcba98,15,0,0); write_reg(24'h78,195,15,0,0);
 write_reg(24'h80,3,15,0,0); write_reg(24'h84,10000,15,0,0);
 for(i=0;i<16;i=i+1) read_reg(24'h90+24'(i*4),32'ha0000000+i,0);
 // High data bytes are not strobed: only command byte zero takes effect.
 write_reg(8,32'hdeadbe01,1,1,0);
 if(!busy) $fatal(1,"start did not arm engine");
 write_reg(24'h54,32'h12345678,15,2,2); read_reg(24'h54,32'hc6120a01,0);
 write_reg(8,1,1,0,2); write_reg(8,2,1,0,2); read_reg(56,5,0);
 write_reg(24'h54,32'hffffffff,0,0,0); // no bytes, no mutation even while busy
 read_reg(24'h54,32'hc6120a01,0);
 allow_memory=1;
 wait(ack_sent); wait(halt);
 if(!busy || core_rst || done || failed) $fatal(1,"terminal/reset before quiescence");
 repeat(25) @(negedge clk);
 read_reg(12,32'h661,0);
 allow_quiet=1;
 wait(done); repeat(5) @(negedge clk);
 read_reg(12,32'h73a,0); read_reg(16,0,0); read_reg(20,3,0); read_reg(24,3,0);
 read_reg(28,195,0); read_reg(44,3,0); read_reg(48,195,0); read_reg(52,0,0);
 read_reg(24'h90,32'ha0000000,0); read_reg(24'hcc,32'ha000000f,0);
 if(commands!=3 || data_frames!=3 || verified!=195) $fatal(1,"incomplete memory evidence");
 write_reg(8,2,1,0,0); read_reg(12,32'h38,0); read_reg(60,0,0);
 // A new invalid run cannot inherit the previous run's memory counters.
 write_reg(24'h78,194,15,0,0); write_reg(8,1,1,0,0);
 wait(failed); repeat(3) @(negedge clk);
 read_reg(16,1,0); read_reg(44,0,0); read_reg(48,0,0);
 if(commands!=3) $fatal(1,"bad MR extent emitted work");
 write_reg(8,2,1,0,0); read_reg(12,32'h38,0);
 if(!b_stalls || !r_stalls || !payload_stalls) $fatal(1,"missing independent stall coverage");
 $display("RESULT {\"axi_reads\":%0d,\"axi_writes\":%0d,\"write_response_stalls\":%0d,\"read_response_stalls\":%0d,\"payload_stalls\":%0d,\"verified_writes\":3,\"verified_bytes\":195,\"rejected_control_writes\":5,\"invalid_mr_rejected\":true}",read_transactions,write_transactions,b_stalls,r_stalls,payload_stalls);
 $finish;
end
always @(negedge clk) if(!rst) begin
 rng={rng[30:0],rng[31]^rng[21]^rng[1]^rng[0]}; mr=allow_memory && rng[2:0]!=0;
 if(took_mem) begin mem_valid=0; memory_index=memory_index+1; end
 if(!mem_valid && memory_index<commands) begin mem_cmd=command_queue[memory_index]; mem_valid=1; end
 if(took_ack) begin ack_valid=0; ack_sent=1; end
 if(data_frames==3 && !ack_sent) begin ack={5'd0,24'h123458,10'd2,1'b1}; ack_valid=1; end
end
always @(posedge clk) if(!rst) begin
 cycle=cycle+1; took_mem=mem_valid && mem_ready; took_ack=ack_valid && ack_ready;
 if(bstalled && (!bv || bp!==b_held)) $fatal(1,"B response changed while stalled");
 if(rstalled && (!rvalid || {rp,rd}!==r_held)) $fatal(1,"R response changed while stalled");
 bstalled=bv && !br; b_held=bp; rstalled=rvalid && !rr; r_held={rp,rd};
 if(bstalled) b_stalls=b_stalls+1; if(rstalled) r_stalls=r_stalls+1;
 if(mv && !mr) payload_stalls=payload_stalls+1;
 if(qv && !core_rst && qp!=={32'hfe22ba44,48'd0,24'h987654,24'h123456,24'd2,32'd3}) $fatal(1,"bad captured QP context");
 if(sv && !core_rst) begin
  if(sq[111:48]!==64'(commands*65) || sq[175:112]!==64'hfedcba9876543210+64'(commands*65)) $fatal(1,"bad local/remote offsets");
  command_queue[commands]={20'd0,sq[203:176],sq[95:48]}; commands=commands+1;
 end
 if(mv && mr) begin
  if(mk!==(offset==0 ? 64'hffffffffffffffff : 64'd1) || ml!==(offset==64)) $fatal(1,"wrong partial tail");
  for(lane=0;lane<64;lane=lane+1) if(mk[lane]) begin
   expected=(((data_frames*65+offset+lane)*131)^((data_frames*65+offset+lane)>>8)^8'h5a)&255;
   if(md[lane*8+:8]!==expected) $fatal(1,"bad payload byte frame=%0d offset=%0d lane=%0d",data_frames,offset,lane);
   verified=verified+1;
  end
  if(ml) begin data_frames=data_frames+1; offset=0; end else offset=offset+64;
 end
 if(cycle>4000) $fatal(1,"test deadline");
end
endmodule
'''


class ControlRTLTests(unittest.TestCase):
    def test_axil_control_and_terminal_evidence(self):
        with tempfile.TemporaryDirectory(prefix="as02-roce-control-") as directory:
            path = pathlib.Path(directory)
            (path / "tb.v").write_text(TB)
            modules = [ROOT / "rdma/rtl" / name for name in
                       ("rocev2_control.v", "rocev2_write_engine.v", "rocev2_pattern_source.v")]
            compiled = subprocess.run(["iverilog", "-g2012", "-s", "tb", "-o", str(path / "test.vvp"),
                                       str(path / "tb.v"), *map(str, modules)], capture_output=True, text=True, timeout=20)
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            result = subprocess.run(["vvp", str(path / "test.vvp")], cwd=path, capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertNotIn("ERROR:", result.stdout + result.stderr)
            records = [json.loads(line[7:]) for line in result.stdout.splitlines() if line.startswith("RESULT ")]
            self.assertEqual(len(records), 1)
            if target := os.environ.get("AS02_CONTROL_RTL_REPORT"):
                record = dict(evidence_type="AXI-Lite control/pattern RTL simulation, not hardware", hardware_verified=False,
                              pass_test=True, **records[0], source_sha256={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in modules},
                              test_sha256=hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest())
                output = pathlib.Path(target)
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(json.dumps(record, indent=2) + "\n")


if __name__ == "__main__":
    unittest.main(verbosity=2)
