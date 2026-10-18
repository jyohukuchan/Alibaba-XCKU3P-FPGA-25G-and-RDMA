#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Protected capture RAM tests: real RTL, byte-exact host readback, no board."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
RTL = ROOT / 'rdma/read/rtl/rocev2_read_buffer.v'

TB = r'''
`timescale 1ns/1ps
module tb;
localparam CAP=32768;
reg clk=0;always #2 clk=~clk;
reg rst=1,clear=0,enable=0;
reg [31:0] lease=CAP,da=0,dl=0;
reg dv=0;wire dr;
reg [95:0] cmd=0;reg cv=0;wire cr;
reg [511:0] data=0;reg [63:0] keep=0;reg valid=0,last=0;wire ready;
reg [31:0] ha=0,hwdata=0;reg hw=0,hv=0;reg [3:0] hs=0;wire hr;
wire [31:0] hd;wire he,hresponse;reg hresponse_ready=0;
wire idle,host_idle,fault;wire [7:0] error_code;
wire [31:0] authorized,committed,bytes,padding,commands;
rocev2_read_buffer #(.CAPACITY_BYTES(CAP)) dut(
 .clk(clk),.rst(rst),.clear(clear),.capture_enable(enable),.local_qpn(10'd2),.lease_bytes(lease),
 .s_axis_desc_address(da),.s_axis_desc_length(dl),.s_axis_desc_valid(dv),.s_axis_desc_ready(dr),
 .s_axis_cmd_tdata(cmd),.s_axis_cmd_tvalid(cv),.s_axis_cmd_tready(cr),
 .s_axis_tdata(data),.s_axis_tkeep(keep),.s_axis_tvalid(valid),.s_axis_tready(ready),.s_axis_tlast(last),
 .host_address(ha),.host_write(hw),.host_wdata(hwdata),.host_wstrb(hs),.host_valid(hv),.host_ready(hr),
 .host_rdata(hd),.host_error(he),.host_response_valid(hresponse),.host_response_ready(hresponse_ready),
 .idle(idle),.host_idle(host_idle),.fault(fault),.error_code(error_code),.authorized_count(authorized),
 .committed_count(committed),.committed_bytes(bytes),.padding_bytes(padding),.command_count(commands));
reg [7:0] expected[0:CAP-1];
reg [31:0] read_value,saved_response;
reg saved_error;
integer i,j,addr,size,chunk,offset,beat,real_count,wire_count,cases=0;
integer next_address=0,total=0,pads=0,ops=0,packets=0,checked_bytes=0;
integer cycles=0;
always @(posedge clk) begin
 cycles=cycles+1;
 if(cycles>3000000) $fatal(1,"test deadline");
end
function [7:0] pattern;
 input integer address;
 begin pattern=(address*179)^(address>>7)^8'hd3;end
endfunction
task host;
 input integer address;
 input write;
 input [31:0] value;
 input [3:0] strb;
 input expect_error;
 begin
  @(negedge clk);ha=address;hw=write;hwdata=value;hs=strb;hv=1;
  @(posedge clk);while(!hr) @(posedge clk);
  @(negedge clk);hv=0;
  while(!hresponse) @(negedge clk);
  if(he!==expect_error) $fatal(1,"host error addr=%h got=%b expected=%b",address,he,expect_error);
  saved_response=hd;saved_error=he;read_value=hd;
  repeat(3) begin
   @(negedge clk);
   if(!hresponse || hd!==saved_response || he!==saved_error) $fatal(1,"host response changed under stall");
  end
  hresponse_ready=1;@(negedge clk);hresponse_ready=0;
 end
endtask
task reset_state;
 begin
  @(negedge clk);enable=0;clear=1;
  @(negedge clk);clear=0;
 end
endtask
task prefill;
 begin
  for(i=0;i<CAP;i=i+4) begin
   host(i,1,32'ha5a5a5a5,4'hf,0);
   for(j=0;j<4;j=j+1) expected[i+j]=8'ha5;
  end
 end
endtask
task verify_ram;
 reg [31:0] want;
 begin
  @(negedge clk);enable=0;
  for(i=0;i<CAP;i=i+4) begin
   host(i,0,0,0,0);
   want={expected[i+3],expected[i+2],expected[i+1],expected[i]};
   if(read_value!==want) $fatal(1,"RAM mismatch at %0d got=%h expected=%h",i,read_value,want);
   checked_bytes=checked_bytes+4;
  end
 end
endtask
task descriptor;
 input integer address,length;
 begin
  @(negedge clk);da=address;dl=length;dv=1;
  @(posedge clk);while(!dr) @(posedge clk);
  @(negedge clk);dv=0;
 end
endtask
task command;
 input [95:0] value;
 begin
  @(negedge clk);cmd=value;cv=1;
  @(posedge clk);while(!cr) @(posedge clk);
  @(negedge clk);cv=0;
 end
endtask
function [95:0] memory_command;
 input integer address,length;
 input final_packet;
 reg [95:0] value;
 begin
  value=0;value[47:0]=address;value[75:48]=length;
  value[76]=final_packet;value[79]=1;value[93:84]=2;
  memory_command=value;
 end
endfunction
task payload_beat;
 input integer address,payload_count,padded_count;
 input final_beat;
 input bad_keep;
 begin
  @(negedge clk);data=0;
  for(j=0;j<payload_count;j=j+1) data[j*8+:8]=pattern(address+j);
  keep=(65'd1<<padded_count)-1;
  if(bad_keep) keep=keep^64'd2;
  last=final_beat;valid=1;
  @(posedge clk);while(!ready) @(posedge clk);
  @(negedge clk);valid=0;
 end
endtask
task receive_descriptor;
 input integer address,length;
 begin
  offset=0;
  while(offset<length) begin
   chunk=length-offset>4096 ? 4096 : length-offset;
   command(memory_command(address+offset,(chunk+3)&~3,offset+chunk==length));
   beat=0;
   while(beat<chunk) begin
    real_count=chunk-beat>64 ? 64 : chunk-beat;
    wire_count=(real_count+3)&~3;
    if((beat/64)%5==0) repeat(3) @(negedge clk);
    payload_beat(address+offset+beat,real_count,wire_count,beat+real_count==chunk,0);
    for(j=0;j<real_count;j=j+1) expected[address+offset+beat+j]=pattern(address+offset+beat+j);
    beat=beat+real_count;
   end
   offset=offset+chunk;packets=packets+1;
  end
  total=total+length;pads=pads+((-length)&3);ops=ops+1;
 end
endtask
task check_good;
 begin
  repeat(2) @(negedge clk);
  if(fault || !idle || authorized!=ops || committed!=ops || bytes!=total || padding!=pads || commands!=packets)
   $fatal(1,"good counters fault=%b idle=%b auth=%0d done=%0d bytes=%0d pad=%0d cmd=%0d expected=%0d/%0d/%0d/%0d",fault,idle,authorized,committed,bytes,padding,commands,ops,total,pads,packets);
 end
endtask
initial begin
 repeat(4) @(negedge clk);rst=0;
 // BODY
 $display("RESULT {\"pass_test\":true,\"checked_bytes\":%0d,\"cases\":%0d,\"cycles\":%0d}",checked_bytes,cases,cycles);
 $finish;
end
endmodule
'''


class ReadBufferRTLTests(unittest.TestCase):
    reports = {}

    def simulate(self, body, capacity=32768):
        with tempfile.TemporaryDirectory(prefix='as02-read-buffer-') as directory:
            path = Path(directory)
            bench = TB.replace('localparam CAP=32768;', f'localparam CAP={capacity};')
            (path / 'tb.v').write_text(bench.replace('// BODY', body))
            compiled = subprocess.run(['iverilog', '-g2012', '-s', 'tb', '-o', str(path / 'test.vvp'),
                                       str(path / 'tb.v'), str(RTL)], capture_output=True, text=True, timeout=30)
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            result = subprocess.run(['vvp', str(path / 'test.vvp')], capture_output=True, text=True, timeout=180)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            rows = [json.loads(line[7:]) for line in result.stdout.splitlines() if line.startswith('RESULT ')]
            self.assertEqual(len(rows), 1, result.stdout)
            self.reports[self._testMethodName] = rows[0]
            return rows[0]

    @classmethod
    def tearDownClass(cls):
        if target := os.environ.get('AS02_READ_BUFFER_REPORT'):
            report = dict(scope='Protected READ buffer RTL, not HLS integration or hardware',
                          hardware_verified=False, tests=cls.reports, complete=len(cls.reports) == 7,
                          source_sha256={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest()
                                         for f in [RTL, Path(__file__)]})
            with Path(target).open('x') as out:
                out.write(json.dumps(report, indent=2) + '\n')

    def test_tails_segmentation_queued_descriptors_and_sentinels(self):
        lengths = [1, 2, 3, 4, 63, 64, 65, 4095, 4096, 4097, 8193]
        allocations, address = [], 0
        for length in lengths:
            allocations.append((address, length))
            address += (length + 63) & ~63
        body = ['prefill;reset_state;enable=1;']
        body += [f'descriptor({a},{n});' for a, n in allocations]
        # An attempted host write/read during capture must return an error.
        body += ["host(0,1,32'hbad0bad0,4'hf,1);host(0,0,0,0,1);"]
        body += [f'receive_descriptor({a},{n});' for a, n in allocations]
        body += ['check_good;verify_ram;cases=11;']
        report = self.simulate('\n'.join(body))
        self.assertEqual(report['checked_bytes'], 32768)

    def test_fifo_capacity_wrap_and_clear_preserves_ram(self):
        body = r'''
prefill;reset_state;enable=1;
for(addr=0;addr<2048;addr=addr+64) descriptor(addr,1);
if(dr) $fatal(1,"descriptor queue failed to backpressure at32");
for(addr=0;addr<2048;addr=addr+64) receive_descriptor(addr,1);
for(addr=2048;addr<4096;addr=addr+64) begin descriptor(addr,63);receive_descriptor(addr,63);end
check_good;reset_state;verify_ram;cases=64;
'''
        self.simulate(body)

    def test_full_256k_capacity_four_64k_reads(self):
        result = self.simulate(r'''
prefill;reset_state;enable=1;
for(addr=0;addr<CAP;addr=addr+65536) descriptor(addr,65536);
for(addr=0;addr<CAP;addr=addr+65536) receive_descriptor(addr,65536);
check_good;
if(committed!=4 || bytes!=262144 || commands!=64 || padding!=0) $fatal(1,"full capture counters wrong");
verify_ram;cases=4;
''', capacity=262144)
        self.assertEqual(result['checked_bytes'], 262144)

    def test_bad_descriptors_and_recovery(self):
        descriptors = [(0, 0), (0, 65537), (1, 64), (64, 64), (0, 32769)]
        body = ['prefill;']
        for address, length in descriptors:
            body += [f'reset_state;enable=1;descriptor({address},{length});',
                     'if(!fault || error_code!=1 || authorized!=0 || committed!=0) $fatal(1,"invalid descriptor admitted");']
        body += ['reset_state;lease=63;enable=1;descriptor(0,1);',
                 'if(!fault || error_code!=1) $fatal(1,"invalid lease admitted");',
                 'reset_state;lease=CAP+64;enable=1;descriptor(0,1);',
                 'if(!fault || error_code!=1) $fatal(1,"oversize lease admitted");',
                 'reset_state;lease=CAP;enable=1;descriptor(0,65);descriptor(64,1);',
                 'if(!fault || error_code!=1 || authorized!=1) $fatal(1,"overlapping slots admitted");',
                 'reset_state;enable=1;descriptor(0,65);receive_descriptor(0,65);check_good;verify_ram;cases=8;']
        self.simulate('\n'.join(body))

    def test_bad_command_address_length_qp_and_flags(self):
        # Every rejected command must leave all initialized RAM unchanged.
        mutations = ["cmd[47:0]=64;", "cmd[47:32]=1;", "cmd[75:48]=65;",
                     "cmd[93:84]=3;", "cmd[79]=0;", "cmd[76]=0;",
                     "cmd[77]=1;", "cmd[78]=1;", "cmd[80]=1;"]
        body = ['prefill;reset_state;enable=1;command(memory_command(0,68,1));',
                'if(!fault || error_code!=2) $fatal(1,"unleased command admitted");']
        for mutation in mutations:
            body += ['reset_state;enable=1;descriptor(0,65);cmd=memory_command(0,68,1);',
                     mutation, 'command(cmd);',
                     'if(!fault || error_code!=2 || commands!=0 || bytes!=0) $fatal(1,"bad command admitted");']
        body += ['verify_ram;cases=10;']
        self.simulate('\n'.join(body))

    def test_bad_keep_and_last_cannot_complete_or_write_bad_beat(self):
        body = ['prefill;']
        for last, bad_keep in [(1, 0), (0, 1)]:
            body += ['reset_state;enable=1;descriptor(0,65);command(memory_command(0,68,1));',
                     f'payload_beat(0,64,64,{last},{bad_keep});',
                     'if(!fault || error_code!=3 || bytes!=0 || committed!=0) $fatal(1,"bad first beat admitted");']
        body += ['reset_state;enable=1;descriptor(0,65);command(memory_command(0,68,1));',
                 'payload_beat(0,64,64,0,0);',
                 'for(j=0;j<64;j=j+1) expected[j]=pattern(j);',
                 'payload_beat(64,1,4,0,0);',
                 'if(!fault || error_code!=3 || bytes!=64 || committed!=0) $fatal(1,"missing last completed");',
                 'verify_ram;cases=3;']
        self.simulate('\n'.join(body))

    def test_host_alignment_range_byte_enables_and_stalled_payload(self):
        body = r'''
prefill;
host(0,1,32'h12345678,4'b0101,0);expected[0]=8'h78;expected[2]=8'h34;
host(1,1,32'hbad0bad0,4'hf,1);host(CAP,1,32'hbad0bad0,4'hf,1);
host(32'hfffffffc,0,0,0,1);
reset_state;enable=1;descriptor(0,1);
// Data may appear before its independent command channel: backpressure it.
@(negedge clk);valid=1;last=1;keep=15;data=512'hd3;
repeat(12) begin @(negedge clk);if(ready || bytes!=0 || committed!=0) $fatal(1,"uncommanded data consumed");end
command(memory_command(0,4,1));
@(posedge clk);if(!ready) $fatal(1,"command did not release payload");
@(negedge clk);valid=0;expected[0]=8'hd3;
if(committed!=0 || idle) $fatal(1,"reported completion before pending RAM write committed");
repeat(2) @(negedge clk);
if(fault || committed!=1 || bytes!=1 || padding!=3) $fatal(1,"stalled payload failed");
verify_ram;cases=5;
'''
        self.simulate(body)


if __name__ == '__main__':
    unittest.main()
