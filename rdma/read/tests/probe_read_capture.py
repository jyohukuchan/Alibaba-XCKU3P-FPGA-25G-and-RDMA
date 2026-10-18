#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Real generated HLS -> protected READ RAM -> byte-exact host-port readback.

Uses the independent wire oracle and the unchanged direct transport probe.
The host port here is an RTL driver, not PCIe hardware or an AXI-Lite app.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

import probe_read_transport as base

ROOT = base.ROOT
SINK_RTL = ROOT / 'rdma/read/rtl/rocev2_read_buffer.v'


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('transport probe dependency changed: ' + old)
    return text.replace(old, new, 1)


SINK = r'''
reg prefill_done=0,transport_done=0,capture_enable=0;
wire descriptor_ready,cmd_sink_ready,data_sink_ready;
wire buffer_fault,buffer_idle;
wire [7:0] buffer_error;
wire [31:0] authorized,committed,committed_bytes,padding_bytes,command_count;
reg [31:0] host_address=0,host_wdata=0;
reg host_write=0,host_valid=0,host_response_ready=0;
wire host_ready,host_response_valid,host_error;
wire [31:0] host_rdata;
wire command_gate=cycle>6000 && cycle>tx_end+400;
wire data_gate=cycle>6500 && cycle>tx_end+800;
assign cmd_ready=cmd_sink_ready && command_gate;
assign data_ready=data_sink_ready && data_gate;
rocev2_read_buffer sink (
 .clk(clk),.rst(rst),.clear(1'b0),.capture_enable(capture_enable),
 .local_qpn(10'd2),.lease_bytes((requested_bytes+32'd63)&~32'd63),
 .s_axis_desc_address(32'd0),.s_axis_desc_length(requested_bytes),
 .s_axis_desc_valid(sqv && sqr),.s_axis_desc_ready(descriptor_ready),
 .s_axis_cmd_tdata(cmd),.s_axis_cmd_tvalid(cmd_valid && cmd_ready),.s_axis_cmd_tready(cmd_sink_ready),
 .s_axis_tdata(data),.s_axis_tkeep(keep),.s_axis_tvalid(data_valid && data_ready),
 .s_axis_tready(data_sink_ready),.s_axis_tlast(data_last),
 .host_address(host_address),.host_write(host_write),.host_wdata(host_wdata),.host_wstrb(4'hf),
 .host_valid(host_valid),.host_ready(host_ready),.host_rdata(host_rdata),.host_error(host_error),
 .host_response_valid(host_response_valid),.host_response_ready(host_response_ready),
 .host_idle(),.idle(buffer_idle),.fault(buffer_fault),.error_code(buffer_error),
 .authorized_count(authorized),.committed_count(committed),.committed_bytes(committed_bytes),
 .padding_bytes(padding_bytes),.command_count(command_count));
integer address,hbyte,readback_bytes=0,sentinel_bytes=0,extent;
reg [7:0] expected_byte;
reg [31:0] saved_host;
task host_transaction;
 input [31:0] address;
 input write;
 begin
  @(negedge clk);host_address=address;host_wdata=32'ha5a5a5a5;host_write=write;host_valid=1;
  @(posedge clk);while(!host_ready) @(posedge clk);
  @(negedge clk);host_valid=0;
  while(!host_response_valid) @(negedge clk);
  if(host_error) $fatal(1,"host access failed addr=%0d",address);
  saved_host=host_rdata;
  repeat(2) begin
   @(negedge clk);
   if(!host_response_valid || host_error || host_rdata!==saved_host) $fatal(1,"host response unstable");
  end
  host_response_ready=1;@(negedge clk);host_response_ready=0;
 end
endtask
initial begin
 wait(!rst && cycle>8);
 extent=((requested_bytes+63)&~63)+64;
 for(address=0;address<extent;address=address+4) host_transaction(address,1);
 @(negedge clk);capture_enable=1;prefill_done=1;
 wait(transport_done);
 @(negedge clk);capture_enable=0;
 for(address=0;address<extent;address=address+4) begin
  host_transaction(address,0);
  for(hbyte=0;hbyte<4;hbyte=hbyte+1) begin
   if(address+hbyte<requested_bytes) begin
    expected_byte=((address+hbyte)*179)^((address+hbyte)>>7)^8'hd3;
    readback_bytes=readback_bytes+1;
   end else begin expected_byte=8'ha5;sentinel_bytes=sentinel_bytes+1;end
   if(saved_host[hbyte*8+:8]!==expected_byte)
    $fatal(1,"host readback mismatch at %0d got=%h expected=%h",address+hbyte,saved_host[hbyte*8+:8],expected_byte);
  end
 end
 if(buffer_fault || !buffer_idle || authorized!=1 || committed!=1 || committed_bytes!=requested_bytes ||
    padding_bytes!=((-requested_bytes)&3) || command_count!=packets)
  $fatal(1,"capture failed fault=%b code=%0d auth=%0d committed=%0d bytes=%0d pad=%0d cmd=%0d",
          buffer_fault,buffer_error,authorized,committed,committed_bytes,padding_bytes,command_count);
 $display("CAPTURE_RESULT {\"host_readback_bytes_verified\":%0d,\"untouched_sentinel_bytes_verified\":%0d,\"committed_operations\":%0d}",readback_bytes,sentinel_bytes,committed);
 $finish;
end
always @(posedge clk) if(!rst) begin
 if(buffer_fault) $fatal(1,"protected sink fault code=%0d",buffer_error);
 if(ack_valid && committed<1) $display("EARLY_ACK_CAPTURE_NOT_COMMITTED");
 if(sqv && sqr && !descriptor_ready) $fatal(1,"SQ accepted without capture descriptor capacity");
end
'''


def bench():
    tb = replace_once(base.TB, 'reg cmd_ready=0;', 'wire cmd_ready;')
    tb = replace_once(tb, 'reg data_ready=0;', 'wire data_ready;')
    tb = replace_once(tb, 'if(qdone && cdone && cycle>4200 && !sqdone)',
                      'if(prefill_done && qdone && cdone && cycle>4200 && !sqdone)')
    tb = replace_once(tb, ' cmd_ready=cycle>6000 && rng[5:3]!=0;\n', '')
    tb = replace_once(tb, ' data_ready=cycle>6500 && rng[8:6]!=0;\n', '')
    tb = replace_once(tb, 'if(quiet==100) begin', 'if(quiet==100 && !transport_done) begin')
    tb = replace_once(tb, '  $finish;', '  transport_done=1;')
    tb = replace_once(tb, 'if(cycle>30000)', 'if(cycle>300000)')
    return replace_once(tb, '\nendmodule\n', '\n' + SINK + '\nendmodule\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--hls-build', type=Path, required=True)
    parser.add_argument('--sizes', type=int, nargs='+', default=[65, 4097])
    parser.add_argument('--wall-timeout', type=int, default=600)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    rtl = args.hls_build.resolve() / 'solution1/syn/verilog'
    if args.report.exists() or any(not 1 <= n <= 65536 for n in args.sizes):
        parser.error('select a new report path and sizes1..65536')
    axis = ROOT / 'external/corundum/fpga/lib/eth/lib/axis/rtl'
    sources = sorted(rtl.glob('*.v')) + [ROOT / ('rdma/rtl/' + n) for n in
        ['rocev2_ipv4_icrc.v', 'rocev2_tx_padding.v', 'rocev2_integrity_transport.v']]
    sources += [SINK_RTL] + [axis / n for n in ['axis_adapter.v', 'axis_fifo.v', 'axis_register.v']]
    sources.append(ROOT / 'external/corundum/fpga/lib/eth/rtl/lfsr.v')
    results = []
    with tempfile.TemporaryDirectory(prefix='as02-read-capture-') as directory:
        path = Path(directory)
        (path / 'tb.v').write_text(bench())
        for dat in rtl.glob('*.dat'):
            shutil.copy2(dat, path / dat.name)
        compiled = subprocess.run(['iverilog', '-g2012', '-s', 'tb', '-o', str(path / 'test.vvp'),
                                  str(path / 'tb.v'), *map(str, sources)], capture_output=True, text=True, timeout=60)
        if compiled.returncode:
            raise RuntimeError(compiled.stderr)
        for size in args.sizes:
            payload = bytes((i * 179 ^ i >> 7 ^ 0xD3) & 255 for i in range(size))
            frames = base.wire.responses(payload, initial_psn=0xFFFFFE, source_ip='198.18.11.1',
                                         destination_ip='198.18.11.2', destination_qpn=2)
            stimulus = [w for frame in frames for w in base.words(frame[14:])]
            (path / 'input.hex').write_text(''.join(f'{w:037x}\n' for w in stimulus))
            sim = subprocess.run(['vvp', str(path / 'test.vvp'), f'+bytes={size}', f'+input_count={len(stimulus)}'],
                                 cwd=path, capture_output=True, text=True, timeout=args.wall_timeout)
            if sim.returncode or 'ERROR:' in sim.stdout:
                print(sim.stdout, flush=True)
                raise RuntimeError(sim.stderr or f'capture case{size} failed')
            result = base.parse(sim.stdout, payload)
            capture = [json.loads(line[15:]) for line in sim.stdout.splitlines() if line.startswith('CAPTURE_RESULT ')]
            if len(capture)!=1 or capture[0]['host_readback_bytes_verified']!=size:
                raise ValueError('missing byte-exact capture evidence')
            result.update(capture[0], protected_capture_used=True,
                          early_ack_before_commit_observed='EARLY_ACK_CAPTURE_NOT_COMMITTED' in sim.stdout)
            results.append(result)
            print(json.dumps(result), flush=True)
    generated = hashlib.sha256()
    for file in sorted([*rtl.glob('*.v'), *rtl.glob('*.dat')]):
        generated.update(file.name.encode() + b'\0' + file.read_bytes())
    dependencies = sources + [Path(__file__), Path(base.__file__), ROOT / 'rdma/read/host/read_wire.py',
        ROOT / 'rdma/host/rocev2_wire.py', ROOT / 'rdma/tests/test_icrc_rtl.py']
    report = dict(scope='Actual HLS/integrity/protected-RAM/host-port RTL; not AXI-Lite app or hardware',
                  hardware_verified=False,complete=True,cases=results,
                  generated_hls_sha256=generated.hexdigest(),
                  source_sha256={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest()
                                 for f in dependencies if f.is_relative_to(ROOT)})
    with args.report.open('x') as out:
        out.write(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
